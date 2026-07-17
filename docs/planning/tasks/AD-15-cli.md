# AD-15: Deliver the `bd-agent` marketplace and deployment CLI

- Historical Jira: [BDP-3316](https://bytedesk.atlassian.net/browse/BDP-3316)
- Delivery role: Core product client
- Release gate: Required for the supported headless operator/developer workflow

## Outcome

Provide a scriptable, third-party-friendly `bd-agent` CLI for contract-bundle
verification, source validation, exact renderer selection, local packaging,
OCI publication/pull/verification, control-plane commands, rollout observation,
forward recovery, and receipt inspection without ByteDesk Platform.

## Inputs

- Marketplace validation, renderer, and OCI command/library surfaces.
- Agent Delivery catalog, installation, reconciliation, and deployment APIs plus OpenAPI.
- Trust-policy and transport-neutral authentication contracts.
- Reference reconciler, canary evidence, and recovery/action resources from
  AD-14.
- Optional consumer adapter profiles; consumer-specific commands must not leak into the public-only workflow.

## Required work

1. Define stable commands for `contract verify`, `catalog list/show`,
   `package validate/build`, `render`, `artifact publish/pull/inspect/verify`,
   `install preview/apply`, `binding show`, `update preview/apply`,
   `deployment status/recover`, and `receipt verify`. Local package and
   publish commands are first-class, not implied by render.
2. Support human-readable output and versioned JSON suitable for automation. Machine JSON for authoritative/digest-bearing objects emits RFC 8785 JCS bytes; human presentation formatting is never used for digest or signature verification.
3. Reuse generated API clients/contracts where practical; do not duplicate trust, policy, compatibility, or authorization-decision logic client-side.
4. Authenticate through supported Agent Delivery and configured consumer user/workload profiles without storing credentials in repository files, shell history, logs, or agent state.
5. Require explicit confirmation or non-interactive acknowledgement flags for mutating commands. Preview displays exact digests, installation, consumer subject, and target.
6. Return stable exit codes for validation, compatibility, trust, authorization decision, conflict, unavailable dependency, and rollout failure.
7. Provide clean-install packaging, shell completion when low cost, examples, and contract tests.
8. Make previews distinguish the tenant-free public catalog render from the complete effective private render embedded in a deployment. Show exact source, customization, skill, renderer, effective-render, deployment, and target digests without displaying secret values.
9. Inspect arbitrary skill payload files as untrusted data without invoking scripts, binaries, hooks, installers, archive handlers outside the bounded validator, or dependency lifecycle commands.
10. Discover renderers by name/version for humans but resolve, preview, and
    record the complete renderer-release descriptor and compiled-allowlist
    match. Never fall back to PATH, tags, local binaries, or another version.
11. Use strong ETags, absent/match preconditions, idempotency keys, RFC 9457
    codes, cursor pagination, and durable action polling exactly as defined by
    the API. Display target rollout, technical evidence, capability evidence,
    and recoverySource as separate concepts.
12. Validate and preview strict functional/file/skill operations atomically,
    showing exact preconditions, conflicts, effective digests, and approval
    requirements without silently rewriting user input.

## Outputs

- Versioned `bd-agent` CLI package and release workflow.
- Command, JSON, and exit-code specification.
- API, OCI, trust, and configurable consumer-auth integrations with tests.
- Third-party quickstart covering public local render plus an optional generic Agent Delivery installation.
- Clean local package/build/publish/pull/verify quickstart using a generic
  fixture registry and no ByteDesk marketplace.
- Separate reference examples for ByteDesk, Hermes, and OpenClaw where available.

## Acceptance criteria

- A clean environment can discover, validate, render, package, and verify a public agent without Agent Delivery service or ByteDesk Platform access where the operation is local/public.
- Mutations always show and accept exact digests, installation, subject, and target; no hidden identity, role, grant, MCP, provider, or credential creation occurs.
- JSON output is deterministic and backward-compatible within the declared CLI major version; canonical-object output is byte-exact RFC 8785 JCS.
- Secrets and tokens are neither printed nor persisted by default.
- CLI receipt verification independently confirms the stored artifact chain and trust-policy inputs.
- Consumer integration is configured through an adapter/profile, not hardcoded to ByteDesk Platform.
- Public commands cannot accidentally emit tenant-specific artifacts, and private previews prove that functional customization caused a full effective re-render rather than a post-render patch.
- `package build` and `artifact publish` produce/return exact manifests,
  schema, renderer, product, trust, and content digests and never select a
  mutable tag as authority.
- CLI mutations cannot bypass the Promotion Coordinator, desired-state CAS,
  consumer authority freshness, or separate canary actors.

## Verification

Run unit/snapshot and generated-client drift, JCS golden, clean-install and
upgrade smoke, offline contract verification, local validate/render/package/
publish/pull/inspect/verify, authenticated action/ETag/idempotency/recovery
workflow, exact renderer selection/substitution denial, configurable consumer
Adapter, rollout/canary display, stable JSON/exit-code current/previous minor,
secret-output/redaction, and offline receipt verification tests.

## Not in scope

Graphical marketplace UI, consumer identity/grant administration, or a production rollout.

## Dependencies

Blocked by AD-04, AD-07, AD-10, AD-13, and AD-14.

## Architecture review amendments

- Long-running render, evaluate, publish, import, and deploy commands consume the core asynchronous operation status, progress, cancellation, correlation, and terminal-evidence contract instead of holding a synchronous request. A consumer adapter may project it into its own job model.
- The CLI can verify a signed catalog, explicit cross-repository digest edges, purpose-specific trust policy, withdrawal/revocation state, and stored receipt chain offline when inputs are available.
- Public-only commands remain usable without ByteDesk credentials. A host reconciler identity is never replaced by, derived from, or reused as a human CLI credential.
