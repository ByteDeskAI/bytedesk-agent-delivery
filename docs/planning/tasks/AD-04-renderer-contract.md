# AD-04: Implement the renderer contract and native Agent Spec output

- Historical Jira: [BDP-3307](https://bytedesk.atlassian.net/browse/BDP-3307)
- Delivery role: Core product
- Release gate: Starts `SUPPLY-CHAIN-CERT`

## Outcome

Provide the deterministic Strategy/Adapter extension point and immutable
renderer-product identity that turn validated portable source into a declared
harness format, beginning with lossless native Agent Spec output. WayFlow is a
pinned external compatibility runtime, not a second renderer output format.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- CONTRACTS-FROZEN renderer identity, machine contracts, canonical encoding,
  operational limits, and exact schema-bundle descriptors from AD-01.
- Generic valid and invalid Agent/Portable SpecializedAgent fixtures; no
  ByteDesk catalog dependency.
- Strict JSON Patch, file-operation, and skill-operation effective-input
  fixtures with exact schema and approval descriptors.
- Harness capability and compatibility metadata contract.
- `wayflowcore==26.1.2` as the pinned reference-runtime compatibility lane for
  native Agent Spec output; it is not a runtime dependency of Agent Delivery.

## Required work

1. Implement the authoritative capability, parameter, harness-configuration,
   compatibility-result, render-manifest, and renderer-release schemas from the
   signed contract bundle.
2. Build a reviewed compiled registry that maps harness/renderer/version to one
   exact renderer-release manifest digest and platform distribution set. Bind
   and record the complete descriptor; version-only selection fails closed.
3. Implement native Agent Spec rendering as the reference implementation with
   no semantic drift. Load the resulting package with pinned WayFlow only in the
   declared compatibility lane; do not emit WayFlow-specific content or include
   WayFlow identity in the native output contract.
4. Separate public canonical fields, consumer functional customization, consumer security-authority inputs, and renderer defaults. Never synthesize MCP, tools, grants, identity, provider access, or credentials from marketplace content. Private functional configuration may supply tools, MCP, providers, models, harness settings, and opaque secret references without becoming authorization.
5. Render only from validated JSON data-model inputs. Serialize every digest-bearing contract object with RFC 8785 JCS; normalize generated text, file ordering, line endings, file modes, and archive metadata; and preserve arbitrary payload bytes exactly so identical inputs produce identical hashes.
6. Emit a render manifest containing scope, source/binding/customization/skill
   digests, Agent Spec version, complete renderer-release descriptor, actual
   distribution/platform and allowlist/schema digests, normalized parameters,
   output inventory, warnings, and compatibility classification.
7. For private compilation, resolve the complete effective Agent Spec and exact approved skill set before invoking the Adapter, then perform a full rerender. Embed the effective manifest and bundle in the private deployment; never patch a public rendered bundle afterward.
8. Add contract tests reusable by every harness adapter and negative tests for unsupported or lossy mappings.
9. Produce renderer-release manifests containing source/toolchain/dependency,
   executable or worker image, platform, schema, allowlist, normalization, SBOM,
   vulnerability/license, conformance, compatibility, and provenance
   descriptors. Embed and attest the compiled allowlist digest in the product
   distribution.
10. Execute every render in a fresh no-network, no-secret, read-only-root,
    dropped-privilege, resource/time-bounded sandbox with only validated inputs
    and a declared output workspace.

## Outputs

- Renderer Strategy/Adapter contract.
- Native Agent Spec adapter plus pinned WayFlow compatibility evidence for the
  supported component matrix.
- Renderer registry and CLI/library entry point usable by CI and later consumer integrations.
- Native renderer release manifest, exact platform distribution descriptors,
  embedded compiled-allowlist digest, and signable product-release evidence.
- Deterministic render-manifest schema.
- JCS render-manifest golden bytes and YAML/JSON-equivalent input fixtures.
- Private effective-render result contract suitable for embedding in a private deployment without a separate private-render OCI artifact.
- Shared contract test suite and fixtures.
- Sandbox runner and execution-spy fixtures proving package/skill/customization
  content never executes.

## Acceptance criteria

- Two clean renders of the same source, exact skill set, renderer, and normalized parameters are byte-identical.
- Native rendering round-trips all canonical semantics.
- No renderer receives raw authoring YAML or can make YAML spelling, comments, anchors, or key order affect semantic identity.
- Renderer output cannot introduce provider credentials, tenant grants, hidden network calls, workload identity, or other consumer authority.
- Public output contains no consumer customization. Private output reflects every normalized customization/file/skill input, and an exact public bundle is reused only when customization is empty and all inputs match.
- Lossy or unsupported mappings are explicit errors or policy-governed documented warnings; never silent.
- Adding a future harness requires a new adapter, not changes to canonical definitions.
- One semantic renderer version permanently maps to one manifest digest;
  bindings and lineage record that manifest and the actually executed
  distribution/platform/allowlist/schema digests.
- No tag, PATH executable, local build, runtime configuration, artifact, or
  plugin can select or expand renderer code.
- Generic fixtures pass without AD-02, AD-03, or any ByteDesk service.

## Verification

Run JSON Schema/offline-bundle and generated-model drift checks; unit, contract,
golden, property/order-normalization, cross-platform deterministic, archive-
safety, renderer-manifest/allowlist substitution, executed-digest readback,
sandbox resource/isolation, input-execution-spy, withdrawal, and negative
compatibility tests.

## Not in scope

Hermes-specific rendering, OpenClaw-specific rendering, OCI publication, consumer authorization, or runtime deployment.

## Dependencies

Blocked by AD-01 only. AD-02 and AD-03 are reference-catalog work and are not
implementation or certification dependencies.

## Architecture review amendments

- Resolve the private functional-customization delta into a complete official Agent Spec effective definition only inside the private render boundary. Revalidate before and after customization.
- Renderer selection is the exact signed release-manifest descriptor resolved
  through the embedded compile-time allowlist; runtime-loaded renderer plugins
  and version-only authority are forbidden.
- Source and skill packages are untrusted data to the renderer. Skill packages may contain arbitrary regular files, including executable code, but renderers may not execute files or package hooks or fetch package-directed remote code/URLs.
- Private customization may change any functional Agent Spec property, including `additional_tools` and functional MCP/provider/model configuration. It cannot change identity, grants, credential values, trust roots, or mandatory consumer security and approval policy.
- Apply archive, path, and resource limits before and after rendering and expose deterministic diagnostics.
