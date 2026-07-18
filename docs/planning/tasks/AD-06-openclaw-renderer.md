# AD-06: Implement the deterministic OpenClaw agent renderer

- Historical Jira: [BDP-3305](https://bytedesk.atlassian.net/browse/BDP-3305)
- Delivery role: Core product harness adapter
- Release gate: Required renderer product for `SUPPLY-CHAIN-CERT`

## Outcome

Render canonical marketplace packages into the OpenClaw agent-directory contract without allowing OpenClaw files to become an independent source of truth.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Landed renderer contract from AD-04.
- An exact `bytedesk.external-input-lock/1` artifact for the
  `bytedesk-openclaw/agents/*/{AGENTS.md,SOUL.md,TOOLS.md}` definitions,
  validators, and runtime expectations used as compatibility evidence. The lock
  binds repository URL, immutable commit, source-tree digest, sorted path/digest
  inventory, and `compatibilityEvidenceOnly: true`; an unpinned checkout or
  mutable branch is not an input or authority.
- Generic public/private Agent Spec, strict customization, file, skill, and
  unsupported-semantics fixtures from AD-04.

## Required work

1. Implement an OpenClaw adapter behind the shared renderer interface.
2. Map canonical instructions and persona into the minimal OpenClaw file set for the public catalog scope, and support the complete resolved private effective definition in the private scope; isolate renderer-owned operational guidance from canonical role content.
3. Do not populate TOOLS, MCP, resources, provider access, identity, credentials, or private customization from marketplace content. Private functional customization may populate tool/MCP/provider/model/harness configuration and opaque secret references during private compilation; consuming-platform security authority remains external.
4. Emit deterministic file ordering/content and a render manifest.
5. Keep the ByteDesk slug inventory from the accepted external-input lock only
   as non-normative compatibility evidence. The AD-17 ByteDesk OpenClaw
   workstream owns the migration map and full-catalog comparison; AD-06 owns
   only the generic renderer and generic conformance corpus.
6. Add generic golden fixtures spanning representative portable semantics;
   ByteDesk full-catalog compatibility belongs to AD-03/AD-17.
7. Fail explicitly when canonical semantics cannot be represented.
8. Fully rerender the resolved private effective definition and exact approved public/private skills. Embed the effective OpenClaw bundle and manifest in the private deployment; do not post-patch a public bundle.
9. Produce the OpenClaw renderer-release manifest and supported platform
   distribution descriptors, pass the compiled-allowlist and sandbox contract,
   and record the actual executed digest in every render.

## Outputs

- Versioned OpenClaw renderer.
- Deterministic generic render fixtures.
- Generic compatibility and intent-preservation report. AD-17 owns the
  ByteDesk-specific migration map and full-catalog comparison.
- Contract and golden tests.
- Immutable OpenClaw renderer-release candidate, schema descriptors, sandbox
  evidence, SBOM, and deterministic cross-platform evidence for AD-08 signing.

## Acceptance criteria

- The complete generic OpenClaw conformance fixture suite renders without a
  ByteDesk catalog, secret, or runtime coupling.
- Repeated clean renders are byte-identical.
- OpenClaw-specific files are generated outputs, not edited canonical inputs.
- No default tool, MCP, provider, identity, or resource access is inferred.
- Arbitrary approved skill regular files are preserved by digest without execution during delivery; OpenClaw runtime execution requires explicit approval of the exact skill digest under current consumer sandbox, network, identity, and call-time authorization controls.
- Intent differences from legacy definitions are reviewed and documented.
- Renderer version, release manifest, executing distribution/platform,
  allowlist, and schema digests are exact and substitution-safe.

## Verification

Run shared schema/contract/golden tests, generic semantic coverage, clean
cross-platform deterministic renders, exact renderer/distribution/allowlist
readback, sandbox and input-execution-spy tests, secret and archive-safety
checks, and pinned OpenClaw static/runtime configuration validation.

## Not in scope

OpenClaw source cutover, runtime deployment, or consuming-platform authorization.

## Dependencies

Blocked by AD-04 only.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.renderer-strategy/1`
  (`describe-capabilities`, `select-renderer`, `render`),
  `bytedesk.port.renderer-adapter/1` (`render`, `validate-output`), and
  `bytedesk.port.renderer-sandbox/1` (`execute-renderer`) define the OpenClaw
  renderer boundary in `contracts/ports/v1/port-registry.json`. Exact
  field-value and closed request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** OpenClaw uses the exact renderer-owned
  schema IDs `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-capability/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-input-parameters/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/harness-configuration/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-compatibility-result/1.0.0`,
  and `https://schemas.bytedesk.ai/agent-delivery/v1/render-manifest/1.0.0`, plus
  renderer-release and harness-render schemas under `contracts/schemas/v1/`.
  OpenClaw and external-input-lock profiles are in
  `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-06 owns only the consumer-neutral OpenClaw Adapter,
  generic corpus, and generic semantic-compatibility report. Run
  `make verify-downstream-ports`; the task-specific suite is
  `downstream.openclaw-renderer.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Boundary.** The AD-17 ByteDesk OpenClaw workstream owns the migration map,
  slug migration, full-catalog comparison, and runtime cutover. Locked consumer
  files remain compatibility evidence and never become generic renderer inputs
  or core authority. Functional private customization is allowed only through a
  full private rerender; consumer security authority remains external.

## Architecture review amendments

- Generated OpenClaw content is untrusted output from a compile-time allowlisted adapter; packages cannot supply renderer plugins or executable hooks.
- OpenClaw functional tool, MCP, provider, model, and harness configuration plus opaque secret references may be expressed in private customization but cannot flow back into canonical source or public renders. Identity, grants, credential values, trust, and mandatory approval/security policy remain consuming-platform-owned.
- Unsupported semantics fail with stable diagnostics and never produce a silently weakened agent.
