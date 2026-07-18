#!/usr/bin/env python3
"""Adversarial tests for deterministic contract metadata refresh."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from contractlib import ContractToolError, canonical_digest
from refresh_contract_metadata import build_refresh_plan, execute_refresh


SCHEMA_PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/"
OLD_DIGEST = "sha256:" + "0" * 64
INTENTIONAL_DENIAL_DIGEST = "sha256:" + "f" * 64


def schema(name: str) -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{SCHEMA_PREFIX}{name}/1.0.0",
        "type": "object",
        "additionalProperties": False,
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_repository(root: Path) -> dict[str, object]:
    schemas = {
        name: schema(name)
        for name in ("alpha", "event-data", "event-types", "schema-descriptor")
    }
    schema_paths: dict[str, str] = {}
    for name, document in schemas.items():
        filename = (
            "event-data-envelope.schema.json"
            if name == "event-data"
            else f"{name}.schema.json"
        )
        relative = f"contracts/schemas/v1/{filename}"
        schema_paths[name] = relative
        write_json(root / relative, document)

    alpha_id = schemas["alpha"]["$id"]
    event_data_id = schemas["event-data"]["$id"]
    descriptor_id = schemas["schema-descriptor"]["$id"]
    positive_path = "contracts/fixtures/schema/positive/alpha.json"
    denial_path = "contracts/fixtures/schema/malicious/alpha-wrong-digest.json"
    descriptor_path = "contracts/fixtures/schema/positive/schema-descriptor.json"
    write_json(
        root / positive_path,
        {"schema": {"id": alpha_id, "digest": OLD_DIGEST}},
    )
    write_json(
        root / denial_path,
        {
            "schema": {
                "id": alpha_id,
                "digest": INTENTIONAL_DENIAL_DIGEST,
            }
        },
    )
    write_json(
        root / descriptor_path,
        {"id": alpha_id, "digest": OLD_DIGEST},
    )
    fixture_index = {
        "profile": "bytedesk.schema-fixtures/1",
        "fixtures": [
            {
                "path": positive_path,
                "schemaId": alpha_id,
                "valid": True,
                "category": "positive",
                "expectedKeyword": [],
            },
            {
                "path": denial_path,
                "schemaId": alpha_id,
                "valid": False,
                "category": "malicious",
                "expectedKeyword": [],
                "expectedSemanticError": "schema_digest_mismatch",
            },
            {
                "path": descriptor_path,
                "schemaId": descriptor_id,
                "valid": True,
                "category": "positive",
                "expectedKeyword": [],
            },
        ],
    }
    write_json(root / "contracts/fixtures/schema/index.json", fixture_index)

    write_json(
        root / "contracts/bundle/v1/schema-inventory.json",
        {
            "profile": "bytedesk.contract-schema-inventory/1",
            "schemas": [
                {
                    "id": alpha_id,
                    "path": schema_paths["alpha"],
                    "digest": OLD_DIGEST,
                }
            ],
        },
    )

    event_type = "ai.bytedesk.agent-delivery.alpha.changed.v1"
    write_json(
        root / "contracts/events/v1/event-types.json",
        {
            "$schema": schemas["event-types"]["$id"],
            "profile": "bytedesk.event-types/1",
            "cloudEventsVersion": "1.0.2",
            "delivery": "at-least-once",
            "ordering": "per-aggregate-sequence",
            "authority": "notification-only",
            "eventTypes": [
                {
                    "type": event_type,
                    "aggregateType": "alpha",
                    "resourceSchemaId": alpha_id,
                    "resourceSchemaDigest": OLD_DIGEST,
                    "resourceUriTemplate": "/v1/alpha/{alphaId}",
                    "resynchronizeOperationId": "getAlpha",
                    "redaction": "consumer-private",
                }
            ],
            "registryCompatibility": "test fixture",
            "resynchronization": {
                "authority": "authenticated-api-read",
                "on": ["unknown-schema-id-or-digest"],
                "resumeAfter": "exact-resource-schema-and-etag-verified",
            },
        },
    )

    openapi_path = root / "contracts/openapi/v1/agent-delivery.openapi.json"
    write_json(
        openapi_path,
        {
            "openapi": "3.2.0",
            "paths": {
                "/v1/alpha/{alphaId}": {
                    "get": {
                        "operationId": "getAlpha",
                        "security": [{"consumerBearer": []}],
                        "responses": {
                            "200": {"$ref": "#/components/responses/Alpha"}
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "Alpha": {
                        "$ref": "../../schemas/v1/alpha.schema.json",
                        "x-bytedesk-schema-id": alpha_id,
                        "x-bytedesk-schema-digest": OLD_DIGEST,
                    },
                    "EventData": {
                        "$ref": "../../schemas/v1/event-data-envelope.schema.json",
                        "x-bytedesk-schema-id": event_data_id,
                        "x-bytedesk-schema-digest": OLD_DIGEST,
                    },
                },
                "responses": {
                    "Alpha": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Alpha"}
                            }
                        }
                    }
                },
            },
        },
    )
    write_json(
        root / "contracts/asyncapi/v1/agent-delivery.asyncapi.json",
        {
            "asyncapi": "3.1.0",
            "components": {
                "schemas": {
                    "EventData": {
                        "$ref": "../../schemas/v1/event-data-envelope.schema.json",
                        "x-bytedesk-schema-id": event_data_id,
                        "x-bytedesk-schema-digest": OLD_DIGEST,
                    }
                },
                "messages": {
                    "Notification": {
                        "x-bytedesk-data-schema-id": event_data_id,
                        "x-bytedesk-data-schema-digest": OLD_DIGEST,
                    }
                },
            },
        },
    )
    example_path = root / "contracts/events/v1/examples/alpha.changed.json"
    write_json(
        example_path,
        {
            "type": event_type,
            "dataschema": event_data_id,
            "data": {
                "schema": {"id": event_data_id, "digest": OLD_DIGEST},
                "dataSchema": {"id": event_data_id, "digest": OLD_DIGEST},
                "resource": {
                    "projectionSchema": {"id": alpha_id, "digest": OLD_DIGEST}
                },
            },
        },
    )

    documentation_path = root / "docs/spec.md"
    documentation_path.parent.mkdir(parents=True, exist_ok=True)
    documentation_path.write_text("# Test contract documentation\n", encoding="utf-8")
    schema_mappings = [
        {"id": document["$id"], "documents": ["docs/spec.md"]}
        for document in schemas.values()
    ]
    write_json(
        root / "contracts/bundle/v1/documentation-map.json",
        {
            "profile": "bytedesk.contract-documentation-map/1",
            "documents": [{"path": "docs/spec.md", "digest": OLD_DIGEST}],
            "schemas": schema_mappings,
            "projections": [
                {
                    "path": "contracts/asyncapi/v1/agent-delivery.asyncapi.json",
                    "source": "contracts/schemas/v1/",
                    "role": "event-projection",
                },
                {
                    "path": "contracts/events/v1/event-types.json",
                    "source": "contracts/schemas/v1/event-types.schema.json",
                    "role": "notification-registry",
                },
                {
                    "path": "contracts/openapi/v1/agent-delivery.openapi.json",
                    "source": "contracts/schemas/v1/",
                    "role": "http-projection",
                },
            ],
        },
    )
    return {
        "schemas": schemas,
        "positivePath": positive_path,
        "denialPath": denial_path,
        "descriptorPath": descriptor_path,
        "fixtureIndex": fixture_index,
    }


def expect_denial(case: str, operation: object, expected: str) -> dict[str, str]:
    try:
        operation()  # type: ignore[operator]
    except ContractToolError as error:
        if expected not in str(error):
            raise AssertionError(f"{case}: unexpected denial: {error}") from error
        return {"id": case, "outcome": "denied"}
    raise AssertionError(f"{case}: mutation unexpectedly accepted")


def main() -> int:
    cases: list[dict[str, str]] = []
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        fixture = make_repository(root)
        initial = build_refresh_plan(root)
        if not initial.stale_paths:
            raise AssertionError("stale metadata was not detected")
        cases.append(
            expect_denial(
                "default-check-denies-generated-drift",
                lambda: execute_refresh(root),
                "contract metadata drift",
            )
        )
        denial_before = (root / str(fixture["denialPath"])).read_bytes()
        write_evidence = execute_refresh(root, write=True)
        if write_evidence["changedFileCount"] < 8:
            raise AssertionError("expected metadata projections were not refreshed")
        if (root / str(fixture["denialPath"])).read_bytes() != denial_before:
            raise AssertionError("intentional semantic denial was rewritten")
        check_evidence = execute_refresh(root, write=False)
        if check_evidence["staleFileCount"] != 0:
            raise AssertionError("refresh is not idempotent")

        schemas = fixture["schemas"]
        alpha = schemas["alpha"]  # type: ignore[index]
        alpha_digest = canonical_digest(alpha)
        positive = json.loads((root / str(fixture["positivePath"])).read_text())
        descriptor = json.loads((root / str(fixture["descriptorPath"])).read_text())
        if positive["schema"] != {"id": alpha["$id"], "digest": alpha_digest}:
            raise AssertionError("indexed root schema descriptor was not refreshed")
        if descriptor != {"id": alpha["$id"], "digest": alpha_digest}:
            raise AssertionError("standalone schema descriptor projection was not refreshed")
        cases.append({"id": "write-check-idempotence-and-denial-preservation", "outcome": "pass"})

        index_path = root / "contracts/fixtures/schema/index.json"
        original_index = json.loads(index_path.read_text())
        duplicate_index = deepcopy(original_index)
        duplicate_index["fixtures"].append(deepcopy(duplicate_index["fixtures"][0]))
        write_json(index_path, duplicate_index)
        cases.append(
            expect_denial(
                "duplicate-indexed-fixture-path",
                lambda: build_refresh_plan(root),
                "duplicate fixture index path",
            )
        )
        write_json(index_path, original_index)

        unknown_index = deepcopy(original_index)
        unknown_index["fixtures"][0]["schemaId"] = f"{SCHEMA_PREFIX}unknown/1.0.0"
        write_json(index_path, unknown_index)
        cases.append(
            expect_denial(
                "unknown-indexed-schema-id",
                lambda: build_refresh_plan(root),
                "unknown schema ID",
            )
        )
        write_json(index_path, original_index)

        documentation_map_path = root / "contracts/bundle/v1/documentation-map.json"
        documentation_map = json.loads(documentation_map_path.read_text())
        documentation_map["documents"][0]["path"] = "docs/missing.md"
        write_json(documentation_map_path, documentation_map)
        cases.append(
            expect_denial(
                "missing-documentation-path",
                lambda: build_refresh_plan(root),
                "is missing",
            )
        )

    result = {
        "profile": "bytedesk.contract-metadata-refresh-tests/1",
        "caseCount": len(cases),
        "cases": cases,
        "outcome": "pass",
    }
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
