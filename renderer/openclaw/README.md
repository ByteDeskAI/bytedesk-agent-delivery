# OpenClaw harness renderer (AD-06, partial)

Implements a generic, consumer-neutral OpenClaw Adapter: a validated Agent
Spec `Agent` document plus generic `RendererInputParameters` (agent id,
workspace, model, sandbox/subagent knobs) → the OpenClaw agent-directory
bundle (`SOUL.md`, `AGENTS.md`, `IDENTITY.md`, `agent.json5`), packaged in
a deterministic USTAR archive.

Every field is grounded in
[OpenClaw's own official public documentation](https://docs.openclaw.ai/)
(agent workspace/bootstrapping concepts, the `agents.list[]` config
schema) — see the citations at the top of `transform.py`. This is the same
standard used for `renderer/hermes` after its schema was corrected: the
generic renderer targets the harness's own public contract, never a single
deployment's private configuration.

## No external-input-lock

Unlike `renderer/hermes`, this renderer has **no**
`bytedesk.external-input-lock/1` compatibility-evidence artifact. AD-06's
task doc names `bytedesk-openclaw/agents/*/{AGENTS.md,SOUL.md,TOOLS.md}` as
a candidate compatibility-evidence source, but that local checkout is
stale legacy code (explicitly disregarded), and there is no current
OpenClaw deployment to lock as evidence instead. AD-06's own scope
statement covers this: "AD-06 owns only the generic renderer and generic
conformance corpus... AD-17 [ByteDesk OpenClaw cutover] owns the migration
map and full-catalog comparison" — and AD-17 remains blocked on that same
missing data. Building the generic renderer against OpenClaw's real public
docs, with no fabricated ByteDesk-specific evidence, is the correct scope
for this task in the absence of that data.

## What this renderer deliberately does not do

Per AD-06 required-work item 3 ("Do not populate TOOLS, MCP, resources,
provider access, identity, credentials, or private customization from
marketplace content"):

- `TOOLS.md` is never written (OpenClaw seeds it on first run, but this
  renderer omits it entirely rather than emit an empty/fake file).
- The rendered `agent.json5`'s `skills`, `tools.allow`, and `tools.deny`
  are always empty arrays; `tools.profile` is always `null`.
- `sandbox.workspaceAccess` defaults to `"none"` — the conservative,
  mandatory-control-preserving choice — and every sandbox field is
  caller-overridable but never silently weakened by this renderer.

Per required-work item 2 ("isolate renderer-owned operational guidance
from canonical role content"), `AGENTS.md` is fixed, renderer-owned
boilerplate — it never derives from or mixes with the source's persona
content in `SOUL.md` (`test_agents_md_is_fixed_renderer_boilerplate_not_derived_from_source`
proves this directly).

## Status

This is a slice of AD-06, not the complete task:

- [x] Pure transform: source + generic renderer parameters → output tree →
      archive/tree digests, deterministic, schema-grounded in OpenClaw's
      own public documentation.
- [x] Compatibility classification that *rejects* (not silently drops)
      unsupported input: non-`Agent` component types, and `tools`/
      `toolboxes` (which require private deployment compilation).
- [ ] Full `bytedesk.render-manifest/1` instance assembly — same
      documented gap as `renderer/native` and `renderer/hermes`; needs a
      real renderer registry.
- [ ] Sandbox execution and qualification/status-head flow (ephemeral test
      keys only, per `docs/planning/infra-defaults.md`).
- [ ] ByteDesk-specific compatibility evidence and migration mapping —
      blocked on real, current OpenClaw deployment data (AD-17).

## Local validation

```sh
uv sync --frozen
make test
```
