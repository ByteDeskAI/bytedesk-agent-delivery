#!/usr/bin/env python3
"""Create deterministic negative bundle cases for denial testing only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_bundle import build_tar, inventory
from contractlib import ContractToolError, canonical_json, write_bytes
from verify_bundle import MANIFEST_ARCHIVE_PATH, read_archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--inject-repository-only",
        type=Path,
        help="add a repository-only file with a valid manifest inventory entry",
    )
    parser.add_argument(
        "--append-trailing-bytes",
        action="store_true",
        help="append non-tar bytes after the deterministic end marker",
    )
    args = parser.parse_args()
    if args.inject_repository_only and args.append_trailing_bytes:
        raise ContractToolError("select only one explicit bundle mutation")
    if args.append_trailing_bytes:
        payload = args.source.resolve().read_bytes() + b"BYTEDESK-TRAILING-BYTES"
        write_bytes(args.output.resolve(), payload)
        print(f"tamperedBundle={args.output.resolve()} mutation=trailing-bytes")
        return 0
    if args.inject_repository_only:
        source = args.source.resolve()
        injected = args.inject_repository_only.resolve()
        try:
            injected_path = injected.relative_to(Path(__file__).resolve().parents[2]).as_posix()
        except ValueError as error:
            raise ContractToolError("injected test member must be inside the repository") from error
        members = read_archive(source)
        manifest = json.loads(members.pop(MANIFEST_ARCHIVE_PATH))
        payload = injected.read_bytes()
        members[injected_path] = payload
        manifest["documents"].append(inventory(injected_path, payload))
        manifest["documents"].sort(key=lambda item: item["path"])
        build_tar(args.output.resolve(), members, canonical_json(manifest))
        print(f"tamperedBundle={args.output.resolve()} injected={injected_path}")
        return 0

    payload = bytearray(args.source.resolve().read_bytes())
    if len(payload) <= 1024:
        raise ContractToolError("test bundle is unexpectedly too small to mutate")
    payload[1024] ^= 1
    write_bytes(args.output.resolve(), bytes(payload))
    print(f"tamperedBundle={args.output.resolve()} offset=1024")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError) as error:
        print(f"test bundle mutation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
