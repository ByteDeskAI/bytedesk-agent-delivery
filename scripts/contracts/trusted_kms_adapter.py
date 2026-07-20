#!/usr/bin/env python3
"""Trusted KMS signature-verification seam for offline contract conformance."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from typing import Any

import rfc8785

from release_status_eligibility import permitted_verification_result


CONTRACT_BUNDLE_RELEASE_PURPOSE = "contract-bundle-release-v1"
CONTRACT_BUNDLE_MEDIA_TYPES = frozenset(
    {
        "application/vnd.bytedesk.agent.contract-bundle.v1+json",
        "application/vnd.bytedesk.agent.contract-bundle.v1+tar",
    }
)


class TrustedKmsVerificationError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise TrustedKmsVerificationError("kms_verification_time_invalid", value)
    return parsed.astimezone(timezone.utc)


def _canonical_digest(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def _reject_contract_bundle_kms_authority(
    *,
    purpose: Any,
    subject_media_type: Any,
) -> None:
    if (
        purpose == CONTRACT_BUNDLE_RELEASE_PURPOSE
        or (
            isinstance(subject_media_type, str)
            and subject_media_type in CONTRACT_BUNDLE_MEDIA_TYPES
        )
    ):
        raise TrustedKmsVerificationError(
            "kms_contract_bundle_keyless_only",
            f"{purpose}:{subject_media_type}",
        )


def signature_verification_vector(
    *,
    vector_id: str,
    request_id: str,
    purpose: str,
    signature_bundle: dict[str, Any],
    subject_digest: str,
    subject_media_type: str,
    key_version: str,
    public_key_digest: str,
    algorithm: str,
    trust_policy: dict[str, str],
    signing_repository: str,
    pin_set_digest: str,
    consumer_id: str | None,
    provider_audit_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Build one externally pinned test-adapter cryptographic result vector."""

    _reject_contract_bundle_kms_authority(
        purpose=purpose,
        subject_media_type=subject_media_type,
    )

    return {
        "vectorId": vector_id,
        "requestId": request_id,
        "purpose": purpose,
        "signatureBundle": deepcopy(signature_bundle),
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "keyVersion": key_version,
        "publicKeyDigest": public_key_digest,
        "algorithm": algorithm,
        "trustPolicy": deepcopy(trust_policy),
        "signingRepository": signing_repository,
        "pinSetDigest": pin_set_digest,
        "consumerId": consumer_id,
        "providerAuditEvidence": deepcopy(provider_audit_evidence),
        "decision": "permitted",
    }


class TrustedKmsVerificationAdapter:
    """Model the declared kms-signing verify-signature Adapter trust boundary.

    Fixture bundle bytes are opaque input. A cryptographic result is accepted
    only when an independently supplied adapter vector pins the complete
    bundle/subject/key/policy tuple. Policy validity and revocations are then
    evaluated at the caller-supplied verification time.
    """

    _fields = {
        "vectorId",
        "requestId",
        "purpose",
        "signatureBundle",
        "subjectDigest",
        "subjectMediaType",
        "keyVersion",
        "publicKeyDigest",
        "algorithm",
        "trustPolicy",
        "signingRepository",
        "pinSetDigest",
        "consumerId",
        "providerAuditEvidence",
        "decision",
    }

    def __init__(self, vectors: list[dict[str, Any]]) -> None:
        self._vectors: list[dict[str, Any]] = []
        vector_ids: set[str] = set()
        tuple_keys: set[str] = set()
        for vector in vectors:
            if set(vector) != self._fields or vector["decision"] != "permitted":
                raise TrustedKmsVerificationError(
                    "kms_verification_vector_invalid",
                    str(vector.get("vectorId")),
                )
            _reject_contract_bundle_kms_authority(
                purpose=vector["purpose"],
                subject_media_type=vector["subjectMediaType"],
            )
            vector_id = vector["vectorId"]
            # A vector is an independent provider assertion over the complete
            # verification context.  Do not allow two vector IDs to make the
            # same request appear independently authenticated, including when
            # the only contextual difference would otherwise be a consumer,
            # media type, key identity, or provider-audit object.
            tuple_key = _canonical_digest(
                {
                    key: deepcopy(value)
                    for key, value in vector.items()
                    if key not in {"vectorId", "decision"}
                }
            )
            if vector_id in vector_ids or tuple_key in tuple_keys:
                raise TrustedKmsVerificationError(
                    "kms_verification_vector_duplicate",
                    vector_id,
                )
            vector_ids.add(vector_id)
            tuple_keys.add(tuple_key)
            self._vectors.append(deepcopy(vector))

    def verify(
        self,
        *,
        result: dict[str, Any],
        policy: dict[str, Any],
        permitted_signer: dict[str, Any],
        verification_time: str,
        expected_purpose: str,
        expected_subject_media_type: str,
        expected_signing_repository: str,
        pin_set_digest: str,
        pin_set_revocations: dict[str, list[str]],
        expected_consumer_id: str | None,
    ) -> dict[str, Any]:
        _reject_contract_bundle_kms_authority(
            purpose=expected_purpose,
            subject_media_type=expected_subject_media_type,
        )
        _reject_contract_bundle_kms_authority(
            purpose=result.get("purpose"),
            subject_media_type=result.get("subjectMediaType"),
        )
        if result["purpose"] != expected_purpose:
            raise TrustedKmsVerificationError(
                "kms_expected_purpose_mismatch",
                expected_purpose,
            )
        if result["subjectMediaType"] != expected_subject_media_type:
            raise TrustedKmsVerificationError(
                "kms_expected_subject_media_type_mismatch",
                expected_subject_media_type,
            )
        if result["repository"] != expected_signing_repository:
            raise TrustedKmsVerificationError(
                "kms_expected_signing_repository_mismatch",
                expected_signing_repository,
            )
        if set(pin_set_revocations) != {
            "policyDigests",
            "keyVersions",
            "publicKeyDigests",
        }:
            raise TrustedKmsVerificationError(
                "kms_pin_set_revocations_invalid",
                pin_set_digest,
            )
        expected = {
            "requestId": result["requestId"],
            "purpose": result["purpose"],
            "signatureBundle": result["signatureBundle"],
            "subjectDigest": result["subjectDigest"],
            "subjectMediaType": result["subjectMediaType"],
            "keyVersion": result["keyVersion"],
            "publicKeyDigest": result["publicKeyDigest"],
            "algorithm": result["algorithm"],
            "trustPolicy": result["trustPolicy"],
            "signingRepository": expected_signing_repository,
            "pinSetDigest": pin_set_digest,
            "consumerId": expected_consumer_id,
            "providerAuditEvidence": result["providerAuditEvidence"],
            "decision": "permitted",
        }
        matches = [
            vector
            for vector in self._vectors
            if all(vector[field] == value for field, value in expected.items())
        ]
        if len(matches) != 1:
            raise TrustedKmsVerificationError(
                "kms_signature_not_verified",
                result["requestId"],
            )
        evaluated_at = _timestamp(verification_time)
        if not (
            _timestamp(policy["effective"]["notBefore"])
            <= evaluated_at
            < _timestamp(policy["effective"]["notAfter"])
        ):
            raise TrustedKmsVerificationError(
                "kms_policy_not_effective_at_verification",
                verification_time,
            )
        revocations = policy["revocations"]
        signer_claims = permitted_signer["claims"]
        revoked = (
            result["keyVersion"] in revocations["keyVersions"]
            or result["publicKeyDigest"] in revocations["digests"]
            or result["subjectDigest"] in revocations["digests"]
            or result["subjectDigest"] in revocations["content"]
            or signer_claims["workflow"] in revocations["workflows"]
            or signer_claims["builderDigest"] in revocations["builders"]
            or result["trustPolicy"]["digest"]
            in pin_set_revocations["policyDigests"]
            or result["keyVersion"] in pin_set_revocations["keyVersions"]
            or result["publicKeyDigest"]
            in pin_set_revocations["publicKeyDigests"]
        )
        if revoked:
            raise TrustedKmsVerificationError(
                "kms_signature_revoked",
                result["requestId"],
            )
        vector = matches[0]
        request_digest = _canonical_digest(
            {
                "profile": "bytedesk.kms-signature-verification-request/1",
                "purpose": expected_purpose,
                "subjectDigest": result["subjectDigest"],
                "subjectMediaType": expected_subject_media_type,
                "signatureBundle": result["signatureBundle"],
                "signingRepository": expected_signing_repository,
                "trustPolicy": result["trustPolicy"],
                "pinSetDigest": pin_set_digest,
                "consumerId": expected_consumer_id,
                "providerAuditEvidence": result["providerAuditEvidence"],
                "verificationTime": verification_time,
            }
        )
        verification_result = {
            "decision": "permitted",
            "vectorId": vector["vectorId"],
            "requestDigest": request_digest,
            "signatureBundleDigest": result["signatureBundle"]["digest"],
            "subjectDigest": result["subjectDigest"],
            "purpose": expected_purpose,
            "subjectMediaType": expected_subject_media_type,
            "signingRepository": expected_signing_repository,
            "verificationTime": verification_time,
            "evaluatedPolicyDigest": result["trustPolicy"]["digest"],
            "pinSetDigest": pin_set_digest,
            "consumerId": expected_consumer_id,
            "authenticatedSigner": deepcopy(permitted_signer),
            "providerAuditEvidence": deepcopy(result["providerAuditEvidence"]),
            "providerAuditEvidenceDigest": result["providerAuditEvidence"]["digest"],
            "verificationEvidenceDigest": "sha256:" + ("0" * 64),
        }
        verification_result["verificationEvidenceDigest"] = _canonical_digest(
            {
                "profile": "bytedesk.kms-signature-verification-evidence/1",
                **{
                    key: deepcopy(value)
                    for key, value in verification_result.items()
                    if key != "verificationEvidenceDigest"
                },
            }
        )
        return verification_result

    def verify_permitted(
        self,
        *,
        result: dict[str, Any],
        policy: dict[str, Any],
        permitted_signer: dict[str, Any],
        verification_time: str,
        expected_purpose: str,
        expected_signed_subject_digest: str,
        expected_signed_subject_media_type: str,
        verification_subject: dict[str, Any],
        expected_signing_repository: str,
        pin_set_digest: str,
        pin_set_revocations: dict[str, list[str]],
        expected_consumer_id: str | None,
        verification_result_schema_descriptor: dict[str, str],
        verification_id: str,
    ) -> dict[str, Any]:
        """Return the uniform closed ``bytedesk.verification-result/1``.

        ``verify`` remains the detailed Adapter-evidence API for existing
        consumers.  New aggregate builders use this method so every signed
        object contributes the same schema-owned permitted-result digest as
        deterministic Merkle and graph verifiers.  The signed subject digest
        is explicit and may be a schema-owned ``authorityDigest``;
        ``verification_subject`` is the exact raw artifact descriptor exposed
        by the generic verification-result contract.  Its raw object media
        may differ from the signed digest/statement media; the caller's
        schema-owned artifact-to-statement binding proves that relationship.
        They are deliberately not conflated.
        """

        _reject_contract_bundle_kms_authority(
            purpose=expected_purpose,
            subject_media_type=expected_signed_subject_media_type,
        )
        _reject_contract_bundle_kms_authority(
            purpose=result.get("purpose"),
            subject_media_type=result.get("subjectMediaType"),
        )

        if set(verification_subject) != {
            "repository",
            "digest",
            "mediaType",
            "size",
            "trustPolicy",
        } or not (
            verification_subject["repository"]
            == expected_signing_repository
            and result["subjectDigest"] == expected_signed_subject_digest
            and result["subjectMediaType"]
            == expected_signed_subject_media_type
            and verification_subject["trustPolicy"]
            == result["trustPolicy"]
        ):
            raise TrustedKmsVerificationError(
                "kms_expected_subject_descriptor_mismatch",
                verification_id,
            )
        detailed = self.verify(
            result=result,
            policy=policy,
            permitted_signer=permitted_signer,
            verification_time=verification_time,
            expected_purpose=expected_purpose,
            expected_subject_media_type=expected_signed_subject_media_type,
            expected_signing_repository=expected_signing_repository,
            pin_set_digest=pin_set_digest,
            pin_set_revocations=pin_set_revocations,
            expected_consumer_id=expected_consumer_id,
        )
        return permitted_verification_result(
            schema_descriptor=verification_result_schema_descriptor,
            verification_id=verification_id,
            subject=verification_subject,
            policy=result["trustPolicy"],
            evaluated_at=verification_time,
            evidence_digests=[detailed["verificationEvidenceDigest"]],
        )
