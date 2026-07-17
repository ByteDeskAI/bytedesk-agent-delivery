#!/usr/bin/env python3
"""Compare independent Go and Python Draft 2020-12 validation evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from contractlib import CONTRACTS_ROOT, ContractToolError, canonical_digest, load_json, write_json
from validate_schemas import FIXTURE_SEMANTIC_ERRORS, validate_fixture_index_document


def indexed(items: Any, key: str, description: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        raise ContractToolError(f"{description} must be an array")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get(key), str):
            raise ContractToolError(f"{description} contains an invalid {key}")
        value = item[key]
        if value in result:
            raise ContractToolError(f"{description} contains duplicate {key}: {value}")
        result[value] = item
    return result


def normalized_schemas(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schemas = indexed(report.get("schemas"), "id", "schema evidence")
    return {
        schema_id: {
            "path": item.get("path"),
            "digest": item.get("digest"),
        }
        for schema_id, item in schemas.items()
    }


def normalized_schema_inventory(report: dict[str, Any]) -> dict[str, Any]:
    inventory = report.get("schemaInventory")
    fields = {"profile", "path", "digest", "schemaCount", "outcome"}
    if not isinstance(inventory, dict) or set(inventory) != fields:
        raise ContractToolError("validator evidence schemaInventory is not closed")
    if (
        inventory["profile"] != "bytedesk.contract-schema-inventory/1"
        or inventory["path"] != "contracts/bundle/v1/schema-inventory.json"
        or not isinstance(inventory["digest"], str)
        or not inventory["digest"].startswith("sha256:")
        or inventory["outcome"] != "pass"
    ):
        raise ContractToolError("validator evidence schemaInventory is invalid")
    return inventory


def normalized_fixtures(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fixtures = indexed(report.get("fixtures"), "path", "fixture evidence")
    result: dict[str, dict[str, Any]] = {}
    for path, item in fixtures.items():
        observed_keywords = item.get("observedKeywords")
        if (
            not isinstance(observed_keywords, list)
            or not all(isinstance(keyword, str) and keyword for keyword in observed_keywords)
            or observed_keywords != sorted(set(observed_keywords))
        ):
            raise ContractToolError(
                f"fixture evidence has invalid observedKeywords: {path}"
            )
        if "observedSemanticError" not in item:
            raise ContractToolError(
                f"fixture evidence lacks observedSemanticError: {path}"
            )
        observed_semantic_error = item["observedSemanticError"]
        if (
            observed_semantic_error is not None
            and observed_semantic_error not in FIXTURE_SEMANTIC_ERRORS
        ):
            raise ContractToolError(
                f"fixture evidence has invalid observedSemanticError: {path}"
            )
        result[path] = {
            "schemaId": item.get("schemaId"),
            "expectedValid": item.get("expectedValid"),
            "observedKeywords": observed_keywords,
            "observedSemanticError": observed_semantic_error,
            "outcome": item.get("outcome"),
        }
    return result


def comparable_fixture_outcomes(
    fixtures: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        path: {
            "schemaId": item["schemaId"],
            "expectedValid": item["expectedValid"],
            "observedSemanticError": item["observedSemanticError"],
            "outcome": item["outcome"],
        }
        for path, item in fixtures.items()
    }


def normalized_denial_exemptions(report: dict[str, Any]) -> list[dict[str, str]]:
    exemptions = report.get("denialCoverageExemptions")
    if not isinstance(exemptions, list):
        raise ContractToolError("validator evidence denialCoverageExemptions must be an array")
    result: list[dict[str, str]] = []
    for exemption in exemptions:
        if (
            not isinstance(exemption, dict)
            or set(exemption) != {"id", "reason"}
            or not isinstance(exemption["id"], str)
            or not exemption["id"]
            or not isinstance(exemption["reason"], str)
            or not exemption["reason"]
        ):
            raise ContractToolError("validator evidence has an invalid denial-coverage exemption")
        result.append(exemption)
    if result != sorted(result, key=lambda item: item["id"]):
        raise ContractToolError("validator denial-coverage exemptions are not sorted")
    if len({item["id"] for item in result}) != len(result):
        raise ContractToolError("validator denial-coverage exemptions contain duplicate IDs")
    return result


def required_keyword_proofs(
    go_fixtures: dict[str, dict[str, Any]],
    python_fixtures: dict[str, dict[str, Any]],
    fixture_index: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare the engine-independent expectedKeyword subset.

    Validator engines legitimately expose different wrapper keywords (`$ref`,
    `allOf`, and `unevaluatedProperties` are common examples), so their full
    diagnostic keyword sets are not portable. The closed fixture index defines
    the required semantic subset, and both independent reports must observe
    every keyword in that subset for each denial fixture.
    """

    indexed_expectations = {item["path"]: item for item in fixture_index}
    if set(indexed_expectations) != set(go_fixtures) or set(indexed_expectations) != set(
        python_fixtures
    ):
        raise ContractToolError("fixture index and validator evidence paths differ")
    proofs: list[dict[str, Any]] = []
    for path in sorted(indexed_expectations):
        expectation = indexed_expectations[path]
        for validator, fixtures in (("go", go_fixtures), ("python", python_fixtures)):
            evidence = fixtures[path]
            if (
                evidence["schemaId"] != expectation["schemaId"]
                or evidence["expectedValid"] is not expectation["valid"]
            ):
                raise ContractToolError(
                    f"{validator} fixture evidence differs from fixture index: {path}"
                )
        if expectation["valid"] is True:
            for validator, fixtures in (("go", go_fixtures), ("python", python_fixtures)):
                if fixtures[path].get("observedSemanticError") is not None:
                    raise ContractToolError(
                        f"{validator} valid fixture reported a semantic error: {path}"
                    )
            continue
        expected_semantic_error = expectation.get("expectedSemanticError")
        if expected_semantic_error is not None:
            for validator, fixtures in (("go", go_fixtures), ("python", python_fixtures)):
                if fixtures[path].get("observedSemanticError") != expected_semantic_error:
                    raise ContractToolError(
                        f"{validator} fixture evidence missed required semantic error "
                        f"path={path} expected={expected_semantic_error!r} "
                        f"observed={fixtures[path].get('observedSemanticError')!r}"
                    )
            continue
        for validator, fixtures in (("go", go_fixtures), ("python", python_fixtures)):
            if fixtures[path].get("observedSemanticError") is not None:
                raise ContractToolError(
                    f"{validator} structural denial reported a semantic error: {path}"
                )
        raw_required = expectation["expectedKeyword"]
        required = [raw_required] if isinstance(raw_required, str) else list(raw_required)
        if not required:
            raise ContractToolError(f"denial fixture has no required keyword proof: {path}")
        for validator, fixtures in (("go", go_fixtures), ("python", python_fixtures)):
            observed = set(fixtures[path]["observedKeywords"])
            missing = sorted(set(required) - observed)
            if missing:
                raise ContractToolError(
                    f"{validator} fixture evidence missed required keywords "
                    f"path={path} missing={missing} observed={sorted(observed)}"
                )
        proofs.append(
            {
                "path": path,
                "requiredKeywords": sorted(required),
                "outcome": "pass",
            }
        )
    return proofs


def required_semantic_proofs(
    go_fixtures: dict[str, dict[str, Any]],
    python_fixtures: dict[str, dict[str, Any]],
    fixture_index: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Prove both engines observed each indexed descriptor-binding denial."""

    indexed_expectations = {item["path"]: item for item in fixture_index}
    if set(indexed_expectations) != set(go_fixtures) or set(indexed_expectations) != set(
        python_fixtures
    ):
        raise ContractToolError("fixture index and validator evidence paths differ")
    proofs: list[dict[str, str]] = []
    for path in sorted(indexed_expectations):
        expected = indexed_expectations[path].get("expectedSemanticError")
        if expected is None:
            continue
        for validator, fixtures in (("go", go_fixtures), ("python", python_fixtures)):
            observed = fixtures[path].get("observedSemanticError")
            if observed != expected:
                raise ContractToolError(
                    f"{validator} fixture evidence missed required semantic error "
                    f"path={path} expected={expected!r} observed={observed!r}"
                )
        proofs.append(
            {
                "path": path,
                "requiredSemanticError": expected,
                "outcome": "pass",
            }
        )
    return proofs


def validate_report(report: Any, path: Path) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ContractToolError(f"validator evidence is not an object: {path}")
    if report.get("profile") != "bytedesk.contract-validation-evidence/1":
        raise ContractToolError(f"unknown validator evidence profile: {path}")
    if report.get("outcome") != "pass" or not isinstance(report.get("validator"), str):
        raise ContractToolError(f"validator evidence did not pass: {path}")
    schemas = normalized_schemas(report)
    fixtures = normalized_fixtures(report)
    if report.get("schemaCount") != len(schemas) or report.get("fixtureCount") != len(fixtures):
        raise ContractToolError(f"validator evidence count mismatch: {path}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", dest="go_path", type=Path, required=True)
    parser.add_argument("--python", dest="python_path", type=Path, required=True)
    parser.add_argument(
        "--index",
        type=Path,
        default=CONTRACTS_ROOT / "fixtures" / "schema" / "index.json",
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    go_report = validate_report(load_json(args.go_path), args.go_path)
    python_report = validate_report(load_json(args.python_path), args.python_path)
    if go_report["validator"] == python_report["validator"]:
        raise ContractToolError("validator IDs are identical; engines are not independent")

    go_schemas = normalized_schemas(go_report)
    python_schemas = normalized_schemas(python_report)
    if go_schemas != python_schemas:
        missing_in_python = sorted(set(go_schemas) - set(python_schemas))
        missing_in_go = sorted(set(python_schemas) - set(go_schemas))
        differing = sorted(
            schema_id
            for schema_id in set(go_schemas).intersection(python_schemas)
            if go_schemas[schema_id] != python_schemas[schema_id]
        )
        raise ContractToolError(
            "independent schema evidence differs "
            f"missingInPython={missing_in_python} missingInGo={missing_in_go} differing={differing}"
        )

    go_inventory = normalized_schema_inventory(go_report)
    python_inventory = normalized_schema_inventory(python_report)
    if go_inventory != python_inventory or go_inventory["schemaCount"] != len(go_schemas):
        raise ContractToolError(
            "independent schema inventory evidence differs "
            f"go={go_inventory} python={python_inventory}"
        )

    go_fixtures = normalized_fixtures(go_report)
    python_fixtures = normalized_fixtures(python_report)
    go_outcomes = comparable_fixture_outcomes(go_fixtures)
    python_outcomes = comparable_fixture_outcomes(python_fixtures)
    if go_outcomes != python_outcomes:
        missing_in_python = sorted(set(go_outcomes) - set(python_outcomes))
        missing_in_go = sorted(set(python_outcomes) - set(go_outcomes))
        differing = sorted(
            path
            for path in set(go_outcomes).intersection(python_outcomes)
            if go_outcomes[path] != python_outcomes[path]
        )
        raise ContractToolError(
            "independent fixture outcomes differ "
            f"missingInPython={missing_in_python} missingInGo={missing_in_go} differing={differing}"
        )
    fixture_index = validate_fixture_index_document(load_json(args.index))
    keyword_proofs = required_keyword_proofs(go_fixtures, python_fixtures, fixture_index)
    semantic_proofs = required_semantic_proofs(
        go_fixtures, python_fixtures, fixture_index
    )

    go_exemptions = normalized_denial_exemptions(go_report)
    python_exemptions = normalized_denial_exemptions(python_report)
    if go_exemptions != python_exemptions:
        raise ContractToolError(
            "independent denial-coverage exemptions differ "
            f"go={go_exemptions} python={python_exemptions}"
        )

    evidence = {
        "profile": "bytedesk.validator-agreement-evidence/1",
        "validators": [
            {
                "id": go_report["validator"],
                "reportDigest": canonical_digest(go_report),
            },
            {
                "id": python_report["validator"],
                "reportDigest": canonical_digest(python_report),
            },
        ],
        "schemaCount": len(go_schemas),
        "schemaInventory": go_inventory,
        "fixtureCount": len(go_fixtures),
        "denialKeywordProofCount": len(keyword_proofs),
        "denialKeywordProofs": keyword_proofs,
        "denialSemanticProofCount": len(semantic_proofs),
        "denialSemanticProofs": semantic_proofs,
        "denialCoverageExemptions": go_exemptions,
        "comparedFields": {
            "schemas": ["id", "path", "digest"],
            "fixtures": [
                "path",
                "schemaId",
                "expectedValid",
                "outcome",
                "expectedKeyword subset of observedKeywords",
                "observedSemanticError",
            ],
        },
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
        print(f"validator evidence comparison failed: {error}", file=sys.stderr)
        raise SystemExit(1)
