#!/usr/bin/env python3
"""Verify the exact acyclic L -> render -> D -> CE private compilation graph."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker
import rfc8785
from referencing import Registry, Resource

import generate_private_compilation_graph_fixtures as fixture_generator
from public_render_authority import (
    public_render_preimage,
    public_source_authentication_preimage,
    public_source_publisher_identity_preimage,
)
from release_status_eligibility import permitted_verification_result
from renderer_authority import (
    inline_authority_preimage,
    renderer_selection_preimage,
    schema_field_authority_preimage,
)
from signing_authority import (
    build_signer_authentication_evidence,
    exact_policy_signer,
)
from trusted_keyless_adapter import (
    CONTRACT_BUNDLE_MEDIA_TYPE,
    CONTRACT_BUNDLE_RELEASE_PURPOSE as KEYLESS_CONTRACT_BUNDLE_RELEASE_PURPOSE,
    KEYLESS_VERIFICATION_EVIDENCE_PROFILE,
    KEYLESS_VERIFICATION_PROFILE,
    SIGNING_REQUEST_MEDIA_TYPE,
    SIGSTORE_BUNDLE_MEDIA_TYPE,
    TrustedKeylessVerificationAdapter,
    TrustedKeylessVerificationError,
)
from trusted_kms_adapter import (
    CONTRACT_BUNDLE_MEDIA_TYPES,
    CONTRACT_BUNDLE_RELEASE_PURPOSE,
    TrustedKmsVerificationAdapter,
    TrustedKmsVerificationError,
)
from status_merkle import verify_consistency, verify_inclusion
from trust_policy_pins import (
    TrustedTrustPolicyProviderAdapter,
    TrustPolicyPinError,
    TrustPolicyPinSet,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"
CASE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "operations"
    / "private-compilation-graph.cases.json"
)
PRODUCT_RELEASE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "product-release-manifest__current.json"
)
RENDERER_CAS_BLOB_ROOT = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "operations"
    / "renderer-cas"
    / "blobs"
    / "sha256"
)

PRIVATE_INPUT_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/private-compilation-input/1.0.0"
)
DEPLOYMENT_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0"
)
EVIDENCE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/private-compilation-evidence/1.0.0"
)
RUNTIME_RELEASE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/runtime-release/1.0.0"
)
ACTIVATION_AUTHORIZATION_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "activation-authorization/1.0.0"
)
CONSUMER_AUTHORITY_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/consumer-authority/1.0.0"
)
CANARY_EVIDENCE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0"
)
AUTHORIZATION_DECISION_PROOF_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "authorization-decision-proof/1.0.0"
)
TRUST_POLICY_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy/1.0.0"
)
SIGNING_RESULT_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/signing-result/1.0.0"
)
SIGNER_AUTHENTICATION_EVIDENCE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "signer-authentication-evidence/1.0.0"
)
PRIVATE_INPUT_AUTHENTICATION_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/private-input-authentication-bundle/1.0.0"
)
TRUST_POLICY_PIN_SET_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "trust-policy-pin-set/1.0.0"
)
TRUST_POLICY_PIN_SET_DESCRIPTOR_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "trust-policy-pin-set-descriptor/1.0.0"
)
TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "trust-policy-pin-set-provider-evidence/1.0.0"
)
STATUS_ELIGIBILITY_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "release-status-eligibility-evidence/1.0.0"
)
RELEASE_STATUS_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/release-status/1.0.0"
)
STATUS_CHECKPOINT_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "release-status-head-checkpoint/1.0.0"
)
STATUS_CHECKPOINT_AUTH_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "release-status-head-authentication-evidence/1.0.0"
)
STATUS_INCLUSION_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "release-status-log-inclusion-proof/1.0.0"
)
STATUS_CONSISTENCY_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "release-status-log-consistency-proof/1.0.0"
)
VERIFICATION_RESULT_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0"
)
PUBLIC_SOURCE_AUTHENTICATION_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "public-source-authentication-evidence/1.0.0"
)
RENDER_MANIFEST_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/render-manifest/1.0.0"
)
PRODUCT_RELEASE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "product-release-manifest/1.0.0"
)
CONTRACT_BUNDLE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/contract-bundle/1.0.0"
)
SIGNING_REQUEST_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/signing-request/1.0.0"
)

CONSUMER_SIGNING_PURPOSES = (
    "consumer-authority-v1",
    "consumer-private-skill-v1",
    "consumer-compilation-input-v1",
    "consumer-deployment-v1",
    "consumer-compilation-evidence-v1",
    "consumer-runtime-release-v1",
    "consumer-release-status-eligibility-v1",
    "consumer-activation-authorization-v1",
)
ALL_TRUST_PURPOSES = frozenset(
    [
        *fixture_generator.PRODUCT_TRUST_PURPOSE_ROLES,
        *CONSUMER_SIGNING_PURPOSES,
    ]
)
ALL_KMS_SIGNING_PURPOSES = frozenset(
    [
        *fixture_generator.PRODUCT_KMS_SIGNER_PURPOSE_ROLES,
        *CONSUMER_SIGNING_PURPOSES,
    ]
)


class GraphError(RuntimeError):
    """One private proof graph invariant failed closed."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise GraphError(code, detail)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        require(key not in value, "duplicate_json_member", key)
        value[key] = member
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                GraphError("non_finite_number", token)
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GraphError("invalid_json", f"{path}: {error}") from error
    require(isinstance(value, dict), "invalid_json_root", str(path))
    return value


def parse_json_bytes(payload: bytes, role: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                GraphError("non_finite_number", token)
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise GraphError("invalid_json", f"{role}: {error}") from error
    require(isinstance(value, dict), "invalid_json_root", role)
    require(canonical_bytes(value) == payload, "noncanonical_cas_json", role)
    return value


def canonical_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def raw_digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def canonical_digest(value: Any) -> str:
    return raw_digest(canonical_bytes(value))


def parse_framed_jcs(payload: bytes, role: str) -> dict[str, Any]:
    require(len(payload) >= 4, "renderer_frame_truncated", role)
    declared_size = int.from_bytes(payload[:4], "big")
    require(
        declared_size <= fixture_generator.RENDERER_FRAME_MAX_PAYLOAD_BYTES,
        "renderer_frame_oversized",
        role,
    )
    require(
        len(payload) == 4 + declared_size,
        "renderer_frame_length_mismatch",
        role,
    )
    document = parse_json_bytes(payload[4:], role)
    require(
        fixture_generator.framed_jcs(document) == payload,
        "renderer_frame_noncanonical",
        role,
    )
    return document


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
    value: dict[str, Any],
    schema_id: str,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    schema = schemas[schema_id]
    require(
        value.get("schema") == {"id": schema_id, "digest": canonical_digest(schema)},
        "schema_descriptor_mismatch",
        schema_id,
    )
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    require(
        not errors,
        "schema_validation_failed",
        f"{schema_id}: {errors[0].message if errors else ''}",
    )


def validate_schema_value(
    value: Any,
    schema_id: str,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    errors = sorted(
        Draft202012Validator(
            schemas[schema_id],
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    require(
        not errors,
        "schema_validation_failed",
        f"{schema_id}: {errors[0].message if errors else ''}",
    )


def validate_trust_policy_pin_sets(
    bindings: Any,
    authentication_vectors: Any,
    operation_time: str,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> tuple[
    dict[str | None, TrustPolicyPinSet],
    dict[str | None, dict[str, Any]],
    dict[str | None, dict[str, Any]],
]:
    require(
        isinstance(bindings, list)
        and len(bindings) == 2
        and isinstance(authentication_vectors, list),
        "trust_policy_pin_set_catalog_invalid",
        "root",
    )
    expected = (
        (
            "product",
            None,
            fixture_generator.renderer_fixture_generator.PRODUCT_TRUST_PURPOSES,
        ),
        ("consumer", "consumer-01", CONSUMER_SIGNING_PURPOSES),
    )
    pin_sets: dict[str | None, TrustPolicyPinSet] = {}
    bindings_by_consumer: dict[str | None, dict[str, Any]] = {}
    verification_by_consumer: dict[str | None, dict[str, Any]] = {}
    for index, (binding, specification) in enumerate(zip(bindings, expected)):
        scope, consumer_id, purposes = specification
        require(
            isinstance(binding, dict)
            and set(binding)
            == {"pinSet", "pinSetDescriptor", "providerEvidence"},
            "trust_policy_pin_set_catalog_invalid",
            str(index),
        )
        document = binding["pinSet"]
        descriptor = binding["pinSetDescriptor"]
        provider_evidence = binding["providerEvidence"]
        validate_schema_instance(
            document,
            TRUST_POLICY_PIN_SET_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_value(
            descriptor,
            TRUST_POLICY_PIN_SET_DESCRIPTOR_SCHEMA_ID,
            registry,
            schemas,
        )
        validate_schema_instance(
            provider_evidence,
            TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE_SCHEMA_ID,
            registry,
            schemas,
        )
        try:
            pin_set = TrustPolicyPinSet(
                document,
                expected_purposes=purposes,
                expected_scope=scope,
                expected_consumer_id=consumer_id,
            )
            provider_vectors = [
                vector
                for vector in authentication_vectors
                if vector.get("providerId") == descriptor["providerId"]
                and vector.get("providerAuthorityDigest")
                == descriptor["providerAuthorityDigest"]
            ]
            provider = TrustedTrustPolicyProviderAdapter(
                provider_id=descriptor["providerId"],
                provider_authority_digest=descriptor[
                    "providerAuthorityDigest"
                ],
                authentication_vectors=provider_vectors,
            )
            verification = provider.verify_activation(
                pin_set=document,
                pin_set_descriptor_value=descriptor,
                evidence=provider_evidence,
                verification_time=operation_time,
            )
        except TrustPolicyPinError as error:
            raise GraphError(error.code, str(error)) from error
        require(
            set(verification)
            == {
                "decision",
                "vectorId",
                "pinSet",
                "pinSetDigest",
                "providerAuthorityDigest",
                "providerEvidenceDigest",
                "readbackAt",
            }
            and verification["decision"] == "active"
            and isinstance(verification["vectorId"], str)
            and verification["pinSet"] == descriptor
            and verification["pinSetDigest"] == pin_set.digest
            and verification["providerAuthorityDigest"]
            == descriptor["providerAuthorityDigest"]
            and verification["providerEvidenceDigest"]
            == provider_evidence["evidenceDigest"]
            and verification["readbackAt"]
            == provider_evidence["readback"]["observedAt"],
            "trust_pin_provider_verification_result_mismatch",
            str(consumer_id),
        )
        require(
            pin_set.consumer_id not in pin_sets,
            "trust_policy_pin_set_catalog_duplicate",
            str(pin_set.consumer_id),
        )
        pin_sets[pin_set.consumer_id] = pin_set
        bindings_by_consumer[pin_set.consumer_id] = deepcopy(binding)
        verification_by_consumer[pin_set.consumer_id] = deepcopy(
            verification
        )
    require(
        set(pin_sets)
        == set(bindings_by_consumer)
        == set(verification_by_consumer)
        == {None, "consumer-01"}
        and len(authentication_vectors) == 2,
        "trust_policy_pin_set_catalog_incomplete",
        str(sorted(str(value) for value in pin_sets)),
    )
    return pin_sets, bindings_by_consumer, verification_by_consumer


class ArtifactStore:
    """Closed digest-keyed raw byte store for the fixture graph."""

    def __init__(
        self,
        trusted_policy_pin_sets: dict[str | None, TrustPolicyPinSet]
        | None = None,
        trusted_policy_provider_bindings: dict[
            str | None, dict[str, Any]
        ]
        | None = None,
        trusted_policy_provider_verifications: dict[
            str | None, dict[str, Any]
        ]
        | None = None,
        signature_verification_vectors: list[dict[str, Any]] | None = None,
        keyless_verification_vectors: list[dict[str, Any]] | None = None,
    ) -> None:
        self._entries: dict[str, tuple[dict[str, Any], bytes]] = {}
        self._raw: dict[str, bytes] = {}
        self._authentication: dict[
            str, tuple[str, dict[str, Any], dict[str, Any]]
        ] = {}
        self._trusted_policy_pin_sets = deepcopy(
            trusted_policy_pin_sets or {}
        )
        self._trusted_policy_provider_bindings = deepcopy(
            trusted_policy_provider_bindings or {}
        )
        self._trusted_policy_provider_verifications = deepcopy(
            trusted_policy_provider_verifications or {}
        )
        self._signature_verification_vectors = deepcopy(
            signature_verification_vectors or []
        )
        self._keyless_verification_vectors = deepcopy(
            keyless_verification_vectors or []
        )
        try:
            self.signature_verifier = TrustedKmsVerificationAdapter(
                self._signature_verification_vectors
            )
        except TrustedKmsVerificationError as error:
            raise GraphError(error.code, str(error)) from error
        try:
            self.keyless_signature_verifier = TrustedKeylessVerificationAdapter(
                self._keyless_verification_vectors
            )
        except TrustedKeylessVerificationError as error:
            raise GraphError(error.code, str(error)) from error

    def clone(self) -> "ArtifactStore":
        # The trust catalogs and KMS verifier are validated once when the base
        # store is built and have no mutating API.  Mutation cases alter only
        # artifact bytes and authentication bindings, so rebuilding that
        # immutable authority state for every case wastes substantial memory
        # and can hide a denial behind process exhaustion.
        cloned = object.__new__(ArtifactStore)
        cloned._trusted_policy_pin_sets = self._trusted_policy_pin_sets
        cloned._trusted_policy_provider_bindings = (
            self._trusted_policy_provider_bindings
        )
        cloned._trusted_policy_provider_verifications = (
            self._trusted_policy_provider_verifications
        )
        cloned._signature_verification_vectors = (
            self._signature_verification_vectors
        )
        cloned._keyless_verification_vectors = (
            self._keyless_verification_vectors
        )
        cloned.signature_verifier = self.signature_verifier
        cloned.keyless_signature_verifier = self.keyless_signature_verifier
        cloned._entries = deepcopy(self._entries)
        cloned._raw = dict(self._raw)
        cloned._authentication = deepcopy(self._authentication)
        return cloned

    def trust_policy_pin(
        self, purpose: str, consumer_id: str | None
    ) -> dict[str, str]:
        pin_set = self._trusted_policy_pin_sets.get(consumer_id)
        pin = None if pin_set is None else pin_set.current.get(purpose)
        require(
            pin is not None,
            "trust_policy_pin_missing",
            f"{purpose}:{consumer_id}",
        )
        return deepcopy(pin)

    def trust_policy_pin_set(
        self, purpose: str, consumer_id: str | None
    ) -> TrustPolicyPinSet:
        pin_set = self._trusted_policy_pin_sets.get(consumer_id)
        require(
            pin_set is not None and purpose in pin_set.current,
            "trust_policy_pin_set_missing",
            f"{purpose}:{consumer_id}",
        )
        return pin_set

    def trust_policy_provider_binding(
        self, consumer_id: str | None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        binding = self._trusted_policy_provider_bindings.get(consumer_id)
        verification = self._trusted_policy_provider_verifications.get(
            consumer_id
        )
        require(
            binding is not None and verification is not None,
            "trust_policy_provider_binding_missing",
            str(consumer_id),
        )
        return deepcopy(binding), deepcopy(verification)

    def register_authentication(
        self,
        role: str,
        subject: dict[str, Any],
        signing_result: dict[str, Any],
    ) -> None:
        digest = subject["digest"]
        require(
            digest not in self._authentication,
            "authentication_catalog_duplicate_subject",
            digest,
        )
        self.resolve(subject)
        self.resolve(signing_result)
        self._authentication[digest] = (
            role,
            deepcopy(subject),
            deepcopy(signing_result),
        )

    def authentication_for(
        self, descriptor: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        entry = self._authentication.get(descriptor["digest"])
        require(
            entry is not None,
            "artifact_authentication_missing",
            descriptor["digest"],
        )
        role, subject, signing_result = entry
        require(
            subject == descriptor,
            "artifact_authentication_subject_substitution",
            role,
        )
        return role, deepcopy(signing_result)

    def authentication_subjects(self) -> set[str]:
        return set(self._authentication)

    def remove_authentication(self, subject_digest: str) -> None:
        require(
            subject_digest in self._authentication,
            "authentication_catalog_subject_missing",
            subject_digest,
        )
        del self._authentication[subject_digest]

    def remove_digest(self, digest: str) -> None:
        require(
            digest in self._raw,
            "digest_catalog_subject_missing",
            digest,
        )
        self._raw.pop(digest, None)
        self._entries.pop(digest, None)

    def substitute_authentication_result(
        self,
        subject_digest: str,
        signing_result: dict[str, Any],
    ) -> None:
        entry = self._authentication.get(subject_digest)
        require(
            entry is not None,
            "authentication_catalog_subject_missing",
            subject_digest,
        )
        role, subject, _ = entry
        self.resolve(signing_result)
        self._authentication[subject_digest] = (
            role,
            subject,
            deepcopy(signing_result),
        )

    def register_digest(self, digest: str, payload: bytes) -> None:
        require(digest == raw_digest(payload), "descriptor_byte_mismatch", digest)
        previous = self._raw.get(digest)
        require(
            previous is None or previous == payload,
            "cas_digest_collision",
            digest,
        )
        self._raw[digest] = payload

    def register(self, descriptor: dict[str, Any], payload: bytes) -> None:
        require(
            descriptor["digest"] == raw_digest(payload)
            and descriptor["size"] == len(payload),
            "descriptor_byte_mismatch",
            descriptor["digest"],
        )
        previous = self._entries.get(descriptor["digest"])
        require(
            previous is None or previous == (descriptor, payload),
            "cas_digest_collision",
            descriptor["digest"],
        )
        self._entries[descriptor["digest"]] = (deepcopy(descriptor), payload)
        self.register_digest(descriptor["digest"], payload)

    def resolve_digest(self, digest: str) -> bytes:
        payload = self._raw.get(digest)
        if payload is None:
            path = RENDERER_CAS_BLOB_ROOT / digest.removeprefix("sha256:")
            require(path.is_file(), "descriptor_unresolved", digest)
            payload = path.read_bytes()
            self.register_digest(digest, payload)
        require(raw_digest(payload) == digest, "descriptor_byte_mismatch", digest)
        return payload

    def resolve(self, descriptor: dict[str, Any]) -> bytes:
        entry = self._entries.get(descriptor["digest"])
        if entry is None:
            payload = self.resolve_digest(descriptor["digest"])
            require(
                len(payload) == descriptor["size"],
                "descriptor_byte_mismatch",
                descriptor["digest"],
            )
            self._entries[descriptor["digest"]] = (deepcopy(descriptor), payload)
            entry = self._entries[descriptor["digest"]]
        registered, payload = entry
        require(
            registered == descriptor,
            "descriptor_role_substitution",
            descriptor["digest"],
        )
        require(
            raw_digest(payload) == descriptor["digest"]
            and len(payload) == descriptor["size"],
            "descriptor_byte_mismatch",
            descriptor["digest"],
        )
        return payload


def validate_artifact_store_clone_isolation(store: ArtifactStore) -> None:
    """Prove mutation stores cannot alter the base artifact/authentication maps."""

    base_entry_digests = set(store._entries)
    base_raw_digests = set(store._raw)
    base_authentication_subjects = store.authentication_subjects()
    cloned = store.clone()
    require(
        cloned._entries is not store._entries
        and cloned._raw is not store._raw
        and cloned._authentication is not store._authentication,
        "artifact_store_clone_mutable_state_shared",
        "artifact maps",
    )
    require(
        cloned._trusted_policy_pin_sets is store._trusted_policy_pin_sets
        and cloned._trusted_policy_provider_bindings
        is store._trusted_policy_provider_bindings
        and cloned._trusted_policy_provider_verifications
        is store._trusted_policy_provider_verifications
        and cloned._signature_verification_vectors
        is store._signature_verification_vectors
        and cloned._keyless_verification_vectors
        is store._keyless_verification_vectors
        and cloned.signature_verifier is store.signature_verifier
        and cloned.keyless_signature_verifier
        is store.keyless_signature_verifier,
        "artifact_store_clone_trust_state_rebuilt",
        "validated authority catalogs",
    )

    probe_payload = b"bytedesk-artifact-store-clone-isolation-v1"
    probe_digest = raw_digest(probe_payload)
    require(probe_digest not in store._raw, "clone_probe_collision", probe_digest)
    cloned.register_digest(probe_digest, probe_payload)
    require(
        probe_digest not in store._raw,
        "artifact_store_clone_raw_state_leak",
        probe_digest,
    )

    removed_digest = min(base_entry_digests)
    cloned.remove_digest(removed_digest)
    require(
        removed_digest in store._entries and removed_digest in store._raw,
        "artifact_store_clone_entry_state_leak",
        removed_digest,
    )
    removed_subject = min(base_authentication_subjects)
    cloned.remove_authentication(removed_subject)
    require(
        removed_subject in store.authentication_subjects(),
        "artifact_store_clone_authentication_state_leak",
        removed_subject,
    )
    require(
        set(store._entries) == base_entry_digests
        and set(store._raw) == base_raw_digests
        and store.authentication_subjects() == base_authentication_subjects,
        "artifact_store_clone_base_state_changed",
        "base store",
    )


def store_from_catalog(
    cases: dict[str, Any],
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    operation_time: str,
) -> ArtifactStore:
    pin_sets, provider_bindings, provider_verifications = (
        validate_trust_policy_pin_sets(
            cases.get("trustPolicyPinSetBindings"),
            cases.get("trustPolicyPinSetProviderAuthenticationVectors"),
            operation_time,
            registry,
            schemas,
        )
    )
    store = ArtifactStore(
        pin_sets,
        provider_bindings,
        provider_verifications,
        cases.get("signatureVerificationVectors"),
        cases.get("keylessVerificationVectors"),
    )
    graph = cases["positiveGraph"]
    for entry in [*graph["artifacts"], *graph["supportingArtifacts"]]:
        path = REPOSITORY_ROOT / entry["blobPath"]
        payload = path.read_bytes()
        require(
            path.name == entry["descriptor"]["digest"].removeprefix("sha256:"),
            "cas_path_digest_mismatch",
            entry["role"],
        )
        store.register(entry["descriptor"], payload)
        projection_path = entry["projectionPath"]
        if projection_path is not None:
            projection = load_json(REPOSITORY_ROOT / projection_path)
            require(
                canonical_bytes(projection) == payload,
                "projection_cas_mismatch",
                entry["role"],
            )
    for entry in graph["supportingDigests"]:
        path = REPOSITORY_ROOT / entry["blobPath"]
        payload = path.read_bytes()
        require(
            path.name == entry["digest"].removeprefix("sha256:")
            and len(payload) == entry["size"],
            "cas_path_digest_mismatch",
            entry["role"],
        )
        store.register_digest(entry["digest"], payload)
    lock = load_json(REPOSITORY_ROOT / graph["lockPath"])
    authentication_catalog = parse_json_bytes(
        store.resolve(lock["inputs"]["inputAuthentication"]),
        "private input authentication bundle",
    )
    require(
        authentication_catalog.get("contract")
        == "bytedesk.private-input-authentication-bundle/1"
        and isinstance(authentication_catalog["entries"], list),
        "authentication_catalog_invalid",
        "inputs.inputAuthentication",
    )
    roles: set[str] = set()
    for entry in authentication_catalog["entries"]:
        require(
            set(entry) == {"role", "subject", "signingResult"}
            and isinstance(entry["role"], str)
            and entry["role"] not in roles,
            "authentication_catalog_invalid",
            str(entry.get("role")),
        )
        roles.add(entry["role"])
        store.register_authentication(
            entry["role"], entry["subject"], entry["signingResult"]
        )
    return store


def role_descriptor(
    descriptor: dict[str, Any], media_type: str, purpose: str, role: str
) -> None:
    require(
        descriptor["mediaType"] == media_type
        and descriptor["trustPolicy"]["id"] == purpose,
        "descriptor_role_substitution",
        role,
    )


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "timestamp_without_timezone", value)
    return parsed.astimezone(timezone.utc)


DESCRIPTOR_PURPOSE_BY_MEDIA_TYPE = {
        "application/vnd.bytedesk.agent.consumer-authority.v1+json": "consumer-authority-v1",
        "application/vnd.bytedesk.agent.skill-approval.v1+json": "consumer-authority-v1",
        "application/vnd.bytedesk.agent.binding.v1+json": "consumer-authority-v1",
        "application/vnd.bytedesk.agent.candidate.v1+json": "consumer-authority-v1",
        fixture_generator.PRIVATE_INPUT_MEDIA_TYPE: "consumer-compilation-input-v1",
        fixture_generator.PRIVATE_INPUT_AUTHENTICATION_MEDIA_TYPE: "consumer-compilation-input-v1",
        fixture_generator.DEPLOYMENT_MEDIA_TYPE: "consumer-deployment-v1",
        fixture_generator.RENDER_PAYLOAD_MEDIA_TYPE: "consumer-deployment-v1",
        fixture_generator.COMPILATION_EVIDENCE_MEDIA_TYPE: "consumer-compilation-evidence-v1",
        fixture_generator.RUNTIME_RELEASE_MEDIA_TYPE: "consumer-runtime-release-v1",
        "application/vnd.bytedesk.agent.render.v1+json": "public-render-v1",
        "application/vnd.bytedesk.agent.compatibility.v1+json": "public-render-v1",
        "application/vnd.bytedesk.agent.source.v1+json": "public-source-v1",
        "application/vnd.bytedesk.agent.v1+json": "public-source-v1",
        "application/vnd.bytedesk.agent.public-source-authentication-evidence.v1+json": "public-source-v1",
        "application/vnd.bytedesk.agent.product-distribution.v1+json": "product-release-v1",
        "application/vnd.bytedesk.agent.product-release-manifest.v1+json": "product-release-v1",
        "application/vnd.bytedesk.agent.renderer-allowlist.v1+json": "product-release-v1",
        "application/vnd.bytedesk.agent.renderer-capability.v1+json": "product-release-v1",
        "application/vnd.bytedesk.agent.renderer-release.v1+json": "product-release-v1",
        "application/vnd.bytedesk.renderer.release.v1+json": "product-release-v1",
        "application/vnd.bytedesk.agent.contract-bundle.v1+json": "contract-bundle-release-v1",
        "application/vnd.bytedesk.agent-spec-semantics.v1+json": "product-release-v1",
        "application/vnd.bytedesk.agent.release-qualification-policy.v1+json": "release-qualification-policy-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-corpus.v1+tar": "release-qualification-policy-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-plan.v1+json": "release-qualification-policy-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-suite.v1+json": "release-qualification-policy-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json": "release-qualification-attempt-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json": "release-qualification-attempt-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json": "release-qualification-attempt-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json": "release-qualification-receipt-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json": "release-qualification-receipt-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json": "release-qualification-receipt-v1",
        "application/vnd.bytedesk.agent.release-qualification-details.v1+json": "release-qualification-evidence-v1",
        "application/vnd.bytedesk.agent.release-qualification-evidence.v1+json": "release-qualification-evidence-v1",
        "application/vnd.bytedesk.agent.release-qualification-predicate.v1+json": "release-qualification-evidence-v1",
        "application/vnd.bytedesk.agent.renderer-qualification-evidence-leaf-statement.v1+json": "release-qualification-evidence-v1",
        "application/vnd.bytedesk.agent.release-qualification.v1+json": "release-qualification-decision-v1",
        "application/vnd.bytedesk.agent.release-status.v1+json": "release-status-v1",
        "application/vnd.bytedesk.agent.release-status-head-authentication-evidence.v1+json": "release-status-head-v1",
        "application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json": "release-status-head-v1",
        "application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json": "release-status-head-v1",
        "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json": "renderer-attempt-v1",
        "application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json": "renderer-attempt-v1",
        "application/vnd.bytedesk.agent.renderer-selection.v1+json": "renderer-attempt-v1",
        "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json": "renderer-execution-v1",
        "application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json": "renderer-execution-v1",
        "application/vnd.bytedesk.agent.render-manifest.v1+json": "public-render-v1",
    }

DESCRIPTOR_PURPOSE_BY_REPOSITORY_AND_MEDIA_TYPE = {
    ("registry.example/public/skills", "application/vnd.bytedesk.agent.skill.v1+json"): "public-source-v1",
    ("registry.example/consumer/skills", "application/vnd.bytedesk.agent.skill.v1+json"): "consumer-private-skill-v1",
    ("registry.example/catalog/skills", "application/vnd.bytedesk.skill.v1+tar"): "public-source-v1",
    ("registry.example/catalog/skills", "application/vnd.bytedesk.agent.skill.v1+json"): "public-source-v1",
    ("registry.consumer.example/private/skills", "application/vnd.bytedesk.skill.v1+tar"): "consumer-private-skill-v1",
    ("registry.example/public/source-layers", "application/vnd.oci.image.layer.v1.tar"): "public-source-v1",
    ("registry.example/public/layers", "application/vnd.oci.image.layer.v1.tar"): "public-source-v1",
    ("registry.example/public/render-layers", "application/vnd.oci.image.layer.v1.tar"): "public-render-v1",
    ("registry.example/agents/renders", fixture_generator.RENDER_PAYLOAD_MEDIA_TYPE): "public-render-v1",
    ("registry.example/agents/renders", "application/vnd.oci.image.layer.v1.tar+gzip"): "public-render-v1",
    ("registry.example/consumer/layers", "application/vnd.oci.image.layer.v1.tar"): "consumer-private-skill-v1",
    ("registry.example/public/evidence", "application/vnd.bytedesk.agent.policy.v1+json"): "public-source-v1",
    ("registry.example/public/evidence", "application/spdx+json"): "public-source-v1",
    ("registry.example/public/evidence", "application/vnd.bytedesk.scan.v1+json"): "public-source-v1",
    ("registry.example/public/evidence", "application/vnd.bytedesk.license.v1+json"): "public-source-v1",
    ("registry.example/consumer/evidence", "application/spdx+json"): "consumer-private-skill-v1",
    ("registry.example/consumer/evidence", "application/vnd.bytedesk.scan.v1+json"): "consumer-private-skill-v1",
    ("registry.example/consumer/evidence", "application/vnd.bytedesk.license.v1+json"): "consumer-private-skill-v1",
    ("registry.example/bytedesk/contracts", "application/vnd.bytedesk.agent.contract-bundle.v1+tar"): "contract-bundle-release-v1",
    ("registry.example/product/qualification", "application/vnd.oci.image.manifest.v1+json"): "release-qualification-policy-v1",
    ("registry.example/product/agent-delivery", "application/vnd.oci.image.manifest.v1+json"): "product-release-v1",
    ("registry.example/product/builders", "application/vnd.oci.image.manifest.v1+json"): "product-release-v1",
    ("registry.example/product/images", "application/vnd.oci.image.manifest.v1+json"): "product-release-v1",
    ("registry.example/product/renderer-workers", "application/vnd.oci.image.manifest.v1+json"): "product-release-v1",
    ("registry.example/product/renderers", "application/vnd.oci.image.manifest.v1+json"): "product-release-v1",
}

ROLE_BOUND_MEDIA_TYPES = {
    fixture_generator.SIGNING_RESULT_MEDIA_TYPE,
    fixture_generator.SIGNATURE_BUNDLE_MEDIA_TYPE,
    fixture_generator.SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
    "application/vnd.oci.image.layer.v1.tar",
    "application/vnd.oci.image.layer.v1.tar+gzip",
}


def expected_descriptor_purpose(
    descriptor: dict[str, Any], role_purpose: str | None = None
) -> str:
    repository = descriptor["repository"]
    media_type = descriptor["mediaType"]
    exact_pair = (repository, media_type)
    if exact_pair in DESCRIPTOR_PURPOSE_BY_REPOSITORY_AND_MEDIA_TYPE:
        return DESCRIPTOR_PURPOSE_BY_REPOSITORY_AND_MEDIA_TYPE[exact_pair]
    if media_type in DESCRIPTOR_PURPOSE_BY_MEDIA_TYPE:
        return DESCRIPTOR_PURPOSE_BY_MEDIA_TYPE[media_type]
    if media_type in ROLE_BOUND_MEDIA_TYPES and role_purpose is not None:
        require(
            role_purpose in ALL_TRUST_PURPOSES,
            "descriptor_role_unclassified",
            role_purpose,
        )
        return role_purpose
    claimed_purpose = descriptor.get("trustPolicy", {}).get("id")
    if claimed_purpose in ALL_TRUST_PURPOSES:
        # New authority-owned artifact media types do not silently become
        # unverifiable when the contract bundle expands.  The claimed purpose
        # is still exact-pinned below and its policy must permit both this
        # repository and media type; role-bound signature support objects never
        # take this fallback.
        return claimed_purpose
    raise GraphError(
        "descriptor_role_unclassified", f"{repository} {media_type}"
    )


def validate_reachable_artifacts(
    roots: list[dict[str, Any]],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    operation_time: str,
) -> int:
    visited: set[str] = set()
    authenticated_subjects: set[str] = set()
    descriptor_count = 0
    detached_signature_purposes = {
        "consumer-authority-v1",
        "consumer-private-skill-v1",
        "public-source-v1",
    }
    detached_signature_exempt_media_types = {
        fixture_generator.SIGNING_RESULT_MEDIA_TYPE,
        fixture_generator.SIGNATURE_BUNDLE_MEDIA_TYPE,
        fixture_generator.SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        (
            "application/vnd.bytedesk.agent."
            "public-source-authentication-evidence.v1+json"
        ),
    }

    contract_purposes = {
        "bytedesk.private-compilation-input/1": "consumer-compilation-input-v1",
        "bytedesk.private-input-authentication-bundle/1": "consumer-compilation-input-v1",
        "bytedesk.consumer-deployment/1": "consumer-deployment-v1",
        "bytedesk.private-compilation-evidence/1": "consumer-compilation-evidence-v1",
        "bytedesk.runtime-release/1": "consumer-runtime-release-v1",
        "bytedesk.agent-source/1": "public-source-v1",
        "bytedesk.skill-package/1": None,
        "bytedesk.harness-render/1": "public-render-v1",
        "bytedesk.product-release-manifest/1": "product-release-v1",
        "bytedesk.release-qualification-policy/1": "release-qualification-policy-v1",
        "bytedesk.renderer-qualification-attempt/1": "release-qualification-attempt-v1",
        "bytedesk.renderer-qualification-attempt-authentication-evidence/1": "release-qualification-attempt-v1",
        "bytedesk.renderer-qualification-receipt/1": "release-qualification-receipt-v1",
        "bytedesk.renderer-qualification-receipt-authentication-evidence/1": "release-qualification-receipt-v1",
        "bytedesk.renderer-qualification-evidence-tree/1": "release-qualification-receipt-v1",
        "bytedesk.release-qualification-evidence/1": "release-qualification-evidence-v1",
        "bytedesk.release-qualification-predicate/1": "release-qualification-evidence-v1",
        "bytedesk.release-qualification/1": "release-qualification-decision-v1",
        "bytedesk.release-status/1": "release-status-v1",
        "bytedesk.release-status-head-checkpoint/1": "release-status-head-v1",
        "bytedesk.release-status-head-authentication-evidence/1": "release-status-head-v1",
        "bytedesk.renderer-attempt-authority/1": "renderer-attempt-v1",
        "bytedesk.renderer-attempt-authentication-evidence/1": "renderer-attempt-v1",
        "bytedesk.renderer-execution-receipt/1": "renderer-execution-v1",
        "bytedesk.renderer-execution-authentication-evidence/1": "renderer-execution-v1",
    }

    def walk(value: Any, role_purpose: str | None = None) -> None:
        nonlocal descriptor_count
        if isinstance(value, list):
            for item in value:
                walk(item, role_purpose)
            return
        if not isinstance(value, dict):
            return
        contract = value.get("contract")
        if contract == "bytedesk.signing-result/1":
            role_purpose = value.get("purpose")
            require(
                role_purpose in ALL_KMS_SIGNING_PURPOSES,
                "signing_result_purpose_unclassified",
                str(role_purpose),
            )
        elif contract in contract_purposes and contract_purposes[contract] is not None:
            role_purpose = contract_purposes[contract]
        if set(value) == {"repository", "digest", "mediaType", "size", "trustPolicy"}:
            descriptor = value
            purpose = expected_descriptor_purpose(descriptor, role_purpose)
            require(
                descriptor["trustPolicy"]["id"] == purpose,
                "descriptor_role_substitution",
                f"{descriptor['repository']} {descriptor['mediaType']}",
            )
            policy = validate_trust_policy_ref(
                descriptor["trustPolicy"],
                purpose,
                None
                if purpose in fixture_generator.PRODUCT_TRUST_PURPOSE_ROLES
                else "consumer-01",
                store,
                registry,
                schemas,
                operation_time,
            )
            require(
                descriptor["repository"] in policy["scope"]["repositories"]
                and descriptor["mediaType"] in policy["scope"]["mediaTypes"],
                "descriptor_outside_trust_scope",
                descriptor["digest"],
            )
            payload = store.resolve(descriptor)
            descriptor_count += 1
            if (
                purpose in detached_signature_purposes
                and descriptor["mediaType"]
                not in detached_signature_exempt_media_types
            ):
                role, signing_result_descriptor = store.authentication_for(
                    descriptor
                )
                role_descriptor(
                    signing_result_descriptor,
                    fixture_generator.SIGNING_RESULT_MEDIA_TYPE,
                    purpose,
                    f"{role} signing result",
                )
                require(
                    signing_result_descriptor["trustPolicy"]
                    == descriptor["trustPolicy"],
                    "artifact_authentication_referrer_scope_mismatch",
                    role,
                )
                signing_result = parse_json_bytes(
                    store.resolve(signing_result_descriptor),
                    f"{role} signing result",
                )
                validate_signing_result(
                    signing_result,
                    purpose,
                    descriptor["digest"],
                    descriptor["mediaType"],
                    (
                        "consumer-01"
                        if purpose
                        in {
                            "consumer-authority-v1",
                            "consumer-private-skill-v1",
                        }
                        else None
                    ),
                    store,
                    registry,
                    schemas,
                    operation_time=operation_time,
                    policy=descriptor["trustPolicy"],
                    expected_repository=signing_result["repository"],
                )
                require(
                    signing_result_descriptor["repository"]
                    == signing_result["repository"],
                    "artifact_authentication_referrer_scope_mismatch",
                    role,
                )
                authenticated_subjects.add(descriptor["digest"])
            if descriptor["digest"] in visited:
                return
            visited.add(descriptor["digest"])
            if "json" in descriptor["mediaType"]:
                document = parse_json_bytes(payload, descriptor["digest"])
                schema_ref = document.get("schema")
                if (
                    isinstance(schema_ref, dict)
                    and schema_ref.get("id") in schemas
                ):
                    validate_schema_instance(
                        document, schema_ref["id"], registry, schemas
                    )
                walk(document, purpose)
            return
        if set(value) == {"digest", "mediaType", "size"}:
            payload = store.resolve_digest(value["digest"])
            require(
                len(payload) == value["size"],
                "descriptor_byte_mismatch",
                value["digest"],
            )
            descriptor_count += 1
            return
        if contract == "bytedesk.private-input-authentication-bundle/1":
            for entry in value["entries"]:
                subject_purpose = expected_descriptor_purpose(entry["subject"])
                walk(entry["subject"], subject_purpose)
                walk(entry["signingResult"], subject_purpose)
            for key, member in value.items():
                if key != "entries":
                    walk(member, role_purpose)
            return
        for key, member in value.items():
            if key in {"trustPolicy", "signerPolicy", "approvalPolicy"} and isinstance(
                member, dict
            ) and set(member) == {"id", "digest"}:
                purpose = member["id"]
                require(
                    purpose in ALL_TRUST_PURPOSES
                    and (
                        key == "trustPolicy"
                        or (
                            role_purpose is not None
                            and purpose == role_purpose
                        )
                    ),
                    "trust_policy_role_substitution",
                    f"{contract or 'embedded'}:{purpose}",
                )
                validate_trust_policy_ref(
                    member,
                    purpose,
                    None
                    if purpose in fixture_generator.PRODUCT_TRUST_PURPOSE_ROLES
                    else "consumer-01",
                    store,
                    registry,
                    schemas,
                    operation_time,
                )
            walk(member, role_purpose)

    for root in roots:
        walk(root)
    require(
        authenticated_subjects == store.authentication_subjects(),
        "authentication_catalog_reachability_mismatch",
        (
            f"missing={sorted(store.authentication_subjects()-authenticated_subjects)} "
            f"unexpected={sorted(authenticated_subjects-store.authentication_subjects())}"
        ),
    )
    return descriptor_count


def reject_sentinel_digests(roots: list[dict[str, Any]]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}/{index}")
        elif isinstance(value, dict):
            for key, member in value.items():
                walk(member, f"{path}/{key}")
        elif isinstance(value, str) and value.startswith("sha256:"):
            hexadecimal = value.removeprefix("sha256:")
            require(
                len(set(hexadecimal)) > 1,
                "sentinel_digest_rejected",
                path,
            )

    for index, root in enumerate(roots):
        walk(root, f"root/{index}")


def validate_lock(
    lock: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    product_release: dict[str, Any],
) -> None:
    inputs = lock["inputs"]
    authorized_inputs = deepcopy(inputs)
    authorized_inputs.pop("inputAuthentication")
    authorized_inputs.pop("authoritySnapshot")
    authorized_inputs.pop("authorizedPrivateInputDigest")
    require(
        inputs["authorizedPrivateInputDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.authorized-private-compilation-input/1",
                "contract": lock["contract"],
                "schema": lock["schema"],
                "inputs": authorized_inputs,
            }
        ),
        "authorized_private_input_digest_mismatch",
        "contract/schema/input preimage",
    )
    require(
        lock["compilationInputDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.private-compilation-input-digest/1",
                "contract": lock["contract"],
                "schema": lock["schema"],
                "inputs": inputs,
            }
        ),
        "compilation_input_digest_mismatch",
        "complete lock",
    )
    selection = inputs["rendererSelection"]
    require(
        selection["selectionDigest"]
        == canonical_digest(renderer_selection_preimage(selection))
        and inputs["rendererSelectionDigest"] == selection["selectionDigest"],
        "renderer_selection_digest_mismatch",
        "locked selection",
    )
    product_release_descriptor = selection["productRelease"]
    role_descriptor(
        product_release_descriptor,
        "application/vnd.bytedesk.agent.product-release-manifest.v1+json",
        "product-release-v1",
        "selected product release",
    )
    resolved_product_release = parse_json_bytes(
        store.resolve(product_release_descriptor),
        "selected product release",
    )
    require(
        resolved_product_release == product_release,
        "product_release_descriptor_mismatch",
        product_release_descriptor["digest"],
    )
    validate_schema_instance(
        product_release,
        PRODUCT_RELEASE_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        product_release["authorityDigest"]
        == canonical_digest(
            inline_authority_preimage(
                product_release,
                schemas[PRODUCT_RELEASE_SCHEMA_ID],
            )
        ),
        "product_release_authority_digest_mismatch",
        product_release_descriptor["digest"],
    )
    validate_signing_result(
        product_release["signingResult"],
        "product-release-v1",
        product_release["authorityDigest"],
        "application/vnd.bytedesk.agent.product-release-manifest.v1+json",
        None,
        store,
        registry,
        schemas,
        operation_time=inputs["reproducibleEpoch"],
        policy=product_release["trustPolicy"],
        expected_repository=product_release["signingResult"]["repository"],
    )
    validate_contract_bundle_keyless_verification(
        product_release,
        store,
        registry,
        schemas,
        inputs["reproducibleEpoch"],
    )
    effective_skills = inputs["effectiveSkillSet"]
    require(
        effective_skills["digest"]
        == canonical_digest(
            {
                "profile": "bytedesk.renderer-effective-skill-set/1",
                "publicSkills": effective_skills["publicSkills"],
                "privateSkills": effective_skills["privateSkills"],
            }
        ),
        "effective_skill_set_digest_mismatch",
        "lock",
    )
    public_skills = effective_skills["publicSkills"]
    private_skills = effective_skills["privateSkills"]
    skill_key = lambda descriptor: (
        descriptor["repository"].encode("utf-8"),
        descriptor["digest"],
    )
    public_keys = [skill_key(value) for value in public_skills]
    private_keys = [skill_key(value) for value in private_skills]
    combined_keys = [*public_keys, *private_keys]
    approval_keys = [
        skill_key(entry["skill"]) for entry in inputs["skillApprovals"]
    ]
    require(
        public_keys == sorted(public_keys)
        and private_keys == sorted(private_keys)
        and len(combined_keys) == len(set(combined_keys))
        and set(public_keys).isdisjoint(private_keys)
        and approval_keys == sorted(approval_keys)
        and len(approval_keys) == len(set(approval_keys))
        and set(approval_keys) == set(combined_keys),
        "skill_collection_not_canonical",
        "ordered/disjoint/unique skills and approvals",
    )
    require(
        inputs["desiredRevision"]["digest"]
        == canonical_digest(
            {
                "profile": "bytedesk.fixture-desired-revision/1",
                "consumerId": inputs["consumerId"],
                "targetId": inputs["targetId"],
                "revision": inputs["desiredRevision"]["revision"],
            }
        )
        and inputs["predecessor"]["digest"]
        == canonical_digest(
            {
                "profile": "bytedesk.fixture-predecessor/1",
                "consumerId": inputs["consumerId"],
                "targetId": inputs["targetId"],
                "revision": inputs["predecessor"]["revision"],
            }
        )
        and inputs["policyDigests"]
        == {
            key: canonical_digest(
                {
                    "profile": "bytedesk.fixture-opaque-consumer-policy/1",
                    "consumerId": inputs["consumerId"],
                    "targetId": inputs["targetId"],
                    "policyClass": key,
                }
            )
            for key in inputs["policyDigests"]
        },
        "fixture_domain_digest_mismatch",
        "revision/predecessor/opaque consumer digests",
    )
    authentication_descriptor = inputs["inputAuthentication"]
    role_descriptor(
        authentication_descriptor,
        fixture_generator.PRIVATE_INPUT_AUTHENTICATION_MEDIA_TYPE,
        "consumer-compilation-input-v1",
        "private input authentication bundle",
    )
    authentication_bundle = parse_json_bytes(
        store.resolve(authentication_descriptor),
        "private input authentication bundle",
    )
    validate_schema_instance(
        authentication_bundle,
        PRIVATE_INPUT_AUTHENTICATION_SCHEMA_ID,
        registry,
        schemas,
    )
    authentication_roles = [
        entry["role"] for entry in authentication_bundle["entries"]
    ]
    authentication_subjects = [
        entry["subject"]["digest"]
        for entry in authentication_bundle["entries"]
    ]
    require(
        all(
            authentication_bundle[field] == inputs[field]
            for field in (
                "consumerId",
                "subjectId",
                "installationId",
                "harnessId",
                "targetId",
            )
        )
        and authentication_roles
        == sorted(authentication_roles, key=lambda value: value.encode("utf-8"))
        and len(authentication_roles) == len(set(authentication_roles))
        and len(authentication_subjects) == len(set(authentication_subjects))
        and set(authentication_subjects) == store.authentication_subjects(),
        "private_input_authentication_bundle_mismatch",
        "scope/order/subject closure",
    )
    authority_descriptor = inputs["authoritySnapshot"]
    role_descriptor(
        authority_descriptor,
        "application/vnd.bytedesk.agent.consumer-authority.v1+json",
        "consumer-authority-v1",
        "private compilation authority",
    )
    authority = parse_json_bytes(
        store.resolve(authority_descriptor), "private compilation authority"
    )
    validate_schema_instance(
        authority, CONSUMER_AUTHORITY_SCHEMA_ID, registry, schemas
    )
    validate_trust_policy_ref(
        authority["signerPolicy"],
        "consumer-authority-v1",
        inputs["consumerId"],
        store,
        registry,
        schemas,
        inputs["reproducibleEpoch"],
    )
    require(
        authority_descriptor["trustPolicy"] == authority["signerPolicy"]
        and authority["authorizedPrivateInputDigest"]
        == inputs["authorizedPrivateInputDigest"]
        and authority["operation"] == "compile"
        and authority["decision"]
        == {
            "class": "permitted",
            "code": "consumer_private_compilation_permitted",
        }
        and authority["opaqueDigests"] == inputs["policyDigests"]
        and authority["bindingDigest"] == inputs["binding"]["digest"]
        and authority["candidateDigest"] == inputs["candidate"]["digest"]
        and authority["desiredRevisionDigest"]
        == inputs["desiredRevision"]["digest"]
        and authority["predecessor"] == inputs["predecessor"]
        and all(
            authority[field] == inputs[field]
            for field in (
                "consumerId",
                "subjectId",
                "installationId",
                "harnessId",
                "targetId",
            )
        ),
        "consumer_authority_lock_mismatch",
        "consumer authority/L",
    )
    epoch = timestamp(inputs["reproducibleEpoch"])
    require(
        timestamp(authority["issuedAt"]) <= epoch
        and timestamp(authority["notBefore"]) <= epoch
        and epoch < timestamp(authority["expiresAt"])
        and authority["nonce"].startswith("nonce_private_compile_")
        and len(authority["nonce"]) >= 24,
        "consumer_authority_stale",
        "issued/notBefore/expiry/nonce",
    )
    role_descriptor(
        inputs["binding"],
        "application/vnd.bytedesk.agent.binding.v1+json",
        "consumer-authority-v1",
        "consumer binding",
    )
    role_descriptor(
        inputs["candidate"],
        "application/vnd.bytedesk.agent.candidate.v1+json",
        "consumer-authority-v1",
        "consumer candidate",
    )
    role_descriptor(
        inputs["publicArtifact"],
        "application/vnd.bytedesk.agent.render.v1+json",
        "public-render-v1",
        "public render",
    )
    role_descriptor(
        inputs["contractBundle"],
        "application/vnd.bytedesk.agent.contract-bundle.v1+json",
        "contract-bundle-release-v1",
        "contract bundle",
    )
    binding = parse_json_bytes(store.resolve(inputs["binding"]), "consumer binding")
    validate_schema_instance(
        binding,
        "https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0",
        registry,
        schemas,
    )
    # A public source and public skill are byte-exact, signed payloads.  Their
    # contents are deliberately opaque to the private compiler: a catalog may
    # carry any schema-valid source format and skills may contain arbitrary
    # regular files, none of which is executed during validation or rendering.
    store.resolve(binding["source"])
    candidate = parse_json_bytes(store.resolve(inputs["candidate"]), "consumer candidate")
    validate_schema_instance(
        candidate,
        "https://schemas.bytedesk.ai/agent-delivery/v1/candidate/1.0.0",
        registry,
        schemas,
    )
    public_render = parse_json_bytes(
        store.resolve(inputs["publicArtifact"]), "public render"
    )
    validate_schema_instance(
        public_render,
        "https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0",
        registry,
        schemas,
    )
    role_descriptor(
        public_render["renderManifest"],
        "application/vnd.bytedesk.agent.render-manifest.v1+json",
        "public-render-v1",
        "public render manifest",
    )
    public_manifest = parse_json_bytes(
        store.resolve(public_render["renderManifest"]),
        "public render manifest",
    )
    validate_schema_instance(
        public_manifest,
        RENDER_MANIFEST_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        public_render["trustPolicy"]
        == inputs["publicArtifact"]["trustPolicy"]
        and public_render["authorityDigest"]
        == canonical_digest(public_render_preimage(public_render))
        and timestamp(public_render["createdAt"]) <= epoch,
        "public_render_authority_mismatch",
        inputs["publicArtifact"]["digest"],
    )
    validate_signing_result(
        public_render["signingResult"],
        "public-render-v1",
        public_render["authorityDigest"],
        "application/vnd.bytedesk.agent.render.v1+json",
        None,
        store,
        registry,
        schemas,
        operation_time=inputs["reproducibleEpoch"],
        policy=public_render["trustPolicy"],
        expected_repository=public_render["signingResult"]["repository"],
    )
    public_subjects = [public_render["source"], *public_render["publicSkills"]]
    authenticated_public_subjects: set[tuple[str, str, str]] = set()
    require(
        len(public_render["publicSourceAuthenticationEvidence"])
        == len(public_subjects),
        "public_source_authentication_coverage_mismatch",
        public_render["authorityDigest"],
    )
    for evidence_descriptor in public_render[
        "publicSourceAuthenticationEvidence"
    ]:
        role_descriptor(
            evidence_descriptor,
            (
                "application/vnd.bytedesk.agent."
                "public-source-authentication-evidence.v1+json"
            ),
            "public-source-v1",
            "public source authentication evidence",
        )
        source_authentication = parse_json_bytes(
            store.resolve(evidence_descriptor),
            "public source authentication evidence",
        )
        validate_schema_instance(
            source_authentication,
            PUBLIC_SOURCE_AUTHENTICATION_SCHEMA_ID,
            registry,
            schemas,
        )
        subject = source_authentication["subject"]
        subject_key = (
            subject["repository"],
            subject["digest"],
            subject["mediaType"],
        )
        require(
            subject in public_subjects
            and subject_key not in authenticated_public_subjects
            and source_authentication["evidenceDigest"]
            == canonical_digest(
                public_source_authentication_preimage(source_authentication)
            ),
            "public_source_authentication_subject_mismatch",
            subject["digest"],
        )
        authenticated_public_subjects.add(subject_key)
        store.resolve(subject)
        source_signing = source_authentication["signingResult"]
        validate_signing_result(
            source_signing,
            "public-source-v1",
            subject["digest"],
            subject["mediaType"],
            None,
            store,
            registry,
            schemas,
            operation_time=inputs["reproducibleEpoch"],
            policy=subject["trustPolicy"],
            expected_repository=source_signing["repository"],
        )
        source_policy = validate_trust_policy_ref(
            source_signing["trustPolicy"],
            "public-source-v1",
            None,
            store,
            registry,
            schemas,
            inputs["reproducibleEpoch"],
        )
        try:
            source_signer = exact_policy_signer(
                source_policy,
                purpose="public-source-v1",
                subject_media_type=source_signing["subjectMediaType"],
                key_version=source_signing["keyVersion"],
                algorithm=source_signing["algorithm"],
                public_key_digest=source_signing["publicKeyDigest"],
            )
        except ValueError as error:
            raise GraphError(
                "public_source_publisher_identity_mismatch",
                subject["digest"],
            ) from error
        require(
            source_authentication["publisherIdentityDigest"]
            == canonical_digest(
                public_source_publisher_identity_preimage(source_signer)
            ),
            "public_source_publisher_identity_mismatch",
            subject["digest"],
        )
    require(
        authenticated_public_subjects
        == {
            (
                subject["repository"],
                subject["digest"],
                subject["mediaType"],
            )
            for subject in public_subjects
        },
        "public_source_authentication_coverage_mismatch",
        public_render["authorityDigest"],
    )
    require(
        inputs["customizationDigest"]
        == canonical_digest(fixture_generator.customization_preimage(binding))
        and
        inputs["contractBundle"] == product_release["contractBundle"]
        and binding["agentId"] == inputs["subjectId"]
        and binding["agentSpecVersion"] == public_manifest["agentSpecVersion"]
        and binding["sourceKind"] == public_manifest["sourceKind"]
        and binding["renderer"]["harnessId"] == inputs["harnessId"]
        and binding["renderer"]["rendererId"]
        == inputs["rendererSelection"]["rendererId"]
        and binding["renderer"]["version"]
        == inputs["rendererSelection"]["rendererVersion"]
        and binding["renderer"]["release"]
        == inputs["rendererSelection"]["rendererRelease"]
        and candidate["consumerId"] == inputs["consumerId"]
        and candidate["installationId"] == inputs["installationId"]
        and candidate["targetId"] == inputs["targetId"]
        and candidate["state"] == "approved"
        and candidate["input"] == binding["source"]
        and public_render["source"] == binding["source"]
        and public_render["publicSkills"] == public_skills
        and public_render["productRelease"]
        == inputs["rendererSelection"]["productRelease"]
        and public_manifest["scope"] == "public"
        and public_manifest["source"] == public_render["source"]
        and public_manifest["publicSkills"] == public_render["publicSkills"]
        and public_manifest["privateSkills"] == []
        and public_manifest.get("bindingDigest") is None
        and public_manifest.get("customizationDigest") is None
        and public_manifest["productRelease"] == public_render["productRelease"]
        and public_manifest["rendererRelease"] == public_render["rendererRelease"]
        and public_manifest["platform"] == public_render["platform"]
        and public_manifest["productDistributionDigest"]
        == public_render["productDistributionDigest"]
        and public_manifest["compiledAllowlistDigest"]
        == public_render["compiledAllowlistDigest"]
        and public_manifest["rendererSchemas"] == public_render["rendererSchemas"]
        and public_manifest["inputParametersDigest"]
        == public_render["normalizedParametersDigest"]
        and public_render["files"]
        == [
            {
                "path": entry["path"],
                "digest": entry["digest"],
                "size": entry["size"],
                "mode": entry["mode"],
            }
            for entry in public_manifest["files"]
        ],
        "private_input_artifact_binding_mismatch",
        "candidate/binding/public render/contract bundle",
    )
    approval_by_skill = {
        entry["skill"]["digest"]: entry for entry in inputs["skillApprovals"]
    }
    effective_skill_descriptors = [
        *inputs["effectiveSkillSet"]["publicSkills"],
        *inputs["effectiveSkillSet"]["privateSkills"],
    ]
    require(
        set(approval_by_skill)
        == {descriptor["digest"] for descriptor in effective_skill_descriptors},
        "skill_approval_set_mismatch",
        "exact effective skill set",
    )
    for skill_descriptor in effective_skill_descriptors:
        public_skill = skill_descriptor in public_skills
        expected_skill_purpose = (
            "public-source-v1"
            if public_skill
            else "consumer-private-skill-v1"
        )
        role_descriptor(
            skill_descriptor,
            "application/vnd.bytedesk.agent.skill.v1+json",
            expected_skill_purpose,
            "effective skill",
        )
        approval_entry = approval_by_skill[skill_descriptor["digest"]]
        role_descriptor(
            approval_entry["approval"],
            "application/vnd.bytedesk.agent.skill-approval.v1+json",
            "consumer-authority-v1",
            "skill approval",
        )
        require(
            approval_entry["skill"] == skill_descriptor,
            "skill_approval_descriptor_mismatch",
            skill_descriptor["digest"],
        )
        skill_payload = store.resolve(skill_descriptor)
        if public_skill:
            skill_package_id = (
                "public-skill-"
                + skill_descriptor["digest"].removeprefix("sha256:")[:24]
            )
            skill_evidence = {
                evidence_class: canonical_digest(
                    {
                        "profile": "bytedesk.public-skill-review-evidence/1",
                        "evidenceClass": evidence_class,
                        "skill": skill_descriptor,
                        "publicRender": inputs["publicArtifact"],
                    }
                )
                for evidence_class in ("scan", "sbom", "license")
            }
        else:
            skill = parse_json_bytes(
                skill_payload, f"skill {skill_descriptor['digest']}"
            )
            validate_schema_instance(
                skill,
                "https://schemas.bytedesk.ai/agent-delivery/v1/skill-package/1.0.0",
                registry,
                schemas,
            )
            skill_package_id = skill["packageId"]
            skill_evidence = {
                evidence_class: skill["evidence"][evidence_class]["digest"]
                for evidence_class in ("scan", "sbom", "license")
            }
        approval = parse_json_bytes(
            store.resolve(approval_entry["approval"]),
            f"skill approval {skill_descriptor['digest']}",
        )
        validate_schema_instance(
            approval,
            "https://schemas.bytedesk.ai/agent-delivery/v1/skill-approval/1.0.0",
            registry,
            schemas,
        )
        require(
            approval["skill"] == skill_descriptor
            and approval["packageId"] == skill_package_id
            and approval["consumerId"] == inputs["consumerId"]
            and approval["subjectId"] == inputs["subjectId"]
            and approval["installationId"] == inputs["installationId"]
            and approval["useScope"]["target"]
            == {"kind": "exact_target", "targetId": inputs["targetId"]}
            and inputs["harnessId"] in approval["useScope"]["harnesses"]
            and "compile" in approval["useScope"]["operations"]
            and timestamp(approval["issuedAt"]) <= epoch
            and epoch < timestamp(approval["expiresAt"])
            and approval["revocation"] == {"status": "active"}
            and approval["approvalPolicy"] == authority["signerPolicy"]
            and approval["signerPolicy"] == authority["signerPolicy"]
            and approval["evidenceDigests"]["scan"]
            == skill_evidence["scan"]
            and approval["evidenceDigests"]["sbom"]
            == skill_evidence["sbom"]
            and approval["evidenceDigests"]["license"]
            == skill_evidence["license"],
            "skill_approval_invalid",
            skill_descriptor["digest"],
        )
    validate_release_status_eligibility(
        descriptor=inputs["releaseStatusEligibility"],
        expected_digest=inputs["releaseStatusEligibilityDigest"],
        expected_verification_digest=inputs[
            "releaseStatusEligibilityVerificationEvidenceDigest"
        ],
        expected_stage="private_compilation",
        operation_time=inputs["reproducibleEpoch"],
        consumer_id=inputs["consumerId"],
        selection=selection,
        entry_prefix="private-compilation",
        eligibility_verification_id=(
            "private-compilation-eligibility-signature"
        ),
        store=store,
        registry=registry,
        schemas=schemas,
    )


def validate_trust_policy_ref(
    policy_ref: dict[str, Any],
    purpose: str,
    consumer_id: str | None,
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    operation_time: str,
) -> dict[str, Any]:
    pin_set = store.trust_policy_pin_set(purpose, consumer_id)
    try:
        pin_set.authorize_policy(
            purpose=purpose,
            reference=policy_ref,
            use="new",
            verification_time=operation_time,
        )
    except TrustPolicyPinError as error:
        raise GraphError(error.code, str(error)) from error
    require(
        policy_ref == store.trust_policy_pin(purpose, consumer_id),
        "trust_policy_pin_mismatch",
        purpose,
    )
    policy = parse_json_bytes(
        store.resolve_digest(policy_ref["digest"]), f"trust policy {purpose}"
    )
    validate_schema_instance(policy, TRUST_POLICY_SCHEMA_ID, registry, schemas)
    require(
        policy_ref == {"id": policy["policyId"], "digest": canonical_digest(policy)}
        and policy["policyId"] == purpose
        and policy["scope"]["purposes"] == [purpose],
        "trust_policy_mismatch",
        purpose,
    )
    if consumer_id is None:
        require(
            "consumers" not in policy["scope"],
            "trust_policy_consumer_smuggling",
            purpose,
        )
    else:
        require(
            policy["scope"].get("consumers") == [consumer_id],
            "trust_policy_consumer_mismatch",
            purpose,
        )
    kms_signers = [
        signer
        for signer in policy["signers"]
        if signer.get("purpose") == purpose
        and signer.get("credentialKind") == "kms_key"
    ]
    keyless_signers = [
        signer
        for signer in policy["signers"]
        if signer.get("purpose") == purpose
        and signer.get("credentialKind") == "sigstore_keyless"
    ]
    if purpose == "contract-bundle-release-v1":
        require(
            not kms_signers and len(keyless_signers) == 1,
            "trust_policy_contract_bundle_keyless_signer_count",
            purpose,
        )
        require(
            policy["scope"]["repositories"]
            == ["registry.example/product/contracts"]
            and policy["scope"]["mediaTypes"]
            == [
                "application/vnd.bytedesk.agent.contract-bundle.v1+json",
            ]
            and policy["scope"]["purposes"]
            == [CONTRACT_BUNDLE_RELEASE_PURPOSE],
            "trust_policy_contract_bundle_scope_mismatch",
            purpose,
        )
        signer = keyless_signers[0]
    else:
        require(
            len(kms_signers) == 1 and not keyless_signers,
            "trust_policy_kms_signer_count",
            purpose,
        )
        signer = kms_signers[0]
    if purpose in fixture_generator.PRODUCT_TRUST_PURPOSE_ROLES:
        require(
            consumer_id is None,
            "trust_policy_product_consumer_scope",
            purpose,
        )
    else:
        require(consumer_id is not None, "trust_policy_consumer_scope", purpose)
    require(
        signer["purpose"] == purpose,
        "trust_policy_signer_purpose_mismatch",
        purpose,
    )
    return policy


def validate_contract_bundle_keyless_verification(
    product_release: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    operation_time: str,
) -> dict[str, Any]:
    """Replay the independent keyless verification edge before private use."""

    receipt = product_release.get("contractBundleVerification")
    require(
        isinstance(receipt, dict),
        "contract_bundle_keyless_verification_missing",
        product_release.get("version", "product release"),
    )
    subject = product_release["contractBundle"]
    require(
        receipt.get("profile") == KEYLESS_VERIFICATION_PROFILE
        and receipt.get("decision") == "permitted"
        and receipt.get("authorityIssued") is False
        and receipt.get("subject") == subject
        and receipt.get("purpose")
        == KEYLESS_CONTRACT_BUNDLE_RELEASE_PURPOSE
        and receipt.get("credentialKind") == "sigstore_keyless"
        and receipt.get("trustPolicy") == subject["trustPolicy"]
        and receipt.get("signingRequestDigest")
        == receipt.get("signingRequest", {}).get("digest")
        and receipt.get("signatureBundleDigest")
        == receipt.get("signatureBundle", {}).get("digest")
        and receipt.get("trustedRootDigest")
        == receipt.get("authenticatedSigner", {}).get("trustedRootDigest")
        and receipt.get("builderDigest")
        == receipt.get("authenticatedSigner", {})
        .get("claims", {})
        .get("builderDigest")
        and receipt.get("verificationEvidenceDigest")
        == canonical_digest(
            {
                "profile": KEYLESS_VERIFICATION_EVIDENCE_PROFILE,
                **{
                    key: deepcopy(value)
                    for key, value in receipt.items()
                    if key != "verificationEvidenceDigest"
                },
            }
        )
        and timestamp(receipt["verifiedAt"])
        <= timestamp(product_release["publishedAt"])
        <= timestamp(operation_time),
        "contract_bundle_keyless_verification_binding_mismatch",
        subject["digest"],
    )
    role_descriptor(
        subject,
        CONTRACT_BUNDLE_MEDIA_TYPE,
        KEYLESS_CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "product release contract bundle",
    )
    subject_bytes = store.resolve(subject)
    contract_bundle = parse_json_bytes(subject_bytes, "product contract bundle")
    validate_schema_instance(
        contract_bundle,
        CONTRACT_BUNDLE_SCHEMA_ID,
        registry,
        schemas,
    )
    policy = validate_trust_policy_ref(
        receipt["trustPolicy"],
        KEYLESS_CONTRACT_BUNDLE_RELEASE_PURPOSE,
        None,
        store,
        registry,
        schemas,
        receipt["verifiedAt"],
    )
    policy_bytes = store.resolve_digest(receipt["trustPolicy"]["digest"])
    keyless_signers = [
        signer
        for signer in policy["signers"]
        if signer.get("purpose")
        == KEYLESS_CONTRACT_BUNDLE_RELEASE_PURPOSE
        and signer.get("credentialKind") == "sigstore_keyless"
    ]
    require(
        policy["signers"] == keyless_signers
        and len(keyless_signers) == 1
        and keyless_signers[0] == receipt["authenticatedSigner"],
        "contract_bundle_keyless_policy_signer_mismatch",
        subject["digest"],
    )

    signing_request_descriptor = receipt["signingRequest"]
    require(
        isinstance(signing_request_descriptor, dict)
        and set(signing_request_descriptor)
        == {"repository", "digest", "mediaType", "size"}
        and signing_request_descriptor["repository"] == subject["repository"]
        and signing_request_descriptor["mediaType"] == SIGNING_REQUEST_MEDIA_TYPE,
        "contract_bundle_keyless_signing_request_descriptor_mismatch",
        subject["digest"],
    )
    signing_request_bytes = store.resolve(signing_request_descriptor)
    signing_request = parse_json_bytes(
        signing_request_bytes,
        "contract bundle signing request",
    )
    validate_schema_instance(
        signing_request,
        SIGNING_REQUEST_SCHEMA_ID,
        registry,
        schemas,
    )
    signature_bundle_descriptor = receipt["signatureBundle"]
    require(
        isinstance(signature_bundle_descriptor, dict)
        and set(signature_bundle_descriptor)
        == {"repository", "digest", "mediaType", "size"}
        and signature_bundle_descriptor["repository"] == subject["repository"]
        and signature_bundle_descriptor["mediaType"] == SIGSTORE_BUNDLE_MEDIA_TYPE,
        "contract_bundle_keyless_signature_bundle_descriptor_mismatch",
        subject["digest"],
    )
    signature_bundle_bytes = store.resolve(signature_bundle_descriptor)
    try:
        verified = store.keyless_signature_verifier.verify(
            subject=subject,
            subject_bytes=subject_bytes,
            policy=policy,
            policy_bytes=policy_bytes,
            permitted_signer=keyless_signers[0],
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
            expected_workflow=receipt["authenticatedSigner"]["claims"][
                "workflow"
            ],
            expected_workload_identity=receipt["authenticatedSigner"][
                "workloadIdentity"
            ],
            expected_claims=receipt["authenticatedSigner"]["claims"],
            expected_builder_digest=receipt["builderDigest"],
            expected_pre_sign_certification_digest=receipt[
                "preSignCertificationDigest"
            ],
            expected_signing_request_digest=receipt["signingRequestDigest"],
            expected_signature_bundle_digest=receipt["signatureBundleDigest"],
        )
    except TrustedKeylessVerificationError as error:
        raise GraphError(error.code, str(error)) from error
    require(
        verified == receipt,
        "contract_bundle_keyless_verification_receipt_mismatch",
        subject["digest"],
    )
    return contract_bundle


def validate_signing_time(
    *,
    signed_at: str,
    operation_time: str,
    not_before: str,
    not_after: str,
    purpose: str,
) -> None:
    require(
        timestamp(not_before)
        <= timestamp(signed_at)
        < timestamp(not_after)
        and timestamp(signed_at) <= timestamp(operation_time),
        "signing_time_outside_policy",
        purpose,
    )


def validate_signing_result(
    result: dict[str, Any],
    purpose: str,
    subject_digest: str,
    subject_media_type: str,
    consumer_id: str | None,
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    *,
    operation_time: str,
    policy: dict[str, Any] | None = None,
    expected_repository: str,
) -> None:
    validate_schema_instance(
        result, SIGNING_RESULT_SCHEMA_ID, registry, schemas
    )
    require(
        result["purpose"] == purpose
        and result["subjectDigest"] == subject_digest
        and result["subjectMediaType"] == subject_media_type,
        "signing_subject_mismatch",
        purpose,
    )
    if consumer_id is None:
        require("consumerId" not in result, "signing_consumer_smuggling", purpose)
    else:
        require(
            result.get("consumerId") == consumer_id,
            "signing_consumer_mismatch",
            purpose,
        )
    if policy is not None:
        require(
            result["trustPolicy"] == policy,
            "signing_policy_mismatch",
            purpose,
        )
    require(
        result["repository"] == expected_repository,
        "signing_repository_mismatch",
        purpose,
    )
    resolved_policy = validate_trust_policy_ref(
        result["trustPolicy"],
        purpose,
        consumer_id,
        store,
        registry,
        schemas,
        operation_time,
    )
    try:
        policy_signer = exact_policy_signer(
            resolved_policy,
            purpose=purpose,
            subject_media_type=result["subjectMediaType"],
            key_version=result["keyVersion"],
            algorithm=result["algorithm"],
            public_key_digest=result["publicKeyDigest"],
        )
    except ValueError as error:
        raise GraphError("signer_not_permitted", purpose) from error
    validate_signing_time(
        signed_at=result["signedAt"],
        operation_time=operation_time,
        not_before=resolved_policy["effective"]["notBefore"],
        not_after=resolved_policy["effective"]["notAfter"],
        purpose=purpose,
    )
    require(
        result["publicKeyDigest"] == policy_signer["publicKeyDigest"],
        "signer_public_key_policy_mismatch",
        purpose,
    )
    request_fields = {
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
    fixture_request_digest = canonical_digest(
        {
            "profile": "bytedesk.fixture-signing-request/1",
            "consumerId": consumer_id,
            **request_fields,
        }
    )
    renderer_request_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-signing-request/1",
            **request_fields,
        }
    )
    require(
        result["requestDigest"]
        in {fixture_request_digest, renderer_request_digest},
        "signing_request_digest_mismatch",
        purpose,
    )
    renderer_signing_profile = result["requestDigest"] == renderer_request_digest
    expected_request_digest = result["requestDigest"]
    signature_bundle = result["signatureBundle"]
    role_descriptor(
        signature_bundle,
        "application/vnd.dev.sigstore.bundle.v0.3+json",
        purpose,
        f"{purpose} signature bundle",
    )
    require(
        signature_bundle["repository"] == result["repository"]
        and result["repository"] in resolved_policy["scope"]["repositories"]
        and subject_media_type in resolved_policy["scope"]["mediaTypes"]
        and signature_bundle["mediaType"]
        in resolved_policy["scope"]["mediaTypes"],
        "signing_scope_mismatch",
        purpose,
    )
    provider_evidence_descriptor = result["providerAuditEvidence"]
    role_descriptor(
        provider_evidence_descriptor,
        fixture_generator.SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        purpose,
        f"{purpose} signer authentication evidence",
    )
    require(
        provider_evidence_descriptor["repository"] == result["repository"]
        and provider_evidence_descriptor["trustPolicy"]
        == result["trustPolicy"]
        and provider_evidence_descriptor["mediaType"]
        in resolved_policy["scope"]["mediaTypes"],
        "signer_authentication_evidence_scope_mismatch",
        purpose,
    )
    provider_evidence = parse_json_bytes(
        store.resolve(provider_evidence_descriptor),
        f"{purpose} signer authentication evidence",
    )
    validate_schema_instance(
        provider_evidence,
        SIGNER_AUTHENTICATION_EVIDENCE_SCHEMA_ID,
        registry,
        schemas,
    )
    expected_provider_evidence = build_signer_authentication_evidence(
        schema_descriptor=fixture_generator.schema_descriptor(
            "signer-authentication-evidence"
        ),
        purpose=purpose,
        subject_media_type=result["subjectMediaType"],
        request_id=result["requestId"],
        request_digest=expected_request_digest,
        provider_request_id=f"fixture-kms-request:{result['requestId']}",
        provider_audit_id=f"fixture-kms-audit:{result['requestId']}",
        authenticated_signer=policy_signer,
        issued_at=result["signedAt"],
        trust_policy=result["trustPolicy"],
    )
    require(
        provider_evidence == expected_provider_evidence,
        "signer_authentication_evidence_policy_mismatch",
        purpose,
    )
    bundle = parse_json_bytes(
        store.resolve(signature_bundle), f"{purpose} signature bundle"
    )
    expected_statement = {
        "profile": (
            "bytedesk.renderer-authenticated-signature-statement/1"
            if renderer_signing_profile
            else "bytedesk.fixture-authenticated-signature-statement/1"
        ),
        "requestId": result["requestId"],
        "requestDigest": expected_request_digest,
        "purpose": purpose,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "algorithm": result["algorithm"],
        "keyVersion": result["keyVersion"],
        "publicKeyDigest": result["publicKeyDigest"],
        "repository": result["repository"],
        "trustPolicy": result["trustPolicy"],
        "providerAuditEvidence": provider_evidence_descriptor,
        "authenticatedSigner": deepcopy(policy_signer),
        "signedAt": result["signedAt"],
    }
    if not renderer_signing_profile:
        expected_statement["consumerId"] = consumer_id
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
        "signature_bundle_binding_mismatch",
        purpose,
    )
    timestamp(operation_time)
    pin_set = store.trust_policy_pin_set(purpose, consumer_id)
    try:
        verification_result = store.signature_verifier.verify(
            result=result,
            policy=resolved_policy,
            permitted_signer=policy_signer,
            verification_time=operation_time,
            expected_purpose=purpose,
            expected_subject_media_type=subject_media_type,
            expected_signing_repository=expected_repository,
            pin_set_digest=pin_set.digest,
            pin_set_revocations=pin_set.revocations,
            expected_consumer_id=consumer_id,
        )
    except TrustedKmsVerificationError as error:
        raise GraphError(error.code, str(error)) from error
    expected_verification_request_digest = canonical_digest(
        {
            "profile": "bytedesk.kms-signature-verification-request/1",
            "purpose": purpose,
            "subjectDigest": subject_digest,
            "subjectMediaType": subject_media_type,
            "signatureBundle": result["signatureBundle"],
            "signingRepository": expected_repository,
            "trustPolicy": result["trustPolicy"],
            "pinSetDigest": pin_set.digest,
            "consumerId": consumer_id,
            "providerAuditEvidence": result["providerAuditEvidence"],
            "verificationTime": operation_time,
        }
    )
    expected_verification_evidence_digest = canonical_digest(
        {
            "profile": "bytedesk.kms-signature-verification-evidence/1",
            **{
                key: deepcopy(value)
                for key, value in verification_result.items()
                if key != "verificationEvidenceDigest"
            },
        }
    )
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
        == expected_verification_request_digest
        and verification_result["signatureBundleDigest"]
        == result["signatureBundle"]["digest"]
        and verification_result["subjectDigest"] == subject_digest
        and verification_result["purpose"] == purpose
        and verification_result["subjectMediaType"] == subject_media_type
        and verification_result["signingRepository"] == expected_repository
        and verification_result["verificationTime"] == operation_time
        and verification_result["evaluatedPolicyDigest"]
        == result["trustPolicy"]["digest"]
        and verification_result["pinSetDigest"] == pin_set.digest
        and verification_result["consumerId"] == consumer_id
        and verification_result["authenticatedSigner"] == policy_signer
        and verification_result["providerAuditEvidence"]
        == result["providerAuditEvidence"]
        and verification_result["providerAuditEvidenceDigest"]
        == result["providerAuditEvidence"]["digest"]
        and verification_result["verificationEvidenceDigest"]
        == expected_verification_evidence_digest,
        "kms_verification_result_mismatch",
        purpose,
    )



def expected_permitted_signature_verification(
    *,
    result: dict[str, Any],
    purpose: str,
    signed_subject_digest: str,
    signed_subject_media_type: str,
    verification_subject: dict[str, Any],
    consumer_id: str | None,
    operation_time: str,
    verification_id: str,
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    validate_signing_result(
        result,
        purpose,
        signed_subject_digest,
        signed_subject_media_type,
        consumer_id,
        store,
        registry,
        schemas,
        operation_time=operation_time,
        expected_repository=result["repository"],
    )
    policy = validate_trust_policy_ref(
        result["trustPolicy"],
        purpose,
        consumer_id,
        store,
        registry,
        schemas,
        operation_time,
    )
    try:
        signer = exact_policy_signer(
            policy,
            purpose=purpose,
            subject_media_type=result["subjectMediaType"],
            key_version=result["keyVersion"],
            algorithm=result["algorithm"],
            public_key_digest=result["publicKeyDigest"],
        )
        pin_set = store.trust_policy_pin_set(purpose, consumer_id)
        return store.signature_verifier.verify_permitted(
            result=result,
            policy=policy,
            permitted_signer=signer,
            verification_time=operation_time,
            expected_purpose=purpose,
            expected_signed_subject_digest=signed_subject_digest,
            expected_signed_subject_media_type=signed_subject_media_type,
            verification_subject=verification_subject,
            expected_signing_repository=result["repository"],
            pin_set_digest=pin_set.digest,
            pin_set_revocations=pin_set.revocations,
            expected_consumer_id=consumer_id,
            verification_result_schema_descriptor=fixture_generator.schema_descriptor(
                "verification-result"
            ),
            verification_id=verification_id,
        )
    except (ValueError, TrustedKmsVerificationError) as error:
        code = getattr(error, "code", "signer_not_permitted")
        raise GraphError(code, verification_id) from error


def require_verification_result(
    digest: str,
    expected: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = store.resolve_digest(digest)
    result = parse_json_bytes(payload, expected["verificationId"])
    validate_schema_instance(
        result, VERIFICATION_RESULT_SCHEMA_ID, registry, schemas
    )
    require(
        raw_digest(payload) == digest and result == expected,
        "release_status_verification_result_mismatch",
        expected["verificationId"],
    )
    return result


def validate_status_eligibility_entry(
    *,
    entry: dict[str, Any],
    entry_id: str,
    expected_kind: str,
    expected_subject: dict[str, Any],
    expected_status: dict[str, Any],
    operation_time: str,
    evidence_time: str | None = None,
    use_recorded_verification_digests: bool = True,
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> list[str]:
    checkpoint_evidence_time = evidence_time or operation_time
    verification_digests: list[str] = []

    def verify_result(
        expected: dict[str, Any], recorded_digest: str | None = None
    ) -> str:
        digest = (
            recorded_digest
            if use_recorded_verification_digests
            else raw_digest(canonical_bytes(expected))
        )
        require(
            isinstance(digest, str),
            "release_status_verification_result_missing",
            expected["verificationId"],
        )
        require_verification_result(
            digest, expected, store, registry, schemas
        )
        verification_digests.append(digest)
        return digest

    require(
        entry["subjectKind"] == expected_kind
        and entry["subject"] == expected_subject
        and entry["status"] == expected_status,
        "release_status_eligibility_subject_substitution",
        entry_id,
    )
    status_payload = store.resolve(entry["status"])
    status = parse_json_bytes(status_payload, f"{entry_id} status")
    validate_schema_instance(status, RELEASE_STATUS_SCHEMA_ID, registry, schemas)
    require(
        status["subjectKind"] == expected_kind
        and status["subject"] == expected_subject
        and status["status"] == "current"
        and timestamp(status["effectiveAt"]) <= timestamp(operation_time)
        and status["authorityDigest"]
        == canonical_digest(
            inline_authority_preimage(
                status, schemas[RELEASE_STATUS_SCHEMA_ID]
            )
        ),
        "release_status_not_eligible",
        entry_id,
    )
    status_verification = expected_permitted_signature_verification(
        result=status["signingResult"],
        purpose="release-status-v1",
        signed_subject_digest=status["authorityDigest"],
        signed_subject_media_type=entry["status"]["mediaType"],
        verification_subject=entry["status"],
        consumer_id=None,
        operation_time=operation_time,
        verification_id=f"{entry_id}-status-signature",
        store=store,
        registry=registry,
        schemas=schemas,
    )
    verify_result(
        status_verification,
        entry["verificationEvidenceDigests"]["status"],
    )
    checkpoint = parse_json_bytes(
        store.resolve(entry["checkpoint"]), f"{entry_id} checkpoint"
    )
    validate_schema_instance(
        checkpoint, STATUS_CHECKPOINT_SCHEMA_ID, registry, schemas
    )
    require(
        checkpoint["subjectKind"] == expected_kind
        and checkpoint["subject"] == expected_subject
        and checkpoint["head"] == entry["status"]
        and checkpoint["headDigest"] == entry["status"]["digest"]
        and checkpoint["requestNonce"] == entry["requestNonce"]
        and checkpoint["clientPriorState"] == entry["clientPriorState"]
        and checkpoint["clientPriorState"]["kind"] == "match"
        and checkpoint["verifiedAt"] == checkpoint_evidence_time
        and timestamp(checkpoint["verifiedAt"])
        <= timestamp(operation_time)
        < timestamp(checkpoint["expiresAt"]),
        "release_status_checkpoint_not_fresh",
        entry_id,
    )
    authentication = parse_json_bytes(
        store.resolve(entry["checkpointAuthenticationEvidence"]),
        f"{entry_id} checkpoint authentication",
    )
    validate_schema_instance(
        authentication,
        STATUS_CHECKPOINT_AUTH_SCHEMA_ID,
        registry,
        schemas,
    )
    require(
        authentication["checkpointDigest"] == entry["checkpoint"]["digest"]
        and authentication["requestNonce"] == entry["requestNonce"]
        and authentication["evidenceDigest"]
        == canonical_digest(
            schema_field_authority_preimage(
                authentication,
                schemas[STATUS_CHECKPOINT_AUTH_SCHEMA_ID],
                "evidenceDigest",
            )
        ),
        "release_status_checkpoint_authentication_mismatch",
        entry_id,
    )
    checkpoint_verification = expected_permitted_signature_verification(
        result=authentication["signingResult"],
        purpose="release-status-head-v1",
        signed_subject_digest=entry["checkpoint"]["digest"],
        signed_subject_media_type=entry["checkpoint"]["mediaType"],
        verification_subject=entry["checkpoint"],
        consumer_id=None,
        operation_time=operation_time,
        verification_id=f"{entry_id}-checkpoint-authentication",
        store=store,
        registry=registry,
        schemas=schemas,
    )
    checkpoint_verification_digest = verify_result(
        checkpoint_verification,
        entry["verificationEvidenceDigests"]["checkpointAuthentication"],
    )
    inclusion = parse_json_bytes(
        store.resolve(entry["headInclusionProof"]),
        f"{entry_id} inclusion proof",
    )
    validate_schema_instance(
        inclusion, STATUS_INCLUSION_SCHEMA_ID, registry, schemas
    )
    require(
        checkpoint["headInclusionProof"] == entry["headInclusionProof"]
        and inclusion["subjectKind"] == expected_kind
        and inclusion["subject"] == expected_subject
        and inclusion["leafDigest"] == checkpoint["headLeafDigest"]
        and inclusion["rootDigest"] == checkpoint["logRootDigest"]
        and inclusion["treeSize"] == checkpoint["treeSize"]
        and verify_inclusion(
            leaf_digest=inclusion["leafDigest"],
            leaf_index=inclusion["leafIndex"],
            tree_size=inclusion["treeSize"],
            audit_path=inclusion["auditPath"],
            expected_root=inclusion["rootDigest"],
        ),
        "release_status_inclusion_verification_failed",
        entry_id,
    )
    inclusion_math = {
        "profile": "bytedesk.release-status-inclusion-verification/1",
        "algorithm": "bytedesk-rfc6962-inclusion-v1",
        "subject": deepcopy(expected_subject),
        "status": deepcopy(entry["status"]),
        "checkpoint": deepcopy(entry["checkpoint"]),
        "proof": deepcopy(entry["headInclusionProof"]),
        "leafDigest": inclusion["leafDigest"],
        "leafIndex": inclusion["leafIndex"],
        "treeSize": inclusion["treeSize"],
        "auditPath": deepcopy(inclusion["auditPath"]),
        "expectedRoot": inclusion["rootDigest"],
        "decision": "permitted",
    }
    inclusion_math_digest = canonical_digest(inclusion_math)
    require(
        store.resolve_digest(inclusion_math_digest)
        == canonical_bytes(inclusion_math),
        "release_status_inclusion_evidence_missing",
        entry_id,
    )
    inclusion_verification = permitted_verification_result(
        schema_descriptor=fixture_generator.schema_descriptor(
            "verification-result"
        ),
        verification_id=f"{entry_id}-head-inclusion",
        subject=entry["headInclusionProof"],
        policy=entry["headInclusionProof"]["trustPolicy"],
        evaluated_at=operation_time,
        evidence_digests=[
            checkpoint_verification_digest,
            inclusion_math_digest,
        ],
    )
    verify_result(
        inclusion_verification,
        entry["verificationEvidenceDigests"]["headInclusionProof"],
    )
    if entry["consistencyProof"] is None:
        require(
            checkpoint["consistencyProof"] is None
            and entry["verificationEvidenceDigests"]["consistencyProof"]
            is None,
            "release_status_consistency_verification_mismatch",
            entry_id,
        )
    else:
        consistency = parse_json_bytes(
            store.resolve(entry["consistencyProof"]),
            f"{entry_id} consistency proof",
        )
        validate_schema_instance(
            consistency, STATUS_CONSISTENCY_SCHEMA_ID, registry, schemas
        )
        require(
            checkpoint["consistencyProof"] == entry["consistencyProof"]
            and consistency["subject"] == expected_subject
            and consistency["authorityDigest"]
            == canonical_digest(
                inline_authority_preimage(
                    consistency, schemas[STATUS_CONSISTENCY_SCHEMA_ID]
                )
            )
            and consistency["to"]["headDigest"] == entry["status"]["digest"]
            and consistency["to"]["logRootDigest"]
            == checkpoint["logRootDigest"]
            and verify_consistency(
                old_size=consistency["from"]["treeSize"],
                new_size=consistency["to"]["treeSize"],
                old_root=consistency["from"]["logRootDigest"],
                new_root=consistency["to"]["logRootDigest"],
                audit_path=consistency["auditPath"],
            ),
            "release_status_consistency_verification_failed",
            entry_id,
        )
        consistency_signature = expected_permitted_signature_verification(
            result=consistency["signingResult"],
            purpose="release-status-head-v1",
            signed_subject_digest=consistency["authorityDigest"],
            signed_subject_media_type=entry["consistencyProof"]["mediaType"],
            verification_subject=entry["consistencyProof"],
            consumer_id=None,
            operation_time=operation_time,
            verification_id=f"{entry_id}-consistency-signature",
            store=store,
            registry=registry,
            schemas=schemas,
        )
        consistency_signature_digest = canonical_digest(consistency_signature)
        verify_result(
            consistency_signature,
            consistency_signature_digest,
        )
        consistency_math = {
            "profile": "bytedesk.release-status-consistency-verification/1",
            "algorithm": consistency["algorithm"],
            "subject": deepcopy(expected_subject),
            "checkpoint": deepcopy(entry["checkpoint"]),
            "proof": deepcopy(entry["consistencyProof"]),
            "from": deepcopy(consistency["from"]),
            "to": deepcopy(consistency["to"]),
            "auditPath": deepcopy(consistency["auditPath"]),
            "decision": "permitted",
        }
        consistency_math_digest = canonical_digest(consistency_math)
        require(
            store.resolve_digest(consistency_math_digest)
            == canonical_bytes(consistency_math),
            "release_status_consistency_evidence_missing",
            entry_id,
        )
        expected_consistency = permitted_verification_result(
            schema_descriptor=fixture_generator.schema_descriptor(
                "verification-result"
            ),
            verification_id=f"{entry_id}-consistency",
            subject=entry["consistencyProof"],
            policy=entry["consistencyProof"]["trustPolicy"],
            evaluated_at=operation_time,
            evidence_digests=[
                checkpoint_verification_digest,
                consistency_signature_digest,
                consistency_math_digest,
            ],
        )
        verify_result(
            expected_consistency,
            entry["verificationEvidenceDigests"]["consistencyProof"],
        )
    return verification_digests


def validate_release_status_eligibility(
    *,
    descriptor: dict[str, Any],
    expected_digest: str,
    expected_verification_digest: str,
    expected_stage: str,
    operation_time: str,
    consumer_id: str,
    selection: dict[str, Any],
    entry_prefix: str,
    eligibility_verification_id: str,
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    role_descriptor(
        descriptor,
        fixture_generator.STATUS_ELIGIBILITY_MEDIA_TYPE,
        "consumer-release-status-eligibility-v1",
        expected_stage,
    )
    eligibility = parse_json_bytes(
        store.resolve(descriptor), f"{expected_stage} eligibility"
    )
    validate_schema_instance(
        eligibility, STATUS_ELIGIBILITY_SCHEMA_ID, registry, schemas
    )
    authority = schemas[STATUS_ELIGIBILITY_SCHEMA_ID][
        "x-bytedesk-digestAuthority"
    ]
    require(
        eligibility["stage"] == expected_stage
        and eligibility["operationTime"] == operation_time
        and eligibility["consumerId"] == consumer_id
        and eligibility["decision"] == "eligible"
        and eligibility["eligibilityDigest"] == expected_digest
        and expected_digest
        == canonical_digest(
            {
                "profile": authority["profile"],
                **{
                    field: deepcopy(value)
                    for field, value in eligibility.items()
                    if field not in authority["exclude"]
                },
            }
        ),
        "release_status_eligibility_digest_mismatch",
        expected_stage,
    )
    provider_binding, provider_verification = (
        store.trust_policy_provider_binding(consumer_id)
    )
    require(
        eligibility["pinSet"] == provider_binding["pinSetDescriptor"]
        and eligibility["pinSetDigest"]
        == provider_binding["pinSet"]["pinSetDigest"]
        == provider_verification["pinSetDigest"]
        and eligibility["pinSetProviderEvidence"]
        == provider_binding["providerEvidence"]
        and timestamp(
            eligibility["pinSetProviderEvidence"]["readback"]["observedAt"]
        )
        <= timestamp(operation_time),
        "release_status_eligibility_pin_provider_mismatch",
        expected_stage,
    )
    validate_status_eligibility_entry(
        entry=eligibility["product"],
        entry_id=f"{entry_prefix}-product",
        expected_kind="product_release",
        expected_subject=selection["productRelease"],
        expected_status=selection["productReleaseStatus"],
        operation_time=operation_time,
        store=store,
        registry=registry,
        schemas=schemas,
    )
    require(
        len(eligibility["renderers"]) == 1,
        "release_status_eligibility_renderer_set_mismatch",
        expected_stage,
    )
    renderer = eligibility["renderers"][0]
    require(
        {
            key: renderer[key]
            for key in (
                "harnessId",
                "rendererId",
                "rendererVersion",
                "targetPlatform",
            )
        }
        == {
            "harnessId": selection["targetHarness"],
            "rendererId": selection["rendererId"],
            "rendererVersion": selection["rendererVersion"],
            "targetPlatform": selection["targetPlatform"],
        },
        "release_status_eligibility_renderer_set_mismatch",
        expected_stage,
    )
    validate_status_eligibility_entry(
        entry=renderer,
        entry_id=f"{entry_prefix}-hermes",
        expected_kind="renderer_release",
        expected_subject=selection["rendererRelease"],
        expected_status=selection["rendererReleaseStatus"],
        operation_time=operation_time,
        store=store,
        registry=registry,
        schemas=schemas,
    )
    expected_verification = expected_permitted_signature_verification(
        result=eligibility["signingResult"],
        purpose="consumer-release-status-eligibility-v1",
        signed_subject_digest=eligibility["eligibilityDigest"],
        signed_subject_media_type=(
            fixture_generator.STATUS_ELIGIBILITY_DIGEST_MEDIA_TYPE
        ),
        verification_subject=descriptor,
        consumer_id=consumer_id,
        operation_time=operation_time,
        verification_id=eligibility_verification_id,
        store=store,
        registry=registry,
        schemas=schemas,
    )
    require_verification_result(
        expected_verification_digest,
        expected_verification,
        store,
        registry,
        schemas,
    )
    return eligibility


def validate_host_use_time_release_status_eligibility(
    *,
    descriptor: dict[str, Any],
    eligibility: dict[str, Any],
    expected_verification_digest: str,
    historical_verification_digest: str,
    operation_time: str,
    consumer_id: str,
    selection: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> str:
    require(
        eligibility["stage"] == "activation"
        and eligibility["consumerId"] == consumer_id
        and timestamp(eligibility["operationTime"])
        <= timestamp(operation_time),
        "host_eligibility_verification_context_mismatch",
        consumer_id,
    )
    fresh_evidence_digests = validate_status_eligibility_entry(
        entry=eligibility["product"],
        entry_id="activation-host-use-product",
        expected_kind="product_release",
        expected_subject=selection["productRelease"],
        expected_status=selection["productReleaseStatus"],
        operation_time=operation_time,
        evidence_time=eligibility["operationTime"],
        use_recorded_verification_digests=False,
        store=store,
        registry=registry,
        schemas=schemas,
    )
    for renderer in eligibility["renderers"]:
        fresh_evidence_digests.extend(
            validate_status_eligibility_entry(
                entry=renderer,
                entry_id=(
                    "activation-host-use-renderer-"
                    + renderer["rendererId"]
                ),
                expected_kind="renderer_release",
                expected_subject=selection["rendererRelease"],
                expected_status=selection["rendererReleaseStatus"],
                operation_time=operation_time,
                evidence_time=eligibility["operationTime"],
                use_recorded_verification_digests=False,
                store=store,
                registry=registry,
                schemas=schemas,
            )
        )
    eligibility_signature = expected_permitted_signature_verification(
        result=eligibility["signingResult"],
        purpose="consumer-release-status-eligibility-v1",
        signed_subject_digest=eligibility["eligibilityDigest"],
        signed_subject_media_type=(
            fixture_generator.STATUS_ELIGIBILITY_DIGEST_MEDIA_TYPE
        ),
        verification_subject=descriptor,
        consumer_id=consumer_id,
        operation_time=operation_time,
        verification_id=(
            "activation-host-use-time-eligibility-signature"
        ),
        store=store,
        registry=registry,
        schemas=schemas,
    )
    eligibility_signature_digest = raw_digest(
        canonical_bytes(eligibility_signature)
    )
    require_verification_result(
        eligibility_signature_digest,
        eligibility_signature,
        store,
        registry,
        schemas,
    )
    fresh_evidence_digests.append(eligibility_signature_digest)
    aggregate = permitted_verification_result(
        schema_descriptor=fixture_generator.schema_descriptor(
            "verification-result"
        ),
        verification_id=(
            "activation-host-use-time-release-eligibility"
        ),
        subject=descriptor,
        policy=eligibility["signingResult"]["trustPolicy"],
        evaluated_at=operation_time,
        evidence_digests=fresh_evidence_digests,
    )
    require_verification_result(
        expected_verification_digest,
        aggregate,
        store,
        registry,
        schemas,
    )
    require(
        expected_verification_digest != historical_verification_digest
        and aggregate["evaluatedAt"] == operation_time,
        "host_eligibility_verification_not_fresh",
        consumer_id,
    )
    return expected_verification_digest

def validate_signer_purpose_separation(
    policies: dict[str, dict[str, Any]],
) -> None:
    keys = [policy["signers"][0]["keyVersion"] for policy in policies.values()]
    workloads = [
        policy["signers"][0]["workloadIdentity"]
        for policy in policies.values()
    ]
    require(
        len(keys) == len(set(keys)),
        "private_signer_key_purpose_collision",
        ",".join(sorted(policies)),
    )
    require(
        len(workloads) == len(set(workloads)),
        "private_signer_workload_purpose_collision",
        ",".join(sorted(policies)),
    )


def validate_payload(
    descriptor: dict[str, Any],
    manifest: dict[str, Any],
    store: ArtifactStore,
) -> None:
    output = manifest["output"]
    require(
        descriptor["digest"] == output["digest"]
        and descriptor["size"] == output["size"]
        and descriptor["mediaType"] == output["mediaType"],
        "render_payload_descriptor_mismatch",
        "manifest.output",
    )
    payload = store.resolve(descriptor)
    forbidden_exact = {
        "render-manifest.json",
        "consumer-deployment.json",
        "private-compilation-evidence.json",
        "oci-layout",
    }
    inventory = {entry["path"]: entry for entry in manifest["files"]}
    for path in inventory:
        require(
            path not in forbidden_exact
            and not path.startswith(".bytedesk-delivery/")
            and not path.startswith("blobs/sha256/"),
            "render_payload_self_inventory",
            path,
        )
    actual: dict[str, tuple[bytes, str]] = {}
    try:
        with tarfile.open(fileobj=BytesIO(payload), mode="r:") as archive:
            for member in archive.getmembers():
                require(member.isfile(), "render_payload_entry_type", member.name)
                stream = archive.extractfile(member)
                require(stream is not None, "render_payload_entry_missing", member.name)
                actual[member.name] = (stream.read(), f"{member.mode:04o}")
    except tarfile.TarError as error:
        raise GraphError("render_payload_invalid_archive", str(error)) from error
    require(
        set(actual) == set(inventory),
        "render_payload_inventory_mismatch",
        "archive paths",
    )
    for path, (content, mode) in actual.items():
        entry = inventory[path]
        require(
            entry["digest"] == raw_digest(content)
            and entry["size"] == len(content)
            and entry["mode"] == mode,
            "render_payload_file_mismatch",
            path,
        )
    require(
        output["treeDigest"]
        == canonical_digest(
            {"profile": "bytedesk.renderer-output-tree/1", "files": manifest["files"]}
        )
        and output["fileCount"] == len(manifest["files"])
        and output["expandedSize"]
        == sum(entry["size"] for entry in manifest["files"]),
        "render_payload_output_mismatch",
        "manifest output identity",
    )


def validate_deployment(
    lock: dict[str, Any],
    deployment: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    inputs = lock["inputs"]
    role_descriptor(
        deployment["compilationInput"],
        fixture_generator.PRIVATE_INPUT_MEDIA_TYPE,
        "consumer-compilation-input-v1",
        "compilation-input",
    )
    resolved_lock = json.loads(store.resolve(deployment["compilationInput"]))
    require(resolved_lock == lock, "deployment_lock_descriptor_mismatch", "L")
    validate_signing_result(
        deployment["compilationInputSigningResult"],
        "consumer-compilation-input-v1",
        deployment["compilationInput"]["digest"],
        fixture_generator.PRIVATE_INPUT_MEDIA_TYPE,
        deployment["consumerId"],
        store,
        registry,
        schemas,
        operation_time=inputs["reproducibleEpoch"],
        policy=deployment["compilationInput"]["trustPolicy"],
        expected_repository=deployment["compilationInput"]["repository"],
    )
    require(
        deployment["deploymentId"] == fixture_generator.deployment_id(lock),
        "deployment_id_mismatch",
        deployment["deploymentId"],
    )
    direct_equalities = {
        "consumerId": inputs["consumerId"],
        "subjectId": inputs["subjectId"],
        "installationId": inputs["installationId"],
        "harnessId": inputs["harnessId"],
        "targetId": inputs["targetId"],
        "candidate": inputs["candidate"],
        "desiredRevision": inputs["desiredRevision"],
        "predecessor": inputs["predecessor"],
        "runtimeSlot": inputs["runtimeSlot"],
        "activationMode": inputs["activationMode"],
        "publicRender": inputs["publicArtifact"],
        "binding": inputs["binding"],
        "compilationAuthority": inputs["authoritySnapshot"],
        "compilationInputDigest": lock["compilationInputDigest"],
        "rendererSelectionDigest": inputs["rendererSelectionDigest"],
        "releaseStatusEligibility": inputs["releaseStatusEligibility"],
        "releaseStatusEligibilityDigest": inputs[
            "releaseStatusEligibilityDigest"
        ],
        "releaseStatusEligibilityVerificationEvidenceDigest": inputs[
            "releaseStatusEligibilityVerificationEvidenceDigest"
        ],
        "trustPolicyPinSetDigest": inputs["trustPolicyPinSetDigest"],
        "trustPolicyPinSetProviderEvidenceDigest": inputs[
            "trustPolicyPinSetProviderEvidenceDigest"
        ],
        "reproducibleEpoch": inputs["reproducibleEpoch"],
        "createdAt": inputs["reproducibleEpoch"],
    }
    for field, expected in direct_equalities.items():
        require(
            deployment[field] == expected,
            "deployment_lock_field_mismatch",
            field,
        )
    expected_skills = sorted(
        inputs["effectiveSkillSet"]["publicSkills"]
        + inputs["effectiveSkillSet"]["privateSkills"],
        key=lambda entry: (entry["repository"].encode("utf-8"), entry["digest"]),
    )
    require(
        deployment["approvedSkills"] == expected_skills
        and deployment["skillApprovals"]
        == [entry["approval"] for entry in inputs["skillApprovals"]],
        "deployment_skill_set_mismatch",
        "effective skills/approvals",
    )
    policies = inputs["policyDigests"]
    require(
        deployment["opaqueConsumerDigests"]
        == {
            "policy": policies["policy"],
            "grantSet": policies["grantSet"],
            "credentialSet": policies["credentialSet"],
            "workloadIdentity": policies["workloadIdentity"],
            "lifecycle": policies["lifecycle"],
            "sandbox": policies["mandatorySandbox"],
            "network": policies["network"],
            "approvalPolicy": policies["approvalPolicy"],
            "targetBinding": policies["targetBinding"],
        },
        "deployment_policy_digest_mismatch",
        "opaque consumer digests",
    )

    selection = inputs["rendererSelection"]
    execution = deployment["rendererExecution"]
    attempt = execution["attemptAuthority"]
    attempt_auth = execution["attemptAuthenticationEvidence"]
    receipt = execution["receipt"]
    execution_auth = execution["authenticationEvidence"]
    manifest = deployment["effectiveRender"]["manifest"]
    resolved_binding = parse_json_bytes(
        store.resolve(inputs["binding"]), "deployment binding"
    )
    portable_definition = fixture_generator.renderer_portable_definition(
        manifest
    )
    portable_definition_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-portable-definition/1",
            **portable_definition,
        }
    )
    functional_inputs = fixture_generator.renderer_functional_inputs(
        manifest, resolved_binding, inputs
    )
    expected_input_tree_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-production-input-tree/1",
            "functionalInputs": functional_inputs,
        }
    )
    expected_request_frame = fixture_generator.renderer_request_frame_document(
        selection,
        portable_definition,
        portable_definition_digest,
        functional_inputs,
        expected_input_tree_digest,
        inputs["contractBundle"]["digest"],
    )
    request_frame_bytes = store.resolve_digest(attempt["framedRequestDigest"])
    require(
        parse_framed_jcs(request_frame_bytes, "renderer request frame")
        == expected_request_frame
        and raw_digest(request_frame_bytes) == attempt["framedRequestDigest"],
        "renderer_request_frame_binding_mismatch",
        attempt["attemptId"],
    )
    expected_attempt_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-attempt-authority-digest/1",
            **{
                key: attempt[key]
                for key in (
                    "attemptId",
                    "attemptFencingToken",
                    "rendererSelectionDigest",
                    "productReleaseStatusCheckpointDigest",
                    "productReleaseStatusCheckpointAuthenticationEvidenceDigest",
                    "productReleaseStatusRequestNonce",
                    "rendererReleaseStatusCheckpointDigest",
                    "rendererReleaseStatusCheckpointAuthenticationEvidenceDigest",
                    "rendererReleaseStatusRequestNonce",
                    "portableDefinitionDigest",
                    "inputTreeDigest",
                    "framedRequestDigest",
                    "contractBundleDigest",
                    "sandboxProfileDigest",
                    "issuerIdentityDigest",
                    "issuedAt",
                    "expiresAt",
                )
            },
        }
    )
    require(
        attempt["authorityDigest"] == expected_attempt_digest
        and attempt["rendererSelectionDigest"] == selection["selectionDigest"]
        and attempt["productReleaseStatusCheckpointDigest"]
        == selection["productReleaseStatusCheckpoint"]["digest"]
        and attempt[
            "productReleaseStatusCheckpointAuthenticationEvidenceDigest"
        ]
        == selection[
            "productReleaseStatusCheckpointAuthenticationEvidence"
        ]["digest"]
        and attempt["productReleaseStatusRequestNonce"]
        == selection["productReleaseStatusRequestNonce"]
        and attempt["rendererReleaseStatusCheckpointDigest"]
        == selection["rendererReleaseStatusCheckpoint"]["digest"]
        and attempt[
            "rendererReleaseStatusCheckpointAuthenticationEvidenceDigest"
        ]
        == selection[
            "rendererReleaseStatusCheckpointAuthenticationEvidence"
        ]["digest"]
        and attempt["rendererReleaseStatusRequestNonce"]
        == selection["rendererReleaseStatusRequestNonce"]
        and attempt["portableDefinitionDigest"] == portable_definition_digest
        and attempt["inputTreeDigest"] == expected_input_tree_digest
        and attempt["framedRequestDigest"] == receipt["framedRequestDigest"]
        and attempt["contractBundleDigest"] == inputs["contractBundle"]["digest"]
        and attempt["sandboxProfileDigest"] == policies["mandatorySandbox"],
        "renderer_attempt_binding_mismatch",
        "T/L/manifest",
    )
    require(
        attempt_auth["evidenceDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.renderer-attempt-authentication-evidence-digest/1",
                "purpose": attempt_auth["purpose"],
                "attemptAuthorityDigest": attempt_auth["attemptAuthorityDigest"],
                "issuerIdentityDigest": attempt_auth["issuerIdentityDigest"],
                "signingResult": attempt_auth["signingResult"],
            }
        )
        and attempt_auth["attemptAuthorityDigest"] == attempt["authorityDigest"]
        and attempt_auth["issuerIdentityDigest"] == attempt["issuerIdentityDigest"],
        "renderer_attempt_authentication_mismatch",
        "T issuer proof",
    )
    validate_signing_result(
        attempt_auth["signingResult"],
        "renderer-attempt-v1",
        attempt["authorityDigest"],
        "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
        None,
        store,
        registry,
        schemas,
        operation_time=inputs["reproducibleEpoch"],
        expected_repository="registry.example/product/renderer-attempt-evidence",
    )
    receipt_equalities = {
        "attemptId": attempt["attemptId"],
        "attemptFencingToken": attempt["attemptFencingToken"],
        "attemptAuthorityDigest": attempt["authorityDigest"],
        "attemptAuthenticationEvidenceDigest": attempt_auth["evidenceDigest"],
        "selectionDigest": selection["selectionDigest"],
        "productReleaseDigest": selection["productRelease"]["digest"],
        "releaseQualificationDigest": selection["releaseQualification"]["digest"],
        "productReleaseStatusDigest": selection["productReleaseStatus"]["digest"],
        "rendererReleaseStatusDigest": selection["rendererReleaseStatus"]["digest"],
        "rendererReleaseDigest": selection["rendererRelease"]["digest"],
        "platform": selection["targetPlatform"],
        "executedDistribution": selection["executableDistribution"],
        "productDistributionDigest": selection["productDistributionDigest"],
        "compiledAllowlistDigest": selection["compiledAllowlistDigest"],
        "inputTreeDigest": attempt["inputTreeDigest"],
        "contractBundleDigest": attempt["contractBundleDigest"],
        "outputTreeDigest": deployment["effectiveRender"]["manifest"]["output"][
            "treeDigest"
        ],
        "outputArchiveDigest": deployment["effectiveRender"]["manifest"]["output"][
            "digest"
        ],
        "outputArchiveSize": deployment["effectiveRender"]["manifest"]["output"][
            "size"
        ],
        "renderManifestDigest": canonical_digest(
            deployment["effectiveRender"]["manifest"]
        ),
        "sandboxProfileDigest": attempt["sandboxProfileDigest"],
        "workerProfileDigest": selection["workerProfileDigest"],
    }
    for field, expected in receipt_equalities.items():
        require(
            receipt[field] == expected,
            "renderer_receipt_binding_mismatch",
            field,
        )
    response_frame_bytes = store.resolve_digest(receipt["framedResponseDigest"])
    require(
        parse_framed_jcs(response_frame_bytes, "renderer response frame")
        == fixture_generator.renderer_response_frame_document(attempt, manifest)
        and raw_digest(response_frame_bytes) == receipt["framedResponseDigest"],
        "renderer_response_frame_binding_mismatch",
        attempt["attemptId"],
    )
    receipt_digest = canonical_digest(receipt)
    require(
        execution_auth["evidenceDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.renderer-execution-authentication-evidence-digest/1",
                "purpose": execution_auth["purpose"],
                "receiptDigest": execution_auth["receiptDigest"],
                "attemptAuthorityDigest": execution_auth["attemptAuthorityDigest"],
                "rendererSelectionDigest": execution_auth[
                    "rendererSelectionDigest"
                ],
                "launcherIdentityDigest": execution_auth["launcherIdentityDigest"],
                "signingResult": execution_auth["signingResult"],
            }
        )
        and execution_auth["receiptDigest"] == receipt_digest
        and execution_auth["attemptAuthorityDigest"] == attempt["authorityDigest"]
        and execution_auth["rendererSelectionDigest"]
        == selection["selectionDigest"]
        and execution_auth["launcherIdentityDigest"]
        == receipt["launcherIdentityDigest"],
        "renderer_execution_authentication_mismatch",
        "receipt authentication",
    )
    validate_signing_result(
        execution_auth["signingResult"],
        "renderer-execution-v1",
        receipt_digest,
        "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
        None,
        store,
        registry,
        schemas,
        operation_time=inputs["reproducibleEpoch"],
        expected_repository="registry.example/product/renderer-execution-evidence",
    )
    expected_input_parameters = fixture_generator.input_parameters_preimage(
        resolved_binding, inputs
    )
    expected_harness_configuration = (
        fixture_generator.harness_configuration_preimage(resolved_binding, inputs)
    )
    expected_effective_input_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-effective-input/1",
            **{
                key: manifest[key]
                for key in (
                    "scope",
                    "source",
                    "sourceKind",
                    "agentSpecVersion",
                    "bindingDigest",
                    "customizationDigest",
                    "effectiveSkillSetDigest",
                    "harnessId",
                    "rendererId",
                    "rendererVersion",
                    "productRelease",
                    "rendererRelease",
                    "executedDistribution",
                    "platform",
                    "productDistributionDigest",
                    "compiledAllowlistDigest",
                    "rendererSchemas",
                    "inputParametersDigest",
                    "harnessConfigurationDigest",
                    "normalizationProfile",
                    "outputArchiveProfile",
                )
            },
        }
    )
    require(
        deployment["effectiveRender"]["manifestDigest"]
        == canonical_digest(manifest),
        "render_manifest_digest_mismatch",
        "embedded manifest",
    )
    require(
        manifest["scope"] == "private"
        and manifest["source"] == resolved_binding["source"]
        and manifest["sourceKind"] == resolved_binding["sourceKind"]
        and manifest["agentSpecVersion"] == resolved_binding["agentSpecVersion"]
        and manifest["bindingDigest"] == inputs["binding"]["digest"]
        and manifest["customizationDigest"] == inputs["customizationDigest"]
        and manifest["publicSkills"]
        == inputs["effectiveSkillSet"]["publicSkills"]
        and manifest["privateSkills"]
        == inputs["effectiveSkillSet"]["privateSkills"]
        and manifest["skillApprovals"] == deployment["skillApprovals"]
        and manifest["inputParametersDigest"]
        == canonical_digest(expected_input_parameters)
        and manifest["harnessConfigurationDigest"]
        == canonical_digest(expected_harness_configuration)
        and manifest["effectiveInputDigest"] == expected_effective_input_digest,
        "render_manifest_lock_mismatch",
        "private functional inputs",
    )
    top_lineage = {
        "productRelease": selection["productRelease"],
        "rendererRelease": selection["rendererRelease"],
        "executedDistribution": receipt["executedDistribution"],
        "productDistributionDigest": selection["productDistributionDigest"],
        "compiledAllowlistDigest": selection["compiledAllowlistDigest"],
    }
    for field, expected in top_lineage.items():
        require(
            deployment[field] == expected and manifest[field] == expected,
            "deployment_renderer_lineage_mismatch",
            field,
        )
    validate_payload(deployment["effectiveRender"]["payload"], manifest, store)


def validate_evidence(
    lock: dict[str, Any],
    deployment: dict[str, Any],
    evidence: dict[str, Any],
    store: ArtifactStore,
    expected_signers: dict[str, dict[str, Any]],
    product_release: dict[str, Any],
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    statement = evidence["statement"]
    require(
        evidence["statementDigest"]
        == canonical_digest(
            {"profile": "bytedesk.private-compilation-statement/1", "statement": statement}
        ),
        "compilation_statement_digest_mismatch",
        "CE.statement",
    )
    require(
        statement["compileRequestDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.private-compilation-request/1",
                "consumerId": statement["consumerId"],
                "idempotencyKey": statement["idempotencyKey"],
                "compilationInputDigest": statement["compilationInputDigest"],
            }
        ),
        "compile_request_digest_mismatch",
        "CE request preimage",
    )
    role_descriptor(
        statement["compilationInput"],
        fixture_generator.PRIVATE_INPUT_MEDIA_TYPE,
        "consumer-compilation-input-v1",
        "CE compilation input",
    )
    require(
        statement["compilationInput"] == deployment["compilationInput"]
        and json.loads(store.resolve(statement["compilationInput"])) == lock
        and statement["compilationInputDigest"] == lock["compilationInputDigest"],
        "compilation_evidence_lock_mismatch",
        "CE/L/D",
    )
    role_descriptor(
        statement["consumerDeployment"],
        fixture_generator.DEPLOYMENT_MEDIA_TYPE,
        "consumer-deployment-v1",
        "CE deployment",
    )
    require(
        json.loads(store.resolve(statement["consumerDeployment"])) == deployment,
        "compilation_evidence_deployment_mismatch",
        "CE/D bytes",
    )
    deployment_signing = statement["deploymentSigningResult"]
    validate_signing_result(
        deployment_signing,
        "consumer-deployment-v1",
        statement["consumerDeployment"]["digest"],
        fixture_generator.DEPLOYMENT_MEDIA_TYPE,
        deployment["consumerId"],
        store,
        registry,
        schemas,
        operation_time=deployment["reproducibleEpoch"],
        policy=deployment["trustPolicy"],
        expected_repository=statement["consumerDeployment"]["repository"],
    )
    require(
        {
            key: deployment_signing[key]
            for key in ("keyVersion", "publicKeyDigest", "trustPolicy")
        }
        == expected_signers["consumer-deployment-v1"],
        "deployment_signer_mismatch",
        "current consumer deployment signer",
    )
    execution = deployment["rendererExecution"]
    attempt = execution["attemptAuthority"]
    attempt_auth = execution["attemptAuthenticationEvidence"]
    receipt = execution["receipt"]
    execution_auth = execution["authenticationEvidence"]
    manifest = deployment["effectiveRender"]["manifest"]
    bindings = {
        "consumerId": deployment["consumerId"],
        "subjectId": deployment["subjectId"],
        "installationId": deployment["installationId"],
        "harnessId": deployment["harnessId"],
        "targetId": deployment["targetId"],
        "outcome": "committed",
        "rendererSelectionDigest": deployment["rendererSelectionDigest"],
        "releaseStatusEligibility": deployment[
            "releaseStatusEligibility"
        ],
        "releaseStatusEligibilityDigest": deployment[
            "releaseStatusEligibilityDigest"
        ],
        "releaseStatusEligibilityVerificationEvidenceDigest": deployment[
            "releaseStatusEligibilityVerificationEvidenceDigest"
        ],
        "trustPolicyPinSetDigest": deployment["trustPolicyPinSetDigest"],
        "trustPolicyPinSetProviderEvidenceDigest": deployment[
            "trustPolicyPinSetProviderEvidenceDigest"
        ],
        "rendererAttemptAuthorityDigest": attempt["authorityDigest"],
        "rendererAttemptAuthenticationEvidenceDigest": attempt_auth[
            "evidenceDigest"
        ],
        "rendererExecutionReceiptDigest": canonical_digest(receipt),
        "rendererExecutionAuthenticationEvidenceDigest": execution_auth[
            "evidenceDigest"
        ],
        "renderManifestDigest": canonical_digest(manifest),
        "renderPayload": deployment["effectiveRender"]["payload"],
        "rendererDistribution": receipt["executedDistribution"],
        "reproducibleEpoch": deployment["reproducibleEpoch"],
        "completedAt": deployment["reproducibleEpoch"],
    }
    for field, expected in bindings.items():
        require(
            statement[field] == expected,
            "compilation_evidence_binding_mismatch",
            field,
        )
    require(
        statement["compilerDistribution"] == product_release["productDistribution"],
        "compiler_distribution_mismatch",
        "actual compiler distribution",
    )
    require(
        statement["compilationSigningPolicy"]
        == evidence["signingResult"]["trustPolicy"],
        "compilation_signing_policy_mismatch",
        "statement/signing result",
    )
    validate_signing_result(
        evidence["signingResult"],
        "consumer-compilation-evidence-v1",
        evidence["statementDigest"],
        fixture_generator.COMPILATION_STATEMENT_MEDIA_TYPE,
        deployment["consumerId"],
        store,
        registry,
        schemas,
        operation_time=deployment["reproducibleEpoch"],
        policy=statement["compilationSigningPolicy"],
        expected_repository="registry.example/consumer/compilation-evidence",
    )
    require(
        {
            key: evidence["signingResult"][key]
            for key in ("keyVersion", "publicKeyDigest", "trustPolicy")
        }
        == expected_signers["consumer-compilation-evidence-v1"],
        "compiler_signer_mismatch",
        "current consumer compilation signer",
    )
    require(
        deployment_signing["keyVersion"] != evidence["signingResult"]["keyVersion"]
        and deployment_signing["publicKeyDigest"]
        != evidence["signingResult"]["publicKeyDigest"]
        and deployment_signing["trustPolicy"]
        != evidence["signingResult"]["trustPolicy"],
        "signer_purpose_separation_failed",
        "deployment/compilation evidence",
    )


def validate_runtime_release(
    deployment: dict[str, Any],
    evidence: dict[str, Any],
    runtime_release: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
) -> None:
    require(
        runtime_release["releaseDigest"]
        == canonical_digest(
            fixture_generator.runtime_release_statement_preimage(
                runtime_release
            )
        ),
        "runtime_release_digest_mismatch",
        runtime_release["releaseId"],
    )
    validate_signing_result(
        runtime_release["signingResult"],
        "consumer-runtime-release-v1",
        runtime_release["releaseDigest"],
        fixture_generator.RUNTIME_RELEASE_STATEMENT_MEDIA_TYPE,
        runtime_release["consumerId"],
        store,
        registry,
        schemas,
        operation_time=runtime_release["preparedAt"],
        policy=runtime_release["trustPolicy"],
        expected_repository="registry.example/consumer/runtime-releases",
    )
    entries = runtime_release["deployments"]
    subject_ids = [entry["subjectId"] for entry in entries]
    activation_constraints = runtime_release["activationConstraints"]
    require(
        len(entries) == 2
        and subject_ids
        == sorted(subject_ids, key=lambda value: value.encode("utf-8"))
        and len(subject_ids) == len(set(subject_ids))
        and len({entry["slotId"] for entry in entries}) == 1
        and len({entry["generation"] for entry in entries}) == 1,
        "runtime_release_deployment_set_invalid",
        "two-subject target-wide fixture",
    )
    require(
        activation_constraints["trustPolicy"] == deployment["trustPolicy"]
        and activation_constraints["authorityPolicyDigest"]
        == deployment["opaqueConsumerDigests"]["policy"]
        and activation_constraints["canaryPolicyDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.fixture-canary-policy/1",
                "consumerId": runtime_release["consumerId"],
            }
        )
        and activation_constraints["recoveryPolicyDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.fixture-recovery-policy/1",
                "consumerId": runtime_release["consumerId"],
            }
        ),
        "runtime_release_activation_constraints_mismatch",
        runtime_release["releaseId"],
    )
    for aggregate_entry in entries:
        aggregate_deployment = parse_json_bytes(
            store.resolve(aggregate_entry["deployment"]),
            f"runtime deployment {aggregate_entry['subjectId']}",
        )
        aggregate_evidence = parse_json_bytes(
            store.resolve(aggregate_entry["compilationEvidence"]),
            f"runtime compilation evidence {aggregate_entry['subjectId']}",
        )
        validate_schema_instance(
            aggregate_deployment, DEPLOYMENT_SCHEMA_ID, registry, schemas
        )
        validate_schema_instance(
            aggregate_evidence, EVIDENCE_SCHEMA_ID, registry, schemas
        )
        aggregate_statement = aggregate_evidence["statement"]
        require(
            aggregate_deployment["consumerId"]
            == runtime_release["consumerId"]
            and aggregate_deployment["subjectId"]
            == aggregate_entry["subjectId"]
            and aggregate_deployment["targetId"]
            == runtime_release["targetId"]
            and aggregate_deployment["runtimeSlot"]
            == {
                "slotId": aggregate_entry["slotId"],
                "generation": aggregate_entry["generation"],
            }
            and aggregate_statement["consumerId"]
            == runtime_release["consumerId"]
            and aggregate_statement["subjectId"]
            == aggregate_entry["subjectId"]
            and aggregate_statement["targetId"]
            == runtime_release["targetId"]
            and aggregate_statement["consumerDeployment"]
            == aggregate_entry["deployment"]
            and aggregate_statement["reproducibleEpoch"]
            == runtime_release["compilationEpoch"]
            and aggregate_evidence["statementDigest"]
            == canonical_digest(
                {
                    "profile": "bytedesk.private-compilation-statement/1",
                    "statement": aggregate_statement,
                }
            ),
            "runtime_compilation_evidence_mismatch",
            aggregate_entry["subjectId"],
        )
        validate_signing_result(
            aggregate_statement["deploymentSigningResult"],
            "consumer-deployment-v1",
            aggregate_entry["deployment"]["digest"],
            fixture_generator.DEPLOYMENT_MEDIA_TYPE,
            runtime_release["consumerId"],
            store,
            registry,
            schemas,
            operation_time=runtime_release["compilationEpoch"],
            policy=aggregate_deployment["trustPolicy"],
            expected_repository=aggregate_entry["deployment"][
                "repository"
            ],
        )
        validate_signing_result(
            aggregate_evidence["signingResult"],
            "consumer-compilation-evidence-v1",
            aggregate_evidence["statementDigest"],
            fixture_generator.COMPILATION_STATEMENT_MEDIA_TYPE,
            runtime_release["consumerId"],
            store,
            registry,
            schemas,
            operation_time=runtime_release["compilationEpoch"],
            policy=aggregate_statement["compilationSigningPolicy"],
            expected_repository=aggregate_entry["compilationEvidence"][
                "repository"
            ],
        )
    entry = entries[0]
    require(
        entry["deployment"] == evidence["statement"]["consumerDeployment"]
        and json.loads(store.resolve(entry["deployment"])) == deployment,
        "runtime_deployment_descriptor_mismatch",
        "runtime/D",
    )
    role_descriptor(
        entry["compilationEvidence"],
        fixture_generator.COMPILATION_EVIDENCE_MEDIA_TYPE,
        "consumer-compilation-evidence-v1",
        "runtime compilation evidence",
    )
    require(
        parse_json_bytes(
            store.resolve(entry["compilationEvidence"]),
            "runtime compilation evidence",
        )
        == evidence
        and evidence["statement"]["consumerDeployment"] == entry["deployment"]
        and evidence["statement"]["consumerId"] == runtime_release["consumerId"]
        and evidence["statement"]["subjectId"] == entry["subjectId"]
        and evidence["statement"]["targetId"] == runtime_release["targetId"]
        and evidence["statement"]["reproducibleEpoch"]
        == runtime_release["compilationEpoch"],
        "runtime_compilation_evidence_mismatch",
        "RR/CE/D",
    )
    expected = {
        "consumerId": deployment["consumerId"],
        "targetId": deployment["targetId"],
        "candidate": deployment["candidate"],
        "desiredRevision": deployment["desiredRevision"],
        "predecessor": deployment["predecessor"],
        "activationMode": deployment["activationMode"],
        "releaseStatusEligibility": deployment[
            "releaseStatusEligibility"
        ],
        "releaseStatusEligibilityDigest": deployment[
            "releaseStatusEligibilityDigest"
        ],
        "releaseStatusEligibilityVerificationEvidenceDigest": deployment[
            "releaseStatusEligibilityVerificationEvidenceDigest"
        ],
        "trustPolicyPinSetDigest": deployment["trustPolicyPinSetDigest"],
        "trustPolicyPinSetProviderEvidenceDigest": deployment[
            "trustPolicyPinSetProviderEvidenceDigest"
        ],
        "compilationEpoch": deployment["reproducibleEpoch"],
        "preparedAt": deployment["reproducibleEpoch"],
    }
    for field, value in expected.items():
        require(
            runtime_release[field] == value,
            "runtime_release_field_mismatch",
            field,
        )
    require(
        entry
        == {
            "subjectId": deployment["subjectId"],
            "deployment": evidence["statement"]["consumerDeployment"],
            "compilationEvidence": entry["compilationEvidence"],
            "slotId": deployment["runtimeSlot"]["slotId"],
            "generation": deployment["runtimeSlot"]["generation"],
        },
        "runtime_release_entry_mismatch",
        "subject/slot/generation",
    )


def validate_activation_subject_coverage(
    activation: dict[str, Any], deployable: list[dict[str, Any]]
) -> list[str]:
    subject_ids = [entry["subjectId"] for entry in deployable]
    require(
        subject_ids
        == sorted(subject_ids, key=lambda value: value.encode("utf-8"))
        and len(subject_ids) == len(set(subject_ids))
        and all(
            entry["slotId"] == activation["slotId"]
            and entry["generation"] == activation["nextSlotGeneration"]
            for entry in deployable
        )
        and activation["expectedActiveGeneration"]
        < activation["nextSlotGeneration"],
        "activation_target_slot_generation_mismatch",
        activation["targetId"],
    )
    for values in (
        activation["candidateReadyEvidence"],
        activation["authoritySnapshots"],
        activation["authorizationDecisionProofs"],
    ):
        require(
            [value["subjectId"] for value in values] == subject_ids,
            "activation_subject_evidence_coverage_mismatch",
            activation["targetId"],
        )
    return subject_ids


def validate_activation_authorization(
    activation: dict[str, Any],
    runtime_release: dict[str, Any],
    runtime_release_descriptor: dict[str, Any],
    selection: dict[str, Any],
    consumer_platform_bindings: list[dict[str, Any]],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    operation_time: str,
    host_eligibility_verification_evidence_digest: str,
) -> None:
    validate_schema_instance(
        activation, ACTIVATION_AUTHORIZATION_SCHEMA_ID, registry, schemas
    )
    authorized_at = activation["authorizedAt"]
    require(
        timestamp(authorized_at) <= timestamp(operation_time)
        < timestamp(activation["expiresAt"])
        and activation["runtimeRelease"] == runtime_release_descriptor
        and activation["consumerId"] == runtime_release["consumerId"]
        and activation["targetId"] == runtime_release["targetId"]
        and activation["activationMode"] == runtime_release["activationMode"]
        and activation["deployableGraph"] == runtime_release["deployments"]
        and activation["deployableGraphDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.activation-deployable-graph/1",
                "runtimeRelease": runtime_release_descriptor,
                "deployableGraph": runtime_release["deployments"],
            }
        ),
        "activation_deployable_graph_mismatch",
        activation["authorizationId"],
    )
    deployable = runtime_release["deployments"]
    subject_ids = validate_activation_subject_coverage(
        activation, deployable
    )
    platform_by_purpose = {
        binding["purpose"]: binding
        for binding in consumer_platform_bindings
    }
    require(
        set(platform_by_purpose)
        == {"host-technical-evidence-v1", "authorization-decision-v1"}
        and all(
            binding["verificationDecision"] == "trusted"
            and binding["trustPolicy"]
            == {
                "id": binding["purpose"],
                "digest": canonical_digest(binding["policyDocument"]),
            }
            and binding["policyDocument"]["authority"]
            == "consumer_platform"
            for binding in consumer_platform_bindings
        ),
        "consumer_platform_evidence_policy_binding_invalid",
        activation["consumerId"],
    )

    def validate_platform_result(
        *,
        entry: dict[str, Any],
        descriptor_field: str,
        policy: dict[str, str],
        verification_id: str,
        adapter_id: str,
    ) -> None:
        descriptor = entry[descriptor_field]
        adapter_evidence = {
            "profile": "bytedesk.consumer-platform-adapter-verification/1",
            "adapterId": adapter_id,
            "consumerId": activation["consumerId"],
            "subject": deepcopy(descriptor),
            "policy": deepcopy(policy),
            "operationTime": authorized_at,
            "decision": "permitted",
        }
        adapter_digest = canonical_digest(adapter_evidence)
        require(
            store.resolve_digest(adapter_digest)
            == canonical_bytes(adapter_evidence),
            "consumer_platform_adapter_evidence_missing",
            verification_id,
        )
        expected = permitted_verification_result(
            schema_descriptor=fixture_generator.schema_descriptor(
                "verification-result"
            ),
            verification_id=verification_id,
            subject=descriptor,
            policy=policy,
            evaluated_at=authorized_at,
            evidence_digests=[adapter_digest, policy["digest"]],
        )
        require_verification_result(
            entry["verificationEvidenceDigest"],
            expected,
            store,
            registry,
            schemas,
        )

    deployment_by_subject = {
        entry["subjectId"]: entry for entry in deployable
    }
    ready_by_subject = {
        entry["subjectId"]: entry
        for entry in activation["candidateReadyEvidence"]
    }
    authority_by_subject = {
        entry["subjectId"]: entry
        for entry in activation["authoritySnapshots"]
    }
    decision_by_subject = {
        entry["subjectId"]: entry
        for entry in activation["authorizationDecisionProofs"]
    }
    for subject_index, subject_id in enumerate(subject_ids, start=1):
        deployable_entry = deployment_by_subject[subject_id]
        ready_entry = ready_by_subject[subject_id]
        authority_entry = authority_by_subject[subject_id]
        decision_entry = decision_by_subject[subject_id]
        ready = parse_json_bytes(
            store.resolve(ready_entry["evidence"]),
            f"activation ready {subject_id}",
        )
        authority = parse_json_bytes(
            store.resolve(authority_entry["authority"]),
            f"activation authority {subject_id}",
        )
        decision = parse_json_bytes(
            store.resolve(decision_entry["proof"]),
            f"activation decision {subject_id}",
        )
        validate_schema_instance(
            ready, CANARY_EVIDENCE_SCHEMA_ID, registry, schemas
        )
        validate_schema_instance(
            authority, CONSUMER_AUTHORITY_SCHEMA_ID, registry, schemas
        )
        validate_schema_instance(
            decision,
            AUTHORIZATION_DECISION_PROOF_SCHEMA_ID,
            registry,
            schemas,
        )
        require(
            ready["actor"] == "host_reconciler"
            and ready["results"]["phase"] == "candidate_ready"
            and ready["consumerId"] == activation["consumerId"]
            and ready["subjectId"] == subject_id
            and ready["targetId"] == activation["targetId"]
            and ready["releaseDigest"] == runtime_release["releaseDigest"]
            and ready["deploymentDigest"]
            == deployable_entry["deployment"]["digest"]
            and ready["slotId"] == activation["slotId"]
            and ready["generation"] == activation["nextSlotGeneration"]
            and timestamp(ready["issuedAt"]) <= timestamp(authorized_at)
            < timestamp(ready["expiresAt"])
            and authority["operation"] == "activate"
            and authority["consumerId"] == activation["consumerId"]
            and authority["subjectId"] == subject_id
            and authority["targetId"] == activation["targetId"]
            and authority["decision"]["class"] == "permitted"
            and timestamp(authority["notBefore"]) <= timestamp(authorized_at)
            < timestamp(authority["expiresAt"])
            and decision["decision"]["class"] == "permitted"
            and decision["consumerId"] == activation["consumerId"]
            and decision["subjectId"] == subject_id
            and decision["targetId"] == activation["targetId"]
            and decision["releaseDigest"] == runtime_release["releaseDigest"]
            and decision["deploymentDigest"]
            == deployable_entry["deployment"]["digest"]
            and decision["transport"]["outcome"]
            == "successful_authorization_response"
            and decision["transport"]["authenticated"] is True
            and decision["transport"]["completed"] is True
            and decision["transport"]["parsed"] is True
            and timestamp(decision["issuedAt"]) <= timestamp(authorized_at)
            < timestamp(decision["expiresAt"])
            and timestamp(activation["expiresAt"])
            <= min(
                timestamp(ready["expiresAt"]),
                timestamp(authority["expiresAt"]),
                timestamp(decision["expiresAt"]),
            )
            and ready["nonce"] == authority["nonce"] == decision["nonce"]
            and activation["authorizationNonce"] != ready["nonce"],
            "activation_subject_evidence_mismatch",
            subject_id,
        )
        validate_platform_result(
            entry=ready_entry,
            descriptor_field="evidence",
            policy=ready["signerPolicy"],
            verification_id=(
                f"activation-candidate-ready-verification-{subject_index:02d}"
            ),
            adapter_id="consumer-host-evidence-adapter-v1",
        )
        validate_platform_result(
            entry=authority_entry,
            descriptor_field="authority",
            policy=authority["signerPolicy"],
            verification_id=(
                f"activation-consumer-authority-verification-{subject_index:02d}"
            ),
            adapter_id="consumer-authority-adapter-v1",
        )
        validate_platform_result(
            entry=decision_entry,
            descriptor_field="proof",
            policy=decision["signerPolicy"],
            verification_id=(
                f"activation-decision-proof-verification-{subject_index:02d}"
            ),
            adapter_id="consumer-authorization-adapter-v1",
        )
    eligibility = validate_release_status_eligibility(
        descriptor=activation["releaseEligibility"],
        expected_digest=activation["releaseEligibilityDigest"],
        expected_verification_digest=activation[
            "releaseEligibilityVerificationEvidenceDigest"
        ],
        expected_stage="activation",
        operation_time=authorized_at,
        consumer_id=activation["consumerId"],
        selection=selection,
        entry_prefix="activation",
        eligibility_verification_id="activation-eligibility-signature",
        store=store,
        registry=registry,
        schemas=schemas,
    )
    validate_host_use_time_release_status_eligibility(
        descriptor=activation["releaseEligibility"],
        eligibility=eligibility,
        expected_verification_digest=(
            host_eligibility_verification_evidence_digest
        ),
        historical_verification_digest=activation[
            "releaseEligibilityVerificationEvidenceDigest"
        ],
        operation_time=operation_time,
        consumer_id=activation["consumerId"],
        selection=selection,
        store=store,
        registry=registry,
        schemas=schemas,
    )
    provider_binding, _ = store.trust_policy_provider_binding(
        activation["consumerId"]
    )
    eligibility_checkpoint_expiries = [
        parse_json_bytes(
            store.resolve(entry["checkpoint"]),
            "activation eligibility checkpoint expiry",
        )["expiresAt"]
        for entry in [eligibility["product"], *eligibility["renderers"]]
    ]
    require(
        activation["trustPolicyPinSetDigest"]
        == eligibility["pinSetDigest"]
        == provider_binding["pinSet"]["pinSetDigest"]
        and activation["trustPolicyPinSetProviderEvidenceDigest"]
        == eligibility["pinSetProviderEvidence"]["evidenceDigest"],
        "activation_pin_provider_evidence_mismatch",
        activation["authorizationId"],
    )
    activation_policy = validate_trust_policy_ref(
        activation["trustPolicy"],
        "consumer-activation-authorization-v1",
        activation["consumerId"],
        store,
        registry,
        schemas,
        authorized_at,
    )
    require(
        timestamp(activation["authorizedAt"])
        < timestamp(activation["expiresAt"])
        <= min(
            *(
                timestamp(value)
                for value in eligibility_checkpoint_expiries
            ),
            timestamp(
                provider_binding["pinSet"]["effective"]["notAfter"]
            ),
            timestamp(activation_policy["effective"]["notAfter"]),
        ),
        "activation_authorization_expiry_exceeds_evidence",
        activation["authorizationId"],
    )
    digest_authority = schemas[ACTIVATION_AUTHORIZATION_SCHEMA_ID][
        "x-bytedesk-digestAuthority"
    ]
    require(
        activation["authorizationDigest"]
        == canonical_digest(
            {
                "profile": digest_authority["profile"],
                **{
                    field: deepcopy(value)
                    for field, value in activation.items()
                    if field not in digest_authority["exclude"]
                },
            }
        ),
        "activation_authorization_digest_mismatch",
        activation["authorizationId"],
    )
    validate_signing_result(
        activation["signingResult"],
        "consumer-activation-authorization-v1",
        activation["authorizationDigest"],
        fixture_generator.ACTIVATION_AUTHORIZATION_STATEMENT_MEDIA_TYPE,
        activation["consumerId"],
        store,
        registry,
        schemas,
        operation_time=operation_time,
        policy=activation["trustPolicy"],
        expected_repository=(
            "registry.example/consumer/activation-authorizations"
        ),
    )


def validate_graph(
    lock: dict[str, Any],
    deployment: dict[str, Any],
    evidence: dict[str, Any],
    runtime_release: dict[str, Any],
    store: ArtifactStore,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    expected_signers: dict[str, dict[str, Any]],
    product_release: dict[str, Any],
    activation_authorization: dict[str, Any] | None = None,
    runtime_release_descriptor: dict[str, Any] | None = None,
    consumer_platform_bindings: list[dict[str, Any]] | None = None,
    host_operation_time: str | None = None,
    host_eligibility_verification_evidence_digest: str | None = None,
) -> None:
    validate_schema_instance(lock, PRIVATE_INPUT_SCHEMA_ID, registry, schemas)
    validate_schema_instance(deployment, DEPLOYMENT_SCHEMA_ID, registry, schemas)
    validate_schema_instance(evidence, EVIDENCE_SCHEMA_ID, registry, schemas)
    validate_schema_instance(
        runtime_release, RUNTIME_RELEASE_SCHEMA_ID, registry, schemas
    )
    roots = [lock, deployment, evidence, runtime_release]
    if activation_authorization is not None:
        roots.append(activation_authorization)
    reject_sentinel_digests(roots)
    validate_reachable_artifacts(
        [lock, deployment, evidence, runtime_release],
        store,
        registry,
        schemas,
        lock["inputs"]["reproducibleEpoch"],
    )
    validate_lock(lock, store, registry, schemas, product_release)
    validate_deployment(lock, deployment, store, registry, schemas)
    validate_evidence(
        lock,
        deployment,
        evidence,
        store,
        expected_signers,
        product_release,
        registry,
        schemas,
    )
    validate_runtime_release(
        deployment, evidence, runtime_release, store, registry, schemas
    )
    if activation_authorization is not None:
        require(
            runtime_release_descriptor is not None
            and consumer_platform_bindings is not None
            and host_operation_time is not None
            and host_eligibility_verification_evidence_digest is not None,
            "activation_validation_context_missing",
            activation_authorization["authorizationId"],
        )
        validate_activation_authorization(
            activation_authorization,
            runtime_release,
            runtime_release_descriptor,
            lock["inputs"]["rendererSelection"],
            consumer_platform_bindings,
            store,
            registry,
            schemas,
            host_operation_time,
            host_eligibility_verification_evidence_digest,
        )


def set_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    segments = pointer.removeprefix("/").split("/")
    target: Any = document
    for segment in segments[:-1]:
        target = target[int(segment)] if isinstance(target, list) else target[segment]
    leaf = segments[-1]
    if isinstance(target, list):
        target[int(leaf)] = value
    else:
        target[leaf] = value


def changed_value(value: Any) -> Any:
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str) and value.startswith("sha256:"):
        return f"sha256:{'f' * 64}"
    if isinstance(value, str):
        if value == "isolated_candidate":
            return "guarded_in_place"
        if value.endswith("Z") and "T" in value:
            return "2026-07-17T12:00:01Z"
        return f"{value}-substituted"
    if isinstance(value, dict) and "digest" in value:
        changed = deepcopy(value)
        changed["digest"] = f"sha256:{'f' * 64}"
        return changed
    raise GraphError("unsupported_mutation", type(value).__name__)


def get_pointer(document: dict[str, Any], pointer: str) -> Any:
    value: Any = document
    for segment in pointer.removeprefix("/").split("/"):
        value = value[int(segment)] if isinstance(value, list) else value[segment]
    return value


def replace_descriptor_bytes(
    descriptor: dict[str, Any], value: dict[str, Any]
) -> dict[str, Any]:
    result = deepcopy(descriptor)
    payload = canonical_bytes(value)
    result["digest"] = raw_digest(payload)
    result["size"] = len(payload)
    return result


def resign_with_authenticated_signer_mutation(
    signing_result: dict[str, Any],
    base_store: ArtifactStore,
    mutate_signer: Callable[[dict[str, Any]], None],
    *,
    public_key_digest: str | None = None,
) -> tuple[dict[str, Any], ArtifactStore]:
    """Produce a cryptographically coherent but policy-invalid fixture result."""
    result = deepcopy(signing_result)
    store = base_store.clone()
    provider_descriptor = result["providerAuditEvidence"]
    provider_evidence = parse_json_bytes(
        store.resolve(provider_descriptor),
        "signer mutation provider evidence",
    )
    bundle_descriptor = result["signatureBundle"]
    bundle = parse_json_bytes(
        store.resolve(bundle_descriptor),
        "signer mutation signature bundle",
    )
    authenticated_signer = deepcopy(provider_evidence["authenticatedSigner"])
    mutate_signer(authenticated_signer)

    if public_key_digest is not None:
        authenticated_signer["publicKeyDigest"] = public_key_digest
        result["publicKeyDigest"] = public_key_digest
        provider_evidence["publicKeyDigest"] = public_key_digest
        bundle["statement"]["publicKeyDigest"] = public_key_digest
        request_digest = canonical_digest(
            {
                "profile": "bytedesk.fixture-signing-request/1",
                "requestId": result["requestId"],
                "purpose": result["purpose"],
                "consumerId": result.get("consumerId"),
                "subjectDigest": result["subjectDigest"],
                "subjectMediaType": result["subjectMediaType"],
                "algorithm": result["algorithm"],
                "keyVersion": result["keyVersion"],
                "publicKeyDigest": result["publicKeyDigest"],
                "repository": result["repository"],
                "trustPolicy": result["trustPolicy"],
            }
        )
        result["requestDigest"] = request_digest
        provider_evidence["requestDigest"] = request_digest
        bundle["statement"]["requestDigest"] = request_digest

    provider_evidence["authenticatedSigner"] = deepcopy(authenticated_signer)
    provider_descriptor = replace_descriptor_bytes(
        provider_descriptor, provider_evidence
    )
    result["providerAuditEvidence"] = provider_descriptor
    bundle["statement"]["providerAuditEvidence"] = deepcopy(
        provider_descriptor
    )
    bundle["statement"]["authenticatedSigner"] = deepcopy(
        authenticated_signer
    )
    bundle["fixtureStatementChecksum"] = canonical_digest(
        {
            "profile": "bytedesk.test-only-kms-statement-checksum/1",
            "statement": bundle["statement"],
        }
    )
    bundle_descriptor = replace_descriptor_bytes(bundle_descriptor, bundle)
    result["signatureBundle"] = bundle_descriptor
    store.register(provider_descriptor, canonical_bytes(provider_evidence))
    store.register(bundle_descriptor, canonical_bytes(bundle))
    return result, store


def forge_with_legitimate_current_key_identity(
    signing_result: dict[str, Any],
    base_store: ArtifactStore,
    forged_subject_digest: str,
) -> tuple[dict[str, Any], ArtifactStore]:
    """Forge coherent fixture JSON while retaining the current permitted key.

    This deliberately cannot add an external trusted-KMS verification vector.
    It proves that a matching key identity, provider-shaped JSON, and a
    recomputed fixture checksum are not cryptographic verification.
    """

    result = deepcopy(signing_result)
    store = base_store.clone()
    original_provider = parse_json_bytes(
        store.resolve(result["providerAuditEvidence"]),
        "legitimate-key forgery provider evidence",
    )
    signer = deepcopy(original_provider["authenticatedSigner"])
    # Preserve the permitted key/workload identity while creating a genuinely
    # new signing operation for which the trusted adapter has no verification
    # vector.  Rebuilding the exact same request would be a replay, not a
    # cryptographic forgery.
    result["requestId"] = result["requestId"] + "-forged"
    result["subjectDigest"] = forged_subject_digest
    result["requestDigest"] = canonical_digest(
        {
            "profile": "bytedesk.fixture-signing-request/1",
            "requestId": result["requestId"],
            "purpose": result["purpose"],
            "consumerId": result.get("consumerId"),
            "subjectDigest": result["subjectDigest"],
            "subjectMediaType": result["subjectMediaType"],
            "algorithm": result["algorithm"],
            "keyVersion": result["keyVersion"],
            "publicKeyDigest": result["publicKeyDigest"],
            "repository": result["repository"],
            "trustPolicy": result["trustPolicy"],
        }
    )
    provider_evidence = build_signer_authentication_evidence(
        schema_descriptor=fixture_generator.schema_descriptor(
            "signer-authentication-evidence"
        ),
        purpose=result["purpose"],
        subject_media_type=result["subjectMediaType"],
        request_id=result["requestId"],
        request_digest=result["requestDigest"],
        provider_request_id=f"fixture-kms-request:{result['requestId']}",
        provider_audit_id=f"fixture-kms-audit:{result['requestId']}",
        authenticated_signer=signer,
        issued_at=result["signedAt"],
        trust_policy=result["trustPolicy"],
    )
    provider_descriptor = replace_descriptor_bytes(
        result["providerAuditEvidence"], provider_evidence
    )
    result["providerAuditEvidence"] = provider_descriptor
    statement = {
        "profile": "bytedesk.fixture-authenticated-signature-statement/1",
        "requestId": result["requestId"],
        "requestDigest": result["requestDigest"],
        "purpose": result["purpose"],
        "consumerId": result.get("consumerId"),
        "subjectDigest": result["subjectDigest"],
        "subjectMediaType": result["subjectMediaType"],
        "algorithm": result["algorithm"],
        "keyVersion": result["keyVersion"],
        "publicKeyDigest": result["publicKeyDigest"],
        "repository": result["repository"],
        "trustPolicy": deepcopy(result["trustPolicy"]),
        "providerAuditEvidence": deepcopy(provider_descriptor),
        "authenticatedSigner": signer,
        "signedAt": result["signedAt"],
    }
    bundle = {
        "profile": "bytedesk.test-only-kms-adapter-bundle/1",
        "statement": statement,
        "fixtureStatementChecksum": canonical_digest(
            {
                "profile": "bytedesk.test-only-kms-statement-checksum/1",
                "statement": statement,
            }
        ),
    }
    bundle_descriptor = replace_descriptor_bytes(
        result["signatureBundle"], bundle
    )
    result["signatureBundle"] = bundle_descriptor
    store.register(provider_descriptor, canonical_bytes(provider_evidence))
    store.register(bundle_descriptor, canonical_bytes(bundle))
    return result, store


def resign_with_attacker_policy(
    signing_result: dict[str, Any], base_store: ArtifactStore
) -> tuple[dict[str, Any], ArtifactStore]:
    """Re-sign one complete proof closure under a valid but unpinned policy."""
    result = deepcopy(signing_result)
    store = base_store.clone()
    policy = parse_json_bytes(
        store.resolve_digest(result["trustPolicy"]["digest"]),
        "baseline policy for coherent attacker",
    )
    attacker_signer = deepcopy(policy["signers"][0])
    attacker_signer["keyVersion"] = result["keyVersion"] + "/attacker"
    attacker_signer["publicKeyDigest"] = canonical_digest(
        {"profile": "bytedesk.fixture-attacker-policy-key/1"}
    )
    attacker_signer["workloadIdentity"] = (
        "spiffe://attacker.example/agent-delivery/" + result["purpose"]
    )
    attacker_signer["claims"]["subject"] = attacker_signer[
        "workloadIdentity"
    ]
    if "repository" in attacker_signer["claims"]:
        attacker_signer["claims"]["repository"] = "Attacker/example"
        attacker_signer["claims"]["workflow"] = (
            ".github/workflows/attacker.yml"
        )
        attacker_signer["claims"]["ref"] = "refs/tags/attacker"
        attacker_signer["claims"]["environment"] = "attacker"
    policy["signers"] = [attacker_signer]
    policy_ref = {
        "id": policy["policyId"],
        "digest": canonical_digest(policy),
    }
    store.register_digest(policy_ref["digest"], canonical_bytes(policy))

    result["keyVersion"] = attacker_signer["keyVersion"]
    result["publicKeyDigest"] = attacker_signer["publicKeyDigest"]
    result["trustPolicy"] = deepcopy(policy_ref)
    request_digest = canonical_digest(
        {
            "profile": "bytedesk.fixture-signing-request/1",
            "requestId": result["requestId"],
            "purpose": result["purpose"],
            "consumerId": result.get("consumerId"),
            "subjectDigest": result["subjectDigest"],
            "subjectMediaType": result["subjectMediaType"],
            "algorithm": result["algorithm"],
            "keyVersion": result["keyVersion"],
            "publicKeyDigest": result["publicKeyDigest"],
            "repository": result["repository"],
            "trustPolicy": result["trustPolicy"],
        }
    )
    result["requestDigest"] = request_digest
    provider_evidence = build_signer_authentication_evidence(
        schema_descriptor=fixture_generator.schema_descriptor(
            "signer-authentication-evidence"
        ),
        purpose=result["purpose"],
        subject_media_type=result["subjectMediaType"],
        request_id=result["requestId"],
        request_digest=request_digest,
        provider_request_id=f"fixture-kms-request:{result['requestId']}",
        provider_audit_id=f"fixture-kms-audit:{result['requestId']}",
        authenticated_signer=attacker_signer,
        issued_at=result["signedAt"],
        trust_policy=policy_ref,
    )
    provider_descriptor = deepcopy(result["providerAuditEvidence"])
    provider_descriptor["trustPolicy"] = deepcopy(policy_ref)
    provider_descriptor = replace_descriptor_bytes(
        provider_descriptor, provider_evidence
    )
    result["providerAuditEvidence"] = provider_descriptor

    bundle_descriptor = result["signatureBundle"]
    bundle = parse_json_bytes(
        store.resolve(bundle_descriptor),
        "baseline bundle for coherent attacker",
    )
    statement = bundle["statement"]
    statement["requestDigest"] = request_digest
    statement["keyVersion"] = result["keyVersion"]
    statement["publicKeyDigest"] = result["publicKeyDigest"]
    statement["trustPolicy"] = deepcopy(policy_ref)
    statement["providerAuditEvidence"] = deepcopy(provider_descriptor)
    statement["authenticatedSigner"] = deepcopy(attacker_signer)
    bundle["fixtureStatementChecksum"] = canonical_digest(
        {
            "profile": "bytedesk.test-only-kms-statement-checksum/1",
            "statement": statement,
        }
    )
    bundle_descriptor["trustPolicy"] = deepcopy(policy_ref)
    bundle_descriptor = replace_descriptor_bytes(bundle_descriptor, bundle)
    result["signatureBundle"] = bundle_descriptor
    store.register(provider_descriptor, canonical_bytes(provider_evidence))
    store.register(bundle_descriptor, canonical_bytes(bundle))
    return result, store


def refresh_evidence_envelope(evidence: dict[str, Any]) -> None:
    evidence["statementDigest"] = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-statement/1",
            "statement": evidence["statement"],
        }
    )
    evidence["signingResult"]["subjectDigest"] = evidence["statementDigest"]


def mutation_store(
    base: ArtifactStore,
    lock: dict[str, Any],
    deployment: dict[str, Any],
    evidence: dict[str, Any],
    payload: bytes,
) -> ArtifactStore:
    store = base.clone()
    store.register(deployment["compilationInput"], canonical_bytes(lock))
    store.register(deployment["effectiveRender"]["payload"], payload)
    store.register(evidence["statement"]["consumerDeployment"], canonical_bytes(deployment))
    return store


def cascaded_lock_replay(
    base: ArtifactStore,
    lock: dict[str, Any],
    deployment: dict[str, Any],
    evidence: dict[str, Any],
    runtime_release: dict[str, Any],
    payload: bytes,
    mutate: Callable[[dict[str, Any]], None],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    ArtifactStore,
]:
    replay_lock = deepcopy(lock)
    mutate(replay_lock)
    inputs = replay_lock["inputs"]
    authorized_inputs = deepcopy(inputs)
    authorized_inputs.pop("inputAuthentication")
    authorized_inputs.pop("authoritySnapshot")
    authorized_inputs.pop("authorizedPrivateInputDigest")
    inputs["authorizedPrivateInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.authorized-private-compilation-input/1",
            "contract": replay_lock["contract"],
            "schema": replay_lock["schema"],
            "inputs": authorized_inputs,
        }
    )
    authority = parse_json_bytes(
        base.resolve(lock["inputs"]["authoritySnapshot"]), "baseline authority"
    )
    authority["authorizedPrivateInputDigest"] = inputs[
        "authorizedPrivateInputDigest"
    ]
    authority_descriptor = replace_descriptor_bytes(
        inputs["authoritySnapshot"], authority
    )
    inputs["authoritySnapshot"] = authority_descriptor
    replay_lock["compilationInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-input-digest/1",
            "contract": replay_lock["contract"],
            "schema": replay_lock["schema"],
            "inputs": inputs,
        }
    )
    lock_descriptor = replace_descriptor_bytes(
        deployment["compilationInput"], replay_lock
    )
    replay_deployment = deepcopy(deployment)
    replay_deployment["compilationAuthority"] = authority_descriptor
    replay_deployment["compilationInput"] = lock_descriptor
    replay_deployment["compilationInputDigest"] = replay_lock[
        "compilationInputDigest"
    ]
    replay_deployment["deploymentId"] = fixture_generator.deployment_id(
        replay_lock
    )
    deployment_descriptor = replace_descriptor_bytes(
        evidence["statement"]["consumerDeployment"], replay_deployment
    )
    replay_evidence = deepcopy(evidence)
    statement = replay_evidence["statement"]
    statement["compilationInput"] = lock_descriptor
    statement["compilationInputDigest"] = replay_lock["compilationInputDigest"]
    statement["compileRequestDigest"] = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-request/1",
            "consumerId": statement["consumerId"],
            "idempotencyKey": statement["idempotencyKey"],
            "compilationInputDigest": statement["compilationInputDigest"],
        }
    )
    statement["consumerDeployment"] = deployment_descriptor
    refresh_evidence_envelope(replay_evidence)
    replay_runtime = deepcopy(runtime_release)
    replay_runtime["deployments"][0]["deployment"] = deployment_descriptor
    dynamic_store = mutation_store(
        base,
        replay_lock,
        replay_deployment,
        replay_evidence,
        payload,
    )
    dynamic_store.register(authority_descriptor, canonical_bytes(authority))
    return (
        replay_lock,
        replay_deployment,
        replay_evidence,
        replay_runtime,
        dynamic_store,
    )


def refresh_mutated_lock_authority(
    base: ArtifactStore,
    baseline_lock: dict[str, Any],
    mutated_lock: dict[str, Any],
    authority_mutation: Callable[[dict[str, Any]], None] | None = None,
) -> ArtifactStore:
    inputs = mutated_lock["inputs"]
    authorized_inputs = deepcopy(inputs)
    authorized_inputs.pop("inputAuthentication")
    authorized_inputs.pop("authoritySnapshot")
    authorized_inputs.pop("authorizedPrivateInputDigest")
    inputs["authorizedPrivateInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.authorized-private-compilation-input/1",
            "contract": mutated_lock["contract"],
            "schema": mutated_lock["schema"],
            "inputs": authorized_inputs,
        }
    )
    authority = parse_json_bytes(
        base.resolve(baseline_lock["inputs"]["authoritySnapshot"]),
        "baseline authority",
    )
    authority["authorizedPrivateInputDigest"] = inputs[
        "authorizedPrivateInputDigest"
    ]
    if authority_mutation is not None:
        authority_mutation(authority)
    authority_descriptor = replace_descriptor_bytes(
        baseline_lock["inputs"]["authoritySnapshot"], authority
    )
    inputs["authoritySnapshot"] = authority_descriptor
    mutated_lock["compilationInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-input-digest/1",
            "contract": mutated_lock["contract"],
            "schema": mutated_lock["schema"],
            "inputs": inputs,
        }
    )
    dynamic_store = base.clone()
    dynamic_store.register(authority_descriptor, canonical_bytes(authority))
    return dynamic_store


def expect_failure(case_id: str, operation: Callable[[], None]) -> dict[str, str]:
    try:
        operation()
    except GraphError as error:
        return {"id": case_id, "outcome": "denied", "reason": error.code}
    raise GraphError("mutation_accepted", case_id)


def validate_private_generator_contract_bundle_kms_denials() -> list[dict[str, str]]:
    """Deny keyless-only bundle media before policy or KMS signer selection."""

    results: list[dict[str, str]] = []

    def expect_denial(purpose: str, media_type: str, case_id: str) -> None:
        before_payloads = dict(fixture_generator.CAS_PAYLOADS)
        before_vectors = deepcopy(fixture_generator.SIGNATURE_VERIFICATION_VECTORS)
        try:
            fixture_generator.signing_result(
                purpose,
                "sha256:" + ("77" * 32),
                media_type,
                None,
                "registry.example/product/contracts",
                "2026-07-17T12:00:00Z",
                {},
                policy_ref={
                    "id": purpose,
                    "digest": "sha256:" + ("88" * 32),
                },
            )
        except fixture_generator.GenerationError as error:
            require(
                str(error) == "KMS signing cannot sign contract-bundle authority",
                "wrong_kms_contract_bundle_denial",
                f"private generator {purpose}:{media_type}: {error}",
            )
        else:
            raise GraphError(
                "kms_contract_bundle_accepted",
                f"private generator {purpose}:{media_type}",
            )
        require(
            fixture_generator.CAS_PAYLOADS == before_payloads
            and fixture_generator.SIGNATURE_VERIFICATION_VECTORS == before_vectors,
            "kms_contract_bundle_denial_had_side_effect",
            f"{purpose}:{media_type}",
        )
        results.append(
            {
                "id": case_id,
                "outcome": "denied",
                "reason": "kms_contract_bundle_keyless_only",
            }
        )

    for media_type in sorted(CONTRACT_BUNDLE_MEDIA_TYPES):
        expect_denial(
            "product-release-v1",
            media_type,
            (
                "private-generator-contract-bundle-"
                + media_type.rsplit("+", 1)[-1]
                + "-media-kms-denial"
            ),
        )
    expect_denial(
        CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "application/vnd.oci.image.manifest.v1+json",
        "private-generator-contract-bundle-purpose-kms-denial",
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    contract_bundle_kms_denials = (
        validate_private_generator_contract_bundle_kms_denials()
    )
    cases = load_json(CASE_PATH)
    positive = cases["positiveGraph"]
    lock = load_json(REPOSITORY_ROOT / positive["lockPath"])
    deployment = load_json(REPOSITORY_ROOT / positive["deploymentPath"])
    evidence = load_json(REPOSITORY_ROOT / positive["evidencePath"])
    runtime_release = load_json(REPOSITORY_ROOT / positive["runtimeReleasePath"])
    activation_authorization = load_json(
        REPOSITORY_ROOT / positive["activationAuthorizationPath"]
    )
    host_use_time_verification = cases[
        "activationHostUseTimeVerification"
    ]
    product_release = load_json(PRODUCT_RELEASE_PATH)
    registry, schemas = build_schema_registry()
    store = store_from_catalog(
        cases,
        registry,
        schemas,
        lock["inputs"]["reproducibleEpoch"],
    )
    validate_artifact_store_clone_isolation(store)
    expected_signers = {
        purpose: {
            key: result[key]
            for key in ("keyVersion", "publicKeyDigest", "trustPolicy")
        }
        for purpose, result in (
            (
                "consumer-deployment-v1",
                evidence["statement"]["deploymentSigningResult"],
            ),
            ("consumer-compilation-evidence-v1", evidence["signingResult"]),
        )
    }
    evidence_artifact = next(
        entry
        for entry in positive["artifacts"]
        if entry["role"] == "private-compilation-evidence"
    )
    role_descriptor(
        evidence_artifact["descriptor"],
        fixture_generator.COMPILATION_EVIDENCE_MEDIA_TYPE,
        "consumer-compilation-evidence-v1",
        "private compilation evidence",
    )
    require(
        parse_json_bytes(
            store.resolve(evidence_artifact["descriptor"]),
            "private compilation evidence",
        )
        == evidence,
        "compilation_evidence_descriptor_mismatch",
        "CE bytes",
    )
    runtime_release_artifact = next(
        entry
        for entry in positive["artifacts"]
        if entry["role"] == "runtime-release"
    )
    activation_artifact = next(
        entry
        for entry in positive["artifacts"]
        if entry["role"] == "activation-authorization"
    )
    require(
        parse_json_bytes(
            store.resolve(activation_artifact["descriptor"]),
            "activation authorization",
        )
        == activation_authorization,
        "activation_authorization_descriptor_mismatch",
        "activation bytes",
    )
    validate_graph(
        lock,
        deployment,
        evidence,
        runtime_release,
        store,
        registry,
        schemas,
        expected_signers,
        product_release,
        activation_authorization=activation_authorization,
        runtime_release_descriptor=runtime_release_artifact["descriptor"],
        consumer_platform_bindings=cases[
            "consumerPlatformEvidencePolicyBindings"
        ],
        host_operation_time=host_use_time_verification["operationTime"],
        host_eligibility_verification_evidence_digest=(
            host_use_time_verification["verificationEvidenceDigest"]
        ),
    )
    private_skill_descriptor = lock["inputs"]["effectiveSkillSet"][
        "privateSkills"
    ][0]
    separated_policy_refs = {
        "consumer-authority-v1": lock["inputs"]["authoritySnapshot"][
            "trustPolicy"
        ],
        "consumer-private-skill-v1": private_skill_descriptor["trustPolicy"],
        "consumer-compilation-input-v1": deployment["compilationInput"][
            "trustPolicy"
        ],
        "consumer-deployment-v1": evidence["statement"][
            "deploymentSigningResult"
        ]["trustPolicy"],
        "consumer-compilation-evidence-v1": evidence["signingResult"][
            "trustPolicy"
        ],
        "consumer-runtime-release-v1": runtime_release["signingResult"][
            "trustPolicy"
        ],
        "renderer-attempt-v1": deployment["rendererExecution"][
            "attemptAuthenticationEvidence"
        ]["signingResult"]["trustPolicy"],
        "renderer-execution-v1": deployment["rendererExecution"][
            "authenticationEvidence"
        ]["signingResult"]["trustPolicy"],
    }
    separated_policies = {
        purpose: validate_trust_policy_ref(
            policy_ref,
            purpose,
            "consumer-01" if purpose.startswith("consumer-") else None,
            store,
            registry,
            schemas,
            deployment["reproducibleEpoch"],
        )
        for purpose, policy_ref in separated_policy_refs.items()
    }
    validate_signer_purpose_separation(separated_policies)
    results: list[dict[str, str]] = [
        {"id": "positive-private-compilation-graph", "outcome": "permitted"},
        {"id": "artifact-store-clone-isolation", "outcome": "permitted"},
        {
            "id": "contract-bundle-keyless-verification-replayed",
            "outcome": "permitted",
        },
        *contract_bundle_kms_denials,
    ]
    missing_contract_bundle_verification = deepcopy(product_release)
    missing_contract_bundle_verification.pop("contractBundleVerification")
    results.append(
        expect_failure(
            "contract-bundle-keyless-verification-missing",
            lambda: validate_contract_bundle_keyless_verification(
                missing_contract_bundle_verification,
                store,
                registry,
                schemas,
                lock["inputs"]["reproducibleEpoch"],
            ),
        )
    )
    substituted_contract_bundle_verification = deepcopy(product_release)
    substituted_receipt = substituted_contract_bundle_verification[
        "contractBundleVerification"
    ]
    substituted_receipt["vectorId"] = canonical_digest(
        {"profile": "bytedesk.substituted-keyless-vector/1"}
    )
    substituted_receipt["verificationEvidenceDigest"] = canonical_digest(
        {
            "profile": KEYLESS_VERIFICATION_EVIDENCE_PROFILE,
            **{
                key: deepcopy(value)
                for key, value in substituted_receipt.items()
                if key != "verificationEvidenceDigest"
            },
        }
    )
    results.append(
        expect_failure(
            "contract-bundle-keyless-verification-substituted",
            lambda: validate_contract_bundle_keyless_verification(
                substituted_contract_bundle_verification,
                store,
                registry,
                schemas,
                lock["inputs"]["reproducibleEpoch"],
            ),
        )
    )
    payload = store.resolve(deployment["effectiveRender"]["payload"])

    compile_eligibility_descriptor = lock["inputs"][
        "releaseStatusEligibility"
    ]
    compile_eligibility = parse_json_bytes(
        store.resolve(compile_eligibility_descriptor),
        "private compilation eligibility",
    )
    eligibility_authority = schemas[STATUS_ELIGIBILITY_SCHEMA_ID][
        "x-bytedesk-digestAuthority"
    ]

    def refresh_eligibility_digest(value: dict[str, Any]) -> None:
        value["eligibilityDigest"] = canonical_digest(
            {
                "profile": eligibility_authority["profile"],
                **{
                    field: deepcopy(member)
                    for field, member in value.items()
                    if field not in eligibility_authority["exclude"]
                },
            }
        )

    def eligibility_mutation_store(
        value: dict[str, Any], base: ArtifactStore = store
    ) -> tuple[dict[str, Any], ArtifactStore]:
        descriptor = replace_descriptor_bytes(
            compile_eligibility_descriptor, value
        )
        dynamic_store = base.clone()
        dynamic_store.register(descriptor, canonical_bytes(value))
        return descriptor, dynamic_store

    missing_renderer_eligibility = deepcopy(compile_eligibility)
    missing_renderer_eligibility["renderers"] = []
    refresh_eligibility_digest(missing_renderer_eligibility)
    missing_renderer_descriptor, missing_renderer_store = (
        eligibility_mutation_store(missing_renderer_eligibility)
    )
    results.append(
        expect_failure(
            "release-status-eligibility-missing-renderer",
            lambda: validate_release_status_eligibility(
                descriptor=missing_renderer_descriptor,
                expected_digest=missing_renderer_eligibility[
                    "eligibilityDigest"
                ],
                expected_verification_digest=lock["inputs"][
                    "releaseStatusEligibilityVerificationEvidenceDigest"
                ],
                expected_stage="private_compilation",
                operation_time=lock["inputs"]["reproducibleEpoch"],
                consumer_id=lock["inputs"]["consumerId"],
                selection=lock["inputs"]["rendererSelection"],
                entry_prefix="private-compilation",
                eligibility_verification_id=(
                    "private-compilation-eligibility-signature"
                ),
                store=missing_renderer_store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    wrong_stage_eligibility = deepcopy(compile_eligibility)
    wrong_stage_eligibility["stage"] = "activation"
    refresh_eligibility_digest(wrong_stage_eligibility)
    wrong_stage_descriptor, wrong_stage_store = eligibility_mutation_store(
        wrong_stage_eligibility
    )
    results.append(
        expect_failure(
            "release-status-eligibility-wrong-stage",
            lambda: validate_release_status_eligibility(
                descriptor=wrong_stage_descriptor,
                expected_digest=wrong_stage_eligibility[
                    "eligibilityDigest"
                ],
                expected_verification_digest=lock["inputs"][
                    "releaseStatusEligibilityVerificationEvidenceDigest"
                ],
                expected_stage="private_compilation",
                operation_time=lock["inputs"]["reproducibleEpoch"],
                consumer_id=lock["inputs"]["consumerId"],
                selection=lock["inputs"]["rendererSelection"],
                entry_prefix="private-compilation",
                eligibility_verification_id=(
                    "private-compilation-eligibility-signature"
                ),
                store=wrong_stage_store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    pin_provider_substitution = deepcopy(compile_eligibility)
    pin_provider_substitution["pinSetProviderEvidence"]["readback"][
        "rawDigest"
    ] = canonical_digest(
        {"profile": "bytedesk.substituted-provider-readback/1"}
    )
    refresh_eligibility_digest(pin_provider_substitution)
    pin_provider_descriptor, pin_provider_store = eligibility_mutation_store(
        pin_provider_substitution
    )
    results.append(
        expect_failure(
            "release-status-eligibility-pin-provider-substitution",
            lambda: validate_release_status_eligibility(
                descriptor=pin_provider_descriptor,
                expected_digest=pin_provider_substitution[
                    "eligibilityDigest"
                ],
                expected_verification_digest=lock["inputs"][
                    "releaseStatusEligibilityVerificationEvidenceDigest"
                ],
                expected_stage="private_compilation",
                operation_time=lock["inputs"]["reproducibleEpoch"],
                consumer_id=lock["inputs"]["consumerId"],
                selection=lock["inputs"]["rendererSelection"],
                entry_prefix="private-compilation",
                eligibility_verification_id=(
                    "private-compilation-eligibility-signature"
                ),
                store=pin_provider_store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    compile_product_entry = compile_eligibility["product"]
    results.append(
        expect_failure(
            "release-status-eligibility-stale",
            lambda: validate_status_eligibility_entry(
                entry=compile_product_entry,
                entry_id="private-compilation-product",
                expected_kind="product_release",
                expected_subject=lock["inputs"]["rendererSelection"][
                    "productRelease"
                ],
                expected_status=lock["inputs"]["rendererSelection"][
                    "productReleaseStatus"
                ],
                operation_time="2026-07-17T12:05:05Z",
                store=store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    wrong_nonce_entry = deepcopy(compile_product_entry)
    wrong_nonce_entry["requestNonce"] = (
        "status_head_nonce_wrong_0123456789abcdef"
    )
    results.append(
        expect_failure(
            "release-status-eligibility-wrong-nonce",
            lambda: validate_status_eligibility_entry(
                entry=wrong_nonce_entry,
                entry_id="private-compilation-product",
                expected_kind="product_release",
                expected_subject=lock["inputs"]["rendererSelection"][
                    "productRelease"
                ],
                expected_status=lock["inputs"]["rendererSelection"][
                    "productReleaseStatus"
                ],
                operation_time=lock["inputs"]["reproducibleEpoch"],
                store=store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    subject_substitution_entry = deepcopy(compile_product_entry)
    subject_substitution_entry["subject"] = deepcopy(
        lock["inputs"]["rendererSelection"]["rendererRelease"]
    )
    results.append(
        expect_failure(
            "release-status-eligibility-subject-substitution",
            lambda: validate_status_eligibility_entry(
                entry=subject_substitution_entry,
                entry_id="private-compilation-product",
                expected_kind="product_release",
                expected_subject=lock["inputs"]["rendererSelection"][
                    "productRelease"
                ],
                expected_status=lock["inputs"]["rendererSelection"][
                    "productReleaseStatus"
                ],
                operation_time=lock["inputs"]["reproducibleEpoch"],
                store=store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    selection_reuse_entry = deepcopy(compile_product_entry)
    selection_checkpoint = parse_json_bytes(
        store.resolve(
            lock["inputs"]["rendererSelection"][
                "productReleaseStatusCheckpoint"
            ]
        ),
        "selection product checkpoint",
    )
    selection_reuse_entry.update(
        {
            "checkpoint": deepcopy(
                lock["inputs"]["rendererSelection"][
                    "productReleaseStatusCheckpoint"
                ]
            ),
            "checkpointAuthenticationEvidence": deepcopy(
                lock["inputs"]["rendererSelection"][
                    "productReleaseStatusCheckpointAuthenticationEvidence"
                ]
            ),
            "requestNonce": lock["inputs"]["rendererSelection"][
                "productReleaseStatusRequestNonce"
            ],
            "clientPriorState": deepcopy(
                selection_checkpoint["clientPriorState"]
            ),
            "headInclusionProof": deepcopy(
                selection_checkpoint["headInclusionProof"]
            ),
            "consistencyProof": deepcopy(
                selection_checkpoint["consistencyProof"]
            ),
        }
    )
    results.append(
        expect_failure(
            "release-status-eligibility-selection-only-reuse",
            lambda: validate_status_eligibility_entry(
                entry=selection_reuse_entry,
                entry_id="private-compilation-product",
                expected_kind="product_release",
                expected_subject=lock["inputs"]["rendererSelection"][
                    "productRelease"
                ],
                expected_status=lock["inputs"]["rendererSelection"][
                    "productReleaseStatus"
                ],
                operation_time=lock["inputs"]["reproducibleEpoch"],
                store=store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    withdrawn_status = parse_json_bytes(
        store.resolve(compile_product_entry["status"]),
        "withdrawn product status mutation",
    )
    withdrawn_status["status"] = "withdrawn"
    withdrawn_status["authorityDigest"] = canonical_digest(
        inline_authority_preimage(
            withdrawn_status, schemas[RELEASE_STATUS_SCHEMA_ID]
        )
    )
    withdrawn_status_descriptor = replace_descriptor_bytes(
        compile_product_entry["status"], withdrawn_status
    )
    withdrawn_store = store.clone()
    withdrawn_store.register(
        withdrawn_status_descriptor, canonical_bytes(withdrawn_status)
    )
    withdrawn_entry = deepcopy(compile_product_entry)
    withdrawn_entry["status"] = withdrawn_status_descriptor
    results.append(
        expect_failure(
            "release-status-eligibility-withdrawn",
            lambda: validate_status_eligibility_entry(
                entry=withdrawn_entry,
                entry_id="private-compilation-product",
                expected_kind="product_release",
                expected_subject=lock["inputs"]["rendererSelection"][
                    "productRelease"
                ],
                expected_status=withdrawn_status_descriptor,
                operation_time=lock["inputs"]["reproducibleEpoch"],
                store=withdrawn_store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )
    forged_eligibility_signing, forged_eligibility_store = (
        forge_with_legitimate_current_key_identity(
            compile_eligibility["signingResult"],
            store,
            compile_eligibility["eligibilityDigest"],
        )
    )
    forged_eligibility = deepcopy(compile_eligibility)
    forged_eligibility["signingResult"] = forged_eligibility_signing
    forged_eligibility_descriptor = replace_descriptor_bytes(
        compile_eligibility_descriptor, forged_eligibility
    )
    forged_eligibility_store.register(
        forged_eligibility_descriptor, canonical_bytes(forged_eligibility)
    )
    results.append(
        expect_failure(
            "release-status-eligibility-kms-forgery",
            lambda: validate_release_status_eligibility(
                descriptor=forged_eligibility_descriptor,
                expected_digest=compile_eligibility[
                    "eligibilityDigest"
                ],
                expected_verification_digest=lock["inputs"][
                    "releaseStatusEligibilityVerificationEvidenceDigest"
                ],
                expected_stage="private_compilation",
                operation_time=lock["inputs"]["reproducibleEpoch"],
                consumer_id=lock["inputs"]["consumerId"],
                selection=lock["inputs"]["rendererSelection"],
                entry_prefix="private-compilation",
                eligibility_verification_id=(
                    "private-compilation-eligibility-signature"
                ),
                store=forged_eligibility_store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )

    activation_eligibility_descriptor = activation_authorization[
        "releaseEligibility"
    ]
    activation_eligibility = parse_json_bytes(
        store.resolve(activation_eligibility_descriptor),
        "activation release eligibility",
    )
    activation_runtime_descriptor = runtime_release_artifact["descriptor"]
    activation_host_time = host_use_time_verification["operationTime"]
    activation_host_verification_digest = host_use_time_verification[
        "verificationEvidenceDigest"
    ]

    def validate_activation_candidate(
        candidate: dict[str, Any] = activation_authorization,
        release: dict[str, Any] = runtime_release,
        release_descriptor: dict[str, Any] = activation_runtime_descriptor,
        candidate_store: ArtifactStore = store,
        operation_time: str = activation_host_time,
        host_verification_digest: str = activation_host_verification_digest,
    ) -> None:
        validate_activation_authorization(
            candidate,
            release,
            release_descriptor,
            lock["inputs"]["rendererSelection"],
            cases["consumerPlatformEvidencePolicyBindings"],
            candidate_store,
            registry,
            schemas,
            operation_time,
            host_verification_digest,
        )

    require(
        len(runtime_release["deployments"]) == 2
        and len(activation_authorization["candidateReadyEvidence"]) == 2
        and len(activation_authorization["authoritySnapshots"]) == 2
        and len(
            activation_authorization["authorizationDecisionProofs"]
        )
        == 2,
        "two_subject_activation_fixture_missing",
        activation_authorization["authorizationId"],
    )
    results.append(
        {
            "id": "positive-two-subject-target-wide-activation",
            "outcome": "permitted",
        }
    )

    coverage_arrays = (
        ("candidate-ready", "candidateReadyEvidence"),
        ("authority", "authoritySnapshots"),
        ("decision", "authorizationDecisionProofs"),
    )
    coverage_case_ids: list[str] = []
    for label, field in coverage_arrays:
        missing = deepcopy(activation_authorization)
        missing[field].pop()
        case_id = f"activation-{label}-coverage-missing"
        coverage_case_ids.append(case_id)
        results.append(
            expect_failure(
                case_id,
                lambda value=missing: validate_activation_candidate(value),
            )
        )
        reordered = deepcopy(activation_authorization)
        reordered[field].reverse()
        case_id = f"activation-{label}-coverage-reordered"
        coverage_case_ids.append(case_id)
        results.append(
            expect_failure(
                case_id,
                lambda value=reordered: validate_activation_candidate(value),
            )
        )
        substituted = deepcopy(activation_authorization)
        substituted[field][1]["subjectId"] = substituted[field][0][
            "subjectId"
        ]
        case_id = f"activation-{label}-coverage-substituted"
        coverage_case_ids.append(case_id)
        results.append(
            expect_failure(
                case_id,
                lambda value=substituted: validate_activation_candidate(
                    value
                ),
            )
        )

    mixed_slot_release = deepcopy(runtime_release)
    mixed_slot_release["deployments"][1]["generation"] += 1
    mixed_slot_release_descriptor = replace_descriptor_bytes(
        activation_runtime_descriptor, mixed_slot_release
    )
    mixed_slot_store = store.clone()
    mixed_slot_store.register(
        mixed_slot_release_descriptor, canonical_bytes(mixed_slot_release)
    )
    mixed_slot_activation = deepcopy(activation_authorization)
    mixed_slot_activation["runtimeRelease"] = mixed_slot_release_descriptor
    mixed_slot_activation["deployableGraph"] = deepcopy(
        mixed_slot_release["deployments"]
    )
    mixed_slot_activation["deployableGraphDigest"] = canonical_digest(
        {
            "profile": "bytedesk.activation-deployable-graph/1",
            "runtimeRelease": mixed_slot_release_descriptor,
            "deployableGraph": mixed_slot_release["deployments"],
        }
    )
    results.append(
        expect_failure(
            "activation-mixed-slot-generation",
            lambda: validate_activation_candidate(
                mixed_slot_activation,
                mixed_slot_release,
                mixed_slot_release_descriptor,
                mixed_slot_store,
            ),
        )
    )

    graph_substitution = deepcopy(activation_authorization)
    graph_substitution["deployableGraph"][1]["deployment"] = deepcopy(
        graph_substitution["deployableGraph"][0]["deployment"]
    )
    graph_substitution["deployableGraphDigest"] = canonical_digest(
        {
            "profile": "bytedesk.activation-deployable-graph/1",
            "runtimeRelease": graph_substitution["runtimeRelease"],
            "deployableGraph": graph_substitution["deployableGraph"],
        }
    )
    results.append(
        expect_failure(
            "activation-deployable-graph-substitution",
            lambda: validate_activation_candidate(graph_substitution),
        )
    )

    digest_only_activation = deepcopy(activation_authorization)
    digest_only_activation["fencingToken"] += 1
    results.append(
        expect_failure(
            "activation-authorization-digest-only",
            lambda: validate_activation_candidate(digest_only_activation),
        )
    )
    results.append(
        expect_failure(
            "activation-authorization-expired-at-use",
            lambda: validate_activation_candidate(
                operation_time=activation_authorization["expiresAt"]
            ),
        )
    )
    forged_activation_signing, forged_activation_store = (
        forge_with_legitimate_current_key_identity(
            activation_authorization["signingResult"],
            store,
            activation_authorization["authorizationDigest"],
        )
    )
    forged_activation = deepcopy(activation_authorization)
    forged_activation["signingResult"] = forged_activation_signing
    results.append(
        expect_failure(
            "activation-authorization-kms-forgery",
            lambda: validate_activation_candidate(
                forged_activation,
                candidate_store=forged_activation_store,
            ),
        )
    )

    def activation_eligibility_mutation(
        value: dict[str, Any]
    ) -> tuple[dict[str, Any], ArtifactStore]:
        descriptor = replace_descriptor_bytes(
            activation_eligibility_descriptor, value
        )
        dynamic_store = store.clone()
        dynamic_store.register(descriptor, canonical_bytes(value))
        candidate = deepcopy(activation_authorization)
        candidate["releaseEligibility"] = descriptor
        candidate["releaseEligibilityDigest"] = value[
            "eligibilityDigest"
        ]
        return candidate, dynamic_store

    activation_missing_renderer_eligibility = deepcopy(
        activation_eligibility
    )
    activation_missing_renderer_eligibility["renderers"] = []
    refresh_eligibility_digest(activation_missing_renderer_eligibility)
    activation_missing_renderer, activation_missing_renderer_store = (
        activation_eligibility_mutation(
            activation_missing_renderer_eligibility
        )
    )
    results.append(
        expect_failure(
            "activation-eligibility-missing-renderer",
            lambda: validate_activation_candidate(
                activation_missing_renderer,
                candidate_store=activation_missing_renderer_store,
            ),
        )
    )
    activation_wrong_stage_eligibility = deepcopy(activation_eligibility)
    activation_wrong_stage_eligibility["stage"] = "private_compilation"
    refresh_eligibility_digest(activation_wrong_stage_eligibility)
    activation_wrong_stage, activation_wrong_stage_store = (
        activation_eligibility_mutation(activation_wrong_stage_eligibility)
    )
    results.append(
        expect_failure(
            "activation-eligibility-stale-or-wrong-stage",
            lambda: validate_activation_candidate(
                activation_wrong_stage,
                candidate_store=activation_wrong_stage_store,
            ),
        )
    )

    missing_historical_verification_store = store.clone()
    missing_historical_verification_store.remove_digest(
        activation_authorization[
            "releaseEligibilityVerificationEvidenceDigest"
        ]
    )
    results.append(
        expect_failure(
            "activation-eligibility-verification-result-missing",
            lambda: validate_activation_candidate(
                candidate_store=missing_historical_verification_store
            ),
        )
    )
    substituted_historical_verification = deepcopy(
        activation_authorization
    )
    substituted_historical_verification[
        "releaseEligibilityVerificationEvidenceDigest"
    ] = lock["inputs"][
        "releaseStatusEligibilityVerificationEvidenceDigest"
    ]
    results.append(
        expect_failure(
            "activation-eligibility-verification-result-substitution",
            lambda: validate_activation_candidate(
                substituted_historical_verification
            ),
        )
    )
    missing_host_verification_store = store.clone()
    missing_host_verification_store.remove_digest(
        activation_host_verification_digest
    )
    results.append(
        expect_failure(
            "activation-host-use-time-verification-missing",
            lambda: validate_activation_candidate(
                candidate_store=missing_host_verification_store
            ),
        )
    )
    results.append(
        expect_failure(
            "activation-host-use-time-verification-substitution",
            lambda: validate_activation_candidate(
                host_verification_digest=activation_authorization[
                    "releaseEligibilityVerificationEvidenceDigest"
                ]
            ),
        )
    )
    activation_product_checkpoint = parse_json_bytes(
        store.resolve(activation_eligibility["product"]["checkpoint"]),
        "activation product checkpoint boundary",
    )
    results.append(
        expect_failure(
            "activation-host-use-time-status-expired-boundary",
            lambda: validate_host_use_time_release_status_eligibility(
                descriptor=activation_eligibility_descriptor,
                eligibility=activation_eligibility,
                expected_verification_digest=(
                    activation_host_verification_digest
                ),
                historical_verification_digest=activation_authorization[
                    "releaseEligibilityVerificationEvidenceDigest"
                ],
                operation_time=activation_product_checkpoint["expiresAt"],
                consumer_id=activation_authorization["consumerId"],
                selection=lock["inputs"]["rendererSelection"],
                store=store,
                registry=registry,
                schemas=schemas,
            ),
        )
    )

    provider_binding_case_ids: list[str] = []

    def provider_catalog_denial(
        case_id: str,
        bindings: list[dict[str, Any]],
        vectors: list[dict[str, Any]],
    ) -> None:
        provider_binding_case_ids.append(case_id)
        results.append(
            expect_failure(
                case_id,
                lambda: validate_trust_policy_pin_sets(
                    bindings,
                    vectors,
                    lock["inputs"]["reproducibleEpoch"],
                    registry,
                    schemas,
                ),
            )
        )

    provider_bindings = cases["trustPolicyPinSetBindings"]
    provider_vectors = cases[
        "trustPolicyPinSetProviderAuthenticationVectors"
    ]
    descriptor_substitution_bindings = deepcopy(provider_bindings)
    descriptor_substitution_bindings[1]["pinSetDescriptor"][
        "digest"
    ] = f"sha256:{'f' * 64}"
    provider_catalog_denial(
        "trust-pin-provider-descriptor-substitution",
        descriptor_substitution_bindings,
        deepcopy(provider_vectors),
    )
    evidence_substitution_bindings = deepcopy(provider_bindings)
    evidence_substitution_bindings[1]["providerEvidence"][
        "providerAuditId"
    ] += "-substituted"
    provider_catalog_denial(
        "trust-pin-provider-evidence-substitution",
        evidence_substitution_bindings,
        deepcopy(provider_vectors),
    )
    readback_substitution_bindings = deepcopy(provider_bindings)
    readback_substitution_bindings[1]["providerEvidence"]["readback"][
        "rawDigest"
    ] = f"sha256:{'e' * 64}"
    provider_catalog_denial(
        "trust-pin-provider-readback-substitution",
        readback_substitution_bindings,
        deepcopy(provider_vectors),
    )
    missing_provider_vectors = [deepcopy(provider_vectors[0])]
    provider_catalog_denial(
        "trust-pin-provider-authentication-vector-missing",
        deepcopy(provider_bindings),
        missing_provider_vectors,
    )

    validate_signing_time(
        signed_at="2026-07-17T12:00:00Z",
        operation_time="2026-07-17T12:00:00Z",
        not_before="2026-07-17T12:00:00Z",
        not_after="2026-07-17T12:01:00Z",
        purpose="boundary-positive",
    )
    results.append(
        {
            "id": "positive-signing-policy-not-before-boundary",
            "outcome": "permitted",
        }
    )
    results.append(
        expect_failure(
            "signing-policy-not-after-boundary",
            lambda: validate_signing_time(
                signed_at="2026-07-17T12:01:00Z",
                operation_time="2026-07-17T12:01:00Z",
                not_before="2026-07-17T12:00:00Z",
                not_after="2026-07-17T12:01:00Z",
                purpose="boundary-not-after",
            ),
        )
    )
    results.append(
        expect_failure(
            "signing-time-future",
            lambda: validate_signing_time(
                signed_at="2026-07-17T12:00:01Z",
                operation_time="2026-07-17T12:00:00Z",
                not_before="2026-07-17T11:59:00Z",
                not_after="2026-07-17T12:02:00Z",
                purpose="future-signing-time",
            ),
        )
    )

    qualification_descriptor = lock["inputs"]["rendererSelection"][
        "releaseQualification"
    ]
    qualification_document = parse_json_bytes(
        store.resolve(qualification_descriptor), "release qualification"
    )
    qualification_role_substitution = deepcopy(qualification_descriptor)
    qualification_role_substitution["trustPolicy"] = deepcopy(
        qualification_document["evidence"][0]["trustPolicy"]
    )
    results.append(
        expect_failure(
            "qualification-decision-purpose-role-substitution",
            lambda: role_descriptor(
                qualification_role_substitution,
                "application/vnd.bytedesk.agent.release-qualification.v1+json",
                "release-qualification-decision-v1",
                "release qualification decision",
            ),
        )
    )
    status_checkpoint_role_substitution = deepcopy(
        lock["inputs"]["rendererSelection"][
            "productReleaseStatusCheckpoint"
        ]
    )
    status_checkpoint_role_substitution["trustPolicy"] = deepcopy(
        lock["inputs"]["rendererSelection"]["productReleaseStatus"][
            "trustPolicy"
        ]
    )
    results.append(
        expect_failure(
            "status-checkpoint-purpose-role-substitution",
            lambda: role_descriptor(
                status_checkpoint_role_substitution,
                "application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json",
                "release-status-head-v1",
                "product release status checkpoint",
            ),
        )
    )

    baseline_compilation_signing = evidence["signingResult"]
    forged_subject_digest = canonical_digest(
        {"profile": "bytedesk.forged-current-key-subject/1"}
    )
    forged_signing, forged_signing_store = (
        forge_with_legitimate_current_key_identity(
            baseline_compilation_signing,
            store,
            forged_subject_digest,
        )
    )
    forged_denial = expect_failure(
        "forged-under-legitimate-current-key",
        lambda: validate_signing_result(
            forged_signing,
            "consumer-compilation-evidence-v1",
            forged_subject_digest,
            fixture_generator.COMPILATION_STATEMENT_MEDIA_TYPE,
            deployment["consumerId"],
            forged_signing_store,
            registry,
            schemas,
            operation_time=deployment["reproducibleEpoch"],
            policy=evidence["statement"]["compilationSigningPolicy"],
            expected_repository=baseline_compilation_signing["repository"],
        ),
    )
    require(
        forged_denial["reason"] == "kms_signature_not_verified",
        "forged_current_key_wrong_denial",
        forged_denial["reason"],
    )
    results.append(forged_denial)
    signing_request_mutations: tuple[tuple[str, Any], ...] = (
        ("requestId", baseline_compilation_signing["requestId"] + "-replayed"),
        ("repository", "registry.example/consumer/other-evidence"),
        ("algorithm", "RSA_PSS_SHA256"),
        ("keyVersion", baseline_compilation_signing["keyVersion"] + "-other"),
        ("publicKeyDigest", canonical_digest({"profile": "wrong-public-key/1"})),
        (
            "trustPolicy",
            evidence["statement"]["deploymentSigningResult"]["trustPolicy"],
        ),
    )
    for field, substituted_value in signing_request_mutations:
        mutated_signing = deepcopy(baseline_compilation_signing)
        mutated_signing[field] = substituted_value
        results.append(
            expect_failure(
                f"signing-request-{field}-substitution",
                lambda value=mutated_signing: validate_signing_result(
                    value,
                    "consumer-compilation-evidence-v1",
                    evidence["statementDigest"],
                    fixture_generator.COMPILATION_STATEMENT_MEDIA_TYPE,
                    deployment["consumerId"],
                    store,
                    registry,
                    schemas,
                    operation_time=deployment["reproducibleEpoch"],
                    policy=evidence["statement"]["compilationSigningPolicy"],
                    expected_repository=baseline_compilation_signing[
                        "repository"
                    ],
                ),
            )
        )

    baseline_product_signing = deployment["rendererExecution"][
        "attemptAuthenticationEvidence"
    ]["signingResult"]
    product_signer_mutations: tuple[tuple[str, str, Any], ...] = (
        (
            "authenticated-signer-workload-substitution",
            "/workloadIdentity",
            "spiffe://attacker.example/agent-delivery/renderer-attempt",
        ),
        (
            "authenticated-signer-issuer-substitution",
            "/claims/issuer",
            "https://attacker.example/oidc",
        ),
        (
            "authenticated-signer-audience-substitution",
            "/claims/audience",
            "attacker-audience",
        ),
        (
            "authenticated-signer-subject-substitution",
            "/claims/subject",
            "repo:Attacker/example:environment:renderer-attempt-v1",
        ),
        (
            "authenticated-signer-repository-substitution",
            "/claims/repository",
            "Attacker/example",
        ),
        (
            "authenticated-signer-workflow-substitution",
            "/claims/workflow",
            ".github/workflows/attacker.yml",
        ),
        (
            "authenticated-signer-ref-substitution",
            "/claims/ref",
            "refs/heads/untrusted",
        ),
        (
            "authenticated-signer-environment-substitution",
            "/claims/environment",
            "untrusted",
        ),
        (
            "authenticated-signer-builder-substitution",
            "/claims/builderDigest",
            canonical_digest({"profile": "bytedesk.fixture-attacker-builder/1"}),
        ),
    )
    for case_id, pointer, substituted_value in product_signer_mutations:
        mutated_signing, mutated_store = (
            resign_with_authenticated_signer_mutation(
                baseline_product_signing,
                store,
                lambda signer, p=pointer, v=substituted_value: set_pointer(
                    signer, p, v
                ),
            )
        )
        results.append(
            expect_failure(
                case_id,
                lambda value=mutated_signing, s=mutated_store: validate_signing_result(
                    value,
                    "renderer-attempt-v1",
                    deployment["rendererExecution"]["attemptAuthority"][
                        "authorityDigest"
                    ],
                    "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
                    None,
                    s,
                    registry,
                    schemas,
                    operation_time=deployment["reproducibleEpoch"],
                    expected_repository=baseline_product_signing["repository"],
                ),
            )
        )

    coherent_wrong_key_signing, coherent_wrong_key_store = (
        resign_with_authenticated_signer_mutation(
            baseline_product_signing,
            store,
            lambda signer: None,
            public_key_digest=canonical_digest(
                {"profile": "bytedesk.fixture-attacker-public-key/1"}
            ),
        )
    )
    results.append(
        expect_failure(
            "authenticated-signer-public-key-substitution",
            lambda: validate_signing_result(
                coherent_wrong_key_signing,
                "renderer-attempt-v1",
                deployment["rendererExecution"]["attemptAuthority"][
                    "authorityDigest"
                ],
                "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
                None,
                coherent_wrong_key_store,
                registry,
                schemas,
                operation_time=deployment["reproducibleEpoch"],
                expected_repository=baseline_product_signing["repository"],
            ),
        )
    )

    attacker_policy_signing, attacker_policy_store = (
        resign_with_attacker_policy(baseline_compilation_signing, store)
    )
    results.append(
        expect_failure(
            "coherent-attacker-trust-policy-substitution",
            lambda: validate_signing_result(
                attacker_policy_signing,
                "consumer-compilation-evidence-v1",
                evidence["statementDigest"],
                fixture_generator.COMPILATION_STATEMENT_MEDIA_TYPE,
                deployment["consumerId"],
                attacker_policy_store,
                registry,
                schemas,
                operation_time=deployment["reproducibleEpoch"],
                expected_repository=baseline_compilation_signing["repository"],
            ),
        )
    )

    key_collision = deepcopy(separated_policies)
    key_collision["consumer-compilation-evidence-v1"]["signers"][0][
        "keyVersion"
    ] = key_collision["consumer-deployment-v1"]["signers"][0]["keyVersion"]
    results.append(
        expect_failure(
            "signer-purpose-key-collision",
            lambda: validate_signer_purpose_separation(key_collision),
        )
    )
    workload_collision = deepcopy(separated_policies)
    workload_collision["consumer-compilation-evidence-v1"]["signers"][0][
        "workloadIdentity"
    ] = workload_collision["consumer-deployment-v1"]["signers"][0][
        "workloadIdentity"
    ]
    results.append(
        expect_failure(
            "signer-purpose-workload-collision",
            lambda: validate_signer_purpose_separation(workload_collision),
        )
    )

    request_frame = fixture_generator.renderer_request_frame_document(
        lock["inputs"]["rendererSelection"],
        fixture_generator.renderer_portable_definition(
            deployment["effectiveRender"]["manifest"]
        ),
        deployment["rendererExecution"]["attemptAuthority"][
            "portableDefinitionDigest"
        ],
        fixture_generator.renderer_functional_inputs(
            deployment["effectiveRender"]["manifest"],
            parse_json_bytes(
                store.resolve(lock["inputs"]["binding"]),
                "frame mutation binding",
            ),
            lock["inputs"],
        ),
        deployment["rendererExecution"]["attemptAuthority"]["inputTreeDigest"],
        lock["inputs"]["contractBundle"]["digest"],
    )
    request_frame["contractBundleDigest"] = canonical_digest(
        {"profile": "substituted-contract-bundle/1"}
    )
    request_frame_bytes = fixture_generator.framed_jcs(request_frame)
    request_frame_digest = raw_digest(request_frame_bytes)
    request_frame_deployment = deepcopy(deployment)
    request_frame_deployment["rendererExecution"]["attemptAuthority"][
        "framedRequestDigest"
    ] = request_frame_digest
    request_frame_deployment["rendererExecution"]["receipt"][
        "framedRequestDigest"
    ] = request_frame_digest
    request_frame_store = store.clone()
    request_frame_store.register_digest(request_frame_digest, request_frame_bytes)
    results.append(
        expect_failure(
            "renderer-request-frame-byte-substitution",
            lambda: validate_deployment(
                lock,
                request_frame_deployment,
                request_frame_store,
                registry,
                schemas,
            ),
        )
    )

    response_frame = fixture_generator.renderer_response_frame_document(
        deployment["rendererExecution"]["attemptAuthority"],
        deployment["effectiveRender"]["manifest"],
    )
    response_frame["result"] = "denied"
    response_frame_bytes = fixture_generator.framed_jcs(response_frame)
    response_frame_digest = raw_digest(response_frame_bytes)
    response_frame_deployment = deepcopy(deployment)
    response_frame_deployment["rendererExecution"]["receipt"][
        "framedResponseDigest"
    ] = response_frame_digest
    response_frame_store = store.clone()
    response_frame_store.register_digest(
        response_frame_digest, response_frame_bytes
    )
    results.append(
        expect_failure(
            "renderer-response-frame-byte-substitution",
            lambda: validate_deployment(
                lock,
                response_frame_deployment,
                response_frame_store,
                registry,
                schemas,
            ),
        )
    )

    missing_authority_authentication = store.clone()
    missing_authority_authentication.remove_authentication(
        lock["inputs"]["authoritySnapshot"]["digest"]
    )
    results.append(
        expect_failure(
            "detached-authority-signature-missing",
            lambda: validate_graph(
                lock,
                deployment,
                evidence,
                runtime_release,
                missing_authority_authentication,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )
    authentication_bundle = parse_json_bytes(
        store.resolve(lock["inputs"]["inputAuthentication"]),
        "authentication substitution bundle",
    )
    private_skill_authentication = next(
        entry
        for entry in authentication_bundle["entries"]
        if entry["subject"]["digest"] == private_skill_descriptor["digest"]
    )
    cross_role_authentication = store.clone()
    cross_role_authentication.substitute_authentication_result(
        lock["inputs"]["authoritySnapshot"]["digest"],
        private_skill_authentication["signingResult"],
    )
    results.append(
        expect_failure(
            "detached-authority-signature-cross-role-substitution",
            lambda: validate_graph(
                lock,
                deployment,
                evidence,
                runtime_release,
                cross_role_authentication,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    deployment_without_lock_signing = deepcopy(deployment)
    deployment_without_lock_signing.pop("compilationInputSigningResult")
    results.append(
        expect_failure(
            "deployment-compilation-input-signing-result-missing",
            lambda: validate_schema_instance(
                deployment_without_lock_signing,
                DEPLOYMENT_SCHEMA_ID,
                registry,
                schemas,
            ),
        )
    )
    for field, value in (
        (
            "subjectDigest",
            canonical_digest({"profile": "substituted-compilation-input/1"}),
        ),
        ("repository", "registry.example/consumer/other-compilation-inputs"),
    ):
        mutated_deployment = deepcopy(deployment)
        mutated_deployment["compilationInputSigningResult"][field] = value
        results.append(
            expect_failure(
                f"compilation-input-signing-result-{field}-substitution",
                lambda candidate=mutated_deployment: validate_deployment(
                    lock,
                    candidate,
                    store,
                    registry,
                    schemas,
                ),
            )
        )
    lock_signing_bundle_descriptor = deployment[
        "compilationInputSigningResult"
    ]["signatureBundle"]
    lock_signing_bundle = parse_json_bytes(
        store.resolve(lock_signing_bundle_descriptor),
        "compilation input signing bundle",
    )
    lock_signing_bundle["statement"]["subjectDigest"] = canonical_digest(
        {"profile": "substituted-compilation-input-bundle-subject/1"}
    )
    lock_signing_bundle["fixtureStatementChecksum"] = canonical_digest(
        {
            "profile": "bytedesk.test-only-kms-statement-checksum/1",
            "statement": lock_signing_bundle["statement"],
        }
    )
    substituted_lock_bundle_descriptor = replace_descriptor_bytes(
        lock_signing_bundle_descriptor, lock_signing_bundle
    )
    lock_bundle_deployment = deepcopy(deployment)
    lock_bundle_deployment["compilationInputSigningResult"][
        "signatureBundle"
    ] = substituted_lock_bundle_descriptor
    lock_bundle_store = store.clone()
    lock_bundle_store.register(
        substituted_lock_bundle_descriptor, canonical_bytes(lock_signing_bundle)
    )
    results.append(
        expect_failure(
            "compilation-input-signature-bundle-substitution",
            lambda: validate_deployment(
                lock,
                lock_bundle_deployment,
                lock_bundle_store,
                registry,
                schemas,
            ),
        )
    )

    for missing_field in ("releaseDigest", "signingResult"):
        incomplete_runtime_release = deepcopy(runtime_release)
        incomplete_runtime_release.pop(missing_field)
        results.append(
            expect_failure(
                f"runtime-release-{missing_field}-missing",
                lambda value=incomplete_runtime_release: validate_schema_instance(
                    value,
                    RUNTIME_RELEASE_SCHEMA_ID,
                    registry,
                    schemas,
                ),
            )
        )
    runtime_signing_mutations = (
        (
            "subject",
            "subjectDigest",
            canonical_digest({"profile": "substituted-runtime-release/1"}),
        ),
        ("purpose", "purpose", "consumer-deployment-v1"),
        (
            "repository",
            "repository",
            "registry.example/consumer/other-runtime-releases",
        ),
    )
    for case_suffix, field, value in runtime_signing_mutations:
        mutated_runtime_release = deepcopy(runtime_release)
        mutated_runtime_release["signingResult"][field] = value
        results.append(
            expect_failure(
                f"runtime-release-signing-{case_suffix}-substitution",
                lambda candidate=mutated_runtime_release: validate_runtime_release(
                    deployment,
                    evidence,
                    candidate,
                    store,
                    registry,
                    schemas,
                ),
            )
        )
    runtime_bundle_descriptor = runtime_release["signingResult"][
        "signatureBundle"
    ]
    runtime_bundle = parse_json_bytes(
        store.resolve(runtime_bundle_descriptor), "runtime release signing bundle"
    )
    runtime_bundle["statement"]["subjectDigest"] = canonical_digest(
        {"profile": "substituted-runtime-release-bundle-subject/1"}
    )
    runtime_bundle["fixtureStatementChecksum"] = canonical_digest(
        {
            "profile": "bytedesk.test-only-kms-statement-checksum/1",
            "statement": runtime_bundle["statement"],
        }
    )
    substituted_runtime_bundle_descriptor = replace_descriptor_bytes(
        runtime_bundle_descriptor, runtime_bundle
    )
    runtime_bundle_release = deepcopy(runtime_release)
    runtime_bundle_release["signingResult"]["signatureBundle"] = (
        substituted_runtime_bundle_descriptor
    )
    runtime_bundle_store = store.clone()
    runtime_bundle_store.register(
        substituted_runtime_bundle_descriptor, canonical_bytes(runtime_bundle)
    )
    results.append(
        expect_failure(
            "runtime-release-signature-bundle-substitution",
            lambda: validate_runtime_release(
                deployment,
                evidence,
                runtime_bundle_release,
                runtime_bundle_store,
                registry,
                schemas,
            ),
        )
    )

    deployment_bytes = store.resolve(evidence["statement"]["consumerDeployment"])
    tampered_deployment_bytes = bytearray(deployment_bytes)
    tampered_deployment_bytes[0] ^= 1
    results.append(
        expect_failure(
            "descriptor-byte-substitution-consumer-deployment",
            lambda: ArtifactStore().register(
                evidence["statement"]["consumerDeployment"],
                bytes(tampered_deployment_bytes),
            ),
        )
    )

    for case_id, mutate in (
        (
            "lock-contract-replay-recomputed-downstream",
            lambda value: value.__setitem__(
                "contract", "bytedesk.private-compilation-input/replayed"
            ),
        ),
        (
            "lock-schema-replay-recomputed-downstream",
            lambda value: value["schema"].__setitem__(
                "digest",
                canonical_digest(
                    {"profile": "bytedesk.fixture-replayed-lock-schema/1"}
                ),
            ),
        ),
    ):
        replay = cascaded_lock_replay(
            store,
            lock,
            deployment,
            evidence,
            runtime_release,
            payload,
            mutate,
        )
        results.append(
            expect_failure(
                case_id,
                lambda values=replay: validate_graph(
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    registry,
                    schemas,
                    expected_signers,
                    product_release,
                ),
            )
        )

    alternate_lock = deepcopy(lock)
    alternate_lock["compilationInputDigest"] = canonical_digest(
        {"profile": "bytedesk.fixture-wrong-lock/1"}
    )
    alternate_lock_descriptor = replace_descriptor_bytes(
        deployment["compilationInput"], alternate_lock
    )
    wrong_lock_evidence = deepcopy(evidence)
    wrong_lock_evidence["statement"]["compilationInput"] = (
        alternate_lock_descriptor
    )
    refresh_evidence_envelope(wrong_lock_evidence)
    wrong_lock_store = store.clone()
    wrong_lock_store.register(
        alternate_lock_descriptor, canonical_bytes(alternate_lock)
    )
    results.append(
        expect_failure(
            "compilation-evidence-wrong-lock-descriptor",
            lambda: validate_graph(
                lock,
                deployment,
                wrong_lock_evidence,
                runtime_release,
                wrong_lock_store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    alternate_deployment = deepcopy(deployment)
    alternate_deployment["deploymentId"] = "deployment-substituted"
    alternate_deployment_descriptor = replace_descriptor_bytes(
        evidence["statement"]["consumerDeployment"], alternate_deployment
    )
    wrong_deployment_evidence = deepcopy(evidence)
    wrong_deployment_evidence["statement"]["consumerDeployment"] = (
        alternate_deployment_descriptor
    )
    refresh_evidence_envelope(wrong_deployment_evidence)
    wrong_deployment_store = store.clone()
    wrong_deployment_store.register(
        alternate_deployment_descriptor, canonical_bytes(alternate_deployment)
    )
    results.append(
        expect_failure(
            "compilation-evidence-wrong-deployment-descriptor",
            lambda: validate_graph(
                lock,
                deployment,
                wrong_deployment_evidence,
                runtime_release,
                wrong_deployment_store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    wrong_runtime = deepcopy(runtime_release)
    wrong_runtime["deployments"][0]["deployment"] = alternate_deployment_descriptor
    results.append(
        expect_failure(
            "runtime-deployment-descriptor-substitution",
            lambda: validate_graph(
                lock,
                deployment,
                evidence,
                wrong_runtime,
                wrong_deployment_store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )
    missing_runtime_evidence = deepcopy(runtime_release)
    missing_runtime_evidence["deployments"][0].pop("compilationEvidence")
    results.append(
        expect_failure(
            "runtime-compilation-evidence-missing",
            lambda: validate_graph(
                lock,
                deployment,
                evidence,
                missing_runtime_evidence,
                store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )
    cross_consumer_evidence = deepcopy(evidence)
    cross_consumer_evidence["statement"]["consumerId"] = "consumer-cross-tenant"
    refresh_evidence_envelope(cross_consumer_evidence)
    cross_consumer_evidence_descriptor = replace_descriptor_bytes(
        evidence_artifact["descriptor"], cross_consumer_evidence
    )
    cross_consumer_store = store.clone()
    cross_consumer_store.register(
        cross_consumer_evidence_descriptor, canonical_bytes(cross_consumer_evidence)
    )
    cross_consumer_runtime = deepcopy(runtime_release)
    cross_consumer_runtime["deployments"][0]["compilationEvidence"] = (
        cross_consumer_evidence_descriptor
    )
    results.append(
        expect_failure(
            "runtime-compilation-evidence-cross-consumer",
            lambda: validate_graph(
                lock,
                deployment,
                evidence,
                cross_consumer_runtime,
                cross_consumer_store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )
    wrong_runtime_evidence = deepcopy(runtime_release)
    wrong_runtime_evidence["deployments"][0]["compilationEvidence"] = (
        evidence["statement"]["consumerDeployment"]
    )
    results.append(
        expect_failure(
            "runtime-compilation-evidence-role-substitution",
            lambda: validate_graph(
                lock,
                deployment,
                evidence,
                wrong_runtime_evidence,
                store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    stale_deployment_signature = deepcopy(evidence)
    stale_deployment_signature["statement"]["deploymentSigningResult"][
        "subjectDigest"
    ] = canonical_digest({"profile": "bytedesk.fixture-stale-deployment-signature/1"})
    refresh_evidence_envelope(stale_deployment_signature)
    results.append(
        expect_failure(
            "deployment-signature-stale-subject",
            lambda: validate_graph(
                lock,
                deployment,
                stale_deployment_signature,
                runtime_release,
                store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    substituted_deployment_signer = deepcopy(evidence)
    substituted_deployment_signer["statement"]["deploymentSigningResult"][
        "publicKeyDigest"
    ] = canonical_digest({"profile": "bytedesk.fixture-wrong-deployment-key/1"})
    refresh_evidence_envelope(substituted_deployment_signer)
    results.append(
        expect_failure(
            "deployment-signer-substitution",
            lambda: validate_graph(
                lock,
                deployment,
                substituted_deployment_signer,
                runtime_release,
                store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    for case_id, signing_result_path in (
        (
            "deployment-signature-bundle-semantic-substitution",
            ("statement", "deploymentSigningResult"),
        ),
        ("compilation-signature-bundle-semantic-substitution", ("signingResult",)),
    ):
        substituted = deepcopy(evidence)
        signing_result = substituted
        for segment in signing_result_path:
            signing_result = signing_result[segment]
        bundle_descriptor = signing_result["signatureBundle"]
        bundle = parse_json_bytes(
            store.resolve(bundle_descriptor), f"{case_id} baseline bundle"
        )
        bundle["statement"]["subjectDigest"] = canonical_digest(
            {"profile": f"bytedesk.fixture-{case_id}/1"}
        )
        bundle["fixtureStatementChecksum"] = canonical_digest(
            {
                "profile": "bytedesk.test-only-kms-statement-checksum/1",
                "statement": bundle["statement"],
            }
        )
        substituted_bundle_descriptor = replace_descriptor_bytes(
            bundle_descriptor, bundle
        )
        signing_result["signatureBundle"] = substituted_bundle_descriptor
        refresh_evidence_envelope(substituted)
        substituted_store = store.clone()
        substituted_store.register(
            substituted_bundle_descriptor, canonical_bytes(bundle)
        )
        results.append(
            expect_failure(
                case_id,
                lambda e=substituted, s=substituted_store: validate_graph(
                    lock,
                    deployment,
                    e,
                    runtime_release,
                    s,
                    registry,
                    schemas,
                    expected_signers,
                    product_release,
                ),
            )
        )

    expired_authority_lock = deepcopy(lock)
    expired_authority_store = refresh_mutated_lock_authority(
        store,
        lock,
        expired_authority_lock,
        lambda authority: authority.__setitem__(
            "expiresAt", "2026-07-17T11:59:59Z"
        ),
    )
    results.append(
        expect_failure(
            "consumer-authority-expired",
            lambda: validate_lock(
                expired_authority_lock,
                expired_authority_store,
                registry,
                schemas,
                product_release,
            ),
        )
    )
    future_authority_lock = deepcopy(lock)
    future_authority_store = refresh_mutated_lock_authority(
        store,
        lock,
        future_authority_lock,
        lambda authority: authority.__setitem__(
            "notBefore",
            (
                timestamp(lock["inputs"]["reproducibleEpoch"])
                + timedelta(seconds=1)
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        ),
    )
    results.append(
        expect_failure(
            "consumer-authority-not-yet-valid",
            lambda: validate_lock(
                future_authority_lock,
                future_authority_store,
                registry,
                schemas,
                product_release,
            ),
        )
    )

    approval_mutations = (
        (
            "skill-approval-expired",
            lambda approval, _other: approval.__setitem__(
                "expiresAt", "2026-07-17T11:59:59Z"
            ),
        ),
        (
            "skill-approval-wrong-skill",
            lambda approval, other: approval.__setitem__("skill", other),
        ),
        (
            "skill-approval-cross-installation",
            lambda approval, _other: approval.__setitem__(
                "installationId", "installation-cross-tenant"
            ),
        ),
    )
    for case_id, mutate_approval in approval_mutations:
        mutated_lock = deepcopy(lock)
        approval_entry = mutated_lock["inputs"]["skillApprovals"][0]
        baseline_approval_entry = lock["inputs"]["skillApprovals"][0]
        approval_document = parse_json_bytes(
            store.resolve(baseline_approval_entry["approval"]), case_id
        )
        mutate_approval(
            approval_document,
            lock["inputs"]["skillApprovals"][1]["skill"],
        )
        approval_descriptor = replace_descriptor_bytes(
            baseline_approval_entry["approval"], approval_document
        )
        approval_entry["approval"] = approval_descriptor
        mutated_store = store.clone()
        mutated_store.register(
            approval_descriptor, canonical_bytes(approval_document)
        )
        mutated_store = refresh_mutated_lock_authority(
            mutated_store, lock, mutated_lock
        )
        results.append(
            expect_failure(
                case_id,
                lambda value=mutated_lock, s=mutated_store: validate_lock(
                    value, s, registry, schemas, product_release
                ),
            )
        )

    compiler_policy = evidence["signingResult"]["trustPolicy"]
    compiler_authority_lock = deepcopy(lock)
    compiler_authority_lock["inputs"]["authoritySnapshot"]["trustPolicy"] = (
        compiler_policy
    )
    results.append(
        expect_failure(
            "compiler-cannot-sign-consumer-authority",
            lambda: validate_lock(
                compiler_authority_lock,
                store,
                registry,
                schemas,
                product_release,
            ),
        )
    )
    compiler_skill_lock = deepcopy(lock)
    compiler_skill = compiler_skill_lock["inputs"]["effectiveSkillSet"][
        "privateSkills"
    ][0]
    original_private_skill_digest = compiler_skill["digest"]
    compiler_skill["trustPolicy"] = compiler_policy
    for approval_entry in compiler_skill_lock["inputs"]["skillApprovals"]:
        if approval_entry["skill"]["digest"] == original_private_skill_digest:
            approval_entry["skill"] = deepcopy(compiler_skill)
    compiler_skill_lock["inputs"]["effectiveSkillSet"]["digest"] = canonical_digest(
        {
            "profile": "bytedesk.renderer-effective-skill-set/1",
            "publicSkills": compiler_skill_lock["inputs"]["effectiveSkillSet"][
                "publicSkills"
            ],
            "privateSkills": compiler_skill_lock["inputs"]["effectiveSkillSet"][
                "privateSkills"
            ],
        }
    )
    compiler_skill_store = refresh_mutated_lock_authority(
        store, lock, compiler_skill_lock
    )
    results.append(
        expect_failure(
            "compiler-cannot-sign-private-skill",
            lambda: validate_lock(
                compiler_skill_lock,
                compiler_skill_store,
                registry,
                schemas,
                product_release,
            ),
        )
    )
    compiler_deployment_signature = deepcopy(evidence)
    deployment_signing = compiler_deployment_signature["statement"][
        "deploymentSigningResult"
    ]
    for field in ("keyVersion", "publicKeyDigest", "trustPolicy"):
        deployment_signing[field] = deepcopy(evidence["signingResult"][field])
    refresh_evidence_envelope(compiler_deployment_signature)
    results.append(
        expect_failure(
            "compiler-cannot-sign-consumer-deployment",
            lambda: validate_graph(
                lock,
                deployment,
                compiler_deployment_signature,
                runtime_release,
                store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    public_render_baseline = parse_json_bytes(
        store.resolve(lock["inputs"]["publicArtifact"]), "public render mutations"
    )
    public_lineage_mutations = (
        (
            "public-render-public-skills-substitution",
            lambda value: value.__setitem__(
                "publicSkills",
                lock["inputs"]["effectiveSkillSet"]["privateSkills"],
            ),
        ),
        (
            "public-render-product-release-substitution",
            lambda value: value.__setitem__(
                "productRelease", lock["inputs"]["rendererSelection"]["rendererRelease"]
            ),
        ),
        (
            "public-render-executed-distribution-substitution",
            lambda value: value.__setitem__(
                "executedDistribution",
                lock["inputs"]["rendererSelection"]["productDistribution"],
            ),
        ),
        (
            "public-render-platform-substitution",
            lambda value: value.__setitem__("platform", "linux/arm64"),
        ),
        (
            "public-render-product-distribution-digest-substitution",
            lambda value: value.__setitem__(
                "productDistributionDigest",
                canonical_digest(
                    {"profile": "bytedesk.fixture-wrong-public-product/1"}
                ),
            ),
        ),
        (
            "public-render-allowlist-digest-substitution",
            lambda value: value.__setitem__(
                "compiledAllowlistDigest",
                canonical_digest(
                    {"profile": "bytedesk.fixture-wrong-public-allowlist/1"}
                ),
            ),
        ),
        (
            "public-render-schema-set-substitution",
            lambda value: value.__setitem__(
                "rendererSchemas", value["rendererSchemas"][:-1]
            ),
        ),
    )
    for case_id, mutate_public_render in public_lineage_mutations:
        mutated_public_render = deepcopy(public_render_baseline)
        mutate_public_render(mutated_public_render)
        public_descriptor = replace_descriptor_bytes(
            lock["inputs"]["publicArtifact"], mutated_public_render
        )
        mutated_lock = deepcopy(lock)
        mutated_lock["inputs"]["publicArtifact"] = public_descriptor
        mutated_store = store.clone()
        mutated_store.register(
            public_descriptor, canonical_bytes(mutated_public_render)
        )
        mutated_store = refresh_mutated_lock_authority(
            mutated_store, lock, mutated_lock
        )
        results.append(
            expect_failure(
                case_id,
                lambda value=mutated_lock, s=mutated_store: validate_lock(
                    value, s, registry, schemas, product_release
                ),
            )
        )

    mutated_binding_lock = deepcopy(lock)
    baseline_binding = parse_json_bytes(
        store.resolve(lock["inputs"]["binding"]), "binding customization mutation"
    )
    baseline_binding["customization"]["agentSpec"]["operations"] = [
        {"op": "replace", "path": "/name", "value": "substituted"}
    ]
    mutated_binding_descriptor = replace_descriptor_bytes(
        lock["inputs"]["binding"], baseline_binding
    )
    mutated_binding_lock["inputs"]["binding"] = mutated_binding_descriptor
    mutated_binding_store = store.clone()
    mutated_binding_store.register(
        mutated_binding_descriptor, canonical_bytes(baseline_binding)
    )
    mutated_binding_store = refresh_mutated_lock_authority(
        mutated_binding_store, lock, mutated_binding_lock
    )
    results.append(
        expect_failure(
            "binding-customization-digest-substitution",
            lambda: validate_lock(
                mutated_binding_lock,
                mutated_binding_store,
                registry,
                schemas,
                product_release,
            ),
        )
    )

    for case_id, mutate_skills in (
        (
            "public-skill-duplicate",
            lambda value: value["inputs"]["effectiveSkillSet"][
                "publicSkills"
            ].append(
                deepcopy(
                    value["inputs"]["effectiveSkillSet"]["publicSkills"][0]
                )
            ),
        ),
        (
            "skill-cross-scope-duplicate",
            lambda value: value["inputs"]["effectiveSkillSet"][
                "privateSkills"
            ].append(
                deepcopy(
                    value["inputs"]["effectiveSkillSet"]["publicSkills"][0]
                )
            ),
        ),
        (
            "skill-approval-duplicate",
            lambda value: value["inputs"]["skillApprovals"].append(
                deepcopy(value["inputs"]["skillApprovals"][0])
            ),
        ),
    ):
        mutated_lock = deepcopy(lock)
        mutate_skills(mutated_lock)
        mutated_lock["inputs"]["effectiveSkillSet"]["digest"] = canonical_digest(
            {
                "profile": "bytedesk.renderer-effective-skill-set/1",
                "publicSkills": mutated_lock["inputs"]["effectiveSkillSet"][
                    "publicSkills"
                ],
                "privateSkills": mutated_lock["inputs"]["effectiveSkillSet"][
                    "privateSkills"
                ],
            }
        )
        mutated_store = refresh_mutated_lock_authority(
            store, lock, mutated_lock
        )
        results.append(
            expect_failure(
                case_id,
                lambda value=mutated_lock, s=mutated_store: validate_lock(
                    value, s, registry, schemas, product_release
                ),
            )
        )

    duplicate_skill_deployment = deepcopy(deployment)
    duplicate_skill_deployment["approvedSkills"].append(
        deepcopy(duplicate_skill_deployment["approvedSkills"][0])
    )
    duplicate_skill_descriptor = replace_descriptor_bytes(
        evidence["statement"]["consumerDeployment"], duplicate_skill_deployment
    )
    duplicate_skill_evidence = deepcopy(evidence)
    duplicate_skill_evidence["statement"]["consumerDeployment"] = (
        duplicate_skill_descriptor
    )
    refresh_evidence_envelope(duplicate_skill_evidence)
    duplicate_skill_runtime = deepcopy(runtime_release)
    duplicate_skill_runtime["deployments"][0]["deployment"] = (
        duplicate_skill_descriptor
    )
    duplicate_skill_store = mutation_store(
        store,
        lock,
        duplicate_skill_deployment,
        duplicate_skill_evidence,
        payload,
    )
    results.append(
        expect_failure(
            "deployment-approved-skill-duplicate",
            lambda: validate_graph(
                lock,
                duplicate_skill_deployment,
                duplicate_skill_evidence,
                duplicate_skill_runtime,
                duplicate_skill_store,
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    deployment_cross_fields = (
        "/consumerId",
        "/subjectId",
        "/installationId",
        "/harnessId",
        "/targetId",
        "/candidate/digest",
        "/desiredRevision/revision",
        "/desiredRevision/digest",
        "/predecessor/digest",
        "/runtimeSlot/slotId",
        "/runtimeSlot/generation",
        "/activationMode",
        "/publicRender/digest",
        "/binding/digest",
        "/source/digest",
        "/compilationAuthority/digest",
        "/compilationInputDigest",
        "/rendererSelectionDigest",
        "/productRelease/digest",
        "/rendererRelease/digest",
        "/executedDistribution/digest",
        "/productDistributionDigest",
        "/compiledAllowlistDigest",
        "/opaqueConsumerDigests/policy",
        "/opaqueConsumerDigests/grantSet",
        "/opaqueConsumerDigests/credentialSet",
        "/opaqueConsumerDigests/workloadIdentity",
        "/opaqueConsumerDigests/lifecycle",
        "/opaqueConsumerDigests/sandbox",
        "/opaqueConsumerDigests/network",
        "/opaqueConsumerDigests/approvalPolicy",
        "/opaqueConsumerDigests/targetBinding",
        "/effectiveRender/manifestDigest",
        "/effectiveRender/manifest/source/digest",
        "/effectiveRender/manifest/customizationDigest",
        "/effectiveRender/manifest/inputParametersDigest",
        "/effectiveRender/manifest/harnessConfigurationDigest",
        "/rendererExecution/attemptAuthority/productReleaseStatusCheckpointDigest",
        "/rendererExecution/attemptAuthority/productReleaseStatusCheckpointAuthenticationEvidenceDigest",
        "/rendererExecution/attemptAuthority/productReleaseStatusRequestNonce",
        "/rendererExecution/attemptAuthority/rendererReleaseStatusCheckpointDigest",
        "/rendererExecution/attemptAuthority/rendererReleaseStatusCheckpointAuthenticationEvidenceDigest",
        "/rendererExecution/attemptAuthority/rendererReleaseStatusRequestNonce",
        "/rendererExecution/attemptAuthority/framedRequestDigest",
        "/reproducibleEpoch",
        "/createdAt",
    )
    for pointer in deployment_cross_fields:
        mutated_deployment = deepcopy(deployment)
        set_pointer(
            mutated_deployment,
            pointer,
            changed_value(get_pointer(mutated_deployment, pointer)),
        )
        mutated_evidence = deepcopy(evidence)
        mutated_descriptor = replace_descriptor_bytes(
            evidence["statement"]["consumerDeployment"], mutated_deployment
        )
        mutated_evidence["statement"]["consumerDeployment"] = mutated_descriptor
        refresh_evidence_envelope(mutated_evidence)
        mutated_runtime = deepcopy(runtime_release)
        mutated_runtime["deployments"][0]["deployment"] = mutated_descriptor
        dynamic_store = mutation_store(
            store, lock, mutated_deployment, mutated_evidence, payload
        )
        results.append(
            expect_failure(
                f"deployment-cross-field-{pointer.removeprefix('/').replace('/', '-')}",
                lambda d=mutated_deployment, e=mutated_evidence, r=mutated_runtime, s=dynamic_store: validate_graph(
                    lock,
                    d,
                    e,
                    r,
                    s,
                    registry,
                    schemas,
                    expected_signers,
                    product_release,
                ),
            )
        )

    for field in (
        "compilationInputDigest",
        "rendererSelectionDigest",
        "rendererAttemptAuthorityDigest",
        "rendererAttemptAuthenticationEvidenceDigest",
        "rendererExecutionReceiptDigest",
        "rendererExecutionAuthenticationEvidenceDigest",
        "renderManifestDigest",
        "compilerIdentityDigest",
        "compilerWorkerProfileDigest",
    ):
        mutated_evidence = deepcopy(evidence)
        mutated_evidence["statement"][field] = f"sha256:{'f' * 64}"
        refresh_evidence_envelope(mutated_evidence)
        dynamic_store = mutation_store(
            store, lock, deployment, mutated_evidence, payload
        )
        results.append(
            expect_failure(
                f"compilation-evidence-{field}-substitution",
                lambda e=mutated_evidence, s=dynamic_store: validate_graph(
                    lock,
                    deployment,
                    e,
                    runtime_release,
                    s,
                    registry,
                    schemas,
                    expected_signers,
                    product_release,
                ),
            )
        )

    wrong_request = deepcopy(evidence)
    wrong_request["statement"]["compileRequestDigest"] = f"sha256:{'f' * 64}"
    refresh_evidence_envelope(wrong_request)
    results.append(
        expect_failure(
            "compilation-evidence-request-substitution",
            lambda: validate_graph(
                lock,
                deployment,
                wrong_request,
                runtime_release,
                mutation_store(store, lock, deployment, wrong_request, payload),
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    wrong_signer = deepcopy(evidence)
    wrong_signer["signingResult"]["publicKeyDigest"] = f"sha256:{'f' * 64}"
    results.append(
        expect_failure(
            "compilation-evidence-compiler-signer-substitution",
            lambda: validate_graph(
                lock,
                deployment,
                wrong_signer,
                runtime_release,
                mutation_store(store, lock, deployment, wrong_signer, payload),
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    for backlink in ("compilationEvidence", "runtimeRelease"):
        mutated_deployment = deepcopy(deployment)
        mutated_deployment[backlink] = evidence["statement"]["consumerDeployment"]
        results.append(
            expect_failure(
                f"deployment-{backlink}-backlink",
                lambda d=mutated_deployment: validate_schema_instance(
                    d, DEPLOYMENT_SCHEMA_ID, registry, schemas
                ),
            )
        )

    self_inventory = deepcopy(deployment)
    self_inventory["effectiveRender"]["manifest"]["files"].append(
        {
            "path": ".bytedesk-delivery/consumer-deployment.json",
            "digest": f"sha256:{'f' * 64}",
            "size": 1,
            "mode": "0444",
            "origin": "generated",
            "ownershipClass": "runtime_read_only",
        }
    )
    self_inventory["effectiveRender"]["manifest"]["files"] = sorted(
        self_inventory["effectiveRender"]["manifest"]["files"],
        key=lambda entry: entry["path"].encode("utf-8"),
    )
    self_inventory["effectiveRender"]["manifestDigest"] = canonical_digest(
        self_inventory["effectiveRender"]["manifest"]
    )
    self_evidence = deepcopy(evidence)
    self_descriptor = replace_descriptor_bytes(
        evidence["statement"]["consumerDeployment"], self_inventory
    )
    self_evidence["statement"]["consumerDeployment"] = self_descriptor
    self_evidence["statement"]["renderManifestDigest"] = self_inventory[
        "effectiveRender"
    ]["manifestDigest"]
    refresh_evidence_envelope(self_evidence)
    self_runtime = deepcopy(runtime_release)
    self_runtime["deployments"][0]["deployment"] = self_descriptor
    results.append(
        expect_failure(
            "render-payload-self-inventory",
            lambda: validate_graph(
                lock,
                self_inventory,
                self_evidence,
                self_runtime,
                mutation_store(
                    store, lock, self_inventory, self_evidence, payload
                ),
                registry,
                schemas,
                expected_signers,
                product_release,
            ),
        )
    )

    rebuilt_a, _ = fixture_generator.build_graph()
    rebuilt_b, _ = fixture_generator.build_graph()
    require(
        rebuilt_a == rebuilt_b,
        "idempotent_rebuild_drift",
        "private graph bytes",
    )
    prospective_lock = json.loads(
        rebuilt_a[fixture_generator.LOCK_PATH].decode("utf-8")
    )
    prospective_authentication_descriptor = prospective_lock["inputs"][
        "inputAuthentication"
    ]
    prospective_authentication_bundle = json.loads(
        rebuilt_a[
            fixture_generator.blob_path(
                prospective_authentication_descriptor["digest"]
            )
        ].decode("utf-8")
    )
    prospective_authentication_projection = json.loads(
        rebuilt_a[
            fixture_generator.PRIVATE_INPUT_AUTHENTICATION_PATH
        ].decode("utf-8")
    )
    require(
        prospective_authentication_projection
        == prospective_authentication_bundle,
        "private_input_authentication_projection_source_drift",
        "stable positive projection",
    )
    prospective_authentication_denial = json.loads(
        rebuilt_a[
            fixture_generator.PRIVATE_INPUT_AUTHENTICATION_UNKNOWN_PATH
        ].decode("utf-8")
    )
    prospective_authentication_without_unknown = deepcopy(
        prospective_authentication_denial
    )
    prospective_authentication_without_unknown.pop("__unknown", None)
    require(
        prospective_authentication_without_unknown
        == prospective_authentication_projection,
        "private_input_authentication_denial_source_drift",
        "unknown-root-field projection",
    )
    prospective_authentication_errors = list(
        Draft202012Validator(
            schemas[PRIVATE_INPUT_AUTHENTICATION_SCHEMA_ID],
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(prospective_authentication_denial)
    )
    require(
        "additionalProperties"
        in {
            error.validator
            for error in prospective_authentication_errors
            if isinstance(error.validator, str)
        },
        "private_input_authentication_denial_not_rejected",
        "unknown root member",
    )
    results.append(
        {
            "id": "private-input-authentication-bundle-unknown-root-field",
            "outcome": "denied",
            "reason": "additionalProperties",
        }
    )
    results.append({"id": "idempotent-byte-replay", "outcome": "permitted"})
    mutation_case_ids_by_class = {
        "activation-authorization-digest-only": (
            "activation-authorization-digest-only",
        ),
        "activation-authorization-expired-at-use": (
            "activation-authorization-expired-at-use",
        ),
        "activation-authorization-kms-forgery": (
            "activation-authorization-kms-forgery",
        ),
        "activation-deployable-graph-substitution": (
            "activation-deployable-graph-substitution",
        ),
        "activation-eligibility-missing-renderer": (
            "activation-eligibility-missing-renderer",
        ),
        "activation-eligibility-stale-or-wrong-stage": (
            "activation-eligibility-stale-or-wrong-stage",
        ),
        "activation-eligibility-verification-result-missing": (
            "activation-eligibility-verification-result-missing",
        ),
        "activation-eligibility-verification-result-substitution": (
            "activation-eligibility-verification-result-substitution",
        ),
        "activation-host-use-time-status-expired-boundary": (
            "activation-host-use-time-status-expired-boundary",
        ),
        "activation-host-use-time-verification-missing": (
            "activation-host-use-time-verification-missing",
        ),
        "activation-host-use-time-verification-substitution": (
            "activation-host-use-time-verification-substitution",
        ),
        "activation-subject-evidence-coverage-mismatch": tuple(
            coverage_case_ids
        ),
        "activation-target-slot-generation-mismatch": (
            "activation-mixed-slot-generation",
        ),
        "compilation-evidence-cross-field-substitution": (
            "compilation-evidence-compilationInputDigest-substitution",
        ),
        "compilation-input-signature-bundle-substitution": (
            "compilation-input-signature-bundle-substitution",
        ),
        "compilation-input-signing-result-missing": (
            "deployment-compilation-input-signing-result-missing",
        ),
        "compilation-input-signing-result-substitution": (
            "compilation-input-signing-result-subjectDigest-substitution",
            "compilation-input-signing-result-repository-substitution",
        ),
        "compiler-signer-substitution": (
            "compilation-evidence-compiler-signer-substitution",
        ),
        "contract-bundle-keyless-verification-missing-or-substituted": (
            "contract-bundle-keyless-verification-missing",
            "contract-bundle-keyless-verification-substituted",
        ),
        "deployment-cross-field-substitution": (
            "deployment-cross-field-consumerId",
        ),
        "deployment-evidence-backlink": (
            "deployment-compilationEvidence-backlink",
        ),
        "deployment-runtime-backlink": (
            "deployment-runtimeRelease-backlink",
        ),
        "descriptor-byte-substitution": (
            "descriptor-byte-substitution-consumer-deployment",
        ),
        "detached-input-authentication-missing": (
            "detached-authority-signature-missing",
        ),
        "detached-input-authentication-role-substitution": (
            "detached-authority-signature-cross-role-substitution",
        ),
        "forged-current-key-signature": (
            "forged-under-legitimate-current-key",
        ),
        "idempotent-byte-replay": ("idempotent-byte-replay",),
        "lock-contract-replay": ("lock-contract-replay-recomputed-downstream",),
        "lock-schema-replay": ("lock-schema-replay-recomputed-downstream",),
        "payload-self-inventory": ("render-payload-self-inventory",),
        "purpose-role-substitution": (
            "qualification-decision-purpose-role-substitution",
            "status-checkpoint-purpose-role-substitution",
            "compiler-cannot-sign-consumer-authority",
            "compiler-cannot-sign-private-skill",
        ),
        "release-status-eligibility-kms-forgery": (
            "release-status-eligibility-kms-forgery",
        ),
        "release-status-eligibility-missing-renderer": (
            "release-status-eligibility-missing-renderer",
        ),
        "release-status-eligibility-pin-provider-substitution": tuple(
            provider_binding_case_ids
        ),
        "release-status-eligibility-selection-only-reuse": (
            "release-status-eligibility-selection-only-reuse",
        ),
        "release-status-eligibility-stale": (
            "release-status-eligibility-stale",
        ),
        "release-status-eligibility-subject-substitution": (
            "release-status-eligibility-subject-substitution",
        ),
        "release-status-eligibility-withdrawn": (
            "release-status-eligibility-withdrawn",
        ),
        "release-status-eligibility-wrong-nonce": (
            "release-status-eligibility-wrong-nonce",
        ),
        "renderer-request-frame-substitution": (
            "renderer-request-frame-byte-substitution",
        ),
        "renderer-response-frame-substitution": (
            "renderer-response-frame-byte-substitution",
        ),
        "runtime-deployment-substitution": (
            "runtime-deployment-descriptor-substitution",
        ),
        "runtime-release-digest-missing": (
            "runtime-release-releaseDigest-missing",
        ),
        "runtime-release-signature-bundle-substitution": (
            "runtime-release-signature-bundle-substitution",
        ),
        "runtime-release-signing-result-missing": (
            "runtime-release-signingResult-missing",
        ),
        "runtime-release-signing-result-substitution": (
            "runtime-release-signing-subject-substitution",
            "runtime-release-signing-purpose-substitution",
            "runtime-release-signing-repository-substitution",
        ),
        "signer-authenticated-identity-substitution": tuple(
            case_id for case_id, _, _ in product_signer_mutations
        ),
        "signer-key-separation": ("signer-purpose-key-collision",),
        "signer-public-key-policy-substitution": (
            "authenticated-signer-public-key-substitution",
        ),
        "signer-workload-separation": ("signer-purpose-workload-collision",),
        "signing-policy-not-after-boundary": (
            "signing-policy-not-after-boundary",
        ),
        "signing-request-field-substitution": tuple(
            f"signing-request-{field}-substitution"
            for field, _ in signing_request_mutations
        ),
        "signing-time-future": ("signing-time-future",),
        "trust-policy-pin-substitution": (
            "coherent-attacker-trust-policy-substitution",
        ),
    }
    required_class_list = cases["requiredMutationClasses"]
    require(
        required_class_list == sorted(set(required_class_list)),
        "mutation_catalog_not_sorted_unique",
        "requiredMutationClasses",
    )
    required_classes = set(required_class_list)
    require(
        required_classes == set(mutation_case_ids_by_class),
        "mutation_catalog_incomplete",
        (
            f"missing={sorted(set(mutation_case_ids_by_class)-required_classes)} "
            f"unexpected={sorted(required_classes-set(mutation_case_ids_by_class))}"
        ),
    )
    result_ids = [result["id"] for result in results]
    require(
        len(result_ids) == len(set(result_ids)),
        "duplicate_mutation_case_id",
        "results",
    )
    results_by_id = {result["id"]: result for result in results}
    for mutation_class, mapped_case_ids in mutation_case_ids_by_class.items():
        require(
            bool(mapped_case_ids),
            "mutation_class_without_case",
            mutation_class,
        )
        for case_id in mapped_case_ids:
            require(
                case_id in results_by_id,
                "mutation_case_not_executed",
                f"{mutation_class}:{case_id}",
            )
            require(
                results_by_id[case_id]["outcome"]
                == ("permitted" if case_id == "idempotent-byte-replay" else "denied"),
                "mutation_case_wrong_outcome",
                f"{mutation_class}:{case_id}",
            )
    report = {
        "profile": "bytedesk.private-compilation-graph-conformance-evidence/1",
        "caseCount": len(results),
        "deploymentCrossFieldMutationCount": len(deployment_cross_fields),
        "requiredMutationCoverage": {
            key: list(value)
            for key, value in sorted(mutation_case_ids_by_class.items())
        },
        "cases": results,
        "outcome": "pass",
    }
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GraphError as error:
        print(f"private compilation graph validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
