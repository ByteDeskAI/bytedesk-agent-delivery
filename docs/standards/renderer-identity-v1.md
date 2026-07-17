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

For identical normalized inputs, every supported platform variant MUST emit
byte-identical logical files, manifests, and artifact digests. Platform-
specific nondeterminism is a release failure, not a compatibility warning.

Unsupported semantics fail. A lossy mapping is allowed only when the renderer
declares the exact loss, policy permits it, and the consumer explicitly
approves it. Renderer updates are independently evaluated candidates and
cannot be hidden inside a source, channel, or agent update.

## Trust and withdrawal

`product-release-v1` is a distinct trust purpose for Agent Delivery binaries,
contract bundles, compiled allowlists, and renderer-release manifests. It is
separate from public source, public render-output, private skill, consumer
authority, and private deployment signers.

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

Unknown or mismatched manifest, executable, distribution, platform, allowlist,
schema, trust-policy, or output digest is terminal. The system does not fall
back to another installed version, a tag, a PATH executable, a locally built
binary, or an artifact-provided implementation. Sandbox setup failure blocks
the render.

## Required verification

Release evidence includes:

- signed manifest/schema/allowlist validation and offline trust resolution;
- one-version-to-one-manifest immutability and substitution denial;
- product distribution, worker, platform, and executed-digest readback;
- SLSA Build Level 3 provenance, SBOM, vulnerability, and license policy;
- clean cross-platform deterministic builds and render outputs;
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
