"""Hermes harness renderer: deterministic Agent Spec -> native Hermes profile.

AD-05 required-work item 1: "Implement a Hermes adapter behind the shared
renderer interface." The target shape (profile directory containing
SOUL.md/config.yaml/.env.template/distribution.yaml, built from
`{{TOKEN}}`-templated files) is real: it mirrors
ops/hermes-native/render-profiles.py and ops/hermes-native/templates/ in
ByteDesk's own bytedesk-platform repository, locked as compatibility
evidence, not copied wholesale.

Two things that repository's real renderer does are deliberately NOT
reproduced here, per required-work item 3 ("Keep MCP servers, workload
credentials, consumer grants, engine IDs, organizational identities, tenant
bindings... out of reusable public render output"):

- `bytedesk_mcp_config`: injects a workload identity's MCP transport
  (endpoint, client certificate/key paths, OAuth) into config.yaml. That is
  consumer workload credential material - it belongs only to a private
  deployment compilation step in a consumer-owned repository, never to this
  core/public renderer.
- `org_section`: appends a department/manager/reports organizational chart
  into SOUL.md from a signed Office org snapshot. That is ByteDesk
  organizational identity - explicitly forbidden in public render output,
  and per required-work item 5 ("without... making ByteDesk's
  office-orchestrator a core fixture") the orchestrator/default-assignee
  profile names are caller-supplied parameters here, never hardcoded.

# ponytail: this module implements the pure transform (source + generic
# renderer input parameters -> output tree -> archive/tree digests) plus a
# compatibility classifier that rejects (not silently drops) unsupported
# input shapes. It does not yet assemble a full bytedesk.render-manifest/1
# instance, matching the same documented gap in renderer/native/transform.py
# and for the same reason: that needs a real renderer registry this pass
# doesn't build. Sandbox execution and qualification are likewise out of
# scope here, per docs/planning/infra-defaults.md.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
from dataclasses import dataclass, field
from typing import Any

import rfc8785

OUTPUT_TREE_PROFILE = "bytedesk.renderer-output-tree/1"

_ONBOARDING_BLOCK = """onboarding:
  profile_build: "off"
  seen:
    busy_input_prompt: true
    tool_progress_prompt: true
    openclaw_residue_cleanup: true
    profile_build_offered: true"""

_TERMINAL_BLOCK = """terminal:
  backend: local
  cwd: {workspace}
  home_mode: profile
  timeout: 180"""

_CONFIG_TEMPLATE = """model:
  provider: {model_provider}
  default: {model_default}
fallback_providers: []
toolsets: {toolsets}
agent:
  reasoning_effort: {reasoning_effort}
approvals:
  mode: "off"
  cron_mode: approve
{onboarding}
{terminal}
kanban:
  dispatch_in_gateway: {dispatch_in_gateway}
  dispatch_interval_seconds: 10
  failure_limit: 2
  orchestrator_profile: {orchestrator_profile}
  default_assignee: {default_assignee}
  max_spawn: {kanban_max_spawn}
  max_in_progress_per_profile: {kanban_max_in_progress_per_profile}
  auto_decompose: {auto_decompose}
  auto_decompose_per_tick: 1
  dispatch_stale_timeout_seconds: 900
gateway:
  api_server:
    max_concurrent_runs: {api_max_concurrent_runs_per_profile}
delegation:
  max_concurrent_children: {delegation_max_concurrent_children}
  max_spawn_depth: {delegation_max_spawn_depth}
  orchestrator_enabled: {delegation_orchestrator_enabled}
plugins:
  enabled: []
"""

_ENV_TEMPLATE = """API_SERVER_ENABLED=true
API_SERVER_HOST={api_host}
API_SERVER_PORT={api_port}
API_SERVER_KEY=
API_SERVER_MODEL_NAME={profile_name}
HERMES_KANBAN_DB={kanban_db}
HERMES_KANBAN_BOARD=default
"""

_DISTRIBUTION_TEMPLATE = """name: {profile_name}
version: 1.0.0
description: {description}
hermes_requires: {hermes_requires}
author: {author}
license: {license}
env_requires:
  - name: API_SERVER_KEY
    description: Unique loopback API bearer key provisioned outside the distribution.
    required: true
  - name: HERMES_KANBAN_DB
    description: Absolute path of the engine shared Kanban database.
    required: true
distribution_owned:
  - SOUL.md
  - config.yaml
  - distribution.yaml
"""


class UnsupportedSemanticsError(ValueError):
    """Raised when the source uses a semantic this renderer cannot represent.

    AD-05 acceptance criterion: "Reject unsupported semantics instead of
    dropping them."
    """


@dataclass(frozen=True)
class RendererInputParameters:
    """Generic, consumer-neutral Hermes harness configuration.

    Every field here is an operational knob (workspace path, capacity
    limits, model defaults), never a workload credential, tenant identity,
    or ByteDesk-specific fixture. `orchestrator_profile` and
    `default_assignee` are caller-supplied precisely so this renderer never
    hardcodes ByteDesk's `office-orchestrator`/`chief-of-staff` roster.
    """

    workspace: str
    api_host: str
    api_port: int
    kanban_db: str
    dispatch_in_gateway: bool = False
    auto_decompose: bool = False
    kanban_tools: bool = False
    reasoning_effort: str = "medium"
    model_provider: str = "openai-codex"
    model_default: str = "gpt-5.5"
    orchestrator_profile: str = "orchestrator"
    default_assignee: str = "orchestrator"
    kanban_max_spawn: int = 1
    kanban_max_in_progress_per_profile: int = 1
    api_max_concurrent_runs_per_profile: int = 1
    delegation_max_concurrent_children: int = 1
    delegation_max_spawn_depth: int = 1
    delegation_orchestrator_enabled: bool = False
    hermes_requires: str = "==0.18.2"
    author: str = "Agent Delivery"
    license: str = "Proprietary"


@dataclass(frozen=True)
class CompatibilityOutcome:
    outcome: str  # "exact" | "compatible_with_warnings" | "unsupported"
    notes: tuple[str, ...] = field(default_factory=tuple)


def classify_compatibility(agent_spec_document: dict[str, Any]) -> CompatibilityOutcome:
    """Classify whether Hermes can represent this source, per AD-05's
    compatibility outcomes (exact / compatible_with_warnings / lossy /
    unsupported - lossy is not reachable here since anything Hermes cannot
    represent at all is rejected as unsupported, not silently approximated).
    """

    if agent_spec_document.get("component_type") != "Agent":
        return CompatibilityOutcome(
            "unsupported",
            (f"component_type {agent_spec_document.get('component_type')!r} is not a resolved Agent",),
        )
    if agent_spec_document.get("tools") or agent_spec_document.get("toolboxes"):
        return CompatibilityOutcome(
            "unsupported",
            ("tools/toolboxes require private deployment compilation, not the public Hermes renderer",),
        )

    notes: list[str] = []
    if agent_spec_document.get("human_in_the_loop") is True:
        notes.append(
            "human_in_the_loop=true has no Hermes config representation - "
            "every profile runs with approvals.mode 'off' (unattended, cron-approved)"
        )
    if agent_spec_document.get("transforms"):
        notes.append("transforms are not represented in Hermes config output")

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
class HermesRenderResult:
    files: tuple[OutputFile, ...]
    archive_bytes: bytes
    tree_digest: str
    archive_digest: str
    expanded_size: int
    compatibility: CompatibilityOutcome

    @property
    def file_count(self) -> int:
        return len(self.files)


def render_hermes(
    agent_spec_document: dict[str, Any], params: RendererInputParameters
) -> HermesRenderResult:
    compatibility = classify_compatibility(agent_spec_document)
    if compatibility.outcome == "unsupported":
        raise UnsupportedSemanticsError("; ".join(compatibility.notes))

    profile_name = agent_spec_document["name"]
    soul_bytes = (agent_spec_document.get("system_prompt") or "").encode("utf-8")
    if not soul_bytes.endswith(b"\n"):
        soul_bytes += b"\n"

    toolsets = ["hermes-cli", "kanban"] if params.kanban_tools else ["hermes-cli"]
    config_text = _CONFIG_TEMPLATE.format(
        model_provider=_yaml_scalar(params.model_provider),
        model_default=_yaml_scalar(params.model_default),
        toolsets=_yaml_list(toolsets),
        reasoning_effort=_yaml_scalar(params.reasoning_effort),
        onboarding=_ONBOARDING_BLOCK,
        terminal=_TERMINAL_BLOCK.format(workspace=_yaml_scalar(params.workspace)),
        dispatch_in_gateway=_yaml_bool(params.dispatch_in_gateway),
        orchestrator_profile=_yaml_scalar(params.orchestrator_profile),
        default_assignee=_yaml_scalar(params.default_assignee),
        kanban_max_spawn=params.kanban_max_spawn,
        kanban_max_in_progress_per_profile=params.kanban_max_in_progress_per_profile,
        auto_decompose=_yaml_bool(params.auto_decompose),
        api_max_concurrent_runs_per_profile=params.api_max_concurrent_runs_per_profile,
        delegation_max_concurrent_children=params.delegation_max_concurrent_children,
        delegation_max_spawn_depth=params.delegation_max_spawn_depth,
        delegation_orchestrator_enabled=_yaml_bool(params.delegation_orchestrator_enabled),
    )
    env_text = _ENV_TEMPLATE.format(
        api_host=params.api_host,
        api_port=params.api_port,
        profile_name=profile_name,
        kanban_db=params.kanban_db,
    )
    distribution_text = _DISTRIBUTION_TEMPLATE.format(
        profile_name=_yaml_scalar(profile_name),
        description=_yaml_scalar(agent_spec_document.get("description") or ""),
        hermes_requires=_yaml_scalar(params.hermes_requires),
        author=_yaml_scalar(params.author),
        license=_yaml_scalar(params.license),
    )

    payloads = {
        "SOUL.md": soul_bytes,
        "config.yaml": config_text.encode("utf-8"),
        ".env.template": env_text.encode("utf-8"),
        "distribution.yaml": distribution_text.encode("utf-8"),
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

    return HermesRenderResult(
        files=files,
        archive_bytes=archive_bytes,
        tree_digest=tree_digest,
        archive_digest=raw_digest(archive_bytes),
        expanded_size=sum(f.size for f in files),
        compatibility=compatibility,
    )


def _yaml_scalar(value: str) -> str:
    import json

    return json.dumps(value)


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_list(values: list[str]) -> str:
    import json

    return json.dumps(values, separators=(",", ":"))


def _deterministic_archive(files: tuple[OutputFile, ...], payloads: dict[str, bytes]) -> bytes:
    """Deterministic USTAR archive: fixed mtime/uid/gid, NFC-path order.

    Same normalization convention as renderer/native/transform.py and
    generate_renderer_digest_fixtures.py:deterministic_render_archive.
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
