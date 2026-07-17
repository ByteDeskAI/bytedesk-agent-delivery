# Marketplace repository and baseline catalog

## Marketplace as source, not service authority

The marketplace is a Git-authored collection of portable Agent Spec packages
and signed catalog metadata. It can be hosted with the product during bootstrap
or behind the same repository contract in an independent Git repository. A
third party can fork it, publish another catalog, or consume it without a
ByteDesk account.

The marketplace does not provision identities, create organizations, install
MCP servers, grant tools, select credentials, or deploy processes. It is an
authoring and discovery source.

## Repository contract

A conforming source repository separates concerns explicitly:

```text
agents/                 selectable portable definitions
systems/                non-selectable reference/system definitions
skills/                 optional separately addressed content
catalog/                catalog source and release-channel metadata
schemas/                pinned schemas and policy fixtures
tests/                   positive and negative conformance fixtures
```

Exact paths may evolve, but one package cannot reach into another package or
depend on untracked repository state. Publication builds a package from a
declared file manifest rather than archiving the entire checkout.

## Package identity

Each package has a stable, globally namespaced identifier. Display name, role
title, description, icon, and tags are mutable metadata. They do not become a
consumer's organizational identity or runtime principal.

The source commit provides authoring provenance. The published OCI digest is
the distribution and activation identity. A Git branch, Git tag, catalog
channel, semantic version, or friendly slug must never substitute for the
digest.

## Baseline catalog

The first catalog migrates the reviewed ByteDesk roster into:

- exactly **34 selectable employee-agent packages**; and
- one non-selectable **`office-orchestrator` reference system package**.

The 34 packages are templates a consumer may choose. Selection can create or
bind a consumer-owned organizational identity only through the consumer's own
workflow. Catalog names, titles, and reporting suggestions are defaults, not
authority.

`office-orchestrator` is present to exercise system-package rendering and
deployment. It is not shown as a selectable employee and cannot implicitly
create a profile, login, role, MCP grant, or provider connection.

Catalog conformance asserts both counts. Adding or removing reference packages
requires an intentional catalog release and documentation update; a CI glob is
not accepted as proof of the expected roster.

## Catalog metadata

A signed catalog index contains:

- catalog schema version and digest;
- source package descriptors by repository, digest, and media type;
- display and search metadata;
- selectable or system classification;
- supported Agent Spec versions;
- available harness compatibility summaries;
- release version, channels, and publication timestamp;
- withdrawal, supersession, and deprecation state;
- optional skill descriptors; and
- expected publisher trust policy identifier.

It may include non-binding capability hints for search. Such hints cannot be
interpreted as an MCP requirement or grant. The consumer decides whether and
how to map capabilities after import.

## Publication pipeline

Marketplace CI performs the following steps from a clean checkout:

1. Pin and verify all toolchain dependencies.
2. Enumerate only declared packages and files.
3. Enforce path, file, archive, mode, and size limits.
4. Validate Agent Spec using the official pinned SDK.
5. Reject forbidden authority fields and secrets.
6. Scan licenses, malware indicators, and accidental credentials.
7. Normalize and build source artifacts twice to prove reproducibility.
8. Run renderer compatibility tests where applicable.
9. Publish by digest to the public registry namespace.
10. Emit provenance, SBOM, signature, and signed catalog index.

Publishing is performed by a workload identity authorized only for marketplace
source artifacts. The pipeline never receives a private tenant deployment key.

## Channels and versions

Semantic versions and channels such as `candidate` and `stable` are discovery
and update-policy inputs. They point to exact signed digests. Consumers store
the digest they approved and use compare-and-swap when adopting a newer one.

Retagging cannot change an installed definition. A withdrawn digest remains
addressable for audit and existing recovery policy, but cannot be newly
imported or activated.

## Contribution governance

A contribution must include:

- an Agent Spec-valid definition;
- provenance for authored files and optional skills;
- policy fixtures proving no authority-bearing content;
- deterministic package and applicable render tests;
- compatibility and migration notes for breaking changes; and
- review by maintainers permitted to approve that package class.

System packages receive separate review because they can affect engine-wide
behavior. New or changed skills receive independent review and do not inherit
approval from an instruction-only change.

## Forks and third-party catalogs

Trust is catalog-specific. A consumer can configure multiple catalogs, each
with its own expected publisher identity and allowed repository namespace.
Package-provided trust metadata never adds a trusted catalog.

A clean-room consumer must be able to:

- fetch the signed catalog;
- verify its publisher;
- inspect and validate a definition;
- render it for a supported harness;
- verify source and render OCI artifacts; and
- decline all ByteDesk-specific integration behavior.

This clean-room path is a release requirement, not an optional community use
case.

## OASF projection

If an OASF or another discovery format is published, it is a generated, signed
projection from the canonical catalog. It is never an authoring source or
deployment authority. A projection records the catalog digest and generator
version so consumers can trace it back to canonical content.

## Related pages

- [Agent Spec and binding](02-agent-spec-and-binding-profile.md)
- [OCI artifact graph](05-oci-artifact-graph.md)
- [Evaluation and promotion](09-evaluation-promotion-updates-and-rollback.md)
