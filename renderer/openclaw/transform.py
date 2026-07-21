"""OpenClaw harness renderer: deterministic Agent Spec -> OpenClaw agent bundle.

AD-06 required-work item 1: "Implement an OpenClaw adapter behind the shared
renderer interface." OpenClaw (docs.openclaw.ai) is a real, independently
documented open-source harness. Every field this renderer emits is taken
from its official public documentation - there is no ByteDesk-specific
compatibility-evidence lock for this renderer, unlike AD-05's Hermes
adapter, because no current OpenClaw source data exists to lock: the only
local OpenClaw checkout (bytedesk-openclaw) is stale legacy code the task
owner explicitly disregarded, and ByteDesk has confirmed there is no
current OpenClaw deployment to treat as evidence - "we are just supporting
openclaw" as a generic third-party target harness, the same relationship
AD-04's native renderer has to the official Agent Spec SDK. AD-06 required-
work item 5 confirms this is a legitimate shape for the task: "AD-06 owns
only the generic renderer and generic conformance corpus" - ByteDesk-
specific compatibility evidence and migration mapping belong to AD-17,
which is blocked on that same missing data.

Sources consulted:

- https://docs.openclaw.ai/concepts/agent-workspace and
  https://docs.openclaw.ai/start/bootstrapping (SOUL.md = persona/values/
  tone/behavioral boundaries injected every session; AGENTS.md = the
  operating manual - behavior rules, uncertainty handling, approval
  requirements; IDENTITY.md = lightweight public card - name/id/role label/
  metadata for routing. TOOLS.md is seeded on first run but this renderer
  never populates it, per required-work item 3.)
- https://docs.openclaw.ai/gateway/config-agents (per-agent config block:
  id, name, workspace, model "provider/model-id" string, skills array,
  tools.profile/allow/deny, sandbox.mode/backend/scope/workspaceAccess,
  subagents.allowAgents/requireAgentId/maxConcurrent/maxChildrenPerAgent/
  maxSpawnDepth, identity.name)

Per required-work item 3 ("Do not populate TOOLS, MCP, resources, provider
access, identity, credentials, or private customization from marketplace
content"), the rendered agent config always has empty `skills`,
`tools.allow`, and `tools.deny`, and TOOLS.md is never written. Per
required-work item 2 ("isolate renderer-owned operational guidance from
canonical role content"), AGENTS.md is fixed, renderer-owned boilerplate -
never derived from or mixed with the source's persona content in SOUL.md.

# ponytail: pure transform only (source + generic renderer parameters ->
# output tree -> archive/tree digests), plus a compatibility classifier
# that rejects unsupported input. No bytedesk.render-manifest/1 instance
# assembly, sandbox execution, or qualification flow yet - same documented
# gap as renderer/native and renderer/hermes, per
# docs/planning/infra-defaults.md.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import dataclass, field
from typing import Any

import rfc8785

OUTPUT_TREE_PROFILE = "bytedesk.renderer-output-tree/1"

_AGENTS_MD_TEMPLATE = """# Agent operating manual

Read the assigned task, its dependencies, constraints, acceptance criteria,
and any existing evidence before acting. Use only approved capabilities and
make the smallest change or artifact that fully satisfies the task.

When uncertain about scope, authority, or whether an action requires
approval, stop and ask rather than guessing. Never fabricate actions,
identifiers, approvals, sources, or completion evidence. Report blockers
with the exact missing input, permission, or capability.
"""


class UnsupportedSemanticsError(ValueError):
    """Raised when the source uses a semantic this renderer cannot represent.

    AD-06 acceptance criterion: "Fail explicitly when canonical semantics
    cannot be represented."
    """


@dataclass(frozen=True)
class RendererInputParameters:
    """Generic, consumer-neutral OpenClaw harness configuration.

    Every field maps to a documented `agents.list[]` entry field. None of
    them are workload credentials, tenant identity, or a ByteDesk-specific
    fixture - `model` in particular has no documented default (OpenClaw
    requires an explicit "provider/model-id" string), so it is a required
    parameter here rather than an invented "safe default".
    """

    agent_id: str
    workspace: str
    model: str  # "provider/model-id", e.g. "anthropic/claude-opus-4-6"
    sandbox_mode: str = "all"  # off | non-main | all - "all" is the conservative default
    sandbox_backend: str = "docker"
    sandbox_scope: str = "agent"
    sandbox_workspace_access: str = "none"  # none | ro | rw
    max_concurrent_children: int = 8
    max_children_per_agent: int = 5
    max_spawn_depth: int = 1
    require_agent_id: bool = True


@dataclass(frozen=True)
class CompatibilityOutcome:
    outcome: str  # "exact" | "compatible_with_warnings" | "unsupported"
    notes: tuple[str, ...] = field(default_factory=tuple)


def classify_compatibility(agent_spec_document: dict[str, Any]) -> CompatibilityOutcome:
    """AD-06 compatibility outcomes: exact / compatible_with_warnings /
    unsupported. Anything OpenClaw cannot represent at all is rejected as
    unsupported (required-work item 7: "Fail explicitly when canonical
    semantics cannot be represented"), never silently dropped.
    """

    if agent_spec_document.get("component_type") != "Agent":
        return CompatibilityOutcome(
            "unsupported",
            (f"component_type {agent_spec_document.get('component_type')!r} is not a resolved Agent",),
        )
    if agent_spec_document.get("tools") or agent_spec_document.get("toolboxes"):
        return CompatibilityOutcome(
            "unsupported",
            ("tools/toolboxes require private deployment compilation, not the public OpenClaw renderer",),
        )

    notes: list[str] = []
    if agent_spec_document.get("human_in_the_loop") is False:
        notes.append(
            "human_in_the_loop=false has no direct OpenClaw config field - "
            "approval behavior is governed by AGENTS.md guidance and sandbox policy, not a single flag"
        )
    if agent_spec_document.get("transforms"):
        notes.append("transforms are not represented in OpenClaw output")

    return CompatibilityOutcome("compatible_with_warnings" if notes else "exact", tuple(notes))


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def raw_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class OutputFile:
    path: str
    digest: str
    size: int
    mode: str
    origin: str
    ownership_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "digest": self.digest,
            "size": self.size,
            "mode": self.mode,
            "origin": self.origin,
            "ownershipClass": self.ownership_class,
        }


@dataclass(frozen=True)
class OpenClawRenderResult:
    files: tuple[OutputFile, ...]
    archive_bytes: bytes
    tree_digest: str
    archive_digest: str
    expanded_size: int
    compatibility: CompatibilityOutcome

    @property
    def file_count(self) -> int:
        return len(self.files)


def render_openclaw(
    agent_spec_document: dict[str, Any], params: RendererInputParameters
) -> OpenClawRenderResult:
    compatibility = classify_compatibility(agent_spec_document)
    if compatibility.outcome == "unsupported":
        raise UnsupportedSemanticsError("; ".join(compatibility.notes))

    display_name = agent_spec_document["name"]
    soul_bytes = (agent_spec_document.get("system_prompt") or "").encode("utf-8")
    if not soul_bytes.endswith(b"\n"):
        soul_bytes += b"\n"

    identity = {
        "id": params.agent_id,
        "name": display_name,
        "role": agent_spec_document.get("description") or "",
    }
    identity_text = (
        "# Identity\n\n"
        f"- **id**: `{identity['id']}`\n"
        f"- **name**: {identity['name']}\n"
        f"- **role**: {identity['role']}\n"
    )

    agent_config = {
        "id": params.agent_id,
        "name": display_name,
        "workspace": params.workspace,
        "model": params.model,
        "skills": [],
        "tools": {"profile": None, "allow": [], "deny": []},
        "sandbox": {
            "mode": params.sandbox_mode,
            "backend": params.sandbox_backend,
            "scope": params.sandbox_scope,
            "workspaceAccess": params.sandbox_workspace_access,
        },
        "subagents": {
            "allowAgents": [],
            "requireAgentId": params.require_agent_id,
            "maxConcurrent": params.max_concurrent_children,
            "maxChildrenPerAgent": params.max_children_per_agent,
            "maxSpawnDepth": params.max_spawn_depth,
        },
        "identity": {"name": display_name},
    }
    agent_json_text = json.dumps(agent_config, indent=2, sort_keys=True) + "\n"

    payloads = {
        "SOUL.md": soul_bytes,
        "AGENTS.md": _AGENTS_MD_TEMPLATE.encode("utf-8"),
        "IDENTITY.md": identity_text.encode("utf-8"),
        "agent.json5": agent_json_text.encode("utf-8"),
    }

    files = tuple(
        OutputFile(
            path=path,
            digest=raw_digest(payload),
            size=len(payload),
            mode="0644",
            origin="source_payload" if path == "SOUL.md" else "renderer_template",
            ownership_class="runtime_read_only",
        )
        for path, payload in sorted(payloads.items())
    )

    tree_digest = canonical_digest(
        {"profile": OUTPUT_TREE_PROFILE, "files": [f.as_dict() for f in files]}
    )
    archive_bytes = _deterministic_archive(files, payloads)

    return OpenClawRenderResult(
        files=files,
        archive_bytes=archive_bytes,
        tree_digest=tree_digest,
        archive_digest=raw_digest(archive_bytes),
        expanded_size=sum(f.size for f in files),
        compatibility=compatibility,
    )


def _deterministic_archive(files: tuple[OutputFile, ...], payloads: dict[str, bytes]) -> bytes:
    """Deterministic USTAR archive: fixed mtime/uid/gid, NFC-path order.

    Same normalization convention as renderer/native and renderer/hermes.
    """

    ordered = sorted(files, key=lambda f: f.path.encode("utf-8"))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for file in ordered:
            payload = payloads[file.path]
            header = tarfile.TarInfo(file.path)
            header.size = len(payload)
            header.mode = int(file.mode, 8)
            header.mtime = 0
            header.uid = 0
            header.gid = 0
            header.uname = ""
            header.gname = ""
            archive.addfile(header, io.BytesIO(payload))
    return buffer.getvalue()
