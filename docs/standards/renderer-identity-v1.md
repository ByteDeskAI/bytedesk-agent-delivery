# Renderer identity v1

**Profile:** `bytedesk.renderer-release/1`

**Status:** Accepted architecture contract; release manifests and allowlist
fixtures are release-blocking AD-04 deliverables

## Purpose

A renderer is trusted executable product code, not package content and not a
version string. This profile gives every renderer implementation an immutable,
verifiable identity and fixes how it is selected, distributed, executed,
withdrawn, and recorded in public and private lineage.

> **Non-normative implementation note:**
> [ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
> fixes the production gVisor worker profile and isolated Python Agent Spec
> compatibility lane. Portable renderer descriptors may still identify an
> allowlisted binary or image distribution; the reference container substrate
> does not permit runtime plugins or artifact-selected code.

## Complete renderer identity

One renderer release is identified by the tuple:

- stable harness and renderer identifiers;
- immutable semantic version and renderer-contract version;
- signed renderer-release manifest descriptor and digest;
- actual executing product distribution or worker-image digest and platform;
- supported Agent Spec version set;
- capability, input-parameter, harness-configuration, compatibility-result,
  and render-manifest schema descriptors and digests; and
- independently trusted `product-release-v1` policy digest.

The release-manifest digest is the primary renderer identity. A name, semantic
version, source commit, image tag, package version, or advertised capability is
never sufficient authority by itself.

## Renderer-release manifest

The manifest is an RFC 8785 canonical JSON object validated under
[Machine contracts v1](machine-contracts-v1.md). It includes:

- source repository, exact commit, and source-tree digest;
- renderer and harness IDs, semantic version, and contract version;
- supported Agent Spec and harness versions;
- all renderer-owned schema descriptors;
- every supported platform variant and its exact executable or OCI image
  descriptor;
- builder image, compiler, toolchain, and locked dependency digests;
- product distribution and embedded allowlist digests;
- SBOM, vulnerability, license, conformance, compatibility, and deterministic-
  output evidence descriptors;
- in-toto/SLSA provenance, publication time, and release signer policy;
- withdrawal, revocation, and end-of-support metadata; and
- the exact output-normalization profile.

One semantic version maps permanently to one release-manifest digest. A change
to code, dependencies, compiler, schema, behavior, normalization, or executable
bits requires a new renderer version and manifest. A reproducible rebuild may
retain a version only when every declared output and executable digest is
byte-identical.

Release builds target SLSA Build Level 3 under the current SLSA specification.
They use isolated, ephemeral build workers, locked dependencies, non-user-
controlled provenance generation, and purpose-separated signing credentials.

## Compiled allowlist

The renderer registry is generated at Agent Delivery build time from reviewed
renderer-release descriptors. Its RFC 8785 digest is embedded in and attested
with the signed product distribution. It maps the harness/renderer/version
tuple to exactly one manifest digest and supported platform variant set.
Duplicate harness/renderer/version keys are invalid even when their manifest
digests differ. Within each manifest, an operating-system/architecture tuple
maps to exactly one executable distribution; conflicting duplicate platform
keys are invalid. These property-key uniqueness rules are semantic invariants
enforced by renderer conformance because JSON Schema `uniqueItems` alone only
rejects byte-equivalent array entries.

An operator or consumer may restrict that compiled set through independent
policy. Runtime configuration, a binding, catalog, skill, artifact, event, or
private customization cannot add a renderer, redirect a renderer descriptor,
or broaden the allowlist. Adding or changing a renderer requires a reviewed
Agent Delivery product release.

Renderer workers may be separately packaged signed binaries or images for
isolation, but they are installed and allowlisted as product components. They
are not dynamically discovered plugins and are never fetched because an agent
artifact requested them. Offline CLI distributions carry the same signed
registry and release manifests.

## Selection and binding

A user may discover renderers by ID and version, but an accepted binding stores
the complete exact renderer-release descriptor: repository, digest, media type,
size, semantic version, and immutable trust-policy ID and digest. The control
plane verifies that descriptor against the running distribution's compiled
allowlist before work begins.

The public render and private deployment record:

- the selected release-manifest digest;
- the actual executed distribution/worker digest and platform;
- the embedded allowlist digest;
- all relevant renderer schema digests; and
- normalized input and output digests.

Before selection, the Strategy verifies the exact signed product/renderer
release objects, their pinned qualification decision, and fresh caller-nonce-
bound authenticated current status heads. The request carries the caller's
operation time and nonce. The returned selection binds those release,
qualification, status, checkpoint, and authentication-evidence descriptors; a
cached status descriptor or trust-policy reference alone is insufficient.

Selection produces one closed `bytedesk.renderer-selection/1` object. It binds
the exact signed renderer-release descriptor, requested harness/version,
renderer ID/version, `linux/amd64` or `linux/arm64` target, the one selected executable-distribution
descriptor, product-distribution and compiled-allowlist digests, all five exact
renderer schema descriptors, worker-profile digest, normalization profile, and a
domain-separated `selectionDigest`. The Strategy passes that object unchanged
to the selected Adapter, the Adapter passes it unchanged to the sandbox, and
output validation compares it with both the render manifest and authenticated
execution readback. No layer re-resolves a platform, executable, release,
allowlist, or schema from the host, `PATH`, a tag, runtime configuration, or
artifact input.

After the isolated process exits, the signed launcher returns a closed
`bytedesk.renderer-execution-receipt/1` plus its independently recomputed JCS
digest and an exact authentication-evidence descriptor. The receipt binds the
attempt and fencing token, selection and renderer-release digests, actual
platform and executed-distribution descriptor, input tree, framed request and
response, output tree, sandbox and worker profiles, authenticated launcher
identity, and completion time. A receipt, digest, evidence descriptor, or
manifest is never accepted alone; all must resolve offline and agree exactly.

The issued renderer-attempt authority additionally binds the accepted product
and renderer status-head checkpoint/authentication-evidence digests. An
execution receipt therefore cannot be replayed under a later, different, stale,
or revoked status observation.

A private full rerender uses the same exact renderer release as its public-
render lineage. If that renderer is no longer currently trusted, a new public
render lineage under a currently trusted renderer is required before private
compilation. Customization cannot patch renderer selection, renderer schemas,
trust policy, execution controls, or renderer code.

## Execution boundary

Every render runs in a fresh, resource-bounded sandbox with:

- no network egress or ingress;
- no consumer credentials, secret values, cloud metadata, signing keys, or
  ambient platform identity;
- read-only product and renderer roots;
- an empty task-specific writable workspace;
- a minimal environment and no inherited home, package-manager, or developer
  configuration;
- dropped privileges, syscall/process/resource limits, and execution timeout;
- explicit input mounts containing only validated canonical objects and byte-
  exact payloads; and
- output collection limited to the declared workspace.

Renderer code may execute because it is trusted product code. Agent, skill,
archive, and customization content never executes. Renderers cannot download
dependencies, invoke package-supplied hooks, load libraries from input, spawn
an input executable, or read consumer databases or secret stores.

## Determinism and compatibility

For the same platform-independent functional input, every supported platform
variant MUST emit byte-identical logical files and deterministic archive bytes.
The file inventory, output tree digest, archive digest, archive size, and every
payload byte are therefore equal across variants. Platform-specific output
drift is a release failure, not a compatibility warning.

Cross-platform equivalence does not make execution identity platform-neutral.
The selected operating-system/architecture key, exact executed-distribution
descriptor, platform, platform-bound `effectiveInputDigest`, compatibility
coverage digest, reproducibility digest, and complete manifest digest MUST
differ between distinct platform variants. A verifier computes the evidence-
only `bytedesk.renderer-functional-input/1` comparison digest from the exact
`bytedesk.renderer-effective-input/1` preimage after replacing the profile and
removing only `executedDistribution` and `platform`. This digest is a release-
test comparison key, not a stored render authority or a substitute for the
platform-bound manifest. Equality of that comparison digest proves both
variants received the same functional input; equality of the tree and archive
identities proves they emitted the same content.

Unsupported semantics fail. A lossy mapping is allowed only when the renderer
declares the exact loss, policy permits it, and the consumer explicitly
approves it. Renderer updates are independently evaluated candidates and
cannot be hidden inside a source, channel, or agent update.

## Digest authority and cross-object invariants

Renderer digest fields use the closed
`bytedesk.renderer-digest-authority/1` profile. Every digest below is lowercase
`sha256:` plus SHA-256 over the RFC 8785 JCS bytes of an object containing
exactly the listed members. The literal `profile` member is domain separation;
it is never omitted, renamed, or inferred. Arrays use their declared order and
objects use the JSON data model before JCS. A digest over a convenient partial
object, authored YAML, archive listing text, or host serialization is not
equivalent.

| Field | Exact preimage |
|---|---|
| `renderer-selection.selectionDigest` | `{"profile":"bytedesk.renderer-selection-digest/1","targetHarness":...,"targetHarnessVersion":...,"rendererId":...,"rendererVersion":...,"rendererRelease":<exact artifact descriptor>,"targetPlatform":...,"executableDistribution":<exact artifact descriptor>,"productDistributionDigest":...,"compiledAllowlistDigest":...,"rendererSchemas":<exact closed schema map>,"workerProfileDigest":...,"normalizationProfile":...}` |
| `renderer-capability.coverageDigest` | `{"profile":"bytedesk.renderer-capability-coverage/1","semanticRegistry":<exact artifact descriptor>,"semantics":<exact semantics array>}` |
| `render-manifest.effectiveSkillSetDigest` | `{"profile":"bytedesk.renderer-effective-skill-set/1","publicSkills":<exact publicSkills array>,"privateSkills":<exact privateSkills array>}` |
| `render-manifest.effectiveInputDigest` | `{"profile":"bytedesk.renderer-effective-input/1","scope":...,"source":...,"sourceKind":...,"agentSpecVersion":...,"bindingDigest":...,"customizationDigest":...,"effectiveSkillSetDigest":...,"harnessId":...,"rendererId":...,"rendererRelease":...,"executedDistribution":...,"platform":...,"productDistributionDigest":...,"compiledAllowlistDigest":...,"rendererSchemas":...,"inputParametersDigest":...,"harnessConfigurationDigest":...,"normalizationProfile":...,"outputArchiveProfile":...}` |
| `renderer-compatibility-result.coverageDigest` | `{"profile":"bytedesk.renderer-compatibility-coverage/1","capabilityDigest":...,"capabilityCoverageDigest":...,"inputDigest":...,"semanticResults":...}` |
| `render-manifest.output.treeDigest` | `{"profile":"bytedesk.renderer-output-tree/1","files":<exact files array>}` |
| `render-manifest.reproducibilityDigest` | `{"profile":"bytedesk.renderer-reproducibility/1","effectiveInputDigest":...,"compatibilityDigest":...,"output":<complete output object>}` where `compatibilityDigest` is SHA-256 over the JCS bytes of the complete embedded compatibility result. |

For a public render, `bindingDigest` and `customizationDigest` are both explicit
JSON `null` values in the effective-input preimage even though those properties
are absent from the public manifest. For a private render they are the exact
required manifest digests. This fixed null convention prevents omission from
creating a second public-input identity.

The following invariants are mandatory and are verified procedurally because
JSON Schema alone cannot recompute hashes or compare sibling objects:

- capability `semantics` are unique and strictly increasing by `semanticId`
  UTF-8 bytes; `semanticCount` equals their length; offline resolution of
  `semanticRegistry` yields exactly those IDs once each;
- public and private skill descriptors are independently unique and strictly
  increasing by `(repository UTF-8 bytes, digest)`. Skill approval evidence is
  intentionally excluded from functional skill-set identity and remains a
  separate authority input;
- `capabilityDigest` is the JCS SHA-256 of the complete capability object and
  `capabilityCoverageDigest` equals that object's `coverageDigest`;
- compatibility `inputDigest` equals the embedding manifest's
  `effectiveInputDigest`; every semantic result is unique, ordered, declared by
  the bound capability object, and has the declared mapping status;
- the compatibility and manifest scope, renderer/harness IDs, exact release,
  executed distribution, platform, Agent Spec version, allowlist, schema set,
  and normalization profile are equal;
- manifest files are unique and strictly increasing by NFC path UTF-8 bytes;
  `output.fileCount` equals their count, `output.expandedSize` equals the safe-
  integer sum of their sizes, and `output.archiveProfile` equals
  `outputArchiveProfile`; and
- `output.digest` is independently recomputed over the exact deterministic
  archive bytes, `output.size` is that archive's byte length, and the
  reproducibility digest binds the complete output object. The logical tree
  digest never substitutes for archive-byte verification; and
- the selected release descriptor digest, target platform, executable
  distribution, worker profile, and selection digest equal the authenticated
  execution receipt; its input/output digests equal the actual framed bytes and
  collected tree; its sandbox profile and fencing token equal the owning
  attempt; and the render manifest's release, platform, executed distribution,
  allowlist, schemas, and output tree equal both selection and receipt.

The renderer Strategy selects an exact compiled release before any of these
objects exist. Each Adapter must emit and verify the same digest profile; an
Adapter cannot define a harness-specific preimage, ignore a field, execute
artifact content, or use a plugin to replace the profile. The executable
positive chains and semantic denials are frozen in
`contracts/fixtures/operations/renderer-digest.cases.json` and verified by
`scripts/contracts/test_renderer_digests.py`.

## Qualification and public-render publication

A renderer release is not selectable merely because its manifest is signed.
The product release pins one immutable qualification policy, suite, and minimum
coverage digest. The qualifier constructs one selection/attempt/receipt/evidence
tree per required renderer/platform tuple and a final signed qualification
decision only after every required evidence role passes. Native Agent Spec,
Hermes, and OpenClaw each require both `linux/amd64` and `linux/arm64`
executable bindings in the initial profile.

For a public render, a declared finalizer consumes the complete tenant-free
source and public skills, validated selection/attempt/execution objects, exact
manifest and archive bytes, qualification decision, and current-status proofs.
It emits one closed `bytedesk.harness-render/1` object with its schema-owned
authority digest and a complete `public-render-v1` signing result. The object
binds every upstream descriptor and output layer needed for recursive offline
verification. A render manifest, logical tree digest, or generator-local object
cannot substitute for this published lineage.

The typed evidence, signer, freshness, append-only status, and denial rules are
normative in
[Release qualification and status v1](release-qualification-v1.md).

## Trust and withdrawal

`product-release-v1` is a distinct KMS-backed trust purpose for Agent Delivery
binaries, compiled allowlists, and renderer-release manifests. Contract bundles
instead verify only under the keyless `contract-bundle-release-v1` purpose and
its separate exact policy. The product and contract policies cannot mix signer,
repository, media-type, or purpose scope. Both are separate from public source,
public render-output, qualification policy,
qualification attempt/receipt/evidence/decision, release status/status-head,
renderer attempt/execution, private skill, consumer authority, compilation,
private deployment, and runtime-release signers.

A withdrawn renderer blocks new rendering and compilation. A revoked renderer
or product distribution also blocks new activation of its outputs unless
current incident policy explicitly trusts an independently rebuilt lineage.
Historical manifests, binaries where retention policy permits, schemas,
attestations, and receipts remain available for forensic and offline historical
verification; retention does not make them eligible for execution.

Forward recovery never executes a revoked renderer. It may reuse historical
functional content only after a current trusted renderer reproduces or safely
remaps it through a newly evaluated public-render lineage.

## Failure behavior

Unknown, omitted, unsupported, ambiently re-resolved, or mismatched selection,
manifest, executable, distribution, platform, allowlist, schema, worker or
sandbox profile, execution receipt, authentication evidence, trust-policy, or
output digest is terminal. The system does not fall
back to another installed version, a tag, a PATH executable, a locally built
binary, or an artifact-provided implementation. Sandbox setup failure blocks
the render.

## Required verification

Release evidence includes:

- signed manifest/schema/allowlist validation and offline trust resolution;
- one-version-to-one-manifest immutability and substitution denial;
- product distribution, worker, platform, and executed-digest readback;
- complete Native Agent Spec, Hermes, and OpenClaw qualification on both server
  architectures, including every required role/subject matrix cell;
- constructible qualification and public-render finalization through declared
  ports rather than fixture-only objects;
- nonce/time/status-head first-contact, unchanged, advancement, rollback, fork,
  expiry, withdrawal, and revocation cases;
- SLSA Build Level 3 provenance, SBOM, vulnerability, and license policy;
- clean cross-platform deterministic builds plus a paired-platform fixture
  proving equal functional-input comparison, logical tree, archive digest, and
  archive size while selection, execution, compatibility, reproducibility, and
  complete manifest identities remain distinct;
- no-network, no-secret, read-only-root, privilege, process, memory, disk, and
  timeout sandbox tests;
- execution-spy fixtures proving input code and hooks never run;
- runtime allowlist expansion, PATH injection, library injection, tag pull,
  plugin loading, and schema substitution denials;
- public/private same-renderer lineage and schema validation; and
- withdrawal, revocation, historical verification, and current-tooling forward
  recovery tests.

## References

- [SLSA v1.2 Build track](https://slsa.dev/spec/v1.2/build-track-basics)
- [in-toto Attestation Framework](https://in-toto.io/Statement/v1)
- [Cosign verification](https://docs.sigstore.dev/cosign/verifying/verify/)
- [Release qualification and status v1](release-qualification-v1.md)
