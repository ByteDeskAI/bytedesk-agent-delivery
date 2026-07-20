#!/usr/bin/env python3
"""Exercise the independent Python fixture schema-descriptor binding rule."""

from __future__ import annotations

from validate_schemas import fixture_schema_descriptor_error


SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/root/1.0.0"
SCHEMA_DIGEST = "sha256:" + "1" * 64


def main() -> int:
    cases = {
        "absent": ({"value": "ok"}, None),
        "exact": (
            {"schema": {"id": SCHEMA_ID, "digest": SCHEMA_DIGEST}},
            None,
        ),
        "wrong-id": (
            {
                "schema": {
                    "id": "https://schemas.bytedesk.ai/agent-delivery/v1/other/1.0.0",
                    "digest": SCHEMA_DIGEST,
                }
            },
            "schema_id_mismatch",
        ),
        "wrong-digest": (
            {
                "schema": {
                    "id": SCHEMA_ID,
                    "digest": "sha256:" + "2" * 64,
                }
            },
            "schema_digest_mismatch",
        ),
        "malformed": ({"schema": "not-an-object"}, "schema_id_mismatch"),
    }
    for case, (instance, expected) in cases.items():
        observed = fixture_schema_descriptor_error(
            instance, SCHEMA_ID, SCHEMA_DIGEST
        )
        if observed != expected:
            raise AssertionError(
                f"{case}: observed={observed!r}, expected={expected!r}"
            )
    print('{"profile":"bytedesk.schema-descriptor-tests/1","caseCount":5,"outcome":"pass"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
