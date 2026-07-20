#!/usr/bin/env python3
"""Build the deterministic, offline Agent Delivery contract bundle."""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from contractlib import (
    CONTRACTS_ROOT,
    REPOSITORY_ROOT,
    SCHEMAS_ROOT,
    ContractToolError,
    atomic_write,
    canonical_digest,
    canonical_json,
    load_json,
    repository_path,
    sha256_bytes,
    stable_file_digest,
    stable_read_bytes,
    strict_json_bytes,
    validation_error_key,
    write_bytes,
)
from bundle_profile import (
    MAX_BUNDLE_BYTES,
    MAX_BUNDLE_MEMBER_BYTES,
    MAX_BUNDLE_MEMBERS,
    BundleProfileError,
    normalized_member_payload,
    portable_path_collision_key,
    validate_portable_path_set,
    write_deterministic_tar,
)
from validate_schemas import (
    SCHEMA_INVENTORY_BUNDLE_PATH,
    validate_denial_fixture_coverage,
    validate_fixture_index_document,
    validate_positive_fixture_coverage,
    validate_schema_inventory,
)


CONTRACT_BUNDLE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/contract-bundle/1.0.0"
)
CONTRACT_BUNDLE_MEDIA_TYPE = "application/vnd.bytedesk.agent.contract-bundle.v1+json"
MANIFEST_ARCHIVE_PATH = "bundle/manifest.json"
REPOSITORY_ONLY_RELEASE_PATTERNS = (
    "contracts/schemas/repository/*.schema.json",
    "contracts/fixtures/schema/repository-index.json",
    "contracts/fixtures/schema/positive/development-plan__*.json",
    "contracts/fixtures/schema/negative/development-plan__*.json",
)
BUNDLE_SOURCE_FIELDS = {
    "profile",
    "include",
    "fixtureIndex",
    "schemaInventory",
    "compatibility",
    "documentationMap",
}
DOCUMENTATION_MAP_FIELDS = {"profile", "documents", "schemas", "projections"}
DOCUMENTATION_INVENTORY_FIELDS = {"path", "digest"}
DOCUMENTATION_SCHEMA_FIELDS = {"id", "documents"}
DOCUMENTATION_PROJECTION_FIELDS = {"path", "source", "role"}
EXACT_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
DOCUMENTATION_PROJECTION_ROLES = {
    "http-projection",
    "event-projection",
    "notification-registry",
}
COMPATIBILITY_FIELDS = {
    "profile",
    "bundleMajor",
    "schemaDialect",
    "openapi",
    "asyncapi",
    "cloudEvents",
    "canonicalization",
    "rules",
    "supportedInteroperability",
    "breakingChanges",
}
COMPATIBILITY_VALUES = {
    "profile": "bytedesk.contract-compatibility/1",
    "bundleMajor": 1,
    "schemaDialect": "https://json-schema.org/draft/2020-12/schema",
    "openapi": "3.2.0",
    "asyncapi": "3.1.0",
    "cloudEvents": "1.0.2",
    "canonicalization": "RFC8785",
}
COMPATIBILITY_RULES = {
    "authorityObjects": "closed-and-major-immutable",
    "commandEnums": "closed",
    "readModels": "optional-fields-may-be-additive-in-a-declared-minor",
    "eventData": "optional-fields-may-be-additive-in-a-declared-minor",
    "unknownSchema": "deny",
    "unknownCommandField": "deny",
    "unknownAuthorityField": "deny",
    "eventGap": "stop-and-api-resynchronize",
    "historicalVerification": "retain-exact-bundle-and-trust-policy",
}
COMPATIBILITY_INTEROPERABILITY = [
    {
        "clientMajor": 1,
        "serverMajor": 1,
        "direction": "both",
        "condition": "exact-schema-digest-or-declared-compatible-read-projection",
    }
]
COMPATIBILITY_BREAKING_CHANGES = [
    "remove-or-rename-field",
    "change-field-type-or-meaning",
    "add-required-field",
    "narrow-accepted-value",
    "change-canonicalization-or-operation-semantics",
    "change-security-interpretation",
    "change-terminal-state-meaning",
]


def validate_bundle_source(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ContractToolError("bundle-source root is not an object")
    unexpected = sorted(set(config) - BUNDLE_SOURCE_FIELDS)
    if unexpected:
        raise ContractToolError(f"bundle-source root has unknown fields: {unexpected}")
    missing = sorted(BUNDLE_SOURCE_FIELDS - set(config))
    if missing:
        raise ContractToolError(f"bundle-source root lacks fields: {missing}")
    if config["profile"] != "bytedesk.contract-bundle-source/1":
        raise ContractToolError("unknown bundle-source profile")
    patterns = config["include"]
    if (
        not isinstance(patterns, list)
        or not patterns
        or not all(isinstance(pattern, str) and pattern for pattern in patterns)
        or len(patterns) != len(set(patterns))
    ):
        raise ContractToolError("bundle-source include must be a non-empty unique string array")
    designated_names = (
        "fixtureIndex",
        "schemaInventory",
        "compatibility",
        "documentationMap",
    )
    designated = [config[name] for name in designated_names]
    if not all(isinstance(value, str) and value for value in designated):
        raise ContractToolError(
            "bundle-source must name fixtureIndex, schemaInventory, compatibility, documentationMap"
        )
    if len(designated) != len(set(designated)):
        raise ContractToolError("bundle-source designated metadata paths must be unique")
    if config["schemaInventory"] != SCHEMA_INVENTORY_BUNDLE_PATH:
        raise ContractToolError("bundle-source names a noncanonical schema inventory path")
    try:
        validate_portable_path_set(designated, "bundle-source designated metadata")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error
    return config


def validate_compatibility(document: Any) -> None:
    if not isinstance(document, dict):
        raise ContractToolError("compatibility root is not an object")
    unexpected = sorted(set(document) - COMPATIBILITY_FIELDS)
    if unexpected:
        raise ContractToolError(f"compatibility root has unknown fields: {unexpected}")
    missing = sorted(COMPATIBILITY_FIELDS - set(document))
    if missing:
        raise ContractToolError(f"compatibility root lacks fields: {missing}")

    rules = document["rules"]
    if not isinstance(rules, dict):
        raise ContractToolError("compatibility rules must be an object")
    rule_unknown = sorted(set(rules) - set(COMPATIBILITY_RULES))
    rule_missing = sorted(set(COMPATIBILITY_RULES) - set(rules))
    if rule_unknown or rule_missing:
        raise ContractToolError(
            "compatibility rules have unknown or missing fields "
            f"unknown={rule_unknown} missing={rule_missing}"
        )

    interoperability = document["supportedInteroperability"]
    if not isinstance(interoperability, list) or not interoperability:
        raise ContractToolError("compatibility supportedInteroperability must be a non-empty array")
    interoperability_fields = {"clientMajor", "serverMajor", "direction", "condition"}
    for entry in interoperability:
        if not isinstance(entry, dict) or set(entry) != interoperability_fields:
            raise ContractToolError("compatibility interoperability entry is not closed")

    if any(document[key] != value for key, value in COMPATIBILITY_VALUES.items()):
        raise ContractToolError("compatibility profile is incomplete or drifted")
    if rules != COMPATIBILITY_RULES:
        raise ContractToolError("compatibility rules are incomplete or drifted")
    if interoperability != COMPATIBILITY_INTEROPERABILITY:
        raise ContractToolError("compatibility interoperability policy is incomplete or drifted")
    if document["breakingChanges"] != COMPATIBILITY_BREAKING_CHANGES:
        raise ContractToolError("compatibility breaking-change policy is incomplete or drifted")


def _resolve_declared_repository_path(
    path: str, description: str, *, allow_directory_marker: bool = False
) -> Path:
    if not isinstance(path, str) or not path or "\\" in path:
        raise ContractToolError(f"{description} is not a non-empty repository path")
    try:
        portable_path_collision_key(
            path.rstrip("/") if allow_directory_marker and path.endswith("/") else path
        )
    except BundleProfileError as error:
        raise ContractToolError(f"{description} is not portable: {error}") from error
    candidate = REPOSITORY_ROOT / path
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except (OSError, ValueError) as error:
        raise ContractToolError(f"{description} escapes or is missing: {path}") from error
    if relative != path.rstrip("/"):
        raise ContractToolError(f"{description} is not canonical: {path}")
    return resolved


def validate_documentation_map(
    document: Any,
    bundled_schema_ids: set[str],
    bundled_paths: set[str],
) -> None:
    if not isinstance(document, dict):
        raise ContractToolError("documentation map root is not an object")
    unexpected = sorted(set(document) - DOCUMENTATION_MAP_FIELDS)
    if unexpected:
        raise ContractToolError(f"documentation map root has unknown fields: {unexpected}")
    missing = sorted(DOCUMENTATION_MAP_FIELDS - set(document))
    if missing:
        raise ContractToolError(f"documentation map root lacks fields: {missing}")
    if document["profile"] != "bytedesk.contract-documentation-map/1":
        raise ContractToolError("documentation map has an invalid profile")

    inventory = document["documents"]
    if not isinstance(inventory, list) or not inventory:
        raise ContractToolError(
            "documentation map documents must be a non-empty array"
        )
    inventory_paths: list[str] = []
    for entry in inventory:
        if not isinstance(entry, dict) or set(entry) != DOCUMENTATION_INVENTORY_FIELDS:
            raise ContractToolError(
                "documentation map documentation inventory entry is not closed"
            )
        documentation_path = entry["path"]
        expected_digest = entry["digest"]
        if not isinstance(documentation_path, str) or not documentation_path:
            raise ContractToolError(
                "documentation map documentation inventory path is invalid"
            )
        if (
            not isinstance(expected_digest, str)
            or EXACT_SHA256_PATTERN.fullmatch(expected_digest) is None
        ):
            raise ContractToolError(
                "documentation map documentation inventory digest is invalid"
            )
        candidate = _resolve_declared_repository_path(
            documentation_path,
            "documentation map documentation inventory path",
        )
        observed_digest, _ = stable_file_digest(
            candidate,
            description=(
                f"documentation map documentation inventory file {documentation_path}"
            ),
            maximum_bytes=MAX_BUNDLE_MEMBER_BYTES,
        )
        if observed_digest != expected_digest:
            raise ContractToolError(
                "documentation map documentation digest differs from repository bytes: "
                f"{documentation_path}"
            )
        inventory_paths.append(documentation_path)
    if inventory_paths != sorted(set(inventory_paths)):
        raise ContractToolError(
            "documentation map documentation inventory is not strictly sorted and unique"
        )
    try:
        validate_portable_path_set(inventory_paths, "documentation inventory")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error

    entries = document["schemas"]
    if not isinstance(entries, list) or not entries:
        raise ContractToolError("documentation map schemas must be a non-empty array")
    mapped_schema_ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != DOCUMENTATION_SCHEMA_FIELDS:
            raise ContractToolError("documentation map schema entry is not closed")
        schema_id = entry["id"]
        documents = entry["documents"]
        if not isinstance(schema_id, str) or not schema_id:
            raise ContractToolError("documentation map schema entry has an invalid id")
        if (
            not isinstance(documents, list)
            or not documents
            or not all(isinstance(value, str) and value for value in documents)
            or len(documents) != len(set(documents))
        ):
            raise ContractToolError(f"schema documentation list is invalid: {schema_id}")
        for documentation_path in documents:
            candidate = _resolve_declared_repository_path(
                documentation_path, "documentation map document path"
            )
            if not candidate.is_file() or candidate.is_symlink():
                raise ContractToolError(
                    f"documentation map path is not a regular file: {documentation_path}"
                )
        mapped_schema_ids.append(schema_id)
    if len(mapped_schema_ids) != len(set(mapped_schema_ids)):
        raise ContractToolError("documentation map contains a duplicate schema ID")
    if set(mapped_schema_ids) != bundled_schema_ids:
        missing_ids = sorted(bundled_schema_ids - set(mapped_schema_ids))
        extra_ids = sorted(set(mapped_schema_ids) - bundled_schema_ids)
        raise ContractToolError(
            f"documentation map schema drift missing={missing_ids} extra={extra_ids}"
        )
    referenced_documentation_paths = {
        path
        for entry in entries
        for path in entry["documents"]
    }
    inventoried_documentation_paths = set(inventory_paths)
    if referenced_documentation_paths != inventoried_documentation_paths:
        missing_inventory = sorted(
            referenced_documentation_paths - inventoried_documentation_paths
        )
        unreferenced_inventory = sorted(
            inventoried_documentation_paths - referenced_documentation_paths
        )
        raise ContractToolError(
            "documentation map documentation reference closure differs "
            f"missingInventory={missing_inventory} "
            f"unreferencedInventory={unreferenced_inventory}"
        )

    projections = document["projections"]
    if not isinstance(projections, list) or not projections:
        raise ContractToolError("documentation map projections must be a non-empty array")
    projection_paths: list[str] = []
    for entry in projections:
        if not isinstance(entry, dict) or set(entry) != DOCUMENTATION_PROJECTION_FIELDS:
            raise ContractToolError("documentation map projection entry is not closed")
        projection_path = entry["path"]
        source = entry["source"]
        role = entry["role"]
        if (
            not isinstance(projection_path, str)
            or not projection_path
            or not isinstance(source, str)
            or not source
            or not isinstance(role, str)
            or role not in DOCUMENTATION_PROJECTION_ROLES
        ):
            raise ContractToolError("documentation map projection entry has invalid values")
        projection = _resolve_declared_repository_path(
            projection_path, "documentation map projection path"
        )
        if not projection.is_file() or projection.is_symlink():
            raise ContractToolError(
                f"documentation map projection is not a regular file: {projection_path}"
            )
        if projection_path not in bundled_paths:
            raise ContractToolError(
                f"documentation map projection is absent from bundle: {projection_path}"
            )
        source_path = _resolve_declared_repository_path(
            source,
            "documentation map projection source",
            allow_directory_marker=True,
        )
        try:
            source_path.relative_to(CONTRACTS_ROOT.resolve())
        except ValueError as error:
            raise ContractToolError(
                f"documentation map projection source is outside contracts/: {source}"
            ) from error
        projection_paths.append(projection_path)
    if len(projection_paths) != len(set(projection_paths)):
        raise ContractToolError("documentation map contains a duplicate projection path")


def normalized_payload(path: Path) -> bytes:
    relative = repository_path(path)
    payload = stable_read_bytes(
        path,
        description=f"bundle input {path}",
        maximum_bytes=MAX_BUNDLE_MEMBER_BYTES,
    )
    try:
        return normalized_member_payload(relative, payload)
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error


def inventory(path: str, payload: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "digest": sha256_bytes(payload),
        "size": len(payload),
        "mode": "0444",
    }


def repository_only_release_path(path: str) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in REPOSITORY_ONLY_RELEASE_PATTERNS)


def expand_inputs(config: dict[str, Any]) -> list[Path]:
    validate_bundle_source(config)
    patterns = config["include"]
    paths: dict[str, Path] = {}

    def add_input(path: Path, declared_path: str) -> None:
        if path.is_symlink() or not path.is_file():
            raise ContractToolError(f"bundle input is not a regular non-symlink file: {declared_path}")
        relative = repository_path(path)
        if relative != declared_path:
            raise ContractToolError(f"bundle input path is not canonical: {declared_path}")
        if not relative.startswith("contracts/"):
            raise ContractToolError(f"bundle input is outside contracts/: {relative}")
        if repository_only_release_path(relative):
            raise ContractToolError(f"repository-only input is forbidden from release bundles: {relative}")
        paths[relative] = path

    for pattern in patterns:
        matches = sorted(REPOSITORY_ROOT.glob(pattern))
        if not matches:
            raise ContractToolError(f"bundle input pattern matched nothing: {pattern}")
        matched_files = 0
        for path in matches:
            if path.is_dir():
                continue
            try:
                declared_path = path.relative_to(REPOSITORY_ROOT).as_posix()
            except ValueError as error:
                raise ContractToolError(f"bundle glob escaped the repository: {pattern}") from error
            add_input(path, declared_path)
            matched_files += 1
        if matched_files == 0:
            raise ContractToolError(f"bundle input pattern matched no regular files: {pattern}")

    for metadata_name in (
        "fixtureIndex",
        "schemaInventory",
        "compatibility",
        "documentationMap",
    ):
        metadata_path = config[metadata_name]
        add_input(REPOSITORY_ROOT / metadata_path, metadata_path)
    fixture_index_path = config["fixtureIndex"]
    fixture_index_file = REPOSITORY_ROOT / fixture_index_path
    fixture_index = load_json(fixture_index_file)
    fixtures = validate_fixture_index_document(fixture_index)
    for item in fixtures:
        fixture_path = item["path"]
        add_input(REPOSITORY_ROOT / fixture_path, fixture_path)
    try:
        validate_portable_path_set(paths, "bundle input")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error
    if len(paths) + 1 > MAX_BUNDLE_MEMBERS:
        raise ContractToolError("bundle inputs exceed the shared member-count limit")
    return [paths[key] for key in sorted(paths)]


def logical_contract(schema_path: Path, schema: dict[str, Any]) -> str:
    properties = schema.get("properties", {})
    for member in ("contract", "profile"):
        value = properties.get(member, {}).get("const") if isinstance(properties, dict) else None
        if isinstance(value, str) and value.startswith("bytedesk.") and "/" in value:
            return value
    return f"bytedesk.{schema_path.name.removesuffix('.schema.json')}/1"


def make_manifest(
    config: dict[str, Any],
    inputs: list[Path],
    payloads: dict[str, bytes],
    *,
    bundle_version: str,
    product_version: str,
    created_at: str,
    trust_policy_id: str,
    trust_policy_digest: str,
) -> dict[str, Any]:
    validate_bundle_source(config)
    trust_policy = {"id": trust_policy_id, "digest": trust_policy_digest}
    schema_entries: list[dict[str, Any]] = []
    bundled_schemas: dict[str, tuple[Path, Any]] = {}
    schema_descriptor: dict[str, str] | None = None
    document_entries: list[dict[str, Any]] = []
    fixture_paths: set[str] = set()

    fixture_index_path = config["fixtureIndex"]
    schema_inventory_path = config["schemaInventory"]
    compatibility_path = config["compatibility"]
    documentation_map_path = config["documentationMap"]
    if schema_inventory_path != SCHEMA_INVENTORY_BUNDLE_PATH:
        raise ContractToolError("bundle-source names a noncanonical schema inventory path")
    designated_values = [
        fixture_index_path,
        schema_inventory_path,
        compatibility_path,
        documentation_map_path,
    ]
    designated = set(designated_values)

    fixture_index = strict_json_bytes(payloads[fixture_index_path], fixture_index_path)
    fixtures = validate_fixture_index_document(fixture_index)
    for item in fixtures:
        fixture_paths.add(item["path"])

    for path in inputs:
        relative = repository_path(path)
        payload = payloads[relative]
        if path.parent.resolve() == SCHEMAS_ROOT.resolve() and path.name.endswith(".schema.json"):
            schema = strict_json_bytes(payload, relative)
            schema_id = schema.get("$id")
            if not isinstance(schema_id, str):
                raise ContractToolError(f"schema lacks $id: {relative}")
            if schema_id in bundled_schemas:
                raise ContractToolError(f"duplicate snapshotted schema ID: {schema_id}")
            version = schema_id.rstrip("/").rsplit("/", 1)[-1]
            entry = {
                "id": schema_id,
                "logicalContract": logical_contract(path, schema),
                "version": version,
                "path": relative,
                "mediaType": "application/schema+json",
                "size": len(payload),
                "digest": sha256_bytes(payload),
                "trustPolicy": trust_policy,
            }
            schema_entries.append(entry)
            bundled_schemas[schema_id] = (path, schema)
            if schema_id == CONTRACT_BUNDLE_SCHEMA_ID:
                schema_descriptor = {"id": schema_id, "digest": entry["digest"]}
        elif relative not in designated:
            document_entries.append(inventory(relative, payload))

    if schema_descriptor is None:
        raise ContractToolError("contract-bundle source schema is missing")
    validate_positive_fixture_coverage(fixtures, (entry["id"] for entry in schema_entries))
    validate_denial_fixture_coverage(fixtures, bundled_schemas)
    if not fixture_paths:
        raise ContractToolError("fixture index contains no fixtures")
    for required in [
        *fixture_paths,
        fixture_index_path,
        schema_inventory_path,
        compatibility_path,
        documentation_map_path,
    ]:
        if required not in payloads:
            raise ContractToolError(f"bundle input inventory is missing {required}")

    schema_entries.sort(key=lambda item: item["id"])
    document_entries.sort(key=lambda item: item["path"])
    schema_inventory = strict_json_bytes(
        payloads[schema_inventory_path], schema_inventory_path
    )
    validate_schema_inventory(
        schema_inventory,
        bundled_schemas,
        repository_root=REPOSITORY_ROOT,
        inventory_path=schema_inventory_path,
    )
    documentation_map = strict_json_bytes(
        payloads[documentation_map_path], documentation_map_path
    )
    bundled_schema_ids = {entry["id"] for entry in schema_entries}
    validate_documentation_map(documentation_map, bundled_schema_ids, set(payloads))

    compatibility = strict_json_bytes(payloads[compatibility_path], compatibility_path)
    validate_compatibility(compatibility)

    build_input = {
        "profile": "bytedesk.contract-bundle-build-input/1",
        "bundleVersion": bundle_version,
        "productVersion": product_version,
        "createdAt": created_at,
        "trustPolicy": trust_policy,
        "inputs": [inventory(path, payloads[path]) for path in sorted(payloads)],
    }
    return {
        "contract": "bytedesk.contract-bundle/1",
        "schema": schema_descriptor,
        "bundleVersion": bundle_version,
        "productVersion": product_version,
        "createdAt": created_at,
        "schemas": schema_entries,
        "documents": document_entries,
        "fixtureIndex": inventory(fixture_index_path, payloads[fixture_index_path]),
        "schemaInventory": inventory(
            schema_inventory_path, payloads[schema_inventory_path]
        ),
        "compatibility": inventory(compatibility_path, payloads[compatibility_path]),
        "documentationMap": inventory(documentation_map_path, payloads[documentation_map_path]),
        "buildInputDigest": canonical_digest(build_input),
        "trustPolicy": trust_policy,
    }


def validate_manifest(manifest: dict[str, Any], payloads: dict[str, bytes]) -> None:
    resources: list[tuple[str, Resource]] = []
    schemas: dict[str, Any] = {}
    for path, payload in payloads.items():
        if not path.startswith("contracts/schemas/v1/") or not path.endswith(
            ".schema.json"
        ):
            continue
        schema = strict_json_bytes(payload, path)
        schema_id = schema.get("$id") if isinstance(schema, dict) else None
        if not isinstance(schema_id, str) or schema_id in schemas:
            raise ContractToolError(f"invalid or duplicate snapshotted schema ID: {path}")
        schemas[schema_id] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    if CONTRACT_BUNDLE_SCHEMA_ID not in schemas:
        raise ContractToolError("snapshotted contract-bundle schema is missing")
    registry = Registry().with_resources(resources)
    schema = schemas[CONTRACT_BUNDLE_SCHEMA_ID]
    errors = list(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(manifest)
    )
    if errors:
        errors.sort(key=validation_error_key)
        raise ContractToolError(f"generated bundle manifest is invalid: {errors[0].message}")


def build_tar(path: Path, payloads: dict[str, bytes], manifest_bytes: bytes) -> str:
    members = dict(payloads)
    members[MANIFEST_ARCHIVE_PATH] = manifest_bytes

    def writer(target: Any) -> None:
        try:
            write_deterministic_tar(target, members)
        except BundleProfileError as error:
            raise ContractToolError(str(error)) from error

    atomic_write(path, writer)
    digest, _ = stable_file_digest(
        path,
        description="generated contract bundle",
        maximum_bytes=MAX_BUNDLE_BYTES,
    )
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=CONTRACTS_ROOT / "bundle" / "v1" / "bundle-source.json",
    )
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "dist" / "contracts")
    parser.add_argument("--bundle-version", default="1.0.0")
    parser.add_argument("--product-version", default="0.1.0-contracts-frozen")
    parser.add_argument("--created-at", default="1970-01-01T00:00:00Z")
    parser.add_argument("--trust-policy-id", required=True)
    parser.add_argument("--trust-policy-digest", required=True)
    args = parser.parse_args()

    config = load_json(args.config)
    validate_bundle_source(config)
    inputs = expand_inputs(config)
    payloads = {repository_path(path): normalized_payload(path) for path in inputs}
    manifest = make_manifest(
        config,
        inputs,
        payloads,
        bundle_version=args.bundle_version,
        product_version=args.product_version,
        created_at=args.created_at,
        trust_policy_id=args.trust_policy_id,
        trust_policy_digest=args.trust_policy_digest,
    )
    validate_manifest(manifest, payloads)
    manifest_bytes = canonical_json(manifest)
    manifest_digest = sha256_bytes(manifest_bytes)

    output_dir = args.output_dir.resolve()
    bundle_path = output_dir / "agent-delivery-contracts-v1.tar"
    manifest_path = output_dir / "agent-delivery-contracts-v1.manifest.json"
    digest_path = output_dir / "agent-delivery-contracts-v1.manifest.sha256"
    bundle_digest = build_tar(bundle_path, payloads, manifest_bytes)
    write_bytes(manifest_path, manifest_bytes)
    write_bytes(digest_path, f"{manifest_digest.removeprefix('sha256:')}  {manifest_path.name}\n".encode())
    print(
        f"bundle={bundle_path} bundleDigest={bundle_digest} "
        f"manifestDigest={manifest_digest} entries={len(payloads)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BundleProfileError, ContractToolError) as error:
        print(f"contract bundle build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
