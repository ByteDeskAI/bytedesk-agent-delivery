#!/usr/bin/env python3
"""Materialize the canonical, independently supplied test trust snapshot.

This helper is conformance-only. Production trust policy is supplied by the
protected reusable signer workflow and is never synthesized from release-tag
repository code.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from contractlib import ContractToolError, canonical_json, load_json, sha256_bytes, write_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-digest", required=True)
    args = parser.parse_args()

    policy = load_json(args.source.resolve())
    if not isinstance(policy, dict):
        raise ContractToolError("test trust-policy source root is not an object")
    payload = canonical_json(policy)
    digest = sha256_bytes(payload)
    if digest != args.expected_digest:
        raise ContractToolError(
            "canonical test trust-policy digest differs from the reviewed Make input"
        )
    write_bytes(args.output.resolve(), payload)
    print(f"trustPolicy={args.output.resolve()} trustPolicyDigest={digest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"test trust-policy creation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
