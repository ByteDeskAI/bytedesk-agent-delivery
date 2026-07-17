#!/usr/bin/env python3
"""Verify a contract bundle using only the bundle, trust input, and local tools."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from tempfile import SpooledTemporaryFile, TemporaryDirectory
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - the reference ledger is POSIX-only
    fcntl = None  # type: ignore[assignment]

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable

from contractlib import (
    ContractToolError,
    canonical_digest,
    canonical_json,
    load_json_bytes,
    sha256_bytes,
    stable_file_digest,
    stable_read_bytes,
    strict_json_bytes,
    validation_error_key,
    write_bytes,
    write_json,
)
from bundle_profile import (
    CANONICAL_ARCHIVE_MEMORY_SPOOL_BYTES,
    MAX_BUNDLE_BYTES,
    MAX_BUNDLE_CONTENT_BYTES,
    MAX_BUNDLE_MEMBER_BYTES,
    MAX_BUNDLE_MEMBERS,
    BundleProfileError,
    normalized_member_payload,
    portable_path_collision_key,
    structured_control_member,
    validate_portable_path_set,
    write_deterministic_tar,
)
from build_bundle import validate_compatibility
from validate_schemas import (
    SCHEMA_INVENTORY_BUNDLE_PATH,
    all_errors,
    fixture_schema_descriptor_error,
    validate_denial_fixture_coverage,
    validate_fixture_index_document,
    validate_positive_fixture_coverage,
    validate_schema_inventory,
)


CONTRACT_BUNDLE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/contract-bundle/1.0.0"
)
SIGNING_REQUEST_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/signing-request/1.0.0"
)
VERIFICATION_RESULT_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0"
)
TRUST_POLICY_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy/1.0.0"
)
CONTRACT_BUNDLE_MEDIA_TYPE = "application/vnd.bytedesk.agent.contract-bundle.v1+json"
MAX_SIGNING_REQUEST_VALIDITY = timedelta(minutes=5)
MAX_SIGNATURE_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_EXTERNAL_VERIFIER_BYTES = 256 * 1024 * 1024
MAX_REPLAY_LEDGER_BYTES = 64 * 1024 * 1024
PINNED_REUSABLE_WORKFLOW_PATTERN = re.compile(
    r"^\.github/workflows/[A-Za-z0-9._-]+\.ya?ml@[0-9a-f]{40}$"
)
MANIFEST_ARCHIVE_PATH = "bundle/manifest.json"
REPOSITORY_ONLY_RELEASE_PATTERNS = (
    "contracts/schemas/repository/*.schema.json",
    "contracts/fixtures/schema/repository-index.json",
    "contracts/fixtures/schema/positive/development-plan__*.json",
    "contracts/fixtures/schema/negative/development-plan__*.json",
)


def safe_member_name(name: str) -> None:
    try:
        portable_path_collision_key(name)
    except BundleProfileError as error:
        raise ContractToolError(f"unsafe archive path: {error}") from error


def repository_only_release_path(path: str) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in REPOSITORY_ONLY_RELEASE_PATTERNS)


def structured_json_member(path: str) -> bool:
    """Resolve the closed path/role profile; suffix alone never grants a role."""

    try:
        return structured_control_member(path)
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error


def deterministic_archive_bytes(members: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    try:
        write_deterministic_tar(output, members)
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error
    return output.getvalue()


@dataclass(frozen=True)
class ArchiveSnapshot:
    members: dict[str, bytes]
    digest: str
    size: int


def read_archive_snapshot(path: Path) -> ArchiveSnapshot:
    raw = stable_read_bytes(
        path,
        description="bundle archive",
        maximum_bytes=MAX_BUNDLE_BYTES,
    )
    if raw.startswith(b"\x1f\x8b"):
        raise ContractToolError("compressed tar is not the deterministic v1 bundle format")
    members: dict[str, bytes] = {}
    cumulative_size = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            for position, info in enumerate(archive, start=1):
                if position > MAX_BUNDLE_MEMBERS:
                    raise ContractToolError("bundle archive exceeds the member-count limit")
                safe_member_name(info.name)
                if repository_only_release_path(info.name):
                    raise ContractToolError(
                        f"repository-only input is forbidden from release bundles: {info.name}"
                    )
                if info.name in members:
                    raise ContractToolError(f"duplicate archive member: {info.name}")
                if not info.isfile():
                    raise ContractToolError(f"non-regular archive member: {info.name}")
                if info.size > MAX_BUNDLE_MEMBER_BYTES:
                    raise ContractToolError(f"archive member exceeds the size limit: {info.name}")
                cumulative_size += info.size
                if cumulative_size > MAX_BUNDLE_CONTENT_BYTES:
                    raise ContractToolError("bundle archive exceeds the cumulative content limit")
                if (
                    info.mode != 0o444
                    or info.uid != 0
                    or info.gid != 0
                    or info.uname != ""
                    or info.gname != ""
                    or info.mtime != 0
                ):
                    raise ContractToolError(f"non-deterministic metadata on {info.name}")
                extracted = archive.extractfile(info)
                if extracted is None:
                    raise ContractToolError(f"cannot read archive member: {info.name}")
                payload = extracted.read(info.size + 1)
                if len(payload) != info.size:
                    raise ContractToolError(f"archive member size is inconsistent: {info.name}")
                members[info.name] = payload
    except (tarfile.TarError, OSError) as error:
        raise ContractToolError(f"invalid contract bundle tar: {error}") from error
    try:
        validate_portable_path_set(members, "archive member")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error
    if MANIFEST_ARCHIVE_PATH not in members:
        raise ContractToolError("bundle has no canonical manifest")
    with SpooledTemporaryFile(max_size=CANONICAL_ARCHIVE_MEMORY_SPOOL_BYTES) as canonical:
        try:
            write_deterministic_tar(canonical, members)
        except BundleProfileError as error:
            raise ContractToolError(str(error)) from error
        canonical.seek(0)
        offset = 0
        while True:
            expected = canonical.read(1024 * 1024)
            if not expected:
                break
            if raw[offset : offset + len(expected)] != expected:
                raise ContractToolError(
                    "archive bytes do not match the exact deterministic v1 tar encoding"
                )
            offset += len(expected)
        if offset != len(raw):
            raise ContractToolError(
                "archive bytes do not match the exact deterministic v1 tar encoding"
            )
    return ArchiveSnapshot(members=members, digest=sha256_bytes(raw), size=len(raw))


def read_archive(path: Path) -> dict[str, bytes]:
    """Compatibility wrapper for conformance tools that need only member bytes."""

    return read_archive_snapshot(path).members


def inventory_map(manifest: dict[str, Any], members: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}

    def add(entry: dict[str, Any]) -> None:
        path = entry["path"]
        if path in expected:
            raise ContractToolError(f"duplicate authenticated inventory path: {path}")
        expected[path] = entry

    for schema in manifest["schemas"]:
        entry = {
            "path": schema["path"],
            "digest": schema["digest"],
            "size": schema["size"],
            "mode": "0444",
        }
        add(entry)
    for entry in manifest["documents"]:
        add(entry)
    for name in ("fixtureIndex", "schemaInventory", "compatibility", "documentationMap"):
        entry = manifest[name]
        add(entry)

    fixture_index_path = manifest["fixtureIndex"]["path"]
    if fixture_index_path not in members:
        raise ContractToolError("fixture index is absent from archive")
    fixture_index = strict_json_bytes(members[fixture_index_path], fixture_index_path)
    fixtures = fixture_index.get("fixtures") if isinstance(fixture_index, dict) else None
    if not isinstance(fixtures, list):
        raise ContractToolError("fixture index has no fixtures array")
    for item in fixtures:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ContractToolError("fixture index contains an invalid path entry")
        fixture_path = item["path"]
        if fixture_path not in members:
            raise ContractToolError(f"indexed fixture is absent: {fixture_path}")
        if fixture_path not in expected:
            raise ContractToolError(
                f"indexed fixture lacks an authenticated document inventory entry: {fixture_path}"
            )
    return expected


def verify_inventory(manifest: dict[str, Any], members: dict[str, bytes]) -> None:
    expected = inventory_map(manifest, members)
    actual_paths = set(members) - {MANIFEST_ARCHIVE_PATH}
    if actual_paths != set(expected):
        missing = sorted(set(expected) - actual_paths)
        extra = sorted(actual_paths - set(expected))
        raise ContractToolError(f"archive inventory mismatch missing={missing} extra={extra}")
    for path, entry in expected.items():
        payload = members[path]
        if entry["mode"] != "0444":
            raise ContractToolError(f"unsupported inventory mode for {path}")
        if entry["size"] != len(payload) or entry["digest"] != sha256_bytes(payload):
            raise ContractToolError(f"inventory digest/size mismatch for {path}")
        value = strict_json_bytes(payload, path) if structured_json_member(path) else None
        try:
            normalized_payload = normalized_member_payload(path, payload)
        except BundleProfileError as error:
            raise ContractToolError(str(error)) from error
        if payload != normalized_payload:
            raise ContractToolError(
                f"structured control member is not exact RFC 8785 bytes: {path}"
            )


def verify_build_input_digest(manifest: dict[str, Any], members: dict[str, bytes]) -> None:
    expected = inventory_map(manifest, members)
    build_input = {
        "profile": "bytedesk.contract-bundle-build-input/1",
        "bundleVersion": manifest["bundleVersion"],
        "productVersion": manifest["productVersion"],
        "createdAt": manifest["createdAt"],
        "trustPolicy": manifest["trustPolicy"],
        "inputs": [expected[path] for path in sorted(expected)],
    }
    if manifest.get("buildInputDigest") != canonical_digest(build_input):
        raise ContractToolError("bundle buildInputDigest does not match authenticated inventory")


def validate_bundled_documentation_map(
    document: Any,
    schema_ids: set[str],
    member_paths: set[str],
) -> None:
    root_fields = {"profile", "documents", "schemas", "projections"}
    if not isinstance(document, dict) or set(document) != root_fields:
        raise ContractToolError("bundled documentation map root is not closed")
    if document["profile"] != "bytedesk.contract-documentation-map/1":
        raise ContractToolError("bundled documentation map has an invalid profile")

    inventory = document["documents"]
    if not isinstance(inventory, list) or not inventory:
        raise ContractToolError("bundled documentation map has no documentation inventory")
    inventory_paths: list[str] = []
    for entry in inventory:
        if not isinstance(entry, dict) or set(entry) != {"path", "digest"}:
            raise ContractToolError(
                "bundled documentation map documentation inventory entry is not closed"
            )
        path = entry["path"]
        digest = entry["digest"]
        if not isinstance(path, str) or not path:
            raise ContractToolError(
                "bundled documentation map documentation inventory path is invalid"
            )
        try:
            portable_path_collision_key(path)
        except BundleProfileError as error:
            raise ContractToolError(
                f"bundled documentation inventory path is not portable: {error}"
            ) from error
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        ):
            raise ContractToolError(
                "bundled documentation map documentation inventory digest is invalid"
            )
        inventory_paths.append(path)
    if inventory_paths != sorted(set(inventory_paths)):
        raise ContractToolError(
            "bundled documentation map documentation inventory is not strictly sorted and unique"
        )
    try:
        validate_portable_path_set(inventory_paths, "documentation inventory")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error

    schema_entries = document["schemas"]
    if not isinstance(schema_entries, list) or not schema_entries:
        raise ContractToolError("bundled documentation map has no schema entries")
    mapped_ids: list[str] = []
    documentation_paths: list[str] = []
    for entry in schema_entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "documents"}:
            raise ContractToolError("bundled documentation schema entry is not closed")
        if not isinstance(entry["id"], str) or not entry["id"]:
            raise ContractToolError("bundled documentation schema ID is invalid")
        documents = entry["documents"]
        if (
            not isinstance(documents, list)
            or not documents
            or not all(isinstance(path, str) and path for path in documents)
            or len(documents) != len(set(documents))
        ):
            raise ContractToolError("bundled documentation path list is invalid")
        mapped_ids.append(entry["id"])
        documentation_paths.extend(documents)
    if len(mapped_ids) != len(set(mapped_ids)) or set(mapped_ids) != schema_ids:
        raise ContractToolError("bundled documentation schema inventory differs from bundle")
    try:
        for path in documentation_paths:
            portable_path_collision_key(path)
    except BundleProfileError as error:
        raise ContractToolError(f"bundled documentation path is not portable: {error}") from error
    referenced_documentation_paths = set(documentation_paths)
    inventoried_documentation_paths = set(inventory_paths)
    if referenced_documentation_paths != inventoried_documentation_paths:
        missing_inventory = sorted(
            referenced_documentation_paths - inventoried_documentation_paths
        )
        unreferenced_inventory = sorted(
            inventoried_documentation_paths - referenced_documentation_paths
        )
        raise ContractToolError(
            "bundled documentation map documentation reference closure differs "
            f"missingInventory={missing_inventory} "
            f"unreferencedInventory={unreferenced_inventory}"
        )

    projections = document["projections"]
    if not isinstance(projections, list) or not projections:
        raise ContractToolError("bundled documentation map has no projections")
    projection_paths: list[str] = []
    for entry in projections:
        if not isinstance(entry, dict) or set(entry) != {"path", "source", "role"}:
            raise ContractToolError("bundled documentation projection entry is not closed")
        path = entry["path"]
        source = entry["source"]
        if entry["role"] not in {
            "http-projection",
            "event-projection",
            "notification-registry",
        }:
            raise ContractToolError("bundled documentation projection role is invalid")
        try:
            portable_path_collision_key(path)
            portable_path_collision_key(source.rstrip("/"))
        except (AttributeError, BundleProfileError) as error:
            raise ContractToolError("bundled documentation projection path is invalid") from error
        if path not in member_paths:
            raise ContractToolError(f"bundled documentation projection is absent: {path}")
        if source.endswith("/"):
            if not any(member.startswith(source) for member in member_paths):
                raise ContractToolError(f"bundled documentation projection source is absent: {source}")
        elif source not in member_paths:
            raise ContractToolError(f"bundled documentation projection source is absent: {source}")
        projection_paths.append(path)
    try:
        validate_portable_path_set(projection_paths, "documentation projection")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error


def validate_authenticated_bundle_semantics(
    manifest: dict[str, Any],
    members: dict[str, bytes],
    registry: Any,
    schemas: dict[str, tuple[str, Any]],
) -> None:
    fixture_path = manifest["fixtureIndex"]["path"]
    fixture_index = strict_json_bytes(members[fixture_path], fixture_path)
    fixtures = validate_fixture_index_document(fixture_index)
    validate_positive_fixture_coverage(fixtures, schemas)
    validate_denial_fixture_coverage(fixtures, schemas)  # type: ignore[arg-type]

    seen_fixture_paths: set[str] = set()
    for item in fixtures:
        fixture_path = item["path"]
        if fixture_path in seen_fixture_paths:
            raise ContractToolError(f"duplicate bundled fixture path: {fixture_path}")
        seen_fixture_paths.add(fixture_path)
        try:
            portable_path_collision_key(fixture_path)
        except BundleProfileError as error:
            raise ContractToolError(f"bundled fixture path is not portable: {error}") from error
        schema_id = item["schemaId"]
        if schema_id not in schemas:
            raise ContractToolError(f"bundled fixture references unknown schema: {schema_id}")
        payload = members.get(fixture_path)
        if payload is None:
            raise ContractToolError(f"bundled fixture is absent: {fixture_path}")
        instance = strict_json_bytes(payload, fixture_path)
        expected_semantic_error = item.get("expectedSemanticError")
        observed_semantic_error = fixture_schema_descriptor_error(
            instance,
            schema_id,
            canonical_digest(schemas[schema_id][1]),
        )
        if observed_semantic_error != expected_semantic_error:
            raise ContractToolError(
                f"bundled fixture descriptor result mismatch: {fixture_path}: "
                f"expected {expected_semantic_error!r}, observed {observed_semantic_error!r}"
            )
        errors = sorted(
            Draft202012Validator(
                schemas[schema_id][1],
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            ).iter_errors(instance),
            key=validation_error_key,
        )
        if item["valid"] is True and errors:
            raise ContractToolError(
                f"bundled valid fixture was rejected: {fixture_path}: {errors[0].message}"
            )
        if expected_semantic_error is not None and errors:
            raise ContractToolError(
                f"bundled semantic denial fixture also failed structural validation: "
                f"{fixture_path}: {errors[0].message}"
            )
        if item["valid"] is False and expected_semantic_error is None and not errors:
            raise ContractToolError(f"bundled denial fixture was accepted: {fixture_path}")
        expected_keywords = item["expectedKeyword"]
        if isinstance(expected_keywords, str):
            expected_keywords = [expected_keywords]
        observed_keywords = {
            nested.validator
            for error in errors
            for nested in all_errors(error)
            if isinstance(nested.validator, str)
        }
        missing_keywords = sorted(set(expected_keywords) - observed_keywords)
        if missing_keywords:
            raise ContractToolError(
                f"bundled denial fixture missed expected keywords {missing_keywords}: {fixture_path}"
            )

    compatibility_path = manifest["compatibility"]["path"]
    validate_compatibility(strict_json_bytes(members[compatibility_path], compatibility_path))
    documentation_path = manifest["documentationMap"]["path"]
    validate_bundled_documentation_map(
        strict_json_bytes(members[documentation_path], documentation_path),
        set(schemas),
        set(members),
    )


def iter_references(value: Any) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str):
                yield child
            else:
                yield from iter_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_references(child)


def build_bundle_registry(
    manifest: dict[str, Any],
    members: dict[str, bytes],
    expected_policy: dict[str, str],
) -> tuple[Registry, dict[str, tuple[str, Any]]]:
    """Build schema authority exclusively from authenticated bundle members."""

    entries = manifest.get("schemas")
    if not isinstance(entries, list) or not entries:
        raise ContractToolError("bundle manifest has no schema inventory")
    expected_entry_keys = {
        "id",
        "logicalContract",
        "version",
        "path",
        "mediaType",
        "size",
        "digest",
        "trustPolicy",
    }
    resources: list[tuple[str, Resource]] = []
    schemas: dict[str, tuple[str, Any]] = {}
    seen_paths: set[str] = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != expected_entry_keys:
            raise ContractToolError(f"schema inventory entry {position} is not closed")
        schema_id = entry.get("id")
        schema_path = entry.get("path")
        if not isinstance(schema_id, str) or not schema_id.startswith(
            "https://schemas.bytedesk.ai/agent-delivery/v1/"
        ):
            raise ContractToolError(f"schema inventory entry {position} has an invalid stable ID")
        if (
            not isinstance(schema_path, str)
            or not schema_path.startswith("contracts/schemas/v1/")
            or not schema_path.endswith(".schema.json")
        ):
            raise ContractToolError(f"schema inventory entry {position} has an invalid schema path")
        safe_member_name(schema_path)
        if schema_id in schemas:
            raise ContractToolError(f"duplicate bundled schema ID: {schema_id}")
        if schema_path in seen_paths:
            raise ContractToolError(f"duplicate bundled schema path: {schema_path}")
        seen_paths.add(schema_path)
        if entry.get("mediaType") != "application/schema+json":
            raise ContractToolError(f"bundled schema has the wrong media type: {schema_id}")
        if entry.get("trustPolicy") != expected_policy:
            raise ContractToolError(f"bundled schema has a different trust policy: {schema_id}")
        payload = members.get(schema_path)
        if payload is None:
            raise ContractToolError(f"bundled schema member is absent: {schema_path}")
        if entry.get("size") != len(payload) or entry.get("digest") != sha256_bytes(payload):
            raise ContractToolError(f"bundled schema inventory mismatch: {schema_id}")
        schema = strict_json_bytes(payload, schema_path)
        if not isinstance(schema, dict):
            raise ContractToolError(f"bundled schema root is not an object: {schema_id}")
        if payload != canonical_json(schema):
            raise ContractToolError(f"bundled schema is not exact RFC 8785 bytes: {schema_id}")
        if schema.get("$id") != schema_id:
            raise ContractToolError(f"bundled schema $id does not match its inventory: {schema_id}")
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise ContractToolError(f"bundled schema uses the wrong dialect: {schema_id}")
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
        except (SchemaError, ValueError) as error:
            raise ContractToolError(f"invalid bundled Draft 2020-12 schema {schema_id}: {error}") from error
        schemas[schema_id] = (schema_path, schema)
        resources.append((schema_id, resource))

    inventory_entry = manifest.get("schemaInventory")
    inventory_fields = {"path", "digest", "size", "mode"}
    if not isinstance(inventory_entry, dict) or set(inventory_entry) != inventory_fields:
        raise ContractToolError("bundle manifest schemaInventory entry is not closed")
    inventory_path = inventory_entry.get("path")
    if inventory_path != SCHEMA_INVENTORY_BUNDLE_PATH:
        raise ContractToolError("bundle manifest names a noncanonical schema inventory path")
    inventory_payload = members.get(inventory_path)
    if inventory_payload is None:
        raise ContractToolError("bundled closed schema inventory is absent")
    if (
        inventory_entry.get("mode") != "0444"
        or inventory_entry.get("size") != len(inventory_payload)
        or inventory_entry.get("digest") != sha256_bytes(inventory_payload)
    ):
        raise ContractToolError("bundled closed schema inventory digest or size differs")
    inventory_document = strict_json_bytes(inventory_payload, inventory_path)
    if inventory_payload != canonical_json(inventory_document):
        raise ContractToolError("bundled closed schema inventory is not exact RFC 8785 bytes")
    validate_schema_inventory(
        inventory_document,
        schemas,
        inventory_path=inventory_path,
    )

    required_ids = {
        CONTRACT_BUNDLE_SCHEMA_ID,
        SIGNING_REQUEST_SCHEMA_ID,
        TRUST_POLICY_SCHEMA_ID,
        VERIFICATION_RESULT_SCHEMA_ID,
        "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0",
    }
    missing_ids = sorted(required_ids - set(schemas))
    if missing_ids:
        raise ContractToolError(f"bundle omits verifier-required schemas: {missing_ids}")
    manifest_descriptor = {
        "id": CONTRACT_BUNDLE_SCHEMA_ID,
        "digest": canonical_digest(schemas[CONTRACT_BUNDLE_SCHEMA_ID][1]),
    }
    if manifest.get("schema") != manifest_descriptor:
        raise ContractToolError("manifest schema descriptor does not match its bundled schema")

    registry = Registry().with_resources(resources)
    for schema_id, (_, schema) in schemas.items():
        try:
            resolver = registry.resolver(schema_id)
            for reference in iter_references(schema):
                resolver.lookup(reference)
            Draft202012Validator(
                schema,
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )
        except (NoSuchResource, Unresolvable) as error:
            raise ContractToolError(
                f"offline bundled reference from {schema_id} is unresolved: {error}"
            ) from error
    return registry, schemas


def load_canonical_request(path: Path) -> tuple[dict[str, Any], bytes]:
    request, payload = load_json_bytes(path)
    if not isinstance(request, dict) or payload != canonical_json(request):
        raise ContractToolError("signing request is not an exact RFC 8785 object")
    return request, payload


def parse_timestamp(value: str, description: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ContractToolError(f"{description} is not a valid date-time") from error
    if parsed.tzinfo is None:
        raise ContractToolError(f"{description} must include an offset")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class TrustEvaluation:
    policy_digest: str
    certificate_identity: str
    certificate_oidc_issuer: str
    certificate_audience: str
    workload_identity: str
    workflow: str
    source_repository: str
    source_ref: str
    environment: str
    builder_digest: str | None


def load_canonical_trust_policy(path: Path) -> tuple[dict[str, Any], bytes]:
    policy, payload = load_json_bytes(path)
    if not isinstance(policy, dict) or payload != canonical_json(policy):
        raise ContractToolError("trust policy snapshot is not an exact RFC 8785 object")
    return policy, payload


def preflight_trust_policy(
    policy: dict[str, Any],
    policy_bytes: bytes,
    *,
    expected_policy: dict[str, str],
    request: dict[str, Any],
    manifest: dict[str, Any],
    verification_time: str,
    available_evidence: set[str],
) -> TrustEvaluation:
    """Evaluate the closed product-release policy without artifact code/data.

    The policy snapshot is independently supplied and pinned by its raw
    canonical digest. This procedural profile runs before signature adapter
    invocation; the bundled schema and exact schema descriptor are checked
    after authentication by :func:`evaluate_trust_policy`.
    """

    root_fields = {
        "contract",
        "schema",
        "policyId",
        "version",
        "effective",
        "scope",
        "signers",
        "requiredEvidence",
        "rules",
        "revocations",
        "failureMode",
        "predecessor",
    }
    if set(policy) != root_fields:
        raise ContractToolError("trust policy preflight object is not closed")
    if policy.get("contract") != "bytedesk.trust-policy/1":
        raise ContractToolError("trust policy contract is invalid")
    policy_digest = sha256_bytes(policy_bytes)
    if policy_digest != expected_policy["digest"]:
        raise ContractToolError("trust policy bytes do not match the independent expected digest")
    if policy.get("policyId") != expected_policy["id"]:
        raise ContractToolError("trust policy ID does not match independent input")
    if not isinstance(policy.get("schema"), dict) or set(policy["schema"]) != {
        "id",
        "digest",
    }:
        raise ContractToolError("trust policy schema descriptor is not closed")
    if policy["schema"].get("id") != TRUST_POLICY_SCHEMA_ID:
        raise ContractToolError("trust policy schema descriptor has the wrong ID")
    if policy.get("failureMode") != "fail_closed":
        raise ContractToolError("trust policy is not fail closed")

    effective = policy.get("effective")
    if not isinstance(effective, dict) or set(effective) != {"notBefore", "notAfter"}:
        raise ContractToolError("trust policy effective window is not closed")
    evaluated_at = parse_timestamp(verification_time, "verification time")
    not_before = parse_timestamp(effective["notBefore"], "policy notBefore")
    not_after = parse_timestamp(effective["notAfter"], "policy notAfter")
    if not_before >= not_after or evaluated_at < not_before or evaluated_at >= not_after:
        raise ContractToolError("trust policy is not effective at verification time")

    scope = policy.get("scope")
    allowed_scope_fields = {"repositories", "mediaTypes", "purposes", "consumers", "targets"}
    if (
        not isinstance(scope, dict)
        or not {"repositories", "mediaTypes", "purposes"}.issubset(scope)
        or not set(scope).issubset(allowed_scope_fields)
        or not all(isinstance(scope[field], list) for field in scope)
    ):
        raise ContractToolError("trust policy scope is not a closed array profile")
    if request["repository"] not in scope["repositories"]:
        raise ContractToolError("signing request repository is outside trust-policy scope")
    if request["mediaType"] not in scope["mediaTypes"]:
        raise ContractToolError("signing request media type is outside trust-policy scope")
    if request["purpose"] not in scope["purposes"]:
        raise ContractToolError("signing request purpose is outside trust-policy scope")

    signers = policy.get("signers")
    if not isinstance(signers, list):
        raise ContractToolError("trust policy signers must be an array")
    signer_matches: list[dict[str, Any]] = []
    signer_fields = {"purpose", "keyVersion", "algorithm", "workloadIdentity", "claims"}
    for signer in signers:
        if not isinstance(signer, dict) or set(signer) != signer_fields:
            raise ContractToolError("trust policy signer is not closed")
        if (
            signer.get("purpose") == request["purpose"]
            and signer.get("keyVersion") == request["keyVersion"]
        ):
            signer_matches.append(signer)
    if len(signer_matches) != 1:
        raise ContractToolError("trust policy does not select exactly one signer")
    signer = signer_matches[0]
    if signer["algorithm"] != "ECDSA_P256_SHA256":
        raise ContractToolError("trust policy signer algorithm is unsupported")
    claims = signer["claims"]
    required_claims = {
        "issuer",
        "audience",
        "subject",
        "repository",
        "workflow",
        "ref",
        "environment",
    }
    allowed_claims = required_claims | {"builderDigest"}
    if not isinstance(claims, dict) or not required_claims.issubset(claims) or not set(
        claims
    ).issubset(allowed_claims):
        raise ContractToolError("product-release signer claims are incomplete or open")
    if not all(isinstance(claims[field], str) and claims[field] for field in required_claims):
        raise ContractToolError("product-release signer claim values are invalid")
    if not isinstance(signer["workloadIdentity"], str) or not signer["workloadIdentity"]:
        raise ContractToolError("product-release signer workload identity is invalid")
    if PINNED_REUSABLE_WORKFLOW_PATTERN.fullmatch(claims["workflow"]) is None:
        raise ContractToolError(
            "product-release signer workflow must be an exact SHA-pinned reusable workflow"
        )
    if not claims["ref"].startswith("refs/tags/v"):
        raise ContractToolError("product-release signer ref is not an immutable release-tag profile")
    if f":environment:{claims['environment']}" not in claims["subject"]:
        raise ContractToolError("product-release signer subject does not bind its environment")
    certificate_identity = f"https://github.com/{claims['repository']}/{claims['workflow']}"
    if signer["workloadIdentity"] != certificate_identity:
        raise ContractToolError(
            "product-release workload identity must equal the authenticated Fulcio SAN URI"
        )

    rules = policy.get("rules")
    rule_fields = {
        "freshnessSeconds",
        "requireNonce",
        "requirePredecessor",
        "denyDowngrade",
        "withdrawal",
        "outage",
    }
    if not isinstance(rules, dict) or set(rules) != rule_fields:
        raise ContractToolError("trust policy rules are not closed")
    if rules["requireNonce"] is not True or not isinstance(rules["freshnessSeconds"], int):
        raise ContractToolError("product-release trust policy must require bounded nonce freshness")
    issued_at = parse_timestamp(request["issuedAt"], "signing request issuedAt")
    if evaluated_at < issued_at or (
        evaluated_at - issued_at
    ).total_seconds() > rules["freshnessSeconds"]:
        raise ContractToolError("signing request exceeds trust-policy freshness")

    required_evidence = policy.get("requiredEvidence")
    if not isinstance(required_evidence, list) or not all(
        isinstance(item, str) for item in required_evidence
    ):
        raise ContractToolError("trust policy required evidence is invalid")
    missing_evidence = sorted(set(required_evidence) - available_evidence)
    if missing_evidence:
        raise ContractToolError(
            f"contract-bundle verification lacks trust-policy evidence: {missing_evidence}"
        )

    revocations = policy.get("revocations")
    revocation_fields = {
        "keyVersions",
        "digests",
        "workflows",
        "builders",
        "schemas",
        "renderers",
        "content",
    }
    if (
        not isinstance(revocations, dict)
        or set(revocations) != revocation_fields
        or not all(isinstance(revocations[field], list) for field in revocation_fields)
    ):
        raise ContractToolError("trust policy revocations are not closed arrays")
    if request["keyVersion"] in revocations["keyVersions"]:
        raise ContractToolError("trust policy revokes the signing key version")
    if claims["workflow"] in revocations["workflows"]:
        raise ContractToolError("trust policy revokes the signing workflow")
    builder_digest = claims.get("builderDigest")
    if builder_digest is not None and (
        not isinstance(builder_digest, str) or builder_digest in revocations["builders"]
    ):
        raise ContractToolError("trust policy revokes or invalidates the signing builder")
    manifest_digest = sha256_bytes(canonical_json(manifest))
    if manifest_digest in revocations["digests"] or manifest_digest in revocations["content"]:
        raise ContractToolError("trust policy revokes the contract bundle manifest")
    schema_entries = manifest.get("schemas")
    if not isinstance(schema_entries, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("digest"), str)
        for entry in schema_entries
    ):
        raise ContractToolError("bundle manifest schema inventory is invalid during policy preflight")
    revoked_schemas = set(revocations["schemas"])
    if any(entry["digest"] in revoked_schemas for entry in schema_entries):
        raise ContractToolError("trust policy revokes a bundled schema")

    return TrustEvaluation(
        policy_digest=policy_digest,
        certificate_identity=certificate_identity,
        certificate_oidc_issuer=claims["issuer"],
        certificate_audience=claims["audience"],
        workload_identity=signer["workloadIdentity"],
        workflow=claims["workflow"],
        source_repository=claims["repository"],
        source_ref=claims["ref"],
        environment=claims["environment"],
        builder_digest=builder_digest,
    )


def evaluate_trust_policy(
    policy: dict[str, Any],
    policy_bytes: bytes,
    *,
    expected_policy: dict[str, str],
    request: dict[str, Any],
    manifest: dict[str, Any],
    verification_time: str,
    available_evidence: set[str],
    registry: Any,
    schemas: dict[str, tuple[str, Any]],
) -> TrustEvaluation:
    expected_schema = {
        "id": TRUST_POLICY_SCHEMA_ID,
        "digest": canonical_digest(schemas[TRUST_POLICY_SCHEMA_ID][1]),
    }
    if policy.get("schema") != expected_schema:
        raise ContractToolError("trust policy uses a stale schema descriptor")
    errors = sorted(
        Draft202012Validator(
            schemas[TRUST_POLICY_SCHEMA_ID][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(policy),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"trust policy schema denial: {errors[0].message}")
    return preflight_trust_policy(
        policy,
        policy_bytes,
        expected_policy=expected_policy,
        request=request,
        manifest=manifest,
        verification_time=verification_time,
        available_evidence=available_evidence,
    )


def validate_signing_request_bindings(
    request: dict[str, Any],
    manifest_bytes: bytes,
    expected: dict[str, Any],
    verification_time: str,
) -> str:
    """Validate the closed security bindings without artifact-provided schemas.

    This preflight is deliberately independent from the bundled schema registry
    so an external verifier can authenticate the exact canonical request before
    evaluating any regular expression or reference supplied by the artifact.
    Full Draft 2020-12 and exact-descriptor validation still follows after the
    signature succeeds.
    """

    required_fields = {
        "contract",
        "schema",
        "requestId",
        "purpose",
        "keyVersion",
        "repository",
        "digest",
        "mediaType",
        "trustPolicy",
        "nonce",
        "issuedAt",
        "expiresAt",
    }
    if set(request) != required_fields:
        raise ContractToolError("signing request preflight object is not closed")
    if request.get("contract") != "bytedesk.signing-request/1":
        raise ContractToolError("signing request contract is invalid")
    if not isinstance(request.get("schema"), dict) or set(request["schema"]) != {
        "id",
        "digest",
    }:
        raise ContractToolError("signing request schema descriptor is not closed")
    exact_fields = {
        "requestId": expected["requestId"],
        "purpose": expected["purpose"],
        "keyVersion": expected["keyVersion"],
        "repository": expected["repository"],
        "digest": sha256_bytes(manifest_bytes),
        "mediaType": CONTRACT_BUNDLE_MEDIA_TYPE,
        "trustPolicy": expected["trustPolicy"],
        "nonce": expected["nonce"],
        "issuedAt": expected["issuedAt"],
        "expiresAt": expected["expiresAt"],
    }
    for field, value in exact_fields.items():
        if request.get(field) != value:
            raise ContractToolError(f"signing request {field} does not match independent input")
    if request.get("purpose") != "product-release-v1":
        raise ContractToolError("contract bundles require product-release-v1 signing purpose")

    issued_at = parse_timestamp(request["issuedAt"], "signing request issuedAt")
    expires_at = parse_timestamp(request["expiresAt"], "signing request expiresAt")
    evaluated_at = parse_timestamp(verification_time, "verification time")
    if issued_at >= expires_at:
        raise ContractToolError("signing request validity window is empty or reversed")
    if expires_at - issued_at > MAX_SIGNING_REQUEST_VALIDITY:
        raise ContractToolError("signing request validity exceeds the five-minute profile")
    if evaluated_at < issued_at or evaluated_at >= expires_at:
        raise ContractToolError("signing request is not current at verification time")
    return canonical_digest(request)


def validate_signing_request(
    request: dict[str, Any],
    manifest_bytes: bytes,
    expected: dict[str, Any],
    verification_time: str,
    registry: Any,
    schemas: dict[str, tuple[str, Any]],
) -> str:
    request_errors = sorted(
        Draft202012Validator(
            schemas[SIGNING_REQUEST_SCHEMA_ID][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(request),
        key=validation_error_key,
    )
    if request_errors:
        raise ContractToolError(f"signing request schema denial: {request_errors[0].message}")
    expected_request_schema = {
        "id": SIGNING_REQUEST_SCHEMA_ID,
        "digest": canonical_digest(schemas[SIGNING_REQUEST_SCHEMA_ID][1]),
    }
    if request.get("schema") != expected_request_schema:
        raise ContractToolError("signing request uses a stale schema descriptor")
    return validate_signing_request_bindings(
        request,
        manifest_bytes,
        expected,
        verification_time,
    )


def replay_ledger_entry_bytes(
    *,
    request_id: str,
    nonce: str,
    request_digest: str,
    verified_at: str,
) -> bytes:
    entry = {
        "profile": "bytedesk.signing-request-replay-ledger-entry/1",
        "requestId": request_id,
        "nonce": nonce,
        "requestDigest": request_digest,
        "verifiedAt": verified_at,
    }
    return canonical_json(entry)


def consume_replay_ledger(
    path: Path,
    *,
    request_id: str,
    nonce: str,
    request_digest: str,
    verified_at: str,
) -> str:
    """TEST ONLY: append one verification to a non-global local ledger.

    This adapter exists only for deterministic conformance. It is not a
    production or cross-host replay authority. Production must implement the
    same three uniqueness keys in one transactional durable datastore.
    """

    if fcntl is None:
        raise ContractToolError("the append-only file replay ledger requires POSIX file locks")
    entry_bytes = replay_ledger_entry_bytes(
        request_id=request_id,
        nonce=nonce,
        request_digest=request_digest,
        verified_at=verified_at,
    )
    entry = strict_json_bytes(entry_bytes, "new replay ledger entry")
    path = path.absolute()
    try:
        parent = path.parent.resolve(strict=True)
        parent_metadata = parent.stat()
    except OSError as error:
        raise ContractToolError(f"cannot resolve local test replay directory: {error}") from error
    if parent != path.parent:
        raise ContractToolError("local test replay directory contains a symbolic-link component")
    if parent_metadata.st_uid != os.geteuid() or stat.S_IMODE(parent_metadata.st_mode) & 0o022:
        raise ContractToolError("local test replay directory must be owner-controlled and non-writable by peers")
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise ContractToolError(f"cannot open replay ledger safely: {error}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ContractToolError("replay ledger must be a regular file")
        if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ContractToolError("local test replay ledger must be owner-only mode 0600")
        if metadata.st_nlink != 1:
            raise ContractToolError("local test replay ledger must have exactly one link")
        with os.fdopen(descriptor, "r+b", buffering=0, closefd=False) as ledger:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked_metadata = os.fstat(descriptor)
            try:
                named_metadata = os.stat(path, follow_symlinks=False)
            except OSError as error:
                raise ContractToolError("local test replay ledger path changed after open") from error
            if (locked_metadata.st_dev, locked_metadata.st_ino) != (
                named_metadata.st_dev,
                named_metadata.st_ino,
            ):
                raise ContractToolError("local test replay ledger path does not name the locked file")
            if locked_metadata.st_size > MAX_REPLAY_LEDGER_BYTES:
                raise ContractToolError("local test replay ledger exceeds its byte limit")
            ledger.seek(0)
            payload = ledger.read(MAX_REPLAY_LEDGER_BYTES + 1)
            if len(payload) > MAX_REPLAY_LEDGER_BYTES:
                raise ContractToolError("local test replay ledger exceeds its byte limit")
            if payload and not payload.endswith(b"\n"):
                raise ContractToolError("replay ledger has an incomplete trailing entry")
            for line_number, line in enumerate(payload.splitlines(), start=1):
                previous = strict_json_bytes(line, f"replay ledger line {line_number}")
                if not isinstance(previous, dict) or set(previous) != set(entry):
                    raise ContractToolError(
                        f"replay ledger line {line_number} is not a closed ledger entry"
                    )
                if line != canonical_json(previous):
                    raise ContractToolError(
                        f"replay ledger line {line_number} is not canonical JSON"
                    )
                if previous.get("profile") != entry["profile"]:
                    raise ContractToolError(
                        f"replay ledger line {line_number} uses an unknown profile"
                    )
                if not all(
                    isinstance(previous.get(field), str) and previous[field]
                    for field in ("requestId", "nonce", "requestDigest", "verifiedAt")
                ) or not (
                    len(previous["requestDigest"]) == 71
                    and previous["requestDigest"].startswith("sha256:")
                    and all(
                        character in "0123456789abcdef"
                        for character in previous["requestDigest"][7:]
                    )
                ):
                    raise ContractToolError(
                        f"replay ledger line {line_number} has invalid field types"
                    )
                parse_timestamp(previous["verifiedAt"], f"replay ledger line {line_number} verifiedAt")
                repeated = sorted(
                    field
                    for field in ("requestId", "nonce", "requestDigest")
                    if previous.get(field) == entry[field]
                )
                if repeated:
                    raise ContractToolError(
                        f"signing request replay denied by ledger keys: {repeated}"
                    )
            appended = entry_bytes + b"\n"
            if locked_metadata.st_size + len(appended) > MAX_REPLAY_LEDGER_BYTES:
                raise ContractToolError("local test replay ledger has no remaining capacity")
            written = 0
            while written < len(appended):
                count = ledger.write(appended[written:])
                if count is None or count <= 0:
                    raise ContractToolError("short write to local test replay ledger")
                written += count
            os.fsync(descriptor)
            directory_descriptor = os.open(parent, os.O_RDONLY | os.O_CLOEXEC)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    return sha256_bytes(entry_bytes)


def verify_ephemeral_signature(request: dict[str, Any], signature: dict[str, Any]) -> None:
    if signature.get("profile") != "bytedesk.test-ephemeral-signature/1" or signature.get(
        "warning"
    ) != "test-only-not-production-release-evidence":
        raise ContractToolError("not an explicit ephemeral test signature")
    if signature.get("requestDigest") != canonical_digest(request):
        raise ContractToolError("test signature request digest mismatch")
    try:
        public_key = serialization.load_der_public_key(
            base64.b64decode(signature["publicKeySpkiDer"], validate=True)
        )
        signed = base64.b64decode(signature["signatureDer"], validate=True)
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
            public_key.curve, ec.SECP256R1
        ):
            raise ContractToolError("test signature key is not ECDSA P-256")
        public_key.verify(signed, canonical_json(request), ec.ECDSA(hashes.SHA256()))
    except (KeyError, ValueError, TypeError, InvalidSignature) as error:
        raise ContractToolError(f"ephemeral test signature is invalid: {error}") from error


def verify_test_signature(
    request: dict[str, Any],
    request_bytes: bytes,
    signature_path: Path,
    manifest_bytes: bytes,
    expected: dict[str, Any],
    verification_time: str,
) -> tuple[str, str]:
    signature, signature_bytes = load_json_bytes(signature_path)
    if not isinstance(signature, dict):
        raise ContractToolError("test signature envelope is not an object")
    if request_bytes != canonical_json(request):
        raise ContractToolError("test signing request snapshot is not canonical")
    verify_ephemeral_signature(request, signature)
    return (
        validate_signing_request_bindings(
            request,
            manifest_bytes,
            expected,
            verification_time,
        ),
        sha256_bytes(signature_bytes),
    )


def verify_sigstore_signature(
    request: dict[str, Any],
    request_bytes: bytes,
    sigstore_bundle_path: Path,
    trusted_root_path: Path,
    manifest_bytes: bytes,
    expected: dict[str, Any],
    verification_time: str,
    expected_trusted_root_digest: str,
    expected_cosign_digest: str,
    expected_certificate_identity: str,
    expected_certificate_oidc_issuer: str,
    expected_certificate_audience: str,
    expected_workload_identity: str,
    expected_source_repository: str,
    expected_source_ref: str,
    expected_source_commit: str,
) -> tuple[dict[str, str], bytes, bytes]:
    if request_bytes != canonical_json(request):
        raise ContractToolError("external signing request snapshot is not canonical")
    request_digest = validate_signing_request_bindings(
        request,
        manifest_bytes,
        expected,
        verification_time,
    )
    sigstore_bundle_bytes = stable_read_bytes(
        sigstore_bundle_path,
        description="Sigstore bundle",
        maximum_bytes=MAX_SIGNATURE_EVIDENCE_BYTES,
    )
    trusted_root_bytes = stable_read_bytes(
        trusted_root_path,
        description="Sigstore trusted root",
        maximum_bytes=MAX_SIGNATURE_EVIDENCE_BYTES,
    )
    trusted_root_digest = sha256_bytes(trusted_root_bytes)
    if trusted_root_digest != expected_trusted_root_digest:
        raise ContractToolError("Sigstore trusted-root digest does not match independent input")
    if not expected_certificate_identity or not expected_certificate_oidc_issuer:
        raise ContractToolError("exact Sigstore certificate identity and issuer are required")

    cosign = shutil.which("cosign")
    if cosign is None:
        raise ContractToolError("exact Cosign verifier is unavailable")
    cosign_path = Path(cosign).resolve(strict=True)
    cosign_bytes = stable_read_bytes(
        cosign_path,
        description="Cosign executable",
        maximum_bytes=MAX_EXTERNAL_VERIFIER_BYTES,
    )
    cosign_digest = sha256_bytes(cosign_bytes)
    if cosign_digest != expected_cosign_digest:
        raise ContractToolError("Cosign executable digest does not match independent input")
    verification_input = {
        "profile": "bytedesk.sigstore-verification-input/1",
        "certificateIdentity": expected_certificate_identity,
        "certificateOidcIssuer": expected_certificate_oidc_issuer,
        "fulcioIssuanceAudiencePolicy": expected_certificate_audience,
        "workloadIdentity": expected_workload_identity,
        "githubWorkflowRepository": expected_source_repository,
        "githubWorkflowRef": expected_source_ref,
        "githubWorkflowSha": expected_source_commit,
        "githubWorkflowTrigger": "workflow_dispatch",
        "trustedRootDigest": trusted_root_digest,
        "cosignExecutableDigest": cosign_digest,
    }
    verification_input_bytes = canonical_json(verification_input)
    try:
        with TemporaryDirectory(prefix="bytedesk-cosign-verification-") as directory:
            snapshot_directory = Path(directory)
            snapshot_bundle = snapshot_directory / "signature.sigstore.json"
            snapshot_root = snapshot_directory / "trusted-root.json"
            snapshot_cosign = snapshot_directory / "cosign"
            write_bytes(snapshot_bundle, sigstore_bundle_bytes, require_absent=True)
            write_bytes(snapshot_root, trusted_root_bytes, require_absent=True)
            write_bytes(snapshot_cosign, cosign_bytes, require_absent=True)
            snapshot_cosign.chmod(0o500)
            command = [
                str(snapshot_cosign),
                "verify-blob",
                "--bundle",
                str(snapshot_bundle),
                "--trusted-root",
                str(snapshot_root),
                "--certificate-identity",
                expected_certificate_identity,
                "--certificate-oidc-issuer",
                expected_certificate_oidc_issuer,
                "--certificate-github-workflow-repository",
                expected_source_repository,
                "--certificate-github-workflow-ref",
                expected_source_ref,
                "--certificate-github-workflow-sha",
                expected_source_commit,
                "--certificate-github-workflow-trigger",
                "workflow_dispatch",
                "-",
            ]
            completed = subprocess.run(
                command,
                input=request_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=180,
                env={
                    "HOME": str(snapshot_directory),
                    "PATH": "/usr/bin:/bin",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContractToolError("Cosign verification adapter failed safely") from error
    if completed.returncode != 0:
        raise ContractToolError(f"Cosign denied the signed request (exit {completed.returncode})")
    if len(completed.stdout) > MAX_SIGNATURE_EVIDENCE_BYTES:
        raise ContractToolError("Cosign verification output exceeds the evidence byte limit")
    return (
        {
            "requestDigest": request_digest,
            "signatureEvidenceDigest": sha256_bytes(sigstore_bundle_bytes),
            "trustedRootDigest": trusted_root_digest,
            "cosignExecutableDigest": cosign_digest,
            "verificationInputDigest": sha256_bytes(verification_input_bytes),
            "cosignOutputDigest": sha256_bytes(completed.stdout),
        },
        verification_input_bytes,
        completed.stdout,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--expected-trust-policy-id", required=True)
    parser.add_argument("--expected-trust-policy-digest", required=True)
    parser.add_argument("--trust-policy", type=Path)
    parser.add_argument("--test-signing-request", type=Path)
    parser.add_argument("--test-signature", type=Path)
    parser.add_argument("--allow-test-signature", action="store_true")
    parser.add_argument("--external-signing-request", type=Path)
    parser.add_argument("--sigstore-bundle", type=Path)
    parser.add_argument("--sigstore-trusted-root", type=Path)
    parser.add_argument("--expected-sigstore-trusted-root-digest")
    parser.add_argument("--expected-cosign-digest")
    parser.add_argument("--expected-certificate-identity")
    parser.add_argument("--expected-certificate-oidc-issuer")
    parser.add_argument("--expected-certificate-audience")
    parser.add_argument("--expected-workload-identity")
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--verification-input-output", type=Path)
    parser.add_argument("--cosign-verification-output", type=Path)
    parser.add_argument("--external-adapter-conformance", action="store_true")
    # Retained as explicit fail-closed compatibility arguments. The repository
    # adapter cannot issue production authority or verification results.
    parser.add_argument("--verification-id")
    parser.add_argument("--verification-result-output", type=Path)
    parser.add_argument("--expected-request-id")
    parser.add_argument("--expected-repository")
    parser.add_argument("--expected-purpose")
    parser.add_argument("--expected-key-version")
    parser.add_argument("--expected-nonce")
    parser.add_argument("--expected-issued-at")
    parser.add_argument("--expected-expires-at")
    parser.add_argument("--verification-time")
    parser.add_argument("--replay-ledger", type=Path)
    parser.add_argument("--allow-test-local-replay-ledger", action="store_true")
    parser.add_argument("--allow-unsigned-structure", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    bundle_path = args.bundle.absolute()
    archive_snapshot = read_archive_snapshot(bundle_path)
    members = archive_snapshot.members
    manifest_bytes = members[MANIFEST_ARCHIVE_PATH]
    manifest = strict_json_bytes(manifest_bytes, MANIFEST_ARCHIVE_PATH)
    if not isinstance(manifest, dict):
        raise ContractToolError("bundle manifest root is not an object")
    if manifest_bytes != canonical_json(manifest):
        raise ContractToolError("bundle manifest is not exact RFC 8785 bytes")
    if args.manifest:
        _, external_manifest = load_json_bytes(args.manifest.resolve())
        if external_manifest != manifest_bytes:
            raise ContractToolError("detached manifest does not exactly match archive manifest")

    expected_policy = {
        "id": args.expected_trust_policy_id,
        "digest": args.expected_trust_policy_digest,
    }

    test_mode_requested = bool(
        args.test_signing_request or args.test_signature or args.allow_test_signature
    )
    external_mode_requested = args.external_adapter_conformance or any(
        value is not None
        for value in (
            args.external_signing_request,
            args.sigstore_bundle,
            args.sigstore_trusted_root,
            args.expected_sigstore_trusted_root_digest,
            args.expected_cosign_digest,
            args.expected_certificate_identity,
            args.expected_certificate_oidc_issuer,
            args.expected_certificate_audience,
            args.expected_workload_identity,
            args.expected_source_commit,
            args.verification_input_output,
            args.cosign_verification_output,
            args.verification_id,
            args.verification_result_output,
        )
    )
    selected_modes = sum(
        [test_mode_requested, external_mode_requested, args.allow_unsigned_structure]
    )
    if selected_modes != 1:
        raise ContractToolError(
            "select exactly one verification mode: explicit test signature, external Adapter conformance, or unsigned structure"
        )

    request_digest: str | None = None
    signature_verification: dict[str, str] | None = None
    trust_evaluation: TrustEvaluation | None = None
    request: dict[str, Any] | None = None
    request_bytes: bytes | None = None
    external_verification_input: bytes | None = None
    external_verification_output: bytes | None = None
    if test_mode_requested or external_mode_requested:
        binding_values = {
            "requestId": args.expected_request_id,
            "repository": args.expected_repository,
            "purpose": args.expected_purpose,
            "keyVersion": args.expected_key_version,
            "nonce": args.expected_nonce,
            "issuedAt": args.expected_issued_at,
            "expiresAt": args.expected_expires_at,
            "trustPolicy": expected_policy,
        }
        missing = sorted(key for key, value in binding_values.items() if value is None)
        if (
            missing
            or args.verification_time is None
            or args.replay_ledger is None
            or args.trust_policy is None
        ):
            raise ContractToolError(
                "signed verification lacks independent request bindings: "
                f"{missing + ([] if args.verification_time else ['verificationTime']) + ([] if args.replay_ledger else ['replayLedger']) + ([] if args.trust_policy else ['trustPolicySnapshot'])}"
            )
        if not args.allow_test_local_replay_ledger:
            raise ContractToolError(
                "repository verification requires explicit opt-in to its test-only non-global replay ledger"
            )
    else:
        binding_values = {}

    if test_mode_requested:
        request_path = args.test_signing_request
    elif external_mode_requested:
        request_path = args.external_signing_request
    else:
        request_path = None

    available_evidence = {"schema", "compatibility"}
    if request_path is not None:
        request, request_bytes = load_canonical_request(request_path.absolute())
        request_digest = validate_signing_request_bindings(
            request,
            manifest_bytes,
            binding_values,
            args.verification_time,
        )
        policy, policy_bytes = load_canonical_trust_policy(args.trust_policy.absolute())
        trust_evaluation = preflight_trust_policy(
            policy,
            policy_bytes,
            expected_policy=expected_policy,
            request=request,
            manifest=manifest,
            verification_time=args.verification_time,
            available_evidence=available_evidence,
        )
    else:
        policy = None
        policy_bytes = None

    if test_mode_requested:
        if not (args.test_signing_request and args.test_signature and args.allow_test_signature):
            raise ContractToolError(
                "test signature verification requires request, signature, and explicit allow flag"
            )
        if request is None or request_bytes is None:
            raise ContractToolError("test signature mode has no canonical request snapshot")
        verified_request_digest, test_signature_evidence_digest = verify_test_signature(
            request,
            request_bytes,
            args.test_signature.resolve(),
            manifest_bytes,
            binding_values,
            args.verification_time,
        )
        if verified_request_digest != request_digest:
            raise ContractToolError("test signature verified a different request snapshot")
        signature_verification = {
            "requestDigest": verified_request_digest,
            "signatureEvidenceDigest": test_signature_evidence_digest,
        }
    elif external_mode_requested:
        required_external = {
            "externalSigningRequest": args.external_signing_request,
            "sigstoreBundle": args.sigstore_bundle,
            "sigstoreTrustedRoot": args.sigstore_trusted_root,
            "expectedSigstoreTrustedRootDigest": args.expected_sigstore_trusted_root_digest,
            "expectedCosignDigest": args.expected_cosign_digest,
            "expectedSourceCommit": args.expected_source_commit,
            "verificationInputOutput": args.verification_input_output,
            "cosignVerificationOutput": args.cosign_verification_output,
            "externalAdapterConformance": args.external_adapter_conformance,
        }
        missing_external = sorted(
            key for key, value in required_external.items() if value is None
        )
        if missing_external:
            raise ContractToolError(
                f"external Sigstore Adapter conformance lacks inputs: {missing_external}"
            )
        if args.verification_id is not None or args.verification_result_output is not None:
            raise ContractToolError(
                "the repository conformance Adapter cannot mint a production verification result"
            )
        if re.fullmatch(r"[0-9a-f]{40}", args.expected_source_commit) is None:
            raise ContractToolError("expected source commit must be an exact lowercase Git SHA")
        if request is None or request_bytes is None or trust_evaluation is None:
            raise ContractToolError("external Adapter mode lacks canonical request/policy snapshots")
        independently_expected = {
            "certificate identity": (
                args.expected_certificate_identity,
                trust_evaluation.certificate_identity,
            ),
            "certificate issuer": (
                args.expected_certificate_oidc_issuer,
                trust_evaluation.certificate_oidc_issuer,
            ),
            "certificate audience": (
                args.expected_certificate_audience,
                trust_evaluation.certificate_audience,
            ),
            "workload identity": (
                args.expected_workload_identity,
                trust_evaluation.workload_identity,
            ),
        }
        for description, (supplied, derived) in independently_expected.items():
            if supplied is not None and supplied != derived:
                raise ContractToolError(
                    f"independently supplied {description} differs from the trust policy"
                )
        for output_path, description in (
            (args.verification_input_output, "verification input output"),
            (args.cosign_verification_output, "Cosign verification output"),
        ):
            if output_path.is_symlink() or output_path.exists():
                raise ContractToolError(f"{description} must be absent before verification")
        (
            signature_verification,
            external_verification_input,
            external_verification_output,
        ) = verify_sigstore_signature(
            request,
            request_bytes,
            args.sigstore_bundle.absolute(),
            args.sigstore_trusted_root.absolute(),
            manifest_bytes,
            binding_values,
            args.verification_time,
            args.expected_sigstore_trusted_root_digest,
            args.expected_cosign_digest,
            trust_evaluation.certificate_identity,
            trust_evaluation.certificate_oidc_issuer,
            trust_evaluation.certificate_audience,
            trust_evaluation.workload_identity,
            trust_evaluation.source_repository,
            trust_evaluation.source_ref,
            args.expected_source_commit,
        )
        if signature_verification["requestDigest"] != request_digest:
            raise ContractToolError("external Adapter verified a different request snapshot")

    # No artifact-provided schema or regular expression is evaluated until an
    # external signed request has been authenticated. The unsigned/test lanes
    # remain explicitly non-authoritative conformance modes.
    registry, schemas = build_bundle_registry(manifest, members, expected_policy)
    schema_inventory_path = manifest["schemaInventory"]["path"]
    schema_inventory_evidence = validate_schema_inventory(
        strict_json_bytes(members[schema_inventory_path], schema_inventory_path),
        schemas,
        inventory_path=schema_inventory_path,
    )
    errors = sorted(
        Draft202012Validator(
            schemas[CONTRACT_BUNDLE_SCHEMA_ID][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(manifest),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"bundle manifest schema denial: {errors[0].message}")
    if manifest["trustPolicy"] != expected_policy:
        raise ContractToolError("bundle trust policy does not match independent verifier input")
    if any(entry["trustPolicy"] != expected_policy for entry in manifest["schemas"]):
        raise ContractToolError("one or more schemas use a different trust policy")
    verify_inventory(manifest, members)
    verify_build_input_digest(manifest, members)
    validate_authenticated_bundle_semantics(manifest, members, registry, schemas)

    if request is not None:
        full_request_digest = validate_signing_request(
            request,
            manifest_bytes,
            binding_values,
            args.verification_time,
            registry,
            schemas,
        )
        if full_request_digest != request_digest:
            raise ContractToolError("full request validation differs from authenticated preflight")
        if policy is None or policy_bytes is None or trust_evaluation is None:
            raise ContractToolError("signed mode lost its independent trust-policy snapshot")
        full_trust_evaluation = evaluate_trust_policy(
            policy,
            policy_bytes,
            expected_policy=expected_policy,
            request=request,
            manifest=manifest,
            verification_time=args.verification_time,
            available_evidence=available_evidence,
            registry=registry,
            schemas=schemas,
        )
        if full_trust_evaluation != trust_evaluation:
            raise ContractToolError("full trust-policy evaluation differs from preflight")

    replay_ledger_entry_digest: str | None = None
    if test_mode_requested or external_mode_requested:
        replay_entry_bytes = replay_ledger_entry_bytes(
            request_id=args.expected_request_id,
            nonce=args.expected_nonce,
            request_digest=request_digest,
            verified_at=args.verification_time,
        )
        replay_ledger_entry_digest = sha256_bytes(replay_entry_bytes)
        if signature_verification is None:
            raise ContractToolError("signed verification produced no signature evidence")
        signature_verification["replayLedgerEntryDigest"] = replay_ledger_entry_digest

    if test_mode_requested or external_mode_requested:
        consumed_digest = consume_replay_ledger(
            args.replay_ledger.absolute(),
            request_id=args.expected_request_id,
            nonce=args.expected_nonce,
            request_digest=request_digest,
            verified_at=args.verification_time,
        )
        if consumed_digest != replay_ledger_entry_digest:
            raise ContractToolError("replay ledger consumed a different canonical entry")

    if external_mode_requested:
        if external_verification_input is None or external_verification_output is None:
            raise ContractToolError("external Adapter produced no conformance evidence")
        write_bytes(
            args.verification_input_output.resolve(),
            external_verification_input,
            require_absent=True,
        )
        write_bytes(
            args.cosign_verification_output.resolve(),
            external_verification_output,
            require_absent=True,
        )

    if test_mode_requested:
        verification_mode = "test_ephemeral"
        outcome = "test_conformance_pass"
    elif external_mode_requested:
        verification_mode = "external_adapter_conformance"
        outcome = "adapter_conformance_pass"
    else:
        verification_mode = "unsigned_structure"
        outcome = "structure_pass"

    trust_evaluation_evidence = None
    if trust_evaluation is not None:
        trust_evaluation_evidence = {
            "policyDigest": trust_evaluation.policy_digest,
            "certificateIdentity": trust_evaluation.certificate_identity,
            "certificateOidcIssuer": trust_evaluation.certificate_oidc_issuer,
            "workloadIdentity": trust_evaluation.workload_identity,
            "workflow": trust_evaluation.workflow,
            "sourceRepository": trust_evaluation.source_repository,
            "sourceRef": trust_evaluation.source_ref,
            "builderDigest": trust_evaluation.builder_digest,
            "policyOnlyClaimsNotPostHocCertificateAssertions": {
                "fulcioIssuanceAudience": trust_evaluation.certificate_audience,
                "tokenEnvironment": trust_evaluation.environment,
            },
        }

    result = {
        "profile": "bytedesk.contract-bundle-verification-evidence/1",
        "verificationMode": verification_mode,
        "signatureAuthenticated": external_mode_requested,
        "testSignatureVerified": test_mode_requested,
        "authorityIssued": False,
        "authorityOutcome": "not_issued",
        "bundleDigest": archive_snapshot.digest,
        "bundleSize": archive_snapshot.size,
        "manifestDigest": sha256_bytes(manifest_bytes),
        "schemaCount": len(manifest["schemas"]),
        "schemaInventory": schema_inventory_evidence,
        "documentCount": len(manifest["documents"]),
        "trustPolicy": expected_policy,
        "testSignatureRequestDigest": request_digest if test_mode_requested else None,
        "adapterConformanceRequestDigest": request_digest if external_mode_requested else None,
        "replayLedgerEntryDigest": replay_ledger_entry_digest,
        "replayProtection": (
            "test_local_non_global"
            if test_mode_requested or external_mode_requested
            else "none"
        ),
        "verificationResultDigest": None,
        "signatureVerification": signature_verification,
        "trustPolicyEvaluation": trust_evaluation_evidence,
        "repositoryOnlyPathExclusion": {
            "patterns": list(REPOSITORY_ONLY_RELEASE_PATTERNS),
            "outcome": "pass",
        },
        "outcome": outcome,
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError) as error:
        print(f"contract bundle verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
