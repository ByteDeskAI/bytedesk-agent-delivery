#!/usr/bin/env python3
"""Compile the prose conformance requirements into an exact adapter-ready plan.

The compiled plan deliberately labels the generated port fixtures as structural
schema samples.  They are executable contract inputs, not evidence that an
adapter has implemented the domain behavior named by a conformance case.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

from contractlib import (
    ContractToolError,
    REPOSITORY_ROOT,
    canonical_digest,
    load_json,
    validation_error_key,
    write_bytes,
)


PORT_ROOT = REPOSITORY_ROOT / "contracts" / "ports" / "v1"
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"

REGISTRY_PATH = PORT_ROOT / "port-registry.json"
TYPE_CATALOG_PATH = PORT_ROOT / "type-catalog.json"
FIXTURE_CATALOG_PATH = PORT_ROOT / "contract-fixtures.json"
PROBLEM_CATALOG_PATH = PORT_ROOT / "problem-catalog.json"
ACTION_CATALOG_PATH = PORT_ROOT / "action-catalog.json"
EVENT_TYPES_PATH = REPOSITORY_ROOT / "contracts" / "events" / "v1" / "event-types.json"
PROTOCOL_PROFILE_PATH = PORT_ROOT / "protocol-profiles.json"
CASE_CATALOG_PATH = PORT_ROOT / "conformance-cases.json"
PROTOCOL_FIXTURE_PATH = PORT_ROOT / "protocol-fixtures.json"
PLAN_PATH = PORT_ROOT / "conformance-plan.json"
PLAN_SCHEMA_PATH = SCHEMA_ROOT / "downstream-conformance-plan.schema.json"
POSITIVE_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "positive"
    / "downstream-conformance-plan__minimal.json"
)
NEGATIVE_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "fixtures"
    / "schema"
    / "negative"
    / "downstream-conformance-plan__unknown-root-field.json"
)

PLAN_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/"
    "downstream-conformance-plan/1.0.0"
)
PLAN_PROFILE = "bytedesk.downstream-conformance-plan/1"
DIGEST_ZERO = "sha256:" + "0" * 64

INPUT_BINDINGS = (
    ("port-registry", REGISTRY_PATH, "portRegistry"),
    ("type-catalog", TYPE_CATALOG_PATH, "typeCatalog"),
    ("contract-fixtures", FIXTURE_CATALOG_PATH, "fixtureCatalog"),
    ("problem-catalog", PROBLEM_CATALOG_PATH, "problemCatalog"),
    ("action-catalog", ACTION_CATALOG_PATH, "actionCatalog"),
    ("event-types", EVENT_TYPES_PATH, "eventTypes"),
    ("protocol-profiles", PROTOCOL_PROFILE_PATH, "protocolProfiles"),
    ("case-catalog", CASE_CATALOG_PATH, "caseCatalog"),
    ("protocol-fixtures", PROTOCOL_FIXTURE_PATH, "protocolFixtures"),
)


class ConformancePlanError(RuntimeError):
    """A deterministic conformance-plan compilation or validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConformancePlanError(message)


def repository_path(path: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except (OSError, ValueError) as error:
        raise ConformancePlanError(f"input path is unavailable or escapes repository: {path}") from error


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


def unique_index(values: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(values):
        require(isinstance(value, dict), f"{label}[{index}] must be an object")
        identifier = value.get(key)
        require(isinstance(identifier, str) and identifier, f"{label}[{index}] lacks {key}")
        require(identifier not in result, f"duplicate {label} {key}: {identifier}")
        result[identifier] = value
    return result


def load_sources() -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for _role, path, name in INPUT_BINDINGS:
        value = load_json(path)
        require(isinstance(value, dict), f"source root must be an object: {path}")
        documents[name] = value

    registry = documents["portRegistry"]
    type_catalog = documents["typeCatalog"]
    fixture_catalog = documents["fixtureCatalog"]
    problems = documents["problemCatalog"]
    actions = documents["actionCatalog"]
    events = documents["eventTypes"]
    profiles = documents["protocolProfiles"]
    cases = documents["caseCatalog"]
    protocol = documents["protocolFixtures"]

    require(registry.get("profile") == "bytedesk.downstream-port-registry/1", "wrong port registry profile")
    require(type_catalog.get("profile") == "bytedesk.port-type-catalog/1", "wrong type catalog profile")
    require(fixture_catalog.get("profile") == "bytedesk.port-contract-fixtures/1", "wrong fixture catalog profile")
    require(problems.get("profile") == "bytedesk.problem-catalog/1", "wrong problem catalog profile")
    require(actions.get("profile") == "bytedesk.action-catalog/1", "wrong action catalog profile")
    require(events.get("profile") == "bytedesk.event-types/1", "wrong event type registry profile")
    require(profiles.get("profile") == "bytedesk.protocol-profiles/1", "wrong protocol profile catalog")
    require(cases.get("profile") == "bytedesk.downstream-conformance-cases/1", "wrong case catalog profile")
    require(protocol.get("profile") == "bytedesk.protocol-fixtures/1", "wrong protocol fixture profile")

    registry_digest = canonical_digest(registry)
    require(type_catalog.get("registry", {}).get("digest") == registry_digest, "type catalog registry binding drift")
    require(fixture_catalog.get("registryDigest") == registry_digest, "fixture catalog registry binding drift")
    require(
        type_catalog.get("fixtures", {}).get("digest") == canonical_digest(fixture_catalog),
        "type catalog fixture binding drift",
    )

    operations: dict[tuple[str, str], dict[str, Any]] = {}
    operation_order: list[tuple[str, str]] = []
    ports: dict[str, dict[str, Any]] = {}
    for port in registry.get("ports", []):
        port_id = port.get("portId")
        require(isinstance(port_id, str), "port lacks portId")
        require(port_id not in ports, f"duplicate port: {port_id}")
        ports[port_id] = port
        for operation in port.get("operations", []):
            operation_id = operation.get("operationId")
            key = (port_id, operation_id)
            require(isinstance(operation_id, str), f"operation lacks operationId: {port_id}")
            require(key not in operations, f"duplicate operation: {port_id}#{operation_id}")
            operations[key] = operation
            operation_order.append(key)
    require(operation_order, "port registry has no operations")

    contracts = unique_index(type_catalog.get("contracts", []), "contractId", "compiled contracts")
    contract_fixtures = unique_index(
        fixture_catalog.get("contracts", []), "contractId", "contract fixtures"
    )
    require(set(contracts) == set(contract_fixtures), "compiled contract and fixture sets differ")
    require(len(contracts) == 2 * len(operations), "each operation must own request and result contracts")

    for port_id, operation_id in operation_order:
        operation = operations[(port_id, operation_id)]
        for direction in ("request", "result"):
            contract_id = operation[f"{direction}Contract"]
            require(contract_id in contracts, f"missing {direction} contract: {port_id}#{operation_id}")
            contract = contracts[contract_id]
            require(
                contract.get("portId") == port_id
                and contract.get("operationId") == operation_id
                and contract.get("direction") == direction,
                f"compiled contract binding drift: {contract_id}",
            )
            require(
                contract.get("schemaDigest") == canonical_digest(contract.get("schema")),
                f"compiled contract schema digest drift: {contract_id}",
            )

    problem_index = unique_index(problems.get("problems", []), "code", "problems")
    action_index = unique_index(actions.get("actions", []), "kind", "actions")
    for action_kind, action in action_index.items():
        operation_key = (action.get("portId"), action.get("operationId"))
        require(operation_key in operations, f"action references unknown operation: {action_kind}")
        operation = operations[operation_key]
        require(
            action.get("requestContract") == operation["requestContract"],
            f"action request contract drift: {action_kind}",
        )
        operation_codes = {error["code"] for error in operation["errors"]}
        require(
            set(action.get("failureCodes", [])) <= operation_codes,
            f"action failure code is absent from its operation: {action_kind}",
        )
    event_index = unique_index(events.get("eventTypes", []), "type", "event types")
    schema_source_digests = {
        source["schemaId"]: source["schemaDigest"]
        for source in type_catalog.get("schemaSources", [])
    }
    for event_type, event in event_index.items():
        require(
            schema_source_digests.get(event.get("resourceSchemaId"))
            == event.get("resourceSchemaDigest"),
            f"event resource schema binding drift: {event_type}",
        )
    profile_index = unique_index(profiles.get("profiles", []), "profileId", "protocol profiles")
    for port_id, port in ports.items():
        protocol_profile_ids = port.get("protocolProfiles")
        require(
            isinstance(protocol_profile_ids, list)
            and len(protocol_profile_ids) == len(set(protocol_profile_ids)),
            f"port protocolProfiles must be a unique array: {port_id}",
        )
        for profile_id in protocol_profile_ids:
            require(
                profile_id in profile_index,
                f"port references unknown protocol profile: {port_id}/{profile_id}",
            )
    case_index = unique_index(cases.get("cases", []), "caseId", "conformance cases")
    protocol_fixture_index = unique_index(protocol.get("fixtures", []), "fixtureId", "protocol fixtures")
    protocol_mutation_index = unique_index(protocol.get("mutations", []), "mutationId", "protocol mutations")

    documents.update(
        {
            "operations": operations,
            "operationOrder": operation_order,
            "ports": ports,
            "contracts": contracts,
            "contractFixtures": contract_fixtures,
            "problems": problem_index,
            "actions": action_index,
            "events": event_index,
            "profileIndex": profile_index,
            "cases": case_index,
            "protocolFixtureIndex": protocol_fixture_index,
            "protocolMutationIndex": protocol_mutation_index,
        }
    )
    return documents


def contract_reference(
    operation: dict[str, Any], direction: str, sources: dict[str, Any]
) -> dict[str, Any]:
    contract_id = operation[f"{direction}Contract"]
    contract = sources["contracts"][contract_id]
    fixture = sources["contractFixtures"][contract_id]
    return {
        "contractId": contract_id,
        "schemaId": contract["schemaId"],
        "schemaDigest": contract["schemaDigest"],
        "fixture": {
            "catalogPath": repository_path(FIXTURE_CATALOG_PATH),
            "contractId": contract_id,
            "selector": "valid",
            "validity": "schema-valid-structural-sample",
            "instanceDigest": canonical_digest(fixture["valid"]),
        },
    }


def pass_oracle() -> dict[str, Any]:
    return {"outcome": "pass", "problemCode": None, "sideEffectState": "none"}


def normalize_directives(fixture: dict[str, Any]) -> list[dict[str, str]]:
    directives: list[dict[str, str]] = []
    scalar_fields = (
        ("assertion", "assertion"),
        ("fault", "fault"),
        ("fixture", "fixture-scenario"),
        ("kind", "harness-profile"),
        ("mutation", "mutation"),
        ("recovery", "recovery"),
    )
    for source_key, kind in scalar_fields:
        if source_key in fixture:
            value = fixture[source_key]
            require(isinstance(value, str) and value, f"fixture {source_key} must be a string")
            directives.append({"kind": kind, "value": value})
    for source_key, kind in (("assertions", "assertion"), ("mutations", "mutation")):
        if source_key in fixture:
            values = fixture[source_key]
            require(isinstance(values, list) and values, f"fixture {source_key} must be an array")
            for value in values:
                require(isinstance(value, str) and value, f"fixture {source_key} item must be a string")
                directives.append({"kind": kind, "value": value})
    for fixture_id in fixture.get("protocolFixtureIds", []):
        directives.append({"kind": "protocol-fixture", "value": fixture_id})
    for mutation_id in fixture.get("protocolMutationIds", []):
        directives.append({"kind": "protocol-mutation", "value": mutation_id})
    require(directives, "case fixture compiles to no adapter directive")
    return directives


def step_directives(case: dict[str, Any], role: str) -> list[dict[str, str]]:
    fixture = case["fixture"]
    if role == "setup":
        return [
            {
                "kind": "harness-profile",
                "value": "invoke the schema-valid prerequisite without the subject fault",
            }
        ]
    if role == "recovery":
        recovery = fixture.get("recovery")
        require(isinstance(recovery, str) and recovery, f"recovery case lacks recovery directive: {case['caseId']}")
        return [{"kind": "recovery", "value": recovery}]
    directives = normalize_directives(fixture)
    if case["expected"]["outcome"] == "recover":
        directives = [directive for directive in directives if directive["kind"] != "recovery"]
        require(directives, f"recovery fault step lacks a subject directive: {case['caseId']}")
    return directives


def rejecting_key(case: dict[str, Any]) -> tuple[str, str] | None:
    reference = case["fixture"].get("rejectingOperation")
    if reference is None:
        return None
    require(isinstance(reference, str) and "#" in reference, "invalid rejectingOperation")
    port_id, operation_id = reference.split("#", 1)
    return port_id, operation_id


def subject_fault_phase(case: dict[str, Any]) -> str:
    expected = case["expected"]
    fixture = case["fixture"]
    case_id = case["caseId"]
    category = case["category"]
    problem = expected["problemCode"]

    if expected["outcome"] == "pass":
        return "verification"
    if fixture.get("protocolMutationIds"):
        return "verification"
    recovery_overrides = {
        "OCI-002-push-response-lost": "after-commit-before-response",
        "STATE-003-cas-response-lost": "after-commit-before-response",
        "COORD-002-crash-after-remote-cas": "after-commit-before-response",
        "HOST-001-crash-before-switch-intent": "execution",
        "HOST-002-crash-after-intent-before-switch": "commit",
        "HOST-004-crash-after-switch-before-marker": "after-commit-before-response",
        "REGION-002-response-lost-after-epoch": "after-commit-before-response",
    }
    if expected["outcome"] == "recover":
        return recovery_overrides.get(case_id, "execution")
    if expected["sideEffectState"] == "commit-unknown":
        return "commit"
    if problem in {"authentication_failed", "trust_verification_failed"}:
        return "authentication"
    if problem in {
        "authorization_denied",
        "signer_purpose_mismatch",
        "authority_invalid",
        "skill_approval_invalid",
    }:
        return "authorization"
    if problem in {
        "precondition_failed",
        "desired_state_cas_mismatch",
        "migration_quiesce_required",
        "host_fenced",
        "region_fence_unproven",
        "idempotency_collision",
    } or "cas" in category or "fencing" in category:
        return "precondition"
    if problem == "dependency_unavailable":
        return "dependency"
    if problem in {"invalid_request", "source_not_immutable", "external_input_unpinned"}:
        return "request-validation"
    return "verification"


def subject_action(case: dict[str, Any]) -> str:
    fixture = case["fixture"]
    if fixture.get("protocolMutationIds"):
        return "execute-protocol-mutations"
    if case["expected"]["outcome"] == "pass":
        return "assert-requirement"
    if "fault" in fixture or "fixture" in fixture:
        return "inject-fault"
    return "apply-case-mutation"


def compile_step(
    case: dict[str, Any],
    index: int,
    coverage: dict[str, Any],
    role: str,
    sources: dict[str, Any],
) -> dict[str, Any]:
    key = (coverage["portId"], coverage["operationId"])
    operation = sources["operations"][key]
    source_fixture = case["fixture"]
    if role == "subject":
        action = subject_action(case)
        phase = subject_fault_phase(case)
        oracle = deepcopy(case["expected"])
        protocol_fixture_ids = list(source_fixture.get("protocolFixtureIds", []))
        protocol_mutation_ids = list(source_fixture.get("protocolMutationIds", []))
    elif role == "recovery":
        action = "resolve"
        phase = "recovery"
        oracle = pass_oracle()
        protocol_fixture_ids = []
        protocol_mutation_ids = []
    else:
        action = "invoke"
        phase = "none"
        oracle = pass_oracle()
        protocol_fixture_ids = []
        protocol_mutation_ids = []
    return {
        "stepId": f"{case['caseId']}/{index + 1:03d}",
        "role": role,
        "portId": key[0],
        "operationId": key[1],
        "protocolProfileIds": list(sources["ports"][key[0]]["protocolProfiles"]),
        "request": contract_reference(operation, "request", sources),
        "result": contract_reference(operation, "result", sources),
        "harness": {
            "action": action,
            "faultPhase": phase,
            "directiveId": f"bytedesk.conformance.case/{case['caseId']}/1",
            "sourceFixtureDigest": canonical_digest(source_fixture),
            "directives": step_directives(case, role),
            "protocolFixtureIds": protocol_fixture_ids,
            "protocolMutationIds": protocol_mutation_ids,
        },
        "oracle": oracle,
    }


def compile_case(case: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    covers = case.get("covers")
    require(isinstance(covers, list) and covers, f"case has no operation coverage: {case.get('caseId')}")
    expected = case.get("expected")
    require(isinstance(expected, dict), f"case lacks oracle: {case.get('caseId')}")
    rejection = rejecting_key(case)

    steps: list[dict[str, Any]] = []
    subject_seen = False
    for index, coverage in enumerate(covers):
        key = (coverage.get("portId"), coverage.get("operationId"))
        require(key in sources["operations"], f"case covers unknown operation: {case['caseId']}/{key}")
        if expected["outcome"] == "deny":
            role = "subject" if key == rejection else "setup"
        elif expected["outcome"] == "recover":
            role = "subject" if index == 0 else "recovery"
        else:
            role = "subject"
        subject_seen = subject_seen or role == "subject"
        steps.append(compile_step(case, index, coverage, role, sources))
    require(subject_seen, f"case compiles without a subject step: {case['caseId']}")

    return {
        "caseId": case["caseId"],
        "sourceCaseDigest": canonical_digest(case),
        "suite": case["suite"],
        "ownerTask": case["ownerTask"],
        "category": case["category"],
        "execution": {
            "adapterExecutionRequired": True,
            "semanticImplementationGolden": False,
            "sourceCasePath": repository_path(CASE_CATALOG_PATH),
        },
        "steps": steps,
        "oracle": deepcopy(expected),
    }


def compile_plan(sources: dict[str, Any]) -> dict[str, Any]:
    input_bindings = []
    for role, path, name in INPUT_BINDINGS:
        document = sources[name]
        input_bindings.append(
            {
                "role": role,
                "path": repository_path(path),
                "profile": document["profile"],
                "digest": canonical_digest(document),
            }
        )

    golden_invocations = []
    for port_id, operation_id in sources["operationOrder"]:
        operation = sources["operations"][(port_id, operation_id)]
        golden_invocations.append(
            {
                "invocationId": f"{port_id}#{operation_id}:schema-golden/1",
                "portId": port_id,
                "operationId": operation_id,
                "protocolProfileIds": list(sources["ports"][port_id]["protocolProfiles"]),
                "semanticImplementationGolden": False,
                "request": contract_reference(operation, "request", sources),
                "result": contract_reference(operation, "result", sources),
                "harness": {
                    "action": "invoke",
                    "faultPhase": "none",
                    "directiveId": f"bytedesk.conformance.operation/{port_id}#{operation_id}/1",
                },
                "oracle": pass_oracle(),
            }
        )

    return {
        "$schema": PLAN_SCHEMA_ID,
        "profile": PLAN_PROFILE,
        "version": 1,
        "semantics": {
            "contractFixtureValidity": "schema-valid-only",
            "semanticImplementationGolden": False,
            "adapterExecutionRequired": True,
        },
        "inputs": input_bindings,
        "goldenInvocations": golden_invocations,
        "cases": [compile_case(case, sources) for case in sources["caseCatalog"]["cases"]],
    }


def schema_fixtures(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a small valid plan and its single-fault closed-root denial."""

    minimal_case = next(case for case in plan["cases"] if len(case["steps"]) == 1)
    subject = minimal_case["steps"][0]
    minimal_golden = next(
        golden
        for golden in plan["goldenInvocations"]
        if golden["portId"] == subject["portId"]
        and golden["operationId"] == subject["operationId"]
    )
    positive = {
        "$schema": plan["$schema"],
        "profile": plan["profile"],
        "version": plan["version"],
        "semantics": deepcopy(plan["semantics"]),
        "inputs": deepcopy(plan["inputs"]),
        "goldenInvocations": [deepcopy(minimal_golden)],
        "cases": [deepcopy(minimal_case)],
    }
    negative = deepcopy(positive)
    negative["unexpectedAuthority"] = "must-be-rejected"
    return positive, negative


def schema_registry(sources: dict[str, Any]) -> Registry:
    documents: dict[str, dict[str, Any]] = {}
    for source in sources["typeCatalog"]["schemaSources"]:
        path = REPOSITORY_ROOT / source["repositoryPath"]
        schema = load_json(path)
        require(schema.get("$id") == source["schemaId"], f"schema source ID drift: {path}")
        require(canonical_digest(schema) == source["schemaDigest"], f"schema source digest drift: {path}")
        documents[source["schemaId"]] = schema
    for collection in ("baseTypes", "types", "contracts"):
        for entry in sources["typeCatalog"][collection]:
            schema = entry["schema"]
            schema_id = schema["$id"]
            require(schema_id not in documents, f"duplicate offline schema ID: {schema_id}")
            require(entry["schemaDigest"] == canonical_digest(schema), f"schema digest drift: {schema_id}")
            documents[schema_id] = schema
    try:
        return Registry().with_resources(
            (schema_id, Resource.from_contents(schema))
            for schema_id, schema in documents.items()
        )
    except ValueError as error:
        raise ConformancePlanError(f"cannot build offline schema registry: {error}") from error


def all_validation_errors(
    schema: dict[str, Any], instance: Any, registry: Registry
) -> list[Any]:
    return sorted(
        Draft202012Validator(schema, registry=registry).iter_errors(instance),
        key=validation_error_key,
    )


def error_keywords(errors: list[Any]) -> set[str]:
    keywords: set[str] = set()
    pending = list(errors)
    while pending:
        error = pending.pop()
        keywords.add(str(error.validator))
        pending.extend(error.context)
    return keywords


def validate_contract_fixtures(sources: dict[str, Any]) -> tuple[int, int]:
    registry = schema_registry(sources)
    valid_count = 0
    mutation_count = 0
    for contract_id, contract in sources["contracts"].items():
        schema = contract["schema"]
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise ConformancePlanError(f"invalid compiled schema {contract_id}: {error}") from error
        fixture = sources["contractFixtures"][contract_id]
        valid_errors = all_validation_errors(schema, fixture["valid"], registry)
        require(not valid_errors, f"valid contract fixture rejected: {contract_id}")
        valid_count += 1
        for denial in fixture["structuralDenials"] + fixture["semanticDenials"]:
            errors = all_validation_errors(schema, denial["instance"], registry)
            require(errors, f"contract denial accepted: {contract_id}/{denial['kind']}")
            require(
                denial["expectedKeyword"] in error_keywords(errors),
                f"contract denial keyword drift: {contract_id}/{denial['kind']}",
            )
            mutation_count += 1
    return valid_count, mutation_count


def validate_oracles(plan: dict[str, Any], sources: dict[str, Any]) -> None:
    operation_goldens = {
        (item["portId"], item["operationId"]) for item in plan["goldenInvocations"]
    }
    require(len(operation_goldens) == len(plan["goldenInvocations"]), "duplicate operation golden")
    require(operation_goldens == set(sources["operations"]), "operation golden coverage differs")
    for golden in plan["goldenInvocations"]:
        require(
            golden["protocolProfileIds"]
            == sources["ports"][golden["portId"]]["protocolProfiles"],
            f"operation golden protocol-profile applicability drift: {golden['invocationId']}",
        )

    compiled_cases = unique_index(plan["cases"], "caseId", "compiled cases")
    require(set(compiled_cases) == set(sources["cases"]), "compiled case set differs")
    for case_id, compiled in compiled_cases.items():
        source = sources["cases"][case_id]
        require(compiled["sourceCaseDigest"] == canonical_digest(source), f"source case digest drift: {case_id}")
        require(compiled["oracle"] == source["expected"], f"case oracle drift: {case_id}")
        actual_coverage = [(step["portId"], step["operationId"]) for step in compiled["steps"]]
        expected_coverage = [(item["portId"], item["operationId"]) for item in source["covers"]]
        require(actual_coverage == expected_coverage, f"compiled step coverage drift: {case_id}")
        for step in compiled["steps"]:
            require(
                step["protocolProfileIds"]
                == sources["ports"][step["portId"]]["protocolProfiles"],
                f"case step protocol-profile applicability drift: {step['stepId']}",
            )

        subjects = [step for step in compiled["steps"] if step["role"] == "subject"]
        if source["expected"]["outcome"] == "deny":
            require(len(subjects) == 1, f"denial must have one rejecting step: {case_id}")
            require(
                source["expected"]["problemCode"] in sources["problems"],
                f"case oracle references an unknown problem: {case_id}",
            )
            reject = rejecting_key(source)
            require((subjects[0]["portId"], subjects[0]["operationId"]) == reject, f"rejecting step drift: {case_id}")
            operation = sources["operations"][reject]
            expected_mapping = {
                "code": source["expected"]["problemCode"],
                "sideEffectState": source["expected"]["sideEffectState"],
            }
            require(expected_mapping in operation["errors"], f"oracle is absent from rejecting operation: {case_id}")
        elif source["expected"]["outcome"] == "recover":
            require(len(subjects) == 1, f"recovery case must have one fault subject: {case_id}")
        else:
            require(len(subjects) == len(compiled["steps"]), f"pass case contains non-subject steps: {case_id}")

        fixture = source["fixture"]
        protocol_fixture_ids = fixture.get("protocolFixtureIds", [])
        protocol_mutation_ids = fixture.get("protocolMutationIds", [])
        for fixture_id in protocol_fixture_ids:
            require(fixture_id in sources["protocolFixtureIndex"], f"unknown protocol fixture: {case_id}/{fixture_id}")
        for mutation_id in protocol_mutation_ids:
            require(mutation_id in sources["protocolMutationIndex"], f"unknown protocol mutation: {case_id}/{mutation_id}")
            mutation = sources["protocolMutationIndex"][mutation_id]
            require(
                mutation["rejectingOperation"] == fixture["rejectingOperation"],
                f"protocol mutation rejecting operation drift: {case_id}/{mutation_id}",
            )
            require(
                mutation["expectedProblemCode"] == source["expected"]["problemCode"],
                f"protocol mutation oracle drift: {case_id}/{mutation_id}",
            )


def validate_plan(plan: dict[str, Any], sources: dict[str, Any]) -> tuple[int, int]:
    require(PLAN_SCHEMA_PATH.is_file(), f"conformance plan schema is missing: {PLAN_SCHEMA_PATH}")
    plan_schema = load_json(PLAN_SCHEMA_PATH)
    require(plan_schema.get("$id") == PLAN_SCHEMA_ID, "conformance plan schema ID drift")
    try:
        Draft202012Validator.check_schema(plan_schema)
    except SchemaError as error:
        raise ConformancePlanError(f"invalid conformance plan schema: {error}") from error
    errors = sorted(Draft202012Validator(plan_schema).iter_errors(plan), key=validation_error_key)
    require(not errors, f"conformance plan fails its schema: {errors[0].message if errors else ''}")
    require(plan == compile_plan(sources), "compiled conformance plan differs from current exact inputs")
    fixture_counts = validate_contract_fixtures(sources)
    validate_oracles(plan, sources)
    return fixture_counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the checked-in plan differs from current exact inputs",
    )
    args = parser.parse_args()
    try:
        sources = load_sources()
        plan = compile_plan(sources)
        valid_count, mutation_count = validate_plan(plan, sources)
        positive_fixture, negative_fixture = schema_fixtures(plan)
        plan_schema = load_json(PLAN_SCHEMA_PATH)
        require(
            not list(Draft202012Validator(plan_schema).iter_errors(positive_fixture)),
            "generated positive conformance-plan fixture is invalid",
        )
        negative_errors = list(Draft202012Validator(plan_schema).iter_errors(negative_fixture))
        require(
            any(error.validator == "additionalProperties" for error in negative_errors),
            "generated negative conformance-plan fixture misses additionalProperties denial",
        )
        outputs = {
            PLAN_PATH: output_bytes(plan),
            POSITIVE_FIXTURE_PATH: output_bytes(positive_fixture),
            NEGATIVE_FIXTURE_PATH: output_bytes(negative_fixture),
        }
        if args.check:
            drift = [
                repository_path(path)
                for path, payload in outputs.items()
                if not path.is_file() or path.read_bytes() != payload
            ]
            require(not drift, f"compiled conformance-plan artifacts have generated drift: {drift}")
        else:
            for path, payload in outputs.items():
                write_bytes(path, payload)
    except (ConformancePlanError, ContractToolError, OSError, ValueError) as error:
        print(f"conformance-plan generation failed: {error}", file=sys.stderr)
        return 1
    step_count = sum(len(case["steps"]) for case in plan["cases"])
    action = "verified" if args.check else "generated"
    print(
        f"conformance plan {action}: {len(plan['goldenInvocations'])} operation goldens, "
        f"{len(plan['cases'])} cases, {step_count} steps, "
        f"{valid_count} valid contract fixtures, {mutation_count} denial mutations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
