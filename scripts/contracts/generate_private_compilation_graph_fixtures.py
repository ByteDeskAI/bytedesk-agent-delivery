#!/usr/bin/env python3
"""Build the acyclic private-compilation proof graph from exact fixture inputs."""

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
from typing import Any

import rfc8785

from contractlib import ContractToolError, write_bytes
from fixture_ownership import (
    FixtureOwnershipError,
    assert_private_generator_owns_declared_outputs,
)
import generate_renderer_digest_fixtures as renderer_fixture_generator
from release_status_eligibility import (
    ReleaseStatusEligibilityBuilder,
    permitted_verification_result,
)
from renderer_authority import inline_authority_preimage, renderer_selection_preimage
from signing_authority import (
    SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
    build_signer_authentication_evidence,
)
from status_head_authority import StatusHeadAuthorityBuilder
from status_merkle import status_leaf_digest, verify_consistency, verify_inclusion
from trusted_kms_adapter import (
    CONTRACT_BUNDLE_MEDIA_TYPES,
    CONTRACT_BUNDLE_RELEASE_PURPOSE,
    TrustedKmsVerificationAdapter,
    signature_verification_vector,
)
from trust_policy_pins import (
    build_initial_trust_policy_pin_set,
    build_pin_set_provider_evidence,
    pin_set_document_descriptor,
    pin_set_provider_authentication_vector,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"
FIXTURE_ROOT = REPOSITORY_ROOT / "contracts" / "fixtures" / "schema"
POSITIVE_ROOT = FIXTURE_ROOT / "positive"
NEGATIVE_ROOT = FIXTURE_ROOT / "negative"
OPERATIONS_ROOT = REPOSITORY_ROOT / "contracts" / "fixtures" / "operations"
CAS_ROOT = OPERATIONS_ROOT / "private-compilation-cas" / "blobs" / "sha256"
CASE_PATH = OPERATIONS_ROOT / "private-compilation-graph.cases.json"

LOCK_PATH = POSITIVE_ROOT / "private-compilation-input__complete-lock.json"
PRIVATE_INPUT_AUTHENTICATION_PATH = (
    POSITIVE_ROOT / "private-input-authentication-bundle__complete.json"
)
MANIFEST_PATH = POSITIVE_ROOT / "render-manifest__hermes-private.json"
COMPATIBILITY_RESULT_PATH = (
    POSITIVE_ROOT / "renderer-compatibility-result__hermes-lossy.json"
)
HERMES_CAPABILITY_PATH = (
    POSITIVE_ROOT / "renderer-capability__hermes.json"
)
DEPLOYMENT_PATH = POSITIVE_ROOT / "consumer-deployment__effective-render.json"
EVIDENCE_PATH = POSITIVE_ROOT / "private-compilation-evidence__committed.json"
RUNTIME_RELEASE_PATH = POSITIVE_ROOT / "runtime-release__prepared.json"
ACTIVATION_AUTHORIZATION_PATH = (
    POSITIVE_ROOT / "activation-authorization__complete.json"
)
ACTIVATION_AUTHORIZATION_UNKNOWN_PATH = (
    NEGATIVE_ROOT / "activation-authorization__unknown-authority-field.json"
)
PRODUCT_RELEASE_PATH = POSITIVE_ROOT / "product-release-manifest__current.json"
CONSUMER_AUTHORITY_PATH = POSITIVE_ROOT / "consumer-authority__compile.json"
DEPLOYMENT_UNKNOWN_PATH = (
    NEGATIVE_ROOT / "consumer-deployment__unknown-authority-field.json"
)
DEPLOYMENT_EVIDENCE_BACKLINK_PATH = (
    NEGATIVE_ROOT / "consumer-deployment__compilation-evidence-backlink.json"
)
DEPLOYMENT_RUNTIME_BACKLINK_PATH = (
    NEGATIVE_ROOT / "consumer-deployment__runtime-release-backlink.json"
)
EVIDENCE_BACKLINK_PATH = (
    NEGATIVE_ROOT / "private-compilation-evidence__deployment-backlink.json"
)
PRIVATE_INPUT_AUTHENTICATION_UNKNOWN_PATH = (
    NEGATIVE_ROOT
    / "private-input-authentication-bundle__unknown-root-field.json"
)
RUNTIME_UNKNOWN_PATH = NEGATIVE_ROOT / "runtime-release__unknown-authority-field.json"

PRIVATE_INPUT_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.private-compilation-input.v1+json"
)
PRIVATE_INPUT_AUTHENTICATION_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.private-input-authentication.v1+json"
)
DEPLOYMENT_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.consumer-deployment.v1+json"
)
COMPILATION_EVIDENCE_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.private-compilation-evidence.v1+json"
)
COMPILATION_STATEMENT_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.private-compilation-statement.v1+json"
)
RUNTIME_RELEASE_MEDIA_TYPE = "application/vnd.bytedesk.agent.runtime-release.v1+json"
RUNTIME_RELEASE_STATEMENT_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.runtime-release-statement.v1+json"
)
STATUS_ELIGIBILITY_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.release-status-eligibility-evidence.v1+json"
)
STATUS_ELIGIBILITY_DIGEST_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.release-status-eligibility-evidence-digest.v1+json"
)
ACTIVATION_AUTHORIZATION_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.activation-authorization.v1+json"
)
ACTIVATION_AUTHORIZATION_STATEMENT_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.activation-authorization-statement.v1+json"
)
SIGNING_RESULT_MEDIA_TYPE = (
    "application/vnd.bytedesk.agent.signing-result.v1+json"
)
SIGNATURE_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
RENDER_PAYLOAD_MEDIA_TYPE = "application/vnd.bytedesk.render.bundle.v1+tar"
RENDERER_FRAME_MAX_PAYLOAD_BYTES = 4 * 1024 * 1024

CAS_PAYLOADS: dict[str, bytes] = {}
SIGNATURE_VERIFICATION_VECTORS: list[dict[str, Any]] = []


class GenerationError(RuntimeError):
    """The checked-in projections cannot produce one exact private graph."""


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise GenerationError(detail)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        require(key not in value, f"duplicate JSON member: {key}")
        value[key] = member
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                GenerationError(f"non-finite JSON number: {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot read {path}: {error}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def raw_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def register_cas_payload(payload: bytes) -> str:
    digest = raw_digest(payload)
    previous = CAS_PAYLOADS.get(digest)
    require(previous is None or previous == payload, f"private CAS collision: {digest}")
    CAS_PAYLOADS[digest] = payload
    return digest


def canonical_digest(value: Any) -> str:
    return raw_digest(canonical_bytes(value))


def output_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")


def schema_descriptor(name: str) -> dict[str, str]:
    schema = load_json(SCHEMA_ROOT / f"{name}.schema.json")
    return {"id": schema["$id"], "digest": canonical_digest(schema)}


PRODUCT_TRUST_PURPOSE_ROLES = {
    "product-release-v1": "product-release",
    CONTRACT_BUNDLE_RELEASE_PURPOSE: "contract-bundle-release",
    "release-qualification-policy-v1": "release-qualification-policy",
    "release-qualification-attempt-v1": "release-qualification-attempt",
    "release-qualification-receipt-v1": "release-qualification-receipt",
    "release-qualification-evidence-v1": "release-qualification-evidence",
    "release-qualification-decision-v1": "release-qualification-decision",
    "release-status-v1": "release-status",
    "release-status-head-v1": "release-status-head",
    "release-status-eligibility-v1": "release-status-eligibility",
    "renderer-attempt-v1": "renderer-attempt",
    "renderer-execution-v1": "renderer-execution",
    "public-source-v1": "public-source",
    "public-render-v1": "public-render",
}
PRODUCT_KMS_SIGNER_PURPOSE_ROLES = {
    purpose: role
    for purpose, role in PRODUCT_TRUST_PURPOSE_ROLES.items()
    if purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE
}


def expected_workload_identity(purpose: str, consumer_id: str | None) -> str:
    if purpose in PRODUCT_KMS_SIGNER_PURPOSE_ROLES:
        require(
            consumer_id is None,
            f"product role cannot be consumer-scoped: {purpose}",
        )
        return (
            "spiffe://bytedesk.ai/agent-delivery/"
            + PRODUCT_KMS_SIGNER_PURPOSE_ROLES[purpose]
        )
    require(
        purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "contract-bundle release identity is keyless-only",
    )
    workload_role = {
        "consumer-authority-v1": "governance-authority-signer",
        "consumer-private-skill-v1": "private-skill-publisher",
        "consumer-compilation-input-v1": "compilation-lock-coordinator",
        "consumer-deployment-v1": "deployment-signer",
        "consumer-compilation-evidence-v1": "compilation-attestor",
        "consumer-runtime-release-v1": "runtime-release-signer",
        "consumer-release-status-eligibility-v1": "release-status-eligibility-attestor",
        "consumer-activation-authorization-v1": "activation-authorization-coordinator",
    }[purpose]
    require(
        consumer_id is not None,
        f"consumer role requires a consumer id: {purpose}",
    )
    return (
        f"consumer:{consumer_id}:agent-delivery:{workload_role}"
    )


def expected_public_key_digest(
    purpose: str, consumer_id: str | None
) -> str:
    return canonical_digest(
        {
            "profile": "bytedesk.fixture-public-key/1",
            "purpose": purpose,
            "consumerId": consumer_id,
        }
    )


def expected_signer_claims(
    purpose: str, consumer_id: str | None
) -> dict[str, str]:
    workload_identity = expected_workload_identity(purpose, consumer_id)
    builder_digest = canonical_digest(
        {
            "profile": "bytedesk.fixture-policy-builder/1",
            "purpose": purpose,
            "consumerId": consumer_id,
        }
    )
    if consumer_id is None:
        return {
            "issuer": "https://token.actions.githubusercontent.com",
            "audience": f"agent-delivery-{purpose}",
            "subject": (
                "repo:ByteDeskAI/bytedesk-agent-delivery:environment:"
                f"{purpose}"
            ),
            "repository": "ByteDeskAI/bytedesk-agent-delivery",
            "workflow": f".github/workflows/{purpose}.yml",
            "ref": "refs/tags/v1.0.0",
            "environment": purpose,
            "builderDigest": builder_digest,
        }
    return {
        "issuer": "https://identity.example/consumers",
        "audience": f"agent-delivery-{purpose}",
        "subject": workload_identity,
        "repository": "ByteDeskAI/bytedesk-agent-delivery",
        "workflow": f".github/workflows/consumer-{purpose}.yml",
        "ref": "refs/tags/v1.0.0",
        "environment": f"{consumer_id}-{purpose}",
        "builderDigest": builder_digest,
    }


def authenticated_signer(
    purpose: str, consumer_id: str | None
) -> dict[str, Any]:
    require(
        purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "contract-bundle release identity is keyless-only",
    )
    key_scope = consumer_id or "product"
    return {
        "purpose": purpose,
        "credentialKind": "kms_key",
        "keyVersion": f"kms://{key_scope}/{purpose}/versions/1",
        "publicKeyDigest": expected_public_key_digest(purpose, consumer_id),
        "algorithm": "ECDSA_P256_SHA256",
        "workloadIdentity": expected_workload_identity(purpose, consumer_id),
        "claims": expected_signer_claims(purpose, consumer_id),
    }


def trust_policy(purpose: str, consumer_id: str | None = None) -> dict[str, str]:
    require(
        purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "contract-bundle trust policy must be imported from keyless authority",
    )
    key_scope = consumer_id or "product"
    workload_identity = expected_workload_identity(purpose, consumer_id)
    repository_scope = {
        "consumer-authority-v1": [
            "registry.example/consumer/authority",
            "registry.example/consumer/approvals",
            "registry.example/consumer/bindings",
            "registry.example/consumer/candidates",
        ],
        "public-source-v1": [
            "registry.example/public/sources",
            "registry.example/public/skills",
            "registry.example/public/evidence",
            "registry.example/public/layers",
            "registry.example/public/source-layers",
        ],
        "public-render-v1": [
            "registry.example/public/renders",
            "registry.example/public/evidence",
            "registry.example/public/layers",
            "registry.example/public/render-layers",
        ],
        "consumer-private-skill-v1": [
            "registry.example/consumer/skills",
            "registry.example/consumer/evidence",
            "registry.example/consumer/layers",
        ],
        "consumer-compilation-input-v1": [
            "registry.example/consumer/compilation-inputs"
        ],
        "consumer-deployment-v1": [
            "registry.example/consumer/deployments",
            "registry.example/consumer/render-payloads",
        ],
        "consumer-compilation-evidence-v1": [
            "registry.example/consumer/compilation-evidence"
        ],
        "consumer-runtime-release-v1": [
            "registry.example/consumer/runtime-releases"
        ],
        "consumer-release-status-eligibility-v1": [
            "registry.example/consumer/status-eligibility"
        ],
        "consumer-activation-authorization-v1": [
            "registry.example/consumer/activation-authorizations"
        ],
        "renderer-attempt-v1": [
            "registry.example/product/renderer-attempt-evidence",
            "registry.example/product/renderer-selections",
        ],
        "renderer-execution-v1": [
            "registry.example/product/renderer-execution-evidence"
        ],
    }[purpose]
    media_type_scope = {
        "consumer-authority-v1": [
            "application/vnd.bytedesk.agent.consumer-authority.v1+json",
            "application/vnd.bytedesk.agent.skill-approval.v1+json",
            "application/vnd.bytedesk.agent.binding.v1+json",
            "application/vnd.bytedesk.agent.candidate.v1+json",
        ],
        "public-source-v1": [
            "application/vnd.bytedesk.agent.source.v1+json",
            "application/vnd.bytedesk.agent.skill.v1+json",
            "application/vnd.bytedesk.agent.public-source-authentication-evidence.v1+json",
            "application/vnd.oci.image.layer.v1.tar",
            "application/spdx+json",
            "application/vnd.bytedesk.scan.v1+json",
            "application/vnd.bytedesk.license.v1+json",
            "application/vnd.bytedesk.agent.policy.v1+json",
        ],
        "public-render-v1": [
            "application/vnd.bytedesk.agent.render.v1+json",
            "application/vnd.bytedesk.agent.render-manifest.v1+json",
            "application/vnd.bytedesk.agent.compatibility.v1+json",
            RENDER_PAYLOAD_MEDIA_TYPE,
            "application/vnd.oci.image.layer.v1.tar",
            "application/vnd.oci.image.layer.v1.tar+gzip",
        ],
        "consumer-private-skill-v1": [
            "application/vnd.bytedesk.agent.skill.v1+json",
            "application/vnd.oci.image.layer.v1.tar",
            "application/spdx+json",
            "application/vnd.bytedesk.scan.v1+json",
            "application/vnd.bytedesk.license.v1+json",
        ],
        "consumer-compilation-input-v1": [
            PRIVATE_INPUT_MEDIA_TYPE,
            PRIVATE_INPUT_AUTHENTICATION_MEDIA_TYPE,
        ],
        "consumer-deployment-v1": [
            DEPLOYMENT_MEDIA_TYPE,
            RENDER_PAYLOAD_MEDIA_TYPE,
            "application/vnd.dev.sigstore.bundle.v0.3+json",
        ],
        "consumer-compilation-evidence-v1": [
            COMPILATION_EVIDENCE_MEDIA_TYPE,
            COMPILATION_STATEMENT_MEDIA_TYPE,
            "application/vnd.dev.sigstore.bundle.v0.3+json",
        ],
        "consumer-runtime-release-v1": [
            RUNTIME_RELEASE_MEDIA_TYPE,
            RUNTIME_RELEASE_STATEMENT_MEDIA_TYPE,
        ],
        "consumer-release-status-eligibility-v1": [
            STATUS_ELIGIBILITY_MEDIA_TYPE,
            STATUS_ELIGIBILITY_DIGEST_MEDIA_TYPE,
        ],
        "consumer-activation-authorization-v1": [
            ACTIVATION_AUTHORIZATION_MEDIA_TYPE,
            ACTIVATION_AUTHORIZATION_STATEMENT_MEDIA_TYPE,
        ],
        "renderer-attempt-v1": [
            "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
            "application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json",
            "application/vnd.bytedesk.agent.renderer-selection.v1+json",
            "application/vnd.dev.sigstore.bundle.v0.3+json",
        ],
        "renderer-execution-v1": [
            "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
            "application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json",
            SIGNATURE_BUNDLE_MEDIA_TYPE,
        ],
    }[purpose]
    for evidence_media_type in (
        SIGNING_RESULT_MEDIA_TYPE,
        SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        SIGNATURE_BUNDLE_MEDIA_TYPE,
    ):
        if evidence_media_type not in media_type_scope:
            media_type_scope.append(evidence_media_type)
    policy: dict[str, Any] = {
        "contract": "bytedesk.trust-policy/1",
        "schema": schema_descriptor("trust-policy"),
        "policyId": purpose,
        "version": "1.0.0",
        "effective": {
            "notBefore": "2026-07-17T00:00:00Z",
            "notAfter": "2027-07-17T00:00:00Z",
        },
        "scope": {
            "repositories": repository_scope,
            "mediaTypes": media_type_scope,
            "purposes": [purpose],
        },
        "signers": [
            {
                "purpose": purpose,
                "credentialKind": "kms_key",
                "keyVersion": f"kms://{key_scope}/{purpose}/versions/1",
                "publicKeyDigest": expected_public_key_digest(
                    purpose, consumer_id
                ),
                "algorithm": "ECDSA_P256_SHA256",
                "workloadIdentity": (
                    workload_identity
                ),
                "claims": expected_signer_claims(purpose, consumer_id),
            }
        ],
        "requiredEvidence": (
            [
                "schema",
                "provenance",
                "sbom",
                "vulnerability",
                "license",
                "malware",
                "secret_scan",
                "scan_completeness",
            ]
            if purpose in {"public-source-v1", "consumer-private-skill-v1"}
            else (
                ["schema", "authority"]
                if consumer_id is not None
                else ["schema", "provenance"]
            )
        ),
        "rules": {
            "freshnessSeconds": 900,
            "requireNonce": True,
            "requirePredecessor": True,
            "denyDowngrade": True,
            "withdrawal": "deny_new_use",
            "outage": "fail_closed_new_work",
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
        "failureMode": "fail_closed",
        "predecessor": {"kind": "none"},
    }
    if consumer_id is not None:
        policy["scope"]["consumers"] = [consumer_id]
    payload = canonical_bytes(policy)
    return {"id": purpose, "digest": register_cas_payload(payload)}


def descriptor_for_bytes(
    repository: str,
    media_type: str,
    payload: bytes,
    policy: dict[str, str],
) -> dict[str, Any]:
    return {
        "repository": repository,
        "digest": register_cas_payload(payload),
        "mediaType": media_type,
        "size": len(payload),
        "trustPolicy": deepcopy(policy),
    }


def blob_path(digest: str) -> Path:
    require(digest.startswith("sha256:"), f"unsupported digest: {digest}")
    return CAS_ROOT / digest.removeprefix("sha256:")


def domain_digest(
    profile: str,
    value: dict[str, Any],
    excluded: set[str],
) -> str:
    return canonical_digest(
        {
            "profile": profile,
            **{key: deepcopy(member) for key, member in value.items() if key not in excluded},
        }
    )


def customization_preimage(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": "bytedesk.functional-customization-digest/1",
        "agentSpec": binding["customization"]["agentSpec"],
        "harnessConfiguration": binding["customization"]["harnessConfiguration"],
        "files": binding["customization"]["files"],
        "skills": binding["customization"]["skills"],
    }


def input_parameters_preimage(
    binding: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.renderer-framed-input-parameters/1",
        "source": binding["source"],
        "sourceKind": binding["sourceKind"],
        "agentSpecVersion": binding["agentSpecVersion"],
        "agentSpecCustomization": binding["customization"]["agentSpec"],
        "fileCustomization": binding["customization"]["files"],
        "skillCustomization": binding["customization"]["skills"],
        "effectiveSkillSet": inputs["effectiveSkillSet"],
    }


def harness_configuration_preimage(
    binding: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.renderer-framed-harness-configuration/1",
        "harnessId": inputs["harnessId"],
        "renderer": binding["renderer"],
        "customization": binding["customization"]["harnessConfiguration"],
    }


def renderer_portable_definition(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": deepcopy(manifest["source"]),
        "sourceKind": manifest["sourceKind"],
        "agentSpecVersion": manifest["agentSpecVersion"],
    }


def renderer_functional_inputs(
    manifest: dict[str, Any],
    binding: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "scope": manifest["scope"],
        "source": deepcopy(manifest["source"]),
        "sourceKind": manifest["sourceKind"],
        "agentSpecVersion": manifest["agentSpecVersion"],
        "bindingDigest": manifest["bindingDigest"],
        "customizationDigest": manifest["customizationDigest"],
        "publicSkills": deepcopy(manifest["publicSkills"]),
        "privateSkills": deepcopy(manifest["privateSkills"]),
        "inputParameters": input_parameters_preimage(binding, inputs),
        "harnessConfiguration": harness_configuration_preimage(binding, inputs),
        "normalizationProfile": manifest["normalizationProfile"],
        "outputArchiveProfile": manifest["outputArchiveProfile"],
    }


def renderer_request_frame_document(
    selection: dict[str, Any],
    portable_definition: dict[str, Any],
    portable_definition_digest: str,
    functional_inputs: dict[str, Any],
    input_tree_digest: str,
    contract_bundle_digest: str,
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.renderer-production-request-frame/1",
        "rendererSelection": deepcopy(selection),
        "portableDefinition": deepcopy(portable_definition),
        "portableDefinitionDigest": portable_definition_digest,
        "functionalInputs": deepcopy(functional_inputs),
        "inputTreeDigest": input_tree_digest,
        "contractBundleDigest": contract_bundle_digest,
    }


def renderer_response_frame_document(
    attempt: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.renderer-production-response-frame/1",
        "attemptId": attempt["attemptId"],
        "attemptFencingToken": attempt["attemptFencingToken"],
        "compatibility": deepcopy(manifest["compatibility"]),
        "renderManifest": deepcopy(manifest),
        "result": "succeeded",
    }


def framed_jcs(value: dict[str, Any]) -> bytes:
    payload = canonical_bytes(value)
    require(
        len(payload) <= RENDERER_FRAME_MAX_PAYLOAD_BYTES,
        "renderer frame exceeds 4 MiB",
    )
    return len(payload).to_bytes(4, "big") + payload


def add_minutes(value: str, minutes: int) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, f"timestamp has no timezone: {value}")
    result = parsed.astimezone(timezone.utc) + timedelta(minutes=minutes)
    return result.isoformat(timespec="seconds").replace("+00:00", "Z")


def signing_result(
    purpose: str,
    subject_digest: str,
    subject_media_type: str,
    consumer_id: str | None,
    repository: str,
    signed_at: str,
    pin_set: dict[str, Any],
    policy_ref: dict[str, str] | None = None,
) -> dict[str, Any]:
    require(
        purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE
        and subject_media_type not in CONTRACT_BUNDLE_MEDIA_TYPES,
        "KMS signing cannot sign contract-bundle authority",
    )
    policy = deepcopy(policy_ref) if policy_ref is not None else trust_policy(
        purpose, consumer_id
    )
    policy_document = json.loads(CAS_PAYLOADS[policy["digest"]])
    permitted_kms_signers = [
        signer
        for signer in policy_document["signers"]
        if signer.get("purpose") == purpose
        and signer.get("credentialKind") == "kms_key"
    ]
    require(
        policy_document["policyId"] == purpose
        and len(permitted_kms_signers) == 1,
        f"signing policy does not resolve one {purpose} signer",
    )
    request_id = (
        f"{purpose}-request-"
        f"{subject_digest.removeprefix('sha256:')[:24]}"
    )
    signer = deepcopy(permitted_kms_signers[0])
    key_version = signer["keyVersion"]
    algorithm = signer["algorithm"]
    public_key_digest = signer["publicKeyDigest"]
    request_preimage = {
        "profile": "bytedesk.fixture-signing-request/1",
        "requestId": request_id,
        "purpose": purpose,
        "consumerId": consumer_id,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "algorithm": algorithm,
        "keyVersion": key_version,
        "publicKeyDigest": public_key_digest,
        "repository": repository,
        "trustPolicy": policy,
    }
    request_digest = canonical_digest(request_preimage)
    provider_evidence = build_signer_authentication_evidence(
        schema_descriptor=schema_descriptor("signer-authentication-evidence"),
        purpose=purpose,
        subject_media_type=subject_media_type,
        request_id=request_id,
        request_digest=request_digest,
        provider_request_id=f"fixture-kms-request:{request_id}",
        provider_audit_id=f"fixture-kms-audit:{request_id}",
        authenticated_signer=signer,
        issued_at=signed_at,
        trust_policy=policy,
    )
    provider_evidence_descriptor = descriptor_for_bytes(
        repository,
        SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        canonical_bytes(provider_evidence),
        policy,
    )
    signature_statement = {
        "profile": "bytedesk.fixture-authenticated-signature-statement/1",
        "requestId": request_id,
        "requestDigest": request_digest,
        "purpose": purpose,
        "consumerId": consumer_id,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "algorithm": algorithm,
        "keyVersion": key_version,
        "publicKeyDigest": public_key_digest,
        "repository": repository,
        "trustPolicy": policy,
        "providerAuditEvidence": deepcopy(provider_evidence_descriptor),
        "authenticatedSigner": deepcopy(signer),
        "signedAt": signed_at,
    }
    signature_payload = canonical_bytes(
        {
            "profile": "bytedesk.test-only-kms-adapter-bundle/1",
            "statement": signature_statement,
            "fixtureStatementChecksum": canonical_digest(
                {
                    "profile": "bytedesk.test-only-kms-statement-checksum/1",
                    "statement": signature_statement,
                }
            ),
        }
    )
    result: dict[str, Any] = {
        "contract": "bytedesk.signing-result/1",
        "schema": schema_descriptor("signing-result"),
        "requestId": request_id,
        "requestDigest": request_digest,
        "purpose": purpose,
        "keyVersion": key_version,
        "algorithm": algorithm,
        "publicKeyDigest": public_key_digest,
        "repository": repository,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "signatureBundle": descriptor_for_bytes(
            repository,
            SIGNATURE_BUNDLE_MEDIA_TYPE,
            signature_payload,
            policy,
        ),
        "trustPolicy": deepcopy(policy),
        "providerAuditEvidence": provider_evidence_descriptor,
        "signedAt": signed_at,
    }
    if consumer_id is not None:
        result["consumerId"] = consumer_id
    SIGNATURE_VERIFICATION_VECTORS.append(
        signature_verification_vector(
            vector_id=(
                "private-"
                + purpose
                + "-"
                + subject_digest.removeprefix("sha256:")[:24]
            ),
            request_id=request_id,
            purpose=purpose,
            signature_bundle=result["signatureBundle"],
            subject_digest=subject_digest,
            subject_media_type=subject_media_type,
            key_version=key_version,
            public_key_digest=public_key_digest,
            algorithm=algorithm,
            trust_policy=policy,
            signing_repository=repository,
            pin_set_digest=pin_set["pinSetDigest"],
            consumer_id=consumer_id,
            provider_audit_evidence=provider_evidence_descriptor,
        )
    )
    return result


def build_payload(manifest: dict[str, Any]) -> bytes:
    payload_files = (
        (
            "agent.yaml",
            b"agentspec_version: 26.1.2\ncomponent_type: Agent\nname: finance-private\n",
            "0444",
            "generated",
            "runtime_read_only",
        ),
        (
            "skills/private/bin/analyze",
            b"#!/bin/sh\nprintf '%s\\n' 'approved private skill payload'\n",
            "0555",
            "private_skill",
            "runtime_executable",
        ),
    )
    stream = BytesIO()
    inventory: list[dict[str, Any]] = []
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for path, content, mode, origin, ownership_class in payload_files:
            info = tarfile.TarInfo(path)
            info.size = len(content)
            info.mode = int(mode, 8)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, BytesIO(content))
            inventory.append(
                {
                    "path": path,
                    "digest": raw_digest(content),
                    "size": len(content),
                    "mode": mode,
                    "origin": origin,
                    "ownershipClass": ownership_class,
                }
            )
    payload = stream.getvalue()
    manifest["files"] = inventory
    manifest["output"] = {
        "digest": raw_digest(payload),
        "treeDigest": canonical_digest(
            {"profile": "bytedesk.renderer-output-tree/1", "files": inventory}
        ),
        "size": len(payload),
        "expandedSize": sum(entry["size"] for entry in inventory),
        "fileCount": len(inventory),
        "mediaType": RENDER_PAYLOAD_MEDIA_TYPE,
        "archiveProfile": manifest["outputArchiveProfile"],
    }
    manifest["reproducibilityDigest"] = canonical_digest(
        {
            "profile": "bytedesk.renderer-reproducibility/1",
            "effectiveInputDigest": manifest["effectiveInputDigest"],
            "compatibilityDigest": canonical_digest(manifest["compatibility"]),
            "output": manifest["output"],
        }
    )
    return payload


def refresh_private_manifest(
    manifest: dict[str, Any],
    inputs: dict[str, Any],
    selection: dict[str, Any],
    capability: dict[str, Any],
) -> None:
    manifest["scope"] = "private"
    manifest["bindingDigest"] = inputs["binding"]["digest"]
    manifest["customizationDigest"] = inputs["customizationDigest"]
    manifest["publicSkills"] = deepcopy(inputs["effectiveSkillSet"]["publicSkills"])
    manifest["privateSkills"] = deepcopy(inputs["effectiveSkillSet"]["privateSkills"])
    manifest["effectiveSkillSetDigest"] = inputs["effectiveSkillSet"]["digest"]
    manifest["skillApprovals"] = [
        deepcopy(entry["approval"]) for entry in inputs["skillApprovals"]
    ]
    manifest["harnessId"] = inputs["harnessId"]
    manifest["rendererId"] = selection["rendererId"]
    manifest["rendererVersion"] = selection["rendererVersion"]
    manifest["productRelease"] = deepcopy(selection["productRelease"])
    manifest["rendererRelease"] = deepcopy(selection["rendererRelease"])
    manifest["executedDistribution"] = deepcopy(selection["executableDistribution"])
    manifest["platform"] = selection["targetPlatform"]
    manifest["productDistributionDigest"] = selection["productDistributionDigest"]
    manifest["compiledAllowlistDigest"] = selection["compiledAllowlistDigest"]
    manifest["rendererSchemas"] = sorted(
        (deepcopy(value) for value in selection["rendererSchemas"].values()),
        key=lambda value: value["id"].encode("utf-8"),
    )
    manifest["normalizationProfile"] = selection["normalizationProfile"]
    manifest["effectiveInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.renderer-effective-input/1",
            "scope": manifest["scope"],
            "source": manifest["source"],
            "sourceKind": manifest["sourceKind"],
            "agentSpecVersion": manifest["agentSpecVersion"],
            "bindingDigest": manifest["bindingDigest"],
            "customizationDigest": manifest["customizationDigest"],
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
    )
    compatibility = manifest["compatibility"]
    compatibility["scope"] = "private"
    compatibility["harnessId"] = inputs["harnessId"]
    compatibility["rendererId"] = selection["rendererId"]
    compatibility["rendererVersion"] = selection["rendererVersion"]
    compatibility["productRelease"] = deepcopy(selection["productRelease"])
    compatibility["rendererRelease"] = deepcopy(selection["rendererRelease"])
    compatibility["executedDistribution"] = deepcopy(
        selection["executableDistribution"]
    )
    compatibility["platform"] = selection["targetPlatform"]
    compatibility["productDistributionDigest"] = selection[
        "productDistributionDigest"
    ]
    compatibility["compiledAllowlistDigest"] = selection["compiledAllowlistDigest"]
    compatibility["rendererSchemas"] = deepcopy(manifest["rendererSchemas"])
    compatibility["normalizationProfile"] = selection["normalizationProfile"]
    compatibility["inputDigest"] = manifest["effectiveInputDigest"]
    compatibility["capabilityDigest"] = canonical_digest(capability)
    compatibility["capabilityCoverageDigest"] = capability["coverageDigest"]
    compatibility["coverageDigest"] = canonical_digest(
        {
            "profile": "bytedesk.renderer-compatibility-coverage/1",
            "capabilityDigest": compatibility["capabilityDigest"],
            "capabilityCoverageDigest": compatibility["capabilityCoverageDigest"],
            "inputDigest": compatibility["inputDigest"],
            "semanticResults": compatibility["semanticResults"],
        }
    )


def deployment_id(lock: dict[str, Any]) -> str:
    inputs = lock["inputs"]
    identity = canonical_digest(
        {
            "profile": "bytedesk.consumer-deployment-id/1",
            "consumerId": inputs["consumerId"],
            "subjectId": inputs["subjectId"],
            "targetId": inputs["targetId"],
            "candidateDigest": inputs["candidate"]["digest"],
            "desiredRevisionDigest": inputs["desiredRevision"]["digest"],
            "compilationInputDigest": lock["compilationInputDigest"],
        }
    )
    return f"deployment-{identity.removeprefix('sha256:')}"


def runtime_release_statement_preimage(
    runtime_release: dict[str, Any]
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.runtime-release-statement/1",
        "release": {
            key: deepcopy(value)
            for key, value in runtime_release.items()
            if key not in {"contract", "schema", "releaseDigest", "signingResult"}
        },
    }


def build_graph() -> tuple[dict[Path, bytes], dict[str, Any]]:
    CAS_PAYLOADS.clear()
    SIGNATURE_VERIFICATION_VECTORS.clear()
    renderer_expected = renderer_fixture_generator.expected_documents()
    renderer_cases = json.loads(
        renderer_expected[renderer_fixture_generator.CASE_PATH].decode("utf-8")
    )
    product_trust_policy_pin_set = deepcopy(
        renderer_cases["trustPolicyPinSet"]
    )
    renderer_policy_pins = product_trust_policy_pin_set["currentForNewUse"]
    renderer_signature_verification_vectors = renderer_cases[
        "signatureVerificationVectors"
    ]
    renderer_keyless_verification_vectors = renderer_cases[
        "keylessVerificationVectors"
    ]
    require(
        len(renderer_keyless_verification_vectors) == 1,
        "renderer contract-bundle keyless verification vector is not unique",
    )
    require(
        [entry["purpose"] for entry in renderer_policy_pins]
        == list(renderer_fixture_generator.PRODUCT_TRUST_PURPOSES),
        "renderer trust-policy pins are incomplete or unordered",
    )
    renderer_policy_pin_by_purpose = {
        entry["purpose"]: deepcopy(entry["trustPolicy"])
        for entry in renderer_policy_pins
    }

    def import_renderer_policy(purpose: str) -> dict[str, str]:
        policy_ref = deepcopy(renderer_policy_pin_by_purpose[purpose])
        policy_path = (
            renderer_fixture_generator.RENDERER_CAS_BLOB_ROOT
            / policy_ref["digest"].removeprefix("sha256:")
        )
        payload = renderer_expected[policy_path]
        require(
            register_cas_payload(payload) == policy_ref["digest"],
            f"renderer policy bytes differ from pin: {purpose}",
        )
        return policy_ref

    lock = load_json(LOCK_PATH)
    manifest = load_json(MANIFEST_PATH)
    # The renderer generator owns the product-release projection.  Consume its
    # prospective bytes rather than the possibly stale checked-in projection so
    # one coordinated renderer -> private generation reaches a true fixed point.
    product_release = json.loads(
        renderer_expected[renderer_fixture_generator.PRODUCT_RELEASE_PATH]
    )
    authority = load_json(CONSUMER_AUTHORITY_PATH)
    lock["schema"] = schema_descriptor("private-compilation-input")
    authority["schema"] = schema_descriptor("consumer-authority")
    inputs = lock["inputs"]
    require("runtimeSlot" in inputs and "activationMode" in inputs, "lock does not freeze runtime placement")
    # Private compilation happens after the public release-status heads used by
    # selection become effective.  Never backdate the operation to the source
    # fixture's older reproducibility timestamp.
    # Public catalog finalization completes at 12:00:06Z in the canonical
    # renderer fixture.  A private compilation can only consume that signed
    # artifact after it exists, so the consumer operation starts afterwards.
    epoch = "2026-07-17T12:00:10Z"
    inputs["reproducibleEpoch"] = epoch
    selection = json.loads(
        renderer_expected[
            renderer_fixture_generator.RENDERER_SELECTION_PATHS["hermes"]
        ]
    )
    capability = json.loads(renderer_expected[HERMES_CAPABILITY_PATH])
    renderer_release = json.loads(
        renderer_expected[
            renderer_fixture_generator.RENDERER_RELEASE_PATHS["hermes"]
        ]
    )
    capability_descriptor = renderer_release["capabilityManifest"]
    require(
        capability_descriptor["digest"] == canonical_digest(capability)
        and capability_descriptor["size"] == len(canonical_bytes(capability))
        and capability["coverageDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.renderer-capability-coverage/1",
                "semanticRegistry": capability["semanticRegistry"],
                "semantics": capability["semantics"],
            }
        )
        and capability["harnessId"] == selection["targetHarness"]
        and capability["rendererId"] == selection["rendererId"]
        and capability["rendererVersion"] == selection["rendererVersion"]
        and selection["targetPlatform"] in capability["supportedPlatforms"]
        and "private" in capability["supportedScopes"],
        "private compatibility capability is not the selected renderer capability",
    )
    inputs["rendererSelection"] = selection
    inputs["rendererSelectionDigest"] = selection["selectionDigest"]
    require(
        selection["selectionDigest"]
        == canonical_digest(renderer_selection_preimage(selection)),
        "private lock renderer selection digest is not authoritative",
    )
    require(
        manifest["scope"] == "private"
        and manifest["harnessId"] == inputs["harnessId"]
        and selection["targetHarness"] == inputs["harnessId"],
        "private lock, selection, and render harness differ",
    )
    consumer_id = inputs["consumerId"]
    inputs["desiredRevision"]["digest"] = canonical_digest(
        {
            "profile": "bytedesk.fixture-desired-revision/1",
            "consumerId": consumer_id,
            "targetId": inputs["targetId"],
            "revision": inputs["desiredRevision"]["revision"],
        }
    )
    inputs["predecessor"]["digest"] = canonical_digest(
        {
            "profile": "bytedesk.fixture-predecessor/1",
            "consumerId": consumer_id,
            "targetId": inputs["targetId"],
            "revision": inputs["predecessor"]["revision"],
        }
    )
    inputs["policyDigests"] = {
        key: canonical_digest(
            {
                "profile": "bytedesk.fixture-opaque-consumer-policy/1",
                "consumerId": consumer_id,
                "targetId": inputs["targetId"],
                "policyClass": key,
            }
        )
        for key in (
            "policy",
            "grantSet",
            "credentialSet",
            "workloadIdentity",
            "lifecycle",
            "mandatorySandbox",
            "network",
            "approvalPolicy",
            "targetBinding",
        )
    }
    authority_policy = trust_policy("consumer-authority-v1", consumer_id)
    input_policy = trust_policy("consumer-compilation-input-v1", consumer_id)
    deployment_policy = trust_policy("consumer-deployment-v1", consumer_id)
    evidence_policy = trust_policy("consumer-compilation-evidence-v1", consumer_id)
    runtime_release_policy = trust_policy(
        "consumer-runtime-release-v1", consumer_id
    )
    public_source_policy = import_renderer_policy("public-source-v1")
    public_render_policy = import_renderer_policy("public-render-v1")
    contract_bundle_release_policy = import_renderer_policy(
        CONTRACT_BUNDLE_RELEASE_PURPOSE
    )
    require(
        contract_bundle_release_policy
        == product_release["contractBundleVerification"]["trustPolicy"]
        == product_release["contractBundle"]["trustPolicy"],
        "product contract-bundle keyless policy is not imported exactly",
    )
    release_status_policy = import_renderer_policy("release-status-v1")
    release_status_head_policy = import_renderer_policy(
        "release-status-head-v1"
    )
    renderer_attempt_policy = import_renderer_policy("renderer-attempt-v1")
    renderer_execution_policy = import_renderer_policy(
        "renderer-execution-v1"
    )
    private_skill_policy = trust_policy("consumer-private-skill-v1", consumer_id)
    status_eligibility_policy = trust_policy(
        "consumer-release-status-eligibility-v1", consumer_id
    )
    activation_authorization_policy = trust_policy(
        "consumer-activation-authorization-v1", consumer_id
    )
    consumer_policy_references = {
        purpose: policy_reference
        for purpose, policy_reference in (
            ("consumer-authority-v1", authority_policy),
            ("consumer-private-skill-v1", private_skill_policy),
            ("consumer-compilation-input-v1", input_policy),
            ("consumer-deployment-v1", deployment_policy),
            ("consumer-compilation-evidence-v1", evidence_policy),
            ("consumer-runtime-release-v1", runtime_release_policy),
            (
                "consumer-release-status-eligibility-v1",
                status_eligibility_policy,
            ),
            (
                "consumer-activation-authorization-v1",
                activation_authorization_policy,
            ),
        )
    }
    consumer_trust_policy_pin_set = build_initial_trust_policy_pin_set(
        schema_descriptor=schema_descriptor("trust-policy-pin-set"),
        pin_set_id=f"{consumer_id}-agent-delivery-v1",
        scope="consumer",
        consumer_id=consumer_id,
        purposes=consumer_policy_references,
        trust_policy_references=consumer_policy_references,
        not_before="2026-07-17T00:00:00Z",
        not_after="2027-07-17T00:00:00Z",
    )

    def pin_set_provider_binding(
        pin_set: dict[str, Any], repository: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        scope_token = pin_set["consumerId"] or "product"
        provider_id = f"{scope_token}-trust-policy-provider"
        provider_authority_digest = canonical_digest(
            {
                "profile": "bytedesk.fixture-trust-policy-provider-authority/1",
                "providerId": provider_id,
                "consumerId": pin_set["consumerId"],
            }
        )
        pin_set_descriptor = pin_set_document_descriptor(
            repository=repository,
            pin_set=pin_set,
            provider_id=provider_id,
            provider_authority_digest=provider_authority_digest,
        )
        pin_set_payload = canonical_bytes(pin_set)
        require(
            register_cas_payload(pin_set_payload)
            == pin_set_descriptor["digest"],
            f"pin-set descriptor bytes differ: {pin_set['pinSetId']}",
        )
        request_id = f"activate-{pin_set['pinSetId']}-revision-1"
        provider_request_id = f"provider-request-{pin_set['pinSetId']}-revision-1"
        provider_audit_id = f"provider-audit-{pin_set['pinSetId']}-revision-1"
        evidence = build_pin_set_provider_evidence(
            schema_descriptor=schema_descriptor(
                "trust-policy-pin-set-provider-evidence"
            ),
            evidence_id=f"{pin_set['pinSetId']}-provider-evidence-revision-1",
            request_id=request_id,
            idempotency_key=f"{pin_set['pinSetId']}-revision-1",
            pin_set=pin_set,
            pin_set_descriptor=pin_set_descriptor,
            provider_request_id=provider_request_id,
            provider_audit_id=provider_audit_id,
            activated_at=add_minutes(epoch, -20),
            observed_at=add_minutes(epoch, -19),
        )
        vector = pin_set_provider_authentication_vector(
            vector_id=f"{pin_set['pinSetId']}-provider-vector-revision-1",
            provider_id=provider_id,
            provider_authority_digest=provider_authority_digest,
            provider_request_id=provider_request_id,
            provider_audit_id=provider_audit_id,
            request_digest=evidence["requestDigest"],
            pin_set_digest_value=pin_set["pinSetDigest"],
        )
        return (
            {
                "pinSet": deepcopy(pin_set),
                "pinSetDescriptor": pin_set_descriptor,
                "providerEvidence": evidence,
            },
            vector,
        )

    product_pin_set_binding, product_pin_set_provider_vector = (
        pin_set_provider_binding(
            product_trust_policy_pin_set,
            "registry.example/provider/product-trust-policy-pin-sets",
        )
    )
    consumer_pin_set_binding, consumer_pin_set_provider_vector = (
        pin_set_provider_binding(
            consumer_trust_policy_pin_set,
            "registry.example/provider/consumer-trust-policy-pin-sets",
        )
    )
    pin_set_provider_bindings = [
        product_pin_set_binding,
        consumer_pin_set_binding,
    ]
    pin_set_provider_authentication_vectors = sorted(
        [
            product_pin_set_provider_vector,
            consumer_pin_set_provider_vector,
        ],
        key=lambda vector: vector["vectorId"],
    )
    materialized_inputs: list[tuple[str, dict[str, Any], Path | None]] = []
    status_supporting_artifacts: list[
        tuple[str, dict[str, Any], Path | None]
    ] = []
    status_verification_payloads: list[tuple[str, str, bytes]] = []
    imported_renderer_payloads: dict[str, bytes] = {
        contract_bundle_release_policy["digest"]: CAS_PAYLOADS[
            contract_bundle_release_policy["digest"]
        ]
    }

    def materialize(
        role: str,
        repository: str,
        media_type: str,
        value: dict[str, Any] | bytes,
        policy: dict[str, str],
    ) -> dict[str, Any]:
        payload_value = canonical_bytes(value) if isinstance(value, dict) else value
        descriptor = descriptor_for_bytes(
            repository, media_type, payload_value, policy
        )
        materialized_inputs.append((role, descriptor, None))
        return descriptor

    def import_renderer_descriptor(
        descriptor: dict[str, Any], role: str, *, require_json: bool = True
    ) -> dict[str, Any] | None:
        path = (
            renderer_fixture_generator.RENDERER_CAS_BLOB_ROOT
            / descriptor["digest"].removeprefix("sha256:")
        )
        payload_bytes = renderer_expected.get(path)
        require(
            payload_bytes is not None
            and raw_digest(payload_bytes) == descriptor["digest"]
            and len(payload_bytes) == descriptor["size"],
            f"renderer artifact descriptor does not resolve exactly: {role}",
        )
        register_cas_payload(payload_bytes)
        imported_renderer_payloads.setdefault(
            descriptor["digest"], payload_bytes
        )
        if descriptor["mediaType"].endswith("+json"):
            document = json.loads(payload_bytes)

            def import_nested(value: Any, nested_role: str) -> None:
                if isinstance(value, list):
                    for index, item in enumerate(value):
                        import_nested(item, f"{nested_role}-{index}")
                elif isinstance(value, dict):
                    if {
                        "repository",
                        "digest",
                        "mediaType",
                        "size",
                    }.issubset(value):
                        import_renderer_descriptor(
                            value, nested_role, require_json=False
                        )
                    else:
                        for key, item in value.items():
                            import_nested(item, f"{nested_role}-{key}")

            import_nested(document, role)
            return document
        require(
            not require_json,
            f"renderer artifact is not JSON: {role}",
        )
        return None

    public_render_finalization = renderer_cases[
        "publicRenderFinalization"
    ]
    public_render_document = deepcopy(
        public_render_finalization["harnessRender"]
    )
    public_render_descriptor = deepcopy(
        public_render_finalization["harnessRenderDescriptor"]
    )
    resolved_public_render = import_renderer_descriptor(
        public_render_descriptor, "canonical-finalized-public-render"
    )
    require(
        resolved_public_render == public_render_document
        and public_render_document["authorityDigest"]
        == public_render_finalization["authorityDigest"],
        "canonical public render finalization differs from signed render",
    )
    source_descriptor = deepcopy(public_render_document["source"])
    import_renderer_descriptor(
        source_descriptor,
        "canonical-public-source",
        require_json=False,
    )
    public_skill = deepcopy(public_render_document["publicSkills"][0])
    import_renderer_descriptor(
        public_skill,
        "canonical-public-skill",
        require_json=False,
    )
    canonical_public_subjects = [source_descriptor, public_skill]
    canonical_public_authentication: list[
        tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = []
    authenticated_public_subjects: set[
        tuple[str, str, str]
    ] = set()
    for index, evidence_descriptor in enumerate(
        public_render_document["publicSourceAuthenticationEvidence"]
    ):
        evidence_document = import_renderer_descriptor(
            evidence_descriptor,
            f"canonical-public-source-authentication-{index:06d}",
        )
        require(
            evidence_document is not None
            and evidence_document.get("contract")
            == "bytedesk.public-source-authentication-evidence/1",
            "canonical public-source authentication evidence is invalid",
        )
        subject = evidence_document["subject"]
        subject_key = (
            subject["repository"],
            subject["digest"],
            subject["mediaType"],
        )
        require(
            subject in canonical_public_subjects
            and subject_key not in authenticated_public_subjects,
            "canonical public-source authentication coverage differs",
        )
        authenticated_public_subjects.add(subject_key)
        role = (
            "canonical-public-source"
            if subject == source_descriptor
            else f"canonical-public-skill-{index:06d}"
        )
        canonical_public_authentication.append(
            (
                role,
                deepcopy(subject),
                deepcopy(evidence_descriptor),
                deepcopy(evidence_document),
            )
        )
    require(
        authenticated_public_subjects
        == {
            (
                subject["repository"],
                subject["digest"],
                subject["mediaType"],
            )
            for subject in canonical_public_subjects
        },
        "canonical public-source authentication evidence is incomplete",
    )

    def skill_package(
        package_id: str,
        scope: str,
        policy: dict[str, str],
        repository_prefix: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        content = f"#!/bin/sh\nprintf '%s\\n' '{package_id}'\n".encode("utf-8")
        content_layer = materialize(
            f"{scope}-skill-content-layer",
            f"{repository_prefix}/layers",
            "application/vnd.oci.image.layer.v1.tar",
            content,
            policy,
        )
        evidence: dict[str, Any] = {}
        for name, media_type in (
            ("sbom", "application/spdx+json"),
            ("scan", "application/vnd.bytedesk.scan.v1+json"),
            ("license", "application/vnd.bytedesk.license.v1+json"),
        ):
            evidence[name] = materialize(
                f"{scope}-skill-{name}",
                f"{repository_prefix}/evidence",
                media_type,
                {
                    "profile": f"bytedesk.fixture-skill-{name}/1",
                    "packageId": package_id,
                    "contentDigest": content_layer["digest"],
                    "outcome": "permitted",
                },
                policy,
            )
        document = {
            "contract": "bytedesk.skill-package/1",
            "schema": schema_descriptor("skill-package"),
            "packageId": package_id,
            "version": "1.0.0",
            "scope": scope,
            "contentLayer": content_layer,
            "files": [
                {
                    "path": "bin/analyze",
                    "digest": raw_digest(content),
                    "size": len(content),
                    "mode": "0755",
                }
            ],
            "nestedArchiveDepth": 0,
            "evidence": evidence,
            "withdrawal": "active",
            "trustPolicy": policy,
        }
        if scope == "consumer-private":
            document["consumerId"] = consumer_id
        descriptor = materialize(
            f"{scope}-skill-package",
            f"{repository_prefix}/skills",
            "application/vnd.bytedesk.agent.skill.v1+json",
            document,
            policy,
        )
        return document, descriptor

    private_skill_document, private_skill = skill_package(
        "private-analysis-helper",
        "consumer-private",
        private_skill_policy,
        "registry.example/consumer",
    )
    binding_document = {
        "contract": "bytedesk.agent-binding/1",
        "schema": schema_descriptor("agent-binding"),
        "agentId": inputs["subjectId"],
        "agentSpecVersion": "26.1.2",
        "sourceKind": "agent",
        "source": source_descriptor,
        "renderer": {
            "harnessId": inputs["harnessId"],
            "rendererId": selection["rendererId"],
            "version": selection["rendererVersion"],
            "release": deepcopy(selection["rendererRelease"]),
        },
        "customization": {
            "agentSpec": {"profile": "bytedesk.json-patch/1", "operations": []},
            "harnessConfiguration": {
                "profile": "bytedesk.json-patch/1",
                "operations": [],
            },
            "files": {"contract": "bytedesk.file-operations/1", "operations": []},
            "skills": {"contract": "bytedesk.skill-operations/1", "operations": []},
        },
        "updatePolicy": {
            "channel": "pinned",
            "automaticCompatibleUpdates": False,
        },
        "precondition": {"kind": "absent"},
    }
    binding_descriptor = materialize(
        "consumer-binding",
        "registry.example/consumer/bindings",
        "application/vnd.bytedesk.agent.binding.v1+json",
        binding_document,
        authority_policy,
    )
    candidate_document = {
        "contract": "bytedesk.candidate/1",
        "schema": schema_descriptor("candidate"),
        "candidateId": "candidate-private-01",
        "consumerId": consumer_id,
        "installationId": inputs["installationId"],
        "targetId": inputs["targetId"],
        "input": source_descriptor,
        "state": "approved",
        "attempt": 1,
        "revision": inputs["desiredRevision"]["revision"],
        "precondition": deepcopy(inputs["predecessor"]),
        "predecessor": deepcopy(inputs["predecessor"]),
        "createdAt": epoch,
        "updatedAt": epoch,
    }
    candidate_descriptor = materialize(
        "consumer-candidate",
        "registry.example/consumer/candidates",
        "application/vnd.bytedesk.agent.candidate.v1+json",
        candidate_document,
        authority_policy,
    )
    public_skill_document = {
        "packageId": (
            "public-skill-"
            + public_skill["digest"].removeprefix("sha256:")[:24]
        ),
        "evidence": {
            evidence_class: {
                "digest": canonical_digest(
                    {
                        "profile": (
                            "bytedesk.public-skill-review-evidence/1"
                        ),
                        "evidenceClass": evidence_class,
                        "skill": public_skill,
                        "publicRender": public_render_descriptor,
                    }
                )
            }
            for evidence_class in ("scan", "sbom", "license")
        },
    }
    approval_entries = []
    for skill_document, skill_descriptor in (
        (public_skill_document, public_skill),
        (private_skill_document, private_skill),
    ):
        approval_document = {
            "contract": "bytedesk.skill-approval/1",
            "schema": schema_descriptor("skill-approval"),
            "packageId": skill_document["packageId"],
            "skill": skill_descriptor,
            "consumerId": consumer_id,
            "subjectId": inputs["subjectId"],
            "installationId": inputs["installationId"],
            "targetClass": "hosted-hermes",
            "useScope": {
                "target": {"kind": "exact_target", "targetId": inputs["targetId"]},
                "harnesses": [inputs["harnessId"]],
                "operations": ["compile", "activate", "runtime_execute"],
            },
            "evidenceDigests": {
                "scan": skill_document["evidence"]["scan"]["digest"],
                "sbom": skill_document["evidence"]["sbom"]["digest"],
                "license": skill_document["evidence"]["license"]["digest"],
                "evaluation": canonical_digest(
                    {
                        "profile": "bytedesk.fixture-skill-evaluation/1",
                        "skillDigest": skill_descriptor["digest"],
                    }
                ),
                "riskDecision": canonical_digest(
                    {
                        "profile": "bytedesk.fixture-skill-risk-decision/1",
                        "skillDigest": skill_descriptor["digest"],
                    }
                ),
            },
            "approvalPolicy": authority_policy,
            "approverClass": "consumer-security-reviewer",
            "decisionReference": (
                f"approval://{consumer_id}/skills/{skill_document['packageId']}/1"
            ),
            "issuedAt": add_minutes(epoch, -5),
            "expiresAt": add_minutes(epoch, 30),
            "revocation": {"status": "active"},
            "signerPolicy": authority_policy,
        }
        approval_descriptor = materialize(
            f"skill-approval-{skill_document['packageId']}",
            "registry.example/consumer/approvals",
            "application/vnd.bytedesk.agent.skill-approval.v1+json",
            approval_document,
            authority_policy,
        )
        approval_entries.append(
            {"skill": skill_descriptor, "approval": approval_descriptor}
        )
    approval_entries.sort(
        key=lambda entry: (
            entry["skill"]["repository"].encode("utf-8"),
            entry["skill"]["digest"],
        )
    )
    inputs["candidate"] = candidate_descriptor
    inputs["binding"] = binding_descriptor
    inputs["publicArtifact"] = public_render_descriptor
    inputs["contractBundle"] = deepcopy(product_release["contractBundle"])
    inputs["effectiveSkillSet"] = {
        "publicSkills": [public_skill],
        "privateSkills": [private_skill],
        "digest": canonical_digest(
            {
                "profile": "bytedesk.renderer-effective-skill-set/1",
                "publicSkills": [public_skill],
                "privateSkills": [private_skill],
            }
        ),
    }
    inputs["skillApprovals"] = approval_entries
    inputs["customizationDigest"] = canonical_digest(
        customization_preimage(binding_document)
    )
    manifest["source"] = deepcopy(source_descriptor)
    manifest["sourceKind"] = binding_document["sourceKind"]
    manifest["agentSpecVersion"] = binding_document["agentSpecVersion"]
    manifest["inputParametersDigest"] = canonical_digest(
        input_parameters_preimage(binding_document, inputs)
    )
    manifest["harnessConfigurationDigest"] = canonical_digest(
        harness_configuration_preimage(binding_document, inputs)
    )

    status_payloads_before = set(CAS_PAYLOADS)

    def renderer_named_document(path: Path) -> dict[str, Any]:
        payload_bytes = renderer_expected.get(path)
        require(payload_bytes is not None, f"missing renderer document: {path}")
        return json.loads(payload_bytes)

    product_current_status = import_renderer_descriptor(
        selection["productReleaseStatus"], "product-current-status"
    )
    renderer_current_status = import_renderer_descriptor(
        selection["rendererReleaseStatus"], "hermes-current-status"
    )
    product_prior_checkpoint = import_renderer_descriptor(
        selection["productReleaseStatusCheckpoint"],
        "product-selection-status-checkpoint",
    )
    renderer_prior_checkpoint = import_renderer_descriptor(
        selection["rendererReleaseStatusCheckpoint"],
        "hermes-selection-status-checkpoint",
    )
    import_renderer_descriptor(
        selection["productReleaseStatusCheckpointAuthenticationEvidence"],
        "product-selection-status-checkpoint-authentication",
    )
    import_renderer_descriptor(
        selection["rendererReleaseStatusCheckpointAuthenticationEvidence"],
        "hermes-selection-status-checkpoint-authentication",
    )

    product_initial_status = renderer_named_document(
        renderer_fixture_generator.RENDERER_CAS_ROOT
        / "product-release-status-sequence-1.json"
    )
    product_intermediate_status = renderer_named_document(
        renderer_fixture_generator.RENDERER_CAS_ROOT
        / "product-release-status-sequence-2.json"
    )
    product_initial_status_descriptor = descriptor_for_bytes(
        "registry.example/product/status",
        "application/vnd.bytedesk.agent.release-status.v1+json",
        canonical_bytes(product_initial_status),
        release_status_policy,
    )
    product_intermediate_status_descriptor = descriptor_for_bytes(
        "registry.example/product/status",
        "application/vnd.bytedesk.agent.release-status.v1+json",
        canonical_bytes(product_intermediate_status),
        release_status_policy,
    )
    product_status_leaves = [
        status_leaf_digest(
            subject_kind="product_release",
            subject=selection["productRelease"],
            sequence=product_initial_status["sequence"],
            epoch=1,
            head=product_initial_status_descriptor,
        ),
        status_leaf_digest(
            subject_kind="product_release",
            subject=selection["productRelease"],
            sequence=product_intermediate_status["sequence"],
            epoch=1,
            head=product_intermediate_status_descriptor,
        ),
        status_leaf_digest(
            subject_kind="product_release",
            subject=selection["productRelease"],
            sequence=product_current_status["sequence"],
            epoch=2,
            head=selection["productReleaseStatus"],
        ),
    ]
    renderer_status_leaves = [
        status_leaf_digest(
            subject_kind="renderer_release",
            subject=selection["rendererRelease"],
            sequence=renderer_current_status["sequence"],
            epoch=1,
            head=selection["rendererReleaseStatus"],
        )
    ]

    status_documents: dict[str, dict[str, Any]] = {}

    def status_artifact_descriptor(
        repository: str,
        media_type: str,
        document: dict[str, Any],
        policy: dict[str, str],
    ) -> dict[str, Any]:
        return descriptor_for_bytes(
            repository, media_type, canonical_bytes(document), policy
        )

    def status_head_signer(purpose: str) -> dict[str, Any]:
        policy_document = json.loads(
            CAS_PAYLOADS[release_status_head_policy["digest"]]
        )
        signers = [
            signer
            for signer in policy_document["signers"]
            if signer["purpose"] == purpose
        ]
        require(len(signers) == 1, "status-head signer is not exact")
        return deepcopy(signers[0])

    status_signing_time = epoch

    def product_status_signing_result(
        purpose: str,
        subject_digest: str,
        subject_media_type: str,
        evidence_id: str,
        policy: dict[str, str],
        repository: str,
    ) -> dict[str, Any]:
        del evidence_id
        return signing_result(
            purpose,
            subject_digest,
            subject_media_type,
            None,
            repository,
            status_signing_time,
            pin_set=product_trust_policy_pin_set,
            policy_ref=policy,
        )

    def sign_status_inline_authority(
        document: dict[str, Any],
        schema_name: str,
        purpose: str,
        subject_media_type: str,
        evidence_id: str,
        policy: dict[str, str],
        repository: str,
    ) -> None:
        document["authorityDigest"] = "sha256:" + ("0" * 64)
        document["signingResult"] = {}
        document["authorityDigest"] = canonical_digest(
            inline_authority_preimage(
                document, load_json(SCHEMA_ROOT / f"{schema_name}.schema.json")
            )
        )
        document["signingResult"] = product_status_signing_result(
            purpose,
            document["authorityDigest"],
            subject_media_type,
            evidence_id,
            policy,
            repository,
        )

    status_head_builder = StatusHeadAuthorityBuilder(
        schema_descriptor=schema_descriptor,
        artifact_descriptor=status_artifact_descriptor,
        sign_inline_authority=sign_status_inline_authority,
        signing_result=product_status_signing_result,
        signer=status_head_signer,
        register_document=lambda document_id, document: status_documents.__setitem__(
            document_id, deepcopy(document)
        ),
        canonical_digest=canonical_digest,
        status_head_auth_schema=load_json(
            SCHEMA_ROOT
            / "release-status-head-authentication-evidence.schema.json"
        ),
        status_head_trust=release_status_head_policy,
    )
    product_compilation_head = status_head_builder.refresh(
        checkpoint_id="private-compilation-product-status-head",
        request_nonce="status_head_nonce_private_compile_product_0123456789abcdef",
        subject_kind="product_release",
        subject=selection["productRelease"],
        status=product_current_status,
        status_descriptor=selection["productReleaseStatus"],
        epoch=2,
        log_leaves=product_status_leaves,
        operation_time=epoch,
        expires_at=add_minutes(epoch, 5),
        prior_checkpoint=product_prior_checkpoint,
        prior_checkpoint_descriptor=selection[
            "productReleaseStatusCheckpoint"
        ],
    )
    renderer_compilation_head = status_head_builder.refresh(
        checkpoint_id="private-compilation-hermes-status-head",
        request_nonce="status_head_nonce_private_compile_hermes_0123456789abcdef",
        subject_kind="renderer_release",
        subject=selection["rendererRelease"],
        status=renderer_current_status,
        status_descriptor=selection["rendererReleaseStatus"],
        epoch=1,
        log_leaves=renderer_status_leaves,
        operation_time=epoch,
        expires_at=add_minutes(epoch, 5),
        prior_checkpoint=renderer_prior_checkpoint,
        prior_checkpoint_descriptor=selection[
            "rendererReleaseStatusCheckpoint"
        ],
    )

    def register_status_verification(
        role: str, verification_result: dict[str, Any]
    ) -> str:
        payload_bytes = canonical_bytes(verification_result)
        digest = register_cas_payload(payload_bytes)
        status_verification_payloads.append((role, digest, payload_bytes))
        return digest

    signature_adapter = TrustedKmsVerificationAdapter(
        [
            *deepcopy(renderer_signature_verification_vectors),
            *deepcopy(SIGNATURE_VERIFICATION_VECTORS),
        ]
    )

    def permitted_signature_verification(
        *,
        verification_id: str,
        result: dict[str, Any],
        generic_subject: dict[str, Any],
        expected_signed_digest: str,
        purpose: str,
        consumer: str | None,
        pin_set: dict[str, Any],
        verification_time: str,
    ) -> str:
        require(
            result["subjectDigest"] == expected_signed_digest,
            f"signed authority digest differs: {verification_id}",
        )
        policy_document = json.loads(
            CAS_PAYLOADS[result["trustPolicy"]["digest"]]
        )
        signers = [
            signer
            for signer in policy_document["signers"]
            if signer["purpose"] == purpose
            and signer.get("credentialKind") == "kms_key"
            and signer.get("keyVersion") == result["keyVersion"]
            and signer.get("publicKeyDigest") == result["publicKeyDigest"]
            and signer["algorithm"] == result["algorithm"]
        ]
        require(len(signers) == 1, f"signature signer differs: {verification_id}")
        detailed = signature_adapter.verify(
            result=result,
            policy=policy_document,
            permitted_signer=signers[0],
            verification_time=verification_time,
            expected_purpose=purpose,
            expected_subject_media_type=result["subjectMediaType"],
            expected_signing_repository=result["repository"],
            pin_set_digest=pin_set["pinSetDigest"],
            pin_set_revocations=pin_set["revocations"],
            expected_consumer_id=consumer,
        )
        verification = permitted_verification_result(
            schema_descriptor=schema_descriptor("verification-result"),
            verification_id=verification_id,
            subject=generic_subject,
            policy=result["trustPolicy"],
            evaluated_at=verification_time,
            evidence_digests=[detailed["verificationEvidenceDigest"]],
        )
        return register_status_verification(verification_id, verification)

    def status_entry(
        *,
        entry_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        built_head: dict[str, Any],
        harness_id: str | None = None,
        renderer_id: str | None = None,
        renderer_version: str | None = None,
        target_platform: str | None = None,
        operation_time: str,
    ) -> dict[str, Any]:
        checkpoint = built_head["checkpoint"]
        checkpoint_descriptor = built_head["checkpointDescriptor"]
        authentication = built_head["authentication"]
        inclusion = built_head["inclusionProof"]
        inclusion_descriptor = built_head["inclusionProofDescriptor"]
        status_verification_digest = permitted_signature_verification(
            verification_id=f"{entry_id}-status-signature",
            result=status["signingResult"],
            generic_subject=status_descriptor,
            expected_signed_digest=status["authorityDigest"],
            purpose="release-status-v1",
            consumer=None,
            pin_set=product_trust_policy_pin_set,
            verification_time=operation_time,
        )
        checkpoint_verification_digest = permitted_signature_verification(
            verification_id=f"{entry_id}-checkpoint-authentication",
            result=authentication["signingResult"],
            generic_subject=checkpoint_descriptor,
            expected_signed_digest=checkpoint_descriptor["digest"],
            purpose="release-status-head-v1",
            consumer=None,
            pin_set=product_trust_policy_pin_set,
            verification_time=operation_time,
        )
        require(
            verify_inclusion(
                leaf_digest=inclusion["leafDigest"],
                leaf_index=inclusion["leafIndex"],
                tree_size=inclusion["treeSize"],
                audit_path=inclusion["auditPath"],
                expected_root=inclusion["rootDigest"],
            ),
            f"status inclusion proof is invalid: {entry_id}",
        )
        inclusion_math = {
            "profile": "bytedesk.release-status-inclusion-verification/1",
            "algorithm": "bytedesk-rfc6962-inclusion-v1",
            "subject": deepcopy(subject),
            "status": deepcopy(status_descriptor),
            "checkpoint": deepcopy(checkpoint_descriptor),
            "proof": deepcopy(inclusion_descriptor),
            "leafDigest": inclusion["leafDigest"],
            "leafIndex": inclusion["leafIndex"],
            "treeSize": inclusion["treeSize"],
            "auditPath": deepcopy(inclusion["auditPath"]),
            "expectedRoot": inclusion["rootDigest"],
            "decision": "permitted",
        }
        inclusion_math_digest = register_cas_payload(
            canonical_bytes(inclusion_math)
        )
        inclusion_verification = permitted_verification_result(
            schema_descriptor=schema_descriptor("verification-result"),
            verification_id=f"{entry_id}-head-inclusion",
            subject=inclusion_descriptor,
            policy=release_status_head_policy,
            evaluated_at=operation_time,
            evidence_digests=[
                checkpoint_verification_digest,
                inclusion_math_digest,
            ],
        )
        inclusion_verification_digest = register_status_verification(
            f"{entry_id}-head-inclusion", inclusion_verification
        )
        consistency_descriptor = built_head["consistencyProofDescriptor"]
        consistency = built_head["consistencyProof"]
        consistency_verification_digest: str | None = None
        if consistency is not None:
            require(
                verify_consistency(
                    old_size=consistency["from"]["treeSize"],
                    new_size=consistency["to"]["treeSize"],
                    old_root=consistency["from"]["logRootDigest"],
                    new_root=consistency["to"]["logRootDigest"],
                    audit_path=consistency["auditPath"],
                ),
                f"status consistency proof is invalid: {entry_id}",
            )
            consistency_signature_digest = permitted_signature_verification(
                verification_id=f"{entry_id}-consistency-signature",
                result=consistency["signingResult"],
                generic_subject=consistency_descriptor,
                expected_signed_digest=consistency["authorityDigest"],
                purpose="release-status-head-v1",
                consumer=None,
                pin_set=product_trust_policy_pin_set,
                verification_time=operation_time,
            )
            consistency_math_digest = register_cas_payload(
                canonical_bytes(
                    {
                        "profile": "bytedesk.release-status-consistency-verification/1",
                        "algorithm": consistency["algorithm"],
                        "subject": deepcopy(subject),
                        "checkpoint": deepcopy(checkpoint_descriptor),
                        "proof": deepcopy(consistency_descriptor),
                        "from": deepcopy(consistency["from"]),
                        "to": deepcopy(consistency["to"]),
                        "auditPath": deepcopy(consistency["auditPath"]),
                        "decision": "permitted",
                    }
                )
            )
            consistency_verification_digest = register_status_verification(
                f"{entry_id}-consistency",
                permitted_verification_result(
                    schema_descriptor=schema_descriptor("verification-result"),
                    verification_id=f"{entry_id}-consistency",
                    subject=consistency_descriptor,
                    policy=release_status_head_policy,
                    evaluated_at=operation_time,
                    evidence_digests=[
                        checkpoint_verification_digest,
                        consistency_signature_digest,
                        consistency_math_digest,
                    ],
                ),
            )
        entry = {
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "status": deepcopy(status_descriptor),
            "statusDocument": deepcopy(status),
            "checkpoint": deepcopy(checkpoint_descriptor),
            "checkpointDocument": deepcopy(checkpoint),
            "checkpointAuthenticationEvidence": deepcopy(
                built_head["authenticationDescriptor"]
            ),
            "checkpointAuthenticationEvidenceDocument": deepcopy(
                authentication
            ),
            "requestNonce": checkpoint["requestNonce"],
            "clientPriorState": deepcopy(checkpoint["clientPriorState"]),
            "headInclusionProof": deepcopy(inclusion_descriptor),
            "headInclusionProofDocument": deepcopy(inclusion),
            "consistencyProof": deepcopy(consistency_descriptor),
            "consistencyProofDocument": deepcopy(consistency),
            "verificationEvidenceDigests": {
                "status": status_verification_digest,
                "checkpointAuthentication": checkpoint_verification_digest,
                "headInclusionProof": inclusion_verification_digest,
                "consistencyProof": consistency_verification_digest,
            },
        }
        if harness_id is not None:
            entry.update(
                {
                    "harnessId": harness_id,
                    "rendererId": renderer_id,
                    "rendererVersion": renderer_version,
                    "targetPlatform": target_platform,
                }
            )
        return entry

    product_eligibility_entry = status_entry(
        entry_id="private-compilation-product",
        subject_kind="product_release",
        subject=selection["productRelease"],
        status=product_current_status,
        status_descriptor=selection["productReleaseStatus"],
        built_head=product_compilation_head,
        operation_time=epoch,
    )
    renderer_eligibility_entry = status_entry(
        entry_id="private-compilation-hermes",
        subject_kind="renderer_release",
        subject=selection["rendererRelease"],
        status=renderer_current_status,
        status_descriptor=selection["rendererReleaseStatus"],
        built_head=renderer_compilation_head,
        harness_id=selection["targetHarness"],
        renderer_id=selection["rendererId"],
        renderer_version=selection["rendererVersion"],
        target_platform=selection["targetPlatform"],
        operation_time=epoch,
    )

    eligibility_signing_time = epoch

    def consumer_eligibility_signing_result(
        purpose: str,
        subject_digest: str,
        subject_media_type: str,
        evidence_id: str,
        policy: dict[str, str],
        repository: str,
    ) -> dict[str, Any]:
        del evidence_id
        return signing_result(
            purpose,
            subject_digest,
            subject_media_type,
            consumer_id,
            repository,
            eligibility_signing_time,
            pin_set=consumer_trust_policy_pin_set,
            policy_ref=policy,
        )

    status_eligibility_builder = ReleaseStatusEligibilityBuilder(
        schema_descriptor=schema_descriptor,
        artifact_descriptor=status_artifact_descriptor,
        signing_result=consumer_eligibility_signing_result,
        canonical_digest=canonical_digest,
        eligibility_schema=load_json(
            SCHEMA_ROOT / "release-status-eligibility-evidence.schema.json"
        ),
        trust_policy=status_eligibility_policy,
        repository="registry.example/consumer/status-eligibility",
        consumer_id=consumer_id,
        pin_set_descriptor=consumer_pin_set_binding["pinSetDescriptor"],
        pin_set_digest=consumer_trust_policy_pin_set["pinSetDigest"],
        pin_set_provider_evidence=consumer_pin_set_binding[
            "providerEvidence"
        ],
        register_document=lambda document_id, document: status_documents.__setitem__(
            document_id, deepcopy(document)
        ),
    )
    status_eligibility, status_eligibility_descriptor = (
        status_eligibility_builder.build(
            evidence_id="private-compilation-release-status-eligibility",
            stage="private_compilation",
            operation_time=epoch,
            product=product_eligibility_entry,
            renderers=[renderer_eligibility_entry],
        )
    )
    # The eligibility signature is evaluated independently at the compilation
    # use time and its permitted result is itself an exact CAS object.
    signature_adapter = TrustedKmsVerificationAdapter(
        [
            *deepcopy(renderer_signature_verification_vectors),
            *deepcopy(SIGNATURE_VERIFICATION_VECTORS),
        ]
    )
    status_eligibility_signature_verification_digest = (
        permitted_signature_verification(
            verification_id="private-compilation-eligibility-signature",
            result=status_eligibility["signingResult"],
            generic_subject=status_eligibility_descriptor,
            expected_signed_digest=status_eligibility["eligibilityDigest"],
            purpose="consumer-release-status-eligibility-v1",
            consumer=consumer_id,
            pin_set=consumer_trust_policy_pin_set,
            verification_time=epoch,
        )
    )
    inputs.update(
        {
            "releaseStatusEligibility": status_eligibility_descriptor,
            "releaseStatusEligibilityDigest": status_eligibility[
                "eligibilityDigest"
            ],
            "releaseStatusEligibilityVerificationEvidenceDigest": (
                status_eligibility_signature_verification_digest
            ),
            "trustPolicyPinSetDigest": consumer_trust_policy_pin_set[
                "pinSetDigest"
            ],
            "trustPolicyPinSetProviderEvidenceDigest": consumer_pin_set_binding[
                "providerEvidence"
            ]["evidenceDigest"],
        }
    )
    status_related_digests = set(CAS_PAYLOADS) - status_payloads_before

    authorized_inputs = deepcopy(inputs)
    authorized_inputs.pop("inputAuthentication", None)
    authorized_inputs.pop("authoritySnapshot")
    authorized_inputs.pop("authorizedPrivateInputDigest")
    authorized_private_input_digest = canonical_digest(
        {
            "profile": "bytedesk.authorized-private-compilation-input/1",
            "contract": lock["contract"],
            "schema": lock["schema"],
            "inputs": authorized_inputs,
        }
    )
    inputs["authorizedPrivateInputDigest"] = authorized_private_input_digest
    authority["authorizedPrivateInputDigest"] = authorized_private_input_digest
    authority["signerPolicy"] = deepcopy(authority_policy)
    authority["signerIdentity"] = (
        f"kms://{consumer_id}/consumer-authority-v1/versions/1"
    )
    authority["opaqueDigests"] = deepcopy(inputs["policyDigests"])
    authority["bindingDigest"] = inputs["binding"]["digest"]
    authority["candidateDigest"] = inputs["candidate"]["digest"]
    authority["desiredRevisionDigest"] = inputs["desiredRevision"]["digest"]
    authority["predecessor"] = deepcopy(inputs["predecessor"])
    authority["issuedAt"] = add_minutes(epoch, -5)
    authority["notBefore"] = add_minutes(epoch, -5)
    authority["expiresAt"] = add_minutes(epoch, 15)
    authority["nonce"] = "nonce_private_compile_0123456789abcdef"
    for field in (
        "consumerId",
        "subjectId",
        "installationId",
        "harnessId",
        "targetId",
    ):
        require(authority[field] == inputs[field], f"authority/lock {field} differs")
    require(
        authority["operation"] == "compile"
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
        and authority["predecessor"] == inputs["predecessor"],
        "consumer authority does not authorize the exact private lock",
    )
    authority_bytes = canonical_bytes(authority)
    authority_descriptor = descriptor_for_bytes(
        "registry.example/consumer/authority",
        "application/vnd.bytedesk.agent.consumer-authority.v1+json",
        authority_bytes,
        authority_policy,
    )
    detached_authentication: list[dict[str, Any]] = []
    detached_authentication_artifacts: list[
        tuple[str, dict[str, Any], Path | None]
    ] = []
    seen_authenticated_subjects: set[str] = set()
    for (
        role,
        subject_descriptor,
        evidence_descriptor,
        evidence_document,
    ) in canonical_public_authentication:
        subject_digest = subject_descriptor["digest"]
        require(
            subject_digest not in seen_authenticated_subjects,
            f"duplicate detached authentication subject: {subject_digest}",
        )
        seen_authenticated_subjects.add(subject_digest)
        signed_referrer = deepcopy(evidence_document["signingResult"])
        require(
            signed_referrer["purpose"] == "public-source-v1"
            and signed_referrer["subjectDigest"] == subject_digest
            and signed_referrer["subjectMediaType"]
            == subject_descriptor["mediaType"]
            and signed_referrer["trustPolicy"]
            == subject_descriptor["trustPolicy"],
            f"canonical public authentication result differs: {role}",
        )
        signed_referrer_descriptor = descriptor_for_bytes(
            signed_referrer["repository"],
            SIGNING_RESULT_MEDIA_TYPE,
            canonical_bytes(signed_referrer),
            signed_referrer["trustPolicy"],
        )
        detached_authentication.append(
            {
                "role": role,
                "subject": deepcopy(subject_descriptor),
                "signingResult": signed_referrer_descriptor,
            }
        )
        detached_authentication_artifacts.extend(
            [
                (
                    f"{role}-authentication-evidence",
                    evidence_descriptor,
                    None,
                ),
                (
                    f"{role}-signing-result",
                    signed_referrer_descriptor,
                    None,
                ),
                (
                    f"{role}-signature-bundle",
                    signed_referrer["signatureBundle"],
                    None,
                ),
                (
                    f"{role}-signer-authentication-evidence",
                    signed_referrer["providerAuditEvidence"],
                    None,
                ),
            ]
        )
    for role, subject_descriptor, _ in [
        *materialized_inputs,
        ("compilation-authority", authority_descriptor, None),
    ]:
        subject_digest = subject_descriptor["digest"]
        require(
            subject_digest not in seen_authenticated_subjects,
            f"duplicate detached authentication subject: {subject_digest}",
        )
        seen_authenticated_subjects.add(subject_digest)
        purpose = subject_descriptor["trustPolicy"]["id"]
        signing_consumer_id = (
            consumer_id
            if purpose in {"consumer-authority-v1", "consumer-private-skill-v1"}
            else None
        )
        signed_referrer = signing_result(
            purpose,
            subject_digest,
            subject_descriptor["mediaType"],
            signing_consumer_id,
            subject_descriptor["repository"],
            epoch,
            pin_set=(
                consumer_trust_policy_pin_set
                if signing_consumer_id is not None
                else product_trust_policy_pin_set
            ),
            policy_ref=subject_descriptor["trustPolicy"],
        )
        require(
            signed_referrer["trustPolicy"] == subject_descriptor["trustPolicy"],
            f"detached authentication policy drift: {role}",
        )
        signed_referrer_descriptor = descriptor_for_bytes(
            subject_descriptor["repository"],
            SIGNING_RESULT_MEDIA_TYPE,
            canonical_bytes(signed_referrer),
            subject_descriptor["trustPolicy"],
        )
        detached_authentication.append(
            {
                "role": role,
                "subject": deepcopy(subject_descriptor),
                "signingResult": signed_referrer_descriptor,
            }
        )
        detached_authentication_artifacts.extend(
            [
                (
                    f"{role}-signing-result",
                    signed_referrer_descriptor,
                    None,
                ),
                (
                    f"{role}-signature-bundle",
                    signed_referrer["signatureBundle"],
                    None,
                ),
                (
                    f"{role}-signer-authentication-evidence",
                    signed_referrer["providerAuditEvidence"],
                    None,
                ),
            ]
        )
    detached_authentication.sort(key=lambda entry: entry["role"].encode("utf-8"))
    authentication_bundle = {
        "contract": "bytedesk.private-input-authentication-bundle/1",
        "schema": schema_descriptor("private-input-authentication-bundle"),
        "consumerId": consumer_id,
        "subjectId": inputs["subjectId"],
        "installationId": inputs["installationId"],
        "harnessId": inputs["harnessId"],
        "targetId": inputs["targetId"],
        "entries": detached_authentication,
    }
    authentication_bundle_descriptor = descriptor_for_bytes(
        "registry.example/consumer/compilation-inputs",
        PRIVATE_INPUT_AUTHENTICATION_MEDIA_TYPE,
        canonical_bytes(authentication_bundle),
        input_policy,
    )
    authentication_bundle_unknown = deepcopy(authentication_bundle)
    authentication_bundle_unknown["__unknown"] = True
    inputs["inputAuthentication"] = authentication_bundle_descriptor
    inputs["authoritySnapshot"] = authority_descriptor
    lock["compilationInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-input-digest/1",
            "contract": lock["contract"],
            "schema": lock["schema"],
            "inputs": inputs,
        }
    )

    refresh_private_manifest(manifest, inputs, selection, capability)
    portable_definition = renderer_portable_definition(manifest)
    functional_inputs = renderer_functional_inputs(
        manifest, binding_document, inputs
    )
    portable_definition_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-portable-definition/1",
            **portable_definition,
        }
    )
    production_input_tree_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-production-input-tree/1",
            "functionalInputs": functional_inputs,
        }
    )
    payload = build_payload(manifest)
    payload_descriptor = descriptor_for_bytes(
        "registry.example/consumer/render-payloads",
        RENDER_PAYLOAD_MEDIA_TYPE,
        payload,
        deployment_policy,
    )

    issuer_identity_digest = canonical_digest(
        {
            "profile": "bytedesk.private-render-issuer-identity/1",
            "consumerId": consumer_id,
            "targetId": inputs["targetId"],
        }
    )
    launcher_identity_digest = canonical_digest(
        {
            "profile": "bytedesk.private-render-launcher-identity/1",
            "consumerId": consumer_id,
            "targetId": inputs["targetId"],
            "rendererDistribution": selection["executableDistribution"],
        }
    )
    request_frame = framed_jcs(
        renderer_request_frame_document(
            selection,
            portable_definition,
            portable_definition_digest,
            functional_inputs,
            production_input_tree_digest,
            inputs["contractBundle"]["digest"],
        )
    )
    framed_request_digest = register_cas_payload(request_frame)
    attempt = {
        "contract": "bytedesk.renderer-attempt-authority/1",
        "schema": schema_descriptor("renderer-attempt-authority"),
        "attemptId": "private-render-attempt-01",
        "attemptFencingToken": 1,
        "rendererSelectionDigest": selection["selectionDigest"],
        "productReleaseStatusCheckpointDigest": selection[
            "productReleaseStatusCheckpoint"
        ]["digest"],
        "productReleaseStatusCheckpointAuthenticationEvidenceDigest": selection[
            "productReleaseStatusCheckpointAuthenticationEvidence"
        ]["digest"],
        "productReleaseStatusRequestNonce": selection[
            "productReleaseStatusRequestNonce"
        ],
        "rendererReleaseStatusCheckpointDigest": selection[
            "rendererReleaseStatusCheckpoint"
        ]["digest"],
        "rendererReleaseStatusCheckpointAuthenticationEvidenceDigest": selection[
            "rendererReleaseStatusCheckpointAuthenticationEvidence"
        ]["digest"],
        "rendererReleaseStatusRequestNonce": selection[
            "rendererReleaseStatusRequestNonce"
        ],
        "portableDefinitionDigest": portable_definition_digest,
        "inputTreeDigest": production_input_tree_digest,
        "framedRequestDigest": framed_request_digest,
        "contractBundleDigest": inputs["contractBundle"]["digest"],
        "sandboxProfileDigest": inputs["policyDigests"]["mandatorySandbox"],
        "issuerIdentityDigest": issuer_identity_digest,
        "issuedAt": epoch,
        "expiresAt": add_minutes(epoch, 5),
        "authorityDigest": "sha256:" + "0" * 64,
    }
    attempt["authorityDigest"] = domain_digest(
        "bytedesk.renderer-attempt-authority-digest/1",
        attempt,
        {"contract", "schema", "authorityDigest"},
    )

    attempt_signing = signing_result(
        "renderer-attempt-v1",
        attempt["authorityDigest"],
        "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
        None,
        "registry.example/product/renderer-attempt-evidence",
        epoch,
        pin_set=product_trust_policy_pin_set,
        policy_ref=renderer_attempt_policy,
    )
    attempt_auth = {
        "contract": "bytedesk.renderer-attempt-authentication-evidence/1",
        "schema": schema_descriptor("renderer-attempt-authentication-evidence"),
        "purpose": "renderer-attempt-v1",
        "attemptAuthorityDigest": attempt["authorityDigest"],
        "issuerIdentityDigest": issuer_identity_digest,
        "signingResult": attempt_signing,
        "evidenceDigest": "sha256:" + "0" * 64,
    }
    attempt_auth["evidenceDigest"] = domain_digest(
        "bytedesk.renderer-attempt-authentication-evidence-digest/1",
        attempt_auth,
        {"contract", "schema", "evidenceDigest"},
    )

    response_frame = framed_jcs(
        renderer_response_frame_document(attempt, manifest)
    )
    framed_response_digest = register_cas_payload(response_frame)
    framed_payloads = [
        ("renderer-request-frame", framed_request_digest, request_frame),
        ("renderer-response-frame", framed_response_digest, response_frame),
    ]

    receipt = {
        "contract": "bytedesk.renderer-execution-receipt/1",
        "schema": schema_descriptor("renderer-execution-receipt"),
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
        "executedDistribution": deepcopy(selection["executableDistribution"]),
        "productDistributionDigest": selection["productDistributionDigest"],
        "compiledAllowlistDigest": selection["compiledAllowlistDigest"],
        "inputTreeDigest": attempt["inputTreeDigest"],
        "contractBundleDigest": attempt["contractBundleDigest"],
        "framedRequestDigest": framed_request_digest,
        "framedResponseDigest": framed_response_digest,
        "outputTreeDigest": manifest["output"]["treeDigest"],
        "outputArchiveDigest": manifest["output"]["digest"],
        "outputArchiveSize": manifest["output"]["size"],
        "renderManifestDigest": canonical_digest(manifest),
        "sandboxProfileDigest": attempt["sandboxProfileDigest"],
        "workerProfileDigest": selection["workerProfileDigest"],
        "launcherIdentityDigest": launcher_identity_digest,
        "completedAt": epoch,
    }
    receipt_digest = canonical_digest(receipt)
    execution_signing = signing_result(
        "renderer-execution-v1",
        receipt_digest,
        "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
        None,
        "registry.example/product/renderer-execution-evidence",
        epoch,
        pin_set=product_trust_policy_pin_set,
        policy_ref=renderer_execution_policy,
    )
    execution_auth = {
        "contract": "bytedesk.renderer-execution-authentication-evidence/1",
        "schema": schema_descriptor("renderer-execution-authentication-evidence"),
        "purpose": "renderer-execution-v1",
        "receiptDigest": receipt_digest,
        "attemptAuthorityDigest": attempt["authorityDigest"],
        "rendererSelectionDigest": selection["selectionDigest"],
        "launcherIdentityDigest": launcher_identity_digest,
        "signingResult": execution_signing,
        "evidenceDigest": "sha256:" + "0" * 64,
    }
    execution_auth["evidenceDigest"] = domain_digest(
        "bytedesk.renderer-execution-authentication-evidence-digest/1",
        execution_auth,
        {"contract", "schema", "evidenceDigest"},
    )

    lock_bytes = canonical_bytes(lock)
    lock_descriptor = descriptor_for_bytes(
        "registry.example/consumer/compilation-inputs",
        PRIVATE_INPUT_MEDIA_TYPE,
        lock_bytes,
        input_policy,
    )
    lock_signing_result = signing_result(
        "consumer-compilation-input-v1",
        lock_descriptor["digest"],
        PRIVATE_INPUT_MEDIA_TYPE,
        consumer_id,
        lock_descriptor["repository"],
        epoch,
        pin_set=consumer_trust_policy_pin_set,
        policy_ref=input_policy,
    )
    effective_skills = sorted(
        deepcopy(
            inputs["effectiveSkillSet"]["publicSkills"]
            + inputs["effectiveSkillSet"]["privateSkills"]
        ),
        key=lambda entry: (entry["repository"].encode("utf-8"), entry["digest"]),
    )
    approval_descriptors = [
        deepcopy(entry["approval"]) for entry in inputs["skillApprovals"]
    ]
    policy_digests = inputs["policyDigests"]
    deployment = {
        "contract": "bytedesk.consumer-deployment/1",
        "schema": schema_descriptor("consumer-deployment"),
        "deploymentId": deployment_id(lock),
        "consumerId": consumer_id,
        "subjectId": inputs["subjectId"],
        "installationId": inputs["installationId"],
        "harnessId": inputs["harnessId"],
        "targetId": inputs["targetId"],
        "candidate": deepcopy(inputs["candidate"]),
        "desiredRevision": deepcopy(inputs["desiredRevision"]),
        "predecessor": deepcopy(inputs["predecessor"]),
        "runtimeSlot": deepcopy(inputs["runtimeSlot"]),
        "activationMode": inputs["activationMode"],
        "source": deepcopy(manifest["source"]),
        "publicRender": deepcopy(inputs["publicArtifact"]),
        "binding": deepcopy(inputs["binding"]),
        "approvedSkills": effective_skills,
        "skillApprovals": approval_descriptors,
        "compilationAuthority": deepcopy(inputs["authoritySnapshot"]),
        "compilationInput": lock_descriptor,
        "compilationInputSigningResult": lock_signing_result,
        "compilationInputDigest": lock["compilationInputDigest"],
        "rendererSelectionDigest": selection["selectionDigest"],
        "releaseStatusEligibility": deepcopy(
            inputs["releaseStatusEligibility"]
        ),
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
        "rendererExecution": {
            "attemptAuthority": attempt,
            "attemptAuthenticationEvidence": attempt_auth,
            "receipt": receipt,
            "authenticationEvidence": execution_auth,
        },
        "productRelease": deepcopy(selection["productRelease"]),
        "rendererRelease": deepcopy(selection["rendererRelease"]),
        "executedDistribution": deepcopy(receipt["executedDistribution"]),
        "productDistributionDigest": selection["productDistributionDigest"],
        "compiledAllowlistDigest": selection["compiledAllowlistDigest"],
        "opaqueConsumerDigests": {
            "policy": policy_digests["policy"],
            "grantSet": policy_digests["grantSet"],
            "credentialSet": policy_digests["credentialSet"],
            "workloadIdentity": policy_digests["workloadIdentity"],
            "lifecycle": policy_digests["lifecycle"],
            "sandbox": policy_digests["mandatorySandbox"],
            "network": policy_digests["network"],
            "approvalPolicy": policy_digests["approvalPolicy"],
            "targetBinding": policy_digests["targetBinding"],
        },
        "effectiveRender": {
            "manifest": manifest,
            "manifestDigest": canonical_digest(manifest),
            "payload": payload_descriptor,
        },
        "reproducibleEpoch": epoch,
        "createdAt": epoch,
        "trustPolicy": deployment_policy,
    }
    deployment_bytes = canonical_bytes(deployment)
    deployment_descriptor = descriptor_for_bytes(
        "registry.example/consumer/deployments",
        DEPLOYMENT_MEDIA_TYPE,
        deployment_bytes,
        deployment_policy,
    )
    deployment_signing_result = signing_result(
        "consumer-deployment-v1",
        deployment_descriptor["digest"],
        DEPLOYMENT_MEDIA_TYPE,
        consumer_id,
        "registry.example/consumer/deployments",
        epoch,
        pin_set=consumer_trust_policy_pin_set,
        policy_ref=deployment_policy,
    )

    idempotency_key = "private-compile-01"
    compile_request_digest = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-request/1",
            "consumerId": consumer_id,
            "idempotencyKey": idempotency_key,
            "compilationInputDigest": lock["compilationInputDigest"],
        }
    )
    statement = {
        "consumerId": consumer_id,
        "subjectId": inputs["subjectId"],
        "installationId": inputs["installationId"],
        "harnessId": inputs["harnessId"],
        "targetId": inputs["targetId"],
        "outcome": "committed",
        "idempotencyKey": idempotency_key,
        "compileRequestDigest": compile_request_digest,
        "compilationInput": lock_descriptor,
        "compilationInputDigest": lock["compilationInputDigest"],
        "consumerDeployment": deployment_descriptor,
        "deploymentSigningResult": deployment_signing_result,
        "rendererSelectionDigest": selection["selectionDigest"],
        "releaseStatusEligibility": deepcopy(
            inputs["releaseStatusEligibility"]
        ),
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
        "rendererAttemptAuthorityDigest": attempt["authorityDigest"],
        "rendererAttemptAuthenticationEvidenceDigest": attempt_auth["evidenceDigest"],
        "rendererExecutionReceiptDigest": receipt_digest,
        "rendererExecutionAuthenticationEvidenceDigest": execution_auth[
            "evidenceDigest"
        ],
        "renderManifestDigest": canonical_digest(manifest),
        "renderPayload": payload_descriptor,
        "compilerDistribution": deepcopy(product_release["productDistribution"]),
        "compilerWorkerProfileDigest": canonical_digest(
            {
                "profile": "bytedesk.private-compiler-worker-profile/1",
                "compilerDistribution": product_release["productDistribution"],
            }
        ),
        "compilerIdentityDigest": canonical_digest(
            {
                "profile": "bytedesk.private-compiler-identity/1",
                "consumerId": consumer_id,
                "targetId": inputs["targetId"],
            }
        ),
        "rendererDistribution": deepcopy(receipt["executedDistribution"]),
        "compilationSigningPolicy": evidence_policy,
        "reproducibleEpoch": epoch,
        "completedAt": epoch,
    }
    statement_digest = canonical_digest(
        {"profile": "bytedesk.private-compilation-statement/1", "statement": statement}
    )
    evidence = {
        "contract": "bytedesk.private-compilation-evidence/1",
        "schema": schema_descriptor("private-compilation-evidence"),
        "purpose": "consumer-compilation-evidence-v1",
        "statement": statement,
        "statementDigest": statement_digest,
        "signingResult": signing_result(
            "consumer-compilation-evidence-v1",
            statement_digest,
            COMPILATION_STATEMENT_MEDIA_TYPE,
            consumer_id,
            "registry.example/consumer/compilation-evidence",
            epoch,
            pin_set=consumer_trust_policy_pin_set,
            policy_ref=evidence_policy,
        ),
    }
    evidence_bytes = canonical_bytes(evidence)
    evidence_descriptor = descriptor_for_bytes(
        "registry.example/consumer/compilation-evidence",
        COMPILATION_EVIDENCE_MEDIA_TYPE,
        evidence_bytes,
        evidence_policy,
    )

    # The activation fixture is deliberately target-wide: a second, distinct
    # subject deployment proves that authorization covers the complete runtime
    # release graph instead of accidentally treating the first deployment as
    # the unit of activation. The private compilation fixture above remains the
    # fully expanded primary-subject proof; this companion deployment/evidence
    # pair is independently schema-valid and purpose-separated signed for the
    # aggregate activation seam.
    secondary_subject_id = "agent-finance-02"
    secondary_deployment = deepcopy(deployment)
    secondary_deployment["subjectId"] = secondary_subject_id
    secondary_deployment["installationId"] = "installation-02"
    secondary_deployment_identity = canonical_digest(
        {
            "profile": "bytedesk.consumer-deployment-id/1",
            "consumerId": consumer_id,
            "subjectId": secondary_subject_id,
            "targetId": inputs["targetId"],
            "candidateDigest": inputs["candidate"]["digest"],
            "desiredRevisionDigest": inputs["desiredRevision"]["digest"],
            "compilationInputDigest": lock["compilationInputDigest"],
        }
    )
    secondary_deployment["deploymentId"] = (
        "deployment-"
        + secondary_deployment_identity.removeprefix("sha256:")
    )
    secondary_deployment_descriptor = descriptor_for_bytes(
        "registry.example/consumer/deployments",
        DEPLOYMENT_MEDIA_TYPE,
        canonical_bytes(secondary_deployment),
        deployment_policy,
    )
    secondary_deployment_signing_result = signing_result(
        "consumer-deployment-v1",
        secondary_deployment_descriptor["digest"],
        DEPLOYMENT_MEDIA_TYPE,
        consumer_id,
        "registry.example/consumer/deployments",
        epoch,
        pin_set=consumer_trust_policy_pin_set,
        policy_ref=deployment_policy,
    )
    secondary_statement = deepcopy(statement)
    secondary_idempotency_key = "private-compile-02"
    secondary_statement.update(
        {
            "subjectId": secondary_subject_id,
            "installationId": "installation-02",
            "idempotencyKey": secondary_idempotency_key,
            "compileRequestDigest": canonical_digest(
                {
                    "profile": "bytedesk.private-compilation-request/1",
                    "consumerId": consumer_id,
                    "idempotencyKey": secondary_idempotency_key,
                    "compilationInputDigest": lock[
                        "compilationInputDigest"
                    ],
                }
            ),
            "consumerDeployment": secondary_deployment_descriptor,
            "deploymentSigningResult": (
                secondary_deployment_signing_result
            ),
        }
    )
    secondary_statement_digest = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-statement/1",
            "statement": secondary_statement,
        }
    )
    secondary_evidence = {
        "contract": "bytedesk.private-compilation-evidence/1",
        "schema": schema_descriptor("private-compilation-evidence"),
        "purpose": "consumer-compilation-evidence-v1",
        "statement": secondary_statement,
        "statementDigest": secondary_statement_digest,
        "signingResult": signing_result(
            "consumer-compilation-evidence-v1",
            secondary_statement_digest,
            COMPILATION_STATEMENT_MEDIA_TYPE,
            consumer_id,
            "registry.example/consumer/compilation-evidence",
            epoch,
            pin_set=consumer_trust_policy_pin_set,
            policy_ref=evidence_policy,
        ),
    }
    secondary_evidence_descriptor = descriptor_for_bytes(
        "registry.example/consumer/compilation-evidence",
        COMPILATION_EVIDENCE_MEDIA_TYPE,
        canonical_bytes(secondary_evidence),
        evidence_policy,
    )
    secondary_runtime_supporting_artifacts = [
        (
            "secondary-consumer-deployment",
            secondary_deployment_descriptor,
            None,
        ),
        (
            "secondary-consumer-deployment-signature-bundle",
            secondary_deployment_signing_result["signatureBundle"],
            None,
        ),
        (
            "secondary-consumer-deployment-signer-authentication-evidence",
            secondary_deployment_signing_result["providerAuditEvidence"],
            None,
        ),
        (
            "secondary-private-compilation-evidence",
            secondary_evidence_descriptor,
            None,
        ),
        (
            "secondary-private-compilation-evidence-signature-bundle",
            secondary_evidence["signingResult"]["signatureBundle"],
            None,
        ),
        (
            "secondary-private-compilation-evidence-signer-authentication-evidence",
            secondary_evidence["signingResult"]["providerAuditEvidence"],
            None,
        ),
    ]

    runtime_release = {
        "contract": "bytedesk.runtime-release/1",
        "schema": schema_descriptor("runtime-release"),
        "releaseId": "runtime-release-01",
        "consumerId": consumer_id,
        "targetId": inputs["targetId"],
        "candidate": deepcopy(inputs["candidate"]),
        "desiredRevision": deepcopy(inputs["desiredRevision"]),
        "predecessor": deepcopy(inputs["predecessor"]),
        "activationMode": inputs["activationMode"],
        "releaseStatusEligibility": deepcopy(
            inputs["releaseStatusEligibility"]
        ),
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
        "deployments": [
            {
                "subjectId": inputs["subjectId"],
                "deployment": deployment_descriptor,
                "compilationEvidence": evidence_descriptor,
                "slotId": inputs["runtimeSlot"]["slotId"],
                "generation": inputs["runtimeSlot"]["generation"],
            },
            {
                "subjectId": secondary_subject_id,
                "deployment": secondary_deployment_descriptor,
                "compilationEvidence": secondary_evidence_descriptor,
                "slotId": inputs["runtimeSlot"]["slotId"],
                "generation": inputs["runtimeSlot"]["generation"],
            },
        ],
        "activationConstraints": {
            "trustPolicy": deployment_policy,
            "authorityPolicyDigest": policy_digests["policy"],
            "canaryPolicyDigest": canonical_digest(
                {"profile": "bytedesk.fixture-canary-policy/1", "consumerId": consumer_id}
            ),
            "recoveryPolicyDigest": canonical_digest(
                {"profile": "bytedesk.fixture-recovery-policy/1", "consumerId": consumer_id}
            ),
        },
        "compilationEpoch": epoch,
        "preparedAt": epoch,
        "trustPolicy": runtime_release_policy,
    }
    runtime_release["releaseDigest"] = canonical_digest(
        runtime_release_statement_preimage(runtime_release)
    )
    runtime_release["signingResult"] = signing_result(
        "consumer-runtime-release-v1",
        runtime_release["releaseDigest"],
        RUNTIME_RELEASE_STATEMENT_MEDIA_TYPE,
        consumer_id,
        "registry.example/consumer/runtime-releases",
        epoch,
        pin_set=consumer_trust_policy_pin_set,
        policy_ref=runtime_release_policy,
    )
    runtime_release_descriptor = descriptor_for_bytes(
        "registry.example/consumer/runtime-releases",
        RUNTIME_RELEASE_MEDIA_TYPE,
        canonical_bytes(runtime_release),
        runtime_release_policy,
    )

    activation_payloads_before = set(CAS_PAYLOADS)
    activation_epoch = "2026-07-17T12:00:11Z"
    status_signing_time = activation_epoch
    eligibility_signing_time = activation_epoch
    product_activation_head = status_head_builder.refresh(
        checkpoint_id="activation-product-status-head",
        request_nonce="status_head_nonce_activation_product_0123456789abcdef",
        subject_kind="product_release",
        subject=selection["productRelease"],
        status=product_current_status,
        status_descriptor=selection["productReleaseStatus"],
        epoch=2,
        log_leaves=product_status_leaves,
        operation_time=activation_epoch,
        expires_at=add_minutes(activation_epoch, 5),
        prior_checkpoint=product_compilation_head["checkpoint"],
        prior_checkpoint_descriptor=product_compilation_head[
            "checkpointDescriptor"
        ],
    )
    renderer_activation_head = status_head_builder.refresh(
        checkpoint_id="activation-hermes-status-head",
        request_nonce="status_head_nonce_activation_hermes_0123456789abcdef",
        subject_kind="renderer_release",
        subject=selection["rendererRelease"],
        status=renderer_current_status,
        status_descriptor=selection["rendererReleaseStatus"],
        epoch=1,
        log_leaves=renderer_status_leaves,
        operation_time=activation_epoch,
        expires_at=add_minutes(activation_epoch, 5),
        prior_checkpoint=renderer_compilation_head["checkpoint"],
        prior_checkpoint_descriptor=renderer_compilation_head[
            "checkpointDescriptor"
        ],
    )
    signature_adapter = TrustedKmsVerificationAdapter(
        [
            *deepcopy(renderer_signature_verification_vectors),
            *deepcopy(SIGNATURE_VERIFICATION_VECTORS),
        ]
    )
    product_activation_entry = status_entry(
        entry_id="activation-product",
        subject_kind="product_release",
        subject=selection["productRelease"],
        status=product_current_status,
        status_descriptor=selection["productReleaseStatus"],
        built_head=product_activation_head,
        operation_time=activation_epoch,
    )
    renderer_activation_entry = status_entry(
        entry_id="activation-hermes",
        subject_kind="renderer_release",
        subject=selection["rendererRelease"],
        status=renderer_current_status,
        status_descriptor=selection["rendererReleaseStatus"],
        built_head=renderer_activation_head,
        harness_id=selection["targetHarness"],
        renderer_id=selection["rendererId"],
        renderer_version=selection["rendererVersion"],
        target_platform=selection["targetPlatform"],
        operation_time=activation_epoch,
    )
    activation_eligibility, activation_eligibility_descriptor = (
        status_eligibility_builder.build(
            evidence_id="activation-release-status-eligibility",
            stage="activation",
            operation_time=activation_epoch,
            product=product_activation_entry,
            renderers=[renderer_activation_entry],
        )
    )
    signature_adapter = TrustedKmsVerificationAdapter(
        [
            *deepcopy(renderer_signature_verification_vectors),
            *deepcopy(SIGNATURE_VERIFICATION_VECTORS),
        ]
    )
    activation_eligibility_verification_digest = (
        permitted_signature_verification(
            verification_id="activation-eligibility-signature",
            result=activation_eligibility["signingResult"],
            generic_subject=activation_eligibility_descriptor,
            expected_signed_digest=activation_eligibility[
                "eligibilityDigest"
            ],
            purpose="consumer-release-status-eligibility-v1",
            consumer=consumer_id,
            pin_set=consumer_trust_policy_pin_set,
            verification_time=activation_epoch,
        )
    )
    host_activation_operation_time = "2026-07-17T12:00:12Z"

    def host_use_time_status_verification_digests(
        *,
        entry_id: str,
        entry: dict[str, Any],
        status_document: dict[str, Any],
        built_head: dict[str, Any],
        subject: dict[str, Any],
    ) -> list[str]:
        checkpoint = built_head["checkpoint"]
        authentication = built_head["authentication"]
        inclusion = built_head["inclusionProof"]
        fresh_digests = [
            permitted_signature_verification(
                verification_id=f"{entry_id}-status-signature",
                result=status_document["signingResult"],
                generic_subject=entry["status"],
                expected_signed_digest=status_document["authorityDigest"],
                purpose="release-status-v1",
                consumer=None,
                pin_set=product_trust_policy_pin_set,
                verification_time=host_activation_operation_time,
            ),
            permitted_signature_verification(
                verification_id=f"{entry_id}-checkpoint-authentication",
                result=authentication["signingResult"],
                generic_subject=entry["checkpoint"],
                expected_signed_digest=entry["checkpoint"]["digest"],
                purpose="release-status-head-v1",
                consumer=None,
                pin_set=product_trust_policy_pin_set,
                verification_time=host_activation_operation_time,
            ),
        ]
        inclusion_math = {
            "profile": "bytedesk.release-status-inclusion-verification/1",
            "algorithm": "bytedesk-rfc6962-inclusion-v1",
            "subject": deepcopy(subject),
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
        inclusion_math_digest = register_cas_payload(
            canonical_bytes(inclusion_math)
        )
        fresh_digests.append(
            register_status_verification(
                f"{entry_id}-head-inclusion",
                permitted_verification_result(
                    schema_descriptor=schema_descriptor(
                        "verification-result"
                    ),
                    verification_id=f"{entry_id}-head-inclusion",
                    subject=entry["headInclusionProof"],
                    policy=release_status_head_policy,
                    evaluated_at=host_activation_operation_time,
                    evidence_digests=[
                        fresh_digests[1],
                        inclusion_math_digest,
                    ],
                ),
            )
        )
        consistency = built_head["consistencyProof"]
        if consistency is not None:
            consistency_signature_digest = (
                permitted_signature_verification(
                    verification_id=f"{entry_id}-consistency-signature",
                    result=consistency["signingResult"],
                    generic_subject=entry["consistencyProof"],
                    expected_signed_digest=consistency["authorityDigest"],
                    purpose="release-status-head-v1",
                    consumer=None,
                    pin_set=product_trust_policy_pin_set,
                    verification_time=host_activation_operation_time,
                )
            )
            fresh_digests.append(consistency_signature_digest)
            consistency_math = {
                "profile": "bytedesk.release-status-consistency-verification/1",
                "algorithm": consistency["algorithm"],
                "subject": deepcopy(subject),
                "checkpoint": deepcopy(entry["checkpoint"]),
                "proof": deepcopy(entry["consistencyProof"]),
                "from": deepcopy(consistency["from"]),
                "to": deepcopy(consistency["to"]),
                "auditPath": deepcopy(consistency["auditPath"]),
                "decision": "permitted",
            }
            consistency_math_digest = register_cas_payload(
                canonical_bytes(consistency_math)
            )
            fresh_digests.append(
                register_status_verification(
                    f"{entry_id}-consistency",
                    permitted_verification_result(
                        schema_descriptor=schema_descriptor(
                            "verification-result"
                        ),
                        verification_id=f"{entry_id}-consistency",
                        subject=entry["consistencyProof"],
                        policy=release_status_head_policy,
                        evaluated_at=host_activation_operation_time,
                        evidence_digests=[
                            fresh_digests[1],
                            consistency_signature_digest,
                            consistency_math_digest,
                        ],
                    ),
                )
            )
        return fresh_digests

    host_eligibility_evidence_digests = (
        host_use_time_status_verification_digests(
            entry_id="activation-host-use-product",
            entry=activation_eligibility["product"],
            status_document=product_current_status,
            built_head=product_activation_head,
            subject=selection["productRelease"],
        )
    )
    host_eligibility_evidence_digests.extend(
        host_use_time_status_verification_digests(
            entry_id=(
                "activation-host-use-renderer-"
                + activation_eligibility["renderers"][0]["rendererId"]
            ),
            entry=activation_eligibility["renderers"][0],
            status_document=renderer_current_status,
            built_head=renderer_activation_head,
            subject=selection["rendererRelease"],
        )
    )
    host_eligibility_evidence_digests.append(
        permitted_signature_verification(
            verification_id=(
                "activation-host-use-time-eligibility-signature"
            ),
            result=activation_eligibility["signingResult"],
            generic_subject=activation_eligibility_descriptor,
            expected_signed_digest=activation_eligibility[
                "eligibilityDigest"
            ],
            purpose="consumer-release-status-eligibility-v1",
            consumer=consumer_id,
            pin_set=consumer_trust_policy_pin_set,
            verification_time=host_activation_operation_time,
        )
    )
    host_eligibility_verification_digest = register_status_verification(
        "activation-host-use-time-release-eligibility",
        permitted_verification_result(
            schema_descriptor=schema_descriptor("verification-result"),
            verification_id=(
                "activation-host-use-time-release-eligibility"
            ),
            subject=activation_eligibility_descriptor,
            policy=status_eligibility_policy,
            evaluated_at=host_activation_operation_time,
            evidence_digests=host_eligibility_evidence_digests,
        ),
    )
    require(
        host_eligibility_verification_digest
        != activation_eligibility_verification_digest,
        "host use-time eligibility result reused Coordinator result",
    )

    consumer_platform_evidence_policy_bindings: list[dict[str, Any]] = []

    def consumer_platform_evidence_policy(purpose: str) -> dict[str, str]:
        provider_id = "consumer-platform-evidence-trust-provider"
        provider_authority_digest = canonical_digest(
            {
                "profile": "bytedesk.consumer-platform-evidence-provider-authority/1",
                "consumerId": consumer_id,
                "providerId": provider_id,
            }
        )
        policy_document = {
            "profile": "bytedesk.consumer-platform-evidence-policy-binding/1",
            "consumerId": consumer_id,
            "purpose": purpose,
            "providerId": provider_id,
            "providerAuthorityDigest": provider_authority_digest,
            "effective": {
                "notBefore": "2026-07-17T00:00:00Z",
                "notAfter": "2027-07-17T00:00:00Z",
            },
            "authority": "consumer_platform",
        }
        policy_digest = register_cas_payload(canonical_bytes(policy_document))
        reference = {"id": purpose, "digest": policy_digest}
        consumer_platform_evidence_policy_bindings.append(
            {
                "purpose": purpose,
                "trustPolicy": deepcopy(reference),
                "policyDocument": policy_document,
                "providerId": provider_id,
                "providerAuthorityDigest": provider_authority_digest,
                "verificationDecision": "trusted",
            }
        )
        return reference

    host_evidence_policy = consumer_platform_evidence_policy(
        "host-technical-evidence-v1"
    )
    authorization_decision_policy = consumer_platform_evidence_policy(
        "authorization-decision-v1"
    )
    authorization_nonce = (
        "activation_authorization_nonce_0123456789abcdef"
    )
    subject_activation_nonce = (
        "activation_subject_nonce_0123456789abcdef"
    )
    activation_plan_digest = canonical_digest(
        {
            "profile": "bytedesk.activation-plan/1",
            "consumerId": consumer_id,
            "targetId": inputs["targetId"],
            "runtimeRelease": runtime_release_descriptor,
            "operationTime": activation_epoch,
        }
    )
    activation_authority = deepcopy(authority)
    activation_authority.pop("authorizedPrivateInputDigest", None)
    activation_authority.update(
        {
            "operation": "activate",
            "authorityRevision": authority["authorityRevision"] + 1,
            "predecessor": {
                "kind": "match",
                "revision": authority["authorityRevision"],
                "digest": authority_descriptor["digest"],
            },
            "decision": {
                "class": "permitted",
                "code": "consumer_activation_permitted",
            },
            "issuedAt": activation_epoch,
            "notBefore": activation_epoch,
            "expiresAt": add_minutes(activation_epoch, 5),
            "nonce": subject_activation_nonce,
        }
    )
    activation_authority_descriptor = descriptor_for_bytes(
        "registry.example/consumer/authority",
        "application/vnd.bytedesk.agent.consumer-authority.v1+json",
        canonical_bytes(activation_authority),
        authority_policy,
    )
    deployment_entry = runtime_release["deployments"][0]

    def restricted_trace(label: str) -> dict[str, str]:
        return {
            "digest": canonical_digest(
                {
                    "profile": "bytedesk.activation-restricted-trace/1",
                    "label": label,
                    "runtimeReleaseDigest": runtime_release[
                        "releaseDigest"
                    ],
                }
            ),
            "classification": "restricted",
        }

    candidate_ready = {
        "contract": "bytedesk.canary-evidence/1",
        "schema": schema_descriptor("canary-evidence"),
        "evidenceId": "activation-candidate-ready-01",
        "actor": "host_reconciler",
        "rolloutId": "rollout-activation-01",
        "planDigest": activation_plan_digest,
        "nonce": subject_activation_nonce,
        "candidateDigest": inputs["candidate"]["digest"],
        "desiredRevisionDigest": inputs["desiredRevision"]["digest"],
        "releaseDigest": runtime_release["releaseDigest"],
        "deploymentDigest": deployment_descriptor["digest"],
        "consumerId": consumer_id,
        "subjectId": inputs["subjectId"],
        "targetId": inputs["targetId"],
        "slotId": deployment_entry["slotId"],
        "generation": deployment_entry["generation"],
        "authorityDigest": activation_authority_descriptor["digest"],
        "policyDigest": policy_digests["policy"],
        "grantSetDigest": policy_digests["grantSet"],
        "workloadIdentityDigest": policy_digests["workloadIdentity"],
        "actorIdentity": f"spiffe://consumer.example/{consumer_id}/host",
        "actorVersion": "1.0.0",
        "signerPolicy": host_evidence_policy,
        "results": {
            "phase": "candidate_ready",
            **{
                check: {"actual": "passed", "trace": restricted_trace(check)}
                for check in (
                    "artifact_readback",
                    "file_inventory",
                    "slot_generation",
                    "service_process",
                    "resource_thresholds",
                    "harness_readiness",
                )
            },
        },
        "issuedAt": activation_epoch,
        "expiresAt": add_minutes(activation_epoch, 5),
        "trace": restricted_trace("candidate-ready"),
    }
    candidate_ready_descriptor = descriptor_for_bytes(
        "registry.example/consumer/host-evidence",
        "application/vnd.bytedesk.agent.canary-evidence.v1+json",
        canonical_bytes(candidate_ready),
        host_evidence_policy,
    )
    decision_proof = {
        "contract": "bytedesk.authorization-decision-proof/1",
        "schema": schema_descriptor("authorization-decision-proof"),
        "proofId": "activation-authorization-decision-01",
        "actor": "consumer_authorization_system",
        "planDigest": activation_plan_digest,
        "nonce": subject_activation_nonce,
        "consumerId": consumer_id,
        "subjectId": inputs["subjectId"],
        "targetId": inputs["targetId"],
        "candidateDigest": inputs["candidate"]["digest"],
        "releaseDigest": runtime_release["releaseDigest"],
        "deploymentDigest": deployment_descriptor["digest"],
        "capability": {
            "id": "deployment.activate",
            "digest": canonical_digest(
                {
                    "profile": "bytedesk.consumer-capability/1",
                    "id": "deployment.activate",
                }
            ),
        },
        "policyDigest": policy_digests["policy"],
        "grantSetDigest": policy_digests["grantSet"],
        "workloadIdentityDigest": policy_digests["workloadIdentity"],
        "decision": {"class": "permitted", "code": "activation_permitted"},
        "signerIdentity": (
            f"spiffe://consumer.example/{consumer_id}/authorization"
        ),
        "signerPolicy": authorization_decision_policy,
        "transport": {
            "outcome": "successful_authorization_response",
            "protocol": "https",
            "statusCode": 200,
            "authenticated": True,
            "completed": True,
            "parsed": True,
            "responseMediaType": "application/json",
            "responseDigest": canonical_digest(
                {
                    "profile": "bytedesk.activation-authorization-response/1",
                    "planDigest": activation_plan_digest,
                    "subjectId": inputs["subjectId"],
                    "deploymentDigest": deployment_descriptor["digest"],
                    "nonce": subject_activation_nonce,
                    "decision": "permitted",
                }
            ),
        },
        "issuedAt": activation_epoch,
        "expiresAt": add_minutes(activation_epoch, 5),
        "trace": restricted_trace("authorization-decision"),
    }
    decision_proof_descriptor = descriptor_for_bytes(
        "registry.example/consumer/authorization-evidence",
        "application/vnd.bytedesk.agent.authorization-decision-proof.v1+json",
        canonical_bytes(decision_proof),
        authorization_decision_policy,
    )

    secondary_subject_activation_nonce = (
        "activation_subject_nonce_02_0123456789abcdef"
    )
    secondary_activation_authority = deepcopy(activation_authority)
    secondary_activation_authority.update(
        {
            "subjectId": secondary_subject_id,
            "installationId": "installation-02",
            "nonce": secondary_subject_activation_nonce,
        }
    )
    secondary_activation_authority_descriptor = descriptor_for_bytes(
        "registry.example/consumer/authority",
        "application/vnd.bytedesk.agent.consumer-authority.v1+json",
        canonical_bytes(secondary_activation_authority),
        authority_policy,
    )
    secondary_candidate_ready = deepcopy(candidate_ready)
    secondary_candidate_ready.update(
        {
            "evidenceId": "activation-candidate-ready-02",
            "nonce": secondary_subject_activation_nonce,
            "subjectId": secondary_subject_id,
            "deploymentDigest": secondary_deployment_descriptor["digest"],
            "authorityDigest": (
                secondary_activation_authority_descriptor["digest"]
            ),
        }
    )
    secondary_candidate_ready["results"] = {
        "phase": "candidate_ready",
        **{
            check: {
                "actual": "passed",
                "trace": restricted_trace(f"{check}-02"),
            }
            for check in (
                "artifact_readback",
                "file_inventory",
                "slot_generation",
                "service_process",
                "resource_thresholds",
                "harness_readiness",
            )
        },
    }
    secondary_candidate_ready["trace"] = restricted_trace(
        "candidate-ready-02"
    )
    secondary_candidate_ready_descriptor = descriptor_for_bytes(
        "registry.example/consumer/host-evidence",
        "application/vnd.bytedesk.agent.canary-evidence.v1+json",
        canonical_bytes(secondary_candidate_ready),
        host_evidence_policy,
    )
    secondary_decision_proof = deepcopy(decision_proof)
    secondary_decision_proof.update(
        {
            "proofId": "activation-authorization-decision-02",
            "nonce": secondary_subject_activation_nonce,
            "subjectId": secondary_subject_id,
            "deploymentDigest": secondary_deployment_descriptor["digest"],
        }
    )
    secondary_decision_proof["transport"]["responseDigest"] = (
        canonical_digest(
            {
                "profile": "bytedesk.activation-authorization-response/1",
                "planDigest": activation_plan_digest,
                "subjectId": secondary_subject_id,
                "deploymentDigest": secondary_deployment_descriptor[
                    "digest"
                ],
                "nonce": secondary_subject_activation_nonce,
                "decision": "permitted",
            }
        )
    )
    secondary_decision_proof["trace"] = restricted_trace(
        "authorization-decision-02"
    )
    secondary_decision_proof_descriptor = descriptor_for_bytes(
        "registry.example/consumer/authorization-evidence",
        "application/vnd.bytedesk.agent.authorization-decision-proof.v1+json",
        canonical_bytes(secondary_decision_proof),
        authorization_decision_policy,
    )

    def consumer_platform_verification_digest(
        *,
        verification_id: str,
        subject: dict[str, Any],
        policy: dict[str, str],
        adapter_id: str,
    ) -> str:
        adapter_evidence = {
            "profile": "bytedesk.consumer-platform-adapter-verification/1",
            "adapterId": adapter_id,
            "consumerId": consumer_id,
            "subject": deepcopy(subject),
            "policy": deepcopy(policy),
            "operationTime": activation_epoch,
            "decision": "permitted",
        }
        adapter_evidence_digest = register_cas_payload(
            canonical_bytes(adapter_evidence)
        )
        return register_status_verification(
            verification_id,
            permitted_verification_result(
                schema_descriptor=schema_descriptor("verification-result"),
                verification_id=verification_id,
                subject=subject,
                policy=policy,
                evaluated_at=activation_epoch,
                evidence_digests=[adapter_evidence_digest, policy["digest"]],
            ),
        )

    candidate_ready_verification_digest = (
        consumer_platform_verification_digest(
            verification_id="activation-candidate-ready-verification-01",
            subject=candidate_ready_descriptor,
            policy=host_evidence_policy,
            adapter_id="consumer-host-evidence-adapter-v1",
        )
    )
    activation_authority_verification_digest = (
        consumer_platform_verification_digest(
            verification_id="activation-consumer-authority-verification-01",
            subject=activation_authority_descriptor,
            policy=authority_policy,
            adapter_id="consumer-authority-adapter-v1",
        )
    )
    decision_proof_verification_digest = (
        consumer_platform_verification_digest(
            verification_id="activation-decision-proof-verification-01",
            subject=decision_proof_descriptor,
            policy=authorization_decision_policy,
            adapter_id="consumer-authorization-adapter-v1",
        )
    )
    secondary_candidate_ready_verification_digest = (
        consumer_platform_verification_digest(
            verification_id="activation-candidate-ready-verification-02",
            subject=secondary_candidate_ready_descriptor,
            policy=host_evidence_policy,
            adapter_id="consumer-host-evidence-adapter-v1",
        )
    )
    secondary_activation_authority_verification_digest = (
        consumer_platform_verification_digest(
            verification_id=(
                "activation-consumer-authority-verification-02"
            ),
            subject=secondary_activation_authority_descriptor,
            policy=authority_policy,
            adapter_id="consumer-authority-adapter-v1",
        )
    )
    secondary_decision_proof_verification_digest = (
        consumer_platform_verification_digest(
            verification_id="activation-decision-proof-verification-02",
            subject=secondary_decision_proof_descriptor,
            policy=authorization_decision_policy,
            adapter_id="consumer-authorization-adapter-v1",
        )
    )
    deployable_graph = deepcopy(runtime_release["deployments"])
    deployable_graph_digest = canonical_digest(
        {
            "profile": "bytedesk.activation-deployable-graph/1",
            "runtimeRelease": runtime_release_descriptor,
            "deployableGraph": deployable_graph,
        }
    )
    activation_authorization = {
        "contract": "bytedesk.activation-authorization/1",
        "schema": schema_descriptor("activation-authorization"),
        "authorizationId": "activation-authorization-01",
        "rolloutId": candidate_ready["rolloutId"],
        "attemptId": "activation-attempt-01",
        "consumerId": consumer_id,
        "targetId": inputs["targetId"],
        "runtimeRelease": runtime_release_descriptor,
        "activationMode": inputs["activationMode"],
        "deployableGraph": deployable_graph,
        "deployableGraphDigest": deployable_graph_digest,
        "candidateReadyEvidence": [
            {
                "subjectId": deployment_entry["subjectId"],
                "evidence": candidate_ready_descriptor,
                "verificationEvidenceDigest": (
                    candidate_ready_verification_digest
                ),
            },
            {
                "subjectId": secondary_subject_id,
                "evidence": secondary_candidate_ready_descriptor,
                "verificationEvidenceDigest": (
                    secondary_candidate_ready_verification_digest
                ),
            },
        ],
        "authoritySnapshots": [
            {
                "subjectId": deployment_entry["subjectId"],
                "authority": activation_authority_descriptor,
                "verificationEvidenceDigest": (
                    activation_authority_verification_digest
                ),
            },
            {
                "subjectId": secondary_subject_id,
                "authority": secondary_activation_authority_descriptor,
                "verificationEvidenceDigest": (
                    secondary_activation_authority_verification_digest
                ),
            },
        ],
        "authorizationDecisionProofs": [
            {
                "subjectId": deployment_entry["subjectId"],
                "proof": decision_proof_descriptor,
                "verificationEvidenceDigest": (
                    decision_proof_verification_digest
                ),
            },
            {
                "subjectId": secondary_subject_id,
                "proof": secondary_decision_proof_descriptor,
                "verificationEvidenceDigest": (
                    secondary_decision_proof_verification_digest
                ),
            },
        ],
        "releaseEligibility": activation_eligibility_descriptor,
        "releaseEligibilityDigest": activation_eligibility[
            "eligibilityDigest"
        ],
        "releaseEligibilityVerificationEvidenceDigest": (
            activation_eligibility_verification_digest
        ),
        "trustPolicyPinSetDigest": consumer_trust_policy_pin_set[
            "pinSetDigest"
        ],
        "trustPolicyPinSetProviderEvidenceDigest": consumer_pin_set_binding[
            "providerEvidence"
        ]["evidenceDigest"],
        "authorizationNonce": authorization_nonce,
        "slotId": deployment_entry["slotId"],
        "expectedActiveGeneration": 0,
        "nextSlotGeneration": deployment_entry["generation"],
        "fencingToken": 1,
        "regionEpoch": 1,
        "authorizedAt": activation_epoch,
        "expiresAt": add_minutes(activation_epoch, 1),
        "trustPolicy": activation_authorization_policy,
        "authorizationDigest": "sha256:" + ("0" * 64),
        "signingResult": {},
    }
    activation_schema = load_json(
        SCHEMA_ROOT / "activation-authorization.schema.json"
    )
    activation_digest_authority = activation_schema[
        "x-bytedesk-digestAuthority"
    ]
    activation_authorization["authorizationDigest"] = canonical_digest(
        {
            "profile": activation_digest_authority["profile"],
            **{
                field: deepcopy(value)
                for field, value in activation_authorization.items()
                if field not in activation_digest_authority["exclude"]
            },
        }
    )
    activation_authorization["signingResult"] = signing_result(
        "consumer-activation-authorization-v1",
        activation_authorization["authorizationDigest"],
        ACTIVATION_AUTHORIZATION_STATEMENT_MEDIA_TYPE,
        consumer_id,
        "registry.example/consumer/activation-authorizations",
        activation_epoch,
        pin_set=consumer_trust_policy_pin_set,
        policy_ref=activation_authorization_policy,
    )
    activation_authorization_descriptor = descriptor_for_bytes(
        "registry.example/consumer/activation-authorizations",
        ACTIVATION_AUTHORIZATION_MEDIA_TYPE,
        canonical_bytes(activation_authorization),
        activation_authorization_policy,
    )
    activation_authorization_unknown = deepcopy(activation_authorization)
    activation_authorization_unknown["writer"] = "host-reconciler"
    activation_related_digests = set(CAS_PAYLOADS) - activation_payloads_before
    activation_supporting_artifacts = [
        (
            "activation-release-status-eligibility",
            activation_eligibility_descriptor,
            None,
        ),
        ("activation-authority", activation_authority_descriptor, None),
        ("activation-candidate-ready", candidate_ready_descriptor, None),
        ("activation-decision-proof", decision_proof_descriptor, None),
    ]

    deployment_unknown = deepcopy(deployment)
    deployment_unknown["opaqueConsumerDigests"]["rawCredential"] = "forbidden"
    deployment_evidence_backlink = deepcopy(deployment)
    deployment_evidence_backlink["compilationEvidence"] = evidence_descriptor
    deployment_runtime_backlink = deepcopy(deployment)
    deployment_runtime_backlink["runtimeRelease"] = {
        "repository": "registry.example/consumer/runtime-releases",
        "digest": canonical_digest(runtime_release),
        "mediaType": "application/vnd.bytedesk.agent.runtime-release.v1+json",
        "size": len(canonical_bytes(runtime_release)),
        "trustPolicy": runtime_release_policy,
    }
    evidence_backlink = deepcopy(evidence)
    evidence_backlink["statement"]["compilationEvidence"] = evidence_descriptor
    runtime_unknown = deepcopy(runtime_release)
    runtime_unknown["writer"] = "host-reconciler"

    artifact_entries = []
    for role, descriptor, projection in (
        ("compilation-input", lock_descriptor, LOCK_PATH),
        ("render-payload", payload_descriptor, None),
        ("consumer-deployment", deployment_descriptor, DEPLOYMENT_PATH),
        ("private-compilation-evidence", evidence_descriptor, EVIDENCE_PATH),
        ("runtime-release", runtime_release_descriptor, RUNTIME_RELEASE_PATH),
        (
            "activation-authorization",
            activation_authorization_descriptor,
            ACTIVATION_AUTHORIZATION_PATH,
        ),
    ):
        artifact_entries.append(
            {
                "role": role,
                "descriptor": descriptor,
                "projectionPath": (
                    projection.relative_to(REPOSITORY_ROOT).as_posix()
                    if projection is not None
                    else None
                ),
                "blobPath": blob_path(descriptor["digest"])
                .relative_to(REPOSITORY_ROOT)
                .as_posix(),
            }
        )
    supporting_artifacts = []
    for role, descriptor, projection in [
        *materialized_inputs,
        *secondary_runtime_supporting_artifacts,
        *activation_supporting_artifacts,
        ("compilation-authority", authority_descriptor, CONSUMER_AUTHORITY_PATH),
        (
            "private-input-authentication-bundle",
            authentication_bundle_descriptor,
            None,
        ),
        *detached_authentication_artifacts,
        (
            "renderer-attempt-signature-bundle",
            attempt_signing["signatureBundle"],
            None,
        ),
        (
            "renderer-attempt-signer-authentication-evidence",
            attempt_signing["providerAuditEvidence"],
            None,
        ),
        (
            "private-compilation-input-signature-bundle",
            lock_signing_result["signatureBundle"],
            None,
        ),
        (
            "private-compilation-input-signer-authentication-evidence",
            lock_signing_result["providerAuditEvidence"],
            None,
        ),
        (
            "renderer-execution-signature-bundle",
            execution_signing["signatureBundle"],
            None,
        ),
        (
            "renderer-execution-signer-authentication-evidence",
            execution_signing["providerAuditEvidence"],
            None,
        ),
        (
            "consumer-deployment-signature-bundle",
            deployment_signing_result["signatureBundle"],
            None,
        ),
        (
            "consumer-deployment-signer-authentication-evidence",
            deployment_signing_result["providerAuditEvidence"],
            None,
        ),
        (
            "compilation-evidence-signature-bundle",
            evidence["signingResult"]["signatureBundle"],
            None,
        ),
        (
            "compilation-evidence-signer-authentication-evidence",
            evidence["signingResult"]["providerAuditEvidence"],
            None,
        ),
        (
            "runtime-release-signature-bundle",
            runtime_release["signingResult"]["signatureBundle"],
            None,
        ),
        (
            "runtime-release-signer-authentication-evidence",
            runtime_release["signingResult"]["providerAuditEvidence"],
            None,
        ),
    ]:
        supporting_artifacts.append(
            {
                "role": role,
                "descriptor": descriptor,
                "projectionPath": (
                    projection.relative_to(REPOSITORY_ROOT).as_posix()
                    if projection is not None
                    else None
                ),
                "blobPath": blob_path(descriptor["digest"])
                .relative_to(REPOSITORY_ROOT)
                .as_posix(),
            }
        )
    policy_refs = {
        ref["id"]: ref
        for ref in (
            authority_policy,
            input_policy,
            deployment_policy,
            evidence_policy,
            runtime_release_policy,
            status_eligibility_policy,
            activation_authorization_policy,
            public_source_policy,
            public_render_policy,
            private_skill_policy,
            release_status_policy,
            release_status_head_policy,
            attempt_signing["trustPolicy"],
            execution_signing["trustPolicy"],
        )
    }
    supporting_digests = [
        {
            "role": f"trust-policy-{purpose}",
            "digest": ref["digest"],
            "size": len(CAS_PAYLOADS[ref["digest"]]),
            "blobPath": blob_path(ref["digest"])
            .relative_to(REPOSITORY_ROOT)
            .as_posix(),
        }
        for purpose, ref in sorted(policy_refs.items())
    ]
    supporting_digests.extend(
        {
            "role": role,
            "digest": digest,
            "size": len(payload_bytes),
            "blobPath": blob_path(digest)
            .relative_to(REPOSITORY_ROOT)
            .as_posix(),
        }
        for role, digest, payload_bytes in framed_payloads
    )
    supporting_digests.extend(
        {
            "role": (
                "trust-policy-pin-set-"
                + binding["pinSet"]["scope"]
            ),
            "digest": binding["pinSetDescriptor"]["digest"],
            "size": binding["pinSetDescriptor"]["size"],
            "blobPath": blob_path(binding["pinSetDescriptor"]["digest"])
            .relative_to(REPOSITORY_ROOT)
            .as_posix(),
        }
        for binding in pin_set_provider_bindings
    )
    supporting_digests.extend(
        {
            "role": f"release-status-evidence-{index:03d}",
            "digest": digest,
            "size": len(CAS_PAYLOADS[digest]),
            "blobPath": blob_path(digest)
            .relative_to(REPOSITORY_ROOT)
            .as_posix(),
        }
        for index, digest in enumerate(sorted(status_related_digests))
    )
    supporting_digests.extend(
        {
            "role": f"activation-evidence-{index:03d}",
            "digest": digest,
            "size": len(CAS_PAYLOADS[digest]),
            "blobPath": blob_path(digest)
            .relative_to(REPOSITORY_ROOT)
            .as_posix(),
        }
        for index, digest in enumerate(sorted(activation_related_digests))
    )
    signature_verification_vectors = [
        *deepcopy(renderer_signature_verification_vectors),
        *deepcopy(SIGNATURE_VERIFICATION_VECTORS),
    ]
    vector_ids = [
        vector["vectorId"] for vector in signature_verification_vectors
    ]
    vector_tuples = [
        (
            vector["requestId"],
            vector["purpose"],
            vector["signatureBundle"]["digest"],
            vector["subjectDigest"],
            vector["signingRepository"],
            vector["trustPolicy"]["digest"],
            vector["pinSetDigest"],
        )
        for vector in signature_verification_vectors
    ]
    require(
        len(vector_ids) == len(set(vector_ids))
        and len(vector_tuples) == len(set(vector_tuples)),
        "duplicate trusted KMS signature-verification vector",
    )
    semantic_cas_digests = {
        artifact["descriptor"]["digest"]
        for artifact in [*artifact_entries, *supporting_artifacts]
    } | {
        entry["digest"] for entry in supporting_digests
    }
    renderer_closure_digests = set(imported_renderer_payloads)
    expected_cas_digests = semantic_cas_digests | renderer_closure_digests
    require(
        set(CAS_PAYLOADS) == expected_cas_digests,
        "private CAS closure mismatch: unexpected="
        f"{sorted(set(CAS_PAYLOADS) - expected_cas_digests)} missing="
        f"{sorted(expected_cas_digests - set(CAS_PAYLOADS))}",
    )
    cas_inventory = [
        {
            "digest": digest,
            "size": len(CAS_PAYLOADS[digest]),
            "blobPath": blob_path(digest)
            .relative_to(REPOSITORY_ROOT)
            .as_posix(),
            "source": (
                "renderer-closure"
                if digest in renderer_closure_digests
                else "private-graph"
            ),
        }
        for digest in sorted(CAS_PAYLOADS)
    ]
    cases = {
        "profile": "bytedesk.private-compilation-graph-conformance/1",
        "version": 1,
        "casInventory": cas_inventory,
        "trustPolicyPinSetBindings": deepcopy(pin_set_provider_bindings),
        "trustPolicyPinSetProviderAuthenticationVectors": deepcopy(
            pin_set_provider_authentication_vectors
        ),
        "consumerPlatformEvidencePolicyBindings": deepcopy(
            consumer_platform_evidence_policy_bindings
        ),
        "activationHostUseTimeVerification": {
            "operationTime": host_activation_operation_time,
            "verificationEvidenceDigest": (
                host_eligibility_verification_digest
            ),
        },
        "signatureVerificationVectors": sorted(
            signature_verification_vectors,
            key=lambda vector: vector["vectorId"],
        ),
        "keylessVerificationVectors": deepcopy(
            renderer_keyless_verification_vectors
        ),
        "positiveGraph": {
            "lockPath": LOCK_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            "deploymentPath": DEPLOYMENT_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            "evidencePath": EVIDENCE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            "runtimeReleasePath": RUNTIME_RELEASE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            "activationAuthorizationPath": ACTIVATION_AUTHORIZATION_PATH.relative_to(
                REPOSITORY_ROOT
            ).as_posix(),
            "artifacts": artifact_entries,
            "supportingArtifacts": supporting_artifacts,
            "supportingDigests": supporting_digests,
        },
        "requiredMutationClasses": [
            "activation-authorization-digest-only",
            "activation-authorization-expired-at-use",
            "activation-authorization-kms-forgery",
            "activation-deployable-graph-substitution",
            "activation-eligibility-missing-renderer",
            "activation-eligibility-stale-or-wrong-stage",
            "activation-eligibility-verification-result-missing",
            "activation-eligibility-verification-result-substitution",
            "activation-host-use-time-status-expired-boundary",
            "activation-host-use-time-verification-missing",
            "activation-host-use-time-verification-substitution",
            "activation-subject-evidence-coverage-mismatch",
            "activation-target-slot-generation-mismatch",
            "compilation-evidence-cross-field-substitution",
            "compilation-input-signature-bundle-substitution",
            "compilation-input-signing-result-missing",
            "compilation-input-signing-result-substitution",
            "compiler-signer-substitution",
            "contract-bundle-keyless-verification-missing-or-substituted",
            "deployment-cross-field-substitution",
            "deployment-evidence-backlink",
            "deployment-runtime-backlink",
            "descriptor-byte-substitution",
            "detached-input-authentication-missing",
            "detached-input-authentication-role-substitution",
            "forged-current-key-signature",
            "idempotent-byte-replay",
            "lock-contract-replay",
            "lock-schema-replay",
            "payload-self-inventory",
            "purpose-role-substitution",
            "release-status-eligibility-kms-forgery",
            "release-status-eligibility-missing-renderer",
            "release-status-eligibility-pin-provider-substitution",
            "release-status-eligibility-selection-only-reuse",
            "release-status-eligibility-stale",
            "release-status-eligibility-subject-substitution",
            "release-status-eligibility-withdrawn",
            "release-status-eligibility-wrong-nonce",
            "renderer-request-frame-substitution",
            "renderer-response-frame-substitution",
            "runtime-deployment-substitution",
            "runtime-release-digest-missing",
            "runtime-release-signature-bundle-substitution",
            "runtime-release-signing-result-missing",
            "runtime-release-signing-result-substitution",
            "signer-authenticated-identity-substitution",
            "signer-key-separation",
            "signer-public-key-policy-substitution",
            "signer-workload-separation",
            "signing-policy-not-after-boundary",
            "signing-request-field-substitution",
            "signing-time-future",
            "trust-policy-pin-substitution",
        ],
    }

    expected: dict[Path, bytes] = {
        CONSUMER_AUTHORITY_PATH: output_bytes(authority),
        LOCK_PATH: output_bytes(lock),
        PRIVATE_INPUT_AUTHENTICATION_PATH: output_bytes(authentication_bundle),
        MANIFEST_PATH: output_bytes(manifest),
        COMPATIBILITY_RESULT_PATH: output_bytes(manifest["compatibility"]),
        DEPLOYMENT_PATH: output_bytes(deployment),
        EVIDENCE_PATH: output_bytes(evidence),
        RUNTIME_RELEASE_PATH: output_bytes(runtime_release),
        ACTIVATION_AUTHORIZATION_PATH: output_bytes(
            activation_authorization
        ),
        ACTIVATION_AUTHORIZATION_UNKNOWN_PATH: output_bytes(
            activation_authorization_unknown
        ),
        DEPLOYMENT_UNKNOWN_PATH: output_bytes(deployment_unknown),
        DEPLOYMENT_EVIDENCE_BACKLINK_PATH: output_bytes(deployment_evidence_backlink),
        DEPLOYMENT_RUNTIME_BACKLINK_PATH: output_bytes(deployment_runtime_backlink),
        EVIDENCE_BACKLINK_PATH: output_bytes(evidence_backlink),
        PRIVATE_INPUT_AUTHENTICATION_UNKNOWN_PATH: output_bytes(
            authentication_bundle_unknown
        ),
        RUNTIME_UNKNOWN_PATH: output_bytes(runtime_unknown),
        CASE_PATH: output_bytes(cases),
    }
    expected.update(
        {blob_path(digest): payload for digest, payload in CAS_PAYLOADS.items()}
    )
    assert_private_generator_owns_declared_outputs(
        expected.keys(), REPOSITORY_ROOT
    )
    return expected, cases


def write_atomic(path: Path, payload: bytes) -> None:
    """Publish generated bytes through the shared exclusive, fsynced writer."""

    write_bytes(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically refresh private graph projections and exact CAS blobs",
    )
    args = parser.parse_args()
    try:
        expected, cases = build_graph()
        drift = [
            path
            for path, payload in expected.items()
            if not path.exists() or path.read_bytes() != payload
        ]
        unexpected_cas = []
        if CAS_ROOT.exists():
            for path in sorted(CAS_ROOT.iterdir()):
                if path.is_symlink():
                    raise GenerationError(f"private CAS contains a symlink: {path}")
                if path.is_file() and path not in expected:
                    unexpected_cas.append(path)
        if args.write:
            for path in drift:
                write_atomic(path, expected[path])
            for path in unexpected_cas:
                path.unlink()
        elif drift or unexpected_cas:
            paths = ", ".join(
                path.relative_to(REPOSITORY_ROOT).as_posix()
                for path in [*drift, *unexpected_cas]
            )
            raise GenerationError(f"private compilation fixtures are stale: {paths}")
    except (
        ContractToolError,
        FixtureOwnershipError,
        KeyError,
        IndexError,
        TypeError,
        GenerationError,
    ) as error:
        print(f"private compilation fixture generation failed: {error}", file=sys.stderr)
        return 1
    print(
        "private compilation graph fixtures "
        + (
            f"refreshed: {len(drift)} files, removed {len(unexpected_cas)} stale CAS files"
            if args.write
            else "are current"
        )
        + f"; mutation classes={len(cases['requiredMutationClasses'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
