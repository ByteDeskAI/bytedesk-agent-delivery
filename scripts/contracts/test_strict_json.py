#!/usr/bin/env python3
"""Prove Python release tooling enforces the accepted structured JSON limits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Callable

from contractlib import (
    MAX_JSON_MODEL_DEPTH,
    MAX_JSON_MODEL_NODES,
    MAX_SAFE_INTEGER,
    MAX_STRUCTURED_JSON_BYTES,
    MIN_SAFE_INTEGER,
    ContractToolError,
    canonical_json,
    load_json,
    strict_json_bytes,
    write_json,
)


def expect_pass(cases: list[dict[str, str]], case_id: str, operation: Callable[[], Any]) -> None:
    operation()
    cases.append({"id": case_id, "outcome": "permitted"})


def expect_denial(
    cases: list[dict[str, str]],
    case_id: str,
    operation: Callable[[], Any],
    expected_message: str,
) -> None:
    try:
        operation()
    except ContractToolError as error:
        if expected_message not in str(error):
            raise ContractToolError(f"unexpected strict JSON denial for {case_id}: {error}") from error
        cases.append({"id": case_id, "outcome": "denied"})
        return
    raise ContractToolError(f"strict JSON denial unexpectedly passed: {case_id}")


def nested_array(depth: int) -> bytes:
    # The scalar is one value level below every containing array.
    return b"[" * (depth - 1) + b"0" + b"]" * (depth - 1)


def array_with_nodes(node_count: int) -> bytes:
    if node_count < 2:
        raise ValueError("array node count must include a container and at least one item")
    return b"[" + b",".join([b"0"] * (node_count - 1)) + b"]"


def object_with_members(member_count: int) -> bytes:
    members = [f'"k{index}":0'.encode("ascii") for index in range(member_count)]
    return b"{" + b",".join(members) + b"}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    cases: list[dict[str, str]] = []

    expect_pass(cases, "baseline-object", lambda: strict_json_bytes(b'{"ok":true}', "baseline"))
    expect_pass(
        cases,
        "input-exactly-four-mib",
        lambda: strict_json_bytes(
            b'"' + b"a" * (MAX_STRUCTURED_JSON_BYTES - 2) + b'"', "input-boundary"
        ),
    )
    expect_denial(
        cases,
        "input-over-four-mib",
        lambda: strict_json_bytes(b" " * (MAX_STRUCTURED_JSON_BYTES + 1), "input-over"),
        "input byte limit",
    )
    expect_pass(
        cases,
        "depth-exactly-64",
        lambda: strict_json_bytes(nested_array(MAX_JSON_MODEL_DEPTH), "depth-boundary"),
    )
    expect_denial(
        cases,
        "depth-65",
        lambda: strict_json_bytes(nested_array(MAX_JSON_MODEL_DEPTH + 1), "depth-over"),
        "depth limit",
    )
    expect_pass(
        cases,
        "nodes-exactly-100000",
        lambda: strict_json_bytes(array_with_nodes(MAX_JSON_MODEL_NODES), "node-boundary"),
    )
    expect_denial(
        cases,
        "nodes-100001",
        lambda: strict_json_bytes(array_with_nodes(MAX_JSON_MODEL_NODES + 1), "node-over"),
        "node limit",
    )
    expect_pass(
        cases,
        "object-member-names-count-as-nodes",
        lambda: strict_json_bytes(object_with_members(49_999), "member-node-boundary"),
    )
    expect_denial(
        cases,
        "object-member-name-crosses-node-limit",
        lambda: strict_json_bytes(object_with_members(50_000), "member-node-over"),
        "node limit",
    )
    expect_pass(
        cases,
        "safe-integer-boundaries",
        lambda: strict_json_bytes(f"[{MIN_SAFE_INTEGER},{MAX_SAFE_INTEGER}]".encode(), "safe-int"),
    )
    expect_denial(
        cases,
        "unsafe-positive-integer",
        lambda: strict_json_bytes(str(MAX_SAFE_INTEGER + 1).encode(), "unsafe-positive"),
        "interoperable range",
    )
    expect_denial(
        cases,
        "unsafe-negative-integer",
        lambda: strict_json_bytes(str(MIN_SAFE_INTEGER - 1).encode(), "unsafe-negative"),
        "interoperable range",
    )
    expect_pass(cases, "largest-finite-exponent", lambda: strict_json_bytes(b"1e308", "finite"))
    expect_denial(
        cases,
        "huge-exponent-does-not-become-infinity",
        lambda: strict_json_bytes(b"1e1000000", "huge-exponent"),
        "non-finite",
    )
    expect_denial(
        cases,
        "nonstandard-nan",
        lambda: strict_json_bytes(b"NaN", "nan"),
        "non-finite",
    )
    expect_denial(
        cases,
        "duplicate-member",
        lambda: strict_json_bytes(b'{"same":1,"same":2}', "duplicate"),
        "duplicate JSON member",
    )
    expect_denial(
        cases,
        "lone-surrogate",
        lambda: strict_json_bytes(b'{"value":"\\ud800"}', "surrogate"),
        "invalid Unicode scalar",
    )
    expect_pass(
        cases,
        "valid-surrogate-pair",
        lambda: strict_json_bytes(b'{"value":"\\ud83d\\ude00"}', "surrogate-pair"),
    )
    expect_denial(
        cases,
        "invalid-utf8",
        lambda: strict_json_bytes(b'{"value":"\xff"}', "invalid-utf8"),
        "cannot parse strict JSON",
    )
    expect_pass(
        cases,
        "canonical-output-exactly-four-mib",
        lambda: canonical_json("a" * (MAX_STRUCTURED_JSON_BYTES - 2)),
    )
    expect_denial(
        cases,
        "canonical-output-over-four-mib",
        lambda: canonical_json("a" * (MAX_STRUCTURED_JSON_BYTES - 1)),
        "output byte limit",
    )
    with TemporaryDirectory(prefix="bytedesk-strict-json-") as directory:
        oversized = Path(directory) / "oversized.json"
        oversized.write_bytes(b" " * (MAX_STRUCTURED_JSON_BYTES + 1))
        expect_denial(
            cases,
            "file-loader-bounded-read",
            lambda: load_json(oversized),
            "input byte limit",
        )

    result = {
        "profile": "bytedesk.strict-json-resource-conformance/1",
        "limits": {
            "inputBytes": MAX_STRUCTURED_JSON_BYTES,
            "canonicalBytes": MAX_STRUCTURED_JSON_BYTES,
            "depth": MAX_JSON_MODEL_DEPTH,
            "nodesIncludingMemberNames": MAX_JSON_MODEL_NODES,
            "minimumInteger": MIN_SAFE_INTEGER,
            "maximumInteger": MAX_SAFE_INTEGER,
        },
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
    except ContractToolError as error:
        print(f"strict JSON conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
