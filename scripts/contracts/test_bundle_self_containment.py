#!/usr/bin/env python3
"""Prove the offline verifier derives schema authority from bundle members."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable

from jsonschema import Draft202012Validator

from contractlib import (
    MAX_JSON_MODEL_DEPTH,
    MAX_JSON_MODEL_NODES,
    MAX_SAFE_INTEGER,
    MAX_STRUCTURED_JSON_BYTES,
    ContractToolError,
    canonical_json,
    sha256_bytes,
    validation_error_key,
    write_json,
)
from verify_bundle import (
    CONTRACT_BUNDLE_SCHEMA_ID,
    MANIFEST_ARCHIVE_PATH,
    SIGNING_REQUEST_SCHEMA_ID,
    build_bundle_registry,
    read_archive,
    strict_json_bytes,
    verify_inventory,
)


PRIVATE_CASE_PATH = (
    "contracts/fixtures/operations/private-compilation-graph.cases.json"
)
PRIVATE_CAS_PREFIX = (
    "contracts/fixtures/operations/private-compilation-cas/blobs/sha256/"
)
RENDERER_CAS_PREFIX = "contracts/fixtures/operations/renderer-cas/blobs/sha256/"


def expect_denial(case_id: str, operation: Callable[[], Any]) -> dict[str, str]:
    try:
        operation()
    except ContractToolError as error:
        return {"id": case_id, "outcome": "denied", "reason": str(error)}
    raise ContractToolError(f"bundle self-containment denial unexpectedly passed: {case_id}")


def replace_schema(
    manifest: dict[str, Any],
    members: dict[str, bytes],
    schema_id: str,
    schema: dict[str, Any],
) -> None:
    payload = canonical_json(schema)
    for entry in manifest["schemas"]:
        if entry["id"] == schema_id:
            members[entry["path"]] = payload
            entry["digest"] = sha256_bytes(payload)
            entry["size"] = len(payload)
            return
    raise ContractToolError(f"test bundle does not contain schema {schema_id}")


def replace_document(
    manifest: dict[str, Any], members: dict[str, bytes], path: str, payload: bytes
) -> None:
    for entry in manifest["documents"]:
        if entry["path"] == path:
            members[path] = payload
            entry["digest"] = sha256_bytes(payload)
            entry["size"] = len(payload)
            return
    raise ContractToolError(f"test bundle does not contain document {path}")


def verify_private_cas_inventory(
    case_catalog: Any,
    members: dict[str, bytes],
) -> tuple[list[dict[str, Any]], set[str], dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(case_catalog, dict):
        raise ContractToolError("private compilation case catalog is not an object")
    cas_inventory = case_catalog.get("casInventory")
    if not isinstance(cas_inventory, list) or not cas_inventory:
        raise ContractToolError("private compilation CAS inventory is absent or empty")
    inventory_digests: list[str] = []
    inventory_paths: list[str] = []
    for index, entry in enumerate(cas_inventory):
        if not isinstance(entry, dict) or set(entry) != {
            "digest",
            "size",
            "blobPath",
            "source",
        }:
            raise ContractToolError(
                f"private compilation CAS inventory entry is malformed: {index}"
            )
        digest = entry["digest"]
        size = entry["size"]
        blob_path = entry["blobPath"]
        source = entry["source"]
        if (
            not isinstance(digest, str)
            or len(digest) != 71
            or not digest.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in digest[7:])
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(blob_path, str)
            or blob_path != PRIVATE_CAS_PREFIX + digest[7:]
            or source not in {"private-graph", "renderer-closure"}
        ):
            raise ContractToolError(
                f"private compilation CAS inventory entry is invalid: {index}"
            )
        inventory_digests.append(digest)
        inventory_paths.append(blob_path)
    if inventory_digests != sorted(inventory_digests):
        raise ContractToolError("private compilation CAS inventory is not sorted")
    if (
        len(inventory_digests) != len(set(inventory_digests))
        or len(inventory_paths) != len(set(inventory_paths))
    ):
        raise ContractToolError("private compilation CAS inventory contains duplicates")

    private_graph = case_catalog.get("positiveGraph")
    if not isinstance(private_graph, dict):
        raise ContractToolError("private compilation positive graph is not an object")
    artifacts = private_graph.get("artifacts")
    supporting_artifacts = private_graph.get("supportingArtifacts")
    supporting_digests = private_graph.get("supportingDigests")
    if not all(
        isinstance(value, list)
        for value in (artifacts, supporting_artifacts, supporting_digests)
    ):
        raise ContractToolError("private compilation positive graph catalogs are invalid")
    descriptor_artifacts = [*artifacts, *supporting_artifacts]
    positive_graph_blobs: set[str] = set()
    for index, artifact in enumerate(descriptor_artifacts):
        if not isinstance(artifact, dict) or not isinstance(
            artifact.get("blobPath"), str
        ):
            raise ContractToolError(
                f"private compilation artifact entry is invalid: {index}"
            )
        positive_graph_blobs.add(artifact["blobPath"])
    for index, entry in enumerate(supporting_digests):
        if not isinstance(entry, dict) or not isinstance(entry.get("blobPath"), str):
            raise ContractToolError(
                f"private compilation supporting digest is invalid: {index}"
            )
        positive_graph_blobs.add(entry["blobPath"])

    expected_private_blobs = set(inventory_paths)
    if not positive_graph_blobs.issubset(expected_private_blobs):
        raise ContractToolError(
            "private compilation positive graph references blobs outside its CAS inventory"
        )
    actual_private_blobs = {
        path for path in members if path.startswith(PRIVATE_CAS_PREFIX)
    }
    if actual_private_blobs != expected_private_blobs:
        raise ContractToolError(
            "private compilation CAS is not the exact closed catalog: "
            f"missing={sorted(expected_private_blobs-actual_private_blobs)} "
            f"extra={sorted(actual_private_blobs-expected_private_blobs)}"
        )
    for entry in cas_inventory:
        payload = members[entry["blobPath"]]
        if entry["digest"] != sha256_bytes(payload) or entry["size"] != len(payload):
            raise ContractToolError(
                "private compilation CAS inventory object mismatch: "
                f"{entry['digest']}"
            )
        if entry["source"] == "private-graph":
            if entry["blobPath"] not in positive_graph_blobs:
                raise ContractToolError(
                    "private-graph CAS inventory entry has no positive-graph reference: "
                    f"{entry['digest']}"
                )
        else:
            renderer_path = RENDERER_CAS_PREFIX + entry["digest"][7:]
            if members.get(renderer_path) != payload:
                raise ContractToolError(
                    "renderer-closure CAS inventory entry has no byte-identical "
                    f"renderer member: {entry['digest']}"
                )
    return cas_inventory, expected_private_blobs, private_graph, descriptor_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    members = read_archive(args.bundle.resolve())
    manifest = strict_json_bytes(members[MANIFEST_ARCHIVE_PATH], MANIFEST_ARCHIVE_PATH)
    if not isinstance(manifest, dict):
        raise ContractToolError("test bundle manifest is not an object")
    policy = manifest.get("trustPolicy")
    if not isinstance(policy, dict):
        raise ContractToolError("test bundle manifest has no trust policy")
    verify_inventory(manifest, members)
    private_cases = strict_json_bytes(members[PRIVATE_CASE_PATH], PRIVATE_CASE_PATH)
    cas_inventory, expected_private_blobs, private_graph, descriptor_artifacts = (
        verify_private_cas_inventory(private_cases, members)
    )
    for artifact in descriptor_artifacts:
        descriptor = artifact["descriptor"]
        blob_path = artifact["blobPath"]
        payload = members[blob_path]
        if (
            descriptor["digest"] != sha256_bytes(payload)
            or descriptor["size"] != len(payload)
            or blob_path.rsplit("/", 1)[-1]
            != descriptor["digest"].removeprefix("sha256:")
        ):
            raise ContractToolError(
                f"private compilation CAS descriptor mismatch: {artifact['role']}"
            )
        projection_path = artifact["projectionPath"]
        if projection_path is not None:
            projection = strict_json_bytes(members[projection_path], projection_path)
            if canonical_json(projection) != payload:
                raise ContractToolError(
                    f"private compilation projection/CAS mismatch: {artifact['role']}"
                )
    for digest_entry in private_graph["supportingDigests"]:
        payload = members[digest_entry["blobPath"]]
        if (
            digest_entry["digest"] != sha256_bytes(payload)
            or digest_entry["size"] != len(payload)
            or digest_entry["blobPath"].rsplit("/", 1)[-1]
            != digest_entry["digest"].removeprefix("sha256:")
        ):
            raise ContractToolError(
                "private compilation CAS digest object mismatch: "
                f"{digest_entry['role']}"
            )
    registry, schemas = build_bundle_registry(manifest, members, policy)
    errors = sorted(
        Draft202012Validator(
            schemas[CONTRACT_BUNDLE_SCHEMA_ID][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(manifest),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"baseline bundled manifest rejected: {errors[0].message}")
    cases: list[dict[str, str]] = [
        {"id": "baseline-bundle-registry", "outcome": "permitted"},
        {"id": "private-compilation-cas-closed-and-resolvable", "outcome": "permitted"},
    ]

    def record_private_cas_denial(
        case_id: str,
        catalog: dict[str, Any],
        archive_members: dict[str, bytes] = members,
    ) -> None:
        cases.append(
            expect_denial(
                case_id,
                lambda: verify_private_cas_inventory(catalog, archive_members),
            )
        )

    unsorted_catalog = deepcopy(private_cases)
    unsorted_catalog["casInventory"][0], unsorted_catalog["casInventory"][1] = (
        unsorted_catalog["casInventory"][1],
        unsorted_catalog["casInventory"][0],
    )
    record_private_cas_denial(
        "private-compilation-cas-inventory-unsorted", unsorted_catalog
    )

    duplicate_catalog = deepcopy(private_cases)
    duplicate_catalog["casInventory"].append(
        deepcopy(duplicate_catalog["casInventory"][-1])
    )
    record_private_cas_denial(
        "private-compilation-cas-inventory-duplicate", duplicate_catalog
    )

    unknown_member_catalog = deepcopy(private_cases)
    unknown_member_catalog["casInventory"][0]["authority"] = "forged"
    record_private_cas_denial(
        "private-compilation-cas-inventory-unknown-member",
        unknown_member_catalog,
    )

    unknown_source_catalog = deepcopy(private_cases)
    unknown_source_catalog["casInventory"][0]["source"] = "untrusted-extension"
    record_private_cas_denial(
        "private-compilation-cas-inventory-unknown-source",
        unknown_source_catalog,
    )

    path_substitution_catalog = deepcopy(private_cases)
    substituted_entry = path_substitution_catalog["casInventory"][0]
    substituted_hex = substituted_entry["digest"][7:]
    substituted_hex = ("1" if substituted_hex[0] == "0" else "0") + substituted_hex[1:]
    substituted_entry["blobPath"] = PRIVATE_CAS_PREFIX + substituted_hex
    record_private_cas_denial(
        "private-compilation-cas-inventory-path-digest-substitution",
        path_substitution_catalog,
    )

    positive_graph_paths = {
        entry["blobPath"]
        for entry in [
            *private_graph["artifacts"],
            *private_graph["supportingArtifacts"],
            *private_graph["supportingDigests"],
        ]
    }
    omitted_catalog = deepcopy(private_cases)
    omitted_entry = next(
        entry
        for entry in omitted_catalog["casInventory"]
        if entry["blobPath"] not in positive_graph_paths
    )
    omitted_catalog["casInventory"].remove(omitted_entry)
    record_private_cas_denial(
        "private-compilation-cas-inventory-member-omitted", omitted_catalog
    )

    extra_catalog = deepcopy(private_cases)
    inventory_digest_set = {
        entry["digest"] for entry in extra_catalog["casInventory"]
    }
    extra_hex = "f" * 64
    if f"sha256:{extra_hex}" in inventory_digest_set:
        extra_hex = "e" * 64
    extra_catalog["casInventory"].append(
        {
            "digest": f"sha256:{extra_hex}",
            "size": 0,
            "blobPath": PRIVATE_CAS_PREFIX + extra_hex,
            "source": "renderer-closure",
        }
    )
    extra_catalog["casInventory"].sort(key=lambda entry: entry["digest"])
    record_private_cas_denial(
        "private-compilation-cas-inventory-unbacked-entry", extra_catalog
    )

    graph_reference_catalog = deepcopy(private_cases)
    graph_entry = next(
        entry
        for entry in graph_reference_catalog["casInventory"]
        if entry["blobPath"] in positive_graph_paths
    )
    graph_reference_catalog["casInventory"].remove(graph_entry)
    record_private_cas_denial(
        "private-compilation-positive-graph-reference-outside-inventory",
        graph_reference_catalog,
    )

    tampered_cas_members = dict(members)
    tampered_path = sorted(expected_private_blobs)[0]
    tampered_payload = bytearray(tampered_cas_members[tampered_path])
    tampered_payload[0] ^= 1
    tampered_cas_members[tampered_path] = bytes(tampered_payload)
    cases.append(
        expect_denial(
            "private-compilation-cas-byte-substitution",
            lambda: verify_inventory(manifest, tampered_cas_members),
        )
    )

    authoritative_manifest = deepcopy(manifest)
    authoritative_members = dict(members)
    authoritative_schema = deepcopy(schemas[SIGNING_REQUEST_SCHEMA_ID][1])
    authoritative_schema["$comment"] = "bundle-member-authority-conformance-probe"
    replace_schema(
        authoritative_manifest,
        authoritative_members,
        SIGNING_REQUEST_SCHEMA_ID,
        authoritative_schema,
    )
    cases.append(
        expect_denial(
            "schema-digest-stale-against-closed-inventory",
            lambda: build_bundle_registry(
                authoritative_manifest,
                authoritative_members,
                policy,
            ),
        )
    )

    removable_entry = next(
        entry
        for entry in manifest["schemas"]
        if entry["id"].endswith("/application-config/1.0.0")
    )
    removed_manifest = deepcopy(manifest)
    removed_manifest["schemas"] = [
        entry
        for entry in removed_manifest["schemas"]
        if entry["id"] != removable_entry["id"]
    ]
    removed_members = dict(members)
    removed_members.pop(removable_entry["path"])
    cases.append(
        expect_denial(
            "schema-removed-against-closed-inventory",
            lambda: build_bundle_registry(removed_manifest, removed_members, policy),
        )
    )

    substituted_manifest = deepcopy(manifest)
    substituted_members = dict(members)
    substituted_entry = next(
        entry
        for entry in substituted_manifest["schemas"]
        if entry["id"] == removable_entry["id"]
    )
    substituted_schema = deepcopy(schemas[removable_entry["id"]][1])
    substituted_id = (
        "https://schemas.bytedesk.ai/agent-delivery/v1/substituted-application-config/1.0.0"
    )
    substituted_schema["$id"] = substituted_id
    substituted_payload = canonical_json(substituted_schema)
    substituted_members[substituted_entry["path"]] = substituted_payload
    substituted_entry["id"] = substituted_id
    substituted_entry["digest"] = sha256_bytes(substituted_payload)
    substituted_entry["size"] = len(substituted_payload)
    cases.append(
        expect_denial(
            "schema-id-substituted-against-closed-inventory",
            lambda: build_bundle_registry(
                substituted_manifest, substituted_members, policy
            ),
        )
    )

    signing_entry = next(
        entry for entry in manifest["schemas"] if entry["id"] == SIGNING_REQUEST_SCHEMA_ID
    )
    missing_members = dict(members)
    missing_members.pop(signing_entry["path"])
    cases.append(
        expect_denial(
            "missing-schema-member",
            lambda: build_bundle_registry(manifest, missing_members, policy),
        )
    )

    digest_members = dict(members)
    digest_members[signing_entry["path"]] += b" "
    cases.append(
        expect_denial(
            "schema-digest-size-mismatch",
            lambda: build_bundle_registry(manifest, digest_members, policy),
        )
    )

    id_manifest = deepcopy(manifest)
    id_members = dict(members)
    id_schema = deepcopy(schemas[SIGNING_REQUEST_SCHEMA_ID][1])
    id_schema["$id"] = "https://schemas.bytedesk.ai/agent-delivery/v1/substituted/1.0.0"
    replace_schema(id_manifest, id_members, SIGNING_REQUEST_SCHEMA_ID, id_schema)
    cases.append(
        expect_denial(
            "schema-id-inventory-substitution",
            lambda: build_bundle_registry(id_manifest, id_members, policy),
        )
    )

    invalid_manifest = deepcopy(manifest)
    invalid_members = dict(members)
    invalid_schema = deepcopy(schemas[SIGNING_REQUEST_SCHEMA_ID][1])
    invalid_schema["type"] = 7
    replace_schema(invalid_manifest, invalid_members, SIGNING_REQUEST_SCHEMA_ID, invalid_schema)
    cases.append(
        expect_denial(
            "schema-metaschema-denial",
            lambda: build_bundle_registry(invalid_manifest, invalid_members, policy),
        )
    )

    reference_manifest = deepcopy(manifest)
    reference_members = dict(members)
    reference_schema = deepcopy(schemas[SIGNING_REQUEST_SCHEMA_ID][1])
    reference_schema.setdefault("allOf", []).append(
        {"$ref": "https://schemas.bytedesk.ai/agent-delivery/v1/absent/1.0.0"}
    )
    replace_schema(
        reference_manifest,
        reference_members,
        SIGNING_REQUEST_SCHEMA_ID,
        reference_schema,
    )
    cases.append(
        expect_denial(
            "offline-reference-closure",
            lambda: build_bundle_registry(reference_manifest, reference_members, policy),
        )
    )

    policy_manifest = deepcopy(manifest)
    policy_manifest["schemas"][0]["trustPolicy"] = {
        "id": "substituted-product-release-v1",
        "digest": "sha256:" + "b" * 64,
    }
    cases.append(
        expect_denial(
            "schema-trust-policy-substitution",
            lambda: build_bundle_registry(policy_manifest, members, policy),
        )
    )

    oversized_schema_manifest = deepcopy(manifest)
    oversized_schema_members = dict(members)
    oversized_schema_payload = b" " * (MAX_STRUCTURED_JSON_BYTES + 1)
    oversized_schema_members[signing_entry["path"]] = oversized_schema_payload
    oversized_schema_entry = next(
        entry
        for entry in oversized_schema_manifest["schemas"]
        if entry["id"] == SIGNING_REQUEST_SCHEMA_ID
    )
    oversized_schema_entry["digest"] = sha256_bytes(oversized_schema_payload)
    oversized_schema_entry["size"] = len(oversized_schema_payload)
    cases.append(
        expect_denial(
            "oversized-bundled-schema-json",
            lambda: build_bundle_registry(
                oversized_schema_manifest, oversized_schema_members, policy
            ),
        )
    )

    fixture_index = strict_json_bytes(
        members[manifest["fixtureIndex"]["path"]], manifest["fixtureIndex"]["path"]
    )
    fixture_path = fixture_index["fixtures"][0]["path"]
    fixture_denials = {
        "oversized-bundled-fixture-json": b" " * (MAX_STRUCTURED_JSON_BYTES + 1),
        "over-depth-bundled-fixture-json": b"[" * MAX_JSON_MODEL_DEPTH
        + b"0"
        + b"]" * MAX_JSON_MODEL_DEPTH,
        "over-node-bundled-fixture-json": b"["
        + b",".join([b"0"] * MAX_JSON_MODEL_NODES)
        + b"]",
        "unsafe-integer-bundled-fixture-json": str(MAX_SAFE_INTEGER + 1).encode(),
        "huge-exponent-bundled-fixture-json": b"1e1000000",
        "lone-surrogate-bundled-fixture-json": b'"\\ud800"',
    }
    for case_id, payload in fixture_denials.items():
        fixture_manifest = deepcopy(manifest)
        fixture_members = dict(members)
        replace_document(fixture_manifest, fixture_members, fixture_path, payload)
        cases.append(
            expect_denial(
                case_id,
                lambda manifest=fixture_manifest, archive=fixture_members: verify_inventory(
                    manifest, archive
                ),
            )
        )

    result = {
        "profile": "bytedesk.offline-bundle-schema-authority-conformance/1",
        "schemaAuthority": "closed-jcs-inventory-and-manifest-bundle-members",
        "caseCount": len(cases),
        "cases": cases,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError, StopIteration) as error:
        print(f"bundle self-containment conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
