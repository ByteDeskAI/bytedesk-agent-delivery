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
- `wayflowcore==26.1.2` as the evidence-only reference-runtime compatibility
  lane for native Agent Spec output, bound to an exact mirrored-wheel digest,
  certification-image digest, and `bytedesk.external-input-lock/1` upstream
  source lock. It is not a renderer, selectable output, production route, or
  runtime dependency of Agent Delivery.

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
   Compute capability coverage, effective skill set, effective input,
   compatibility coverage, output tree, and reproducibility identity only with
   the closed `bytedesk.renderer-digest-authority/1` RFC 8785 JCS SHA-256
   preimages. Recompute archive digest/size from exact bytes and enforce every
   count, size, ordering, and cross-object equality procedurally.
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
11. Implement the constructible qualification flow for one exact renderer and
    platform: selection, signed fenced attempt, exact framed request/response,
    typed evidence tree, authenticated receipt, typed predicates/evidence, and
    final signed decision under the product-pinned policy and suite.
12. Require fresh caller-nonce/time-bound authenticated current product and
    renderer status heads before selection, bind their exact checkpoint and
    authentication-evidence descriptors through selection and attempt, and
    reject rollback, fork, expiry, wrong nonce, and non-current state.
13. Implement the public-render finalizer that consumes complete tenant-free
    source/skills, validated renderer execution outputs, qualification, and
    current-status proofs and emits a signed, recursively verifiable
    `bytedesk.harness-render/1` artifact.

## Outputs

- Renderer Strategy/Adapter contract.
- Native Agent Spec adapter plus pinned WayFlow compatibility evidence for the
  supported component matrix.
- Renderer registry and CLI/library entry point usable by CI and later consumer integrations.
- Native renderer release manifest, exact platform distribution descriptors,
  embedded compiled-allowlist digest, and signable product-release evidence.
- Deterministic render-manifest schema.
- JCS render-manifest golden bytes and YAML/JSON-equivalent input fixtures.
- Executable renderer digest chains and semantic denials for count, ordering,
  preimage, capability/compatibility/input binding, output tree, archive
  identity, expanded size, and reproducibility substitution.
- A paired `linux/amd64` and `linux/arm64` conformance fixture proving that the
  same platform-independent functional input produces the same logical tree and
  exact archive identity while platform selection, execution, compatibility,
  reproducibility, and complete manifest identities remain distinct.
- Private effective-render result contract suitable for embedding in a private deployment without a separate private-render OCI artifact.
- Shared contract test suite and fixtures.
- Qualification and public-render finalizer contracts that return every exact
  typed object, descriptor, frame, archive byte sequence, and authentication
  proof needed by their downstream consumer.
- Sandbox runner and execution-spy fixtures proving package/skill/customization
  content never executes.

## Acceptance criteria

- Two clean renders of the same source, exact skill set, renderer, and normalized parameters are byte-identical.
- The same platform-independent functional input rendered by every supported
  platform variant produces byte-identical logical files and archive bytes.
  Tree/archive digests and archive size match, while the exact platform
  selection, executed distribution, platform-bound effective-input and
  compatibility identities, reproducibility identity, and manifest digest
  differ and remain verifiable.
- Every renderer digest is reproducible from its one versioned preimage; a
  changed or omitted preimage member, stale aggregate count/size, mismatched
  capability/compatibility/manifest identity, changed logical file entry, or
  changed archive digest is rejected.
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
- `select-renderer` binds an explicit target platform and exact release
  descriptor into one closed `bytedesk.renderer-selection/1`; Strategy,
  Adapter, sandbox, validation, and manifest lineage carry it unchanged.
- Sandbox execution returns an authenticated closed execution receipt whose
  platform, executable distribution, selection, input/output, fencing token,
  worker profile, and sandbox profile are independently read back and matched
  before output is accepted.
- Generic fixtures pass without AD-02, AD-03, or any ByteDesk service.
- Native Agent Spec, Hermes, and OpenClaw are represented by complete
  `linux/amd64` and `linux/arm64` qualification/execution bindings; every
  required role/subject/platform matrix cell passes.
- A public render has a schema-owned authority digest and complete
  `public-render-v1` signing result over its tenant-free lineage. No test-only
  generator object is its production construction path.

## Verification

Run JSON Schema/offline-bundle and generated-model drift checks; unit, contract,
golden, property/order-normalization, paired-platform functional-input/output-
equivalence, archive-safety, renderer-manifest/allowlist substitution, executed-
digest readback, qualification matrix/tree/predicate/finalization, status-head
nonce/time/consistency, pure public-render finalization, sandbox resource/isolation,
input-execution-spy, withdrawal, and negative compatibility tests.

## Not in scope

Hermes-specific rendering, OpenClaw-specific rendering, OCI publication, consumer authorization, or runtime deployment.

## Dependencies

Blocked by AD-01 only. AD-02 and AD-03 are reference-catalog work and are not
implementation or certification dependencies.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.agent-spec-validator/1`
  (`validate-agent-spec`), `bytedesk.port.renderer-strategy/1`
  (`describe-capabilities`, `select-qualification-renderer`, `select-renderer`,
  `render`),
  `bytedesk.port.renderer-adapter/1` (`render`, `validate-output`),
  `bytedesk.port.renderer-sandbox/1` (`execute-renderer`,
  `execute-qualification`),
  `bytedesk.port.release-qualification-finalizer/1`
  (`finalize-release-qualification`),
  `bytedesk.port.public-render-finalizer/1` (`finalize-public-render`), and
  `bytedesk.port.release-status-head/1` (`append-release-status`,
  `resolve-append-attempt`, `resolve-status-head`), and
  `bytedesk.port.wayflow-compatibility/1` (`verify-native-output`) are the exact
  renderer boundary. Their entries live in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Renderer-owned schema IDs are
  `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-capability/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-input-parameters/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/harness-configuration/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-compatibility-result/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/render-manifest/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-eligibility-evidence/1.0.0` at
  their corresponding `contracts/schemas/v1/` paths. Renderer release,
  allowlist, sandbox, framed-worker, normalization, and WayFlow evidence-only
  profiles are pinned in `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-04 owns the shared renderer contract, official
  validator, native renderer, sandbox, and WayFlow evidence fixtures. Run
  `make verify-downstream-ports`; task suites
  `downstream.renderer-contract.v1` and `downstream.native-renderer.v1` live in
  `contracts/ports/v1/conformance-cases.json`. The owned qualification-operation
  cases include `QUAL-SELECT-001-exact-qualification-renderer` for
  `select-qualification-renderer` and
  `RENDER-014-qualification-attempt-authentication-mismatch` for
  `execute-qualification`. Execute the suites' exact harness steps and closed
  oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Boundary.** Native Agent Spec is the only selectable native output. Pinned
  WayFlow 26.1.2 is CI/certification evidence only: it is not a renderer, output
  format, production port, runtime dependency, or authority. Renderer input may
  carry consumer functional customization only during private compilation;
  identity, grants, credentials, trust, approval, and mandatory security policy
  remain outside the renderer.
  Finalization is pure deterministic construction, validation, and
  purpose-separated signing. It does not publish to OCI, perform registry
  readback, or issue publication authority; AD-07 owns the separate
  `push-artifact` commit and publication evidence.

## Architecture review amendments

- Resolve the private functional-customization delta into a complete official Agent Spec effective definition only inside the private render boundary. Revalidate before and after customization.
- Renderer selection is the exact signed release-manifest descriptor resolved
  through the embedded compile-time allowlist; runtime-loaded renderer plugins
  and version-only authority are forbidden.
- Source and skill packages are untrusted data to the renderer. Skill packages may contain arbitrary regular files, including executable code, but renderers may not execute files or package hooks or fetch package-directed remote code/URLs.
- Private customization may change any functional Agent Spec property, including `additional_tools` and functional MCP/provider/model configuration. It cannot change identity, grants, credential values, trust roots, or mandatory consumer security and approval policy.
- Apply archive, path, and resource limits before and after rendering and expose deterministic diagnostics.
- Keep worker request, response, and diagnostic streams on launcher-private
  anonymous pipes and bounded attempt files. Execution-spy conformance must
  prove renderer-derived canaries never reach launcher container stdout/stderr,
  CRI, node, Kubernetes-event, or telemetry logs; those container streams are
  empty or fixed non-content lifecycle codes only.
