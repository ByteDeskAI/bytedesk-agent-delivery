# AD-15: Deliver the `bd-agent` marketplace and deployment CLI

- Historical Jira: [BDP-3316](https://bytedesk.atlassian.net/browse/BDP-3316)
- Delivery role: Core product client
- Release gate: Required for the supported headless operator/developer workflow

## Outcome

Provide a scriptable, third-party-friendly `bd-agent` CLI for catalog discovery, package validation and rendering, OCI verification, installation/import, desired-state pin management, deployment status, and receipt inspection without requiring ByteDesk Platform.

## Inputs

- Marketplace validation, renderer, and OCI command/library surfaces.
- Agent Delivery catalog, installation, reconciliation, and deployment APIs plus OpenAPI.
- Trust-policy and transport-neutral authentication contracts.
- Optional consumer adapter profiles; consumer-specific commands must not leak into the public-only workflow.

## Required work

1. Define stable commands for `catalog list/show`, `package validate`, `render`, `artifact inspect/verify`, `install preview/apply`, `binding show`, `update preview/apply`, `deployment status`, and `receipt verify`.
2. Support human-readable output and versioned JSON suitable for automation.
3. Reuse generated API clients/contracts where practical; do not duplicate trust, policy, compatibility, or authorization-decision logic client-side.
4. Authenticate through supported Agent Delivery and configured consumer user/workload profiles without storing credentials in repository files, shell history, logs, or agent state.
5. Require explicit confirmation or non-interactive acknowledgement flags for mutating commands. Preview displays exact digests, installation, consumer subject, and target.
6. Return stable exit codes for validation, compatibility, trust, authorization decision, conflict, unavailable dependency, and rollout failure.
7. Provide clean-install packaging, shell completion when low cost, examples, and contract tests.

## Outputs

- Versioned `bd-agent` CLI package and release workflow.
- Command, JSON, and exit-code specification.
- API, OCI, trust, and configurable consumer-auth integrations with tests.
- Third-party quickstart covering public local render plus an optional generic Agent Delivery installation.
- Separate reference examples for ByteDesk, Hermes, and OpenClaw where available.

## Acceptance criteria

- A clean environment can discover, validate, render, package, and verify a public agent without Agent Delivery service or ByteDesk Platform access where the operation is local/public.
- Mutations always show and accept exact digests, installation, subject, and target; no hidden identity, role, grant, MCP, provider, or credential creation occurs.
- JSON output is deterministic and backward-compatible within the declared CLI major version.
- Secrets and tokens are neither printed nor persisted by default.
- CLI receipt verification independently confirms the stored artifact chain and trust-policy inputs.
- Consumer integration is configured through an adapter/profile, not hardcoded to ByteDesk Platform.

## Verification

Run unit/snapshot tests, clean-install smoke, public-only workflow, authenticated non-production Agent Delivery workflow, configurable consumer-adapter fixture, negative trust/auth/conflict tests, offline receipt verification, and secret-output audit.

## Not in scope

Graphical marketplace UI, consumer identity/grant administration, or a production rollout.

## Dependencies

Blocked by AD-07, AD-10, and AD-13. Deployment commands integrate with AD-14 when available.

## Architecture review amendments

- Long-running render, evaluate, publish, import, and deploy commands consume the core asynchronous operation status, progress, cancellation, correlation, and terminal-evidence contract instead of holding a synchronous request. A consumer adapter may project it into its own job model.
- The CLI can verify a signed catalog, explicit cross-repository digest edges, purpose-specific trust policy, withdrawal/revocation state, and stored receipt chain offline when inputs are available.
- Public-only commands remain usable without ByteDesk credentials. A host reconciler identity is never replaced by, derived from, or reused as a human CLI credential.
