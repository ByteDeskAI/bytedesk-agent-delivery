#!/usr/bin/env python3
"""Prove the source-resolution corpus against the exact official Agent Spec SDK."""

from __future__ import annotations

import argparse
from copy import deepcopy
from importlib.metadata import version
import json
from pathlib import Path
import sys
import warnings


def deny_network(event: str, _arguments: tuple[object, ...]) -> None:
    if event.startswith("socket."):
        raise RuntimeError(f"Agent Spec conformance attempted forbidden network event {event}")


sys.addaudithook(deny_network)

import rfc8785
from pyagentspec.agent import Agent
from pyagentspec.serialization import AgentSpecDeserializer
from pyagentspec.specialized_agent import (
    AgentSpecializationParameters,
    SpecializedAgent,
)

from contractlib import CONTRACTS_ROOT, ContractToolError, load_json, write_json


PINNED_VERSION = "26.1.2"
FIXTURES = CONTRACTS_ROOT / "fixtures" / "operations" / "source-resolution.cases.json"
FIXTURE_FIELDS = {
    "name",
    "declaredKind",
    "document",
    "officialValid",
    "officialWarningCount",
    "valid",
    "expectedBaseId",
}


def validate_official_fixture(case: dict[str, object]) -> dict[str, object]:
    unknown = set(case) - FIXTURE_FIELDS
    required = {"name", "declaredKind", "document", "officialValid", "valid"}
    missing = required - set(case)
    if unknown or missing:
        raise ContractToolError(
            f"source-resolution fixture is not closed: unknown={sorted(unknown)}, "
            f"missing={sorted(missing)}"
        )
    name = case["name"]
    if not isinstance(name, str) or not name:
        raise ContractToolError("source-resolution fixture name is invalid")
    official_valid = case["officialValid"]
    if not isinstance(official_valid, bool):
        raise ContractToolError(f"{name}: officialValid must be boolean")
    document = case["document"]
    if not isinstance(document, dict):
        raise ContractToolError(f"{name}: document must be an object")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            canonical_document = rfc8785.dumps(deepcopy(document)).decode("utf-8")
            resolved = AgentSpecDeserializer().from_json(canonical_document)
        except Exception as error:  # Official SDK exposes multiple denial types.
            if official_valid:
                raise ContractToolError(
                    f"{name}: official Agent Spec {PINNED_VERSION} denied an expected-valid fixture"
                ) from error
            return {
                "id": name,
                "expected": "deny",
                "outcome": "denied",
                "errorType": type(error).__name__,
            }

    if not official_valid:
        raise ContractToolError(
            f"{name}: official Agent Spec {PINNED_VERSION} accepted an expected-invalid fixture"
        )
    expected_warning_count = case.get("officialWarningCount", 0)
    if not isinstance(expected_warning_count, int) or isinstance(expected_warning_count, bool) or expected_warning_count < 0:
        raise ContractToolError(f"{name}: officialWarningCount must be a non-negative integer")
    if len(caught) != expected_warning_count:
        messages = [str(item.message) for item in caught]
        raise ContractToolError(
            f"{name}: official warning count {len(caught)} != {expected_warning_count}: {messages}"
        )

    component_type = document.get("component_type")
    if component_type == "Agent":
        if type(resolved) is not Agent:
            raise ContractToolError(f"{name}: official result is not exactly Agent")
        observed_kind = "agent"
    elif component_type == "SpecializedAgent":
        if type(resolved) is not SpecializedAgent:
            raise ContractToolError(
                f"{name}: official result is not exactly SpecializedAgent"
            )
        if type(resolved.agent) is not Agent:
            raise ContractToolError(f"{name}: official base did not resolve to Agent")
        if type(resolved.agent_specialization_parameters) is not AgentSpecializationParameters:
            raise ContractToolError(
                f"{name}: official parameters did not resolve to AgentSpecializationParameters"
            )
        observed_kind = "specialized-agent"
    else:
        raise ContractToolError(f"{name}: unknown accepted official component_type")

    return {
        "id": name,
        "expected": "permit",
        "outcome": "permitted",
        "officialKind": observed_kind,
        "warningCount": len(caught),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    installed_version = version("pyagentspec")
    if installed_version != PINNED_VERSION:
        raise ContractToolError(
            f"official Agent Spec SDK version {installed_version!r} is not {PINNED_VERSION!r}"
        )
    fixture_set = load_json(FIXTURES)
    if set(fixture_set) != {"profile", "cases"}:
        raise ContractToolError("source-resolution fixture root is not closed")
    if fixture_set["profile"] != "bytedesk.agent-spec-source-resolution-fixtures/1":
        raise ContractToolError("source-resolution fixture profile is not v1")
    fixtures = fixture_set["cases"]
    if not isinstance(fixtures, list) or not fixtures:
        raise ContractToolError("source-resolution fixture cases are absent")

    cases = [validate_official_fixture(case) for case in fixtures]
    if len({case["id"] for case in cases}) != len(cases):
        raise ContractToolError("source-resolution fixture names are not unique")
    result = {
        "profile": "bytedesk.agent-spec-source-resolution-conformance/1",
        "sdk": "pyagentspec",
        "sdkVersion": installed_version,
        "networkPolicy": "python-audit-hook-deny-all-socket-events",
        "caseCount": len(cases),
        "cases": cases,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
