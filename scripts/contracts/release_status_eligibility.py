#!/usr/bin/env python3
"""Reusable stage-bound release-status eligibility construction.

This module owns the closed eligibility aggregate and the uniform verification
result shape shared by product finalization, public publication, private
compilation, and activation.  It deliberately does not fetch artifacts or
perform cryptography: callers must supply already resolved status-head objects
and permitted verifier evidence produced by their trusted adapters.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable


STATUS_ELIGIBILITY_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent."
    "release-status-eligibility-evidence.v1+json"
)
STATUS_ELIGIBILITY_DIGEST_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent."
    "release-status-eligibility-evidence-digest.v1+json"
)
PRODUCT_STAGES = {
    "qualification_finalization",
    "public_render_finalization",
    "public_render_publication",
}
CONSUMER_STAGES = {"private_compilation", "activation"}


class ReleaseStatusEligibilityError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise ReleaseStatusEligibilityError(code, detail)


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ReleaseStatusEligibilityError(
            "release_status_eligibility_timestamp_invalid", str(value)
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReleaseStatusEligibilityError(
            "release_status_eligibility_timestamp_invalid", str(value)
        )
    return parsed.astimezone(timezone.utc)


def permitted_verification_result(
    *,
    schema_descriptor: dict[str, str],
    verification_id: str,
    subject: dict[str, Any],
    policy: dict[str, str],
    evaluated_at: str,
    evidence_digests: list[str],
) -> dict[str, Any]:
    """Return one closed permitted ``bytedesk.verification-result/1``.

    ``evidence_digests`` may bind a trusted KMS adapter result, a deterministic
    mathematical-verifier statement, or both.  Sorting makes the set stable;
    semantic roles remain encoded in the evidence objects those digests name.
    """

    ordered = sorted(set(evidence_digests), key=lambda value: value.encode("utf-8"))
    _require(
        len(ordered) == len(evidence_digests) and len(ordered) > 0,
        "release_status_verification_evidence_invalid",
        verification_id,
    )
    _timestamp(evaluated_at)
    return {
        "contract": "bytedesk.verification-result/1",
        "schema": deepcopy(schema_descriptor),
        "verificationId": verification_id,
        "subject": deepcopy(subject),
        "policy": deepcopy(policy),
        "evaluatedAt": evaluated_at,
        "outcome": "permitted",
        "reasonCodes": [],
        "evidenceDigests": ordered,
    }


class ReleaseStatusEligibilityBuilder:
    """Construct one purpose- and stage-separated eligibility object.

    Each entry supplied to :meth:`build` contains the emitted descriptor fields
    plus private ``*Document`` members used only for construction-time binding
    checks.  This prevents a generator from accidentally signing descriptors
    that do not name the exact current status, nonce-bound checkpoint, and
    proofs it evaluated.
    """

    _emitted_status_fields = (
        "subjectKind",
        "subject",
        "status",
        "checkpoint",
        "checkpointAuthenticationEvidence",
        "requestNonce",
        "clientPriorState",
        "headInclusionProof",
        "consistencyProof",
        "verificationEvidenceDigests",
    )
    _renderer_fields = (
        "harnessId",
        "rendererId",
        "rendererVersion",
        "targetPlatform",
    )

    def __init__(
        self,
        *,
        schema_descriptor: Callable[[str], dict[str, str]],
        artifact_descriptor: Callable[
            [str, str, dict[str, Any], dict[str, str]], dict[str, Any]
        ],
        signing_result: Callable[..., dict[str, Any]],
        canonical_digest: Callable[[Any], str],
        eligibility_schema: dict[str, Any],
        trust_policy: dict[str, str],
        repository: str,
        consumer_id: str | None,
        pin_set_descriptor: dict[str, Any],
        pin_set_digest: str,
        pin_set_provider_evidence: dict[str, Any],
        register_document: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.schema_descriptor = schema_descriptor
        self.artifact_descriptor = artifact_descriptor
        self.signing_result = signing_result
        self.canonical_digest = canonical_digest
        self.eligibility_schema = deepcopy(eligibility_schema)
        self.trust_policy = deepcopy(trust_policy)
        self.repository = repository
        self.consumer_id = consumer_id
        self.pin_set_descriptor = deepcopy(pin_set_descriptor)
        self.pin_set_digest = pin_set_digest
        self.pin_set_provider_evidence = deepcopy(pin_set_provider_evidence)
        self.register_document = register_document

    def _entry(
        self,
        raw: dict[str, Any],
        *,
        operation_time: str,
        expected_kind: str,
    ) -> dict[str, Any]:
        status_document = raw["statusDocument"]
        checkpoint_document = raw["checkpointDocument"]
        checkpoint_authentication_document = raw[
            "checkpointAuthenticationEvidenceDocument"
        ]
        inclusion_document = raw["headInclusionProofDocument"]
        consistency_document = raw.get("consistencyProofDocument")
        _require(
            raw["subjectKind"] == expected_kind
            and status_document["subjectKind"] == expected_kind
            and checkpoint_document["subjectKind"] == expected_kind
            and inclusion_document["subjectKind"] == expected_kind,
            "release_status_eligibility_subject_kind_mismatch",
            raw.get("subjectKind", "missing"),
        )
        _require(
            status_document["subject"] == raw["subject"]
            and checkpoint_document["subject"] == raw["subject"]
            and inclusion_document["subject"] == raw["subject"],
            "release_status_eligibility_subject_mismatch",
            raw["subject"]["digest"],
        )
        _require(
            status_document["status"] == "current"
            and _timestamp(status_document["effectiveAt"])
            <= _timestamp(operation_time),
            "release_status_eligibility_status_not_current",
            raw["status"]["digest"],
        )
        _require(
            raw["status"]["digest"] == self.canonical_digest(status_document)
            and checkpoint_document["head"] == raw["status"]
            and checkpoint_document["headDigest"] == raw["status"]["digest"]
            and raw["checkpoint"]["digest"]
            == self.canonical_digest(checkpoint_document),
            "release_status_eligibility_head_binding_mismatch",
            raw["checkpoint"]["digest"],
        )
        _require(
            checkpoint_document["requestNonce"] == raw["requestNonce"]
            and checkpoint_document["clientPriorState"]
            == raw["clientPriorState"]
            and checkpoint_document["verifiedAt"] == operation_time
            and _timestamp(checkpoint_document["verifiedAt"])
            <= _timestamp(operation_time)
            < _timestamp(checkpoint_document["expiresAt"]),
            "release_status_eligibility_checkpoint_freshness_mismatch",
            raw["checkpoint"]["digest"],
        )
        _require(
            raw["checkpointAuthenticationEvidence"]["digest"]
            == self.canonical_digest(checkpoint_authentication_document)
            and checkpoint_authentication_document["checkpointDigest"]
            == raw["checkpoint"]["digest"]
            and checkpoint_authentication_document["requestNonce"]
            == raw["requestNonce"],
            "release_status_eligibility_checkpoint_authentication_mismatch",
            raw["checkpoint"]["digest"],
        )
        _require(
            checkpoint_document["headInclusionProof"]
            == raw["headInclusionProof"]
            and raw["headInclusionProof"]["digest"]
            == self.canonical_digest(inclusion_document)
            and inclusion_document["rootDigest"]
            == checkpoint_document["logRootDigest"]
            and inclusion_document["leafDigest"]
            == checkpoint_document["headLeafDigest"]
            and inclusion_document["treeSize"] == checkpoint_document["treeSize"],
            "release_status_eligibility_inclusion_binding_mismatch",
            raw["headInclusionProof"]["digest"],
        )
        if raw["consistencyProof"] is None:
            _require(
                checkpoint_document["consistencyProof"] is None
                and consistency_document is None,
                "release_status_eligibility_consistency_binding_mismatch",
                raw["checkpoint"]["digest"],
            )
        else:
            _require(
                consistency_document is not None
                and checkpoint_document["consistencyProof"]
                == raw["consistencyProof"]
                and raw["consistencyProof"]["digest"]
                == self.canonical_digest(consistency_document)
                and consistency_document["subject"] == raw["subject"]
                and consistency_document["to"]["headDigest"]
                == raw["status"]["digest"]
                and consistency_document["to"]["logRootDigest"]
                == checkpoint_document["logRootDigest"]
                and consistency_document["to"]["treeSize"]
                == checkpoint_document["treeSize"],
                "release_status_eligibility_consistency_binding_mismatch",
                raw["consistencyProof"]["digest"],
            )
        verification = raw["verificationEvidenceDigests"]
        _require(
            set(verification)
            == {
                "status",
                "checkpointAuthentication",
                "headInclusionProof",
                "consistencyProof",
            }
            and all(
                isinstance(verification[field], str)
                and verification[field].startswith("sha256:")
                for field in (
                    "status",
                    "checkpointAuthentication",
                    "headInclusionProof",
                )
            )
            and (
                (raw["consistencyProof"] is None and verification["consistencyProof"] is None)
                or (
                    raw["consistencyProof"] is not None
                    and isinstance(verification["consistencyProof"], str)
                    and verification["consistencyProof"].startswith("sha256:")
                )
            ),
            "release_status_eligibility_verification_evidence_invalid",
            raw["subject"]["digest"],
        )
        emitted = {
            field: deepcopy(raw[field]) for field in self._emitted_status_fields
        }
        if expected_kind == "renderer_release":
            for field in self._renderer_fields:
                emitted[field] = deepcopy(raw[field])
        return emitted

    def build(
        self,
        *,
        evidence_id: str,
        stage: str,
        operation_time: str,
        product: dict[str, Any],
        renderers: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        _timestamp(operation_time)
        if stage in PRODUCT_STAGES:
            purpose = "release-status-eligibility-v1"
            _require(
                self.consumer_id is None,
                "release_status_eligibility_consumer_scope_mismatch",
                stage,
            )
        elif stage in CONSUMER_STAGES:
            purpose = "consumer-release-status-eligibility-v1"
            _require(
                isinstance(self.consumer_id, str),
                "release_status_eligibility_consumer_scope_mismatch",
                stage,
            )
        else:
            raise ReleaseStatusEligibilityError(
                "release_status_eligibility_stage_invalid", stage
            )
        _require(
            self.trust_policy["id"] == purpose,
            "release_status_eligibility_purpose_mismatch",
            stage,
        )
        _require(
            self.pin_set_provider_evidence["pinSet"]
            == self.pin_set_descriptor
            and self.pin_set_provider_evidence["pinSetDigest"]
            == self.pin_set_digest
            and self.pin_set_provider_evidence["consumerId"]
            == self.consumer_id
            and _timestamp(
                self.pin_set_provider_evidence["readback"]["observedAt"]
            )
            <= _timestamp(operation_time),
            "release_status_eligibility_pin_provider_mismatch",
            stage,
        )
        emitted_product = self._entry(
            product,
            operation_time=operation_time,
            expected_kind="product_release",
        )
        _require(
            len(renderers) > 0,
            "release_status_eligibility_renderer_set_empty",
            stage,
        )
        emitted_renderers = [
            self._entry(
                renderer,
                operation_time=operation_time,
                expected_kind="renderer_release",
            )
            for renderer in renderers
        ]
        ordering = lambda entry: (
            entry["harnessId"].encode("utf-8"),
            entry["rendererId"].encode("utf-8"),
            entry["rendererVersion"].encode("utf-8"),
            entry["targetPlatform"].encode("utf-8"),
            entry["subject"]["digest"].encode("utf-8"),
        )
        _require(
            emitted_renderers == sorted(emitted_renderers, key=ordering)
            and len(
                {
                    (
                        entry["harnessId"],
                        entry["rendererId"],
                        entry["rendererVersion"],
                        entry["targetPlatform"],
                        entry["subject"]["digest"],
                    )
                    for entry in emitted_renderers
                }
            )
            == len(emitted_renderers),
            "release_status_eligibility_renderer_set_invalid",
            stage,
        )
        document = {
            "contract": "bytedesk.release-status-eligibility-evidence/1",
            "schema": self.schema_descriptor(
                "release-status-eligibility-evidence"
            ),
            "evidenceId": evidence_id,
            "stage": stage,
            "operationTime": operation_time,
            "consumerId": self.consumer_id,
            "pinSet": deepcopy(self.pin_set_descriptor),
            "pinSetDigest": self.pin_set_digest,
            "pinSetProviderEvidence": deepcopy(
                self.pin_set_provider_evidence
            ),
            "product": emitted_product,
            "renderers": emitted_renderers,
            "decision": "eligible",
            "eligibilityDigest": "sha256:" + ("0" * 64),
            "trustPolicy": deepcopy(self.trust_policy),
            "signingResult": {},
        }
        authority = self.eligibility_schema.get(
            "x-bytedesk-digestAuthority"
        )
        _require(
            isinstance(authority, dict)
            and authority.get("profile")
            == "bytedesk.release-status-eligibility-evidence-digest/1"
            and authority.get("exclude")
            == ["contract", "schema", "eligibilityDigest", "signingResult"],
            "release_status_eligibility_digest_authority_invalid",
            stage,
        )
        document["eligibilityDigest"] = self.canonical_digest(
            {
                "profile": authority["profile"],
                **{
                    field: deepcopy(value)
                    for field, value in document.items()
                    if field not in authority["exclude"]
                },
            }
        )
        document["signingResult"] = self.signing_result(
            purpose,
            document["eligibilityDigest"],
            STATUS_ELIGIBILITY_DIGEST_MEDIA_TYPE,
            evidence_id,
            self.trust_policy,
            self.repository,
        )
        if self.register_document is not None:
            self.register_document(evidence_id, document)
        descriptor = self.artifact_descriptor(
            self.repository,
            STATUS_ELIGIBILITY_MEDIA_TYPE,
            document,
            self.trust_policy,
        )
        return document, descriptor
