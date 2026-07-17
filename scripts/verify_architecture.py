#!/usr/bin/env python3
"""Validate and deterministically export the accepted ADR and C4/Mermaid subset."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import re
import sys
from pathlib import Path
from typing import Iterable

from contracts.contractlib import (
    REPOSITORY_ROOT,
    ContractToolError,
    sha256_bytes,
    write_bytes,
    write_json,
)


ADR_ROOT = REPOSITORY_ROOT / "docs" / "architecture" / "adr"
C4_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "c4.md"
DECISION_REGISTER_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "decision-register.md"
ADR_NAME = re.compile(r"^(?P<number>[0-9]{4})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")
ADR_HEADING = re.compile(r"^# ADR-(?P<number>[0-9]{4}):\s+\S.*$", re.MULTILINE)
ACCEPTED_STATUS = re.compile(r"^(?:-\s*)?\*\*Status:\*\*\s+Accepted\s*$", re.MULTILINE)
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
NODE_ID = r"[A-Za-z][A-Za-z0-9_]*"
EDGE = re.compile(
    rf"^(?P<source>{NODE_ID})\s*(?P<arrow><-->|-->|---|-.->)"
    rf"(?:\|(?P<label>[^|]{{1,512}})\|)?\s*(?P<target>{NODE_ID})$"
)
NODE = re.compile(
    rf"^(?P<identifier>{NODE_ID})\s*"
    rf"(?P<shape>\[\([^\[\]()\r\n]{{1,512}}\)\]|\[[^\[\]\r\n]{{1,512}}\])$"
)
FLOW = re.compile(r"^flowchart\s+(LR|RL|TB|BT)$")
EXPECTED_DIAGRAM_HEADINGS = {
    "C1 — System context",
    "C2 — Agent Delivery containers",
    "C2 reference deployment",
    "C3 — Core components",
    "Dynamic view — end-to-end delivery flows",
}
EXPECTED_DYNAMIC_NODES = {
    "Authoring",
    "Publication",
    "Import",
    "PrivateCustomization",
    "Compilation",
    "Coordinator",
    "DesiredState",
    "Reconciliation",
    "Canary",
    "Activation",
    "EligibleHistory",
    "ForwardRecovery",
}
EXPECTED_DYNAMIC_EDGES = frozenset(
    {
        ("Authoring", "Publication", "-->", None),
        ("Publication", "Import", "-->", None),
        ("Import", "PrivateCustomization", "-->", None),
        ("PrivateCustomization", "Compilation", "-->", None),
        ("Compilation", "Coordinator", "-->", None),
        ("Coordinator", "DesiredState", "-->", "sole logical CAS writer"),
        ("DesiredState", "Reconciliation", "-->", None),
        ("Reconciliation", "Canary", "-->", None),
        ("Canary", "Coordinator", "-->", None),
        ("Coordinator", "Activation", "-->", None),
        ("EligibleHistory", "ForwardRecovery", "-->", None),
        ("ForwardRecovery", "Compilation", "-->", None),
    }
)


@dataclass(frozen=True)
class MermaidBlock:
    heading: str
    source: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    arrow: str
    label: str | None


@dataclass(frozen=True)
class Diagram:
    heading: str
    direction: str
    nodes: frozenset[str]
    edges: tuple[Edge, ...]
    source: str


def extract_mermaid_blocks(markdown: str) -> list[MermaidBlock]:
    blocks: list[MermaidBlock] = []
    current_heading: str | None = None
    active_heading: str | None = None
    active: list[str] | None = None
    for line in markdown.splitlines():
        heading = HEADING.match(line)
        if active is None and heading:
            current_heading = heading.group(2)
            continue
        if active is None and line.strip() == "```mermaid":
            if current_heading is None:
                raise ContractToolError("Mermaid block has no architecture heading")
            active_heading = current_heading
            active = []
            continue
        if active is not None and line.strip() == "```":
            blocks.append(MermaidBlock(active_heading or "", "\n".join(active) + "\n"))
            active_heading = None
            active = None
            continue
        if active is not None:
            active.append(line)
    if active is not None:
        raise ContractToolError("C4 document has an unclosed Mermaid block")
    return blocks


def parse_diagram(block: MermaidBlock) -> Diagram:
    statements = [line.strip() for line in block.source.splitlines() if line.strip()]
    if not statements or not FLOW.fullmatch(statements[0]):
        raise ContractToolError(f"{block.heading}: unsupported or missing flowchart direction")
    direction = statements[0].split()[1]
    nodes: set[str] = set()
    edges: list[Edge] = []
    edge_signatures: set[tuple[str, str, str, str | None]] = set()
    for statement in statements[1:]:
        if statement.startswith("%%"):
            continue
        edge_match = EDGE.fullmatch(statement)
        if edge_match:
            edge = Edge(
                source=edge_match.group("source"),
                target=edge_match.group("target"),
                arrow=edge_match.group("arrow"),
                label=edge_match.group("label"),
            )
            signature = (edge.source, edge.target, edge.arrow, edge.label)
            if signature in edge_signatures:
                raise ContractToolError(
                    f"{block.heading}: duplicate Mermaid relationship {statement!r}"
                )
            edge_signatures.add(signature)
            edges.append(edge)
            continue
        node_match = NODE.fullmatch(statement)
        if not node_match:
            raise ContractToolError(f"{block.heading}: unsupported Mermaid statement {statement!r}")
        identifier = node_match.group("identifier")
        if identifier in nodes:
            raise ContractToolError(f"{block.heading}: duplicate Mermaid node {identifier}")
        nodes.add(identifier)
    if not nodes or not edges:
        raise ContractToolError(f"{block.heading}: diagram must contain nodes and relationships")
    for edge in edges:
        for endpoint in (edge.source, edge.target):
            if endpoint not in nodes:
                raise ContractToolError(
                    f"{block.heading}: relationship references undeclared node {endpoint}"
                )
    return Diagram(block.heading, direction, frozenset(nodes), tuple(edges), block.source)


def incoming_sources(diagram: Diagram, target: str) -> set[str]:
    incoming: set[str] = set()
    for edge in diagram.edges:
        if edge.target == target:
            incoming.add(edge.source)
        if edge.arrow == "<-->" and edge.source == target:
            incoming.add(edge.target)
    return incoming


def validate_desired_state_authority(diagrams: Iterable[Diagram]) -> None:
    expected = {
        ("C1 — System context", "Desired"): {"Delivery"},
        ("C2 — Agent Delivery containers", "DesiredPort"): {"Core"},
        ("C3 — Core components", "Desired"): {"Promotion"},
        ("Dynamic view — end-to-end delivery flows", "DesiredState"): {"Coordinator"},
    }
    by_heading = {diagram.heading: diagram for diagram in diagrams}
    for (heading, target), allowed in expected.items():
        diagram = by_heading.get(heading)
        if diagram is None or target not in diagram.nodes:
            raise ContractToolError(f"missing desired-state authority node {heading}/{target}")
        observed = incoming_sources(diagram, target)
        if observed != allowed:
            raise ContractToolError(
                f"{heading}: desired-state writers {sorted(observed)} != {sorted(allowed)}"
            )


def validate_dynamic_flow(diagram: Diagram) -> None:
    """Freeze the exact accepted end-to-end order, including forward recovery."""

    if diagram.heading != "Dynamic view — end-to-end delivery flows":
        raise ContractToolError("end-to-end validation received the wrong diagram")
    if diagram.nodes != EXPECTED_DYNAMIC_NODES:
        raise ContractToolError(
            "end-to-end flow node coverage differs "
            f"missing={sorted(EXPECTED_DYNAMIC_NODES - set(diagram.nodes))} "
            f"extra={sorted(set(diagram.nodes) - EXPECTED_DYNAMIC_NODES)}"
        )
    observed = frozenset(
        (edge.source, edge.target, edge.arrow, edge.label) for edge in diagram.edges
    )
    if observed != EXPECTED_DYNAMIC_EDGES:
        missing = sorted(
            EXPECTED_DYNAMIC_EDGES - observed,
            key=lambda item: (item[0], item[1], item[2], item[3] or ""),
        )
        extra = sorted(
            observed - EXPECTED_DYNAMIC_EDGES,
            key=lambda item: (item[0], item[1], item[2], item[3] or ""),
        )
        raise ContractToolError(
            f"end-to-end flow relationships differ missing={missing} extra={extra}"
        )


def validate_diagram_coverage(diagrams: list[Diagram]) -> None:
    headings = [diagram.heading for diagram in diagrams]
    if len(headings) != len(set(headings)):
        duplicates = sorted(
            heading for heading in set(headings) if headings.count(heading) > 1
        )
        raise ContractToolError(f"duplicate C4 diagram headings: {duplicates}")
    observed = set(headings)
    if observed != EXPECTED_DIAGRAM_HEADINGS:
        raise ContractToolError(
            "C4 diagram coverage differs "
            f"missing={sorted(EXPECTED_DIAGRAM_HEADINGS - observed)} "
            f"extra={sorted(observed - EXPECTED_DIAGRAM_HEADINGS)}"
        )


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        raise ContractToolError("architecture heading has no exportable slug")
    return normalized


def validate_adrs() -> list[dict[str, object]]:
    paths = sorted(ADR_ROOT.glob("*.md"))
    if not paths:
        raise ContractToolError("architecture has no ADRs")
    evidence: list[dict[str, object]] = []
    numbers: list[int] = []
    for path in paths:
        name = ADR_NAME.fullmatch(path.name)
        if not name:
            raise ContractToolError(f"ADR filename is not canonical: {path.name}")
        number = int(name.group("number"))
        payload = path.read_bytes()
        text = payload.decode("utf-8")
        heading = ADR_HEADING.search(text)
        if heading is None or int(heading.group("number")) != number:
            raise ContractToolError(f"ADR heading/filename mismatch: {path.name}")
        if ACCEPTED_STATUS.search(text) is None:
            raise ContractToolError(f"ADR is not explicitly Accepted: {path.name}")
        if number > 1 and "Depends on:" not in text:
            raise ContractToolError(f"ADR lacks an explicit dependency declaration: {path.name}")
        numbers.append(number)
        evidence.append(
            {
                "number": number,
                "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                "status": "Accepted",
                "digest": sha256_bytes(payload),
            }
        )
    if numbers != list(range(1, len(numbers) + 1)):
        raise ContractToolError(f"ADR numbers are not contiguous from 0001: {numbers}")
    register = DECISION_REGISTER_PATH.read_text(encoding="utf-8")
    decisions = re.findall(r"^##\s+([0-9]+)\.\s+", register, flags=re.MULTILINE)
    if decisions != [str(value) for value in range(1, 11)]:
        raise ContractToolError("architecture decision register must contain exact decisions 1..10")
    if "**Status:** Accepted" not in register:
        raise ContractToolError("architecture decision register is not Accepted")
    for item in evidence:
        if f"adr/{int(item['number']):04d}-" not in register:
            raise ContractToolError(f"decision register does not reference ADR-{item['number']:04d}")
    return evidence


def verify(output_dir: Path) -> dict[str, object]:
    c4_bytes = C4_PATH.read_bytes()
    blocks = extract_mermaid_blocks(c4_bytes.decode("utf-8"))
    diagrams = [parse_diagram(block) for block in blocks]
    validate_diagram_coverage(diagrams)
    dynamic = next(
        diagram
        for diagram in diagrams
        if diagram.heading == "Dynamic view — end-to-end delivery flows"
    )
    validate_dynamic_flow(dynamic)
    validate_desired_state_authority(diagrams)
    output_dir.mkdir(parents=True, exist_ok=True)
    diagram_evidence: list[dict[str, object]] = []
    for index, diagram in enumerate(diagrams, start=1):
        exported = output_dir / f"{index:02d}-{slug(diagram.heading)}.mmd"
        source_bytes = diagram.source.encode("utf-8")
        write_bytes(exported, source_bytes)
        diagram_evidence.append(
            {
                "heading": diagram.heading,
                "direction": diagram.direction,
                "nodeCount": len(diagram.nodes),
                "relationshipCount": len(diagram.edges),
                "sourceDigest": sha256_bytes(source_bytes),
                "export": exported.relative_to(REPOSITORY_ROOT).as_posix(),
            }
        )
    adrs = validate_adrs()
    return {
        "profile": "bytedesk.architecture-validation-evidence/1",
        "c4Document": {
            "path": C4_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            "digest": sha256_bytes(c4_bytes),
            "diagramCount": len(diagrams),
            "diagrams": diagram_evidence,
            "desiredStateWriterInvariant": "pass",
            "endToEndFlowCoverage": "exact-required-node-and-edge-set-pass",
            "forwardRecoveryPathInvariant": "eligible-history-to-current-compilation-pass",
        },
        "adrCount": len(adrs),
        "adrs": adrs,
        "decisionCount": 10,
        "outcome": "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "dist" / "architecture",
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = verify(args.output_dir.resolve())
    if args.evidence:
        write_json(args.evidence.resolve(), result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError, UnicodeError) as error:
        print(f"architecture verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
