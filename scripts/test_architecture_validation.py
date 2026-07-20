#!/usr/bin/env python3
"""Focused denial tests for the repository architecture validator."""

from __future__ import annotations

import json
import sys

from contracts.contractlib import ContractToolError
from verify_architecture import (
    MermaidBlock,
    parse_diagram,
    validate_diagram_coverage,
    validate_dynamic_flow,
    validate_desired_state_authority,
)


def expect_denial(case_id: str, operation: object) -> dict[str, str]:
    try:
        operation()  # type: ignore[operator]
    except ContractToolError:
        return {"id": case_id, "outcome": "denied"}
    raise ContractToolError(f"architecture denial case passed: {case_id}")


def main() -> int:
    valid = parse_diagram(
        MermaidBlock(
            "C1 — System context",
            "flowchart LR\n  Delivery[Delivery]\n  Desired[(Desired)]\n  Delivery --> Desired\n",
        )
    )
    cases = [{"id": "valid-subset", "outcome": "permitted"}]
    cases.append(
        expect_denial(
            "duplicate-architecture-heading",
            lambda: validate_diagram_coverage([valid, valid]),
        )
    )
    cases.append(
        expect_denial(
            "undeclared-edge-endpoint",
            lambda: parse_diagram(
                MermaidBlock(
                    "probe",
                    "flowchart LR\n  Known[Known]\n  Known --> Missing\n",
                )
            ),
        )
    )
    cases.append(
        expect_denial(
            "duplicate-node",
            lambda: parse_diagram(
                MermaidBlock(
                    "probe",
                    "flowchart LR\n  Same[One]\n  Same[Two]\n  Same --> Same\n",
                )
            ),
        )
    )
    cases.append(
        expect_denial(
            "unclosed-node-shape",
            lambda: parse_diagram(
                MermaidBlock(
                    "probe",
                    "flowchart LR\n  Broken[unclosed\n  Other[Other]\n  Broken --> Other\n",
                )
            ),
        )
    )
    cases.append(
        expect_denial(
            "duplicate-relationship",
            lambda: parse_diagram(
                MermaidBlock(
                    "probe",
                    "flowchart LR\n  One[One]\n  Two[Two]\n  One --> Two\n  One --> Two\n",
                )
            ),
        )
    )
    cases.append(
        expect_denial(
            "wrong-desired-state-writer",
            lambda: validate_desired_state_authority(
                [
                    parse_diagram(
                        MermaidBlock(
                            "C1 — System context",
                            "flowchart LR\n  Host[Host]\n  Delivery[Delivery]\n  Desired[(Desired)]\n  Host --> Desired\n",
                        )
                    ),
                    parse_diagram(
                        MermaidBlock(
                            "C2 — Agent Delivery containers",
                            "flowchart LR\n  Core[Core]\n  DesiredPort[(Desired)]\n  Core --> DesiredPort\n",
                        )
                    ),
                    parse_diagram(
                        MermaidBlock(
                            "C3 — Core components",
                            "flowchart LR\n  Promotion[Promotion]\n  Desired[(Desired)]\n  Promotion --> Desired\n",
                        )
                    ),
                    parse_diagram(
                        MermaidBlock(
                            "Dynamic view — end-to-end delivery flows",
                            "flowchart LR\n  Coordinator[Coordinator]\n  DesiredState[(Desired)]\n  Coordinator --> DesiredState\n",
                        )
                    ),
                ]
            ),
        )
    )
    dynamic_source = """flowchart LR
  Authoring[Authoring]
  Publication[Publication]
  Import[Import]
  PrivateCustomization[Private customization]
  Compilation[Compilation]
  Coordinator[Coordinator]
  DesiredState[(Desired state)]
  Reconciliation[Reconciliation]
  Canary[Canary]
  Activation[Activation]
  EligibleHistory[Eligible history]
  ForwardRecovery[Forward recovery]
  Authoring --> Publication
  Publication --> Import
  Import --> PrivateCustomization
  PrivateCustomization --> Compilation
  Compilation --> Coordinator
  Coordinator -->|sole logical CAS writer| DesiredState
  DesiredState --> Reconciliation
  Reconciliation --> Canary
  Canary --> Coordinator
  Coordinator --> Activation
  EligibleHistory --> ForwardRecovery
  ForwardRecovery --> Compilation
"""
    dynamic = parse_diagram(
        MermaidBlock("Dynamic view — end-to-end delivery flows", dynamic_source)
    )
    validate_dynamic_flow(dynamic)
    cases.append({"id": "exact-dynamic-flow", "outcome": "permitted"})
    cases.append(
        expect_denial(
            "dynamic-flow-missing-publication-import",
            lambda: validate_dynamic_flow(
                parse_diagram(
                    MermaidBlock(
                        "Dynamic view — end-to-end delivery flows",
                        dynamic_source.replace("  Publication --> Import\n", ""),
                    )
                )
            ),
        )
    )
    cases.append(
        expect_denial(
            "dynamic-flow-recovery-bypasses-compilation",
            lambda: validate_dynamic_flow(
                parse_diagram(
                    MermaidBlock(
                        "Dynamic view — end-to-end delivery flows",
                        dynamic_source.replace(
                            "  ForwardRecovery --> Compilation\n",
                            "  ForwardRecovery --> Coordinator\n",
                        ),
                    )
                )
            ),
        )
    )
    result = {
        "profile": "bytedesk.architecture-validator-conformance/1",
        "caseCount": len(cases),
        "cases": cases,
        "baselineNodeCount": len(valid.nodes),
        "outcome": "pass",
    }
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"architecture validator conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
