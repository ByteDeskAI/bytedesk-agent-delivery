#!/usr/bin/env python3
"""Emit exact, machine-readable evidence for two clean contract builds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from contractlib import (
    ContractToolError,
    REPOSITORY_ROOT,
    sha256_bytes,
    stable_read_bytes,
    write_json,
)


MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def _display_path(path: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.name


def compare_pair(
    artifact: str,
    left: Path,
    right: Path,
    *,
    maximum_bytes: int,
) -> dict[str, object]:
    left_bytes = stable_read_bytes(
        left,
        description=f"first {artifact} build",
        maximum_bytes=maximum_bytes,
    )
    right_bytes = stable_read_bytes(
        right,
        description=f"second {artifact} build",
        maximum_bytes=maximum_bytes,
    )
    if left_bytes != right_bytes:
        raise ContractToolError(f"clean {artifact} builds are not byte-for-byte identical")
    digest = sha256_bytes(left_bytes)
    return {
        "artifact": artifact,
        "firstPath": _display_path(left),
        "secondPath": _display_path(right),
        "size": len(left_bytes),
        "firstDigest": digest,
        "secondDigest": sha256_bytes(right_bytes),
        "byteForByteEqual": True,
        "outcome": "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-a", type=Path, required=True)
    parser.add_argument("--bundle-b", type=Path, required=True)
    parser.add_argument("--manifest-a", type=Path, required=True)
    parser.add_argument("--manifest-b", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    comparisons = [
        compare_pair(
            "contract-bundle",
            args.bundle_a,
            args.bundle_b,
            maximum_bytes=MAX_BUNDLE_BYTES,
        ),
        compare_pair(
            "contract-bundle-manifest",
            args.manifest_a,
            args.manifest_b,
            maximum_bytes=MAX_MANIFEST_BYTES,
        ),
    ]
    result = {
        "profile": "bytedesk.reproducible-contract-build-evidence/1",
        "comparisonCount": len(comparisons),
        "comparisons": comparisons,
        "outcome": "pass",
    }
    write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError) as error:
        print(f"reproducible build comparison failed: {error}", file=sys.stderr)
        raise SystemExit(1)
