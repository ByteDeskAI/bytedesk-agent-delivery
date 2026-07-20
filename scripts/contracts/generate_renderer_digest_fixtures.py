#!/usr/bin/env python3
"""Refresh renderer fixture digests from the frozen RFC 8785 preimages."""

from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
from typing import Any, Callable

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import _WrappedReferencingError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

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
    signer_authority_binding_digest,
    signer_identity_digest,
)
from trusted_keyless_adapter import (
    SIGNING_REQUEST_MEDIA_TYPE,
    SIGSTORE_BUNDLE_MEDIA_TYPE,
    TrustedKeylessVerificationAdapter,
    keyless_signature_verification_vector,
)
from trusted_kms_adapter import (
    CONTRACT_BUNDLE_MEDIA_TYPES,
    CONTRACT_BUNDLE_RELEASE_PURPOSE,
    TrustedKmsVerificationAdapter,
    signature_verification_vector,
)
from release_status_eligibility import (
    ReleaseStatusEligibilityBuilder,
    permitted_verification_result,
)
from trust_policy_pins import (
    build_initial_product_pin_set,
    build_pin_set_provider_evidence,
    pin_set_document_descriptor,
    pin_set_provider_authentication_vector,
)
from status_merkle import (
    consistency_proof as merkle_consistency_proof,
    inclusion_proof as merkle_inclusion_proof,
    merkle_root,
    status_leaf_digest,
    verify_consistency as verify_merkle_consistency,
    verify_inclusion as verify_merkle_inclusion,
)
from status_head_authority import StatusHeadAuthorityBuilder
from oci_graph import (
    OciGraphVerifier,
    build_oci_blob_stream,
    build_oci_manifest,
    encode_bounded_bytes,
    public_render_publication_payload_digest,
)
from fixture_ownership import (
    assert_renderer_excludes_private_outputs,
    is_private_compilation_owned_output,
    renderer_private_auxiliary_paths,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "contracts" / "fixtures" / "schema"
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"
INVENTORY_PATH = REPOSITORY_ROOT / "contracts" / "bundle" / "v1" / "schema-inventory.json"
DOCUMENTATION_MAP_PATH = REPOSITORY_ROOT / "contracts" / "bundle" / "v1" / "documentation-map.json"
CASE_PATH = REPOSITORY_ROOT / "contracts" / "fixtures" / "operations" / "renderer-digest.cases.json"
CONSUMER_AUTHORITY_COMPILE_PATH = (
    FIXTURE_ROOT / "positive" / "consumer-authority__compile.json"
)
PRIVATE_COMPILATION_INPUT_PATH = (
    FIXTURE_ROOT / "positive" / "private-compilation-input__complete-lock.json"
)
RENDERER_RELEASE_PATHS = {
    "native": FIXTURE_ROOT / "positive" / "renderer-release__native.json",
    "hermes": FIXTURE_ROOT / "positive" / "renderer-release__hermes.json",
    "openclaw": FIXTURE_ROOT / "positive" / "renderer-release__openclaw.json",
}
RENDERER_ALLOWLIST_PATH = FIXTURE_ROOT / "positive" / "renderer-allowlist__compiled.json"
RENDERER_ALLOWLIST_UNKNOWN_AUTHORITY_PATH = (
    FIXTURE_ROOT
    / "negative"
    / "renderer-allowlist__unknown-authority-field.json"
)
PRODUCT_RELEASE_PATH = FIXTURE_ROOT / "positive" / "product-release-manifest__current.json"
PRODUCT_DISTRIBUTION_PATH = FIXTURE_ROOT / "positive" / "product-distribution-manifest__current.json"
CONTRACT_BUNDLE_FIXTURE_PATH = (
    FIXTURE_ROOT / "positive" / "contract-bundle__offline.json"
)
OPERATIONAL_READINESS_REPORT_PATH = (
    FIXTURE_ROOT / "positive" / "operational-readiness-report__ga-denied.json"
)
PRODUCT_RELEASE_TRUST_POLICY_PATH = (
    FIXTURE_ROOT / "positive" / "trust-policy__product-release.json"
)
CONTRACT_BUNDLE_RELEASE_TRUST_POLICY_PATH = (
    FIXTURE_ROOT / "positive" / "trust-policy__contract-bundle-release.json"
)
PRODUCT_RELEASE_TRUST_POLICY_UNKNOWN_AUTHORITY_PATH = (
    FIXTURE_ROOT / "negative" / "trust-policy__unknown-authority-field.json"
)
HARNESS_RENDER_PATH = FIXTURE_ROOT / "positive" / "harness-render__tenant-free.json"
PUBLIC_RENDER_SIGNING_RESULT_PATH = (
    FIXTURE_ROOT / "positive" / "signing-result__public-render.json"
)
PUBLIC_SOURCE_AUTHENTICATION_PATH = (
    FIXTURE_ROOT
    / "positive"
    / "public-source-authentication-evidence__source.json"
)
PRIVATE_SUBJECT_PUBLIC_SOURCE_AUTHENTICATION_PATH = (
    FIXTURE_ROOT
    / "negative"
    / "public-source-authentication-evidence__private-subject.json"
)
RELEASE_STATUS_APPEND_RESOLUTION_PATH = (
    FIXTURE_ROOT
    / "positive"
    / "release-status-append-resolution__committed.json"
)
PRODUCT_RELEASE_SIGNER_AUTHENTICATION_EVIDENCE_PATH = (
    FIXTURE_ROOT
    / "positive"
    / "signer-authentication-evidence__product-release.json"
)
PRODUCT_RELEASE_SIGNER_IDENTITY_PATH = (
    FIXTURE_ROOT / "positive" / "signer-identity__product-release.json"
)
RELEASE_QUALIFICATION_PATH = FIXTURE_ROOT / "positive" / "release-qualification__current.json"
PRODUCT_RELEASE_STATUS_PATH = FIXTURE_ROOT / "positive" / "release-status__product-current.json"
RENDERER_RELEASE_STATUS_PATHS = {
    name: FIXTURE_ROOT / "positive" / f"release-status__renderer-{name}-current.json"
    for name in ("native", "hermes", "openclaw")
}
RENDERER_QUALIFICATION_SELECTION_PATHS = {
    name: FIXTURE_ROOT / "positive" / f"renderer-qualification-selection__{name}-amd64.json"
    for name in ("native", "hermes", "openclaw")
}
RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_PATH = (
    FIXTURE_ROOT / "positive" / "renderer-attempt-authentication-evidence__native-amd64.json"
)
RENDERER_CAS_ROOT = REPOSITORY_ROOT / "contracts" / "fixtures" / "operations" / "renderer-cas"
RENDERER_CAS_BLOB_ROOT = RENDERER_CAS_ROOT / "blobs" / "sha256"
RENDERER_SELECTION_PATHS = {
    "native": FIXTURE_ROOT / "positive" / "renderer-selection__native-amd64.json",
    "hermes": FIXTURE_ROOT / "positive" / "renderer-selection__hermes-amd64.json",
    "openclaw": FIXTURE_ROOT / "positive" / "renderer-selection__openclaw-amd64.json",
}
RENDERER_ATTEMPT_AUTHORITY_PATH = (
    FIXTURE_ROOT / "positive" / "renderer-attempt-authority__native-amd64.json"
)
RENDERER_EXECUTION_RECEIPT_PATH = (
    FIXTURE_ROOT / "positive" / "renderer-execution-receipt__native-amd64.json"
)
RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_PATH = (
    FIXTURE_ROOT
    / "positive"
    / "renderer-execution-authentication-evidence__native-amd64.json"
)

RENDERER_CLOSED_SCHEMA_DENIAL_SOURCES = (
    ("product-distribution-manifest", PRODUCT_DISTRIBUTION_PATH),
    ("product-release-manifest", PRODUCT_RELEASE_PATH),
    (
        "release-qualification-evidence",
        RENDERER_CAS_ROOT
        / "product-distribution-product-distribution-malware-evidence.json",
    ),
    (
        "release-qualification-policy",
        RENDERER_CAS_ROOT / "release-qualification-policy.json",
    ),
    (
        "release-qualification-predicate",
        RENDERER_CAS_ROOT
        / "product-distribution-product-distribution-malware-predicate.json",
    ),
    ("release-qualification", RELEASE_QUALIFICATION_PATH),
    (
        "release-status-head-authentication-evidence",
        RENDERER_CAS_ROOT
        / "product-release-status-head-initial-authentication-evidence.json",
    ),
    (
        "release-status-head-checkpoint",
        RENDERER_CAS_ROOT / "product-release-status-head-initial.json",
    ),
    (
        "release-status-log-consistency-proof",
        RENDERER_CAS_ROOT / "product-release-status-log-epoch-1-to-2.json",
    ),
    (
        "release-status-log-inclusion-proof",
        RENDERER_CAS_ROOT
        / "product-release-status-head-initial-head-inclusion.json",
    ),
    (
        "release-status",
        RENDERER_CAS_ROOT / "product-release-status-sequence-1.json",
    ),
    (
        "renderer-attempt-authentication-evidence",
        RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_PATH,
    ),
    ("renderer-attempt-authority", RENDERER_ATTEMPT_AUTHORITY_PATH),
    (
        "renderer-execution-authentication-evidence",
        RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_PATH,
    ),
    (
        "renderer-qualification-attempt-authentication-evidence",
        RENDERER_CAS_ROOT / "native-qualification-attempt-auth.json",
    ),
    (
        "renderer-qualification-attempt",
        RENDERER_CAS_ROOT / "native-qualification-attempt.json",
    ),
    (
        "renderer-qualification-evidence-tree",
        RENDERER_CAS_ROOT / "native-amd64-qualification-evidence-tree.json",
    ),
    (
        "renderer-qualification-receipt-authentication-evidence",
        RENDERER_CAS_ROOT / "native-qualification-receipt-auth.json",
    ),
    (
        "renderer-qualification-receipt",
        RENDERER_CAS_ROOT / "native-qualification-receipt.json",
    ),
    (
        "renderer-qualification-selection",
        RENDERER_QUALIFICATION_SELECTION_PATHS["native"],
    ),
    (
        "renderer-qualification-suite",
        RENDERER_CAS_ROOT / "qualification-suite.json",
    ),
    (
        "signer-authentication-evidence",
        PRODUCT_RELEASE_SIGNER_AUTHENTICATION_EVIDENCE_PATH,
    ),
    ("signer-identity", PRODUCT_RELEASE_SIGNER_IDENTITY_PATH),
)

CAPABILITY_COVERAGE_PROFILE = "bytedesk.renderer-capability-coverage/1"
EFFECTIVE_SKILL_SET_PROFILE = "bytedesk.renderer-effective-skill-set/1"
EFFECTIVE_INPUT_PROFILE = "bytedesk.renderer-effective-input/1"
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
AUTHORIZED_PRIVATE_INPUT_PROFILE = "bytedesk.authorized-private-compilation-input/1"
PRIVATE_COMPILATION_INPUT_PROFILE = "bytedesk.private-compilation-input-digest/1"
QUALIFICATION_COVERAGE_PROFILE = "bytedesk.renderer-qualification-required-coverage/1"
SIGNING_RESULT_MEDIA_TYPE = "application/vnd.bytedesk.agent.signing-result.v1+json"
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
KMS_SIGNING_PURPOSES = frozenset(
    {
        *PRODUCT_KMS_SIGNING_PURPOSES,
        "consumer-private-skill-v1",
        "consumer-authority-v1",
    }
)
PRIVATE_MANIFEST_EFFECTIVE_INPUT_SUBSTITUTION_CASE = {
    "caseId": "renderer-private-manifest-effective-input-substitution",
    "chainId": "hermes-private-lossy",
    "target": "manifest",
    "mutation": {
        "operation": "replace",
        "path": "/effectiveInputDigest",
        "value": "sha256:" + ("ff" * 32),
    },
    "expectedError": "effective_input_digest_mismatch",
}

# Exact raw bytes addressed by renderer artifact descriptors. JSON authority
# objects are stored as RFC 8785 JCS bytes; opaque artifacts retain their
# declared byte representation. Pretty schema fixtures are projections only.
CAS_PAYLOADS: dict[str, bytes] = {}
OPERATION_PAYLOADS: dict[Path, bytes] = {}
SIGNATURE_VERIFICATION_VECTORS: list[dict[str, Any]] = []
KEYLESS_VERIFICATION_VECTORS: list[dict[str, Any]] = []
ACTIVE_TRUST_POLICY_PIN_SET: dict[str, Any] | None = None
ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR: dict[str, Any] | None = None
ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE: dict[str, Any] | None = None
TRUST_POLICY_PROVIDER_AUTHENTICATION_VECTORS: list[dict[str, Any]] = []
PUBLIC_RENDER_FINALIZATION_RESULT: dict[str, Any] | None = None

MANAGED_SCHEMA_NAMES = (
    "consumer-authority",
    "harness-render",
    "harness-configuration",
    "private-compilation-input",
    "product-distribution-manifest",
    "product-release-manifest",
    "public-source-authentication-evidence",
    "release-qualification",
    "release-qualification-evidence",
    "release-qualification-finalization-matrix",
    "release-qualification-predicate",
    "release-qualification-policy",
    "release-status",
    "release-status-eligibility-evidence",
    "release-status-head-authentication-evidence",
    "release-status-head-checkpoint",
    "release-status-log-consistency-proof",
    "release-status-log-inclusion-proof",
    "renderer-allowlist",
    "renderer-attempt-authority",
    "renderer-attempt-authentication-evidence",
    "renderer-capability",
    "renderer-compatibility-result",
    "renderer-execution-authentication-evidence",
    "renderer-execution-receipt",
    "renderer-input-parameters",
    "renderer-release",
    "renderer-qualification-attempt",
    "renderer-qualification-attempt-authentication-evidence",
    "renderer-qualification-evidence-tree",
    "renderer-qualification-receipt",
    "renderer-qualification-receipt-authentication-evidence",
    "renderer-qualification-selection",
    "renderer-qualification-suite",
    "renderer-selection",
    "render-manifest",
    "signing-result",
    "signer-authentication-evidence",
    "signer-identity",
    "trust-policy-pin-set",
    "trust-policy-pin-set-descriptor",
    "trust-policy-pin-set-provider-evidence",
    "verification-result",
)
RENDERER_POSITIVE_FIXTURE_PREFIXES = (
    "harness-configuration__",
    "harness-render__",
    "product-distribution-manifest__",
    "product-release-manifest__",
    "release-qualification__",
    "release-status__",
    "render-manifest__",
    "renderer-",
)


class GenerationError(RuntimeError):
    """The source fixtures cannot produce a closed renderer digest chain."""


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise GenerationError(detail)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON member: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                GenerationError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def canonical_digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(value)).hexdigest()}"


def raw_digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def is_sentinel_digest(digest: str) -> bool:
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return False
    value = digest.removeprefix("sha256:")
    return len(value) == 64 and any(
        value == value[:width] * (len(value) // width)
        for width in (1, 2, 4, 8, 16)
    )


def register_cas_payload(payload: bytes) -> str:
    digest = raw_digest(payload)
    previous = CAS_PAYLOADS.setdefault(digest, payload)
    require(previous == payload, f"CAS digest collision: {digest}")
    return digest


def domain_digest(
    profile: str, document: dict[str, Any], excluded: set[str]
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


def file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def output_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
        + "\n"
    ).encode("utf-8")


def deterministic_render_archive(manifest: dict[str, Any]) -> bytes:
    payloads: list[tuple[dict[str, Any], bytes]] = []
    for entry in manifest["files"]:
        payload = rfc8785.dumps(
            {
                "profile": "bytedesk.renderer-fixture-output-file/1",
                "scope": manifest["scope"],
                "harnessId": manifest["harnessId"],
                "rendererId": manifest["rendererId"],
                "path": entry["path"],
                "origin": entry["origin"],
            }
        ) + b"\n"
        entry["digest"] = raw_digest(payload)
        entry["size"] = len(payload)
        payloads.append((entry, payload))
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w", format=tarfile.USTAR_FORMAT) as output:
        for entry, payload in payloads:
            header = tarfile.TarInfo(entry["path"])
            header.size = len(payload)
            header.mode = int(entry["mode"], 8)
            header.mtime = 0
            header.uid = 0
            header.gid = 0
            header.uname = ""
            header.gname = ""
            output.addfile(header, io.BytesIO(payload))
    return archive.getvalue()


def deterministic_oci_layer(entries: list[tuple[str, bytes]]) -> bytes:
    """Return a deterministic gzip-compressed USTAR layer for exact blobs."""

    require(bool(entries), "OCI layer requires at least one regular file")
    ordered = sorted(entries, key=lambda entry: entry[0].encode("utf-8"))
    require(
        len({path for path, _ in ordered}) == len(ordered),
        "OCI layer contains duplicate paths",
    )
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w", format=tarfile.USTAR_FORMAT) as output:
        for path, payload in ordered:
            require(
                path and not path.startswith("/") and ".." not in Path(path).parts,
                f"unsafe OCI layer path: {path}",
            )
            header = tarfile.TarInfo(path)
            header.size = len(payload)
            header.mode = 0o644
            header.mtime = 0
            header.uid = 0
            header.gid = 0
            header.uname = ""
            header.gname = ""
            output.addfile(header, io.BytesIO(payload))
    return gzip.compress(archive.getvalue(), compresslevel=9, mtime=0)


def framed_jcs(value: dict[str, Any]) -> bytes:
    payload = rfc8785.dumps(value)
    require(len(payload) <= 16 * 1024 * 1024, "renderer frame exceeds 16 MiB")
    return len(payload).to_bytes(4, "big") + payload


def write_atomic(path: Path, payload: bytes) -> None:
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


def walk(value: Any, visit: Callable[[dict[str, Any]], None]) -> None:
    if isinstance(value, dict):
        visit(value)
        for child in list(value.values()):
            walk(child, visit)
    elif isinstance(value, list):
        for child in value:
            walk(child, visit)


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


def compatibility_coverage_preimage(compatibility: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": COMPATIBILITY_COVERAGE_PROFILE,
        "capabilityDigest": compatibility["capabilityDigest"],
        "capabilityCoverageDigest": compatibility["capabilityCoverageDigest"],
        "inputDigest": compatibility["inputDigest"],
        "semanticResults": compatibility["semanticResults"],
    }


def output_tree_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"profile": OUTPUT_TREE_PROFILE, "files": manifest["files"]}


def reproducibility_preimage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": REPRODUCIBILITY_PROFILE,
        "effectiveInputDigest": manifest["effectiveInputDigest"],
        "compatibilityDigest": canonical_digest(manifest["compatibility"]),
        "output": manifest["output"],
    }


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


def attempt_authentication_evidence_preimage(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile": RENDERER_ATTEMPT_AUTHENTICATION_EVIDENCE_PROFILE,
        "purpose": evidence["purpose"],
        "attemptAuthorityDigest": evidence["attemptAuthorityDigest"],
        "issuerIdentityDigest": evidence["issuerIdentityDigest"],
        "signingResult": evidence["signingResult"],
    }


def execution_authentication_evidence_preimage(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile": RENDERER_EXECUTION_AUTHENTICATION_EVIDENCE_PROFILE,
        "purpose": evidence["purpose"],
        "receiptDigest": evidence["receiptDigest"],
        "attemptAuthorityDigest": evidence["attemptAuthorityDigest"],
        "rendererSelectionDigest": evidence["rendererSelectionDigest"],
        "launcherIdentityDigest": evidence["launcherIdentityDigest"],
        "signingResult": evidence["signingResult"],
    }


def refresh_private_compilation_authorized_input(document: dict[str, Any]) -> None:
    if document.get("contract") != "bytedesk.private-compilation-input/1":
        return
    inputs = document["inputs"]
    inputs.setdefault("runtimeSlot", {"slotId": "candidate-b", "generation": 9})
    inputs.setdefault("activationMode", "isolated_candidate")
    selection = inputs["rendererSelection"]
    inputs["rendererSelectionDigest"] = selection["selectionDigest"]
    effective_skills = inputs["effectiveSkillSet"]
    effective_skills["digest"] = canonical_digest(
        {
            "profile": EFFECTIVE_SKILL_SET_PROFILE,
            "publicSkills": effective_skills["publicSkills"],
            "privateSkills": effective_skills["privateSkills"],
        }
    )
    authorized_inputs = deepcopy(inputs)
    authorized_inputs.pop("authoritySnapshot")
    authorized_inputs.pop("authorizedPrivateInputDigest")
    inputs["authorizedPrivateInputDigest"] = canonical_digest(
        {
            "profile": AUTHORIZED_PRIVATE_INPUT_PROFILE,
            "contract": document["contract"],
            "schema": document["schema"],
            "inputs": authorized_inputs,
        }
    )
    require(
        inputs["authorizedPrivateInputDigest"]
        != canonical_digest(
            {
                "profile": AUTHORIZED_PRIVATE_INPUT_PROFILE,
                "contract": "bytedesk.private-compilation-input/replayed",
                "schema": document["schema"],
                "inputs": authorized_inputs,
            }
        )
        and inputs["authorizedPrivateInputDigest"]
        != canonical_digest(
            {
                "profile": AUTHORIZED_PRIVATE_INPUT_PROFILE,
                "contract": document["contract"],
                "schema": {
                    "id": document["schema"]["id"],
                    "digest": f"sha256:{'0' * 64}",
                },
                "inputs": authorized_inputs,
            }
        ),
        "authorized private input digest accepted a contract or schema replay",
    )


def refresh_private_compilation_final_digest(document: dict[str, Any]) -> None:
    if document.get("contract") != "bytedesk.private-compilation-input/1":
        return
    inputs = document["inputs"]
    document["compilationInputDigest"] = canonical_digest(
        {
            "profile": PRIVATE_COMPILATION_INPUT_PROFILE,
            "contract": document["contract"],
            "schema": document["schema"],
            "inputs": inputs,
        }
    )


def renderer_identity(value: dict[str, Any]) -> tuple[str, str]:
    harness_id = value["harnessId"] if "harnessId" in value else value["targetHarness"]
    return harness_id, value["rendererId"]


def renderer_key(value: dict[str, Any]) -> tuple[str, str, str]:
    harness_id, renderer_id = renderer_identity(value)
    version = value["version"] if "version" in value else value["rendererVersion"]
    return harness_id, renderer_id, version


def artifact_descriptor(
    repository: str,
    media_type: str,
    document: dict[str, Any],
    trust_policy: dict[str, Any],
) -> dict[str, Any]:
    canonical_bytes = rfc8785.dumps(document)
    return {
        "repository": repository,
        "digest": register_cas_payload(canonical_bytes),
        "mediaType": media_type,
        "size": len(canonical_bytes),
        "trustPolicy": deepcopy(trust_policy),
    }


def opaque_descriptor(
    repository: str,
    media_type: str,
    payload: bytes,
    trust_policy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "repository": repository,
        "digest": register_cas_payload(payload),
        "mediaType": media_type,
        "size": len(payload),
        "trustPolicy": deepcopy(trust_policy),
    }


def json_payload_descriptor(
    repository: str,
    media_type: str,
    value: dict[str, Any],
    trust_policy: dict[str, Any],
) -> dict[str, Any]:
    return opaque_descriptor(
        repository,
        media_type,
        rfc8785.dumps(value),
        trust_policy,
    )


def verification_evidence_descriptor(
    repository: str,
    media_type: str,
    payload: bytes,
) -> dict[str, Any]:
    """Describe exact evidence bytes without claiming subject-policy scope."""

    return {
        "repository": repository,
        "digest": register_cas_payload(payload),
        "mediaType": media_type,
        "size": len(payload),
    }


def oci_distribution_descriptor(
    repository: str,
    artifact_id: str,
    architecture: str,
    trust_policy: dict[str, Any],
) -> dict[str, Any]:
    config_bytes = rfc8785.dumps(
        {
            "architecture": architecture,
            "config": {},
            "created": "2026-07-17T12:00:00Z",
            "os": "linux",
            "rootfs": {"diff_ids": [], "type": "layers"},
        }
    )
    config_digest = register_cas_payload(config_bytes)
    manifest_bytes = rfc8785.dumps(
        {
            "annotations": {"ai.bytedesk.artifact.id": artifact_id},
            "config": {
                "digest": config_digest,
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "size": len(config_bytes),
            },
            "layers": [],
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "schemaVersion": 2,
        }
    )
    return opaque_descriptor(
        repository,
        "application/vnd.oci.image.manifest.v1+json",
        manifest_bytes,
        trust_policy,
    )


def product_signer(purpose: str) -> dict[str, Any]:
    """Return the exact independently pinned product signer identity."""

    require(
        purpose in KMS_SIGNING_PURPOSES,
        f"KMS signer purpose is not permitted: {purpose}",
    )

    return {
        "purpose": purpose,
        "credentialKind": "kms_key",
        "keyVersion": f"kms://product/{purpose}/versions/1",
        "publicKeyDigest": canonical_digest(
            {"profile": "bytedesk.test-public-key/1", "purpose": purpose}
        ),
        "algorithm": "ECDSA_P256_SHA256",
        "workloadIdentity": (
            "spiffe://bytedesk.ai/agent-delivery/"
            f"{purpose.removesuffix('-v1')}"
        ),
        "claims": {
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
            "builderDigest": canonical_digest(
                {
                    "profile": "bytedesk.trust-policy-builder/1",
                    "purpose": purpose,
                }
            ),
        },
    }


def contract_bundle_keyless_signer() -> dict[str, Any]:
    """Return the exact keyless identity permitted for contract bundles."""

    workflow = (
        ".github/workflows/contract-release-signer.yml@"
        "1111111111111111111111111111111111111111"
    )
    return {
        "purpose": "contract-bundle-release-v1",
        "credentialKind": "sigstore_keyless",
        "trustedRootDigest": canonical_digest(
            {"profile": "bytedesk.test-sigstore-trusted-root/1"}
        ),
        "algorithm": "ECDSA_P256_SHA256",
        "workloadIdentity": (
            "https://github.com/ByteDeskAI/bytedesk-agent-delivery/" + workflow
        ),
        "claims": {
            "issuer": "https://token.actions.githubusercontent.com",
            "audience": "sigstore",
            "subject": (
                "repo:ByteDeskAI/bytedesk-agent-delivery:environment:"
                "contract-release"
            ),
            "repository": "ByteDeskAI/bytedesk-agent-delivery",
            "workflow": workflow,
            "ref": "refs/tags/v1.0.0",
            "environment": "contract-release",
            "builderDigest": canonical_digest(
                {"profile": "bytedesk.test-contract-release-sealed-builder/1"}
            ),
        },
    }


def contract_bundle_keyless_verification(
    *,
    subject: dict[str, Any],
    subject_document: dict[str, Any],
    policy: dict[str, Any],
    trust_policy: dict[str, str],
    verified_at: str = "2026-07-17T12:00:00Z",
) -> dict[str, Any]:
    """Build the exact trusted-Adapter edge required before product release."""

    repository = "registry.example/product/contracts"
    subject_media_type = (
        "application/vnd.bytedesk.agent.contract-bundle.v1+json"
    )
    require(
        subject
        == {
            "repository": repository,
            "digest": subject["digest"],
            "mediaType": subject_media_type,
            "size": subject["size"],
            "trustPolicy": trust_policy,
        }
        and subject["digest"] == canonical_digest(subject_document)
        and subject["size"] == len(rfc8785.dumps(subject_document)),
        "contract-bundle descriptor is not exact keyless verification input",
    )
    policy_bytes = rfc8785.dumps(policy)
    require(
        trust_policy
        == {"id": CONTRACT_BUNDLE_RELEASE_PURPOSE, "digest": raw_digest(policy_bytes)}
        and policy["scope"]
        == {
            "repositories": [repository],
            "mediaTypes": [subject_media_type],
            "purposes": [CONTRACT_BUNDLE_RELEASE_PURPOSE],
        },
        "contract-bundle keyless policy scope is not exact",
    )
    signer = contract_bundle_keyless_signer()
    require(
        policy["signers"] == [signer],
        "contract-bundle keyless policy does not select one exact signer",
    )
    signer_digest = signer_identity_digest(signer)
    builder_digest = signer["claims"]["builderDigest"]
    pre_sign_certification_digest = canonical_digest(
        {
            "profile": "bytedesk.test-contract-bundle-pre-sign-certification/1",
            "subject": subject,
            "builderDigest": builder_digest,
        }
    )
    signing_request_schema = load_json(
        SCHEMA_ROOT / "signing-request.schema.json"
    )
    signing_request = {
        "contract": "bytedesk.signing-request/1",
        "schema": {
            "id": signing_request_schema["$id"],
            "digest": canonical_digest(signing_request_schema),
        },
        "requestId": "contract-bundle-keyless-release-1",
        "purpose": CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "credentialKind": "sigstore_keyless",
        "signerIdentityDigest": signer_digest,
        "builderDigest": builder_digest,
        "preSignCertificationDigest": pre_sign_certification_digest,
        "repository": repository,
        "digest": subject["digest"],
        "mediaType": subject_media_type,
        "trustPolicy": deepcopy(trust_policy),
        "nonce": "nonce_contract_bundle_release_0123456789abcdef",
        "issuedAt": "2026-07-17T12:00:00Z",
        "expiresAt": "2026-07-17T12:05:00Z",
    }
    signing_request_bytes = rfc8785.dumps(signing_request)
    signing_request_descriptor = verification_evidence_descriptor(
        repository,
        SIGNING_REQUEST_MEDIA_TYPE,
        signing_request_bytes,
    )
    signature_statement = {
        "profile": "bytedesk.test-only-keyless-signature-statement/1",
        "requestId": signing_request["requestId"],
        "requestDigest": signing_request_descriptor["digest"],
        "purpose": CONTRACT_BUNDLE_RELEASE_PURPOSE,
        "credentialKind": "sigstore_keyless",
        "subject": deepcopy(subject),
        "signerIdentityDigest": signer_digest,
        "trustedRootDigest": signer["trustedRootDigest"],
        "authenticatedSigner": deepcopy(signer),
        "builderDigest": builder_digest,
        "preSignCertificationDigest": pre_sign_certification_digest,
        "trustPolicy": deepcopy(trust_policy),
        "verifiedAt": verified_at,
    }
    signature_bundle_document = {
        "profile": "bytedesk.test-only-keyless-adapter-bundle/1",
        "statement": signature_statement,
        "fixtureStatementChecksum": canonical_digest(
            {
                "profile": "bytedesk.test-only-keyless-statement-checksum/1",
                "statement": signature_statement,
            }
        ),
    }
    signature_bundle_bytes = rfc8785.dumps(signature_bundle_document)
    signature_bundle_descriptor = verification_evidence_descriptor(
        repository,
        SIGSTORE_BUNDLE_MEDIA_TYPE,
        signature_bundle_bytes,
    )
    vector_id = canonical_digest(
        {
            "profile": "bytedesk.test-keyless-verification-vector-id/1",
            "subject": subject,
            "signingRequest": signing_request_descriptor,
            "signatureBundle": signature_bundle_descriptor,
            "signerIdentityDigest": signer_digest,
            "verifiedAt": verified_at,
        }
    )
    vector = keyless_signature_verification_vector(
        vector_id=vector_id,
        subject=subject,
        purpose=CONTRACT_BUNDLE_RELEASE_PURPOSE,
        signer_identity_digest_value=signer_digest,
        trusted_root_digest=signer["trustedRootDigest"],
        authenticated_signer=signer,
        builder_digest=builder_digest,
        pre_sign_certification_digest=pre_sign_certification_digest,
        signing_request=signing_request_descriptor,
        signing_request_digest=signing_request_descriptor["digest"],
        signature_bundle=signature_bundle_descriptor,
        signature_bundle_digest=signature_bundle_descriptor["digest"],
        trust_policy=trust_policy,
        verified_at=verified_at,
    )
    KEYLESS_VERIFICATION_VECTORS.append(vector)
    return TrustedKeylessVerificationAdapter([vector]).verify(
        subject=subject,
        subject_bytes=rfc8785.dumps(subject_document),
        policy=policy,
        policy_bytes=policy_bytes,
        permitted_signer=signer,
        signing_request=signing_request,
        signing_request_bytes=signing_request_bytes,
        signing_request_descriptor=signing_request_descriptor,
        signature_bundle_bytes=signature_bundle_bytes,
        signature_bundle_descriptor=signature_bundle_descriptor,
        verification_time=verified_at,
        expected_purpose=CONTRACT_BUNDLE_RELEASE_PURPOSE,
        expected_subject_repository=repository,
        expected_subject_digest=subject["digest"],
        expected_subject_media_type=subject_media_type,
        expected_trust_policy=trust_policy,
        expected_signer_identity_digest=signer_digest,
        expected_trusted_root_digest=signer["trustedRootDigest"],
        expected_workflow=signer["claims"]["workflow"],
        expected_workload_identity=signer["workloadIdentity"],
        expected_claims=signer["claims"],
        expected_builder_digest=builder_digest,
        expected_pre_sign_certification_digest=pre_sign_certification_digest,
        expected_signing_request_digest=signing_request_descriptor["digest"],
        expected_signature_bundle_digest=signature_bundle_descriptor["digest"],
    )


def renderer_signing_result(
    schema_digests: dict[str, str],
    purpose: str,
    subject_digest: str,
    subject_media_type: str,
    evidence_id: str,
    evidence_trust: dict[str, Any],
    repository: str = "registry.example/product/qualification",
    signed_at: str = "2026-07-17T12:00:01Z",
) -> dict[str, Any]:
    require(
        purpose != CONTRACT_BUNDLE_RELEASE_PURPOSE
        and subject_media_type not in CONTRACT_BUNDLE_MEDIA_TYPES,
        "KMS signing cannot sign contract-bundle authority",
    )
    require(
        ACTIVE_TRUST_POLICY_PIN_SET is not None,
        "signing result requires the independently constructed product pin set",
    )
    request_id = f"sign-{evidence_id}"
    signer = product_signer(purpose)
    algorithm = signer["algorithm"]
    key_version = signer["keyVersion"]
    public_key_digest = signer["publicKeyDigest"]
    request_digest = canonical_digest(
        {
            "profile": "bytedesk.renderer-signing-request/1",
            "requestId": request_id,
            "purpose": purpose,
            "subjectDigest": subject_digest,
            "subjectMediaType": subject_media_type,
            "algorithm": algorithm,
            "keyVersion": key_version,
            "publicKeyDigest": public_key_digest,
            "repository": repository,
            "trustPolicy": evidence_trust,
        }
    )
    provider_audit_evidence = build_signer_authentication_evidence(
        schema_descriptor={
            "id": (
                "https://schemas.bytedesk.ai/agent-delivery/v1/"
                "signer-authentication-evidence/1.0.0"
            ),
            "digest": schema_digests[
                "https://schemas.bytedesk.ai/agent-delivery/v1/"
                "signer-authentication-evidence/1.0.0"
            ],
        },
        purpose=purpose,
        subject_media_type=subject_media_type,
        request_id=request_id,
        request_digest=request_digest,
        provider_request_id=f"fixture-kms-request:{request_id}",
        provider_audit_id=f"fixture-kms-audit:{request_id}",
        authenticated_signer=signer,
        issued_at=signed_at,
        trust_policy=evidence_trust,
    )
    provider_audit_evidence_descriptor = json_payload_descriptor(
        repository,
        SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
        provider_audit_evidence,
        evidence_trust,
    )
    signature_statement = {
        "profile": "bytedesk.renderer-authenticated-signature-statement/1",
        "requestId": request_id,
        "requestDigest": request_digest,
        "purpose": purpose,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "algorithm": algorithm,
        "keyVersion": key_version,
        "publicKeyDigest": public_key_digest,
        "repository": repository,
        "trustPolicy": deepcopy(evidence_trust),
        "providerAuditEvidence": deepcopy(
            provider_audit_evidence_descriptor
        ),
        "authenticatedSigner": deepcopy(signer),
        "signedAt": signed_at,
    }
    signature_bundle = json_payload_descriptor(
        repository,
        "application/vnd.dev.sigstore.bundle.v0.3+json",
        {
            "profile": "bytedesk.test-only-kms-adapter-bundle/1",
            "statement": signature_statement,
            "fixtureStatementChecksum": canonical_digest(
                {
                    "profile": "bytedesk.test-only-kms-statement-checksum/1",
                    "statement": signature_statement,
                }
            ),
        },
        evidence_trust,
    )
    signing_schema_id = (
        "https://schemas.bytedesk.ai/agent-delivery/v1/signing-result/1.0.0"
    )
    result = {
        "contract": "bytedesk.signing-result/1",
        "schema": {
            "id": signing_schema_id,
            "digest": schema_digests[signing_schema_id],
        },
        "requestId": request_id,
        "requestDigest": request_digest,
        "purpose": purpose,
        "keyVersion": key_version,
        "algorithm": algorithm,
        "publicKeyDigest": public_key_digest,
        "repository": repository,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "signatureBundle": signature_bundle,
        "trustPolicy": deepcopy(evidence_trust),
        "providerAuditEvidence": provider_audit_evidence_descriptor,
        "signedAt": signed_at,
    }
    vector_id = canonical_digest(
        {
            "profile": "bytedesk.test-kms-verification-vector-id/1",
            "requestId": request_id,
            "purpose": purpose,
            "signatureBundle": signature_bundle,
            "subjectDigest": subject_digest,
            "trustPolicy": evidence_trust,
            "signingRepository": repository,
            "pinSetDigest": ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
            "consumerId": None,
            "providerAuditEvidence": provider_audit_evidence_descriptor,
        }
    )
    SIGNATURE_VERIFICATION_VECTORS.append(
        signature_verification_vector(
            vector_id=vector_id,
            request_id=request_id,
            purpose=purpose,
            signature_bundle=signature_bundle,
            subject_digest=subject_digest,
            subject_media_type=subject_media_type,
            key_version=key_version,
            public_key_digest=public_key_digest,
            algorithm=algorithm,
            trust_policy=evidence_trust,
            signing_repository=repository,
            pin_set_digest=ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
            consumer_id=None,
            provider_audit_evidence=provider_audit_evidence_descriptor,
        )
    )
    return result


def publication_evidence_preimage(document: dict[str, Any]) -> dict[str, Any]:
    schema = load_json(SCHEMA_ROOT / "publication-evidence.schema.json")
    authority = schema.get("x-bytedesk-digestAuthority")
    require(
        isinstance(authority, dict)
        and authority.get("profile") == "bytedesk.publication-evidence-digest/1"
        and authority.get("exclude")
        == ["contract", "schema", "evidenceDigest"],
        "publication-evidence digest authority metadata drift",
    )
    properties = schema.get("properties")
    required = schema.get("required")
    require(
        isinstance(properties, dict)
        and isinstance(required, list)
        and not [field for field in required if field not in document]
        and not [field for field in document if field not in properties],
        "publication-evidence document is not the closed schema shape",
    )
    excluded = set(authority["exclude"])
    return {
        "profile": authority["profile"],
        **{
            field: deepcopy(value)
            for field, value in document.items()
            if field not in excluded
        },
    }


def build_release_status_append_resolution(
    release_status: dict[str, Any],
) -> dict[str, Any]:
    require(
        release_status.get("contract") == "bytedesk.release-status/1"
        and release_status.get("sequence") == 1
        and release_status.get("predecessorDigest") is None
        and release_status.get("authorityDigest")
        == release_status.get("signingResult", {}).get("subjectDigest")
        and set(
            release_status.get("signingResult", {}).get(
                "providerAuditEvidence", {}
            )
        )
        == {"repository", "digest", "mediaType", "size", "trustPolicy"},
        "release-status append fixture requires a canonical initial status",
    )
    repository = "registry.example/product/status"
    artifact_type = "application/vnd.bytedesk.agent.release-status.v1+json"
    release_status_bytes = rfc8785.dumps(release_status)
    status_layer = deterministic_oci_layer(
        [("release-status.json", release_status_bytes)]
    )
    root_descriptor, manifest_bytes, oci_blobs = build_oci_manifest(
        repository=repository,
        artifact_type=artifact_type,
        layers=[("evidence", status_layer)],
    )
    for payload in oci_blobs.values():
        register_cas_payload(payload)
    graph = OciGraphVerifier(
        fetch=lambda requested_repository, digest: oci_blobs[
            (requested_repository, digest)
        ]
    ).verify(
        root_descriptor,
        expected_repository=repository,
        expected_artifact_type=artifact_type,
    )
    manifest = json.loads(
        manifest_bytes,
        object_pairs_hook=strict_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            GenerationError(f"non-finite JSON number: {value}")
        ),
    )
    config_descriptor = deepcopy(manifest["config"])
    layer_descriptors = [
        {
            "digest": descriptor["digest"],
            "mediaType": descriptor["mediaType"],
            "size": descriptor["size"],
        }
        for descriptor in manifest["layers"]
    ]
    status_trust = deepcopy(release_status["trustPolicy"])
    release_status_descriptor = {
        "repository": repository,
        "digest": root_descriptor["digest"],
        "mediaType": root_descriptor["mediaType"],
        "size": root_descriptor["size"],
        "trustPolicy": status_trust,
    }
    append_idempotency_key = "append-release-status-01"
    append_request_digest = canonical_digest(
        {
            "profile": "bytedesk.release-status-append-request/1",
            "idempotencyKey": append_idempotency_key,
            "subjectKind": release_status["subjectKind"],
            "subject": release_status["subject"],
            "expectedHead": None,
            "expectedSequence": 0,
            "status": release_status["status"],
            "reasonCode": release_status["reasonCode"],
            "replacement": release_status.get("replacement"),
            "effectiveAt": release_status["effectiveAt"],
        }
    )
    published_at = "2026-07-17T12:00:04Z"
    readback_at = "2026-07-17T12:00:05Z"
    authorization_context_digest = canonical_digest(
        {
            "profile": (
                "bytedesk.release-status-publication-authorization-context/1"
            ),
            "appendRequestDigest": append_request_digest,
            "authorityDigest": release_status["authorityDigest"],
            "operationTime": published_at,
        }
    )
    publication_idempotency_key = "publish-release-status-01"
    publication_request_digest = canonical_digest(
        {
            "profile": "bytedesk.oci-registry-push-request/1",
            "idempotencyKey": publication_idempotency_key,
            "repository": repository,
            "rootDescriptor": root_descriptor,
            "manifestDigest": raw_digest(manifest_bytes),
            "configDescriptor": config_descriptor,
            "layerDescriptors": layer_descriptors,
            "graphDigest": graph["graphDigest"],
            "artifactType": artifact_type,
            "subject": None,
            "authorizationContextDigest": authorization_context_digest,
        }
    )
    registry_identity = "spiffe://registry.example/workload/oci"
    publication_evidence_schema = load_json(
        SCHEMA_ROOT / "publication-evidence.schema.json"
    )
    publication_evidence = {
        "contract": "bytedesk.publication-evidence/1",
        "schema": {
            "id": publication_evidence_schema["$id"],
            "digest": canonical_digest(publication_evidence_schema),
        },
        "idempotencyKey": publication_idempotency_key,
        "requestDigest": publication_request_digest,
        "authorizationContextDigest": authorization_context_digest,
        "repository": repository,
        "rootDescriptor": deepcopy(root_descriptor),
        "configDescriptor": config_descriptor,
        "layerDescriptors": layer_descriptors,
        "graphDigest": graph["graphDigest"],
        "artifactType": artifact_type,
        "subject": None,
        "registryIdentity": registry_identity,
        "registryIdentityDigest": canonical_digest(
            {
                "profile": "bytedesk.registry-identity-verification/1",
                "identity": registry_identity,
                "repository": repository,
            }
        ),
        "registryRequestId": "registry-request-release-status-01",
        "committedDescriptor": deepcopy(root_descriptor),
        "committedRawDigest": root_descriptor["digest"],
        "readbackDescriptor": deepcopy(root_descriptor),
        "readbackRawDigest": root_descriptor["digest"],
        "publishedAt": published_at,
        "readbackAt": readback_at,
        "evidenceDigest": "sha256:" + ("0" * 64),
    }
    publication_evidence["evidenceDigest"] = canonical_digest(
        publication_evidence_preimage(publication_evidence)
    )
    append_result = {
        "releaseStatus": deepcopy(release_status),
        "releaseStatusDescriptor": release_status_descriptor,
        "authorityDigest": release_status["authorityDigest"],
        "signingResult": deepcopy(release_status["signingResult"]),
        "publicationEvidence": publication_evidence,
        "resultDigest": "sha256:" + ("0" * 64),
    }
    append_result["resultDigest"] = canonical_digest(
        {
            field: deepcopy(value)
            for field, value in append_result.items()
            if field != "resultDigest"
        }
    )
    resolution_schema = load_json(
        SCHEMA_ROOT / "release-status-append-resolution.schema.json"
    )
    return {
        "contract": "bytedesk.release-status-append-resolution/1",
        "schema": {
            "id": resolution_schema["$id"],
            "digest": canonical_digest(resolution_schema),
        },
        "disposition": "committed",
        "idempotencyKey": append_idempotency_key,
        "requestDigest": append_request_digest,
        "appendResult": append_result,
        "resolvedAt": "2026-07-17T12:00:06Z",
    }


def canonicalize_indexed_provider_audit_fixtures(
    documents: dict[Path, dict[str, Any]],
) -> None:
    public_source_documents = [
        document
        for path, document in documents.items()
        if path.parent == RENDERER_CAS_ROOT
        and document.get("contract")
        == "bytedesk.public-source-authentication-evidence/1"
    ]
    canonical_sources = [
        document
        for document in public_source_documents
        if document.get("subject", {}).get("mediaType")
        == "application/vnd.bytedesk.agent.source.v1+json"
    ]
    canonical_skills = [
        document
        for document in public_source_documents
        if document.get("subject", {}).get("mediaType")
        == "application/vnd.bytedesk.agent.skill.v1+json"
    ]
    require(
        len(canonical_sources) == 1 and len(canonical_skills) == 1,
        "renderer public-source authentication projection source drift",
    )
    documents[PUBLIC_SOURCE_AUTHENTICATION_PATH] = deepcopy(
        canonical_sources[0]
    )
    private_subject = deepcopy(canonical_skills[0])
    private_subject["subject"]["trustPolicy"]["id"] = (
        "consumer-private-skill-v1"
    )
    private_subject["evidenceDigest"] = canonical_digest(
        public_source_authentication_preimage(private_subject)
    )
    documents[PRIVATE_SUBJECT_PUBLIC_SOURCE_AUTHENTICATION_PATH] = (
        private_subject
    )
    initial_status_path = (
        RENDERER_CAS_ROOT / "product-release-status-sequence-1.json"
    )
    require(
        initial_status_path in documents,
        "renderer canonical initial release status is missing",
    )
    documents[RELEASE_STATUS_APPEND_RESOLUTION_PATH] = (
        build_release_status_append_resolution(documents[initial_status_path])
    )


def renderer_closed_schema_denial_path(schema_name: str) -> Path:
    return FIXTURE_ROOT / "negative" / f"{schema_name}__unknown-root-field.json"


def materialize_renderer_closed_schema_denials(
    documents: dict[Path, dict[str, Any]],
) -> None:
    require(
        len(RENDERER_CLOSED_SCHEMA_DENIAL_SOURCES) == 23
        and len({name for name, _ in RENDERER_CLOSED_SCHEMA_DENIAL_SOURCES}) == 23,
        "renderer closed-schema denial source inventory drift",
    )
    for schema_name, source_path in RENDERER_CLOSED_SCHEMA_DENIAL_SOURCES:
        require(
            source_path in documents,
            "renderer closed-schema denial source is missing: "
            + source_path.relative_to(REPOSITORY_ROOT).as_posix(),
        )
        positive = documents[source_path]
        require(
            isinstance(positive, dict) and "__unknown" not in positive,
            f"renderer closed-schema positive source is invalid: {schema_name}",
        )
        denial = deepcopy(positive)
        denial["__unknown"] = True
        documents[renderer_closed_schema_denial_path(schema_name)] = denial


def validate_renderer_closed_schema_denials(
    documents: dict[Path, dict[str, Any]],
    managed_schemas: dict[str, dict[str, Any]],
) -> None:
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        schema_id = schema.get("$id")
        require(
            isinstance(schema_id, str) and schema_id not in schemas,
            f"renderer denial validation schema ID is invalid: {path}",
        )
        schemas[schema_id] = schema
    require(
        all(
            schema_id in schemas and schemas[schema_id] == schema
            for schema_id, schema in managed_schemas.items()
        ),
        "renderer denial validation schema registry differs from managed schemas",
    )

    def references(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [
                reference
                for key, child in value.items()
                for reference in (
                    [child]
                    if key in {"$ref", "$dynamicRef"}
                    and isinstance(child, str)
                    else references(child)
                )
            ]
        if isinstance(value, list):
            return [
                reference
                for child in value
                for reference in references(child)
            ]
        return []

    for schema_id, schema in schemas.items():
        for reference in references(schema):
            base = reference.split("#", 1)[0]
            require(
                not base or base in schemas,
                "renderer denial validation has a non-offline schema reference: "
                f"{schema_id} -> {reference}",
            )
    registry = Registry().with_resources(
        (schema_id, Resource.from_contents(schema))
        for schema_id, schema in schemas.items()
    )
    allowed_keywords = {"additionalProperties", "unevaluatedProperties"}
    for schema_name, source_path in RENDERER_CLOSED_SCHEMA_DENIAL_SOURCES:
        schema_id = (
            "https://schemas.bytedesk.ai/agent-delivery/v1/"
            f"{schema_name}/1.0.0"
        )
        require(
            schema_id in schemas,
            f"renderer closed-schema denial schema is missing: {schema_name}",
        )
        validator = Draft202012Validator(
            schemas[schema_id],
            registry=registry,
            format_checker=FormatChecker(),
        )
        try:
            positive_errors = list(validator.iter_errors(documents[source_path]))
            denial_path = renderer_closed_schema_denial_path(schema_name)
            denial_errors = list(validator.iter_errors(documents[denial_path]))
        except (Unresolvable, _WrappedReferencingError) as error:
            raise GenerationError(
                "renderer closed-schema denial reference is not offline-resolvable: "
                f"{schema_name}: {error}"
            ) from error
        require(
            not positive_errors,
            "renderer closed-schema denial source is not positive: "
            f"{schema_name}: "
            + (positive_errors[0].message if positive_errors else ""),
        )
        denial_keywords = {error.validator for error in denial_errors}
        require(
            bool(denial_errors)
            and denial_keywords <= allowed_keywords
            and all(not error.absolute_path for error in denial_errors),
            "renderer closed-schema denial is not root-unknown-only: "
            f"{schema_name}: {sorted(str(value) for value in denial_keywords)}",
        )

    indexed_positive_projections = (
        (
            PRODUCT_RELEASE_TRUST_POLICY_PATH,
            "trust-policy",
        ),
        (
            PUBLIC_RENDER_SIGNING_RESULT_PATH,
            "signing-result",
        ),
        (
            PUBLIC_SOURCE_AUTHENTICATION_PATH,
            "public-source-authentication-evidence",
        ),
        (
            RELEASE_STATUS_APPEND_RESOLUTION_PATH,
            "release-status-append-resolution",
        ),
    )
    for projection_path, schema_name in indexed_positive_projections:
        schema_id = (
            "https://schemas.bytedesk.ai/agent-delivery/v1/"
            f"{schema_name}/1.0.0"
        )
        require(
            projection_path in documents and schema_id in schemas,
            "renderer indexed projection source or schema is missing: "
            + projection_path.relative_to(REPOSITORY_ROOT).as_posix(),
        )
        validator = Draft202012Validator(
            schemas[schema_id],
            registry=registry,
            format_checker=FormatChecker(),
        )
        try:
            projection_errors = list(
                validator.iter_errors(documents[projection_path])
            )
        except (Unresolvable, _WrappedReferencingError) as error:
            raise GenerationError(
                "renderer indexed projection reference is not "
                f"offline-resolvable: {schema_name}: {error}"
            ) from error
        require(
            not projection_errors,
            "renderer indexed projection is not positive: "
            f"{schema_name}: "
            + (projection_errors[0].message if projection_errors else ""),
        )

    private_subject_schema_id = (
        "https://schemas.bytedesk.ai/agent-delivery/v1/"
        "public-source-authentication-evidence/1.0.0"
    )
    private_subject_validator = Draft202012Validator(
        schemas[private_subject_schema_id],
        registry=registry,
        format_checker=FormatChecker(),
    )
    try:
        private_subject_errors = list(
            private_subject_validator.iter_errors(
                documents[PRIVATE_SUBJECT_PUBLIC_SOURCE_AUTHENTICATION_PATH]
            )
        )
    except (Unresolvable, _WrappedReferencingError) as error:
        raise GenerationError(
            "renderer private-subject denial reference is not "
            f"offline-resolvable: {error}"
        ) from error
    require(
        len(private_subject_errors) == 1
        and private_subject_errors[0].validator == "const"
        and list(private_subject_errors[0].absolute_path)
        == ["subject", "trustPolicy", "id"],
        "renderer private-subject denial does not fail only the intended "
        "public trust-policy condition",
    )

    def obsolete_provider_classification_paths(
        value: Any,
        path: tuple[str, ...] = (),
    ) -> list[tuple[str, ...]]:
        if isinstance(value, dict):
            findings = []
            provider_audit_evidence = value.get("providerAuditEvidence")
            if (
                isinstance(provider_audit_evidence, dict)
                and "classification" in provider_audit_evidence
            ):
                findings.append(
                    (*path, "providerAuditEvidence", "classification")
                )
            return findings + [
                finding
                for key, child in value.items()
                for finding in obsolete_provider_classification_paths(
                    child,
                    (*path, key),
                )
            ]
        if isinstance(value, list):
            return [
                finding
                for index, child in enumerate(value)
                for finding in obsolete_provider_classification_paths(
                    child,
                    (*path, str(index)),
                )
            ]
        return []

    obsolete_classifications = [
        (path, finding)
        for path, document in documents.items()
        for finding in obsolete_provider_classification_paths(document)
    ]
    require(
        not obsolete_classifications,
        "renderer projections retain obsolete providerAuditEvidence.classification: "
        + ", ".join(
            f"{path.relative_to(REPOSITORY_ROOT).as_posix()}#"
            + "/".join(finding)
            for path, finding in obsolete_classifications
        ),
    )


def refresh_release_graph(
    documents: dict[Path, dict[str, Any]], schema_digests: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Construct the acyclic C -> R -> A -> P -> M -> S authority graph."""

    allowlist = documents[RENDERER_ALLOWLIST_PATH]
    product_release = documents[PRODUCT_RELEASE_PATH]
    product_release.pop("evidence", None)
    product_release.pop("support", None)

    def schema_descriptor(name: str) -> dict[str, str]:
        schema_id = f"https://schemas.bytedesk.ai/agent-delivery/v1/{name}/1.0.0"
        return {"id": schema_id, "digest": schema_digests[schema_id]}

    trust_policy_schema = load_json(SCHEMA_ROOT / "trust-policy.schema.json")
    trust_policy_template = load_json(PRODUCT_RELEASE_TRUST_POLICY_PATH)

    def exact_trust_policy(
        policy_id: str,
        repositories: list[str],
        media_types: list[str],
        required_evidence: list[str],
    ) -> dict[str, Any]:
        policy = deepcopy(trust_policy_template)
        if (
            policy_id != "contract-bundle-release-v1"
            and SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE not in media_types
        ):
            media_types = [
                *media_types,
                SIGNER_AUTHENTICATION_EVIDENCE_MEDIA_TYPE,
            ]
        if (
            policy_id != "contract-bundle-release-v1"
            and SIGNING_RESULT_MEDIA_TYPE not in media_types
        ):
            media_types = [*media_types, SIGNING_RESULT_MEDIA_TYPE]
        policy["schema"]["digest"] = canonical_digest(trust_policy_schema)
        policy["policyId"] = policy_id
        policy["scope"] = {
            "repositories": repositories,
            "mediaTypes": media_types,
            "purposes": [policy_id],
        }
        policy["signers"] = [
            contract_bundle_keyless_signer()
            if policy_id == "contract-bundle-release-v1"
            else product_signer(policy_id)
        ]
        policy["requiredEvidence"] = required_evidence
        policy_path = RENDERER_CAS_ROOT / f"trust-policy-{policy_id}.json"
        documents[policy_path] = policy
        if policy_id == "product-release-v1":
            documents[PRODUCT_RELEASE_TRUST_POLICY_PATH] = deepcopy(policy)
        elif policy_id == "contract-bundle-release-v1":
            documents[CONTRACT_BUNDLE_RELEASE_TRUST_POLICY_PATH] = deepcopy(
                policy
            )
        return {"id": policy_id, "digest": register_cas_payload(rfc8785.dumps(policy))}

    trust_refs = {
        "product-release-v1": exact_trust_policy(
            "product-release-v1",
            [
                "registry.example/product/agent-delivery",
                "registry.example/product/builders",
                "registry.example/product/contracts",
                "registry.example/product/renderers",
            ],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.bytedesk.agent-spec-semantics.v1+json",
                "application/vnd.bytedesk.agent.product-distribution.v1+json",
                "application/vnd.bytedesk.agent.product-release-manifest.v1+json",
                "application/vnd.bytedesk.agent.renderer-allowlist.v1+json",
                "application/vnd.bytedesk.agent.renderer-capability.v1+json",
                "application/vnd.bytedesk.agent.renderer-release.v1+json",
                "application/vnd.bytedesk.contract-release-evaluator-conformance.v1+json",
            ],
            [
                "schema", "provenance", "sbom", "vulnerability", "license",
                "compatibility", "readiness", "conformance", "determinism",
                "malware", "secret_scan", "executed_distribution",
                "scan_completeness",
            ],
        ),
        "contract-bundle-release-v1": exact_trust_policy(
            "contract-bundle-release-v1",
            ["registry.example/product/contracts"],
            [
                "application/vnd.bytedesk.agent.contract-bundle.v1+json",
            ],
            [
                "schema", "provenance", "sbom", "vulnerability", "license",
                "compatibility", "conformance", "determinism", "malware",
                "secret_scan", "executed_distribution", "scan_completeness",
            ],
        ),
        "release-qualification-policy-v1": exact_trust_policy(
            "release-qualification-policy-v1",
            ["registry.example/product/qualification"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.bytedesk.agent.release-qualification-policy.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-corpus.v1+tar",
                "application/vnd.bytedesk.agent.renderer-qualification-plan.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-suite.v1+json",
            ],
            ["schema", "conformance", "authority"],
        ),
        "release-qualification-attempt-v1": exact_trust_policy(
            "release-qualification-attempt-v1",
            ["registry.example/product/qualification"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json",
            ],
            ["schema", "authority"],
        ),
        "release-qualification-receipt-v1": exact_trust_policy(
            "release-qualification-receipt-v1",
            ["registry.example/product/qualification"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
            ],
            ["schema", "executed_distribution", "authority"],
        ),
        "release-qualification-evidence-v1": exact_trust_policy(
            "release-qualification-evidence-v1",
            [
                "registry.example/product/qualification",
                "registry.example/product/qualification-details",
            ],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.release-qualification-details.v1+json",
                "application/vnd.bytedesk.agent.release-qualification-evidence.v1+json",
                "application/vnd.bytedesk.agent.release-qualification-predicate.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json",
                "application/vnd.bytedesk.agent.renderer-qualification-evidence-leaf-statement.v1+json",
            ],
            ["schema", "conformance", "compatibility", "determinism", "evaluation"],
        ),
        "release-qualification-decision-v1": exact_trust_policy(
            "release-qualification-decision-v1",
            ["registry.example/product/qualification"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.release-qualification-finalization-matrix.v1+json",
                "application/vnd.bytedesk.agent.release-qualification.v1+json",
            ],
            ["schema", "conformance", "authority"],
        ),
        "release-status-v1": exact_trust_policy(
            "release-status-v1",
            ["registry.example/product/status"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.release-status.v1+json",
            ],
            ["schema", "authority"],
        ),
        "release-status-head-v1": exact_trust_policy(
            "release-status-head-v1",
            ["registry.example/product/status-heads"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.release-status-head-authentication-evidence.v1+json",
                "application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json",
                "application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json",
                "application/vnd.bytedesk.agent.release-status-log-inclusion-proof.v1+json",
                "application/vnd.bytedesk.agent.release-status.v1+json",
            ],
            ["schema", "authority", "freshness", "consistency"],
        ),
        "release-status-eligibility-v1": exact_trust_policy(
            "release-status-eligibility-v1",
            ["registry.example/product/status-eligibility"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.release-status-eligibility-evidence.v1+json",
                "application/vnd.bytedesk.agent.release-status-eligibility-evidence-digest.v1+json",
            ],
            ["schema", "authority", "freshness", "consistency"],
        ),
        "renderer-attempt-v1": exact_trust_policy(
            "renderer-attempt-v1",
            [
                "registry.example/product/renderer-attempt-evidence",
                "registry.example/product/renderer-selections",
            ],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
                "application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json",
                "application/vnd.bytedesk.agent.renderer-selection.v1+json",
            ],
            ["schema", "authority"],
        ),
        "renderer-execution-v1": exact_trust_policy(
            "renderer-execution-v1",
            ["registry.example/product/renderer-execution-evidence"],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json",
                "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
            ],
            ["schema", "executed_distribution", "authority"],
        ),
        "public-source-v1": exact_trust_policy(
            "public-source-v1",
            [
                "registry.example/agents/evidence",
                "registry.example/agents/skills",
                "registry.example/agents/source",
                "registry.example/catalog/agents",
                "registry.example/catalog/skills",
            ],
            [
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.bytedesk.agent.public-source-authentication-evidence.v1+json",
                "application/spdx+json",
                "application/vnd.bytedesk.agent.compatibility.v1+json",
                "application/vnd.bytedesk.agent.policy.v1+json",
                "application/vnd.bytedesk.agent.skill.v1+json",
                "application/vnd.bytedesk.agent.source.v1+json",
                "application/vnd.bytedesk.license.v1+json",
                "application/vnd.bytedesk.scan.v1+json",
                "application/vnd.oci.image.layer.v1.tar+gzip",
            ],
            [
                "schema",
                "provenance",
                "sbom",
                "vulnerability",
                "license",
                "malware",
                "secret_scan",
                "scan_completeness",
            ],
        ),
        "public-render-v1": exact_trust_policy(
            "public-render-v1",
            [
                "registry.example/agents/evidence",
                "registry.example/agents/renders",
                "registry.example/public/renders",
            ],
            [
                "application/vnd.bytedesk.agent.compatibility.v1+json",
                "application/vnd.bytedesk.agent.render.v1+json",
                "application/vnd.bytedesk.agent.render-manifest.v1+json",
                "application/vnd.bytedesk.render.bundle.v1+tar",
                "application/vnd.dev.sigstore.bundle.v0.3+json",
                "application/vnd.oci.image.layer.v1.tar+gzip",
            ],
            ["schema", "conformance", "compatibility", "determinism"],
        ),
        "consumer-private-skill-v1": exact_trust_policy(
            "consumer-private-skill-v1",
            [
                "registry.example/consumer/skills",
                "registry.example/skills/escalation",
            ],
            [
                "application/vnd.bytedesk.agent.skill.v1+json",
            ],
            ["schema", "authority", "skill_approval"],
        ),
        "consumer-authority-v1": exact_trust_policy(
            "consumer-authority-v1",
            ["registry.example/consumer/approvals"],
            ["application/vnd.bytedesk.agent.skill-approval.v1+json"],
            ["schema", "authority"],
        ),
    }
    global ACTIVE_TRUST_POLICY_PIN_SET
    global ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR
    global ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE
    pin_set_schema_id = (
        "https://schemas.bytedesk.ai/agent-delivery/v1/"
        "trust-policy-pin-set/1.0.0"
    )
    ACTIVE_TRUST_POLICY_PIN_SET = build_initial_product_pin_set(
        schema_descriptor={
            "id": pin_set_schema_id,
            "digest": schema_digests[pin_set_schema_id],
        },
        pin_set_id="product-agent-delivery-v1",
        purposes=PRODUCT_TRUST_PURPOSES,
        trust_policy_references=trust_refs,
        not_before="2026-01-01T00:00:00Z",
        not_after="2027-01-01T00:00:00Z",
    )
    provider_id = "product-trust-policy-provider"
    provider_authority_digest = canonical_digest(
        {
            "profile": "bytedesk.external-trust-policy-provider-anchor/1",
            "providerId": provider_id,
            "environment": "production",
        }
    )
    pin_set_repository = "registry.example/product/trust-policy-pin-sets"
    ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR = pin_set_document_descriptor(
        repository=pin_set_repository,
        pin_set=ACTIVE_TRUST_POLICY_PIN_SET,
        provider_id=provider_id,
        provider_authority_digest=provider_authority_digest,
    )
    register_cas_payload(rfc8785.dumps(ACTIVE_TRUST_POLICY_PIN_SET))
    pin_provider_evidence_schema_id = (
        "https://schemas.bytedesk.ai/agent-delivery/v1/"
        "trust-policy-pin-set-provider-evidence/1.0.0"
    )
    ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE = (
        build_pin_set_provider_evidence(
            schema_descriptor={
                "id": pin_provider_evidence_schema_id,
                "digest": schema_digests[pin_provider_evidence_schema_id],
            },
            evidence_id="product-pin-set-provider-evidence-r1",
            request_id="activate-product-pin-set-r1",
            idempotency_key="activate-product-pin-set-r1",
            pin_set=ACTIVE_TRUST_POLICY_PIN_SET,
            pin_set_descriptor=ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR,
            provider_request_id="provider-request-product-pin-set-r1",
            provider_audit_id="provider-audit-product-pin-set-r1",
            activated_at="2025-12-31T23:59:58Z",
            observed_at="2025-12-31T23:59:59Z",
        )
    )
    provider_vector_id = canonical_digest(
        {
            "profile": "bytedesk.test-trust-policy-provider-vector-id/1",
            "providerId": provider_id,
            "providerAuthorityDigest": provider_authority_digest,
            "providerRequestId": (
                ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE[
                    "providerRequestId"
                ]
            ),
            "providerAuditId": (
                ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE[
                    "providerAuditId"
                ]
            ),
            "requestDigest": (
                ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE["requestDigest"]
            ),
            "pinSetDigest": ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
        }
    )
    TRUST_POLICY_PROVIDER_AUTHENTICATION_VECTORS.append(
        pin_set_provider_authentication_vector(
            vector_id=provider_vector_id,
            provider_id=provider_id,
            provider_authority_digest=provider_authority_digest,
            provider_request_id=(
                ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE[
                    "providerRequestId"
                ]
            ),
            provider_audit_id=(
                ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE[
                    "providerAuditId"
                ]
            ),
            request_digest=(
                ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE["requestDigest"]
            ),
            pin_set_digest_value=ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
        )
    )
    signer_separation = []
    for purpose in PRODUCT_TRUST_PURPOSES:
        policy_signers = documents[
            RENDERER_CAS_ROOT / f"trust-policy-{purpose}.json"
        ]["signers"]
        require(
            len(policy_signers) == 1
            and policy_signers[0]["purpose"] == purpose,
            f"trust policy does not resolve one exact signer: {purpose}",
        )
        signer = policy_signers[0]
        if purpose == "contract-bundle-release-v1":
            require(
                signer["credentialKind"] == "sigstore_keyless"
                and "keyVersion" not in signer
                and "publicKeyDigest" not in signer
                and signer["claims"]["audience"] == "sigstore"
                and signer["claims"]["environment"] == "contract-release",
                "contract-bundle signer is not exact keyless identity",
            )
            credential_identity = signer["trustedRootDigest"]
        else:
            require(
                signer["credentialKind"] == "kms_key"
                and signer["claims"]["audience"]
                == f"agent-delivery-{purpose}"
                and signer["claims"]["environment"] == purpose
                and signer["claims"]["subject"].endswith(f":{purpose}"),
                f"inconsistent signer workload claims: {purpose}",
            )
            credential_identity = (
                signer["keyVersion"] + ":" + signer["publicKeyDigest"]
            )
        signer_separation.append(
            (
                signer["credentialKind"],
                credential_identity,
                signer["workloadIdentity"],
                signer["claims"]["audience"],
                signer["claims"]["subject"],
            )
        )
    require(
        len(signer_separation) == len(set(signer_separation)),
        "incompatible signer purposes share key or workload claims",
    )
    trust_policy = trust_refs["product-release-v1"]
    contract_bundle_trust_policy = trust_refs[
        "contract-bundle-release-v1"
    ]
    qualification_policy_trust = trust_refs["release-qualification-policy-v1"]
    qualification_attempt_trust = trust_refs["release-qualification-attempt-v1"]
    qualification_receipt_trust = trust_refs["release-qualification-receipt-v1"]
    qualification_evidence_trust = trust_refs["release-qualification-evidence-v1"]
    qualification_decision_trust = trust_refs["release-qualification-decision-v1"]
    status_trust = trust_refs["release-status-v1"]
    status_head_trust = trust_refs["release-status-head-v1"]

    def signing_result(
        purpose: str,
        subject_digest: str,
        subject_media_type: str,
        evidence_id: str,
        evidence_trust: dict[str, Any],
        repository: str = "registry.example/product/qualification",
        signed_at: str = "2026-07-17T12:00:01Z",
    ) -> dict[str, Any]:
        return renderer_signing_result(
            schema_digests,
            purpose,
            subject_digest,
            subject_media_type,
            evidence_id,
            evidence_trust,
            repository,
            signed_at,
        )

    def sign_inline_authority(
        document: dict[str, Any],
        schema_name: str,
        purpose: str,
        subject_media_type: str,
        evidence_id: str,
        authority_trust: dict[str, Any],
        repository: str,
    ) -> None:
        document["authorityDigest"] = "sha256:" + ("0" * 64)
        document["signingResult"] = {}
        authority_schema = load_json(SCHEMA_ROOT / f"{schema_name}.schema.json")
        document["authorityDigest"] = canonical_digest(
            inline_authority_preimage(document, authority_schema)
        )
        document["signingResult"] = signing_result(
            purpose,
            document["authorityDigest"],
            subject_media_type,
            evidence_id,
            authority_trust,
            repository,
        )
    require(
        trust_policy["id"] == "product-release-v1",
        "product release fixture uses the wrong trust purpose",
    )
    product_release["trustPolicy"] = deepcopy(trust_policy)
    contract_bundle_document = documents[CONTRACT_BUNDLE_FIXTURE_PATH]
    contract_bundle_schema = load_json(SCHEMA_ROOT / "contract-bundle.schema.json")
    contract_bundle_document["schema"]["digest"] = canonical_digest(
        contract_bundle_schema
    )
    contract_bundle_document["trustPolicy"] = deepcopy(
        contract_bundle_trust_policy
    )

    def bind_bundle_member(
        member: dict[str, Any], source_path: Path
    ) -> None:
        require(source_path.is_file(), f"missing contract bundle member: {source_path}")
        if source_path.suffix == ".json":
            payload = rfc8785.dumps(load_json(source_path))
        else:
            payload = source_path.read_bytes()
        member["digest"] = register_cas_payload(payload)
        member["size"] = len(payload)

    for schema_member in contract_bundle_document["schemas"]:
        bind_bundle_member(
            schema_member,
            REPOSITORY_ROOT / "contracts" / schema_member["path"],
        )
        schema_member["trustPolicy"] = deepcopy(contract_bundle_trust_policy)
    bundle_document_sources = {
        "api/openapi.json": REPOSITORY_ROOT
        / "contracts/openapi/v1/agent-delivery.openapi.json",
        "events/asyncapi.json": REPOSITORY_ROOT
        / "contracts/asyncapi/v1/agent-delivery.asyncapi.json",
    }
    for member in contract_bundle_document["documents"]:
        require(
            member["path"] in bundle_document_sources,
            f"unknown contract bundle document: {member['path']}",
        )
        bind_bundle_member(member, bundle_document_sources[member["path"]])
    for field, source_path in {
        "fixtureIndex": FIXTURE_ROOT / "index.json",
        "schemaInventory": INVENTORY_PATH,
        "compatibility": REPOSITORY_ROOT / "contracts/bundle/v1/compatibility.json",
        "documentationMap": DOCUMENTATION_MAP_PATH,
    }.items():
        bind_bundle_member(contract_bundle_document[field], source_path)
    contract_bundle_document["buildInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.contract-bundle-build-input/1",
            "schemas": contract_bundle_document["schemas"],
            "documents": contract_bundle_document["documents"],
            "fixtureIndex": contract_bundle_document["fixtureIndex"],
            "schemaInventory": contract_bundle_document["schemaInventory"],
            "compatibility": contract_bundle_document["compatibility"],
            "documentationMap": contract_bundle_document["documentationMap"],
        }
    )
    product_release["contractBundle"] = artifact_descriptor(
        "registry.example/product/contracts",
        "application/vnd.bytedesk.agent.contract-bundle.v1+json",
        contract_bundle_document,
        contract_bundle_trust_policy,
    )
    product_release["contractBundleVerification"] = (
        contract_bundle_keyless_verification(
            subject=product_release["contractBundle"],
            subject_document=contract_bundle_document,
            policy=documents[
                RENDERER_CAS_ROOT
                / "trust-policy-contract-bundle-release-v1.json"
            ],
            trust_policy=contract_bundle_trust_policy,
        )
    )
    product_release["builder"] = oci_distribution_descriptor(
        "registry.example/product/builders",
        "agent-delivery-release-builder-1.0.0",
        "amd64",
        trust_policy,
    )
    product_release["toolchainDigest"] = canonical_digest(
        {"profile": "bytedesk.product-toolchain/1", "version": product_release["version"]}
    )
    product_release["dependencyLockDigest"] = canonical_digest(
        {"profile": "bytedesk.product-dependency-lock/1", "version": product_release["version"]}
    )

    capabilities: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path, document in documents.items():
        if "/positive/renderer-capability__" not in path.as_posix():
            continue
        key = renderer_key(document)
        document.pop("rendererRelease", None)
        document.setdefault(
            "source",
            {
                "repository": "https://github.com/ByteDeskAI/bytedesk-agent-delivery",
                "commit": hashlib.sha256(f"{key[0]}:{key[1]}".encode()).hexdigest()[:40],
                "treeDigest": canonical_digest(
                    {"profile": "bytedesk.renderer-capability-source/1", "key": list(key)}
                ),
            },
        )
        document["trustPolicy"] = deepcopy(trust_policy)
        document["semanticRegistry"] = json_payload_descriptor(
            "registry.example/product/contracts",
            "application/vnd.bytedesk.agent-spec-semantics.v1+json",
            {
                "profile": "bytedesk.agent-spec-semantics/1",
                "version": document["agentSpecVersion"],
                "semantics": deepcopy(document["semantics"]),
            },
            trust_policy,
        )
        document["semanticCount"] = len(document["semantics"])
        document["coverageDigest"] = canonical_digest(
            capability_coverage_preimage(document)
        )
        require(key not in capabilities, f"duplicate positive capability: {key}")
        capabilities[key] = document

    releases: dict[tuple[str, str, str], dict[str, Any]] = {}
    release_descriptors: dict[tuple[str, str, str], dict[str, Any]] = {}
    for harness_id, release_path in RENDERER_RELEASE_PATHS.items():
        release = documents[release_path]
        capability = next(
            value
            for key, value in capabilities.items()
            if key[0] == harness_id and key[1] == harness_id
        )
        key = renderer_key(capability)
        release["harnessId"] = harness_id
        release["rendererId"] = harness_id
        release["version"] = capability["rendererVersion"]
        release["rendererContractVersion"] = capability["rendererContractVersion"]
        release["source"] = deepcopy(capability["source"])
        release["supportedAgentSpecVersions"] = [capability["agentSpecVersion"]]
        release["supportedHarnessVersions"] = deepcopy(
            capability["supportedHarnessVersions"]
        )
        release.pop("productDistributionDigest", None)
        release.pop("compiledAllowlistDigest", None)
        release.pop("evidence", None)
        release.pop("support", None)
        release["trustPolicy"] = deepcopy(trust_policy)
        release["builder"] = oci_distribution_descriptor(
            "registry.example/product/builders",
            f"{harness_id}-renderer-builder-{capability['rendererVersion']}",
            "amd64",
            trust_policy,
        )
        release["toolchainDigest"] = canonical_digest(
            {
                "profile": "bytedesk.renderer-toolchain/1",
                "harnessId": harness_id,
                "version": capability["rendererVersion"],
            }
        )
        release["dependencyLockDigest"] = canonical_digest(
            {
                "profile": "bytedesk.renderer-dependency-lock/1",
                "harnessId": harness_id,
                "version": capability["rendererVersion"],
            }
        )
        release["capabilityManifest"] = artifact_descriptor(
            "registry.example/product/renderers",
            "application/vnd.bytedesk.agent.renderer-capability.v1+json",
            capability,
            trust_policy,
        )
        release["platforms"] = []
        for platform_name in capability["supportedPlatforms"]:
            os_name, architecture = platform_name.split("/", 1)
            distribution = oci_distribution_descriptor(
                "registry.example/product/renderers",
                f"{harness_id}-renderer-{capability['rendererVersion']}-{platform_name}",
                architecture,
                trust_policy,
            )
            release["platforms"].append(
                {"os": os_name, "architecture": architecture, "distribution": distribution}
            )
        release["normalizationProfile"] = "bytedesk-render-normalization-v1"
        sign_inline_authority(
            release,
            "renderer-release",
            "product-release-v1",
            "application/vnd.bytedesk.agent.renderer-release.v1+json",
            f"renderer-release-{harness_id}-{capability['rendererVersion']}",
            trust_policy,
            "registry.example/product/renderers",
        )
        descriptor = artifact_descriptor(
            "registry.example/product/renderers",
            "application/vnd.bytedesk.agent.renderer-release.v1+json",
            release,
            trust_policy,
        )
        releases[key] = release
        release_descriptors[key] = descriptor

    allowlist.pop("productDistributionDigest", None)
    allowlist["trustPolicy"] = deepcopy(trust_policy)
    allowlist["entries"] = []
    for key, capability_document in sorted(capabilities.items()):
        descriptor = deepcopy(release_descriptors[key])
        allowlist["entries"].append(
            {
                "harnessId": key[0],
                "rendererId": key[1],
                "version": key[2],
                "release": descriptor,
                "platforms": deepcopy(capability_document["supportedPlatforms"]),
            }
        )
    sign_inline_authority(
        allowlist,
        "renderer-allowlist",
        "product-release-v1",
        "application/vnd.bytedesk.agent.renderer-allowlist.v1+json",
        "compiled-renderer-allowlist",
        trust_policy,
        "registry.example/product/agent-delivery",
    )
    allowlist_descriptor = artifact_descriptor(
        "registry.example/product/agent-delivery",
        "application/vnd.bytedesk.agent.renderer-allowlist.v1+json",
        allowlist,
        trust_policy,
    )

    executable_product = oci_distribution_descriptor(
        "registry.example/product/agent-delivery",
        f"agent-delivery-{product_release['version']}",
        "amd64",
        trust_policy,
    )
    product_distribution = documents.get(PRODUCT_DISTRIBUTION_PATH, {})
    product_distribution.update(
        {
            "contract": "bytedesk.product-distribution-manifest/1",
            "schema": schema_descriptor("product-distribution-manifest"),
            "version": product_release["version"],
            "executableDistribution": executable_product,
            "embeddedCompiledAllowlist": deepcopy(allowlist_descriptor),
            "contractBundle": deepcopy(product_release["contractBundle"]),
            "builder": deepcopy(product_release["builder"]),
            "toolchainDigest": product_release["toolchainDigest"],
            "dependencyLockDigest": product_release["dependencyLockDigest"],
            "builtAt": product_release["publishedAt"],
            "trustPolicy": deepcopy(trust_policy),
        }
    )
    documents[PRODUCT_DISTRIBUTION_PATH] = product_distribution
    product_distribution["schema"] = schema_descriptor("product-distribution-manifest")
    product_distribution["embeddedCompiledAllowlist"] = deepcopy(allowlist_descriptor)
    product_distribution["contractBundle"] = deepcopy(product_release["contractBundle"])
    product_distribution["trustPolicy"] = deepcopy(trust_policy)
    product_distribution["executableDistribution"]["trustPolicy"] = deepcopy(
        trust_policy
    )
    sign_inline_authority(
        product_distribution,
        "product-distribution-manifest",
        "product-release-v1",
        "application/vnd.bytedesk.agent.product-distribution.v1+json",
        "product-distribution-current",
        trust_policy,
        "registry.example/product/agent-delivery",
    )
    product_distribution_descriptor = artifact_descriptor(
        "registry.example/product/agent-delivery",
        "application/vnd.bytedesk.agent.product-distribution.v1+json",
        product_distribution,
        trust_policy,
    )

    product_release["compiledAllowlist"] = deepcopy(allowlist_descriptor)
    product_release["productDistribution"] = deepcopy(product_distribution_descriptor)
    product_release["rendererReleases"] = sorted(
        [deepcopy(entry["release"]) for entry in allowlist["entries"]],
        key=lambda value: (value["repository"].encode("utf-8"), value["digest"]),
    )
    required_roles = [
        "provenance", "sbom", "vulnerability", "malware", "secret_scan",
        "scan_completeness", "license", "conformance", "compatibility",
        "determinism", "sandbox", "executed_distribution",
    ]
    metadata_roles = ["provenance", "conformance", "compatibility"]
    contract_roles = [
        "provenance", "vulnerability", "malware", "secret_scan",
        "scan_completeness", "license", "conformance", "compatibility",
        "determinism",
    ]
    coverage_roles = {
        "product_release": metadata_roles,
        "product_distribution": required_roles,
        "contract_bundle": contract_roles,
        "every_renderer_release": metadata_roles,
        "every_renderer_executable": required_roles,
    }
    scope_subject_role = {
        "product_release": "product_release",
        "product_distribution": "product_distribution",
        "contract_bundle": "contract_bundle",
        "every_renderer_release": "renderer_release",
        "every_renderer_executable": "renderer_executable",
    }
    required_coverage = [
        {
            "requirementId": f"{scope.replace('_', '-')}-{role.replace('_', '-')}",
            "role": role,
            "subjectScope": scope,
            "subjectRole": scope_subject_role[scope],
        }
        for scope, roles in coverage_roles.items()
        for role in roles
    ]
    sandbox_profile_digest = canonical_digest(
        {"profile": "bytedesk.renderer-qualification-sandbox/1"}
    )
    qualification_worker_profile_digest = canonical_digest(
        {"profile": "bytedesk.renderer-qualification-worker/1", "version": "1.0.0"}
    )
    qualification_protocol_profile_digest = canonical_digest(
        {"profile": "bytedesk.renderer-qualification-protocol/1", "version": "1.0.0"}
    )
    resource_profile_digest = canonical_digest(
        {"profile": "bytedesk.renderer-qualification-resources/1", "cpu": 2, "memoryMiB": 4096}
    )
    timeout_profile_digest = canonical_digest(
        {"profile": "bytedesk.renderer-qualification-timeouts/1", "attemptSeconds": 900}
    )
    conformance_plan = json_payload_descriptor(
        "registry.example/product/qualification",
        "application/vnd.bytedesk.agent.renderer-qualification-plan.v1+json",
        {
            "profile": "bytedesk.renderer-qualification-plan/1",
            "version": "1.0.0",
            "requiredCoverage": required_coverage,
        },
        qualification_policy_trust,
    )
    input_corpus = opaque_descriptor(
        "registry.example/product/qualification",
        "application/vnd.bytedesk.agent.renderer-qualification-corpus.v1+tar",
        b"bytedesk-renderer-qualification-corpus-v1\n",
        qualification_policy_trust,
    )
    evaluator_distribution = oci_distribution_descriptor(
        "registry.example/product/qualification",
        "renderer-qualification-evaluator-1.0.0",
        "amd64",
        qualification_policy_trust,
    )
    suite = {
        "contract": "bytedesk.renderer-qualification-suite/1",
        "schema": schema_descriptor("renderer-qualification-suite"),
        "suiteId": "renderer-release-qualification",
        "version": "1.0.0",
        "requiredRoles": required_roles,
        "requiredCoverage": required_coverage,
        "conformancePlan": deepcopy(conformance_plan),
        "inputCorpus": deepcopy(input_corpus),
        "evaluatorDistribution": deepcopy(evaluator_distribution),
        "contractBundle": deepcopy(product_release["contractBundle"]),
        "qualificationWorkerProfileDigest": qualification_worker_profile_digest,
        "qualificationProtocolProfileDigest": qualification_protocol_profile_digest,
        "sandboxProfileDigest": sandbox_profile_digest,
        "resourceProfileDigest": resource_profile_digest,
        "timeoutProfileDigest": timeout_profile_digest,
        "trustPolicy": deepcopy(qualification_policy_trust),
    }
    suite_path = RENDERER_CAS_ROOT / "qualification-suite.json"
    documents[suite_path] = suite
    suite_descriptor = artifact_descriptor(
        "registry.example/product/qualification",
        "application/vnd.bytedesk.agent.renderer-qualification-suite.v1+json",
        suite,
        qualification_policy_trust,
    )
    minimum_qualification_coverage_digest = canonical_digest(
        {
            "profile": QUALIFICATION_COVERAGE_PROFILE,
            "requiredCoverage": required_coverage,
        }
    )
    policy = {
        "contract": "bytedesk.release-qualification-policy/1",
        "schema": schema_descriptor("release-qualification-policy"),
        "policyId": "product-release-qualification",
        "qualificationSuite": deepcopy(suite_descriptor),
        "requiredCoverageDigest": minimum_qualification_coverage_digest,
        "requireEveryRendererRelease": True,
        "requireEveryRendererPlatform": True,
        "allowExpiredEvidence": False,
        "decisionRule": "exact_required_coverage_matrix_passes",
        "trustPolicy": deepcopy(qualification_policy_trust),
    }
    sign_inline_authority(
        policy,
        "release-qualification-policy",
        "release-qualification-policy-v1",
        "application/vnd.bytedesk.agent.release-qualification-policy.v1+json",
        "release-qualification-policy-current",
        qualification_policy_trust,
        "registry.example/product/qualification",
    )
    policy_path = RENDERER_CAS_ROOT / "release-qualification-policy.json"
    documents[policy_path] = policy
    policy_descriptor = artifact_descriptor(
        "registry.example/product/qualification",
        "application/vnd.bytedesk.agent.release-qualification-policy.v1+json",
        policy,
        qualification_policy_trust,
    )
    product_release["qualificationPolicy"] = deepcopy(policy_descriptor)
    product_release["qualificationSuite"] = deepcopy(suite_descriptor)
    product_release["minimumQualificationCoverageDigest"] = (
        minimum_qualification_coverage_digest
    )
    sign_inline_authority(
        product_release,
        "product-release-manifest",
        "product-release-v1",
        "application/vnd.bytedesk.agent.product-release-manifest.v1+json",
        "product-release-current",
        trust_policy,
        "registry.example/product/agent-delivery",
    )
    product_release_descriptor = artifact_descriptor(
        "registry.example/product/agent-delivery",
        "application/vnd.bytedesk.agent.product-release-manifest.v1+json",
        product_release,
        trust_policy,
    )

    native_key = next(key for key in releases if key[0] == "native")
    qualification_leaf_material: dict[
        tuple[str, str, str], dict[str, Any]
    ] = {}

    def qualification_specs(
        key: tuple[str, str, str], platform_name: str
    ) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
        specs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
        platform = next(
            value
            for value in releases[key]["platforms"]
            if f"{value['os']}/{value['architecture']}" == platform_name
        )
        for requirement in required_coverage:
            scope = requirement["subjectScope"]
            if scope == "product_release" and key == native_key and platform_name == "linux/amd64":
                specs.append((requirement, deepcopy(product_release_descriptor), "product-release"))
            elif scope == "product_distribution" and key == native_key and platform_name == "linux/amd64":
                specs.append((requirement, deepcopy(product_distribution_descriptor), "product-distribution"))
            elif scope == "contract_bundle" and key == native_key and platform_name == "linux/amd64":
                specs.append((requirement, deepcopy(product_release["contractBundle"]), "contract-bundle"))
            elif scope == "every_renderer_release" and platform_name == "linux/amd64":
                specs.append((requirement, deepcopy(release_descriptors[key]), f"renderer-{key[0]}-release"))
            elif scope == "every_renderer_executable":
                specs.append((requirement, deepcopy(platform["distribution"]), f"renderer-{key[0]}-{platform['architecture']}"))
        return sorted(
            specs,
            key=lambda value: (
                value[0]["requirementId"].encode("utf-8"),
                value[0]["role"].encode("utf-8"),
                value[1]["digest"],
            ),
        )

    def qualification_evidence_tree(
        key: tuple[str, str, str],
        platform_name: str,
        selection: dict[str, Any],
        attempt: dict[str, Any],
        collector_identity_digest: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        leaves: list[dict[str, Any]] = []
        for index, (requirement, subject, subject_token) in enumerate(
            qualification_specs(key, platform_name)
        ):
            artifact_id = f"{subject_token}-{requirement['requirementId']}"
            details = json_payload_descriptor(
                "registry.example/product/qualification-details",
                "application/vnd.bytedesk.agent.release-qualification-details.v1+json",
                {
                    "profile": "bytedesk.release-qualification-details/1",
                    "requirementId": requirement["requirementId"],
                    "role": requirement["role"],
                    "subjectRole": requirement["subjectRole"],
                    "subjectDigest": subject["digest"],
                    "qualificationSelectionDigest": selection["selectionDigest"],
                    "result": "pass",
                },
                qualification_evidence_trust,
            )
            statement = {
                "profile": "bytedesk.renderer-qualification-evidence-leaf-statement/1",
                "requirementId": requirement["requirementId"],
                "role": requirement["role"],
                "subjectRole": requirement["subjectRole"],
                "subject": deepcopy(subject),
                "details": deepcopy(details),
                "result": "pass",
            }
            statement_digest = canonical_digest(statement)
            producer_signing_result = signing_result(
                "release-qualification-evidence-v1",
                statement_digest,
                "application/vnd.bytedesk.agent.renderer-qualification-evidence-leaf-statement.v1+json",
                f"{artifact_id}-leaf",
                qualification_evidence_trust,
            )
            leaf = {
                "index": index,
                "requirementId": requirement["requirementId"],
                "role": requirement["role"],
                "subjectRole": requirement["subjectRole"],
                "subject": deepcopy(subject),
                "details": deepcopy(details),
                "result": "pass",
                "statementDigest": statement_digest,
                "producerSigningResult": producer_signing_result,
                "leafDigest": f"sha256:{'0' * 64}",
            }
            leaf["leafDigest"] = domain_digest(
                "bytedesk.renderer-qualification-evidence-leaf-digest/1",
                leaf,
                {"leafDigest"},
            )
            material_key = (
                selection["selectionDigest"],
                requirement["requirementId"],
                subject["digest"],
            )
            require(
                material_key not in qualification_leaf_material,
                f"duplicate qualification leaf: {material_key}",
            )
            qualification_leaf_material[material_key] = {
                "artifactId": artifact_id,
                "details": details,
                "leaf": leaf,
            }
            leaves.append(leaf)
        require(leaves, f"qualification execution has no evidence leaves: {key}:{platform_name}")
        tree = {
            "contract": "bytedesk.renderer-qualification-evidence-tree/1",
            "schema": schema_descriptor("renderer-qualification-evidence-tree"),
            "treeId": f"{key[0]}-{platform_name.replace('/', '-')}-qualification-tree",
            "qualificationSelectionDigest": selection["selectionDigest"],
            "qualificationSuite": deepcopy(suite_descriptor),
            "attemptAuthorityDigest": attempt["authorityDigest"],
            "platform": platform_name,
            "executedDistribution": deepcopy(selection["executableDistribution"]),
            "collectorIdentityDigest": collector_identity_digest,
            "leaves": leaves,
            "treeDigest": f"sha256:{'0' * 64}",
            "producedAt": "2026-07-17T12:00:00Z",
        }
        tree["treeDigest"] = domain_digest(
            "bytedesk.renderer-qualification-evidence-tree-digest/1",
            tree,
            {"contract", "schema", "treeDigest"},
        )
        descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json",
            tree,
            qualification_receipt_trust,
        )
        documents[
            RENDERER_CAS_ROOT
            / f"{key[0]}-{platform_name.split('/', 1)[1]}-qualification-evidence-tree.json"
        ] = tree
        return tree, descriptor

    qualification_selection_descriptors: dict[tuple[str, str, str], dict[str, Any]] = {}
    qualification_execution: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, release in sorted(releases.items()):
        platform = next(
            value for value in release["platforms"] if value["architecture"] == "amd64"
        )
        selection = {
            "contract": "bytedesk.renderer-qualification-selection/1",
            "schema": schema_descriptor("renderer-qualification-selection"),
            "purpose": "release_qualification",
            "productRelease": deepcopy(product_release_descriptor),
            "productDistribution": deepcopy(product_distribution_descriptor),
            "compiledAllowlist": deepcopy(allowlist_descriptor),
            "capability": deepcopy(release["capabilityManifest"]),
            "rendererRelease": deepcopy(release_descriptors[key]),
            "targetHarness": key[0],
            "targetHarnessVersion": release["supportedHarnessVersions"][0],
            "rendererId": key[1],
            "rendererVersion": key[2],
            "targetPlatform": "linux/amd64",
            "executableDistribution": deepcopy(platform["distribution"]),
            "contractBundle": deepcopy(product_release["contractBundle"]),
            "rendererSchemas": deepcopy(release["schemas"]),
            "workerProfileDigest": release["workerProtocol"]["profileDigest"],
            "normalizationProfile": release["normalizationProfile"],
            "qualificationSuite": deepcopy(suite_descriptor),
            "conformancePlan": deepcopy(conformance_plan),
            "inputCorpus": deepcopy(input_corpus),
            "evaluatorDistribution": deepcopy(evaluator_distribution),
            "qualificationWorkerProfileDigest": qualification_worker_profile_digest,
            "qualificationProtocolProfileDigest": qualification_protocol_profile_digest,
            "sandboxProfileDigest": sandbox_profile_digest,
            "resourceProfileDigest": resource_profile_digest,
            "timeoutProfileDigest": timeout_profile_digest,
            "productionEligible": False,
            "outputDisposition": "discard_after_evidence_capture",
            "selectionDigest": f"sha256:{'0' * 64}",
        }
        selection["selectionDigest"] = domain_digest(
            "bytedesk.renderer-qualification-selection-digest/1",
            selection,
            {"contract", "schema", "selectionDigest"},
        )
        selection_path = RENDERER_QUALIFICATION_SELECTION_PATHS[key[0]]
        documents[selection_path] = selection
        selection_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json",
            selection,
            qualification_attempt_trust,
        )
        qualification_selection_descriptors[key] = selection_descriptor

        attempt = {
            "contract": "bytedesk.renderer-qualification-attempt/1",
            "schema": schema_descriptor("renderer-qualification-attempt"),
            "attemptId": f"qualify-{key[0]}-amd64-1",
            "attemptFencingToken": 1,
            "qualificationSelectionDigest": selection["selectionDigest"],
            "inputTreeDigest": canonical_digest(
                {
                    "profile": "bytedesk.renderer-qualification-input/1",
                    "qualificationSelection": selection,
                    "qualificationSuite": suite_descriptor,
                    "conformancePlan": conformance_plan,
                    "inputCorpus": input_corpus,
                    "evaluatorDistribution": evaluator_distribution,
                }
            ),
            "contractBundleDigest": product_release["contractBundle"]["digest"],
            "qualificationSuiteDigest": suite_descriptor["digest"],
            "conformancePlanDigest": conformance_plan["digest"],
            "inputCorpusDigest": input_corpus["digest"],
            "evaluatorDistributionDigest": evaluator_distribution["digest"],
            "qualificationWorkerProfileDigest": qualification_worker_profile_digest,
            "qualificationProtocolProfileDigest": qualification_protocol_profile_digest,
            "sandboxProfileDigest": sandbox_profile_digest,
            "resourceProfileDigest": resource_profile_digest,
            "timeoutProfileDigest": timeout_profile_digest,
            "issuerIdentityDigest": canonical_digest(
                {"profile": "bytedesk.renderer-qualification-issuer/1", "renderer": list(key)}
            ),
            "issuedAt": "2026-07-17T11:59:00Z",
            "expiresAt": "2026-07-17T12:05:00Z",
            "authorityDigest": f"sha256:{'0' * 64}",
        }
        qualification_request_frame = framed_jcs(
            {
                "profile": "bytedesk.renderer-qualification-request-frame/1",
                "qualificationSelection": deepcopy(selection),
                "inputTreeDigest": attempt["inputTreeDigest"],
                "qualificationSuite": deepcopy(suite),
                "conformancePlan": deepcopy(conformance_plan),
                "inputCorpus": deepcopy(input_corpus),
                "evaluatorDistribution": deepcopy(evaluator_distribution),
            }
        )
        register_cas_payload(qualification_request_frame)
        attempt["framedRequestDigest"] = raw_digest(qualification_request_frame)
        attempt["authorityDigest"] = domain_digest(
            "bytedesk.renderer-qualification-attempt-digest/1",
            attempt,
            {"contract", "schema", "authorityDigest"},
        )
        attempt_path = RENDERER_CAS_ROOT / f"{key[0]}-qualification-attempt.json"
        documents[attempt_path] = attempt
        attempt_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
            attempt,
            qualification_attempt_trust,
        )
        attempt_auth = {
            "contract": "bytedesk.renderer-qualification-attempt-authentication-evidence/1",
            "schema": schema_descriptor("renderer-qualification-attempt-authentication-evidence"),
            "purpose": "release-qualification-attempt-v1",
            "attemptAuthorityDigest": attempt["authorityDigest"],
            "issuerIdentityDigest": attempt["issuerIdentityDigest"],
            "signingResult": signing_result(
                "release-qualification-attempt-v1",
                attempt["authorityDigest"],
                "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
                f"{key[0]}-qualification-attempt",
                qualification_attempt_trust,
                signed_at="2026-07-17T11:59:30Z",
            ),
            "evidenceDigest": f"sha256:{'0' * 64}",
        }
        attempt_auth["evidenceDigest"] = domain_digest(
            "bytedesk.renderer-qualification-attempt-authentication-evidence-digest/1",
            attempt_auth,
            {"contract", "schema", "evidenceDigest"},
        )
        attempt_auth_path = RENDERER_CAS_ROOT / f"{key[0]}-qualification-attempt-auth.json"
        documents[attempt_auth_path] = attempt_auth
        attempt_auth_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json",
            attempt_auth,
            qualification_attempt_trust,
        )
        launcher_identity_digest = canonical_digest(
            {"profile": "bytedesk.renderer-qualification-launcher/1", "renderer": list(key)}
        )
        _, evidence_tree_descriptor = qualification_evidence_tree(
            key,
            selection["targetPlatform"],
            selection,
            attempt,
            launcher_identity_digest,
        )
        evidence_tree_digest = evidence_tree_descriptor["digest"]
        qualification_response_frame = framed_jcs(
            {
                "profile": "bytedesk.renderer-qualification-response-frame/1",
                "attemptId": attempt["attemptId"],
                "attemptFencingToken": attempt["attemptFencingToken"],
                "qualificationSelectionDigest": selection["selectionDigest"],
                "evaluatorDistribution": deepcopy(evaluator_distribution),
                "evidenceTreeDigest": evidence_tree_digest,
                "result": "pass",
            }
        )
        register_cas_payload(qualification_response_frame)
        receipt = {
            "contract": "bytedesk.renderer-qualification-receipt/1",
            "schema": schema_descriptor("renderer-qualification-receipt"),
            "attemptId": attempt["attemptId"],
            "attemptFencingToken": attempt["attemptFencingToken"],
            "attemptAuthorityDigest": attempt["authorityDigest"],
            "attemptAuthenticationEvidenceDigest": attempt_auth["evidenceDigest"],
            "qualificationSelectionDigest": selection["selectionDigest"],
            "rendererReleaseDigest": release_descriptors[key]["digest"],
            "platform": selection["targetPlatform"],
            "executedDistribution": deepcopy(selection["executableDistribution"]),
            "inputTreeDigest": attempt["inputTreeDigest"],
            "contractBundleDigest": attempt["contractBundleDigest"],
            "qualificationSuiteDigest": attempt["qualificationSuiteDigest"],
            "conformancePlanDigest": attempt["conformancePlanDigest"],
            "inputCorpusDigest": attempt["inputCorpusDigest"],
            "evaluatorDistribution": deepcopy(evaluator_distribution),
            "qualificationWorkerProfileDigest": attempt["qualificationWorkerProfileDigest"],
            "qualificationProtocolProfileDigest": attempt["qualificationProtocolProfileDigest"],
            "framedRequestDigest": attempt["framedRequestDigest"],
            "framedResponseDigest": raw_digest(qualification_response_frame),
            "evidenceTree": deepcopy(evidence_tree_descriptor),
            "evidenceTreeDigest": evidence_tree_digest,
            "sandboxProfileDigest": sandbox_profile_digest,
            "resourceProfileDigest": attempt["resourceProfileDigest"],
            "timeoutProfileDigest": attempt["timeoutProfileDigest"],
            "rendererWorkerProfileDigest": selection["workerProfileDigest"],
            "launcherIdentityDigest": launcher_identity_digest,
            "completedAt": "2026-07-17T12:00:02Z",
        }
        receipt_digest = canonical_digest(receipt)
        receipt_path = RENDERER_CAS_ROOT / f"{key[0]}-qualification-receipt.json"
        documents[receipt_path] = receipt
        receipt_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
            receipt,
            qualification_receipt_trust,
        )
        receipt_auth = {
            "contract": "bytedesk.renderer-qualification-receipt-authentication-evidence/1",
            "schema": schema_descriptor("renderer-qualification-receipt-authentication-evidence"),
            "purpose": "release-qualification-receipt-v1",
            "receiptDigest": receipt_digest,
            "qualificationSelectionDigest": selection["selectionDigest"],
            "launcherIdentityDigest": receipt["launcherIdentityDigest"],
            "signingResult": signing_result(
                "release-qualification-receipt-v1",
                receipt_digest,
                "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
                f"{key[0]}-qualification-receipt",
                qualification_receipt_trust,
                signed_at="2026-07-17T12:00:03Z",
            ),
            "evidenceDigest": f"sha256:{'0' * 64}",
        }
        receipt_auth["evidenceDigest"] = domain_digest(
            "bytedesk.renderer-qualification-receipt-authentication-evidence-digest/1",
            receipt_auth,
            {"contract", "schema", "evidenceDigest"},
        )
        receipt_auth_path = RENDERER_CAS_ROOT / f"{key[0]}-qualification-receipt-auth.json"
        documents[receipt_auth_path] = receipt_auth
        receipt_auth_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json",
            receipt_auth,
            qualification_receipt_trust,
        )
        qualification_execution[key] = {
            "selection": selection_descriptor,
            "selectionDigest": selection["selectionDigest"],
            "attempt": attempt_descriptor,
            "attemptAuth": attempt_auth_descriptor,
            "receipt": receipt_descriptor,
            "receiptAuth": receipt_auth_descriptor,
            "selectionDocument": selection,
            "attemptDocument": attempt,
            "attemptAuthDocument": attempt_auth,
            "receiptDocument": receipt,
            "receiptAuthDocument": receipt_auth,
            "receiptPath": receipt_path,
            "receiptAuthPath": receipt_auth_path,
        }

    platform_qualification_execution: dict[
        tuple[tuple[str, str, str], str], dict[str, Any]
    ] = {
        (key, "linux/amd64"): execution
        for key, execution in qualification_execution.items()
    }
    for key, release in sorted(releases.items()):
        for platform in release["platforms"]:
            platform_name = f"{platform['os']}/{platform['architecture']}"
            if platform_name == "linux/amd64":
                continue
            base_selection = documents[RENDERER_QUALIFICATION_SELECTION_PATHS[key[0]]]
            selection = deepcopy(base_selection)
            selection["targetPlatform"] = platform_name
            selection["executableDistribution"] = deepcopy(platform["distribution"])
            selection["selectionDigest"] = domain_digest(
                "bytedesk.renderer-qualification-selection-digest/1",
                selection,
                {"contract", "schema", "selectionDigest"},
            )
            path_token = platform["architecture"]
            selection_path = (
                RENDERER_CAS_ROOT
                / f"{key[0]}-{path_token}-qualification-selection.json"
            )
            documents[selection_path] = selection
            selection_descriptor = artifact_descriptor(
                "registry.example/product/qualification",
                "application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json",
                selection,
                qualification_attempt_trust,
            )

            attempt = deepcopy(
                documents[RENDERER_CAS_ROOT / f"{key[0]}-qualification-attempt.json"]
            )
            attempt["attemptId"] = f"qualify-{key[0]}-{path_token}-1"
            attempt["qualificationSelectionDigest"] = selection["selectionDigest"]
            attempt["inputTreeDigest"] = canonical_digest(
                {
                    "profile": "bytedesk.renderer-qualification-input/1",
                    "qualificationSelection": selection,
                    "qualificationSuite": suite_descriptor,
                    "conformancePlan": conformance_plan,
                    "inputCorpus": input_corpus,
                    "evaluatorDistribution": evaluator_distribution,
                }
            )
            attempt["issuerIdentityDigest"] = canonical_digest(
                {
                    "profile": "bytedesk.renderer-qualification-issuer/1",
                    "renderer": list(key),
                    "platform": platform_name,
                }
            )
            qualification_request_frame = framed_jcs(
                {
                    "profile": "bytedesk.renderer-qualification-request-frame/1",
                    "qualificationSelection": deepcopy(selection),
                    "inputTreeDigest": attempt["inputTreeDigest"],
                    "qualificationSuite": deepcopy(suite),
                    "conformancePlan": deepcopy(conformance_plan),
                    "inputCorpus": deepcopy(input_corpus),
                    "evaluatorDistribution": deepcopy(evaluator_distribution),
                }
            )
            register_cas_payload(qualification_request_frame)
            attempt["framedRequestDigest"] = raw_digest(
                qualification_request_frame
            )
            attempt["authorityDigest"] = domain_digest(
                "bytedesk.renderer-qualification-attempt-digest/1",
                attempt,
                {"contract", "schema", "authorityDigest"},
            )
            attempt_path = (
                RENDERER_CAS_ROOT / f"{key[0]}-{path_token}-qualification-attempt.json"
            )
            documents[attempt_path] = attempt
            attempt_descriptor = artifact_descriptor(
                "registry.example/product/qualification",
                "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
                attempt,
                qualification_attempt_trust,
            )

            attempt_auth = deepcopy(
                documents[
                    RENDERER_CAS_ROOT / f"{key[0]}-qualification-attempt-auth.json"
                ]
            )
            attempt_auth["attemptAuthorityDigest"] = attempt["authorityDigest"]
            attempt_auth["issuerIdentityDigest"] = attempt["issuerIdentityDigest"]
            attempt_auth["signingResult"] = signing_result(
                "release-qualification-attempt-v1",
                attempt["authorityDigest"],
                "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json",
                f"{key[0]}-{path_token}-qualification-attempt",
                qualification_attempt_trust,
                signed_at="2026-07-17T11:59:30Z",
            )
            attempt_auth["evidenceDigest"] = domain_digest(
                "bytedesk.renderer-qualification-attempt-authentication-evidence-digest/1",
                attempt_auth,
                {"contract", "schema", "evidenceDigest"},
            )
            attempt_auth_path = (
                RENDERER_CAS_ROOT
                / f"{key[0]}-{path_token}-qualification-attempt-auth.json"
            )
            documents[attempt_auth_path] = attempt_auth
            attempt_auth_descriptor = artifact_descriptor(
                "registry.example/product/qualification",
                "application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json",
                attempt_auth,
                qualification_attempt_trust,
            )

            receipt = deepcopy(
                documents[RENDERER_CAS_ROOT / f"{key[0]}-qualification-receipt.json"]
            )
            receipt["attemptId"] = attempt["attemptId"]
            receipt["attemptAuthorityDigest"] = attempt["authorityDigest"]
            receipt["attemptAuthenticationEvidenceDigest"] = attempt_auth[
                "evidenceDigest"
            ]
            receipt["qualificationSelectionDigest"] = selection["selectionDigest"]
            receipt["platform"] = platform_name
            receipt["executedDistribution"] = deepcopy(platform["distribution"])
            receipt["inputTreeDigest"] = attempt["inputTreeDigest"]
            launcher_identity_digest = canonical_digest(
                {
                    "profile": "bytedesk.renderer-qualification-launcher/1",
                    "renderer": list(key),
                    "platform": platform_name,
                }
            )
            _, evidence_tree_descriptor = qualification_evidence_tree(
                key,
                platform_name,
                selection,
                attempt,
                launcher_identity_digest,
            )
            evidence_tree_digest = evidence_tree_descriptor["digest"]
            qualification_response_frame = framed_jcs(
                {
                    "profile": "bytedesk.renderer-qualification-response-frame/1",
                    "attemptId": attempt["attemptId"],
                    "attemptFencingToken": attempt["attemptFencingToken"],
                    "qualificationSelectionDigest": selection["selectionDigest"],
                    "evaluatorDistribution": deepcopy(evaluator_distribution),
                    "evidenceTreeDigest": evidence_tree_digest,
                    "result": "pass",
                }
            )
            register_cas_payload(qualification_response_frame)
            receipt["framedRequestDigest"] = attempt["framedRequestDigest"]
            receipt["framedResponseDigest"] = raw_digest(
                qualification_response_frame
            )
            receipt["evidenceTree"] = deepcopy(evidence_tree_descriptor)
            receipt["evidenceTreeDigest"] = evidence_tree_digest
            receipt["launcherIdentityDigest"] = launcher_identity_digest
            receipt_digest = canonical_digest(receipt)
            receipt_path = (
                RENDERER_CAS_ROOT / f"{key[0]}-{path_token}-qualification-receipt.json"
            )
            documents[receipt_path] = receipt
            receipt_descriptor = artifact_descriptor(
                "registry.example/product/qualification",
                "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
                receipt,
                qualification_receipt_trust,
            )

            receipt_auth = deepcopy(
                documents[
                    RENDERER_CAS_ROOT / f"{key[0]}-qualification-receipt-auth.json"
                ]
            )
            receipt_auth["receiptDigest"] = receipt_digest
            receipt_auth["qualificationSelectionDigest"] = selection[
                "selectionDigest"
            ]
            receipt_auth["launcherIdentityDigest"] = receipt[
                "launcherIdentityDigest"
            ]
            receipt_auth["signingResult"] = signing_result(
                "release-qualification-receipt-v1",
                receipt_digest,
                "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json",
                f"{key[0]}-{path_token}-qualification-receipt",
                qualification_receipt_trust,
                signed_at="2026-07-17T12:00:03Z",
            )
            receipt_auth["evidenceDigest"] = domain_digest(
                "bytedesk.renderer-qualification-receipt-authentication-evidence-digest/1",
                receipt_auth,
                {"contract", "schema", "evidenceDigest"},
            )
            receipt_auth_path = (
                RENDERER_CAS_ROOT
                / f"{key[0]}-{path_token}-qualification-receipt-auth.json"
            )
            documents[receipt_auth_path] = receipt_auth
            receipt_auth_descriptor = artifact_descriptor(
                "registry.example/product/qualification",
                "application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json",
                receipt_auth,
                qualification_receipt_trust,
            )
            platform_qualification_execution[(key, platform_name)] = {
                "selection": selection_descriptor,
                "selectionDigest": selection["selectionDigest"],
                "attempt": attempt_descriptor,
                "attemptAuth": attempt_auth_descriptor,
                "receipt": receipt_descriptor,
                "receiptAuth": receipt_auth_descriptor,
                "selectionDocument": selection,
                "attemptDocument": attempt,
                "attemptAuthDocument": attempt_auth,
                "receiptDocument": receipt,
                "receiptAuthDocument": receipt_auth,
                "receiptPath": receipt_path,
                "receiptAuthPath": receipt_auth_path,
            }

    native_key = next(key for key in releases if key[0] == "native")
    reference_execution = platform_qualification_execution[
        (native_key, "linux/amd64")
    ]
    expanded_requirements: list[
        tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]
    ] = []
    for requirement in required_coverage:
        scope = requirement["subjectScope"]
        if scope == "product_release":
            expanded_requirements.append(
                (
                    requirement,
                    deepcopy(product_release_descriptor),
                    reference_execution,
                    "product-release",
                )
            )
        elif scope == "product_distribution":
            expanded_requirements.append(
                (
                    requirement,
                    deepcopy(product_distribution_descriptor),
                    reference_execution,
                    "product-distribution",
                )
            )
        elif scope == "contract_bundle":
            expanded_requirements.append(
                (
                    requirement,
                    deepcopy(product_release["contractBundle"]),
                    reference_execution,
                    "contract-bundle",
                )
            )
        elif scope == "every_renderer_release":
            for key in sorted(releases):
                expanded_requirements.append(
                    (
                        requirement,
                        deepcopy(release_descriptors[key]),
                        platform_qualification_execution[(key, "linux/amd64")],
                        f"renderer-{key[0]}-release",
                    )
                )
        elif scope == "every_renderer_executable":
            for key, release in sorted(releases.items()):
                for platform in sorted(
                    release["platforms"],
                    key=lambda value: (value["os"], value["architecture"]),
                ):
                    platform_name = f"{platform['os']}/{platform['architecture']}"
                    expanded_requirements.append(
                        (
                            requirement,
                            deepcopy(platform["distribution"]),
                            platform_qualification_execution[(key, platform_name)],
                            f"renderer-{key[0]}-{platform['architecture']}",
                        )
                    )
        else:
            raise GenerationError(f"unknown qualification subject scope: {scope}")

    evidence_descriptors: list[dict[str, Any]] = []
    qualification_evidence_documents: dict[str, dict[str, Any]] = {}
    evidence_keys: set[tuple[str, str, str]] = set()
    for requirement, subject, execution, subject_token in expanded_requirements:
        evidence_key = (
            requirement["requirementId"],
            requirement["subjectRole"],
            subject["digest"],
        )
        require(
            evidence_key not in evidence_keys,
            f"duplicate expanded qualification requirement: {evidence_key}",
        )
        evidence_keys.add(evidence_key)
        artifact_id = f"{subject_token}-{requirement['requirementId']}"
        material_key = (
            execution["selectionDigest"],
            requirement["requirementId"],
            subject["digest"],
        )
        require(
            material_key in qualification_leaf_material,
            f"qualification evidence lacks collector leaf: {material_key}",
        )
        material = qualification_leaf_material[material_key]
        require(
            material["artifactId"] == artifact_id,
            f"qualification leaf identity mismatch: {artifact_id}",
        )
        details = deepcopy(material["details"])
        leaf = material["leaf"]
        evidence_tree_descriptor = execution["receiptDocument"]["evidenceTree"]
        predicate = {
            "contract": "bytedesk.release-qualification-predicate/1",
            "schema": schema_descriptor("release-qualification-predicate"),
            "predicateId": artifact_id,
            "requirementId": requirement["requirementId"],
            "role": requirement["role"],
            "subjectRole": requirement["subjectRole"],
            "subject": deepcopy(subject),
            "qualificationSuite": deepcopy(suite_descriptor),
            "qualificationSelectionDigest": execution["selectionDigest"],
            "qualificationReceiptDigest": execution["receipt"]["digest"],
            "conformancePlanDigest": conformance_plan["digest"],
            "inputCorpusDigest": input_corpus["digest"],
            "evaluatorDistribution": deepcopy(evaluator_distribution),
            "evidenceTree": deepcopy(evidence_tree_descriptor),
            "evidenceLeafIndex": leaf["index"],
            "evidenceLeafDigest": leaf["leafDigest"],
            "evidenceLeafStatementDigest": leaf["statementDigest"],
            "evidenceLeafSigningResult": deepcopy(leaf["producerSigningResult"]),
            "details": details,
            "result": "pass",
            "producedAt": "2026-07-17T12:00:00Z",
            "trustPolicy": deepcopy(qualification_evidence_trust),
        }
        predicate_path = RENDERER_CAS_ROOT / f"{artifact_id}-predicate.json"
        documents[predicate_path] = predicate
        predicate_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.release-qualification-predicate.v1+json",
            predicate,
            qualification_evidence_trust,
        )
        evidence = {
            "contract": "bytedesk.release-qualification-evidence/1",
            "schema": schema_descriptor("release-qualification-evidence"),
            "evidenceId": f"{artifact_id}-evidence",
            "role": requirement["role"],
            "subjectRole": requirement["subjectRole"],
            "subject": deepcopy(subject),
            "predicateContract": "bytedesk.release-qualification-predicate/1",
            "predicateSchema": schema_descriptor("release-qualification-predicate"),
            "predicate": predicate_descriptor,
            "qualificationSelection": deepcopy(execution["selection"]),
            "qualificationAttempt": deepcopy(execution["attempt"]),
            "qualificationAttemptAuthenticationEvidence": deepcopy(
                execution["attemptAuth"]
            ),
            "qualificationReceipt": deepcopy(execution["receipt"]),
            "qualificationReceiptAuthenticationEvidence": deepcopy(
                execution["receiptAuth"]
            ),
            "evidenceTree": deepcopy(evidence_tree_descriptor),
            "evidenceLeafIndex": leaf["index"],
            "evidenceLeafDigest": leaf["leafDigest"],
            "evidenceLeafStatementDigest": leaf["statementDigest"],
            "evidenceLeafSigningResult": deepcopy(leaf["producerSigningResult"]),
            "result": "pass",
            "observedAt": "2026-07-17T12:00:00Z",
            "expiresAt": "2026-08-16T12:00:00Z",
            "trustPolicy": deepcopy(qualification_evidence_trust),
        }
        evidence_path = RENDERER_CAS_ROOT / f"{artifact_id}-evidence.json"
        documents[evidence_path] = evidence
        evidence_descriptor = artifact_descriptor(
            "registry.example/product/qualification",
            "application/vnd.bytedesk.agent.release-qualification-evidence.v1+json",
            evidence,
            qualification_evidence_trust,
        )
        evidence_descriptors.append(evidence_descriptor)
        qualification_evidence_documents[evidence_descriptor["digest"]] = evidence

    def current_status(
        status_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        *,
        sequence: int = 1,
        predecessor_digest: str | None = None,
        effective_at: str = "2026-07-17T12:00:03Z",
        reason_code: str = "initial_release",
        status_value: str = "current",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        status = {
            "contract": "bytedesk.release-status/1",
            "schema": schema_descriptor("release-status"),
            "statusId": status_id,
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "sequence": sequence,
            "predecessorDigest": predecessor_digest,
            "status": status_value,
            "reasonCode": reason_code,
            "effectiveAt": effective_at,
            "trustPolicy": deepcopy(status_trust),
        }
        sign_inline_authority(
            status,
            "release-status",
            "release-status-v1",
            "application/vnd.bytedesk.agent.release-status.v1+json",
            status_id,
            status_trust,
            "registry.example/product/status",
        )
        return status, artifact_descriptor(
            "registry.example/product/status",
            "application/vnd.bytedesk.agent.release-status.v1+json",
            status,
            status_trust,
        )

    product_initial_status, product_initial_status_descriptor = current_status(
        "product-release-1-initial",
        "product_release",
        product_release_descriptor,
        effective_at="2026-07-17T12:00:02Z",
    )
    documents[
        RENDERER_CAS_ROOT / "product-release-status-sequence-1.json"
    ] = product_initial_status
    product_intermediate_status, product_intermediate_status_descriptor = current_status(
        "product-release-1-sequence-2",
        "product_release",
        product_release_descriptor,
        sequence=2,
        predecessor_digest=product_initial_status_descriptor["digest"],
        reason_code="release_reaffirmed_sequence_2",
        effective_at="2026-07-17T12:00:02.500000Z",
    )
    documents[
        RENDERER_CAS_ROOT / "product-release-status-sequence-2.json"
    ] = product_intermediate_status
    product_status, product_status_descriptor = current_status(
        "product-release-1-current",
        "product_release",
        product_release_descriptor,
        sequence=3,
        predecessor_digest=product_intermediate_status_descriptor["digest"],
        reason_code="release_reaffirmed_sequence_3",
    )
    documents[PRODUCT_RELEASE_STATUS_PATH] = product_status
    renderer_status_descriptors: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, descriptor in release_descriptors.items():
        status, status_descriptor = current_status(
            f"renderer-{key[0]}-{key[2]}-current", "renderer_release", descriptor
        )
        documents[RENDERER_RELEASE_STATUS_PATHS[key[0]]] = status
        renderer_status_descriptors[key] = status_descriptor

    status_head_auth_schema = load_json(
        SCHEMA_ROOT / "release-status-head-authentication-evidence.schema.json"
    )
    status_head_builder = StatusHeadAuthorityBuilder(
        schema_descriptor=schema_descriptor,
        artifact_descriptor=artifact_descriptor,
        sign_inline_authority=sign_inline_authority,
        signing_result=signing_result,
        signer=product_signer,
        register_document=lambda document_id, document: documents.__setitem__(
            RENDERER_CAS_ROOT / f"{document_id}.json", document
        ),
        canonical_digest=canonical_digest,
        status_head_auth_schema=status_head_auth_schema,
        status_head_trust=status_head_trust,
    )

    def status_consistency_proof(
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
            log_leaves,
            prior_checkpoint["treeSize"],
        )
        proof = {
            "contract": "bytedesk.release-status-log-consistency-proof/1",
            "schema": schema_descriptor("release-status-log-consistency-proof"),
            "proofId": proof_id,
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "from": from_endpoint,
            "to": deepcopy(to_endpoint),
            "algorithm": "bytedesk-rfc6962-prefix-consistency-v1",
            "auditPath": deepcopy(audit_path),
            "proofDataDigest": canonical_digest(
                {
                    "profile": "bytedesk.release-status-log-consistency-proof-data/1",
                    "subjectKind": subject_kind,
                    "subject": subject,
                    "from": from_endpoint,
                    "to": to_endpoint,
                    "algorithm": "bytedesk-rfc6962-prefix-consistency-v1",
                    "auditPath": audit_path,
                }
            ),
            "authorityBindingDigest": signer_authority_binding_digest(
                signer=product_signer("release-status-head-v1"),
                trust_policy=status_head_trust,
                repository="registry.example/product/status-heads",
            ),
            "trustPolicy": deepcopy(status_head_trust),
        }
        sign_inline_authority(
            proof,
            "release-status-log-consistency-proof",
            "release-status-head-v1",
            "application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json",
            proof_id,
            status_head_trust,
            "registry.example/product/status-heads",
        )
        documents[RENDERER_CAS_ROOT / f"{proof_id}.json"] = proof
        return proof, artifact_descriptor(
            "registry.example/product/status-heads",
            "application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json",
            proof,
            status_head_trust,
        )

    def status_inclusion_proof(
        checkpoint_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        epoch: int,
        log_leaves: list[str],
    ) -> tuple[str, dict[str, Any]]:
        tree_size = len(log_leaves)
        require(
            tree_size == status["sequence"] and tree_size > 0,
            "generated status tree size must equal status sequence",
        )
        leaf_digest = status_leaf_digest(
            subject_kind=subject_kind,
            subject=subject,
            sequence=status["sequence"],
            epoch=epoch,
            head=status_descriptor,
        )
        require(
            log_leaves[-1] == leaf_digest,
            "generated current status leaf differs from the Merkle log tail",
        )
        proof_id = f"{checkpoint_id}-head-inclusion"
        proof = {
            "contract": "bytedesk.release-status-log-inclusion-proof/1",
            "schema": schema_descriptor("release-status-log-inclusion-proof"),
            "proofId": proof_id,
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "treeSize": tree_size,
            "leafIndex": tree_size - 1,
            "leafDigest": leaf_digest,
            "rootDigest": merkle_root(log_leaves),
            "algorithm": "bytedesk-rfc6962-head-inclusion-v1",
            "auditPath": merkle_inclusion_proof(log_leaves, tree_size - 1),
            "trustPolicy": deepcopy(status_head_trust),
        }
        documents[RENDERER_CAS_ROOT / f"{proof_id}.json"] = proof
        return leaf_digest, artifact_descriptor(
            "registry.example/product/status-heads",
            "application/vnd.bytedesk.agent.release-status-log-inclusion-proof.v1+json",
            proof,
            status_head_trust,
        )

    def current_status_head(
        checkpoint_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        *,
        epoch: int = 1,
        log_leaves: list[str],
        prior: tuple[dict[str, Any], dict[str, Any]] | None = None,
        consistency_proof_id: str | None = None,
        verified_at: str = "2026-07-17T12:00:03Z",
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        nonce_token = checkpoint_id.replace(".", "_")
        request_nonce = f"status_head_nonce_{nonce_token}_0123456789abcdef"
        built = status_head_builder.refresh(
            checkpoint_id=checkpoint_id,
            request_nonce=request_nonce,
            subject_kind=subject_kind,
            subject=subject,
            status=status,
            status_descriptor=status_descriptor,
            epoch=epoch,
            log_leaves=log_leaves,
            operation_time=verified_at,
            expires_at="2026-07-17T12:05:00Z",
            prior_checkpoint=None if prior is None else prior[0],
            prior_checkpoint_descriptor=None if prior is None else prior[1],
            consistency_proof_id=consistency_proof_id,
        )
        return (
            built["checkpoint"],
            built["checkpointDescriptor"],
            built["authentication"],
            built["authenticationDescriptor"],
        )

    product_initial_leaf = status_leaf_digest(
        subject_kind="product_release",
        subject=product_release_descriptor,
        sequence=product_initial_status["sequence"],
        epoch=1,
        head=product_initial_status_descriptor,
    )
    product_intermediate_leaf = status_leaf_digest(
        subject_kind="product_release",
        subject=product_release_descriptor,
        sequence=product_intermediate_status["sequence"],
        epoch=1,
        head=product_intermediate_status_descriptor,
    )
    product_final_leaf = status_leaf_digest(
        subject_kind="product_release",
        subject=product_release_descriptor,
        sequence=product_status["sequence"],
        epoch=2,
        head=product_status_descriptor,
    )
    product_initial_leaves = [product_initial_leaf]
    product_all_leaves = [
        product_initial_leaf,
        product_intermediate_leaf,
        product_final_leaf,
    ]
    product_initial_head = current_status_head(
        "product-release-status-head-initial",
        "product_release",
        product_release_descriptor,
        product_initial_status,
        product_initial_status_descriptor,
        log_leaves=product_initial_leaves,
    )
    product_refresh_head = current_status_head(
        "product-release-status-head-refresh",
        "product_release",
        product_release_descriptor,
        product_initial_status,
        product_initial_status_descriptor,
        log_leaves=product_initial_leaves,
        prior=(product_initial_head[0], product_initial_head[1]),
        verified_at="2026-07-17T12:00:03.250000Z",
    )
    (
        product_status_checkpoint,
        product_status_checkpoint_descriptor,
        product_status_checkpoint_authentication,
        product_status_checkpoint_authentication_descriptor,
    ) = current_status_head(
        "product-release-status-head-epoch-2",
        "product_release",
        product_release_descriptor,
        product_status,
        product_status_descriptor,
        epoch=2,
        log_leaves=product_all_leaves,
        prior=(product_refresh_head[0], product_refresh_head[1]),
        consistency_proof_id="product-release-status-log-epoch-1-to-2",
        verified_at="2026-07-17T12:00:03.500000Z",
    )
    renderer_status_heads: dict[
        tuple[str, str, str], tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = {}
    for key, status_descriptor in renderer_status_descriptors.items():
        renderer_status = documents[RENDERER_RELEASE_STATUS_PATHS[key[0]]]
        renderer_leaves = [
            status_leaf_digest(
                subject_kind="renderer_release",
                subject=release_descriptors[key],
                sequence=renderer_status["sequence"],
                epoch=1,
                head=status_descriptor,
            )
        ]
        renderer_initial_head = current_status_head(
            f"renderer-{key[0]}-{key[2]}-status-head-initial",
            "renderer_release",
            release_descriptors[key],
            renderer_status,
            status_descriptor,
            log_leaves=renderer_leaves,
        )
        renderer_status_heads[key] = current_status_head(
            f"renderer-{key[0]}-{key[2]}-status-head-refresh",
            "renderer_release",
            release_descriptors[key],
            renderer_status,
            status_descriptor,
            log_leaves=renderer_leaves,
            prior=(renderer_initial_head[0], renderer_initial_head[1]),
            verified_at="2026-07-17T12:00:03.250000Z",
        )

    first_contact_subject = json_payload_descriptor(
        "registry.example/product/renderers",
        "application/vnd.bytedesk.agent.renderer-release.v1+json",
        {
            "profile": "bytedesk.status-head-first-contact-subject/1",
            "releaseId": "external-renderer-release-7",
        },
        trust_policy,
    )
    first_contact_status, first_contact_status_descriptor = current_status(
        "external-renderer-release-7-current",
        "renderer_release",
        first_contact_subject,
        sequence=7,
        predecessor_digest=canonical_digest(
            {
                "profile": "bytedesk.external-status-predecessor/1",
                "sequence": 6,
            }
        ),
        reason_code="external_log_bootstrap",
    )
    documents[
        RENDERER_CAS_ROOT / "status-head-first-contact-sequence-7-status.json"
    ] = first_contact_status
    first_contact_leaves = [
        canonical_digest(
            {
                "profile": "bytedesk.external-status-history-leaf/1",
                "subject": first_contact_subject,
                "sequence": sequence,
            }
        )
        for sequence in range(1, 7)
    ]
    first_contact_leaves.append(
        status_leaf_digest(
            subject_kind="renderer_release",
            subject=first_contact_subject,
            sequence=first_contact_status["sequence"],
            epoch=1,
            head=first_contact_status_descriptor,
        )
    )
    current_status_head(
        "status-head-first-contact-sequence-7",
        "renderer_release",
        first_contact_subject,
        first_contact_status,
        first_contact_status_descriptor,
        log_leaves=first_contact_leaves,
        verified_at="2026-07-17T12:00:03.750000Z",
    )

    far_behind_subject = json_payload_descriptor(
        "registry.example/product/renderers",
        "application/vnd.bytedesk.agent.renderer-release.v1+json",
        {
            "profile": "bytedesk.status-head-far-behind-subject/1",
            "releaseId": "external-renderer-release-1024",
        },
        trust_policy,
    )
    far_behind_initial_status, far_behind_initial_status_descriptor = current_status(
        "external-renderer-release-1024-sequence-1",
        "renderer_release",
        far_behind_subject,
        effective_at="2026-07-17T12:00:02Z",
        reason_code="external_log_initial",
    )
    documents[
        RENDERER_CAS_ROOT / "status-head-far-behind-sequence-1-status.json"
    ] = far_behind_initial_status
    far_behind_current_status, far_behind_current_status_descriptor = current_status(
        "external-renderer-release-1024-current",
        "renderer_release",
        far_behind_subject,
        sequence=1024,
        predecessor_digest=canonical_digest(
            {
                "profile": "bytedesk.external-status-predecessor/1",
                "sequence": 1023,
                "subject": far_behind_subject,
            }
        ),
        effective_at="2026-07-17T12:00:03.500000Z",
        reason_code="external_log_far_behind_current",
    )
    documents[
        RENDERER_CAS_ROOT / "status-head-far-behind-sequence-1024-status.json"
    ] = far_behind_current_status
    far_behind_initial_leaf = status_leaf_digest(
        subject_kind="renderer_release",
        subject=far_behind_subject,
        sequence=1,
        epoch=1,
        head=far_behind_initial_status_descriptor,
    )
    far_behind_leaves = [far_behind_initial_leaf]
    far_behind_leaves.extend(
        canonical_digest(
            {
                "profile": "bytedesk.external-status-history-leaf/1",
                "subject": far_behind_subject,
                "sequence": sequence,
            }
        )
        for sequence in range(2, 1024)
    )
    far_behind_leaves.append(
        status_leaf_digest(
            subject_kind="renderer_release",
            subject=far_behind_subject,
            sequence=1024,
            epoch=3,
            head=far_behind_current_status_descriptor,
        )
    )
    far_behind_initial_head = current_status_head(
        "status-head-far-behind-sequence-1",
        "renderer_release",
        far_behind_subject,
        far_behind_initial_status,
        far_behind_initial_status_descriptor,
        log_leaves=[far_behind_initial_leaf],
        verified_at="2026-07-17T12:00:03Z",
    )
    current_status_head(
        "status-head-far-behind-sequence-1024",
        "renderer_release",
        far_behind_subject,
        far_behind_current_status,
        far_behind_current_status_descriptor,
        epoch=3,
        log_leaves=far_behind_leaves,
        prior=(far_behind_initial_head[0], far_behind_initial_head[1]),
        consistency_proof_id="status-head-far-behind-sequence-1-to-1024",
        verified_at="2026-07-17T12:00:03.750000Z",
    )

    unrelated_withdrawn_subject = json_payload_descriptor(
        "registry.example/product/renderers",
        "application/vnd.bytedesk.agent.renderer-release.v1+json",
        {
            "profile": "bytedesk.unrelated-withdrawn-release/1",
            "releaseId": "retired-renderer-release",
        },
        trust_policy,
    )
    unrelated_withdrawn_status, _ = current_status(
        "unrelated-renderer-release-withdrawn",
        "renderer_release",
        unrelated_withdrawn_subject,
        reason_code="retired_release",
        status_value="withdrawn",
    )
    documents[
        RENDERER_CAS_ROOT / "unrelated-withdrawn-release-status.json"
    ] = unrelated_withdrawn_status

    # Qualification is finalized only after a fresh, nonce-bound status-head
    # refresh for the complete product/renderer-platform matrix.  The
    # selection-time checkpoints above remain separate evidence and cannot be
    # replayed as qualification-finalization authority.
    qualification_time = "2026-07-17T12:00:03.900000Z"
    qualification_expiry = "2026-08-16T12:00:00Z"
    verification_schema = schema_descriptor("verification-result")
    require(
        ACTIVE_TRUST_POLICY_PIN_SET is not None
        and ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR is not None
        and ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE is not None,
        "qualification finalization requires the active product pin set",
    )

    def register_verification_result(
        verification_id: str,
        result: dict[str, Any],
    ) -> str:
        path = RENDERER_CAS_ROOT / f"{verification_id}.json"
        documents[path] = result
        digest = register_cas_payload(rfc8785.dumps(result))
        require(
            digest == canonical_digest(result),
            f"verification result digest mismatch: {verification_id}",
        )
        return digest

    def verify_signed_subject(
        *,
        verification_id: str,
        signing_evidence: dict[str, Any],
        signed_subject_digest: str,
        signed_subject_media_type: str,
        verification_subject: dict[str, Any],
        purpose: str,
        repository: str,
    ) -> str:
        adapter = TrustedKmsVerificationAdapter(
            deepcopy(SIGNATURE_VERIFICATION_VECTORS)
        )
        detailed = adapter.verify(
            result=signing_evidence,
            policy=documents[
                RENDERER_CAS_ROOT / f"trust-policy-{purpose}.json"
            ],
            permitted_signer=product_signer(purpose),
            verification_time=qualification_time,
            expected_purpose=purpose,
            expected_subject_media_type=signed_subject_media_type,
            expected_signing_repository=repository,
            pin_set_digest=ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
            pin_set_revocations=ACTIVE_TRUST_POLICY_PIN_SET["revocations"],
            expected_consumer_id=None,
        )
        require(
            signing_evidence["subjectDigest"] == signed_subject_digest
            and verification_subject["repository"] == repository
            and verification_subject["trustPolicy"]
            == signing_evidence["trustPolicy"],
            f"signed verification subject mismatch: {verification_id}",
        )
        detailed_evidence = {
            "profile": "bytedesk.kms-signature-verification-evidence/1",
            **{
                key: deepcopy(value)
                for key, value in detailed.items()
                if key != "verificationEvidenceDigest"
            },
        }
        require(
            register_cas_payload(rfc8785.dumps(detailed_evidence))
            == detailed["verificationEvidenceDigest"],
            f"KMS verification evidence digest mismatch: {verification_id}",
        )
        result = permitted_verification_result(
            schema_descriptor=verification_schema,
            verification_id=verification_id,
            subject=verification_subject,
            policy=signing_evidence["trustPolicy"],
            evaluated_at=qualification_time,
            evidence_digests=[detailed["verificationEvidenceDigest"]],
        )
        return register_verification_result(verification_id, result)

    def verify_deterministic_subject(
        *,
        verification_id: str,
        subject: dict[str, Any],
        policy_ref: dict[str, Any],
        evidence_statement: dict[str, Any],
    ) -> str:
        evidence_digest = register_cas_payload(rfc8785.dumps(evidence_statement))
        result = permitted_verification_result(
            schema_descriptor=verification_schema,
            verification_id=verification_id,
            subject=subject,
            policy=policy_ref,
            evaluated_at=qualification_time,
            evidence_digests=[evidence_digest],
        )
        return register_verification_result(verification_id, result)

    def qualification_status_head(
        *,
        checkpoint_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        epoch: int,
        log_leaves: list[str],
        prior_checkpoint: dict[str, Any],
        prior_checkpoint_descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        nonce_token = checkpoint_id.replace(".", "_")
        return status_head_builder.refresh(
            checkpoint_id=checkpoint_id,
            request_nonce=(
                f"qualification_finalization_{nonce_token}_nonce_0123456789abcdef"
            ),
            subject_kind=subject_kind,
            subject=subject,
            status=status,
            status_descriptor=status_descriptor,
            epoch=epoch,
            log_leaves=log_leaves,
            operation_time=qualification_time,
            expires_at="2026-07-17T12:05:00Z",
            prior_checkpoint=prior_checkpoint,
            prior_checkpoint_descriptor=prior_checkpoint_descriptor,
        )

    product_qualification_head = qualification_status_head(
        checkpoint_id="product-release-qualification-finalization-status-head",
        subject_kind="product_release",
        subject=product_release_descriptor,
        status=product_status,
        status_descriptor=product_status_descriptor,
        epoch=2,
        log_leaves=product_all_leaves,
        prior_checkpoint=product_status_checkpoint,
        prior_checkpoint_descriptor=product_status_checkpoint_descriptor,
    )
    renderer_qualification_heads: dict[
        tuple[str, str, str], dict[str, Any]
    ] = {}
    for key, status_descriptor in renderer_status_descriptors.items():
        renderer_status = documents[RENDERER_RELEASE_STATUS_PATHS[key[0]]]
        renderer_leaves = [
            status_leaf_digest(
                subject_kind="renderer_release",
                subject=release_descriptors[key],
                sequence=renderer_status["sequence"],
                epoch=1,
                head=status_descriptor,
            )
        ]
        renderer_qualification_heads[key] = qualification_status_head(
            checkpoint_id=(
                f"renderer-{key[0]}-{key[2]}-qualification-finalization-status-head"
            ),
            subject_kind="renderer_release",
            subject=release_descriptors[key],
            status=renderer_status,
            status_descriptor=status_descriptor,
            epoch=1,
            log_leaves=renderer_leaves,
            prior_checkpoint=renderer_status_heads[key][0],
            prior_checkpoint_descriptor=renderer_status_heads[key][1],
        )

    def status_eligibility_entry(
        *,
        entry_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        status: dict[str, Any],
        status_descriptor: dict[str, Any],
        head: dict[str, Any],
    ) -> dict[str, Any]:
        checkpoint = head["checkpoint"]
        checkpoint_descriptor = head["checkpointDescriptor"]
        authentication = head["authentication"]
        authentication_descriptor = head["authenticationDescriptor"]
        inclusion = head["inclusionProof"]
        inclusion_descriptor = head["inclusionProofDescriptor"]
        consistency = head["consistencyProof"]
        consistency_descriptor = head["consistencyProofDescriptor"]
        status_verification = verify_signed_subject(
            verification_id=f"{entry_id}-status-verification",
            signing_evidence=status["signingResult"],
            signed_subject_digest=status["authorityDigest"],
            signed_subject_media_type=(
                "application/vnd.bytedesk.agent.release-status.v1+json"
            ),
            verification_subject=status_descriptor,
            purpose="release-status-v1",
            repository="registry.example/product/status",
        )
        checkpoint_verification = verify_signed_subject(
            verification_id=f"{entry_id}-checkpoint-authentication-verification",
            signing_evidence=authentication["signingResult"],
            signed_subject_digest=checkpoint_descriptor["digest"],
            signed_subject_media_type=(
                "application/vnd.bytedesk.agent."
                "release-status-head-checkpoint.v1+json"
            ),
            verification_subject=checkpoint_descriptor,
            purpose="release-status-head-v1",
            repository="registry.example/product/status-heads",
        )
        inclusion_verified = verify_merkle_inclusion(
            leaf_digest=inclusion["leafDigest"],
            leaf_index=inclusion["leafIndex"],
            tree_size=inclusion["treeSize"],
            audit_path=inclusion["auditPath"],
            expected_root=inclusion["rootDigest"],
        )
        require(inclusion_verified, f"invalid generated inclusion proof: {entry_id}")
        inclusion_verification = verify_deterministic_subject(
            verification_id=f"{entry_id}-inclusion-verification",
            subject=inclusion_descriptor,
            policy_ref=status_head_trust,
            evidence_statement={
                "profile": "bytedesk.release-status-inclusion-verification/1",
                "subjectKind": subject_kind,
                "subject": subject,
                "checkpointDigest": checkpoint_descriptor["digest"],
                "proofDigest": inclusion_descriptor["digest"],
                "algorithm": inclusion["algorithm"],
                "leafDigest": inclusion["leafDigest"],
                "leafIndex": inclusion["leafIndex"],
                "treeSize": inclusion["treeSize"],
                "rootDigest": inclusion["rootDigest"],
                "auditPath": inclusion["auditPath"],
                "verified": True,
                "evaluatedAt": qualification_time,
            },
        )
        consistency_verification: str | None = None
        if consistency is not None:
            require(
                consistency_descriptor is not None
                and verify_merkle_consistency(
                    old_size=consistency["from"]["treeSize"],
                    new_size=consistency["to"]["treeSize"],
                    old_root=consistency["from"]["logRootDigest"],
                    new_root=consistency["to"]["logRootDigest"],
                    audit_path=consistency["auditPath"],
                ),
                f"invalid generated consistency proof: {entry_id}",
            )
            consistency_verification = verify_deterministic_subject(
                verification_id=f"{entry_id}-consistency-verification",
                subject=consistency_descriptor,
                policy_ref=status_head_trust,
                evidence_statement={
                    "profile": "bytedesk.release-status-consistency-verification/1",
                    "subjectKind": subject_kind,
                    "subject": subject,
                    "checkpointDigest": checkpoint_descriptor["digest"],
                    "proofDigest": consistency_descriptor["digest"],
                    "algorithm": consistency["algorithm"],
                    "from": consistency["from"],
                    "to": consistency["to"],
                    "auditPath": consistency["auditPath"],
                    "verified": True,
                    "evaluatedAt": qualification_time,
                },
            )
        return {
            "subjectKind": subject_kind,
            "subject": deepcopy(subject),
            "status": deepcopy(status_descriptor),
            "checkpoint": deepcopy(checkpoint_descriptor),
            "checkpointAuthenticationEvidence": deepcopy(
                authentication_descriptor
            ),
            "requestNonce": checkpoint["requestNonce"],
            "clientPriorState": deepcopy(checkpoint["clientPriorState"]),
            "headInclusionProof": deepcopy(inclusion_descriptor),
            "consistencyProof": deepcopy(consistency_descriptor),
            "verificationEvidenceDigests": {
                "status": status_verification,
                "checkpointAuthentication": checkpoint_verification,
                "headInclusionProof": inclusion_verification,
                "consistencyProof": consistency_verification,
            },
            "statusDocument": status,
            "checkpointDocument": checkpoint,
            "checkpointAuthenticationEvidenceDocument": authentication,
            "headInclusionProofDocument": inclusion,
            "consistencyProofDocument": consistency,
        }

    product_eligibility_entry = status_eligibility_entry(
        entry_id="qualification-finalization-product-release",
        subject_kind="product_release",
        subject=product_release_descriptor,
        status=product_status,
        status_descriptor=product_status_descriptor,
        head=product_qualification_head,
    )
    renderer_eligibility_entries: list[dict[str, Any]] = []
    for key, release in releases.items():
        base_entry = status_eligibility_entry(
            entry_id=f"qualification-finalization-renderer-{key[0]}-{key[2]}",
            subject_kind="renderer_release",
            subject=release_descriptors[key],
            status=documents[RENDERER_RELEASE_STATUS_PATHS[key[0]]],
            status_descriptor=renderer_status_descriptors[key],
            head=renderer_qualification_heads[key],
        )
        for platform in sorted(
            release["platforms"],
            key=lambda value: (value["os"], value["architecture"]),
        ):
            entry = deepcopy(base_entry)
            entry.update(
                {
                    "harnessId": key[0],
                    "rendererId": key[1],
                    "rendererVersion": key[2],
                    "targetPlatform": (
                        f"{platform['os']}/{platform['architecture']}"
                    ),
                }
            )
            renderer_eligibility_entries.append(entry)
    renderer_eligibility_entries.sort(
        key=lambda entry: (
            entry["harnessId"].encode("utf-8"),
            entry["rendererId"].encode("utf-8"),
            entry["rendererVersion"].encode("utf-8"),
            entry["targetPlatform"].encode("utf-8"),
            entry["subject"]["digest"].encode("utf-8"),
        )
    )

    eligibility_builder = ReleaseStatusEligibilityBuilder(
        schema_descriptor=schema_descriptor,
        artifact_descriptor=artifact_descriptor,
        signing_result=signing_result,
        canonical_digest=canonical_digest,
        eligibility_schema=load_json(
            SCHEMA_ROOT / "release-status-eligibility-evidence.schema.json"
        ),
        trust_policy=trust_refs["release-status-eligibility-v1"],
        repository="registry.example/product/status-eligibility",
        consumer_id=None,
        pin_set_descriptor=ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR,
        pin_set_digest=ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
        pin_set_provider_evidence=ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE,
        register_document=lambda document_id, document: documents.__setitem__(
            RENDERER_CAS_ROOT / f"{document_id}.json", document
        ),
    )
    qualification_eligibility, qualification_eligibility_descriptor = (
        eligibility_builder.build(
            evidence_id="product-release-qualification-finalization-eligibility",
            stage="qualification_finalization",
            operation_time=qualification_time,
            product=product_eligibility_entry,
            renderers=renderer_eligibility_entries,
        )
    )
    qualification_eligibility_verification = verify_signed_subject(
        verification_id=(
            "product-release-qualification-finalization-eligibility-verification"
        ),
        signing_evidence=qualification_eligibility["signingResult"],
        signed_subject_digest=qualification_eligibility["eligibilityDigest"],
        signed_subject_media_type=(
            "application/vnd.bytedesk.agent."
            "release-status-eligibility-evidence-digest.v1+json"
        ),
        verification_subject=qualification_eligibility_descriptor,
        purpose="release-status-eligibility-v1",
        repository="registry.example/product/status-eligibility",
    )

    ordered_evidence = sorted(
        evidence_descriptors,
        key=lambda descriptor: (
            qualification_evidence_documents[descriptor["digest"]][
                "subjectRole"
            ].encode("utf-8"),
            qualification_evidence_documents[descriptor["digest"]]["subject"][
                "digest"
            ].encode("utf-8"),
            qualification_evidence_documents[descriptor["digest"]]["role"].encode(
                "utf-8"
            ),
            descriptor["digest"].encode("utf-8"),
        ),
    )
    matrix_renderer_entries = [
        {
            "rendererRelease": deepcopy(release_descriptors[key]),
            "platform": platform,
            "qualificationSelection": deepcopy(execution["selection"]),
            "qualificationAttempt": deepcopy(execution["attempt"]),
            "qualificationAttemptAuthenticationEvidence": deepcopy(
                execution["attemptAuth"]
            ),
            "qualificationReceipt": deepcopy(execution["receipt"]),
            "qualificationReceiptAuthenticationEvidence": deepcopy(
                execution["receiptAuth"]
            ),
        }
        for (key, platform), execution in platform_qualification_execution.items()
    ]
    matrix_renderer_entries.sort(
        key=lambda entry: (
            entry["rendererRelease"]["digest"].encode("utf-8"),
            entry["platform"].encode("utf-8"),
        )
    )
    finalization_matrix = {
        "contract": "bytedesk.release-qualification-finalization-matrix/1",
        "schema": schema_descriptor("release-qualification-finalization-matrix"),
        "productRelease": deepcopy(product_release_descriptor),
        "qualificationPolicy": deepcopy(policy_descriptor),
        "qualificationSuite": deepcopy(suite_descriptor),
        "rendererEntries": matrix_renderer_entries,
        "evidence": deepcopy(ordered_evidence),
        "matrixDigest": "sha256:" + ("0" * 64),
    }
    matrix_authority = load_json(
        SCHEMA_ROOT / "release-qualification-finalization-matrix.schema.json"
    )["x-bytedesk-digestAuthority"]
    finalization_matrix["matrixDigest"] = domain_digest(
        matrix_authority["profile"],
        finalization_matrix,
        set(matrix_authority["exclude"]),
    )
    matrix_path = (
        FIXTURE_ROOT
        / "positive"
        / "release-qualification-finalization-matrix__native-amd64.json"
    )
    documents[matrix_path] = finalization_matrix
    finalization_matrix_descriptor = artifact_descriptor(
        "registry.example/product/qualification",
        "application/vnd.bytedesk.agent."
        "release-qualification-finalization-matrix.v1+json",
        finalization_matrix,
        qualification_decision_trust,
    )

    policy_verification = verify_signed_subject(
        verification_id="release-qualification-policy-finalization-verification",
        signing_evidence=policy["signingResult"],
        signed_subject_digest=policy["authorityDigest"],
        signed_subject_media_type=(
            "application/vnd.bytedesk.agent."
            "release-qualification-policy.v1+json"
        ),
        verification_subject=policy_descriptor,
        purpose="release-qualification-policy-v1",
        repository="registry.example/product/qualification",
    )
    suite_verification = verify_deterministic_subject(
        verification_id="renderer-qualification-suite-finalization-verification",
        subject=suite_descriptor,
        policy_ref=qualification_policy_trust,
        evidence_statement={
            "profile": "bytedesk.renderer-qualification-suite-verification/1",
            "suiteDigest": suite_descriptor["digest"],
            "suiteSchema": suite["schema"],
            "qualificationPolicyDigest": policy_descriptor["digest"],
            "requiredCoverageDigest": minimum_qualification_coverage_digest,
            "evaluatedAt": qualification_time,
            "verified": True,
        },
    )

    qualification = {
        "contract": "bytedesk.release-qualification/1",
        "schema": schema_descriptor("release-qualification"),
        "qualificationId": "product-release-1-qualification",
        "productRelease": deepcopy(product_release_descriptor),
        "rendererReleases": deepcopy(product_release["rendererReleases"]),
        "evidence": deepcopy(ordered_evidence),
        "policy": deepcopy(policy_descriptor),
        "finalizationMatrix": deepcopy(finalization_matrix_descriptor),
        "finalizationMatrixDigest": finalization_matrix["matrixDigest"],
        "qualificationStatusEligibility": deepcopy(
            qualification_eligibility_descriptor
        ),
        "qualificationStatusEligibilityDigest": qualification_eligibility[
            "eligibilityDigest"
        ],
        "qualificationStatusEligibilityVerificationDigest": (
            qualification_eligibility_verification
        ),
        "pinSetDigest": ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
        "pinSetProviderEvidenceDigest": (
            ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE["evidenceDigest"]
        ),
        "policyVerificationDigest": policy_verification,
        "suiteVerificationDigest": suite_verification,
        "decision": "qualified",
        "qualifiedAt": qualification_time,
        "expiresAt": qualification_expiry,
        "trustPolicy": deepcopy(qualification_decision_trust),
    }
    sign_inline_authority(
        qualification,
        "release-qualification",
        "release-qualification-decision-v1",
        "application/vnd.bytedesk.agent.release-qualification.v1+json",
        "product-release-qualification-decision",
        qualification_decision_trust,
        "registry.example/product/qualification",
    )
    documents[RELEASE_QUALIFICATION_PATH] = qualification
    qualification_descriptor = artifact_descriptor(
        "registry.example/product/qualification",
        "application/vnd.bytedesk.agent.release-qualification.v1+json",
        qualification,
        qualification_decision_trust,
    )

    def bind_release_lineage(value: dict[str, Any]) -> None:
        if (
            value.get("mediaType")
            == "application/vnd.bytedesk.agent.contract-bundle.v1+json"
        ):
            value["trustPolicy"] = deepcopy(contract_bundle_trust_policy)
        contract = value.get("contract")
        if contract == "bytedesk.renderer-selection/1":
            value["operationTime"] = "2026-07-17T12:00:04Z"
            value["productRelease"] = deepcopy(product_release_descriptor)
            value["releaseQualification"] = deepcopy(qualification_descriptor)
            value["productReleaseStatus"] = deepcopy(product_status_descriptor)
            value["productReleaseStatusCheckpoint"] = deepcopy(
                product_status_checkpoint_descriptor
            )
            value["productReleaseStatusCheckpointAuthenticationEvidence"] = deepcopy(
                product_status_checkpoint_authentication_descriptor
            )
            value["productReleaseStatusRequestNonce"] = product_status_checkpoint[
                "requestNonce"
            ]
            value["productDistribution"] = deepcopy(product_distribution_descriptor)
            value["compiledAllowlist"] = deepcopy(allowlist_descriptor)
            key = renderer_key(value)
            if key in releases:
                release = releases[key]
                value["targetHarnessVersion"] = release["supportedHarnessVersions"][0]
                value["rendererVersion"] = release["version"]
                value["rendererRelease"] = deepcopy(release_descriptors[key])
                value["rendererReleaseStatus"] = deepcopy(
                    renderer_status_descriptors[key]
                )
                value["rendererReleaseStatusCheckpoint"] = deepcopy(
                    renderer_status_heads[key][1]
                )
                value["rendererReleaseStatusCheckpointAuthenticationEvidence"] = deepcopy(
                    renderer_status_heads[key][3]
                )
                value["rendererReleaseStatusRequestNonce"] = renderer_status_heads[
                    key
                ][0]["requestNonce"]
                value["capability"] = deepcopy(release["capabilityManifest"])
                platforms = [
                    platform
                    for platform in release["platforms"]
                    if f"{platform['os']}/{platform['architecture']}"
                    == value["targetPlatform"]
                ]
                # Intentionally unsupported target-platform denial fixtures
                # retain their invalid platform/distribution pair. Positive
                # selections have exactly one release platform match.
                if platforms:
                    require(
                        len(platforms) == 1,
                        f"duplicate release platform for {key}: {value['targetPlatform']}",
                    )
                    value["executableDistribution"] = deepcopy(
                        platforms[0]["distribution"]
                    )
                value["workerProfileDigest"] = release["workerProtocol"]["profileDigest"]
                value["normalizationProfile"] = release["normalizationProfile"]
            value["productDistributionDigest"] = product_distribution_descriptor["digest"]
            value["compiledAllowlistDigest"] = allowlist_descriptor["digest"]
        elif contract in {
            "bytedesk.render-manifest/1",
            "bytedesk.renderer-compatibility-result/1",
        }:
            value["productRelease"] = deepcopy(product_release_descriptor)
            value["productDistributionDigest"] = product_release["productDistribution"]["digest"]
            value["compiledAllowlistDigest"] = allowlist_descriptor["digest"]
            identity = renderer_identity(value)
            matching = [
                key for key in release_descriptors if key[:2] == identity
            ]
            require(len(matching) == 1, f"ambiguous renderer version for {identity}")
            key = matching[0]
            value["rendererVersion"] = key[2]
            if key in release_descriptors:
                value["rendererRelease"] = deepcopy(release_descriptors[key])
                platform_name = value.get("platform")
                if isinstance(platform_name, str):
                    matching_platforms = [
                        platform
                        for platform in releases[key]["platforms"]
                        if f"{platform['os']}/{platform['architecture']}"
                        == platform_name
                    ]
                    require(
                        len(matching_platforms) == 1,
                        f"renderer output platform is not uniquely released: {key}:{platform_name}",
                    )
                    value["executedDistribution"] = deepcopy(
                        matching_platforms[0]["distribution"]
                    )
        elif contract in {"bytedesk.harness-render/1", "bytedesk.consumer-deployment/1"}:
            value["productRelease"] = deepcopy(product_release_descriptor)
            value["productDistributionDigest"] = product_release["productDistribution"]["digest"]
            value["compiledAllowlistDigest"] = allowlist_descriptor["digest"]

    for document in documents.values():
        walk(document, bind_release_lineage)
    return trust_refs


def refresh_renderer_documents(
    documents: dict[Path, dict[str, Any]],
    schema_digests: dict[str, str],
) -> dict[str, dict[str, Any]]:
    global PUBLIC_RENDER_FINALIZATION_RESULT
    def refresh_descriptor(value: dict[str, Any]) -> None:
        schema_id = value.get("id")
        if schema_id in schema_digests and "digest" in value:
            value["digest"] = schema_digests[schema_id]

    for document in documents.values():
        walk(document, refresh_descriptor)

    canonical_public_subject_media_types = {
        "application/vnd.bytedesk.agent.v1+json": (
            "application/vnd.bytedesk.agent.source.v1+json"
        ),
        "application/vnd.bytedesk.skill.v1+tar": (
            "application/vnd.bytedesk.agent.skill.v1+json"
        ),
    }

    def normalize_public_subject_descriptor(value: dict[str, Any]) -> None:
        if set(value) == {
            "repository",
            "digest",
            "mediaType",
            "size",
            "trustPolicy",
        }:
            normalized = canonical_public_subject_media_types.get(
                value["mediaType"]
            )
            if normalized is not None:
                value["mediaType"] = normalized

    for document in documents.values():
        walk(document, normalize_public_subject_descriptor)

    trust_refs = refresh_release_graph(documents, schema_digests)

    standalone_signing_result = documents.get(PUBLIC_RENDER_SIGNING_RESULT_PATH)
    require(
        isinstance(standalone_signing_result, dict)
        and standalone_signing_result.get("contract") == "bytedesk.signing-result/1"
        and standalone_signing_result.get("purpose") == "public-render-v1",
        "standalone public-render signing-result fixture is missing or invalid",
    )
    request_id = standalone_signing_result.get("requestId")
    require(
        isinstance(request_id, str) and request_id.startswith("sign-")
        and len(request_id) > len("sign-"),
        "standalone public-render signing request ID cannot derive evidence identity",
    )
    documents[PUBLIC_RENDER_SIGNING_RESULT_PATH] = renderer_signing_result(
        schema_digests=schema_digests,
        purpose="public-render-v1",
        subject_digest=standalone_signing_result["subjectDigest"],
        subject_media_type=standalone_signing_result["subjectMediaType"],
        evidence_id=request_id.removeprefix("sign-"),
        evidence_trust=trust_refs["public-render-v1"],
        repository=standalone_signing_result["repository"],
        signed_at=standalone_signing_result["signedAt"],
    )
    product_release_provider_descriptor = documents[PRODUCT_RELEASE_PATH][
        "signingResult"
    ]["providerAuditEvidence"]
    product_release_provider_payload = CAS_PAYLOADS.get(
        product_release_provider_descriptor["digest"]
    )
    require(
        isinstance(product_release_provider_payload, bytes)
        and len(product_release_provider_payload)
        == product_release_provider_descriptor["size"],
        "product-release signer-authentication evidence is not CAS-resolvable",
    )
    product_release_provider_evidence = json.loads(
        product_release_provider_payload,
        object_pairs_hook=strict_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            GenerationError(f"non-finite JSON number: {value}")
        ),
    )
    require(
        isinstance(product_release_provider_evidence, dict)
        and product_release_provider_evidence.get("contract")
        == "bytedesk.signer-authentication-evidence/1"
        and product_release_provider_evidence.get("purpose")
        == "product-release-v1"
        and product_release_provider_evidence.get("authenticatedSigner")
        == product_signer("product-release-v1"),
        "product-release signer-authentication evidence identity drift",
    )
    documents[PRODUCT_RELEASE_SIGNER_AUTHENTICATION_EVIDENCE_PATH] = deepcopy(
        product_release_provider_evidence
    )
    documents[PRODUCT_RELEASE_SIGNER_IDENTITY_PATH] = deepcopy(
        product_release_provider_evidence["authenticatedSigner"]
    )

    def materialize_positive_authority(
        value: Any,
        context: str,
        contract: str,
    ) -> Any:
        if isinstance(value, dict):
            if set(value) == {
                "repository", "digest", "mediaType", "size", "trustPolicy"
            }:
                trust_id = value["trustPolicy"].get("id")
                if (
                    value["mediaType"]
                    == "application/vnd.bytedesk.agent.skill-approval.v1+json"
                ):
                    trust_id = "consumer-authority-v1"
                if trust_id in trust_refs:
                    value["trustPolicy"] = deepcopy(trust_refs[trust_id])
                if value["digest"] not in CAS_PAYLOADS:
                    media_type = value["mediaType"]
                    if media_type == "application/vnd.oci.image.manifest.v1+json":
                        exact = oci_distribution_descriptor(
                            value["repository"],
                            f"fixture-{hashlib.sha256(context.encode()).hexdigest()[:24]}",
                            "amd64",
                            value["trustPolicy"],
                        )
                    else:
                        payload = (
                            rfc8785.dumps(
                                {
                                    "profile": "bytedesk.renderer-fixture-artifact/1",
                                    "contractContext": contract,
                                    "pathContext": context,
                                    "repository": value["repository"],
                                    "mediaType": media_type,
                                }
                            )
                            if media_type.endswith("+json")
                            or media_type in {
                                "application/spdx+json",
                                "application/vnd.dev.sigstore.bundle.v0.3+json",
                            }
                            else (
                                "bytedesk-renderer-fixture-artifact\n"
                                f"{contract}\n{context}\n{media_type}\n"
                            ).encode("utf-8")
                        )
                        exact = opaque_descriptor(
                            value["repository"],
                            media_type,
                            payload,
                            value["trustPolicy"],
                        )
                    value.update(exact)
                return value
            for key, child in list(value.items()):
                value[key] = materialize_positive_authority(
                    child,
                    f"{context}/{key}",
                    contract,
                )
            return value
        if isinstance(value, list):
            for index, child in enumerate(value):
                value[index] = materialize_positive_authority(
                    child,
                    f"{context}/{index}",
                    contract,
                )
            return value
        if isinstance(value, str) and is_sentinel_digest(value):
            return canonical_digest(
                {
                    "profile": "bytedesk.renderer-fixture-authority/1",
                    "contract": contract,
                    "path": context,
                }
            )
        return value

    for path, document in documents.items():
        if (
            "/positive/" in path.as_posix()
            and path.name.startswith(RENDERER_POSITIVE_FIXTURE_PREFIXES)
        ):
            materialize_positive_authority(
                document,
                path.relative_to(REPOSITORY_ROOT).as_posix(),
                str(document.get("contract", "unknown")),
            )

    def refresh_selection(value: dict[str, Any]) -> None:
        if value.get("contract") == "bytedesk.renderer-selection/1":
            value["selectionDigest"] = canonical_digest(
                renderer_selection_preimage(value)
            )

    for document in documents.values():
        walk(document, refresh_selection)

    # These two private-generator-owned fixtures are renderer conformance
    # inputs only.  Mutate isolated copies to retain the digest-propagation
    # checks without claiming or rewriting either projection.
    compile_lock = load_json(PRIVATE_COMPILATION_INPUT_PATH)
    compile_authority = load_json(CONSUMER_AUTHORITY_COMPILE_PATH)
    for auxiliary in (compile_lock, compile_authority):
        walk(auxiliary, refresh_descriptor)
        walk(auxiliary, normalize_public_subject_descriptor)
    refresh_private_compilation_authorized_input(compile_lock)
    require(
        compile_authority.get("contract") == "bytedesk.consumer-authority/1"
        and compile_authority.get("operation") == "compile",
        "compile authority fixture is not a consumer compile authority",
    )
    compile_authority["authorizedPrivateInputDigest"] = compile_lock["inputs"][
        "authorizedPrivateInputDigest"
    ]
    compile_authority_bytes = rfc8785.dumps(compile_authority)
    authority_descriptor = compile_lock["inputs"]["authoritySnapshot"]
    authority_descriptor["digest"] = canonical_digest(compile_authority)
    authority_descriptor["size"] = len(compile_authority_bytes)
    refresh_private_compilation_final_digest(compile_lock)

    mutated_lock = deepcopy(compile_lock)
    mutated_lock["inputs"]["customizationDigest"] = f"sha256:{'0' * 64}"
    refresh_private_compilation_authorized_input(mutated_lock)
    mutated_authority = deepcopy(compile_authority)
    mutated_authority["authorizedPrivateInputDigest"] = mutated_lock["inputs"][
        "authorizedPrivateInputDigest"
    ]
    mutated_authority_bytes = rfc8785.dumps(mutated_authority)
    mutated_lock["inputs"]["authoritySnapshot"]["digest"] = canonical_digest(
        mutated_authority
    )
    mutated_lock["inputs"]["authoritySnapshot"]["size"] = len(
        mutated_authority_bytes
    )
    refresh_private_compilation_final_digest(mutated_lock)
    require(
        mutated_authority["authorizedPrivateInputDigest"]
        != compile_authority["authorizedPrivateInputDigest"]
        and mutated_lock["inputs"]["authoritySnapshot"]["digest"]
        != compile_lock["inputs"]["authoritySnapshot"]["digest"]
        and mutated_lock["compilationInputDigest"]
        != compile_lock["compilationInputDigest"],
        "changed private input did not propagate through signed authority, descriptor, and final lock",
    )

    for mutation_name, mutate in (
        (
            "runtime-slot-id",
            lambda value: value["inputs"]["runtimeSlot"].__setitem__(
                "slotId", "candidate-c"
            ),
        ),
        (
            "runtime-slot-generation",
            lambda value: value["inputs"]["runtimeSlot"].__setitem__(
                "generation", value["inputs"]["runtimeSlot"]["generation"] + 1
            ),
        ),
        (
            "activation-mode",
            lambda value: value["inputs"].__setitem__(
                "activationMode",
                "guarded_in_place"
                if value["inputs"]["activationMode"] == "isolated_candidate"
                else "isolated_candidate",
            ),
        ),
    ):
        mutated = deepcopy(compile_lock)
        mutate(mutated)
        refresh_private_compilation_authorized_input(mutated)
        mutated_compile_authority = deepcopy(compile_authority)
        mutated_compile_authority["authorizedPrivateInputDigest"] = mutated[
            "inputs"
        ]["authorizedPrivateInputDigest"]
        authority_bytes = rfc8785.dumps(mutated_compile_authority)
        mutated["inputs"]["authoritySnapshot"]["digest"] = canonical_digest(
            mutated_compile_authority
        )
        mutated["inputs"]["authoritySnapshot"]["size"] = len(authority_bytes)
        refresh_private_compilation_final_digest(mutated)
        require(
            mutated["inputs"]["authorizedPrivateInputDigest"]
            != compile_lock["inputs"]["authorizedPrivateInputDigest"]
            and mutated["inputs"]["authoritySnapshot"]["digest"]
            != compile_lock["inputs"]["authoritySnapshot"]["digest"]
            and mutated["compilationInputDigest"]
            != compile_lock["compilationInputDigest"],
            f"{mutation_name} did not invalidate authority, lock, and request identity",
        )

    case_catalog = load_json(CASE_PATH)
    capabilities: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path, document in documents.items():
        if "/positive/renderer-capability__" not in path.as_posix():
            continue
        require(document.get("contract") == "bytedesk.renderer-capability/1", f"wrong capability fixture: {path}")
        document["semanticCount"] = len(document["semantics"])
        document["coverageDigest"] = canonical_digest(
            capability_coverage_preimage(document)
        )
        key = renderer_key(document)
        require(key not in capabilities, f"duplicate positive capability: {key}")
        capabilities[key] = document

    def refresh_any_capability(value: dict[str, Any]) -> None:
        if value.get("contract") != "bytedesk.renderer-capability/1":
            return
        value["semanticCount"] = len(value["semantics"])
        value["coverageDigest"] = canonical_digest(capability_coverage_preimage(value))

    for document in documents.values():
        walk(document, refresh_any_capability)

    manifests: list[dict[str, Any]] = []

    def refresh_manifest_input(value: dict[str, Any]) -> None:
        if value.get("contract") != "bytedesk.render-manifest/1":
            return
        value["effectiveSkillSetDigest"] = canonical_digest(
            effective_skill_set_preimage(value)
        )
        value["effectiveInputDigest"] = canonical_digest(
            effective_input_preimage(value)
        )
        archive_bytes = deterministic_render_archive(value)
        value["output"]["digest"] = register_cas_payload(archive_bytes)
        value["output"]["size"] = len(archive_bytes)
        value["output"]["treeDigest"] = canonical_digest(output_tree_preimage(value))
        value["output"]["fileCount"] = len(value["files"])
        value["output"]["expandedSize"] = sum(
            file_entry["size"] for file_entry in value["files"]
        )
        value["output"]["archiveProfile"] = value["outputArchiveProfile"]
        manifests.append(value)

    for document in documents.values():
        walk(document, refresh_manifest_input)

    def refresh_compatibility(
        compatibility: dict[str, Any], input_digest: str | None = None
    ) -> None:
        capability = capabilities.get(renderer_key(compatibility))
        require(capability is not None, f"no positive capability for {renderer_key(compatibility)}")
        compatibility["capabilityDigest"] = canonical_digest(capability)
        compatibility["capabilityCoverageDigest"] = capability["coverageDigest"]
        if input_digest is not None:
            compatibility["inputDigest"] = input_digest
        compatibility["coverageDigest"] = canonical_digest(
            compatibility_coverage_preimage(compatibility)
        )

    positive_bindings: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entry in case_catalog["positiveChains"]:
        compatibility_path = REPOSITORY_ROOT / entry["compatibilityPath"]
        manifest_path = REPOSITORY_ROOT / entry["manifestPath"]
        missing_paths = {
            path
            for path in (compatibility_path, manifest_path)
            if path not in documents
        }
        if missing_paths:
            require(
                missing_paths == {compatibility_path, manifest_path}
                and all(
                    is_private_compilation_owned_output(
                        path, REPOSITORY_ROOT
                    )
                    for path in missing_paths
                ),
                "renderer positive chain has partial or unowned outputs: "
                + ", ".join(
                    path.relative_to(REPOSITORY_ROOT).as_posix()
                    for path in sorted(
                        missing_paths, key=lambda value: value.as_posix()
                    )
                ),
            )
            continue
        compatibility = documents[compatibility_path]
        manifest = documents[manifest_path]
        refresh_compatibility(compatibility, manifest["effectiveInputDigest"])
        manifest["compatibility"] = deepcopy(compatibility)
        positive_bindings.append((compatibility, manifest))

    bound_compatibility_ids = {id(value) for value, _ in positive_bindings}

    for document in documents.values():
        def refresh_standalone(value: dict[str, Any]) -> None:
            if (
                value.get("contract") == "bytedesk.renderer-compatibility-result/1"
                and id(value) not in bound_compatibility_ids
            ):
                refresh_compatibility(value)

        walk(document, refresh_standalone)

    for manifest in manifests:
        refresh_compatibility(
            manifest["compatibility"], manifest["effectiveInputDigest"]
        )
        manifest["reproducibilityDigest"] = canonical_digest(
            reproducibility_preimage(manifest)
        )

    for binding in case_catalog["executionReceiptBindings"]:
        selection = documents[REPOSITORY_ROOT / binding["selectionPath"]]
        authority = documents[REPOSITORY_ROOT / binding["attemptAuthorityPath"]]
        attempt_evidence = documents[
            REPOSITORY_ROOT / binding["attemptAuthenticationEvidencePath"]
        ]
        receipt = documents[REPOSITORY_ROOT / binding["receiptPath"]]
        evidence = documents[REPOSITORY_ROOT / binding["authenticationEvidencePath"]]
        manifest = documents[REPOSITORY_ROOT / binding["manifestPath"]]
        require(
            selection.get("contract") == "bytedesk.renderer-selection/1"
            and authority.get("contract") == "bytedesk.renderer-attempt-authority/1"
            and attempt_evidence.get("contract")
            == "bytedesk.renderer-attempt-authentication-evidence/1"
            and receipt.get("contract") == "bytedesk.renderer-execution-receipt/1"
            and evidence.get("contract")
            == "bytedesk.renderer-execution-authentication-evidence/1",
            f"wrong renderer execution binding: {binding['bindingId']}",
        )
        authority["rendererSelectionDigest"] = selection["selectionDigest"]
        authority["productReleaseStatusCheckpointDigest"] = selection[
            "productReleaseStatusCheckpoint"
        ]["digest"]
        authority["productReleaseStatusCheckpointAuthenticationEvidenceDigest"] = (
            selection["productReleaseStatusCheckpointAuthenticationEvidence"]["digest"]
        )
        authority["productReleaseStatusRequestNonce"] = selection[
            "productReleaseStatusRequestNonce"
        ]
        authority["rendererReleaseStatusCheckpointDigest"] = selection[
            "rendererReleaseStatusCheckpoint"
        ]["digest"]
        authority["rendererReleaseStatusCheckpointAuthenticationEvidenceDigest"] = (
            selection["rendererReleaseStatusCheckpointAuthenticationEvidence"]["digest"]
        )
        authority["rendererReleaseStatusRequestNonce"] = selection[
            "rendererReleaseStatusRequestNonce"
        ]
        scope_token = manifest["scope"]
        harness_token = selection["targetHarness"]
        input_parameters = documents[
            FIXTURE_ROOT
            / "positive"
            / f"renderer-input-parameters__{harness_token}-{scope_token}.json"
        ]
        harness_configuration = documents[
            FIXTURE_ROOT
            / "positive"
            / f"harness-configuration__{harness_token}-{scope_token}.json"
        ]
        portable_definition = {
            "source": deepcopy(manifest["source"]),
            "sourceKind": manifest["sourceKind"],
            "agentSpecVersion": manifest["agentSpecVersion"],
        }
        authority["portableDefinitionDigest"] = canonical_digest(
            {
                "profile": "bytedesk.renderer-portable-definition/1",
                **portable_definition,
            }
        )
        functional_inputs = {
            "scope": manifest["scope"],
            "source": deepcopy(manifest["source"]),
            "sourceKind": manifest["sourceKind"],
            "agentSpecVersion": manifest["agentSpecVersion"],
            "bindingDigest": manifest.get("bindingDigest"),
            "customizationDigest": manifest.get("customizationDigest"),
            "publicSkills": deepcopy(manifest["publicSkills"]),
            "privateSkills": deepcopy(manifest["privateSkills"]),
            "inputParameters": deepcopy(input_parameters),
            "harnessConfiguration": deepcopy(harness_configuration),
            "normalizationProfile": manifest["normalizationProfile"],
            "outputArchiveProfile": manifest["outputArchiveProfile"],
        }
        authority["inputTreeDigest"] = canonical_digest(
            {
                "profile": "bytedesk.renderer-production-input-tree/1",
                "functionalInputs": functional_inputs,
            }
        )
        authority["contractBundleDigest"] = documents[PRODUCT_RELEASE_PATH][
            "contractBundle"
        ]["digest"]
        authority["issuedAt"] = "2026-07-17T12:00:04Z"
        authority["expiresAt"] = "2026-07-17T12:05:00Z"
        authority["sandboxProfileDigest"] = canonical_digest(
            {"profile": "bytedesk.renderer-production-sandbox/1", "version": 1}
        )
        authority["issuerIdentityDigest"] = canonical_digest(
            {"profile": "bytedesk.renderer-attempt-issuer/1", "issuer": "promotion-coordinator"}
        )
        request_frame = framed_jcs(
            {
                "profile": "bytedesk.renderer-production-request-frame/1",
                "rendererSelection": deepcopy(selection),
                "portableDefinition": portable_definition,
                "portableDefinitionDigest": authority["portableDefinitionDigest"],
                "functionalInputs": functional_inputs,
                "inputTreeDigest": authority["inputTreeDigest"],
                "contractBundleDigest": authority["contractBundleDigest"],
            }
        )
        request_frame_path = REPOSITORY_ROOT / binding["framedRequestPath"]
        OPERATION_PAYLOADS[request_frame_path] = request_frame
        register_cas_payload(request_frame)
        authority["framedRequestDigest"] = raw_digest(request_frame)
        authority["authorityDigest"] = canonical_digest(
            renderer_attempt_authority_preimage(authority)
        )
        attempt_evidence["purpose"] = "renderer-attempt-v1"
        attempt_evidence["attemptAuthorityDigest"] = authority["authorityDigest"]
        attempt_evidence["issuerIdentityDigest"] = authority["issuerIdentityDigest"]
        attempt_trust = trust_refs["renderer-attempt-v1"]
        attempt_evidence["signingResult"] = renderer_signing_result(
            schema_digests,
            "renderer-attempt-v1",
            authority["authorityDigest"],
            "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
            f"{binding['bindingId']}-renderer-attempt",
            attempt_trust,
            "registry.example/product/renderer-attempt-evidence",
        )
        attempt_evidence["evidenceDigest"] = canonical_digest(
            attempt_authentication_evidence_preimage(attempt_evidence)
        )
        receipt["attemptId"] = authority["attemptId"]
        receipt["attemptFencingToken"] = authority["attemptFencingToken"]
        receipt["attemptAuthorityDigest"] = authority["authorityDigest"]
        receipt["attemptAuthenticationEvidenceDigest"] = attempt_evidence[
            "evidenceDigest"
        ]
        receipt["selectionDigest"] = selection["selectionDigest"]
        receipt["productReleaseDigest"] = selection["productRelease"]["digest"]
        receipt["releaseQualificationDigest"] = selection[
            "releaseQualification"
        ]["digest"]
        receipt["productReleaseStatusDigest"] = selection[
            "productReleaseStatus"
        ]["digest"]
        receipt["rendererReleaseStatusDigest"] = selection[
            "rendererReleaseStatus"
        ]["digest"]
        receipt["rendererReleaseDigest"] = selection["rendererRelease"]["digest"]
        receipt["platform"] = selection["targetPlatform"]
        receipt["executedDistribution"] = deepcopy(selection["executableDistribution"])
        receipt["productDistributionDigest"] = selection["productDistributionDigest"]
        receipt["compiledAllowlistDigest"] = selection["compiledAllowlistDigest"]
        receipt["inputTreeDigest"] = authority["inputTreeDigest"]
        receipt["contractBundleDigest"] = authority["contractBundleDigest"]
        receipt["framedRequestDigest"] = authority["framedRequestDigest"]
        response_frame = framed_jcs(
            {
                "profile": "bytedesk.renderer-production-response-frame/1",
                "attemptId": authority["attemptId"],
                "attemptFencingToken": authority["attemptFencingToken"],
                "compatibility": deepcopy(manifest["compatibility"]),
                "renderManifest": deepcopy(manifest),
                "result": "succeeded",
            }
        )
        response_frame_path = REPOSITORY_ROOT / binding["framedResponsePath"]
        OPERATION_PAYLOADS[response_frame_path] = response_frame
        register_cas_payload(response_frame)
        receipt["framedResponseDigest"] = raw_digest(response_frame)
        receipt["outputTreeDigest"] = manifest["output"]["treeDigest"]
        receipt["outputArchiveDigest"] = manifest["output"]["digest"]
        receipt["outputArchiveSize"] = manifest["output"]["size"]
        receipt["renderManifestDigest"] = canonical_digest(manifest)
        receipt["sandboxProfileDigest"] = authority["sandboxProfileDigest"]
        receipt["workerProfileDigest"] = selection["workerProfileDigest"]
        receipt["launcherIdentityDigest"] = canonical_digest(
            {
                "profile": "bytedesk.renderer-production-launcher/1",
                "attemptId": authority["attemptId"],
            }
        )
        receipt["completedAt"] = "2026-07-17T12:00:06Z"
        receipt_digest = canonical_digest(receipt)
        evidence["purpose"] = "renderer-execution-v1"
        evidence["receiptDigest"] = receipt_digest
        evidence["attemptAuthorityDigest"] = authority["authorityDigest"]
        evidence["rendererSelectionDigest"] = selection["selectionDigest"]
        evidence["launcherIdentityDigest"] = receipt["launcherIdentityDigest"]
        execution_trust = trust_refs["renderer-execution-v1"]
        evidence["signingResult"] = renderer_signing_result(
            schema_digests,
            "renderer-execution-v1",
            receipt_digest,
            "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
            f"{binding['bindingId']}-renderer-execution",
            execution_trust,
            "registry.example/product/renderer-execution-evidence",
        )
        evidence["evidenceDigest"] = canonical_digest(
            execution_authentication_evidence_preimage(evidence)
        )
        for authority_document in (
            selection,
            authority,
            attempt_evidence,
            receipt,
            evidence,
            manifest,
        ):
            register_cas_payload(rfc8785.dumps(authority_document))

        if manifest["scope"] == "public" and selection["targetHarness"] == "native":
            require(
                manifest["privateSkills"] == []
                and manifest.get("bindingDigest") is None
                and manifest.get("customizationDigest") is None,
                "public render source contains private lineage",
            )
            public_render_trust = trust_refs["public-render-v1"]
            selection_descriptor = artifact_descriptor(
                "registry.example/product/renderer-selections",
                "application/vnd.bytedesk.agent.renderer-selection.v1+json",
                selection,
                attempt_trust,
            )
            authority_descriptor = artifact_descriptor(
                "registry.example/product/renderer-attempt-evidence",
                "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json",
                authority,
                attempt_trust,
            )
            attempt_evidence_descriptor = artifact_descriptor(
                "registry.example/product/renderer-attempt-evidence",
                "application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json",
                attempt_evidence,
                attempt_trust,
            )
            receipt_descriptor = artifact_descriptor(
                "registry.example/product/renderer-execution-evidence",
                "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json",
                receipt,
                execution_trust,
            )
            execution_evidence_descriptor = artifact_descriptor(
                "registry.example/product/renderer-execution-evidence",
                "application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json",
                evidence,
                execution_trust,
            )
            manifest_descriptor = artifact_descriptor(
                "registry.example/agents/renders",
                "application/vnd.bytedesk.agent.render-manifest.v1+json",
                manifest,
                public_render_trust,
            )
            output_archive = CAS_PAYLOADS[manifest["output"]["digest"]]
            output_archive_descriptor = opaque_descriptor(
                "registry.example/agents/renders",
                manifest["output"]["mediaType"],
                output_archive,
                public_render_trust,
            )
            output_layer_descriptor = opaque_descriptor(
                "registry.example/agents/renders",
                "application/vnd.oci.image.layer.v1.tar+gzip",
                gzip.compress(output_archive, compresslevel=9, mtime=0),
                public_render_trust,
            )
            compatibility_descriptor = json_payload_descriptor(
                "registry.example/agents/evidence",
                "application/vnd.bytedesk.agent.compatibility.v1+json",
                manifest["compatibility"],
                public_render_trust,
            )
            public_source_trust = trust_refs["public-source-v1"]
            public_source_policy = documents[
                RENDERER_CAS_ROOT / "trust-policy-public-source-v1.json"
            ]
            public_source_signers = [
                signer
                for signer in public_source_policy["signers"]
                if signer["purpose"] == "public-source-v1"
            ]
            require(
                len(public_source_signers) == 1,
                "public source trust policy must permit exactly one signer",
            )
            public_source_publisher_identity_digest = canonical_digest(
                public_source_publisher_identity_preimage(
                    public_source_signers[0]
                )
            )
            public_source_authentication_descriptors: list[dict[str, Any]] = []
            source_subjects = [manifest["source"], *manifest["publicSkills"]]
            for source_index, source_subject in enumerate(source_subjects):
                source_authentication = {
                    "contract": "bytedesk.public-source-authentication-evidence/1",
                    "schema": {
                        "id": "https://schemas.bytedesk.ai/agent-delivery/v1/public-source-authentication-evidence/1.0.0",
                        "digest": schema_digests[
                            "https://schemas.bytedesk.ai/agent-delivery/v1/public-source-authentication-evidence/1.0.0"
                        ],
                    },
                    "purpose": "public-source-v1",
                    "subject": deepcopy(source_subject),
                    "publisherIdentityDigest": (
                        public_source_publisher_identity_digest
                    ),
                    "signingResult": renderer_signing_result(
                        schema_digests,
                        "public-source-v1",
                        source_subject["digest"],
                        source_subject["mediaType"],
                        f"{binding['bindingId']}-public-source-{source_index}",
                        public_source_trust,
                        "registry.example/agents/evidence",
                    ),
                    "evidenceDigest": "sha256:" + ("0" * 64),
                }
                source_authentication["evidenceDigest"] = canonical_digest(
                    public_source_authentication_preimage(source_authentication)
                )
                source_authentication_path = (
                    RENDERER_CAS_ROOT
                    / f"{binding['bindingId']}-public-source-{source_index}-authentication.json"
                )
                documents[source_authentication_path] = source_authentication
                public_source_authentication_descriptors.append(
                    artifact_descriptor(
                        "registry.example/agents/evidence",
                        "application/vnd.bytedesk.agent.public-source-authentication-evidence.v1+json",
                        source_authentication,
                        public_source_trust,
                    )
                )

            public_finalization_time = "2026-07-17T12:00:06.500000Z"
            status_trust = trust_refs["release-status-v1"]
            status_head_trust = trust_refs["release-status-head-v1"]
            status_eligibility_trust = trust_refs[
                "release-status-eligibility-v1"
            ]

            def public_schema_descriptor(name: str) -> dict[str, str]:
                schema_id = (
                    "https://schemas.bytedesk.ai/agent-delivery/v1/"
                    f"{name}/1.0.0"
                )
                return {"id": schema_id, "digest": schema_digests[schema_id]}

            def public_signing_result(
                purpose: str,
                subject_digest: str,
                subject_media_type: str,
                evidence_id: str,
                evidence_trust: dict[str, Any],
                repository: str,
            ) -> dict[str, Any]:
                return renderer_signing_result(
                    schema_digests,
                    purpose,
                    subject_digest,
                    subject_media_type,
                    evidence_id,
                    evidence_trust,
                    repository,
                )

            def public_sign_inline_authority(
                document: dict[str, Any],
                schema_name: str,
                purpose: str,
                subject_media_type: str,
                evidence_id: str,
                authority_trust: dict[str, Any],
                repository: str,
            ) -> None:
                document["authorityDigest"] = "sha256:" + ("0" * 64)
                document["signingResult"] = {}
                authority_schema = load_json(
                    SCHEMA_ROOT / f"{schema_name}.schema.json"
                )
                document["authorityDigest"] = canonical_digest(
                    inline_authority_preimage(document, authority_schema)
                )
                document["signingResult"] = public_signing_result(
                    purpose,
                    document["authorityDigest"],
                    subject_media_type,
                    evidence_id,
                    authority_trust,
                    repository,
                )

            public_status_head_builder = StatusHeadAuthorityBuilder(
                schema_descriptor=public_schema_descriptor,
                artifact_descriptor=artifact_descriptor,
                sign_inline_authority=public_sign_inline_authority,
                signing_result=public_signing_result,
                signer=product_signer,
                register_document=lambda document_id, document: documents.__setitem__(
                    RENDERER_CAS_ROOT / f"{document_id}.json", document
                ),
                canonical_digest=canonical_digest,
                status_head_auth_schema=load_json(
                    SCHEMA_ROOT
                    / "release-status-head-authentication-evidence.schema.json"
                ),
                status_head_trust=status_head_trust,
            )

            product_status = documents[PRODUCT_RELEASE_STATUS_PATH]
            product_status_descriptor = artifact_descriptor(
                "registry.example/product/status",
                "application/vnd.bytedesk.agent.release-status.v1+json",
                product_status,
                status_trust,
            )
            product_status_history = [
                documents[
                    RENDERER_CAS_ROOT
                    / "product-release-status-sequence-1.json"
                ],
                documents[
                    RENDERER_CAS_ROOT
                    / "product-release-status-sequence-2.json"
                ],
                product_status,
            ]
            product_status_history_descriptors = [
                artifact_descriptor(
                    "registry.example/product/status",
                    "application/vnd.bytedesk.agent.release-status.v1+json",
                    status_document,
                    status_trust,
                )
                for status_document in product_status_history
            ]
            product_status_leaves = [
                status_leaf_digest(
                    subject_kind="product_release",
                    subject=selection["productRelease"],
                    sequence=status_document["sequence"],
                    epoch=1 if index < 2 else 2,
                    head=status_descriptor,
                )
                for index, (status_document, status_descriptor) in enumerate(
                    zip(
                        product_status_history,
                        product_status_history_descriptors,
                        strict=True,
                    )
                )
            ]
            product_prior_checkpoint = documents[
                RENDERER_CAS_ROOT
                / "product-release-qualification-finalization-status-head.json"
            ]
            product_prior_checkpoint_descriptor = artifact_descriptor(
                "registry.example/product/status-heads",
                "application/vnd.bytedesk.agent."
                "release-status-head-checkpoint.v1+json",
                product_prior_checkpoint,
                status_head_trust,
            )
            public_product_head = public_status_head_builder.refresh(
                checkpoint_id=(
                    "product-release-public-render-finalization-status-head"
                ),
                request_nonce=(
                    "public_render_finalization_product_release_nonce_"
                    "0123456789abcdef"
                ),
                subject_kind="product_release",
                subject=selection["productRelease"],
                status=product_status,
                status_descriptor=product_status_descriptor,
                epoch=2,
                log_leaves=product_status_leaves,
                operation_time=public_finalization_time,
                expires_at="2026-07-17T12:05:00Z",
                prior_checkpoint=product_prior_checkpoint,
                prior_checkpoint_descriptor=product_prior_checkpoint_descriptor,
            )

            renderer_status = documents[RENDERER_RELEASE_STATUS_PATHS["native"]]
            renderer_status_descriptor = artifact_descriptor(
                "registry.example/product/status",
                "application/vnd.bytedesk.agent.release-status.v1+json",
                renderer_status,
                status_trust,
            )
            renderer_status_leaves = [
                status_leaf_digest(
                    subject_kind="renderer_release",
                    subject=selection["rendererRelease"],
                    sequence=renderer_status["sequence"],
                    epoch=1,
                    head=renderer_status_descriptor,
                )
            ]
            renderer_prior_checkpoint = documents[
                RENDERER_CAS_ROOT
                / (
                    "renderer-native-1.0.0-qualification-"
                    "finalization-status-head.json"
                )
            ]
            renderer_prior_checkpoint_descriptor = artifact_descriptor(
                "registry.example/product/status-heads",
                "application/vnd.bytedesk.agent."
                "release-status-head-checkpoint.v1+json",
                renderer_prior_checkpoint,
                status_head_trust,
            )
            public_renderer_head = public_status_head_builder.refresh(
                checkpoint_id=(
                    "renderer-native-1.0.0-public-render-"
                    "finalization-status-head"
                ),
                request_nonce=(
                    "public_render_finalization_renderer_native_nonce_"
                    "0123456789abcdef"
                ),
                subject_kind="renderer_release",
                subject=selection["rendererRelease"],
                status=renderer_status,
                status_descriptor=renderer_status_descriptor,
                epoch=1,
                log_leaves=renderer_status_leaves,
                operation_time=public_finalization_time,
                expires_at="2026-07-17T12:05:00Z",
                prior_checkpoint=renderer_prior_checkpoint,
                prior_checkpoint_descriptor=renderer_prior_checkpoint_descriptor,
            )

            def store_public_verification(
                verification_id: str,
                result: dict[str, Any],
            ) -> str:
                documents[
                    RENDERER_CAS_ROOT / f"{verification_id}.json"
                ] = result
                return register_cas_payload(rfc8785.dumps(result))

            def public_signature_verification(
                *,
                verification_id: str,
                signing_evidence: dict[str, Any],
                signed_subject_digest: str,
                signed_subject_media_type: str,
                subject: dict[str, Any],
                purpose: str,
                repository: str,
            ) -> str:
                require(
                    ACTIVE_TRUST_POLICY_PIN_SET is not None,
                    "public finalization requires the product pin set",
                )
                detailed = TrustedKmsVerificationAdapter(
                    deepcopy(SIGNATURE_VERIFICATION_VECTORS)
                ).verify(
                    result=signing_evidence,
                    policy=documents[
                        RENDERER_CAS_ROOT / f"trust-policy-{purpose}.json"
                    ],
                    permitted_signer=product_signer(purpose),
                    verification_time=public_finalization_time,
                    expected_purpose=purpose,
                    expected_subject_media_type=signed_subject_media_type,
                    expected_signing_repository=repository,
                    pin_set_digest=ACTIVE_TRUST_POLICY_PIN_SET[
                        "pinSetDigest"
                    ],
                    pin_set_revocations=ACTIVE_TRUST_POLICY_PIN_SET[
                        "revocations"
                    ],
                    expected_consumer_id=None,
                )
                require(
                    signing_evidence["subjectDigest"] == signed_subject_digest
                    and subject["repository"] == repository
                    and subject["trustPolicy"]
                    == signing_evidence["trustPolicy"],
                    f"public verification subject mismatch: {verification_id}",
                )
                detailed_evidence = {
                    "profile": "bytedesk.kms-signature-verification-evidence/1",
                    **{
                        key: deepcopy(value)
                        for key, value in detailed.items()
                        if key != "verificationEvidenceDigest"
                    },
                }
                require(
                    register_cas_payload(rfc8785.dumps(detailed_evidence))
                    == detailed["verificationEvidenceDigest"],
                    f"public KMS verification evidence mismatch: {verification_id}",
                )
                result = permitted_verification_result(
                    schema_descriptor=public_schema_descriptor(
                        "verification-result"
                    ),
                    verification_id=verification_id,
                    subject=subject,
                    policy=signing_evidence["trustPolicy"],
                    evaluated_at=public_finalization_time,
                    evidence_digests=[detailed["verificationEvidenceDigest"]],
                )
                return store_public_verification(verification_id, result)

            def public_status_entry(
                *,
                entry_id: str,
                subject_kind: str,
                subject: dict[str, Any],
                status_document: dict[str, Any],
                status_descriptor: dict[str, Any],
                head: dict[str, Any],
            ) -> dict[str, Any]:
                checkpoint = head["checkpoint"]
                checkpoint_descriptor = head["checkpointDescriptor"]
                authentication = head["authentication"]
                inclusion = head["inclusionProof"]
                inclusion_descriptor = head["inclusionProofDescriptor"]
                status_verification = public_signature_verification(
                    verification_id=f"{entry_id}-status-verification",
                    signing_evidence=status_document["signingResult"],
                    signed_subject_digest=status_document["authorityDigest"],
                    signed_subject_media_type=(
                        "application/vnd.bytedesk.agent."
                        "release-status.v1+json"
                    ),
                    subject=status_descriptor,
                    purpose="release-status-v1",
                    repository="registry.example/product/status",
                )
                authentication_verification = public_signature_verification(
                    verification_id=(
                        f"{entry_id}-checkpoint-authentication-verification"
                    ),
                    signing_evidence=authentication["signingResult"],
                    signed_subject_digest=checkpoint_descriptor["digest"],
                    signed_subject_media_type=(
                        "application/vnd.bytedesk.agent."
                        "release-status-head-checkpoint.v1+json"
                    ),
                    subject=checkpoint_descriptor,
                    purpose="release-status-head-v1",
                    repository="registry.example/product/status-heads",
                )
                require(
                    verify_merkle_inclusion(
                        leaf_digest=inclusion["leafDigest"],
                        leaf_index=inclusion["leafIndex"],
                        tree_size=inclusion["treeSize"],
                        audit_path=inclusion["auditPath"],
                        expected_root=inclusion["rootDigest"],
                    ),
                    f"invalid public-finalization inclusion proof: {entry_id}",
                )
                math_statement = {
                    "profile": (
                        "bytedesk.release-status-inclusion-verification/1"
                    ),
                    "stage": "public_render_finalization",
                    "subjectKind": subject_kind,
                    "subject": subject,
                    "checkpointDigest": checkpoint_descriptor["digest"],
                    "proofDigest": inclusion_descriptor["digest"],
                    "algorithm": inclusion["algorithm"],
                    "leafDigest": inclusion["leafDigest"],
                    "leafIndex": inclusion["leafIndex"],
                    "treeSize": inclusion["treeSize"],
                    "rootDigest": inclusion["rootDigest"],
                    "auditPath": inclusion["auditPath"],
                    "evaluatedAt": public_finalization_time,
                    "verified": True,
                }
                math_evidence_digest = register_cas_payload(
                    rfc8785.dumps(math_statement)
                )
                inclusion_result = permitted_verification_result(
                    schema_descriptor=public_schema_descriptor(
                        "verification-result"
                    ),
                    verification_id=f"{entry_id}-inclusion-verification",
                    subject=inclusion_descriptor,
                    policy=status_head_trust,
                    evaluated_at=public_finalization_time,
                    evidence_digests=[math_evidence_digest],
                )
                inclusion_verification = store_public_verification(
                    f"{entry_id}-inclusion-verification",
                    inclusion_result,
                )
                return {
                    "subjectKind": subject_kind,
                    "subject": deepcopy(subject),
                    "status": deepcopy(status_descriptor),
                    "checkpoint": deepcopy(checkpoint_descriptor),
                    "checkpointAuthenticationEvidence": deepcopy(
                        head["authenticationDescriptor"]
                    ),
                    "requestNonce": checkpoint["requestNonce"],
                    "clientPriorState": deepcopy(
                        checkpoint["clientPriorState"]
                    ),
                    "headInclusionProof": deepcopy(inclusion_descriptor),
                    "consistencyProof": None,
                    "verificationEvidenceDigests": {
                        "status": status_verification,
                        "checkpointAuthentication": (
                            authentication_verification
                        ),
                        "headInclusionProof": inclusion_verification,
                        "consistencyProof": None,
                    },
                    "statusDocument": status_document,
                    "checkpointDocument": checkpoint,
                    "checkpointAuthenticationEvidenceDocument": (
                        authentication
                    ),
                    "headInclusionProofDocument": inclusion,
                    "consistencyProofDocument": None,
                }

            public_product_entry = public_status_entry(
                entry_id="public-finalization-product-release",
                subject_kind="product_release",
                subject=selection["productRelease"],
                status_document=product_status,
                status_descriptor=product_status_descriptor,
                head=public_product_head,
            )
            public_renderer_entry = public_status_entry(
                entry_id="public-finalization-renderer-native-1.0.0-amd64",
                subject_kind="renderer_release",
                subject=selection["rendererRelease"],
                status_document=renderer_status,
                status_descriptor=renderer_status_descriptor,
                head=public_renderer_head,
            )
            public_renderer_entry.update(
                {
                    "harnessId": selection["targetHarness"],
                    "rendererId": selection["rendererId"],
                    "rendererVersion": selection["rendererVersion"],
                    "targetPlatform": selection["targetPlatform"],
                }
            )
            require(
                ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR is not None
                and ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE is not None,
                "public finalization lacks pin-set provider evidence",
            )
            public_eligibility_builder = ReleaseStatusEligibilityBuilder(
                schema_descriptor=public_schema_descriptor,
                artifact_descriptor=artifact_descriptor,
                signing_result=public_signing_result,
                canonical_digest=canonical_digest,
                eligibility_schema=load_json(
                    SCHEMA_ROOT
                    / "release-status-eligibility-evidence.schema.json"
                ),
                trust_policy=status_eligibility_trust,
                repository="registry.example/product/status-eligibility",
                consumer_id=None,
                pin_set_descriptor=ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR,
                pin_set_digest=ACTIVE_TRUST_POLICY_PIN_SET["pinSetDigest"],
                pin_set_provider_evidence=(
                    ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE
                ),
                register_document=lambda document_id, document: documents.__setitem__(
                    RENDERER_CAS_ROOT / f"{document_id}.json", document
                ),
            )
            public_eligibility, public_eligibility_descriptor = (
                public_eligibility_builder.build(
                    evidence_id="public-render-finalization-status-eligibility",
                    stage="public_render_finalization",
                    operation_time=public_finalization_time,
                    product=public_product_entry,
                    renderers=[public_renderer_entry],
                )
            )
            public_eligibility_verification = public_signature_verification(
                verification_id=(
                    "public-render-finalization-status-eligibility-verification"
                ),
                signing_evidence=public_eligibility["signingResult"],
                signed_subject_digest=public_eligibility["eligibilityDigest"],
                signed_subject_media_type=(
                    "application/vnd.bytedesk.agent."
                    "release-status-eligibility-evidence-digest.v1+json"
                ),
                subject=public_eligibility_descriptor,
                purpose="release-status-eligibility-v1",
                repository="registry.example/product/status-eligibility",
            )
            public_render = documents[HARNESS_RENDER_PATH]
            public_render.clear()
            public_render.update(
                {
                    "contract": "bytedesk.harness-render/1",
                    "schema": {
                        "id": "https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0",
                        "digest": schema_digests[
                            "https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0"
                        ],
                    },
                    "source": deepcopy(manifest["source"]),
                    "publicSkills": deepcopy(manifest["publicSkills"]),
                    "publicSourceAuthenticationEvidence": (
                        public_source_authentication_descriptors
                    ),
                    "productRelease": deepcopy(selection["productRelease"]),
                    "releaseQualification": deepcopy(
                        selection["releaseQualification"]
                    ),
                    "releaseStatusEligibility": deepcopy(
                        public_eligibility_descriptor
                    ),
                    "releaseStatusEligibilityDigest": public_eligibility[
                        "eligibilityDigest"
                    ],
                    "releaseStatusEligibilityVerificationEvidenceDigest": (
                        public_eligibility_verification
                    ),
                    "rendererRelease": deepcopy(selection["rendererRelease"]),
                    "executedDistribution": deepcopy(
                        selection["executableDistribution"]
                    ),
                    "platform": selection["targetPlatform"],
                    "productDistributionDigest": selection[
                        "productDistributionDigest"
                    ],
                    "compiledAllowlistDigest": selection[
                        "compiledAllowlistDigest"
                    ],
                    "rendererSchemas": deepcopy(manifest["rendererSchemas"]),
                    "normalizedParametersDigest": manifest[
                        "inputParametersDigest"
                    ],
                    "rendererSelection": selection_descriptor,
                    "rendererAttemptAuthority": authority_descriptor,
                    "rendererAttemptAuthenticationEvidence": (
                        attempt_evidence_descriptor
                    ),
                    "rendererExecutionReceipt": receipt_descriptor,
                    "rendererExecutionAuthenticationEvidence": (
                        execution_evidence_descriptor
                    ),
                    "renderManifest": manifest_descriptor,
                    "outputArchive": output_archive_descriptor,
                    "compatibility": compatibility_descriptor,
                    "outputLayer": output_layer_descriptor,
                    "files": [
                        {
                            "path": entry["path"],
                            "digest": entry["digest"],
                            "size": entry["size"],
                            "mode": entry["mode"],
                        }
                        for entry in manifest["files"]
                    ],
                    "createdAt": public_finalization_time,
                    "trustPolicy": deepcopy(public_render_trust),
                    "authorityDigest": "sha256:" + ("0" * 64),
                    "signingResult": {},
                }
            )
            require_tenant_free_public_lineage(public_render, manifest)
            public_render["authorityDigest"] = canonical_digest(
                public_render_preimage(public_render)
            )
            public_render["signingResult"] = renderer_signing_result(
                schema_digests,
                "public-render-v1",
                public_render["authorityDigest"],
                "application/vnd.bytedesk.agent.render.v1+json",
                f"{binding['bindingId']}-public-render",
                public_render_trust,
                "registry.example/agents/renders",
                signed_at=public_finalization_time,
            )
            public_render_bytes = rfc8785.dumps(public_render)
            register_cas_payload(public_render_bytes)
            public_render_descriptor = artifact_descriptor(
                "registry.example/agents/renders",
                "application/vnd.bytedesk.agent.render.v1+json",
                public_render,
                public_render_trust,
            )

            portable_layer = deterministic_oci_layer(
                [
                    (
                        "agent/source",
                        CAS_PAYLOADS[public_render["source"]["digest"]],
                    )
                ]
            )
            public_skill_layer: bytes | None = None
            if public_render["publicSkills"]:
                public_skill_layer = deterministic_oci_layer(
                    [
                        (
                            f"skills/{index:06d}-{skill['digest'].removeprefix('sha256:')}",
                            CAS_PAYLOADS[skill["digest"]],
                        )
                        for index, skill in enumerate(
                            public_render["publicSkills"]
                        )
                    ]
                )
            public_output_layer = CAS_PAYLOADS[
                public_render["outputLayer"]["digest"]
            ]
            evidence_entries: list[tuple[str, bytes]] = [
                ("evidence/harness-render.json", public_render_bytes),
                (
                    "evidence/release-status-eligibility.json",
                    rfc8785.dumps(public_eligibility),
                ),
                ("evidence/renderer-selection.json", rfc8785.dumps(selection)),
                (
                    "evidence/renderer-attempt-authority.json",
                    rfc8785.dumps(authority),
                ),
                (
                    "evidence/renderer-attempt-authentication.json",
                    rfc8785.dumps(attempt_evidence),
                ),
                (
                    "evidence/renderer-execution-receipt.json",
                    rfc8785.dumps(receipt),
                ),
                (
                    "evidence/renderer-execution-authentication.json",
                    rfc8785.dumps(evidence),
                ),
                ("evidence/render-manifest.json", rfc8785.dumps(manifest)),
            ]
            for source_index, descriptor in enumerate(
                public_source_authentication_descriptors
            ):
                evidence_entries.append(
                    (
                        f"evidence/public-source-authentication-{source_index:06d}.json",
                        CAS_PAYLOADS[descriptor["digest"]],
                    )
                )
            evidence_layer = deterministic_oci_layer(evidence_entries)
            oci_layers = [("portable-definition", portable_layer)]
            if public_skill_layer is not None:
                oci_layers.append(("public-skills", public_skill_layer))
            oci_layers.extend(
                [
                    ("public-render", public_output_layer),
                    ("evidence", evidence_layer),
                ]
            )
            destination_repository = "registry.example/agents/renders"
            root_descriptor, manifest_bytes, oci_blobs = build_oci_manifest(
                repository=destination_repository,
                artifact_type=(
                    "application/vnd.bytedesk.agent.render.v1+json"
                ),
                layers=oci_layers,
                annotations={
                    "ai.bytedesk.agent-delivery.authority-digest": public_render[
                        "authorityDigest"
                    ],
                    "ai.bytedesk.agent-delivery.status-eligibility-digest": (
                        public_eligibility["eligibilityDigest"]
                    ),
                },
            )
            for (_, _), payload in oci_blobs.items():
                register_cas_payload(payload)
            graph = OciGraphVerifier(
                fetch=lambda repository, digest: oci_blobs[(repository, digest)]
            ).verify(
                root_descriptor,
                expected_repository=destination_repository,
                expected_artifact_type=(
                    "application/vnd.bytedesk.agent.render.v1+json"
                ),
            )
            manifest_document = json.loads(manifest_bytes)
            non_root_descriptors = [
                manifest_document["config"],
                *manifest_document["layers"],
            ]
            blob_streams = [
                build_oci_blob_stream(
                    media_type=descriptor["mediaType"],
                    payload=oci_blobs[
                        (destination_repository, descriptor["digest"])
                    ],
                )
                for descriptor in non_root_descriptors
            ]
            publication_payload_digest = public_render_publication_payload_digest(
                destination_repository=destination_repository,
                harness_render_descriptor=public_render_descriptor,
                root_descriptor=root_descriptor,
                manifest_bytes=manifest_bytes,
                blobs=blob_streams,
                graph_digest=graph["graphDigest"],
            )
            PUBLIC_RENDER_FINALIZATION_RESULT = {
                "harnessRender": deepcopy(public_render),
                "harnessRenderDescriptor": deepcopy(public_render_descriptor),
                "authorityDigest": public_render["authorityDigest"],
                "signingResult": deepcopy(public_render["signingResult"]),
                "rootDescriptor": deepcopy(root_descriptor),
                "manifestBytes": encode_bounded_bytes(manifest_bytes),
                "blobs": blob_streams,
                "graphDigest": graph["graphDigest"],
                "publicationPayloadDigest": publication_payload_digest,
            }
            documents[
                RENDERER_CAS_ROOT / "public-render-finalization-result.json"
            ] = deepcopy(PUBLIC_RENDER_FINALIZATION_RESULT)
    canonicalize_indexed_provider_audit_fixtures(documents)
    materialize_renderer_closed_schema_denials(documents)
    return trust_refs


def expected_documents() -> dict[Path, bytes]:
    global ACTIVE_TRUST_POLICY_PIN_SET
    global ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR
    global ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE
    global PUBLIC_RENDER_FINALIZATION_RESULT
    CAS_PAYLOADS.clear()
    OPERATION_PAYLOADS.clear()
    SIGNATURE_VERIFICATION_VECTORS.clear()
    KEYLESS_VERIFICATION_VECTORS.clear()
    TRUST_POLICY_PROVIDER_AUTHENTICATION_VECTORS.clear()
    ACTIVE_TRUST_POLICY_PIN_SET = None
    ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR = None
    ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE = None
    PUBLIC_RENDER_FINALIZATION_RESULT = None
    renderer_tokens = tuple(
        token
        for name in MANAGED_SCHEMA_NAMES
        for token in (
            f"https://schemas.bytedesk.ai/agent-delivery/v1/{name}/1.0.0",
            f"bytedesk.{name}/1",
        )
    )
    declared_auxiliary_paths = renderer_private_auxiliary_paths(
        REPOSITORY_ROOT
    )
    require(
        declared_auxiliary_paths
        == {CONSUMER_AUTHORITY_COMPILE_PATH, PRIVATE_COMPILATION_INPUT_PATH},
        "renderer private auxiliary input declaration drift",
    )
    fixture_paths = []
    for path in sorted(FIXTURE_ROOT.rglob("*.json")):
        if is_private_compilation_owned_output(path, REPOSITORY_ROOT):
            continue
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in renderer_tokens) or (
            path.parent.name == "positive"
            and path.name.startswith(RENDERER_POSITIVE_FIXTURE_PREFIXES)
        ):
            fixture_paths.append(path)
    documents = {path: load_json(path) for path in fixture_paths}
    for path in (
        CONTRACT_BUNDLE_FIXTURE_PATH,
        OPERATIONAL_READINESS_REPORT_PATH,
    ):
        documents.setdefault(path, load_json(path))
    native_release = documents[RENDERER_RELEASE_PATHS["native"]]
    for harness_id, path in RENDERER_RELEASE_PATHS.items():
        if path not in documents:
            documents[path] = deepcopy(native_release)
    native_selection = documents[RENDERER_SELECTION_PATHS["native"]]
    for harness_id, path in RENDERER_SELECTION_PATHS.items():
        if path not in documents:
            selection = deepcopy(native_selection)
            selection["targetHarness"] = harness_id
            selection["rendererId"] = harness_id
            selection["targetPlatform"] = "linux/amd64"
            documents[path] = selection

    schemas: dict[str, dict[str, Any]] = {}
    schema_digests: dict[str, str] = {}
    for name in MANAGED_SCHEMA_NAMES:
        schema = load_json(SCHEMA_ROOT / f"{name}.schema.json")
        schema_id = schema["$id"]
        schemas[schema_id] = schema
        schema_digests[schema_id] = canonical_digest(schema)

    trust_refs = refresh_renderer_documents(documents, schema_digests)
    allowlist_unknown_authority = deepcopy(documents[RENDERER_ALLOWLIST_PATH])
    allowlist_unknown_authority["unknownAuthority"] = True
    documents[RENDERER_ALLOWLIST_UNKNOWN_AUTHORITY_PATH] = (
        allowlist_unknown_authority
    )
    trust_policy_unknown_authority = deepcopy(
        documents[PRODUCT_RELEASE_TRUST_POLICY_PATH]
    )
    trust_policy_unknown_authority["unknownAuthority"] = True
    documents[PRODUCT_RELEASE_TRUST_POLICY_UNKNOWN_AUTHORITY_PATH] = (
        trust_policy_unknown_authority
    )
    validate_renderer_closed_schema_denials(documents, schemas)
    expected = {path: output_bytes(document) for path, document in documents.items()}
    expected.update(OPERATION_PAYLOADS)
    expected.update(
        {
            RENDERER_CAS_BLOB_ROOT / digest.removeprefix("sha256:"): payload
            for digest, payload in CAS_PAYLOADS.items()
        }
    )
    case_catalog = load_json(CASE_PATH)
    matching_private_manifest_cases = [
        index
        for index, case in enumerate(case_catalog["negativeCases"])
        if case.get("caseId")
        == PRIVATE_MANIFEST_EFFECTIVE_INPUT_SUBSTITUTION_CASE["caseId"]
    ]
    require(
        len(matching_private_manifest_cases) <= 1,
        "duplicate private-manifest effective-input substitution case",
    )
    if matching_private_manifest_cases:
        case_catalog["negativeCases"][
            matching_private_manifest_cases[0]
        ] = deepcopy(PRIVATE_MANIFEST_EFFECTIVE_INPUT_SUBSTITUTION_CASE)
    else:
        insertion_index = next(
            (
                index + 1
                for index, case in enumerate(case_catalog["negativeCases"])
                if case.get("caseId")
                == "renderer-effective-input-digest-mismatch"
            ),
            len(case_catalog["negativeCases"]),
        )
        case_catalog["negativeCases"].insert(
            insertion_index,
            deepcopy(PRIVATE_MANIFEST_EFFECTIVE_INPUT_SUBSTITUTION_CASE),
        )
    require(
        ACTIVE_TRUST_POLICY_PIN_SET is not None,
        "product trust-policy pin set was not constructed",
    )
    require(
        ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR is not None
        and ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE is not None
        and len(TRUST_POLICY_PROVIDER_AUTHENTICATION_VECTORS) == 1,
        "product trust-policy pin set lacks provider activation authority",
    )
    case_catalog.pop("trustPolicyPins", None)
    case_catalog["trustPolicyPinSet"] = deepcopy(ACTIVE_TRUST_POLICY_PIN_SET)
    case_catalog["trustPolicyPinSetDescriptor"] = deepcopy(
        ACTIVE_TRUST_POLICY_PIN_SET_DESCRIPTOR
    )
    case_catalog["trustPolicyPinSetProviderEvidence"] = deepcopy(
        ACTIVE_TRUST_POLICY_PIN_SET_PROVIDER_EVIDENCE
    )
    case_catalog["trustPolicyProviderAuthenticationVectors"] = sorted(
        deepcopy(TRUST_POLICY_PROVIDER_AUTHENTICATION_VECTORS),
        key=lambda vector: vector["vectorId"],
    )
    unique_vectors = {
        vector["vectorId"]: vector
        for vector in SIGNATURE_VERIFICATION_VECTORS
    }
    require(
        len(unique_vectors) == len(SIGNATURE_VERIFICATION_VECTORS),
        "duplicate trusted KMS verification vector",
    )
    case_catalog["signatureVerificationVectors"] = sorted(
        unique_vectors.values(),
        key=lambda vector: vector["vectorId"],
    )
    unique_keyless_vectors = {
        vector["vectorId"]: vector
        for vector in KEYLESS_VERIFICATION_VECTORS
    }
    require(
        len(unique_keyless_vectors) == len(KEYLESS_VERIFICATION_VECTORS) == 1,
        "contract-bundle keyless verification vector is not unique",
    )
    case_catalog["keylessVerificationVectors"] = sorted(
        unique_keyless_vectors.values(),
        key=lambda vector: vector["vectorId"],
    )
    require(
        PUBLIC_RENDER_FINALIZATION_RESULT is not None,
        "public render finalization result was not constructed",
    )
    case_catalog["publicRenderFinalization"] = deepcopy(
        PUBLIC_RENDER_FINALIZATION_RESULT
    )
    embedded_allowlist_digest = documents[PRODUCT_RELEASE_PATH]["compiledAllowlist"][
        "digest"
    ]
    for binding in case_catalog["releaseSelectionBindings"]:
        binding["productDistributionEmbeddedAllowlistDigest"] = (
            embedded_allowlist_digest
        )
    expected[CASE_PATH] = output_bytes(case_catalog)

    inventory = load_json(INVENTORY_PATH)
    inventory_ids: set[str] = set()
    for entry in inventory["schemas"]:
        schema_id = entry["id"]
        if schema_id in schema_digests:
            entry["digest"] = schema_digests[schema_id]
            inventory_ids.add(schema_id)
    for schema_id in sorted(set(schema_digests) - inventory_ids):
        name = schema_id.removesuffix("/1.0.0").rsplit("/", 1)[-1]
        inventory["schemas"].append(
            {
                "id": schema_id,
                "path": f"contracts/schemas/v1/{name}.schema.json",
                "digest": schema_digests[schema_id],
            }
        )
    inventory["schemas"] = sorted(
        inventory["schemas"], key=lambda entry: entry["id"].encode("utf-8")
    )
    expected[INVENTORY_PATH] = output_bytes(inventory)

    documentation_map = load_json(DOCUMENTATION_MAP_PATH)
    for entry in documentation_map["documents"]:
        path = REPOSITORY_ROOT / entry["path"]
        if entry["path"] == "docs/standards/renderer-identity-v1.md":
            entry["digest"] = file_digest(path)
    expected[DOCUMENTATION_MAP_PATH] = output_bytes(documentation_map)
    try:
        assert_renderer_excludes_private_outputs(
            expected.keys(), REPOSITORY_ROOT
        )
    except RuntimeError as error:
        raise GenerationError(str(error)) from error
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically refresh renderer fixture, inventory, and documentation digests",
    )
    args = parser.parse_args()
    try:
        expected = expected_documents()
        drift = [
            path
            for path, payload in expected.items()
            if not path.exists() or path.read_bytes() != payload
        ]
        unexpected_cas = []
        if RENDERER_CAS_ROOT.exists():
            for path in sorted(RENDERER_CAS_ROOT.rglob("*")):
                if path.is_symlink():
                    raise GenerationError(f"renderer CAS contains a symlink: {path}")
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
            raise GenerationError(f"renderer digest fixtures are stale: {paths}")
    except (KeyError, IndexError, TypeError, GenerationError) as error:
        print(f"renderer digest fixture generation failed: {error}", file=sys.stderr)
        return 1
    print(
        "renderer digest fixtures "
        + (
            f"refreshed: {len(drift)} files, removed {len(unexpected_cas)} stale CAS files"
            if args.write
            else "are current"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
