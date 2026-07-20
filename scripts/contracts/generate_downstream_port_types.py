#!/usr/bin/env python3
"""Generate the exact offline downstream-port type catalog and wire fixtures."""

from __future__ import annotations

import argparse
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

try:
    from referencing import Registry, Resource
except ModuleNotFoundError:  # Plain system Python is only a best-effort fallback.
    from jsonschema import RefResolver

    Registry = None
    Resource = None

try:
    import rfc8785
except ModuleNotFoundError:  # The repository's locked environment includes it.
    rfc8785 = None


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PORT_ROOT = REPOSITORY_ROOT / "contracts" / "ports" / "v1"
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"
REGISTRY_PATH = PORT_ROOT / "port-registry.json"
PROBLEM_CATALOG_PATH = PORT_ROOT / "problem-catalog.json"
CASE_CATALOG_PATH = PORT_ROOT / "conformance-cases.json"
TYPE_CATALOG_PATH = PORT_ROOT / "type-catalog.json"
FIXTURE_CATALOG_PATH = PORT_ROOT / "contract-fixtures.json"
PROBLEM_DETAILS_SCHEMA_PATH = SCHEMA_ROOT / "problem-details.schema.json"
SCHEMA_FIXTURE_INDEX_PATH = (
    REPOSITORY_ROOT / "contracts" / "fixtures" / "schema" / "index.json"
)

DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/"
PORT_SCHEMA_PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/ports/"
SHA256_ZERO = "sha256:" + "0" * 64
SHA256_ONE = "sha256:" + "1" * 64
SHA256_EMPTY = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SAMPLE_ID = "sample-1"
SAMPLE_TIME = "2026-01-01T00:00:00Z"
ARRAY_MAX_ITEMS = 1024
STRING_MAX_CODE_POINTS = 4096
BYTES_MAX_DECODED = 4 * 1024 * 1024
BYTES_MAX_ENCODED = (BYTES_MAX_DECODED * 4 + 2) // 3
OCI_BLOB_MAX_DECODED = 64 * 1024 * 1024
SIDE_EFFECT_STATE_ORDER = (
    "none",
    "not-committed",
    "committed-unchanged",
    "commit-unknown",
)

COMMON_ID = f"{SCHEMA_PREFIX}common/1.0.0"
SHA_REF = f"{COMMON_ID}#/$defs/sha256"
IDENTIFIER_REF = f"{COMMON_ID}#/$defs/identifier"
TIMESTAMP_REF = f"{COMMON_ID}#/$defs/timestamp"
MEDIA_TYPE_REF = f"{COMMON_ID}#/$defs/mediaType"
NONNEGATIVE_REF = f"{COMMON_ID}#/$defs/nonNegativeSafeInteger"
POSITIVE_REF = f"{COMMON_ID}#/$defs/positiveSafeInteger"
REDACTED_EVIDENCE_REF = f"{COMMON_ID}#/$defs/redactedEvidenceRef"
OCI_REPOSITORY_REF = f"{COMMON_ID}#/$defs/ociRepository"
TRUST_POLICY_REF = f"{COMMON_ID}#/$defs/trustPolicyRef"
ARTIFACT_DESCRIPTOR_REF = f"{COMMON_ID}#/$defs/artifactDescriptor"


class GenerationError(RuntimeError):
    """Raised when the source contracts cannot produce a closed catalog."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GenerationError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        require(key not in value, f"duplicate JSON member {key!r}")
        value[key] = child
    return value


def reject_constant(value: str) -> None:
    raise GenerationError(f"non-finite JSON number is forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required input is missing: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot load strict JSON {path}: {error}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def canonical_digest(value: Any) -> str:
    if rfc8785 is not None:
        payload = rfc8785.dumps(value)
    else:
        # This fallback is intentionally limited to the JCS-safe data model used
        # by the generated port artifacts. The locked repository environment
        # independently rechecks the same bytes with the RFC 8785 package.
        def require_jcs_safe(child: Any) -> None:
            if isinstance(child, float):
                raise GenerationError("floating-point JSON requires the locked RFC 8785 library")
            if isinstance(child, int) and not isinstance(child, bool):
                require(
                    -9007199254740991 <= child <= 9007199254740991,
                    "unsafe JSON integer is not canonicalizable",
                )
            if isinstance(child, str):
                require(
                    not any(0xD800 <= ord(character) <= 0xDFFF for character in child),
                    "lone surrogate is not canonicalizable",
                )
            elif isinstance(child, dict):
                for key, item in child.items():
                    require_jcs_safe(key)
                    require_jcs_safe(item)
            elif isinstance(child, list):
                for item in child:
                    require_jcs_safe(item)

        require_jcs_safe(value)
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def output_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


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


def schema_id(name: str) -> str:
    return f"{SCHEMA_PREFIX}{name}/1.0.0"


def type_schema_id(reference: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", reference.lower()).strip("-")
    require(bool(slug), f"cannot derive stable type schema ID from {reference!r}")
    return f"{PORT_SCHEMA_PREFIX}types/{slug}/1.0.0"


def contract_schema_id(contract_id: str) -> str:
    contract_name = contract_id.removeprefix("bytedesk.port.").removesuffix("/1")
    return f"{PORT_SCHEMA_PREFIX}contracts/{contract_name.replace('.', '/')}/1.0.0"


def kebab_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", value).replace("_", "-").lower()


def field_value_type_id(
    port_id: str,
    operation_id: str,
    direction: str,
    field_name: str,
) -> str:
    port_name = port_id.removeprefix("bytedesk.port.").removesuffix("/1")
    return (
        f"bytedesk.port-field.{port_name}.{operation_id}.{direction}."
        f"{kebab_case(field_name)}/1"
    )


def normalize_registry_value_types(registry: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(registry)
    seen: set[str] = set()
    for port in normalized["ports"]:
        for operation in port["operations"]:
            for direction, fields_key in (
                ("request", "requestFields"),
                ("result", "resultFields"),
            ):
                for field in operation[fields_key]:
                    value_type = field_value_type_id(
                        port["portId"],
                        operation["operationId"],
                        direction,
                        field["name"],
                    )
                    require(value_type not in seen, f"duplicate field value type: {value_type}")
                    seen.add(value_type)
                    field["valueType"] = value_type
    return normalized


def normalize_case_port_suites(
    cases: dict[str, Any], registry: dict[str, Any]
) -> dict[str, Any]:
    normalized = deepcopy(cases)
    suites_by_port = {port["portId"]: port["suite"] for port in registry["ports"]}
    for case in normalized["cases"]:
        suites: list[str] = []
        for cover in case["covers"]:
            require(cover["portId"] in suites_by_port, f"case covers unknown port: {cover['portId']}")
            suite = suites_by_port[cover["portId"]]
            if suite not in suites:
                suites.append(suite)
        case["portSuites"] = suites
    return normalized


CLI_COMMANDS = [
    "contract verify",
    "catalog list",
    "catalog show",
    "package validate",
    "package build",
    "render",
    "artifact publish",
    "artifact pull",
    "artifact inspect",
    "artifact verify",
    "install preview",
    "install apply",
    "binding show",
    "update preview",
    "update apply",
    "deployment status",
    "deployment recover",
    "receipt verify",
]


def semantic_string_override(
    port_id: str,
    operation_id: str,
    direction: str,
    field_name: str,
) -> tuple[str, dict[str, Any], str]:
    key = (port_id, operation_id, direction, field_name)
    enums: dict[tuple[str, str, str, str], list[str]] = {
        ("bytedesk.port.catalog/1", "resolve-catalog-release", "request", "channel"): ["stable", "preview", "deprecated"],
        ("bytedesk.port.scm/1", "receive-webhook", "request", "provider"): ["github", "gitlab", "generic"],
        ("bytedesk.port.scm/1", "receive-webhook", "result", "eventKind"): ["push", "pull-request", "tag", "scheduled-reconciliation"],
        ("bytedesk.port.renderer-strategy/1", "select-renderer", "request", "targetHarness"): ["native", "hermes", "openclaw"],
        ("bytedesk.port.renderer-strategy/1", "select-qualification-renderer", "request", "targetHarness"): ["native", "hermes", "openclaw"],
        ("bytedesk.port.renderer-strategy/1", "select-qualification-renderer", "request", "targetPlatform"): ["linux/amd64", "linux/arm64"],
        ("bytedesk.port.renderer-strategy/1", "select-renderer", "request", "targetPlatform"): ["linux/amd64", "linux/arm64"],
        ("bytedesk.port.kms-signing/1", "resolve-signing-request", "result", "resolution"): ["not-seen", "signed", "denied", "indeterminate"],
        ("bytedesk.port.evidence-archive/1", "put-evidence", "request", "retentionClass"): ["standard", "extended", "legal-hold"],
        ("bytedesk.port.consumer-authority-approval/1", "resolve-authority-snapshot", "request", "operation"): ["compile", "activate", "recover"],
        ("bytedesk.port.consumer-authority-approval/1", "resolve-skill-approval", "request", "operation"): ["render", "compile", "activate", "recover", "runtime_execute"],
        ("bytedesk.port.consumer-projection/1", "resolve-consumer-subject", "request", "resolutionMode"): ["resolve-only", "consumer-managed-create"],
        ("bytedesk.port.desired-state-store/1", "read-target-state", "request", "consistency"): ["authoritative"],
        ("bytedesk.port.desired-state-store/1", "resolve-idempotency", "result", "resolution"): ["not-seen", "committed", "rejected", "indeterminate"],
        ("bytedesk.port.control-plane-api-events/1", "read-resource", "request", "resourceType"): ["action", "candidate", "catalog-index", "consumer-authority", "consumer-deployment", "deployment-receipt", "installation", "region-fence", "rollout", "skill-approval", "target-delivery-state", "verification-result"],
        ("bytedesk.port.control-plane-api-events/1", "read-resource", "result", "readOutcome"): ["found", "not-modified"],
        ("bytedesk.port.control-plane-api-events/1", "resynchronize-events", "request", "aggregateType"): ["installation", "action", "candidate", "rollout", "target-delivery-state"],
        ("bytedesk.port.promotion-coordinator/1", "evaluate-evidence", "result", "decision"): ["permitted", "denied", "indeterminate"],
        ("bytedesk.port.promotion-coordinator/1", "authorize-activation", "request", "activationMode"): ["isolated_candidate", "guarded_in_place"],
        ("bytedesk.port.promotion-coordinator/1", "cancel-rollout", "result", "cancellationOutcome"): ["cancelled", "too-late", "already-terminal"],
        ("bytedesk.port.private-compiler/1", "resolve-compile-attempt", "result", "resolution"): ["not-seen", "committed", "denied", "indeterminate"],
        ("bytedesk.port.host-reconciler/1", "recover-attempt-journal", "result", "recoveryDisposition"): ["resume-staging", "complete-switch", "quarantine-indeterminate", "already-complete", "fenced"],
        ("bytedesk.port.host-reconciler/1", "cleanup-candidate", "result", "cleanupResult"): ["removed", "retained-active", "retained-predecessor", "retained-evidence", "no-op"],
        ("bytedesk.port.capability-verifier/1", "verify-capability-result", "result", "policyOutcome"): ["permitted", "denied"],
        ("bytedesk.port.cli-automation/1", "execute-local", "request", "command"): CLI_COMMANDS,
        ("bytedesk.port.cli-automation/1", "execute-remote", "request", "command"): CLI_COMMANDS,
        ("bytedesk.port.cli-automation/1", "execute-local", "request", "outputMode"): ["human", "bytedesk.cli-result/1-json"],
        ("bytedesk.port.cli-automation/1", "execute-remote", "request", "waitMode"): ["no-wait", "wait-for-terminal"],
        ("bytedesk.port.supply-chain-evidence/1", "evaluate-licenses", "request", "expressionParserProfile"): ["spdx-license-expression-2.3-strict/1"],
        ("bytedesk.port.supply-chain-evidence/1", "evaluate-licenses", "request", "licenseListVersion"): ["3.28.0"],
        ("bytedesk.port.release-status-head/1", "append-release-status", "request", "subjectKind"): ["product_release", "renderer_release"],
        ("bytedesk.port.release-status-head/1", "append-release-status", "request", "status"): ["current", "withdrawn", "revoked", "end_of_support"],
        ("bytedesk.port.release-status-head/1", "resolve-current-status", "request", "subjectKind"): ["product_release", "renderer_release"],
        ("bytedesk.port.release-status-head/1", "resolve-status-head", "request", "subjectKind"): ["product_release", "renderer_release"],
    }
    base = {"$ref": type_schema_id("primitive:string")}
    if key in enums:
        values = enums[key]
        return "enum", {"allOf": [base, {"enum": values}]}, values[0]
    if field_name == "mediaType":
        return "media-type", {"allOf": [base, {"$ref": MEDIA_TYPE_REF}]}, "application/json"
    if field_name == "repository":
        if port_id == "bytedesk.port.oci-registry/1":
            return "oci-repository", {"allOf": [base, {"$ref": OCI_REPOSITORY_REF}]}, "registry.example.invalid/agent-delivery"
        return "repository-uri", {"allOf": [base, {"type": "string", "format": "uri", "maxLength": 2048, "pattern": "^https://"}]}, "https://example.invalid/agents.git"
    if field_name == "audience":
        return (
            "audience-token",
            {
                "allOf": [
                    base,
                    {
                        "pattern": "^[A-Za-z0-9][A-Za-z0-9._~:/-]{0,511}$",
                        "maxLength": 512,
                    },
                ]
            },
            "agent-delivery-private-compiler",
        )
    if field_name in {"commit", "immutableCommit"}:
        return "immutable-commit", {"allOf": [base, {"pattern": "^(?:[0-9a-f]{40}|[0-9a-f]{64})$", "maxLength": 64}]}, "0" * 40
    if field_name in {"nonce", "dispatchNonce"}:
        return "nonce", {"allOf": [base, {"pattern": "^[A-Za-z0-9_-]{16,512}$", "maxLength": 512}]}, "nonce-1234567890"
    if field_name in {"quiesceToken", "resumeToken"}:
        return "opaque-token", {"allOf": [base, {"pattern": "^[A-Za-z0-9._~:-]{16,4096}$", "maxLength": 4096}]}, "token-1234567890"
    if field_name in {"location", "apiEndpoint"}:
        return "uri", {"allOf": [base, {"type": "string", "format": "uri", "maxLength": 2048}]}, "https://api.example.invalid/v1/actions/action-1"
    if field_name in {"inputPath", "offlineContractBundlePath", "receiptPath", "trustPolicyPath"}:
        return "filesystem-path", {"allOf": [base, {"pattern": "^[^\\u0000\\r\\n]+$", "maxLength": 4096}]}, "artifacts/input.json"
    if field_name == "consumerRevision":
        return "revision-token", {"allOf": [base, {"pattern": "^[A-Za-z0-9._:-]{1,256}$", "maxLength": 256}]}, "revision-1"
    if field_name == "reasonCode":
        return "reason-code", {"allOf": [base, {"pattern": "^[a-z][a-z0-9_]{0,127}$", "maxLength": 128}]}, "operator_requested"
    if field_name == "targetHarnessVersion":
        return (
            "semantic-version",
            {
                "allOf": [
                    base,
                    {
                        "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
                        "maxLength": 128,
                    },
                ]
            },
            "26.1.2",
        )
    raise GenerationError(f"primitive:string field lacks a semantic refinement: {key}")


def semantic_integer_override(
    port_id: str,
    operation_id: str,
    direction: str,
    field_name: str,
) -> tuple[str, dict[str, Any], int]:
    base = {"$ref": type_schema_id("primitive:nonnegative-integer")}
    if field_name == "limit":
        return "pagination-limit", {"allOf": [base, {"minimum": 1, "maximum": 1000}]}, 100
    if field_name == "maximumBytes":
        maximum = 4194304 if port_id == "bytedesk.port.catalog/1" else 67108864
        refinement = "byte-limit-4mib" if maximum == 4194304 else "byte-limit-64mib"
        return refinement, {"allOf": [base, {"minimum": 1, "maximum": maximum}]}, maximum
    if field_name == "deadlineMilliseconds":
        return "deadline-milliseconds", {"allOf": [base, {"minimum": 1, "maximum": 300000}]}, 30000
    if field_name == "timeoutSeconds":
        return "timeout-seconds", {"allOf": [base, {"minimum": 1, "maximum": 86400}]}, 300
    if field_name == "pollMaximumSeconds":
        return "poll-maximum-seconds", {"allOf": [base, {"minimum": 1, "maximum": 30}]}, 30
    if field_name in {"afterRevision", "knownSequence"}:
        return "zero-based-cursor", {"allOf": [base, {"minimum": 0, "maximum": 9007199254740991}]}, 0
    return "positive-counter", {"allOf": [base, {"minimum": 1, "maximum": 9007199254740991}]}, 1


def ref(target: str) -> dict[str, str]:
    return {"$ref": target}


def nullable(target: dict[str, Any]) -> dict[str, Any]:
    return {"oneOf": [target, {"type": "null"}]}


def closed_object(
    properties: dict[str, Any], required: Iterable[str] | None = None
) -> dict[str, Any]:
    required_fields = list(properties) if required is None else list(required)
    return {
        "type": "object",
        "required": required_fields,
        "properties": properties,
        "additionalProperties": False,
        "unevaluatedProperties": False,
    }


def bounded_string(*, pattern: str | None = None, enum: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "string",
        "minLength": 1,
        "maxLength": STRING_MAX_CODE_POINTS,
    }
    if pattern is not None:
        schema["pattern"] = pattern
    if enum is not None:
        schema["enum"] = enum
    return schema


def bounded_bytes() -> dict[str, Any]:
    return {
        "type": "string",
        "minLength": 0,
        "maxLength": BYTES_MAX_ENCODED,
        "pattern": "^(?:[A-Za-z0-9_-]{4})*(?:[A-Za-z0-9_-]{2,3})?$",
        "contentEncoding": "base64url-no-padding",
    }


def schema_document(reference: str, body: dict[str, Any]) -> dict[str, Any]:
    document = {"$schema": DIALECT, "$id": type_schema_id(reference)}
    document.update(deepcopy(body))
    return document


def iter_references(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str):
                yield child
            else:
                yield from iter_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_references(child)


def load_source_schemas() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    schemas: dict[str, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        schema_identifier = schema.get("$id")
        require(
            isinstance(schema_identifier, str) and schema_identifier.startswith(SCHEMA_PREFIX),
            f"schema has no accepted ID: {path}",
        )
        require(schema_identifier not in schemas, f"duplicate schema ID: {schema_identifier}")
        Draft202012Validator.check_schema(schema)
        schemas[schema_identifier] = schema
        paths[schema_identifier] = path.relative_to(REPOSITORY_ROOT).as_posix()
    return schemas, paths


def load_positive_schema_fixtures() -> dict[str, Any]:
    index = load_json(SCHEMA_FIXTURE_INDEX_PATH)
    fixtures: dict[str, Any] = {}
    for entry in index.get("fixtures", []):
        if not isinstance(entry, dict) or entry.get("valid") is not True:
            continue
        schema_identifier = entry.get("schemaId")
        fixture_path = entry.get("path")
        if (
            isinstance(schema_identifier, str)
            and schema_identifier not in fixtures
            and isinstance(fixture_path, str)
        ):
            fixtures[schema_identifier] = load_json(REPOSITORY_ROOT / fixture_path)
    explicit_fallbacks = {
        schema_id("renderer-attempt-authentication-evidence"): (
            SCHEMA_FIXTURE_INDEX_PATH.parent
            / "positive"
            / "renderer-attempt-authentication-evidence__native-amd64.json"
        ),
        schema_id("renderer-qualification-selection"): (
            SCHEMA_FIXTURE_INDEX_PATH.parent
            / "positive"
            / "renderer-qualification-selection__native-amd64.json"
        ),
        schema_id("renderer-qualification-attempt"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/native-qualification-attempt.json"
        ),
        schema_id("renderer-qualification-attempt-authentication-evidence"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/native-qualification-attempt-auth.json"
        ),
        schema_id("renderer-qualification-receipt"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/native-qualification-receipt.json"
        ),
        schema_id("renderer-qualification-receipt-authentication-evidence"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/native-qualification-receipt-auth.json"
        ),
        schema_id("release-qualification-policy"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/release-qualification-policy.json"
        ),
        schema_id("renderer-qualification-suite"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/qualification-suite.json"
        ),
        schema_id("release-status-head-checkpoint"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/product-release-status-head-initial.json"
        ),
        schema_id("release-status-head-authentication-evidence"): (
            REPOSITORY_ROOT
            / "contracts/fixtures/operations/renderer-cas/product-release-status-head-initial-authentication-evidence.json"
        ),
    }
    for schema_identifier, fixture_path in explicit_fallbacks.items():
        if schema_identifier not in fixtures:
            fixtures[schema_identifier] = load_json(fixture_path)
    return fixtures


def build_problem_details_schema(
    port_registry: dict[str, Any], problem_catalog: dict[str, Any]
) -> dict[str, Any]:
    """Compile the closed RFC 9457 schema from its two authority sources."""

    require(
        port_registry.get("$schema")
        == "https://schemas.bytedesk.ai/agent-delivery/v1/downstream-port-registry/1.0.0",
        "port registry schema binding drift",
    )
    require(
        port_registry.get("profile") == "bytedesk.downstream-port-registry/1",
        "port registry profile drift",
    )
    require(port_registry.get("version") == 1, "port registry version drift")
    require(
        problem_catalog.get("$schema")
        == "https://schemas.bytedesk.ai/agent-delivery/v1/problem-catalog/1.0.0",
        "problem catalog schema binding drift",
    )
    require(
        problem_catalog.get("profile") == "bytedesk.problem-catalog/1",
        "problem catalog profile drift",
    )
    require(problem_catalog.get("version") == 1, "problem catalog version drift")
    problem_entries = problem_catalog.get("problems")
    require(isinstance(problem_entries, list), "problem catalog problems must be an array")

    problems: dict[str, dict[str, Any]] = {}
    for index, problem in enumerate(problem_entries):
        require(isinstance(problem, dict), f"problem[{index}] is not an object")
        require(
            set(problem)
            == {"code", "type", "status", "retryable", "sideEffectStates", "cliExit"},
            f"problem[{index}] members drift",
        )
        code = problem.get("code")
        require(
            isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]*", code) is not None,
            f"invalid problem code: {code!r}",
        )
        require(code not in problems, f"duplicate problem code: {code}")
        require(
            problem.get("type")
            == f"https://problems.bytedesk.ai/agent-delivery/{code.replace('_', '-')}",
            f"problem type/code mismatch: {code}",
        )
        status = problem.get("status")
        require(
            type(status) is int and 400 <= status <= 599,
            f"invalid problem status: {code}",
        )
        require(type(problem.get("retryable")) is bool, f"invalid retryable flag: {code}")
        cli_exit = problem.get("cliExit")
        require(
            type(cli_exit) is int and 2 <= cli_exit <= 13,
            f"invalid CLI exit class: {code}",
        )
        states = problem.get("sideEffectStates")
        require(
            isinstance(states, list)
            and states
            and all(isinstance(state, str) for state in states),
            f"invalid side-effect states: {code}",
        )
        require(len(states) == len(set(states)), f"duplicate side-effect state: {code}")
        require(
            states == [state for state in SIDE_EFFECT_STATE_ORDER if state in states],
            f"non-canonical side-effect state order: {code}",
        )
        problems[code] = problem

    codes = list(problems)
    require(codes == sorted(codes), "problem catalog must be sorted by stable code")

    ports = port_registry.get("ports")
    require(isinstance(ports, list) and ports, "port registry ports must be a non-empty array")
    port_ids: set[str] = set()
    operation_entries: list[tuple[str, str, list[dict[str, Any]]]] = []
    referenced_states: dict[str, set[str]] = {}
    operation_keys: set[tuple[str, str]] = set()
    for port_index, port in enumerate(ports):
        require(isinstance(port, dict), f"port[{port_index}] is not an object")
        port_id = port.get("portId")
        require(isinstance(port_id, str) and port_id, f"invalid port ID: {port_index}")
        require(port_id not in port_ids, f"duplicate port ID: {port_id}")
        port_ids.add(port_id)
        operations = port.get("operations")
        require(
            isinstance(operations, list) and operations,
            f"port operations must be a non-empty array: {port_id}",
        )
        for operation_index, operation in enumerate(operations):
            require(
                isinstance(operation, dict),
                f"operation[{operation_index}] is not an object: {port_id}",
            )
            operation_id = operation.get("operationId")
            require(
                isinstance(operation_id, str)
                and re.fullmatch(r"[a-z][a-z0-9-]*", operation_id) is not None,
                f"invalid operation ID: {port_id}/{operation_id!r}",
            )
            operation_key = (port_id, operation_id)
            require(operation_key not in operation_keys, f"duplicate operation: {operation_key}")
            operation_keys.add(operation_key)
            errors = operation.get("errors")
            require(
                isinstance(errors, list) and errors,
                f"operation errors must be a non-empty array: {operation_key}",
            )
            operation_codes: set[str] = set()
            for error_index, error in enumerate(errors):
                require(
                    isinstance(error, dict)
                    and set(error) == {"code", "sideEffectState"},
                    f"operation error members drift: {operation_key}/{error_index}",
                )
                code = error.get("code")
                state = error.get("sideEffectState")
                require(code in problems, f"operation references unknown problem: {operation_key}/{code}")
                require(code not in operation_codes, f"duplicate operation problem: {operation_key}/{code}")
                require(
                    state in SIDE_EFFECT_STATE_ORDER,
                    f"invalid operation side-effect state: {operation_key}/{code}",
                )
                require(
                    state in problems[code]["sideEffectStates"],
                    f"operation side-effect state is not permitted: {operation_key}/{code}",
                )
                operation_codes.add(code)
                referenced_states.setdefault(code, set()).add(state)
            operation_entries.append((port_id, operation_id, errors))

    require(
        set(problems) == set(referenced_states),
        "problem catalog and registered operation errors differ; "
        f"missing={sorted(set(referenced_states) - set(problems))} "
        f"orphans={sorted(set(problems) - set(referenced_states))}",
    )
    for code, problem in problems.items():
        require(
            set(problem["sideEffectStates"]) == referenced_states[code],
            f"problem side-effect permissions differ from operation mappings: {code}",
        )

    problem_property_names = {
        "type",
        "title",
        "status",
        "detail",
        "instance",
        "code",
        "portId",
        "operationId",
        "correlationId",
        "actionId",
        "retryable",
        "sideEffectState",
        "retryAfterSeconds",
        "violations",
        "expectedRevision",
        "expectedDigest",
        "currentRevision",
        "currentDigest",
        "documentation",
    }
    maximum_properties = len(problem_property_names)
    problem_variants = [
        {
            "type": "object",
            "maxProperties": maximum_properties,
            "properties": {
                "code": {"const": code},
                "type": {"const": problem["type"]},
                "status": {"const": problem["status"]},
                "retryable": {"const": problem["retryable"]},
                "sideEffectState": {"enum": problem["sideEffectStates"]},
            },
            "required": ["code", "type", "status", "retryable", "sideEffectState"],
        }
        for code, problem in problems.items()
    ]
    operation_variants = []
    for port_id, operation_id, errors in sorted(
        operation_entries, key=lambda entry: (entry[0], entry[1])
    ):
        error_variants = [
            {
                "type": "object",
                "properties": {
                    "code": {"const": error["code"]},
                    "sideEffectState": {"const": error["sideEffectState"]},
                },
                "required": ["code", "sideEffectState"],
                "maxProperties": maximum_properties,
            }
            for error in sorted(errors, key=lambda entry: entry["code"])
        ]
        operation_variants.append(
            {
                "type": "object",
                "properties": {
                    "portId": {"const": port_id},
                    "operationId": {"const": operation_id},
                },
                "required": ["portId", "operationId"],
                "allOf": [{"oneOf": error_variants}],
                "maxProperties": maximum_properties,
            }
        )

    schema = {
        "$schema": DIALECT,
        "$id": schema_id("problem-details"),
        "title": "Closed Agent Delivery RFC 9457 problem details",
        "type": "object",
        "required": [
            "type",
            "title",
            "status",
            "code",
            "portId",
            "operationId",
            "correlationId",
            "retryable",
            "sideEffectState",
            "violations",
            "documentation",
        ],
        "properties": {
            "type": {
                "type": "string",
                "format": "uri",
                "maxLength": 2048,
                "pattern": r"^https://problems\.bytedesk\.ai/agent-delivery/",
            },
            "title": {"type": "string", "minLength": 1, "maxLength": 256},
            "status": {"type": "integer", "minimum": 400, "maximum": 599},
            "detail": {"type": "string", "maxLength": 2048},
            "instance": {"type": "string", "format": "uri-reference", "maxLength": 2048},
            "code": {"type": "string", "enum": codes},
            "portId": {"type": "string", "enum": sorted(port_ids)},
            "operationId": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "pattern": r"^[a-z][a-z0-9-]*$",
            },
            "correlationId": {"$ref": IDENTIFIER_REF},
            "actionId": {"$ref": IDENTIFIER_REF},
            "retryable": {"type": "boolean"},
            "sideEffectState": {"type": "string", "enum": list(SIDE_EFFECT_STATE_ORDER)},
            "retryAfterSeconds": {"type": "integer", "minimum": 0, "maximum": 86400},
            "violations": {
                "type": "array",
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "required": ["pointer", "code", "message"],
                    "properties": {
                        "pointer": {
                            "type": "string",
                            "maxLength": 1024,
                            "pattern": r"^(?:/(?:[^~/]|~[01])*)*$",
                        },
                        "code": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 128,
                            "pattern": r"^[a-z][a-z0-9_]{0,127}$",
                        },
                        "message": {"type": "string", "minLength": 1, "maxLength": 512},
                    },
                    "additionalProperties": False,
                    "unevaluatedProperties": False,
                },
            },
            "expectedRevision": {"$ref": POSITIVE_REF},
            "expectedDigest": {"$ref": SHA_REF},
            "currentRevision": {"$ref": POSITIVE_REF},
            "currentDigest": {"$ref": SHA_REF},
            "documentation": {
                "type": "string",
                "format": "uri",
                "maxLength": 2048,
                "pattern": r"^https://docs\.bytedesk\.ai/agent-delivery/problems/",
            },
        },
        "dependentRequired": {
            "expectedRevision": ["expectedDigest"],
            "expectedDigest": ["expectedRevision"],
            "currentRevision": ["currentDigest"],
            "currentDigest": ["currentRevision"],
        },
        "allOf": [
            {"oneOf": problem_variants},
            {"oneOf": operation_variants},
            {
                "if": {
                    "properties": {"retryable": {"const": False}},
                    "required": ["retryable"],
                },
                "then": {"not": {"required": ["retryAfterSeconds"]}},
            },
        ],
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "description": (
            "Explanatory, redacted RFC 9457 output. The closed catalog binds every code "
            "to one type, status, retryability value, permitted side-effect-state set, and "
            "CLI exit class. The required portId and operationId bind the exact registered "
            "code/side-effect-state pair for the failed operation. It never carries "
            "authority, secret values, stack traces, or raw provider payloads."
        ),
    }
    require(
        set(schema["properties"]) == problem_property_names,
        "problem-details root property closure and variant bound differ",
    )
    Draft202012Validator.check_schema(schema)
    return schema


def generate_problem_details_schema() -> dict[str, Any]:
    """Load authoritative inputs and invoke the one problem-schema compiler."""

    return build_problem_details_schema(
        load_json(REGISTRY_PATH), load_json(PROBLEM_CATALOG_PATH)
    )


EXACT_SCHEMA_TARGETS = {
    "action": schema_id("action"),
    "archive-root": schema_id("archive-root"),
    "authorization-decision-proof": schema_id("authorization-decision-proof"),
    "candidate": schema_id("candidate"),
    "canary-evidence": schema_id("canary-evidence"),
    "catalog-index": schema_id("catalog-index"),
    "catalog-index#/$defs/catalogRelease": (
        f"{schema_id('catalog-index')}#/properties/entries/items"
    ),
    "command-request": schema_id("command-request"),
    "common#/$defs/digest": SHA_REF,
    "common#/$defs/identifier": IDENTIFIER_REF,
    "common#/$defs/nonce": f"{COMMON_ID}#/$defs/nonce",
    "common#/$defs/ociRepository": OCI_REPOSITORY_REF,
    "common#/$defs/positiveSafeInteger": POSITIVE_REF,
    "common#/$defs/timestamp": TIMESTAMP_REF,
    "common#/$defs/artifactDescriptor": ARTIFACT_DESCRIPTOR_REF,
    ARTIFACT_DESCRIPTOR_REF: ARTIFACT_DESCRIPTOR_REF,
    "bytedesk.port.consumer-deployment-descriptor/1": (
        f"{COMMON_ID}#/$defs/consumerDeploymentDescriptor"
    ),
    "bytedesk.port.consumer-runtime-release-descriptor/1": (
        f"{COMMON_ID}#/$defs/consumerRuntimeReleaseDescriptor"
    ),
    "consumer-authority": schema_id("consumer-authority"),
    "deployment-receipt": schema_id("deployment-receipt"),
    "evaluation-attestation": schema_id("evaluation-attestation"),
    "observation": schema_id("observation"),
    "precondition": schema_id("precondition"),
    "private-compilation-input": schema_id("private-compilation-input"),
    "private-compilation-input#/$defs/policyDigests": (
        f"{schema_id('private-compilation-input')}#/$defs/policyDigests"
    ),
    "recovery-plan": schema_id("recovery-plan"),
    "region-fence": schema_id("region-fence"),
    "rollout": schema_id("rollout"),
    "schema-descriptor": schema_id("schema-descriptor"),
    "kms-signing-request": schema_id("kms-signing-request"),
    "skill-approval": schema_id("skill-approval"),
    "target-delivery-state": schema_id("target-delivery-state"),
    "verification-result": schema_id("verification-result"),
    "renderer-selection": schema_id("renderer-selection"),
    "renderer-execution-receipt": schema_id("renderer-execution-receipt"),
    schema_id("harness-render"): schema_id("harness-render"),
    schema_id("publication-evidence"): schema_id("publication-evidence"),
    schema_id("public-source-authentication-evidence"): schema_id(
        "public-source-authentication-evidence"
    ),
    schema_id("release-qualification-finalization-matrix"): schema_id(
        "release-qualification-finalization-matrix"
    ),
    schema_id("release-qualification-policy"): schema_id(
        "release-qualification-policy"
    ),
    schema_id("release-qualification"): schema_id("release-qualification"),
    schema_id("release-status-eligibility-evidence"): schema_id(
        "release-status-eligibility-evidence"
    ),
    schema_id("release-status-append-resolution"): schema_id(
        "release-status-append-resolution"
    ),
    f"{schema_id('release-status-append-resolution')}#/$defs/appendResult": (
        f"{schema_id('release-status-append-resolution')}#/$defs/appendResult"
    ),
    schema_id("release-status-head-authentication-evidence"): schema_id(
        "release-status-head-authentication-evidence"
    ),
    schema_id("release-status-head-checkpoint"): schema_id(
        "release-status-head-checkpoint"
    ),
    f"{schema_id('release-status-head-checkpoint')}#/$defs/clientPriorState": (
        f"{schema_id('release-status-head-checkpoint')}#/$defs/clientPriorState"
    ),
    schema_id("renderer-execution-receipt"): schema_id(
        "renderer-execution-receipt"
    ),
    schema_id("renderer-selection"): schema_id("renderer-selection"),
    schema_id("renderer-qualification-suite"): schema_id(
        "renderer-qualification-suite"
    ),
    schema_id("signing-result"): schema_id("signing-result"),
    schema_id("trust-policy-pin-set"): schema_id("trust-policy-pin-set"),
    schema_id("trust-policy-pin-set-descriptor"): schema_id(
        "trust-policy-pin-set-descriptor"
    ),
    schema_id("trust-policy-pin-set-provider-evidence"): schema_id(
        "trust-policy-pin-set-provider-evidence"
    ),
    schema_id("trust-policy-pin-set-resolution-query"): schema_id(
        "trust-policy-pin-set-resolution-query"
    ),
    schema_id("trust-policy-pin-set-resolution"): schema_id(
        "trust-policy-pin-set-resolution"
    ),
    schema_id("renderer-attempt-authority"): schema_id("renderer-attempt-authority"),
    schema_id("renderer-attempt-authentication-evidence"): schema_id(
        "renderer-attempt-authentication-evidence"
    ),
    schema_id("renderer-execution-authentication-evidence"): schema_id(
        "renderer-execution-authentication-evidence"
    ),
    schema_id("renderer-qualification-selection"): schema_id(
        "renderer-qualification-selection"
    ),
    schema_id("renderer-qualification-attempt"): schema_id(
        "renderer-qualification-attempt"
    ),
    schema_id("renderer-qualification-attempt-authentication-evidence"): schema_id(
        "renderer-qualification-attempt-authentication-evidence"
    ),
    schema_id("renderer-qualification-receipt"): schema_id(
        "renderer-qualification-receipt"
    ),
    schema_id("renderer-qualification-receipt-authentication-evidence"): schema_id(
        "renderer-qualification-receipt-authentication-evidence"
    ),
    schema_id("render-manifest"): schema_id("render-manifest"),
    schema_id("renderer-capability"): schema_id("renderer-capability"),
    schema_id("renderer-compatibility-result"): schema_id(
        "renderer-compatibility-result"
    ),
    "primitive:identifier": IDENTIFIER_REF,
    "primitive:media-type": MEDIA_TYPE_REF,
    "primitive:nonnegative-integer": NONNEGATIVE_REF,
    "bytedesk.port.cli-result/1": schema_id("cli-result"),
    "bytedesk.port.desired-state-commit-receipt/1": schema_id(
        "desired-state-store-receipt"
    ),
    "bytedesk.port.migration-checkpoint/1": schema_id(
        "desired-state-store-migration"
    ),
    "bytedesk.port.promotion-result/1": schema_id("promotion-decision"),
    "bytedesk.port.signature-envelope/1": schema_id("signing-result"),
}

EXACT_ARRAY_SCHEMA_REFS = {
    "bytedesk.port.activation-deployable-graph/1",
    "bytedesk.port.activation-candidate-ready-evidence-set/1",
    "bytedesk.port.activation-authority-snapshot-set/1",
    "bytedesk.port.activation-authorization-decision-proof-set/1",
}


def inline_definitions() -> dict[str, tuple[dict[str, Any], Any]]:
    signature_schema = ref(schema_id("signing-result"))
    receipt_schema = ref(schema_id("desired-state-store-receipt"))
    migration_schema = ref(schema_id("desired-state-store-migration"))
    action_schema = ref(schema_id("action"))

    definitions: dict[str, tuple[dict[str, Any], Any]] = {
        "action-or-null": (nullable(action_schema), None),
        "common#/$defs/digest-or-null": (nullable(ref(SHA_REF)), None),
        "primitive:boolean": ({"type": "boolean"}, True),
        "primitive:bounded-bytes": (bounded_bytes(), ""),
        "primitive:opaque-token": (
            {
                "oneOf": [
                    {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": STRING_MAX_CODE_POINTS,
                        "pattern": "^[A-Za-z0-9._~:-]+$",
                    },
                    {"type": "null"},
                ]
            },
            None,
        ),
        "primitive:rfc3339-utc": (
            {
                "type": "string",
                "maxLength": 64,
                "format": "date-time",
                "pattern": "Z$",
            },
            SAMPLE_TIME,
        ),
        "primitive:uri": (
            {
                "type": "string",
                "format": "uri",
                "minLength": 1,
                "maxLength": 2048,
            },
            "https://example.invalid/resource/1",
        ),
        "primitive:string": (bounded_string(), "sample"),
        "bytedesk.port.cli-watch-exit-code/1": (
            {"type": "integer", "enum": [0, 10, 11, 12]},
            10,
        ),
        "bytedesk.port.desired-state-commit-receipt-or-null/1": (
            nullable(receipt_schema),
            None,
        ),
        "bytedesk.port.migration-checkpoint-or-null/1": (
            nullable(migration_schema),
            None,
        ),
        "bytedesk.port.signature-envelope-or-null/1": (
            nullable(signature_schema),
            None,
        ),
    }

    definitions.update(custom_port_definitions())
    return definitions


def custom_port_definitions() -> dict[str, tuple[dict[str, Any], Any]]:
    digest = ref(SHA_REF)
    identifier = ref(IDENTIFIER_REF)
    timestamp = ref(TIMESTAMP_REF)
    media_type = ref(MEDIA_TYPE_REF)
    nonnegative = ref(NONNEGATIVE_REF)
    positive = ref(POSITIVE_REF)
    evidence = ref(REDACTED_EVIDENCE_REF)
    repository = ref(OCI_REPOSITORY_REF)
    trust_policy = ref(TRUST_POLICY_REF)
    sha256_hex = {"type": "string", "pattern": "^[0-9a-f]{64}$", "maxLength": 64}

    definitions: dict[str, tuple[dict[str, Any], Any]] = {}

    def artifact_role(
        media_type_value: str,
        trust_purpose: str,
    ) -> dict[str, Any]:
        return {
            "allOf": [
                ref(ARTIFACT_DESCRIPTOR_REF),
                {
                    "required": ["mediaType", "trustPolicy"],
                    "properties": {
                        "mediaType": {"const": media_type_value},
                        "trustPolicy": {
                            "required": ["id"],
                            "properties": {"id": {"const": trust_purpose}},
                        },
                    },
                },
            ]
        }

    def artifact_role_sample(
        repository_suffix: str,
        media_type_value: str,
        trust_purpose: str,
        digest_value: str,
    ) -> dict[str, Any]:
        return {
            "repository": f"registry.example.invalid/consumer/{repository_suffix}",
            "digest": digest_value,
            "mediaType": media_type_value,
            "size": 0,
            "trustPolicy": {"id": trust_purpose, "digest": SHA256_ONE},
        }

    private_input_descriptor_schema = artifact_role(
        "application/vnd.bytedesk.agent.private-compilation-input.v1+json",
        "consumer-compilation-input-v1",
    )
    deployment_descriptor_schema = ref(
        f"{COMMON_ID}#/$defs/consumerDeploymentDescriptor"
    )
    compilation_evidence_descriptor_schema = artifact_role(
        "application/vnd.bytedesk.agent.private-compilation-evidence.v1+json",
        "consumer-compilation-evidence-v1",
    )
    private_input_descriptor_sample = artifact_role_sample(
        "compilation-inputs",
        "application/vnd.bytedesk.agent.private-compilation-input.v1+json",
        "consumer-compilation-input-v1",
        SHA256_ZERO,
    )
    compilation_evidence_descriptor_sample = artifact_role_sample(
        "compilation-evidence",
        "application/vnd.bytedesk.agent.private-compilation-evidence.v1+json",
        "consumer-compilation-evidence-v1",
        f"sha256:{'2' * 64}",
    )

    definitions["bytedesk.port.private-compilation-input-descriptor/1"] = (
        private_input_descriptor_schema,
        private_input_descriptor_sample,
    )
    definitions["bytedesk.port.private-compilation-evidence-descriptor/1"] = (
        compilation_evidence_descriptor_schema,
        compilation_evidence_descriptor_sample,
    )
    definitions["bytedesk.port.consumer-authority-candidate-descriptor/1"] = (
        artifact_role(
            "application/vnd.bytedesk.agent.candidate.v1+json",
            "consumer-authority-v1",
        ),
        artifact_role_sample(
            "candidates",
            "application/vnd.bytedesk.agent.candidate.v1+json",
            "consumer-authority-v1",
            SHA256_ZERO,
        ),
    )
    definitions["bytedesk.port.consumer-authority-binding-descriptor/1"] = (
        artifact_role(
            "application/vnd.bytedesk.agent.binding.v1+json",
            "consumer-authority-v1",
        ),
        artifact_role_sample(
            "bindings",
            "application/vnd.bytedesk.agent.binding.v1+json",
            "consumer-authority-v1",
            SHA256_ONE,
        ),
    )
    definitions["bytedesk.port.consumer-authority-descriptor/1"] = (
        artifact_role(
            "application/vnd.bytedesk.agent.consumer-authority.v1+json",
            "consumer-authority-v1",
        ),
        artifact_role_sample(
            "authority",
            "application/vnd.bytedesk.agent.consumer-authority.v1+json",
            "consumer-authority-v1",
            f"sha256:{'2' * 64}",
        ),
    )
    definitions["bytedesk.port.skill-approval-descriptor/1"] = (
        artifact_role(
            "application/vnd.bytedesk.agent.skill-approval.v1+json",
            "consumer-authority-v1",
        ),
        artifact_role_sample(
            "approvals",
            "application/vnd.bytedesk.agent.skill-approval.v1+json",
            "consumer-authority-v1",
            f"sha256:{'3' * 64}",
        ),
    )
    definitions["bytedesk.port.consumer-skill-descriptor/1"] = (
        {
            "oneOf": [
                artifact_role(
                    "application/vnd.bytedesk.agent.skill.v1+json",
                    "public-source-v1",
                ),
                artifact_role(
                    "application/vnd.bytedesk.agent.skill.v1+json",
                    "consumer-private-skill-v1",
                ),
            ]
        },
        artifact_role_sample(
            "skills",
            "application/vnd.bytedesk.agent.skill.v1+json",
            "consumer-private-skill-v1",
            f"sha256:{'4' * 64}",
        ),
    )
    definitions["bytedesk.port.public-skill-descriptor/1"] = (
        artifact_role(
            "application/vnd.bytedesk.agent.skill.v1+json",
            "public-source-v1",
        ),
        {
            "repository": "registry.example.invalid/bytedesk/public-skills",
            "digest": f"sha256:{'5' * 64}",
            "mediaType": "application/vnd.bytedesk.agent.skill.v1+json",
            "size": 0,
            "trustPolicy": {"id": "public-source-v1", "digest": SHA256_ONE},
        },
    )
    definitions["bytedesk.port.release-status-descriptor-or-null/1"] = (
        nullable(
            artifact_role(
                "application/vnd.bytedesk.agent.release-status.v1+json",
                "release-status-v1",
            )
        ),
        None,
    )
    definitions["bytedesk.port.release-replacement-descriptor-or-null/1"] = (
        nullable(
            {
                "oneOf": [
                    artifact_role(
                        "application/vnd.bytedesk.agent.product-release-manifest.v1+json",
                        "product-release-v1",
                    ),
                    artifact_role(
                        "application/vnd.bytedesk.agent.renderer-release.v1+json",
                        "product-release-v1",
                    ),
                ]
            }
        ),
        None,
    )
    definitions["bytedesk.port.private-compilation-artifacts-or-null/1"] = (
        nullable(
            closed_object(
                {
                    "compilationInputDescriptor": private_input_descriptor_schema,
                    "consumerDeploymentDescriptor": deployment_descriptor_schema,
                    "compilationEvidenceDescriptor": compilation_evidence_descriptor_schema,
                }
            )
        ),
        None,
    )
    definitions["bytedesk.port.problem-details-or-null/1"] = (
        nullable(ref(schema_id("problem-details"))),
        None,
    )

    definitions["bytedesk.port.activation-authorization/1"] = (
        ref(schema_id("activation-authorization")),
        {"$fixtureFrom": schema_id("activation-authorization")},
    )
    for reference, property_name in (
        ("bytedesk.port.activation-deployable-graph/1", "deployableGraph"),
        (
            "bytedesk.port.activation-candidate-ready-evidence-set/1",
            "candidateReadyEvidence",
        ),
        (
            "bytedesk.port.activation-authority-snapshot-set/1",
            "authoritySnapshots",
        ),
        (
            "bytedesk.port.activation-authorization-decision-proof-set/1",
            "authorizationDecisionProofs",
        ),
        (
            "bytedesk.port.activation-release-eligibility-descriptor/1",
            "releaseEligibility",
        ),
    ):
        definitions[reference] = (
            ref(f"{schema_id('activation-authorization')}#/properties/{property_name}"),
            {
                "$fixtureProperty": {
                    "schemaId": schema_id("activation-authorization"),
                    "property": property_name,
                }
            },
        )

    definitions["bytedesk.port.api-resource/1"] = (
        {
            "oneOf": [
                ref(schema_id(name))
                for name in (
                    "action",
                    "candidate",
                    "catalog-index",
                    "consumer-authority",
                    "consumer-deployment",
                    "deployment-receipt",
                    "installation",
                    "region-fence",
                    "rollout",
                    "skill-approval",
                    "target-delivery-state",
                    "verification-result",
                )
            ]
        },
        {"$fixtureFrom": schema_id("target-delivery-state")},
    )

    definitions["bytedesk.port.api-resource-or-null/1"] = (
        nullable(definitions["bytedesk.port.api-resource/1"][0]),
        None,
    )

    event_data = load_json(
        REPOSITORY_ROOT
        / "contracts"
        / "fixtures"
        / "schema"
        / "positive"
        / "event-data-envelope__notification.json"
    )
    definitions["bytedesk.port.sse-event/1"] = (
        closed_object(
            {
                "eventId": identifier,
                "data": ref(schema_id("event-data")),
                "dataDigest": digest,
                "aggregateSequence": positive,
            }
        ),
        {
            "eventId": "event-1",
            "data": event_data,
            "dataDigest": canonical_digest(event_data),
            "aggregateSequence": event_data["aggregate"]["sequence"],
        },
    )

    definitions["bytedesk.port.archive-commit-evidence/1"] = (
        closed_object(
            {
                "archiveId": identifier,
                "previousRootDigest": nullable(digest),
                "committedRootDigest": digest,
                "revision": positive,
                "preconditionDigest": digest,
                "storeEvidence": evidence,
                "recordedAt": timestamp,
            }
        ),
        {
            "archiveId": "archive-1",
            "previousRootDigest": None,
            "committedRootDigest": SHA256_ZERO,
            "revision": 1,
            "preconditionDigest": SHA256_ONE,
            "storeEvidence": {
                "digest": SHA256_ONE,
                "classification": "restricted",
            },
            "recordedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.archive-storage-receipt/1"] = (
        closed_object(
            {
                "evidenceDigest": digest,
                "storageKey": identifier,
                "region": identifier,
                "retentionClass": bounded_string(
                    enum=["standard", "extended", "legal-hold"]
                ),
                "storedAt": timestamp,
            }
        ),
        {
            "evidenceDigest": SHA256_ZERO,
            "storageKey": "evidence-1",
            "region": "us-east-1",
            "retentionClass": "standard",
            "storedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.capability-dispatch-receipt/1"] = (
        closed_object(
            {
                "checkId": identifier,
                "requestDigest": digest,
                "consumerId": identifier,
                "targetId": identifier,
                "candidateDigest": digest,
                "checkProfileDigest": digest,
                "nonce": bounded_string(pattern="^[A-Za-z0-9_-]{16,512}$"),
                "authorizationDecisionDigest": digest,
                "endpoint": {
                    "type": "string",
                    "format": "uri",
                    "minLength": 1,
                    "maxLength": 2048,
                },
                "coordinatorFencingToken": positive,
                "issuedAt": timestamp,
                "expiresAt": timestamp,
            }
        ),
        {
            "checkId": "check-1",
            "requestDigest": SHA256_ONE,
            "consumerId": "consumer-1",
            "targetId": "target-1",
            "candidateDigest": SHA256_ZERO,
            "checkProfileDigest": SHA256_ONE,
            "nonce": "nonce-1234567890",
            "authorizationDecisionDigest": SHA256_ZERO,
            "endpoint": "https://consumer.example.invalid/capability",
            "coordinatorFencingToken": 1,
            "issuedAt": SAMPLE_TIME,
            "expiresAt": "2026-01-01T00:05:00Z",
        },
    )

    authorization_schema = load_json(
        SCHEMA_ROOT / "authorization-decision-proof.schema.json"
    )
    authorization_proof = load_json(
        REPOSITORY_ROOT
        / "contracts"
        / "fixtures"
        / "schema"
        / "positive"
        / "authorization-decision-proof__policy-denied.json"
    )
    authorization_proof["schema"]["digest"] = canonical_digest(
        authorization_schema
    )
    permitted_proof = deepcopy(authorization_proof)
    permitted_proof["proofId"] = "permitted-proof-1"
    permitted_proof["capability"] = {
        "id": "capability.required",
        "digest": SHA256_ZERO,
    }
    permitted_proof["decision"] = {
        "class": "permitted",
        "code": "capability_check_permitted",
    }
    denied_sentinel_proof = deepcopy(authorization_proof)
    denied_sentinel_proof["proofId"] = "denied-sentinel-proof-1"
    denied_sentinel_proof["capability"] = {
        "id": "capability.denied-sentinel",
        "digest": SHA256_ONE,
    }

    capability_descriptor = closed_object(
        {
            "id": identifier,
            "digest": digest,
        }
    )
    uri = {
        "type": "string",
        "format": "uri",
        "minLength": 1,
        "maxLength": 2048,
    }
    certification_schema = closed_object(
        {
            "certificationId": identifier,
            "outcome": {"const": "not_applicable"},
            "consumerId": identifier,
            "subjectId": identifier,
            "targetId": identifier,
            "candidateDigest": digest,
            "checkProfileDigest": digest,
            "planDigest": digest,
            "desiredRevisionDigest": digest,
            "releaseDigest": digest,
            "deploymentDigest": digest,
            "authorityDigest": digest,
            "policyDigest": digest,
            "grantSetDigest": digest,
            "workloadIdentityDigest": digest,
            "signerIdentity": uri,
            "signerPolicy": trust_policy,
            "signatureEvidenceDigest": digest,
            "issuedAt": timestamp,
            "expiresAt": timestamp,
        }
    )
    certification_value = {
        "certificationId": "not-applicable-certification-1",
        "outcome": "not_applicable",
        "consumerId": "consumer-1",
        "subjectId": "subject-1",
        "targetId": "target-1",
        "candidateDigest": SHA256_ZERO,
        "checkProfileDigest": SHA256_ONE,
        "planDigest": SHA256_ZERO,
        "desiredRevisionDigest": SHA256_ONE,
        "releaseDigest": SHA256_ZERO,
        "deploymentDigest": SHA256_ONE,
        "authorityDigest": SHA256_ZERO,
        "policyDigest": SHA256_ONE,
        "grantSetDigest": SHA256_ZERO,
        "workloadIdentityDigest": SHA256_ONE,
        "signerIdentity": "spiffe://consumer.example/certification",
        "signerPolicy": {
            "id": "consumer-not-applicable-certification-v1",
            "digest": SHA256_ZERO,
        },
        "signatureEvidenceDigest": SHA256_ONE,
        "issuedAt": SAMPLE_TIME,
        "expiresAt": "2026-01-01T00:05:00Z",
    }
    definitions["bytedesk.port.capability-verification-proof-set/1"] = (
        {
            "oneOf": [
                closed_object(
                    {
                        "mode": {"const": "required"},
                        "dispatchAuthorization": ref(authorization_schema["$id"]),
                        "permittedCapability": ref(authorization_schema["$id"]),
                        "deniedSentinel": ref(authorization_schema["$id"]),
                    }
                ),
                closed_object(
                    {
                        "mode": {"const": "certified_not_applicable"},
                        "dispatchAuthorization": ref(authorization_schema["$id"]),
                        "certification": certification_schema,
                    }
                ),
            ]
        },
        {
            "mode": "required",
            "dispatchAuthorization": permitted_proof,
            "permittedCapability": permitted_proof,
            "deniedSentinel": denied_sentinel_proof,
        },
    )

    authenticated_record_schema = closed_object(
        {
            "recordId": identifier,
            "subjectKind": bounded_string(
                enum=[
                    "dispatch-authorization-proof",
                    "required-capability-decision-proof",
                    "denied-sentinel-decision-proof",
                    "capability-evidence",
                    "not-applicable-certification",
                ]
            ),
            "subjectDigest": digest,
            "verificationMethod": bounded_string(
                enum=[
                    "detached-signature",
                    "mutual-tls-channel",
                    "workload-identity-channel",
                ]
            ),
            "verifiedSignerIdentity": uri,
            "verifiedSignerPolicy": trust_policy,
            "verificationEvidenceDigest": digest,
            "verifiedAt": timestamp,
            "validUntil": timestamp,
        }
    )

    def authenticated_record_value(
        record_id: str,
        subject_kind: str,
        subject_digest: str,
        signer_identity: str,
        signer_policy: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "recordId": record_id,
            "subjectKind": subject_kind,
            "subjectDigest": subject_digest,
            "verificationMethod": "detached-signature",
            "verifiedSignerIdentity": signer_identity,
            "verifiedSignerPolicy": signer_policy,
            "verificationEvidenceDigest": SHA256_ONE,
            "verifiedAt": SAMPLE_TIME,
            "validUntil": "2026-01-01T00:05:00Z",
        }

    capability_evidence = load_json(
        REPOSITORY_ROOT
        / "contracts"
        / "fixtures"
        / "schema"
        / "positive"
        / "canary-evidence__capability.json"
    )
    capability_evidence["schema"]["digest"] = canonical_digest(
        load_json(SCHEMA_ROOT / "canary-evidence.schema.json")
    )
    definitions["bytedesk.port.capability-authenticated-evidence-set/1"] = (
        {
            "oneOf": [
                closed_object(
                    {
                        "mode": {"const": "required"},
                        "dispatchAuthorization": authenticated_record_schema,
                        "requiredCapability": authenticated_record_schema,
                        "deniedSentinel": authenticated_record_schema,
                        "capabilityEvidence": authenticated_record_schema,
                    }
                ),
                closed_object(
                    {
                        "mode": {"const": "certified_not_applicable"},
                        "dispatchAuthorization": authenticated_record_schema,
                        "notApplicableCertification": authenticated_record_schema,
                        "capabilityEvidence": authenticated_record_schema,
                    }
                ),
            ]
        },
        {
            "mode": "required",
            "dispatchAuthorization": authenticated_record_value(
                "auth-dispatch-1",
                "dispatch-authorization-proof",
                canonical_digest(permitted_proof),
                permitted_proof["signerIdentity"],
                permitted_proof["signerPolicy"],
            ),
            "requiredCapability": authenticated_record_value(
                "auth-required-1",
                "required-capability-decision-proof",
                canonical_digest(permitted_proof),
                permitted_proof["signerIdentity"],
                permitted_proof["signerPolicy"],
            ),
            "deniedSentinel": authenticated_record_value(
                "auth-sentinel-1",
                "denied-sentinel-decision-proof",
                canonical_digest(denied_sentinel_proof),
                denied_sentinel_proof["signerIdentity"],
                denied_sentinel_proof["signerPolicy"],
            ),
            "capabilityEvidence": authenticated_record_value(
                "auth-evidence-1",
                "capability-evidence",
                canonical_digest(capability_evidence),
                capability_evidence["actorIdentity"],
                capability_evidence["signerPolicy"],
            ),
        },
    )

    common_expectations = {
        "consumerId": identifier,
        "subjectId": identifier,
        "targetId": identifier,
        "candidateDigest": digest,
        "checkProfileDigest": digest,
        "planDigest": digest,
        "desiredRevisionDigest": digest,
        "releaseDigest": digest,
        "deploymentDigest": digest,
        "authorityDigest": digest,
        "policyDigest": digest,
        "grantSetDigest": digest,
        "workloadIdentityDigest": digest,
        "authorizationSignerIdentity": uri,
        "authorizationSignerPolicy": trust_policy,
        "capabilityVerifierIdentity": uri,
        "capabilityVerifierVersion": bounded_string(),
        "capabilityEvidenceSignerPolicy": trust_policy,
        "authorizationProofSchemaDigest": digest,
        "canaryEvidenceSchemaDigest": digest,
    }
    common_expectation_value = {
        "consumerId": "consumer-1",
        "subjectId": "subject-1",
        "targetId": "target-1",
        "candidateDigest": SHA256_ZERO,
        "checkProfileDigest": SHA256_ONE,
        "planDigest": SHA256_ZERO,
        "desiredRevisionDigest": SHA256_ONE,
        "releaseDigest": SHA256_ZERO,
        "deploymentDigest": SHA256_ONE,
        "authorityDigest": SHA256_ZERO,
        "policyDigest": SHA256_ONE,
        "grantSetDigest": SHA256_ZERO,
        "workloadIdentityDigest": SHA256_ONE,
        "authorizationSignerIdentity": "spiffe://consumer.example/authorization",
        "authorizationSignerPolicy": {
            "id": "authorization-decision-v1",
            "digest": SHA256_ZERO,
        },
        "capabilityVerifierIdentity": "spiffe://consumer.example/capability-verifier",
        "capabilityVerifierVersion": "1.0.0",
        "capabilityEvidenceSignerPolicy": {
            "id": "consumer-capability-evidence-v1",
            "digest": SHA256_ONE,
        },
        "authorizationProofSchemaDigest": canonical_digest(authorization_schema),
        "canaryEvidenceSchemaDigest": canonical_digest(
            load_json(SCHEMA_ROOT / "canary-evidence.schema.json")
        ),
    }
    definitions["bytedesk.port.capability-verification-expectations/1"] = (
        {
            "oneOf": [
                closed_object(
                    {
                        **common_expectations,
                        "mode": {"const": "required"},
                        "permittedCapability": capability_descriptor,
                        "deniedSentinelCapability": capability_descriptor,
                    }
                ),
                closed_object(
                    {
                        **common_expectations,
                        "mode": {"const": "certified_not_applicable"},
                        "notApplicableCertificationSignerIdentity": uri,
                        "notApplicableCertificationPolicy": trust_policy,
                    }
                ),
            ]
        },
        {
            **common_expectation_value,
            "mode": "required",
            "permittedCapability": {
                "id": "capability.required",
                "digest": SHA256_ZERO,
            },
            "deniedSentinelCapability": {
                "id": "capability.denied-sentinel",
                "digest": SHA256_ONE,
            },
        },
    )

    definitions["bytedesk.port.consumer-projection-receipt/1"] = (
        closed_object(
            {
                "projectionId": identifier,
                "consumerId": identifier,
                "targetId": identifier,
                "projectionKind": bounded_string(
                    enum=["deployment-receipt", "consumer-resource"]
                ),
                "sourceReceiptDigest": digest,
                "consumerResourceId": identifier,
                "evidenceDigest": digest,
                "projectedAt": timestamp,
            }
        ),
        {
            "projectionId": "projection-1",
            "consumerId": "consumer-1",
            "targetId": "target-1",
            "projectionKind": "deployment-receipt",
            "sourceReceiptDigest": SHA256_ZERO,
            "consumerResourceId": "resource-1",
            "evidenceDigest": SHA256_ONE,
            "projectedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.consumer-subject-reference/1"] = (
        closed_object(
            {
                "consumerId": identifier,
                "namespace": bounded_string(pattern="^[A-Za-z0-9._:-]+$"),
                "externalSubjectId": identifier,
                "subjectKind": {"const": "agent"},
                "directoryVersionDigest": digest,
            }
        ),
        {
            "consumerId": "consumer-1",
            "namespace": "workforce",
            "externalSubjectId": "agent-1",
            "subjectKind": "agent",
            "directoryVersionDigest": SHA256_ZERO,
        },
    )

    definitions["bytedesk.port.functional-history-reference/1"] = (
        closed_object(
            {
                "revision": positive,
                "functionalDigest": digest,
                "sourceDeploymentDigest": digest,
                "withdrawn": {"type": "boolean"},
                "recordedAt": timestamp,
            }
        ),
        {
            "revision": 1,
            "functionalDigest": SHA256_ZERO,
            "sourceDeploymentDigest": SHA256_ONE,
            "withdrawn": False,
            "recordedAt": SAMPLE_TIME,
        },
    )

    material_kinds = [
        "source-commit-and-tree",
        "builder",
        "workflow",
        "toolchain",
        "component-lock",
        "renderer-release",
        "public-skill",
        "private-skill",
        "policy-binding",
        "customization",
        "test-evidence",
    ]
    slsa_material_schema = closed_object(
        {
            "uri": {
                "type": "string",
                "format": "uri",
                "minLength": 1,
                "maxLength": 2048,
            },
            "digest": closed_object({"sha256": sha256_hex}),
            "annotations": closed_object(
                {
                    "ai.bytedesk.material-kind": bounded_string(enum=material_kinds),
                    "ai.bytedesk.material-id": identifier,
                }
            ),
        }
    )
    slsa_material_sample = {
        "uri": "https://example.invalid/material/source-1",
        "digest": {"sha256": "0" * 64},
        "annotations": {
            "ai.bytedesk.material-kind": "source-commit-and-tree",
            "ai.bytedesk.material-id": "source-commit-and-tree",
        },
    }
    definitions["bytedesk.port.slsa-material/1"] = (
        slsa_material_schema,
        slsa_material_sample,
    )

    definitions["bytedesk.port.intoto-provenance/1"] = (
        closed_object(
            {
                "_type": {"const": "https://in-toto.io/Statement/v1"},
                "subject": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 128,
                    "items": closed_object(
                        {
                            "name": bounded_string(),
                            "digest": closed_object({"sha256": sha256_hex}),
                        }
                    ),
                },
                "predicateType": {"const": "https://slsa.dev/provenance/v1"},
                "predicate": closed_object(
                    {
                        "buildDefinition": closed_object(
                            {
                                "buildType": {
                                    "type": "string",
                                    "format": "uri",
                                    "minLength": 1,
                                    "maxLength": 2048,
                                },
                                "externalParameters": closed_object(
                                    {"digest": digest}
                                ),
                                "resolvedDependencies": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 128,
                                    "items": slsa_material_schema,
                                },
                            }
                        ),
                        "runDetails": closed_object(
                            {
                                "builder": closed_object(
                                    {
                                        "id": {
                                            "type": "string",
                                            "format": "uri",
                                            "minLength": 1,
                                            "maxLength": 2048,
                                        }
                                    }
                                ),
                                "metadata": closed_object(
                                    {
                                        "invocationId": identifier,
                                        "startedOn": timestamp,
                                        "finishedOn": timestamp,
                                    }
                                ),
                            }
                        ),
                    }
                ),
            }
        ),
        {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [{"name": "artifact", "digest": {"sha256": "0" * 64}}],
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {
                    "buildType": "https://build.example.invalid/types/agent-delivery/v1",
                    "externalParameters": {"digest": SHA256_ONE},
                    "resolvedDependencies": [slsa_material_sample],
                },
                "runDetails": {
                    "builder": {"id": "https://build.example.invalid/builders/1"},
                    "metadata": {
                        "invocationId": "build-1",
                        "startedOn": SAMPLE_TIME,
                        "finishedOn": "2026-01-01T00:01:00Z",
                    },
                },
            },
        },
    )

    chunk_schema = closed_object(
        {
            "index": nonnegative,
            "offset": nonnegative,
            "size": {"type": "integer", "minimum": 1, "maximum": BYTES_MAX_DECODED},
            "digest": digest,
            "contentBase64url": bounded_bytes(),
        }
    )
    one_byte_digest = "sha256:" + hashlib.sha256(b"x").hexdigest()
    definitions["bytedesk.port.oci-blob-stream/1"] = (
        closed_object(
            {
                "digest": digest,
                "mediaType": media_type,
                "size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": OCI_BLOB_MAX_DECODED,
                },
                "chunks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1024,
                    "items": chunk_schema,
                },
            }
        ),
        {
            "digest": one_byte_digest,
            "mediaType": "application/octet-stream",
            "size": 1,
            "chunks": [
                {
                    "index": 0,
                    "offset": 0,
                    "size": 1,
                    "digest": one_byte_digest,
                    "contentBase64url": "eA",
                }
            ],
        },
    )

    definitions["bytedesk.port.oci-descriptor/1"] = (
        closed_object(
            {
                "repository": repository,
                "digest": digest,
                "mediaType": media_type,
                "artifactType": media_type,
                "size": nonnegative,
                "subjectDigest": nullable(digest),
                "annotationsDigest": nullable(digest),
            }
        ),
        {
            "repository": "registry.example.invalid/agent-delivery",
            "digest": SHA256_ZERO,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "artifactType": "application/vnd.bytedesk.agent-source.v1+json",
            "size": 2,
            "subjectDigest": None,
            "annotationsDigest": None,
        },
    )

    finding_schema = closed_object(
        {
            "findingId": identifier,
            "classification": identifier,
            "path": bounded_string(pattern="^[^\\u0000\\r\\n]+$"),
            "severity": bounded_string(
                enum=["none", "low", "medium", "high", "critical"]
            ),
        }
    )
    findings_schema = {
        "type": "array",
        "minItems": 0,
        "maxItems": 100000,
        "items": finding_schema,
    }
    outcome_schema = bounded_string(enum=["pass", "deny", "indeterminate"])

    definitions["bytedesk.port.vulnerability-report/1"] = (
        closed_object(
            {
                "artifactDigest": digest,
                "sbomDigest": digest,
                "scannerImageDigest": digest,
                "scannerRulesDigest": digest,
                "advisorySnapshotDigest": digest,
                "severityPolicyDigest": digest,
                "scanTime": timestamp,
                "outcome": outcome_schema,
                "coverageComplete": {"type": "boolean"},
                "findings": findings_schema,
            }
        ),
        {
            "artifactDigest": SHA256_ZERO,
            "sbomDigest": SHA256_ONE,
            "scannerImageDigest": SHA256_ZERO,
            "scannerRulesDigest": SHA256_ONE,
            "advisorySnapshotDigest": SHA256_ZERO,
            "severityPolicyDigest": SHA256_ONE,
            "scanTime": SAMPLE_TIME,
            "outcome": "pass",
            "coverageComplete": True,
            "findings": [],
        },
    )

    definitions["bytedesk.port.malware-report/1"] = (
        closed_object(
            {
                "artifactDigest": digest,
                "scannerImageDigest": digest,
                "signatureDatabaseDigest": digest,
                "sandboxProfileDigest": digest,
                "scanTime": timestamp,
                "outcome": outcome_schema,
                "coverageComplete": {"type": "boolean"},
                "findings": findings_schema,
            }
        ),
        {
            "artifactDigest": SHA256_ZERO,
            "scannerImageDigest": SHA256_ONE,
            "signatureDatabaseDigest": SHA256_ZERO,
            "sandboxProfileDigest": SHA256_ONE,
            "scanTime": SAMPLE_TIME,
            "outcome": "pass",
            "coverageComplete": True,
            "findings": [],
        },
    )

    definitions["bytedesk.port.secret-scan-report/1"] = (
        closed_object(
            {
                "artifactDigest": digest,
                "scannerImageDigest": digest,
                "rulesetDigest": digest,
                "allowlistDigest": digest,
                "scanTime": timestamp,
                "outcome": outcome_schema,
                "coverageComplete": {"type": "boolean"},
                "findings": findings_schema,
            }
        ),
        {
            "artifactDigest": SHA256_ZERO,
            "scannerImageDigest": SHA256_ONE,
            "rulesetDigest": SHA256_ZERO,
            "allowlistDigest": SHA256_ONE,
            "scanTime": SAMPLE_TIME,
            "outcome": "pass",
            "coverageComplete": True,
            "findings": [],
        },
    )

    definitions["bytedesk.port.scan-completeness-report/1"] = (
        closed_object(
            {
                "artifactDigest": digest,
                "inventoryDigest": digest,
                "vulnerabilityReportDigest": digest,
                "malwareReportDigest": digest,
                "secretScanReportDigest": digest,
                "evaluatorImageDigest": digest,
                "evaluatedAt": timestamp,
                "outcome": outcome_schema,
                "complete": {"type": "boolean"},
            }
        ),
        {
            "artifactDigest": SHA256_ZERO,
            "inventoryDigest": SHA256_ONE,
            "vulnerabilityReportDigest": SHA256_ZERO,
            "malwareReportDigest": SHA256_ONE,
            "secretScanReportDigest": SHA256_ZERO,
            "evaluatorImageDigest": SHA256_ONE,
            "evaluatedAt": SAMPLE_TIME,
            "outcome": "pass",
            "complete": True,
        },
    )

    definitions["bytedesk.port.license-report/1"] = (
        closed_object(
            {
                "sbomDigest": digest,
                "licensePolicyId": identifier,
                "licensePolicyDigest": digest,
                "evaluatorImageDigest": digest,
                "expressionParserProfile": {"const": "spdx-license-expression-2.3-strict/1"},
                "licenseListVersion": {"const": "3.28.0"},
                "licenseListDigest": digest,
                "exceptionListDigest": digest,
                "evaluationTime": timestamp,
                "outcome": outcome_schema,
                "expressions": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": 100000,
                    "items": closed_object(
                        {
                            "packageId": identifier,
                            "expression": bounded_string(),
                            "disposition": bounded_string(
                                enum=["allowed", "denied", "unknown"]
                            ),
                        }
                    ),
                },
            }
        ),
        {
            "sbomDigest": SHA256_ZERO,
            "licensePolicyId": "license-policy-1",
            "licensePolicyDigest": SHA256_ONE,
            "evaluatorImageDigest": SHA256_ZERO,
            "expressionParserProfile": "spdx-license-expression-2.3-strict/1",
            "licenseListVersion": "3.28.0",
            "licenseListDigest": "sha256:f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee",
            "exceptionListDigest": "sha256:bd145bb558f44432fcd6f0d7e956ed0124dff72af7641a7cfcb1b557dc390a5b",
            "evaluationTime": SAMPLE_TIME,
            "outcome": "pass",
            "expressions": [],
        },
    )

    definitions["bytedesk.port.resolved-consumer-subject/1"] = (
        closed_object(
            {
                "consumerId": identifier,
                "subjectId": identifier,
                "subjectKind": {"const": "agent"},
                "version": positive,
                "status": bounded_string(enum=["current", "retired"]),
                "resolvedAt": timestamp,
            }
        ),
        {
            "consumerId": "consumer-1",
            "subjectId": "agent-1",
            "subjectKind": "agent",
            "version": 1,
            "status": "current",
            "resolvedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.restore-evidence/1"] = (
        closed_object(
            {
                "restoreId": identifier,
                "sourceArchiveDigest": digest,
                "restoredEvidenceDigest": digest,
                "targetRepository": repository,
                "verificationDigest": digest,
                "activated": {"const": False},
                "restoredAt": timestamp,
            }
        ),
        {
            "restoreId": "restore-1",
            "sourceArchiveDigest": SHA256_ZERO,
            "restoredEvidenceDigest": SHA256_ONE,
            "targetRepository": "registry.example.invalid/restored-evidence",
            "verificationDigest": SHA256_ZERO,
            "activated": False,
            "restoredAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.retention-evidence/1"] = (
        closed_object(
            {
                "evidenceDigest": digest,
                "retentionClass": bounded_string(
                    enum=["standard", "extended", "legal-hold"]
                ),
                "retainUntil": timestamp,
                "legalHold": {"type": "boolean"},
                "archiveRootDigest": digest,
                "observedAt": timestamp,
            }
        ),
        {
            "evidenceDigest": SHA256_ZERO,
            "retentionClass": "standard",
            "retainUntil": "2027-01-01T00:00:00Z",
            "legalHold": False,
            "archiveRootDigest": SHA256_ONE,
            "observedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.scm-authentication-envelope/1"] = (
        closed_object(
            {
                "provider": bounded_string(enum=["github", "gitlab", "generic"]),
                "deliveryId": identifier,
                "algorithm": bounded_string(enum=["hmac-sha256", "ed25519"]),
                "keyId": identifier,
                "signatureBase64url": bounded_string(pattern="^[A-Za-z0-9_-]+$"),
                "signedPayloadDigest": digest,
                "receivedAt": timestamp,
            }
        ),
        {
            "provider": "generic",
            "deliveryId": "delivery-1",
            "algorithm": "ed25519",
            "keyId": "key-1",
            "signatureBase64url": "AA",
            "signedPayloadDigest": SHA256_ZERO,
            "receivedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.scm-inbox-receipt/1"] = (
        closed_object(
            {
                "deliveryId": identifier,
                "payloadDigest": digest,
                "committedOffset": nonnegative,
                "duplicate": {"type": "boolean"},
                "receivedAt": timestamp,
            }
        ),
        {
            "deliveryId": "delivery-1",
            "payloadDigest": SHA256_ZERO,
            "committedOffset": 0,
            "duplicate": False,
            "receivedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.source-evidence/1"] = (
        closed_object(
            {
                "repositoryUrl": {
                    "type": "string",
                    "format": "uri",
                    "minLength": 1,
                    "maxLength": 2048,
                },
                "immutableCommit": bounded_string(pattern="^(?:[0-9a-f]{40}|[0-9a-f]{64})$"),
                "treeDigest": digest,
                "inventoryDigest": digest,
                "fetcherIdentity": identifier,
                "signatureVerification": bounded_string(
                    enum=["verified", "not-present"]
                ),
                "fetchedAt": timestamp,
            }
        ),
        {
            "repositoryUrl": "https://example.invalid/agents.git",
            "immutableCommit": "0" * 40,
            "treeDigest": SHA256_ZERO,
            "inventoryDigest": SHA256_ONE,
            "fetcherIdentity": "fetcher-1",
            "signatureVerification": "verified",
            "fetchedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.spdx-sbom-descriptor/1"] = (
        closed_object(
            {
                "specification": {"const": "SPDX-2.3"},
                "interoperabilityProfile": {
                    "const": "agent-delivery-v1-spdx-2.3-json"
                },
                "documentNamespace": {
                    "type": "string",
                    "format": "uri",
                    "minLength": 1,
                    "maxLength": 2048,
                },
                "documentDigest": digest,
                "artifactDigest": digest,
                "mediaType": {"const": "application/spdx+json"},
                "packageCount": nonnegative,
                "fileCount": nonnegative,
                "relationshipCount": nonnegative,
                "generatedAt": timestamp,
            }
        ),
        {
            "specification": "SPDX-2.3",
            "interoperabilityProfile": "agent-delivery-v1-spdx-2.3-json",
            "documentNamespace": "https://example.invalid/spdx/document-1",
            "documentDigest": SHA256_ZERO,
            "artifactDigest": SHA256_ONE,
            "mediaType": "application/spdx+json",
            "packageCount": 1,
            "fileCount": 1,
            "relationshipCount": 1,
            "generatedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.target-state-change/1"] = (
        closed_object(
            {
                "sequence": positive,
                "kind": bounded_string(enum=["upsert", "delete"]),
                "consumerId": identifier,
                "targetId": identifier,
                "revision": positive,
                "digest": digest,
                "eventId": identifier,
                "observedAt": timestamp,
            }
        ),
        {
            "sequence": 1,
            "kind": "upsert",
            "consumerId": "consumer-1",
            "targetId": "target-1",
            "revision": 1,
            "digest": SHA256_ZERO,
            "eventId": "event-1",
            "observedAt": SAMPLE_TIME,
        },
    )

    definitions["bytedesk.port.target-state-history-entry/1"] = (
        closed_object(
            {
                "consumerId": identifier,
                "targetId": identifier,
                "revision": positive,
                "digest": digest,
                "previousDigest": nullable(digest),
                "writerFencingToken": positive,
                "regionEpoch": positive,
                "commitReceiptDigest": digest,
                "committedAt": timestamp,
            }
        ),
        {
            "consumerId": "consumer-1",
            "targetId": "target-1",
            "revision": 1,
            "digest": SHA256_ZERO,
            "previousDigest": None,
            "writerFencingToken": 1,
            "regionEpoch": 1,
            "commitReceiptDigest": SHA256_ONE,
            "committedAt": SAMPLE_TIME,
        },
    )

    return definitions


def resolve_sample_marker(value: Any, fixtures: dict[str, Any]) -> Any:
    if isinstance(value, dict) and set(value) == {"$fixtureFrom"}:
        schema_identifier = value["$fixtureFrom"]
        require(schema_identifier in fixtures, f"no positive fixture for {schema_identifier}")
        return deepcopy(fixtures[schema_identifier])
    if isinstance(value, dict) and set(value) == {"$fixtureProperty"}:
        marker = value["$fixtureProperty"]
        require(
            isinstance(marker, dict) and set(marker) == {"schemaId", "property"},
            "invalid $fixtureProperty marker",
        )
        schema_identifier = marker["schemaId"]
        property_name = marker["property"]
        require(
            schema_identifier in fixtures,
            f"no positive fixture for {schema_identifier}",
        )
        fixture = fixtures[schema_identifier]
        require(
            isinstance(property_name, str) and property_name in fixture,
            f"positive fixture for {schema_identifier} has no {property_name!r}",
        )
        return deepcopy(fixture[property_name])
    return value


def schema_target_sample(
    reference: str,
    target: str,
    fixtures: dict[str, Any],
) -> Any:
    if reference == "common#/$defs/digest":
        return SHA256_ZERO
    if reference in {"common#/$defs/identifier", "primitive:identifier"}:
        return SAMPLE_ID
    if reference == "common#/$defs/nonce":
        return "nonce-1234567890"
    if reference == "common#/$defs/ociRepository":
        return "registry.example.invalid/bytedesk/agent-delivery"
    if reference == "common#/$defs/positiveSafeInteger":
        return 1
    if reference == "common#/$defs/timestamp":
        return SAMPLE_TIME
    if reference in {"common#/$defs/artifactDescriptor", ARTIFACT_DESCRIPTOR_REF}:
        return {
            "repository": "registry.example.invalid/bytedesk/evidence",
            "digest": SHA256_ZERO,
            "mediaType": "application/vnd.bytedesk.evidence.v1+json",
            "size": 0,
            "trustPolicy": {
                "id": "trust-policy-1",
                "digest": SHA256_ONE,
            },
        }
    if reference == "bytedesk.port.consumer-deployment-descriptor/1":
        return {
            "repository": "registry.example.invalid/consumer/deployments",
            "digest": SHA256_ZERO,
            "mediaType": "application/vnd.bytedesk.agent.consumer-deployment.v1+json",
            "size": 0,
            "trustPolicy": {
                "id": "consumer-deployment-v1",
                "digest": SHA256_ONE,
            },
        }
    if reference == "bytedesk.port.consumer-runtime-release-descriptor/1":
        return {
            "repository": "registry.example.invalid/consumer/runtime-releases",
            "digest": SHA256_ZERO,
            "mediaType": "application/vnd.bytedesk.agent.runtime-release.v1+json",
            "size": 0,
            "trustPolicy": {
                "id": "consumer-runtime-release-v1",
                "digest": SHA256_ONE,
            },
        }
    if reference == "primitive:media-type":
        return "application/json"
    if reference == "primitive:nonnegative-integer":
        return 0
    if reference == "catalog-index#/$defs/catalogRelease":
        catalog = fixtures[schema_id("catalog-index")]
        return deepcopy(catalog["entries"][0])
    if reference == "private-compilation-input#/$defs/policyDigests":
        private_input = fixtures[schema_id("private-compilation-input")]
        return deepcopy(private_input["inputs"]["policyDigests"])
    if reference == f"{schema_id('release-status-append-resolution')}#/$defs/appendResult":
        resolution = fixtures[schema_id("release-status-append-resolution")]
        append_result = resolution.get("appendResult")
        require(
            isinstance(append_result, dict),
            "release-status append-resolution fixture has no committed appendResult",
        )
        return deepcopy(append_result)
    if reference == f"{schema_id('release-status-head-checkpoint')}#/$defs/clientPriorState":
        checkpoint = fixtures[schema_id("release-status-head-checkpoint")]
        return deepcopy(checkpoint["clientPriorState"])
    base, _ = urldefrag(target)
    require(base in fixtures, f"no positive fixture for target {reference}: {base}")
    return deepcopy(fixtures[base])


def invalid_value(valid: Any) -> Any:
    if valid is None:
        return 17
    if isinstance(valid, bool):
        return "not-a-boolean"
    if isinstance(valid, int):
        return "not-an-integer"
    if isinstance(valid, str):
        return {"not": "a-string"}
    if isinstance(valid, list):
        return {"not": "an-array"}
    if isinstance(valid, dict):
        return None
    raise GenerationError(f"cannot derive invalid fixture for {type(valid).__name__}")


def validation_errors(
    schema: dict[str, Any], instance: Any, schema_store: Any
) -> list[Any]:
    def deny_network(uri: str) -> Any:
        raise GenerationError(f"network schema resolution is forbidden: {uri}")

    if Registry is not None and isinstance(schema_store, Registry):
        validator = Draft202012Validator(
            schema,
            registry=schema_store,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
    else:
        resolver = RefResolver.from_schema(
            schema,
            store=schema_store,
            handlers={"http": deny_network, "https": deny_network},
        )
        validator = Draft202012Validator(
            schema,
            resolver=resolver,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
    return sorted(
        validator.iter_errors(instance),
        key=lambda error: (list(error.absolute_path), error.validator, error.message),
    )


def source_closure(
    seed_ids: set[str], schemas: dict[str, dict[str, Any]]
) -> set[str]:
    pending = list(seed_ids)
    closure: set[str] = set()
    while pending:
        schema_identifier = pending.pop()
        if schema_identifier in closure:
            continue
        require(schema_identifier in schemas, f"offline schema source is missing: {schema_identifier}")
        closure.add(schema_identifier)
        for reference in iter_references(schemas[schema_identifier]):
            if reference.startswith("#"):
                continue
            base, _ = urldefrag(reference)
            require(
                base.startswith(SCHEMA_PREFIX),
                f"network or non-product schema reference is forbidden: {reference}",
            )
            pending.append(base)
    return closure


def operation_contract_variants(contract_id: str) -> list[dict[str, Any]] | None:
    """Return the closed cross-field variants owned by one port operation."""

    variants: dict[str, list[dict[str, Any]]] = {
        "bytedesk.port.catalog.list-catalog-releases.request/1": [
            {
                "required": ["cursor", "snapshotDigest"],
                "properties": {
                    "cursor": {"type": "null"},
                    "snapshotDigest": {"type": "null"},
                },
            },
            {
                "required": ["cursor", "snapshotDigest"],
                "properties": {
                    "cursor": {
                        "$ref": type_schema_id("primitive:opaque-token")
                        + "#/oneOf/0"
                    },
                    "snapshotDigest": {"$ref": SHA_REF},
                },
            },
        ],
        "bytedesk.port.oci-registry.head-artifact.result/1": [
            {
                "required": ["exists"],
                "properties": {"exists": {"const": True}},
            }
        ],
        "bytedesk.port.oci-registry.list-referrers.request/1": [
            {
                "required": ["cursor", "snapshotDigest"],
                "properties": {
                    "cursor": {"type": "null"},
                    "snapshotDigest": {"type": "null"},
                },
            },
            {
                "required": ["cursor", "snapshotDigest"],
                "properties": {
                    "cursor": {
                        "$ref": type_schema_id("primitive:opaque-token")
                        + "#/oneOf/0"
                    },
                    "snapshotDigest": {"$ref": SHA_REF},
                },
            },
        ],
        "bytedesk.port.kms-signing.resolve-signing-request.result/1": [
            {
                "required": ["resolution", "signatureEnvelope"],
                "properties": {
                    "resolution": {"const": "signed"},
                    "signatureEnvelope": {
                        "$ref": type_schema_id("bytedesk.port.signature-envelope/1")
                    },
                },
            },
            {
                "required": ["resolution", "signatureEnvelope"],
                "properties": {
                    "resolution": {
                        "enum": ["not-seen", "denied", "indeterminate"]
                    },
                    "signatureEnvelope": {"type": "null"},
                },
            },
        ],
        "bytedesk.port.consumer-authority-approval.resolve-authority-snapshot.request/1": [
            {
                "required": ["operation", "authorizedPrivateInputDigest"],
                "properties": {
                    "operation": {"const": "compile"},
                    "authorizedPrivateInputDigest": {"$ref": SHA_REF},
                },
            },
            {
                "required": ["operation"],
                "properties": {
                    "operation": {"enum": ["activate", "recover"]},
                    "authorizedPrivateInputDigest": False,
                },
            },
        ],
        "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1": [
            {
                "required": [
                    "verificationResult",
                    "authorizedPrivateInputDigest",
                ],
                "properties": {
                    "verificationResult": {
                        "required": ["outcome"],
                        "properties": {"outcome": {"const": "permitted"}},
                    },
                    "authorizedPrivateInputDigest": {"$ref": SHA_REF},
                },
            }
        ],
        "bytedesk.port.desired-state-store.watch-target-state.result/1": [
            {
                "required": ["changes", "nextResumeToken", "resyncRequired"],
                "properties": {
                    "resyncRequired": {"const": False},
                    "nextResumeToken": {
                        "$ref": type_schema_id("primitive:opaque-token")
                        + "#/oneOf/0"
                    },
                },
            },
            {
                "required": ["changes", "nextResumeToken", "resyncRequired"],
                "properties": {
                    "resyncRequired": {"const": True},
                    "changes": {"maxItems": 0},
                    "nextResumeToken": {"type": "null"},
                },
            },
        ],
        "bytedesk.port.desired-state-store.resolve-idempotency.result/1": [
            {
                "required": ["resolution", "commitReceipt"],
                "properties": {
                    "resolution": {"const": "committed"},
                    "commitReceipt": {
                        "$ref": type_schema_id(
                            "bytedesk.port.desired-state-commit-receipt/1"
                        )
                    },
                },
            },
            {
                "required": ["resolution", "commitReceipt"],
                "properties": {
                    "resolution": {
                        "enum": ["not-seen", "rejected", "indeterminate"]
                    },
                    "commitReceipt": {"type": "null"},
                },
            },
        ],
        "bytedesk.port.desired-state-store.read-target-history.request/1": [
            {
                "required": ["beforeRevision", "snapshotDigest"],
                "properties": {
                    "beforeRevision": {"type": "null"},
                    "snapshotDigest": {"type": "null"},
                },
            },
            {
                "required": ["beforeRevision", "snapshotDigest"],
                "properties": {
                    "beforeRevision": {
                        "$ref": type_schema_id("primitive:opaque-token")
                        + "#/oneOf/0"
                    },
                    "snapshotDigest": {"$ref": SHA_REF},
                },
            },
        ],
        "bytedesk.port.control-plane-api-events.read-resource.result/1": [
            {
                "required": ["readOutcome", "resource", "etag"],
                "properties": {
                    "readOutcome": {"const": "found"},
                    "resource": {
                        "$ref": type_schema_id("bytedesk.port.api-resource/1")
                    },
                },
            },
            {
                "required": ["readOutcome", "resource", "etag"],
                "properties": {
                    "readOutcome": {"const": "not-modified"},
                    "resource": {"type": "null"},
                },
            },
        ],
        "bytedesk.port.promotion-coordinator.evaluate-evidence.result/1": [
            {
                "required": ["decision", "evaluationAttestation", "missingEvidence"],
                "properties": {
                    "decision": {"const": "permitted"},
                    "evaluationAttestation": {
                        "required": ["result"],
                        "properties": {"result": {"const": "passed"}},
                    },
                    "missingEvidence": {"maxItems": 0},
                },
            },
            {
                "required": ["decision", "evaluationAttestation", "missingEvidence"],
                "properties": {
                    "decision": {"const": "denied"},
                    "evaluationAttestation": {
                        "required": ["result"],
                        "properties": {"result": {"const": "failed"}},
                    },
                    "missingEvidence": {"maxItems": 0},
                },
            },
            {
                "required": ["decision", "evaluationAttestation", "missingEvidence"],
                "properties": {
                    "decision": {"const": "indeterminate"},
                    "evaluationAttestation": {
                        "required": ["result"],
                        "properties": {"result": {"const": "manual_review"}},
                    },
                    "missingEvidence": {"minItems": 1},
                },
            },
        ],
        "bytedesk.port.private-compiler.resolve-compile-attempt.result/1": [
            {
                "required": ["resolution", "artifacts", "problem"],
                "properties": {
                    "resolution": {"const": "committed"},
                    "artifacts": {
                        "$ref": type_schema_id(
                            "bytedesk.port.private-compilation-artifacts-or-null/1"
                        )
                        + "#/oneOf/0"
                    },
                    "problem": {"type": "null"},
                },
            },
            {
                "required": ["resolution", "artifacts", "problem"],
                "properties": {
                    "resolution": {"const": "not-seen"},
                    "artifacts": {"type": "null"},
                    "problem": {"type": "null"},
                },
            },
            {
                "required": ["resolution", "artifacts", "problem"],
                "properties": {
                    "resolution": {"enum": ["denied", "indeterminate"]},
                    "artifacts": {"type": "null"},
                    "problem": {"$ref": schema_id("problem-details")},
                },
            },
        ],
        "bytedesk.port.cli-automation.watch-action.result/1": [
            {
                "required": ["terminalAction", "lastObservedAction", "exitCode"],
                "properties": {
                    "terminalAction": {"type": "null"},
                    "lastObservedAction": {
                        "required": ["state"],
                        "properties": {
                            "state": {
                                "enum": [
                                    "queued",
                                    "claimed",
                                    "running",
                                    "retry_wait",
                                    "cancellation_requested",
                                ]
                            }
                        },
                    },
                    "exitCode": {"const": 12},
                },
            },
            {
                "required": ["terminalAction", "lastObservedAction", "exitCode"],
                "properties": {
                    "terminalAction": {
                        "required": ["state"],
                        "properties": {"state": {"const": "succeeded"}},
                    },
                    "lastObservedAction": {
                        "required": ["state"],
                        "properties": {"state": {"const": "succeeded"}},
                    },
                    "exitCode": {"const": 0},
                },
            },
            {
                "required": ["terminalAction", "lastObservedAction", "exitCode"],
                "properties": {
                    "terminalAction": {
                        "required": ["state"],
                        "properties": {
                            "state": {"enum": ["failed", "dead_lettered"]}
                        },
                    },
                    "lastObservedAction": {
                        "required": ["state"],
                        "properties": {
                            "state": {"enum": ["failed", "dead_lettered"]}
                        },
                    },
                    "exitCode": {"const": 10},
                },
            },
            {
                "required": ["terminalAction", "lastObservedAction", "exitCode"],
                "properties": {
                    "terminalAction": {
                        "required": ["state"],
                        "properties": {"state": {"const": "cancelled"}},
                    },
                    "lastObservedAction": {
                        "required": ["state"],
                        "properties": {"state": {"const": "cancelled"}},
                    },
                    "exitCode": {"const": 11},
                },
            },
        ],
    }
    return deepcopy(variants.get(contract_id))


def normalize_operation_fixture(contract_id: str, instance: dict[str, Any]) -> None:
    """Select one coherent positive branch for every aggregate contract."""

    if contract_id == "bytedesk.port.desired-state-store.watch-target-state.result/1":
        instance["resyncRequired"] = False
        instance["nextResumeToken"] = "resume-token-0001"
    elif contract_id == "bytedesk.port.control-plane-api-events.read-resource.result/1":
        instance["readOutcome"] = "found"
        instance["resource"] = load_json(
            REPOSITORY_ROOT
            / "contracts"
            / "fixtures"
            / "schema"
            / "positive"
            / "target-delivery-state__initial.json"
        )
        instance["etag"] = canonical_digest(instance["resource"])
    elif contract_id == "bytedesk.port.promotion-coordinator.evaluate-evidence.result/1":
        instance["decision"] = "permitted"
        instance["evaluationAttestation"]["result"] = "passed"
        instance["missingEvidence"] = []
    elif contract_id == "bytedesk.port.cli-automation.watch-action.result/1":
        instance["terminalAction"] = deepcopy(instance["lastObservedAction"])
        instance["exitCode"] = 10
    elif contract_id == "bytedesk.port.desired-state-store.migrate-target-state.result/1":
        instance["migrationId"] = instance["migrationCheckpoint"]["migrationId"]
    elif contract_id == "bytedesk.port.control-plane-api-events.subscribe-events.result/1":
        event = instance["eventStream"]
        event["dataDigest"] = canonical_digest(event["data"])
        event["aggregateSequence"] = event["data"]["aggregate"]["sequence"]
    elif (
        contract_id
        == "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1"
    ):
        instance["verificationResult"]["outcome"] = "permitted"
        instance["verificationResult"]["reasonCodes"] = []


def operation_semantic_mutations(
    contract_id: str, valid: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    """Create deterministic cross-field mutations rejected by contract schemas."""

    mutated = deepcopy(valid)
    if contract_id == "bytedesk.port.catalog.list-catalog-releases.request/1":
        mutated["cursor"] = "cursor-0000000001"
        return [("continuation-without-snapshot", mutated)]
    if contract_id == "bytedesk.port.oci-registry.head-artifact.result/1":
        mutated["exists"] = False
        return [("absence-returned-as-success", mutated)]
    if contract_id == "bytedesk.port.oci-registry.list-referrers.request/1":
        mutated["cursor"] = "cursor-0000000001"
        return [("continuation-without-snapshot", mutated)]
    if contract_id == "bytedesk.port.kms-signing.resolve-signing-request.result/1":
        mutated["resolution"] = "signed"
        return [("signed-without-envelope", mutated)]
    if (
        contract_id
        == "bytedesk.port.consumer-authority-approval.resolve-authority-snapshot.request/1"
    ):
        mutated["operation"] = "activate"
        return [("non-compile-with-authorized-input-digest", mutated)]
    if (
        contract_id
        == "bytedesk.port.consumer-authority-approval.verify-private-authority.result/1"
    ):
        mutated["verificationResult"]["outcome"] = "denied"
        mutated["verificationResult"]["reasonCodes"] = ["policy_denied"]
        return [("denied-returned-as-authorized-success", mutated)]
    if contract_id == "bytedesk.port.desired-state-store.watch-target-state.result/1":
        mutated["resyncRequired"] = True
        mutated["nextResumeToken"] = None
        return [("gap-returned-with-changes", mutated)]
    if contract_id == "bytedesk.port.desired-state-store.resolve-idempotency.result/1":
        mutated["resolution"] = "committed"
        return [("committed-without-receipt", mutated)]
    if contract_id == "bytedesk.port.desired-state-store.read-target-history.request/1":
        mutated["beforeRevision"] = "cursor-0000000001"
        return [("continuation-without-snapshot", mutated)]
    if contract_id == "bytedesk.port.control-plane-api-events.read-resource.result/1":
        mutated["resource"] = None
        return [("found-without-resource", mutated)]
    if contract_id == "bytedesk.port.promotion-coordinator.evaluate-evidence.result/1":
        mutated["missingEvidence"] = ["missing-check"]
        return [("permitted-with-missing-evidence", mutated)]
    if contract_id == "bytedesk.port.private-compiler.resolve-compile-attempt.result/1":
        mutated["resolution"] = "committed"
        denied = deepcopy(valid)
        denied["resolution"] = "denied"
        return [
            ("committed-without-complete-artifacts", mutated),
            ("denied-without-problem", denied),
        ]
    if contract_id == "bytedesk.port.cli-automation.watch-action.result/1":
        mutated["exitCode"] = 11
        return [("terminal-failure-with-cancelled-exit", mutated)]
    return []


def compile_contract_schema(
    contract_id: str,
    fields: list[dict[str, Any]],
    field_type_schema_ids: dict[str, str],
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field in fields:
        properties[field["name"]] = {
            "$ref": field_type_schema_ids[field["valueType"]]
        }
        if field["required"]:
            required.append(field["name"])
    schema = {
        "$schema": DIALECT,
        "$id": contract_schema_id(contract_id),
        "title": contract_id,
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
        "unevaluatedProperties": False,
    }
    variants = operation_contract_variants(contract_id)
    if variants is not None:
        schema["oneOf"] = variants
    return schema


def build_registry(
    source_ids: set[str],
    source_schemas: dict[str, dict[str, Any]],
    type_schemas: dict[str, dict[str, Any]],
) -> Any:
    store = {
        schema_identifier: source_schemas[schema_identifier]
        for schema_identifier in sorted(source_ids)
    }
    store.update({schema["$id"]: schema for schema in type_schemas.values()})
    if Registry is None or Resource is None:
        return store
    return Registry().with_resources(
        [(schema_id, Resource.from_contents(schema)) for schema_id, schema in store.items()]
    )


def generate_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    port_registry = load_json(REGISTRY_PATH)
    normalized_registry = normalize_registry_value_types(port_registry)
    require(
        normalized_registry == port_registry,
        "port registry field value types are missing or stale; run with --normalize-registry",
    )
    registry_digest = canonical_digest(port_registry)
    problem_document = load_json(PROBLEM_CATALOG_PATH)
    problem_schema = build_problem_details_schema(port_registry, problem_document)
    source_schemas, source_paths = load_source_schemas()
    source_schemas[problem_schema["$id"]] = problem_schema
    source_paths[problem_schema["$id"]] = (
        PROBLEM_DETAILS_SCHEMA_PATH.relative_to(REPOSITORY_ROOT).as_posix()
    )
    positive_fixtures = load_positive_schema_fixtures()

    usage_kinds: dict[str, set[str]] = {}
    for port in port_registry["ports"]:
        for operation in port["operations"]:
            for field in operation["requestFields"] + operation["resultFields"]:
                usage_kinds.setdefault(field["schemaRef"], set()).add(field["type"])

    inline = inline_definitions()
    derived_references = {
        "contracts/events/v1/event-types.json",
        "contracts/ports/v1/problem-catalog.json",
    }
    defined_references = set(EXACT_SCHEMA_TARGETS) | set(inline) | derived_references
    require(
        defined_references == set(usage_kinds),
        "type definitions do not exactly cover registry references; "
        f"missing={sorted(set(usage_kinds)-defined_references)} "
        f"orphans={sorted(defined_references-set(usage_kinds))}",
    )

    type_schemas: dict[str, dict[str, Any]] = {}
    type_sources: dict[str, dict[str, Any]] = {}
    type_samples: dict[str, Any] = {}

    for reference, target in EXACT_SCHEMA_TARGETS.items():
        base, fragment = urldefrag(target)
        require(base in source_schemas, f"schema target is not available offline: {target}")
        type_schemas[reference] = schema_document(reference, {"$ref": target})
        type_sources[reference] = {
            "kind": "schema-target",
            "schemaId": base,
            "schemaDigest": canonical_digest(source_schemas[base]),
            "jsonPointer": f"/{fragment.lstrip('/')}" if fragment else "",
        }
        type_samples[reference] = schema_target_sample(
            reference, target, positive_fixtures
        )

    for reference, (body, sample) in inline.items():
        type_schemas[reference] = schema_document(reference, body)
        type_sources[reference] = {"kind": "inline"}
        type_samples[reference] = resolve_sample_marker(sample, positive_fixtures)

    event_document = load_json(REPOSITORY_ROOT / "contracts/events/v1/event-types.json")
    event_values = [entry["type"] for entry in event_document["eventTypes"]]
    event_reference = "contracts/events/v1/event-types.json"
    type_schemas[event_reference] = schema_document(
        event_reference,
        {"type": "string", "enum": event_values, "maxLength": 256},
    )
    type_sources[event_reference] = {
        "kind": "derived-enum",
        "repositoryPath": event_reference,
        "documentDigest": canonical_digest(event_document),
        "arrayPointer": "/eventTypes",
        "valuePointer": "/type",
    }
    type_samples[event_reference] = event_values[0]

    exit_values = sorted({entry["cliExit"] for entry in problem_document["problems"]})
    problem_reference = "contracts/ports/v1/problem-catalog.json"
    type_schemas[problem_reference] = schema_document(
        problem_reference,
        {"type": "integer", "enum": exit_values},
    )
    type_sources[problem_reference] = {
        "kind": "derived-enum",
        "repositoryPath": problem_reference,
        "documentDigest": canonical_digest(problem_document),
        "arrayPointer": "/problems",
        "valuePointer": "/cliExit",
    }
    type_samples[problem_reference] = exit_values[0]

    seed_source_ids: set[str] = set()
    for schema in type_schemas.values():
        Draft202012Validator.check_schema(schema)
        for reference in iter_references(schema):
            if reference.startswith("#"):
                continue
            base, _ = urldefrag(reference)
            if base.startswith(SCHEMA_PREFIX):
                seed_source_ids.add(base)
    closed_source_ids = source_closure(seed_source_ids, source_schemas)
    schema_sources = [
        {
            "schemaId": source_id,
            "schemaDigest": canonical_digest(source_schemas[source_id]),
            "repositoryPath": source_paths[source_id],
            "mediaType": "application/schema+json",
        }
        for source_id in sorted(closed_source_ids)
    ]

    base_validation_registry = build_registry(
        closed_source_ids, source_schemas, type_schemas
    )
    base_type_entries: list[dict[str, Any]] = []
    for reference in sorted(type_schemas):
        schema = type_schemas[reference]
        sample = type_samples[reference]
        valid_errors = validation_errors(schema, sample, base_validation_registry)
        require(
            not valid_errors,
            f"valid type fixture is rejected for {reference}: {valid_errors[0].message if valid_errors else ''}",
        )
        invalid = invalid_value(sample)
        invalid_errors = validation_errors(schema, invalid, base_validation_registry)
        require(invalid_errors, f"invalid type fixture is accepted for {reference}")
        base_type_entries.append(
            {
                "schemaRef": reference,
                "usageKinds": sorted(usage_kinds[reference]),
                "schemaDigest": canonical_digest(schema),
                "schema": schema,
                "source": type_sources[reference],
                "fixture": {
                    "valid": sample,
                    "invalid": {
                        "instance": invalid,
                        "expectedKeyword": invalid_errors[0].validator,
                    },
                },
            }
        )

    base_type_ids = {
        entry["schemaRef"]: entry["schema"]["$id"] for entry in base_type_entries
    }
    field_type_schemas: dict[str, dict[str, Any]] = {}
    field_type_samples: dict[str, Any] = {}
    field_type_metadata: dict[str, dict[str, str]] = {}
    for port in port_registry["ports"]:
        for operation in port["operations"]:
            for direction, fields_key in (
                ("request", "requestFields"),
                ("result", "resultFields"),
            ):
                for field in operation[fields_key]:
                    value_type = field["valueType"]
                    expected_value_type = field_value_type_id(
                        port["portId"],
                        operation["operationId"],
                        direction,
                        field["name"],
                    )
                    require(
                        value_type == expected_value_type,
                        f"field value type drift: {value_type} != {expected_value_type}",
                    )
                    require(
                        value_type not in field_type_schemas,
                        f"duplicate field value type: {value_type}",
                    )
                    base_schema = {"$ref": base_type_ids[field["schemaRef"]]}
                    if field["schemaRef"] == "primitive:string":
                        refinement, body, sample = semantic_string_override(
                            port["portId"],
                            operation["operationId"],
                            direction,
                            field["name"],
                        )
                    elif (
                        port["portId"] == "bytedesk.port.capability-verifier/1"
                        and operation["operationId"] == "verify-capability-result"
                        and direction == "request"
                        and field["name"] == "capabilityEvidence"
                    ):
                        refinement = "consumer-capability-verifier-actor"
                        body = {
                            "allOf": [
                                base_schema,
                                {
                                    "required": ["actor", "capabilityDispatch"],
                                    "properties": {
                                        "actor": {
                                            "const": "consumer_capability_verifier"
                                        }
                                    },
                                },
                            ]
                        }
                        sample = load_json(
                            REPOSITORY_ROOT
                            / "contracts"
                            / "fixtures"
                            / "schema"
                            / "positive"
                            / "canary-evidence__capability.json"
                        )
                    elif field["schemaRef"] == "primitive:nonnegative-integer":
                        refinement, body, sample = semantic_integer_override(
                            port["portId"],
                            operation["operationId"],
                            direction,
                            field["name"],
                        )
                    elif (
                        field["type"] == "array"
                        and field["schemaRef"] in EXACT_ARRAY_SCHEMA_REFS
                    ):
                        refinement = "exact-array-contract"
                        body = base_schema
                        sample = deepcopy(type_samples[field["schemaRef"]])
                    elif field["type"] == "array":
                        refinement = "bounded-array"
                        body: dict[str, Any] = {
                            "type": "array",
                            "minItems": 0,
                            "maxItems": ARRAY_MAX_ITEMS,
                            "items": base_schema,
                        }
                        sample = [deepcopy(type_samples[field["schemaRef"]])]
                    else:
                        refinement = "base"
                        body = base_schema
                        sample = deepcopy(type_samples[field["schemaRef"]])
                    field_type_schemas[value_type] = schema_document(value_type, body)
                    field_type_samples[value_type] = sample
                    field_type_metadata[value_type] = {
                        "portId": port["portId"],
                        "operationId": operation["operationId"],
                        "direction": direction,
                        "fieldName": field["name"],
                        "baseSchemaRef": field["schemaRef"],
                        "refinement": refinement,
                    }

    all_type_schemas = dict(type_schemas)
    all_type_schemas.update(field_type_schemas)
    validation_registry = build_registry(
        closed_source_ids, source_schemas, all_type_schemas
    )
    field_type_entries: list[dict[str, Any]] = []
    for value_type, schema in field_type_schemas.items():
        sample = field_type_samples[value_type]
        valid_errors = validation_errors(schema, sample, validation_registry)
        require(
            not valid_errors,
            f"valid field-type fixture is rejected for {value_type}: "
            f"{valid_errors[0].message if valid_errors else ''}",
        )
        invalid = invalid_value(sample)
        invalid_errors = validation_errors(schema, invalid, validation_registry)
        require(invalid_errors, f"invalid field-type fixture is accepted: {value_type}")
        metadata = field_type_metadata[value_type]
        field_type_entries.append(
            {
                "typeId": value_type,
                "portId": metadata["portId"],
                "operationId": metadata["operationId"],
                "direction": metadata["direction"],
                "fieldName": metadata["fieldName"],
                "baseSchemaRef": metadata["baseSchemaRef"],
                "refinement": metadata["refinement"],
                "schemaDigest": canonical_digest(schema),
                "schema": schema,
                "fixture": {
                    "valid": sample,
                    "invalid": {
                        "instance": invalid,
                        "expectedKeyword": invalid_errors[0].validator,
                    },
                },
            }
        )

    field_type_schema_ids = {
        entry["typeId"]: entry["schema"]["$id"] for entry in field_type_entries
    }
    contract_entries: list[dict[str, Any]] = []
    fixture_entries: list[dict[str, Any]] = []
    for port in port_registry["ports"]:
        for operation in port["operations"]:
            for direction, contract_key, fields_key in (
                ("request", "requestContract", "requestFields"),
                ("result", "resultContract", "resultFields"),
            ):
                contract_id = operation[contract_key]
                fields = operation[fields_key]
                schema = compile_contract_schema(
                    contract_id, fields, field_type_schema_ids
                )
                Draft202012Validator.check_schema(schema)
                contract_entries.append(
                    {
                        "contractId": contract_id,
                        "portId": port["portId"],
                        "operationId": operation["operationId"],
                        "direction": direction,
                        "schemaId": schema["$id"],
                        "schemaDigest": canonical_digest(schema),
                        "schema": schema,
                    }
                )
                valid: dict[str, Any] = {}
                for field in fields:
                    valid[field["name"]] = deepcopy(
                        field_type_samples[field["valueType"]]
                    )
                normalize_operation_fixture(contract_id, valid)
                errors = validation_errors(schema, valid, validation_registry)
                require(
                    not errors,
                    f"generated valid contract fixture is rejected for {contract_id}: "
                    f"{errors[0].message if errors else ''}",
                )

                unknown = deepcopy(valid)
                unknown["__unknown"] = True
                missing = deepcopy(valid)
                del missing[fields[0]["name"]]
                illegal_null = deepcopy(valid)
                nonnullable = next(
                    field
                    for field in fields
                    if not field["type"].endswith("-or-null")
                )
                illegal_null[nonnullable["name"]] = None
                denials: list[dict[str, Any]] = []
                for denial_kind, instance in (
                    ("unknown-field", unknown),
                    ("missing-required", missing),
                    ("illegal-null", illegal_null),
                ):
                    denial_errors = validation_errors(
                        schema, instance, validation_registry
                    )
                    require(
                        denial_errors,
                        f"structural denial is accepted for {contract_id}/{denial_kind}",
                    )
                    denials.append(
                        {
                            "kind": denial_kind,
                            "instance": instance,
                            "expectedKeyword": denial_errors[0].validator,
                        }
                    )
                semantic_denials: list[dict[str, Any]] = []
                for denial_kind, instance in operation_semantic_mutations(
                    contract_id, valid
                ):
                    denial_errors = validation_errors(
                        schema, instance, validation_registry
                    )
                    require(
                        denial_errors,
                        f"semantic denial is accepted for {contract_id}/{denial_kind}",
                    )
                    semantic_denials.append(
                        {
                            "kind": denial_kind,
                            "instance": instance,
                            "expectedKeyword": "oneOf",
                        }
                    )
                fixture_entries.append(
                    {
                        "contractId": contract_id,
                        "valid": valid,
                        "structuralDenials": denials,
                        "semanticDenials": semantic_denials,
                    }
                )

    fixture_catalog = {
        "$schema": schema_id("port-contract-fixtures"),
        "profile": "bytedesk.port-contract-fixtures/1",
        "version": 1,
        "registryDigest": registry_digest,
        "contracts": fixture_entries,
    }
    fixture_digest = canonical_digest(fixture_catalog)
    type_catalog = {
        "$schema": schema_id("port-type-catalog"),
        "profile": "bytedesk.port-type-catalog/1",
        "version": 1,
        "registry": {
            "path": "contracts/ports/v1/port-registry.json",
            "digest": registry_digest,
        },
        "schemaDialect": DIALECT,
        "wireProfile": {
            "jsonEncoding": "utf-8-rfc8785-jcs-json",
            "unknownFields": "reject",
            "nullability": "only-explicit-nullable-types",
            "array": {"minItems": 0, "maxItems": ARRAY_MAX_ITEMS},
            "string": {"maxCodePoints": STRING_MAX_CODE_POINTS},
            "bytes": {
                "encoding": "base64url-no-padding",
                "maxDecodedBytes": BYTES_MAX_DECODED,
                "maxEncodedCharacters": BYTES_MAX_ENCODED,
            },
            "integer": {"minimum": 0, "maximum": 9007199254740991},
        },
        "schemaSources": schema_sources,
        "baseTypes": base_type_entries,
        "types": field_type_entries,
        "contracts": contract_entries,
        "fixtures": {
            "profile": fixture_catalog["profile"],
            "path": "contracts/ports/v1/contract-fixtures.json",
            "digest": fixture_digest,
        },
    }
    return type_catalog, fixture_catalog, problem_schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if checked-in generated artifacts differ from current inputs",
    )
    parser.add_argument(
        "--normalize-registry",
        action="store_true",
        help="materialize the deterministic unique valueType on every registry field",
    )
    parser.add_argument(
        "--normalize-cases",
        action="store_true",
        help="materialize exact covered port owner suites on every conformance case",
    )
    parser.add_argument(
        "--problem-schema-only",
        action="store_true",
        help=(
            "refresh or check only problem-details.schema.json as the required "
            "schema-inventory prepass"
        ),
    )
    args = parser.parse_args()
    try:
        if args.normalize_registry:
            registry = load_json(REGISTRY_PATH)
            write_atomic(REGISTRY_PATH, output_bytes(normalize_registry_value_types(registry)))
        if args.normalize_cases:
            registry = load_json(REGISTRY_PATH)
            cases = load_json(CASE_CATALOG_PATH)
            write_atomic(
                CASE_CATALOG_PATH,
                output_bytes(normalize_case_port_suites(cases, registry)),
            )
        if args.problem_schema_only:
            problem_schema = generate_problem_details_schema()
            type_catalog = None
            fixture_catalog = None
            outputs = {
                PROBLEM_DETAILS_SCHEMA_PATH: output_bytes(problem_schema),
            }
        else:
            type_catalog, fixture_catalog, problem_schema = generate_documents()
            outputs = {
                PROBLEM_DETAILS_SCHEMA_PATH: output_bytes(problem_schema),
                TYPE_CATALOG_PATH: output_bytes(type_catalog),
                FIXTURE_CATALOG_PATH: output_bytes(fixture_catalog),
            }
        if args.check:
            drift = [
                path.relative_to(REPOSITORY_ROOT).as_posix()
                for path, expected in outputs.items()
                if not path.is_file() or path.read_bytes() != expected
            ]
            require(not drift, f"generated downstream-port artifacts drift: {drift}")
        else:
            for path, payload in outputs.items():
                write_atomic(path, payload)
    except (GenerationError, ValueError) as error:
        print(f"downstream-port type generation failed: {error}", file=sys.stderr)
        return 1
    action = "verified" if args.check else "generated"
    if args.problem_schema_only:
        print(
            f"problem-details schema {action}: "
            f"{len(problem_schema['properties']['code']['enum'])} problem codes, "
            f"{len(problem_schema['properties']['portId']['enum'])} ports, "
            f"{len(problem_schema['allOf'][1]['oneOf'])} operation variants"
        )
        return 0
    require(type_catalog is not None, "type catalog generation did not complete")
    require(fixture_catalog is not None, "fixture catalog generation did not complete")
    print(
        f"downstream-port types {action}: "
        f"{len(type_catalog['baseTypes'])} base types, "
        f"{len(type_catalog['types'])} field types, "
        f"{len(type_catalog['contracts'])} contracts, "
        f"{len(fixture_catalog['contracts'])} fixtures, "
        f"{len(problem_schema['properties']['code']['enum'])} problem codes, "
        f"{len(problem_schema['allOf'][1]['oneOf'])} problem operation variants"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
