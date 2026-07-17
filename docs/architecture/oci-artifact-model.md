# OCI artifact model

## Principles

- Exact digests are identity and authority; tags, SemVer, and channels are
  discovery.
- Every authoritative object has an exact JSON Schema Draft 2020-12 ID/digest
  from an independently trusted signed contract bundle and an RFC 8785 identity.
- An OCI `subject` and its referrers are repository-local. Cross-repository
  edges are complete exact descriptors in signed downstream manifests.
- Product/public and per-consumer private artifacts use separate repositories,
  credentials, trust purposes, and privacy policy.
- Artifact provenance, consumer authority, skill approval, desired state,
  canary evidence, and runtime observation remain distinct evidence planes.

The production reference in
[ADR-0002](adr/0002-implementation-stack-and-reference-topology.md) synchronously
pushes and digest-verifies this graph through active and recovery-region Harbor
HA endpoints. Each endpoint owns one versioned encrypted region-local S3
backend and an isolated metadata plane; a separate dual-region Object Lock
archive retains evidence. Distribution 3 is the local/protocol profile.
Registry and storage remain replaceable Adapters; exact OCI descriptors and
digests remain authority, and neither storage nor Registry metadata replaces
PostgreSQL command/CAS state.

## Graph

```text
signed product release
  +--> contract bundle digest
  +--> compiled renderer allowlist digest
  +--> renderer-release digest(s) --> exact worker/platform digest(s)

signed catalog index
  +--> public Agent/ SpecializedAgent source digest
  |      +--> exact public skill digest(s)
  +--> public render digest
          +--> source/skills
          +--> renderer release + actual execution digest + schemas

private binding + exact skill approvals + current authority snapshot
  +--> per-consumer private deployment digest
          +--> embedded effective render bundle/manifest

per-consumer runtime release digest
  +--> exact private deployment digest(s)
  +--> target identity, system-package membership, and activation constraints

one TargetDeliveryState revision
  +--> prepared release
  +--> nonce-bound canary plan
  +--> Host technical evidence
  +--> Consumer capability evidence
  +--> promoted revision or new forward recovery plan/revision

Each OCI subject <- same-repository signature/provenance/SBOM/evidence referrers
```

An arrow uses OCI `subject` only when both objects are in the same repository.
Otherwise the signed downstream object records repository, digest, media type,
size, policy ID, and immutable policy digest and the verifier traverses it
explicitly.

## Contract and renderer artifacts

The signed contract bundle contains schemas and transitive references,
OpenAPI, AsyncAPI, compatibility metadata, and fixtures. Runtime resolution is
offline; an object cannot fetch or supply the schema used to validate itself.
Historical bundles remain available for receipt verification.

A renderer release is trusted executable product code. Its manifest binds
source/build/toolchain/dependency digests, supported Agent Spec and harness
versions, platform worker descriptors, embedded allowlist, renderer-owned
schemas, normalization, SBOM, vulnerability/license, compatibility,
determinism, and SLSA/in-toto evidence. Every render additionally records the
actual executing distribution/platform digest. A semantic version, source
commit, image tag, or PATH binary is not renderer authority.

## Determinism and payload identity

Builders validate accepted JSON or constrained YAML through the exact contract
schema and serialize authoritative values with RFC 8785. YAML presentation is
never authority. Builders fix operation order, generated UTF-8/LF text, file
order, normalized safe paths, timestamps, modes, ownership class, compression,
and annotations. Contract role rather than filename selects structured parsing;
arbitrary `.yaml`, `.json`, and binary payloads preserve exact raw bytes.

Two clean builds with identical schema, source, skill, renderer release,
execution variant, allowlist, parameter, authority-relevant, and normalized
inputs must produce the same declared output. Cross-platform renderer variants
under one release must emit byte-identical logical files and artifact digests.

## Public source, skill, and render

Public source explicitly declares `agent` or `specialized-agent`; `Agent` is the
default and a complete public `SpecializedAgent` is portable source, not private
customization. Public source, skill, and render objects contain no consumer
identifier, private policy, credential, secret reference, grant, or workload
identity.

Skills may carry arbitrary regular files, including executable content, but are
untrusted non-executing input. Publisher signatures prove origin. Runtime use
requires separate current consumer approval of each exact skill digest.

A public render derives only from unchanged source and its declared public
skills. It records the complete renderer-release descriptor, actual executing
distribution/platform, allowlist, renderer schemas, parameters, compatibility,
output layer, and file inventory.

## Consumer-private artifacts

A binding carries the exact schema/source/renderer descriptors, closed
functional property/file/skill operations, exact skill set, update policy, and
absent-or-match revision/digest precondition. It cannot contain authority or
write desired state.

A short-lived consumer-authority snapshot independently binds current identity,
policy, grants, credential set, workload identity, lifecycle, mandatory
sandbox/network/approval controls, target, candidate, desired revision,
operation, nonce, predecessor, and time. Each skill has separate consumer
approval evidence. These envelopes are opaque to Agent Delivery and contain no
reusable credential.

The private deployment binds exact public lineage, binding/customization,
approved skills, compilation authority snapshot, current consumer subdigests,
renderer execution evidence, installation, subject, target, and slot. It embeds
the complete effective render bundle and manifest and is signed under a
purpose-separated key isolated to that consumer.

The compiler reconstructs and revalidates the complete effective Agent Spec and
fully rerenders with the same exact current trusted renderer release as public
lineage. It never patches public output. V1 has no private-render artifact.
Public bytes are reusable only for empty customization when every input and
identity matches.

A runtime release aggregates deployments for one target. It is prepared
content, not desired state. Only the Promotion Coordinator can reference it from
the target aggregate through exact CAS.

## Desired-state and evidence artifacts

Each target has one `TargetDeliveryState` in one selected `DesiredStateStore`.
The Promotion Coordinator alone advances its revision/digest and predecessor.
The Host Reconciler and Consumer Capability Verifier return separate evidence
bound to the Coordinator's signed canary plan, rollout, nonce, candidate,
desired revision, authority/policy, target, slot/generation, and expiry.

Technical evidence proves exact staged/active artifact, files, process/service,
ownership/modes/resources, parser/readiness, switch phase, and recovery marker.
Capability evidence proves candidate workload login, one permitted capability,
and one sentinel capability denied by the normal authorization engine with the
expected policy class. Transport failure or absence is not denial proof.

Promotion is the Coordinator's atomic new target revision after fresh matching
evidence. A post-switch failure becomes `recovery_required`, not a relabeled old
state.

## Forward recovery

Historical known-good is evidence, not automatic activation eligibility.
Recovery creates a new prepared deployment/release and target revision using
eligible historical functional source/customization/file/skill descriptors,
current trusted schemas and renderer/compiler tooling, current content trust
and skill approvals, a fresh authority snapshot, full evaluation, and fresh
canary evidence.

The graph records current predecessor, failed rollout, historical
`recoverySource`, current-tooling substitution, eligibility result, and every
new output/evidence digest. It never reactivates the old deployment, render
bundle, desired record, receipt, signature, authority snapshot, credential
state, or revoked renderer. Explicitly withdrawn or compromised content is
ineligible.

## Retention and restore roots

Garbage collection preserves active and pending releases, historical known-good
and recovery-eligible functional content, contract/renderer releases and policy
snapshots required for historical verification, approvals, observations,
incidents, audit, and legal holds. A withdrawn digest may remain evidence while
being ineligible for new use.

Default evidence retention is 400 days. Contract bundles, renderer release
manifests, and trust snapshots remain available for at least seven years and
never less than consumer evidence retention. Restore verifies manifests, blobs,
referrers, signatures, schemas, trust, desired state, observations, and receipts
as one graph before signing or promotion resumes.

See [OCI media types v1](../standards/oci-media-types-v1.md),
[Renderer identity v1](../standards/renderer-identity-v1.md),
[Consumer authority and private signing v1](../standards/consumer-authority-v1.md),
and [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md).
