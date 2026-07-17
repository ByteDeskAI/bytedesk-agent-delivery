# AD-06: Implement the deterministic OpenClaw agent renderer

- Historical Jira: [BDP-3305](https://bytedesk.atlassian.net/browse/BDP-3305)
- Delivery role: Core product harness adapter
- Release gate: Required for the OpenClaw reference consumer, not for consumers using another harness

## Outcome

Render canonical marketplace packages into the OpenClaw agent-directory contract without allowing OpenClaw files to become an independent source of truth.

## Inputs

- Landed renderer contract from AD-04.
- Current `bytedesk-openclaw/agents/*/{AGENTS.md,SOUL.md,TOOLS.md}` definitions and runtime expectations as compatibility evidence.
- Marketplace baseline catalog.

## Required work

1. Implement an OpenClaw adapter behind the shared renderer interface.
2. Map canonical instructions and persona into the minimal OpenClaw file set; isolate renderer-owned operational guidance from canonical role content.
3. Do not populate TOOLS, MCP, resources, provider access, identity, or credentials from marketplace content. Emit only neutral placeholders or omit files as the harness contract permits; consuming-platform authority remains external.
4. Emit deterministic file ordering/content and a render manifest.
5. Build a migration mapping from existing ByteDesk OpenClaw slugs to canonical marketplace IDs.
6. Add golden parity fixtures for representative agents and full-catalog compatibility tests.
7. Fail explicitly when canonical semantics cannot be represented.

## Outputs

- Versioned OpenClaw renderer.
- Deterministic render fixtures and migration map.
- Compatibility and intent-preservation report.
- Contract and golden tests.

## Acceptance criteria

- Every applicable baseline agent renders without secret or runtime coupling.
- Repeated clean renders are byte-identical.
- OpenClaw-specific files are generated outputs, not edited canonical inputs.
- No default tool, MCP, provider, identity, or resource access is inferred.
- Intent differences from legacy definitions are reviewed and documented.

## Verification

Run shared contract tests, full-catalog render, byte comparison, secret scan, archive-safety checks, and pinned OpenClaw static/runtime configuration validation where available.

## Not in scope

OpenClaw source cutover, runtime deployment, or consuming-platform authorization.

## Dependencies

Blocked by AD-03 and AD-04.

## Architecture review amendments

- Generated OpenClaw content is inert output from a compile-time allowlisted adapter; packages cannot supply renderer plugins or executable hooks.
- Any OpenClaw tool, MCP, provider, identity, credential, or approval configuration remains consuming-platform-owned and cannot flow back into canonical source.
- Unsupported semantics fail with stable diagnostics and never produce a silently weakened agent.
