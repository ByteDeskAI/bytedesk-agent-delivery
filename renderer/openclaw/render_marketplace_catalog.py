#!/usr/bin/env python3
"""Render the real marketplace catalog through the generic OpenClaw adapter.

AD-17 required-work item 1: "Generate the expected public OpenClaw catalog
bundle from exact signed source/render digests..." This produces that
bundle - a deterministic render of every real, already-validated
`bytedesk-agent-marketplace` package through `transform.render_openclaw` -
using only the generic renderer built for AD-06. It does not require any
ByteDesk-specific OpenClaw data (none exists; see AD-17's own gap note),
and it is not the migration map/full-catalog comparison AD-17 required-
work item 5 separately assigns to the ByteDesk OpenClaw workstream (that
still needs real OpenClaw deployment data this environment doesn't have).

Signing: the "signed" half of "signed source/render digests" is not
attempted here beyond the ephemeral test-key pattern already established
throughout this repository (`scripts/contracts/sign_test_ephemeral.py`,
`signing/kms/ephemeral.py`) - no production KMS exists. This script
produces the real render and its real digests; production signing remains
a documented infra-defaults.md gap, not silently skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from transform import (  # noqa: E402
    RendererInputParameters,
    UnsupportedSemanticsError,
    render_openclaw,
)


def discover_marketplace_packages(agents_root: Path) -> list[Path]:
    return sorted(agents_root.glob("*/agent.yaml"))


def render_catalog(agents_root: Path, params_factory) -> dict:
    entries = []
    for agent_yaml in discover_marketplace_packages(agents_root):
        package_id = agent_yaml.parent.name
        document = yaml.safe_load(agent_yaml.read_text())
        params = params_factory(package_id)
        try:
            result = render_openclaw(document, params)
        except UnsupportedSemanticsError as error:
            entries.append({"packageId": package_id, "outcome": "unsupported", "reason": str(error)})
            continue
        entries.append(
            {
                "packageId": package_id,
                "outcome": "rendered",
                "compatibility": result.compatibility.outcome,
                "compatibilityNotes": list(result.compatibility.notes),
                "treeDigest": result.tree_digest,
                "archiveDigest": result.archive_digest,
                "fileCount": result.file_count,
            }
        )
    return {
        "profile": "bytedesk.openclaw-catalog-render-manifest/1",
        "packageCount": len(entries),
        "renderedCount": sum(1 for e in entries if e["outcome"] == "rendered"),
        "unsupportedCount": sum(1 for e in entries if e["outcome"] == "unsupported"),
        "signing": "ephemeral-test-key-pattern-only; no production KMS in this environment",
        "entries": entries,
    }


def default_params(package_id: str) -> RendererInputParameters:
    # A real, valid OpenClaw model string (per docs.openclaw.ai) used as the
    # generic catalog example - not a ByteDesk-specific or credentialed
    # binding. A real deployment compiler would supply its own choice here.
    return RendererInputParameters(
        agent_id=package_id,
        workspace=f"~/.openclaw/workspace-{package_id}",
        model="anthropic/claude-opus-4-6",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marketplace-agents-root", required=True, type=Path)
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parent / "catalog-render/manifest.json",
        type=Path,
    )
    args = parser.parse_args()

    manifest = render_catalog(args.marketplace_agents_root, default_params)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        f"rendered {manifest['renderedCount']}/{manifest['packageCount']} packages "
        f"through the generic OpenClaw adapter ({manifest['unsupportedCount']} unsupported)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
