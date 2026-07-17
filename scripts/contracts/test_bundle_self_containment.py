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
        {"id": "baseline-bundle-registry", "outcome": "permitted"}
    ]

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
