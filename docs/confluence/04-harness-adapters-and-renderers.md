# Harness adapters and deterministic renderers

## Design goal

One portable definition must produce usable output for multiple harnesses
without making a harness format canonical. Rendering is a deterministic build
operation with explicit compatibility evidence, not an opaque template export.

## Strategy and Adapter pattern

The renderer boundary uses two established patterns:

- A **Strategy** is selected by the allowlisted harness identifier and exact
  renderer version.
- An **Adapter** maps canonical Agent Spec semantics to the target harness's
  files and configuration model.

The registry is compiled into the trusted renderer distribution. Version one
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

Concrete model/provider settings, MCP servers, tools, grants, credentials, and
workload identities are not emitted by these public renderers. A consumer adds
them later to a private deployment through its own integration Adapter.

## Renderer input contract

Inputs are complete and immutable:

- verified source descriptor and Agent Spec document;
- optional constrained binding and normalized specialization;
- exact Agent Spec version;
- harness identifier and renderer version;
- renderer implementation digest;
- declared, non-secret render parameters; and
- separately approved optional skill digests.

The renderer cannot access a consumer database, secret store, ambient home
directory, package manager, or network. Any unavoidable build input is pinned,
declared, and captured in provenance.

## Renderer output contract

Every render produces:

- the target bundle;
- an ordered manifest of output paths and digests;
- source, binding, skill, and renderer descriptors;
- normalized parameters;
- Agent Spec and target compatibility results;
- warnings, lossy mappings, and unsupported fields;
- expected file modes and ownership class; and
- a reproducibility identifier.

The output is invalid if the manifest omits a generated file or names a file
outside the declared root.

## Deterministic normalization

Byte-identical inputs must produce byte-identical output. Normalization fixes:

- lexical file ordering;
- UTF-8 encoding and LF line endings;
- map/key serialization and insignificant whitespace;
- file modes and logical ownership metadata;
- archive timestamps and entry headers;
- compression algorithm and settings;
- generated identifiers and template ordering; and
- omission versus explicit null/default behavior.

Tests build in isolated clean directories and compare complete artifact
digests. Reproducibility cannot depend on a warm cache or a developer machine.

## Compatibility reporting

Each Adapter publishes a versioned capability matrix. For every canonical
semantic, the result is `exact`, `compatible-with-warning`, `lossy`, or
`unsupported`.

Loss is never silent. A lossy result blocks automatic promotion and requires a
consumer decision captured in the deployment receipt. Unsupported output is
not publishable as a successful render.

Warnings are structured codes with stable machine-readable fields. Human text
may improve without breaking clients.

## Security model

Definitions, skills, and binding text are untrusted inert data. Rendering:

- does not execute package scripts;
- does not follow absolute paths, traversal, symlinks, or hardlinks;
- rejects devices, FIFOs, sockets, and unsafe modes;
- applies file-count, path-depth, compressed-size, expanded-size, and ratio
  limits;
- writes to a fresh confined workspace;
- never interpolates content into a shell command; and
- emits no undeclared network requests.

Template expansion treats all values as data. Harness file names are chosen by
the Adapter, not supplied as arbitrary package paths.

## Renderer versioning

A renderer version is an immutable implementation identity, not merely a
semantic version label. Public render descriptors include both a human version
and implementation digest. A new digest under the same immutable version is
forbidden.

Compatibility changes follow these rules:

- bug fixes that change bytes create a new renderer version;
- added exact support can be backward-compatible but still creates new render
  artifacts;
- removed or newly lossy support is breaking; and
- the consumer pins the renderer used for a binding until it explicitly
  accepts an update.

## Conformance suite

Every Adapter runs the same contract suite:

- official Agent Spec positive and negative fixtures;
- all 34 selectable baseline definitions;
- the non-selectable `office-orchestrator` reference package;
- deterministic clean rebuilds;
- Unicode, newline, path, mode, and archive edge cases;
- forbidden authority-field fixtures;
- missing, malformed, lossy, and unsupported semantic cases; and
- verification that no emitted file claims MCP grants, identity, roles,
  credentials, or provider authority.

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
7. Clear separation between portable output and consumer-owned authority.

The renderer registry remains compile-time allowlisted until a separate ADR
defines a secure plugin lifecycle.

## Related pages

- [Agent Spec and binding](02-agent-spec-and-binding-profile.md)
- [OCI artifact graph](05-oci-artifact-graph.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
