# AD-04: Implement the renderer contract and native Agent Spec output

- Historical Jira: [BDP-3307](https://bytedesk.atlassian.net/browse/BDP-3307)
- Delivery role: Core product
- Release gate: Blocks harness renderers and OCI render publication

## Outcome

Provide the deterministic Strategy/Adapter extension point that turns one canonical marketplace package into a declared harness format, beginning with lossless native Agent Spec/WayFlow output.

## Inputs

- Accepted AD-01 renderer contract and AD-02 marketplace schema.
- Baseline valid and invalid fixture packages.
- Harness capability and compatibility metadata contract.

## Required work

1. Define a small domain-named renderer interface, compile-time renderer registry, request/result contracts, diagnostics, compatibility result, and deterministic file-bundle abstraction.
2. Select renderers by stable harness identifier and explicit renderer version; unknown identifiers fail closed.
3. Implement native Agent Spec/WayFlow rendering as the reference implementation with no semantic drift.
4. Separate canonical fields, consumer-supplied bindings, and renderer defaults. Never synthesize MCP, tools, grants, identity, provider access, or credentials from marketplace content.
5. Normalize ordering, line endings, encoding, file modes, and archive metadata so identical inputs produce identical hashes.
6. Emit a render manifest containing source digest, Agent Spec version, renderer ID/version, input parameters, output files/digests, warnings, and compatibility classification.
7. Add contract tests reusable by every harness adapter and negative tests for unsupported or lossy mappings.

## Outputs

- Renderer Strategy/Adapter contract.
- Native Agent Spec/WayFlow adapter.
- Renderer registry and CLI/library entry point usable by CI and later consumer integrations.
- Deterministic render-manifest schema.
- Shared contract test suite and fixtures.

## Acceptance criteria

- Two clean renders of the same source and parameters are byte-identical.
- Native rendering round-trips all canonical semantics.
- Renderer output cannot introduce provider credentials, tenant grants, hidden network calls, workload identity, or other consumer authority.
- Lossy or unsupported mappings are explicit errors or policy-governed documented warnings; never silent.
- Adding a future harness requires a new adapter, not changes to canonical definitions.

## Verification

Run unit, contract, golden, property/order-normalization, archive-safety, and negative compatibility tests.

## Not in scope

Hermes-specific rendering, OpenClaw-specific rendering, OCI publication, consumer authorization, or runtime deployment.

## Dependencies

Blocked by AD-02. AD-03 supplies the full-catalog fixture but is not required for the renderer contract implementation.

## Architecture review amendments

- Resolve the constrained binding envelope into a complete official Agent Spec `SpecializedAgent` only inside the render boundary.
- Renderer selection is a compile-time allowlisted Strategy registry; runtime-loaded renderer plugins are forbidden.
- Source and skill packages are untrusted inert data. Renderers may not execute package hooks or fetch remote code/URLs.
- `human_in_the_loop` specialization cannot reduce a consuming platform's approval posture; `additional_tools` and authority-bearing fields are rejected.
- Apply archive, path, and resource limits before and after rendering and expose deterministic diagnostics.
