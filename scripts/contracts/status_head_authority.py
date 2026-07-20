#!/usr/bin/env python3
"""Reusable release-status head authority construction.

The builder is deliberately storage- and signer-agnostic.  Callers provide the
same closed descriptor, signing, and document-registration adapters used by
their fixture or production boundary; this module owns all Merkle/head
semantics so public selection and consumer-private compilation cannot drift.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from renderer_authority import schema_field_authority_preimage
from signing_authority import signer_authority_binding_digest
from status_merkle import (
    consistency_proof as merkle_consistency_proof,
    inclusion_proof as merkle_inclusion_proof,
    merkle_root,
    status_leaf_digest,
)


class StatusHeadAuthorityError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise StatusHeadAuthorityError(code, detail)


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise StatusHeadAuthorityError(
            "status_head_timestamp_invalid", str(value)
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StatusHeadAuthorityError("status_head_timestamp_invalid", str(value))
    return parsed.astimezone(timezone.utc)


class StatusHeadAuthorityBuilder:
    """Build one nonce-bound, Merkle-proven release-status head refresh."""

    def __init__(
        self,
        *,
        schema_descriptor: Callable[[str], dict[str, str]],
        artifact_descriptor: Callable[
            [str, str, dict[str, Any], dict[str, Any]], dict[str, Any]
        ],
        sign_inline_authority: Callable[..., None],
        signing_result: Callable[..., dict[str, Any]],
        signer: Callable[[str], dict[str, Any]],
        register_document: Callable[[str, dict[str, Any]], None],
        canonical_digest: Callable[[Any], str],
        status_head_auth_schema: dict[str, Any],
        status_head_trust: dict[str, Any],
        repository: str = "registry.example/product/status-heads",
        purpose: str = "release-status-head-v1",
    ) -> None:
        self.schema_descriptor = schema_descriptor
        self.artifact_descriptor = artifact_descriptor
        self.sign_inline_authority = sign_inline_authority
        self.signing_result = signing_result
        self.signer = signer
        self.register_document = register_document
        self.canonical_digest = canonical_digest
        self.status_head_auth_schema = deepcopy(status_head_auth_schema)
        self.status_head_trust = deepcopy(status_head_trust)
        self.repository = repository
        self.purpose = purpose

    def _descriptor(
        self, media_type: str, document: dict[str, Any]
    ) -> dict[str, Any]:
        return self.artifact_descriptor(
            self.repository,
            media_type,
            document,
            self.status_head_trust,
        )

    def _inclusion_proof(
        self,
        *,
        checkpoint_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        epoch: int,
        log_leaves: list[str],
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        tree_size = len(log_leaves)
        _require(
            tree_size > 0 and tree_size == status.get("sequence"),
            "status_head_tree_sequence_mismatch",
            checkpoint_id,
        )
        leaf_digest = status_leaf_digest(
            subject_kind=subject_kind,
            subject=subject,
            sequence=status["sequence"],
            epoch=epoch,
            head=status_descriptor,
        )
        _require(
            log_leaves[-1] == leaf_digest,
            "status_head_tail_leaf_mismatch",
            checkpoint_id,
        )
        proof_id = f"{checkpoint_id}-head-inclusion"
        proof = {
            "contract": "bytedesk.release-status-log-inclusion-proof/1",
            "schema": self.schema_descriptor(
                "release-status-log-inclusion-proof"
            ),
            "proofId": proof_id,
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "treeSize": tree_size,
            "leafIndex": tree_size - 1,
            "leafDigest": leaf_digest,
            "rootDigest": merkle_root(log_leaves),
            "algorithm": "bytedesk-rfc6962-head-inclusion-v1",
            "auditPath": merkle_inclusion_proof(log_leaves, tree_size - 1),
            "trustPolicy": deepcopy(self.status_head_trust),
        }
        self.register_document(proof_id, proof)
        descriptor = self._descriptor(
            "application/vnd.bytedesk.agent."
            "release-status-log-inclusion-proof.v1+json",
            proof,
        )
        return leaf_digest, proof, descriptor

    def _consistency_proof(
        self,
        *,
        proof_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        prior_checkpoint: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        epoch: int,
        log_leaves: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from_endpoint = {
            "treeSize": prior_checkpoint["treeSize"],
            "sequence": prior_checkpoint["sequence"],
            "epoch": prior_checkpoint["epoch"],
            "headDigest": prior_checkpoint["headDigest"],
            "logRootDigest": prior_checkpoint["logRootDigest"],
        }
        to_endpoint = {
            "treeSize": len(log_leaves),
            "sequence": status["sequence"],
            "epoch": epoch,
            "headDigest": status_descriptor["digest"],
            "logRootDigest": merkle_root(log_leaves),
        }
        audit_path = merkle_consistency_proof(
            log_leaves, prior_checkpoint["treeSize"]
        )
        proof = {
            "contract": "bytedesk.release-status-log-consistency-proof/1",
            "schema": self.schema_descriptor(
                "release-status-log-consistency-proof"
            ),
            "proofId": proof_id,
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "from": from_endpoint,
            "to": deepcopy(to_endpoint),
            "algorithm": "bytedesk-rfc6962-prefix-consistency-v1",
            "auditPath": deepcopy(audit_path),
            "proofDataDigest": self.canonical_digest(
                {
                    "profile": (
                        "bytedesk.release-status-log-"
                        "consistency-proof-data/1"
                    ),
                    "subjectKind": subject_kind,
                    "subject": subject,
                    "from": from_endpoint,
                    "to": to_endpoint,
                    "algorithm": "bytedesk-rfc6962-prefix-consistency-v1",
                    "auditPath": audit_path,
                }
            ),
            "authorityBindingDigest": signer_authority_binding_digest(
                signer=self.signer(self.purpose),
                trust_policy=self.status_head_trust,
                repository=self.repository,
            ),
            "trustPolicy": deepcopy(self.status_head_trust),
        }
        self.sign_inline_authority(
            proof,
            "release-status-log-consistency-proof",
            self.purpose,
            "application/vnd.bytedesk.agent."
            "release-status-log-consistency-proof.v1+json",
            proof_id,
            self.status_head_trust,
            self.repository,
        )
        self.register_document(proof_id, proof)
        descriptor = self._descriptor(
            "application/vnd.bytedesk.agent."
            "release-status-log-consistency-proof.v1+json",
            proof,
        )
        return proof, descriptor

    def refresh(
        self,
        *,
        checkpoint_id: str,
        request_nonce: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        epoch: int,
        log_leaves: list[str],
        operation_time: str,
        expires_at: str,
        prior_checkpoint: dict[str, Any] | None = None,
        prior_checkpoint_descriptor: dict[str, Any] | None = None,
        consistency_proof_id: str | None = None,
    ) -> dict[str, Any]:
        _require(
            (prior_checkpoint is None) == (prior_checkpoint_descriptor is None),
            "status_head_prior_state_incomplete",
            checkpoint_id,
        )
        _require(
            _timestamp(operation_time) <= _timestamp(expires_at),
            "status_head_expiry_invalid",
            checkpoint_id,
        )
        _require(
            status.get("subjectKind") == subject_kind
            and status.get("subject") == subject
            and status_descriptor.get("digest")
            == self.canonical_digest(status),
            "status_head_status_binding_mismatch",
            checkpoint_id,
        )
        _require(
            _timestamp(status["effectiveAt"]) <= _timestamp(operation_time),
            "status_head_status_not_effective",
            checkpoint_id,
        )
        tree_size = len(log_leaves)
        head_leaf_digest, inclusion, inclusion_descriptor = (
            self._inclusion_proof(
                checkpoint_id=checkpoint_id,
                subject_kind=subject_kind,
                subject=subject,
                status=status,
                status_descriptor=status_descriptor,
                epoch=epoch,
                log_leaves=log_leaves,
            )
        )
        log_root_digest = merkle_root(log_leaves)
        consistency: dict[str, Any] | None = None
        consistency_descriptor: dict[str, Any] | None = None
        if prior_checkpoint is None:
            client_prior_state = {"kind": "none"}
        else:
            _require(
                prior_checkpoint["subjectKind"] == subject_kind
                and prior_checkpoint["subject"] == subject,
                "status_head_prior_subject_mismatch",
                checkpoint_id,
            )
            client_prior_state = {
                "kind": "match",
                "checkpoint": deepcopy(prior_checkpoint_descriptor),
                "sequence": prior_checkpoint["sequence"],
                "epoch": prior_checkpoint["epoch"],
                "treeSize": prior_checkpoint["treeSize"],
                "logRootDigest": prior_checkpoint["logRootDigest"],
                "headLeafDigest": prior_checkpoint["headLeafDigest"],
            }
            unchanged = (
                tree_size == prior_checkpoint["treeSize"]
                and status["sequence"] == prior_checkpoint["sequence"]
                and status_descriptor == prior_checkpoint["head"]
                and epoch == prior_checkpoint["epoch"]
                and log_root_digest == prior_checkpoint["logRootDigest"]
                and head_leaf_digest == prior_checkpoint["headLeafDigest"]
            )
            if not unchanged:
                _require(
                    tree_size > prior_checkpoint["treeSize"]
                    and status["sequence"] > prior_checkpoint["sequence"]
                    and epoch >= prior_checkpoint["epoch"],
                    "status_head_rollback_or_equivocation",
                    checkpoint_id,
                )
                consistency, consistency_descriptor = self._consistency_proof(
                    proof_id=(
                        consistency_proof_id
                        or f"{checkpoint_id}-consistency"
                    ),
                    subject_kind=subject_kind,
                    subject=subject,
                    prior_checkpoint=prior_checkpoint,
                    status=status,
                    status_descriptor=status_descriptor,
                    epoch=epoch,
                    log_leaves=log_leaves,
                )

        checkpoint = {
            "contract": "bytedesk.release-status-head-checkpoint/1",
            "schema": self.schema_descriptor("release-status-head-checkpoint"),
            "checkpointId": checkpoint_id,
            "requestNonce": request_nonce,
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "sequence": status["sequence"],
            "treeSize": tree_size,
            "head": deepcopy(status_descriptor),
            "headDigest": status_descriptor["digest"],
            "headLeafDigest": head_leaf_digest,
            "headInclusionProof": deepcopy(inclusion_descriptor),
            "epoch": epoch,
            "logRootDigest": log_root_digest,
            "clientPriorState": client_prior_state,
            "consistencyProof": deepcopy(consistency_descriptor),
            "verifiedAt": operation_time,
            "expiresAt": expires_at,
            "trustPolicy": deepcopy(self.status_head_trust),
        }
        self.register_document(checkpoint_id, checkpoint)
        checkpoint_descriptor = self._descriptor(
            "application/vnd.bytedesk.agent."
            "release-status-head-checkpoint.v1+json",
            checkpoint,
        )
        authentication = {
            "contract": (
                "bytedesk.release-status-head-authentication-evidence/1"
            ),
            "schema": self.schema_descriptor(
                "release-status-head-authentication-evidence"
            ),
            "purpose": self.purpose,
            "checkpointDigest": checkpoint_descriptor["digest"],
            "requestNonce": request_nonce,
            "authorityBindingDigest": signer_authority_binding_digest(
                signer=self.signer(self.purpose),
                trust_policy=self.status_head_trust,
                repository=self.repository,
            ),
            "signingResult": self.signing_result(
                self.purpose,
                checkpoint_descriptor["digest"],
                "application/vnd.bytedesk.agent."
                "release-status-head-checkpoint.v1+json",
                checkpoint_id,
                self.status_head_trust,
                self.repository,
            ),
            "evidenceDigest": "sha256:" + ("0" * 64),
        }
        authentication["evidenceDigest"] = self.canonical_digest(
            schema_field_authority_preimage(
                authentication,
                self.status_head_auth_schema,
                "evidenceDigest",
            )
        )
        authentication_id = f"{checkpoint_id}-authentication-evidence"
        self.register_document(authentication_id, authentication)
        authentication_descriptor = self._descriptor(
            "application/vnd.bytedesk.agent."
            "release-status-head-authentication-evidence.v1+json",
            authentication,
        )
        return {
            "checkpoint": checkpoint,
            "checkpointDescriptor": checkpoint_descriptor,
            "authentication": authentication,
            "authenticationDescriptor": authentication_descriptor,
            "inclusionProof": inclusion,
            "inclusionProofDescriptor": inclusion_descriptor,
            "consistencyProof": consistency,
            "consistencyProofDescriptor": consistency_descriptor,
        }
