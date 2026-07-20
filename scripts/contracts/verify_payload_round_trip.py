#!/usr/bin/env python3
"""Prove arbitrary YAML and complete-byte binary payloads remain byte exact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractlib import REPOSITORY_ROOT, ContractToolError, sha256_bytes, write_json
from verify_bundle import (
    MANIFEST_ARCHIVE_PATH,
    inventory_map,
    read_archive,
    strict_json_bytes,
    verify_inventory,
)


ARBITRARY_YAML = "contracts/fixtures/encoding/payload/arbitrary-unparsed.yaml"
EVERY_BYTE_BINARY = "contracts/fixtures/encoding/payload/every-byte-value.bin"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    members = read_archive(args.bundle.resolve())
    manifest = strict_json_bytes(members[MANIFEST_ARCHIVE_PATH], MANIFEST_ARCHIVE_PATH)
    verify_inventory(manifest, members)
    inventory = inventory_map(manifest, members)

    cases: list[dict[str, object]] = []
    for path in (ARBITRARY_YAML, EVERY_BYTE_BINARY):
        source = (REPOSITORY_ROOT / path).read_bytes()
        archived = members.get(path)
        if archived is None or archived != source:
            raise ContractToolError(f"payload did not survive bundle round trip byte-for-byte: {path}")
        digest = sha256_bytes(source)
        entry = inventory.get(path)
        if entry is None or entry.get("digest") != digest or entry.get("size") != len(source):
            raise ContractToolError(f"payload inventory does not bind source bytes: {path}")
        cases.append(
            {
                "path": path,
                "size": len(source),
                "sourceDigest": digest,
                "archiveDigest": sha256_bytes(archived),
                "outcome": "pass",
            }
        )

    binary = (REPOSITORY_ROOT / EVERY_BYTE_BINARY).read_bytes()
    if binary != bytes(range(256)):
        raise ContractToolError("binary payload is not the exact ordered 0x00..0xff byte set")
    yaml_payload = (REPOSITORY_ROOT / ARBITRARY_YAML).read_bytes()
    if not yaml_payload.startswith(b"%YAML 1.2\n") or b"*must-not-be-resolved" not in yaml_payload:
        raise ContractToolError("arbitrary YAML payload fixture lost its parser-denial markers")

    result = {
        "profile": "bytedesk.byte-exact-payload-round-trip-evidence/1",
        "yamlParserInvoked": False,
        "binaryByteValueCount": len(set(binary)),
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
    except (ContractToolError, OSError) as error:
        print(f"payload round-trip verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
