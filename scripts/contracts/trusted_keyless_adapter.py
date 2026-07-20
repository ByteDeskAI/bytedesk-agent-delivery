#!/usr/bin/env python3
"""Trusted Sigstore-keyless verification seam for offline conformance graphs.

This module deliberately does not implement Fulcio certificate, Rekor inclusion,
or Cosign signature verification.  It accepts only an independently supplied
verification vector over the complete keyless context, exactly as
``trusted_kms_adapter`` models an external KMS verification outcome.  A
production Adapter must create the equivalent outcome only after performing
those cryptographic and transparency-log checks independently.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

import rfc8785

from signing_authority import (
    SIGNER_IDENTITY_FIELDS_BY_CREDENTIAL,
    signer_identity_digest,
)


CONTRACT_BUNDLE_RELEASE_PURPOSE = "contract-bundle-release-v1"
CONTRACT_BUNDLE_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.contract-bundle.v1+json"
)
SIGNING_REQUEST_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.signing-request.v1+json"
)
SIGSTORE_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
KEYLESS_VERIFICATION_PROFILE = (
    "bytedesk.contract-bundle-keyless-verification/1"
)
KEYLESS_VERIFICATION_EVIDENCE_PROFILE = (
    "bytedesk.keyless-signature-verification-evidence/1"
)
MAX_SIGNING_REQUEST_VALIDITY = timedelta(minutes=5)


class TrustedKeylessVerificationError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _canonical_digest(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def _raw_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _timestamp(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise TrustedKeylessVerificationError(code, str(value)) from error
    if parsed.tzinfo is None:
        raise TrustedKeylessVerificationError(code, str(value))
    return parsed.astimezone(timezone.utc)


def _require_descriptor(
    value: Any,
    *,
    code: str,
    expected_repository: str | None = None,
    expected_media_type: str | None = None,
    expected_trust_policy: dict[str, str] | None = None,
) -> dict[str, Any]:
    fields = {"repository", "digest", "mediaType", "size"}
    if expected_trust_policy is not None:
        fields.add("trustPolicy")
    if not isinstance(value, dict) or set(value) != fields:
        raise TrustedKeylessVerificationError(code, "descriptor shape")
    if expected_repository is not None and value["repository"] != expected_repository:
        raise TrustedKeylessVerificationError(code, "repository")
    if expected_media_type is not None and value["mediaType"] != expected_media_type:
        raise TrustedKeylessVerificationError(code, "mediaType")
    if expected_trust_policy is not None and value["trustPolicy"] != expected_trust_policy:
        raise TrustedKeylessVerificationError(code, "trustPolicy")
    if not isinstance(value["size"], int) or isinstance(value["size"], bool) or value["size"] < 0:
        raise TrustedKeylessVerificationError(code, "size")
    return value


def _require_exact_keyless_signer(value: Any) -> dict[str, Any]:
    expected_fields = SIGNER_IDENTITY_FIELDS_BY_CREDENTIAL["sigstore_keyless"]
    if (
        not isinstance(value, dict)
        or set(value) != expected_fields
        or value.get("purpose") != CONTRACT_BUNDLE_RELEASE_PURPOSE
        or value.get("credentialKind") != "sigstore_keyless"
        or value.get("algorithm") != "ECDSA_P256_SHA256"
        or "keyVersion" in value
        or "publicKeyDigest" in value
    ):
        raise TrustedKeylessVerificationError(
            "keyless_signer_invalid",
            str(value.get("purpose") if isinstance(value, dict) else value),
        )
    claims = value.get("claims")
    if not isinstance(claims, dict) or set(claims) != {
        "issuer",
        "audience",
        "subject",
        "repository",
        "workflow",
        "ref",
        "environment",
        "builderDigest",
    }:
        raise TrustedKeylessVerificationError(
            "keyless_signer_invalid",
            "claims",
        )
    return value


def keyless_signature_verification_vector(
    *,
    vector_id: str,
    subject: dict[str, Any],
    purpose: str,
    signer_identity_digest_value: str,
    trusted_root_digest: str,
    authenticated_signer: dict[str, Any],
    builder_digest: str,
    pre_sign_certification_digest: str,
    signing_request: dict[str, Any],
    signing_request_digest: str,
    signature_bundle: dict[str, Any],
    signature_bundle_digest: str,
    trust_policy: dict[str, str],
    verified_at: str,
) -> dict[str, Any]:
    """Build one complete externally asserted keyless verification vector."""

    return {
        "vectorId": vector_id,
        "subject": deepcopy(subject),
        "purpose": purpose,
        "credentialKind": "sigstore_keyless",
        "signerIdentityDigest": signer_identity_digest_value,
        "trustedRootDigest": trusted_root_digest,
        "authenticatedSigner": deepcopy(authenticated_signer),
        "builderDigest": builder_digest,
        "preSignCertificationDigest": pre_sign_certification_digest,
        "signingRequest": deepcopy(signing_request),
        "signingRequestDigest": signing_request_digest,
        "signatureBundle": deepcopy(signature_bundle),
        "signatureBundleDigest": signature_bundle_digest,
        "trustPolicy": deepcopy(trust_policy),
        "verifiedAt": verified_at,
        "decision": "permitted",
        "authorityIssued": False,
    }


class TrustedKeylessVerificationAdapter:
    """Consume exact external Sigstore-keyless verification vectors.

    ``authorityIssued`` is always false: signature verification authenticates
    bytes but does not itself issue product, consumer, or runtime authority.
    The later purpose-signed product-release manifest binds this receipt.
    """

    _fields = {
        "vectorId",
        "subject",
        "purpose",
        "credentialKind",
        "signerIdentityDigest",
        "trustedRootDigest",
        "authenticatedSigner",
        "builderDigest",
        "preSignCertificationDigest",
        "signingRequest",
        "signingRequestDigest",
        "signatureBundle",
        "signatureBundleDigest",
        "trustPolicy",
        "verifiedAt",
        "decision",
        "authorityIssued",
    }

    def __init__(self, vectors: list[dict[str, Any]]) -> None:
        self._vectors: list[dict[str, Any]] = []
        vector_ids: set[str] = set()
        tuple_digests: set[str] = set()
        for vector in vectors:
            if (
                not isinstance(vector, dict)
                or set(vector) != self._fields
                or vector.get("decision") != "permitted"
                or vector.get("authorityIssued") is not False
                or vector.get("purpose") != CONTRACT_BUNDLE_RELEASE_PURPOSE
                or vector.get("credentialKind") != "sigstore_keyless"
            ):
                raise TrustedKeylessVerificationError(
                    "keyless_verification_vector_invalid",
                    str(vector.get("vectorId") if isinstance(vector, dict) else vector),
                )
            _require_exact_keyless_signer(vector["authenticatedSigner"])
            vector_id = vector["vectorId"]
            tuple_digest = _canonical_digest(
                {
                    key: deepcopy(value)
                    for key, value in vector.items()
                    if key not in {"vectorId", "decision", "authorityIssued"}
                }
            )
            if vector_id in vector_ids or tuple_digest in tuple_digests:
                raise TrustedKeylessVerificationError(
                    "keyless_verification_vector_duplicate",
                    str(vector_id),
                )
            vector_ids.add(vector_id)
            tuple_digests.add(tuple_digest)
            self._vectors.append(deepcopy(vector))

    def verify(
        self,
        *,
        subject: dict[str, Any],
        subject_bytes: bytes,
        policy: dict[str, Any],
        policy_bytes: bytes,
        permitted_signer: dict[str, Any],
        signing_request: dict[str, Any],
        signing_request_bytes: bytes,
        signing_request_descriptor: dict[str, Any],
        signature_bundle_bytes: bytes,
        signature_bundle_descriptor: dict[str, Any],
        verification_time: str,
        expected_purpose: str,
        expected_subject_repository: str,
        expected_subject_digest: str,
        expected_subject_media_type: str,
        expected_trust_policy: dict[str, str],
        expected_signer_identity_digest: str,
        expected_trusted_root_digest: str,
        expected_workflow: str,
        expected_workload_identity: str,
        expected_claims: dict[str, Any],
        expected_builder_digest: str,
        expected_pre_sign_certification_digest: str,
        expected_signing_request_digest: str,
        expected_signature_bundle_digest: str,
    ) -> dict[str, Any]:
        """Verify exact bytes, policy, identity, request, and Sigstore evidence."""

        if expected_purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE:
            raise TrustedKeylessVerificationError(
                "keyless_purpose_mismatch",
                expected_purpose,
            )
        if subject.get("repository") != expected_subject_repository:
            raise TrustedKeylessVerificationError(
                "keyless_subject_repository_mismatch",
                expected_subject_repository,
            )
        if subject.get("mediaType") != expected_subject_media_type:
            raise TrustedKeylessVerificationError(
                "keyless_subject_media_type_mismatch",
                expected_subject_media_type,
            )
        if expected_subject_media_type != CONTRACT_BUNDLE_MEDIA_TYPE:
            raise TrustedKeylessVerificationError(
                "keyless_subject_media_type_mismatch",
                expected_subject_media_type,
            )
        if signing_request.get("credentialKind") != "sigstore_keyless":
            raise TrustedKeylessVerificationError(
                "keyless_credential_required",
                str(signing_request.get("credentialKind")),
            )
        signer = _require_exact_keyless_signer(permitted_signer)

        _require_descriptor(
            subject,
            code="keyless_subject_descriptor_invalid",
            expected_repository=expected_subject_repository,
            expected_media_type=expected_subject_media_type,
            expected_trust_policy=expected_trust_policy,
        )
        if subject.get("digest") != expected_subject_digest:
            raise TrustedKeylessVerificationError(
                "keyless_subject_digest_mismatch",
                expected_subject_digest,
            )
        if (
            _raw_digest(subject_bytes) != subject["digest"]
            or len(subject_bytes) != subject["size"]
        ):
            raise TrustedKeylessVerificationError(
                "keyless_subject_bytes_mismatch",
                subject["digest"],
            )

        if not isinstance(policy, dict) or rfc8785.dumps(policy) != policy_bytes:
            raise TrustedKeylessVerificationError(
                "keyless_policy_bytes_mismatch",
                expected_trust_policy["id"],
            )
        if (
            expected_trust_policy
            != {
                "id": policy.get("policyId"),
                "digest": _raw_digest(policy_bytes),
            }
            or subject["trustPolicy"] != expected_trust_policy
        ):
            raise TrustedKeylessVerificationError(
                "keyless_policy_mismatch",
                expected_trust_policy["id"],
            )
        scope = policy.get("scope")
        if not isinstance(scope, dict) or scope != {
            "repositories": [expected_subject_repository],
            "mediaTypes": [CONTRACT_BUNDLE_MEDIA_TYPE],
            "purposes": [CONTRACT_BUNDLE_RELEASE_PURPOSE],
        }:
            raise TrustedKeylessVerificationError(
                "keyless_policy_scope_mismatch",
                expected_trust_policy["id"],
            )
        policy_signers = policy.get("signers")
        if policy_signers != [signer]:
            raise TrustedKeylessVerificationError(
                "keyless_policy_signer_mismatch",
                expected_trust_policy["id"],
            )

        actual_signer_identity_digest = signer_identity_digest(signer)
        if (
            actual_signer_identity_digest != expected_signer_identity_digest
            or signing_request.get("signerIdentityDigest")
            != expected_signer_identity_digest
        ):
            raise TrustedKeylessVerificationError(
                "keyless_signer_identity_digest_mismatch",
                expected_signer_identity_digest,
            )
        if signer["trustedRootDigest"] != expected_trusted_root_digest:
            raise TrustedKeylessVerificationError(
                "keyless_trusted_root_mismatch",
                expected_trusted_root_digest,
            )
        if signer["claims"]["workflow"] != expected_workflow:
            raise TrustedKeylessVerificationError(
                "keyless_workflow_mismatch",
                expected_workflow,
            )
        if signer["workloadIdentity"] != expected_workload_identity:
            raise TrustedKeylessVerificationError(
                "keyless_workload_identity_mismatch",
                expected_workload_identity,
            )
        if signer["claims"] != expected_claims:
            raise TrustedKeylessVerificationError(
                "keyless_claims_mismatch",
                expected_workflow,
            )
        if (
            signer["claims"]["builderDigest"] != expected_builder_digest
            or signing_request.get("builderDigest") != expected_builder_digest
        ):
            raise TrustedKeylessVerificationError(
                "keyless_builder_mismatch",
                expected_builder_digest,
            )
        if (
            signing_request.get("preSignCertificationDigest")
            != expected_pre_sign_certification_digest
        ):
            raise TrustedKeylessVerificationError(
                "keyless_pre_sign_certification_mismatch",
                expected_pre_sign_certification_digest,
            )

        request_fields = {
            "contract",
            "schema",
            "requestId",
            "purpose",
            "credentialKind",
            "signerIdentityDigest",
            "builderDigest",
            "preSignCertificationDigest",
            "repository",
            "digest",
            "mediaType",
            "trustPolicy",
            "nonce",
            "issuedAt",
            "expiresAt",
        }
        if (
            set(signing_request) != request_fields
            or signing_request.get("contract") != "bytedesk.signing-request/1"
            or signing_request.get("purpose") != CONTRACT_BUNDLE_RELEASE_PURPOSE
            or signing_request.get("repository") != expected_subject_repository
            or signing_request.get("digest") != expected_subject_digest
            or signing_request.get("mediaType") != CONTRACT_BUNDLE_MEDIA_TYPE
            or signing_request.get("trustPolicy") != expected_trust_policy
        ):
            raise TrustedKeylessVerificationError(
                "keyless_signing_request_binding_mismatch",
                str(signing_request.get("requestId")),
            )
        request_digest = _raw_digest(signing_request_bytes)
        if rfc8785.dumps(signing_request) != signing_request_bytes:
            raise TrustedKeylessVerificationError(
                "keyless_signing_request_bytes_mismatch",
                str(signing_request.get("requestId")),
            )
        _require_descriptor(
            signing_request_descriptor,
            code="keyless_signing_request_descriptor_mismatch",
            expected_repository=expected_subject_repository,
            expected_media_type=SIGNING_REQUEST_MEDIA_TYPE,
        )
        if (
            request_digest != signing_request_descriptor["digest"]
            or request_digest != expected_signing_request_digest
            or len(signing_request_bytes) != signing_request_descriptor["size"]
        ):
            raise TrustedKeylessVerificationError(
                "keyless_signing_request_digest_mismatch",
                expected_signing_request_digest,
            )
        issued_at = _timestamp(
            signing_request["issuedAt"],
            "keyless_signing_request_time_invalid",
        )
        expires_at = _timestamp(
            signing_request["expiresAt"],
            "keyless_signing_request_time_invalid",
        )
        evaluated_at = _timestamp(
            verification_time,
            "keyless_verification_time_invalid",
        )
        if (
            issued_at >= expires_at
            or expires_at - issued_at > MAX_SIGNING_REQUEST_VALIDITY
            or evaluated_at < issued_at
            or evaluated_at >= expires_at
        ):
            raise TrustedKeylessVerificationError(
                "keyless_signing_request_not_current",
                signing_request["requestId"],
            )
        effective = policy.get("effective")
        if not isinstance(effective, dict) or not (
            _timestamp(
                effective.get("notBefore"),
                "keyless_policy_time_invalid",
            )
            <= evaluated_at
            < _timestamp(
                effective.get("notAfter"),
                "keyless_policy_time_invalid",
            )
        ):
            raise TrustedKeylessVerificationError(
                "keyless_policy_not_effective",
                verification_time,
            )

        _require_descriptor(
            signature_bundle_descriptor,
            code="keyless_signature_bundle_descriptor_mismatch",
            expected_repository=expected_subject_repository,
            expected_media_type=SIGSTORE_BUNDLE_MEDIA_TYPE,
        )
        if signature_bundle_descriptor["digest"] != expected_signature_bundle_digest:
            raise TrustedKeylessVerificationError(
                "keyless_signature_bundle_digest_mismatch",
                expected_signature_bundle_digest,
            )
        if (
            _raw_digest(signature_bundle_bytes) != signature_bundle_descriptor["digest"]
            or len(signature_bundle_bytes) != signature_bundle_descriptor["size"]
        ):
            raise TrustedKeylessVerificationError(
                "keyless_signature_bundle_digest_mismatch",
                expected_signature_bundle_digest,
            )

        revocations = policy.get("revocations")
        if not isinstance(revocations, dict) or set(revocations) != {
            "keyVersions",
            "digests",
            "workflows",
            "builders",
            "schemas",
            "renderers",
            "content",
        }:
            raise TrustedKeylessVerificationError(
                "keyless_policy_revocations_invalid",
                expected_trust_policy["id"],
            )
        revoked = (
            expected_trusted_root_digest in revocations["digests"]
            or expected_subject_digest in revocations["digests"]
            or expected_signing_request_digest in revocations["digests"]
            or expected_signature_bundle_digest in revocations["digests"]
            or expected_pre_sign_certification_digest in revocations["digests"]
            or expected_subject_digest in revocations["content"]
            or expected_workflow in revocations["workflows"]
            or expected_builder_digest in revocations["builders"]
        )
        if revoked:
            raise TrustedKeylessVerificationError(
                "keyless_signature_revoked",
                signing_request["requestId"],
            )

        expected_vector = keyless_signature_verification_vector(
            vector_id="",
            subject=subject,
            purpose=expected_purpose,
            signer_identity_digest_value=expected_signer_identity_digest,
            trusted_root_digest=expected_trusted_root_digest,
            authenticated_signer=signer,
            builder_digest=expected_builder_digest,
            pre_sign_certification_digest=expected_pre_sign_certification_digest,
            signing_request=signing_request_descriptor,
            signing_request_digest=expected_signing_request_digest,
            signature_bundle=signature_bundle_descriptor,
            signature_bundle_digest=expected_signature_bundle_digest,
            trust_policy=expected_trust_policy,
            verified_at=verification_time,
        )
        matches = [
            vector
            for vector in self._vectors
            if all(
                vector[field] == expected_vector[field]
                for field in self._fields
                if field != "vectorId"
            )
        ]
        if len(matches) != 1:
            raise TrustedKeylessVerificationError(
                "keyless_signature_not_verified",
                signing_request["requestId"],
            )
        vector = matches[0]
        receipt = {
            "profile": KEYLESS_VERIFICATION_PROFILE,
            **deepcopy(vector),
        }
        receipt["verificationEvidenceDigest"] = _canonical_digest(
            {
                "profile": KEYLESS_VERIFICATION_EVIDENCE_PROFILE,
                **deepcopy(receipt),
            }
        )
        return receipt
