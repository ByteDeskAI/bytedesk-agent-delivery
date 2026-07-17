#!/usr/bin/env python3
"""Prove the Python validator enforces the exact closed schema inventory."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from contractlib import ContractToolError, canonical_digest, write_json
from validate_schemas import validate_schema_inventory


PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/"


def schema(name: str, maximum: int = 128) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{PREFIX}{name}/1.0.0",
        "type": "string",
        "minLength": 1,
        "maxLength": maximum,
    }


def inventory_for(schemas: dict[str, tuple[Path, Any]], root: Path) -> dict[str, Any]:
    return {
        "profile": "bytedesk.contract-schema-inventory/1",
        "schemas": [
            {
                "id": schema_id,
                "path": path.relative_to(root).as_posix(),
                "digest": canonical_digest(document),
            }
            for schema_id, (path, document) in sorted(schemas.items())
        ],
    }


def expect_denial(case: str, operation: Callable[[], None]) -> dict[str, str]:
    try:
        operation()
    except ContractToolError as error:
        if "schema inventory mismatch" not in str(error):
            raise AssertionError(f"{case}: unexpected denial: {error}") from error
        return {"id": case, "outcome": "denied", "reason": str(error)}
    else:
        raise AssertionError(f"{case}: schema inventory mutation was accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        schema_root = root / "contracts" / "schemas" / "v1"
        first = schema("first")
        second = schema("second")
        schemas = {
            first["$id"]: (schema_root / "first.schema.json", first),
            second["$id"]: (schema_root / "second.schema.json", second),
        }
        inventory = inventory_for(schemas, root)
        validate_schema_inventory(inventory, schemas, repository_root=root)
        cases: list[dict[str, str]] = [
            {"id": "baseline-exact-inventory", "outcome": "permitted"}
        ]

        removed = dict(schemas)
        del removed[first["$id"]]
        cases.append(
            expect_denial(
                "removed-schema",
                lambda: validate_schema_inventory(
                    inventory, removed, repository_root=root
                ),
            )
        )

        added = dict(schemas)
        extra = schema("extra")
        added[extra["$id"]] = (schema_root / "extra.schema.json", extra)
        cases.append(
            expect_denial(
                "added-schema",
                lambda: validate_schema_inventory(
                    inventory, added, repository_root=root
                ),
            )
        )

        renamed = dict(schemas)
        renamed[first["$id"]] = (schema_root / "renamed.schema.json", first)
        cases.append(
            expect_denial(
                "renamed-schema",
                lambda: validate_schema_inventory(
                    inventory, renamed, repository_root=root
                ),
            )
        )

        substituted = dict(schemas)
        replacement = deepcopy(first)
        replacement["$id"] = f"{PREFIX}substituted/1.0.0"
        del substituted[first["$id"]]
        substituted[replacement["$id"]] = (
            schema_root / "first.schema.json",
            replacement,
        )
        cases.append(
            expect_denial(
                "substituted-schema-id",
                lambda: validate_schema_inventory(
                    inventory, substituted, repository_root=root
                ),
            )
        )

        stale = dict(schemas)
        changed = schema("first", maximum=129)
        stale[first["$id"]] = (schema_root / "first.schema.json", changed)
        cases.append(
            expect_denial(
                "stale-schema-digest",
                lambda: validate_schema_inventory(
                    inventory, stale, repository_root=root
                ),
            )
        )

    result = {
        "profile": "bytedesk.schema-inventory-conformance/1",
        "caseCount": len(cases),
        "cases": cases,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
