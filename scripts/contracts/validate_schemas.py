#!/usr/bin/env python3
"""Validate all Draft 2020-12 schemas and indexed fixtures offline.

This is the independent Python/jsonschema validator lane. The Go validator is
the other required implementation; sharing fixture expectations is deliberate,
sharing validation code is not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable

from contractlib import (
    CONTRACTS_ROOT,
    REPOSITORY_ROOT,
    SCHEMAS_ROOT,
    ContractToolError,
    canonical_digest,
    load_json,
    repository_path,
    validation_error_key,
    write_json,
)


SCHEMA_INVENTORY_PROFILE = "bytedesk.contract-schema-inventory/1"
SCHEMA_INVENTORY_BUNDLE_PATH = "contracts/bundle/v1/schema-inventory.json"
SCHEMA_INVENTORY_PATH = REPOSITORY_ROOT / SCHEMA_INVENTORY_BUNDLE_PATH
SCHEMA_ID_PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/"
SCHEMA_INVENTORY_ROOT_FIELDS = {"profile", "schemas"}
SCHEMA_INVENTORY_ENTRY_FIELDS = {"id", "path", "digest"}
EXACT_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


def stable_schema_id(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith(SCHEMA_ID_PREFIX):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "schemas.bytedesk.ai"
        and parsed.path.startswith("/agent-delivery/v1/")
        and parsed.query == ""
        and parsed.fragment == ""
    )


def _schema_repository_path(path: Path | str, repository_root: Path) -> str:
    if isinstance(path, Path):
        try:
            return path.relative_to(repository_root).as_posix()
        except ValueError as error:
            raise ContractToolError(
                f"schema path is outside the repository: {path}"
            ) from error
    if isinstance(path, str):
        return path
    raise ContractToolError("schema path is not a path or bundled path string")


def validate_schema_inventory(
    document: Any,
    schemas: dict[str, tuple[Path | str, Any]],
    *,
    repository_root: Path = REPOSITORY_ROOT,
    inventory_path: Path | str = SCHEMA_INVENTORY_PATH,
) -> dict[str, Any]:
    """Independently bind discovered schemas to the one closed exact inventory."""

    if not isinstance(document, dict) or set(document) != SCHEMA_INVENTORY_ROOT_FIELDS:
        raise ContractToolError("schema inventory root is not closed")
    if document["profile"] != SCHEMA_INVENTORY_PROFILE:
        raise ContractToolError("schema inventory has an unknown profile")
    entries = document["schemas"]
    if not isinstance(entries, list) or not entries:
        raise ContractToolError("schema inventory schemas must be a non-empty array")

    expected: dict[str, tuple[str, str]] = {}
    seen_paths: set[str] = set()
    ordered_ids: list[str] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != SCHEMA_INVENTORY_ENTRY_FIELDS:
            raise ContractToolError(
                f"schema inventory entry {position} is not closed"
            )
        schema_id = entry["id"]
        schema_path = entry["path"]
        schema_digest = entry["digest"]
        if (
            not stable_schema_id(schema_id)
            or not isinstance(schema_path, str)
            or not schema_path.startswith("contracts/schemas/v1/")
            or not schema_path.endswith(".schema.json")
            or "\\" in schema_path
            or any(segment in {"", ".", ".."} for segment in schema_path.split("/"))
            or not isinstance(schema_digest, str)
            or EXACT_SHA256.fullmatch(schema_digest) is None
        ):
            raise ContractToolError(
                f"schema inventory entry {position} has an invalid id, path, or digest"
            )
        if schema_id in expected or schema_path in seen_paths:
            raise ContractToolError("schema inventory contains a duplicate ID or path")
        expected[schema_id] = (schema_path, schema_digest)
        seen_paths.add(schema_path)
        ordered_ids.append(schema_id)
    if ordered_ids != sorted(ordered_ids):
        raise ContractToolError(
            "schema inventory entries must have unique IDs in ascending order"
        )

    actual = {
        schema_id: (
            _schema_repository_path(path, repository_root),
            canonical_digest(schema),
        )
        for schema_id, (path, schema) in schemas.items()
    }
    missing = sorted(set(expected) - set(actual))
    added = sorted(set(actual) - set(expected))
    changed = sorted(
        schema_id
        for schema_id in set(expected).intersection(actual)
        if expected[schema_id] != actual[schema_id]
    )
    if missing or added or changed:
        raise ContractToolError(
            "schema inventory mismatch "
            f"missing={missing} added={added} changed={changed}"
        )

    if inventory_path == SCHEMA_INVENTORY_PATH:
        inventory_display_path = SCHEMA_INVENTORY_BUNDLE_PATH
    else:
        inventory_display_path = _schema_repository_path(inventory_path, repository_root)
    return {
        "profile": SCHEMA_INVENTORY_PROFILE,
        "path": inventory_display_path,
        "digest": canonical_digest(document),
        "schemaCount": len(expected),
        "outcome": "pass",
    }


def all_errors(error: Any) -> Iterable[Any]:
    yield error
    for child in error.context:
        yield from all_errors(child)


def build_registry() -> tuple[Registry, dict[str, tuple[Path, Any]]]:
    resources: list[tuple[str, Resource]] = []
    schemas: dict[str, tuple[Path, Any]] = {}
    for path in sorted(SCHEMAS_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        if not isinstance(schema, dict):
            raise ContractToolError(f"schema root is not an object: {repository_path(path)}")
        schema_id = schema.get("$id")
        if not stable_schema_id(schema_id):
            raise ContractToolError(f"missing or invalid stable $id: {repository_path(path)}")
        if schema_id in schemas:
            raise ContractToolError(f"duplicate schema $id: {schema_id}")
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
        except (SchemaError, ValueError) as error:
            raise ContractToolError(f"invalid Draft 2020-12 schema {schema_id}: {error}") from error
        schemas[schema_id] = (path, schema)
        resources.append((schema_id, resource))
    if not schemas:
        raise ContractToolError("no source schemas found")
    validate_schema_inventory(load_json(SCHEMA_INVENTORY_PATH), schemas)
    return Registry().with_resources(resources), schemas


def validate_reference_closure(registry: Registry, schemas: dict[str, tuple[Path, Any]]) -> None:
    for schema_id, (_, schema) in schemas.items():
        validator = Draft202012Validator(
            schema,
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        try:
            # Eagerly walk every reference, including references in branches that
            # no positive fixture happens to exercise.
            for reference in iter_references(schema):
                resolver = registry.resolver(schema_id)
                resolver.lookup(reference)
        except (NoSuchResource, Unresolvable) as error:
            raise ContractToolError(f"offline reference from {schema_id} is unresolved: {error}") from error
        # Instantiation catches invalid registry/dialect combinations early.
        if validator is None:  # pragma: no cover - defensive invariant
            raise ContractToolError(f"could not construct validator for {schema_id}")


def iter_references(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str):
                yield child
            else:
                yield from iter_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_references(child)


FIXTURE_INDEX_ROOT_FIELDS = {"profile", "fixtures"}
FIXTURE_INDEX_REQUIRED_ENTRY_FIELDS = {
    "path",
    "schemaId",
    "valid",
    "category",
    "expectedKeyword",
}
FIXTURE_INDEX_ENTRY_FIELDS = FIXTURE_INDEX_REQUIRED_ENTRY_FIELDS | {
    "expectedSemanticError",
}
FIXTURE_CATEGORIES = {"positive", "boundary", "negative", "malicious"}
FIXTURE_SEMANTIC_ERRORS = {
    "schema_id_mismatch",
    "schema_digest_mismatch",
}
COMMON_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0"
COMMON_DEFINITIONS_ROOT_FIELDS = {"$schema", "$id", "title", "$defs"}


def fixture_schema_descriptor_error(
    instance: Any, expected_id: str, expected_digest: str
) -> str | None:
    """Bind an optional root schema descriptor to the selected exact schema.

    Descriptor shape remains the selected JSON Schema's responsibility. This
    independent cross-field check prevents a structurally valid descriptor
    from naming different schema authority.
    """

    if not isinstance(instance, dict) or "schema" not in instance:
        return None
    descriptor = instance["schema"]
    if not isinstance(descriptor, dict) or descriptor.get("id") != expected_id:
        return "schema_id_mismatch"
    if descriptor.get("digest") != expected_digest:
        return "schema_digest_mismatch"
    return None


def validate_fixture_index_document(index: Any) -> list[dict[str, Any]]:
    """Parse the closed shared fixture-index contract without validating instances."""

    if not isinstance(index, dict):
        raise ContractToolError("fixture index must be an object")
    unexpected_root = sorted(set(index) - FIXTURE_INDEX_ROOT_FIELDS)
    if unexpected_root:
        raise ContractToolError(f"fixture index root has unknown fields: {unexpected_root}")
    missing_root = sorted(FIXTURE_INDEX_ROOT_FIELDS - set(index))
    if missing_root:
        raise ContractToolError(f"fixture index root lacks fields: {missing_root}")
    if index["profile"] != "bytedesk.schema-fixtures/1":
        raise ContractToolError("fixture index has an unknown profile")
    if not isinstance(index["fixtures"], list) or not index["fixtures"]:
        raise ContractToolError("fixture index must contain a non-empty fixtures array")

    entries: list[dict[str, Any]] = []
    for position, item in enumerate(index["fixtures"]):
        if not isinstance(item, dict):
            raise ContractToolError(f"fixture index entry {position} is not an object")
        unexpected = sorted(set(item) - FIXTURE_INDEX_ENTRY_FIELDS)
        if unexpected:
            raise ContractToolError(
                f"fixture index entry {position} has unknown fields: {unexpected}"
            )
        missing = sorted(FIXTURE_INDEX_REQUIRED_ENTRY_FIELDS - set(item))
        if missing:
            raise ContractToolError(f"fixture index entry {position} lacks fields: {missing}")

        fixture_path = item["path"]
        schema_id = item["schemaId"]
        expected_valid = item["valid"]
        category = item["category"]
        expected_keyword = item["expectedKeyword"]
        expected_semantic_error = item.get("expectedSemanticError")
        if not isinstance(fixture_path, str) or not fixture_path:
            raise ContractToolError(f"fixture index entry {position} path must be non-empty")
        if not isinstance(schema_id, str) or not schema_id:
            raise ContractToolError(f"fixture index entry {position} schemaId must be non-empty")
        if not isinstance(expected_valid, bool):
            raise ContractToolError(f"fixture index entry {position} valid must be boolean")
        if not isinstance(category, str) or category not in FIXTURE_CATEGORIES:
            raise ContractToolError(
                f"fixture index entry {position} has invalid category: {category!r}"
            )
        category_is_valid = category in {"positive", "boundary"}
        if expected_valid is not category_is_valid:
            raise ContractToolError(
                f"fixture index entry {position} category {category!r} "
                f"does not match valid={expected_valid!r}"
            )

        if isinstance(expected_keyword, str):
            if not expected_keyword:
                raise ContractToolError(
                    f"fixture index entry {position} expectedKeyword cannot be empty"
                )
            expected_keywords = [expected_keyword]
        elif isinstance(expected_keyword, list) and all(
            isinstance(keyword, str) and keyword for keyword in expected_keyword
        ):
            expected_keywords = expected_keyword
            if len(expected_keywords) != len(set(expected_keywords)):
                raise ContractToolError(
                    f"fixture index entry {position} expectedKeyword values must be unique"
                )
        else:
            raise ContractToolError(
                f"fixture index entry {position} expectedKeyword must be a non-empty "
                "string or a unique string array"
            )
        if expected_valid and expected_keywords:
            raise ContractToolError(
                f"fixture index entry {position} valid fixture expectedKeyword must be an empty array"
            )
        if expected_semantic_error is not None and (
            not isinstance(expected_semantic_error, str)
            or expected_semantic_error not in FIXTURE_SEMANTIC_ERRORS
        ):
            raise ContractToolError(
                f"fixture index entry {position} expectedSemanticError must be "
                "schema_id_mismatch or schema_digest_mismatch"
            )
        if expected_valid and expected_semantic_error is not None:
            raise ContractToolError(
                f"fixture index entry {position} valid fixture cannot declare "
                "expectedSemanticError"
            )
        if not expected_valid and not expected_keywords and expected_semantic_error is None:
            raise ContractToolError(
                f"fixture index entry {position} denial fixture expectedKeyword must not be "
                "empty unless expectedSemanticError is present"
            )
        if not expected_valid and expected_keywords and expected_semantic_error is not None:
            raise ContractToolError(
                f"fixture index entry {position} denial fixture must declare exactly one of "
                "expectedKeyword or expectedSemanticError"
            )
        entries.append(item)
    return entries


def validate_positive_fixture_coverage(
    fixtures: list[dict[str, Any]], schema_ids: Iterable[str]
) -> None:
    covered = {
        item["schemaId"]
        for item in fixtures
        if item["valid"] is True and item["category"] == "positive"
    }
    missing = sorted(set(schema_ids) - covered)
    if missing:
        raise ContractToolError(
            f"schemas lack indexed valid positive fixtures: {missing}"
        )


def validate_denial_fixture_coverage(
    fixtures: list[dict[str, Any]],
    schemas: dict[str, tuple[Path, Any]],
) -> list[dict[str, str]]:
    """Require a denial per instance schema and expose the one narrow exemption."""

    exemptions: list[dict[str, str]] = []
    common = schemas.get(COMMON_SCHEMA_ID)
    if common is not None:
        common_root = common[1]
        if (
            not isinstance(common_root, dict)
            or set(common_root) != COMMON_DEFINITIONS_ROOT_FIELDS
            or not isinstance(common_root.get("$defs"), dict)
            or not common_root["$defs"]
        ):
            raise ContractToolError(
                "common denial-coverage exemption must remain a definitions-library root"
            )
        exemptions.append(
            {
                "id": COMMON_SCHEMA_ID,
                "reason": "definitions-library-no-instance-contract",
            }
        )

    covered = {item["schemaId"] for item in fixtures if item["valid"] is False}
    required = set(schemas) - {COMMON_SCHEMA_ID}
    missing = sorted(required - covered)
    if missing:
        raise ContractToolError(f"schemas lack indexed denial fixtures: {missing}")
    return exemptions


def validate_fixtures(
    registry: Registry,
    schemas: dict[str, tuple[Path, Any]],
    index_path: Path,
) -> list[dict[str, Any]]:
    index = load_json(index_path)
    fixtures = validate_fixture_index_document(index)
    validate_positive_fixture_coverage(fixtures, schemas)
    validate_denial_fixture_coverage(fixtures, schemas)

    results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for item in fixtures:
        fixture_path_text = item["path"]
        schema_id = item["schemaId"]
        expected_valid = item["valid"]
        if fixture_path_text in seen_paths:
            raise ContractToolError(f"duplicate fixture path in index: {fixture_path_text}")
        seen_paths.add(fixture_path_text)
        if schema_id not in schemas:
            raise ContractToolError(f"fixture references unknown bundled schema: {schema_id}")

        fixture_candidate = REPOSITORY_ROOT / fixture_path_text
        try:
            fixture_path = fixture_candidate.resolve(strict=True)
        except OSError as error:
            raise ContractToolError(f"fixture path is unavailable: {fixture_path_text}") from error
        try:
            fixture_path.relative_to(CONTRACTS_ROOT.resolve())
        except ValueError as error:
            raise ContractToolError(f"fixture path escapes contracts/: {fixture_path_text}") from error
        if fixture_candidate.is_symlink():
            raise ContractToolError(f"fixture path is a symbolic link: {fixture_path_text}")
        if repository_path(fixture_path) != fixture_path_text:
            raise ContractToolError(f"fixture path is not canonical: {fixture_path_text}")
        instance = load_json(fixture_path)
        schema = schemas[schema_id][1]
        expected_semantic_error = item.get("expectedSemanticError")
        observed_semantic_error = fixture_schema_descriptor_error(
            instance, schema_id, canonical_digest(schema)
        )
        if observed_semantic_error != expected_semantic_error:
            raise ContractToolError(
                f"fixture {fixture_path_text} schema descriptor semantic result mismatch: "
                f"expected {expected_semantic_error!r}, observed {observed_semantic_error!r}"
            )
        errors = sorted(
            Draft202012Validator(
                schema,
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            ).iter_errors(instance),
            key=validation_error_key,
        )

        if expected_valid and errors:
            raise ContractToolError(
                f"valid fixture rejected: {fixture_path_text}: {errors[0].message}"
            )
        if expected_semantic_error is not None and errors:
            raise ContractToolError(
                f"semantic denial fixture also failed structural validation: "
                f"{fixture_path_text}: {errors[0].message}"
            )
        if not expected_valid and expected_semantic_error is None and not errors:
            raise ContractToolError(f"denial fixture unexpectedly accepted: {fixture_path_text}")

        expected_keywords = item["expectedKeyword"]
        if isinstance(expected_keywords, str):
            expected_keywords = [expected_keywords]
        actual_keywords = {
            nested.validator
            for error in errors
            for nested in all_errors(error)
            if isinstance(nested.validator, str)
        }
        missing = sorted(set(expected_keywords) - actual_keywords)
        if missing:
            raise ContractToolError(
                f"denial fixture {fixture_path_text} missed expected keywords {missing}; "
                f"observed {sorted(actual_keywords)}"
            )

        results.append(
            {
                "path": fixture_path_text,
                "schemaId": schema_id,
                "expectedValid": expected_valid,
                "observedKeywords": sorted(actual_keywords),
                "observedSemanticError": observed_semantic_error,
                "outcome": "pass",
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--index",
        type=Path,
        default=CONTRACTS_ROOT / "fixtures" / "schema" / "index.json",
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    registry, schemas = build_registry()
    schema_inventory_evidence = validate_schema_inventory(
        load_json(SCHEMA_INVENTORY_PATH), schemas
    )
    validate_reference_closure(registry, schemas)
    fixture_results = validate_fixtures(registry, schemas, args.index)
    denial_coverage_exemptions = validate_denial_fixture_coverage(
        validate_fixture_index_document(load_json(args.index)), schemas
    )
    evidence = {
        "profile": "bytedesk.contract-validation-evidence/1",
        "validator": "python-jsonschema-draft-2020-12",
        "schemaCount": len(schemas),
        "fixtureCount": len(fixture_results),
        "schemas": [
            {
                "id": schema_id,
                "path": repository_path(path),
                "digest": canonical_digest(schema),
            }
            for schema_id, (path, schema) in sorted(schemas.items())
        ],
        "schemaInventory": schema_inventory_evidence,
        "fixtures": fixture_results,
        "denialCoverageExemptions": denial_coverage_exemptions,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, evidence)
    print(json.dumps(evidence, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"contract validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
