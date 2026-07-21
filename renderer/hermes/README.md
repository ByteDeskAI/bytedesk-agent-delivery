# Hermes harness renderer (AD-05, partial)

Implements a generic, consumer-neutral Hermes Adapter: a validated Agent
Spec `Agent` document plus generic `RendererInputParameters` (workspace,
API host/port, kanban DB path, capacity knobs) → the four-file native Hermes
profile distribution (`SOUL.md`, `config.yaml`, `.env.template`,
`distribution.yaml`), packaged in a deterministic USTAR archive.

The target shape and token-templated config files are real: they mirror
`ops/hermes-native/render-profiles.py` and `ops/hermes-native/templates/`
in ByteDesk's own `bytedesk-platform` repository, locked as compatibility
evidence in `provenance/external-input-lock.json` (see
`build_external_input_lock.py`) — not copied wholesale, and never treated
as core authority.

## What this renderer deliberately does not do

Per AD-05 required-work item 3 ("Keep MCP servers, workload credentials,
consumer grants, engine IDs, organizational identities, tenant bindings...
out of reusable public render output"), two things the real ByteDesk
renderer does are intentionally absent here:

- **No workload MCP wiring.** The real renderer's `bytedesk_mcp_config`
  injects a workload identity's MCP transport (endpoint, client
  certificate/key paths, OAuth) into `config.yaml`. That is consumer
  workload credential material — it belongs only to a private deployment
  compilation step in a consumer-owned repository, never to this core/public
  renderer. `plugins.enabled` always renders `[]` here.
- **No organizational chart injection.** The real renderer's `org_section`
  appends a department/manager/reports chart into `SOUL.md` from a signed
  Office org snapshot. That is ByteDesk organizational identity, explicitly
  forbidden in public render output. `orchestrator_profile` and
  `default_assignee` are caller-supplied parameters here specifically so
  ByteDesk's `office-orchestrator`/`chief-of-staff` roster is never a core
  fixture (required-work item 5).

`office-signing-key.json`, `workload-credential.py`, and `deployment.json`
in the locked source tree are real ByteDesk trust-anchor/organizational/
workload files — none of their bytes are read by this renderer or its
external-input-lock builder; only the pure rendering logic
(`render-profiles.py`) and its token-templated config files are locked.

## Status

This is a slice of AD-05, not the complete task:

- [x] Pure transform: source + generic renderer parameters → output tree →
      archive/tree digests, deterministic.
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
