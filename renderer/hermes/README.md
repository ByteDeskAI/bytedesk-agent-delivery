# Hermes harness renderer (AD-05, partial)

Implements a generic, consumer-neutral Hermes Adapter: a validated Agent
Spec `Agent` document plus generic `RendererInputParameters` (workspace,
API host/port, kanban DB path, capacity knobs) → the four-file native Hermes
profile distribution (`SOUL.md`, `config.yaml`, `.env.template`,
`distribution.yaml`), packaged in a deterministic USTAR archive.

Every `config.yaml` field this renderer emits is taken from Hermes Agent's
own official public documentation (NousResearch,
[hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)),
not from any single deployment's private configuration — see the citations
at the top of `transform.py`. This is the same standard applied to the
OpenClaw adapter: the generic renderer targets the harness's own public
contract, not one consumer's compatibility evidence.

`provenance/external-input-lock.json` (built by
`build_external_input_lock.py`) separately locks ByteDesk's own
`ops/hermes-native/render-profiles.py` and `templates/` from
`bytedesk-platform` as **compatibility evidence only** — proof that a real
production deployment exercises this same target shape, not the schema
authority. An earlier draft of this renderer copied that template's field
set verbatim, including a `plugins` section, an `onboarding` block, and
`gateway.api_server.max_concurrent_runs` — none of which appear in Hermes
Agent's public documentation. Those were ByteDesk-specific additions (the
`onboarding` block matches the bytedesk-office plugin's first-touch
latches described in `ops/hermes-native/README.md`) that this renderer
must not present as core Hermes semantics. They were removed; the real
top-level `max_concurrent_sessions` field replaces the unconfirmed one.

## What this renderer deliberately does not do

Per AD-05 required-work item 3 ("Keep MCP servers, workload credentials,
consumer grants, engine IDs, organizational identities, tenant bindings...
out of reusable public render output"):

- **No workload MCP wiring.** ByteDesk's real renderer injects a workload
  identity's MCP transport (endpoint, client certificate/key paths, OAuth)
  into `config.yaml`. That is consumer workload credential material — it
  belongs only to a private deployment compilation step in a consumer-owned
  repository, never to this core/public renderer.
- **No organizational chart injection.** ByteDesk's real renderer appends a
  department/manager/reports chart into `SOUL.md` from a signed Office org
  snapshot. That is organizational identity, explicitly forbidden in public
  render output. `orchestrator_profile` and `default_assignee` are
  caller-required parameters here specifically so no specific profile
  roster is ever a core fixture (required-work item 5).

`office-signing-key.json`, `workload-credential.py`, and `deployment.json`
in the locked source tree are real ByteDesk trust-anchor/organizational/
workload files — none of their bytes are read by this renderer or its
external-input-lock builder; only the pure rendering logic
(`render-profiles.py`) and its token-templated config files are locked.

## Status

This is a slice of AD-05, not the complete task:

- [x] Pure transform: source + generic renderer parameters → output tree →
      archive/tree digests, deterministic, schema-grounded in Hermes
      Agent's own public documentation.
- [x] Compatibility classification that *rejects* (not silently drops)
      unsupported input: non-`Agent` component types, and `tools`/
      `toolboxes` (which require private deployment compilation).
- [x] Real `bytedesk.external-input-lock/1` compatibility-evidence artifact,
      schema-validated, covering exactly the renderer logic and templates —
      never the adjacent credential/org-data files.
- [ ] Full `bytedesk.render-manifest/1` instance assembly — same documented
      gap as `renderer/native`; needs a real renderer registry.
- [ ] Sandbox execution and qualification flow (ephemeral test keys only,
      per `docs/planning/infra-defaults.md`).

## Local validation

```sh
uv sync --frozen
make test
```

To regenerate the external-input-lock against a fresh checkout:

```sh
uv run python build_external_input_lock.py \
  --lock-repo-root /path/to/bytedesk-platform \
  --retrieved-at $(date -u +%Y-%m-%dT%H:%M:%SZ)
```
