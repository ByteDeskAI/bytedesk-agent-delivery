# Harness adapters and deterministic renderers

## Design goal

One portable definition must produce usable output for multiple harnesses
without making a harness format canonical. Public catalog renders are
tenant-free. Consumer customization is resolved only in authenticated private
deployment compilation, which then performs a complete deterministic render.
Rendering is a build operation with explicit compatibility evidence, not an
opaque template export or a post-render patch.

## Strategy and Adapter pattern

The renderer boundary uses two established patterns:

- A **Strategy** is selected by the allowlisted harness identifier and exact
  signed `bytedesk.renderer-release/1` manifest descriptor.
- An **Adapter** maps canonical Agent Spec semantics to the target harness's
  files and configuration model.

The registry is generated at product-build time, embedded in the signed product
distribution, and identified by its own canonical digest. Version one
does not load renderer plugins from marketplace packages or runtime paths. A
new harness adds an Adapter, capability declaration, fixtures, and contract
tests; it does not change canonical definitions.

## Initial adapters

The initial interoperability targets are:

- **Native Agent Spec**: normalized Agent Spec output and the reference for
  semantic comparison.
- **Hermes**: deterministic profile, instruction, and metadata files suitable
  for the supported Hermes host protocol.
- **OpenClaw**: deterministic agent content in the supported OpenClaw layout.

Concrete model/provider/harness settings, MCP servers, tools, opaque secret
references, grants, credentials, workload identities, tenant identifiers, and
other customization are not emitted by public catalog renderers. A private
binding may describe functional configuration and opaque references, but the
consumer separately supplies and enforces the authority needed to use them.

## Public catalog render input contract

Public inputs are complete, immutable, and tenant-free:

- verified source descriptor and Agent Spec document;
- exact Agent Spec version;
- harness identifier and complete renderer-release descriptor;
- actual supported platform distribution/worker descriptor;
- product-release trust-policy, embedded allowlist, and renderer-owned schema
  digests;
- declared, non-secret public render parameters; and
- exact public skill digests approved for the catalog render.

Public catalog, validation, preview, and render endpoints reject bindings,
customization deltas, private skill descriptors, opaque secret references, and
tenant metadata rather than silently omitting them.

The renderer cannot access a consumer database, secret store, ambient home
directory, package manager, or network. Any unavoidable build input is pinned,
declared, and captured in provenance.

## Private effective render input contract

Authenticated deployment compilation accepts the verified public source, the
canonical binding customization delta, exact public and private skill
descriptors, signed exact-digest skill approvals, a fresh signed consumer-
authority snapshot, the exact renderer release, and all normalized parameters.
The delta may override any functional Agent Spec property, describe
tools/MCP/provider/model/harness configuration and opaque secret references, and
add, replace, or remove arbitrary regular files.

The compiler resolves and verifies every input, applies Agent Spec and file
customization before rendering, constructs the complete effective package, and
runs from the beginning the same exact renderer release and supported executing
distribution identified by the tenant-free public-render lineage. It embeds the
resulting bundle and manifest
directly in the private deployment. V1 has no separate private-render artifact,
and it never patches a public bundle after rendering.

Exact public render bytes may be reused only when the customization has no
operations, the effective skill set exactly equals the source-declared public
skill set, and every normalized source, skill, renderer implementation, and
parameter input matches. Reused bytes are still verified and embedded in the
private deployment.

Every structured source, binding, parameter, and manifest input reaches the
renderer as a JSON data-model value whose identity is its RFC 8785 JCS byte
serialization. Contract-authoring YAML is only a pre-render authoring format
and never a renderer cache key, digest-bearing semantic input, signed output,
or activation input.
An optional integrity reference to retained authoring YAML is provenance or
storage-integrity evidence only, never semantic identity, artifact authority,
or activation authority.
Arbitrary payload inputs, including files named `.yaml` or `.json`, are passed
and hashed as their exact raw bytes rather than parsed based on extension.

## Renderer output contract

Every render produces:

- the target bundle;
- an ordered manifest of output paths and digests;
- source, customization/binding, public and private skill, and renderer
  descriptors as applicable;
- renderer-release manifest, actual executed distribution/worker, platform,
  product distribution, embedded allowlist, and renderer-schema digests;
- normalized parameters;
- Agent Spec and target compatibility results;
- warnings, lossy mappings, and unsupported fields;
- expected file modes and ownership class; and
- a reproducibility identifier.

The output is invalid if the manifest omits a generated file or names a file
outside the declared root.

Renderer capability, parameter, harness-configuration, compatibility-result,
and render-manifest objects use closed Draft 2020-12 schemas from the signed
contract bundle. Unknown fields, schema substitutions, or runtime network
schema resolution fail closed.

## Deterministic normalization

Byte-identical inputs must produce byte-identical output. Normalization fixes:

- lexical file ordering;
- UTF-8 encoding and LF line endings for renderer-generated text only; arbitrary
  input payload bytes are copied unchanged;
- RFC 8785 JCS serialization for authoritative structured objects, independent
  of accepted YAML whitespace, comments, key order, scalar spelling, or quotes;
- file modes and logical ownership metadata;
- archive timestamps and entry headers;
- compression algorithm and settings;
- generated identifiers and template ordering; and
- omission versus explicit null/default behavior.

Tests build in isolated clean directories and compare complete artifact
digests. Equivalent accepted YAML and JSON inputs must resolve to the same
structured input digest, while changing one raw payload byte must change the
corresponding payload digest. Reproducibility cannot depend on a warm cache or
a developer machine.

## Compatibility reporting

Each Adapter publishes a versioned capability matrix. For every canonical
semantic, including the complete privately customized effective input when
applicable, the result is `exact`, `compatible-with-warning`, `lossy`, or
`unsupported`.

Loss is never silent. A lossy result blocks automatic promotion and requires a
consumer decision captured in the deployment receipt. Unsupported output is
not publishable as a successful render.

Warnings are structured codes with stable machine-readable fields. Human text
may improve without breaking clients.

## Security model

Definitions, skills, binding text, and file deltas are untrusted data. Skills
and file additions may be scripts or binaries, but neither the public renderer
nor private compiler executes them. Rendering:

- does not execute package or skill scripts, binaries, macros, install commands,
  or hooks;
- does not follow absolute paths, traversal, symlinks, or hardlinks;
- rejects devices, FIFOs, sockets, and unsafe modes;
- applies file-count, path-depth, compressed-size, expanded-size, and ratio
  limits;
- writes to a fresh confined workspace;
- never interpolates content into a shell command; and
- emits no undeclared network requests.

Each render runs in a fresh bounded sandbox with no network, credentials,
cloud metadata, signing key, ambient home, package-manager configuration, or
inherited developer state. Product and renderer roots are read-only; only a
task-specific workspace is writable. A sandbox setup or executed-distribution
readback mismatch blocks the render.

Template expansion treats all values as data. Binding file operations are
limited to normalized relative regular-file paths under the declared root;
absolute paths, traversal, links, devices, FIFOs, sockets, unsafe entries, raw
secrets, hooks, and package-directed fetches are rejected. A runtime may later
execute skill content only after explicit approval of its exact digest and
under current consumer sandbox, network, identity, and call-time authorization.

## Renderer release identity

A renderer semantic version is discovery metadata within a larger immutable
execution identity. Authority is the signed renderer-release manifest plus the
actual executing product distribution or worker digest and platform, supported
Agent Spec set, renderer-owned schemas, embedded allowlist, and immutable
`product-release-v1` policy digest. A name, tag, source commit, package version,
or PATH executable is never sufficient.

One semantic version maps permanently to one manifest digest. Public renders,
private deployments, compatibility evidence, and receipts record both that
manifest and the actual executed distribution. A withdrawn renderer blocks new
rendering and compilation. A revoked renderer or product distribution is never
executed for forward recovery; historical functional content must enter a new
evaluated public-render lineage under current trusted tooling.

Compatibility changes follow these rules:

- bug fixes that change bytes create a new renderer version;
- added exact support can be backward-compatible but still creates new render
  artifacts;
- removed or newly lossy support is breaking; and
- the consumer pins the renderer used for a binding until it explicitly
  accepts an update.

Renderer release provenance, SBOM, vulnerability, license, deterministic-
output, executable-readback, and sandbox evidence follows
[Renderer identity v1](../standards/renderer-identity-v1.md), including the v1
SLSA Build Level 3 target.

## Conformance suite

Every Adapter runs the same contract suite:

- official Agent Spec positive and negative fixtures;
- generic public Agent and portable SpecializedAgent fixtures covering every
  supported semantic and denial boundary;
- deterministic clean rebuilds;
- signed renderer manifest/allowlist validation, actual executable or worker
  digest readback, platform substitution denial, and one-version-to-one-
  manifest immutability;
- Unicode, newline, path, mode, and archive edge cases;
- accepted equivalent YAML/JSON contract fixtures, RFC 8785 canonical bytes,
  disallowed YAML constructs, and byte-exact `.yaml`, `.json`, and binary
  payload fixtures;
- forbidden authority-field fixtures;
- missing, malformed, lossy, and unsupported semantic cases;
- verification that public output contains no tenant customization, MCP/provider
  configuration, opaque secret references, identity, roles, credentials, or
  grants;
- private-compile fixtures covering arbitrary Agent Spec overrides, safe
  add/replace/remove regular-file operations, public/private skills, full
  rerendering, exact public-render reuse, and rejection of post-render patches;
  and
- verification that private functional configuration never counts as proof of
  MCP/tool/provider authority and that unapproved executable skill content is
  never run; and
- no-network, no-secret, read-only-root, PATH/library injection, resource-limit,
  timeout, withdrawal, revocation, and current-tooling recovery fixtures.

The separate `REFERENCE-CATALOG-CERT` runs the same released Adapter suite over
all 34 selectable ByteDesk definitions and the non-selectable
`office-orchestrator` package. Those catalog fixtures increase reference
coverage but do not gate the standalone renderer products or `CORE-CERT`.

Harness-specific tests then prove the generated content is accepted by the
target parser and selects the expected profile without activating a live
consumer workload.

## Adding a harness

A new Adapter proposal must provide:

1. A stable harness identifier and ownership.
2. A capability matrix against the pinned Agent Spec version.
3. A deterministic file model and activation boundary.
4. Security limits and parser behavior.
5. Reference fixtures and golden manifests.
6. A target-runtime validation method.
7. One certified activation mode: isolated-candidate or guarded in-place, with
   safe-boundary and crash-point behavior compatible with Delivery lifecycle
   v1.
8. Clear separation among tenant-free public output, private functional
   customization, and consumer-owned security authority.

The renderer registry remains compile-time allowlisted until a separate ADR
defines a secure plugin lifecycle.

## Related pages

- [Agent Spec and binding](02-agent-spec-and-binding-profile.md)
- [OCI artifact graph](05-oci-artifact-graph.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
