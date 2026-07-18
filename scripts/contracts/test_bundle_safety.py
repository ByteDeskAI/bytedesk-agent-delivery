#!/usr/bin/env python3
"""Exercise compiled release-bundle exclusions against real repository inputs."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import sys
from typing import Any, Callable

from jsonschema import Draft202012Validator

from build_bundle import (
    expand_inputs,
    repository_only_release_path as builder_rejects,
    validate_bundle_source,
    validate_compatibility,
    validate_documentation_map,
)
from compare_validator_evidence import required_keyword_proofs, required_semantic_proofs
from contractlib import (
    CONTRACTS_ROOT,
    REPOSITORY_ROOT,
    SCHEMAS_ROOT,
    ContractToolError,
    load_json,
    repository_path,
    stable_file_digest,
    write_json,
)
from lint_projections import (
    ASYNCAPI_DOCUMENT_URI,
    ASYNCAPI_ROOT_FIELDS,
    OPENAPI_DOCUMENT_URI,
    OPENAPI_PATH,
    OPENAPI_ROOT_FIELDS,
    check_header_object,
    check_projection_root,
    validate_event_type_registry,
)
from validate_schemas import (
    SCHEMA_INVENTORY_PATH,
    build_registry,
    validate_denial_fixture_coverage,
    validate_fixture_index_document,
    validate_positive_fixture_coverage,
    validate_schema_inventory,
)
from verify_bundle import (
    repository_only_release_path as verifier_rejects,
    validate_bundled_documentation_map,
)
from bundle_profile import BundleProfileError, normalized_member_payload


SOURCE_CONFIG = CONTRACTS_ROOT / "bundle" / "v1" / "bundle-source.json"
FORBIDDEN_INPUTS = (
    "contracts/schemas/repository/development-plan.schema.json",
    "contracts/fixtures/schema/repository-index.json",
    "contracts/fixtures/schema/positive/development-plan__current.json",
    "contracts/fixtures/schema/negative/development-plan__product-contract-marker.json",
)


def expect_denial(
    denials: list[dict[str, str]],
    case: str,
    operation: Callable[[], Any],
    expected_message: str,
) -> None:
    try:
        operation()
    except ContractToolError as error:
        if expected_message not in str(error):
            raise ContractToolError(
                f"unexpected metadata denial for {case}: {error}"
            ) from error
        denials.append({"case": case, "outcome": "denied"})
    else:
        raise ContractToolError(f"malformed metadata was accepted: {case}")


def single_property_repairs(
    instance: dict[str, Any],
    validator: Draft202012Validator,
) -> list[tuple[str | int, ...]]:
    """Return property paths whose removal makes one denial fixture valid."""

    property_paths: list[tuple[str | int, ...]] = []

    def collect(value: Any, path: tuple[str | int, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = (*path, key)
                property_paths.append(child_path)
                collect(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect(child, (*path, index))

    collect(instance, ())
    repairs: list[tuple[str | int, ...]] = []
    for property_path in property_paths:
        candidate = deepcopy(instance)
        parent: Any = candidate
        for segment in property_path[:-1]:
            parent = parent[segment]
        del parent[property_path[-1]]
        if validator.is_valid(candidate):
            repairs.append(property_path)
    return repairs


def exercise_metadata_denials(denials: list[dict[str, str]]) -> None:
    fixture_index = load_json(CONTRACTS_ROOT / "fixtures" / "schema" / "index.json")
    schemas = {
        schema["$id"]: (path, schema)
        for path in sorted(SCHEMAS_ROOT.glob("*.schema.json"))
        for schema in [load_json(path)]
    }
    schema_ids = set(schemas)

    schema_inventory = load_json(SCHEMA_INVENTORY_PATH)
    validate_schema_inventory(schema_inventory, schemas)
    mutated = deepcopy(schema_inventory)
    mutated["authority"] = "smuggled"
    expect_denial(
        denials,
        "schema-inventory-unknown-root-field",
        lambda: validate_schema_inventory(mutated, schemas),
        "root is not closed",
    )
    mutated = deepcopy(schema_inventory)
    mutated["schemas"][0]["force"] = True
    expect_denial(
        denials,
        "schema-inventory-unknown-entry-field",
        lambda: validate_schema_inventory(mutated, schemas),
        "entry 0 is not closed",
    )
    mutated = deepcopy(schema_inventory)
    mutated["schemas"].pop(0)
    expect_denial(
        denials,
        "schema-inventory-removal",
        lambda: validate_schema_inventory(mutated, schemas),
        "schema inventory mismatch",
    )

    mutated = deepcopy(fixture_index)
    mutated["authority"] = "smuggled"
    expect_denial(
        denials,
        "fixture-index-unknown-root-field",
        lambda: validate_fixture_index_document(mutated),
        "root has unknown fields",
    )
    mutated = deepcopy(fixture_index)
    mutated["fixtures"][0]["force"] = True
    expect_denial(
        denials,
        "fixture-index-unknown-entry-field",
        lambda: validate_fixture_index_document(mutated),
        "entry 0 has unknown fields",
    )
    mutated = deepcopy(fixture_index)
    mutated["fixtures"][0]["category"] = "advisory"
    expect_denial(
        denials,
        "fixture-index-invalid-category",
        lambda: validate_fixture_index_document(mutated),
        "invalid category",
    )
    mutated = deepcopy(fixture_index)
    mutated["fixtures"][0]["category"] = "negative"
    expect_denial(
        denials,
        "fixture-index-category-validity-mismatch",
        lambda: validate_fixture_index_document(mutated),
        "does not match valid",
    )
    mutated = deepcopy(fixture_index)
    mutated["fixtures"][0]["expectedKeyword"] = None
    expect_denial(
        denials,
        "fixture-index-null-expected-keyword",
        lambda: validate_fixture_index_document(mutated),
        "expectedKeyword",
    )
    mutated = deepcopy(fixture_index)
    mutated["fixtures"][0]["expectedKeyword"] = ["required", "required"]
    expect_denial(
        denials,
        "fixture-index-duplicate-expected-keyword",
        lambda: validate_fixture_index_document(mutated),
        "unique",
    )
    mutated = deepcopy(fixture_index)
    mutated["fixtures"][0]["expectedSemanticError"] = "advisory"
    expect_denial(
        denials,
        "fixture-index-unknown-semantic-error",
        lambda: validate_fixture_index_document(mutated),
        "expectedSemanticError",
    )
    mutated = deepcopy(fixture_index)
    structural_denial = next(
        entry
        for entry in mutated["fixtures"]
        if entry["valid"] is False and entry["expectedKeyword"]
    )
    structural_denial["expectedSemanticError"] = "schema_id_mismatch"
    expect_denial(
        denials,
        "fixture-index-mixed-denial-proof-classes",
        lambda: validate_fixture_index_document(mutated),
        "exactly one of expectedKeyword or expectedSemanticError",
    )
    mutated = deepcopy(fixture_index)
    denial = next(entry for entry in mutated["fixtures"] if entry["valid"] is False)
    denial["expectedKeyword"] = []
    expect_denial(
        denials,
        "fixture-index-empty-denial-expected-keyword",
        lambda: validate_fixture_index_document(mutated),
        "denial fixture expectedKeyword must not be empty",
    )
    parsed = validate_fixture_index_document(fixture_index)
    uncovered_id = next(iter(sorted(schema_ids)))
    without_one_positive = [
        entry
        for entry in parsed
        if not (
            entry["schemaId"] == uncovered_id
            and entry["valid"] is True
            and entry["category"] == "positive"
        )
    ]
    expect_denial(
        denials,
        "fixture-index-missing-schema-positive",
        lambda: validate_positive_fixture_coverage(without_one_positive, schema_ids),
        "schemas lack indexed valid positive fixtures",
    )
    denial_schema_id = next(
        entry["schemaId"] for entry in parsed if entry["valid"] is False
    )
    without_one_denial = [
        entry
        for entry in parsed
        if not (entry["schemaId"] == denial_schema_id and entry["valid"] is False)
    ]
    expect_denial(
        denials,
        "fixture-index-missing-schema-denial",
        lambda: validate_denial_fixture_coverage(without_one_denial, schemas),
        "schemas lack indexed denial fixtures",
    )
    malformed_common = deepcopy(schemas)
    common_id = "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0"
    common_path, common_schema = malformed_common[common_id]
    common_schema = deepcopy(common_schema)
    common_schema["type"] = "object"
    malformed_common[common_id] = (common_path, common_schema)
    expect_denial(
        denials,
        "common-denial-exemption-gained-instance-contract",
        lambda: validate_denial_fixture_coverage(parsed, malformed_common),
        "definitions-library root",
    )
    keyword_fixture = {
        "path": "contracts/fixtures/schema/negative/example.json",
        "schemaId": "https://schemas.bytedesk.ai/agent-delivery/v1/example/1.0.0",
        "valid": False,
        "category": "negative",
        "expectedKeyword": "unevaluatedProperties",
    }
    go_keyword_evidence = {
        keyword_fixture["path"]: {
            "schemaId": keyword_fixture["schemaId"],
            "expectedValid": False,
            "observedKeywords": ["unevaluatedProperties"],
            "outcome": "pass",
        }
    }
    python_keyword_evidence = deepcopy(go_keyword_evidence)
    python_keyword_evidence[keyword_fixture["path"]]["observedKeywords"] = ["required"]
    expect_denial(
        denials,
        "validator-comparator-missing-required-keyword",
        lambda: required_keyword_proofs(
            go_keyword_evidence, python_keyword_evidence, [keyword_fixture]
        ),
        "python fixture evidence missed required keywords",
    )
    semantic_fixture = {
        "path": "contracts/fixtures/schema/malicious/wrong-schema.json",
        "schemaId": "https://schemas.bytedesk.ai/agent-delivery/v1/example/1.0.0",
        "valid": False,
        "category": "malicious",
        "expectedKeyword": [],
        "expectedSemanticError": "schema_id_mismatch",
    }
    go_semantic_evidence = {
        semantic_fixture["path"]: {
            "schemaId": semantic_fixture["schemaId"],
            "expectedValid": False,
            "observedKeywords": [],
            "observedSemanticError": "schema_id_mismatch",
            "outcome": "pass",
        }
    }
    python_semantic_evidence = deepcopy(go_semantic_evidence)
    python_semantic_evidence[semantic_fixture["path"]][
        "observedSemanticError"
    ] = "schema_digest_mismatch"
    expect_denial(
        denials,
        "validator-comparator-missing-required-semantic-error",
        lambda: required_semantic_proofs(
            go_semantic_evidence, python_semantic_evidence, [semantic_fixture]
        ),
        "python fixture evidence missed required semantic error",
    )

    event_types = load_json(CONTRACTS_ROOT / "events" / "v1" / "event-types.json")
    mutated = deepcopy(event_types)
    mutated["consumerAuthority"] = True
    expect_denial(
        denials,
        "event-types-unknown-root-field",
        lambda: validate_event_type_registry(mutated),
        "root has unknown fields",
    )
    mutated = deepcopy(event_types)
    mutated["eventTypes"][0]["grant"] = "smuggled"
    expect_denial(
        denials,
        "event-types-unknown-entry-field",
        lambda: validate_event_type_registry(mutated),
        "entry has unknown fields",
    )

    documentation_map = load_json(CONTRACTS_ROOT / "bundle" / "v1" / "documentation-map.json")
    bundled_schema_ids = {entry["id"] for entry in documentation_map["schemas"]}
    bundled_paths = {
        repository_path(path)
        for path in expand_inputs(load_json(SOURCE_CONFIG))
    }
    validate_documentation_map(documentation_map, bundled_schema_ids, bundled_paths)
    validate_bundled_documentation_map(
        documentation_map,
        bundled_schema_ids,
        bundled_paths,
    )
    denials.append(
        {
            "case": "documentation-map-current-repository-and-offline-baseline",
            "outcome": "permitted",
        }
    )

    mutated = deepcopy(documentation_map)
    mutated["authority"] = "smuggled"
    expect_denial(
        denials,
        "documentation-map-unknown-root-field",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "root has unknown fields",
    )
    mutated = deepcopy(documentation_map)
    mutated["schemas"][0]["deprecated"] = False
    expect_denial(
        denials,
        "documentation-map-unknown-schema-entry-field",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "schema entry is not closed",
    )
    mutated = deepcopy(documentation_map)
    mutated["projections"][0]["authority"] = "smuggled"
    expect_denial(
        denials,
        "documentation-map-unknown-projection-entry-field",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "projection entry is not closed",
    )

    mutated = deepcopy(documentation_map)
    del mutated["documents"][0]
    expect_denial(
        denials,
        "documentation-map-missing-inventory-entry-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation reference closure differs",
    )
    expect_denial(
        denials,
        "documentation-map-missing-inventory-entry-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation reference closure differs",
    )

    extra_document_path = "docs/README.md"
    extra_document_digest, _ = stable_file_digest(
        REPOSITORY_ROOT / extra_document_path,
        description="extra documentation-map denial fixture",
    )
    mutated = deepcopy(documentation_map)
    mutated["documents"].append(
        {"path": extra_document_path, "digest": extra_document_digest}
    )
    mutated["documents"].sort(key=lambda entry: entry["path"])
    expect_denial(
        denials,
        "documentation-map-extra-inventory-entry-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation reference closure differs",
    )
    expect_denial(
        denials,
        "documentation-map-extra-inventory-entry-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation reference closure differs",
    )

    mutated = deepcopy(documentation_map)
    mutated["documents"][0]["digest"] = f"sha256:{'0' * 64}"
    expect_denial(
        denials,
        "documentation-map-stale-inventory-digest-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation digest differs from repository bytes",
    )

    mutated = deepcopy(documentation_map)
    mutated["documents"][0]["digest"] = "sha256:not-a-digest"
    expect_denial(
        denials,
        "documentation-map-malformed-inventory-digest-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation inventory digest is invalid",
    )
    expect_denial(
        denials,
        "documentation-map-malformed-inventory-digest-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation inventory digest is invalid",
    )

    mutated = deepcopy(documentation_map)
    mutated["documents"][0]["authority"] = "smuggled"
    expect_denial(
        denials,
        "documentation-map-unknown-inventory-entry-field-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation inventory entry is not closed",
    )
    expect_denial(
        denials,
        "documentation-map-unknown-inventory-entry-field-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation inventory entry is not closed",
    )

    mutated = deepcopy(documentation_map)
    mutated["schemas"][0]["documents"][0] = extra_document_path
    expect_denial(
        denials,
        "documentation-map-uninventoried-schema-reference-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation reference closure differs",
    )
    expect_denial(
        denials,
        "documentation-map-uninventoried-schema-reference-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation reference closure differs",
    )

    mutated = deepcopy(documentation_map)
    mutated["documents"][0], mutated["documents"][1] = (
        mutated["documents"][1],
        mutated["documents"][0],
    )
    expect_denial(
        denials,
        "documentation-map-unsorted-inventory-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation inventory is not strictly sorted",
    )
    expect_denial(
        denials,
        "documentation-map-unsorted-inventory-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation inventory is not strictly sorted",
    )

    mutated = deepcopy(documentation_map)
    mutated["documents"].insert(1, deepcopy(mutated["documents"][0]))
    expect_denial(
        denials,
        "documentation-map-duplicate-inventory-entry-builder",
        lambda: validate_documentation_map(mutated, bundled_schema_ids, bundled_paths),
        "documentation inventory is not strictly sorted",
    )
    expect_denial(
        denials,
        "documentation-map-duplicate-inventory-entry-offline",
        lambda: validate_bundled_documentation_map(
            mutated, bundled_schema_ids, bundled_paths
        ),
        "documentation inventory is not strictly sorted",
    )

    compatibility = load_json(CONTRACTS_ROOT / "bundle" / "v1" / "compatibility.json")
    mutated = deepcopy(compatibility)
    mutated["override"] = True
    expect_denial(
        denials,
        "compatibility-unknown-root-field",
        lambda: validate_compatibility(mutated),
        "root has unknown fields",
    )
    mutated = deepcopy(compatibility)
    mutated["rules"]["force"] = "allow"
    expect_denial(
        denials,
        "compatibility-unknown-rule",
        lambda: validate_compatibility(mutated),
        "rules have unknown or missing fields",
    )
    mutated = deepcopy(compatibility)
    del mutated["rules"]["unknownAuthorityField"]
    expect_denial(
        denials,
        "compatibility-missing-rule",
        lambda: validate_compatibility(mutated),
        "rules have unknown or missing fields",
    )
    mutated = deepcopy(compatibility)
    mutated["rules"]["unknownAuthorityField"] = "allow"
    expect_denial(
        denials,
        "compatibility-rule-value-drift",
        lambda: validate_compatibility(mutated),
        "rules are incomplete or drifted",
    )
    mutated = deepcopy(compatibility)
    mutated["supportedInteroperability"][0]["force"] = True
    expect_denial(
        denials,
        "compatibility-open-interoperability-entry",
        lambda: validate_compatibility(mutated),
        "interoperability entry is not closed",
    )

    bundle_source = load_json(SOURCE_CONFIG)
    mutated = deepcopy(bundle_source)
    mutated["hooks"] = ["run-me"]
    expect_denial(
        denials,
        "bundle-source-unknown-root-field",
        lambda: validate_bundle_source(mutated),
        "root has unknown fields",
    )
    mutated = deepcopy(bundle_source)
    mutated["schemaInventory"] = "contracts/bundle/v1/substituted.json"
    expect_denial(
        denials,
        "bundle-source-schema-inventory-path-substitution",
        lambda: validate_bundle_source(mutated),
        "noncanonical schema inventory path",
    )

    registry, validation_schemas = build_registry()
    single_fault_count = 0
    for entry in parsed:
        if not entry["path"].endswith("__unknown-authority-field.json"):
            continue
        instance = load_json(CONTRACTS_ROOT.parent / entry["path"])
        if not isinstance(instance, dict):
            raise ContractToolError(
                f"unknown-authority denial is not a closed single-field mutation: {entry['path']}"
            )
        validator = Draft202012Validator(
            validation_schemas[entry["schemaId"]][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        repairs = single_property_repairs(instance, validator)
        if len(repairs) != 1:
            raise ContractToolError(
                "unknown-authority denial is not a closed single-field mutation: "
                f"{entry['path']}: repair candidates={repairs}"
            )
        single_fault_count += 1
    if single_fault_count == 0:
        raise ContractToolError("no unknown-authority single-fault denials were exercised")
    denials.append(
        {
            "case": f"unknown-authority-single-fault-{single_fault_count}",
            "outcome": "proved",
        }
    )


def exercise_projection_denials(denials: list[dict[str, str]]) -> None:
    openapi = load_json(OPENAPI_PATH)
    asyncapi = load_json(
        CONTRACTS_ROOT / "asyncapi" / "v1" / "agent-delivery.asyncapi.json"
    )

    mutated = deepcopy(openapi)
    mutated["$id"] = "https://example.invalid/shadow-identity"
    expect_denial(
        denials,
        "openapi-unknown-fixed-root-field",
        lambda: check_projection_root(
            mutated,
            OPENAPI_ROOT_FIELDS,
            "$self",
            OPENAPI_DOCUMENT_URI,
            "OpenAPI",
        ),
        "unknown fixed fields",
    )
    mutated = deepcopy(openapi)
    mutated["x_invalid"] = True
    expect_denial(
        denials,
        "openapi-malformed-extension-root-field",
        lambda: check_projection_root(
            mutated,
            OPENAPI_ROOT_FIELDS,
            "$self",
            OPENAPI_DOCUMENT_URI,
            "OpenAPI",
        ),
        "unknown fixed fields",
    )
    mutated = deepcopy(asyncapi)
    mutated["$self"] = OPENAPI_DOCUMENT_URI
    expect_denial(
        denials,
        "asyncapi-openapi-self-field",
        lambda: check_projection_root(
            mutated,
            ASYNCAPI_ROOT_FIELDS,
            "x-bytedesk-document-uri",
            ASYNCAPI_DOCUMENT_URI,
            "AsyncAPI",
        ),
        "unknown fixed fields",
    )
    mutated = deepcopy(asyncapi)
    mutated["x-bytedesk-document-uri"] = "https://example.invalid/substitution"
    expect_denial(
        denials,
        "asyncapi-document-uri-substitution",
        lambda: check_projection_root(
            mutated,
            ASYNCAPI_ROOT_FIELDS,
            "x-bytedesk-document-uri",
            ASYNCAPI_DOCUMENT_URI,
            "AsyncAPI",
        ),
        "exact stable document URI",
    )

    expect_denial(
        denials,
        "openapi-header-unknown-field",
        lambda: check_header_object(
            OPENAPI_PATH,
            {"name": "ETag", "schema": {"type": "string"}},
            "test header",
        ),
        "unknown Header Object fields",
    )
    expect_denial(
        denials,
        "openapi-header-schema-content-conflict",
        lambda: check_header_object(
            OPENAPI_PATH,
            {
                "schema": {"type": "string"},
                "content": {"text/plain": {"schema": {"type": "string"}}},
            },
            "test header",
        ),
        "exactly one of schema or content",
    )
    expect_denial(
        denials,
        "openapi-header-nonboolean-required",
        lambda: check_header_object(
            OPENAPI_PATH,
            {"required": "true", "schema": {"type": "string"}},
            "test header",
        ),
        "required field is not boolean",
    )
    expect_denial(
        denials,
        "openapi-header-invalid-style",
        lambda: check_header_object(
            OPENAPI_PATH,
            {"style": "form", "schema": {"type": "string"}},
            "test header",
        ),
        "non-header serialization style",
    )
    expect_denial(
        denials,
        "openapi-header-reference-sibling",
        lambda: check_header_object(
            OPENAPI_PATH,
            {"$ref": "#/components/headers/ETag", "name": "ETag"},
            "test header",
        ),
        "reference has unknown fields",
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=str)
    args = parser.parse_args()

    source = load_json(SOURCE_CONFIG)
    denials: list[dict[str, str]] = []
    private_cas_include = (
        "contracts/fixtures/operations/private-compilation-cas/blobs/sha256/*"
    )
    if source["include"].count(private_cas_include) != 1:
        raise ContractToolError(
            "bundle source does not contain the one closed private CAS namespace"
        )
    cas_payload = b"private-cas-raw-byte-profile"
    cas_digest = hashlib.sha256(cas_payload).hexdigest()
    cas_path = private_cas_include.removesuffix("*") + cas_digest
    if normalized_member_payload(cas_path, cas_payload) != cas_payload:
        raise ContractToolError("private CAS bytes were normalized instead of preserved")
    for case_id, path, payload in (
        (
            "private-cas-invalid-digest-path",
            private_cas_include.removesuffix("*") + "not-a-digest",
            cas_payload,
        ),
        (
            "private-cas-path-byte-mismatch",
            cas_path,
            cas_payload + b"-substituted",
        ),
    ):
        try:
            normalized_member_payload(path, payload)
        except BundleProfileError:
            denials.append({"case": case_id, "outcome": "denied"})
        else:
            raise ContractToolError(f"malformed private CAS was accepted: {case_id}")
    for path in FORBIDDEN_INPUTS:
        if not builder_rejects(path) or not verifier_rejects(path):
            raise ContractToolError(f"compiled builder/verifier exclusion drift for {path}")
        test_source = dict(source)
        test_source["include"] = [path]
        try:
            expand_inputs(test_source)
        except ContractToolError as error:
            if "repository-only input is forbidden" not in str(error):
                raise ContractToolError(f"unexpected builder denial for {path}: {error}") from error
            denials.append({"path": path, "outcome": "denied"})
        else:
            raise ContractToolError(f"builder expanded repository-only input: {path}")

    exercise_metadata_denials(denials)
    exercise_projection_denials(denials)

    result = {
        "profile": "bytedesk.bundle-source-exclusion-evidence/1",
        "caseCount": len(denials),
        "cases": denials,
        "outcome": "pass",
    }
    if args.evidence:
        from pathlib import Path

        write_json(Path(args.evidence), result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"bundle safety test failed: {error}", file=sys.stderr)
        raise SystemExit(1)
