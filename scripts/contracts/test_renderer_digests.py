#!/usr/bin/env python3
"""Verify renderer digest preimages and cross-object authority invariants."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import rfc8785
from referencing import Registry, Resource

from renderer_authority import (
    RENDERER_SELECTION_PROFILE,
    inline_authority_preimage,
    renderer_selection_preimage,
    schema_field_authority_preimage,
)
from public_render_authority import (
    public_render_preimage,
    public_source_authentication_preimage,
    public_source_publisher_identity_preimage,
    require_tenant_free_public_lineage,
)
from signing_authority import (
    SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
    build_signer_authentication_evidence,
    exact_policy_signer,
    signer_authority_binding_digest,
    signer_identity_digest,
)
from trusted_keyless_adapter import (
    KEYLESS_VERIFICATION_PROFILE,
    SIGNING_REQUEST_MEDIA_TYPE,
    SIGSTORE_BUNDLE_MEDIA_TYPE,
    TrustedKeylessVerificationAdapter,
    TrustedKeylessVerificationError,
    keyless_signature_verification_vector,
)
from trusted_kms_adapter import (
    CONTRACT_BUNDLE_MEDIA_TYPES,
    CONTRACT_BUNDLE_RELEASE_PURPOSE,
    TrustedKmsVerificationAdapter,
    TrustedKmsVerificationError,
)
from trust_policy_pins import (
    TrustPolicyPinError,
    TrustPolicyPinSet,
    TrustedTrustPolicyProviderAdapter,
    build_pin_set_provider_evidence,
    pin_set_digest,
    pin_set_document_descriptor,
    pin_set_provider_authentication_vector,
)
from status_merkle import (
    status_leaf_digest,
    verify_consistency as verify_merkle_consistency,
    verify_inclusion as verify_merkle_inclusion,
)
from oci_graph import (
    OciGraphError,
    OciGraphVerifier,
    decode_bounded_bytes,
    decode_oci_blob_stream,
    encode_bounded_bytes,
    public_render_publication_payload_digest,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = REPOSITORY_ROOT / "contracts" / "ports" / "v1" / "protocol-profiles.json"
CASE_PATH = REPOSITORY_ROOT / "contracts" / "fixtures" / "operations" / "renderer-digest.cases.json"
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"

CAPABILITY_COVERAGE_PROFILE = "bytedesk.renderer-capability-coverage/1"
EFFECTIVE_SKILL_SET_PROFILE = "bytedesk.renderer-effective-skill-set/1"
EFFECTIVE_INPUT_PROFILE = "bytedesk.renderer-effective-input/1"
FUNCTIONAL_INPUT_PROFILE = "bytedesk.renderer-functional-input/1"
COMPATIBILITY_COVERAGE_PROFILE = "bytedesk.renderer-compatibility-coverage/1"
OUTPUT_TREE_PROFILE = "bytedesk.renderer-output-tree/1"
REPRODUCIBILITY_PROFILE = "bytedesk.renderer-reproducibility/1"
RENDERER_ATTEMPT_AUTHORITY_PROFILE = "bytedesk.renderer-attempt-authority-digest/1"
RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_PROFILE = (
    "bytedesk.renderer-attempt-authentication-evidence-digest/1"
)
RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_PROFILE = (
    "bytedesk.renderer-execution-authentication-evidence-digest/1"
)
DIGEST_AUTHORITY_PROFILE = "bytedesk.renderer-digest-authority/1"
CAPABILITY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-capability/1.0.0"
COMPATIBILITY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-compatibility-result/1.0.0"
MANIFEST_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/render-manifest/1.0.0"
ALLOWLIST_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-allowlist/1.0.0"
RELEASE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-release/1.0.0"
RENDERER_SELECTION_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-selection/1.0.0"
RENDERER_EXECUTION_RECEIPT_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-execution-receipt/1.0.0"
RENDERER_ATTEMPT_AUTHORITY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-attempt-authority/1.0.0"
RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-execution-authentication-evidence/1.0.0"
PRODUCT_RELEASE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/product-release-manifest/1.0.0"
PRODUCT_DISTRIBUTION_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/product-distribution-manifest/1.0.0"
HARNESS_RENDER_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0"
PUBLIC_SOURCE_AUTH_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/public-source-authentication-evidence/1.0.0"
RELEASE_QUALIFICATION_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification/1.0.0"
RELEASE_QUALIFICATION_EVIDENCE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-evidence/1.0.0"
RELEASE_QUALIFICATION_PREDICATE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-predicate/1.0.0"
RELEASE_QUALIFICATION_POLICY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-policy/1.0.0"
RELEASE_QUALIFICATION_FINALIZATION_MATRIX_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-finalization-matrix/1.0.0"
RELEASE_STATUS_ELIGIBILITY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status-eligibility-evidence/1.0.0"
VERIFICATION_RESULT_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0"
RELEASE_STATUS_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status/1.0.0"
RELEASE_STATUS_HEAD_CHECKPOINT_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status-head-checkpoint/1.0.0"
RELEASE_STATUS_HEAD_AUTH_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status-head-authentication-evidence/1.0.0"
RELEASE_STATUS_LOG_CONSISTENCY_PROOF_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status-log-consistency-proof/1.0.0"
RELEASE_STATUS_LOG_INCLUSION_PROOF_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status-log-inclusion-proof/1.0.0"
RELEASE_STATUS_APPEND_RESOLUTION_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/release-status-append-resolution/1.0.0"
QUALIFICATION_SELECTION_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-selection/1.0.0"
QUALIFICATION_SUITE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-suite/1.0.0"
QUALIFICATION_ATTEMPT_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-attempt/1.0.0"
QUALIFICATION_ATTEMPT_AUTH_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-attempt-authentication-evidence/1.0.0"
QUALIFICATION_EVIDENCE_TREE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-evidence-tree/1.0.0"
QUALIFICATION_RECEIPT_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-receipt/1.0.0"
QUALIFICATION_RECEIPT_AUTH_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-receipt-authentication-evidence/1.0.0"
RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-attempt-authentication-evidence/1.0.0"
TRUST_POLICY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy/1.0.0"
SIGNING_RESULT_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/signing-result/1.0.0"
SIGNER_AUTHENTICATION_EVIDENCE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/signer-authentication-evidence/1.0.0"
SIGNER_IDENTITY_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/signer-identity/1.0.0"
TRUST_POLICY_PIN_SET_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set/1.0.0"
TRUST_POLICY_PIN_SET_DESCRIPTOR_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set-descriptor/1.0.0"
TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set-provider-evidence/1.0.0"
CONTRACT_BUNDLE_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/contract-bundle/1.0.0"
PRODUCT_TRUST_POLICY_PROVIDER_ID = "product-trust-policy-provider"
RENDERER_CAS_BLOB_ROOT = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "operations"
    / "renderer-cas"
    / "blobs"
    / "sha256"
)
PUBLIC_RENDER_SIGNING_RESULT_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "signing-result__public-render.json"
)
PUBLIC_SOURCE_AUTHENTICATION_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "public-source-authentication-evidence__source.json"
)
PRIVATE_SUBJECT_PUBLIC_SOURCE_AUTHENTICATION_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "negative"
    / "public-source-authentication-evidence__private-subject.json"
)
RELEASE_STATUS_APPEND_RESOLUTION_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "release-status-append-resolution__committed.json"
)
PRODUCT_RELEASE_SIGNER_AUTHENTICATION_EVIDENCE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "signer-authentication-evidence__product-release.json"
)
PRODUCT_RELEASE_SIGNER_IDENTITY_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "signer-identity__product-release.json"
)
PRODUCT_RELEASE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "product-release-manifest__current.json"
)
QUALIFICATION_COVERAGE_PROFILE = "bytedesk.renderer-qualification-required-coverage/1"
PRODUCT_KMS_SIGNING_PURPOSES = (
    "product-release-v1",
    "release-qualification-policy-v1",
    "release-qualification-attempt-v1",
    "release-qualification-receipt-v1",
    "release-qualification-evidence-v1",
    "release-qualification-decision-v1",
    "release-status-v1",
    "release-status-head-v1",
    "release-status-eligibility-v1",
    "renderer-attempt-v1",
    "renderer-execution-v1",
    "public-source-v1",
    "public-render-v1",
)
PRODUCT_TRUST_PURPOSES = (
    PRODUCT_KMS_SIGNING_PURPOSES[0],
    CONTRACT_BUNDLE_RELEASE_PURPOSE,
    *PRODUCT_KMS_SIGNING_PURPOSES[1:],
)
SELECTION_FIXTURES = {
    "allowlist": REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "renderer-allowlist__compiled.json",
    "release": REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "renderer-release__native.json",
}
SELECTION_SCHEMA_IDS = {
    "allowlist": ALLOWLIST_SCHEMA_ID,
    "release": RELEASE_SCHEMA_ID,
}


class RendererDigestError(RuntimeError):
    """A renderer object violates the frozen digest-authority contract."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise RendererDigestError(code, detail)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RendererDigestError("duplicate_json_member", key)
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                RendererDigestError("non_finite_number", value)
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RendererDigestError("invalid_json", f"{path}: {error}") from error
    require(isinstance(value, dict), "invalid_json_root", str(path))
    return value


def canonical_digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(value)).hexdigest()}"


def projection_descriptor(
    *,
    repository: str,
    media_type: str,
    document: dict[str, Any],
    trust_policy: dict[str, str],
) -> dict[str, Any]:
    payload = rfc8785.dumps(document)
    return {
        "repository": repository,
        "digest": raw_digest(payload),
        "mediaType": media_type,
        "size": len(payload),
        "trustPolicy": deepcopy(trust_policy),
    }


def build_schema_registry() -> tuple[Registry, dict[str, dict[str, Any]]]:
    registry = Registry()
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        schema_id = schema.get("$id")
        require(isinstance(schema_id, str), "schema_id_missing", str(path))
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
        schemas[schema_id] = schema
    return registry, schemas


def validate_schema_instance(
    instance: dict[str, Any],
    schema_id: str,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    schema = schemas[schema_id]
    require(
        instance.get("schema")
        == {"id": schema_id, "digest": canonical_digest(schema)},
        "schema_descriptor_mismatch",
        schema_id,
    )
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    require(
        not errors,
        "schema_validation_failed",
        f"{schema_id}: {errors[0].message if errors else ''}",
    )


def validate_plain_schema_instance(
    instance: dict[str, Any],
    schema_id: str,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    """Validate an authority-external object that has no inline schema field."""

    errors = sorted(
        Draft202012Validator(
            schemas[schema_id],
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    require(
        not errors,
        "schema_validation_failed",
        f"{schema_id}: {errors[0].message if errors else ''}",
    )


def raw_digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


RFC3339_INSTANT = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)


def timestamp(value: Any, identity: str) -> datetime:
    require(
        isinstance(value, str) and RFC3339_INSTANT.fullmatch(value) is not None,
        "invalid_timestamp_profile",
        identity,
    )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RendererDigestError(
            "invalid_timestamp_profile", f"{identity}: {value}"
        ) from error
    require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        "timestamp_without_timezone",
        identity,
    )
    return parsed.astimezone(timezone.utc)


def validate_timestamp_profile() -> int:
    require(
        timestamp("2026-07-17T12:00:00Z", "equivalent-z")
        == timestamp("2026-07-17T07:00:00-05:00", "equivalent-offset"),
        "timestamp_offset_normalization_failed",
        "equivalent instants",
    )
    require(
        timestamp("2026-07-17T11:59:59.999999Z", "fraction-before")
        < timestamp("2026-07-17T12:00:00.000000Z", "fraction-after"),
        "timestamp_fraction_order_failed",
        "fraction boundary",
    )
    for value in (
        "2026-07-17T12:00:00",
        "2026-07-17 12:00:00Z",
        "2026-07-17T12:00:00z",
        "2026-07-17T12:00:00.0000000Z",
    ):
        try:
            timestamp(value, "negative timestamp profile case")
        except RendererDigestError as error:
            require(
                error.code in {"invalid_timestamp_profile", "timestamp_without_timezone"},
                "wrong_timestamp_profile_error",
                value,
            )
        else:
            raise RendererDigestError("invalid_timestamp_accepted", value)
    return 6


def validate_attempt_dependency_expiry(
    *,
    issued_at: str,
    expires_at: str,
    completed_at: str,
    dependency_expiries: dict[str, str],
    identity: str,
) -> None:
    issued = timestamp(issued_at, f"{identity}:issuedAt")
    expires = timestamp(expires_at, f"{identity}:expiresAt")
    completed = timestamp(completed_at, f"{identity}:completedAt")
    require(
        issued < expires
        and all(
            expires <= timestamp(value, f"{identity}:{name}")
            for name, value in dependency_expiries.items()
        ),
        "renderer_attempt_expiry_exceeds_dependency",
        identity,
    )
    require(
        issued <= completed < expires
        and all(
            completed < timestamp(value, f"{identity}:{name}")
            for name, value in dependency_expiries.items()
        ),
        "renderer_receipt_expiry_exceeds_dependency",
        identity,
    )


def validate_attempt_expiry_boundaries() -> int:
    bounds = {
        "productCheckpointExpiresAt": "2026-07-17T12:05:00Z",
        "rendererCheckpointExpiresAt": "2026-07-17T12:05:00Z",
        "qualificationExpiresAt": "2026-08-16T12:00:00Z",
        "signingPolicyExpiresAt": "2027-01-01T00:00:00Z",
        "pinSetExpiresAt": "2027-01-01T00:00:00Z",
    }
    validate_attempt_dependency_expiry(
        issued_at="2026-07-17T12:00:04Z",
        expires_at="2026-07-17T12:05:00Z",
        completed_at="2026-07-17T12:04:59.999999Z",
        dependency_expiries=bounds,
        identity="attempt-expiry-equality-boundary",
    )
    require_semantic_denial(
        "renderer_attempt_expiry_exceeds_dependency",
        lambda: validate_attempt_dependency_expiry(
            issued_at="2026-07-17T12:00:04Z",
            expires_at="2026-07-17T12:05:01Z",
            completed_at="2026-07-17T12:05:00Z",
            dependency_expiries=bounds,
            identity="attempt-expiry-plus-one-second",
        ),
        "attempt expiry one second after checkpoint expiry",
    )
    require_semantic_denial(
        "renderer_receipt_expiry_exceeds_dependency",
        lambda: validate_attempt_dependency_expiry(
            issued_at="2026-07-17T12:00:04Z",
            expires_at="2026-07-17T12:05:00Z",
            completed_at="2026-07-17T12:05:00Z",
            dependency_expiries=bounds,
            identity="receipt-at-exact-expiry",
        ),
        "receipt completion at the exclusive expiry instant",
    )
    require_semantic_denial(
        "renderer_receipt_expiry_exceeds_dependency",
        lambda: validate_attempt_dependency_expiry(
            issued_at="2026-07-17T12:00:04Z",
            expires_at="2026-07-17T12:05:00Z",
            completed_at="2026-07-17T12:05:01Z",
            dependency_expiries=bounds,
            identity="receipt-expiry-plus-one-second",
        ),
        "receipt completion one second after checkpoint expiry",
    )
    return 4


def validate_signing_time_window(
    *,
    not_before: str,
    not_after: str,
    signed_at: str,
    verification_time: str,
    identity: str,
) -> None:
    signed = timestamp(signed_at, f"{identity}:signedAt")
    verified = timestamp(verification_time, f"{identity}:verificationTime")
    require(
        timestamp(not_before, f"{identity}:notBefore")
        <= signed
        < timestamp(not_after, f"{identity}:notAfter"),
        "signing_time_outside_policy",
        identity,
    )
    require(
        signed <= verified,
        "signing_time_after_verification",
        identity,
    )


def validate_signing_time_boundaries() -> int:
    validate_signing_time_window(
        not_before="2026-01-01T00:00:00Z",
        not_after="2027-01-01T00:00:00Z",
        signed_at="2026-01-01T00:00:00Z",
        verification_time="2026-01-01T00:00:00Z",
        identity="signing-not-before-equality",
    )
    validate_signing_time_window(
        not_before="2026-01-01T00:00:00Z",
        not_after="2027-01-01T00:00:00Z",
        signed_at="2026-12-31T23:59:59.999999Z",
        verification_time="2026-12-31T23:59:59.999999Z",
        identity="signing-last-valid-microsecond",
    )
    require_semantic_denial(
        "signing_time_outside_policy",
        lambda: validate_signing_time_window(
            not_before="2026-01-01T00:00:00Z",
            not_after="2027-01-01T00:00:00Z",
            signed_at="2027-01-01T00:00:00Z",
            verification_time="2027-01-01T00:00:00Z",
            identity="signing-at-policy-expiry",
        ),
        "signature exactly at policy notAfter",
    )
    require_semantic_denial(
        "signing_time_after_verification",
        lambda: validate_signing_time_window(
            not_before="2026-01-01T00:00:00Z",
            not_after="2027-01-01T00:00:00Z",
            signed_at="2026-07-17T12:00:01Z",
            verification_time="2026-07-17T12:00:00Z",
            identity="future-signature",
        ),
        "signature issued after verification time",
    )
    return 4


def load_jcs_object(payload: bytes, identity: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                RendererDigestError("non_finite_number", value)
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RendererDigestError("invalid_cas_json", f"{identity}: {error}") from error
    require(isinstance(value, dict), "invalid_cas_json", f"{identity}: root")
    require(
        rfc8785.dumps(value) == payload,
        "noncanonical_cas_json",
        identity,
    )
    return value


def is_sentinel_digest(digest: str) -> bool:
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return False
    value = digest.removeprefix("sha256:")
    if len(value) != 64:
        return False
    return any(
        value == value[:width] * (len(value) // width)
        for width in (1, 2, 4, 8, 16)
    )


class RendererCasResolver:
    """Resolve exact raw renderer fixture artifacts from the fixture-local CAS."""

    def __init__(
        self,
        registry: Registry,
        schemas: dict[str, dict[str, Any]],
        trust_policy_pin_set: TrustPolicyPinSet,
        signature_verification_vectors: list[dict[str, Any]],
        keyless_verification_vectors: list[dict[str, Any]],
    ) -> None:
        self.registry = registry
        self.schemas = schemas
        self.trust_policy_pin_set = trust_policy_pin_set
        try:
            self.signature_verifier = TrustedKmsVerificationAdapter(
                signature_verification_vectors
            )
        except TrustedKmsVerificationError as error:
            raise RendererDigestError(error.code, str(error)) from error
        try:
            self.keyless_signature_verifier = TrustedKeylessVerificationAdapter(
                keyless_verification_vectors
            )
        except TrustedKeylessVerificationError as error:
            raise RendererDigestError(error.code, str(error)) from error
        self.payloads: dict[str, bytes] = {}
        require(RENDERER_CAS_BLOB_ROOT.is_dir(), "renderer_cas_missing", str(RENDERER_CAS_BLOB_ROOT))
        for path in sorted(RENDERER_CAS_BLOB_ROOT.iterdir()):
            require(not path.is_symlink(), "renderer_cas_symlink", str(path))
            require(path.is_file(), "renderer_cas_non_regular", str(path))
            require(
                len(path.name) == 64
                and path.name == path.name.lower()
                and all(character in "0123456789abcdef" for character in path.name),
                "renderer_cas_invalid_name",
                path.name,
            )
            payload = path.read_bytes()
            digest = raw_digest(payload)
            require(
                digest == f"sha256:{path.name}",
                "renderer_cas_path_digest_mismatch",
                path.name,
            )
            require(digest not in self.payloads, "renderer_cas_duplicate", digest)
            self.payloads[digest] = payload
        require(bool(self.payloads), "renderer_cas_missing", "empty")

    def payload(self, digest: str, size: int | None = None) -> bytes:
        require(
            not is_sentinel_digest(digest),
            "sentinel_digest_in_positive_graph",
            digest,
        )
        require(digest in self.payloads, "renderer_cas_object_missing", digest)
        payload = self.payloads[digest]
        require(raw_digest(payload) == digest, "renderer_cas_digest_mismatch", digest)
        if size is not None:
            require(len(payload) == size, "renderer_cas_size_mismatch", digest)
        return payload

    def trust_policy(
        self,
        reference: dict[str, Any],
        repository: str,
        media_type: str,
        *,
        policy_use: str = "new",
        verification_time: str | None = None,
        signing_time: str | None = None,
    ) -> dict[str, Any]:
        require(set(reference) == {"id", "digest"}, "invalid_trust_reference", str(reference))
        if verification_time is None:
            if policy_use == "new":
                permitted = self.trust_policy_pin_set.current.get(reference["id"])
                require(
                    reference == permitted,
                    "trust_policy_pin_mismatch",
                    reference["id"],
                )
            else:
                historical = self.trust_policy_pin_set.historical.get(
                    (reference["id"], reference["digest"])
                )
                require(
                    reference == self.trust_policy_pin_set.current.get(reference["id"])
                    or historical is not None,
                    "trust_policy_pin_mismatch",
                    reference["id"],
                )
        else:
            try:
                self.trust_policy_pin_set.authorize_policy(
                    purpose=reference["id"],
                    reference=reference,
                    use=policy_use,
                    verification_time=verification_time,
                    signing_time=signing_time,
                )
            except TrustPolicyPinError as error:
                raise RendererDigestError(error.code, str(error)) from error
        payload = self.payload(reference["digest"])
        policy = load_jcs_object(payload, reference["digest"])
        validate_schema_instance(
            policy,
            TRUST_POLICY_SCHEMA_ID,
            self.registry,
            self.schemas,
        )
        require(policy["policyId"] == reference["id"], "trust_policy_id_mismatch", reference["id"])
        scope = policy["scope"]
        require(
            reference["id"] in scope["purposes"]
            and repository in scope["repositories"]
            and media_type in scope["mediaTypes"],
            "trust_policy_scope_mismatch",
            f"{reference['id']}:{repository}:{media_type}",
        )
        return policy

    def artifact(
        self,
        descriptor: dict[str, Any],
        *,
        media_type: str,
        contract: str | None = None,
        schema_id: str | None = None,
        policy_use: str = "new",
        verification_time: str | None = None,
        signing_time: str | None = None,
    ) -> dict[str, Any] | bytes:
        require(
            set(descriptor)
            == {"repository", "digest", "mediaType", "size", "trustPolicy"},
            "invalid_artifact_descriptor",
            str(descriptor),
        )
        require(descriptor["mediaType"] == media_type, "artifact_media_type_mismatch", descriptor["digest"])
        payload = self.payload(descriptor["digest"], descriptor["size"])
        self.trust_policy(
            descriptor["trustPolicy"],
            descriptor["repository"],
            descriptor["mediaType"],
            policy_use=policy_use,
            verification_time=verification_time,
            signing_time=signing_time,
        )
        if media_type.endswith("+json") or media_type in {
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.dev.sigstore.bundle.v0.3+json",
        }:
            document = load_jcs_object(payload, descriptor["digest"])
            if "trustPolicy" in document:
                require(
                    document["trustPolicy"] == descriptor["trustPolicy"],
                    "artifact_document_trust_policy_mismatch",
                    descriptor["digest"],
                )
            if contract is not None:
                require(document.get("contract") == contract, "artifact_contract_mismatch", descriptor["digest"])
            if schema_id is not None:
                validate_schema_instance(document, schema_id, self.registry, self.schemas)
            return document
        require(contract is None and schema_id is None, "artifact_contract_unresolved", descriptor["digest"])
        return payload


def validate_trust_policy_pin_set(
    document: Any,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    *,
    prior_pin_set: dict[str, Any] | None = None,
) -> TrustPolicyPinSet:
    require(isinstance(document, dict), "invalid_trust_policy_pin_set", "not an object")
    validate_schema_instance(
        document,
        TRUST_POLICY_PIN_SET_SCHEMA_ID,
        registry,
        schemas,
    )
    try:
        return TrustPolicyPinSet(
            document,
            expected_purposes=PRODUCT_TRUST_PURPOSES,
            expected_scope="product",
            expected_consumer_id=None,
            prior_pin_set=prior_pin_set,
        )
    except TrustPolicyPinError as error:
        raise RendererDigestError(error.code, str(error)) from error


def validate_trust_policy_pin_set_authority(
    catalog: dict[str, Any],
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> TrustPolicyPinSet:
    """Accept a pin set only after external provider activation/readback proof."""

    pin_set = catalog["trustPolicyPinSet"]
    descriptor = catalog["trustPolicyPinSetDescriptor"]
    evidence = catalog["trustPolicyPinSetProviderEvidence"]
    vectors = catalog["trustPolicyProviderAuthenticationVectors"]
    view = validate_trust_policy_pin_set(pin_set, registry, schemas)
    validate_plain_schema_instance(
        descriptor,
        TRUST_POLICY_PIN_SET_DESCRIPTOR_SCHEMA_ID,
        registry,
        schemas,
    )
    validate_schema_instance(
        evidence,
        TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID,
        registry,
        schemas,
    )
    expected_provider_authority_digest = canonical_digest(
        {
            "profile": "bytedesk.external-trust-policy-provider-anchor/1",
            "providerId": PRODUCT_TRUST_POLICY_PROVIDER_ID,
            "environment": "production",
        }
    )
    require(
        descriptor["providerId"] == PRODUCT_TRUST_POLICY_PROVIDER_ID
        and descriptor["providerAuthorityDigest"]
        == expected_provider_authority_digest,
        "trust_pin_provider_anchor_mismatch",
        descriptor.get("providerId", "unknown"),
    )
    pin_payload_path = (
        RENDERER_CAS_BLOB_ROOT
        / descriptor["digest"].removeprefix("sha256:")
    )
    require(
        pin_payload_path.is_file() and not pin_payload_path.is_symlink(),
        "trust_pin_provider_object_missing",
        descriptor["digest"],
    )
    pin_payload = pin_payload_path.read_bytes()
    require(
        raw_digest(pin_payload) == descriptor["digest"]
        and len(pin_payload) == descriptor["size"]
        and load_jcs_object(pin_payload, descriptor["digest"]) == pin_set,
        "trust_pin_provider_object_mismatch",
        descriptor["digest"],
    )
    try:
        adapter = TrustedTrustPolicyProviderAdapter(
            provider_id=PRODUCT_TRUST_POLICY_PROVIDER_ID,
            provider_authority_digest=expected_provider_authority_digest,
            authentication_vectors=vectors,
        )
        result = adapter.verify_activation(
            pin_set=pin_set,
            pin_set_descriptor_value=descriptor,
            evidence=evidence,
            verification_time="2026-07-17T12:00:04Z",
        )
    except TrustPolicyPinError as error:
        raise RendererDigestError(error.code, str(error)) from error
    require(
        result["decision"] == "active"
        and result["pinSet"] == descriptor
        and result["pinSetDigest"] == pin_set["pinSetDigest"]
        and result["providerAuthorityDigest"]
        == expected_provider_authority_digest
        and result["providerEvidenceDigest"] == evidence["evidenceDigest"]
        and timestamp(result["readbackAt"], "pin-provider:readbackAt")
        <= timestamp("2026-07-17T12:00:04Z", "pin-provider:verificationTime"),
        "trust_pin_provider_result_mismatch",
        pin_set["pinSetId"],
    )
    return view


def validate_trust_policy_pin_rotation(
    initial: dict[str, Any],
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> int:
    """Exercise CAS rotation, retirement, audit history, and revocation."""

    purpose = "public-render-v1"
    previous_reference = next(
        entry["trustPolicy"]
        for entry in initial["currentForNewUse"]
        if entry["purpose"] == purpose
    )
    current_reference = {
        "id": purpose,
        "digest": canonical_digest(
            {
                "profile": "bytedesk.rotated-trust-policy/1",
                "purpose": purpose,
                "revision": 2,
            }
        ),
    }
    rotated = deepcopy(initial)
    rotated["revision"] = 2
    rotated["precondition"] = {
        "kind": "match",
        "revision": initial["revision"],
        "digest": initial["pinSetDigest"],
    }
    for entry in rotated["currentForNewUse"]:
        if entry["purpose"] == purpose:
            entry["trustPolicy"] = deepcopy(current_reference)
    rotated["historicalVerification"] = [
        {
            "purpose": purpose,
            "trustPolicy": deepcopy(previous_reference),
            "validForSigning": {
                "notBefore": "2026-01-01T00:00:00Z",
                "notAfter": "2026-07-17T12:00:07Z",
            },
        }
    ]
    rotated["pinSetDigest"] = pin_set_digest(rotated)
    validate_schema_instance(rotated, TRUST_POLICY_PIN_SET_SCHEMA_ID, registry, schemas)
    try:
        rotated_view = TrustPolicyPinSet(
            rotated,
            expected_purposes=PRODUCT_TRUST_PURPOSES,
            expected_scope="product",
            expected_consumer_id=None,
            prior_pin_set=initial,
        )
    except TrustPolicyPinError as error:
        raise RendererDigestError(error.code, str(error)) from error

    provider_authority_digest = canonical_digest(
        {
            "profile": "bytedesk.external-trust-policy-provider-anchor/1",
            "providerId": PRODUCT_TRUST_POLICY_PROVIDER_ID,
            "environment": "production",
        }
    )
    descriptor = pin_set_document_descriptor(
        repository="registry.example/product/trust-policy-pin-sets",
        pin_set=rotated,
        provider_id=PRODUCT_TRUST_POLICY_PROVIDER_ID,
        provider_authority_digest=provider_authority_digest,
    )
    evidence = build_pin_set_provider_evidence(
        schema_descriptor={
            "id": TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID,
            "digest": canonical_digest(
                schemas[TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID]
            ),
        },
        evidence_id="product-pin-set-provider-evidence-r2",
        request_id="activate-product-pin-set-r2",
        idempotency_key="activate-product-pin-set-r2",
        pin_set=rotated,
        pin_set_descriptor=descriptor,
        provider_request_id="provider-request-product-pin-set-r2",
        provider_audit_id="provider-audit-product-pin-set-r2",
        activated_at="2026-07-17T12:00:08Z",
        observed_at="2026-07-17T12:00:09Z",
    )
    vector = pin_set_provider_authentication_vector(
        vector_id=canonical_digest(
            {
                "profile": "bytedesk.test-trust-policy-provider-vector-id/1",
                "providerRequestId": evidence["providerRequestId"],
                "requestDigest": evidence["requestDigest"],
                "pinSetDigest": rotated["pinSetDigest"],
            }
        ),
        provider_id=PRODUCT_TRUST_POLICY_PROVIDER_ID,
        provider_authority_digest=provider_authority_digest,
        provider_request_id=evidence["providerRequestId"],
        provider_audit_id=evidence["providerAuditId"],
        request_digest=evidence["requestDigest"],
        pin_set_digest_value=rotated["pinSetDigest"],
    )
    try:
        provider_result = TrustedTrustPolicyProviderAdapter(
            provider_id=PRODUCT_TRUST_POLICY_PROVIDER_ID,
            provider_authority_digest=provider_authority_digest,
            authentication_vectors=[vector],
        ).verify_activation(
            pin_set=rotated,
            pin_set_descriptor_value=descriptor,
            evidence=evidence,
            verification_time="2026-07-17T12:00:10Z",
        )
    except TrustPolicyPinError as error:
        raise RendererDigestError(error.code, str(error)) from error
    require(
        provider_result["decision"] == "active"
        and provider_result["pinSetDigest"] == rotated["pinSetDigest"],
        "trust_pin_rotation_provider_mismatch",
        purpose,
    )

    def authorize(view: TrustPolicyPinSet, **kwargs: Any) -> None:
        try:
            view.authorize_policy(**kwargs)
        except TrustPolicyPinError as error:
            raise RendererDigestError(error.code, str(error)) from error

    authorize(
        rotated_view,
        purpose=purpose,
        reference=current_reference,
        use="new",
        verification_time="2026-07-17T12:00:10Z",
    )
    authorize(
        rotated_view,
        purpose=purpose,
        reference=previous_reference,
        use="historical",
        signing_time="2026-07-17T12:00:06.999999Z",
        verification_time="2026-07-17T12:00:10Z",
    )
    require_semantic_denial(
        "trust_policy_not_pinned_at_signing_time",
        lambda: authorize(
            rotated_view,
            purpose=purpose,
            reference=previous_reference,
            use="historical",
            signing_time="2026-07-17T12:00:07Z",
            verification_time="2026-07-17T12:00:10Z",
        ),
        "historical signature exactly at validForSigning.notAfter",
    )
    require_semantic_denial(
        "trust_policy_retired_for_new_use",
        lambda: authorize(
            rotated_view,
            purpose=purpose,
            reference=previous_reference,
            use="new",
            verification_time="2026-07-17T12:00:10Z",
        ),
        "retired policy used for a new operation",
    )

    wrong_predecessor = deepcopy(rotated)
    wrong_predecessor["precondition"]["digest"] = current_reference["digest"]
    wrong_predecessor["pinSetDigest"] = pin_set_digest(wrong_predecessor)

    def construct_wrong_predecessor() -> None:
        try:
            TrustPolicyPinSet(
                wrong_predecessor,
                expected_purposes=PRODUCT_TRUST_PURPOSES,
                expected_scope="product",
                expected_consumer_id=None,
                prior_pin_set=initial,
            )
        except TrustPolicyPinError as error:
            raise RendererDigestError(error.code, str(error)) from error

    require_semantic_denial(
        "trust_pin_set_precondition_mismatch",
        construct_wrong_predecessor,
        "rotation with a substituted CAS predecessor",
    )

    revoked = deepcopy(rotated)
    revoked["revision"] = 3
    revoked["precondition"] = {
        "kind": "match",
        "revision": rotated["revision"],
        "digest": rotated["pinSetDigest"],
    }
    revoked["revocations"]["policyDigests"] = [previous_reference["digest"]]
    revoked["pinSetDigest"] = pin_set_digest(revoked)
    try:
        revoked_view = TrustPolicyPinSet(
            revoked,
            expected_purposes=PRODUCT_TRUST_PURPOSES,
            expected_scope="product",
            expected_consumer_id=None,
            prior_pin_set=rotated,
        )
    except TrustPolicyPinError as error:
        raise RendererDigestError(error.code, str(error)) from error
    require_semantic_denial(
        "trust_policy_pin_revoked",
        lambda: authorize(
            revoked_view,
            purpose=purpose,
            reference=previous_reference,
            use="historical",
            signing_time="2026-07-17T12:00:06.999999Z",
            verification_time="2026-07-17T12:00:10Z",
        ),
        "revoked historical policy used for audit verification",
    )
    authorize(
        rotated_view,
        purpose=purpose,
        reference=current_reference,
        use="new",
        verification_time="2026-12-31T23:59:59.999999Z",
    )
    require_semantic_denial(
        "trust_pin_set_not_effective",
        lambda: authorize(
            rotated_view,
            purpose=purpose,
            reference=current_reference,
            use="new",
            verification_time=rotated["effective"]["notAfter"],
        ),
        "new use exactly at pin-set expiry",
    )
    require_semantic_denial(
        "trust_pin_set_not_effective",
        lambda: authorize(
            rotated_view,
            purpose=purpose,
            reference=current_reference,
            use="new",
            verification_time="2027-01-01T00:00:01Z",
        ),
        "new use one second after pin-set expiry",
    )

    def reject_invalid_window(candidate: dict[str, Any]) -> None:
        try:
            TrustPolicyPinSet(
                candidate,
                expected_purposes=PRODUCT_TRUST_PURPOSES,
                expected_scope="product",
                expected_consumer_id=None,
                prior_pin_set=initial,
            )
        except TrustPolicyPinError as error:
            raise RendererDigestError(error.code, str(error)) from error

    zero_effective = deepcopy(rotated)
    zero_effective["effective"]["notAfter"] = zero_effective["effective"][
        "notBefore"
    ]
    zero_effective["pinSetDigest"] = pin_set_digest(zero_effective)
    require_semantic_denial(
        "trust_pin_set_effective_invalid",
        lambda: reject_invalid_window(zero_effective),
        "zero-length pin-set effective window",
    )
    zero_history = deepcopy(rotated)
    zero_history["historicalVerification"][0]["validForSigning"]["notAfter"] = (
        zero_history["historicalVerification"][0]["validForSigning"][
            "notBefore"
        ]
    )
    zero_history["pinSetDigest"] = pin_set_digest(zero_history)
    require_semantic_denial(
        "trust_pin_set_history_invalid",
        lambda: reject_invalid_window(zero_history),
        "zero-length historical signing window",
    )
    return 11


def domain_digest(
    profile: str,
    document: dict[str, Any],
    excluded: set[str],
) -> str:
    return canonical_digest(
        {
            "profile": profile,
            **{
                key: deepcopy(value)
                for key, value in document.items()
                if key not in excluded
            },
        }
    )


def validate_signing_result(
    result: dict[str, Any],
    *,
    purpose: str,
    subject_digest: str,
    subject_media_type: str,
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    verification_time: datetime | str,
    policy_use: str = "new",
) -> None:
    validate_schema_instance(
        result,
        SIGNING_RESULT_SCHEMA_ID,
        registry,
        schemas,
    )
    require(result["purpose"] == purpose, "signing_purpose_mismatch", purpose)
    require(result["subjectDigest"] == subject_digest, "signing_subject_mismatch", purpose)
    require(
        result["subjectMediaType"] == subject_media_type,
        "signing_subject_media_mismatch",
        purpose,
    )
    require(
        result["signatureBundle"]["repository"] == result["repository"]
        and result["signatureBundle"]["trustPolicy"] == result["trustPolicy"],
        "signing_bundle_descriptor_mismatch",
        purpose,
    )
    if isinstance(verification_time, datetime):
        verification_time_value = verification_time.astimezone(timezone.utc).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
    else:
        verification_time_value = verification_time
    policy = resolver.trust_policy(
        result["trustPolicy"],
        result["repository"],
        result["subjectMediaType"],
        policy_use=policy_use,
        verification_time=verification_time_value,
        signing_time=result["signedAt"],
    )
    try:
        permitted_signer = exact_policy_signer(
            policy,
            purpose=purpose,
            subject_media_type=subject_media_type,
            key_version=result["keyVersion"],
            algorithm=result["algorithm"],
            public_key_digest=result["publicKeyDigest"],
        )
    except ValueError as error:
        raise RendererDigestError("signer_not_permitted", purpose) from error
    validate_signing_time_window(
        not_before=policy["effective"]["notBefore"],
        not_after=policy["effective"]["notAfter"],
        signed_at=result["signedAt"],
        verification_time=verification_time_value,
        identity=purpose,
    )
    expected_request_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-signing-request/1",
            "requestId": result["requestId"],
            "purpose": purpose,
            "subjectDigest": subject_digest,
            "subjectMediaType": subject_media_type,
            "algorithm": result["algorithm"],
            "keyVersion": result["keyVersion"],
            "publicKeyDigest": result["publicKeyDigest"],
            "repository": result["repository"],
            "trustPolicy": result["trustPolicy"],
        }
    )
    require(
        result["requestDigest"] == expected_request_digest,
        "signing_request_digest_mismatch",
        purpose,
    )
    provider_evidence = resolver.artifact(
        result["providerAuditEvidence"],
        media_type=SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        contract="bytedesk.signer-authentication-evidence/1",
        schema_id=SIGNER_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
    )
    require(
        isinstance(provider_evidence, dict)
        and provider_evidence["purpose"] == purpose
        and provider_evidence["requestId"] == result["requestId"]
        and provider_evidence["requestDigest"] == expected_request_digest
        and provider_evidence["keyVersion"] == result["keyVersion"]
        and provider_evidence["algorithm"] == result["algorithm"]
        and provider_evidence["publicKeyDigest"] == result["publicKeyDigest"]
        and provider_evidence["authenticatedSigner"] == permitted_signer
        and provider_evidence["trustPolicy"] == result["trustPolicy"]
        and provider_evidence["issuedAt"] == result["signedAt"],
        "provider_signer_identity_mismatch",
        purpose,
    )
    bundle = resolver.artifact(
        result["signatureBundle"],
        media_type="application/vnd.dev.sigstore.bundle.v0.3+json",
    )
    require(isinstance(bundle, dict), "signing_bundle_invalid", purpose)
    expected_statement = {
        "profile": "bytedesk.renderer-authenticated-signature-statement/1",
        "requestId": result["requestId"],
        "requestDigest": expected_request_digest,
        "purpose": result["purpose"],
        "subjectDigest": result["subjectDigest"],
        "subjectMediaType": result["subjectMediaType"],
        "algorithm": result["algorithm"],
        "keyVersion": result["keyVersion"],
        "publicKeyDigest": result["publicKeyDigest"],
        "repository": result["repository"],
        "trustPolicy": result["trustPolicy"],
        "providerAuditEvidence": result["providerAuditEvidence"],
        "authenticatedSigner": permitted_signer,
        "signedAt": result["signedAt"],
    }
    require(
        bundle
        == {
            "profile": "bytedesk.test-only-kms-adapter-bundle/1",
            "statement": expected_statement,
            "fixtureStatementChecksum": canonical_digest(
                {
                    "profile": "bytedesk.test-only-kms-statement-checksum/1",
                    "statement": expected_statement,
                }
            ),
        },
        "signing_bundle_payload_mismatch",
        purpose,
    )
    try:
        verification_result = resolver.signature_verifier.verify(
            result=result,
            policy=policy,
            permitted_signer=permitted_signer,
            verification_time=verification_time_value,
            expected_purpose=purpose,
            expected_subject_media_type=subject_media_type,
            expected_signing_repository=result["repository"],
            pin_set_digest=resolver.trust_policy_pin_set.digest,
            pin_set_revocations=resolver.trust_policy_pin_set.revocations,
            expected_consumer_id=resolver.trust_policy_pin_set.consumer_id,
        )
    except TrustedKmsVerificationError as error:
        raise RendererDigestError(error.code, str(error)) from error
    require(
        set(verification_result)
        == {
            "decision",
            "vectorId",
            "requestDigest",
            "signatureBundleDigest",
            "subjectDigest",
            "purpose",
            "subjectMediaType",
            "signingRepository",
            "verificationTime",
            "evaluatedPolicyDigest",
            "pinSetDigest",
            "consumerId",
            "authenticatedSigner",
            "providerAuditEvidence",
            "providerAuditEvidenceDigest",
            "verificationEvidenceDigest",
        }
        and verification_result["decision"] == "permitted"
        and isinstance(verification_result["vectorId"], str)
        and verification_result["requestDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.kms-signature-verification-request/1",
                "purpose": purpose,
                "subjectDigest": subject_digest,
                "subjectMediaType": subject_media_type,
                "signatureBundle": result["signatureBundle"],
                "signingRepository": result["repository"],
                "trustPolicy": result["trustPolicy"],
                "pinSetDigest": resolver.trust_policy_pin_set.digest,
                "consumerId": resolver.trust_policy_pin_set.consumer_id,
                "providerAuditEvidence": result["providerAuditEvidence"],
                "verificationTime": verification_time_value,
            }
        )
        and verification_result["signatureBundleDigest"]
        == result["signatureBundle"]["digest"]
        and verification_result["subjectDigest"] == subject_digest
        and verification_result["purpose"] == purpose
        and verification_result["subjectMediaType"] == subject_media_type
        and verification_result["signingRepository"] == result["repository"]
        and verification_result["verificationTime"] == verification_time_value
        and verification_result["evaluatedPolicyDigest"]
        == result["trustPolicy"]["digest"]
        and verification_result["pinSetDigest"]
        == resolver.trust_policy_pin_set.digest
        and verification_result["consumerId"]
        == resolver.trust_policy_pin_set.consumer_id
        and verification_result["authenticatedSigner"] == permitted_signer
        and verification_result["providerAuditEvidence"]
        == result["providerAuditEvidence"]
        and verification_result["providerAuditEvidenceDigest"]
        == result["providerAuditEvidence"]["digest"]
        and verification_result["verificationEvidenceDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.kms-signature-verification-evidence/1",
                **{
                    key: deepcopy(value)
                    for key, value in verification_result.items()
                    if key != "verificationEvidenceDigest"
                },
            }
        ),
        "kms_verification_result_mismatch",
        purpose,
    )


def validate_standalone_signing_projections(
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> int:
    signing_result = load_json(PUBLIC_RENDER_SIGNING_RESULT_PATH)
    require(
        set(signing_result["providerAuditEvidence"])
        == {"repository", "digest", "mediaType", "size", "trustPolicy"},
        "provider_audit_descriptor_incomplete",
        PUBLIC_RENDER_SIGNING_RESULT_PATH.name,
    )
    validate_signing_result(
        signing_result,
        purpose="public-render-v1",
        subject_digest=signing_result["subjectDigest"],
        subject_media_type=signing_result["subjectMediaType"],
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=signing_result["signedAt"],
    )

    product_release = load_json(PRODUCT_RELEASE_PATH)
    product_signer_evidence = resolver.artifact(
        product_release["signingResult"]["providerAuditEvidence"],
        media_type=SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        contract="bytedesk.signer-authentication-evidence/1",
        schema_id=SIGNER_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
    )
    signer_authentication_evidence = load_json(
        PRODUCT_RELEASE_SIGNER_AUTHENTICATION_EVIDENCE_PATH
    )
    validate_schema_instance(
        signer_authentication_evidence,
        SIGNER_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        signer_authentication_evidence == product_signer_evidence,
        "signer_authentication_projection_mismatch",
        "product-release-v1",
    )
    signer_identity = load_json(PRODUCT_RELEASE_SIGNER_IDENTITY_PATH)
    validate_plain_schema_instance(
        signer_identity,
        SIGNER_IDENTITY_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        signer_identity
        == signer_authentication_evidence["authenticatedSigner"],
        "signer_identity_projection_mismatch",
        "product-release-v1",
    )
    return 3


def validate_indexed_provider_audit_projections(
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> int:
    public_source = load_json(PUBLIC_SOURCE_AUTHENTICATION_PATH)
    validate_schema_instance(
        public_source,
        PUBLIC_SOURCE_AUTH_SCHEMA_ID,
        registry,
        schemas,
    )
    release_status_append = load_json(RELEASE_STATUS_APPEND_RESOLUTION_PATH)
    validate_schema_instance(
        release_status_append,
        RELEASE_STATUS_APPEND_RESOLUTION_SCHEMA_ID,
        registry,
        schemas,
    )

    private_subject = load_json(
        PRIVATE_SUBJECT_PUBLIC_SOURCE_AUTHENTICATION_PATH
    )
    private_subject_errors = list(
        Draft202012Validator(
            schemas[PUBLIC_SOURCE_AUTH_SCHEMA_ID],
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(private_subject)
    )
    require(
        len(private_subject_errors) == 1
        and private_subject_errors[0].validator == "const"
        and list(private_subject_errors[0].absolute_path)
        == ["subject", "trustPolicy", "id"],
        "private_subject_denial_scope_mismatch",
        "expected only subject.trustPolicy.id to violate public-source-v1",
    )

    indexed_documents = {
        PUBLIC_RENDER_SIGNING_RESULT_PATH: load_json(
            PUBLIC_RENDER_SIGNING_RESULT_PATH
        ),
        PUBLIC_SOURCE_AUTHENTICATION_PATH: public_source,
        PRIVATE_SUBJECT_PUBLIC_SOURCE_AUTHENTICATION_PATH: private_subject,
        RELEASE_STATUS_APPEND_RESOLUTION_PATH: release_status_append,
    }

    def retains_obsolete_classification(value: Any) -> bool:
        if isinstance(value, dict):
            provider_audit_evidence = value.get("providerAuditEvidence")
            return (
                isinstance(provider_audit_evidence, dict)
                and "classification" in provider_audit_evidence
            ) or any(
                retains_obsolete_classification(child)
                for child in value.values()
            )
        if isinstance(value, list):
            return any(
                retains_obsolete_classification(child) for child in value
            )
        return False

    obsolete_paths = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path, document in indexed_documents.items()
        if retains_obsolete_classification(document)
    ]
    require(
        not obsolete_paths,
        "obsolete_provider_audit_classification",
        ", ".join(obsolete_paths),
    )
    return len(indexed_documents)


def validate_inline_authority(
    document: dict[str, Any],
    *,
    schema_id: str,
    purpose: str,
    subject_media_type: str,
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    verification_time: datetime | str,
) -> None:
    require(
        document["trustPolicy"] == document["signingResult"]["trustPolicy"],
        "inline_authority_trust_policy_mismatch",
        purpose,
    )
    require(
        document["authorityDigest"]
        == canonical_digest(inline_authority_preimage(document, schemas[schema_id])),
        "inline_authority_digest_mismatch",
        purpose,
    )
    validate_signing_result(
        document["signingResult"],
        purpose=purpose,
        subject_digest=document["authorityDigest"],
        subject_media_type=subject_media_type,
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=verification_time,
    )


def validate_kms_context_denials(
    *,
    result: dict[str, Any],
    resolver: RendererCasResolver,
    verification_time: str,
) -> int:
    purpose = result["purpose"]
    policy = resolver.trust_policy(
        result["trustPolicy"],
        result["repository"],
        result["subjectMediaType"],
        verification_time=verification_time,
        signing_time=result["signedAt"],
    )
    permitted_signer = exact_policy_signer(
        policy,
        purpose=purpose,
        subject_media_type=result["subjectMediaType"],
        key_version=result["keyVersion"],
        algorithm=result["algorithm"],
        public_key_digest=result["publicKeyDigest"],
    )
    base = {
        "result": result,
        "policy": policy,
        "permitted_signer": permitted_signer,
        "verification_time": verification_time,
        "expected_purpose": purpose,
        "expected_subject_media_type": result["subjectMediaType"],
        "expected_signing_repository": result["repository"],
        "pin_set_digest": resolver.trust_policy_pin_set.digest,
        "pin_set_revocations": resolver.trust_policy_pin_set.revocations,
        "expected_consumer_id": resolver.trust_policy_pin_set.consumer_id,
    }
    forged_key = deepcopy(result)
    forged_key["keyVersion"] = f"{result['keyVersion']}-forged"
    forged_provider = deepcopy(result)
    forged_provider["providerAuditEvidence"] = {
        **forged_provider["providerAuditEvidence"],
        "digest": "sha256:" + ("ee" * 32),
    }
    cases: list[tuple[str, dict[str, Any], str]] = [
        (
            "kms_expected_purpose_mismatch",
            {**base, "expected_purpose": "public-source-v1"},
            "wrong expected purpose",
        ),
        (
            "kms_expected_subject_media_type_mismatch",
            {
                **base,
                "expected_subject_media_type": (
                    "application/vnd.bytedesk.agent.source.v1+json"
                ),
            },
            "wrong signed media type",
        ),
        (
            "kms_expected_signing_repository_mismatch",
            {
                **base,
                "expected_signing_repository": "registry.example/attacker",
            },
            "wrong signing repository",
        ),
        (
            "kms_signature_not_verified",
            {**base, "pin_set_digest": "sha256:" + ("dd" * 32)},
            "wrong product pin set",
        ),
        (
            "kms_signature_not_verified",
            {**base, "expected_consumer_id": "consumer-attacker"},
            "product signature replayed in consumer context",
        ),
        (
            "kms_signature_not_verified",
            {**base, "result": forged_key},
            "forged current key version",
        ),
        (
            "kms_signature_not_verified",
            {**base, "result": forged_provider},
            "forged provider audit evidence",
        ),
    ]
    for expected_code, arguments, identity in cases:
        try:
            resolver.signature_verifier.verify(**arguments)
        except TrustedKmsVerificationError as error:
            require(
                error.code == expected_code,
                "wrong_kms_context_denial",
                f"{identity}: expected {expected_code}, observed {error.code}",
            )
        else:
            raise RendererDigestError(
                "kms_context_substitution_accepted",
                identity,
            )
    return len(cases)


def validate_contract_bundle_kms_denials() -> int:
    """Prove both contract-bundle representations remain keyless-only.

    Expected and observed contexts agree exactly.  Media-only probes retain a
    normal KMS purpose, while a separate purpose-only probe uses non-bundle
    media.  Deliberately unusable policy/signer inputs prove both boundaries
    reject before KMS signer or trust-policy selection.
    """

    import generate_renderer_digest_fixtures as fixture_generator

    require(
        PRODUCT_TRUST_PURPOSES == fixture_generator.PRODUCT_TRUST_PURPOSES
        and PRODUCT_KMS_SIGNING_PURPOSES
        == fixture_generator.PRODUCT_KMS_SIGNING_PURPOSES
        and CONTRACT_BUNDLE_RELEASE_PURPOSE in PRODUCT_TRUST_PURPOSES
        and CONTRACT_BUNDLE_RELEASE_PURPOSE not in PRODUCT_KMS_SIGNING_PURPOSES,
        "kms_contract_bundle_purpose_partition_invalid",
        CONTRACT_BUNDLE_RELEASE_PURPOSE,
    )
    adapter = TrustedKmsVerificationAdapter([])

    def matching_result(purpose: str, media_type: str) -> dict[str, Any]:
        trust_policy = {
            "id": purpose,
            "digest": "sha256:" + ("22" * 32),
        }
        return {
            "requestId": (
                f"contract-bundle-{purpose}-{media_type.rsplit('+', 1)[-1]}"
            ),
            "purpose": purpose,
            "signatureBundle": {
                "repository": "registry.example/product/contracts",
                "digest": "sha256:" + ("11" * 32),
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "size": 1,
                "trustPolicy": deepcopy(trust_policy),
            },
            "subjectDigest": "sha256:" + ("33" * 32),
            "subjectMediaType": media_type,
            "keyVersion": "kms://must-not-be-selected/versions/1",
            "publicKeyDigest": "sha256:" + ("44" * 32),
            "algorithm": "ECDSA_P256_SHA256",
            "trustPolicy": deepcopy(trust_policy),
            "repository": "registry.example/product/contracts",
            "providerAuditEvidence": {
                "repository": "registry.example/product/contracts",
                "digest": "sha256:" + ("55" * 32),
                "mediaType": SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
                "size": 1,
                "trustPolicy": deepcopy(trust_policy),
            },
        }

    def expect_adapter_denial(purpose: str, media_type: str) -> None:
        result = matching_result(purpose, media_type)
        try:
            adapter.verify(
                result=result,
                policy={},
                permitted_signer={},
                verification_time="2026-07-17T12:00:00Z",
                expected_purpose=purpose,
                expected_subject_media_type=media_type,
                expected_signing_repository=result["repository"],
                pin_set_digest="sha256:" + ("66" * 32),
                pin_set_revocations={
                    "policyDigests": [],
                    "keyVersions": [],
                    "publicKeyDigests": [],
                },
                expected_consumer_id=None,
            )
        except TrustedKmsVerificationError as error:
            require(
                error.code == "kms_contract_bundle_keyless_only",
                "wrong_kms_contract_bundle_denial",
                f"Adapter {purpose}:{media_type}: {error.code}",
            )
        else:
            raise RendererDigestError(
                "kms_contract_bundle_accepted",
                f"Adapter {purpose}:{media_type}",
            )

    def expect_generator_denial(purpose: str, media_type: str) -> None:
        result = matching_result(purpose, media_type)
        previous_pin_set = fixture_generator.ACTIVE_TRUST_POLICY_PIN_SET
        fixture_generator.ACTIVE_TRUST_POLICY_PIN_SET = None
        try:
            try:
                fixture_generator.renderer_signing_result(
                    {},
                    purpose,
                    result["subjectDigest"],
                    media_type,
                    "must-not-select-kms-signer",
                    result["trustPolicy"],
                    result["repository"],
                )
            except fixture_generator.GenerationError as error:
                require(
                    str(error)
                    == "KMS signing cannot sign contract-bundle authority",
                    "wrong_kms_contract_bundle_denial",
                    f"renderer generator {purpose}:{media_type}: {error}",
                )
            else:
                raise RendererDigestError(
                    "kms_contract_bundle_accepted",
                    f"renderer generator {purpose}:{media_type}",
                )
        finally:
            fixture_generator.ACTIVE_TRUST_POLICY_PIN_SET = previous_pin_set

    def expect_authority_helper_denials(purpose: str, media_type: str) -> None:
        try:
            exact_policy_signer(
                {},
                purpose=purpose,
                subject_media_type=media_type,
                key_version="kms://must-not-be-selected/versions/1",
                algorithm="ECDSA_P256_SHA256",
                public_key_digest="sha256:" + ("44" * 32),
            )
        except ValueError as error:
            require(
                str(error) == "KMS signing cannot sign contract-bundle authority",
                "wrong_kms_contract_bundle_denial",
                f"signer selector {purpose}:{media_type}: {error}",
            )
        else:
            raise RendererDigestError(
                "kms_contract_bundle_accepted",
                f"signer selector {purpose}:{media_type}",
            )

        try:
            build_signer_authentication_evidence(
                schema_descriptor={},
                purpose=purpose,
                subject_media_type=media_type,
                request_id="must-not-build-provider-evidence",
                request_digest="sha256:" + ("11" * 32),
                provider_request_id="must-not-contact-provider",
                provider_audit_id="must-not-write-provider-audit",
                authenticated_signer={},
                issued_at="2026-07-17T12:00:00Z",
                trust_policy={},
            )
        except ValueError as error:
            require(
                str(error) == "KMS signing cannot sign contract-bundle authority",
                "wrong_kms_contract_bundle_denial",
                f"provider evidence builder {purpose}:{media_type}: {error}",
            )
        else:
            raise RendererDigestError(
                "kms_contract_bundle_accepted",
                f"provider evidence builder {purpose}:{media_type}",
            )

    probes = [
        ("product-release-v1", media_type)
        for media_type in sorted(CONTRACT_BUNDLE_MEDIA_TYPES)
    ]
    probes.append(
        (
            CONTRACT_BUNDLE_RELEASE_PURPOSE,
            "application/vnd.oci.image.manifest.v1+json",
        )
    )
    for purpose, media_type in probes:
        expect_adapter_denial(purpose, media_type)
        expect_generator_denial(purpose, media_type)
        expect_authority_helper_denials(purpose, media_type)
    return len(probes) * 4


def validate_keyless_adapter_contract() -> int:
    """Prove the independent keyless Adapter binds the complete release edge."""

    repository = "registry.example/product/contracts"
    purpose = CONTRACT_BUNDLE_RELEASE_PURPOSE
    media_type = "application/vnd.bytedesk.agent.contract-bundle.v1+json"
    verified_at = "2026-07-17T12:00:02Z"
    signer = {
        "purpose": purpose,
        "credentialKind": "sigstore_keyless",
        "trustedRootDigest": canonical_digest(
            {"profile": "bytedesk.test-sigstore-trusted-root/1"}
        ),
        "algorithm": "ECDSA_P256_SHA256",
        "workloadIdentity": (
            "https://github.com/ByteDeskAI/bytedesk-agent-delivery/"
            ".github/workflows/contract-release-signer.yml@"
            "1111111111111111111111111111111111111111"
        ),
        "claims": {
            "issuer": "https://token.actions.githubusercontent.com",
            "audience": "sigstore",
            "subject": (
                "repo:ByteDeskAI/bytedesk-agent-delivery:environment:"
                "contract-release"
            ),
            "repository": "ByteDeskAI/bytedesk-agent-delivery",
            "workflow": (
                ".github/workflows/contract-release-signer.yml@"
                "1111111111111111111111111111111111111111"
            ),
            "ref": "refs/tags/v1.0.0",
            "environment": "contract-release",
            "builderDigest": canonical_digest(
                {"profile": "bytedesk.test-contract-release-sealed-builder/1"}
            ),
        },
    }
    policy = {
        "contract": "bytedesk.trust-policy/1",
        "schema": {
            "id": TRUST_POLICY_SCHEMA_ID,
            "digest": "sha256:" + ("10" * 32),
        },
        "policyId": purpose,
        "version": "1.0.0",
        "predecessor": {"kind": "none"},
        "scope": {
            "repositories": [repository],
            "mediaTypes": [media_type],
            "purposes": [purpose],
        },
        "signers": [deepcopy(signer)],
        "requiredEvidence": [
            "schema",
            "provenance",
            "sbom",
            "vulnerability",
            "license",
            "compatibility",
            "conformance",
            "determinism",
            "malware",
            "secret_scan",
            "executed_distribution",
            "scan_completeness",
        ],
        "effective": {
            "notBefore": "2026-07-17T00:00:00Z",
            "notAfter": "2027-07-17T00:00:00Z",
        },
        "revocations": {
            "keyVersions": [],
            "digests": [],
            "workflows": [],
            "builders": [],
            "schemas": [],
            "renderers": [],
            "content": [],
        },
        "rules": {
            "requireNonce": True,
            "requirePredecessor": True,
            "denyDowngrade": True,
            "freshnessSeconds": 900,
            "outage": "fail_closed_new_work",
            "withdrawal": "deny_new_use",
        },
        "failureMode": "fail_closed",
    }
    policy_bytes = rfc8785.dumps(policy)
    trust_policy = {"id": purpose, "digest": raw_digest(policy_bytes)}
    subject_bytes = rfc8785.dumps(
        {
            "contract": "bytedesk.contract-bundle/1",
            "fixture": "keyless-adapter-contract",
            "trustPolicy": trust_policy,
        }
    )
    subject = {
        "repository": repository,
        "digest": raw_digest(subject_bytes),
        "mediaType": media_type,
        "size": len(subject_bytes),
        "trustPolicy": deepcopy(trust_policy),
    }
    signer_digest = signer_identity_digest(signer)
    certification_digest = canonical_digest(
        {
            "profile": "bytedesk.test-contract-bundle-pre-sign-certification/1",
            "subject": subject,
            "builderDigest": signer["claims"]["builderDigest"],
        }
    )
    signing_request = {
        "contract": "bytedesk.signing-request/1",
        "schema": {
            "id": (
                "https://schemas.bytedesk.ai/agent-delivery/v1/"
                "signing-request/1.0.0"
            ),
            "digest": "sha256:" + ("20" * 32),
        },
        "requestId": "contract-bundle-keyless-adapter-01",
        "purpose": purpose,
        "credentialKind": "sigstore_keyless",
        "signerIdentityDigest": signer_digest,
        "builderDigest": signer["claims"]["builderDigest"],
        "preSignCertificationDigest": certification_digest,
        "repository": repository,
        "digest": subject["digest"],
        "mediaType": media_type,
        "trustPolicy": deepcopy(trust_policy),
        "nonce": "nonce_contract_bundle_adapter_0123456789abcdef",
        "issuedAt": "2026-07-17T12:00:00Z",
        "expiresAt": "2026-07-17T12:05:00Z",
    }
    signing_request_bytes = rfc8785.dumps(signing_request)
    signing_request_descriptor = {
        "repository": repository,
        "digest": raw_digest(signing_request_bytes),
        "mediaType": SIGNING_REQUEST_MEDIA_TYPE,
        "size": len(signing_request_bytes),
    }
    signature_bundle_bytes = rfc8785.dumps(
        {
            "profile": "bytedesk.test-only-keyless-adapter-bundle/1",
            "requestDigest": signing_request_descriptor["digest"],
            "subjectDigest": subject["digest"],
            "signerIdentityDigest": signer_digest,
        }
    )
    signature_bundle = {
        "repository": repository,
        "digest": raw_digest(signature_bundle_bytes),
        "mediaType": SIGSTORE_BUNDLE_MEDIA_TYPE,
        "size": len(signature_bundle_bytes),
    }
    vector_id = canonical_digest(
        {
            "profile": "bytedesk.test-keyless-verification-vector-id/1",
            "subject": subject,
            "signingRequest": signing_request_descriptor,
            "signatureBundle": signature_bundle,
            "signerIdentityDigest": signer_digest,
            "verifiedAt": verified_at,
        }
    )
    vector = keyless_signature_verification_vector(
        vector_id=vector_id,
        subject=subject,
        purpose=purpose,
        signer_identity_digest_value=signer_digest,
        trusted_root_digest=signer["trustedRootDigest"],
        authenticated_signer=signer,
        builder_digest=signer["claims"]["builderDigest"],
        pre_sign_certification_digest=certification_digest,
        signing_request=signing_request_descriptor,
        signing_request_digest=signing_request_descriptor["digest"],
        signature_bundle=signature_bundle,
        signature_bundle_digest=signature_bundle["digest"],
        trust_policy=trust_policy,
        verified_at=verified_at,
    )
    adapter = TrustedKeylessVerificationAdapter([vector])
    base = {
        "subject": subject,
        "subject_bytes": subject_bytes,
        "policy": policy,
        "policy_bytes": policy_bytes,
        "permitted_signer": signer,
        "signing_request": signing_request,
        "signing_request_bytes": signing_request_bytes,
        "signing_request_descriptor": signing_request_descriptor,
        "signature_bundle_bytes": signature_bundle_bytes,
        "signature_bundle_descriptor": signature_bundle,
        "verification_time": verified_at,
        "expected_purpose": purpose,
        "expected_subject_repository": repository,
        "expected_subject_digest": subject["digest"],
        "expected_subject_media_type": media_type,
        "expected_trust_policy": trust_policy,
        "expected_signer_identity_digest": signer_digest,
        "expected_trusted_root_digest": signer["trustedRootDigest"],
        "expected_workflow": signer["claims"]["workflow"],
        "expected_workload_identity": signer["workloadIdentity"],
        "expected_claims": signer["claims"],
        "expected_builder_digest": signer["claims"]["builderDigest"],
        "expected_pre_sign_certification_digest": certification_digest,
        "expected_signing_request_digest": signing_request_descriptor["digest"],
        "expected_signature_bundle_digest": signature_bundle["digest"],
    }
    receipt = adapter.verify(**base)
    require(
        receipt["profile"] == KEYLESS_VERIFICATION_PROFILE
        and receipt["decision"] == "permitted"
        and receipt["authorityIssued"] is False
        and receipt["subject"] == subject
        and receipt["authenticatedSigner"] == signer
        and receipt["signingRequest"] == signing_request_descriptor
        and receipt["signatureBundle"] == signature_bundle
        and receipt["verificationEvidenceDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.keyless-signature-verification-evidence/1",
                **{
                    key: deepcopy(value)
                    for key, value in receipt.items()
                    if key != "verificationEvidenceDigest"
                },
            }
        ),
        "keyless_verification_receipt_mismatch",
        vector_id,
    )

    kms_request = deepcopy(signing_request)
    kms_request["credentialKind"] = "kms_key"
    kms_signer = deepcopy(signer)
    kms_signer["credentialKind"] = "kms_key"
    kms_signer["keyVersion"] = "kms://must-not-verify/versions/1"
    kms_signer["publicKeyDigest"] = "sha256:" + ("30" * 32)
    kms_signer.pop("trustedRootDigest")
    cases: list[tuple[str, TrustedKeylessVerificationAdapter, dict[str, Any], str]] = [
        (
            "keyless_purpose_mismatch",
            adapter,
            {**base, "expected_purpose": "product-release-v1"},
            "wrong purpose",
        ),
        (
            "keyless_credential_required",
            adapter,
            {**base, "signing_request": kms_request},
            "KMS request credential",
        ),
        (
            "keyless_signer_invalid",
            adapter,
            {**base, "permitted_signer": kms_signer},
            "KMS signer identity",
        ),
        (
            "keyless_trusted_root_mismatch",
            adapter,
            {**base, "expected_trusted_root_digest": "sha256:" + ("40" * 32)},
            "wrong trusted root",
        ),
        (
            "keyless_workflow_mismatch",
            adapter,
            {**base, "expected_workflow": ".github/workflows/attacker.yml"},
            "wrong workflow",
        ),
        (
            "keyless_workload_identity_mismatch",
            adapter,
            {**base, "expected_workload_identity": "https://attacker.invalid"},
            "wrong workload identity",
        ),
        (
            "keyless_claims_mismatch",
            adapter,
            {
                **base,
                "expected_claims": {
                    **signer["claims"],
                    "subject": "repo:attacker/example:environment:contract-release",
                },
            },
            "wrong certificate claims",
        ),
        (
            "keyless_builder_mismatch",
            adapter,
            {**base, "expected_builder_digest": "sha256:" + ("50" * 32)},
            "wrong builder",
        ),
        (
            "keyless_pre_sign_certification_mismatch",
            adapter,
            {
                **base,
                "expected_pre_sign_certification_digest": "sha256:" + ("60" * 32),
            },
            "wrong pre-sign certification",
        ),
        (
            "keyless_signature_bundle_digest_mismatch",
            adapter,
            {**base, "signature_bundle_bytes": signature_bundle_bytes + b"\n"},
            "changed Sigstore bundle bytes",
        ),
        (
            "keyless_subject_repository_mismatch",
            adapter,
            {**base, "expected_subject_repository": "registry.example/attacker"},
            "wrong subject repository",
        ),
        (
            "keyless_subject_media_type_mismatch",
            adapter,
            {
                **base,
                "expected_subject_media_type": (
                    "application/vnd.bytedesk.agent.contract-bundle.v1+tar"
                ),
            },
            "wrong subject media type",
        ),
        (
            "keyless_signature_not_verified",
            TrustedKeylessVerificationAdapter([]),
            base,
            "missing trusted verification vector",
        ),
    ]
    for expected_code, selected_adapter, arguments, identity in cases:
        try:
            selected_adapter.verify(**arguments)
        except TrustedKeylessVerificationError as error:
            require(
                error.code == expected_code,
                "wrong_keyless_context_denial",
                f"{identity}: expected {expected_code}, observed {error.code}",
            )
        else:
            raise RendererDigestError(
                "keyless_context_substitution_accepted",
                identity,
            )
    try:
        require_contract_bundle_verification_receipt(
            None,
            "product release without independent keyless verification",
        )
    except RendererDigestError as error:
        require(
            error.code == "contract_bundle_keyless_verification_missing",
            "wrong_keyless_context_denial",
            f"missing receipt: observed {error.code}",
        )
    else:
        raise RendererDigestError(
            "keyless_context_substitution_accepted",
            "missing contract-bundle verification receipt",
        )
    return 2 + len(cases)


def require_contract_bundle_verification_receipt(value: Any, identity: str) -> None:
    require(
        isinstance(value, dict),
        "contract_bundle_keyless_verification_missing",
        identity,
    )


def validate_contract_bundle_keyless_verification(
    product_release: dict[str, Any],
    contract_bundle: dict[str, Any],
    *,
    resolver: RendererCasResolver,
) -> None:
    """Resolve and verify the complete independent keyless authority edge."""

    receipt = product_release.get("contractBundleVerification")
    require_contract_bundle_verification_receipt(
        receipt,
        product_release.get("version", "product release"),
    )
    require(
        receipt["profile"] == KEYLESS_VERIFICATION_PROFILE
        and receipt["decision"] == "permitted"
        and receipt["authorityIssued"] is False
        and receipt["subject"] == product_release["contractBundle"]
        and receipt["trustPolicy"] == product_release["contractBundle"]["trustPolicy"]
        and receipt["signingRequestDigest"] == receipt["signingRequest"]["digest"]
        and receipt["signatureBundleDigest"] == receipt["signatureBundle"]["digest"]
        and receipt["trustedRootDigest"]
        == receipt["authenticatedSigner"]["trustedRootDigest"]
        and receipt["builderDigest"]
        == receipt["authenticatedSigner"]["claims"]["builderDigest"]
        and receipt["verificationEvidenceDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.keyless-signature-verification-evidence/1",
                **{
                    key: deepcopy(value)
                    for key, value in receipt.items()
                    if key != "verificationEvidenceDigest"
                },
            }
        ),
        "contract_bundle_keyless_verification_binding_mismatch",
        product_release["contractBundle"]["digest"],
    )
    subject = product_release["contractBundle"]
    subject_bytes = resolver.payload(subject["digest"], subject["size"])
    require(
        load_jcs_object(subject_bytes, subject["digest"]) == contract_bundle,
        "contract_bundle_keyless_subject_bytes_mismatch",
        subject["digest"],
    )
    policy = resolver.trust_policy(
        receipt["trustPolicy"],
        subject["repository"],
        subject["mediaType"],
        verification_time=receipt["verifiedAt"],
    )
    policy_bytes = resolver.payload(receipt["trustPolicy"]["digest"])
    signers = [
        signer
        for signer in policy["signers"]
        if signer.get("purpose") == CONTRACT_BUNDLE_RELEASE_PURPOSE
        and signer.get("credentialKind") == "sigstore_keyless"
    ]
    require(
        len(signers) == 1
        and policy["signers"] == signers
        and signers[0] == receipt["authenticatedSigner"],
        "contract_bundle_keyless_policy_signer_mismatch",
        subject["digest"],
    )
    signing_request_descriptor = receipt["signingRequest"]
    require(
        set(signing_request_descriptor)
        == {"repository", "digest", "mediaType", "size"},
        "contract_bundle_keyless_signing_request_descriptor_mismatch",
        subject["digest"],
    )
    signing_request_bytes = resolver.payload(
        signing_request_descriptor["digest"],
        signing_request_descriptor["size"],
    )
    signing_request = load_jcs_object(
        signing_request_bytes,
        signing_request_descriptor["digest"],
    )
    signature_bundle_descriptor = receipt["signatureBundle"]
    require(
        set(signature_bundle_descriptor)
        == {"repository", "digest", "mediaType", "size"},
        "contract_bundle_keyless_signature_bundle_descriptor_mismatch",
        subject["digest"],
    )
    signature_bundle_bytes = resolver.payload(
        signature_bundle_descriptor["digest"],
        signature_bundle_descriptor["size"],
    )
    try:
        verified = resolver.keyless_signature_verifier.verify(
            subject=subject,
            subject_bytes=subject_bytes,
            policy=policy,
            policy_bytes=policy_bytes,
            permitted_signer=signers[0],
            signing_request=signing_request,
            signing_request_bytes=signing_request_bytes,
            signing_request_descriptor=signing_request_descriptor,
            signature_bundle_bytes=signature_bundle_bytes,
            signature_bundle_descriptor=signature_bundle_descriptor,
            verification_time=receipt["verifiedAt"],
            expected_purpose=receipt["purpose"],
            expected_subject_repository=receipt["subject"]["repository"],
            expected_subject_digest=receipt["subject"]["digest"],
            expected_subject_media_type=receipt["subject"]["mediaType"],
            expected_trust_policy=receipt["trustPolicy"],
            expected_signer_identity_digest=receipt["signerIdentityDigest"],
            expected_trusted_root_digest=receipt["trustedRootDigest"],
            expected_workflow=receipt["authenticatedSigner"]["claims"]["workflow"],
            expected_workload_identity=receipt["authenticatedSigner"]["workloadIdentity"],
            expected_claims=receipt["authenticatedSigner"]["claims"],
            expected_builder_digest=receipt["builderDigest"],
            expected_pre_sign_certification_digest=receipt[
                "preSignCertificationDigest"
            ],
            expected_signing_request_digest=receipt["signingRequestDigest"],
            expected_signature_bundle_digest=receipt["signatureBundleDigest"],
        )
    except TrustedKeylessVerificationError as error:
        raise RendererDigestError(error.code, str(error)) from error
    require(
        verified == receipt,
        "contract_bundle_keyless_verification_receipt_mismatch",
        subject["digest"],
    )


def validate_public_source_publisher_identity(
    source_authentication: dict[str, Any],
    resolver: RendererCasResolver,
) -> None:
    """Require the evidence identity to equal its one permitted exact signer."""

    signing_result = source_authentication["signingResult"]
    source_policy = resolver.trust_policy(
        signing_result["trustPolicy"],
        signing_result["repository"],
        signing_result["subjectMediaType"],
    )
    public_source_signers = [
        signer
        for signer in source_policy["signers"]
        if signer["purpose"] == "public-source-v1"
        and signer["keyVersion"] == signing_result["keyVersion"]
        and signer["algorithm"] == signing_result["algorithm"]
    ]
    require(
        len(public_source_signers) == 1
        and source_authentication["publisherIdentityDigest"]
        == canonical_digest(
            public_source_publisher_identity_preimage(public_source_signers[0])
        ),
        "public_source_publisher_identity_mismatch",
        source_authentication["subject"]["digest"],
    )


def validate_product_signer_separation(
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> int:
    purposes = PRODUCT_TRUST_PURPOSES
    policies: dict[str, dict[str, Any]] = {}
    for digest, payload in resolver.payloads.items():
        try:
            document = load_jcs_object(payload, digest)
        except RendererDigestError:
            continue
        if document.get("contract") != "bytedesk.trust-policy/1":
            continue
        policy_id = document.get("policyId")
        if policy_id not in purposes:
            continue
        require(
            isinstance(policy_id, str) and policy_id not in policies,
            "trust_policy_duplicate",
            str(policy_id),
        )
        validate_schema_instance(document, TRUST_POLICY_SCHEMA_ID, registry, schemas)
        policies[policy_id] = document
    signatures: list[tuple[str, str, str, str, str, str, str]] = []
    for purpose in purposes:
        require(purpose in policies, "purpose_trust_policy_missing", purpose)
        policy = policies[purpose]
        require(
            policy["scope"]["purposes"] == [purpose],
            "purpose_trust_policy_not_exact",
            purpose,
        )
        if purpose == "release-status-eligibility-v1":
            require(
                {
                    "application/vnd.bytedesk.agent.release-status-eligibility-evidence.v1+json",
                    "application/vnd.bytedesk.agent.release-status-eligibility-evidence-digest.v1+json",
                }.issubset(set(policy["scope"]["mediaTypes"])),
                "release_status_eligibility_policy_media_scope_mismatch",
                purpose,
            )
        signers = [signer for signer in policy["signers"] if signer["purpose"] == purpose]
        require(len(signers) == 1, "purpose_signer_not_unique", purpose)
        kms_signers = [
            signer
            for signer in signers
            if signer.get("credentialKind") == "kms_key"
        ]
        keyless_signers = [
            signer
            for signer in signers
            if signer.get("credentialKind") == "sigstore_keyless"
        ]
        if purpose == "contract-bundle-release-v1":
            require(
                len(keyless_signers) == 1
                and policy["scope"]["repositories"]
                == ["registry.example/product/contracts"]
                and policy["scope"]["mediaTypes"]
                == [
                    "application/vnd.bytedesk.agent.contract-bundle.v1+json",
                ]
                and policy["scope"]["purposes"]
                == [CONTRACT_BUNDLE_RELEASE_PURPOSE]
                and "keyVersion" not in keyless_signers[0]
                and "publicKeyDigest" not in keyless_signers[0]
                and keyless_signers[0]["claims"]["audience"] == "sigstore",
                "contract_bundle_keyless_signer_missing",
                purpose,
            )
            signer = keyless_signers[0]
            signatures.append(
                (
                    signer["trustedRootDigest"],
                    signer["trustedRootDigest"],
                    signer["workloadIdentity"],
                    signer["claims"]["audience"],
                    signer["claims"]["subject"],
                    signer["claims"]["workflow"],
                    signer["claims"]["environment"],
                )
            )
        else:
            require(
                len(kms_signers) == 1
                and not keyless_signers,
                "purpose_kms_signer_not_unique",
                purpose,
            )
            signer = kms_signers[0]
            signatures.append(
                (
                    signer["keyVersion"],
                    signer["publicKeyDigest"],
                    signer["workloadIdentity"],
                    signer["claims"]["audience"],
                    signer["claims"]["subject"],
                    signer["claims"]["workflow"],
                    signer["claims"]["environment"],
                )
            )
        if purpose != "contract-bundle-release-v1":
            require(
                not keyless_signers,
                "unexpected_keyless_product_signer",
                purpose,
            )
    require(
        len(signatures) == len(set(signatures)),
        "incompatible_product_signer_identity_reused",
        "key/public-key/workload/audience/subject/workflow/environment",
    )
    return len(purposes)


def validate_chain_schemas(
    chain: dict[str, dict[str, Any]],
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    validate_schema_instance(chain["capability"], CAPABILITY_SCHEMA_ID, registry, schemas)
    validate_schema_instance(chain["compatibility"], COMPATIBILITY_SCHEMA_ID, registry, schemas)
    validate_schema_instance(chain["manifest"], MANIFEST_SCHEMA_ID, registry, schemas)


def descriptor_key(value: dict[str, Any]) -> tuple[bytes, str]:
    return value["repository"].encode("utf-8"), value["digest"]


def capability_coverage_preimage(capability: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": CAPABILITY_COVERAGE_PROFILE,
        "semanticRegistry": capability["semanticRegistry"],
        "semantics": capability["semantics"],
    }


def effective_skill_set_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": EFFECTIVE_SKILL_SET_PROFILE,
        "publicSkills": manifest["publicSkills"],
        "privateSkills": manifest["privateSkills"],
    }


def effective_input_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": EFFECTIVE_INPUT_PROFILE,
        "scope": manifest["scope"],
        "source": manifest["source"],
        "sourceKind": manifest["sourceKind"],
        "agentSpecVersion": manifest["agentSpecVersion"],
        "bindingDigest": manifest.get("bindingDigest"),
        "customizationDigest": manifest.get("customizationDigest"),
        "effectiveSkillSetDigest": manifest["effectiveSkillSetDigest"],
        "harnessId": manifest["harnessId"],
        "rendererId": manifest["rendererId"],
        "rendererVersion": manifest["rendererVersion"],
        "productRelease": manifest["productRelease"],
        "rendererRelease": manifest["rendererRelease"],
        "executedDistribution": manifest["executedDistribution"],
        "platform": manifest["platform"],
        "productDistributionDigest": manifest["productDistributionDigest"],
        "compiledAllowlistDigest": manifest["compiledAllowlistDigest"],
        "rendererSchemas": manifest["rendererSchemas"],
        "inputParametersDigest": manifest["inputParametersDigest"],
        "harnessConfigurationDigest": manifest["harnessConfigurationDigest"],
        "normalizationProfile": manifest["normalizationProfile"],
        "outputArchiveProfile": manifest["outputArchiveProfile"],
    }


def functional_input_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the platform-independent functional render input identity."""

    preimage = effective_input_preimage(manifest)
    preimage["profile"] = FUNCTIONAL_INPUT_PROFILE
    del preimage["executedDistribution"]
    del preimage["platform"]
    return preimage


def compatibility_coverage_preimage(compatibility: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": COMPATIBILITY_COVERAGE_PROFILE,
        "capabilityDigest": compatibility["capabilityDigest"],
        "capabilityCoverageDigest": compatibility["capabilityCoverageDigest"],
        "inputDigest": compatibility["inputDigest"],
        "semanticResults": compatibility["semanticResults"],
    }


def output_tree_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": OUTPUT_TREE_PROFILE,
        "files": manifest["files"],
    }


def reproducibility_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": REPRODUCIBILITY_PROFILE,
        "effectiveInputDigest": manifest["effectiveInputDigest"],
        "compatibilityDigest": canonical_digest(manifest["compatibility"]),
        "output": manifest["output"],
    }


def validate_capability(capability: dict[str, Any]) -> None:
    require(
        "rendererRelease" not in capability,
        "renderer_capability_release_backlink",
        "pre-release capability metadata cannot contain its enclosing release",
    )
    semantics = capability["semantics"]
    require(
        capability["semanticCount"] == len(semantics),
        "semantic_count_mismatch",
        "semanticCount must equal the exact semantics array length",
    )
    semantic_ids = [entry["semanticId"] for entry in semantics]
    require(
        semantic_ids == sorted(semantic_ids, key=lambda value: value.encode("utf-8"))
        and len(semantic_ids) == len(set(semantic_ids)),
        "semantic_order_invalid",
        "semantics must be unique and strictly increasing by semanticId UTF-8 bytes",
    )
    require(
        capability["coverageDigest"]
        == canonical_digest(capability_coverage_preimage(capability)),
        "capability_coverage_digest_mismatch",
        "coverageDigest does not bind the semantic registry and exact semantics",
    )


def validate_manifest_input(manifest: dict[str, Any]) -> None:
    for field in ("publicSkills", "privateSkills"):
        skills = manifest[field]
        require(
            [descriptor_key(value) for value in skills]
            == sorted(descriptor_key(value) for value in skills)
            and len({descriptor_key(value) for value in skills}) == len(skills),
            "skill_order_invalid",
            f"{field} must be unique and strictly ordered by repository and digest",
        )
    require(
        manifest["effectiveSkillSetDigest"]
        == canonical_digest(effective_skill_set_preimage(manifest)),
        "effective_skill_set_digest_mismatch",
        "effectiveSkillSetDigest does not bind the exact public/private skill descriptors",
    )
    require(
        manifest["effectiveInputDigest"]
        == canonical_digest(effective_input_preimage(manifest)),
        "effective_input_digest_mismatch",
        "effectiveInputDigest does not bind the exact normalized render inputs",
    )


def validate_compatibility(
    capability: dict[str, Any],
    compatibility: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    require(
        manifest["compatibility"] == compatibility,
        "compatibility_object_mismatch",
        "the embedded compatibility result must equal the standalone result byte-for-byte after JCS",
    )
    require(
        compatibility["capabilityDigest"] == canonical_digest(capability),
        "compatibility_capability_digest_mismatch",
        "capabilityDigest does not identify the complete capability object",
    )
    require(
        compatibility["capabilityCoverageDigest"] == capability["coverageDigest"],
        "compatibility_capability_coverage_mismatch",
        "compatibility result does not bind the capability coverage digest",
    )
    require(
        compatibility["inputDigest"] == manifest["effectiveInputDigest"],
        "compatibility_input_digest_mismatch",
        "compatibility inputDigest differs from the exact effective input",
    )

    identity_fields = (
        "scope",
        "harnessId",
        "rendererId",
        "rendererVersion",
        "productRelease",
        "rendererRelease",
        "executedDistribution",
        "platform",
        "agentSpecVersion",
        "productDistributionDigest",
        "compiledAllowlistDigest",
        "rendererSchemas",
        "normalizationProfile",
    )
    for field in identity_fields:
        require(
            compatibility[field] == manifest[field],
            "manifest_compatibility_identity_mismatch",
            f"manifest and compatibility result differ at {field}",
        )
    for field in ("harnessId", "rendererId", "rendererVersion", "agentSpecVersion"):
        capability_field = field
        require(
            compatibility[field] == capability[capability_field],
            "capability_compatibility_identity_mismatch",
            f"capability and compatibility result differ at {field}",
        )
    require(
        compatibility["scope"] in capability["supportedScopes"],
        "capability_scope_mismatch",
        "compatibility scope is not declared by the capability object",
    )
    require(
        compatibility["platform"] in capability["supportedPlatforms"],
        "capability_platform_mismatch",
        "compatibility platform is not declared by the capability object",
    )

    capability_schema_descriptors = [capability["schema"], *capability["schemas"].values()]
    require(
        compatibility["rendererSchemas"]
        == sorted(capability_schema_descriptors, key=lambda value: value["id"].encode("utf-8")),
        "renderer_schema_set_mismatch",
        "compatibility rendererSchemas differ from the exact capability schema set",
    )
    capability_semantics = {
        entry["semanticId"]: entry["status"] for entry in capability["semantics"]
    }
    result_ids = [entry["semanticId"] for entry in compatibility["semanticResults"]]
    require(
        result_ids == sorted(result_ids, key=lambda value: value.encode("utf-8"))
        and len(result_ids) == len(set(result_ids)),
        "compatibility_semantic_order_invalid",
        "semanticResults must be unique and strictly ordered",
    )
    for entry in compatibility["semanticResults"]:
        require(
            entry["semanticId"] in capability_semantics,
            "compatibility_semantic_not_declared",
            entry["semanticId"],
        )
        require(
            entry["status"] == capability_semantics[entry["semanticId"]],
            "compatibility_semantic_status_mismatch",
            entry["semanticId"],
        )
    require(
        compatibility["coverageDigest"]
        == canonical_digest(compatibility_coverage_preimage(compatibility)),
        "compatibility_coverage_digest_mismatch",
        "coverageDigest does not bind capability coverage, input, and semantic results",
    )


def validate_manifest_output(manifest: dict[str, Any]) -> None:
    files = manifest["files"]
    paths = [entry["path"] for entry in files]
    require(
        paths == sorted(paths, key=lambda value: value.encode("utf-8"))
        and len(paths) == len(set(paths)),
        "output_path_order_invalid",
        "output files must be unique and strictly ordered by NFC UTF-8 path",
    )
    reserved_delivery_paths = {
        "render-manifest.json",
        ".bytedesk/render-manifest.json",
        ".bytedesk/compatibility.json",
        ".bytedesk/private-compilation-input.json",
        ".bytedesk/consumer-deployment.json",
        ".bytedesk/private-compilation-evidence.json",
        ".bytedesk/oci-config.json",
        ".bytedesk/oci-manifest.json",
    }
    require(
        not any(
            path in reserved_delivery_paths
            or path.startswith(".bytedesk/evidence/")
            for path in paths
        ),
        "output_payload_contains_delivery_metadata",
        "render output inventory includes a manifest, evidence, deployment, compilation, or enclosing OCI authority object",
    )
    output = manifest["output"]
    require(
        output["treeDigest"] == canonical_digest(output_tree_preimage(manifest)),
        "output_tree_digest_mismatch",
        "treeDigest does not bind the exact file inventory",
    )
    require(
        output["fileCount"] == len(files),
        "output_file_count_mismatch",
        "output.fileCount must equal the files array length",
    )
    require(
        output["expandedSize"] == sum(entry["size"] for entry in files),
        "output_expanded_size_mismatch",
        "output.expandedSize must equal the exact sum of file sizes",
    )
    require(
        output["archiveProfile"] == manifest["outputArchiveProfile"],
        "output_archive_profile_mismatch",
        "output archive profile differs from the normalized render input",
    )
    require(
        manifest["reproducibilityDigest"]
        == canonical_digest(reproducibility_preimage(manifest)),
        "reproducibility_digest_mismatch",
        "reproducibilityDigest does not bind exact input, compatibility, tree, and archive identity",
    )


def validate_chain(chain: dict[str, dict[str, Any]]) -> None:
    validate_capability(chain["capability"])
    validate_manifest_input(chain["manifest"])
    validate_compatibility(
        chain["capability"], chain["compatibility"], chain["manifest"]
    )
    validate_manifest_output(chain["manifest"])


def materialize_platform_variant(
    base_chain: dict[str, dict[str, Any]],
    variant: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Bind one platform distribution and recompute its platform-bound identities."""

    selection_key = variant["selectionKey"]
    expected_platform = f"{selection_key['os']}/{selection_key['architecture']}"
    require(
        variant["platform"] == expected_platform,
        "cross_platform_selection_mismatch",
        f"{variant['variantId']}: selectionKey does not identify platform",
    )
    chain = deepcopy(base_chain)
    manifest = chain["manifest"]
    compatibility = chain["compatibility"]
    for document in (manifest, compatibility):
        document["platform"] = variant["platform"]
        document["executedDistribution"] = deepcopy(variant["executedDistribution"])
    manifest["effectiveInputDigest"] = canonical_digest(effective_input_preimage(manifest))
    compatibility["inputDigest"] = manifest["effectiveInputDigest"]
    compatibility["coverageDigest"] = canonical_digest(
        compatibility_coverage_preimage(compatibility)
    )
    manifest["compatibility"] = deepcopy(compatibility)
    manifest["reproducibilityDigest"] = canonical_digest(
        reproducibility_preimage(manifest)
    )
    return chain


def cross_platform_identities(
    chain: dict[str, dict[str, Any]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    manifest = chain["manifest"]
    return {
        "functionalInputDigest": canonical_digest(functional_input_preimage(manifest)),
        "output.treeDigest": manifest["output"]["treeDigest"],
        "output.digest": manifest["output"]["digest"],
        "output.size": manifest["output"]["size"],
        "selectionKey": variant["selectionKey"],
        "executedDistribution": manifest["executedDistribution"],
        "platform": manifest["platform"],
        "effectiveInputDigest": manifest["effectiveInputDigest"],
        "compatibility.coverageDigest": manifest["compatibility"]["coverageDigest"],
        "reproducibilityDigest": manifest["reproducibilityDigest"],
        "manifestDigest": canonical_digest(manifest),
    }


def validate_cross_platform_cases(
    cases: list[dict[str, Any]],
    chains: dict[str, dict[str, dict[str, Any]]],
    schema_registry: Registry,
    schemas: dict[str, dict[str, Any]],
    existing_case_ids: set[str],
) -> int:
    required_equal = {
        "functionalInputDigest",
        "output.treeDigest",
        "output.digest",
        "output.size",
    }
    required_different = {
        "selectionKey",
        "executedDistribution",
        "platform",
        "effectiveInputDigest",
        "compatibility.coverageDigest",
        "reproducibilityDigest",
        "manifestDigest",
    }
    seen: set[str] = set()
    for case in cases:
        case_id = case["caseId"]
        require(
            case_id not in existing_case_ids and case_id not in seen,
            "duplicate_cross_platform_case",
            case_id,
        )
        seen.add(case_id)
        require(case["chainId"] in chains, "unknown_chain", case["chainId"])
        require(
            set(case["requiredEqualIdentities"]) == required_equal
            and len(case["requiredEqualIdentities"]) == len(required_equal),
            "cross_platform_equal_contract_incomplete",
            case_id,
        )
        require(
            set(case["requiredDifferentIdentities"]) == required_different
            and len(case["requiredDifferentIdentities"]) == len(required_different),
            "cross_platform_distinct_contract_incomplete",
            case_id,
        )
        variants = case["variants"]
        require(
            len(variants) >= 2,
            "cross_platform_variants_incomplete",
            case_id,
        )
        require(
            len({variant["variantId"] for variant in variants}) == len(variants),
            "cross_platform_variant_duplicate",
            case_id,
        )
        materialized: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for variant in variants:
            chain = materialize_platform_variant(chains[case["chainId"]], variant)
            validate_chain_schemas(chain, schema_registry, schemas)
            validate_chain(chain)
            materialized.append((variant, cross_platform_identities(chain, variant)))

        for identity in required_equal:
            values = {
                rfc8785.dumps(identities[identity])
                for _, identities in materialized
            }
            require(
                len(values) == 1,
                "cross_platform_output_drift",
                f"{case_id}: {identity}",
            )
        for identity in required_different:
            values = {
                rfc8785.dumps(identities[identity])
                for _, identities in materialized
            }
            require(
                len(values) == len(materialized),
                "cross_platform_identity_collision",
                f"{case_id}: {identity}",
            )
    return len(seen)


def validate_selection_authority(target: str, document: dict[str, Any]) -> None:
    """Validate exact executable-selection keys beyond JSON Schema expressivity."""

    if target == "allowlist":
        keys = [
            (entry["harnessId"], entry["rendererId"], entry["version"])
            for entry in document["entries"]
        ]
        require(
            len(keys) == len(set(keys)),
            "renderer_allowlist_key_ambiguous",
            "each harnessId/rendererId/version tuple must select exactly one release",
        )
        return
    if target == "release":
        keys = [
            (entry["os"], entry["architecture"])
            for entry in document["platforms"]
        ]
        require(
            len(keys) == len(set(keys)),
            "renderer_platform_key_ambiguous",
            "each os/architecture tuple must select exactly one distribution",
        )
        return
    raise RendererDigestError("invalid_selection_target", target)


def resolve_pointer(document: Any, pointer: str) -> tuple[Any, str]:
    require(pointer.startswith("/"), "invalid_mutation", pointer)
    segments = [segment.replace("~1", "/").replace("~0", "~") for segment in pointer[1:].split("/")]
    current = document
    for segment in segments[:-1]:
        current = current[int(segment)] if isinstance(current, list) else current[segment]
    return current, segments[-1]


def apply_mutation(document: dict[str, Any], mutation: dict[str, Any]) -> None:
    parent, leaf = resolve_pointer(document, mutation["path"])
    if mutation["operation"] == "replace":
        if isinstance(parent, list):
            parent[int(leaf)] = deepcopy(mutation["value"])
        else:
            parent[leaf] = deepcopy(mutation["value"])
    elif mutation["operation"] == "add":
        if isinstance(parent, list):
            parent.insert(int(leaf), deepcopy(mutation["value"]))
        else:
            require(leaf not in parent, "invalid_mutation", mutation["path"])
            parent[leaf] = deepcopy(mutation["value"])
    elif mutation["operation"] == "swap":
        target = parent[int(leaf)] if isinstance(parent, list) else parent[leaf]
        first = mutation["firstIndex"]
        second = mutation["secondIndex"]
        target[first], target[second] = target[second], target[first]
    elif mutation["operation"] == "appendCopy":
        target = parent[int(leaf)] if isinstance(parent, list) else parent[leaf]
        require(isinstance(target, list), "invalid_mutation", mutation["path"])
        copied = deepcopy(target[mutation["sourceIndex"]])
        for replacement in mutation["replacements"]:
            apply_mutation(copied, replacement)
        target.append(copied)
    else:
        raise RendererDigestError("invalid_mutation", mutation["operation"])


def load_chains(catalog: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    chains: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in catalog["positiveChains"]:
        chain_id = entry["chainId"]
        require(chain_id not in chains, "duplicate_chain", chain_id)
        chains[chain_id] = {
            "capability": load_json(REPOSITORY_ROOT / entry["capabilityPath"]),
            "compatibility": load_json(REPOSITORY_ROOT / entry["compatibilityPath"]),
            "manifest": load_json(REPOSITORY_ROOT / entry["manifestPath"]),
        }
    return chains


def renderer_attempt_authority_preimage(authority: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": RENDERER_ATTEMPT_AUTHORITY_PROFILE,
        "attemptId": authority["attemptId"],
        "attemptFencingToken": authority["attemptFencingToken"],
        "rendererSelectionDigest": authority["rendererSelectionDigest"],
        "productReleaseStatusCheckpointDigest": authority[
            "productReleaseStatusCheckpointDigest"
        ],
        "productReleaseStatusCheckpointAuthenticationEvidenceDigest": authority[
            "productReleaseStatusCheckpointAuthenticationEvidenceDigest"
        ],
        "productReleaseStatusRequestNonce": authority[
            "productReleaseStatusRequestNonce"
        ],
        "rendererReleaseStatusCheckpointDigest": authority[
            "rendererReleaseStatusCheckpointDigest"
        ],
        "rendererReleaseStatusCheckpointAuthenticationEvidenceDigest": authority[
            "rendererReleaseStatusCheckpointAuthenticationEvidenceDigest"
        ],
        "rendererReleaseStatusRequestNonce": authority[
            "rendererReleaseStatusRequestNonce"
        ],
        "portableDefinitionDigest": authority["portableDefinitionDigest"],
        "inputTreeDigest": authority["inputTreeDigest"],
        "framedRequestDigest": authority["framedRequestDigest"],
        "contractBundleDigest": authority["contractBundleDigest"],
        "sandboxProfileDigest": authority["sandboxProfileDigest"],
        "issuerIdentityDigest": authority["issuerIdentityDigest"],
        "issuedAt": authority["issuedAt"],
        "expiresAt": authority["expiresAt"],
    }


def attempt_authentication_evidence_preimage(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_PROFILE,
        "purpose": evidence["purpose"],
        "attemptAuthorityDigest": evidence["attemptAuthorityDigest"],
        "issuerIdentityDigest": evidence["issuerIdentityDigest"],
        "signingResult": evidence["signingResult"],
    }


def execution_authentication_evidence_preimage(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_PROFILE,
        "purpose": evidence["purpose"],
        "receiptDigest": evidence["receiptDigest"],
        "attemptAuthorityDigest": evidence["attemptAuthorityDigest"],
        "rendererSelectionDigest": evidence["rendererSelectionDigest"],
        "launcherIdentityDigest": evidence["launcherIdentityDigest"],
        "signingResult": evidence["signingResult"],
    }


class GraphAudit:
    """Enforce the closed renderer authority DAG, including rank and SCC denial."""

    def __init__(self) -> None:
        self.edges: dict[str, set[str]] = {}

    def edge(
        self,
        source: str,
        source_rank: int,
        target: str,
        target_rank: int,
        role: str,
        *,
        allow_same_rank: bool = False,
    ) -> None:
        require(source != target, "renderer_graph_self_edge", role)
        require(
            target_rank < source_rank
            or (allow_same_rank and target_rank == source_rank),
            "renderer_graph_rank_violation",
            f"{role}:{source_rank}->{target_rank}",
        )
        self.edges.setdefault(source, set()).add(target)
        self.edges.setdefault(target, set())

    def finish(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            require(node not in visiting, "renderer_graph_cycle", node)
            if node in visited:
                return
            visiting.add(node)
            for child in sorted(self.edges.get(node, ())):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(self.edges):
            visit(node)


def resolve_projection(
    descriptor: dict[str, Any],
    projection: dict[str, Any],
    *,
    media_type: str,
    contract: str,
    schema_id: str,
    resolver: RendererCasResolver,
) -> None:
    resolved = resolver.artifact(
        descriptor,
        media_type=media_type,
        contract=contract,
        schema_id=schema_id,
    )
    require(
        resolved == projection,
        "artifact_projection_mismatch",
        descriptor["digest"],
    )


def validate_status_consistency_endpoints(
    proof: dict[str, Any],
    *,
    subject_kind: str,
    subject: dict[str, Any],
    from_endpoint: dict[str, Any],
    to_endpoint: dict[str, Any],
) -> None:
    require(
        proof["subjectKind"] == subject_kind
        and proof["subject"] == subject
        and proof["from"] == from_endpoint
        and proof["to"] == to_endpoint,
        "release_status_head_consistency_endpoint_mismatch",
        proof["proofId"],
    )
    require(
        proof["proofDataDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.release-status-log-consistency-proof-data/1",
                "subjectKind": subject_kind,
                "subject": subject,
                "from": from_endpoint,
                "to": to_endpoint,
                "algorithm": "bytedesk-rfc6962-prefix-consistency-v1",
                "auditPath": proof["auditPath"],
            }
        ),
        "release_status_head_consistency_data_mismatch",
        proof["proofId"],
    )


def validate_status_merkle_consistency(
    proof: dict[str, Any],
    *,
    from_endpoint: dict[str, Any],
    to_endpoint: dict[str, Any],
) -> None:
    require(
        proof["algorithm"] == "bytedesk-rfc6962-prefix-consistency-v1",
        "release_status_head_consistency_algorithm_mismatch",
        proof["proofId"],
    )
    require(
        from_endpoint["treeSize"] < to_endpoint["treeSize"]
        and from_endpoint["treeSize"] == from_endpoint["sequence"]
        and to_endpoint["treeSize"] == to_endpoint["sequence"],
        "release_status_head_consistency_tree_size_mismatch",
        proof["proofId"],
    )
    require(
        verify_merkle_consistency(
            old_size=from_endpoint["treeSize"],
            new_size=to_endpoint["treeSize"],
            old_root=from_endpoint["logRootDigest"],
            new_root=to_endpoint["logRootDigest"],
            audit_path=proof["auditPath"],
        ),
        "release_status_head_consistency_proof_invalid",
        proof["proofId"],
    )


def validate_status_consistency_proof(
    descriptor: dict[str, Any],
    *,
    subject_kind: str,
    subject: dict[str, Any],
    from_endpoint: dict[str, Any],
    to_endpoint: dict[str, Any],
    expected_authority_binding_digest: str,
    expected_trust_policy: dict[str, str],
    expected_signer: dict[str, Any],
    expected_signing_repository: str,
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    verification_time: datetime | str,
) -> dict[str, Any]:
    proof = resolver.artifact(
        descriptor,
        media_type="application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json",
        contract="bytedesk.release-status-log-consistency-proof/1",
        schema_id=RELEASE_STATUS_LOG_CONSISTENCY_PROOF_SCHEMA_ID,
    )
    require(isinstance(proof, dict), "release_status_head_consistency_missing", subject["digest"])
    validate_status_consistency_endpoints(
        proof,
        subject_kind=subject_kind,
        subject=subject,
        from_endpoint=from_endpoint,
        to_endpoint=to_endpoint,
    )
    validate_status_merkle_consistency(
        proof,
        from_endpoint=from_endpoint,
        to_endpoint=to_endpoint,
    )
    require(
        descriptor["trustPolicy"] == expected_trust_policy
        and descriptor["repository"] == expected_signing_repository
        and proof["trustPolicy"] == expected_trust_policy
        and proof["signingResult"]["trustPolicy"] == expected_trust_policy
        and proof["signingResult"]["repository"]
        == expected_signing_repository
        and proof["signingResult"]["keyVersion"] == expected_signer["keyVersion"]
        and proof["signingResult"]["publicKeyDigest"]
        == expected_signer["publicKeyDigest"]
        and proof["signingResult"]["algorithm"] == expected_signer["algorithm"]
        and proof["authorityBindingDigest"]
        == expected_authority_binding_digest,
        "release_status_head_consistency_authority_mismatch",
        proof["proofId"],
    )
    validate_inline_authority(
        proof,
        schema_id=RELEASE_STATUS_LOG_CONSISTENCY_PROOF_SCHEMA_ID,
        purpose="release-status-head-v1",
        subject_media_type="application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=verification_time,
    )
    return proof


def validate_status_merkle_inclusion_proof(proof: dict[str, Any]) -> None:
    require(
        proof.get("algorithm") == "bytedesk-rfc6962-head-inclusion-v1",
        "release_status_head_inclusion_algorithm_mismatch",
        proof.get("proofId", "unknown"),
    )
    require(
        verify_merkle_inclusion(
            leaf_digest=proof["leafDigest"],
            leaf_index=proof["leafIndex"],
            tree_size=proof["treeSize"],
            audit_path=proof["auditPath"],
            expected_root=proof["rootDigest"],
        ),
        "release_status_head_inclusion_proof_invalid",
        proof["proofId"],
    )


def validate_status_head_inclusion(
    checkpoint: dict[str, Any],
    *,
    subject_kind: str,
    subject: dict[str, Any],
    status_descriptor: dict[str, Any],
    expected_repository: str,
    resolver: RendererCasResolver,
) -> dict[str, Any]:
    descriptor = checkpoint["headInclusionProof"]
    proof = resolver.artifact(
        descriptor,
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-log-inclusion-proof.v1+json"
        ),
        contract="bytedesk.release-status-log-inclusion-proof/1",
        schema_id=RELEASE_STATUS_LOG_INCLUSION_PROOF_SCHEMA_ID,
    )
    require(
        isinstance(proof, dict),
        "release_status_head_inclusion_missing",
        checkpoint["checkpointId"],
    )
    expected_leaf_digest = status_leaf_digest(
        subject_kind=subject_kind,
        subject=subject,
        sequence=checkpoint["sequence"],
        epoch=checkpoint["epoch"],
        head=status_descriptor,
    )
    require(
        descriptor["repository"] == expected_repository,
        "release_status_head_inclusion_repository_mismatch",
        checkpoint["checkpointId"],
    )
    require(
        descriptor["trustPolicy"] == checkpoint["trustPolicy"]
        and proof["trustPolicy"] == checkpoint["trustPolicy"]
        and proof["algorithm"] == "bytedesk-rfc6962-head-inclusion-v1"
        and proof["subjectKind"] == subject_kind
        and proof["subject"] == subject
        and checkpoint["treeSize"] == checkpoint["sequence"]
        and proof["treeSize"] == checkpoint["treeSize"]
        and proof["leafIndex"] == checkpoint["treeSize"] - 1
        and proof["leafDigest"] == checkpoint["headLeafDigest"]
        == expected_leaf_digest
        and proof["rootDigest"] == checkpoint["logRootDigest"],
        "release_status_head_inclusion_binding_mismatch",
        checkpoint["checkpointId"],
    )
    validate_status_merkle_inclusion_proof(proof)
    return proof


def validate_status_head_use(
    checkpoint: Any,
    authentication: Any,
    *,
    expected_nonce: str,
    operation_time: datetime | None,
) -> None:
    require(
        isinstance(checkpoint, dict) and isinstance(authentication, dict),
        "release_status_head_unavailable",
        expected_nonce,
    )
    require(
        checkpoint["requestNonce"]
        == authentication["requestNonce"]
        == expected_nonce,
        "release_status_head_nonce_mismatch",
        checkpoint["checkpointId"],
    )
    require(
        isinstance(operation_time, datetime),
        "release_status_head_operation_time_missing",
        checkpoint["checkpointId"],
    )
    require(
        timestamp(checkpoint["verifiedAt"], "status-head:verifiedAt")
        <= operation_time
        < timestamp(checkpoint["expiresAt"], "status-head:expiresAt"),
        "release_status_head_not_fresh_at_use",
        checkpoint["checkpointId"],
    )


def validate_status_head_high_water(
    checkpoint: dict[str, Any],
    prior: dict[str, Any],
) -> bool:
    unchanged_high_water = checkpoint["treeSize"] == prior["treeSize"]
    proof = checkpoint["consistencyProof"]
    if unchanged_high_water:
        require(
            checkpoint["sequence"] == prior["sequence"]
            and checkpoint["epoch"] == prior["epoch"]
            and checkpoint["head"] == prior["head"]
            and checkpoint["headLeafDigest"] == prior["headLeafDigest"]
            and checkpoint["logRootDigest"] == prior["logRootDigest"]
            and proof is None,
            "release_status_head_fork",
            checkpoint["checkpointId"],
        )
    else:
        require(
            checkpoint["treeSize"] > prior["treeSize"]
            and checkpoint["sequence"] > prior["sequence"]
            and checkpoint["epoch"] >= prior["epoch"],
            "release_status_head_rollback",
            checkpoint["checkpointId"],
        )
        require(
            isinstance(proof, dict),
            "release_status_head_consistency_missing",
            checkpoint["checkpointId"],
        )
    return unchanged_high_water


def validate_selected_status_current(status: dict[str, Any], identity: str) -> None:
    require(
        status["status"] == "current",
        "release_status_selected_status_not_current",
        identity,
    )


def validate_status_head_binding(
    *,
    checkpoint_descriptor: dict[str, Any],
    authentication_descriptor: dict[str, Any],
    subject_kind: str,
    subject: dict[str, Any],
    status_descriptor: dict[str, Any],
    status: dict[str, Any],
    expected_nonce: str,
    operation_time: datetime | None,
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    expected_client_prior_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    checkpoint = resolver.artifact(
        checkpoint_descriptor,
        media_type="application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json",
        contract="bytedesk.release-status-head-checkpoint/1",
        schema_id=RELEASE_STATUS_HEAD_CHECKPOINT_SCHEMA_ID,
    )
    authentication = resolver.artifact(
        authentication_descriptor,
        media_type="application/vnd.bytedesk.agent.release-status-head-authentication-evidence.v1+json",
        contract="bytedesk.release-status-head-authentication-evidence/1",
        schema_id=RELEASE_STATUS_HEAD_AUTH_SCHEMA_ID,
    )
    require(
        isinstance(checkpoint, dict) and isinstance(authentication, dict),
        "release_status_head_unresolved",
        subject["digest"],
    )
    validate_status_head_use(
        checkpoint,
        authentication,
        expected_nonce=expected_nonce,
        operation_time=operation_time,
    )
    if expected_client_prior_state is not None:
        require(
            checkpoint["clientPriorState"] == expected_client_prior_state,
            "release_status_head_client_prior_state_mismatch",
            checkpoint["checkpointId"],
        )
    require(
        checkpoint["subjectKind"] == subject_kind
        and checkpoint["subject"] == subject
        and checkpoint["head"] == status_descriptor
        and checkpoint["headDigest"] == status_descriptor["digest"]
        and checkpoint["sequence"] == status["sequence"]
        and checkpoint["treeSize"] == checkpoint["sequence"]
        and status["subjectKind"] == subject_kind
        and status["subject"] == subject
        and status_descriptor["digest"] == canonical_digest(status),
        "release_status_head_binding_mismatch",
        checkpoint["checkpointId"],
    )
    require(
        isinstance(operation_time, datetime)
        and timestamp(status["effectiveAt"], status["statusId"])
        <= operation_time,
        "release_status_effective_after_operation_time",
        checkpoint["checkpointId"],
    )
    validate_inline_authority(
        status,
        schema_id=RELEASE_STATUS_SCHEMA_ID,
        purpose="release-status-v1",
        subject_media_type="application/vnd.bytedesk.agent.release-status.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=operation_time,
    )
    validate_selected_status_current(status, checkpoint["checkpointId"])
    validate_status_head_inclusion(
        checkpoint,
        subject_kind=subject_kind,
        subject=subject,
        status_descriptor=status_descriptor,
        expected_repository=checkpoint_descriptor["repository"],
        resolver=resolver,
    )
    require(
        authentication["checkpointDigest"] == checkpoint_descriptor["digest"]
        and authentication["evidenceDigest"]
        == canonical_digest(
            schema_field_authority_preimage(
                authentication,
                schemas[RELEASE_STATUS_HEAD_AUTH_SCHEMA_ID],
                "evidenceDigest",
            )
        ),
        "release_status_head_authentication_mismatch",
        checkpoint["checkpointId"],
    )
    validate_signing_result(
        authentication["signingResult"],
        purpose="release-status-head-v1",
        subject_digest=checkpoint_descriptor["digest"],
        subject_media_type="application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=operation_time,
    )
    status_head_policy = resolver.trust_policy(
        checkpoint["trustPolicy"],
        checkpoint_descriptor["repository"],
        checkpoint_descriptor["mediaType"],
    )
    head_signing_result = authentication["signingResult"]
    try:
        head_signer = exact_policy_signer(
            status_head_policy,
            purpose="release-status-head-v1",
            subject_media_type=head_signing_result["subjectMediaType"],
            key_version=head_signing_result["keyVersion"],
            algorithm=head_signing_result["algorithm"],
            public_key_digest=head_signing_result["publicKeyDigest"],
        )
    except ValueError as error:
        raise RendererDigestError(
            "release_status_head_authority_mismatch",
            checkpoint["checkpointId"],
        ) from error
    expected_head_authority_binding_digest = signer_authority_binding_digest(
        signer=head_signer,
        trust_policy=checkpoint["trustPolicy"],
        repository=head_signing_result["repository"],
    )
    require(
        authentication["authorityBindingDigest"]
        == expected_head_authority_binding_digest
        and checkpoint_descriptor["repository"]
        == authentication_descriptor["repository"]
        == head_signing_result["repository"]
        and checkpoint["trustPolicy"] == authentication["signingResult"]["trustPolicy"]
        == checkpoint_descriptor["trustPolicy"]
        == authentication_descriptor["trustPolicy"],
        "release_status_head_authority_mismatch",
        checkpoint["checkpointId"],
    )
    verified_at = timestamp(checkpoint["verifiedAt"], "status-head:verifiedAt")
    expires_at = timestamp(checkpoint["expiresAt"], "status-head:expiresAt")
    require(
        verified_at < expires_at
        and (expires_at - verified_at).total_seconds()
        <= status_head_policy["rules"]["freshnessSeconds"]
        and status_head_policy["rules"]["requireNonce"] is True
        and status_head_policy["rules"]["denyDowngrade"] is True,
        "release_status_head_invalid_window",
        checkpoint["checkpointId"],
    )
    prior_state = checkpoint["clientPriorState"]
    if prior_state["kind"] == "match":
        prior = resolver.artifact(
            prior_state["checkpoint"],
            media_type="application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json",
            contract="bytedesk.release-status-head-checkpoint/1",
            schema_id=RELEASE_STATUS_HEAD_CHECKPOINT_SCHEMA_ID,
        )
        require(
            isinstance(prior, dict)
            and prior["subjectKind"] == subject_kind
            and prior["subject"] == subject
            and prior["sequence"] == prior_state["sequence"]
            and prior["epoch"] == prior_state["epoch"]
            and prior["treeSize"] == prior_state["treeSize"]
            and prior["logRootDigest"] == prior_state["logRootDigest"]
            and prior["headLeafDigest"] == prior_state["headLeafDigest"]
            ,
            "release_status_head_rollback",
            checkpoint["checkpointId"],
        )
        prior_status = resolver.artifact(
            prior["head"],
            media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            contract="bytedesk.release-status/1",
            schema_id=RELEASE_STATUS_SCHEMA_ID,
        )
        require(
            isinstance(prior_status, dict)
            and prior["headDigest"] == prior["head"]["digest"]
            == canonical_digest(prior_status)
            and prior_status["subjectKind"] == subject_kind
            and prior_status["subject"] == subject
            and prior_status["sequence"] == prior["sequence"]
            and timestamp(prior_status["effectiveAt"], prior_status["statusId"])
            <= timestamp(status["effectiveAt"], status["statusId"]),
            "release_status_head_persisted_status_mismatch",
            checkpoint["checkpointId"],
        )
        validate_inline_authority(
            prior_status,
            schema_id=RELEASE_STATUS_SCHEMA_ID,
            purpose="release-status-v1",
            subject_media_type=(
                "application/vnd.bytedesk.agent.release-status.v1+json"
            ),
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=operation_time,
        )
        validate_status_head_inclusion(
            prior,
            subject_kind=subject_kind,
            subject=subject,
            status_descriptor=prior["head"],
            expected_repository=prior_state["checkpoint"]["repository"],
            resolver=resolver,
        )
        unchanged_high_water = validate_status_head_high_water(checkpoint, prior)
        if unchanged_high_water:
            pass
        else:
            validate_status_consistency_proof(
                checkpoint["consistencyProof"],
                subject_kind=subject_kind,
                subject=subject,
                from_endpoint={
                    "treeSize": prior["treeSize"],
                    "sequence": prior["sequence"],
                    "epoch": prior["epoch"],
                    "headDigest": prior["headDigest"],
                    "logRootDigest": prior["logRootDigest"],
                },
                to_endpoint={
                    "treeSize": checkpoint["treeSize"],
                    "sequence": checkpoint["sequence"],
                    "epoch": checkpoint["epoch"],
                    "headDigest": checkpoint["headDigest"],
                    "logRootDigest": checkpoint["logRootDigest"],
                },
                expected_authority_binding_digest=(
                    expected_head_authority_binding_digest
                ),
                expected_trust_policy=checkpoint["trustPolicy"],
                expected_signer=head_signer,
                expected_signing_repository=head_signing_result["repository"],
                resolver=resolver,
                registry=registry,
                schemas=schemas,
                verification_time=operation_time,
            )
    else:
        require(
            checkpoint["consistencyProof"] is None,
            "release_status_head_unexpected_consistency_proof",
            checkpoint["checkpointId"],
        )
    return checkpoint, authentication


def validate_release_selection_bindings(
    bindings: list[dict[str, Any]],
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    graph: GraphAudit,
) -> tuple[int, dict[str, Any]]:
    expected_fields = {
        "bindingId",
        "capabilityPath",
        "releasePath",
        "allowlistPath",
        "productReleasePath",
        "selectionPath",
        "productDistributionEmbeddedAllowlistDigest",
    }
    seen: set[str] = set()
    shared: dict[str, Any] | None = None
    product_distribution_projection = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/schema/positive/product-distribution-manifest__current.json"
    )
    for binding in bindings:
        require(set(binding) == expected_fields, "invalid_release_binding", "fields")
        binding_id = binding["bindingId"]
        require(binding_id not in seen, "invalid_release_binding", binding_id)
        seen.add(binding_id)
        capability = load_json(REPOSITORY_ROOT / binding["capabilityPath"])
        release = load_json(REPOSITORY_ROOT / binding["releasePath"])
        allowlist = load_json(REPOSITORY_ROOT / binding["allowlistPath"])
        product_release = load_json(REPOSITORY_ROOT / binding["productReleasePath"])
        selection = load_json(REPOSITORY_ROOT / binding["selectionPath"])
        selection_operation_time = timestamp(
            selection["operationTime"],
            f"{binding_id}:selection-operation-time",
        )
        for document, schema_id in (
            (capability, CAPABILITY_SCHEMA_ID),
            (release, RELEASE_SCHEMA_ID),
            (allowlist, ALLOWLIST_SCHEMA_ID),
            (product_distribution_projection, PRODUCT_DISTRIBUTION_SCHEMA_ID),
            (product_release, PRODUCT_RELEASE_SCHEMA_ID),
            (selection, RENDERER_SELECTION_SCHEMA_ID),
        ):
            validate_schema_instance(document, schema_id, registry, schemas)
        validate_capability(capability)
        validate_selection_authority("release", release)
        validate_selection_authority("allowlist", allowlist)
        validate_inline_authority(
            release,
            schema_id=RELEASE_SCHEMA_ID,
            purpose="product-release-v1",
            subject_media_type="application/vnd.bytedesk.agent.renderer-release.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        validate_inline_authority(
            allowlist,
            schema_id=ALLOWLIST_SCHEMA_ID,
            purpose="product-release-v1",
            subject_media_type="application/vnd.bytedesk.agent.renderer-allowlist.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        validate_inline_authority(
            product_distribution_projection,
            schema_id=PRODUCT_DISTRIBUTION_SCHEMA_ID,
            purpose="product-release-v1",
            subject_media_type="application/vnd.bytedesk.agent.product-distribution.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        validate_inline_authority(
            product_release,
            schema_id=PRODUCT_RELEASE_SCHEMA_ID,
            purpose="product-release-v1",
            subject_media_type="application/vnd.bytedesk.agent.product-release-manifest.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        require(
            selection["selectionDigest"]
            == canonical_digest(renderer_selection_preimage(selection)),
            "renderer_selection_digest_mismatch",
            binding_id,
        )
        key = (
            selection["targetHarness"],
            selection["rendererId"],
            selection["rendererVersion"],
        )
        require(
            key
            == (release["harnessId"], release["rendererId"], release["version"])
            == (
                capability["harnessId"],
                capability["rendererId"],
                capability["rendererVersion"],
            ),
            "renderer_identity_mismatch",
            binding_id,
        )
        resolve_projection(
            release["capabilityManifest"],
            capability,
            media_type="application/vnd.bytedesk.agent.renderer-capability.v1+json",
            contract="bytedesk.renderer-capability/1",
            schema_id=CAPABILITY_SCHEMA_ID,
            resolver=resolver,
        )
        semantic_registry = resolver.artifact(
            capability["semanticRegistry"],
            media_type="application/vnd.bytedesk.agent-spec-semantics.v1+json",
        )
        require(
            isinstance(semantic_registry, dict)
            and semantic_registry.get("semantics") == capability["semantics"],
            "renderer_semantic_registry_mismatch",
            binding_id,
        )
        builder_manifest = resolver.artifact(
            release["builder"],
            media_type="application/vnd.oci.image.manifest.v1+json",
        )
        require(
            isinstance(builder_manifest, dict)
            and builder_manifest.get("schemaVersion") == 2,
            "renderer_builder_distribution_invalid",
            binding_id,
        )
        for platform in release["platforms"]:
            platform_manifest = resolver.artifact(
                platform["distribution"],
                media_type="application/vnd.oci.image.manifest.v1+json",
            )
            require(
                isinstance(platform_manifest, dict)
                and platform_manifest.get("schemaVersion") == 2,
                "renderer_platform_distribution_invalid",
                binding_id,
            )
        matching_entries = [
            entry
            for entry in allowlist["entries"]
            if (entry["harnessId"], entry["rendererId"], entry["version"]) == key
        ]
        require(len(matching_entries) == 1, "renderer_allowlist_entry_mismatch", binding_id)
        release_descriptor = matching_entries[0]["release"]
        resolve_projection(
            release_descriptor,
            release,
            media_type="application/vnd.bytedesk.agent.renderer-release.v1+json",
            contract="bytedesk.renderer-release/1",
            schema_id=RELEASE_SCHEMA_ID,
            resolver=resolver,
        )
        require(
            release_descriptor == selection["rendererRelease"],
            "renderer_release_selection_mismatch",
            binding_id,
        )
        product_distribution = resolver.artifact(
            product_release["productDistribution"],
            media_type="application/vnd.bytedesk.agent.product-distribution.v1+json",
            contract="bytedesk.product-distribution-manifest/1",
            schema_id=PRODUCT_DISTRIBUTION_SCHEMA_ID,
        )
        require(
            product_distribution == product_distribution_projection,
            "renderer_product_distribution_mismatch",
            binding_id,
        )
        for descriptor, media_type in (
            (
                product_distribution["executableDistribution"],
                "application/vnd.oci.image.manifest.v1+json",
            ),
            (
                product_distribution["builder"],
                "application/vnd.oci.image.manifest.v1+json",
            ),
        ):
            manifest = resolver.artifact(descriptor, media_type=media_type)
            require(
                isinstance(manifest, dict) and manifest.get("schemaVersion") == 2,
                "product_distribution_nested_artifact_invalid",
                binding_id,
            )
        contract_bundle = resolver.artifact(
            product_distribution["contractBundle"],
            media_type="application/vnd.bytedesk.agent.contract-bundle.v1+json",
            contract="bytedesk.contract-bundle/1",
            schema_id=CONTRACT_BUNDLE_SCHEMA_ID,
        )
        require(isinstance(contract_bundle, dict), "contract_bundle_unresolved", binding_id)
        require(
            product_release["contractBundle"]
            == product_distribution["contractBundle"],
            "product_release_contract_bundle_mismatch",
            binding_id,
        )
        validate_contract_bundle_keyless_verification(
            product_release,
            contract_bundle,
            resolver=resolver,
        )
        allowlist_descriptor = product_distribution["embeddedCompiledAllowlist"]
        resolve_projection(
            allowlist_descriptor,
            allowlist,
            media_type="application/vnd.bytedesk.agent.renderer-allowlist.v1+json",
            contract="bytedesk.renderer-allowlist/1",
            schema_id=ALLOWLIST_SCHEMA_ID,
            resolver=resolver,
        )
        require(
            product_release["compiledAllowlist"] == allowlist_descriptor
            and binding["productDistributionEmbeddedAllowlistDigest"]
            == allowlist_descriptor["digest"],
            "renderer_allowlist_product_mismatch",
            binding_id,
        )
        allowlist_release_set = sorted(
            (entry["release"] for entry in allowlist["entries"]),
            key=descriptor_key,
        )
        require(
            product_release["rendererReleases"] == allowlist_release_set,
            "renderer_release_set_mismatch",
            binding_id,
        )
        product_release_descriptor = selection["productRelease"]
        resolve_projection(
            product_release_descriptor,
            product_release,
            media_type="application/vnd.bytedesk.agent.product-release-manifest.v1+json",
            contract="bytedesk.product-release-manifest/1",
            schema_id=PRODUCT_RELEASE_SCHEMA_ID,
            resolver=resolver,
        )
        require(
            selection["productDistribution"] == product_release["productDistribution"]
            and selection["compiledAllowlist"] == product_release["compiledAllowlist"]
            and selection["capability"] == release["capabilityManifest"]
            and selection["productDistributionDigest"]
            == product_release["productDistribution"]["digest"]
            and selection["compiledAllowlistDigest"]
            == product_release["compiledAllowlist"]["digest"],
            "renderer_product_release_mismatch",
            binding_id,
        )
        selected_platforms = [
            platform
            for platform in release["platforms"]
            if f"{platform['os']}/{platform['architecture']}"
            == selection["targetPlatform"]
        ]
        require(
            len(selected_platforms) == 1
            and selected_platforms[0]["distribution"]
            == selection["executableDistribution"],
            "renderer_executable_selection_mismatch",
            binding_id,
        )
        qualification = resolver.artifact(
            selection["releaseQualification"],
            media_type="application/vnd.bytedesk.agent.release-qualification.v1+json",
            contract="bytedesk.release-qualification/1",
            schema_id=RELEASE_QUALIFICATION_SCHEMA_ID,
        )
        product_status = resolver.artifact(
            selection["productReleaseStatus"],
            media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            contract="bytedesk.release-status/1",
            schema_id=RELEASE_STATUS_SCHEMA_ID,
        )
        renderer_status = resolver.artifact(
            selection["rendererReleaseStatus"],
            media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            contract="bytedesk.release-status/1",
            schema_id=RELEASE_STATUS_SCHEMA_ID,
        )
        validate_inline_authority(
            qualification,
            schema_id=RELEASE_QUALIFICATION_SCHEMA_ID,
            purpose="release-qualification-decision-v1",
            subject_media_type="application/vnd.bytedesk.agent.release-qualification.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        validate_inline_authority(
            product_status,
            schema_id=RELEASE_STATUS_SCHEMA_ID,
            purpose="release-status-v1",
            subject_media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        validate_inline_authority(
            renderer_status,
            schema_id=RELEASE_STATUS_SCHEMA_ID,
            purpose="release-status-v1",
            subject_media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=selection_operation_time,
        )
        require(
            product_status["subject"] == product_release_descriptor
            and renderer_status["subject"] == release_descriptor,
            "release_status_subject_mismatch",
            binding_id,
        )
        product_checkpoint, product_checkpoint_authentication = validate_status_head_binding(
            checkpoint_descriptor=selection["productReleaseStatusCheckpoint"],
            authentication_descriptor=selection[
                "productReleaseStatusCheckpointAuthenticationEvidence"
            ],
            subject_kind="product_release",
            subject=product_release_descriptor,
            status_descriptor=selection["productReleaseStatus"],
            status=product_status,
            expected_nonce=selection["productReleaseStatusRequestNonce"],
            operation_time=selection_operation_time,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )
        renderer_checkpoint, renderer_checkpoint_authentication = validate_status_head_binding(
            checkpoint_descriptor=selection["rendererReleaseStatusCheckpoint"],
            authentication_descriptor=selection[
                "rendererReleaseStatusCheckpointAuthenticationEvidence"
            ],
            subject_kind="renderer_release",
            subject=release_descriptor,
            status_descriptor=selection["rendererReleaseStatus"],
            status=renderer_status,
            expected_nonce=selection["rendererReleaseStatusRequestNonce"],
            operation_time=selection_operation_time,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )

        graph.edge(release_descriptor["digest"], 1, release["capabilityManifest"]["digest"], 0, "R->C")
        graph.edge(allowlist_descriptor["digest"], 2, release_descriptor["digest"], 1, "A->R")
        graph.edge(product_release["productDistribution"]["digest"], 3, allowlist_descriptor["digest"], 2, "P->A")
        graph.edge(product_release_descriptor["digest"], 4, product_release["productDistribution"]["digest"], 3, "M->P")
        graph.edge(product_release_descriptor["digest"], 4, allowlist_descriptor["digest"], 2, "M->A")
        graph.edge(product_release_descriptor["digest"], 4, release_descriptor["digest"], 1, "M->R")
        graph.edge(selection["releaseQualification"]["digest"], 12, product_release_descriptor["digest"], 4, "G->M")
        graph.edge(selection["productReleaseStatus"]["digest"], 13, product_release_descriptor["digest"], 4, "status->M")
        graph.edge(selection["rendererReleaseStatus"]["digest"], 13, release_descriptor["digest"], 1, "status->R")
        graph.edge(selection["selectionDigest"], 14, selection["releaseQualification"]["digest"], 12, "S->G")
        graph.edge(selection["selectionDigest"], 14, selection["productReleaseStatus"]["digest"], 13, "S->M-status")
        graph.edge(selection["selectionDigest"], 14, selection["rendererReleaseStatus"]["digest"], 13, "S->R-status")
        graph.edge(selection["selectionDigest"], 14, selection["productReleaseStatusCheckpointAuthenticationEvidence"]["digest"], 13, "S->M-head-auth")
        graph.edge(selection["selectionDigest"], 14, selection["rendererReleaseStatusCheckpointAuthenticationEvidence"]["digest"], 13, "S->R-head-auth")
        graph.edge(selection["productReleaseStatusCheckpointAuthenticationEvidence"]["digest"], 13, selection["productReleaseStatusCheckpoint"]["digest"], 13, "M-head-auth->checkpoint", allow_same_rank=True)
        graph.edge(selection["rendererReleaseStatusCheckpointAuthenticationEvidence"]["digest"], 13, selection["rendererReleaseStatusCheckpoint"]["digest"], 13, "R-head-auth->checkpoint", allow_same_rank=True)
        graph.edge(selection["productReleaseStatusCheckpoint"]["digest"], 13, selection["productReleaseStatus"]["digest"], 13, "M-checkpoint->status", allow_same_rank=True)
        graph.edge(selection["rendererReleaseStatusCheckpoint"]["digest"], 13, selection["rendererReleaseStatus"]["digest"], 13, "R-checkpoint->status", allow_same_rank=True)
        graph.edge(selection["selectionDigest"], 14, product_release_descriptor["digest"], 4, "S->M")
        graph.edge(selection["selectionDigest"], 14, release_descriptor["digest"], 1, "S->R")

        context = {
            "capability": capability,
            "release": release,
            "releaseDescriptor": release_descriptor,
            "allowlist": allowlist,
            "allowlistDescriptor": allowlist_descriptor,
            "productDistribution": product_distribution,
            "productRelease": product_release,
            "productReleaseDescriptor": product_release_descriptor,
            "qualification": qualification,
            "qualificationDescriptor": selection["releaseQualification"],
            "selection": selection,
            "productStatusCheckpoint": product_checkpoint,
            "productStatusCheckpointAuthentication": product_checkpoint_authentication,
            "rendererStatusCheckpoint": renderer_checkpoint,
            "rendererStatusCheckpointAuthentication": renderer_checkpoint_authentication,
        }
        if shared is None:
            shared = context
        else:
            for field in (
                "allowlist",
                "allowlistDescriptor",
                "productDistribution",
                "productRelease",
                "productReleaseDescriptor",
                "qualification",
                "qualificationDescriptor",
            ):
                require(shared[field] == context[field], "release_binding_shared_graph_mismatch", field)
    require(bool(seen) and shared is not None, "invalid_release_binding", "empty")
    shared["bindings"] = bindings
    return len(seen), shared


def validate_status_head_negative_cases(
    context: dict[str, Any],
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> int:
    selection = context["selection"]
    checkpoint = deepcopy(context["productStatusCheckpoint"])
    authentication = deepcopy(context["productStatusCheckpointAuthentication"])
    expected_nonce = selection["productReleaseStatusRequestNonce"]
    prior_state = checkpoint["clientPriorState"]
    require(prior_state["kind"] == "match", "status_head_negative_prior_missing", "product")
    prior = resolver.artifact(
        prior_state["checkpoint"],
        media_type="application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json",
        contract="bytedesk.release-status-head-checkpoint/1",
        schema_id=RELEASE_STATUS_HEAD_CHECKPOINT_SCHEMA_ID,
    )
    require(isinstance(prior, dict), "status_head_negative_prior_missing", "product")
    proof = resolver.artifact(
        checkpoint["consistencyProof"],
        media_type="application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json",
        contract="bytedesk.release-status-log-consistency-proof/1",
        schema_id=RELEASE_STATUS_LOG_CONSISTENCY_PROOF_SCHEMA_ID,
    )
    require(isinstance(proof, dict), "status_head_negative_proof_missing", "product")
    inclusion_proof = resolver.artifact(
        checkpoint["headInclusionProof"],
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-log-inclusion-proof.v1+json"
        ),
        contract="bytedesk.release-status-log-inclusion-proof/1",
        schema_id=RELEASE_STATUS_LOG_INCLUSION_PROOF_SCHEMA_ID,
    )
    require(
        isinstance(inclusion_proof, dict),
        "status_head_negative_inclusion_missing",
        "product",
    )

    first_contact_status = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "status-head-first-contact-sequence-7-status.json"
    )
    first_contact_checkpoint = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "status-head-first-contact-sequence-7.json"
    )
    first_contact_authentication = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "status-head-first-contact-sequence-7-authentication-evidence.json"
    )
    first_contact_checkpoint_descriptor = projection_descriptor(
        repository="registry.example/product/status-heads",
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-head-checkpoint.v1+json"
        ),
        document=first_contact_checkpoint,
        trust_policy=first_contact_checkpoint["trustPolicy"],
    )
    first_contact_authentication_descriptor = projection_descriptor(
        repository="registry.example/product/status-heads",
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-head-authentication-evidence.v1+json"
        ),
        document=first_contact_authentication,
        trust_policy=first_contact_checkpoint["trustPolicy"],
    )
    validate_status_head_binding(
        checkpoint_descriptor=first_contact_checkpoint_descriptor,
        authentication_descriptor=first_contact_authentication_descriptor,
        subject_kind="renderer_release",
        subject=first_contact_checkpoint["subject"],
        status_descriptor=first_contact_checkpoint["head"],
        status=first_contact_status,
        expected_nonce=first_contact_checkpoint["requestNonce"],
        operation_time=timestamp(
            first_contact_checkpoint["verifiedAt"],
            "first-contact-sequence-7",
        ),
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        expected_client_prior_state={"kind": "none"},
    )
    require(
        first_contact_checkpoint["sequence"] == 7
        and first_contact_checkpoint["clientPriorState"] == {"kind": "none"},
        "status_head_first_contact_not_exercised",
        first_contact_checkpoint["checkpointId"],
    )

    far_behind_status = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "status-head-far-behind-sequence-1024-status.json"
    )
    far_behind_checkpoint = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "status-head-far-behind-sequence-1024.json"
    )
    far_behind_authentication = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "status-head-far-behind-sequence-1024-authentication-evidence.json"
    )
    far_behind_checkpoint_descriptor = projection_descriptor(
        repository="registry.example/product/status-heads",
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-head-checkpoint.v1+json"
        ),
        document=far_behind_checkpoint,
        trust_policy=far_behind_checkpoint["trustPolicy"],
    )
    far_behind_authentication_descriptor = projection_descriptor(
        repository="registry.example/product/status-heads",
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-head-authentication-evidence.v1+json"
        ),
        document=far_behind_authentication,
        trust_policy=far_behind_checkpoint["trustPolicy"],
    )
    validate_status_head_binding(
        checkpoint_descriptor=far_behind_checkpoint_descriptor,
        authentication_descriptor=far_behind_authentication_descriptor,
        subject_kind="renderer_release",
        subject=far_behind_checkpoint["subject"],
        status_descriptor=far_behind_checkpoint["head"],
        status=far_behind_status,
        expected_nonce=far_behind_checkpoint["requestNonce"],
        operation_time=timestamp(
            far_behind_checkpoint["verifiedAt"],
            "far-behind-sequence-1024",
        ),
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        expected_client_prior_state=far_behind_checkpoint["clientPriorState"],
    )
    far_behind_proof = resolver.artifact(
        far_behind_checkpoint["consistencyProof"],
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-log-consistency-proof.v1+json"
        ),
        contract="bytedesk.release-status-log-consistency-proof/1",
        schema_id=RELEASE_STATUS_LOG_CONSISTENCY_PROOF_SCHEMA_ID,
    )
    require(
        isinstance(far_behind_proof, dict)
        and far_behind_checkpoint["treeSize"] == 1024
        and len(far_behind_proof["auditPath"]) <= 10,
        "status_head_far_behind_logarithmic_proof_missing",
        far_behind_checkpoint["checkpointId"],
    )
    far_behind_inclusion_proof = resolver.artifact(
        far_behind_checkpoint["headInclusionProof"],
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-log-inclusion-proof.v1+json"
        ),
        contract="bytedesk.release-status-log-inclusion-proof/1",
        schema_id=RELEASE_STATUS_LOG_INCLUSION_PROOF_SCHEMA_ID,
    )
    require(
        isinstance(far_behind_inclusion_proof, dict)
        and len(far_behind_inclusion_proof["auditPath"]) >= 2
        and far_behind_inclusion_proof["auditPath"][0]
        != far_behind_inclusion_proof["auditPath"][1],
        "status_head_far_behind_logarithmic_proof_missing",
        f"{far_behind_checkpoint['checkpointId']}: inclusion path",
    )

    unrelated_withdrawn_status = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/operations/renderer-cas/"
        "unrelated-withdrawn-release-status.json"
    )
    validate_schema_instance(
        unrelated_withdrawn_status,
        RELEASE_STATUS_SCHEMA_ID,
        registry,
        schemas,
    )
    validate_inline_authority(
        unrelated_withdrawn_status,
        schema_id=RELEASE_STATUS_SCHEMA_ID,
        purpose="release-status-v1",
        subject_media_type="application/vnd.bytedesk.agent.release-status.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=timestamp(
            unrelated_withdrawn_status["effectiveAt"],
            "unrelated-withdrawn-status-use",
        ),
    )
    require(
        unrelated_withdrawn_status["status"] == "withdrawn",
        "unrelated_withdrawn_status_not_exercised",
        unrelated_withdrawn_status["statusId"],
    )
    from_endpoint = {
        "treeSize": prior["treeSize"],
        "sequence": prior["sequence"],
        "epoch": prior["epoch"],
        "headDigest": prior["headDigest"],
        "logRootDigest": prior["logRootDigest"],
    }
    to_endpoint = {
        "treeSize": checkpoint["treeSize"],
        "sequence": checkpoint["sequence"],
        "epoch": checkpoint["epoch"],
        "headDigest": checkpoint["headDigest"],
        "logRootDigest": checkpoint["logRootDigest"],
    }
    rollback_prior = deepcopy(prior)
    rollback_prior["sequence"] = checkpoint["sequence"] + 1
    fork_checkpoint = deepcopy(checkpoint)
    fork_checkpoint["treeSize"] = prior["treeSize"]
    fork_checkpoint["sequence"] = prior["sequence"]
    fork_checkpoint["epoch"] = prior["epoch"]
    fork_checkpoint["logRootDigest"] = "sha256:" + ("33" * 32)
    fork_checkpoint["consistencyProof"] = None
    null_advance_checkpoint = deepcopy(checkpoint)
    null_advance_checkpoint["consistencyProof"] = None

    wrong_from_root = deepcopy(proof)
    wrong_from_root["from"]["logRootDigest"] = "sha256:" + ("44" * 32)
    wrong_to_root = deepcopy(proof)
    wrong_to_root["to"]["logRootDigest"] = "sha256:" + ("55" * 32)
    wrong_subject = deepcopy(proof)
    wrong_subject["subject"]["digest"] = "sha256:" + ("66" * 32)
    wrong_epoch = deepcopy(proof)
    wrong_epoch["from"]["epoch"] += 1
    omitted_consistency_node = deepcopy(proof)
    omitted_consistency_node["auditPath"] = omitted_consistency_node["auditPath"][:-1]
    reordered_consistency_nodes = deepcopy(proof)
    reordered_consistency_nodes["auditPath"].reverse()
    substituted_consistency_node = deepcopy(proof)
    substituted_consistency_node["auditPath"][0] = "sha256:" + ("77" * 32)
    wrong_consistency_algorithm = deepcopy(proof)
    wrong_consistency_algorithm["algorithm"] = "bytedesk-rfc6962-unknown-v1"
    wrong_consistency_tree_size = deepcopy(to_endpoint)
    wrong_consistency_tree_size["treeSize"] += 1
    wrong_inclusion_node = deepcopy(inclusion_proof)
    wrong_inclusion_node["auditPath"][0] = "sha256:" + ("88" * 32)
    reordered_inclusion_nodes = deepcopy(far_behind_inclusion_proof)
    reordered_inclusion_nodes["auditPath"][0], reordered_inclusion_nodes["auditPath"][1] = (
        reordered_inclusion_nodes["auditPath"][1],
        reordered_inclusion_nodes["auditPath"][0],
    )
    wrong_inclusion_tree_size = deepcopy(inclusion_proof)
    wrong_inclusion_tree_size["treeSize"] += 1
    wrong_inclusion_root = deepcopy(inclusion_proof)
    wrong_inclusion_root["rootDigest"] = "sha256:" + ("99" * 32)
    wrong_inclusion_algorithm = deepcopy(inclusion_proof)
    wrong_inclusion_algorithm["algorithm"] = "bytedesk-rfc6962-unknown-v1"
    selected_non_current = resolver.artifact(
        selection["productReleaseStatus"],
        media_type="application/vnd.bytedesk.agent.release-status.v1+json",
        contract="bytedesk.release-status/1",
        schema_id=RELEASE_STATUS_SCHEMA_ID,
    )
    require(
        isinstance(selected_non_current, dict),
        "status_head_selected_status_missing",
        "product",
    )
    selected_non_current = deepcopy(selected_non_current)
    selected_non_current["status"] = "withdrawn"

    cases: list[tuple[str, Any, str]] = [
        (
            "release_status_head_unavailable",
            lambda: validate_status_head_use(
                None,
                authentication,
                expected_nonce=expected_nonce,
                operation_time=None,
            ),
            "status-head outage",
        ),
        (
            "release_status_head_nonce_mismatch",
            lambda: validate_status_head_use(
                checkpoint,
                authentication,
                expected_nonce="wrong_status_head_nonce_0123456789abcdef",
                operation_time=None,
            ),
            "wrong caller nonce",
        ),
        (
            "release_status_head_not_fresh_at_use",
            lambda: validate_status_head_use(
                checkpoint,
                authentication,
                expected_nonce=expected_nonce,
                operation_time=timestamp(checkpoint["expiresAt"], "expired-head"),
            ),
            "expired checkpoint at use",
        ),
        (
            "release_status_head_not_fresh_at_use",
            lambda: validate_status_head_use(
                checkpoint,
                authentication,
                expected_nonce=expected_nonce,
                operation_time=(
                    timestamp(checkpoint["verifiedAt"], "future-head")
                    - timedelta(microseconds=1)
                ),
            ),
            "not-yet-valid checkpoint",
        ),
        (
            "release_status_head_rollback",
            lambda: validate_status_head_high_water(checkpoint, rollback_prior),
            "persisted sequence rollback",
        ),
        (
            "release_status_head_fork",
            lambda: validate_status_head_high_water(fork_checkpoint, prior),
            "same high-water fork",
        ),
        (
            "release_status_head_consistency_missing",
            lambda: validate_status_head_high_water(null_advance_checkpoint, prior),
            "null proof on log advancement",
        ),
        (
            "release_status_selected_status_not_current",
            lambda: validate_selected_status_current(
                selected_non_current,
                "selected product release",
            ),
            "selected status is withdrawn",
        ),
        (
            "release_status_head_consistency_proof_invalid",
            lambda: validate_status_merkle_consistency(
                omitted_consistency_node,
                from_endpoint=from_endpoint,
                to_endpoint=to_endpoint,
            ),
            "omitted consistency node",
        ),
        (
            "release_status_head_consistency_proof_invalid",
            lambda: validate_status_merkle_consistency(
                reordered_consistency_nodes,
                from_endpoint=from_endpoint,
                to_endpoint=to_endpoint,
            ),
            "reordered consistency nodes",
        ),
        (
            "release_status_head_consistency_proof_invalid",
            lambda: validate_status_merkle_consistency(
                substituted_consistency_node,
                from_endpoint=from_endpoint,
                to_endpoint=to_endpoint,
            ),
            "substituted consistency node",
        ),
        (
            "release_status_head_consistency_tree_size_mismatch",
            lambda: validate_status_merkle_consistency(
                proof,
                from_endpoint=from_endpoint,
                to_endpoint=wrong_consistency_tree_size,
            ),
            "wrong consistency tree size",
        ),
        (
            "release_status_head_consistency_algorithm_mismatch",
            lambda: validate_status_merkle_consistency(
                wrong_consistency_algorithm,
                from_endpoint=from_endpoint,
                to_endpoint=to_endpoint,
            ),
            "wrong consistency algorithm",
        ),
        (
            "release_status_head_inclusion_algorithm_mismatch",
            lambda: validate_status_merkle_inclusion_proof(
                wrong_inclusion_algorithm
            ),
            "wrong inclusion algorithm",
        ),
    ]
    for mutated, identity in (
        (wrong_inclusion_node, "substituted inclusion node"),
        (reordered_inclusion_nodes, "reordered inclusion nodes"),
        (wrong_inclusion_tree_size, "wrong inclusion tree size"),
        (wrong_inclusion_root, "wrong inclusion root"),
    ):
        cases.append(
            (
                "release_status_head_inclusion_proof_invalid",
                lambda mutated=mutated: validate_status_merkle_inclusion_proof(
                    mutated
                ),
                identity,
            )
        )
    for mutated, identity in (
        (wrong_from_root, "wrong consistency from root"),
        (wrong_to_root, "wrong consistency to root"),
        (wrong_subject, "wrong consistency subject"),
        (wrong_epoch, "wrong consistency epoch"),
    ):
        cases.append(
            (
                "release_status_head_consistency_endpoint_mismatch",
                lambda mutated=mutated: validate_status_consistency_endpoints(
                    mutated,
                    subject_kind="product_release",
                    subject=selection["productRelease"],
                    from_endpoint=from_endpoint,
                    to_endpoint=to_endpoint,
                ),
                identity,
            )
        )
    for expected_error, operation, identity in cases:
        require_semantic_denial(expected_error, operation, identity)
    return len(cases)


def validate_qualification_leaf_binding(
    tree_digest: str,
    tree: dict[str, Any],
    evidence: dict[str, Any],
    predicate: dict[str, Any],
    consumed: set[tuple[str, int]],
) -> dict[str, Any]:
    leaf_index = evidence["evidenceLeafIndex"]
    require(
        isinstance(leaf_index, int) and 0 <= leaf_index < len(tree["leaves"]),
        "qualification_evidence_leaf_missing",
        evidence["evidenceId"],
    )
    leaf = tree["leaves"][leaf_index]
    leaf_use = (tree_digest, leaf_index)
    require(
        leaf_use not in consumed,
        "qualification_evidence_leaf_reused",
        evidence["evidenceId"],
    )
    consumed.add(leaf_use)
    require(
        leaf["requirementId"] == predicate["requirementId"]
        and leaf["role"] == evidence["role"] == predicate["role"]
        and leaf["subjectRole"]
        == evidence["subjectRole"]
        == predicate["subjectRole"]
        and leaf["subject"] == evidence["subject"] == predicate["subject"]
        and leaf["details"] == predicate["details"]
        and leaf["result"] == evidence["result"] == predicate["result"]
        and evidence["evidenceLeafDigest"]
        == predicate["evidenceLeafDigest"]
        == leaf["leafDigest"]
        and evidence["evidenceLeafStatementDigest"]
        == predicate["evidenceLeafStatementDigest"]
        == leaf["statementDigest"]
        and evidence["evidenceLeafSigningResult"]
        == predicate["evidenceLeafSigningResult"]
        == leaf["producerSigningResult"],
        "qualification_evidence_leaf_binding_mismatch",
        evidence["evidenceId"],
    )
    return leaf


def validate_predicate_schema_binding(
    evidence: dict[str, Any],
    predicate: dict[str, Any],
) -> None:
    require(
        evidence["predicate"]["digest"] == canonical_digest(predicate),
        "qualification_predicate_descriptor_mismatch",
        evidence["evidenceId"],
    )
    require(
        evidence["predicateSchema"] == predicate["schema"],
        "qualification_predicate_schema_mismatch",
        evidence["evidenceId"],
    )


def require_semantic_denial(
    expected_code: str,
    operation: Any,
    identity: str,
) -> None:
    try:
        operation()
    except RendererDigestError as error:
        require(
            error.code == expected_code,
            "wrong_qualification_negative_error",
            f"{identity}: expected {expected_code}, observed {error.code}",
        )
    else:
        raise RendererDigestError(
            "qualification_negative_case_accepted",
            f"{identity}: {expected_code}",
        )


def validate_qualification_policy_pin(
    product_release: dict[str, Any],
    qualification: dict[str, Any],
    policy: dict[str, Any],
) -> None:
    require(
        qualification["policy"] == product_release["qualificationPolicy"]
        and policy["qualificationSuite"] == product_release["qualificationSuite"]
        and product_release["minimumQualificationCoverageDigest"]
        == policy["requiredCoverageDigest"],
        "qualification_policy_not_pinned_by_product_release",
        qualification["qualificationId"],
    )


def validate_qualification_policy_scope(
    policy: dict[str, Any],
    suite: dict[str, Any],
) -> None:
    required_scopes = {entry["subjectScope"] for entry in suite["requiredCoverage"]}
    require(
        policy["requireEveryRendererRelease"] is True
        and policy["requireEveryRendererPlatform"] is True
        and "every_renderer_release" in required_scopes
        and "every_renderer_executable" in required_scopes,
        "qualification_policy_scope_incomplete",
        policy["policyId"],
    )


def resolve_permitted_verification_result(
    *,
    digest: str,
    subject: dict[str, Any],
    policy: dict[str, Any],
    evaluated_at: str,
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = resolver.payload(digest)
    result = load_jcs_object(payload, digest)
    validate_schema_instance(
        result,
        VERIFICATION_RESULT_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        result["subject"] == subject
        and result["policy"] == policy
        and result["evaluatedAt"] == evaluated_at
        and result["outcome"] == "permitted"
        and result["reasonCodes"] == []
        and bool(result["evidenceDigests"]),
        "release_status_verification_result_mismatch",
        result.get("verificationId", digest),
    )
    for evidence_digest in result["evidenceDigests"]:
        resolver.payload(evidence_digest)
    return result


def validate_release_status_eligibility(
    *,
    descriptor: dict[str, Any],
    expected_digest: str,
    expected_verification_digest: str,
    expected_stage: str,
    expected_operation_time: str,
    expected_product: dict[str, Any],
    expected_renderers: list[tuple[dict[str, Any], str, str, str, str]],
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    eligibility = resolver.artifact(
        descriptor,
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-eligibility-evidence.v1+json"
        ),
        contract="bytedesk.release-status-eligibility-evidence/1",
        schema_id=RELEASE_STATUS_ELIGIBILITY_SCHEMA_ID,
    )
    require(
        isinstance(eligibility, dict)
        and eligibility["stage"] == expected_stage
        and eligibility["operationTime"] == expected_operation_time
        and eligibility["consumerId"] is None
        and eligibility["decision"] == "eligible"
        and eligibility["eligibilityDigest"] == expected_digest,
        "release_status_eligibility_context_mismatch",
        expected_stage,
    )
    eligibility_schema = schemas[RELEASE_STATUS_ELIGIBILITY_SCHEMA_ID]
    authority = eligibility_schema["x-bytedesk-digestAuthority"]
    require(
        expected_digest
        == domain_digest(
            authority["profile"],
            eligibility,
            set(authority["exclude"]),
        ),
        "release_status_eligibility_digest_mismatch",
        expected_stage,
    )
    pin_set = resolver.trust_policy_pin_set.document
    pin_descriptor = eligibility["pinSet"]
    provider_evidence = eligibility["pinSetProviderEvidence"]
    validate_schema_instance(
        provider_evidence,
        TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        eligibility["pinSetDigest"] == pin_set["pinSetDigest"]
        and pin_descriptor["digest"] == canonical_digest(pin_set)
        and pin_descriptor["size"] == len(rfc8785.dumps(pin_set))
        and provider_evidence["pinSet"] == pin_descriptor
        and provider_evidence["pinSetDigest"] == pin_set["pinSetDigest"]
        and provider_evidence["consumerId"] is None
        and provider_evidence["readback"]["pinSet"] == pin_descriptor
        and provider_evidence["readback"]["rawDigest"]
        == pin_descriptor["digest"]
        and provider_evidence["evidenceDigest"]
        == canonical_digest(
            schema_field_authority_preimage(
                provider_evidence,
                schemas[TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID],
                "evidenceDigest",
            )
        ),
        "release_status_eligibility_pin_provider_mismatch",
        expected_stage,
    )
    operation_time = timestamp(
        eligibility["operationTime"],
        f"{expected_stage}:operation-time",
    )

    expected_entries = [
        (expected_product, None, None, None, None),
        *expected_renderers,
    ]
    actual_entries = [eligibility["product"], *eligibility["renderers"]]
    require(
        len(actual_entries) == len(expected_entries),
        "release_status_eligibility_coverage_mismatch",
        expected_stage,
    )
    for entry, expected in zip(actual_entries, expected_entries, strict=True):
        expected_subject, harness_id, renderer_id, renderer_version, platform = expected
        subject_kind = (
            "product_release" if harness_id is None else "renderer_release"
        )
        require(
            entry["subjectKind"] == subject_kind
            and entry["subject"] == expected_subject
            and (
                harness_id is None
                or (
                    entry["harnessId"] == harness_id
                    and entry["rendererId"] == renderer_id
                    and entry["rendererVersion"] == renderer_version
                    and entry["targetPlatform"] == platform
                )
            ),
            "release_status_eligibility_coverage_mismatch",
            expected_subject["digest"],
        )
        status = resolver.artifact(
            entry["status"],
            media_type=(
                "application/vnd.bytedesk.agent.release-status.v1+json"
            ),
            contract="bytedesk.release-status/1",
            schema_id=RELEASE_STATUS_SCHEMA_ID,
        )
        require(
            isinstance(status, dict),
            "release_status_eligibility_status_unresolved",
            expected_subject["digest"],
        )
        checkpoint, _ = validate_status_head_binding(
            checkpoint_descriptor=entry["checkpoint"],
            authentication_descriptor=entry[
                "checkpointAuthenticationEvidence"
            ],
            subject_kind=subject_kind,
            subject=expected_subject,
            status_descriptor=entry["status"],
            status=status,
            expected_nonce=entry["requestNonce"],
            operation_time=operation_time,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            expected_client_prior_state=entry["clientPriorState"],
        )
        inclusion = resolver.artifact(
            entry["headInclusionProof"],
            media_type=(
                "application/vnd.bytedesk.agent."
                "release-status-log-inclusion-proof.v1+json"
            ),
            contract="bytedesk.release-status-log-inclusion-proof/1",
            schema_id=RELEASE_STATUS_LOG_INCLUSION_PROOF_SCHEMA_ID,
        )
        require(
            isinstance(inclusion, dict)
            and checkpoint["headInclusionProof"] == entry["headInclusionProof"],
            "release_status_eligibility_inclusion_mismatch",
            expected_subject["digest"],
        )
        verification = entry["verificationEvidenceDigests"]
        resolve_permitted_verification_result(
            digest=verification["status"],
            subject=entry["status"],
            policy=entry["status"]["trustPolicy"],
            evaluated_at=expected_operation_time,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )
        resolve_permitted_verification_result(
            digest=verification["checkpointAuthentication"],
            subject=entry["checkpoint"],
            policy=entry["checkpoint"]["trustPolicy"],
            evaluated_at=expected_operation_time,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )
        resolve_permitted_verification_result(
            digest=verification["headInclusionProof"],
            subject=entry["headInclusionProof"],
            policy=entry["headInclusionProof"]["trustPolicy"],
            evaluated_at=expected_operation_time,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )
        require(
            (entry["consistencyProof"] is None)
            == (verification["consistencyProof"] is None),
            "release_status_eligibility_consistency_mismatch",
            expected_subject["digest"],
        )
        if entry["consistencyProof"] is not None:
            resolve_permitted_verification_result(
                digest=verification["consistencyProof"],
                subject=entry["consistencyProof"],
                policy=entry["consistencyProof"]["trustPolicy"],
                evaluated_at=expected_operation_time,
                resolver=resolver,
                registry=registry,
                schemas=schemas,
            )

    validate_signing_result(
        eligibility["signingResult"],
        purpose="release-status-eligibility-v1",
        subject_digest=eligibility["eligibilityDigest"],
        subject_media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-eligibility-evidence-digest.v1+json"
        ),
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=operation_time,
    )
    resolve_permitted_verification_result(
        digest=expected_verification_digest,
        subject=descriptor,
        policy=descriptor["trustPolicy"],
        evaluated_at=expected_operation_time,
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )
    return eligibility


def validate_qualification_graph(
    context: dict[str, Any],
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    graph: GraphAudit,
) -> tuple[int, int]:
    product_release = context["productRelease"]
    product_release_descriptor = context["productReleaseDescriptor"]
    product_distribution_descriptor = product_release["productDistribution"]
    allowlist_descriptor = product_release["compiledAllowlist"]
    qualification = context["qualification"]
    qualification_descriptor = context["qualificationDescriptor"]
    qualification_operation_time = timestamp(
        qualification["qualifiedAt"],
        "qualification:operation-time",
    )
    require(
        qualification["productRelease"] == product_release_descriptor
        and qualification["rendererReleases"] == product_release["rendererReleases"],
        "qualification_release_set_mismatch",
        qualification["qualificationId"],
    )
    policy = resolver.artifact(
        qualification["policy"],
        media_type="application/vnd.bytedesk.agent.release-qualification-policy.v1+json",
        contract="bytedesk.release-qualification-policy/1",
        schema_id=RELEASE_QUALIFICATION_POLICY_SCHEMA_ID,
    )
    suite = resolver.artifact(
        policy["qualificationSuite"],
        media_type="application/vnd.bytedesk.agent.renderer-qualification-suite.v1+json",
        contract="bytedesk.renderer-qualification-suite/1",
        schema_id=QUALIFICATION_SUITE_SCHEMA_ID,
    )
    validate_inline_authority(
        policy,
        schema_id=RELEASE_QUALIFICATION_POLICY_SCHEMA_ID,
        purpose="release-qualification-policy-v1",
        subject_media_type=(
            "application/vnd.bytedesk.agent."
            "release-qualification-policy.v1+json"
        ),
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=qualification_operation_time,
    )
    validate_qualification_policy_pin(product_release, qualification, policy)
    require(
        policy["requiredCoverageDigest"]
        == canonical_digest(
            {
                "profile": QUALIFICATION_COVERAGE_PROFILE,
                "requiredCoverage": suite["requiredCoverage"],
            }
        ),
        "qualification_coverage_digest_mismatch",
        policy["policyId"],
    )
    requirement_ids = [entry["requirementId"] for entry in suite["requiredCoverage"]]
    requirement_pairs = [
        (entry["role"], entry["subjectScope"])
        for entry in suite["requiredCoverage"]
    ]
    require(
        len(requirement_ids) == len(set(requirement_ids))
        and len(requirement_pairs) == len(set(requirement_pairs)),
        "qualification_requirement_ambiguous",
        suite["suiteId"],
    )
    validate_qualification_policy_scope(policy, suite)
    require(
        set(suite["requiredRoles"])
        == {entry["role"] for entry in suite["requiredCoverage"]},
        "qualification_role_matrix_mismatch",
        suite["suiteId"],
    )
    plan = resolver.artifact(
        suite["conformancePlan"],
        media_type="application/vnd.bytedesk.agent.renderer-qualification-plan.v1+json",
    )
    require(
        isinstance(plan, dict)
        and plan.get("profile") == "bytedesk.renderer-qualification-plan/1"
        and plan.get("requiredCoverage") == suite["requiredCoverage"],
        "qualification_plan_matrix_mismatch",
        suite["suiteId"],
    )
    corpus = resolver.artifact(
        suite["inputCorpus"],
        media_type="application/vnd.bytedesk.agent.renderer-qualification-corpus.v1+tar",
    )
    require(isinstance(corpus, bytes) and bool(corpus), "qualification_corpus_empty", suite["suiteId"])
    evaluator = resolver.artifact(
        suite["evaluatorDistribution"],
        media_type="application/vnd.oci.image.manifest.v1+json",
    )
    require(
        isinstance(evaluator, dict)
        and evaluator.get("schemaVersion") == 2
        and evaluator.get("mediaType")
        == "application/vnd.oci.image.manifest.v1+json",
        "qualification_evaluator_invalid",
        suite["suiteId"],
    )
    contract_bundle = resolver.artifact(
        suite["contractBundle"],
        media_type="application/vnd.bytedesk.agent.contract-bundle.v1+json",
        contract="bytedesk.contract-bundle/1",
        schema_id=CONTRACT_BUNDLE_SCHEMA_ID,
    )
    require(
        suite["contractBundle"] == product_release["contractBundle"]
        and isinstance(contract_bundle, dict),
        "qualification_contract_bundle_mismatch",
        suite["suiteId"],
    )

    release_documents: dict[str, dict[str, Any]] = {}
    for descriptor in product_release["rendererReleases"]:
        release = resolver.artifact(
            descriptor,
            media_type="application/vnd.bytedesk.agent.renderer-release.v1+json",
            contract="bytedesk.renderer-release/1",
            schema_id=RELEASE_SCHEMA_ID,
        )
        require(isinstance(release, dict), "renderer_release_unresolved", descriptor["digest"])
        release_documents[descriptor["digest"]] = release

    matrix = resolver.artifact(
        qualification["finalizationMatrix"],
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-qualification-finalization-matrix.v1+json"
        ),
        contract="bytedesk.release-qualification-finalization-matrix/1",
        schema_id=RELEASE_QUALIFICATION_FINALIZATION_MATRIX_SCHEMA_ID,
    )
    require(
        isinstance(matrix, dict)
        and matrix["productRelease"] == product_release_descriptor
        and matrix["qualificationPolicy"] == qualification["policy"]
        and matrix["qualificationSuite"] == policy["qualificationSuite"]
        and matrix["matrixDigest"] == qualification["finalizationMatrixDigest"]
        and matrix["evidence"] == qualification["evidence"],
        "qualification_finalization_matrix_binding_mismatch",
        qualification["qualificationId"],
    )
    matrix_authority = schemas[
        RELEASE_QUALIFICATION_FINALIZATION_MATRIX_SCHEMA_ID
    ]["x-bytedesk-digestAuthority"]
    require(
        matrix["matrixDigest"]
        == domain_digest(
            matrix_authority["profile"],
            matrix,
            set(matrix_authority["exclude"]),
        ),
        "qualification_finalization_matrix_digest_mismatch",
        qualification["qualificationId"],
    )
    expected_eligibility_renderers = sorted(
        [
            (
                descriptor,
                release["harnessId"],
                release["rendererId"],
                release["version"],
                f"{platform['os']}/{platform['architecture']}",
            )
            for descriptor in product_release["rendererReleases"]
            for release in [release_documents[descriptor["digest"]]]
            for platform in release["platforms"]
        ],
        key=lambda entry: (
            entry[1].encode("utf-8"),
            entry[2].encode("utf-8"),
            entry[3].encode("utf-8"),
            entry[4].encode("utf-8"),
            entry[0]["digest"].encode("utf-8"),
        ),
    )
    qualification_eligibility = validate_release_status_eligibility(
        descriptor=qualification["qualificationStatusEligibility"],
        expected_digest=qualification["qualificationStatusEligibilityDigest"],
        expected_verification_digest=qualification[
            "qualificationStatusEligibilityVerificationDigest"
        ],
        expected_stage="qualification_finalization",
        expected_operation_time=qualification["qualifiedAt"],
        expected_product=product_release_descriptor,
        expected_renderers=expected_eligibility_renderers,
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )
    require(
        qualification["pinSetDigest"]
        == qualification_eligibility["pinSetDigest"]
        and qualification["pinSetProviderEvidenceDigest"]
        == qualification_eligibility["pinSetProviderEvidence"][
            "evidenceDigest"
        ],
        "qualification_pin_provider_binding_mismatch",
        qualification["qualificationId"],
    )
    resolve_permitted_verification_result(
        digest=qualification["policyVerificationDigest"],
        subject=qualification["policy"],
        policy=qualification["policy"]["trustPolicy"],
        evaluated_at=qualification["qualifiedAt"],
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )
    resolve_permitted_verification_result(
        digest=qualification["suiteVerificationDigest"],
        subject=policy["qualificationSuite"],
        policy=policy["qualificationSuite"]["trustPolicy"],
        evaluated_at=qualification["qualifiedAt"],
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )

    expected: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for requirement in suite["requiredCoverage"]:
        scope = requirement["subjectScope"]
        subjects: list[dict[str, Any]] = []
        if scope == "product_release":
            subjects = [product_release_descriptor]
        elif scope == "product_distribution":
            subjects = [product_distribution_descriptor]
        elif scope == "contract_bundle":
            subjects = [product_release["contractBundle"]]
        elif scope == "every_renderer_release":
            subjects = product_release["rendererReleases"]
        elif scope == "every_renderer_executable":
            subjects = [
                platform["distribution"]
                for release in release_documents.values()
                for platform in release["platforms"]
            ]
        else:
            raise RendererDigestError("qualification_scope_unknown", scope)
        for subject in subjects:
            key = (
                requirement["requirementId"],
                requirement["role"],
                requirement["subjectRole"],
                subject["digest"],
            )
            require(key not in expected, "qualification_expected_duplicate", str(key))
            expected[key] = subject

    actual: set[tuple[str, str, str, str]] = set()
    evidence_trees: dict[str, dict[str, Any]] = {}
    consumed_evidence_leaves: set[tuple[str, int]] = set()
    observed_matrix_entries: dict[tuple[str, str], dict[str, Any]] = {}
    denial_sample: tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    for evidence_descriptor in qualification["evidence"]:
        evidence = resolver.artifact(
            evidence_descriptor,
            media_type="application/vnd.bytedesk.agent.release-qualification-evidence.v1+json",
            contract="bytedesk.release-qualification-evidence/1",
            schema_id=RELEASE_QUALIFICATION_EVIDENCE_SCHEMA_ID,
        )
        predicate = resolver.artifact(
            evidence["predicate"],
            media_type="application/vnd.bytedesk.agent.release-qualification-predicate.v1+json",
            contract="bytedesk.release-qualification-predicate/1",
            schema_id=RELEASE_QUALIFICATION_PREDICATE_SCHEMA_ID,
        )
        key = (
            predicate["requirementId"],
            evidence["role"],
            evidence["subjectRole"],
            evidence["subject"]["digest"],
        )
        require(key in expected, "qualification_unexpected_evidence", str(key))
        require(key not in actual, "qualification_duplicate_evidence", str(key))
        actual.add(key)
        validate_predicate_schema_binding(evidence, predicate)
        require(
            evidence["subject"] == expected[key]
            and predicate["subject"] == evidence["subject"]
            and predicate["role"] == evidence["role"]
            and predicate["subjectRole"] == evidence["subjectRole"]
            and predicate["result"] == evidence["result"] == "pass",
            "qualification_predicate_subject_mismatch",
            evidence["evidenceId"],
        )
        selection = resolver.artifact(
            evidence["qualificationSelection"],
            media_type="application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json",
            contract="bytedesk.renderer-qualification-selection/1",
            schema_id=QUALIFICATION_SELECTION_SCHEMA_ID,
        )
        require(
            selection["selectionDigest"]
            == domain_digest(
                "bytedesk.renderer-qualification-selection-digest/1",
                selection,
                {"contract", "schema", "selectionDigest"},
            ),
            "qualification_selection_digest_mismatch",
            evidence["evidenceId"],
        )
        require(
            selection["qualificationSuite"] == policy["qualificationSuite"]
            and selection["conformancePlan"] == suite["conformancePlan"]
            and selection["inputCorpus"] == suite["inputCorpus"]
            and selection["evaluatorDistribution"] == suite["evaluatorDistribution"]
            and selection["contractBundle"] == suite["contractBundle"]
            and selection["qualificationWorkerProfileDigest"]
            == suite["qualificationWorkerProfileDigest"]
            and selection["qualificationProtocolProfileDigest"]
            == suite["qualificationProtocolProfileDigest"]
            and selection["sandboxProfileDigest"] == suite["sandboxProfileDigest"]
            and selection["resourceProfileDigest"] == suite["resourceProfileDigest"]
            and selection["timeoutProfileDigest"] == suite["timeoutProfileDigest"],
            "qualification_selection_suite_mismatch",
            evidence["evidenceId"],
        )
        require(
            selection["productRelease"] == product_release_descriptor
            and selection["productDistribution"] == product_distribution_descriptor
            and selection["compiledAllowlist"] == allowlist_descriptor
            and selection["rendererRelease"]["digest"] in release_documents,
            "qualification_selection_release_mismatch",
            evidence["evidenceId"],
        )
        selected_release = release_documents[selection["rendererRelease"]["digest"]]
        require(
            selection["capability"] == selected_release["capabilityManifest"],
            "qualification_selection_capability_mismatch",
            evidence["evidenceId"],
        )
        platforms = [
            platform
            for platform in selected_release["platforms"]
            if f"{platform['os']}/{platform['architecture']}"
            == selection["targetPlatform"]
        ]
        require(
            len(platforms) == 1
            and platforms[0]["distribution"] == selection["executableDistribution"],
            "qualification_selection_executable_mismatch",
            evidence["evidenceId"],
        )
        attempt = resolver.artifact(
            evidence["qualificationAttempt"],
            media_type="application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
            contract="bytedesk.renderer-qualification-attempt/1",
            schema_id=QUALIFICATION_ATTEMPT_SCHEMA_ID,
        )
        require(
            attempt["authorityDigest"]
            == domain_digest(
                "bytedesk.renderer-qualification-attempt-digest/1",
                attempt,
                {"contract", "schema", "authorityDigest"},
            )
            and attempt["qualificationSelectionDigest"] == selection["selectionDigest"]
            and attempt["contractBundleDigest"] == suite["contractBundle"]["digest"]
            and attempt["qualificationSuiteDigest"]
            == policy["qualificationSuite"]["digest"]
            and attempt["conformancePlanDigest"] == suite["conformancePlan"]["digest"]
            and attempt["inputCorpusDigest"] == suite["inputCorpus"]["digest"]
            and attempt["evaluatorDistributionDigest"]
            == suite["evaluatorDistribution"]["digest"]
            and attempt["qualificationWorkerProfileDigest"]
            == suite["qualificationWorkerProfileDigest"]
            and attempt["qualificationProtocolProfileDigest"]
            == suite["qualificationProtocolProfileDigest"]
            and attempt["sandboxProfileDigest"] == suite["sandboxProfileDigest"]
            and attempt["resourceProfileDigest"] == suite["resourceProfileDigest"]
            and attempt["timeoutProfileDigest"] == suite["timeoutProfileDigest"],
            "qualification_attempt_mismatch",
            evidence["evidenceId"],
        )
        attempt_auth = resolver.artifact(
            evidence["qualificationAttemptAuthenticationEvidence"],
            media_type="application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json",
            contract="bytedesk.renderer-qualification-attempt-authentication-evidence/1",
            schema_id=QUALIFICATION_ATTEMPT_AUTH_SCHEMA_ID,
        )
        require(
            attempt_auth["evidenceDigest"]
            == domain_digest(
                "bytedesk.renderer-qualification-attempt-authentication-evidence-digest/1",
                attempt_auth,
                {"contract", "schema", "evidenceDigest"},
            )
            and attempt_auth["attemptAuthorityDigest"] == attempt["authorityDigest"]
            and attempt_auth["issuerIdentityDigest"] == attempt["issuerIdentityDigest"],
            "qualification_attempt_auth_mismatch",
            evidence["evidenceId"],
        )
        receipt = resolver.artifact(
            evidence["qualificationReceipt"],
            media_type="application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
            contract="bytedesk.renderer-qualification-receipt/1",
            schema_id=QUALIFICATION_RECEIPT_SCHEMA_ID,
        )
        require(
            receipt["attemptId"] == attempt["attemptId"]
            and receipt["attemptFencingToken"] == attempt["attemptFencingToken"]
            and receipt["attemptAuthorityDigest"] == attempt["authorityDigest"]
            and receipt["attemptAuthenticationEvidenceDigest"]
            == attempt_auth["evidenceDigest"]
            and receipt["qualificationSelectionDigest"] == selection["selectionDigest"]
            and receipt["rendererReleaseDigest"] == selection["rendererRelease"]["digest"]
            and receipt["platform"] == selection["targetPlatform"]
            and receipt["executedDistribution"] == selection["executableDistribution"]
            and receipt["contractBundleDigest"] == attempt["contractBundleDigest"]
            and receipt["qualificationSuiteDigest"] == attempt["qualificationSuiteDigest"]
            and receipt["conformancePlanDigest"] == attempt["conformancePlanDigest"]
            and receipt["inputCorpusDigest"] == attempt["inputCorpusDigest"]
            and receipt["evaluatorDistribution"] == suite["evaluatorDistribution"]
            and receipt["qualificationWorkerProfileDigest"]
            == attempt["qualificationWorkerProfileDigest"]
            and receipt["qualificationProtocolProfileDigest"]
            == attempt["qualificationProtocolProfileDigest"]
            and receipt["sandboxProfileDigest"] == attempt["sandboxProfileDigest"]
            and receipt["resourceProfileDigest"] == attempt["resourceProfileDigest"]
            and receipt["timeoutProfileDigest"] == attempt["timeoutProfileDigest"]
            and receipt["rendererWorkerProfileDigest"] == selection["workerProfileDigest"]
            and timestamp(attempt["issuedAt"], f"{evidence['evidenceId']}:issuedAt")
            <= timestamp(receipt["completedAt"], f"{evidence['evidenceId']}:completedAt")
            < timestamp(attempt["expiresAt"], f"{evidence['evidenceId']}:expiresAt"),
            "qualification_receipt_mismatch",
            evidence["evidenceId"],
        )
        validate_signing_result(
            attempt_auth["signingResult"],
            purpose="release-qualification-attempt-v1",
            subject_digest=attempt["authorityDigest"],
            subject_media_type="application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=timestamp(
                receipt["completedAt"],
                f"{evidence['evidenceId']}:attempt-signature-use",
            ),
        )
        receipt_auth = resolver.artifact(
            evidence["qualificationReceiptAuthenticationEvidence"],
            media_type="application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json",
            contract="bytedesk.renderer-qualification-receipt-authentication-evidence/1",
            schema_id=QUALIFICATION_RECEIPT_AUTH_SCHEMA_ID,
        )
        receipt_digest = evidence["qualificationReceipt"]["digest"]
        require(
            receipt_auth["evidenceDigest"]
            == domain_digest(
                "bytedesk.renderer-qualification-receipt-authentication-evidence-digest/1",
                receipt_auth,
                {"contract", "schema", "evidenceDigest"},
            )
            and receipt_auth["receiptDigest"] == receipt_digest
            and receipt_auth["qualificationSelectionDigest"]
            == selection["selectionDigest"]
            and receipt_auth["launcherIdentityDigest"]
            == receipt["launcherIdentityDigest"],
            "qualification_receipt_auth_mismatch",
            evidence["evidenceId"],
        )
        validate_signing_result(
            receipt_auth["signingResult"],
            purpose="release-qualification-receipt-v1",
            subject_digest=receipt_digest,
            subject_media_type="application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=timestamp(
                qualification["qualifiedAt"],
                f"{evidence['evidenceId']}:receipt-signature-use",
            ),
        )
        matrix_key = (
            selection["rendererRelease"]["digest"],
            selection["targetPlatform"],
        )
        matrix_entry = {
            "rendererRelease": deepcopy(selection["rendererRelease"]),
            "platform": selection["targetPlatform"],
            "qualificationSelection": deepcopy(
                evidence["qualificationSelection"]
            ),
            "qualificationAttempt": deepcopy(evidence["qualificationAttempt"]),
            "qualificationAttemptAuthenticationEvidence": deepcopy(
                evidence["qualificationAttemptAuthenticationEvidence"]
            ),
            "qualificationReceipt": deepcopy(evidence["qualificationReceipt"]),
            "qualificationReceiptAuthenticationEvidence": deepcopy(
                evidence["qualificationReceiptAuthenticationEvidence"]
            ),
        }
        previous_matrix_entry = observed_matrix_entries.setdefault(
            matrix_key, matrix_entry
        )
        require(
            previous_matrix_entry == matrix_entry,
            "qualification_finalization_matrix_execution_mismatch",
            str(matrix_key),
        )
        tree_descriptor = receipt["evidenceTree"]
        require(
            tree_descriptor["digest"] == receipt["evidenceTreeDigest"]
            and evidence["evidenceTree"] == tree_descriptor
            and predicate["evidenceTree"] == tree_descriptor,
            "qualification_evidence_tree_binding_mismatch",
            evidence["evidenceId"],
        )
        tree_digest = tree_descriptor["digest"]
        if tree_digest not in evidence_trees:
            tree = resolver.artifact(
                tree_descriptor,
                media_type="application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json",
                contract="bytedesk.renderer-qualification-evidence-tree/1",
                schema_id=QUALIFICATION_EVIDENCE_TREE_SCHEMA_ID,
            )
            require(isinstance(tree, dict), "qualification_evidence_tree_invalid", tree_digest)
            require(
                tree["treeDigest"]
                == domain_digest(
                    "bytedesk.renderer-qualification-evidence-tree-digest/1",
                    tree,
                    {"contract", "schema", "treeDigest"},
                )
                and tree["qualificationSelectionDigest"]
                == selection["selectionDigest"]
                and tree["qualificationSuite"] == policy["qualificationSuite"]
                and tree["attemptAuthorityDigest"] == attempt["authorityDigest"]
                and tree["platform"] == receipt["platform"]
                and tree["executedDistribution"] == receipt["executedDistribution"]
                and tree["collectorIdentityDigest"] == receipt["launcherIdentityDigest"],
                "qualification_evidence_tree_mismatch",
                tree_digest,
            )
            require(
                [leaf["index"] for leaf in tree["leaves"]]
                == list(range(len(tree["leaves"]))),
                "qualification_evidence_leaf_index_mismatch",
                tree_digest,
            )
            leaf_keys: set[tuple[str, str, str, str]] = set()
            for leaf in tree["leaves"]:
                statement = {
                    "profile": "bytedesk.renderer-qualification-evidence-leaf-statement/1",
                    "requirementId": leaf["requirementId"],
                    "role": leaf["role"],
                    "subjectRole": leaf["subjectRole"],
                    "subject": leaf["subject"],
                    "details": leaf["details"],
                    "result": leaf["result"],
                }
                require(
                    leaf["statementDigest"] == canonical_digest(statement)
                    and leaf["leafDigest"]
                    == domain_digest(
                        "bytedesk.renderer-qualification-evidence-leaf-digest/1",
                        leaf,
                        {"leafDigest"},
                    ),
                    "qualification_evidence_leaf_digest_mismatch",
                    f"{tree_digest}:{leaf['index']}",
                )
                validate_signing_result(
                    leaf["producerSigningResult"],
                    purpose="release-qualification-evidence-v1",
                    subject_digest=leaf["statementDigest"],
                    subject_media_type="application/vnd.bytedesk.agent.renderer-qualification-evidence-leaf-statement.v1+json",
                    resolver=resolver,
                    registry=registry,
                    schemas=schemas,
                    verification_time=timestamp(
                        receipt["completedAt"],
                        f"{evidence['evidenceId']}:evidence-signature-use",
                    ),
                )
                leaf_key = (
                    leaf["requirementId"],
                    leaf["role"],
                    leaf["subjectRole"],
                    leaf["subject"]["digest"],
                )
                require(
                    leaf_key not in leaf_keys,
                    "qualification_evidence_leaf_duplicate",
                    str(leaf_key),
                )
                leaf_keys.add(leaf_key)
            evidence_trees[tree_digest] = tree
        tree = evidence_trees[tree_digest]
        validate_qualification_leaf_binding(
            tree_digest,
            tree,
            evidence,
            predicate,
            consumed_evidence_leaves,
        )
        if denial_sample is None:
            denial_sample = (
                tree_digest,
                deepcopy(tree),
                deepcopy(evidence),
                deepcopy(predicate),
            )
        details = resolver.artifact(
            predicate["details"],
            media_type="application/vnd.bytedesk.agent.release-qualification-details.v1+json",
        )
        require(
            isinstance(details, dict)
            and details.get("requirementId") == predicate["requirementId"]
            and details.get("role") == predicate["role"]
            and details.get("subjectRole") == predicate["subjectRole"]
            and details.get("subjectDigest") == predicate["subject"]["digest"]
            and details.get("qualificationSelectionDigest")
            == selection["selectionDigest"]
            and details.get("result") == "pass"
            and predicate["qualificationSuite"] == policy["qualificationSuite"]
            and predicate["qualificationSelectionDigest"]
            == selection["selectionDigest"]
            and predicate["qualificationReceiptDigest"] == receipt_digest
            and predicate["conformancePlanDigest"] == suite["conformancePlan"]["digest"]
            and predicate["inputCorpusDigest"] == suite["inputCorpus"]["digest"]
            and predicate["evaluatorDistribution"] == suite["evaluatorDistribution"]
            and timestamp(evidence["observedAt"], f"{evidence['evidenceId']}:observedAt")
            <= timestamp(qualification["qualifiedAt"], "qualification:qualifiedAt")
            and timestamp(evidence["expiresAt"], f"{evidence['evidenceId']}:expiresAt")
            >= timestamp(qualification["expiresAt"], "qualification:expiresAt"),
            "qualification_predicate_material_mismatch",
            evidence["evidenceId"],
        )

        graph.edge(evidence["qualificationSelection"]["digest"], 5, product_release_descriptor["digest"], 4, "QS->M")
        graph.edge(evidence["qualificationAttempt"]["digest"], 6, evidence["qualificationSelection"]["digest"], 5, "Tq->QS")
        graph.edge(evidence["qualificationAttemptAuthenticationEvidence"]["digest"], 7, evidence["qualificationAttempt"]["digest"], 6, "TqAuth->Tq")
        graph.edge(evidence["qualificationReceipt"]["digest"], 8, evidence["qualificationAttemptAuthenticationEvidence"]["digest"], 7, "Qq->TqAuth")
        graph.edge(evidence["qualificationReceiptAuthenticationEvidence"]["digest"], 9, evidence["qualificationReceipt"]["digest"], 8, "QqAuth->Qq")
        graph.edge(evidence["predicate"]["digest"], 10, evidence["qualificationReceiptAuthenticationEvidence"]["digest"], 9, "predicate->QqAuth")
        graph.edge(evidence_descriptor["digest"], 11, evidence["predicate"]["digest"], 10, "E->predicate")
        graph.edge(qualification_descriptor["digest"], 12, evidence_descriptor["digest"], 11, "G->E")

    expected_leaf_uses = {
        (tree_digest, leaf["index"])
        for tree_digest, tree in evidence_trees.items()
        for leaf in tree["leaves"]
    }
    require(
        consumed_evidence_leaves == expected_leaf_uses,
        "qualification_evidence_leaf_coverage_incomplete",
        f"expected={len(expected_leaf_uses)} actual={len(consumed_evidence_leaves)}",
    )
    require(actual == set(expected), "qualification_coverage_incomplete", f"expected={len(expected)} actual={len(actual)}")
    expected_matrix_entries = sorted(
        observed_matrix_entries.values(),
        key=lambda entry: (
            entry["rendererRelease"]["digest"].encode("utf-8"),
            entry["platform"].encode("utf-8"),
        ),
    )
    require(
        matrix["rendererEntries"] == expected_matrix_entries
        and len(expected_matrix_entries) == len(expected_eligibility_renderers),
        "qualification_finalization_matrix_coverage_mismatch",
        qualification["qualificationId"],
    )
    require(
        qualification["decision"] == "qualified"
        and timestamp(qualification["qualifiedAt"], "qualification:qualifiedAt")
        < timestamp(qualification["expiresAt"], "qualification:expiresAt"),
        "qualification_decision_invalid",
        qualification["qualificationId"],
    )
    require(denial_sample is not None, "qualification_denial_sample_missing", "evidence")
    sample_tree_digest, sample_tree, sample_evidence, sample_predicate = denial_sample

    missing_leaf_evidence = deepcopy(sample_evidence)
    missing_leaf_evidence["evidenceLeafIndex"] = len(sample_tree["leaves"])
    tampered_digest_evidence = deepcopy(sample_evidence)
    tampered_digest_evidence["evidenceLeafDigest"] = "sha256:" + ("00" * 32)
    cross_role_evidence = deepcopy(sample_evidence)
    cross_role_predicate = deepcopy(sample_predicate)
    cross_role = next(
        role
        for role in (
            "provenance",
            "sbom",
            "vulnerability",
            "malware",
            "secret_scan",
            "scan_completeness",
            "license",
            "conformance",
            "compatibility",
            "determinism",
            "sandbox",
            "executed_distribution",
        )
        if role != sample_evidence["role"]
    )
    cross_role_evidence["role"] = cross_role
    cross_role_predicate["role"] = cross_role
    substituted_schema_predicate = deepcopy(sample_predicate)
    substituted_schema_predicate["schema"] = deepcopy(sample_evidence["schema"])
    substituted_schema_evidence = deepcopy(sample_evidence)
    substituted_schema_evidence["predicate"]["digest"] = canonical_digest(
        substituted_schema_predicate
    )

    def reject_reused_leaf() -> None:
        consumed: set[tuple[str, int]] = set()
        validate_qualification_leaf_binding(
            sample_tree_digest,
            sample_tree,
            sample_evidence,
            sample_predicate,
            consumed,
        )
        validate_qualification_leaf_binding(
            sample_tree_digest,
            sample_tree,
            sample_evidence,
            sample_predicate,
            consumed,
        )

    weaker_product_release = deepcopy(product_release)
    weaker_product_release["qualificationPolicy"] = {
        **weaker_product_release["qualificationPolicy"],
        "digest": "sha256:" + ("11" * 32),
    }
    substituted_coverage_release = deepcopy(product_release)
    substituted_coverage_release["minimumQualificationCoverageDigest"] = (
        "sha256:" + ("22" * 32)
    )
    omitted_scope_suite = deepcopy(suite)
    omitted_scope_suite["requiredCoverage"] = [
        entry
        for entry in omitted_scope_suite["requiredCoverage"]
        if entry["subjectScope"] != "every_renderer_executable"
    ]
    weaker_policy = deepcopy(policy)
    weaker_policy["requireEveryRendererPlatform"] = False
    tampered_finalization_matrix = deepcopy(matrix)
    tampered_finalization_matrix["rendererEntries"] = (
        tampered_finalization_matrix["rendererEntries"][:-1]
    )
    wrong_stage_eligibility = deepcopy(qualification_eligibility)
    wrong_stage_eligibility["stage"] = "public_render_finalization"
    missing_renderer_eligibility = deepcopy(qualification_eligibility)
    missing_renderer_eligibility["renderers"] = (
        missing_renderer_eligibility["renderers"][:-1]
    )
    mismatched_pin_qualification = deepcopy(qualification)
    mismatched_pin_qualification["pinSetDigest"] = "sha256:" + ("33" * 32)
    substituted_policy_verification = deepcopy(qualification)
    substituted_policy_verification["policyVerificationDigest"] = (
        "sha256:" + ("44" * 32)
    )

    negative_cases: list[tuple[str, Any, str]] = [
        (
            "qualification_evidence_leaf_missing",
            lambda: validate_qualification_leaf_binding(
                sample_tree_digest,
                sample_tree,
                missing_leaf_evidence,
                sample_predicate,
                set(),
            ),
            "missing evidence leaf",
        ),
        (
            "qualification_evidence_leaf_binding_mismatch",
            lambda: validate_qualification_leaf_binding(
                sample_tree_digest,
                sample_tree,
                tampered_digest_evidence,
                sample_predicate,
                set(),
            ),
            "tampered evidence leaf digest",
        ),
        (
            "qualification_evidence_leaf_reused",
            reject_reused_leaf,
            "reused evidence leaf",
        ),
        (
            "qualification_evidence_leaf_binding_mismatch",
            lambda: validate_qualification_leaf_binding(
                sample_tree_digest,
                sample_tree,
                cross_role_evidence,
                cross_role_predicate,
                set(),
            ),
            "cross-role evidence leaf",
        ),
        (
            "qualification_predicate_schema_mismatch",
            lambda: validate_predicate_schema_binding(
                substituted_schema_evidence,
                substituted_schema_predicate,
            ),
            "recomputed predicate descriptor with substituted schema",
        ),
        (
            "qualification_policy_not_pinned_by_product_release",
            lambda: validate_qualification_policy_pin(
                weaker_product_release,
                qualification,
                policy,
            ),
            "unapproved qualification policy",
        ),
        (
            "qualification_policy_not_pinned_by_product_release",
            lambda: validate_qualification_policy_pin(
                substituted_coverage_release,
                qualification,
                policy,
            ),
            "substituted minimum coverage digest",
        ),
        (
            "qualification_policy_scope_incomplete",
            lambda: validate_qualification_policy_scope(policy, omitted_scope_suite),
            "omitted executable coverage scope",
        ),
        (
            "qualification_policy_scope_incomplete",
            lambda: validate_qualification_policy_scope(weaker_policy, suite),
            "weakened every-platform policy",
        ),
        (
            "qualification_finalization_matrix_digest_mismatch",
            lambda: require(
                tampered_finalization_matrix["matrixDigest"]
                == domain_digest(
                    matrix_authority["profile"],
                    tampered_finalization_matrix,
                    set(matrix_authority["exclude"]),
                ),
                "qualification_finalization_matrix_digest_mismatch",
                "matrix renderer omitted",
            ),
            "finalization matrix renderer omission",
        ),
        (
            "release_status_eligibility_context_mismatch",
            lambda: require(
                wrong_stage_eligibility["stage"]
                == "qualification_finalization"
                and wrong_stage_eligibility["operationTime"]
                == qualification["qualifiedAt"],
                "release_status_eligibility_context_mismatch",
                "wrong qualification eligibility stage",
            ),
            "public-finalization eligibility substituted into qualification",
        ),
        (
            "release_status_eligibility_coverage_mismatch",
            lambda: require(
                len(missing_renderer_eligibility["renderers"])
                == len(expected_eligibility_renderers),
                "release_status_eligibility_coverage_mismatch",
                "qualification renderer omitted",
            ),
            "qualification eligibility renderer omission",
        ),
        (
            "qualification_pin_provider_binding_mismatch",
            lambda: require(
                mismatched_pin_qualification["pinSetDigest"]
                == qualification_eligibility["pinSetDigest"],
                "qualification_pin_provider_binding_mismatch",
                "qualification pin-set substitution",
            ),
            "qualification pin-set digest substitution",
        ),
        (
            "qualification_policy_verification_mismatch",
            lambda: require(
                substituted_policy_verification["policyVerificationDigest"]
                == qualification["policyVerificationDigest"],
                "qualification_policy_verification_mismatch",
                "qualification policy verification substitution",
            ),
            "qualification policy verification substitution",
        ),
    ]
    for expected_error, operation, identity in negative_cases:
        require_semantic_denial(expected_error, operation, identity)
    return len(actual), len(negative_cases)


def validate_execution_receipt_bindings(
    bindings: list[dict[str, Any]],
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    resolver: RendererCasResolver,
    graph: GraphAudit,
) -> int:
    seen: set[str] = set()
    for binding in bindings:
        require(
            set(binding)
            == {
                "bindingId",
                "selectionPath",
                "attemptAuthorityPath",
                "attemptAuthenticationEvidencePath",
                "receiptPath",
                "authenticationEvidencePath",
                "manifestPath",
                "framedRequestPath",
                "framedResponsePath",
            },
            "invalid_execution_binding",
            "fields",
        )
        binding_id = binding["bindingId"]
        require(
            isinstance(binding_id, str) and binding_id and binding_id not in seen,
            "invalid_execution_binding",
            str(binding_id),
        )
        seen.add(binding_id)
        selection = load_json(REPOSITORY_ROOT / binding["selectionPath"])
        authority = load_json(REPOSITORY_ROOT / binding["attemptAuthorityPath"])
        attempt_auth = load_json(
            REPOSITORY_ROOT / binding["attemptAuthenticationEvidencePath"]
        )
        receipt = load_json(REPOSITORY_ROOT / binding["receiptPath"])
        authentication = load_json(
            REPOSITORY_ROOT / binding["authenticationEvidencePath"]
        )
        manifest = load_json(REPOSITORY_ROOT / binding["manifestPath"])
        validate_schema_instance(
            selection,
            RENDERER_SELECTION_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_instance(
            authority,
            RENDERER_ATTEMPT_AUTHORITY_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_instance(
            attempt_auth,
            RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_instance(
            receipt,
            RENDERER_EXECUTION_RECEIPT_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_instance(
            authentication,
            RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_instance(manifest, MANIFEST_SCHEMA_ID, registry, schemas)
        require(
            selection["selectionDigest"]
            == canonical_digest(renderer_selection_preimage(selection)),
            "renderer_selection_digest_mismatch",
            binding_id,
        )
        for document in (selection, authority, attempt_auth, receipt, authentication, manifest):
            canonical = rfc8785.dumps(document)
            resolver.payload(raw_digest(canonical), len(canonical))
        request_frame = (REPOSITORY_ROOT / binding["framedRequestPath"]).read_bytes()
        response_frame = (REPOSITORY_ROOT / binding["framedResponsePath"]).read_bytes()
        for frame, frame_name in (
            (request_frame, "request"),
            (response_frame, "response"),
        ):
            require(len(frame) >= 4, "renderer_frame_truncated", f"{binding_id}:{frame_name}")
            declared = int.from_bytes(frame[:4], "big")
            require(
                declared == len(frame) - 4 and declared <= 16 * 1024 * 1024,
                "renderer_frame_length_mismatch",
                f"{binding_id}:{frame_name}",
            )
            load_jcs_object(frame[4:], f"{binding_id}:{frame_name}")
        request_payload = load_jcs_object(request_frame[4:], f"{binding_id}:request")
        functional_inputs = request_payload.get("functionalInputs")
        portable_definition = request_payload.get("portableDefinition")
        require(
            set(request_payload)
            == {
                "profile",
                "rendererSelection",
                "portableDefinition",
                "portableDefinitionDigest",
                "functionalInputs",
                "inputTreeDigest",
                "contractBundleDigest",
            }
            and request_payload["profile"]
            == "bytedesk.renderer-production-request-frame/1"
            and request_payload["rendererSelection"] == selection
            and isinstance(portable_definition, dict)
            and isinstance(functional_inputs, dict)
            and request_payload["portableDefinitionDigest"]
            == authority["portableDefinitionDigest"]
            == canonical_digest(
                {
                    "profile": "bytedesk.renderer-portable-definition/1",
                    **portable_definition,
                }
            )
            and request_payload["inputTreeDigest"]
            == authority["inputTreeDigest"]
            == canonical_digest(
                {
                    "profile": "bytedesk.renderer-production-input-tree/1",
                    "functionalInputs": functional_inputs,
                }
            )
            and request_payload["contractBundleDigest"]
            == authority["contractBundleDigest"]
            and authority["framedRequestDigest"] == raw_digest(request_frame),
            "renderer_request_frame_mismatch",
            binding_id,
        )
        validate_schema_instance(
            functional_inputs["inputParameters"],
            selection["rendererSchemas"]["inputParameters"]["id"],
            registry,
            schemas,
        )
        validate_schema_instance(
            functional_inputs["harnessConfiguration"],
            selection["rendererSchemas"]["harnessConfiguration"]["id"],
            registry,
            schemas,
        )
        require(
            portable_definition
            == {
                "source": manifest["source"],
                "sourceKind": manifest["sourceKind"],
                "agentSpecVersion": manifest["agentSpecVersion"],
            }
            and functional_inputs["scope"] == manifest["scope"]
            and functional_inputs["source"] == manifest["source"]
            and functional_inputs["sourceKind"] == manifest["sourceKind"]
            and functional_inputs["agentSpecVersion"] == manifest["agentSpecVersion"]
            and functional_inputs["bindingDigest"] == manifest.get("bindingDigest")
            and functional_inputs["customizationDigest"]
            == manifest.get("customizationDigest")
            and functional_inputs["publicSkills"] == manifest["publicSkills"]
            and functional_inputs["privateSkills"] == manifest["privateSkills"]
            and functional_inputs["normalizationProfile"]
            == manifest["normalizationProfile"]
            and functional_inputs["outputArchiveProfile"]
            == manifest["outputArchiveProfile"],
            "renderer_request_functional_input_mismatch",
            binding_id,
        )
        require(
            authority["authorityDigest"]
            == canonical_digest(renderer_attempt_authority_preimage(authority))
            and authority["rendererSelectionDigest"] == selection["selectionDigest"]
            and authority["productReleaseStatusCheckpointDigest"]
            == selection["productReleaseStatusCheckpoint"]["digest"]
            and authority[
                "productReleaseStatusCheckpointAuthenticationEvidenceDigest"
            ]
            == selection[
                "productReleaseStatusCheckpointAuthenticationEvidence"
            ]["digest"]
            and authority["productReleaseStatusRequestNonce"]
            == selection["productReleaseStatusRequestNonce"]
            and authority["rendererReleaseStatusCheckpointDigest"]
            == selection["rendererReleaseStatusCheckpoint"]["digest"]
            and authority[
                "rendererReleaseStatusCheckpointAuthenticationEvidenceDigest"
            ]
            == selection[
                "rendererReleaseStatusCheckpointAuthenticationEvidence"
            ]["digest"]
            and authority["rendererReleaseStatusRequestNonce"]
            == selection["rendererReleaseStatusRequestNonce"],
            "renderer_attempt_authority_mismatch",
            binding_id,
        )
        require(
            attempt_auth["evidenceDigest"]
            == canonical_digest(attempt_authentication_evidence_preimage(attempt_auth))
            and attempt_auth["attemptAuthorityDigest"] == authority["authorityDigest"]
            and attempt_auth["issuerIdentityDigest"] == authority["issuerIdentityDigest"],
            "renderer_attempt_authentication_mismatch",
            binding_id,
        )
        validate_signing_result(
            attempt_auth["signingResult"],
            purpose="renderer-attempt-v1",
            subject_digest=authority["authorityDigest"],
            subject_media_type="application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=timestamp(
                authority["issuedAt"],
                f"{binding_id}:attempt-signature-use",
            ),
        )
        qualification = resolver.artifact(
            selection["releaseQualification"],
            media_type="application/vnd.bytedesk.agent.release-qualification.v1+json",
            contract="bytedesk.release-qualification/1",
            schema_id=RELEASE_QUALIFICATION_SCHEMA_ID,
        )
        product_status = resolver.artifact(
            selection["productReleaseStatus"],
            media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            contract="bytedesk.release-status/1",
            schema_id=RELEASE_STATUS_SCHEMA_ID,
        )
        renderer_status = resolver.artifact(
            selection["rendererReleaseStatus"],
            media_type="application/vnd.bytedesk.agent.release-status.v1+json",
            contract="bytedesk.release-status/1",
            schema_id=RELEASE_STATUS_SCHEMA_ID,
        )
        product_checkpoint, _ = validate_status_head_binding(
            checkpoint_descriptor=selection["productReleaseStatusCheckpoint"],
            authentication_descriptor=selection[
                "productReleaseStatusCheckpointAuthenticationEvidence"
            ],
            subject_kind="product_release",
            subject=selection["productRelease"],
            status_descriptor=selection["productReleaseStatus"],
            status=product_status,
            expected_nonce=selection["productReleaseStatusRequestNonce"],
            operation_time=timestamp(authority["issuedAt"], f"{binding_id}:issuedAt"),
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )
        renderer_checkpoint, _ = validate_status_head_binding(
            checkpoint_descriptor=selection["rendererReleaseStatusCheckpoint"],
            authentication_descriptor=selection[
                "rendererReleaseStatusCheckpointAuthenticationEvidence"
            ],
            subject_kind="renderer_release",
            subject=selection["rendererRelease"],
            status_descriptor=selection["rendererReleaseStatus"],
            status=renderer_status,
            expected_nonce=selection["rendererReleaseStatusRequestNonce"],
            operation_time=timestamp(authority["issuedAt"], f"{binding_id}:issuedAt"),
            resolver=resolver,
            registry=registry,
            schemas=schemas,
        )
        attempt_signing_policy = resolver.trust_policy(
            attempt_auth["signingResult"]["trustPolicy"],
            attempt_auth["signingResult"]["repository"],
            attempt_auth["signingResult"]["subjectMediaType"],
            verification_time=authority["issuedAt"],
        )
        validate_attempt_dependency_expiry(
            issued_at=authority["issuedAt"],
            expires_at=authority["expiresAt"],
            completed_at=receipt["completedAt"],
            dependency_expiries={
                "productCheckpointExpiresAt": product_checkpoint["expiresAt"],
                "rendererCheckpointExpiresAt": renderer_checkpoint["expiresAt"],
                "qualificationExpiresAt": qualification["expiresAt"],
                "attemptSigningPolicyExpiresAt": attempt_signing_policy[
                    "effective"
                ]["notAfter"],
                "pinSetExpiresAt": resolver.trust_policy_pin_set.document[
                    "effective"
                ]["notAfter"],
            },
            identity=binding_id,
        )
        require(
            timestamp(qualification["qualifiedAt"], "qualification:qualifiedAt")
            <= timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            < timestamp(qualification["expiresAt"], "qualification:expiresAt")
            and timestamp(
                product_status["effectiveAt"], f"{binding_id}:productStatus"
            )
            <= timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            and timestamp(
                renderer_status["effectiveAt"], f"{binding_id}:rendererStatus"
            )
            <= timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            and timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            < timestamp(authority["expiresAt"], f"{binding_id}:expiresAt")
            and timestamp(product_checkpoint["verifiedAt"], "product-head:verifiedAt")
            <= timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            < timestamp(product_checkpoint["expiresAt"], "product-head:expiresAt")
            and timestamp(renderer_checkpoint["verifiedAt"], "renderer-head:verifiedAt")
            <= timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            < timestamp(renderer_checkpoint["expiresAt"], "renderer-head:expiresAt")
            and product_status["status"] == renderer_status["status"] == "current",
            "renderer_attempt_temporal_eligibility_mismatch",
            binding_id,
        )
        require(
            receipt["attemptId"] == authority["attemptId"]
            and receipt["attemptFencingToken"] == authority["attemptFencingToken"]
            and receipt["attemptAuthorityDigest"] == authority["authorityDigest"]
            and receipt["attemptAuthenticationEvidenceDigest"]
            == attempt_auth["evidenceDigest"]
            and receipt["selectionDigest"] == selection["selectionDigest"]
            and receipt["productReleaseDigest"] == selection["productRelease"]["digest"]
            and receipt["releaseQualificationDigest"]
            == selection["releaseQualification"]["digest"]
            and receipt["productReleaseStatusDigest"]
            == selection["productReleaseStatus"]["digest"]
            and receipt["rendererReleaseStatusDigest"]
            == selection["rendererReleaseStatus"]["digest"]
            and receipt["rendererReleaseDigest"]
            == selection["rendererRelease"]["digest"]
            and receipt["platform"] == selection["targetPlatform"]
            and receipt["executedDistribution"]
            == selection["executableDistribution"]
            and receipt["productDistributionDigest"]
            == selection["productDistributionDigest"]
            and receipt["compiledAllowlistDigest"]
            == selection["compiledAllowlistDigest"]
            and receipt["inputTreeDigest"] == authority["inputTreeDigest"]
            and receipt["contractBundleDigest"] == authority["contractBundleDigest"]
            and receipt["framedRequestDigest"] == raw_digest(request_frame)
            and receipt["framedResponseDigest"] == raw_digest(response_frame)
            and receipt["outputTreeDigest"] == manifest["output"]["treeDigest"]
            and receipt["outputArchiveDigest"] == manifest["output"]["digest"]
            and receipt["outputArchiveSize"] == manifest["output"]["size"]
            and receipt["renderManifestDigest"] == canonical_digest(manifest)
            and receipt["sandboxProfileDigest"] == authority["sandboxProfileDigest"]
            and receipt["workerProfileDigest"]
            == selection["workerProfileDigest"]
            and timestamp(authority["issuedAt"], f"{binding_id}:issuedAt")
            <= timestamp(receipt["completedAt"], f"{binding_id}:completedAt")
            < timestamp(authority["expiresAt"], f"{binding_id}:expiresAt"),
            "renderer_execution_receipt_mismatch",
            binding_id,
        )
        response_payload = load_jcs_object(response_frame[4:], f"{binding_id}:response")
        require(
            response_payload
            == {
                "profile": "bytedesk.renderer-production-response-frame/1",
                "attemptId": authority["attemptId"],
                "attemptFencingToken": authority["attemptFencingToken"],
                "compatibility": manifest["compatibility"],
                "renderManifest": manifest,
                "result": "succeeded",
            },
            "renderer_response_frame_mismatch",
            binding_id,
        )
        receipt_digest = canonical_digest(receipt)
        require(
            authentication["evidenceDigest"]
            == canonical_digest(execution_authentication_evidence_preimage(authentication))
            and authentication["receiptDigest"] == receipt_digest
            and authentication["attemptAuthorityDigest"] == authority["authorityDigest"]
            and authentication["rendererSelectionDigest"] == selection["selectionDigest"]
            and authentication["launcherIdentityDigest"]
            == receipt["launcherIdentityDigest"],
            "renderer_execution_authentication_mismatch",
            binding_id,
        )
        validate_signing_result(
            authentication["signingResult"],
            purpose="renderer-execution-v1",
            subject_digest=receipt_digest,
            subject_media_type="application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=timestamp(
                receipt["completedAt"],
                f"{binding_id}:execution-signature-use",
            ),
        )
        validate_manifest_output(manifest)
        archive = resolver.payload(manifest["output"]["digest"], manifest["output"]["size"])
        try:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as payload_tar:
                members = payload_tar.getmembers()
                require(
                    all(member.isfile() and not member.issym() and not member.islnk() for member in members),
                    "renderer_output_archive_non_regular",
                    binding_id,
                )
                require(
                    [member.name for member in members]
                    == [entry["path"] for entry in manifest["files"]],
                    "renderer_output_archive_inventory_mismatch",
                    binding_id,
                )
                for member, entry in zip(members, manifest["files"], strict=True):
                    extracted = payload_tar.extractfile(member)
                    require(extracted is not None, "renderer_output_archive_read_failed", member.name)
                    payload = extracted.read()
                    require(
                        raw_digest(payload) == entry["digest"]
                        and len(payload) == entry["size"]
                        and member.mode == int(entry["mode"], 8),
                        "renderer_output_archive_file_mismatch",
                        member.name,
                    )
        except tarfile.TarError as error:
            raise RendererDigestError("renderer_output_archive_invalid", str(error)) from error

        graph.edge(authority["authorityDigest"], 15, selection["selectionDigest"], 14, "T->S")
        graph.edge(attempt_auth["evidenceDigest"], 16, authority["authorityDigest"], 15, "T-auth->T")
        graph.edge(receipt_digest, 17, attempt_auth["evidenceDigest"], 16, "Q->T-auth")
        graph.edge(authentication["evidenceDigest"], 18, receipt_digest, 17, "X->Q")
        graph.edge(manifest["output"]["digest"], 19, authentication["evidenceDigest"], 18, "O->X")
    require(bool(seen), "invalid_execution_binding", "empty")
    return len(seen)


def validate_public_finalization_result(
    *,
    finalization: dict[str, Any],
    public_render: dict[str, Any],
    resolver: RendererCasResolver,
) -> None:
    required_fields = {
        "harnessRender",
        "harnessRenderDescriptor",
        "authorityDigest",
        "signingResult",
        "rootDescriptor",
        "manifestBytes",
        "blobs",
        "graphDigest",
        "publicationPayloadDigest",
    }
    require(
        set(finalization) == required_fields,
        "public_render_finalization_result_invalid",
        "root fields",
    )
    resolved_render = resolver.artifact(
        finalization["harnessRenderDescriptor"],
        media_type="application/vnd.bytedesk.agent.render.v1+json",
        contract="bytedesk.harness-render/1",
        schema_id=HARNESS_RENDER_SCHEMA_ID,
    )
    require(
        finalization["harnessRender"] == resolved_render == public_render
        and finalization["authorityDigest"] == public_render["authorityDigest"]
        and finalization["signingResult"] == public_render["signingResult"],
        "public_render_finalization_authority_mismatch",
        public_render["authorityDigest"],
    )
    root = finalization["rootDescriptor"]
    try:
        manifest_bytes = decode_bounded_bytes(
            finalization["manifestBytes"], maximum_bytes=4_194_304
        )
    except OciGraphError as error:
        raise RendererDigestError(
            "public_render_finalization_manifest_mismatch", str(error)
        ) from error
    require(
        root.get("digest") == raw_digest(manifest_bytes)
        and root.get("size") == len(manifest_bytes),
        "public_render_finalization_manifest_mismatch",
        str(root.get("digest")),
    )
    manifest = load_jcs_object(manifest_bytes, root["digest"])
    expected_descriptors = [manifest["config"], *manifest["layers"]]
    blob_streams = finalization["blobs"]
    require(
        isinstance(blob_streams, list)
        and len(blob_streams) == len(expected_descriptors),
        "public_render_finalization_blob_set_mismatch",
        root["digest"],
    )
    blob_payloads: dict[str, bytes] = {}
    try:
        for stream, descriptor in zip(
            blob_streams, expected_descriptors, strict=True
        ):
            require(
                isinstance(stream, dict)
                and set(stream) == {"digest", "mediaType", "size", "chunks"}
                and {
                    "digest": stream.get("digest"),
                    "mediaType": stream.get("mediaType"),
                    "size": stream.get("size"),
                }
                == {
                    "digest": descriptor["digest"],
                    "mediaType": descriptor["mediaType"],
                    "size": descriptor["size"],
                }
                and stream["digest"] not in blob_payloads
                and stream["digest"] != root["digest"],
                "public_render_finalization_blob_set_mismatch",
                str(stream.get("digest")),
            )
            blob_payloads[stream["digest"]] = decode_oci_blob_stream(stream)
    except OciGraphError as error:
        raise RendererDigestError(
            "public_render_finalization_blob_set_mismatch", str(error)
        ) from error

    def fetch(repository: str, digest: str) -> bytes:
        if repository != root["repository"]:
            raise KeyError((repository, digest))
        if digest == root["digest"]:
            return manifest_bytes
        if digest in blob_payloads:
            return blob_payloads[digest]
        raise KeyError((repository, digest))

    try:
        graph = OciGraphVerifier(fetch=fetch).verify(
            root,
            expected_repository=root["repository"],
            expected_artifact_type=(
                "application/vnd.bytedesk.agent.render.v1+json"
            ),
        )
    except OciGraphError as error:
        raise RendererDigestError(error.code, str(error)) from error
    require(
        finalization["graphDigest"] == graph["graphDigest"],
        "public_render_finalization_graph_mismatch",
        root["digest"],
    )
    try:
        expected_payload_digest = public_render_publication_payload_digest(
            destination_repository=root["repository"],
            harness_render_descriptor=finalization[
                "harnessRenderDescriptor"
            ],
            root_descriptor=root,
            manifest_bytes=manifest_bytes,
            blobs=blob_streams,
            graph_digest=finalization["graphDigest"],
        )
    except OciGraphError as error:
        raise RendererDigestError(
            "public_render_publication_payload_digest_mismatch", str(error)
        ) from error
    require(
        finalization["publicationPayloadDigest"] == expected_payload_digest,
        "public_render_publication_payload_digest_mismatch",
        root["digest"],
    )


def validate_public_render_signature_chronology(
    public_render: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    """Reject a detached public-render signature made before its content."""

    signed_at = timestamp(
        public_render["signingResult"]["signedAt"],
        "public-render:signature:signedAt",
    )
    require(
        timestamp(public_render["createdAt"], "public-render:createdAt")
        <= signed_at
        and timestamp(
            receipt["completedAt"], "public-render:receipt:completedAt"
        )
        <= signed_at,
        "public_render_signature_precedes_content",
        public_render["authorityDigest"],
    )


def validate_public_render(
    resolver: RendererCasResolver,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    finalization: dict[str, Any],
) -> tuple[int, int]:
    public_render = load_json(
        REPOSITORY_ROOT
        / "contracts/fixtures/schema/positive/harness-render__tenant-free.json"
    )
    validate_schema_instance(public_render, HARNESS_RENDER_SCHEMA_ID, registry, schemas)
    eligibility_renderer_release = resolver.artifact(
        public_render["rendererRelease"],
        media_type="application/vnd.bytedesk.agent.renderer-release.v1+json",
        contract="bytedesk.renderer-release/1",
        schema_id=RELEASE_SCHEMA_ID,
    )
    require(
        isinstance(eligibility_renderer_release, dict),
        "public_render_renderer_release_unresolved",
        public_render["rendererRelease"]["digest"],
    )
    public_eligibility_probe = resolver.artifact(
        public_render["releaseStatusEligibility"],
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-eligibility-evidence.v1+json"
        ),
        contract="bytedesk.release-status-eligibility-evidence/1",
        schema_id=RELEASE_STATUS_ELIGIBILITY_SCHEMA_ID,
    )
    require(
        isinstance(public_eligibility_probe, dict),
        "release_status_eligibility_unresolved",
        public_render["releaseStatusEligibility"]["digest"],
    )
    public_eligibility = validate_release_status_eligibility(
        descriptor=public_render["releaseStatusEligibility"],
        expected_digest=public_render["releaseStatusEligibilityDigest"],
        expected_verification_digest=public_render[
            "releaseStatusEligibilityVerificationEvidenceDigest"
        ],
        expected_stage="public_render_finalization",
        expected_operation_time=public_eligibility_probe["operationTime"],
        expected_product=public_render["productRelease"],
        expected_renderers=[
            (
                public_render["rendererRelease"],
                eligibility_renderer_release["harnessId"],
                eligibility_renderer_release["rendererId"],
                eligibility_renderer_release["version"],
                public_render["platform"],
            )
        ],
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )
    public_finalization_time = timestamp(
        public_eligibility["operationTime"],
        "public-render:finalization-time",
    )
    require(
        timestamp(public_render["createdAt"], "public-render:createdAt")
        <= public_finalization_time,
        "public_render_created_after_finalization",
        public_render["authorityDigest"],
    )
    validate_public_finalization_result(
        finalization=finalization,
        public_render=public_render,
        resolver=resolver,
    )
    serialized = json.dumps(public_render, sort_keys=True)
    for forbidden in (
        '"consumerId"',
        '"targetId"',
        '"privateSkills"',
        '"customizationDigest"',
        '"bindingDigest"',
        '"authoritySnapshot"',
        '"skillApprovals"',
        '"credential',
    ):
        require(
            forbidden not in serialized,
            "public_render_contains_private_lineage",
            forbidden,
        )
    require(
        public_render["authorityDigest"]
        == canonical_digest(public_render_preimage(public_render)),
        "inline_authority_digest_mismatch",
        "public-render-v1",
    )
    validate_signing_result(
        public_render["signingResult"],
        purpose="public-render-v1",
        subject_digest=public_render["authorityDigest"],
        subject_media_type="application/vnd.bytedesk.agent.render.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=public_finalization_time,
    )

    selection = resolver.artifact(
        public_render["rendererSelection"],
        media_type="application/vnd.bytedesk.agent.renderer-selection.v1+json",
        contract="bytedesk.renderer-selection/1",
        schema_id=RENDERER_SELECTION_SCHEMA_ID,
    )
    authority = resolver.artifact(
        public_render["rendererAttemptAuthority"],
        media_type="application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
        contract="bytedesk.renderer-attempt-authority/1",
        schema_id=RENDERER_ATTEMPT_AUTHORITY_SCHEMA_ID,
    )
    attempt_authentication = resolver.artifact(
        public_render["rendererAttemptAuthenticationEvidence"],
        media_type="application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json",
        contract="bytedesk.renderer-attempt-authentication-evidence/1",
        schema_id=RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
    )
    receipt = resolver.artifact(
        public_render["rendererExecutionReceipt"],
        media_type="application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
        contract="bytedesk.renderer-execution-receipt/1",
        schema_id=RENDERER_EXECUTION_RECEIPT_SCHEMA_ID,
    )
    execution_authentication = resolver.artifact(
        public_render["rendererExecutionAuthenticationEvidence"],
        media_type="application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json",
        contract="bytedesk.renderer-execution-authentication-evidence/1",
        schema_id=RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
    )
    manifest = resolver.artifact(
        public_render["renderManifest"],
        media_type="application/vnd.bytedesk.agent.render-manifest.v1+json",
        contract="bytedesk.render-manifest/1",
        schema_id=MANIFEST_SCHEMA_ID,
    )
    require(
        all(
            isinstance(value, dict)
            for value in (
                selection,
                authority,
                attempt_authentication,
                receipt,
                execution_authentication,
                manifest,
            )
        ),
        "public_render_lineage_unresolved",
        public_render["authorityDigest"],
    )
    validate_public_render_signature_chronology(public_render, receipt)
    try:
        require_tenant_free_public_lineage(public_render, manifest)
    except ValueError as error:
        raise RendererDigestError(
            "public_render_contains_private_lineage",
            str(error),
        ) from error
    require(
        selection["selectionDigest"]
        == canonical_digest(renderer_selection_preimage(selection))
        and authority["rendererSelectionDigest"] == selection["selectionDigest"]
        and authority["authorityDigest"]
        == canonical_digest(renderer_attempt_authority_preimage(authority))
        and attempt_authentication["attemptAuthorityDigest"]
        == authority["authorityDigest"]
        and attempt_authentication["evidenceDigest"]
        == canonical_digest(
            attempt_authentication_evidence_preimage(attempt_authentication)
        ),
        "public_render_attempt_lineage_mismatch",
        public_render["authorityDigest"],
    )
    validate_signing_result(
        attempt_authentication["signingResult"],
        purpose="renderer-attempt-v1",
        subject_digest=authority["authorityDigest"],
        subject_media_type="application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=public_finalization_time,
    )
    receipt_digest = canonical_digest(receipt)
    require(
        receipt["attemptAuthorityDigest"] == authority["authorityDigest"]
        and receipt["attemptAuthenticationEvidenceDigest"]
        == attempt_authentication["evidenceDigest"]
        and receipt["selectionDigest"] == selection["selectionDigest"]
        and receipt["renderManifestDigest"] == canonical_digest(manifest)
        and receipt["outputArchiveDigest"] == manifest["output"]["digest"]
        and receipt["outputArchiveSize"] == manifest["output"]["size"]
        and execution_authentication["receiptDigest"] == receipt_digest
        and execution_authentication["attemptAuthorityDigest"]
        == authority["authorityDigest"]
        and execution_authentication["rendererSelectionDigest"]
        == selection["selectionDigest"]
        and execution_authentication["evidenceDigest"]
        == canonical_digest(
            execution_authentication_evidence_preimage(execution_authentication)
        ),
        "public_render_execution_lineage_mismatch",
        public_render["authorityDigest"],
    )
    validate_signing_result(
        execution_authentication["signingResult"],
        purpose="renderer-execution-v1",
        subject_digest=receipt_digest,
        subject_media_type="application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
        resolver=resolver,
        registry=registry,
        schemas=schemas,
        verification_time=public_finalization_time,
    )

    product_release = resolver.artifact(
        selection["productRelease"],
        media_type="application/vnd.bytedesk.agent.product-release-manifest.v1+json",
        contract="bytedesk.product-release-manifest/1",
        schema_id=PRODUCT_RELEASE_SCHEMA_ID,
    )
    product_distribution = resolver.artifact(
        selection["productDistribution"],
        media_type="application/vnd.bytedesk.agent.product-distribution.v1+json",
        contract="bytedesk.product-distribution-manifest/1",
        schema_id=PRODUCT_DISTRIBUTION_SCHEMA_ID,
    )
    allowlist = resolver.artifact(
        selection["compiledAllowlist"],
        media_type="application/vnd.bytedesk.agent.renderer-allowlist.v1+json",
        contract="bytedesk.renderer-allowlist/1",
        schema_id=ALLOWLIST_SCHEMA_ID,
    )
    release = resolver.artifact(
        selection["rendererRelease"],
        media_type="application/vnd.bytedesk.agent.renderer-release.v1+json",
        contract="bytedesk.renderer-release/1",
        schema_id=RELEASE_SCHEMA_ID,
    )
    qualification = resolver.artifact(
        selection["releaseQualification"],
        media_type="application/vnd.bytedesk.agent.release-qualification.v1+json",
        contract="bytedesk.release-qualification/1",
        schema_id=RELEASE_QUALIFICATION_SCHEMA_ID,
    )
    product_status = resolver.artifact(
        selection["productReleaseStatus"],
        media_type="application/vnd.bytedesk.agent.release-status.v1+json",
        contract="bytedesk.release-status/1",
        schema_id=RELEASE_STATUS_SCHEMA_ID,
    )
    renderer_status = resolver.artifact(
        selection["rendererReleaseStatus"],
        media_type="application/vnd.bytedesk.agent.release-status.v1+json",
        contract="bytedesk.release-status/1",
        schema_id=RELEASE_STATUS_SCHEMA_ID,
    )
    inline_authorities = (
        (product_release, PRODUCT_RELEASE_SCHEMA_ID, "product-release-v1", "application/vnd.bytedesk.agent.product-release-manifest.v1+json"),
        (product_distribution, PRODUCT_DISTRIBUTION_SCHEMA_ID, "product-release-v1", "application/vnd.bytedesk.agent.product-distribution.v1+json"),
        (allowlist, ALLOWLIST_SCHEMA_ID, "product-release-v1", "application/vnd.bytedesk.agent.renderer-allowlist.v1+json"),
        (release, RELEASE_SCHEMA_ID, "product-release-v1", "application/vnd.bytedesk.agent.renderer-release.v1+json"),
        (qualification, RELEASE_QUALIFICATION_SCHEMA_ID, "release-qualification-decision-v1", "application/vnd.bytedesk.agent.release-qualification.v1+json"),
        (product_status, RELEASE_STATUS_SCHEMA_ID, "release-status-v1", "application/vnd.bytedesk.agent.release-status.v1+json"),
        (renderer_status, RELEASE_STATUS_SCHEMA_ID, "release-status-v1", "application/vnd.bytedesk.agent.release-status.v1+json"),
    )
    for document, schema_id, purpose, media_type in inline_authorities:
        require(isinstance(document, dict), "public_render_authority_unresolved", purpose)
        validate_inline_authority(
            document,
            schema_id=schema_id,
            purpose=purpose,
            subject_media_type=media_type,
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=public_finalization_time,
        )
    require(
        public_render["productRelease"] == selection["productRelease"]
        and public_render["releaseQualification"] == selection["releaseQualification"]
        and public_render["rendererRelease"] == selection["rendererRelease"]
        and public_render["executedDistribution"] == selection["executableDistribution"]
        and public_render["platform"] == selection["targetPlatform"]
        and public_render["productDistributionDigest"]
        == selection["productDistributionDigest"]
        and public_render["compiledAllowlistDigest"]
        == selection["compiledAllowlistDigest"],
        "public_render_release_lineage_mismatch",
        public_render["authorityDigest"],
    )
    operation_time = public_finalization_time
    validate_status_head_binding(
        checkpoint_descriptor=selection["productReleaseStatusCheckpoint"],
        authentication_descriptor=selection[
            "productReleaseStatusCheckpointAuthenticationEvidence"
        ],
        subject_kind="product_release",
        subject=selection["productRelease"],
        status_descriptor=selection["productReleaseStatus"],
        status=product_status,
        expected_nonce=selection["productReleaseStatusRequestNonce"],
        operation_time=operation_time,
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )
    validate_status_head_binding(
        checkpoint_descriptor=selection["rendererReleaseStatusCheckpoint"],
        authentication_descriptor=selection[
            "rendererReleaseStatusCheckpointAuthenticationEvidence"
        ],
        subject_kind="renderer_release",
        subject=selection["rendererRelease"],
        status_descriptor=selection["rendererReleaseStatus"],
        status=renderer_status,
        expected_nonce=selection["rendererReleaseStatusRequestNonce"],
        operation_time=operation_time,
        resolver=resolver,
        registry=registry,
        schemas=schemas,
    )

    archive = resolver.artifact(
        public_render["outputArchive"],
        media_type=manifest["output"]["mediaType"],
    )
    output_layer = resolver.artifact(
        public_render["outputLayer"],
        media_type="application/vnd.oci.image.layer.v1.tar+gzip",
    )
    compatibility = resolver.artifact(
        public_render["compatibility"],
        media_type="application/vnd.bytedesk.agent.compatibility.v1+json",
    )
    require(
        isinstance(archive, bytes)
        and isinstance(output_layer, bytes)
        and gzip.decompress(output_layer) == archive
        and raw_digest(archive) == manifest["output"]["digest"]
        and len(archive) == manifest["output"]["size"]
        and compatibility == manifest["compatibility"]
        and public_render["source"] == manifest["source"]
        and public_render["publicSkills"] == manifest["publicSkills"]
        and manifest["privateSkills"] == []
        and manifest.get("bindingDigest") is None
        and manifest.get("customizationDigest") is None
        and public_render["rendererSchemas"] == manifest["rendererSchemas"]
        and public_render["normalizedParametersDigest"]
        == manifest["inputParametersDigest"]
        and public_render["files"]
        == [
            {
                "path": entry["path"],
                "digest": entry["digest"],
                "size": entry["size"],
                "mode": entry["mode"],
            }
            for entry in manifest["files"]
        ],
        "public_render_payload_lineage_mismatch",
        public_render["authorityDigest"],
    )

    public_subjects = [public_render["source"], *public_render["publicSkills"]]
    require(
        len(public_render["publicSourceAuthenticationEvidence"])
        == len(public_subjects),
        "public_source_authentication_coverage_mismatch",
        public_render["authorityDigest"],
    )
    authenticated_subjects: set[tuple[str, str, str]] = set()
    for descriptor in public_render["publicSourceAuthenticationEvidence"]:
        source_authentication = resolver.artifact(
            descriptor,
            media_type="application/vnd.bytedesk.agent.public-source-authentication-evidence.v1+json",
            contract="bytedesk.public-source-authentication-evidence/1",
            schema_id=PUBLIC_SOURCE_AUTH_SCHEMA_ID,
        )
        require(isinstance(source_authentication, dict), "public_source_authentication_missing", descriptor["digest"])
        subject = source_authentication["subject"]
        subject_key = (subject["repository"], subject["digest"], subject["mediaType"])
        require(
            subject in public_subjects and subject_key not in authenticated_subjects,
            "public_source_authentication_subject_mismatch",
            subject["digest"],
        )
        authenticated_subjects.add(subject_key)
        source_payload = resolver.artifact(
            subject,
            media_type=subject["mediaType"],
        )
        require(
            isinstance(source_payload, (dict, bytes)),
            "public_source_payload_unresolved",
            subject["digest"],
        )
        require(
            source_authentication["evidenceDigest"]
            == canonical_digest(
                public_source_authentication_preimage(source_authentication)
            ),
            "public_source_authentication_digest_mismatch",
            subject["digest"],
        )
        validate_signing_result(
            source_authentication["signingResult"],
            purpose="public-source-v1",
            subject_digest=subject["digest"],
            subject_media_type=subject["mediaType"],
            resolver=resolver,
            registry=registry,
            schemas=schemas,
            verification_time=public_finalization_time,
        )
        validate_public_source_publisher_identity(source_authentication, resolver)
    require(
        authenticated_subjects
        == {
            (subject["repository"], subject["digest"], subject["mediaType"])
            for subject in public_subjects
        },
        "public_source_authentication_coverage_mismatch",
        public_render["authorityDigest"],
    )

    tampered_render = deepcopy(public_render)
    tampered_render["outputArchive"]["digest"] = "sha256:" + ("77" * 32)
    tampered_signature = deepcopy(public_render)
    tampered_signature["signingResult"]["subjectDigest"] = "sha256:" + ("88" * 32)
    premature_signature = deepcopy(public_render)
    premature_signature["signingResult"]["signedAt"] = (
        "2026-07-17T12:00:06.499999Z"
    )
    post_signature_receipt = deepcopy(receipt)
    post_signature_receipt["completedAt"] = "2026-07-17T12:00:06.500001Z"
    missing_source_evidence = deepcopy(public_render)
    missing_source_evidence["publicSourceAuthenticationEvidence"] = []
    substituted_publisher = deepcopy(source_authentication)
    substituted_publisher["publisherIdentityDigest"] = "sha256:" + ("99" * 32)
    substituted_publisher["evidenceDigest"] = canonical_digest(
        public_source_authentication_preimage(substituted_publisher)
    )
    missing_source_payload = deepcopy(public_subjects[0])
    missing_source_payload["digest"] = "sha256:" + ("aa" * 31) + "ab"
    tampered_finalization_graph = deepcopy(finalization)
    tampered_finalization_graph["graphDigest"] = "sha256:" + ("bb" * 32)
    tampered_publication_payload = deepcopy(finalization)
    tampered_publication_payload["publicationPayloadDigest"] = (
        "sha256:" + ("cc" * 32)
    )
    incomplete_finalization_blobs = deepcopy(finalization)
    incomplete_finalization_blobs["blobs"] = (
        incomplete_finalization_blobs["blobs"][:-1]
    )
    reordered_finalization_blobs = deepcopy(finalization)
    require(
        len(reordered_finalization_blobs["blobs"]) >= 2,
        "public_render_finalization_blob_set_mismatch",
        "reorder denial requires at least two blobs",
    )
    reordered_finalization_blobs["blobs"][0], reordered_finalization_blobs[
        "blobs"
    ][1] = (
        reordered_finalization_blobs["blobs"][1],
        reordered_finalization_blobs["blobs"][0],
    )
    tampered_finalization_manifest = deepcopy(finalization)
    tampered_finalization_manifest["manifestBytes"] = encode_bounded_bytes(
        decode_bounded_bytes(
            tampered_finalization_manifest["manifestBytes"],
            maximum_bytes=4_194_304,
        )
        + b"\n"
    )
    qualification_eligibility = resolver.artifact(
        qualification["qualificationStatusEligibility"],
        media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-eligibility-evidence.v1+json"
        ),
        contract="bytedesk.release-status-eligibility-evidence/1",
        schema_id=RELEASE_STATUS_ELIGIBILITY_SCHEMA_ID,
    )
    require(
        isinstance(qualification_eligibility, dict),
        "release_status_eligibility_unresolved",
        qualification["qualificationId"],
    )
    missing_renderer_eligibility = deepcopy(public_eligibility)
    missing_renderer_eligibility["renderers"] = []
    negative_cases: list[tuple[str, Any, str]] = [
        (
            "inline_authority_digest_mismatch",
            lambda: validate_inline_authority(
                tampered_render,
                schema_id=HARNESS_RENDER_SCHEMA_ID,
                purpose="public-render-v1",
                subject_media_type="application/vnd.bytedesk.agent.render.v1+json",
                resolver=resolver,
                registry=registry,
                schemas=schemas,
                verification_time=public_finalization_time,
            ),
            "public render payload substitution",
        ),
        (
            "signing_subject_mismatch",
            lambda: validate_signing_result(
                tampered_signature["signingResult"],
                purpose="public-render-v1",
                subject_digest=public_render["authorityDigest"],
                subject_media_type="application/vnd.bytedesk.agent.render.v1+json",
                resolver=resolver,
                registry=registry,
                schemas=schemas,
                verification_time=public_finalization_time,
            ),
            "public render signature substitution",
        ),
        (
            "public_render_signature_precedes_content",
            lambda: validate_public_render_signature_chronology(
                premature_signature,
                receipt,
            ),
            "public render signature created before HarnessRender",
        ),
        (
            "public_render_signature_precedes_content",
            lambda: validate_public_render_signature_chronology(
                public_render,
                post_signature_receipt,
            ),
            "public render signature created before renderer receipt",
        ),
        (
            "public_source_authentication_coverage_mismatch",
            lambda: require(
                len(missing_source_evidence["publicSourceAuthenticationEvidence"])
                == len(public_subjects),
                "public_source_authentication_coverage_mismatch",
                "missing public source authentication",
            ),
            "missing public source authentication",
        ),
        (
            "public_source_publisher_identity_mismatch",
            lambda: validate_public_source_publisher_identity(
                substituted_publisher,
                resolver,
            ),
            "public source publisher identity substitution",
        ),
        (
            "renderer_cas_object_missing",
            lambda: resolver.artifact(
                missing_source_payload,
                media_type=missing_source_payload["mediaType"],
            ),
            "public source payload unavailable offline",
        ),
        (
            "public_render_finalization_graph_mismatch",
            lambda: validate_public_finalization_result(
                finalization=tampered_finalization_graph,
                public_render=public_render,
                resolver=resolver,
            ),
            "public OCI graph digest substitution",
        ),
        (
            "public_render_publication_payload_digest_mismatch",
            lambda: validate_public_finalization_result(
                finalization=tampered_publication_payload,
                public_render=public_render,
                resolver=resolver,
            ),
            "publication payload digest substitution",
        ),
        (
            "public_render_finalization_blob_set_mismatch",
            lambda: validate_public_finalization_result(
                finalization=incomplete_finalization_blobs,
                public_render=public_render,
                resolver=resolver,
            ),
            "missing recursive OCI blob",
        ),
        (
            "public_render_finalization_blob_set_mismatch",
            lambda: validate_public_finalization_result(
                finalization=reordered_finalization_blobs,
                public_render=public_render,
                resolver=resolver,
            ),
            "reordered OCI blob streams",
        ),
        (
            "public_render_finalization_manifest_mismatch",
            lambda: validate_public_finalization_result(
                finalization=tampered_finalization_manifest,
                public_render=public_render,
                resolver=resolver,
            ),
            "raw OCI manifest byte substitution",
        ),
        (
            "release_status_eligibility_context_mismatch",
            lambda: require(
                qualification_eligibility["stage"]
                == public_eligibility["stage"]
                and qualification_eligibility["operationTime"]
                == public_eligibility["operationTime"],
                "release_status_eligibility_context_mismatch",
                "qualification-stage eligibility reused for public finalization",
            ),
            "qualification-stage status evidence reuse",
        ),
        (
            "release_status_eligibility_coverage_mismatch",
            lambda: require(
                len(missing_renderer_eligibility["renderers"]) == 1,
                "release_status_eligibility_coverage_mismatch",
                "public finalization renderer omitted",
            ),
            "missing public-finalization renderer status",
        ),
    ]
    for expected_error, operation, identity in negative_cases:
        require_semantic_denial(expected_error, operation, identity)
    kms_context_denials = validate_kms_context_denials(
        result=public_render["signingResult"],
        resolver=resolver,
        verification_time=public_eligibility["operationTime"],
    )
    return len(public_subjects), len(negative_cases) + kms_context_denials


def validate_profile() -> None:
    catalog = load_json(PROFILE_PATH)
    profiles = {
        entry["profileId"]: entry for entry in catalog["profiles"]
    }
    renderer = profiles["bytedesk.renderer-contract/1"]
    requirements = renderer["requirements"]
    require(
        requirements["inputIdentity"] == DIGEST_AUTHORITY_PROFILE,
        "renderer_digest_profile_missing",
        "renderer inputIdentity must select the frozen digest-authority profile",
    )
    require(
        requirements["outputIdentity"] == DIGEST_AUTHORITY_PROFILE,
        "renderer_digest_profile_missing",
        "renderer outputIdentity must select the frozen digest-authority profile",
    )
    require(
        CASE_PATH.relative_to(REPOSITORY_ROOT).as_posix() in renderer["repoPaths"],
        "renderer_digest_conformance_unbound",
        "renderer contract profile must bind the semantic conformance catalog",
    )


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    payload = (
        json.dumps(evidence, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_validation() -> dict[str, Any]:
    validate_profile()
    contract_bundle_kms_denial_count = validate_contract_bundle_kms_denials()
    keyless_adapter_case_count = validate_keyless_adapter_contract()
    schema_registry, schemas = build_schema_registry()
    catalog = load_json(CASE_PATH)
    require(
        set(catalog)
        == {
            "profile",
            "version",
            "executionReceiptBindings",
            "positiveChains",
            "negativeCases",
            "selectionNegativeCases",
            "crossPlatformCases",
            "releaseSelectionBindings",
            "releaseGraphNegativeCases",
            "trustPolicyPinSet",
            "trustPolicyPinSetDescriptor",
            "trustPolicyPinSetProviderEvidence",
            "trustPolicyProviderAuthenticationVectors",
            "signatureVerificationVectors",
            "keylessVerificationVectors",
            "publicRenderFinalization",
        },
        "invalid_case_catalog",
        "root fields",
    )
    require(
        catalog["profile"] == "bytedesk.renderer-digest-conformance/1"
        and catalog["version"] == 1,
        "invalid_case_catalog",
        "profile or version",
    )
    chains = load_chains(catalog)
    for chain in chains.values():
        validate_chain_schemas(chain, schema_registry, schemas)
        validate_chain(chain)

    selection_documents = {
        target: load_json(path) for target, path in SELECTION_FIXTURES.items()
    }
    for target, document in selection_documents.items():
        validate_schema_instance(
            document,
            SELECTION_SCHEMA_IDS[target],
            schema_registry,
            schemas,
        )
        validate_selection_authority(target, document)

    trust_policy_pin_set = validate_trust_policy_pin_set_authority(
        catalog,
        schema_registry,
        schemas,
    )
    trust_policy_pin_rotation_case_count = validate_trust_policy_pin_rotation(
        catalog["trustPolicyPinSet"],
        schema_registry,
        schemas,
    )
    resolver = RendererCasResolver(
        schema_registry,
        schemas,
        trust_policy_pin_set,
        catalog["signatureVerificationVectors"],
        catalog["keylessVerificationVectors"],
    )
    standalone_signing_projection_count = validate_standalone_signing_projections(
        resolver,
        schema_registry,
        schemas,
    )
    indexed_provider_audit_projection_count = (
        validate_indexed_provider_audit_projections(
            schema_registry,
            schemas,
        )
    )
    substituted_policy_ref = deepcopy(
        trust_policy_pin_set.current["public-render-v1"]
    )
    substituted_policy_ref["digest"] = trust_policy_pin_set.current["public-source-v1"][
        "digest"
    ]
    require_semantic_denial(
        "trust_policy_pin_mismatch",
        lambda: resolver.trust_policy(
            substituted_policy_ref,
            "registry.example/agents/renders",
            "application/vnd.bytedesk.agent.render.v1+json",
        ),
        "coherent attacker-controlled policy substitution",
    )
    graph = GraphAudit()
    release_binding_count, release_context = validate_release_selection_bindings(
        catalog["releaseSelectionBindings"],
        resolver,
        schema_registry,
        schemas,
        graph,
    )
    status_head_negative_case_count = validate_status_head_negative_cases(
        release_context,
        resolver,
        schema_registry,
        schemas,
    )
    qualification_evidence_count, qualification_negative_case_count = validate_qualification_graph(
        release_context,
        resolver,
        schema_registry,
        schemas,
        graph,
    )

    execution_receipt_binding_count = validate_execution_receipt_bindings(
        catalog["executionReceiptBindings"],
        schema_registry,
        schemas,
        resolver,
        graph,
    )
    public_source_count, public_render_negative_case_count = validate_public_render(
        resolver,
        schema_registry,
        schemas,
        catalog["publicRenderFinalization"],
    )
    separated_product_signer_count = validate_product_signer_separation(
        resolver,
        schema_registry,
        schemas,
    )

    seen_cases: set[str] = set()
    for case in catalog["negativeCases"]:
        case_id = case["caseId"]
        require(case_id not in seen_cases, "duplicate_negative_case", case_id)
        seen_cases.add(case_id)
        require(case["chainId"] in chains, "unknown_chain", case["chainId"])
        mutated = deepcopy(chains[case["chainId"]])
        target = case["target"]
        if target == "compatibility":
            apply_mutation(mutated["compatibility"], case["mutation"])
            mutated["manifest"]["compatibility"] = deepcopy(mutated["compatibility"])
        elif target == "embeddedCompatibility":
            apply_mutation(mutated["manifest"]["compatibility"], case["mutation"])
        else:
            require(target in mutated, "invalid_mutation_target", target)
            apply_mutation(mutated[target], case["mutation"])
        validate_chain_schemas(mutated, schema_registry, schemas)
        try:
            validate_chain(mutated)
        except RendererDigestError as error:
            require(
                error.code == case["expectedError"],
                "wrong_negative_error",
                f"{case_id}: expected {case['expectedError']}, observed {error.code}",
            )
        else:
            raise RendererDigestError(
                "negative_case_accepted", f"{case_id}: {case['expectedError']}"
            )

    seen_selection_cases: set[str] = set()
    for case in catalog["selectionNegativeCases"]:
        case_id = case["caseId"]
        require(
            case_id not in seen_cases and case_id not in seen_selection_cases,
            "duplicate_negative_case",
            case_id,
        )
        seen_selection_cases.add(case_id)
        target = case["target"]
        require(target in selection_documents, "invalid_mutation_target", target)
        mutated = deepcopy(selection_documents[target])
        apply_mutation(mutated, case["mutation"])
        validate_schema_instance(
            mutated,
            SELECTION_SCHEMA_IDS[target],
            schema_registry,
            schemas,
        )
        try:
            validate_selection_authority(target, mutated)
        except RendererDigestError as error:
            require(
                error.code == case["expectedError"],
                "wrong_negative_error",
                f"{case_id}: expected {case['expectedError']}, observed {error.code}",
            )
        else:
            raise RendererDigestError(
                "negative_case_accepted", f"{case_id}: {case['expectedError']}"
            )

    cross_platform_case_count = validate_cross_platform_cases(
        catalog["crossPlatformCases"],
        chains,
        schema_registry,
        schemas,
        seen_cases | seen_selection_cases,
    )
    graph.finish()
    timestamp_case_count = validate_timestamp_profile()
    attempt_expiry_case_count = validate_attempt_expiry_boundaries()
    signing_time_case_count = validate_signing_time_boundaries()

    return {
        "profile": "bytedesk.renderer-digest-validation-evidence/1",
        "result": "pass",
        "contractProfile": DIGEST_AUTHORITY_PROFILE,
        "positiveChains": len(chains),
        "negativeCases": (
            len(seen_cases)
            + len(seen_selection_cases)
            + qualification_negative_case_count
            + status_head_negative_case_count
            + public_render_negative_case_count
        ),
        "crossPlatformCases": cross_platform_case_count,
        "releaseSelectionBindings": release_binding_count,
        "qualificationEvidence": qualification_evidence_count,
        "qualificationNegativeCases": qualification_negative_case_count,
        "statusHeadNegativeCases": status_head_negative_case_count,
        "executionReceiptBindings": execution_receipt_binding_count,
        "publicRenderAuthenticatedSources": public_source_count,
        "publicRenderNegativeCases": public_render_negative_case_count,
        "separatedProductSignerPurposes": separated_product_signer_count,
        "standaloneSigningProjections": standalone_signing_projection_count,
        "indexedProviderAuditProjections": (
            indexed_provider_audit_projection_count
        ),
        "contractBundleKmsDenials": contract_bundle_kms_denial_count,
        "contractBundleKeylessAdapterCases": keyless_adapter_case_count,
        "timestampCases": timestamp_case_count,
        "attemptExpiryCases": attempt_expiry_case_count,
        "signingTimeCases": signing_time_case_count,
        "trustPolicyPinRotationCases": trust_policy_pin_rotation_case_count,
        "rendererCasObjects": len(resolver.payloads),
        "caseCatalogDigest": canonical_digest(catalog),
        "checks": [
            "rfc8785-jcs-sha256-domain-separated-preimages",
            "capability-semantic-count-order-and-coverage",
            "effective-skill-set-and-render-input-identity",
            "capability-compatibility-manifest-cross-binding",
            "compatibility-coverage-binding",
            "output-tree-count-expanded-size-and-archive-profile",
            "reproducibility-binds-input-compatibility-tree-and-archive-identity",
            "cross-platform-functional-input-and-output-byte-equivalence",
            "unique-allowlist-and-platform-selection-keys",
            "exact-release-graph-and-current-status-heads",
            "complete-release-qualification-evidence-matrix",
            "typed-authenticated-evidence-tree-denials",
            "product-release-pinned-qualification-policy-suite-and-coverage",
            "selection-to-execution-receipt-readback",
            "closed-authenticated-signature-bundle-and-request-binding",
            "contract-bundle-json-and-tar-remain-keyless-only",
            "contract-bundle-keyless-verification-receipt-and-external-adapter",
            "timezone-aware-rfc3339-temporal-eligibility",
            "acyclic-authority-graph-rank-and-cycle-audit",
            "semantic-denial-corpus",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        evidence = run_validation()
    except (KeyError, IndexError, TypeError, RendererDigestError) as error:
        print(f"renderer digest validation failed: {error}", file=sys.stderr)
        return 1
    if args.evidence is not None:
        write_evidence(args.evidence, evidence)
    print(
        "renderer digest validation passed: "
        f"{evidence['positiveChains']} positive chains, "
        f"{evidence['negativeCases']} semantic denials, "
        f"{evidence['crossPlatformCases']} cross-platform equivalence case"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
