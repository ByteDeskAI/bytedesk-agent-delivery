#!/usr/bin/env python3
"""Exercise exact-file reproducibility comparison and its denial path."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from contractlib import ContractToolError, write_json
from compare_reproducible_builds import compare_pair


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        left = root / "left.bin"
        equal = root / "equal.bin"
        changed = root / "changed.bin"
        left.write_bytes(b"contract-bytes")
        equal.write_bytes(b"contract-bytes")
        changed.write_bytes(b"contract-byteS")

        result = compare_pair("self-test", left, equal, maximum_bytes=64)
        if not result["byteForByteEqual"]:
            raise AssertionError("equal files were not reported equal")

        try:
            compare_pair("self-test-denial", left, changed, maximum_bytes=64)
        except ContractToolError:
            pass
        else:
            raise AssertionError("changed file was reported reproducible")

    result = {
        "profile": "bytedesk.reproducible-build-comparator-tests/1",
        "caseCount": 2,
        "cases": [
            {"id": "exact-bytes", "outcome": "pass"},
            {"id": "one-byte-change", "outcome": "denied"},
        ],
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(
        '{"profile":"bytedesk.reproducible-build-comparator-tests/1",'
        '"caseCount":2,"outcome":"pass"}'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
