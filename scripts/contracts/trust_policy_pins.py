#!/usr/bin/env python3
"""Versioned external trust-policy pin-set authority primitives."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable

import rfc8785
import hashlib


PIN_SET_PROFILE = "bytedesk.trust-policy-pin-set-digest/1"
PIN_SET_FIELDS = (
    "pinSetId",
    "scope",
    "consumerId",
    "revision",
    "precondition",
    "currentForNewUse",
    "historicalVerification",
    "revocations",
    "effective",
)
PIN_SET_MEDIA_TYPE = "application/vnd.bytedesk.agent.trust-policy-pin-set.v1+json"
PIN_SET_PROVIDER_EVIDENCE_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent."
    "trust-policy-pin-set-provider-evidence.v1+json"
)
PROVIDER_EVIDENCE_FIELDS = (
    "evidenceId",
    "requestId",
    "idempotencyKey",
    "requestDigest",
    "pinSet",
    "pinSetId",
    "scope",
    "consumerId",
    "revision",
    "pinSetDigest",
    "precondition",
    "providerId",
    "providerAuthorityDigest",
    "providerRequestId",
    "providerAuditId",
    "result",
    "activatedAt",
    "readback",
)


class TrustPolicyPinError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def pin_set_provider_authentication_vector(
    *,
    vector_id: str,
    provider_id: str,
    provider_authority_digest: str,
    provider_request_id: str,
    provider_audit_id: str,
    request_digest: str,
    pin_set_digest_value: str,
) -> dict[str, Any]:
    return {
        "vectorId": vector_id,
        "providerId": provider_id,
        "providerAuthorityDigest": provider_authority_digest,
        "providerRequestId": provider_request_id,
        "providerAuditId": provider_audit_id,
        "requestDigest": request_digest,
        "pinSetDigest": pin_set_digest_value,
        "decision": "authenticated",
    }


def _digest(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise TrustPolicyPinError("trust_pin_set_timestamp_invalid", str(value)) from error
    if parsed.tzinfo is None:
        raise TrustPolicyPinError("trust_pin_set_timestamp_invalid", str(value))
    return parsed.astimezone(timezone.utc)


def pin_set_preimage(pin_set: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in PIN_SET_FIELDS if field not in pin_set]
    if missing:
        raise TrustPolicyPinError("trust_pin_set_fields_invalid", str(missing))
    return {
        "profile": PIN_SET_PROFILE,
        **{field: deepcopy(pin_set[field]) for field in PIN_SET_FIELDS},
    }


def pin_set_digest(pin_set: dict[str, Any]) -> str:
    return _digest(pin_set_preimage(pin_set))


def pin_set_document_descriptor(
    *,
    repository: str,
    pin_set: dict[str, Any],
    provider_id: str,
    provider_authority_digest: str,
) -> dict[str, Any]:
    payload = rfc8785.dumps(pin_set)
    return {
        "repository": repository,
        "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "mediaType": PIN_SET_MEDIA_TYPE,
        "size": len(payload),
        "providerId": provider_id,
        "providerAuthorityDigest": provider_authority_digest,
    }


def pin_set_provider_request_digest(
    *,
    request_id: str,
    idempotency_key: str,
    pin_set_descriptor: dict[str, Any],
    pin_set_digest_value: str,
    precondition: dict[str, Any],
    provider_id: str,
    provider_authority_digest: str,
    operation_time: str,
) -> str:
    return _digest(
        {
            "profile": "bytedesk.trust-policy-pin-set-provider-request/1",
            "requestId": request_id,
            "idempotencyKey": idempotency_key,
            "pinSet": pin_set_descriptor,
            "pinSetDigest": pin_set_digest_value,
            "precondition": precondition,
            "providerId": provider_id,
            "providerAuthorityDigest": provider_authority_digest,
            "operationTime": operation_time,
        }
    )


def build_pin_set_provider_evidence(
    *,
    schema_descriptor: dict[str, str],
    evidence_id: str,
    request_id: str,
    idempotency_key: str,
    pin_set: dict[str, Any],
    pin_set_descriptor: dict[str, Any],
    provider_request_id: str,
    provider_audit_id: str,
    activated_at: str,
    observed_at: str,
) -> dict[str, Any]:
    provider_id = pin_set_descriptor["providerId"]
    provider_authority_digest = pin_set_descriptor["providerAuthorityDigest"]
    request_digest = pin_set_provider_request_digest(
        request_id=request_id,
        idempotency_key=idempotency_key,
        pin_set_descriptor=pin_set_descriptor,
        pin_set_digest_value=pin_set["pinSetDigest"],
        precondition=pin_set["precondition"],
        provider_id=provider_id,
        provider_authority_digest=provider_authority_digest,
        operation_time=activated_at,
    )
    evidence = {
        "contract": "bytedesk.trust-policy-pin-set-provider-evidence/1",
        "schema": deepcopy(schema_descriptor),
        "evidenceId": evidence_id,
        "requestId": request_id,
        "idempotencyKey": idempotency_key,
        "requestDigest": request_digest,
        "pinSet": deepcopy(pin_set_descriptor),
        "pinSetId": pin_set["pinSetId"],
        "scope": pin_set["scope"],
        "consumerId": pin_set["consumerId"],
        "revision": pin_set["revision"],
        "pinSetDigest": pin_set["pinSetDigest"],
        "precondition": deepcopy(pin_set["precondition"]),
        "providerId": provider_id,
        "providerAuthorityDigest": provider_authority_digest,
        "providerRequestId": provider_request_id,
        "providerAuditId": provider_audit_id,
        "result": "active",
        "activatedAt": activated_at,
        "readback": {
            "pinSet": deepcopy(pin_set_descriptor),
            "rawDigest": pin_set_descriptor["digest"],
            "observedAt": observed_at,
        },
        "evidenceDigest": "sha256:" + ("0" * 64),
    }
    evidence["evidenceDigest"] = _digest(
        {
            "profile": "bytedesk.trust-policy-pin-set-provider-evidence-digest/1",
            **{
                field: deepcopy(evidence[field])
                for field in PROVIDER_EVIDENCE_FIELDS
            },
        }
    )
    return evidence


class TrustedTrustPolicyProviderAdapter:
    """Verify pin-set activation/readback against external provider vectors."""

    _vector_fields = {
        "vectorId",
        "providerId",
        "providerAuthorityDigest",
        "providerRequestId",
        "providerAuditId",
        "requestDigest",
        "pinSetDigest",
        "decision",
    }

    def __init__(
        self,
        *,
        provider_id: str,
        provider_authority_digest: str,
        authentication_vectors: list[dict[str, Any]],
    ) -> None:
        self.provider_id = provider_id
        self.provider_authority_digest = provider_authority_digest
        self._vectors: dict[str, dict[str, Any]] = {}
        for vector in authentication_vectors:
            if (
                set(vector) != self._vector_fields
                or vector["decision"] != "authenticated"
                or vector["providerId"] != provider_id
                or vector["providerAuthorityDigest"] != provider_authority_digest
                or vector["vectorId"] in self._vectors
            ):
                raise TrustPolicyPinError(
                    "trust_pin_provider_vector_invalid",
                    str(vector.get("vectorId")),
                )
            self._vectors[vector["vectorId"]] = deepcopy(vector)

    def verify_activation(
        self,
        *,
        pin_set: dict[str, Any],
        pin_set_descriptor_value: dict[str, Any],
        evidence: dict[str, Any],
        verification_time: str,
    ) -> dict[str, Any]:
        expected_descriptor = pin_set_document_descriptor(
            repository=pin_set_descriptor_value["repository"],
            pin_set=pin_set,
            provider_id=self.provider_id,
            provider_authority_digest=self.provider_authority_digest,
        )
        if pin_set_descriptor_value != expected_descriptor:
            raise TrustPolicyPinError(
                "trust_pin_provider_descriptor_mismatch",
                pin_set.get("pinSetId", "unknown"),
            )
        expected_request_digest = pin_set_provider_request_digest(
            request_id=evidence["requestId"],
            idempotency_key=evidence["idempotencyKey"],
            pin_set_descriptor=expected_descriptor,
            pin_set_digest_value=pin_set["pinSetDigest"],
            precondition=pin_set["precondition"],
            provider_id=self.provider_id,
            provider_authority_digest=self.provider_authority_digest,
            operation_time=evidence["activatedAt"],
        )
        expected_evidence_digest = _digest(
            {
                "profile": "bytedesk.trust-policy-pin-set-provider-evidence-digest/1",
                **{
                    field: deepcopy(evidence[field])
                    for field in PROVIDER_EVIDENCE_FIELDS
                },
            }
        )
        if not (
            evidence["pinSet"] == expected_descriptor
            and evidence["pinSetId"] == pin_set["pinSetId"]
            and evidence["scope"] == pin_set["scope"]
            and evidence["consumerId"] == pin_set["consumerId"]
            and evidence["revision"] == pin_set["revision"]
            and evidence["pinSetDigest"] == pin_set["pinSetDigest"]
            and evidence["precondition"] == pin_set["precondition"]
            and evidence["providerId"] == self.provider_id
            and evidence["providerAuthorityDigest"]
            == self.provider_authority_digest
            and evidence["requestDigest"] == expected_request_digest
            and evidence["result"] == "active"
            and evidence["readback"]
            == {
                "pinSet": expected_descriptor,
                "rawDigest": expected_descriptor["digest"],
                "observedAt": evidence["readback"]["observedAt"],
            }
            and evidence["evidenceDigest"] == expected_evidence_digest
            and _timestamp(evidence["activatedAt"])
            <= _timestamp(evidence["readback"]["observedAt"])
            <= _timestamp(verification_time)
        ):
            raise TrustPolicyPinError(
                "trust_pin_provider_evidence_mismatch",
                pin_set["pinSetId"],
            )
        matches = [
            vector
            for vector in self._vectors.values()
            if vector["providerRequestId"] == evidence["providerRequestId"]
            and vector["providerAuditId"] == evidence["providerAuditId"]
            and vector["requestDigest"] == expected_request_digest
            and vector["pinSetDigest"] == pin_set["pinSetDigest"]
        ]
        if len(matches) != 1:
            raise TrustPolicyPinError(
                "trust_pin_provider_authentication_failed",
                evidence["providerRequestId"],
            )
        return {
            "decision": "active",
            "vectorId": matches[0]["vectorId"],
            "pinSet": deepcopy(expected_descriptor),
            "pinSetDigest": pin_set["pinSetDigest"],
            "providerAuthorityDigest": self.provider_authority_digest,
            "providerEvidenceDigest": evidence["evidenceDigest"],
            "readbackAt": evidence["readback"]["observedAt"],
        }


def build_initial_trust_policy_pin_set(
    *,
    schema_descriptor: dict[str, str],
    pin_set_id: str,
    scope: str,
    consumer_id: str | None,
    purposes: Iterable[str],
    trust_policy_references: dict[str, dict[str, str]],
    not_before: str,
    not_after: str,
) -> dict[str, Any]:
    ordered_purposes = tuple(purposes)
    pin_set = {
        "contract": "bytedesk.trust-policy-pin-set/1",
        "schema": deepcopy(schema_descriptor),
        "pinSetId": pin_set_id,
        "scope": scope,
        "consumerId": consumer_id,
        "revision": 1,
        "precondition": {"kind": "absent"},
        "currentForNewUse": [
            {
                "purpose": purpose,
                "trustPolicy": deepcopy(trust_policy_references[purpose]),
            }
            for purpose in ordered_purposes
        ],
        "historicalVerification": [],
        "revocations": {
            "policyDigests": [],
            "keyVersions": [],
            "publicKeyDigests": [],
        },
        "effective": {"notBefore": not_before, "notAfter": not_after},
        "pinSetDigest": "sha256:" + ("0" * 64),
    }
    pin_set["pinSetDigest"] = pin_set_digest(pin_set)
    return pin_set


def build_initial_product_pin_set(
    *,
    schema_descriptor: dict[str, str],
    pin_set_id: str,
    purposes: Iterable[str],
    trust_policy_references: dict[str, dict[str, str]],
    not_before: str,
    not_after: str,
) -> dict[str, Any]:
    return build_initial_trust_policy_pin_set(
        schema_descriptor=schema_descriptor,
        pin_set_id=pin_set_id,
        scope="product",
        consumer_id=None,
        purposes=purposes,
        trust_policy_references=trust_policy_references,
        not_before=not_before,
        not_after=not_after,
    )


class TrustPolicyPinSet:
    """Validated current/historical policy authority for one pin-set revision."""

    def __init__(
        self,
        pin_set: dict[str, Any],
        *,
        expected_purposes: Iterable[str],
        expected_scope: str,
        expected_consumer_id: str | None,
        prior_pin_set: dict[str, Any] | None = None,
    ) -> None:
        self.document = deepcopy(pin_set)
        expected = tuple(expected_purposes)
        if pin_set.get("pinSetDigest") != pin_set_digest(pin_set):
            raise TrustPolicyPinError("trust_pin_set_digest_mismatch", str(pin_set.get("pinSetId")))
        if pin_set.get("scope") != expected_scope or pin_set.get("consumerId") != expected_consumer_id:
            raise TrustPolicyPinError("trust_pin_set_scope_mismatch", str(pin_set.get("pinSetId")))
        revision = pin_set.get("revision")
        precondition = pin_set.get("precondition")
        if revision == 1:
            if prior_pin_set is not None or precondition != {"kind": "absent"}:
                raise TrustPolicyPinError("trust_pin_set_precondition_mismatch", str(revision))
        else:
            expected_precondition = (
                None
                if prior_pin_set is None
                else {
                    "kind": "match",
                    "revision": prior_pin_set["revision"],
                    "digest": prior_pin_set["pinSetDigest"],
                }
            )
            if (
                expected_precondition is None
                or precondition != expected_precondition
                or revision != prior_pin_set["revision"] + 1
            ):
                raise TrustPolicyPinError("trust_pin_set_precondition_mismatch", str(revision))

        current_entries = pin_set.get("currentForNewUse")
        if not isinstance(current_entries, list) or [entry.get("purpose") for entry in current_entries] != list(expected):
            raise TrustPolicyPinError("trust_pin_set_incomplete", str(pin_set.get("pinSetId")))
        self.current: dict[str, dict[str, str]] = {}
        seen_policy_digests: set[str] = set()
        for entry in current_entries:
            if set(entry) != {"purpose", "trustPolicy"}:
                raise TrustPolicyPinError("trust_pin_set_entry_invalid", str(entry))
            purpose = entry["purpose"]
            reference = entry["trustPolicy"]
            if (
                not isinstance(reference, dict)
                or set(reference) != {"id", "digest"}
                or reference["id"] != purpose
                or purpose in self.current
                or reference["digest"] in seen_policy_digests
            ):
                raise TrustPolicyPinError("trust_pin_set_entry_invalid", purpose)
            self.current[purpose] = deepcopy(reference)
            seen_policy_digests.add(reference["digest"])

        historical_entries = pin_set.get("historicalVerification")
        if not isinstance(historical_entries, list):
            raise TrustPolicyPinError("trust_pin_set_history_invalid", str(pin_set.get("pinSetId")))
        expected_history_order = sorted(
            historical_entries,
            key=lambda entry: (
                entry.get("purpose", "").encode("utf-8"),
                entry.get("trustPolicy", {}).get("digest", "").encode("utf-8"),
            ),
        )
        if historical_entries != expected_history_order:
            raise TrustPolicyPinError("trust_pin_set_history_order_invalid", str(pin_set.get("pinSetId")))
        self.historical: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in historical_entries:
            if set(entry) != {"purpose", "trustPolicy", "validForSigning"}:
                raise TrustPolicyPinError("trust_pin_set_history_invalid", str(entry))
            purpose = entry["purpose"]
            reference = entry["trustPolicy"]
            window = entry["validForSigning"]
            key = (purpose, reference.get("digest"))
            if (
                purpose not in self.current
                or set(reference) != {"id", "digest"}
                or reference["id"] != purpose
                or key in self.historical
                or reference == self.current[purpose]
                or set(window) != {"notBefore", "notAfter"}
                or _timestamp(window["notBefore"]) >= _timestamp(window["notAfter"])
            ):
                raise TrustPolicyPinError("trust_pin_set_history_invalid", str(key))
            self.historical[key] = deepcopy(entry)

        revocations = pin_set.get("revocations")
        if not isinstance(revocations, dict) or set(revocations) != {
            "policyDigests",
            "keyVersions",
            "publicKeyDigests",
        }:
            raise TrustPolicyPinError("trust_pin_set_revocations_invalid", str(pin_set.get("pinSetId")))
        for values in revocations.values():
            if values != sorted(set(values), key=lambda value: value.encode("utf-8")):
                raise TrustPolicyPinError("trust_pin_set_revocations_invalid", str(values))
        self.revocations = deepcopy(revocations)
        effective = pin_set.get("effective")
        if (
            not isinstance(effective, dict)
            or set(effective) != {"notBefore", "notAfter"}
            or _timestamp(effective["notBefore"]) >= _timestamp(effective["notAfter"])
        ):
            raise TrustPolicyPinError("trust_pin_set_effective_invalid", str(pin_set.get("pinSetId")))

    @property
    def digest(self) -> str:
        return self.document["pinSetDigest"]

    @property
    def consumer_id(self) -> str | None:
        return self.document["consumerId"]

    def authorize_policy(
        self,
        *,
        purpose: str,
        reference: dict[str, str],
        use: str,
        verification_time: str,
        signing_time: str | None = None,
    ) -> None:
        evaluated_at = _timestamp(verification_time)
        if not (
            _timestamp(self.document["effective"]["notBefore"])
            <= evaluated_at
            < _timestamp(self.document["effective"]["notAfter"])
        ):
            raise TrustPolicyPinError("trust_pin_set_not_effective", verification_time)
        if reference.get("digest") in self.revocations["policyDigests"]:
            raise TrustPolicyPinError("trust_policy_pin_revoked", purpose)
        if use == "new":
            if self.current.get(purpose) != reference:
                raise TrustPolicyPinError("trust_policy_retired_for_new_use", purpose)
            return
        if use != "historical" or signing_time is None:
            raise TrustPolicyPinError("trust_policy_pin_use_invalid", use)
        if self.current.get(purpose) == reference:
            return
        historical = self.historical.get((purpose, reference.get("digest")))
        if historical is None:
            raise TrustPolicyPinError("trust_policy_pin_mismatch", purpose)
        signed_at = _timestamp(signing_time)
        window = historical["validForSigning"]
        if not (_timestamp(window["notBefore"]) <= signed_at < _timestamp(window["notAfter"])):
            raise TrustPolicyPinError("trust_policy_not_pinned_at_signing_time", purpose)
