#!/usr/bin/env python3
"""Closed conformance-only release-evidence creation and verification helpers.

The repository verifier never turns this evidence into production authority.
Production release evidence is resolved as authenticated OCI referrers by the
independently pinned sealed verifier.  This module gives the repository's
external-Adapter harness an executable, fail-closed equivalent contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from contractlib import (
    ContractToolError,
    canonical_digest,
    canonical_json,
    load_json,
    sha256_bytes,
    stable_read_bytes,
    strict_json_bytes,
    validation_error_key,
)


EVALUATION_ATTESTATION_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/evaluation-attestation/1.0.0"
)
CONTRACT_BUNDLE_MEDIA_TYPE = "application/vnd.bytedesk.agent.contract-bundle.v1+json"
ATTESTATION_FILENAME = "attestation.json"
MAX_RELEASE_EVIDENCE_FILE_BYTES = 64 * 1024 * 1024
MAX_RELEASE_EVIDENCE_TREE_BYTES = 256 * 1024 * 1024

RELEASE_EVIDENCE_IDS = (
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
)

SOURCE_EVIDENCE = {
    "schema": (
        (
            "go_schema",
            "go-schema-validation.json",
            "bytedesk.contract-validation-evidence/1",
            "outcome",
        ),
        (
            "python_schema",
            "python-schema-validation.json",
            "bytedesk.contract-validation-evidence/1",
            "outcome",
        ),
        (
            "validator_agreement",
            "validator-agreement.json",
            "bytedesk.validator-agreement-evidence/1",
            "outcome",
        ),
        (
            "schema_inventory",
            "schema-inventory-conformance.json",
            "bytedesk.schema-inventory-conformance/1",
            "outcome",
        ),
    ),
    "conformance": (
        (
            "strict_json",
            "strict-json-resource-conformance.json",
            "bytedesk.strict-json-resource-conformance/1",
            "outcome",
        ),
        (
            "agent_spec_source",
            "agent-spec-source-resolution-conformance.json",
            "bytedesk.agent-spec-source-resolution-conformance/1",
            "outcome",
        ),
        (
            "downstream_ports",
            "downstream-port-validation.json",
            "bytedesk.downstream-port-validation-evidence/1",
            "result",
        ),
        (
            "protocol_fixtures",
            "protocol-fixture-validation.json",
            "bytedesk.protocol-fixture-validation-evidence/1",
            "result",
        ),
        (
            "renderer_digests",
            "renderer-digest-validation.json",
            "bytedesk.renderer-digest-validation-evidence/1",
            "result",
        ),
        (
            "conformance_plan",
            "downstream-conformance-plan-validation.json",
            "bytedesk.conformance-plan-validation-evidence/1",
            "result",
        ),
        (
            "release_workflow",
            "release-workflow-boundary.json",
            "bytedesk.contract-release-workflow-boundary/1",
            "outcome",
        ),
    ),
    "determinism": (
        (
            "reproducible_build",
            "reproducible-build.json",
            "bytedesk.reproducible-contract-build-evidence/1",
            "outcome",
        ),
    ),
}

EXECUTED_DISTRIBUTION_TOOL_PATHS = (
    ".github/workflows/contracts.yml",
    "Makefile",
    "go.mod",
    "go.sum",
    "pyproject.toml",
    "uv.lock",
    "cmd/schema-validator/main.go",
    "internal/contracts/canonical/canonical.go",
    "internal/contracts/canonical/encode.go",
    "internal/contracts/canonical/errors.go",
    "internal/contracts/canonical/json.go",
    "internal/contracts/canonical/yaml.go",
    "internal/contracts/schema/validator.go",
    "scripts/verify_architecture.py",
    "scripts/verify_repository.py",
    "scripts/contracts/build_bundle.py",
    "scripts/contracts/bundle_profile.py",
    "scripts/contracts/compare_reproducible_builds.py",
    "scripts/contracts/compare_validator_evidence.py",
    "scripts/contracts/contractlib.py",
    "scripts/contracts/release_evidence.py",
    "scripts/contracts/create_test_release_evidence.py",
    "scripts/contracts/create_test_trust_policy.py",
    "scripts/contracts/generate_conformance_plan.py",
    "scripts/contracts/generate_downstream_port_types.py",
    "scripts/contracts/generate_protocol_fixtures.py",
    "scripts/contracts/generate_renderer_digest_fixtures.py",
    "scripts/contracts/lint_projections.py",
    "scripts/contracts/refresh_contract_metadata.py",
    "scripts/contracts/test_agent_spec_source_resolution.py",
    "scripts/contracts/test_bundle_safety.py",
    "scripts/contracts/test_conformance_plan.py",
    "scripts/contracts/test_contract_metadata_refresh.py",
    "scripts/contracts/test_downstream_ports.py",
    "scripts/contracts/test_projection_validation.py",
    "scripts/contracts/test_protocol_fixtures.py",
    "scripts/contracts/test_release_evidence.py",
    "scripts/contracts/test_renderer_digests.py",
    "scripts/contracts/test_release_workflow_structure.py",
    "scripts/contracts/test_schema_inventory.py",
    "scripts/contracts/test_strict_json.py",
    "scripts/contracts/test_supply_chain_security.py",
    "scripts/contracts/validate_schemas.py",
    "scripts/contracts/verify_bundle.py",
)
PRODUCT_RELEASE_POLICY_ID = "product-release-v1"
PRODUCT_RELEASE_POLICY_PATH = Path(
    "contracts/fixtures/operations/renderer-cas/"
    "trust-policy-product-release-v1.json"
)
TEST_EVALUATOR_REPOSITORY = "registry.example/product/builders"
TEST_EVALUATOR_MEDIA_TYPE = (
    "application/vnd.bytedesk.contract-release-evaluator-conformance.v1+json"
)

SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
OCI_REPOSITORY_PATTERN = re.compile(
    r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?/)?"
    r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$"
)


@dataclass(frozen=True)
class ReleaseEvidenceEvaluation:
    available_evidence: frozenset[str]
    attestation_digest: str
    evidence_digests: Mapping[str, str]
    evaluated_at: str
    evaluator: Mapping[str, Any]
    builder_digest: str
    authority_issued: bool
    attestation: Mapping[str, Any]


def evidence_filename(evidence_id: str) -> str:
    if evidence_id not in RELEASE_EVIDENCE_IDS:
        raise ContractToolError(f"unknown release-evidence ID: {evidence_id}")
    return f"{evidence_id}.json"


def release_evidence_subject(
    *, repository: str, digest: str, size: int, trust_policy: dict[str, str]
) -> dict[str, Any]:
    if OCI_REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ContractToolError("release-evidence subject repository is not an exact OCI repository")
    _require_digest(digest, "release-evidence subject digest")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ContractToolError("release-evidence subject size is invalid")
    _validate_policy_ref(trust_policy, "release-evidence subject trust policy")
    return {
        "repository": repository,
        "digest": digest,
        "mediaType": CONTRACT_BUNDLE_MEDIA_TYPE,
        "size": size,
        "trustPolicy": dict(trust_policy),
    }


def _require_digest(value: Any, description: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ContractToolError(f"{description} is not an exact SHA-256 digest")
    return value


def _require_exact_fields(value: Any, fields: set[str], description: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractToolError(f"{description} is not a closed object")
    return value


def _validate_policy_ref(value: Any, description: str) -> dict[str, str]:
    result = _require_exact_fields(value, {"id", "digest"}, description)
    if not isinstance(result["id"], str) or not result["id"]:
        raise ContractToolError(f"{description} ID is invalid")
    _require_digest(result["digest"], f"{description} digest")
    return result


def _validate_artifact_descriptor(value: Any, description: str) -> dict[str, Any]:
    result = _require_exact_fields(
        value, {"repository", "digest", "mediaType", "size", "trustPolicy"}, description
    )
    if (
        not isinstance(result["repository"], str)
        or OCI_REPOSITORY_PATTERN.fullmatch(result["repository"]) is None
    ):
        raise ContractToolError(f"{description} repository is invalid")
    _require_digest(result["digest"], f"{description} digest")
    if not isinstance(result["mediaType"], str) or not result["mediaType"]:
        raise ContractToolError(f"{description} media type is invalid")
    if (
        not isinstance(result["size"], int)
        or isinstance(result["size"], bool)
        or result["size"] < 0
    ):
        raise ContractToolError(f"{description} size is invalid")
    _validate_policy_ref(result["trustPolicy"], f"{description} trust policy")
    return result


def _parse_timestamp(value: Any, description: str) -> datetime:
    if not isinstance(value, str):
        raise ContractToolError(f"{description} is not a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractToolError(f"{description} is not a valid date-time") from error
    if parsed.tzinfo is None:
        raise ContractToolError(f"{description} has no UTC offset")
    return parsed.astimezone(timezone.utc)


def _read_regular_bytes(path: Path, description: str) -> bytes:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise ContractToolError(f"{description} is absent: {path}") from error
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ContractToolError(f"{description} is not a regular file: {path}")
    return stable_read_bytes(
        path,
        description=description,
        maximum_bytes=MAX_RELEASE_EVIDENCE_FILE_BYTES,
    )


def _load_canonical_document(path: Path, description: str) -> tuple[dict[str, Any], bytes]:
    payload = _read_regular_bytes(path, description)
    value = strict_json_bytes(payload, description)
    if not isinstance(value, dict) or payload != canonical_json(value):
        raise ContractToolError(f"{description} is not an exact RFC 8785 JSON object")
    return value, payload


def _source_paths() -> set[str]:
    return {
        f"sources/{filename}"
        for specifications in SOURCE_EVIDENCE.values()
        for _, filename, _, _ in specifications
    }


def expected_evidence_tree_paths() -> set[str]:
    return (
        {ATTESTATION_FILENAME}
        | {evidence_filename(evidence_id) for evidence_id in RELEASE_EVIDENCE_IDS}
        | _source_paths()
    )


def _validate_directory_closure(evidence_dir: Path) -> None:
    if evidence_dir.is_symlink() or not evidence_dir.is_dir():
        raise ContractToolError("release-evidence directory is absent or not a directory")
    expected_root = {
        ATTESTATION_FILENAME,
        "sources",
        *(evidence_filename(evidence_id) for evidence_id in RELEASE_EVIDENCE_IDS),
    }
    observed_root = {path.name for path in evidence_dir.iterdir()}
    if observed_root != expected_root:
        raise ContractToolError(
            "release-evidence root is not closed "
            f"missing={sorted(expected_root - observed_root)} "
            f"extra={sorted(observed_root - expected_root)}"
        )
    sources_dir = evidence_dir / "sources"
    if sources_dir.is_symlink() or not sources_dir.is_dir():
        raise ContractToolError("release-evidence sources entry is not a directory")
    expected_sources = {PurePosixPath(path).name for path in _source_paths()}
    observed_sources = {path.name for path in sources_dir.iterdir()}
    if observed_sources != expected_sources:
        raise ContractToolError(
            "release-evidence sources are not closed "
            f"missing={sorted(expected_sources - observed_sources)} "
            f"extra={sorted(observed_sources - expected_sources)}"
        )
    observed: set[str] = set()
    cumulative_size = 0
    for relative in sorted(expected_evidence_tree_paths()):
        path = evidence_dir / PurePosixPath(relative)
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise ContractToolError(f"release-evidence tree contains a non-regular file: {relative}")
        if metadata.st_size > MAX_RELEASE_EVIDENCE_FILE_BYTES:
            raise ContractToolError(f"release-evidence file exceeds the byte limit: {relative}")
        cumulative_size += metadata.st_size
        if cumulative_size > MAX_RELEASE_EVIDENCE_TREE_BYTES:
            raise ContractToolError("release-evidence tree exceeds the cumulative byte limit")
        observed.add(relative)
    expected = expected_evidence_tree_paths()
    if observed != expected:
        raise ContractToolError(
            "release-evidence tree is not closed "
            f"missing={sorted(expected - observed)} extra={sorted(observed - expected)}"
        )


def executed_distribution_tools(repo_root: Path) -> list[dict[str, Any]]:
    relative_paths = set(EXECUTED_DISTRIBUTION_TOOL_PATHS)
    for pattern in ("cmd/**/*.go", "internal/**/*.go", "scripts/**/*.py"):
        relative_paths.update(
            path.relative_to(repo_root).as_posix()
            for path in repo_root.glob(pattern)
            if path.is_file() and not path.is_symlink()
        )
    tools: list[dict[str, Any]] = []
    for relative in sorted(relative_paths):
        path = repo_root / PurePosixPath(relative)
        payload = _read_regular_bytes(path, f"executed-distribution tool {relative}")
        tools.append(
            {"path": relative, "digest": sha256_bytes(payload), "size": len(payload)}
        )
    return tools


def conformance_builder_tools(repo_root: Path) -> list[dict[str, Any]]:
    """Return builder code without policy-bearing orchestration inputs.

    The complete executed-distribution evidence still authenticates these
    orchestration files. They are excluded only from the builder identity
    because the Makefile and contracts workflow carry the expected builder and
    trust-policy pins, which would otherwise make that identity circular.
    """

    policy_orchestration_paths = {
        ".github/workflows/contracts.yml",
        "Makefile",
    }
    return [
        tool
        for tool in executed_distribution_tools(repo_root)
        if tool["path"] not in policy_orchestration_paths
    ]


def executed_distribution_digest(tools: list[dict[str, Any]]) -> str:
    return canonical_digest(executed_distribution_payload(tools))


def executed_distribution_payload(tools: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "profile": "bytedesk.contract-release-executed-distribution/1",
        "tools": tools,
    }


def conformance_builder_payload(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the exact local builder code without policy-bearing orchestration.

    Production replaces this conformance-only descriptor with the independently
    published sealed-verifier OCI manifest digest.  Keeping Makefile and the CI
    workflow out of this inventory prevents the policy digest they carry from
    becoming a circular builder input.
    """

    return {
        "profile": "bytedesk.contract-release-conformance-builder-distribution/1",
        "tools": tools,
    }


def conformance_builder_descriptor(repo_root: Path) -> dict[str, Any]:
    tools = conformance_builder_tools(repo_root)
    payload = canonical_json(conformance_builder_payload(tools))
    return {
        "profile": "bytedesk.contract-release-conformance-builder/1",
        "digest": sha256_bytes(payload),
        "size": len(payload),
    }


def _test_evaluator_trust_policy_ref(repo_root: Path) -> dict[str, str]:
    policy_path = repo_root / PRODUCT_RELEASE_POLICY_PATH
    policy = load_json(policy_path)
    if not isinstance(policy, dict) or policy.get("policyId") != PRODUCT_RELEASE_POLICY_ID:
        raise ContractToolError(
            "test evaluator trust policy is not the exact product-release policy"
        )
    scope = policy.get("scope")
    if not isinstance(scope, dict):
        raise ContractToolError("test evaluator trust-policy scope is invalid")
    purposes = scope.get("purposes")
    repositories = scope.get("repositories")
    media_types = scope.get("mediaTypes")
    if purposes != [PRODUCT_RELEASE_POLICY_ID]:
        raise ContractToolError(
            "test evaluator trust policy is not purpose-isolated to product release"
        )
    if (
        not isinstance(repositories, list)
        or not all(isinstance(item, str) for item in repositories)
        or len(repositories) != len(set(repositories))
        or TEST_EVALUATOR_REPOSITORY not in repositories
    ):
        raise ContractToolError(
            "test evaluator repository is outside the product-release policy scope"
        )
    if (
        not isinstance(media_types, list)
        or not all(isinstance(item, str) for item in media_types)
        or len(media_types) != len(set(media_types))
        or TEST_EVALUATOR_MEDIA_TYPE not in media_types
    ):
        raise ContractToolError(
            "test evaluator media type is outside the product-release policy scope"
        )
    return {
        "id": PRODUCT_RELEASE_POLICY_ID,
        "digest": canonical_digest(policy),
    }


def expected_test_evaluator(repo_root: Path) -> dict[str, Any]:
    trust_policy = _test_evaluator_trust_policy_ref(repo_root)
    tools = executed_distribution_tools(repo_root)
    distribution_bytes = canonical_json(executed_distribution_payload(tools))
    return {
        "repository": TEST_EVALUATOR_REPOSITORY,
        "digest": executed_distribution_digest(tools),
        "mediaType": TEST_EVALUATOR_MEDIA_TYPE,
        "size": len(distribution_bytes),
        "trustPolicy": trust_policy,
    }


def evaluation_schema_descriptor(repo_root: Path) -> dict[str, str]:
    schema = load_json(repo_root / "contracts/schemas/v1/evaluation-attestation.schema.json")
    if not isinstance(schema, dict) or schema.get("$id") != EVALUATION_ATTESTATION_SCHEMA_ID:
        raise ContractToolError("trusted evaluation-attestation schema source is invalid")
    return {"id": EVALUATION_ATTESTATION_SCHEMA_ID, "digest": canonical_digest(schema)}


def inventory_records(members: Mapping[str, bytes]) -> list[dict[str, Any]]:
    return [
        {"path": path, "digest": sha256_bytes(payload), "size": len(payload)}
        for path, payload in sorted(members.items())
    ]


def inventory_digest(members: Mapping[str, bytes]) -> str:
    return canonical_digest(inventory_records(members))


def spdx_package_verification_code(members: Mapping[str, bytes]) -> str:
    checksums = sorted(
        hashlib.sha1(payload, usedforsecurity=False).hexdigest() for payload in members.values()
    )
    return hashlib.sha1("".join(checksums).encode("ascii"), usedforsecurity=False).hexdigest()


def build_spdx_document(
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest: dict[str, Any],
    members: Mapping[str, bytes],
    created_at: str,
) -> dict[str, Any]:
    package_id = "SPDXRef-Package-Agent-Delivery-Contract-Bundle"
    files: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": package_id,
        }
    ]
    for index, (path, payload) in enumerate(sorted(members.items()), start=1):
        file_id = f"SPDXRef-File-{index:06d}"
        file_license = (
            "Apache-2.0"
            if path.startswith("contracts/vendor/openapi/3.2.0/")
            or path.startswith("contracts/vendor/asyncapi/3.1.0/")
            else "MIT"
        )
        files.append(
            {
                "SPDXID": file_id,
                "fileName": f"./{path}",
                "checksums": [
                    {
                        "algorithm": "SHA1",
                        "checksumValue": hashlib.sha1(
                            payload, usedforsecurity=False
                        ).hexdigest(),
                    },
                    {
                        "algorithm": "SHA256",
                        "checksumValue": sha256_bytes(payload).removeprefix("sha256:"),
                    },
                ],
                "licenseConcluded": file_license,
                "licenseInfoInFiles": [file_license],
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": package_id,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": file_id,
            }
        )
    subject_hex = subject["digest"].removeprefix("sha256:")
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "name": f"agent-delivery-contract-bundle-{manifest['bundleVersion']}",
        "documentNamespace": f"https://evidence.bytedesk.ai/spdx/contract-bundle/{subject_hex}",
        "creationInfo": {
            "created": created_at,
            "creators": ["Tool: ByteDesk Contract Release Conformance/1"],
        },
        "documentDescribes": [package_id],
        "packages": [
            {
                "SPDXID": package_id,
                "name": subject["repository"],
                "versionInfo": manifest["bundleVersion"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "packageVerificationCode": {
                    "packageVerificationCodeValue": spdx_package_verification_code(members)
                },
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": subject_hex}
                ],
                "licenseConcluded": "MIT AND Apache-2.0",
                "licenseDeclared": "MIT AND Apache-2.0",
                "licenseInfoFromFiles": ["Apache-2.0", "MIT"],
                "copyrightText": "Copyright (c) 2026 ByteDesk AI",
            }
        ],
        "files": files,
        "relationships": relationships,
        "comment": (
            "bytedesk.contract-release-evidence/sbom/1;"
            f"policy={policy['id']}@{policy['digest']}"
        ),
    }


def build_slsa_provenance(
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    evaluator: dict[str, Any],
    evaluated_at: str,
) -> dict[str, Any]:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": subject["repository"],
                "digest": {"sha256": subject["digest"].removeprefix("sha256:")},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://schemas.bytedesk.ai/build-types/contract-bundle/v1",
                "externalParameters": {
                    "bundleVersion": manifest["bundleVersion"],
                    "productVersion": manifest["productVersion"],
                    "manifestDigest": sha256_bytes(manifest_bytes),
                    "trustPolicy": dict(policy),
                },
                "internalParameters": {},
                "resolvedDependencies": [
                    {
                        "uri": "urn:bytedesk:contract-bundle:build-input",
                        "digest": {
                            "sha256": manifest["buildInputDigest"].removeprefix("sha256:")
                        },
                    },
                    {
                        "uri": "urn:bytedesk:contract-bundle:manifest",
                        "digest": {
                            "sha256": sha256_bytes(manifest_bytes).removeprefix("sha256:")
                        },
                    },
                ],
            },
            "runDetails": {
                "builder": {
                    "id": f"https://{evaluator['repository']}@{evaluator['digest']}"
                },
                "metadata": {
                    "invocationId": (
                        "urn:bytedesk:contract-release-conformance:"
                        + sha256_bytes(manifest_bytes).removeprefix("sha256:")
                    ),
                    "startedOn": evaluated_at,
                    "finishedOn": evaluated_at,
                },
            },
        },
    }


def _pin(name: str, version: str) -> str:
    return canonical_digest({"name": name, "version": version})


PINNED_SCANNERS = {
    "vulnerability": {
        "id": "bytedesk-test-vulnerability-scanner",
        "version": "1.0.0-conformance",
        "imageDigest": _pin("vulnerability-scanner-image", "1.0.0-conformance"),
        "rulesDigest": _pin("vulnerability-advisory-snapshot", "2026-07-17"),
    },
    "malware": {
        "id": "bytedesk-test-malware-scanner",
        "version": "1.0.0-conformance",
        "imageDigest": _pin("malware-scanner-image", "1.0.0-conformance"),
        "rulesDigest": _pin("malware-signature-snapshot", "2026-07-17"),
    },
    "secret_scan": {
        "id": "bytedesk-test-secret-scanner",
        "version": "1.0.0-conformance",
        "imageDigest": _pin("secret-scanner-image", "1.0.0-conformance"),
        "rulesDigest": _pin("secret-scanner-rules", "2026-07-17"),
    },
}

PINNED_LICENSE_PROFILE = {
    "licenseCatalog": {
        "id": "spdx-license-identifiers",
        "version": "3.27-conformance-subset",
        "digest": canonical_digest(
            {"identifiers": ["Apache-2.0", "MIT"], "profile": "conformance"}
        ),
    },
    "parser": {
        "id": "bytedesk-spdx-expression-parser",
        "version": "1.0.0-conformance",
        "digest": _pin("spdx-expression-parser", "1.0.0-conformance"),
    },
    "licensePolicy": {
        "id": "contract-release-license-policy-v1",
        "digest": canonical_digest(
            {
                "allowed": ["Apache-2.0", "MIT"],
                "denied": [],
                "unknown": "manual_review",
            }
        ),
    },
}


def build_scan_report(
    *,
    evidence_id: str,
    subject: dict[str, Any],
    policy: dict[str, str],
    sbom_digest: str,
    members: Mapping[str, bytes],
    evaluated_at: str,
) -> dict[str, Any]:
    if evidence_id not in PINNED_SCANNERS:
        raise ContractToolError(f"unknown scanner evidence ID: {evidence_id}")
    return {
        "profile": f"bytedesk.contract-release-{evidence_id.replace('_', '-')}-report/1",
        "subject": dict(subject),
        "policy": dict(policy),
        "scanner": dict(PINNED_SCANNERS[evidence_id]),
        "sbomDigest": sbom_digest,
        "coverage": {
            "fileCount": len(members),
            "scannedFileCount": len(members),
            "skippedFiles": [],
        },
        "findings": [],
        "scannedAt": evaluated_at,
        "outcome": "pass",
        "testOnly": True,
        "authorityIssued": False,
    }


def _validate_subject_policy_envelope(
    document: dict[str, Any],
    *,
    fields: set[str],
    profile: str,
    subject: dict[str, Any],
    policy: dict[str, str],
    description: str,
) -> None:
    _require_exact_fields(document, fields, description)
    if document.get("profile") != profile:
        raise ContractToolError(f"{description} profile is invalid")
    if document.get("subject") != subject:
        raise ContractToolError(f"{description} subject binding is invalid")
    if document.get("policy") != policy:
        raise ContractToolError(f"{description} policy binding is invalid")
    if document.get("outcome") != "pass":
        raise ContractToolError(f"{description} did not pass")
    if document.get("authorityIssued") is not False:
        raise ContractToolError(f"{description} ambiguously issued authority")


def _load_source(
    evidence_dir: Path,
    descriptor: Any,
    *,
    expected_id: str,
    expected_filename: str,
    expected_profile: str,
    outcome_field: str,
) -> dict[str, Any]:
    value = _require_exact_fields(
        descriptor,
        {"id", "path", "digest", "size", "profile", "outcomeField"},
        f"release-evidence source {expected_id}",
    )
    expected_path = f"sources/{expected_filename}"
    if value != {
        "id": expected_id,
        "path": expected_path,
        "digest": value.get("digest"),
        "size": value.get("size"),
        "profile": expected_profile,
        "outcomeField": outcome_field,
    }:
        raise ContractToolError(f"release-evidence source descriptor is invalid: {expected_id}")
    _require_digest(value["digest"], f"release-evidence source {expected_id} digest")
    if not isinstance(value["size"], int) or value["size"] < 1:
        raise ContractToolError(f"release-evidence source {expected_id} size is invalid")
    payload = _read_regular_bytes(
        evidence_dir / PurePosixPath(expected_path), f"release-evidence source {expected_id}"
    )
    if len(payload) != value["size"] or sha256_bytes(payload) != value["digest"]:
        raise ContractToolError(f"release-evidence source bytes do not match: {expected_id}")
    source = strict_json_bytes(payload, f"release-evidence source {expected_id}")
    if not isinstance(source, dict):
        raise ContractToolError(f"release-evidence source is not an object: {expected_id}")
    if source.get("profile") != expected_profile or source.get(outcome_field) != "pass":
        raise ContractToolError(f"release-evidence source did not pass: {expected_id}")
    return source


def _validate_schema_evidence(
    document: dict[str, Any],
    *,
    evidence_dir: Path,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    members: Mapping[str, bytes],
) -> None:
    fields = {
        "profile",
        "subject",
        "policy",
        "manifestDigest",
        "schemaInventory",
        "schemaCount",
        "fixtureCount",
        "sources",
        "outcome",
        "authorityIssued",
    }
    _validate_subject_policy_envelope(
        document,
        fields=fields,
        profile="bytedesk.contract-release-schema-evidence/1",
        subject=subject,
        policy=policy,
        description="schema release evidence",
    )
    if document["manifestDigest"] != sha256_bytes(manifest_bytes):
        raise ContractToolError("schema release evidence has the wrong manifest digest")
    if document["schemaInventory"] != manifest["schemaInventory"]:
        raise ContractToolError("schema release evidence has the wrong schema inventory")
    fixture_path = manifest["fixtureIndex"]["path"]
    fixture_index = strict_json_bytes(members[fixture_path], fixture_path)
    fixture_count = len(fixture_index.get("fixtures", [])) if isinstance(fixture_index, dict) else -1
    if document["schemaCount"] != len(manifest["schemas"]) or document["fixtureCount"] != fixture_count:
        raise ContractToolError("schema release evidence count binding is invalid")
    if not isinstance(document["sources"], list) or len(document["sources"]) != len(
        SOURCE_EVIDENCE["schema"]
    ):
        raise ContractToolError("schema release evidence source set is incomplete")
    for descriptor, specification in zip(document["sources"], SOURCE_EVIDENCE["schema"]):
        source = _load_source(
            evidence_dir,
            descriptor,
            expected_id=specification[0],
            expected_filename=specification[1],
            expected_profile=specification[2],
            outcome_field=specification[3],
        )
        if specification[0] in {"go_schema", "python_schema", "validator_agreement"}:
            if source.get("schemaCount") != document["schemaCount"] or source.get(
                "fixtureCount"
            ) != document["fixtureCount"]:
                raise ContractToolError(
                    f"schema release-evidence source count mismatch: {specification[0]}"
                )


def _validate_compatibility_evidence(
    document: dict[str, Any],
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest: dict[str, Any],
    members: Mapping[str, bytes],
) -> None:
    fields = {
        "profile",
        "subject",
        "policy",
        "document",
        "bundleMajor",
        "schemaDialect",
        "canonicalization",
        "outcome",
        "authorityIssued",
    }
    _validate_subject_policy_envelope(
        document,
        fields=fields,
        profile="bytedesk.contract-release-compatibility-evidence/1",
        subject=subject,
        policy=policy,
        description="compatibility release evidence",
    )
    if document["document"] != manifest["compatibility"]:
        raise ContractToolError("compatibility release evidence descriptor is invalid")
    path = manifest["compatibility"]["path"]
    compatibility = strict_json_bytes(members[path], path)
    if not isinstance(compatibility, dict) or compatibility.get("profile") != (
        "bytedesk.contract-compatibility/1"
    ):
        raise ContractToolError("bundle compatibility document profile is invalid")
    expected = {
        "bundleMajor": compatibility.get("bundleMajor"),
        "schemaDialect": compatibility.get("schemaDialect"),
        "canonicalization": compatibility.get("canonicalization"),
    }
    if any(document[key] != value for key, value in expected.items()):
        raise ContractToolError("compatibility release evidence semantic binding is invalid")
    if document["bundleMajor"] != int(str(manifest["bundleVersion"]).split(".", 1)[0]):
        raise ContractToolError("compatibility release evidence bundle major is inconsistent")


def _validate_conformance_evidence(
    document: dict[str, Any],
    *,
    evidence_dir: Path,
    subject: dict[str, Any],
    policy: dict[str, str],
) -> None:
    fields = {
        "profile",
        "subject",
        "policy",
        "sources",
        "sourceCount",
        "outcome",
        "authorityIssued",
    }
    _validate_subject_policy_envelope(
        document,
        fields=fields,
        profile="bytedesk.contract-release-conformance-evidence/1",
        subject=subject,
        policy=policy,
        description="conformance release evidence",
    )
    specifications = SOURCE_EVIDENCE["conformance"]
    if document["sourceCount"] != len(specifications) or not isinstance(
        document["sources"], list
    ) or len(document["sources"]) != len(specifications):
        raise ContractToolError("conformance release evidence source set is incomplete")
    for descriptor, specification in zip(document["sources"], specifications):
        source = _load_source(
            evidence_dir,
            descriptor,
            expected_id=specification[0],
            expected_filename=specification[1],
            expected_profile=specification[2],
            outcome_field=specification[3],
        )
        if specification[0] in {
            "downstream_ports",
            "protocol_fixtures",
            "renderer_digests",
            "conformance_plan",
        }:
            checks = source.get("checks")
            if not isinstance(checks, list) or not checks:
                raise ContractToolError(
                    f"conformance source has no executable checks: {specification[0]}"
                )
        else:
            cases = source.get("cases")
            if not isinstance(cases, list) or not cases:
                raise ContractToolError(
                    f"conformance source has no executable cases: {specification[0]}"
                )


def _validate_determinism_evidence(
    document: dict[str, Any],
    *,
    evidence_dir: Path,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest_bytes: bytes,
) -> None:
    fields = {
        "profile",
        "subject",
        "policy",
        "manifestDigest",
        "source",
        "outcome",
        "authorityIssued",
    }
    _validate_subject_policy_envelope(
        document,
        fields=fields,
        profile="bytedesk.contract-release-determinism-evidence/1",
        subject=subject,
        policy=policy,
        description="determinism release evidence",
    )
    if document["manifestDigest"] != sha256_bytes(manifest_bytes):
        raise ContractToolError("determinism release evidence manifest digest is invalid")
    specification = SOURCE_EVIDENCE["determinism"][0]
    source = _load_source(
        evidence_dir,
        document["source"],
        expected_id=specification[0],
        expected_filename=specification[1],
        expected_profile=specification[2],
        outcome_field=specification[3],
    )
    comparisons = source.get("comparisons")
    if not isinstance(comparisons, list) or source.get("comparisonCount") != 2:
        raise ContractToolError("determinism evidence must contain both exact comparisons")
    by_artifact = {
        item.get("artifact"): item for item in comparisons if isinstance(item, dict)
    }
    if set(by_artifact) != {"contract-bundle", "contract-bundle-manifest"}:
        raise ContractToolError("determinism evidence comparison set is invalid")
    expected_digests = {
        "contract-bundle": subject["digest"],
        "contract-bundle-manifest": sha256_bytes(manifest_bytes),
    }
    for artifact, expected_digest in expected_digests.items():
        comparison = by_artifact[artifact]
        if (
            comparison.get("firstDigest") != expected_digest
            or comparison.get("secondDigest") != expected_digest
            or comparison.get("byteForByteEqual") is not True
            or comparison.get("outcome") != "pass"
        ):
            raise ContractToolError(f"determinism evidence failed exact comparison: {artifact}")


def _validate_spdx(
    document: dict[str, Any],
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest: dict[str, Any],
    members: Mapping[str, bytes],
    evaluated_at: str,
) -> None:
    expected = build_spdx_document(
        subject=subject,
        policy=policy,
        manifest=manifest,
        members=members,
        created_at=evaluated_at,
    )
    if document != expected:
        raise ContractToolError("SPDX 2.3 evidence is incomplete or differs from the exact bundle inventory")


def _validate_provenance(
    document: dict[str, Any],
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    evaluator: dict[str, Any],
    evaluated_at: str,
) -> None:
    expected = build_slsa_provenance(
        subject=subject,
        policy=policy,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        evaluator=evaluator,
        evaluated_at=evaluated_at,
    )
    if document != expected:
        raise ContractToolError("SLSA provenance is incomplete or not bound to the exact subject/materials")


def _validate_scan_report(
    evidence_id: str,
    document: dict[str, Any],
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    sbom_digest: str,
    members: Mapping[str, bytes],
    evaluated_at: str,
) -> None:
    expected = build_scan_report(
        evidence_id=evidence_id,
        subject=subject,
        policy=policy,
        sbom_digest=sbom_digest,
        members=members,
        evaluated_at=evaluated_at,
    )
    if document != expected:
        raise ContractToolError(
            f"{evidence_id} evidence is unpinned, incomplete, or not bound to the exact subject"
        )


def build_license_report(
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    sbom_digest: str,
    evaluated_at: str,
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.contract-release-license-report/1",
        "subject": dict(subject),
        "policy": dict(policy),
        "sbomDigest": sbom_digest,
        **PINNED_LICENSE_PROFILE,
        "packages": [
            {
                "spdxId": "SPDXRef-Package-Agent-Delivery-Contract-Bundle",
                "declared": "MIT AND Apache-2.0",
                "concluded": "MIT AND Apache-2.0",
                "disposition": "allowed",
            }
        ],
        "evaluatedAt": evaluated_at,
        "outcome": "pass",
        "testOnly": True,
        "authorityIssued": False,
    }


def _validate_license_report(
    document: dict[str, Any],
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    sbom_digest: str,
    evaluated_at: str,
) -> None:
    if document != build_license_report(
        subject=subject,
        policy=policy,
        sbom_digest=sbom_digest,
        evaluated_at=evaluated_at,
    ):
        raise ContractToolError("license evidence is unpinned, incomplete, or not bound to the SBOM")


def build_scan_completeness_report(
    *,
    subject: dict[str, Any],
    policy: dict[str, str],
    sbom_digest: str,
    report_digests: dict[str, str],
    members: Mapping[str, bytes],
    evaluated_at: str,
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.contract-release-scan-completeness/1",
        "subject": dict(subject),
        "policy": dict(policy),
        "sbomDigest": sbom_digest,
        "inventoryDigest": inventory_digest(members),
        "reports": dict(report_digests),
        "coverage": {
            "fileCount": len(members),
            "scannedFileCount": len(members),
            "skippedFiles": [],
        },
        "complete": True,
        "evaluatedAt": evaluated_at,
        "outcome": "pass",
        "testOnly": True,
        "authorityIssued": False,
    }


def build_executed_distribution_report(
    *,
    repo_root: Path,
    subject: dict[str, Any],
    policy: dict[str, str],
    evaluator: dict[str, Any],
) -> dict[str, Any]:
    tools = executed_distribution_tools(repo_root)
    builder = conformance_builder_descriptor(repo_root)
    return {
        "profile": "bytedesk.contract-release-executed-distribution/1",
        "subject": dict(subject),
        "policy": dict(policy),
        "evaluator": dict(evaluator),
        "distributionDigest": executed_distribution_digest(tools),
        "distributionSize": len(canonical_json(executed_distribution_payload(tools))),
        "tools": tools,
        "builder": builder,
        "builderExecutionAuthenticated": False,
        "binding": "conformance_only",
        "networkAccess": False,
        "outcome": "pass",
        "testOnly": True,
        "authorityIssued": False,
    }


def source_descriptor(
    *,
    source_id: str,
    filename: str,
    profile: str,
    outcome_field: str,
    payload: bytes,
) -> dict[str, Any]:
    return {
        "id": source_id,
        "path": f"sources/{filename}",
        "digest": sha256_bytes(payload),
        "size": len(payload),
        "profile": profile,
        "outcomeField": outcome_field,
    }


def validate_release_evidence_schema(
    evaluation: ReleaseEvidenceEvaluation,
    *,
    registry: Any,
    schemas: Mapping[str, tuple[str, Any]],
) -> None:
    if EVALUATION_ATTESTATION_SCHEMA_ID not in schemas:
        raise ContractToolError("bundle omits the accepted evaluation-attestation schema")
    errors = sorted(
        Draft202012Validator(
            schemas[EVALUATION_ATTESTATION_SCHEMA_ID][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(evaluation.attestation),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"release-evidence attestation schema denial: {errors[0].message}")


def validate_release_evidence(
    attestation_path: Path,
    evidence_dir: Path,
    *,
    repo_root: Path,
    subject: dict[str, Any],
    policy: dict[str, Any],
    policy_bytes: bytes,
    expected_policy: dict[str, str],
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    members: Mapping[str, bytes],
    verification_time: str,
) -> ReleaseEvidenceEvaluation:
    """Validate and derive the complete conformance evidence set.

    No caller-supplied availability list is accepted.  A required evidence ID
    becomes available only after its unique check is ``passed``, its bytes
    match the attested digest, and its type-specific completeness rules pass.
    """

    _validate_directory_closure(evidence_dir)
    expected_attestation_path = (evidence_dir / ATTESTATION_FILENAME).absolute()
    if attestation_path.absolute() != expected_attestation_path:
        raise ContractToolError("release-evidence attestation is not resolved from its closed tree")
    _validate_policy_ref(expected_policy, "independently expected trust policy")
    if sha256_bytes(policy_bytes) != expected_policy["digest"] or policy.get(
        "policyId"
    ) != expected_policy["id"]:
        raise ContractToolError("release evidence uses a different independent trust policy")
    required = policy.get("requiredEvidence")
    if (
        not isinstance(required, list)
        or not all(isinstance(item, str) for item in required)
        or len(required) != len(set(required))
    ):
        raise ContractToolError("release-evidence policy requiredEvidence is invalid")
    if set(required) != set(RELEASE_EVIDENCE_IDS):
        raise ContractToolError(
            "conformance release-evidence policy does not require the exact product-release set"
        )
    _validate_artifact_descriptor(subject, "independently expected release-evidence subject")
    if subject["trustPolicy"] != expected_policy:
        raise ContractToolError("release-evidence subject trust policy differs from independent policy")

    attestation, attestation_bytes = _load_canonical_document(
        attestation_path, "release-evidence attestation"
    )
    _require_exact_fields(
        attestation,
        {
            "contract",
            "schema",
            "subject",
            "policy",
            "result",
            "checks",
            "evaluatedAt",
            "evaluator",
            "trustPolicy",
        },
        "release-evidence attestation",
    )
    if attestation["contract"] != "bytedesk.evaluation-attestation/1":
        raise ContractToolError("release-evidence attestation contract is invalid")
    expected_schema = evaluation_schema_descriptor(repo_root)
    if attestation["schema"] != expected_schema:
        raise ContractToolError("release-evidence attestation schema descriptor is stale")
    bundled_schema = next(
        (
            item
            for item in manifest.get("schemas", [])
            if isinstance(item, dict) and item.get("id") == EVALUATION_ATTESTATION_SCHEMA_ID
        ),
        None,
    )
    if not isinstance(bundled_schema, dict) or {
        "id": bundled_schema.get("id"),
        "digest": bundled_schema.get("digest"),
    } != expected_schema:
        raise ContractToolError("bundle does not carry the exact accepted evaluation schema")
    if attestation["subject"] != subject:
        raise ContractToolError("release-evidence attestation subject binding is invalid")
    if attestation["policy"] != expected_policy or attestation["trustPolicy"] != expected_policy:
        raise ContractToolError("release-evidence attestation policy binding is invalid")
    if attestation["result"] != "passed":
        raise ContractToolError("release-evidence attestation did not pass")
    evaluator = expected_test_evaluator(repo_root)
    if attestation["evaluator"] != evaluator:
        raise ContractToolError("release-evidence evaluator is not the exact pinned conformance tool")
    evaluated_at = _parse_timestamp(attestation["evaluatedAt"], "release evidence evaluatedAt")
    verified_at = _parse_timestamp(verification_time, "release evidence verification time")
    if evaluated_at > verified_at:
        raise ContractToolError("release evidence was evaluated in the future")
    rules = policy.get("rules")
    if not isinstance(rules, dict):
        raise ContractToolError("release-evidence policy rules are invalid")
    freshness = rules.get("freshnessSeconds")
    if not isinstance(freshness, int) or freshness < 1 or (
        verified_at - evaluated_at
    ).total_seconds() > freshness:
        raise ContractToolError("release evidence exceeds trust-policy freshness")

    checks = attestation.get("checks")
    if not isinstance(checks, list):
        raise ContractToolError("release-evidence attestation checks are invalid")
    by_id: dict[str, dict[str, Any]] = {}
    for check in checks:
        item = _require_exact_fields(
            check, {"id", "result", "evidenceDigest"}, "release-evidence check"
        )
        check_id = item.get("id")
        if not isinstance(check_id, str) or check_id not in RELEASE_EVIDENCE_IDS:
            raise ContractToolError("release-evidence attestation contains an unknown check")
        if check_id in by_id:
            raise ContractToolError(f"release-evidence attestation duplicates check: {check_id}")
        if item.get("result") != "passed":
            raise ContractToolError(f"required release-evidence check did not pass: {check_id}")
        _require_digest(item.get("evidenceDigest"), f"release-evidence check {check_id}")
        by_id[check_id] = item
    if set(by_id) != set(required):
        raise ContractToolError(
            "release-evidence attestation check set differs from trust policy "
            f"missing={sorted(set(required) - set(by_id))} extra={sorted(set(by_id) - set(required))}"
        )

    documents: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    for evidence_id in RELEASE_EVIDENCE_IDS:
        document, payload = _load_canonical_document(
            evidence_dir / evidence_filename(evidence_id),
            f"release-evidence document {evidence_id}",
        )
        if sha256_bytes(payload) != by_id[evidence_id]["evidenceDigest"]:
            raise ContractToolError(f"release-evidence bytes do not match attestation: {evidence_id}")
        documents[evidence_id] = document
        payloads[evidence_id] = payload

    sbom_digest = sha256_bytes(payloads["sbom"])
    _validate_schema_evidence(
        documents["schema"],
        evidence_dir=evidence_dir,
        subject=subject,
        policy=expected_policy,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        members=members,
    )
    _validate_compatibility_evidence(
        documents["compatibility"],
        subject=subject,
        policy=expected_policy,
        manifest=manifest,
        members=members,
    )
    _validate_conformance_evidence(
        documents["conformance"],
        evidence_dir=evidence_dir,
        subject=subject,
        policy=expected_policy,
    )
    _validate_determinism_evidence(
        documents["determinism"],
        evidence_dir=evidence_dir,
        subject=subject,
        policy=expected_policy,
        manifest_bytes=manifest_bytes,
    )
    _validate_spdx(
        documents["sbom"],
        subject=subject,
        policy=expected_policy,
        manifest=manifest,
        members=members,
        evaluated_at=attestation["evaluatedAt"],
    )
    _validate_provenance(
        documents["provenance"],
        subject=subject,
        policy=expected_policy,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        evaluator=evaluator,
        evaluated_at=attestation["evaluatedAt"],
    )
    for evidence_id in ("vulnerability", "malware", "secret_scan"):
        _validate_scan_report(
            evidence_id,
            documents[evidence_id],
            subject=subject,
            policy=expected_policy,
            sbom_digest=sbom_digest,
            members=members,
            evaluated_at=attestation["evaluatedAt"],
        )
    _validate_license_report(
        documents["license"],
        subject=subject,
        policy=expected_policy,
        sbom_digest=sbom_digest,
        evaluated_at=attestation["evaluatedAt"],
    )
    expected_report_digests = {
        evidence_id: sha256_bytes(payloads[evidence_id])
        for evidence_id in ("vulnerability", "malware", "secret_scan")
    }
    expected_completeness = build_scan_completeness_report(
        subject=subject,
        policy=expected_policy,
        sbom_digest=sbom_digest,
        report_digests=expected_report_digests,
        members=members,
        evaluated_at=attestation["evaluatedAt"],
    )
    if documents["scan_completeness"] != expected_completeness:
        raise ContractToolError("scan-completeness evidence is false or cross-binds another report")
    expected_distribution = build_executed_distribution_report(
        repo_root=repo_root,
        subject=subject,
        policy=expected_policy,
        evaluator=evaluator,
    )
    if documents["executed_distribution"] != expected_distribution:
        raise ContractToolError("executed-distribution evidence is unpinned or incomplete")

    return ReleaseEvidenceEvaluation(
        available_evidence=frozenset(by_id),
        attestation_digest=sha256_bytes(attestation_bytes),
        evidence_digests={
            evidence_id: sha256_bytes(payloads[evidence_id])
            for evidence_id in RELEASE_EVIDENCE_IDS
        },
        evaluated_at=attestation["evaluatedAt"],
        evaluator=evaluator,
        builder_digest=expected_distribution["builder"]["digest"],
        authority_issued=False,
        attestation=attestation,
    )
