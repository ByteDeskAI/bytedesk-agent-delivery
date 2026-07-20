#!/usr/bin/env python3
"""Schema-owned tenant-free public-render authority helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from renderer_authority import (
    inline_authority_preimage,
    schema_field_authority_preimage,
)
from signing_authority import signer_identity_preimage


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts/schemas/v1"
HARNESS_RENDER_SCHEMA = json.loads(
    (SCHEMA_ROOT / "harness-render.schema.json").read_text(encoding="utf-8")
)
PUBLIC_SOURCE_AUTH_SCHEMA = json.loads(
    (SCHEMA_ROOT / "public-source-authentication-evidence.schema.json").read_text(
        encoding="utf-8"
    )
)
PUBLIC_RENDER_EXCLUDED_FIELDS = frozenset(
    HARNESS_RENDER_SCHEMA["x-bytedesk-digestAuthority"]["exclude"]
)
PUBLIC_RENDER_AUTHORITY_FIELDS = tuple(
    field
    for field in HARNESS_RENDER_SCHEMA["required"]
    if field not in PUBLIC_RENDER_EXCLUDED_FIELDS
)


def public_render_preimage(document: dict[str, Any]) -> dict[str, Any]:
    """Return the complete schema-owned HarnessRender signing preimage."""

    return inline_authority_preimage(document, HARNESS_RENDER_SCHEMA)


def public_source_authentication_preimage(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Return the exact detached public-source evidence digest preimage."""

    return schema_field_authority_preimage(
        evidence,
        PUBLIC_SOURCE_AUTH_SCHEMA,
        "evidenceDigest",
    )


def public_source_publisher_identity_preimage(
    signer: dict[str, Any],
) -> dict[str, Any]:
    """Bind the complete purpose-separated signer identity permitted by policy."""

    if signer["purpose"] != "public-source-v1":
        raise ValueError("public-source signer has the wrong purpose")
    return signer_identity_preimage(signer)


def require_tenant_free_public_lineage(
    public_render: dict[str, Any],
    render_manifest: dict[str, Any],
) -> None:
    """Reject consumer-scoped inputs before signing a public render."""

    if render_manifest.get("scope") != "public":
        raise ValueError("public render requires a public render manifest")
    if render_manifest.get("privateSkills") != []:
        raise ValueError("public render manifest contains private skills")
    if render_manifest.get("bindingDigest") is not None:
        raise ValueError("public render manifest contains a binding digest")
    if render_manifest.get("customizationDigest") is not None:
        raise ValueError("public render manifest contains a customization digest")
    forbidden = {
        "consumerId",
        "targetId",
        "privateSkills",
        "bindingDigest",
        "customizationDigest",
        "authoritySnapshot",
        "skillApprovals",
        "credentials",
    }
    present = sorted(forbidden.intersection(public_render))
    if present:
        raise ValueError(f"public render contains consumer fields: {present}")
