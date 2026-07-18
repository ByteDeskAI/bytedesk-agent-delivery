#!/usr/bin/env python3
"""Validate the closed downstream-port IDL and its conformance catalog."""

from __future__ import annotations

import argparse
import base64
import binascii
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import urldefrag

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable
import rfc8785

from renderer_authority import renderer_selection_preimage
from oci_graph import ARTIFACT_TYPE_ROLES
from generate_downstream_port_types import (
    EXACT_ARRAY_SCHEMA_REFS,
    build_problem_details_schema,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PORT_ROOT = REPOSITORY_ROOT / "contracts" / "ports" / "v1"

REGISTRY_PATH = PORT_ROOT / "port-registry.json"
PROBLEM_PATH = PORT_ROOT / "problem-catalog.json"
ACTION_PATH = PORT_ROOT / "action-catalog.json"
PROFILE_PATH = PORT_ROOT / "protocol-profiles.json"
CASE_PATH = PORT_ROOT / "conformance-cases.json"
TYPE_CATALOG_PATH = PORT_ROOT / "type-catalog.json"
CONTRACT_FIXTURE_PATH = PORT_ROOT / "contract-fixtures.json"
COVERAGE_MATRIX_PATH = (
    REPOSITORY_ROOT / "docs" / "architecture" / "downstream-contract-coverage.md"
)
ACTION_SCHEMA_PATH = REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / "action.schema.json"
PROBLEM_SCHEMA_PATH = (
    REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / "problem-details.schema.json"
)
RENDERER_RELEASE_PATH = (
    REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / "renderer-release.schema.json"
)
EVENT_TYPES_PATH = REPOSITORY_ROOT / "contracts" / "events" / "v1" / "event-types.json"
HOST_JOURNAL_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "schemas"
    / "v1"
    / "host-switch-journal-entry.schema.json"
)
SIGNING_REQUEST_SCHEMA_PATH = (
    REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / "signing-request.schema.json"
)
SIGNING_RESULT_SCHEMA_PATH = (
    REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / "signing-result.schema.json"
)
EXTERNAL_INPUT_LOCK_SCHEMA_PATH = (
    REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / "external-input-lock.schema.json"
)
RENDERER_SELECTION_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "renderer-selection__native-amd64.json"
)
RENDERER_EXECUTION_RECEIPT_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "renderer-execution-receipt__native-amd64.json"
)
PRIVATE_COMPILATION_INPUT_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "private-compilation-input__complete-lock.json"
)
CONSUMER_AUTHORITY_COMPILE_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "consumer-authority__compile.json"
)

PORT_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
PORT_SCHEMA_PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/ports/"
TYPE_CATALOG_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/port-type-catalog/1.0.0"
)
CONTRACT_FIXTURE_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/port-contract-fixtures/1.0.0"
)


REQUIRED_PORT_OPERATIONS: dict[str, tuple[str, ...]] = {
    "bytedesk.port.catalog/1": (
        "list-catalog-releases",
        "resolve-catalog-release",
        "fetch-catalog-object",
        "publish-catalog-release",
    ),
    "bytedesk.port.scm/1": (
        "receive-webhook",
        "fetch-commit",
        "scan-repository",
        "publish-candidate-signal",
    ),
    "bytedesk.port.agent-spec-validator/1": ("validate-agent-spec",),
    "bytedesk.port.renderer-strategy/1": (
        "describe-capabilities",
        "select-qualification-renderer",
        "select-renderer",
        "render",
    ),
    "bytedesk.port.renderer-adapter/1": ("render", "validate-output"),
    "bytedesk.port.renderer-sandbox/1": (
        "execute-renderer",
        "execute-qualification",
    ),
    "bytedesk.port.wayflow-compatibility/1": ("verify-native-output",),
    "bytedesk.port.oci-registry/1": (
        "head-artifact",
        "pull-artifact",
        "push-artifact",
        "list-referrers",
        "verify-artifact-graph",
    ),
    "bytedesk.port.kms-signing/1": (
        "sign-digest",
        "resolve-signing-request",
        "verify-signature",
    ),
    "bytedesk.port.supply-chain-evidence/1": (
        "generate-sbom",
        "generate-provenance",
        "scan-malware",
        "scan-secrets",
        "attest-scan-completeness",
        "scan-vulnerabilities",
        "evaluate-licenses",
    ),
    "bytedesk.port.evidence-archive/1": (
        "put-evidence",
        "read-evidence",
        "advance-archive-root",
        "restore-evidence",
    ),
    "bytedesk.port.consumer-authority-approval/1": (
        "resolve-authority-snapshot",
        "resolve-skill-approval",
        "verify-private-authority",
    ),
    "bytedesk.port.consumer-projection/1": (
        "resolve-consumer-subject",
        "project-consumer-receipt",
    ),
    "bytedesk.port.desired-state-store/1": (
        "read-target-state",
        "watch-target-state",
        "compare-and-swap-target-state",
        "resolve-idempotency",
        "read-target-history",
        "migrate-target-state",
    ),
    "bytedesk.port.control-plane-api-events/1": (
        "submit-command",
        "read-resource",
        "append-host-observation",
        "append-capability-evidence",
        "subscribe-events",
        "resynchronize-events",
    ),
    "bytedesk.port.promotion-coordinator/1": (
        "start-rollout",
        "evaluate-evidence",
        "authorize-activation",
        "commit-promotion",
        "plan-forward-recovery",
        "cancel-rollout",
    ),
    "bytedesk.port.private-compiler/1": (
        "compile-private-deployment",
        "resolve-compile-attempt",
    ),
    "bytedesk.port.host-reconciler/1": (
        "stage-candidate",
        "preflight-candidate",
        "activate-candidate",
        "readback-active-state",
        "append-host-observation",
        "recover-attempt-journal",
        "cleanup-candidate",
    ),
    "bytedesk.port.capability-verifier/1": (
        "dispatch-capability-check",
        "verify-capability-result",
    ),
    "bytedesk.port.cli-automation/1": (
        "execute-local",
        "execute-remote",
        "watch-action",
        "verify-receipt",
    ),
    "bytedesk.port.region-fence/1": (
        "prepare-region-fence",
        "activate-recovery-region",
        "verify-region-fence",
    ),
    "bytedesk.port.release-status-head/1": (
        "append-release-status",
        "resolve-append-attempt",
        "resolve-status-head",
    ),
    "bytedesk.port.trust-policy-provider/1": (
        "activate-pin-set",
        "resolve-pin-set",
    ),
    "bytedesk.port.release-qualification-finalizer/1": (
        "finalize-release-qualification",
    ),
    "bytedesk.port.public-render-finalizer/1": ("finalize-public-render",),
    "bytedesk.port.public-render-publisher/1": ("publish-public-render",),
}

REQUIRED_TASKS = {f"AD-{number:02d}" for number in range(2, 19)}
REQUIRED_TASK_SUITES = {
    "downstream.marketplace.v1",
    "downstream.reference-catalog.v1",
    "downstream.renderer-contract.v1",
    "downstream.native-renderer.v1",
    "downstream.hermes-renderer.v1",
    "downstream.openclaw-renderer.v1",
    "downstream.oci-registry.v1",
    "downstream.signing-evidence.v1",
    "downstream.consumer-state.v1",
    "downstream.api-events.v1",
    "downstream.scm-intake.v1",
    "downstream.promotion.v1",
    "downstream.private-compiler.v1",
    "downstream.host-reconciler.v1",
    "downstream.capability-verifier.v1",
    "downstream.cli-automation.v1",
    "downstream.bytedesk-hermes.v1",
    "downstream.bytedesk-openclaw.v1",
    "downstream.certification.v1",
}

ALLOWED_TASK_SUITES_BY_OWNER: dict[str, set[str]] = {
    "AD-02": {"downstream.marketplace.v1"},
    "AD-03": {"downstream.reference-catalog.v1"},
    "AD-04": {"downstream.renderer-contract.v1", "downstream.native-renderer.v1"},
    "AD-05": {"downstream.hermes-renderer.v1"},
    "AD-06": {"downstream.openclaw-renderer.v1"},
    "AD-07": {"downstream.oci-registry.v1"},
    "AD-08": {"downstream.signing-evidence.v1"},
    "AD-09": {"downstream.consumer-state.v1"},
    "AD-10": {"downstream.api-events.v1"},
    "AD-11": {"downstream.scm-intake.v1"},
    "AD-12": {"downstream.promotion.v1"},
    "AD-13": {"downstream.private-compiler.v1"},
    "AD-14": {"downstream.host-reconciler.v1", "downstream.capability-verifier.v1"},
    "AD-15": {"downstream.cli-automation.v1"},
    "AD-16": {"downstream.bytedesk-hermes.v1"},
    "AD-17": {"downstream.bytedesk-openclaw.v1"},
    "AD-18": {"downstream.certification.v1"},
}

EXACT_TASK_SUITE_BY_CASE = {
    "STATUS-APPEND-001-response-lost-after-publication": "downstream.renderer-contract.v1",
    "STATUS-APPEND-002-pending-reservation-does-not-retry": "downstream.renderer-contract.v1",
    "STATUS-APPEND-003-stable-not-found-allows-same-retry": "downstream.renderer-contract.v1",
    "STATUS-APPEND-004-resolver-request-digest-collision": "downstream.renderer-contract.v1",
    "STATUS-HEAD-001-fresh-authenticated-resolution": "downstream.renderer-contract.v1",
    "STATUS-HEAD-002-rollback-or-fork-denied": "downstream.renderer-contract.v1",
    "QUAL-SELECT-001-exact-qualification-renderer": "downstream.renderer-contract.v1",
    "QUAL-FINAL-001-complete-exact-matrix": "downstream.renderer-contract.v1",
    "QUAL-FINAL-002-matrix-or-authority-substitution": "downstream.renderer-contract.v1",
    "PUBLIC-FINAL-001-tenant-free-finalization": "downstream.renderer-contract.v1",
    "PUBLIC-FINAL-002-status-or-private-input-denied": "downstream.renderer-contract.v1",
    "TRUST-PIN-001-activate-and-read-back": "downstream.signing-evidence.v1",
    "TRUST-PIN-002-activation-response-lost": "downstream.signing-evidence.v1",
    "TRUST-PIN-003-current-resolution": "downstream.signing-evidence.v1",
    "TRUST-PIN-004-rollback-or-equivocation-denied": "downstream.signing-evidence.v1",
    "PUBLIC-PUBLISH-001-fresh-authorized-publication": "downstream.oci-registry.v1",
    "PUBLIC-PUBLISH-002-payload-or-authorization-substitution": "downstream.oci-registry.v1",
    "PUBLIC-PUBLISH-003-response-lost-after-commit": "downstream.oci-registry.v1",
    "PROMOTION-RECEIPT-001-complete-subject-sets": "downstream.promotion.v1",
    "PROMOTION-RECEIPT-002-complete-receipt-set": "downstream.promotion.v1",
}

REQUIRED_PROFILE_KEYS: dict[str, set[str]] = {
    "bytedesk.worker-framing/1": {
        "framing",
        "payloadEncoding",
        "oneRequestPerProcess",
        "maxRequestBytes",
        "maxResponseBytes",
        "maxDiagnosticsBytes",
        "deadlineSource",
        "workerStdin",
        "workerStdout",
        "workerStderr",
        "launcherContainerStdout",
        "launcherContainerStderr",
        "contentStreamIsolation",
        "diagnosticHandling",
        "inheritedFileDescriptors",
        "network",
        "secrets",
        "filesystem",
        "failureMapping",
    },
    "bytedesk.oci-archive-layout/1": {
        "referenceAuthority",
        "tagAndChannelUse",
        "manifestEncoding",
        "layerOrder",
        "publicArtifactRule",
        "privateArtifactRule",
        "archiveFormat",
        "archiveMetadata",
        "pathProfile",
        "rejectLinksAndSpecialFiles",
        "rejectDuplicatePortablePaths",
        "maximumExpandedBytes",
        "maximumMemberBytes",
        "maximumMembers",
        "archiveRootMutation",
        "restoreRule",
    },
    "bytedesk.supply-chain-pins/1": {
        "actionReferences",
        "containerReferences",
        "languageDependencies",
        "schemaReferences",
        "trustReferences",
        "rendererReferences",
        "scannerReferences",
        "sourceReferences",
        "forbiddenSelectors",
        "unavailableBehavior",
        "evidence",
    },
    "bytedesk.renderer-contract/1": {
        "promisedSchemaIds",
        "selection",
        "forbiddenSelection",
        "invocation",
        "inputIdentity",
        "outputIdentity",
        "executeArtifactContent",
        "normalization",
        "publicRender",
        "privateRender",
        "wayflowAuthority",
    },
    "bytedesk.desired-state-store/1": {
        "selectedStoreCardinality",
        "supportedStoreClasses",
        "soleLogicalWriter",
        "nonWriters",
        "read",
        "watch",
        "createPrecondition",
        "updatePrecondition",
        "idempotency",
        "migration",
        "regionFencing",
    },
    "bytedesk.api-events/1": {
        "httpContract",
        "eventContract",
        "cloudEventsVersion",
        "delivery",
        "ordering",
        "authority",
        "transports",
        "sse",
        "eventTypes",
        "unknownSchema",
        "sequenceGap",
        "deduplication",
        "mutationPreconditions",
        "problemContract",
    },
    "bytedesk.promotion-coordinator/1": {
        "soleWriter",
        "isolatedCandidateOrdering",
        "guardedInPlaceOrdering",
        "managedCommitPoint",
        "externalCommitPoints",
        "cancellation",
        "fences",
        "crashRecovery",
        "recovery",
    },
    "bytedesk.host-switch-journal/1": {
        "journalIdentity",
        "phases",
        "appendRule",
        "durability",
        "switchPrimitive",
        "switchIntent",
        "switchMarker",
        "generationFence",
        "crashDisposition",
        "cleanup",
        "executionBoundary",
    },
    "bytedesk.capability-verification/1": {
        "dispatchActor",
        "verificationActor",
        "forbiddenDispatchActors",
        "bindingFields",
        "chainBindings",
        "outcomeDerivation",
        "outcomes",
        "denialProof",
        "notDenial",
        "freshness",
        "isolatedCandidateSequence",
        "guardedInPlaceSequence",
        "evidenceSeparation",
        "failureMapping",
    },
    "bytedesk.cli-automation/1": {
        "executable",
        "commandTree",
        "outputModes",
        "jsonEncoding",
        "stdout",
        "stderr",
        "secretHandling",
        "mutationConfirmation",
        "asyncProgress",
        "exitCodes",
        "compatibility",
    },
    "bytedesk.external-input-lock/1": {
        "artifactProfile",
        "schemaContract",
        "requiredFields",
        "roles",
        "repository",
        "commit",
        "treeDigest",
        "paths",
        "validators",
        "compatibilityEvidenceOnly",
        "fetch",
        "verification",
        "forbiddenSelectors",
        "unavailableBehavior",
        "authorityBoundary",
    },
    "bytedesk.oci-artifact-profile/1": {
        "manifest",
        "index",
        "config",
        "artifactTypes",
        "layers",
        "subject",
        "referrers",
        "crossRepositoryEdges",
        "graphBounds",
        "publication",
        "verification",
        "archive",
    },
    "bytedesk.signing-evidence-profile/1": {
        "cryptographicProfile",
        "kmsProfile",
        "purposeProfiles",
        "isolation",
        "signingRequest",
        "signingResult",
        "cosign",
        "sbom",
        "provenance",
        "vulnerabilityScan",
        "malwareScan",
        "secretScan",
        "scanCompleteness",
        "licenseEvaluation",
        "evidenceAttachment",
        "rotationAndRevocation",
        "failureBehavior",
    },
}

REQUIRED_CRITICAL_CASES = {
    "LOCK-001-floating-selector-rejected",
    "OCI-002-push-response-lost",
    "STATE-001-omitted-or-partial-cas",
    "STATE-003-cas-response-lost",
    "API-001-event-gap-forces-resync",
    "COORD-002-crash-after-switch-before-cas",
    "HOST-001-crash-before-switch-intent",
    "HOST-002-crash-after-intent-before-switch",
    "HOST-003-crash-during-switch-indeterminate",
    "HOST-004-crash-after-switch-before-marker",
    "CAP-001-transport-failure-is-not-denial",
    "CAP-002-denial-requires-exact-proof",
    "CAP-003-host-cannot-dispatch",
    "CAP-004-exact-binding-mismatch",
    "CLI-001-wait-timeout-does-not-cancel",
    "REGION-001-source-not-fenced",
    "REGION-002-response-lost-after-epoch",
    "OCI-003-empty-config-digest-mismatch",
    "OCI-004-layer-profile-drift",
    "OCI-005-cross-repository-subject",
    "SIGN-003-key-algorithm-substitution",
    "SIGN-004-keyless-contract-bundle-rejected-by-kms-port",
    "EVIDENCE-001-incomplete-required-sbom",
    "EVIDENCE-002-provenance-builder-mismatch",
    "EVIDENCE-003-unpinned-scan-snapshot",
    "EVIDENCE-004-scan-coverage-incomplete",
    "EVIDENCE-005-license-policy-unavailable",
    "RENDER-003-container-stream-content-denied",
    "RENDER-004-target-platform-required",
    "RENDER-005-unsupported-target-platform",
    "RENDER-006-selection-platform-mismatch",
    "RENDER-007-renderer-release-substitution",
    "RENDER-008-executable-distribution-swap",
    "RENDER-009-compiled-allowlist-swap",
    "RENDER-010-ambient-architecture-change",
    "RENDER-011-execution-readback-mismatch",
    "RENDER-012-release-allowlist-product-selection-mismatch",
    "RENDER-013-qualification-selection-production-denied",
    "RENDER-014-qualification-attempt-authentication-mismatch",
    "AUTH-003-private-input-digest-mismatch",
    "AUTH-004-denied-private-authority-has-no-success-result",
    "COMPILE-003-changed-approval-denied",
    "COMPILE-004-duplicate-or-reordered-approvals-denied",
    "COMPILE-005-cross-consumer-or-target-denied",
    "COMPILE-006-contract-bundle-substitution-denied",
    "COMPILE-007-policy-drift-denied",
    "COMPILE-008-renderer-selection-substitution-denied",
    "COMPILE-009-expanded-input-idempotency-collision",
    "COMPILE-010-request-digest-mismatch-denied",
}

CLI_EXIT_CODES = set(range(2, 14))
SIDE_EFFECT_STATE_ORDER = (
    "none",
    "not-committed",
    "committed-unchanged",
    "commit-unknown",
)
SIDE_EFFECT_STATES = set(SIDE_EFFECT_STATE_ORDER)
NO_SIDE_EFFECT_FAILURE_SEMANTICS = {
    "fail-closed-no-side-effect",
    "fail-closed-read-only",
}
TERMINAL_FACT_PROBLEMS = {
    "action_cancelled",
    "action_terminal_failed",
}
RESULT_CONTRACT_CLASSES = {"artifact", "resource"}
EXPECTED_ACTION_RESULT_CLASSES = {
    "validate": "resource",
    "render": "artifact",
    "package": "artifact",
    "publish": "resource",
    "import": "resource",
    "compile": "artifact",
    "sign": "artifact",
    "promote": "resource",
    "recover": "resource",
    "withdraw": "resource",
    "retire": "resource",
    "reconcile": "resource",
    "archive": "resource",
    "restore": "artifact",
    "region_failover": "resource",
}

UNPINNED_SELECTOR_PATTERNS = (
    re.compile(r"\blatest\b", re.IGNORECASE),
    re.compile(r"\bcurrent\s+(?:stable|upstream|version|release)\b", re.IGNORECASE),
    re.compile(r"\bnewest\s+available\b", re.IGNORECASE),
    re.compile(r"(?<![-\w])HEAD(?![-\w])"),
    re.compile(r"\b(?:main|master)\s+branch\b", re.IGNORECASE),
    re.compile(r"\bfloating\s+(?:tag|version|range|dependency)\b", re.IGNORECASE),
    re.compile(
        r"\bunversioned\s+(?:dependency|tool|image|action|renderer|validator|plugin)\b",
        re.IGNORECASE,
    ),
)


class ContractValidationError(RuntimeError):
    """Raised when a downstream-port contract invariant fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractValidationError(message)


def operation_error_states(operation: dict[str, Any]) -> dict[str, str]:
    """Return the operation's closed stable-code to side-effect-state mapping."""

    return {
        mapping["code"]: mapping["sideEffectState"]
        for mapping in operation["errors"]
    }


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ContractValidationError(f"non-finite JSON number is forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required JSON file is missing: {path.relative_to(REPOSITORY_ROOT)}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractValidationError(f"cannot load strict JSON {path}: {error}") from error
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    require(
        actual == expected,
        f"{label} keys differ; missing={sorted(expected - actual)} extra={sorted(actual - expected)}",
    )


def unique_strings(values: Any, label: str, *, nonempty: bool = True) -> list[str]:
    require(isinstance(values, list), f"{label} must be an array")
    require(not nonempty or bool(values), f"{label} must not be empty")
    require(all(isinstance(value, str) and value for value in values), f"{label} has invalid string")
    require(len(values) == len(set(values)), f"{label} contains duplicates")
    return values


def canonical_digest(value: Any) -> str:
    try:
        payload = rfc8785.dumps(value)
    except (ValueError, TypeError) as error:
        raise ContractValidationError(f"value is not RFC 8785 canonicalizable: {error}") from error
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def validate_repository_paths(paths: Any, label: str) -> None:
    for relative in unique_strings(paths, label):
        path = Path(relative)
        require(not path.is_absolute(), f"{label} must contain repository-relative paths: {relative}")
        require(".." not in path.parts, f"{label} contains parent traversal: {relative}")
        require((REPOSITORY_ROOT / path).exists(), f"{label} references missing path: {relative}")


def validate_registry(
    registry: dict[str, Any],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, set[str]]]:
    exact_keys(
        registry,
        {
            "$schema",
            "profile",
            "version",
            "compatibility",
            "typeCatalog",
            "contractFixtures",
            "ports",
        },
        "port registry root",
    )
    require(
        registry["$schema"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/downstream-port-registry/1.0.0",
        "port registry schema binding drift",
    )
    require(registry["profile"] == "bytedesk.downstream-port-registry/1", "wrong port registry profile")
    require(registry["version"] == 1, "wrong port registry version")
    require(isinstance(registry["compatibility"], str) and registry["compatibility"], "missing compatibility rule")
    require(
        registry["typeCatalog"] == "contracts/ports/v1/type-catalog.json",
        "port registry type-catalog binding drift",
    )
    require(
        registry["contractFixtures"]
        == "contracts/ports/v1/contract-fixtures.json",
        "port registry contract-fixture binding drift",
    )
    require(isinstance(registry["ports"], list), "ports must be an array")

    port_keys = {
        "portId",
        "kind",
        "owner",
        "tasks",
        "suite",
        "contractPaths",
        "promisedSchemas",
        "protocolProfiles",
        "operations",
    }
    operation_keys = {
        "operationId",
        "requestContract",
        "resultContract",
        "requestFields",
        "resultFields",
        "errors",
        "idempotency",
        "failureSemantics",
        "commitUncertainty",
        "authentication",
        "authorization",
        "compatibility",
        "owner",
        "suite",
    }
    field_keys = {"name", "type", "required", "schemaRef", "valueType"}
    ports_by_id: dict[str, dict[str, Any]] = {}
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    referenced_error_states: dict[str, set[str]] = {}
    covered_tasks: set[str] = set()
    value_types: set[str] = set()

    for index, port in enumerate(registry["ports"]):
        require(isinstance(port, dict), f"port[{index}] must be an object")
        exact_keys(port, port_keys, f"port[{index}]")
        port_id = port["portId"]
        require(isinstance(port_id, str) and re.fullmatch(r"bytedesk\.port\.[a-z0-9-]+/1", port_id), f"invalid port ID: {port_id!r}")
        require(port_id not in ports_by_id, f"duplicate port ID: {port_id}")
        ports_by_id[port_id] = port
        require(port["kind"] in {"adapter", "strategy", "protocol", "api", "cli"}, f"invalid port kind: {port_id}")
        require(isinstance(port["owner"], str) and port["owner"], f"missing owner: {port_id}")
        require(isinstance(port["suite"], str) and re.fullmatch(r"downstream\.[a-z0-9.-]+", port["suite"]), f"invalid suite: {port_id}")
        tasks = unique_strings(port["tasks"], f"{port_id}.tasks")
        require(set(tasks) <= REQUIRED_TASKS, f"{port_id} references task outside AD-02..AD-18")
        covered_tasks.update(tasks)
        validate_repository_paths(port["contractPaths"], f"{port_id}.contractPaths")
        unique_strings(port["promisedSchemas"], f"{port_id}.promisedSchemas", nonempty=False)
        protocol_profiles = unique_strings(
            port["protocolProfiles"],
            f"{port_id}.protocolProfiles",
            nonempty=False,
        )
        require(
            all(
                re.fullmatch(r"bytedesk\.[a-z0-9-]+/1", profile_id)
                for profile_id in protocol_profiles
            ),
            f"{port_id}.protocolProfiles contains a malformed profile ID",
        )
        require(isinstance(port["operations"], list) and port["operations"], f"{port_id} has no operations")

        for op_index, operation in enumerate(port["operations"]):
            label = f"{port_id}.operations[{op_index}]"
            require(isinstance(operation, dict), f"{label} must be an object")
            exact_keys(operation, operation_keys, label)
            operation_id = operation["operationId"]
            require(isinstance(operation_id, str) and re.fullmatch(r"[a-z][a-z0-9-]*", operation_id), f"invalid operation ID: {port_id}/{operation_id!r}")
            key = (port_id, operation_id)
            require(key not in operations, f"duplicate operation: {port_id}/{operation_id}")
            operations[key] = operation
            for contract_key in ("requestContract", "resultContract"):
                require(
                    isinstance(operation[contract_key], str)
                    and re.fullmatch(r"bytedesk\.port\.[a-z0-9-]+\.[a-z0-9-]+\.(?:request|result)/1", operation[contract_key]),
                    f"invalid {contract_key}: {port_id}/{operation_id}",
                )
            contract_prefix = f"{port_id.removesuffix('/1')}.{operation_id}"
            require(
                operation["requestContract"] == f"{contract_prefix}.request/1"
                and operation["resultContract"] == f"{contract_prefix}.result/1",
                f"operation contract IDs do not derive from port and operation IDs: "
                f"{port_id}/{operation_id}",
            )
            for fields_key in ("requestFields", "resultFields"):
                fields = operation[fields_key]
                require(isinstance(fields, list) and fields, f"{label}.{fields_key} must not be empty")
                names: list[str] = []
                for field_index, field in enumerate(fields):
                    field_label = f"{label}.{fields_key}[{field_index}]"
                    require(isinstance(field, dict), f"{field_label} must be an object")
                    exact_keys(field, field_keys, field_label)
                    require(isinstance(field["name"], str) and re.fullmatch(r"[a-z][A-Za-z0-9]*", field["name"]), f"invalid field name: {field_label}")
                    require(isinstance(field["type"], str) and field["type"], f"invalid field type: {field_label}")
                    require(type(field["required"]) is bool, f"required must be boolean: {field_label}")
                    require(isinstance(field["schemaRef"], str) and field["schemaRef"], f"missing schemaRef: {field_label}")
                    require(
                        isinstance(field["valueType"], str)
                        and re.fullmatch(
                            r"bytedesk\.port-field\.[a-z0-9.-]+/(?:1)",
                            field["valueType"],
                        ),
                        f"invalid field value type: {field_label}",
                    )
                    require(
                        field["valueType"] not in value_types,
                        f"field value type is not unique: {field['valueType']}",
                    )
                    value_types.add(field["valueType"])
                    if field["schemaRef"].startswith("contracts/"):
                        require((REPOSITORY_ROOT / field["schemaRef"]).is_file(), f"missing field schemaRef path: {field['schemaRef']}")
                    names.append(field["name"])
                require(len(names) == len(set(names)), f"duplicate field name: {label}.{fields_key}")
            error_mappings = operation["errors"]
            require(
                isinstance(error_mappings, list) and error_mappings,
                f"{label}.errors must be a nonempty array",
            )
            error_codes: set[str] = set()
            for error_index, mapping in enumerate(error_mappings):
                mapping_label = f"{label}.errors[{error_index}]"
                require(isinstance(mapping, dict), f"{mapping_label} must be an object")
                exact_keys(mapping, {"code", "sideEffectState"}, mapping_label)
                code = mapping["code"]
                state = mapping["sideEffectState"]
                require(
                    isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]*", code),
                    f"invalid problem code: {mapping_label}",
                )
                require(code not in error_codes, f"duplicate operation problem code: {label}/{code}")
                require(state in SIDE_EFFECT_STATES, f"invalid operation side-effect state: {label}/{code}")
                if operation["failureSemantics"] in NO_SIDE_EFFECT_FAILURE_SEMANTICS:
                    require(
                        state == "none",
                        f"read-only/no-side-effect failure must map to none: {label}/{code}",
                    )
                else:
                    require(
                        state != "none",
                        f"mutating operation failure must report its commit conclusion: {label}/{code}",
                    )
                if state == "commit-unknown":
                    require(
                        operation["commitUncertainty"] != "not-applicable",
                        f"commit-unknown requires an exact resolution procedure: {label}/{code}",
                    )
                if state == "committed-unchanged":
                    require(
                        code in TERMINAL_FACT_PROBLEMS,
                        f"committed-unchanged is reserved for durable terminal facts: {label}/{code}",
                    )
                error_codes.add(code)
                referenced_error_states.setdefault(code, set()).add(state)
            for text_key in (
                "idempotency",
                "failureSemantics",
                "commitUncertainty",
                "authentication",
                "authorization",
                "compatibility",
            ):
                require(isinstance(operation[text_key], str) and operation[text_key], f"missing {text_key}: {label}")
            require(operation["owner"] == port["owner"], f"operation owner drift: {port_id}/{operation_id}")
            require(operation["suite"] == port["suite"], f"operation suite drift: {port_id}/{operation_id}")

    require(set(ports_by_id) == set(REQUIRED_PORT_OPERATIONS), "required port ID set differs from registry")
    for port_id, required_operations in REQUIRED_PORT_OPERATIONS.items():
        actual = tuple(operation["operationId"] for operation in ports_by_id[port_id]["operations"])
        require(actual == required_operations, f"closed operation order/set differs for {port_id}: {actual}")
    kms_signing_request = next(
        field
        for field in operations[("bytedesk.port.kms-signing/1", "sign-digest")][
            "requestFields"
        ]
        if field["name"] == "signingRequest"
    )
    require(
        kms_signing_request["schemaRef"] == "kms-signing-request",
        "KMS sign-digest does not require the KMS-only signing-request refinement",
    )
    require(covered_tasks == REQUIRED_TASKS, f"port task coverage differs: {sorted(covered_tasks)}")
    return operations, referenced_error_states


def iter_schema_references(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str):
                yield child
            else:
                yield from iter_schema_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_schema_references(child)


def all_validation_errors(error: Any) -> Iterable[Any]:
    yield error
    for child in error.context:
        yield from all_validation_errors(child)


def validation_errors(
    schema: dict[str, Any], instance: Any, resource_registry: Registry
) -> list[Any]:
    return sorted(
        Draft202012Validator(
            schema,
            registry=resource_registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(instance),
        key=lambda error: (list(error.absolute_path), error.validator, error.message),
    )


def resolve_json_pointer(document: Any, pointer: str, label: str) -> Any:
    require(isinstance(pointer, str), f"{label} JSON pointer must be a string")
    if pointer == "":
        return document
    require(pointer.startswith("/"), f"{label} JSON pointer must be absolute")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            require(token in current, f"{label} JSON pointer is unresolved: {pointer}")
            current = current[token]
        elif isinstance(current, list):
            require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None, f"{label} has invalid array index")
            index = int(token)
            require(index < len(current), f"{label} array index is out of range")
            current = current[index]
        else:
            raise ContractValidationError(f"{label} traverses a scalar: {pointer}")
    return current


def port_kebab_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", value).replace("_", "-").lower()


def expected_field_value_type(
    port_id: str, operation_id: str, direction: str, field_name: str
) -> str:
    port_name = port_id.removeprefix("bytedesk.port.").removesuffix("/1")
    return (
        f"bytedesk.port-field.{port_name}.{operation_id}.{direction}."
        f"{port_kebab_case(field_name)}/1"
    )


def expected_port_type_schema_id(type_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", type_id.lower()).strip("-")
    require(bool(slug), f"cannot derive field schema ID: {type_id}")
    return f"{PORT_SCHEMA_PREFIX}types/{slug}/1.0.0"


def expected_contract_schema_id(contract_id: str) -> str:
    name = contract_id.removeprefix("bytedesk.port.").removesuffix("/1")
    return f"{PORT_SCHEMA_PREFIX}contracts/{name.replace('.', '/')}/1.0.0"


def expected_contract_schema(
    contract_id: str,
    fields: list[dict[str, Any]],
    field_type_schema_ids: dict[str, str],
    variants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    schema = {
        "$schema": PORT_SCHEMA_DIALECT,
        "$id": expected_contract_schema_id(contract_id),
        "title": contract_id,
        "type": "object",
        "required": [field["name"] for field in fields if field["required"]],
        "properties": {
            field["name"]: {"$ref": field_type_schema_ids[field["valueType"]]}
            for field in fields
        },
        "additionalProperties": False,
        "unevaluatedProperties": False,
    }
    if variants is not None:
        schema["oneOf"] = variants
    return schema


def require_closed_inline_objects(value: Any, label: str) -> None:
    if isinstance(value, dict):
        require(
            value.get("additionalProperties") is not True,
            f"{label} explicitly opens additional properties",
        )
        require(
            value.get("unevaluatedProperties") is not True,
            f"{label} explicitly opens unevaluated properties",
        )
        node_type = value.get("type")
        if node_type == "array":
            maximum = value.get("maxItems")
            require(
                isinstance(maximum, int) and not isinstance(maximum, bool)
                and 0 <= maximum <= 100000,
                f"{label} has an unbounded direct array",
            )
        elif node_type == "string" and "const" not in value and not (
            isinstance(value.get("enum"), list) and value["enum"]
        ):
            maximum = value.get("maxLength")
            encoded_bytes = value.get("contentEncoding") == "base64url-no-padding"
            maximum_allowed = 5592406 if encoded_bytes else 4194304
            require(
                isinstance(maximum, int) and not isinstance(maximum, bool)
                and 0 <= maximum <= maximum_allowed,
                f"{label} has an unbounded direct string",
            )
            if encoded_bytes:
                require(
                    value.get("pattern")
                    == r"^(?:[A-Za-z0-9_-]{4})*(?:[A-Za-z0-9_-]{2,3})?$",
                    f"{label} has a noncanonical encoded-byte grammar",
                )
        elif node_type == "integer" and "const" not in value and not (
            isinstance(value.get("enum"), list) and value["enum"]
        ):
            minimum = value.get("minimum")
            maximum = value.get("maximum")
            require(
                isinstance(minimum, int) and not isinstance(minimum, bool)
                and isinstance(maximum, int) and not isinstance(maximum, bool)
                and -9007199254740991 <= minimum <= maximum <= 9007199254740991,
                f"{label} has an unbounded direct integer",
            )
        elif node_type == "object":
            require(value.get("additionalProperties") is False, f"{label} has an open object")
            require(value.get("unevaluatedProperties") is False, f"{label} lacks closed unevaluated properties")
        for child in value.values():
            require_closed_inline_objects(child, label)
    elif isinstance(value, list):
        for child in value:
            require_closed_inline_objects(child, label)


def validate_expected_keyword(errors: list[Any], expected: Any, label: str) -> None:
    require(isinstance(expected, str) and expected, f"{label} expected keyword is invalid")
    keywords = {
        nested.validator
        for error in errors
        for nested in all_validation_errors(error)
        if isinstance(nested.validator, str)
    }
    require(expected in keywords, f"{label} expected keyword {expected!r} not observed; got {sorted(keywords)}")


def decode_canonical_bounded_base64url(value: Any, label: str) -> bytes:
    require(isinstance(value, str), f"{label} must be a base64url string")
    require(
        len(value) <= 5592406,
        f"{label} exceeds the 4 MiB decoded-byte representation bound",
    )
    require(
        re.fullmatch(r"(?:[A-Za-z0-9_-]{4})*(?:[A-Za-z0-9_-]{2,3})?", value)
        is not None,
        f"{label} is not unpadded base64url with a possible 2/3-character tail",
    )
    try:
        decoded = base64.urlsafe_b64decode(
            value + "=" * ((4 - len(value) % 4) % 4)
        )
    except (binascii.Error, ValueError) as error:
        raise ContractValidationError(f"{label} cannot be decoded: {error}") from error
    require(len(decoded) <= 4194304, f"{label} decodes beyond 4 MiB")
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    require(canonical == value, f"{label} has non-zero unused tail bits")
    return decoded


def validate_bounded_bytes_profile(
    base_types: dict[str, dict[str, Any]], resource_registry: Registry
) -> int:
    expected_pattern = r"^(?:[A-Za-z0-9_-]{4})*(?:[A-Za-z0-9_-]{2,3})?$"
    encoded_nodes: list[dict[str, Any]] = []

    def collect_encoded_nodes(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("contentEncoding") == "base64url-no-padding":
                encoded_nodes.append(value)
            for child in value.values():
                collect_encoded_nodes(child)
        elif isinstance(value, list):
            for child in value:
                collect_encoded_nodes(child)

    for entry in base_types.values():
        collect_encoded_nodes(entry["schema"])
    require(
        len(encoded_nodes) == 2,
        "base64url-no-padding schema occurrence count drift",
    )
    for bytes_schema in encoded_nodes:
        require(bytes_schema.get("type") == "string", "bounded bytes are not strings")
        require(bytes_schema.get("minLength") == 0, "bounded-byte minimum drift")
        require(bytes_schema.get("pattern") == expected_pattern, "bounded-byte grammar drift")
        require(bytes_schema.get("maxLength") == 5592406, "bounded-byte encoded ceiling drift")

    bytes_schema = base_types["primitive:bounded-bytes"]["schema"]
    require(decode_canonical_bounded_base64url("AA", "canonical byte probe") == b"\x00", "canonical byte decode drift")
    decode_canonical_bounded_base64url(
        base_types["primitive:bounded-bytes"]["fixture"]["valid"],
        "primitive bounded-byte fixture",
    )
    oci_blob = base_types["bytedesk.port.oci-blob-stream/1"]
    oci_fixture = oci_blob["fixture"]["valid"]
    require(0 < oci_fixture["size"] <= 67108864, "OCI blob aggregate size bound drift")
    oci_parts: list[bytes] = []
    expected_offset = 0
    for expected_index, chunk in enumerate(oci_fixture["chunks"]):
        require(chunk["index"] == expected_index, "OCI blob chunk index/order drift")
        require(chunk["offset"] == expected_offset, "OCI blob chunk offset gap or overlap")
        chunk_bytes = decode_canonical_bounded_base64url(
            chunk["contentBase64url"], f"OCI blob chunk {expected_index}"
        )
        require(0 < len(chunk_bytes) <= 4194304, "OCI blob chunk decoded bound drift")
        require(len(chunk_bytes) == chunk["size"], "OCI blob chunk size drift")
        require(
            chunk["digest"] == f"sha256:{hashlib.sha256(chunk_bytes).hexdigest()}",
            "OCI blob chunk digest drift",
        )
        oci_parts.append(chunk_bytes)
        expected_offset += len(chunk_bytes)
    oci_bytes = b"".join(oci_parts)
    require(
        len(oci_bytes) == oci_fixture["size"],
        "OCI blob aggregate size does not match reconstructed content",
    )
    require(
        oci_fixture["digest"] == f"sha256:{hashlib.sha256(oci_bytes).hexdigest()}",
        "OCI blob aggregate digest does not match reconstructed content",
    )

    def expect_rejected(value: str, label: str, *, schema_rejects: bool) -> None:
        errors = validation_errors(bytes_schema, value, resource_registry)
        require(bool(errors) is schema_rejects, f"bounded-byte schema disposition drift: {label}")
        try:
            decode_canonical_bounded_base64url(value, label)
        except ContractValidationError:
            return
        raise ContractValidationError(f"bounded-byte semantic mutation accepted: {label}")

    expect_rejected("A", "length-modulo-four-one", schema_rejects=True)
    expect_rejected("AA+_", "invalid-base64url-alphabet", schema_rejects=True)
    expect_rejected("AA==", "forbidden-base64url-padding", schema_rejects=True)
    # AB decodes to the same byte as AA; exact re-encoding catches its non-zero
    # unused low-order bits even though the regular-language schema accepts it.
    expect_rejected("AB", "non-zero-unused-tail-bits", schema_rejects=False)
    oversized = base64.urlsafe_b64encode(b"\x00" * 4194305).rstrip(b"=").decode("ascii")
    oversized_errors = validation_errors(bytes_schema, oversized, resource_registry)
    require(
        any(error.validator == "maxLength" for error in oversized_errors),
        "more-than-4-MiB canonical byte payload is accepted by schema",
    )
    expect_rejected(oversized, "decoded-byte-ceiling", schema_rejects=True)
    return 5


def validate_port_type_mutation_guards(
    port_registry: dict[str, Any],
    type_catalog: dict[str, Any],
    fixture_catalog: dict[str, Any],
    base_types: dict[str, dict[str, Any]],
    field_types: dict[str, dict[str, Any]],
    resource_registry: Registry,
) -> int:
    """Prove important denials independently from generated negative fixtures."""

    # The caller already executed oversized string and array probes plus five
    # canonical byte-wire mutations.
    probe_count = 7

    def expect_invalid(
        schema: dict[str, Any], instance: Any, label: str
    ) -> None:
        nonlocal probe_count
        require(
            validation_errors(schema, instance, resource_registry),
            f"adversarial mutation accepted: {label}",
        )
        probe_count += 1

    def expect_valid(schema: dict[str, Any], instance: Any, label: str) -> None:
        nonlocal probe_count
        errors = validation_errors(schema, instance, resource_registry)
        require(
            not errors,
            f"required boundary value rejected: {label}/{errors[0].message if errors else ''}",
        )
        probe_count += 1

    def field_with_refinement(refinement: str) -> dict[str, Any]:
        match = next(
            (entry for entry in field_types.values() if entry["refinement"] == refinement),
            None,
        )
        require(match is not None, f"no field type exercises refinement {refinement}")
        return match

    expect_invalid(
        base_types["primitive:boolean"]["schema"],
        "true",
        "wrong scalar type",
    )
    expect_invalid(
        field_with_refinement("enum")["schema"],
        "__unknown__",
        "unknown semantic enum",
    )
    expect_invalid(
        base_types["primitive:nonnegative-integer"]["schema"],
        9007199254740992,
        "unsafe JSON integer",
    )
    expect_invalid(
        base_types["primitive:rfc3339-utc"]["schema"],
        "2026-01-01",
        "malformed RFC3339 UTC timestamp",
    )
    expect_invalid(
        base_types["common#/$defs/digest"]["schema"],
        "sha256:bad",
        "malformed digest",
    )
    expect_invalid(
        base_types["primitive:media-type"]["schema"],
        "not a media type",
        "malformed media type",
    )
    for refinement, mutation in (
        ("immutable-commit", "main"),
        ("oci-repository", "https://registry.example.invalid/repository"),
        ("repository-uri", "http://example.invalid/repository.git"),
        ("uri", "not a uri"),
        ("filesystem-path", "bad\npath"),
        ("nonce", "short"),
        ("semantic-version", "1.2"),
    ):
        expect_invalid(
            field_with_refinement(refinement)["schema"],
            mutation,
            f"malformed {refinement}",
        )

    pagination = field_with_refinement("pagination-limit")["schema"]
    expect_invalid(pagination, 0, "zero pagination limit")
    expect_invalid(pagination, 1001, "oversized pagination limit")
    for refinement, maximum in (
        ("byte-limit-4mib", 4194304),
        ("byte-limit-64mib", 67108864),
    ):
        expect_invalid(
            field_with_refinement(refinement)["schema"],
            maximum + 1,
            f"oversized {refinement}",
        )
    expect_invalid(
        field_with_refinement("positive-counter")["schema"],
        0,
        "zero positive counter",
    )
    expect_valid(
        field_with_refinement("zero-based-cursor")["schema"],
        0,
        "zero-based cursor origin",
    )
    deadline = field_with_refinement("deadline-milliseconds")["schema"]
    expect_invalid(deadline, 0, "zero deadline")
    expect_invalid(deadline, 300001, "oversized deadline")

    def expect_catalog_rejected(
        mutated_type_catalog: dict[str, Any], label: str
    ) -> None:
        nonlocal probe_count
        try:
            validate_port_type_catalog(
                port_registry,
                mutated_type_catalog,
                fixture_catalog,
                run_mutation_probes=False,
            )
        except ContractValidationError:
            probe_count += 1
            return
        raise ContractValidationError(f"adversarial catalog mutation accepted: {label}")

    missing_type = deepcopy(type_catalog)
    missing_type["types"].pop()
    expect_catalog_rejected(missing_type, "missing field type")

    orphan_type = deepcopy(type_catalog)
    orphan = deepcopy(orphan_type["types"][-1])
    orphan["typeId"] = "bytedesk.port-field.orphan.mutation.request.value/1"
    orphan["schema"]["$id"] = expected_port_type_schema_id(orphan["typeId"])
    orphan["schemaDigest"] = canonical_digest(orphan["schema"])
    orphan_type["types"].append(orphan)
    expect_catalog_rejected(orphan_type, "orphan field type")

    cycle = deepcopy(type_catalog)
    cycle_entry = next(
        entry for entry in cycle["baseTypes"] if entry["schemaRef"] == "primitive:string"
    )
    cycle_id = cycle_entry["schema"]["$id"]
    cycle_entry["schema"] = {
        "$schema": PORT_SCHEMA_DIALECT,
        "$id": cycle_id,
        "$ref": cycle_id,
    }
    cycle_entry["schemaDigest"] = canonical_digest(cycle_entry["schema"])
    expect_catalog_rejected(cycle, "type reference cycle")

    open_object = deepcopy(type_catalog)
    open_entry = next(
        entry
        for entry in open_object["baseTypes"]
        if entry["schemaRef"] == "bytedesk.port.activation-authorization/1"
    )
    open_entry["schema"]["additionalProperties"] = True
    open_entry["schemaDigest"] = canonical_digest(open_entry["schema"])
    expect_catalog_rejected(open_object, "open inline object")

    bad_source_digest = deepcopy(type_catalog)
    bad_source_digest["schemaSources"][0]["schemaDigest"] = "sha256:" + "f" * 64
    expect_catalog_rejected(bad_source_digest, "bad offline source digest")

    network_resolution = deepcopy(type_catalog)
    network_entry = next(
        entry
        for entry in network_resolution["baseTypes"]
        if entry["schemaRef"] == "primitive:string"
    )
    network_entry["schema"] = {
        "$schema": PORT_SCHEMA_DIALECT,
        "$id": network_entry["schema"]["$id"],
        "$ref": "https://evil.invalid/network-schema.json",
    }
    network_entry["schemaDigest"] = canonical_digest(network_entry["schema"])
    expect_catalog_rejected(network_resolution, "attempted network resolution")

    return probe_count


def validate_port_type_catalog(
    port_registry: dict[str, Any],
    type_catalog: dict[str, Any],
    fixture_catalog: dict[str, Any],
    *,
    run_mutation_probes: bool = True,
) -> dict[str, int]:
    exact_keys(
        type_catalog,
        {
            "$schema",
            "profile",
            "version",
            "registry",
            "schemaDialect",
            "wireProfile",
            "schemaSources",
            "baseTypes",
            "types",
            "contracts",
            "fixtures",
        },
        "port type catalog root",
    )
    require(type_catalog["$schema"] == TYPE_CATALOG_SCHEMA_ID, "port type catalog schema binding drift")
    require(type_catalog["profile"] == "bytedesk.port-type-catalog/1", "wrong port type catalog profile")
    require(type_catalog["version"] == 1, "wrong port type catalog version")
    require(type_catalog["schemaDialect"] == PORT_SCHEMA_DIALECT, "port type schema dialect drift")
    exact_keys(type_catalog["registry"], {"path", "digest"}, "port type registry binding")
    require(type_catalog["registry"]["path"] == port_registry["typeCatalog"].replace("type-catalog.json", "port-registry.json"), "port type registry path drift")
    registry_digest = canonical_digest(port_registry)
    require(type_catalog["registry"]["digest"] == registry_digest, "port type registry digest drift")

    wire = type_catalog["wireProfile"]
    exact_keys(
        wire,
        {"jsonEncoding", "unknownFields", "nullability", "array", "string", "bytes", "integer"},
        "port wire profile",
    )
    require(wire["jsonEncoding"] == "utf-8-rfc8785-jcs-json", "port wire encoding drift")
    require(wire["unknownFields"] == "reject", "port wire profile permits unknown fields")
    require(wire["nullability"] == "only-explicit-nullable-types", "port nullability profile drift")
    require(wire["array"] == {"minItems": 0, "maxItems": 1024}, "port array bound drift")
    require(wire["string"] == {"maxCodePoints": 4096}, "port string bound drift")
    require(
        wire["bytes"]
        == {
            "encoding": "base64url-no-padding",
            "maxDecodedBytes": 4194304,
            "maxEncodedCharacters": 5592406,
        },
        "port byte encoding/bound drift",
    )
    require(wire["integer"] == {"minimum": 0, "maximum": 9007199254740991}, "port integer bound drift")

    source_keys = {"schemaId", "schemaDigest", "repositoryPath", "mediaType"}
    source_schemas: dict[str, dict[str, Any]] = {}
    source_paths: set[str] = set()
    source_order: list[str] = []
    require(isinstance(type_catalog["schemaSources"], list) and type_catalog["schemaSources"], "port schema sources are empty")
    for index, source in enumerate(type_catalog["schemaSources"]):
        require(isinstance(source, dict), f"schemaSources[{index}] must be an object")
        exact_keys(source, source_keys, f"schemaSources[{index}]")
        schema_id = source["schemaId"]
        path_text = source["repositoryPath"]
        require(isinstance(schema_id, str) and schema_id.startswith("https://schemas.bytedesk.ai/agent-delivery/v1/"), f"invalid offline schema ID: {schema_id!r}")
        require(isinstance(path_text, str) and path_text.startswith("contracts/schemas/v1/") and path_text.endswith(".schema.json"), f"invalid offline schema path: {path_text!r}")
        require(".." not in Path(path_text).parts and not Path(path_text).is_absolute(), f"unsafe offline schema path: {path_text}")
        require(schema_id not in source_schemas and path_text not in source_paths, "duplicate offline schema source")
        schema = load_json(REPOSITORY_ROOT / path_text)
        require(schema.get("$id") == schema_id, f"offline schema ID/path mismatch: {schema_id}")
        require(source["schemaDigest"] == canonical_digest(schema), f"offline schema digest drift: {schema_id}")
        require(source["mediaType"] == "application/schema+json", f"offline schema media type drift: {schema_id}")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise ContractValidationError(f"invalid offline source schema {schema_id}: {error}") from error
        source_schemas[schema_id] = schema
        source_paths.add(path_text)
        source_order.append(schema_id)
    require(source_order == sorted(source_order), "offline schema sources are not ID-sorted")

    actual_base_usage: dict[str, set[str]] = {}
    expected_field_bindings: list[tuple[str, str, str, str, dict[str, Any]]] = []
    for port in port_registry["ports"]:
        for operation in port["operations"]:
            for direction, fields_key in (("request", "requestFields"), ("result", "resultFields")):
                for field in operation[fields_key]:
                    actual_base_usage.setdefault(field["schemaRef"], set()).add(field["type"])
                    expected_type_id = expected_field_value_type(
                        port["portId"], operation["operationId"], direction, field["name"]
                    )
                    require(field["valueType"] == expected_type_id, f"noncanonical field value type: {field['valueType']}")
                    expected_field_bindings.append((port["portId"], operation["operationId"], direction, field["name"], field))

    base_keys = {"schemaRef", "usageKinds", "schemaDigest", "schema", "source", "fixture"}
    base_types: dict[str, dict[str, Any]] = {}
    base_type_schema_ids: dict[str, str] = {}
    base_schema_documents: dict[str, dict[str, Any]] = {}
    base_order: list[str] = []
    require(isinstance(type_catalog["baseTypes"], list) and type_catalog["baseTypes"], "base type catalog is empty")
    for index, entry in enumerate(type_catalog["baseTypes"]):
        require(isinstance(entry, dict), f"baseTypes[{index}] must be an object")
        exact_keys(entry, base_keys, f"baseTypes[{index}]")
        schema_ref = entry["schemaRef"]
        require(isinstance(schema_ref, str) and schema_ref not in base_types, f"invalid or duplicate base schemaRef: {schema_ref!r}")
        require(entry["usageKinds"] == sorted(actual_base_usage.get(schema_ref, set())), f"base type usage drift: {schema_ref}")
        schema = entry["schema"]
        require(isinstance(schema, dict), f"base type schema must be object: {schema_ref}")
        require(schema.get("$schema") == PORT_SCHEMA_DIALECT, f"base type dialect drift: {schema_ref}")
        schema_id = schema.get("$id")
        require(schema_id == expected_port_type_schema_id(schema_ref), f"base type schema ID drift: {schema_ref}")
        require(schema_id not in base_schema_documents, f"duplicate base type schema ID: {schema_id}")
        require(entry["schemaDigest"] == canonical_digest(schema), f"base type schema digest drift: {schema_ref}")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise ContractValidationError(f"invalid base type schema {schema_ref}: {error}") from error
        source = entry["source"]
        require(isinstance(source, dict) and isinstance(source.get("kind"), str), f"base type source is invalid: {schema_ref}")
        if source["kind"] == "inline":
            exact_keys(source, {"kind"}, f"baseTypes[{index}].source")
            require_closed_inline_objects(schema, f"base type {schema_ref}")
        elif source["kind"] == "schema-target":
            exact_keys(source, {"kind", "schemaId", "schemaDigest", "jsonPointer"}, f"baseTypes[{index}].source")
            target_id = source["schemaId"]
            require(target_id in source_schemas, f"base type references unlisted schema: {schema_ref}")
            require(source["schemaDigest"] == canonical_digest(source_schemas[target_id]), f"base target digest drift: {schema_ref}")
            pointer = source["jsonPointer"]
            resolve_json_pointer(source_schemas[target_id], pointer, f"base target {schema_ref}")
            expected_ref = target_id + (f"#{pointer}" if pointer else "")
            require(set(schema) == {"$schema", "$id", "$ref"} and schema["$ref"] == expected_ref, f"base target wrapper drift: {schema_ref}")
        elif source["kind"] == "derived-enum":
            exact_keys(source, {"kind", "repositoryPath", "documentDigest", "arrayPointer", "valuePointer"}, f"baseTypes[{index}].source")
            source_path = source["repositoryPath"]
            require(source_path in {"contracts/events/v1/event-types.json", "contracts/ports/v1/problem-catalog.json"}, f"unapproved derived enum source: {source_path}")
            document = load_json(REPOSITORY_ROOT / source_path)
            require(source["documentDigest"] == canonical_digest(document), f"derived enum source digest drift: {schema_ref}")
            values_source = resolve_json_pointer(document, source["arrayPointer"], f"derived enum {schema_ref}")
            require(isinstance(values_source, list) and values_source, f"derived enum array is empty: {schema_ref}")
            values = [resolve_json_pointer(item, source["valuePointer"], f"derived enum value {schema_ref}") for item in values_source]
            if source_path.endswith("problem-catalog.json"):
                values = sorted(set(values))
            else:
                require(len(values) == len(set(values)), f"derived enum values duplicate: {schema_ref}")
            require(schema.get("enum") == values, f"derived enum values drift: {schema_ref}")
        else:
            raise ContractValidationError(f"unknown base type source kind: {schema_ref}/{source['kind']}")
        exact_keys(entry["fixture"], {"valid", "invalid"}, f"base type fixture {schema_ref}")
        exact_keys(entry["fixture"]["invalid"], {"instance", "expectedKeyword"}, f"base invalid fixture {schema_ref}")
        base_types[schema_ref] = entry
        base_type_schema_ids[schema_ref] = schema_id
        base_schema_documents[schema_id] = schema
        base_order.append(schema_ref)
    require(base_order == sorted(base_order), "base types are not schemaRef-sorted")
    require(set(base_types) == set(actual_base_usage), f"base type closure differs; missing={sorted(set(actual_base_usage)-set(base_types))} orphans={sorted(set(base_types)-set(actual_base_usage))}")

    field_keys = {"typeId", "portId", "operationId", "direction", "fieldName", "baseSchemaRef", "refinement", "schemaDigest", "schema", "fixture"}
    field_types: dict[str, dict[str, Any]] = {}
    field_type_schema_ids: dict[str, str] = {}
    field_schema_documents: dict[str, dict[str, Any]] = {}
    field_entry_order: list[str] = []
    require(isinstance(type_catalog["types"], list), "field type catalog must be an array")
    require(len(type_catalog["types"]) == len(expected_field_bindings), "field type count differs from registry fields")
    for index, (entry, expected_binding) in enumerate(zip(type_catalog["types"], expected_field_bindings)):
        require(isinstance(entry, dict), f"types[{index}] must be an object")
        exact_keys(entry, field_keys, f"types[{index}]")
        port_id, operation_id, direction, field_name, field = expected_binding
        type_id = field["valueType"]
        require(entry["typeId"] == type_id, f"field type order/ID drift at {index}")
        require(entry["portId"] == port_id and entry["operationId"] == operation_id and entry["direction"] == direction and entry["fieldName"] == field_name, f"field type registry binding drift: {type_id}")
        require(entry["baseSchemaRef"] == field["schemaRef"] and entry["baseSchemaRef"] in base_types, f"field type base binding drift: {type_id}")
        schema = entry["schema"]
        require(isinstance(schema, dict), f"field type schema must be object: {type_id}")
        schema_id = expected_port_type_schema_id(type_id)
        require(schema.get("$schema") == PORT_SCHEMA_DIALECT and schema.get("$id") == schema_id, f"field type schema identity drift: {type_id}")
        require_closed_inline_objects(schema, f"field type {type_id}")
        refinement = entry["refinement"]
        require(isinstance(refinement, str) and refinement, f"field refinement is missing: {type_id}")
        if field["type"] == "array":
            if field["schemaRef"] in EXACT_ARRAY_SCHEMA_REFS:
                require(
                    refinement == "exact-array-contract",
                    f"exact array field lost its source contract: {type_id}",
                )
                expected_body = {
                    "$schema": PORT_SCHEMA_DIALECT,
                    "$id": schema_id,
                    "$ref": base_type_schema_ids[field["schemaRef"]],
                }
            else:
                require(refinement == "bounded-array", f"array field lacks its complete bounded type: {type_id}")
                expected_body = {
                    "$schema": PORT_SCHEMA_DIALECT,
                    "$id": schema_id,
                    "type": "array",
                    "minItems": wire["array"]["minItems"],
                    "maxItems": wire["array"]["maxItems"],
                    "items": {"$ref": base_type_schema_ids[field["schemaRef"]]},
                }
            require(schema == expected_body, f"field type is not a complete canonical array schema: {type_id}")
        elif refinement == "consumer-capability-verifier-actor":
            require(
                port_id == "bytedesk.port.capability-verifier/1"
                and operation_id == "verify-capability-result"
                and direction == "request"
                and field_name == "capabilityEvidence"
                and field["schemaRef"] == "canary-evidence",
                f"capability actor refinement is attached to the wrong field: {type_id}",
            )
            require(set(schema) == {"$schema", "$id", "allOf"}, f"capability actor field shape drift: {type_id}")
            require(
                schema["allOf"]
                == [
                    {"$ref": base_type_schema_ids[field["schemaRef"]]},
                    {
                        "required": ["actor", "capabilityDispatch"],
                        "properties": {
                            "actor": {"const": "consumer_capability_verifier"}
                        },
                    },
                ],
                f"capability actor field does not require consumer evidence and dispatch binding: {type_id}",
            )
        elif field["schemaRef"] == "primitive:string":
            allowed_refinements = {
                "enum",
                "media-type",
                "oci-repository",
                "repository-uri",
                "audience-token",
                "immutable-commit",
                "nonce",
                "opaque-token",
                "uri",
                "filesystem-path",
                "revision-token",
                "reason-code",
                "semantic-version",
            }
            require(refinement in allowed_refinements, f"semantic string field remains generic: {type_id}")
            require(set(schema) == {"$schema", "$id", "allOf"}, f"semantic field schema shape drift: {type_id}")
            all_of = schema["allOf"]
            require(isinstance(all_of, list) and len(all_of) == 2, f"semantic field refinement is not conjunctive: {type_id}")
            require(all_of[0] == {"$ref": base_type_schema_ids[field["schemaRef"]]}, f"semantic field omits bounded string base: {type_id}")
            constraint = all_of[1]
            require(isinstance(constraint, dict) and constraint, f"semantic field constraint is empty: {type_id}")
            if refinement == "enum":
                exact_keys(constraint, {"enum"}, f"semantic enum {type_id}")
                unique_strings(constraint["enum"], f"semantic enum {type_id}")
            elif refinement == "media-type":
                require(constraint == {"$ref": "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0#/$defs/mediaType"}, f"media-type grammar drift: {type_id}")
            elif refinement == "oci-repository":
                require(constraint == {"$ref": "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0#/$defs/ociRepository"}, f"OCI repository grammar drift: {type_id}")
            elif refinement == "repository-uri":
                require(constraint.get("type") == "string" and constraint.get("format") == "uri" and constraint.get("pattern") == "^https://" and constraint.get("maxLength") == 2048, f"repository URI grammar drift: {type_id}")
            elif refinement == "audience-token":
                require(
                    constraint.get("pattern")
                    == "^[A-Za-z0-9][A-Za-z0-9._~:/-]{0,511}$"
                    and constraint.get("maxLength") == 512,
                    f"audience token grammar drift: {type_id}",
                )
            elif refinement == "immutable-commit":
                require(constraint.get("pattern") == "^(?:[0-9a-f]{40}|[0-9a-f]{64})$" and constraint.get("maxLength") == 64, f"immutable commit grammar drift: {type_id}")
            elif refinement == "nonce":
                require(constraint.get("pattern") == "^[A-Za-z0-9_-]{16,512}$" and constraint.get("maxLength") == 512, f"nonce grammar drift: {type_id}")
            elif refinement == "opaque-token":
                require(constraint.get("pattern") == "^[A-Za-z0-9._~:-]{16,4096}$" and constraint.get("maxLength") == 4096, f"opaque token grammar drift: {type_id}")
            elif refinement == "uri":
                require(constraint.get("type") == "string" and constraint.get("format") == "uri" and constraint.get("maxLength") == 2048, f"URI grammar drift: {type_id}")
            elif refinement == "filesystem-path":
                require(constraint.get("pattern") == "^[^\\u0000\\r\\n]+$" and constraint.get("maxLength") == 4096, f"filesystem path grammar drift: {type_id}")
            elif refinement == "revision-token":
                require(constraint.get("pattern") == "^[A-Za-z0-9._:-]{1,256}$" and constraint.get("maxLength") == 256, f"revision token grammar drift: {type_id}")
            elif refinement == "reason-code":
                require(constraint.get("pattern") == "^[a-z][a-z0-9_]{0,127}$" and constraint.get("maxLength") == 128, f"reason-code grammar drift: {type_id}")
            elif refinement == "semantic-version":
                require(constraint.get("pattern") == "^[0-9]+\\.[0-9]+\\.[0-9]+$" and constraint.get("maxLength") == 128, f"semantic-version grammar drift: {type_id}")
        elif field["schemaRef"] == "primitive:nonnegative-integer":
            integer_refinements = {
                "pagination-limit": (1, 1000),
                "byte-limit-4mib": (1, 4194304),
                "byte-limit-64mib": (1, 67108864),
                "deadline-milliseconds": (1, 300000),
                "timeout-seconds": (1, 86400),
                "poll-maximum-seconds": (1, 30),
                "zero-based-cursor": (0, 9007199254740991),
                "positive-counter": (1, 9007199254740991),
            }
            require(
                refinement in integer_refinements,
                f"semantic integer field remains generic: {type_id}",
            )
            require(
                set(schema) == {"$schema", "$id", "allOf"},
                f"semantic integer schema shape drift: {type_id}",
            )
            all_of = schema["allOf"]
            require(
                isinstance(all_of, list) and len(all_of) == 2,
                f"semantic integer refinement is not conjunctive: {type_id}",
            )
            require(
                all_of[0] == {"$ref": base_type_schema_ids[field["schemaRef"]]},
                f"semantic integer omits safe nonnegative base: {type_id}",
            )
            minimum, maximum = integer_refinements[refinement]
            require(
                all_of[1] == {"minimum": minimum, "maximum": maximum},
                f"semantic integer bound drift: {type_id}",
            )
            if refinement == "pagination-limit":
                require(field_name == "limit", f"pagination refinement on non-limit field: {type_id}")
            elif refinement.startswith("byte-limit-"):
                require(field_name == "maximumBytes", f"byte-limit refinement on wrong field: {type_id}")
                expected = (
                    "byte-limit-4mib"
                    if port_id == "bytedesk.port.catalog/1"
                    else "byte-limit-64mib"
                )
                require(refinement == expected, f"byte-limit profile drift: {type_id}")
            elif refinement == "deadline-milliseconds":
                require(field_name == "deadlineMilliseconds", f"deadline refinement on wrong field: {type_id}")
            elif refinement == "timeout-seconds":
                require(field_name == "timeoutSeconds", f"timeout refinement on wrong field: {type_id}")
            elif refinement == "poll-maximum-seconds":
                require(field_name == "pollMaximumSeconds", f"poll refinement on wrong field: {type_id}")
            elif refinement == "zero-based-cursor":
                require(field_name in {"afterRevision", "knownSequence"}, f"zero cursor on wrong field: {type_id}")
            else:
                require(
                    field_name not in {
                        "limit",
                        "maximumBytes",
                        "deadlineMilliseconds",
                        "timeoutSeconds",
                        "pollMaximumSeconds",
                        "afterRevision",
                        "knownSequence",
                    },
                    f"generic positive counter masks a special integer field: {type_id}",
                )
        else:
            require(refinement == "base", f"non-string scalar has unexpected refinement: {type_id}")
            expected_body = {
                "$schema": PORT_SCHEMA_DIALECT,
                "$id": schema_id,
                "$ref": base_type_schema_ids[field["schemaRef"]],
            }
            require(schema == expected_body, f"field type is not a complete canonical value schema: {type_id}")
        require(entry["schemaDigest"] == canonical_digest(schema), f"field type schema digest drift: {type_id}")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise ContractValidationError(f"invalid field type schema {type_id}: {error}") from error
        require(type_id not in field_types and schema_id not in field_schema_documents, f"duplicate field type: {type_id}")
        exact_keys(entry["fixture"], {"valid", "invalid"}, f"field type fixture {type_id}")
        exact_keys(entry["fixture"]["invalid"], {"instance", "expectedKeyword"}, f"field invalid fixture {type_id}")
        field_types[type_id] = entry
        field_type_schema_ids[type_id] = schema_id
        field_schema_documents[schema_id] = schema
        field_entry_order.append(type_id)
    require(len(field_types) == len(expected_field_bindings), "field value types are not unique")

    all_schema_documents = dict(source_schemas)
    all_schema_documents.update(base_schema_documents)
    all_schema_documents.update(field_schema_documents)
    try:
        resource_registry = Registry().with_resources(
            [(schema_id, Resource.from_contents(schema)) for schema_id, schema in all_schema_documents.items()]
        )
    except ValueError as error:
        raise ContractValidationError(f"cannot build closed offline port schema registry: {error}") from error

    type_ids = set(base_schema_documents) | set(field_schema_documents)
    source_ids = set(source_schemas)
    type_graph: dict[str, set[str]] = {schema_id: set() for schema_id in type_ids}
    source_seeds: set[str] = set()
    for schema_id in sorted(type_ids):
        schema = all_schema_documents[schema_id]
        resolver = resource_registry.resolver(schema_id)
        for reference in iter_schema_references(schema):
            try:
                resolver.lookup(reference)
            except (NoSuchResource, Unresolvable) as error:
                raise ContractValidationError(f"unresolved offline type reference {schema_id} -> {reference}: {error}") from error
            if reference.startswith("#"):
                continue
            base, _ = urldefrag(reference)
            require(base in type_ids or base in source_ids, f"network/fallback type reference is forbidden: {schema_id} -> {reference}")
            if base in type_ids:
                type_graph[schema_id].add(base)
            else:
                source_seeds.add(base)

    visiting: set[str] = set()
    visited: set[str] = set()
    def visit_type(schema_id: str) -> None:
        require(schema_id not in visiting, f"catalog type cycle detected at {schema_id}")
        if schema_id in visited:
            return
        visiting.add(schema_id)
        for dependency in sorted(type_graph[schema_id]):
            visit_type(dependency)
        visiting.remove(schema_id)
        visited.add(schema_id)
    for schema_id in sorted(type_graph):
        visit_type(schema_id)

    reachable_sources: set[str] = set()
    pending_sources = list(source_seeds)
    while pending_sources:
        schema_id = pending_sources.pop()
        if schema_id in reachable_sources:
            continue
        require(schema_id in source_schemas, f"unlisted transitive schema source: {schema_id}")
        reachable_sources.add(schema_id)
        resolver = resource_registry.resolver(schema_id)
        for reference in iter_schema_references(source_schemas[schema_id]):
            try:
                resolver.lookup(reference)
            except (NoSuchResource, Unresolvable) as error:
                raise ContractValidationError(f"unresolved offline source reference {schema_id} -> {reference}: {error}") from error
            if reference.startswith("#"):
                continue
            base, _ = urldefrag(reference)
            require(base in source_ids, f"source schema network/fallback reference is forbidden: {schema_id} -> {reference}")
            pending_sources.append(base)
    require(reachable_sources == source_ids, f"schema source closure differs; missing={sorted(reachable_sources-source_ids)} orphans={sorted(source_ids-reachable_sources)}")

    nullable_field_types = {"string-or-null", "object-or-null", "digest-or-null"}
    nullable_fields = 0
    for type_id, entry in field_types.items():
        schema = entry["schema"]
        fixture = entry["fixture"]
        valid_errors = validation_errors(schema, fixture["valid"], resource_registry)
        require(not valid_errors, f"valid field-type fixture rejected: {type_id}/{valid_errors[0].message if valid_errors else ''}")
        invalid_errors = validation_errors(schema, fixture["invalid"]["instance"], resource_registry)
        require(invalid_errors, f"invalid field-type fixture accepted: {type_id}")
        validate_expected_keyword(invalid_errors, fixture["invalid"]["expectedKeyword"], f"field type {type_id}")
        field = next(binding[4] for binding in expected_field_bindings if binding[4]["valueType"] == type_id)
        null_errors = validation_errors(schema, None, resource_registry)
        if field["type"] in nullable_field_types:
            nullable_fields += 1
            require(not null_errors, f"explicit nullable field rejects null: {type_id}")
        else:
            require(null_errors, f"non-nullable field accepts null: {type_id}")

    for schema_ref, entry in base_types.items():
        schema = entry["schema"]
        fixture = entry["fixture"]
        valid_errors = validation_errors(schema, fixture["valid"], resource_registry)
        require(not valid_errors, f"valid base-type fixture rejected: {schema_ref}/{valid_errors[0].message if valid_errors else ''}")
        invalid_errors = validation_errors(schema, fixture["invalid"]["instance"], resource_registry)
        require(invalid_errors, f"invalid base-type fixture accepted: {schema_ref}")
        validate_expected_keyword(invalid_errors, fixture["invalid"]["expectedKeyword"], f"base type {schema_ref}")

    oversized_string = "x" * (wire["string"]["maxCodePoints"] + 1)
    string_errors = validation_errors(base_types["primitive:string"]["schema"], oversized_string, resource_registry)
    require(any(error.validator == "maxLength" for error in string_errors), "oversized primitive string is accepted")
    byte_mutations = validate_bounded_bytes_profile(
        base_types, resource_registry
    )
    require(byte_mutations == 5, "bounded-byte mutation suite count drift")
    array_type = next((entry for entry in field_types.values() if entry["schema"].get("type") == "array"), None)
    require(array_type is not None, "no bounded array field type exists")
    oversized_array = [array_type["fixture"]["valid"][0]] * (wire["array"]["maxItems"] + 1)
    array_errors = validation_errors(array_type["schema"], oversized_array, resource_registry)
    require(any(error.validator == "maxItems" for error in array_errors), "oversized field array is accepted")

    contract_keys = {"contractId", "portId", "operationId", "direction", "schemaId", "schemaDigest", "schema"}
    expected_contracts: list[tuple[str, str, str, str, list[dict[str, Any]]]] = []
    for port in port_registry["ports"]:
        for operation in port["operations"]:
            expected_contracts.extend(
                [
                    (operation["requestContract"], port["portId"], operation["operationId"], "request", operation["requestFields"]),
                    (operation["resultContract"], port["portId"], operation["operationId"], "result", operation["resultFields"]),
                ]
            )
    require(isinstance(type_catalog["contracts"], list) and len(type_catalog["contracts"]) == len(expected_contracts), "compiled contract count drift")
    compiled_schemas: dict[str, dict[str, Any]] = {}
    for index, (entry, expected) in enumerate(zip(type_catalog["contracts"], expected_contracts)):
        require(isinstance(entry, dict), f"contracts[{index}] must be an object")
        exact_keys(entry, contract_keys, f"contracts[{index}]")
        contract_id, port_id, operation_id, direction, fields = expected
        require(entry["contractId"] == contract_id and entry["portId"] == port_id and entry["operationId"] == operation_id and entry["direction"] == direction, f"compiled contract registry binding drift: {contract_id}")
        embedded_variants = entry["schema"].get("oneOf")
        expected_schema = expected_contract_schema(
            contract_id,
            fields,
            field_type_schema_ids,
            embedded_variants,
        )
        require(entry["schema"] == expected_schema, f"embedded compiled schema differs from registry: {contract_id}")
        require(entry["schemaId"] == expected_schema["$id"], f"compiled schema ID drift: {contract_id}")
        require(entry["schemaDigest"] == canonical_digest(expected_schema), f"compiled schema digest drift: {contract_id}")
        require(expected_schema["additionalProperties"] is False and expected_schema["unevaluatedProperties"] is False, f"compiled schema is open: {contract_id}")
        require_closed_inline_objects(expected_schema, f"compiled schema {contract_id}")
        try:
            Draft202012Validator.check_schema(expected_schema)
        except SchemaError as error:
            raise ContractValidationError(f"invalid compiled contract schema {contract_id}: {error}") from error
        require(contract_id not in compiled_schemas, f"duplicate compiled contract ID: {contract_id}")
        compiled_schemas[contract_id] = expected_schema

    semantic_contracts = {
        "bytedesk.port.catalog.list-catalog-releases.request/1",
        "bytedesk.port.kms-signing.resolve-signing-request.result/1",
        "bytedesk.port.consumer-authority-approval.resolve-authority-snapshot.request/1",
        "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1",
        "bytedesk.port.oci-registry.head-artifact.result/1",
        "bytedesk.port.oci-registry.list-referrers.request/1",
        "bytedesk.port.desired-state-store.watch-target-state.result/1",
        "bytedesk.port.desired-state-store.resolve-idempotency.result/1",
        "bytedesk.port.desired-state-store.read-target-history.request/1",
        "bytedesk.port.control-plane-api-events.read-resource.result/1",
        "bytedesk.port.promotion-coordinator.evaluate-evidence.result/1",
        "bytedesk.port.private-compiler.resolve-compile-attempt.result/1",
        "bytedesk.port.cli-automation.watch-action.result/1",
    }
    expected_semantic_denial_kinds = {
        "bytedesk.port.catalog.list-catalog-releases.request/1": (
            "continuation-without-snapshot",
        ),
        "bytedesk.port.oci-registry.head-artifact.result/1": (
            "absence-returned-as-success",
        ),
        "bytedesk.port.oci-registry.list-referrers.request/1": (
            "continuation-without-snapshot",
        ),
        "bytedesk.port.kms-signing.resolve-signing-request.result/1": (
            "signed-without-envelope",
        ),
        "bytedesk.port.consumer-authority-approval.resolve-authority-snapshot.request/1": (
            "non-compile-with-authorized-input-digest",
        ),
        "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1": (
            "denied-returned-as-authorized-success",
        ),
        "bytedesk.port.desired-state-store.watch-target-state.result/1": (
            "gap-returned-with-changes",
        ),
        "bytedesk.port.desired-state-store.resolve-idempotency.result/1": (
            "committed-without-receipt",
        ),
        "bytedesk.port.desired-state-store.read-target-history.request/1": (
            "continuation-without-snapshot",
        ),
        "bytedesk.port.control-plane-api-events.read-resource.result/1": (
            "found-without-resource",
        ),
        "bytedesk.port.promotion-coordinator.evaluate-evidence.result/1": (
            "permitted-with-missing-evidence",
        ),
        "bytedesk.port.private-compiler.resolve-compile-attempt.result/1": (
            "committed-without-complete-artifacts",
            "denied-without-problem",
        ),
        "bytedesk.port.cli-automation.watch-action.result/1": (
            "terminal-failure-with-cancelled-exit",
        ),
    }
    require(
        set(expected_semantic_denial_kinds) == semantic_contracts,
        "semantic denial oracle inventory differs from semantic contracts",
    )
    actual_semantic_contracts = {
        contract_id
        for contract_id, schema in compiled_schemas.items()
        if "oneOf" in schema
    }
    require(
        actual_semantic_contracts == semantic_contracts,
        "operation-level semantic schema set drift: "
        f"missing={sorted(semantic_contracts-actual_semantic_contracts)} "
        f"unexpected={sorted(actual_semantic_contracts-semantic_contracts)}",
    )
    expected_variant_shapes = {
        "bytedesk.port.catalog.list-catalog-releases.request/1": (2, {"cursor", "snapshotDigest"}),
        "bytedesk.port.oci-registry.head-artifact.result/1": (1, {"exists"}),
        "bytedesk.port.oci-registry.list-referrers.request/1": (2, {"cursor", "snapshotDigest"}),
        "bytedesk.port.kms-signing.resolve-signing-request.result/1": (2, {"resolution", "signatureEnvelope"}),
        "bytedesk.port.consumer-authority-approval.resolve-authority-snapshot.request/1": (
            2,
            {"operation"},
        ),
        "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1": (
            1,
            {"verificationResult", "authorizedPrivateInputDigest"},
        ),
        "bytedesk.port.desired-state-store.watch-target-state.result/1": (2, {"nextResumeToken", "resyncRequired"}),
        "bytedesk.port.desired-state-store.resolve-idempotency.result/1": (2, {"resolution", "commitReceipt"}),
        "bytedesk.port.desired-state-store.read-target-history.request/1": (2, {"beforeRevision", "snapshotDigest"}),
        "bytedesk.port.control-plane-api-events.read-resource.result/1": (2, {"readOutcome", "resource"}),
        "bytedesk.port.promotion-coordinator.evaluate-evidence.result/1": (3, {"decision", "evaluationAttestation", "missingEvidence"}),
        "bytedesk.port.private-compiler.resolve-compile-attempt.result/1": (3, {"resolution", "artifacts", "problem"}),
        "bytedesk.port.cli-automation.watch-action.result/1": (4, {"terminalAction", "lastObservedAction", "exitCode"}),
    }
    for contract_id in sorted(semantic_contracts):
        variants = compiled_schemas[contract_id].get("oneOf")
        require(
            isinstance(variants, list),
            f"operation-level semantic variants are not schema-enforced: {contract_id}",
        )
        expected_count, discriminants = expected_variant_shapes[contract_id]
        require(len(variants) == expected_count, f"semantic variant count drift: {contract_id}")
        for variant in variants:
            require(
                discriminants <= set(variant.get("required", [])),
                f"semantic variant omits required discriminants: {contract_id}",
            )
            require(
                discriminants <= set(variant.get("properties", {})),
                f"semantic variant omits discriminant constraints: {contract_id}",
            )

    exact_keys(type_catalog["fixtures"], {"profile", "path", "digest"}, "port fixture binding")
    require(type_catalog["fixtures"]["profile"] == "bytedesk.port-contract-fixtures/1", "port fixture profile binding drift")
    require(type_catalog["fixtures"]["path"] == "contracts/ports/v1/contract-fixtures.json", "port fixture path binding drift")
    require(type_catalog["fixtures"]["digest"] == canonical_digest(fixture_catalog), "port fixture digest drift")
    exact_keys(
        fixture_catalog,
        {"$schema", "profile", "version", "registryDigest", "contracts"},
        "port contract fixture root",
    )
    require(
        fixture_catalog["$schema"] == CONTRACT_FIXTURE_SCHEMA_ID,
        "port contract fixture schema binding drift",
    )
    require(fixture_catalog["profile"] == "bytedesk.port-contract-fixtures/1" and fixture_catalog["version"] == 1, "wrong port contract fixture profile/version")
    require(fixture_catalog["registryDigest"] == registry_digest, "port contract fixture registry digest drift")
    require(isinstance(fixture_catalog["contracts"], list) and len(fixture_catalog["contracts"]) == len(expected_contracts), "port contract fixture count drift")
    denial_count = 0
    semantic_denial_count = 0
    for index, (fixture, expected) in enumerate(zip(fixture_catalog["contracts"], expected_contracts)):
        contract_id = expected[0]
        exact_keys(
            fixture,
            {"contractId", "valid", "structuralDenials", "semanticDenials"},
            f"contract fixture[{index}]",
        )
        require(fixture["contractId"] == contract_id, f"contract fixture order/ID drift: {contract_id}")
        schema = compiled_schemas[contract_id]
        valid = fixture["valid"]
        require(isinstance(valid, dict) and set(valid) == set(schema["properties"]), f"valid fixture field membership drift: {contract_id}")
        valid_errors = validation_errors(schema, valid, resource_registry)
        require(not valid_errors, f"valid contract fixture rejected: {contract_id}/{valid_errors[0].message if valid_errors else ''}")
        denials = fixture["structuralDenials"]
        require(isinstance(denials, list) and [denial.get("kind") for denial in denials] == ["unknown-field", "missing-required", "illegal-null"], f"structural denial set/order drift: {contract_id}")
        for denial_index, denial in enumerate(denials):
            exact_keys(denial, {"kind", "instance", "expectedKeyword"}, f"{contract_id}.structuralDenials[{denial_index}]")
            require(isinstance(denial["instance"], dict), f"structural denial instance is not an object: {contract_id}")
            errors = validation_errors(schema, denial["instance"], resource_registry)
            require(errors, f"structural denial accepted: {contract_id}/{denial['kind']}")
            validate_expected_keyword(errors, denial["expectedKeyword"], f"{contract_id}/{denial['kind']}")
            denial_count += 1
        semantic_denials = fixture["semanticDenials"]
        require(isinstance(semantic_denials, list), f"semantic denials are not an array: {contract_id}")
        expected_semantic_kinds = expected_semantic_denial_kinds.get(
            contract_id, ()
        )
        require(
            tuple(denial["kind"] for denial in semantic_denials)
            == expected_semantic_kinds,
            f"semantic denial inventory drift: {contract_id}",
        )
        for denial_index, denial in enumerate(semantic_denials):
            exact_keys(
                denial,
                {"kind", "instance", "expectedKeyword"},
                f"{contract_id}.semanticDenials[{denial_index}]",
            )
            require(
                denial["expectedKeyword"] == "oneOf",
                f"semantic denial does not target the aggregate variant: {contract_id}",
            )
            errors = validation_errors(schema, denial["instance"], resource_registry)
            require(errors, f"semantic denial accepted: {contract_id}/{denial['kind']}")
            validate_expected_keyword(
                errors,
                denial["expectedKeyword"],
                f"{contract_id}/{denial['kind']}",
            )
            semantic_denial_count += 1

        if contract_id == "bytedesk.port.control-plane-api-events.read-resource.result/1":
            require(valid["readOutcome"] == "found" and isinstance(valid["resource"], dict), "read-resource positive branch drift")
            require(valid["etag"] == canonical_digest(valid["resource"]), "read-resource ETag is not sha256(JCS(resource))")
        elif contract_id == "bytedesk.port.cli-automation.watch-action.result/1":
            require(valid["terminalAction"] == valid["lastObservedAction"], "terminal watch result does not repeat the exact terminal action")
        elif contract_id == "bytedesk.port.desired-state-store.migrate-target-state.result/1":
            require(valid["migrationId"] == valid["migrationCheckpoint"]["migrationId"], "migration result/checkpoint identity drift")
        elif contract_id == "bytedesk.port.control-plane-api-events.subscribe-events.result/1":
            event = valid["eventStream"]
            require(event["dataDigest"] == canonical_digest(event["data"]), "SSE data digest drift")
            require(event["aggregateSequence"] == event["data"]["aggregate"]["sequence"], "SSE aggregate sequence drift")
        elif (
            contract_id
            == "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1"
        ):
            require(
                valid["verificationResult"]["outcome"] == "permitted"
                and valid["verificationResult"]["reasonCodes"] == [],
                "private-authority success fixture is not permitted",
            )
            require(
                semantic_denials[0]["kind"]
                == "denied-returned-as-authorized-success"
                and semantic_denials[0]["instance"]["verificationResult"]["outcome"]
                == "denied",
                "private-authority denied-result semantic fixture drift",
            )

    adversarial_mutations = 0
    if run_mutation_probes:
        adversarial_mutations = validate_port_type_mutation_guards(
            port_registry,
            type_catalog,
            fixture_catalog,
            base_types,
            field_types,
            resource_registry,
        )

    return {
        "schemaSources": len(source_schemas),
        "baseTypes": len(base_types),
        "fieldValueTypes": len(field_types),
        "semanticFieldRefinements": sum(
            entry["refinement"] not in {"base", "bounded-array"}
            for entry in field_types.values()
        ),
        "nullableFields": nullable_fields,
        "compiledContracts": len(compiled_schemas),
        "contractFixtures": len(fixture_catalog["contracts"]),
        "structuralDenials": denial_count,
        "semanticDenials": semantic_denial_count,
        "adversarialMutations": adversarial_mutations,
    }


def validate_problems(
    problem_catalog: dict[str, Any], referenced_error_states: dict[str, set[str]]
) -> dict[str, dict[str, Any]]:
    exact_keys(problem_catalog, {"$schema", "profile", "version", "problems"}, "problem catalog root")
    require(
        problem_catalog["$schema"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/problem-catalog/1.0.0",
        "problem catalog schema binding drift",
    )
    require(problem_catalog["profile"] == "bytedesk.problem-catalog/1", "wrong problem catalog profile")
    require(problem_catalog["version"] == 1, "wrong problem catalog version")
    require(isinstance(problem_catalog["problems"], list), "problems must be an array")
    keys = {"code", "type", "status", "retryable", "sideEffectStates", "cliExit"}
    problems: dict[str, dict[str, Any]] = {}
    types: set[str] = set()
    order: list[str] = []
    for index, problem in enumerate(problem_catalog["problems"]):
        require(isinstance(problem, dict), f"problem[{index}] must be an object")
        exact_keys(problem, keys, f"problem[{index}]")
        code = problem["code"]
        require(isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]*", code), f"invalid problem code: {code!r}")
        require(code not in problems, f"duplicate problem code: {code}")
        expected_type = f"https://problems.bytedesk.ai/agent-delivery/{code.replace('_', '-')}"
        require(problem["type"] == expected_type, f"problem type/code mismatch: {code}")
        require(problem["type"] not in types, f"duplicate problem type: {problem['type']}")
        require(type(problem["status"]) is int and 400 <= problem["status"] <= 599, f"invalid status: {code}")
        require(type(problem["retryable"]) is bool, f"retryable must be boolean: {code}")
        side_effect_states = unique_strings(
            problem["sideEffectStates"], f"problem[{index}].sideEffectStates"
        )
        require(
            all(state in SIDE_EFFECT_STATES for state in side_effect_states),
            f"invalid side-effect state: {code}",
        )
        require(
            side_effect_states
            == [state for state in SIDE_EFFECT_STATE_ORDER if state in side_effect_states],
            f"problem side-effect states are not in canonical order: {code}",
        )
        require(type(problem["cliExit"]) is int and problem["cliExit"] in CLI_EXIT_CODES, f"invalid CLI exit: {code}")
        if problem["retryable"]:
            require(problem["cliExit"] in {9, 12, 13}, f"retryable problem has non-retryable CLI class: {code}")
        problems[code] = problem
        types.add(problem["type"])
        order.append(code)
    require(order == sorted(order), "problem catalog must be sorted by stable code")
    referenced_errors = set(referenced_error_states)
    require(set(problems) == referenced_errors, f"closed problem set differs from operation errors; missing={sorted(referenced_errors-set(problems))} extra={sorted(set(problems)-referenced_errors)}")
    for code, problem in problems.items():
        require(
            set(problem["sideEffectStates"]) == referenced_error_states[code],
            f"problem side-effect permissions differ from operation mappings: {code}",
        )
    return problems


def validate_problem_schema_alignment(
    problem_schema: dict[str, Any],
    problems: dict[str, dict[str, Any]],
    operations: dict[tuple[str, str], dict[str, Any]],
) -> None:
    require(
        problem_schema.get("$id")
        == "https://schemas.bytedesk.ai/agent-delivery/v1/problem-details/1.0.0",
        "problem-details schema ID drift",
    )
    required = set(problem_schema.get("required", []))
    require(
        {
            "type",
            "status",
            "code",
            "portId",
            "operationId",
            "retryable",
            "sideEffectState",
        }
        <= required,
        "problem-details does not require the catalog-mapped fields",
    )
    properties = problem_schema.get("properties")
    require(isinstance(properties, dict), "problem-details properties are missing")
    code_enum = properties.get("code", {}).get("enum")
    require(isinstance(code_enum, list), "problem-details code is not a closed enum")
    require(code_enum == list(problems), "problem-details code enum and problem catalog differ")
    side_effect_enum = properties.get("sideEffectState", {}).get("enum")
    require(
        isinstance(side_effect_enum, list) and set(side_effect_enum) == SIDE_EFFECT_STATES,
        "problem-details side-effect enum and catalog profile differ",
    )
    require(properties.get("retryable", {}).get("type") == "boolean", "problem retryable type drift")
    port_id_enum = properties.get("portId", {}).get("enum")
    require(
        port_id_enum == sorted({port_id for port_id, _ in operations}),
        "problem-details port ID enum and registry differ",
    )
    require(
        properties.get("operationId", {}).get("pattern") == r"^[a-z][a-z0-9-]*$",
        "problem-details operation ID pattern drift",
    )
    status = properties.get("status", {})
    require(status.get("type") == "integer" and status.get("minimum") == 400 and status.get("maximum") == 599, "problem status range drift")
    type_pattern = properties.get("type", {}).get("pattern")
    require(isinstance(type_pattern, str), "problem type URI pattern is missing")
    compiled_type = re.compile(type_pattern)
    for code, mapping in problems.items():
        require(compiled_type.search(mapping["type"]) is not None, f"problem type rejected by problem-details: {code}")
        require(mapping["status"] >= status["minimum"] and mapping["status"] <= status["maximum"], f"problem status rejected by schema: {code}")
        require(
            set(mapping["sideEffectStates"]) <= set(side_effect_enum),
            f"problem side effects rejected by schema: {code}",
        )

    try:
        variants = problem_schema["allOf"][0]["oneOf"]
    except (KeyError, IndexError, TypeError) as error:
        raise ContractValidationError(
            "problem-details has no closed per-code tuple variants"
        ) from error
    variants_by_code: dict[str, dict[str, Any]] = {}
    for variant in variants:
        variant_properties = variant.get("properties", {})
        code = variant_properties.get("code", {}).get("const")
        require(isinstance(code, str), "problem-details variant has no code discriminator")
        require(code not in variants_by_code, f"duplicate problem-details variant: {code}")
        variants_by_code[code] = variant_properties
    require(set(variants_by_code) == set(problems), "problem-details variants and catalog differ")
    for code, mapping in problems.items():
        side_effect_rule = variants_by_code[code].get("sideEffectState", {})
        allowed_states = side_effect_rule.get("enum")
        if allowed_states is None and "const" in side_effect_rule:
            allowed_states = [side_effect_rule["const"]]
        require(
            allowed_states == mapping["sideEffectStates"],
            f"problem-details per-code side-effect permissions drift: {code}",
        )

    try:
        operation_variants = problem_schema["allOf"][1]["oneOf"]
    except (KeyError, IndexError, TypeError) as error:
        raise ContractValidationError(
            "problem-details has no closed per-operation mappings"
        ) from error
    schema_operation_mappings: dict[tuple[str, str], dict[str, str]] = {}
    for variant in operation_variants:
        variant_properties = variant.get("properties", {})
        port_id = variant_properties.get("portId", {}).get("const")
        operation_id = variant_properties.get("operationId", {}).get("const")
        key = (port_id, operation_id)
        require(
            all(isinstance(part, str) for part in key),
            "problem-details operation variant has no discriminator",
        )
        require(key not in schema_operation_mappings, f"duplicate problem operation variant: {key}")
        try:
            error_variants = variant["allOf"][0]["oneOf"]
        except (KeyError, IndexError, TypeError) as error:
            raise ContractValidationError(
                f"problem operation variant has no closed errors: {key}"
            ) from error
        error_mappings: dict[str, str] = {}
        for error_variant in error_variants:
            error_properties = error_variant.get("properties", {})
            code = error_properties.get("code", {}).get("const")
            state = error_properties.get("sideEffectState", {}).get("const")
            require(
                isinstance(code, str) and state in SIDE_EFFECT_STATES,
                f"invalid problem operation error variant: {key}",
            )
            require(code not in error_mappings, f"duplicate problem operation error: {key}/{code}")
            error_mappings[code] = state
        schema_operation_mappings[key] = error_mappings
    require(
        set(schema_operation_mappings) == set(operations),
        "problem-details operation variants and registry differ",
    )
    for key, operation in operations.items():
        require(
            schema_operation_mappings[key] == operation_error_states(operation),
            f"problem-details operation mappings and registry differ: {key}",
        )


def validate_problem_schema_generator_ownership(
    problem_schema: dict[str, Any],
    registry: dict[str, Any],
    problem_catalog: dict[str, Any],
) -> None:
    prospective = build_problem_details_schema(registry, problem_catalog)
    require(
        problem_schema == prospective,
        "problem-details schema is not the deterministic downstream generator output",
    )

    catalog_mutation = deepcopy(problem_catalog)
    catalog_mutation["problems"].append(
        {
            "code": "zz_generator_mutation",
            "type": "https://problems.bytedesk.ai/agent-delivery/zz-generator-mutation",
            "status": 500,
            "retryable": False,
            "sideEffectStates": ["none"],
            "cliExit": 11,
        }
    )
    catalog_registry_mutation = deepcopy(registry)
    catalog_registry_mutation["ports"][0]["operations"][0]["errors"].append(
        {"code": "zz_generator_mutation", "sideEffectState": "none"}
    )
    catalog_projection = build_problem_details_schema(
        catalog_registry_mutation, catalog_mutation
    )
    require(
        catalog_projection != prospective
        and catalog_projection["properties"]["code"]["enum"][-1]
        == "zz_generator_mutation",
        "problem catalog additions do not change the generated problem schema",
    )

    registry_mutation = deepcopy(registry)
    registry_mutation["ports"][0]["operations"].append(
        {
            "operationId": "zz-generator-mutation",
            "errors": [
                {"code": "authentication_failed", "sideEffectState": "none"}
            ],
        }
    )
    registry_projection = build_problem_details_schema(
        registry_mutation, problem_catalog
    )
    require(
        registry_projection != prospective
        and len(registry_projection["allOf"][1]["oneOf"])
        == len(prospective["allOf"][1]["oneOf"]) + 1,
        "port registry additions do not change the generated problem schema",
    )


def validate_actions(
    action_catalog: dict[str, Any],
    action_schema: dict[str, Any],
    operations: dict[tuple[str, str], dict[str, Any]],
    problems: dict[str, dict[str, Any]],
) -> None:
    exact_keys(action_catalog, {"$schema", "profile", "version", "actions"}, "action catalog root")
    require(
        action_catalog["$schema"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/action-catalog/1.0.0",
        "action catalog schema binding drift",
    )
    require(action_catalog["profile"] == "bytedesk.action-catalog/1", "wrong action catalog profile")
    require(action_catalog["version"] == 1, "wrong action catalog version")
    require(isinstance(action_catalog["actions"], list), "actions must be an array")
    keys = {
        "kind",
        "portId",
        "operationId",
        "requestContract",
        "resultContractClass",
        "terminalResultContract",
        "ownerTask",
        "cancellableUntil",
        "idempotency",
        "failureCodes",
    }
    actions: dict[str, dict[str, Any]] = {}
    for index, action in enumerate(action_catalog["actions"]):
        require(isinstance(action, dict), f"action[{index}] must be an object")
        exact_keys(action, keys, f"action[{index}]")
        kind = action["kind"]
        require(isinstance(kind, str) and kind not in actions, f"invalid or duplicate action kind: {kind!r}")
        operation_key = (action["portId"], action["operationId"])
        require(operation_key in operations, f"action references unknown operation: {operation_key}")
        require(action["requestContract"] == operations[operation_key]["requestContract"], f"action request contract drift: {kind}")
        require(action["resultContractClass"] in RESULT_CONTRACT_CLASSES, f"unknown action result class: {kind}")
        require(action["resultContractClass"] == EXPECTED_ACTION_RESULT_CLASSES.get(kind), f"action result class drift: {kind}")
        expected_terminal_contract = f"bytedesk.action-result.{kind.replace('_', '-')}/1"
        require(action["terminalResultContract"] == expected_terminal_contract, f"terminal result contract drift: {kind}")
        require(action["ownerTask"] in REQUIRED_TASKS, f"invalid action owner task: {kind}")
        require(isinstance(action["cancellableUntil"], str) and action["cancellableUntil"], f"missing cancellation point: {kind}")
        require(isinstance(action["idempotency"], str) and action["idempotency"], f"missing action idempotency: {kind}")
        failures = unique_strings(action["failureCodes"], f"action[{kind}].failureCodes")
        require(set(failures) <= set(problems), f"action references unknown problem: {kind}")
        require(
            set(failures) <= set(operation_error_states(operations[operation_key])),
            f"action failure is not declared by its operation: {kind}",
        )
        actions[kind] = action
    try:
        schema_kinds = action_schema["properties"]["kind"]["enum"]
    except (KeyError, TypeError) as error:
        raise ContractValidationError("action schema has no properties.kind.enum") from error
    require(set(actions) == set(schema_kinds), "action catalog kinds do not align with action schema enum")
    require(list(actions) == list(schema_kinds), "action catalog order must align with action schema enum")
    result_variants = action_schema.get("properties", {}).get("result", {}).get("oneOf")
    require(isinstance(result_variants, list), "action result is not a closed union")
    schema_result_classes: set[str] = set()
    for variant in result_variants:
        try:
            schema_result_classes.add(variant["properties"]["kind"]["const"])
        except (KeyError, TypeError) as error:
            raise ContractValidationError("action result variant lacks kind discriminator") from error
    require(schema_result_classes == RESULT_CONTRACT_CLASSES, "action result classes drift from catalog")
    expected_contracts = [actions[kind]["terminalResultContract"] for kind in schema_kinds]
    result_contract_property = action_schema.get("properties", {}).get("resultContract")
    require(isinstance(result_contract_property, dict), "action schema lacks resultContract discriminator")
    require(result_contract_property.get("enum") == expected_contracts, "action resultContract enum and catalog differ")
    schema_bindings: dict[str, tuple[str, str]] = {}
    for rule in action_schema.get("allOf", []):
        try:
            rule_kind = rule["if"]["properties"]["kind"]["const"]
            contract_id = rule["then"]["properties"]["resultContract"]["const"]
            result_class = rule["then"]["properties"]["result"]["properties"]["kind"]["const"]
        except (KeyError, TypeError):
            continue
        require(rule_kind not in schema_bindings, f"duplicate action kind/result binding: {rule_kind}")
        schema_bindings[rule_kind] = (contract_id, result_class)
    expected_bindings = {
        kind: (actions[kind]["terminalResultContract"], actions[kind]["resultContractClass"])
        for kind in schema_kinds
    }
    require(schema_bindings == expected_bindings, "action schema kind/result contract bindings differ from action catalog")


def renderer_schema_ids() -> tuple[dict[str, str], list[str]]:
    files = {
        "capability": "renderer-capability.schema.json",
        "inputParameters": "renderer-input-parameters.schema.json",
        "harnessConfiguration": "harness-configuration.schema.json",
        "compatibilityResult": "renderer-compatibility-result.schema.json",
        "renderManifest": "render-manifest.schema.json",
    }
    ids: dict[str, str] = {}
    for property_name, filename in files.items():
        schema = load_json(REPOSITORY_ROOT / "contracts" / "schemas" / "v1" / filename)
        schema_id = schema.get("$id")
        require(isinstance(schema_id, str) and schema_id, f"renderer schema has no $id: {filename}")
        ids[property_name] = schema_id
    return ids, list(ids.values())


def validate_profiles(
    profile_catalog: dict[str, Any],
    registry: dict[str, Any],
    renderer_release: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    exact_keys(
        profile_catalog,
        {"$schema", "profile", "version", "profiles"},
        "protocol profile catalog root",
    )
    require(
        profile_catalog["$schema"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/protocol-profiles/1.0.0",
        "protocol profile catalog schema binding drift",
    )
    require(profile_catalog["profile"] == "bytedesk.protocol-profiles/1", "wrong profile catalog profile")
    require(profile_catalog["version"] == 1, "wrong profile catalog version")
    require(isinstance(profile_catalog["profiles"], list), "profiles must be an array")
    profile_keys = {"profileId", "ownerTask", "repoPaths", "requirements"}
    profiles: dict[str, dict[str, Any]] = {}
    for index, profile in enumerate(profile_catalog["profiles"]):
        require(isinstance(profile, dict), f"profile[{index}] must be an object")
        exact_keys(profile, profile_keys, f"profile[{index}]")
        profile_id = profile["profileId"]
        require(isinstance(profile_id, str) and profile_id not in profiles, f"invalid or duplicate profile ID: {profile_id!r}")
        require(profile["ownerTask"] in REQUIRED_TASKS, f"invalid profile owner task: {profile_id}")
        validate_repository_paths(profile["repoPaths"], f"{profile_id}.repoPaths")
        require(isinstance(profile["requirements"], dict), f"profile requirements must be object: {profile_id}")
        profiles[profile_id] = profile
    require(set(profiles) == set(REQUIRED_PROFILE_KEYS), "required profile ID set differs")
    referenced_profiles: set[str] = set()
    for port in registry["ports"]:
        port_profiles = set(port["protocolProfiles"])
        require(
            port_profiles <= set(profiles),
            f"{port['portId']} references unknown protocol profiles: "
            f"{sorted(port_profiles - set(profiles))}",
        )
        referenced_profiles.update(port_profiles)
    require(
        referenced_profiles == set(profiles),
        "protocol profiles are not all assigned to at least one port; "
        f"unassigned={sorted(set(profiles) - referenced_profiles)}",
    )
    for profile_id, keys in REQUIRED_PROFILE_KEYS.items():
        exact_keys(profiles[profile_id]["requirements"], keys, f"{profile_id}.requirements")

    worker = profiles["bytedesk.worker-framing/1"]["requirements"]
    require(worker["framing"] == "uint32-be-length-prefixed", "worker framing drift")
    require(worker["payloadEncoding"] == "rfc8785-jcs-json", "worker encoding drift")
    require(worker["oneRequestPerProcess"] is True, "worker process cardinality drift")
    require(worker["network"] == "denied" and worker["secrets"] == "none", "worker isolation weakened")
    require(worker["maxRequestBytes"] == worker["maxResponseBytes"] == 4194304, "worker frame bounds drift")
    require(
        worker["workerStdin"] == "launcher-private-anonymous-pipe-single-framed-request"
        and worker["workerStdout"] == "launcher-private-anonymous-pipe-single-framed-response-and-eof"
        and worker["workerStderr"] == "launcher-private-anonymous-pipe-bounded-untrusted-diagnostics-to-output-file",
        "worker private-pipe topology drift",
    )
    require(
        worker["launcherContainerStdout"] == "empty-or-fixed-non-content-lifecycle-codes"
        and worker["launcherContainerStderr"] == "empty-or-fixed-non-content-lifecycle-codes"
        and worker["contentStreamIsolation"]
        == "renderer-response-and-diagnostics-never-reach-cri-node-kubernetes-event-or-telemetry-logs",
        "worker content reached a container or platform logging stream",
    )
    require(
        worker["diagnosticHandling"]
        == "bounded-untrusted-private-output-file-hash-redact-evidence-destroy-with-attempt",
        "worker diagnostic handling drift",
    )
    require(
        worker["inheritedFileDescriptors"]
        == "closed-except-launcher-private-worker-pipes-and-launcher-owned-directories",
        "worker inherited descriptor boundary drift",
    )
    require(
        worker["failureMapping"].get("containerStreamContent") == "artifact_unsafe",
        "worker container-stream leakage is not fail-closed",
    )

    oci = profiles["bytedesk.oci-archive-layout/1"]["requirements"]
    require(oci["referenceAuthority"] == "repository-plus-sha256-digest-only", "OCI authority is not digest-only")
    require(oci["tagAndChannelUse"] == "discovery-only", "OCI tag authority drift")
    require(oci["rejectLinksAndSpecialFiles"] is True, "archive links/special files must be rejected")
    require(oci["archiveRootMutation"] == "absent-create-or-exact-revision-plus-digest-match", "archive CAS drift")

    pins = profiles["bytedesk.supply-chain-pins/1"]["requirements"]
    selectors = set(unique_strings(pins["forbiddenSelectors"], "supply-chain forbidden selectors"))
    require({"latest", "branch-head", "path-binary", "floating-range"} <= selectors, "supply-chain pin denials incomplete")
    require(pins["unavailableBehavior"] == "fail-closed-with-no-fallback", "supply-chain fallback is not closed")

    schema_ids_by_property, promised_schema_ids = renderer_schema_ids()
    try:
        release_properties = renderer_release["properties"]["schemas"]
        release_required = release_properties["required"]
        release_declared = set(release_properties["properties"])
    except (KeyError, TypeError) as error:
        raise ContractValidationError("renderer release has no closed schemas promise") from error
    require(list(release_required) == list(schema_ids_by_property), "renderer release promised property order/set drift")
    require(release_declared == set(schema_ids_by_property), "renderer release schema promise is not closed")
    renderer_profile = profiles["bytedesk.renderer-contract/1"]["requirements"]
    require(renderer_profile["promisedSchemaIds"] == promised_schema_ids, "renderer profile promised schema IDs drift")
    require(renderer_profile["executeArtifactContent"] is False, "renderer profile permits artifact execution")
    require(renderer_profile["invocation"] == "bytedesk.worker-framing/1", "renderer worker profile drift")
    renderer_ports = {
        "bytedesk.port.renderer-strategy/1",
        "bytedesk.port.renderer-adapter/1",
    }
    for port in registry["ports"]:
        if port["portId"] in renderer_ports:
            require(port["promisedSchemas"] == promised_schema_ids, f"renderer port schema promises drift: {port['portId']}")
        else:
            require(
                not (set(port["promisedSchemas"]) & set(promised_schema_ids)),
                f"non-renderer port promises renderer-contract schemas: {port['portId']}",
            )

    desired = profiles["bytedesk.desired-state-store/1"]["requirements"]
    require(desired["selectedStoreCardinality"] == "exactly-one-per-consumer-runtime-target", "desired store cardinality drift")
    require(desired["soleLogicalWriter"] == "Promotion Coordinator", "desired store writer drift")
    require(desired["createPrecondition"] == {"kind":"absent","omission":"reject","null":"reject"}, "create CAS profile drift")
    update = desired["updatePrecondition"]
    require(update["kind"] == "match" and update["required"] == ["exactRevision", "exactDigest"], "update CAS profile drift")
    require(all(update[key] == "reject" for key in ("wildcard", "force", "digestOnly")), "weak update CAS is permitted")
    require(desired["migration"]["dualWrite"] is False and desired["migration"]["checkpointed"] is True, "desired store migration profile drift")
    return profiles


def validate_event_profile(
    profiles: dict[str, dict[str, Any]], event_registry: dict[str, Any]
) -> None:
    exact_keys(
        event_registry,
        {
            "$schema",
            "profile",
            "cloudEventsVersion",
            "delivery",
            "ordering",
            "authority",
            "registryCompatibility",
            "resynchronization",
            "eventTypes",
        },
        "event registry root",
    )
    require(
        event_registry["$schema"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/event-types/1.0.0",
        "event registry schema binding drift",
    )
    require(isinstance(event_registry.get("eventTypes"), list), "event registry eventTypes must be an array")
    event_names: list[str] = []
    schema_ids: list[str] = []
    for index, event in enumerate(event_registry["eventTypes"]):
        require(isinstance(event, dict), f"eventTypes[{index}] must be an object")
        require(isinstance(event.get("type"), str) and event["type"], f"event type missing at index {index}")
        require(isinstance(event.get("resourceSchemaId"), str) and event["resourceSchemaId"], f"event resource schema missing at index {index}")
        event_names.append(event["type"])
        schema_ids.append(event["resourceSchemaId"])
    require(len(event_names) == len(set(event_names)), "duplicate event type")
    api = profiles["bytedesk.api-events/1"]["requirements"]
    require(api["cloudEventsVersion"] == event_registry["cloudEventsVersion"], "CloudEvents version drift")
    require(api["delivery"] == event_registry["delivery"], "event delivery drift")
    require(api["ordering"] == event_registry["ordering"], "event ordering drift")
    require(api["authority"] == event_registry["authority"], "event authority drift")
    require(api["eventTypes"] == event_names, "protocol profile and event registry differ")
    known_schema_ids: set[str] = set()
    for path in (REPOSITORY_ROOT / "contracts" / "schemas" / "v1").glob("*.schema.json"):
        schema = load_json(path)
        if isinstance(schema.get("$id"), str):
            known_schema_ids.add(schema["$id"])
    require(set(schema_ids) <= known_schema_ids, "event registry references unknown resource schema ID")
    require(api["sse"]["allowedOnlyOn"] == "event-subscription", "Last-Event-ID is not scoped to subscription")
    require(api["unknownSchema"] == api["sequenceGap"] == "stop-projection-and-resynchronize", "event resync rule drift")


def validate_profile_semantics(
    profiles: dict[str, dict[str, Any]], registry: dict[str, Any]
) -> None:
    coordinator = profiles["bytedesk.promotion-coordinator/1"]["requirements"]
    require(coordinator["soleWriter"] == "Promotion Coordinator", "coordinator sole-writer drift")
    isolated = coordinator["isolatedCandidateOrdering"]
    guarded = coordinator["guardedInPlaceOrdering"]
    require(isolated.index("dispatch-nonce-bound-capability-check") < isolated.index("authorize-activation") < isolated.index("atomic-switch"), "isolated candidate capability/switch order drift")
    require(guarded.index("atomic-switch") < guarded.index("dispatch-nonce-bound-capability-check") < guarded.index("compare-and-swap-target-state"), "guarded-in-place capability/CAS order drift")
    require(coordinator["managedCommitPoint"] == "successful-target-delivery-state-cas", "coordinator commit point drift")
    require(set(coordinator["crashRecovery"]) == {"beforeRemoteCommit","commitResponseLost","afterHostSwitchBeforeDesiredCas","afterDesiredCasBeforeReceipt","staleCoordinator"}, "coordinator crash matrix incomplete")

    host = profiles["bytedesk.host-switch-journal/1"]["requirements"]
    require(host["phases"].index("switch_intent_durable") < host["phases"].index("switched") < host["phases"].index("readback_verified"), "host switch journal order drift")
    require(set(host["crashDisposition"]) == {"beforeIntent","afterIntentBeforeSwitch","duringSwitch","afterSwitchBeforeMarker","afterMarkerBeforeObservation","staleAttempt"}, "host crash matrix incomplete")
    require("fsync" in host["durability"], "host journal durability does not require fsync")
    require(
        host["cleanup"]
        == "never-delete-any-active-graph-subject-predecessor-required-evidence-or-unresolved-attempt-output",
        "host cleanup safety drift",
    )

    capability = profiles["bytedesk.capability-verification/1"]["requirements"]
    require(capability["dispatchActor"] == "Promotion Coordinator", "capability dispatch actor drift")
    require("host-reconciler" in capability["forbiddenDispatchActors"], "host can dispatch capability check")
    require(
        capability["bindingFields"]
        == [
            "consumerId",
            "targetId",
            "candidateDigest",
            "checkProfileDigest",
            "dispatchNonce",
            "authorizationDecisionDigest",
            "issuedAt",
            "expiresAt",
        ],
        "capability exact binding fields drift",
    )
    require(
        capability["chainBindings"]
        == {
            "dispatchReceiptFields": [
                "checkId", "requestDigest", "consumerId", "targetId",
                "candidateDigest", "checkProfileDigest", "nonce",
                "authorizationDecisionDigest", "endpoint",
                "coordinatorFencingToken", "issuedAt", "expiresAt",
            ],
            "verificationRequestFields": [
                "dispatchReceipt", "dispatchReceiptDigest",
                "capabilityEvidence", "verificationProofs",
                "authenticatedEvidence", "expectations", "receivedAt",
            ],
            "evidenceDispatchFields": [
                "requestDigest", "receiptDigest", "checkProfileDigest",
                "authorizationDecisionDigest",
            ],
            "acceptedResultFields": [
                "acceptedEvidenceDigest", "policyOutcome", "freshUntil",
            ],
            "comparison": "exact-jcs-sha256-and-field-equality",
            "mismatch": "evidence_invalid",
        },
        "capability proof/request/receipt/evidence/accepted chain profile drift",
    )
    required_rows = {
        (
            row["workloadLogin"],
            row["requiredCapability"],
            row["deniedSentinel"],
        ): row["outcome"]
        for row in capability["outcomeDerivation"]
        if row["mode"] == "required"
    }
    expected_required_rows = {
        (workload, required, sentinel): (
            "permitted"
            if (workload, required, sentinel)
            == ("passed", "permitted", "policy_denied")
            else "denied"
        )
        for workload in ("passed", "failed")
        for required in ("permitted", "policy_denied")
        for sentinel in ("permitted", "policy_denied")
    }
    require(
        required_rows == expected_required_rows,
        "required capability outcome derivation is not a closed truth table",
    )
    not_applicable_rows = {
        row["certifiedResult"]: row["outcome"]
        for row in capability["outcomeDerivation"]
        if row["mode"] == "certified_not_applicable"
    }
    require(
        not_applicable_rows
        == {"not_applicable": "permitted", "failed": "denied"},
        "not-applicable capability outcome derivation is not closed",
    )
    require(
        capability["failureMapping"]
        == {
            "invalid_inputs": "evidence_invalid",
            "invalid_contract": "evidence_invalid",
            "binding_mismatch": "evidence_invalid",
            "stale_evidence": "evidence_invalid",
            "permit_authorization_proof_missing": "evidence_invalid",
            "permit_authorization_decision_mismatch": "evidence_invalid",
            "host_canary_check_failed": "evidence_invalid",
            "workload_login_failed": "evidence_invalid",
            "not_applicable_check_failed": "evidence_invalid",
            "uncertified_not_applicable": "evidence_invalid",
            "signer_mismatch": "trust_verification_failed",
            "unauthenticated_evidence": "trust_verification_failed",
            "unauthenticated_authorization_proof": "trust_verification_failed",
            "capability_denial_not_proven": "capability_denial_not_proven",
            "authorization_transport_failure": "capability_transport_failed",
        },
        "canary internal-to-public problem mapping drift",
    )
    require(capability["outcomes"] == ["permitted", "denied"], "capability domain result set/order drift")
    require(
        {
            "timeout",
            "connection-failure",
            "missing-result",
            "malformed-result",
            "expired-result",
            "unknown-signer",
        }
        <= set(capability["notDenial"]),
        "false-denial protection incomplete",
    )
    capability_port = next(
        port
        for port in registry["ports"]
        if port["portId"] == "bytedesk.port.capability-verifier/1"
    )
    capability_operations = {
        operation["operationId"]: operation
        for operation in capability_port["operations"]
    }
    dispatch = capability_operations["dispatch-capability-check"]
    require(
        [field["name"] for field in dispatch["requestFields"]]
        == [
            "consumerId",
            "targetId",
            "candidateDigest",
            "checkProfileDigest",
            "dispatchNonce",
            "authorizationDecisionProof",
            "authorizationDecisionDigest",
            "issuedAt",
            "expiresAt",
        ],
        "capability dispatch request and profile binding fields differ",
    )
    verify = capability_operations["verify-capability-result"]
    require(
        [field["name"] for field in verify["requestFields"]]
        == [
            "dispatchReceipt",
            "dispatchReceiptDigest",
            "capabilityEvidence",
            "verificationProofs",
            "authenticatedEvidence",
            "expectations",
            "receivedAt",
        ],
        "capability verification request shape drift",
    )
    require(
        verify["requestFields"][0]["schemaRef"]
        == "bytedesk.port.capability-dispatch-receipt/1",
        "capability verification omits the exact dispatch receipt",
    )
    evidence_field = verify["requestFields"][2]
    require(
        evidence_field["schemaRef"] == "canary-evidence"
        and evidence_field["type"] == "object",
        "capability verification does not consume the canonical evidence envelope",
    )
    require(
        verify["requestFields"][3]["schemaRef"]
        == "bytedesk.port.capability-verification-proof-set/1"
        and verify["requestFields"][4]["schemaRef"]
        == "bytedesk.port.capability-authenticated-evidence-set/1"
        and verify["requestFields"][5]["schemaRef"]
        == "bytedesk.port.capability-verification-expectations/1",
        "capability verification omits proof, independent authentication, or trusted expectations",
    )
    require(
        set(operation_error_states(verify))
        == {
            "evidence_invalid",
            "capability_transport_failed",
            "capability_denial_not_proven",
            "trust_verification_failed",
        },
        "capability operation problems drift from non-domain outcomes",
    )

    renderer_ports = {
        port["portId"]: {
            operation["operationId"]: operation
            for operation in port["operations"]
        }
        for port in registry["ports"]
        if port["portId"]
        in {
            "bytedesk.port.renderer-strategy/1",
            "bytedesk.port.renderer-adapter/1",
            "bytedesk.port.renderer-sandbox/1",
        }
    }
    select_renderer = renderer_ports["bytedesk.port.renderer-strategy/1"]["select-renderer"]
    require(
        [field["name"] for field in select_renderer["requestFields"]]
        == [
            "targetHarness",
            "targetHarnessVersion",
            "targetPlatform",
            "productReleaseDescriptor",
            "releaseQualificationDescriptor",
            "productReleaseStatusDescriptor",
            "productReleaseStatusCheckpointDescriptor",
            "productReleaseStatusCheckpointAuthenticationEvidenceDescriptor",
            "productReleaseStatusRequestNonce",
            "rendererReleaseStatusDescriptor",
            "rendererReleaseStatusCheckpointDescriptor",
            "rendererReleaseStatusCheckpointAuthenticationEvidenceDescriptor",
            "rendererReleaseStatusRequestNonce",
            "productDistributionDescriptor",
            "compiledAllowlistDescriptor",
            "capabilityDescriptor",
            "rendererReleaseDescriptor",
            "allowlistDigest",
        ],
        "renderer selection request omits release, qualification, status, capability, or allowlist authority",
    )
    select_renderer_fields = {
        field["name"]: field for field in select_renderer["requestFields"]
    }
    artifact_descriptor_refs = {
        "common#/$defs/artifactDescriptor",
        "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0#/$defs/artifactDescriptor",
    }
    require(
        select_renderer_fields["targetPlatform"]["schemaRef"]
        == "primitive:string"
        and all(
            select_renderer_fields[name]["schemaRef"]
            in artifact_descriptor_refs
            for name in (
                "productReleaseDescriptor",
                "releaseQualificationDescriptor",
                "productReleaseStatusDescriptor",
                "productReleaseStatusCheckpointDescriptor",
                "productReleaseStatusCheckpointAuthenticationEvidenceDescriptor",
                "rendererReleaseStatusDescriptor",
                "rendererReleaseStatusCheckpointDescriptor",
                "rendererReleaseStatusCheckpointAuthenticationEvidenceDescriptor",
                "productDistributionDescriptor",
                "compiledAllowlistDescriptor",
                "capabilityDescriptor",
                "rendererReleaseDescriptor",
            )
        )
        and select_renderer_fields["productReleaseStatusRequestNonce"][
            "schemaRef"
        ]
        == "common#/$defs/nonce"
        and select_renderer_fields["rendererReleaseStatusRequestNonce"][
            "schemaRef"
        ]
        == "common#/$defs/nonce"
        and select_renderer_fields["allowlistDigest"]["schemaRef"]
        == "common#/$defs/digest",
        "renderer selection target platform or release descriptor is not exact",
    )
    require(
        [field["name"] for field in select_renderer["resultFields"]]
        == ["selection"],
        "renderer selection result is not one closed authority object",
    )
    require(
        select_renderer["resultFields"][0]["schemaRef"] == "renderer-selection",
        "renderer selection result does not use renderer-selection/1",
    )

    strategy_render = renderer_ports["bytedesk.port.renderer-strategy/1"]["render"]
    require(
        [field["name"] for field in strategy_render["requestFields"]]
        == [
            "rendererSelection",
            "attemptAuthority",
            "attemptAuthenticationEvidence",
            "framedRequest",
        ],
        "renderer Strategy render request loses selection, attempt authority, authentication, or exact frame",
    )
    require(
        strategy_render["requestFields"][0]["schemaRef"]
        == "renderer-selection"
        and strategy_render["requestFields"][1]["schemaRef"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-attempt-authority/1.0.0"
        and strategy_render["requestFields"][2]["schemaRef"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-attempt-authentication-evidence/1.0.0"
        and strategy_render["requestFields"][3]["schemaRef"]
        == "primitive:bounded-bytes",
        "renderer Strategy render does not consume exact authenticated attempt inputs",
    )
    require(
        [field["name"] for field in strategy_render["resultFields"]]
        == [
            "outputArchive",
            "outputArchiveDigest",
            "outputArchiveSize",
            "renderManifest",
            "renderDigest",
            "outputTreeDigest",
            "executionReceipt",
            "executionReceiptDigest",
            "executionAuthenticationEvidence",
        ],
        "renderer Strategy result omits authenticated execution readback",
    )

    adapter_render = renderer_ports["bytedesk.port.renderer-adapter/1"]["render"]
    require(
        [field["name"] for field in adapter_render["requestFields"]]
        == [
            "rendererSelection",
            "attemptAuthority",
            "attemptAuthenticationEvidence",
            "framedRequest",
        ],
        "renderer Adapter request loses selection, attempt authority, authentication, or exact frame",
    )
    require(
        [field["name"] for field in adapter_render["resultFields"]]
        == [
            "framedResponse",
            "outputTreeDigest",
            "outputArchive",
            "outputArchiveDigest",
            "outputArchiveSize",
            "renderManifest",
            "renderManifestDigest",
            "executionReceipt",
            "executionReceiptDigest",
            "executionAuthenticationEvidence",
        ],
        "renderer Adapter result omits authenticated execution readback",
    )

    validate_output = renderer_ports["bytedesk.port.renderer-adapter/1"]["validate-output"]
    require(
        [field["name"] for field in validate_output["requestFields"]]
        == [
            "rendererSelection",
            "attemptAuthority",
            "attemptAuthenticationEvidence",
            "framedRequest",
            "framedResponse",
            "outputArchive",
            "outputArchiveDigest",
            "outputArchiveSize",
            "outputTreeDigest",
            "renderManifest",
            "executionReceipt",
            "executionReceiptDigest",
            "executionAuthenticationEvidence",
        ],
        "renderer output validation cannot cross-check authenticated execution",
    )

    sandbox_execute = renderer_ports["bytedesk.port.renderer-sandbox/1"]["execute-renderer"]
    require(
        [field["name"] for field in sandbox_execute["requestFields"]]
        == [
            "rendererSelection",
            "attemptAuthority",
            "attemptAuthenticationEvidence",
            "framedRequest",
            "deadlineMilliseconds",
        ],
        "renderer sandbox request permits bare executable or ambient selection",
    )
    require(
        [field["name"] for field in sandbox_execute["resultFields"]]
        == [
            "framedResponse",
            "outputTreeDigest",
            "outputArchive",
            "outputArchiveDigest",
            "outputArchiveSize",
            "renderManifest",
            "renderManifestDigest",
            "boundedDiagnostics",
            "executionReceipt",
            "executionReceiptDigest",
            "executionAuthenticationEvidence",
        ],
        "renderer sandbox result omits authenticated actual-execution identity",
    )
    for operation, field_name in (
        (strategy_render, "rendererSelection"),
        (adapter_render, "rendererSelection"),
        (validate_output, "rendererSelection"),
        (sandbox_execute, "rendererSelection"),
    ):
        field = next(field for field in operation["requestFields"] if field["name"] == field_name)
        require(
            field["schemaRef"] == "renderer-selection" and field["type"] == "object",
            "renderer selection is not carried as one closed object",
        )
    for operation in (strategy_render, adapter_render, sandbox_execute):
        receipt = next(field for field in operation["resultFields"] if field["name"] == "executionReceipt")
        evidence = next(
            field
            for field in operation["resultFields"]
            if field["name"] == "executionAuthenticationEvidence"
        )
        require(
            receipt["schemaRef"] == "renderer-execution-receipt"
            and evidence["schemaRef"]
            == "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-execution-authentication-evidence/1.0.0",
            "renderer execution readback is not a closed receipt plus exact authentication evidence",
        )

    selection = load_json(RENDERER_SELECTION_FIXTURE_PATH)
    require(
        selection["selectionDigest"]
        == canonical_digest(renderer_selection_preimage(selection)),
        "renderer selection digest is not bound to the complete domain-separated authority",
    )
    execution_receipt = load_json(RENDERER_EXECUTION_RECEIPT_FIXTURE_PATH)
    require(
        execution_receipt["selectionDigest"] == selection["selectionDigest"]
        and execution_receipt["rendererReleaseDigest"]
        == selection["rendererRelease"]["digest"]
        and execution_receipt["platform"] == selection["targetPlatform"]
        and execution_receipt["executedDistribution"]
        == selection["executableDistribution"]
        and execution_receipt["workerProfileDigest"]
        == selection["workerProfileDigest"],
        "renderer execution receipt does not read back the exact selection",
    )

    consumer_authority_port = next(
        port
        for port in registry["ports"]
        if port["portId"] == "bytedesk.port.consumer-authority-approval/1"
    )
    authority_operations = {
        operation["operationId"]: operation
        for operation in consumer_authority_port["operations"]
    }
    resolve_authority = authority_operations["resolve-authority-snapshot"]
    resolve_skill_approval = authority_operations["resolve-skill-approval"]
    verify_private_authority = authority_operations["verify-private-authority"]
    require(
        [field["name"] for field in resolve_authority["requestFields"]]
        == [
            "consumerId",
            "subjectId",
            "installationId",
            "harnessId",
            "targetId",
            "audience",
            "operation",
            "authorizedPrivateInputDigest",
            "candidate",
            "binding",
            "desiredRevisionDigest",
            "policyDigests",
            "nonce",
            "verificationTime",
        ],
        "authority resolution cannot select the exact current compile authority",
    )
    require(
        next(
            field
            for field in resolve_authority["requestFields"]
            if field["name"] == "authorizedPrivateInputDigest"
        )["required"]
        is False,
        "authorized private input digest must be compile-conditional",
    )
    require(
        [field["name"] for field in resolve_authority["resultFields"]]
        == [
            "consumerAuthority",
            "authorityDescriptor",
            "authoritySigningResult",
            "authorityDigest",
        ],
        "authority resolution omits exact bytes or signature evidence",
    )
    require(
        {
            field["name"]: field["schemaRef"]
            for field in resolve_authority["requestFields"]
        }["candidate"]
        == "bytedesk.port.consumer-authority-candidate-descriptor/1"
        and {
            field["name"]: field["schemaRef"]
            for field in resolve_authority["requestFields"]
        }["binding"]
        == "bytedesk.port.consumer-authority-binding-descriptor/1",
        "authority resolution accepts untyped candidate or binding descriptors",
    )
    require(
        {"resource_not_found", "dependency_unavailable"}
        <= {error["code"] for error in resolve_authority["errors"]}
        and "never issues authority" in resolve_authority["idempotency"],
        "authority no-match, indeterminate publication, or no-issuance semantics are absent",
    )
    require(
        [field["name"] for field in resolve_skill_approval["requestFields"]]
        == [
            "consumerId",
            "subjectId",
            "installationId",
            "harnessId",
            "targetId",
            "operation",
            "skill",
            "nonce",
            "verificationTime",
        ]
        and [field["name"] for field in resolve_skill_approval["resultFields"]]
        == [
            "skillApproval",
            "approvalDescriptor",
            "approvalSigningResult",
            "approvalDigest",
        ],
        "skill approval resolution is not exact, scoped, current, and signed",
    )
    require(
        next(
            field
            for field in resolve_skill_approval["requestFields"]
            if field["name"] == "skill"
        )["schemaRef"]
        == "bytedesk.port.consumer-skill-descriptor/1"
        and {"resource_not_found", "dependency_unavailable"}
        <= {error["code"] for error in resolve_skill_approval["errors"]},
        "skill approval resolution accepts a digest-only skill or collapses no-match into outage",
    )
    require(
        [field["name"] for field in verify_private_authority["requestFields"]]
        == [
            "privateCompilationInput",
            "consumerAuthority",
            "authorityDescriptor",
            "authoritySigningResult",
            "skillApprovals",
            "approvalDescriptors",
            "approvalSigningResults",
            "verificationTime",
        ],
        "private authority verification still accepts digest-only inputs",
    )
    verify_schema_refs = {
        field["name"]: field["schemaRef"]
        for field in verify_private_authority["requestFields"]
    }
    require(
        verify_schema_refs["privateCompilationInput"] == "private-compilation-input"
        and verify_schema_refs["consumerAuthority"] == "consumer-authority"
        and verify_schema_refs["skillApprovals"] == "skill-approval"
        and verify_schema_refs["authorityDescriptor"]
        == "bytedesk.port.consumer-authority-descriptor/1"
        and verify_schema_refs["approvalDescriptors"]
        == "bytedesk.port.skill-approval-descriptor/1",
        "private authority verification schemas do not carry complete closed objects and role descriptors",
    )
    require(
        "authority_denied"
        in {error["code"] for error in verify_private_authority["errors"]},
        "private-authority denial is not a terminal operation error",
    )
    require(
        "permitted" in verify_private_authority["authorization"]
        and "authorizedPrivateInputDigest"
        in verify_private_authority["authorization"],
        "private-authority success does not require a permitted signed input digest",
    )

    private_compiler = next(
        port
        for port in registry["ports"]
        if port["portId"] == "bytedesk.port.private-compiler/1"
    )
    private_operations = {
        operation["operationId"]: operation
        for operation in private_compiler["operations"]
    }
    compile_private = private_operations["compile-private-deployment"]
    require(
        [field["name"] for field in compile_private["requestFields"]]
        == ["compilationInput", "idempotencyKey", "compileRequestDigest"],
        "private compile request is not one complete lock plus recoverable idempotency identity",
    )
    require(
        compile_private["requestFields"][0]["schemaRef"]
        == "private-compilation-input"
        and compile_private["requestFields"][0]["type"] == "object",
        "private compile request does not consume the closed input lock",
    )
    require(
        [field["name"] for field in compile_private["resultFields"]]
        == [
            "compileRequestDigest",
            "compilationInputDescriptor",
            "consumerDeploymentDescriptor",
            "compilationEvidenceDescriptor",
        ],
        "private compile result does not return the exact lock, deployment, and evidence descriptors",
    )
    require(
        [field["schemaRef"] for field in compile_private["resultFields"][1:]]
        == [
            "bytedesk.port.private-compilation-input-descriptor/1",
            "bytedesk.port.consumer-deployment-descriptor/1",
            "bytedesk.port.private-compilation-evidence-descriptor/1",
        ],
        "private compile artifact descriptors are not role-, media-, and trust-purpose constrained",
    )
    resolve_compile = private_operations["resolve-compile-attempt"]
    require(
        [field["name"] for field in resolve_compile["requestFields"]]
        == ["consumerId", "idempotencyKey", "compileRequestDigest"],
        "private compile resolution cannot address the exact original request",
    )
    require(
        [field["name"] for field in resolve_compile["resultFields"]]
        == [
            "resolution",
            "compileRequestDigest",
            "artifacts",
            "problem",
        ],
        "private compile resolution does not return all committed descriptors or a closed failure",
    )

    compilation_lock = load_json(PRIVATE_COMPILATION_INPUT_FIXTURE_PATH)
    locked_inputs = compilation_lock["inputs"]
    compile_authority = load_json(CONSUMER_AUTHORITY_COMPILE_FIXTURE_PATH)
    require(
        set(locked_inputs["runtimeSlot"]) == {"slotId", "generation"}
        and locked_inputs["activationMode"]
        in {"isolated_candidate", "guarded_in_place"},
        "private compilation lock does not freeze runtime slot and activation mode",
    )

    def validate_compile_authority_binding(
        authority: dict[str, Any], inputs: dict[str, Any]
    ) -> None:
        require(
            authority["operation"] == "compile",
            "compile authority has the wrong operation",
        )
        require(
            authority["decision"]["class"] == "permitted",
            "compile authority decision is not permitted",
        )
        require(
            authority["authorizedPrivateInputDigest"]
            == inputs["authorizedPrivateInputDigest"],
            "compile authority signed input digest mismatch",
        )
        require(
            {
                "consumerId": authority["consumerId"],
                "subjectId": authority["subjectId"],
                "installationId": authority["installationId"],
                "harnessId": authority["harnessId"],
                "targetId": authority["targetId"],
            }
            == {
                key: inputs[key]
                for key in (
                    "consumerId",
                    "subjectId",
                    "installationId",
                    "harnessId",
                    "targetId",
                )
            }
            and authority["predecessor"] == inputs["predecessor"]
            and authority["bindingDigest"] == inputs["binding"]["digest"]
            and authority["candidateDigest"] == inputs["candidate"]["digest"]
            and authority["desiredRevisionDigest"]
            == inputs["desiredRevision"]["digest"]
            and authority["opaqueDigests"] == inputs["policyDigests"],
            "compile authority identity or policy digest mismatch",
        )
        authority_bytes = rfc8785.dumps(authority)
        require(
            inputs["authoritySnapshot"]["digest"] == canonical_digest(authority)
            and inputs["authoritySnapshot"]["size"] == len(authority_bytes),
            "private compilation authority descriptor does not resolve to the signed compile authority",
        )

    validate_compile_authority_binding(compile_authority, locked_inputs)
    authority_denials: list[tuple[str, dict[str, Any], str]] = []
    mismatched_input = deepcopy(compile_authority)
    mismatched_input["authorizedPrivateInputDigest"] = f"sha256:{'0' * 64}"
    authority_denials.append(
        (
            "signed-input-digest-mismatch",
            mismatched_input,
            "compile authority signed input digest mismatch",
        )
    )
    denied_authority = deepcopy(compile_authority)
    denied_authority["decision"]["class"] = "denied"
    authority_denials.append(
        (
            "denied-decision",
            denied_authority,
            "compile authority decision is not permitted",
        )
    )
    mismatched_policy = deepcopy(compile_authority)
    mismatched_policy["opaqueDigests"]["policy"] = f"sha256:{'0' * 64}"
    authority_denials.append(
        (
            "policy-subdigest-mismatch",
            mismatched_policy,
            "compile authority identity or policy digest mismatch",
        )
    )
    mismatched_predecessor = deepcopy(compile_authority)
    mismatched_predecessor["predecessor"]["digest"] = f"sha256:{'0' * 64}"
    authority_denials.append(
        (
            "predecessor-mismatch",
            mismatched_predecessor,
            "compile authority identity or policy digest mismatch",
        )
    )
    for denial_id, mutated_authority, expected_error in authority_denials:
        try:
            validate_compile_authority_binding(mutated_authority, locked_inputs)
        except ContractValidationError as error:
            require(
                str(error) == expected_error,
                f"private authority denial {denial_id} failed for the wrong reason: {error}",
            )
        else:
            raise ContractValidationError(
                f"private authority semantic denial was accepted: {denial_id}"
            )

    changed_inputs = deepcopy(locked_inputs)
    changed_inputs["customizationDigest"] = f"sha256:{'0' * 64}"
    changed_authorized_preimage = deepcopy(changed_inputs)
    changed_authorized_preimage.pop("inputAuthentication", None)
    changed_authorized_preimage.pop("authoritySnapshot")
    changed_authorized_preimage.pop("authorizedPrivateInputDigest")
    changed_inputs["authorizedPrivateInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.authorized-private-compilation-input/1",
            "contract": compilation_lock["contract"],
            "schema": compilation_lock["schema"],
            "inputs": changed_authorized_preimage,
        }
    )
    changed_authority = deepcopy(compile_authority)
    changed_authority["authorizedPrivateInputDigest"] = changed_inputs[
        "authorizedPrivateInputDigest"
    ]
    changed_authority_bytes = rfc8785.dumps(changed_authority)
    changed_inputs["authoritySnapshot"]["digest"] = canonical_digest(
        changed_authority
    )
    changed_inputs["authoritySnapshot"]["size"] = len(changed_authority_bytes)
    changed_lock = deepcopy(compilation_lock)
    changed_lock["inputs"] = changed_inputs
    changed_lock["compilationInputDigest"] = canonical_digest(
        {
            "profile": "bytedesk.private-compilation-input-digest/1",
            "contract": changed_lock["contract"],
            "schema": changed_lock["schema"],
            "inputs": changed_inputs,
        }
    )
    validate_compile_authority_binding(changed_authority, changed_inputs)
    require(
        changed_inputs["authorizedPrivateInputDigest"]
        != locked_inputs["authorizedPrivateInputDigest"]
        and changed_inputs["authoritySnapshot"]["digest"]
        != locked_inputs["authoritySnapshot"]["digest"]
        and changed_lock["compilationInputDigest"]
        != compilation_lock["compilationInputDigest"],
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
        mutated_lock = deepcopy(compilation_lock)
        mutate(mutated_lock)
        mutated_inputs = mutated_lock["inputs"]
        authorized_preimage = deepcopy(mutated_inputs)
        authorized_preimage.pop("inputAuthentication", None)
        authorized_preimage.pop("authoritySnapshot")
        authorized_preimage.pop("authorizedPrivateInputDigest")
        mutated_inputs["authorizedPrivateInputDigest"] = canonical_digest(
            {
                "profile": "bytedesk.authorized-private-compilation-input/1",
                "contract": mutated_lock["contract"],
                "schema": mutated_lock["schema"],
                "inputs": authorized_preimage,
            }
        )
        mutated_authority = deepcopy(compile_authority)
        mutated_authority["authorizedPrivateInputDigest"] = mutated_inputs[
            "authorizedPrivateInputDigest"
        ]
        authority_bytes = rfc8785.dumps(mutated_authority)
        mutated_inputs["authoritySnapshot"]["digest"] = canonical_digest(
            mutated_authority
        )
        mutated_inputs["authoritySnapshot"]["size"] = len(authority_bytes)
        mutated_lock["compilationInputDigest"] = canonical_digest(
            {
                "profile": "bytedesk.private-compilation-input-digest/1",
                "contract": mutated_lock["contract"],
                "schema": mutated_lock["schema"],
                "inputs": mutated_inputs,
            }
        )
        require(
            mutated_inputs["authorizedPrivateInputDigest"]
            != locked_inputs["authorizedPrivateInputDigest"]
            and mutated_inputs["authoritySnapshot"]["digest"]
            != locked_inputs["authoritySnapshot"]["digest"]
            and mutated_lock["compilationInputDigest"]
            != compilation_lock["compilationInputDigest"],
            f"private {mutation_name} did not invalidate authority and lock identity",
        )
    locked_selection = locked_inputs["rendererSelection"]
    locked_selection_preimage = renderer_selection_preimage(locked_selection)
    require(
        locked_inputs["rendererSelectionDigest"]
        == locked_selection["selectionDigest"]
        == canonical_digest(locked_selection_preimage),
        "private compilation lock does not carry the complete renderer selection",
    )
    require(
        locked_inputs["harnessId"] == locked_selection["targetHarness"],
        "private compilation harness differs from renderer selection",
    )

    def validate_compilation_collections(document: dict[str, Any]) -> None:
        inputs = document["inputs"]
        effective = inputs["effectiveSkillSet"]
        public_skills = effective["publicSkills"]
        private_skills = effective["privateSkills"]
        for label, skills in (("public", public_skills), ("private", private_skills)):
            keys = [(item["repository"].encode("utf-8"), item["digest"]) for item in skills]
            require(
                keys == sorted(keys) and len(keys) == len(set(keys)),
                f"private compilation {label} skills are not canonical and unique",
            )
        require(
            effective["digest"]
            == canonical_digest(
                {
                    "profile": "bytedesk.renderer-effective-skill-set/1",
                    "publicSkills": public_skills,
                    "privateSkills": private_skills,
                }
            ),
            "private compilation effective skill-set digest mismatch",
        )
        approval_bindings = inputs["skillApprovals"]
        approval_keys = [
            (entry["skill"]["repository"].encode("utf-8"), entry["skill"]["digest"])
            for entry in approval_bindings
        ]
        approval_descriptors = [
            canonical_digest(entry["approval"])
            for entry in approval_bindings
        ]
        effective_keys = {
            (entry["repository"].encode("utf-8"), entry["digest"])
            for entry in public_skills + private_skills
        }
        require(
            approval_keys == sorted(approval_keys)
            and len(approval_keys) == len(set(approval_keys))
            and set(approval_keys) == effective_keys
            and len(approval_descriptors) == len(set(approval_descriptors)),
            "private compilation skill approvals are duplicate, reordered, incomplete, or ambiguous",
        )

    validate_compilation_collections(compilation_lock)
    for semantic_denial_name in (
        "private-compilation-input__duplicate-skill-approval.json",
        "private-compilation-input__reordered-skill-approvals.json",
    ):
        semantic_denial = load_json(
            REPOSITORY_ROOT
            / "contracts"
            / "fixtures"
            / "schema"
            / "negative"
            / semantic_denial_name
        )
        try:
            validate_compilation_collections(semantic_denial)
        except ContractValidationError:
            pass
        else:
            raise ContractValidationError(
                f"private compilation semantic denial was accepted: {semantic_denial_name}"
            )

    authorized_inputs = deepcopy(locked_inputs)
    authorized_inputs.pop("inputAuthentication", None)
    authorized_inputs.pop("authoritySnapshot")
    authorized_inputs.pop("authorizedPrivateInputDigest")
    require(
        locked_inputs["authorizedPrivateInputDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.authorized-private-compilation-input/1",
                "contract": compilation_lock["contract"],
                "schema": compilation_lock["schema"],
                "inputs": authorized_inputs,
            }
        ),
        "private compilation authority digest does not bind the lock contract, exact schema, and all authorized inputs",
    )
    for replay_name, replay_contract, replay_schema in (
        (
            "contract",
            "bytedesk.private-compilation-input/replayed",
            compilation_lock["schema"],
        ),
        (
            "schema",
            compilation_lock["contract"],
            {
                "id": compilation_lock["schema"]["id"],
                "digest": f"sha256:{'0' * 64}",
            },
        ),
    ):
        require(
            locked_inputs["authorizedPrivateInputDigest"]
            != canonical_digest(
                {
                    "profile": "bytedesk.authorized-private-compilation-input/1",
                    "contract": replay_contract,
                    "schema": replay_schema,
                    "inputs": authorized_inputs,
                }
            ),
            f"private compilation authority digest accepted {replay_name} replay",
        )
    require(
        compilation_lock["compilationInputDigest"]
        == canonical_digest(
            {
                "profile": "bytedesk.private-compilation-input-digest/1",
                "contract": compilation_lock["contract"],
                "schema": compilation_lock["schema"],
                "inputs": locked_inputs,
            }
        ),
        "private compilation input digest does not bind the complete closed lock",
    )

    cli = profiles["bytedesk.cli-automation/1"]["requirements"]
    expected_exits = {
        "success": 0,
        "usage_or_configuration": 2,
        "validation": 3,
        "compatibility": 4,
        "trust": 5,
        "authentication": 6,
        "authorization_or_policy": 7,
        "conflict_or_precondition": 8,
        "unavailable_or_retryable": 9,
        "terminal_operation_failure": 10,
        "cancelled": 11,
        "client_wait_timeout": 12,
        "protocol_or_contract": 13,
    }
    require(cli["exitCodes"] == expected_exits, "CLI exit-code profile drift")
    unique_strings(cli["commandTree"], "CLI command tree")
    require(cli["asyncProgress"]["fields"] == ["phase","completed","total","checkpoint"], "CLI progress contract drift")
    require(cli["asyncProgress"]["maximumPollSeconds"] == 30, "CLI poll maximum drift")

    lock = profiles["bytedesk.external-input-lock/1"]["requirements"]
    required_lock_fields = [
        "contract",
        "schema",
        "lockId",
        "role",
        "repository",
        "commit",
        "treeDigest",
        "paths",
        "validators",
        "compatibilityEvidenceOnly",
        "retrievedAt",
    ]
    require(lock["artifactProfile"] == "bytedesk.external-input-lock/1", "external lock profile ID drift")
    require(
        lock["schemaContract"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/external-input-lock/1.0.0",
        "external lock schema contract drift",
    )
    require(lock["requiredFields"] == required_lock_fields, "external lock required fields drift")
    require(
        lock["roles"]
        == ["compatibility_evidence", "migration_input", "reference_consumer_certification"],
        "external lock roles drift",
    )
    require(lock["compatibilityEvidenceOnly"] is True, "external input may become runtime authority")
    require(lock["commit"]["branchOrTag"] == "forbidden", "external lock permits mutable source selector")
    require(lock["commit"]["pattern"] == "^[0-9a-f]{40,64}$", "external lock commit pattern drift")
    inventory = lock["paths"]
    require(inventory["entryFields"] == ["path", "digest", "size"], "external lock path entry drift")
    require(inventory["ordering"] == "strict-ascending-portable-path-utf8", "external lock inventory order drift")
    require(inventory["duplicatePaths"] == inventory["missingOrExtraPaths"] == "reject", "external lock inventory is not exact")
    require(lock["validators"]["identity"] == "exact-artifact-descriptor-digest", "external lock validator identity drift")
    require(lock["unavailableBehavior"] == "fail-closed-with-no-substitution", "external lock permits fallback")


def validate_external_input_lock_alignment(
    profiles: dict[str, dict[str, Any]], lock_schema: dict[str, Any]
) -> None:
    lock = profiles["bytedesk.external-input-lock/1"]["requirements"]
    require(lock_schema.get("$id") == lock["schemaContract"], "external lock schema ID/profile drift")
    require(lock_schema.get("required") == lock["requiredFields"], "external lock required fields/schema drift")
    properties = lock_schema.get("properties")
    require(isinstance(properties, dict), "external lock schema properties missing")
    require(properties.get("contract", {}).get("const") == lock["artifactProfile"], "external lock contract/profile drift")
    require(properties.get("role", {}).get("enum") == lock["roles"], "external lock role/schema drift")
    require(properties.get("repository", {}).get("pattern") == "^https://", "external lock repository is not HTTPS-only")
    require(properties.get("commit", {}).get("pattern") == lock["commit"]["pattern"], "external lock commit/schema drift")
    paths = properties.get("paths", {})
    require(paths.get("minItems") == lock["paths"]["minimumItems"], "external lock minimum path count drift")
    require(paths.get("maxItems") == lock["paths"]["maximumItems"], "external lock maximum path count drift")
    require(paths.get("items", {}).get("required") == lock["paths"]["entryFields"], "external lock path fields/schema drift")
    validators = properties.get("validators", {})
    require(validators.get("minItems") == lock["validators"]["minimumItems"], "external lock minimum validator count drift")
    require(validators.get("maxItems") == lock["validators"]["maximumItems"], "external lock maximum validator count drift")
    require(properties.get("compatibilityEvidenceOnly", {}).get("const") is True, "external lock schema permits authority")


def validate_oci_signing_profile_semantics(
    profiles: dict[str, dict[str, Any]],
    registry: dict[str, Any],
    signing_request_schema: dict[str, Any],
    signing_result_schema: dict[str, Any],
) -> None:
    oci = profiles["bytedesk.oci-artifact-profile/1"]["requirements"]
    manifest = oci["manifest"]
    require(manifest == {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "schemaVersion": 2,
        "encoding": "rfc8785-jcs-json",
        "requiredMembers": ["schemaVersion","mediaType","artifactType","config","layers"],
        "optionalMembers": ["subject","annotations"],
        "unknownMembers": "reject",
        "digestAlgorithm": "sha256",
    }, "closed OCI manifest profile drift")
    require(oci["index"]["mediaType"] == "application/vnd.oci.image.index.v1+json", "OCI index media type drift")
    require(oci["index"]["tagSelection"] == "forbidden", "OCI index permits tag selection")
    config = oci["config"]
    config_bytes = config["bytesUtf8"].encode("utf-8")
    require(config["mediaType"] == "application/vnd.oci.empty.v1+json", "OCI empty config media type drift")
    require(config["size"] == len(config_bytes) == 2, "OCI empty config size drift")
    require(config["digest"] == f"sha256:{hashlib.sha256(config_bytes).hexdigest()}", "OCI empty config digest drift")
    require(config["semanticAuthority"] is False, "OCI empty config gained semantic authority")

    media_registry_text = (
        REPOSITORY_ROOT / "docs" / "standards" / "oci-media-types-v1.md"
    ).read_text(encoding="utf-8")
    registered_media_types = re.findall(
        r"^\|[^|]+\|\s*`(application/vnd\.bytedesk\.[^`]+)`\s*\|$",
        media_registry_text,
        flags=re.MULTILINE,
    )
    executable_media_types = list(ARTIFACT_TYPE_ROLES)
    require(
        executable_media_types == registered_media_types,
        "executable OCI artifact roles and media-type registry differ",
    )

    def artifact_type_key(role: str) -> str:
        head, *tail = role.split("_")
        return head + "".join(part[:1].upper() + part[1:] for part in tail)

    expected_artifact_types = {
        artifact_type_key(role): media_type
        for media_type, role in ARTIFACT_TYPE_ROLES.items()
    }
    require(
        list(oci["artifactTypes"].items())
        == list(expected_artifact_types.items()),
        "OCI artifact profile key/value/order map differs from executable roles and media-type registry",
    )
    require(
        len(expected_artifact_types) == 53
        and len(set(expected_artifact_types.values())) == 53,
        "OCI artifact type registry is not the exact unique 53-entry contract",
    )

    layers = oci["layers"]
    generic_oci = profiles["bytedesk.oci-archive-layout/1"]["requirements"]
    require(layers["mediaType"] == "application/vnd.oci.image.layer.v1.tar+gzip", "OCI layer media type drift")
    require(layers["roleOrder"] == generic_oci["layerOrder"], "OCI layer role order drift")
    require(layers["undeclaredOrDuplicateRole"] == "reject", "OCI profile permits undeclared or duplicate role")
    tar = layers["tar"]
    require(tar["pathOrder"] == "strict-ascending-portable-path-utf8", "OCI tar ordering drift")
    require(tar["uid"] == tar["gid"] == tar["mtime"] == 0, "OCI tar numeric normalization drift")
    require(tar["acceptedTypes"] == ["regular-file","directory"], "OCI tar member type drift")
    require(tar["linksAndSpecialFiles"] == "reject", "OCI tar permits links or special files")
    gzip = layers["gzip"]
    require(gzip["algorithm"] == "deflate" and gzip["level"] == 9 and gzip["mtime"] == 0, "OCI gzip algorithm/level/time drift")
    require(gzip["operatingSystemByte"] == 255 and gzip["extraFields"] == "none" and gzip["concatenatedMembers"] == "reject", "OCI gzip header/profile drift")
    require(layers["arbitraryPayloadBytes"] == "byte-exact-no-extension-based-parsing", "OCI payload bytes are not exact")

    subject = oci["subject"]
    require(subject["repositoryRule"] == "same-repository-as-referrer", "OCI subject repository rule drift")
    require(subject["missingWrongOrCrossRepository"] == "reject", "OCI subject validation is not closed")
    cross = oci["crossRepositoryEdges"]
    require(cross["ociSubjectUse"] == "forbidden", "cross-repository OCI subject is permitted")
    require(cross["requiredDescriptorMembers"] == ["repository","digest","mediaType","size","trustPolicy"], "cross-repository descriptor drift")
    require(cross["trustPolicyMembers"] == ["id","digest"], "cross-repository trust-policy identity drift")
    require(cross["artifactProvidedTrustRoot"] == "forbidden", "artifact can bootstrap trust")
    bounds = oci["graphBounds"]
    require(all(type(bounds[key]) is int and bounds[key] > 0 for key in ("maximumDepth","maximumDescriptors","maximumManifestBytes","maximumBlobBytes","maximumExpandedBytes","maximumTraversalSeconds")), "OCI graph bounds are not closed positive integers")
    require(oci["publication"]["buildCount"] == 2, "OCI reproducible publication build count drift")
    require(oci["verification"]["execution"] == "never", "OCI verification may execute content")
    archive = oci["archive"]
    require(archive["format"] == "posix-ustar", "OCI archive format drift")
    require(archive["maximumMembers"] == generic_oci["maximumMembers"], "OCI archive member bound drift")
    require(archive["maximumMemberBytes"] == generic_oci["maximumMemberBytes"], "OCI archive member-byte bound drift")
    require(archive["maximumExpandedBytes"] == generic_oci["maximumExpandedBytes"], "OCI archive expanded-byte bound drift")
    require(archive["rootCreatePrecondition"] == "absent" and archive["rootUpdatePrecondition"] == "exact-revision-plus-digest-match", "OCI archive-root CAS drift")

    signing = profiles["bytedesk.signing-evidence-profile/1"]["requirements"]
    crypto = signing["cryptographicProfile"]
    require(crypto == {
        "contractName": "ECDSA_P256_SHA256",
        "keyType": "ECDSA",
        "curve": "NIST-P-256",
        "digest": "SHA-256",
        "providerSigningAlgorithm": "ECDSA_SHA_256",
        "signatureEncoding": "ASN.1-DER",
        "publicKeyEncoding": "DER-SubjectPublicKeyInfo",
        "privateKeyExport": "forbidden",
    }, "signing cryptographic profile drift")
    require(signing["kmsProfile"]["keySpec"] == "ECC_NIST_P256", "KMS key spec drift")
    require(signing["kmsProfile"]["keyUsage"] == "SIGN_VERIFY", "KMS key usage drift")
    require(signing["kmsProfile"]["workloadPermission"] == ["GetPublicKey","Sign"], "KMS workload permissions drift")
    require("Export" in signing["kmsProfile"]["forbiddenPermissions"], "KMS export is not forbidden")
    require(signing["isolation"]["consumerAuthoritySignerAccessFromAgentDelivery"] == "forbidden", "Agent Delivery can issue consumer authority")
    require(signing["isolation"]["crossConsumerPrivateKey"] == "forbidden", "cross-consumer private signing is permitted")
    require(signing["purposeProfiles"] == {
        "productRelease": "product-release-v1",
        "publicSource": "public-source-v1",
        "publicRender": "public-render-v1",
        "consumerPrivateSkill": "consumer-private-skill-v1",
        "consumerAuthority": "consumer-authority-v1",
        "consumerDeployment": "consumer-deployment-v1",
        "consumerRuntimeRelease": "consumer-runtime-release-v1",
        "releaseQualificationPolicy": "release-qualification-policy-v1",
        "releaseQualificationAttempt": "release-qualification-attempt-v1",
        "releaseQualificationReceipt": "release-qualification-receipt-v1",
        "releaseQualificationEvidence": "release-qualification-evidence-v1",
        "releaseQualificationDecision": "release-qualification-decision-v1",
        "releaseStatus": "release-status-v1",
        "releaseStatusHead": "release-status-head-v1",
        "releaseStatusEligibility": "release-status-eligibility-v1",
        "consumerReleaseStatusEligibility": "consumer-release-status-eligibility-v1",
        "rendererAttempt": "renderer-attempt-v1",
        "rendererExecution": "renderer-execution-v1",
        "consumerCompilationInput": "consumer-compilation-input-v1",
        "consumerCompilationEvidence": "consumer-compilation-evidence-v1",
        "consumerActivationAuthorization": "consumer-activation-authorization-v1",
    }, "signer purpose profile key/value map drift")
    require(signing["signingRequest"]["schemaId"] == signing_request_schema.get("$id"), "signing request schema ID drift")
    require(signing["signingResult"]["schemaId"] == signing_result_schema.get("$id"), "signing result schema ID drift")
    result_algorithm = (
        signing_result_schema.get("properties", {}).get("algorithm", {}).get("const")
    )
    require(
        result_algorithm == crypto["contractName"],
        "signing result schema rejects selected algorithm",
    )
    require(signing["cosign"]["version"] == "3.0.6", "Cosign semantic version profile drift")
    require(signing["cosign"]["executableAuthority"] == "exact-component-lock-descriptor-and-sha256-digest", "Cosign executable is not digest-authoritative")

    sbom = signing["sbom"]
    require(sbom["specification"] == "SPDX-2.3" and sbom["mediaType"] == "application/spdx+json", "SBOM profile drift")
    require(
        sbom["interoperabilityProfile"]
        == "agent-delivery-v1-spdx-2.3-json",
        "SBOM interoperability profile drift",
    )
    require(
        sbom["versionPolicy"]
        == "interoperability-pin-not-latest-version-claim",
        "SBOM version policy overclaims latest-version status",
    )
    require(sbom["fileChecksum"] == "SHA256", "SBOM file checksum drift")
    require(
        sbom["requiredInputs"]
        == ["artifactDigest", "generatorImageDigest", "componentLockDigest"],
        "SBOM operation inputs drift",
    )
    require({"packages","files","relationships"} <= set(sbom["requiredSections"]), "SBOM coverage fields incomplete")
    require(sbom["missingIncompleteOrUnknownComponent"] == "reject", "incomplete SBOM is accepted")
    provenance = signing["provenance"]
    require(provenance["specification"] == "SLSA-v1.2", "SLSA specification profile drift")
    require(provenance["statementType"] == "https://in-toto.io/Statement/v1", "in-toto statement profile drift")
    require(provenance["predicateType"] == "https://slsa.dev/provenance/v1", "SLSA predicate profile drift")
    require(provenance["targetBuildLevel"] == 3, "SLSA build level drift")
    require(
        provenance["requiredInputs"]
        == [
            "subjectDigest", "buildType", "builderId", "invocationId",
            "externalParametersDigest", "resolvedDependencies", "startedOn",
            "finishedOn",
        ],
        "SLSA generation inputs do not express the complete v1.2 wire shape",
    )
    require(provenance["builderAndWorkflowAuthority"] == "exact-pinned-identities", "provenance builder/workflow is not pinned")

    vulnerability = signing["vulnerabilityScan"]
    require(vulnerability["mediaType"] == "application/vnd.bytedesk.scan.v1+json", "vulnerability media type drift")
    require({"scannerImageDigest","scannerRulesDigest","advisorySnapshotDigest","severityPolicyDigest"} <= set(vulnerability["requiredInputs"]), "vulnerability scan inputs are not fully pinned")
    require(vulnerability["resultClasses"] == ["pass","deny","indeterminate"], "vulnerability result variants drift")
    require(vulnerability["indeterminatePromotionEligible"] is False, "indeterminate vulnerability scan can promote")
    require(vulnerability["artifactExecution"] == "forbidden", "vulnerability scanner may execute artifact")
    malware = signing["malwareScan"]
    require(malware["mediaType"] == "application/vnd.bytedesk.malware-scan.v1+json", "malware media type drift")
    require(malware["detectedOrCoverageIncomplete"] == "deny" and malware["artifactExecution"] == "forbidden", "malware scan failure/execution boundary drift")
    secret_scan = signing["secretScan"]
    require(secret_scan["mediaType"] == "application/vnd.bytedesk.secret-scan.v1+json", "secret scan media type drift")
    require(secret_scan["rawSecretInArtifact"] == "deny", "raw secret artifact is permitted")
    require("no-secret-bytes" in secret_scan["findingsRedaction"], "secret scan findings may expose secret bytes")
    completeness = signing["scanCompleteness"]
    require(
        completeness["mediaType"]
        == "application/vnd.bytedesk.scan-completeness.v1+json",
        "scan completeness media type drift",
    )
    require(
        completeness["requiredReports"] == ["vulnerability", "malware", "secret"]
        and completeness["missingMismatchedOrIncomplete"] == "deny",
        "scan completeness does not fail closed over all required reports",
    )
    require(
        completeness["evidenceCannotGrantRuntimeAuthority"] is True,
        "scan completeness evidence can grant runtime authority",
    )
    license_profile = signing["licenseEvaluation"]
    require(license_profile["expressionSyntax"] == "SPDX-2.3-license-expression", "license expression profile drift")
    require(license_profile["evidenceCannotGrantRuntimeAuthority"] is True, "license evidence can grant runtime authority")
    allowed_referrers = set(oci["referrers"]["allowedArtifactTypes"])
    evidence_media = {
        sbom["mediaType"], provenance["mediaType"], vulnerability["mediaType"],
        malware["mediaType"], secret_scan["mediaType"], completeness["mediaType"],
        license_profile["mediaType"],
    }
    require(evidence_media <= allowed_referrers, "signing/evidence media types are absent from OCI referrer profile")
    require(signing["failureBehavior"]["artifactOrSkillFilesExecuted"] == "nonconforming", "evidence tools may execute artifact content")

    supply_port = next(
        port
        for port in registry["ports"]
        if port["portId"] == "bytedesk.port.supply-chain-evidence/1"
    )
    supply_operations = {
        operation["operationId"]: operation
        for operation in supply_port["operations"]
    }
    required_inputs = {
        "generate-sbom": sbom["requiredInputs"],
        "generate-provenance": provenance["requiredInputs"],
        "scan-vulnerabilities": vulnerability["requiredInputs"],
        "scan-malware": malware["requiredInputs"],
        "scan-secrets": secret_scan["requiredInputs"],
        "attest-scan-completeness": completeness["requiredInputs"],
        "evaluate-licenses": license_profile["requiredInputs"],
    }
    require(
        set(supply_operations) == set(required_inputs),
        "supply-chain operation set and signing profile differ",
    )
    for operation_id, expected_fields in required_inputs.items():
        require(
            [field["name"] for field in supply_operations[operation_id]["requestFields"]]
            == expected_fields,
            f"supply-chain pinned input drift: {operation_id}",
        )
    expected_reports = {
        "scan-vulnerabilities": "bytedesk.port.vulnerability-report/1",
        "scan-malware": "bytedesk.port.malware-report/1",
        "scan-secrets": "bytedesk.port.secret-scan-report/1",
        "attest-scan-completeness": "bytedesk.port.scan-completeness-report/1",
        "evaluate-licenses": "bytedesk.port.license-report/1",
    }
    for operation_id, report_ref in expected_reports.items():
        result_fields = {
            field["name"]: field
            for field in supply_operations[operation_id]["resultFields"]
        }
        require(
            result_fields["report"]["schemaRef"] == report_ref,
            f"supply-chain result does not carry the exact report: {operation_id}",
        )


def validate_host_journal_alignment(
    profiles: dict[str, dict[str, Any]],
    host_journal_schema: dict[str, Any],
    registry: dict[str, Any],
) -> None:
    profile = profiles["bytedesk.host-switch-journal/1"]["requirements"]
    expected_phases = [
        "accepted","artifact_verified","staged","preflight_passed",
        "candidate_ready_recorded","activation_authorized","switch_intent_durable",
        "switched","readback_verified","observation_accepted","cleanup_eligible","completed",
    ]
    require(profile["phases"] == expected_phases, "host journal profile phase set/order drift")
    require(
        host_journal_schema.get("$id")
        == "https://schemas.bytedesk.ai/agent-delivery/v1/host-switch-journal-entry/1.0.0",
        "host journal schema ID drift",
    )
    schema_phases = (
        host_journal_schema.get("properties", {}).get("phase", {}).get("enum")
    )
    require(schema_phases == expected_phases, "host journal schema/profile phases differ")
    required = set(host_journal_schema.get("required", []))
    require(set(profile["journalIdentity"]) <= required, "host journal schema omits profile identity fields")
    require(
        {"releaseDigest", "deployableGraphDigest"} <= set(profile["journalIdentity"])
        and "deploymentDigest" not in profile["journalIdentity"],
        "host journal identity is not target-wide runtime-release/deployable-graph identity",
    )
    require({"phase","sequence","previousEntry","recordedAt"} <= required, "host journal chain fields are not required")
    properties = host_journal_schema.get("properties", {})
    require("switchMarker" in properties and "readback" in properties, "host journal switch/readback evidence properties missing")
    require(
        {
            "activationAuthorizationDigest",
            "hostEligibilityVerificationEvidenceDigest",
        }
        <= set(properties),
        "host journal omits activation authorization or Host use-time eligibility evidence digest",
    )

    required_by_phase: dict[str, set[str]] = {}
    for rule in host_journal_schema.get("allOf", []):
        try:
            phases = rule["if"]["properties"]["phase"]["enum"]
            fields = rule["then"]["required"]
        except (KeyError, TypeError):
            continue
        for phase in phases:
            required_by_phase.setdefault(phase, set()).update(fields)
    switch_index = expected_phases.index("switched")
    readback_index = expected_phases.index("readback_verified")
    for index, phase in enumerate(expected_phases):
        if index >= switch_index:
            require("switchMarker" in required_by_phase.get(phase, set()), f"switch marker not required for host phase {phase}")
        if index >= readback_index:
            require("readback" in required_by_phase.get(phase, set()), f"readback not required for host phase {phase}")
        if index >= expected_phases.index("activation_authorized"):
            require(
                {
                    "activationAuthorizationDigest",
                    "hostEligibilityVerificationEvidenceDigest",
                }
                <= required_by_phase.get(phase, set()),
                f"activation/use-time verification digests not required for host phase {phase}",
            )

    ports = {port["portId"]: port for port in registry["ports"]}
    host_operations = {
        operation["operationId"]: operation
        for operation in ports["bytedesk.port.host-reconciler/1"]["operations"]
    }
    activate = host_operations["activate-candidate"]
    activate_request = {field["name"]: field for field in activate["requestFields"]}
    activate_result = {field["name"]: field for field in activate["resultFields"]}
    require(
        {
            "runtimeRelease",
            "releaseDigest",
            "deployableGraphDigest",
            "activationAuthorization",
            "activationAuthorizationDigest",
            "operationTime",
        }
        <= set(activate_request),
        "Host activation request omits target-wide graph or authorization identity",
    )
    require(
        {
            "releaseDigest",
            "deployableGraphDigest",
            "activationAuthorizationDigest",
            "hostEligibilityVerification",
            "hostEligibilityVerificationEvidenceDigest",
        }
        <= set(activate_result),
        "Host activation result omits durable graph/authorization/use-time verification evidence",
    )

    coordinator_operations = {
        operation["operationId"]: operation
        for operation in ports["bytedesk.port.promotion-coordinator/1"]["operations"]
    }
    authorize = coordinator_operations["authorize-activation"]
    authorize_request = {field["name"]: field for field in authorize["requestFields"]}
    authorize_result = {field["name"]: field for field in authorize["resultFields"]}
    for field_name, schema_ref in {
        "deployableGraph": "bytedesk.port.activation-deployable-graph/1",
        "candidateReadyEvidence": "bytedesk.port.activation-candidate-ready-evidence-set/1",
        "authoritySnapshots": "bytedesk.port.activation-authority-snapshot-set/1",
        "authorizationDecisionProofs": "bytedesk.port.activation-authorization-decision-proof-set/1",
    }.items():
        field = authorize_request.get(field_name)
        require(
            field is not None
            and field["type"] == "array"
            and field["schemaRef"] == schema_ref,
            f"Coordinator activation request {field_name} is not the exact canonical array contract",
        )
    require(
        {
            "releaseDigest",
            "deployableGraphDigest",
            "authorizationNonce",
            "slotId",
            "fencingToken",
            "operationTime",
        }
        <= set(authorize_request),
        "Coordinator activation request omits graph, nonce, slot, or use-time fence",
    )
    require(
        {
            "activationAuthorizationDigest",
            "releaseDigest",
            "deployableGraphDigest",
            "releaseEligibility",
            "releaseEligibilityDigest",
            "releaseEligibilityVerification",
            "releaseEligibilityVerificationEvidenceDigest",
            "authorizationNonce",
            "slotId",
            "operationTime",
        }
        <= set(authorize_result),
        "Coordinator activation result omits exact authorization/eligibility echoes",
    )


def validate_cases(
    case_catalog: dict[str, Any],
    operations: dict[tuple[str, str], dict[str, Any]],
    problems: dict[str, dict[str, Any]],
) -> None:
    require(
        set(ALLOWED_TASK_SUITES_BY_OWNER) == REQUIRED_TASKS,
        "task-suite ownership must define every task exactly once",
    )
    require(
        set().union(*ALLOWED_TASK_SUITES_BY_OWNER.values()) == REQUIRED_TASK_SUITES,
        "required task suites drift from exact task-suite ownership",
    )
    require(len(REQUIRED_TASK_SUITES) == 19, "required task-suite count drift")
    exact_keys(case_catalog, {"$schema", "profile", "version", "cases"}, "conformance catalog root")
    require(
        case_catalog["$schema"]
        == "https://schemas.bytedesk.ai/agent-delivery/v1/downstream-conformance-cases/1.0.0",
        "conformance catalog schema binding drift",
    )
    require(case_catalog["profile"] == "bytedesk.downstream-conformance-cases/1", "wrong conformance profile")
    require(case_catalog["version"] == 1, "wrong conformance version")
    require(isinstance(case_catalog["cases"], list), "conformance cases must be an array")
    case_keys = {"caseId", "suite", "portSuites", "ownerTask", "covers", "category", "fixture", "expected"}
    cover_keys = {"portId", "operationId"}
    expected_keys = {"outcome", "problemCode", "sideEffectState"}
    case_ids: set[str] = set()
    suites: set[str] = set()
    covered_operations: set[tuple[str, str]] = set()
    referenced_problem_codes: set[str] = set()
    covered_port_suites: set[str] = set()
    all_port_suites = {operation["suite"] for operation in operations.values()}
    for index, case in enumerate(case_catalog["cases"]):
        require(isinstance(case, dict), f"case[{index}] must be an object")
        exact_keys(case, case_keys, f"case[{index}]")
        case_id = case["caseId"]
        require(
            isinstance(case_id, str)
            and re.fullmatch(
                r"[A-Z][A-Z0-9-]*-[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*",
                case_id,
            ),
            f"invalid case ID: {case_id!r}",
        )
        require(case_id not in case_ids, f"duplicate case ID: {case_id}")
        case_ids.add(case_id)
        require(isinstance(case["suite"], str) and case["suite"].startswith("downstream."), f"invalid suite: {case_id}")
        suites.add(case["suite"])
        require(case["ownerTask"] in REQUIRED_TASKS, f"invalid case owner task: {case_id}")
        require(
            case["suite"] in ALLOWED_TASK_SUITES_BY_OWNER[case["ownerTask"]],
            f"case task-suite ownership drift: {case_id}/{case['ownerTask']}/{case['suite']}",
        )
        if case_id in EXACT_TASK_SUITE_BY_CASE:
            require(
                case["suite"] == EXACT_TASK_SUITE_BY_CASE[case_id],
                f"case exact task suite drift: {case_id}/{case['suite']}",
            )
        require(isinstance(case["category"], str) and case["category"], f"missing case category: {case_id}")
        require(isinstance(case["fixture"], dict) and case["fixture"], f"case fixture must be a nonempty object: {case_id}")
        require(isinstance(case["covers"], list) and case["covers"], f"case covers must not be empty: {case_id}")
        local_covers: set[tuple[str, str]] = set()
        for cover_index, cover in enumerate(case["covers"]):
            require(isinstance(cover, dict), f"case cover must be object: {case_id}/{cover_index}")
            exact_keys(cover, cover_keys, f"{case_id}.covers[{cover_index}]")
            key = (cover["portId"], cover["operationId"])
            require(key in operations, f"case references unknown operation: {case_id}/{key}")
            require(key not in local_covers, f"case has duplicate operation cover: {case_id}/{key}")
            local_covers.add(key)
            covered_operations.add(key)
        expected_port_suites: list[str] = []
        for cover in case["covers"]:
            suite = operations[(cover["portId"], cover["operationId"])]["suite"]
            if suite not in expected_port_suites:
                expected_port_suites.append(suite)
        require(case["portSuites"] == expected_port_suites, f"case port owner suites drift: {case_id}")
        covered_port_suites.update(expected_port_suites)
        expected = case["expected"]
        require(isinstance(expected, dict), f"case expected must be object: {case_id}")
        exact_keys(expected, expected_keys, f"{case_id}.expected")
        require(expected["outcome"] in {"pass", "deny", "recover"}, f"invalid outcome: {case_id}")
        require(expected["sideEffectState"] in SIDE_EFFECT_STATES, f"invalid case side-effect state: {case_id}")
        code = expected["problemCode"]
        if expected["outcome"] == "deny":
            require(isinstance(code, str) and code in problems, f"denial case has unknown problem: {case_id}")
            rejecting_operation = case["fixture"].get("rejectingOperation")
            require(
                isinstance(rejecting_operation, str)
                and rejecting_operation.count("#") == 1,
                f"denial case requires one rejectingOperation: {case_id}",
            )
            rejecting_key = tuple(rejecting_operation.split("#", 1))
            require(
                rejecting_key in local_covers,
                f"rejectingOperation is not covered by case: {case_id}/{rejecting_operation}",
            )
            rejecting_errors = operation_error_states(operations[rejecting_key])
            require(
                code in rejecting_errors,
                f"rejectingOperation does not declare problem: "
                f"{case_id}/{rejecting_operation}/{code}",
            )
            require(
                expected["sideEffectState"] == rejecting_errors[code],
                f"case/operation side-effect state drift: {case_id}",
            )
            referenced_problem_codes.add(code)
        else:
            require(code is None, f"pass/recover case must not claim a problem: {case_id}")
    require(covered_operations == set(operations), f"conformance operation coverage differs; missing={sorted(set(operations)-covered_operations)}")
    require(REQUIRED_TASK_SUITES <= suites, f"task suites missing from conformance catalog: {sorted(REQUIRED_TASK_SUITES-suites)}")
    require(
        set(EXACT_TASK_SUITE_BY_CASE) <= case_ids,
        "exact task-suite cases are missing from the conformance catalog",
    )
    require(REQUIRED_CRITICAL_CASES <= case_ids, f"critical conformance cases missing: {sorted(REQUIRED_CRITICAL_CASES-case_ids)}")
    require(referenced_problem_codes <= set(problems), "conformance case references unknown problem")
    require(covered_port_suites == all_port_suites, f"conformance port owner suite coverage differs: {sorted(all_port_suites-covered_port_suites)}")


def validate_coverage_matrix(
    registry: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    *,
    text_override: str | None = None,
    run_mutation_probe: bool = True,
) -> int:
    text = (
        COVERAGE_MATRIX_PATH.read_text(encoding="utf-8")
        if text_override is None
        else text_override
    )
    start_marker = "<!-- downstream-port-coverage-matrix:start -->"
    end_marker = "<!-- downstream-port-coverage-matrix:end -->"
    require(text.count(start_marker) == 1, "coverage matrix start marker must appear once")
    require(text.count(end_marker) == 1, "coverage matrix end marker must appear once")
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker)
    require(start < end, "coverage matrix markers are out of order")

    expected_ports = {port["portId"]: port for port in registry["ports"]}
    expected_operation_count = sum(
        len(port["operations"]) for port in registry["ports"]
    )
    declared_counts = re.findall(
        r"The closed registry contains (\d+) ports and (\d+) operations\.",
        text,
    )
    require(
        len(declared_counts) == 1,
        "coverage summary must declare registry port and operation counts once",
    )
    require(
        tuple(map(int, declared_counts[0]))
        == (len(expected_ports), expected_operation_count),
        "coverage summary port/operation counts differ from registry; "
        f"expected={(len(expected_ports), expected_operation_count)} "
        f"actual={tuple(map(int, declared_counts[0]))}",
    )
    certification_count_claim = (
        f"All {len(expected_ports)} closed ports and all "
        f"{expected_operation_count} operations"
    )
    require(
        certification_count_claim in text,
        "AD-18 coverage count claim differs from registry",
    )
    documented_ports: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(text[start:end].splitlines(), start=1):
        if not line.startswith("| `bytedesk.port."):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        require(
            len(cells) == 8,
            f"coverage matrix row {line_number} must contain exactly eight cells",
        )
        port_ids = re.findall(r"`(bytedesk\.port\.[a-z0-9-]+/1)`", cells[0])
        require(
            len(port_ids) == 1,
            f"coverage matrix row {line_number} must identify exactly one port",
        )
        port_id = port_ids[0]
        require(
            port_id in expected_ports,
            f"coverage matrix references unregistered port: {port_id}",
        )
        require(
            port_id not in documented_ports,
            f"coverage matrix contains duplicate port row: {port_id}",
        )
        identity_and_operations = re.findall(r"`([^`]+)`", cells[0])
        require(
            identity_and_operations[0] == port_id,
            f"coverage matrix row does not begin with its port ID: {port_id}",
        )
        documented_operations = identity_and_operations[1:]
        require(
            cells[0]
            == "<br>".join(
                f"`{value}`" for value in [port_id, *documented_operations]
            ),
            f"coverage matrix has malformed port/operation list: {port_id}",
        )
        require(
            all(
                re.fullmatch(r"[a-z][a-z0-9-]+", operation_id)
                for operation_id in documented_operations
            ),
            f"coverage matrix has malformed operation ID: {port_id}",
        )
        owner_suite = re.fullmatch(
            r"`([a-z][a-z0-9-]+)`<br>`(downstream\.[a-z0-9.-]+)`",
            cells[5],
        )
        require(owner_suite is not None, f"coverage matrix has malformed owner/suite: {port_id}")
        documented_errors = re.findall(r"`([a-z][a-z0-9_]*)`", cells[2])
        require(
            cells[2] == ", ".join(f"`{code}`" for code in documented_errors),
            f"coverage matrix has malformed error list: {port_id}",
        )
        task_cell = cells[6]
        require(
            re.fullmatch(r"AD-\d{2}(?:, AD-\d{2})*", task_cell) is not None,
            f"coverage matrix has malformed task list: {port_id}",
        )
        documented_ports[port_id] = {
            "operations": documented_operations,
            "authority": cells[1],
            "authorityCodeTokens": set(re.findall(r"`([^`]+)`", cells[1])),
            "authorityLinkLabels": {
                label
                for label, _target in re.findall(
                    r"\[([^\]]+)\]\(([^)]+)\)",
                    cells[1],
                )
            },
            "authorityRepositoryLinks": {
                resolved.relative_to(REPOSITORY_ROOT).as_posix()
                for _label, target in re.findall(
                    r"\[([^\]]+)\]\(([^)]+)\)",
                    cells[1],
                )
                if not re.match(r"^[a-z][a-z0-9+.-]*:", target)
                and (resolved := (COVERAGE_MATRIX_PATH.parent / target).resolve())
                .is_relative_to(REPOSITORY_ROOT)
            },
            "errors": documented_errors,
            "owner": owner_suite.group(1),
            "suite": owner_suite.group(2),
            "tasks": re.findall(r"AD-\d{2}", task_cell),
        }

    require(
        set(documented_ports) == set(expected_ports),
        "coverage matrix port rows differ from registry; "
        f"missing={sorted(set(expected_ports)-set(documented_ports))} "
        f"extra={sorted(set(documented_ports)-set(expected_ports))}",
    )
    registered_promised_schemas = {
        schema_id
        for port in registry["ports"]
        for schema_id in port["promisedSchemas"]
    }
    for port_id, expected_port in expected_ports.items():
        documented_port = documented_ports[port_id]
        expected_operations = [
            operation["operationId"] for operation in expected_port["operations"]
        ]
        require(
            documented_port["operations"] == expected_operations,
            f"coverage matrix operation list differs from registry: {port_id}; "
            f"expected={expected_operations} actual={documented_port['operations']}",
        )
        authority_code_tokens = documented_port["authorityCodeTokens"]
        authority_link_labels = documented_port["authorityLinkLabels"]
        authority_repository_links = documented_port["authorityRepositoryLinks"]
        for contract_path in expected_port["contractPaths"]:
            require(
                contract_path in authority_link_labels
                and contract_path in authority_repository_links,
                f"coverage matrix authority omits exact registry contract path: "
                f"{port_id}/{contract_path}",
            )
        operation_contracts = {
            contract_id
            for operation in expected_port["operations"]
            for contract_id in (
                operation["requestContract"],
                operation["resultContract"],
            )
        }
        require(
            operation_contracts <= authority_code_tokens,
            f"coverage matrix authority omits operation contract IDs: {port_id}; "
            f"missing={sorted(operation_contracts - authority_code_tokens)}",
        )
        documented_operation_contracts = {
            token
            for token in authority_code_tokens
            if re.fullmatch(
                r"bytedesk\.port\.[a-z0-9-]+\.[a-z0-9-]+\.(?:request|result)/1",
                token,
            )
        }
        require(
            documented_operation_contracts == operation_contracts,
            f"coverage matrix authority contains stale operation contract IDs: {port_id}; "
            f"extra={sorted(documented_operation_contracts - operation_contracts)}",
        )
        promised_schemas = set(expected_port["promisedSchemas"])
        documented_promised_schemas = (
            authority_code_tokens & registered_promised_schemas
        )
        require(
            documented_promised_schemas == promised_schemas,
            f"coverage matrix authority promised schema IDs differ from registry: "
            f"{port_id}; missing={sorted(promised_schemas - documented_promised_schemas)} "
            f"extra={sorted(documented_promised_schemas - promised_schemas)}",
        )
        expected_profiles = set(expected_port["protocolProfiles"])
        documented_profiles = authority_code_tokens & set(profiles)
        require(
            documented_profiles == expected_profiles,
            f"coverage matrix authority protocol profiles differ from registry: {port_id}; "
            f"missing={sorted(expected_profiles - documented_profiles)} "
            f"extra={sorted(documented_profiles - expected_profiles)}",
        )
        expected_errors = sorted(
            {
                code
                for operation in expected_port["operations"]
                for code in operation_error_states(operation)
            }
        )
        require(
            documented_port["errors"] == expected_errors,
            f"coverage matrix error list differs from registry: {port_id}; "
            f"expected={expected_errors} actual={documented_port['errors']}",
        )
        require(
            documented_port["owner"] == expected_port["owner"],
            f"coverage matrix owner differs from registry: {port_id}; "
            f"expected={expected_port['owner']} actual={documented_port['owner']}",
        )
        require(
            documented_port["suite"] == expected_port["suite"],
            f"coverage matrix suite differs from registry: {port_id}; "
            f"expected={expected_port['suite']} actual={documented_port['suite']}",
        )
        require(
            documented_port["tasks"] == expected_port["tasks"],
            f"coverage matrix task list differs from registry: {port_id}; "
            f"expected={expected_port['tasks']} actual={documented_port['tasks']}",
        )

    if not run_mutation_probe:
        return 0
    probe_port = registry["ports"][0]
    probe_token = probe_port["operations"][0]["requestContract"]
    encoded_probe = f"`{probe_token}`"
    require(
        text.count(encoded_probe) == 1,
        f"coverage authority mutation token must occur exactly once: {probe_token}",
    )
    mutated_text = text.replace(encoded_probe, "", 1)
    try:
        validate_coverage_matrix(
            registry,
            profiles,
            text_override=mutated_text,
            run_mutation_probe=False,
        )
    except ContractValidationError as error:
        require(
            probe_token in str(error),
            "coverage authority mutation failed for an unrelated reason",
        )
    else:
        raise ContractValidationError(
            f"coverage authority mutation was accepted: removed {probe_token}"
        )
    return 1


def validate_task_traceability(registry: dict[str, Any]) -> None:
    task_dir = REPOSITORY_ROOT / "docs" / "planning" / "tasks"
    task_paths: dict[str, Path] = {}
    for path in task_dir.glob("AD-*.md"):
        match = re.match(r"(AD-\d{2})-", path.name)
        if match and match.group(1) in REQUIRED_TASKS:
            require(match.group(1) not in task_paths, f"multiple task docs for {match.group(1)}")
            task_paths[match.group(1)] = path
    require(set(task_paths) == REQUIRED_TASKS, f"task docs missing for port implementation: {sorted(REQUIRED_TASKS-set(task_paths))}")
    known_ports = set(REQUIRED_PORT_OPERATIONS)
    expected_ports_by_task: dict[str, set[str]] = {
        task_id: set() for task_id in REQUIRED_TASKS
    }
    for port in registry["ports"]:
        for task_id in port["tasks"]:
            expected_ports_by_task[task_id].add(port["portId"])
    for task_id, path in sorted(task_paths.items()):
        text = path.read_text(encoding="utf-8")
        require("## Normative contracts and conformance" in text, f"{task_id} lacks normative traceability section")
        for required_path in (
            "contracts/ports/v1/port-registry.json",
            "contracts/ports/v1/type-catalog.json",
            "contracts/ports/v1/contract-fixtures.json",
            "contracts/ports/v1/protocol-profiles.json",
            "contracts/ports/v1/conformance-cases.json",
        ):
            require(required_path in text, f"{task_id} does not reference {required_path}")
        referenced_ports = set(re.findall(r"`(bytedesk\.port\.[a-z0-9-]+/1)`", text))
        require(referenced_ports, f"{task_id} references no downstream port")
        require(referenced_ports <= known_ports, f"{task_id} references unregistered ports: {sorted(referenced_ports-known_ports)}")
        require(
            referenced_ports == expected_ports_by_task[task_id],
            f"{task_id} port citations differ from registry tasks; "
            f"missing={sorted(expected_ports_by_task[task_id]-referenced_ports)} "
            f"extra={sorted(referenced_ports-expected_ports_by_task[task_id])}",
        )
        for pattern in UNPINNED_SELECTOR_PATTERNS:
            match = pattern.search(text)
            if match is not None:
                raise ContractValidationError(
                    f"{task_id} contains unpinned-current selector wording "
                    f"{match.group(0)!r}"
                )


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    payload = (
        json.dumps(evidence, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
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
    registry = load_json(REGISTRY_PATH)
    type_catalog = load_json(TYPE_CATALOG_PATH)
    contract_fixtures = load_json(CONTRACT_FIXTURE_PATH)
    problems_doc = load_json(PROBLEM_PATH)
    actions = load_json(ACTION_PATH)
    profiles_doc = load_json(PROFILE_PATH)
    cases = load_json(CASE_PATH)
    action_schema = load_json(ACTION_SCHEMA_PATH)
    problem_schema = load_json(PROBLEM_SCHEMA_PATH)
    renderer_release = load_json(RENDERER_RELEASE_PATH)
    event_registry = load_json(EVENT_TYPES_PATH)
    host_journal_schema = load_json(HOST_JOURNAL_SCHEMA_PATH)
    signing_request_schema = load_json(SIGNING_REQUEST_SCHEMA_PATH)
    signing_result_schema = load_json(SIGNING_RESULT_SCHEMA_PATH)
    external_input_lock_schema = load_json(EXTERNAL_INPUT_LOCK_SCHEMA_PATH)

    operations, referenced_error_states = validate_registry(registry)
    port_type_counts = validate_port_type_catalog(
        registry,
        type_catalog,
        contract_fixtures,
    )
    problems = validate_problems(problems_doc, referenced_error_states)
    validate_problem_schema_generator_ownership(
        problem_schema, registry, problems_doc
    )
    validate_problem_schema_alignment(problem_schema, problems, operations)
    validate_actions(actions, action_schema, operations, problems)
    profiles = validate_profiles(profiles_doc, registry, renderer_release)
    validate_event_profile(profiles, event_registry)
    validate_profile_semantics(profiles, registry)
    validate_external_input_lock_alignment(profiles, external_input_lock_schema)
    validate_oci_signing_profile_semantics(
        profiles,
        registry,
        signing_request_schema,
        signing_result_schema,
    )
    validate_host_journal_alignment(profiles, host_journal_schema, registry)
    validate_cases(cases, operations, problems)
    coverage_authority_mutations = validate_coverage_matrix(registry, profiles)
    validate_task_traceability(registry)

    return {
        "profile": "bytedesk.downstream-port-validation-evidence/1",
        "result": "pass",
        "digests": {
            "portRegistry": canonical_digest(registry),
            "problemCatalog": canonical_digest(problems_doc),
            "actionCatalog": canonical_digest(actions),
            "protocolProfiles": canonical_digest(profiles_doc),
            "conformanceCases": canonical_digest(cases),
            "portTypeCatalog": canonical_digest(type_catalog),
            "portContractFixtures": canonical_digest(contract_fixtures),
        },
        "counts": {
            "ports": len(registry["ports"]),
            "operations": len(operations),
            "problems": len(problems),
            "actions": len(actions["actions"]),
            "profiles": len(profiles_doc["profiles"]),
            "conformanceCases": len(cases["cases"]),
            "taskDocuments": len(REQUIRED_TASKS),
            "coverageAuthorityMutations": coverage_authority_mutations,
            **port_type_counts,
        },
        "checks": [
            "closed-root-and-entry-shapes",
            "required-port-operation-and-task-coverage",
            "digest-bound-offline-port-type-closure",
            "unique-complete-field-value-types",
            "product-semantic-string-and-integer-refinements",
            "canonical-unpadded-base64url-byte-semantics",
            "embedded-closed-request-result-schemas",
            "contract-fixtures-and-adversarial-denials",
            "closed-problem-and-cli-exit-mapping",
            "operation-specific-problem-side-effect-mappings",
            "rfc9457-exact-port-operation-problem-binding",
            "action-schema-enum-alignment",
            "event-registry-alignment",
            "renderer-promised-schema-ids",
            "protocol-ordering-fencing-and-failure-semantics",
            "capability-evidence-exact-binding-and-domain-outcomes",
            "complete-conformance-operation-coverage",
            "conformance-denials-bind-rejecting-operation",
            "exact-registry-derived-coverage-counts-operations-errors-owner-suite-and-tasks",
            "exact-registry-derived-coverage-authority-and-mutation-denial",
            "exact-registry-derived-task-port-traceability",
            "repository-path-resolution",
            "no-unpinned-current-task-selectors",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        help="write deterministic validation evidence JSON to this path",
    )
    args = parser.parse_args()
    try:
        evidence = run_validation()
    except ContractValidationError as error:
        failure = {
            "profile": "bytedesk.downstream-port-validation-evidence/1",
            "result": "fail",
            "error": str(error),
        }
        if args.evidence is not None:
            write_evidence(args.evidence, failure)
        print(f"downstream-port validation failed: {error}", file=sys.stderr)
        return 1
    if args.evidence is not None:
        write_evidence(args.evidence, evidence)
    print(
        "downstream-port validation passed: "
        f"{evidence['counts']['ports']} ports, "
        f"{evidence['counts']['operations']} operations, "
        f"{evidence['counts']['conformanceCases']} conformance cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
