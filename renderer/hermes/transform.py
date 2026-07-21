"""Hermes harness renderer: deterministic Agent Spec -> native Hermes profile.

AD-05 required-work item 1: "Implement a Hermes adapter behind the shared
renderer interface." Hermes Agent (NousResearch, hermes-agent.nousresearch.com)
is a real, independently documented open-source harness; every `config.yaml`
field this renderer emits is taken from its official public documentation,
not from any single deployment's private configuration - the same standard
applied to the OpenClaw adapter. Sources consulted:

- https://hermes-agent.nousresearch.com/docs/user-guide/configuration/
  (agent.reasoning_effort, agent.disabled_toolsets, model.provider/default,
  terminal.backend/cwd/timeout/home_mode)
- https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
  (kanban.dispatch_in_gateway, kanban.dispatch_interval_seconds,
  kanban.failure_limit, kanban.auto_decompose, kanban.auto_decompose_per_tick,
  kanban.orchestrator_profile, kanban.default_assignee,
  kanban.max_in_progress_per_profile, kanban.dispatch_stale_timeout_seconds)
- https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
  (delegation.max_concurrent_children, delegation.max_spawn_depth,
  delegation.orchestrator_enabled)
- https://hermes-agent.nousresearch.com/docs/user-guide/security and
  general documentation (approvals.mode: smart|manual|off,
  approvals.cron_mode: deny|approve)
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/api-server.md
  (API_SERVER_ENABLED/HOST/PORT/KEY/MODEL_NAME env vars - API server
  configuration is env-only; "config.yaml support coming in a future
  release" per that page, so these never appear in config.yaml here)

Fields with no confirmed public documentation - a `plugins` section, an
`onboarding` block, and `gateway.api_server.max_concurrent_runs` - are not
emitted. An earlier draft of this renderer copied those verbatim from
ByteDesk's own production `ops/hermes-native/templates/config.yaml` in
bytedesk-platform; that template is real and working, but it is one
deployment's compatibility evidence, not the generic harness contract, and
mixing the two would have made ByteDesk-specific customization look like
core Hermes semantics. The top-level `max_concurrent_sessions` field
replaces the unconfirmed `gateway.api_server.max_concurrent_runs`.

Per required-work item 3 ("Keep MCP servers, workload credentials, consumer
grants, engine IDs, organizational identities, tenant bindings... out of
reusable public render output"), this renderer also never emits an MCP
transport block or an organizational chart into SOUL.md - both are private-
deployment-compilation-only concerns in any case, independent of the schema
correction above.

# ponytail: this module implements the pure transform (source + generic
# renderer input parameters -> output tree -> archive/tree digests) plus a
# compatibility classifier that rejects (not silently drops) unsupported
# input shapes. It does not yet assemble a full bytedesk.render-manifest/1
# instance, matching the same documented gap in renderer/native/transform.py.
# Sandbox execution and qualification are likewise out of scope here, per
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

_CONFIG_TEMPLATE = """model:
  provider: {model_provider}
  default: {model_default}
agent:
  reasoning_effort: {reasoning_effort}
  disabled_toolsets: {disabled_toolsets}
terminal:
  backend: {terminal_backend}
  cwd: {workspace}
  home_mode: {terminal_home_mode}
  timeout: {terminal_timeout}
approvals:
  mode: {approvals_mode}
  cron_mode: {approvals_cron_mode}
max_concurrent_sessions: {max_concurrent_sessions}
kanban:
  dispatch_in_gateway: {dispatch_in_gateway}
  dispatch_interval_seconds: {kanban_dispatch_interval_seconds}
  failure_limit: {kanban_failure_limit}
  orchestrator_profile: {orchestrator_profile}
  default_assignee: {default_assignee}
  max_in_progress_per_profile: {kanban_max_in_progress_per_profile}
  auto_decompose: {auto_decompose}
  auto_decompose_per_tick: {kanban_auto_decompose_per_tick}
  dispatch_stale_timeout_seconds: {kanban_dispatch_stale_timeout_seconds}
delegation:
  max_concurrent_children: {delegation_max_concurrent_children}
  max_spawn_depth: {delegation_max_spawn_depth}
  orchestrator_enabled: {delegation_orchestrator_enabled}
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
    limits, model defaults) documented in Hermes Agent's own public
    reference, never a workload credential, tenant identity, or
    deployment-specific fixture. `orchestrator_profile` and
    `default_assignee` are caller-supplied precisely so this renderer never
    hardcodes any specific profile roster (AD-05 required-work item 5).
    """

    # No officially documented default exists for these - Hermes Agent's own
    # schema leaves model.provider/model.default blank until configured, and
    # a specific model/profile-roster/version binding is a real product
    # decision this renderer must not invent on the caller's behalf.
    workspace: str
    api_host: str
    api_port: int
    kanban_db: str
    model_provider: str
    model_default: str
    orchestrator_profile: str
    default_assignee: str
    hermes_requires: str
    # Every field below has a real, documented Hermes Agent default and is
    # safe to leave at that default for a generic public render.
    reasoning_effort: str = "medium"
    disabled_toolsets: tuple[str, ...] = ()
    terminal_backend: str = "local"
    terminal_home_mode: str = "auto"
    terminal_timeout: int = 180
    approvals_mode: str = "off"
    approvals_cron_mode: str = "approve"
    max_concurrent_sessions: int = 1
    dispatch_in_gateway: bool = True
    kanban_dispatch_interval_seconds: int = 60
    kanban_failure_limit: int = 2
    kanban_max_in_progress_per_profile: int = 1
    auto_decompose: bool = True
    kanban_auto_decompose_per_tick: int = 3
    kanban_dispatch_stale_timeout_seconds: int = 14400
    delegation_max_concurrent_children: int = 3
    delegation_max_spawn_depth: int = 1
    delegation_orchestrator_enabled: bool = True
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
            "human_in_the_loop=true has no direct Hermes config.yaml field - "
            "represented only through the caller-chosen approvals.mode/cron_mode"
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

    config_text = _CONFIG_TEMPLATE.format(
        model_provider=_yaml_scalar(params.model_provider),
        model_default=_yaml_scalar(params.model_default),
        reasoning_effort=_yaml_scalar(params.reasoning_effort),
        disabled_toolsets=_yaml_list(list(params.disabled_toolsets)),
        terminal_backend=_yaml_scalar(params.terminal_backend),
        workspace=_yaml_scalar(params.workspace),
        terminal_home_mode=_yaml_scalar(params.terminal_home_mode),
        terminal_timeout=params.terminal_timeout,
        approvals_mode=_yaml_scalar(params.approvals_mode),
        approvals_cron_mode=_yaml_scalar(params.approvals_cron_mode),
        max_concurrent_sessions=params.max_concurrent_sessions,
        dispatch_in_gateway=_yaml_bool(params.dispatch_in_gateway),
        kanban_dispatch_interval_seconds=params.kanban_dispatch_interval_seconds,
        kanban_failure_limit=params.kanban_failure_limit,
        orchestrator_profile=_yaml_scalar(params.orchestrator_profile),
        default_assignee=_yaml_scalar(params.default_assignee),
        kanban_max_in_progress_per_profile=params.kanban_max_in_progress_per_profile,
        auto_decompose=_yaml_bool(params.auto_decompose),
        kanban_auto_decompose_per_tick=params.kanban_auto_decompose_per_tick,
        kanban_dispatch_stale_timeout_seconds=params.kanban_dispatch_stale_timeout_seconds,
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
    return json.dumps(value)


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_list(values: list[str]) -> str:
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
