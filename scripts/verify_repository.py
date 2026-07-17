#!/usr/bin/env python3
"""Verify repository-wide documentation, JSON, and planning invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
import rfc8785


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".venv", "dist", "build", "node_modules", "__pycache__"}
SHA256_TOKEN = re.compile(r"sha256:([^\s`\"'<>\]\[(){},;]+)")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


class VerificationError(RuntimeError):
    pass


def strict_json(payload: str, description: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"duplicate JSON member {key!r} in {description}")
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise VerificationError(f"non-finite JSON number {value} in {description}")

    try:
        return json.loads(payload, object_pairs_hook=object_pairs, parse_constant=constant)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise VerificationError(f"invalid JSON in {description}: {error}") from error


def repository_files(suffix: str) -> list[Path]:
    return sorted(
        path
        for path in REPOSITORY_ROOT.rglob(f"*{suffix}")
        if not any(part in IGNORED_PARTS for part in path.relative_to(REPOSITORY_ROOT).parts)
    )


def github_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        heading = re.sub(r"<[^>]+>", "", match.group(1)).strip().lower()
        heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
        heading = re.sub(r"\s+", "-", heading)
        count = counts.get(heading, 0)
        counts[heading] = count + 1
        anchors.add(heading if count == 0 else f"{heading}-{count}")
    return anchors


def link_target(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1 : raw.index(">")]
    # Local repository links do not use unescaped spaces. Anything after one is
    # a Markdown title and is excluded from the target.
    return raw.split(maxsplit=1)[0]


def contract_schema_registry() -> tuple[Registry, dict[str, Any]]:
    resources: list[tuple[str, Resource[Any]]] = []
    schemas: dict[str, Any] = {}
    for path in sorted((REPOSITORY_ROOT / "contracts" / "schemas" / "v1").glob("*.schema.json")):
        schema = strict_json(path.read_text(encoding="utf-8"), path.relative_to(REPOSITORY_ROOT).as_posix())
        schema_id = schema.get("$id") if isinstance(schema, dict) else None
        if not isinstance(schema_id, str):
            raise VerificationError(f"schema lacks $id: {path.relative_to(REPOSITORY_ROOT)}")
        schemas[schema_id] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources), schemas


def verify_contract_example(
    instance: Any,
    description: str,
    registry: Registry,
    schemas: dict[str, Any],
) -> bool:
    if not isinstance(instance, dict) or instance.get("contract") != "bytedesk.agent-binding/1":
        return False
    schema_id = "https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0"
    expected_digest = "sha256:" + hashlib.sha256(rfc8785.dumps(schemas[schema_id])).hexdigest()
    if instance.get("schema") != {"id": schema_id, "digest": expected_digest}:
        raise VerificationError(
            f"AgentBinding example in {description} does not pin the live schema ID and digest"
        )
    errors = sorted(
        Draft202012Validator(
            schemas[schema_id],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(instance),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise VerificationError(
            f"schema-invalid AgentBinding example in {description} at {location}: {errors[0].message}"
        )
    return True


def workflow_action_references(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "uses":
                if not isinstance(child, str) or not child:
                    raise VerificationError("workflow action reference must be a non-empty string")
                references.append(child)
            references.extend(workflow_action_references(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(workflow_action_references(child))
    return references


def verify_markdown() -> tuple[int, int, int, int, int, int]:
    markdown_files = repository_files(".md")
    links = 0
    fence_markers = 0
    structured: list[tuple[str, str, str]] = []
    anchor_cache: dict[Path, set[str]] = {}
    validated_contract_examples = 0

    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        active_marker: str | None = None
        active_language = ""
        block: list[str] = []
        prose: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = FENCE.match(line)
            if match:
                marker, info = match.groups()
                if active_marker is None:
                    active_marker = marker
                    active_language = info.strip().split(maxsplit=1)[0].lower() if info.strip() else ""
                    block = []
                elif marker[0] == active_marker[0] and len(marker) >= len(active_marker):
                    if active_language in {"json", "yaml", "yml"}:
                        structured.append((path.relative_to(REPOSITORY_ROOT).as_posix(), active_language, "\n".join(block) + "\n"))
                    active_marker = None
                    active_language = ""
                    block = []
                else:
                    block.append(line)
                fence_markers += 1
                continue
            if active_marker is None:
                prose.append(line)
            else:
                block.append(line)
        if active_marker is not None:
            raise VerificationError(f"unclosed Markdown fence in {path.relative_to(REPOSITORY_ROOT)}")

        prose_text = "\n".join(prose)
        for match in MARKDOWN_LINK.finditer(prose_text):
            target = urllib.parse.unquote(link_target(match.group(1)))
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            links += 1
            path_text, separator, fragment = target.partition("#")
            target_path = path if path_text == "" else (path.parent / path_text)
            try:
                resolved = target_path.resolve(strict=True)
                resolved.relative_to(REPOSITORY_ROOT.resolve())
            except (OSError, ValueError) as error:
                raise VerificationError(
                    f"unresolved or escaping local link in {path.relative_to(REPOSITORY_ROOT)}: {target}"
                ) from error
            if fragment and resolved.suffix.lower() == ".md":
                anchors = anchor_cache.setdefault(resolved, github_anchors(resolved.read_text(encoding="utf-8")))
                if fragment not in anchors:
                    raise VerificationError(
                        f"unresolved Markdown anchor in {path.relative_to(REPOSITORY_ROOT)}: {target}"
                    )

        for match in SHA256_TOKEN.finditer(prose_text):
            raw_token = match.group(1)
            if raw_token == "...":
                continue
            token = raw_token.rstrip(".")
            if not re.fullmatch(r"[0-9a-f]{64}", token):
                raise VerificationError(
                    f"invalid SHA-256 token in {path.relative_to(REPOSITORY_ROOT)}: sha256:{token}"
                )

    yaml_blocks = [item for item in structured if item[1] in {"yaml", "yml"}]
    yaml_paths = sorted(
        path
        for path in set(repository_files(".yaml") + repository_files(".yml"))
        if path.relative_to(REPOSITORY_ROOT).parts[:2] != ("contracts", "fixtures")
    )
    tool_path: Path | None = None
    registry, schemas = contract_schema_registry()
    action_reference_count = 0
    with tempfile.TemporaryDirectory(prefix="agent-delivery-doc-verify-") as temporary:
        if yaml_blocks or yaml_paths:
            tool_path = Path(temporary) / "contract-tool"
            run(["go", "build", "-o", str(tool_path), "./cmd/contract-tool"])
        for name, language, payload in structured:
            if language == "json":
                instance = strict_json(payload, f"structured fence in {name}")
            else:
                completed = subprocess.run(
                    [str(tool_path), "canonicalize", "--format=yaml", "-"],
                    cwd=REPOSITORY_ROOT,
                    input=payload,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if completed.returncode != 0:
                    raise VerificationError(
                        f"invalid restricted-YAML fence in {name}: {completed.stderr.strip()}"
                    )
                instance = strict_json(completed.stdout, f"canonical structured fence in {name}")
            if verify_contract_example(instance, name, registry, schemas):
                validated_contract_examples += 1
        for path in yaml_paths:
            completed = subprocess.run(
                [str(tool_path), "canonicalize", "--format=yaml", str(path)],
                cwd=REPOSITORY_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if completed.returncode != 0:
                raise VerificationError(
                    f"invalid restricted-YAML repository file in "
                    f"{path.relative_to(REPOSITORY_ROOT)}: {completed.stderr.strip()}"
                )
            document = strict_json(
                completed.stdout,
                f"canonical repository YAML in {path.relative_to(REPOSITORY_ROOT)}",
            )
            if path.relative_to(REPOSITORY_ROOT).parts[:2] == (".github", "workflows"):
                references = workflow_action_references(document)
                for reference in references:
                    if reference.startswith("./"):
                        continue
                    if reference.startswith("docker://"):
                        if not re.fullmatch(r"docker://[^@\s]+@sha256:[0-9a-f]{64}", reference):
                            raise VerificationError(
                                f"workflow container action is not digest-pinned in "
                                f"{path.relative_to(REPOSITORY_ROOT)}: {reference}"
                            )
                    elif not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference):
                        raise VerificationError(
                            f"workflow action is not commit-SHA-pinned in "
                            f"{path.relative_to(REPOSITORY_ROOT)}: {reference}"
                        )
                action_reference_count += len(references)
    return (
        len(markdown_files),
        links,
        len(structured),
        validated_contract_examples,
        len(yaml_paths),
        action_reference_count,
    )


def verify_json_files() -> tuple[int, int]:
    paths = repository_files(".json")
    parsed = 0
    denial_fixtures = 0
    for path in paths:
        relative_parts = path.relative_to(REPOSITORY_ROOT).parts
        if relative_parts[:3] == ("contracts", "fixtures", "encoding") and any(
            category in relative_parts for category in ("negative", "malicious")
        ):
            denial_fixtures += 1
            continue
        strict_json(path.read_text(encoding="utf-8"), path.relative_to(REPOSITORY_ROOT).as_posix())
        parsed += 1
    return parsed, denial_fixtures


def verify_plan() -> tuple[int, int, int]:
    path = REPOSITORY_ROOT / "docs/planning/development-plan.json"
    plan = strict_json(path.read_text(encoding="utf-8"), "docs/planning/development-plan.json")
    tracks = {item["id"] for item in plan["tracks"]}
    tasks = {item["id"]: item for item in plan["tasks"]}
    milestones = {item["id"]: item for item in plan["milestones"]}
    if len(tracks) != 3 or len(tasks) != 18 or len(milestones) != 7:
        raise VerificationError(
            f"planning cardinality drift: tracks={len(tracks)} tasks={len(tasks)} milestones={len(milestones)}"
        )
    nodes = {f"task:{value}" for value in tasks} | {f"milestone:{value}" for value in milestones}
    edges: dict[str, list[str]] = {node: [] for node in nodes}
    for kind, values in (("task", tasks), ("milestone", milestones)):
        for identifier, item in values.items():
            if item["track"] not in tracks:
                raise VerificationError(f"{kind} {identifier} references unknown track")
            node = f"{kind}:{identifier}"
            for dependency in item["dependsOnTasks"]:
                target = f"task:{dependency}"
                if target not in nodes:
                    raise VerificationError(f"{node} references unknown dependency {target}")
                edges[node].append(target)
            for dependency in item["dependsOnMilestones"]:
                target = f"milestone:{dependency}"
                if target not in nodes:
                    raise VerificationError(f"{node} references unknown dependency {target}")
                edges[node].append(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise VerificationError(f"planning dependency cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in edges[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(nodes):
        visit(node)
    return len(tracks), len(tasks), len(milestones)


def run(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise VerificationError(f"command failed ({' '.join(command)}):\n{completed.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    (
        markdown_count,
        link_count,
        structured_count,
        contract_example_count,
        yaml_count,
        action_reference_count,
    ) = verify_markdown()
    json_count, json_denial_count = verify_json_files()
    tracks, tasks, milestones = verify_plan()
    run(["git", "diff", "--check"])
    evidence = {
        "profile": "bytedesk.repository-verification-evidence/1",
        "markdownFiles": markdown_count,
        "localLinks": link_count,
        "structuredFences": structured_count,
        "validatedContractExamples": contract_example_count,
        "yamlFiles": yaml_count,
        "pinnedWorkflowActionReferences": action_reference_count,
        "jsonFiles": json_count,
        "intentionalJSONDenialFixtures": json_denial_count,
        "tracks": tracks,
        "tasks": tasks,
        "milestones": milestones,
        "gitDiffCheck": "pass",
        "outcome": "pass",
    }
    payload = json.dumps(evidence, separators=(",", ":"), ensure_ascii=False) + "\n"
    if args.evidence:
        output = args.evidence.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"repository verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
