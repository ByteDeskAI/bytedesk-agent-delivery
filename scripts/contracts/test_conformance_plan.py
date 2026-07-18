#!/usr/bin/env python3
"""Execute and adversarially probe the compiled downstream conformance plan."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

from generate_conformance_plan import (  # type: ignore[import-not-found]
    ConformancePlanError,
    NEGATIVE_FIXTURE_PATH,
    PLAN_PATH,
    POSITIVE_FIXTURE_PATH,
    compile_plan,
    load_sources,
    output_bytes,
    schema_fixtures,
    validate_plan,
)
from contractlib import ContractToolError, canonical_digest, load_json, write_json


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConformancePlanError(message)


def require_rejected(plan: dict, sources: dict, label: str) -> None:
    try:
        validate_plan(plan, sources)
    except ConformancePlanError:
        return
    raise ConformancePlanError(f"adversarial plan mutation was accepted: {label}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        help="atomically write the non-authoritative conformance-plan validation record",
    )
    args = parser.parse_args()
    adversarial_denial_ids = [
        "wrong-contract-schema-digest",
        "structural-fixture-semantic-golden-forbidden",
        "operation-semantic-golden-forbidden",
        "oracle-side-effect-drift",
        "missing-operation-golden",
        "unknown-protocol-mutation",
        "protocol-profile-applicability-drift",
    ]
    try:
        sources = load_sources()
        expected = compile_plan(sources)
        checked_in = load_json(PLAN_PATH)
        require(isinstance(checked_in, dict), "checked-in plan root is not an object")
        valid_fixture_count, denial_mutation_count = validate_plan(checked_in, sources)
        require(checked_in == expected, "checked-in plan differs from deterministic compilation")
        require(
            PLAN_PATH.read_bytes() == output_bytes(expected),
            "checked-in plan bytes differ from deterministic compilation",
        )
        positive_fixture, negative_fixture = schema_fixtures(expected)
        require(load_json(POSITIVE_FIXTURE_PATH) == positive_fixture, "positive plan fixture drift")
        require(load_json(NEGATIVE_FIXTURE_PATH) == negative_fixture, "negative plan fixture drift")

        wrong_schema_digest = deepcopy(checked_in)
        wrong_schema_digest["goldenInvocations"][0]["request"]["schemaDigest"] = (
            "sha256:" + "0" * 64
        )
        require_rejected(wrong_schema_digest, sources, "wrong contract schema digest")

        false_semantic_golden = deepcopy(checked_in)
        false_semantic_golden["semantics"]["semanticImplementationGolden"] = True
        require_rejected(false_semantic_golden, sources, "structural fixture promoted to semantic golden")

        false_operation_golden = deepcopy(checked_in)
        false_operation_golden["goldenInvocations"][0]["semanticImplementationGolden"] = True
        require_rejected(false_operation_golden, sources, "operation sample promoted to semantic golden")

        wrong_oracle = deepcopy(checked_in)
        denial = next(
            case for case in wrong_oracle["cases"] if case["oracle"]["outcome"] == "deny"
        )
        denial["oracle"]["sideEffectState"] = "commit-unknown"
        require_rejected(wrong_oracle, sources, "oracle side-effect drift")

        missing_operation = deepcopy(checked_in)
        missing_operation["goldenInvocations"].pop()
        require_rejected(missing_operation, sources, "operation golden omitted")

        wrong_protocol_mutation = deepcopy(checked_in)
        protocol_case = next(
            case
            for case in wrong_protocol_mutation["cases"]
            if any(step["harness"]["protocolMutationIds"] for step in case["steps"])
        )
        subject = next(step for step in protocol_case["steps"] if step["role"] == "subject")
        subject["harness"]["protocolMutationIds"][0] = "UNKNOWN-MUTATION"
        require_rejected(wrong_protocol_mutation, sources, "unknown protocol mutation")

        wrong_profile_applicability = deepcopy(checked_in)
        profile_ids = wrong_profile_applicability["goldenInvocations"][0]["protocolProfileIds"]
        replacement = ["bytedesk.worker-framing/1"]
        wrong_profile_applicability["goldenInvocations"][0]["protocolProfileIds"] = (
            [] if profile_ids == replacement else replacement
        )
        require_rejected(
            wrong_profile_applicability,
            sources,
            "operation protocol-profile applicability drift",
        )

        require(
            len(expected["goldenInvocations"]) == len(sources["operations"]),
            "golden invocation count differs from operation count",
        )
        require(
            len(expected["cases"]) == len(sources["caseCatalog"]["cases"]),
            "compiled case count differs from source case count",
        )
        require(len(checked_in["inputs"]) == 9, "plan must bind exactly nine machine authorities")

        if args.evidence is not None:
            step_count = sum(len(case["steps"]) for case in checked_in["cases"])
            evidence = {
                "profile": "bytedesk.conformance-plan-validation-evidence/1",
                "version": 1,
                "authorityIssued": False,
                "result": "pass",
                "inputs": deepcopy(checked_in["inputs"]),
                "plan": {
                    "path": "contracts/ports/v1/conformance-plan.json",
                    "profile": checked_in["profile"],
                    "digest": canonical_digest(checked_in),
                },
                "counts": {
                    "inputAuthorities": len(checked_in["inputs"]),
                    "operationGoldens": len(checked_in["goldenInvocations"]),
                    "sourceCases": len(checked_in["cases"]),
                    "compiledSteps": step_count,
                    "validContractFixtures": valid_fixture_count,
                    "denialMutations": denial_mutation_count,
                    "adversarialDenials": len(adversarial_denial_ids),
                },
                "checks": [
                    "plan-schema-valid",
                    "nine-input-digests-exact",
                    "generated-plan-byte-exact",
                    "operation-golden-coverage-complete",
                    "case-step-coverage-complete",
                    "contract-valid-fixtures-accepted",
                    "contract-denial-mutations-rejected",
                    "closed-oracles-match-operations",
                    "protocol-fixtures-and-mutations-bound",
                    "port-protocol-profile-applicability-exact",
                    "structural-samples-not-semantic-goldens",
                ],
                "adversarialDenials": [
                    {"denialId": denial_id, "observed": "rejected"}
                    for denial_id in adversarial_denial_ids
                ],
            }
            write_json(args.evidence, evidence)
    except (ConformancePlanError, ContractToolError, OSError, ValueError) as error:
        print(f"conformance-plan validation failed: {error}", file=sys.stderr)
        return 1

    step_count = sum(len(case["steps"]) for case in expected["cases"])
    print(
        "conformance plan verified: "
        f"{len(expected['goldenInvocations'])} operation goldens, "
        f"{len(expected['cases'])} compiled cases, {step_count} deterministic steps, "
        "all contract fixtures and adversarial probes passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
