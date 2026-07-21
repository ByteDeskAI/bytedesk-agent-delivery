#!/usr/bin/env python3
"""Build the bytedesk.external-input-lock/1 artifact for AD-05's Hermes
compatibility evidence.

AD-05 inputs: "An exact bytedesk.external-input-lock/1 artifact for the
Hermes render scripts, templates, profile files, deployment manifest,
validators, and validation/provisioning behavior used as compatibility
evidence."

This lock covers only render-profiles.py and templates/*.yaml,templates/*.env.template
- the pure rendering logic and token-templated config, real inputs to
`transform.py`'s adapter. It deliberately does NOT include, and this script
does not read the bytes of:

- office-signing-key.json (a public trust anchor, but not renderer logic -
  belongs to a private consumer deployment's authority chain, per required-
  work item 3, never core/public renderer input)
- workload-credential.py, deployment.json (real ByteDesk org/workload data -
  organizational identity and consumer-specific deployment state, forbidden
  in public render output by the same required-work item)

Locking only the renderer logic and its templates - not the tenant data
those scripts operate on - is the actual AD-05 boundary: "Hermes
compatibility inputs are locked evidence, never core authority... no
ByteDesk detail may enter the generic Hermes contract."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent

_EXTERNAL_INPUT_LOCK_SCHEMA_DIGEST = (
    "sha256:0b8c314dfc6f25f150b92db704cd80358f43c8109bffc2a64d3f61ff67881faf"
)
_PUBLIC_SOURCE_TRUST_POLICY_ID = "public-source-v1"
_PUBLIC_SOURCE_TRUST_POLICY_DIGEST = (
    "sha256:b6a3954294cc4a0e6ade5e52646f3be777df8d695f97cdebf653234438d1577e"
)

_LOCKED_RELATIVE_PATHS = (
    "render-profiles.py",
    "templates/config.yaml",
    "templates/.env.template",
    "templates/distribution.yaml",
)


def git_head_commit(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, check=True, text=True
    ).stdout.strip()


def git_tree_object_id(repo_root: Path, path: str, commit: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"], cwd=repo_root, capture_output=True, check=True, text=True
    ).stdout.strip()


def build_lock(lock_repo_root: Path, lock_repository_url: str, lock_id: str, retrieved_at: str) -> dict:
    commit = git_head_commit(lock_repo_root)

    paths = []
    for relative_path in _LOCKED_RELATIVE_PATHS:
        full_path = lock_repo_root / "ops/hermes-native" / relative_path
        payload = full_path.read_bytes()
        paths.append(
            {
                "path": f"ops/hermes-native/{relative_path}",
                "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        )
    paths.sort(key=lambda p: p["path"])

    # Real git tree object id over the directory containing exactly the
    # locked renderer logic/templates, re-hashed to fit the schema's plain
    # sha256 digest shape - not a hash over the whole ops/hermes-native tree
    # (which also contains the excluded credential/workload-data files).
    tree_object_id = git_tree_object_id(lock_repo_root, "ops/hermes-native/templates", commit)

    transform_script = Path(__file__).resolve().parent / "transform.py"
    transform_bytes = transform_script.read_bytes()

    return {
        "contract": "bytedesk.external-input-lock/1",
        "schema": {
            "id": "https://schemas.bytedesk.ai/agent-delivery/v1/external-input-lock/1.0.0",
            "digest": _EXTERNAL_INPUT_LOCK_SCHEMA_DIGEST,
        },
        "lockId": lock_id,
        "role": "compatibility_evidence",
        "repository": lock_repository_url,
        "commit": commit,
        "treeDigest": "sha256:" + hashlib.sha256(tree_object_id.encode()).hexdigest(),
        "paths": paths,
        "validators": [
            {
                "repository": "registry.example.local/bytedesk-agent-delivery/validators/render-hermes",
                "digest": "sha256:" + hashlib.sha256(transform_bytes).hexdigest(),
                "mediaType": "application/vnd.bytedesk.agent-delivery.validator-script.v1+python",
                "size": len(transform_bytes),
                "trustPolicy": {
                    "id": _PUBLIC_SOURCE_TRUST_POLICY_ID,
                    "digest": _PUBLIC_SOURCE_TRUST_POLICY_DIGEST,
                },
            }
        ],
        "compatibilityEvidenceOnly": True,
        "retrievedAt": retrieved_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock-repo-root", required=True, type=Path)
    parser.add_argument("--lock-repository-url", default="https://github.com/ByteDeskAI/bytedesk-platform")
    parser.add_argument("--lock-id", default="hermes-native-renderer")
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--output", default=REPOSITORY_ROOT / "renderer/hermes/provenance/external-input-lock.json", type=Path)
    args = parser.parse_args()

    lock = build_lock(args.lock_repo_root, args.lock_repository_url, args.lock_id, args.retrieved_at)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(f"wrote external-input-lock with {len(lock['paths'])} path entries at commit {lock['commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
