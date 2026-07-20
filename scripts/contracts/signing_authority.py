#!/usr/bin/env python3
"""Shared schema-owned signing identity and provider-evidence helpers."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import rfc8785


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIGNER_IDENTITY_SCHEMA = json.loads(
    (
        REPOSITORY_ROOT
        / "contracts/schemas/v1/signer-identity.schema.json"
    ).read_text(encoding="utf-8")
)
SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.signer-authentication-evidence.v1+json"
)
CONTRACT_BUNDLE_RELEASE_PURPOSE = "contract-bundle-release-v1"
CONTRACT_BUNDLE_MEDIA_TYPES = frozenset(
    {
        "application/vnd.bytedesk.agent.contract-bundle.v1+json",
        "application/vnd.bytedesk.agent.contract-bundle.v1+tar",
    }
)
SIGNER_IDENTITY_COMMON_FIELDS = frozenset(SIGNER_IDENTITY_SCHEMA["required"])
SIGNER_IDENTITY_FIELDS_BY_CREDENTIAL = {
    "kms_key": SIGNER_IDENTITY_COMMON_FIELDS | {"keyVersion", "publicKeyDigest"},
    "sigstore_keyless": SIGNER_IDENTITY_COMMON_FIELDS | {"trustedRootDigest"},
}


def _require_exact_signer(signer: dict[str, Any]) -> None:
    expected = SIGNER_IDENTITY_FIELDS_BY_CREDENTIAL.get(signer.get("credentialKind"))
    if expected is None or set(signer) != expected:
        raise ValueError("signer is not the closed signer-identity schema object")


def _reject_contract_bundle_kms_authority(
    *, purpose: str, subject_media_type: str
) -> None:
    """Reject contract-bundle authority before KMS policy or evidence work."""

    if (
        purpose == CONTRACT_BUNDLE_RELEASE_PURPOSE
        or subject_media_type in CONTRACT_BUNDLE_MEDIA_TYPES
    ):
        raise ValueError("KMS signing cannot sign contract-bundle authority")


def signer_identity_preimage(signer: dict[str, Any]) -> dict[str, Any]:
    """Return the domain-separated full signer identity preimage."""

    _require_exact_signer(signer)
    return {
        "profile": "bytedesk.authenticated-signer-identity/1",
        "signer": deepcopy(signer),
    }


def signer_identity_digest(signer: dict[str, Any]) -> str:
    """Return the RFC 8785 SHA-256 identity used across authority evidence."""

    return "sha256:" + hashlib.sha256(
        rfc8785.dumps(signer_identity_preimage(signer))
    ).hexdigest()


def signer_authority_binding_preimage(
    *,
    signer: dict[str, Any],
    trust_policy: dict[str, str],
    repository: str,
) -> dict[str, Any]:
    """Bind a full signer identity to the exact policy and signing repository."""

    _require_exact_signer(signer)
    if set(trust_policy) != {"id", "digest"}:
        raise ValueError("signer authority binding requires an exact trust-policy ref")
    return {
        "profile": "bytedesk.signer-authority-binding/1",
        "trustPolicy": deepcopy(trust_policy),
        "repository": repository,
        "signer": deepcopy(signer),
    }


def signer_authority_binding_digest(
    *,
    signer: dict[str, Any],
    trust_policy: dict[str, str],
    repository: str,
) -> str:
    """Return the RFC 8785 SHA-256 exact policy/signer/repository binding."""

    return "sha256:" + hashlib.sha256(
        rfc8785.dumps(
            signer_authority_binding_preimage(
                signer=signer,
                trust_policy=trust_policy,
                repository=repository,
            )
        )
    ).hexdigest()


def exact_policy_signer(
    policy: dict[str, Any],
    *,
    purpose: str,
    subject_media_type: str,
    key_version: str,
    algorithm: str,
    public_key_digest: str,
) -> dict[str, Any]:
    """Resolve exactly one full signer tuple from an independently loaded policy."""

    _reject_contract_bundle_kms_authority(
        purpose=purpose,
        subject_media_type=subject_media_type,
    )

    matches = [
        signer
        for signer in policy.get("signers", [])
        if signer.get("purpose") == purpose
        and signer.get("credentialKind") == "kms_key"
        and signer.get("keyVersion") == key_version
        and signer.get("algorithm") == algorithm
        and signer.get("publicKeyDigest") == public_key_digest
    ]
    if len(matches) != 1:
        raise ValueError("trust policy does not permit exactly one full signer tuple")
    _require_exact_signer(matches[0])
    return deepcopy(matches[0])


def build_signer_authentication_evidence(
    *,
    schema_descriptor: dict[str, str],
    purpose: str,
    subject_media_type: str,
    request_id: str,
    request_digest: str,
    provider_request_id: str,
    provider_audit_id: str,
    authenticated_signer: dict[str, Any],
    issued_at: str,
    trust_policy: dict[str, str],
) -> dict[str, Any]:
    """Build the closed, graph-independent provider authentication evidence object."""

    _reject_contract_bundle_kms_authority(
        purpose=purpose,
        subject_media_type=subject_media_type,
    )

    _require_exact_signer(authenticated_signer)
    if authenticated_signer["credentialKind"] != "kms_key":
        raise ValueError("provider KMS evidence requires a kms_key signer identity")
    if authenticated_signer["purpose"] != purpose:
        raise ValueError("provider evidence purpose differs from signer purpose")
    return {
        "contract": "bytedesk.signer-authentication-evidence/1",
        "schema": deepcopy(schema_descriptor),
        "purpose": purpose,
        "requestId": request_id,
        "requestDigest": request_digest,
        "providerRequestId": provider_request_id,
        "providerAuditId": provider_audit_id,
        "keyVersion": authenticated_signer["keyVersion"],
        "algorithm": authenticated_signer["algorithm"],
        "publicKeyDigest": authenticated_signer["publicKeyDigest"],
        "authenticatedSigner": deepcopy(authenticated_signer),
        "issuedAt": issued_at,
        "trustPolicy": deepcopy(trust_policy),
    }
