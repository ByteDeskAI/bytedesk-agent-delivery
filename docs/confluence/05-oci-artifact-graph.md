# OCI artifact graph

## Why OCI

Agent Delivery uses OCI because distribution needs immutable content addressing,
registry replication, subject/referrer relationships, signatures, provenance,
SBOMs, retention, and access control. OCI is the transport and evidence graph;
it does not define Agent Spec semantics or consumer authorization.

The normative artifact names, schemas, and content types are defined in
[OCI media types v1](../standards/oci-media-types-v1.md).

## Digest-first identity

Every authoritative edge names an OCI repository, exact digest, expected media
type, and expected trust policy. Tags, semantic versions, and catalog channels
are mutable discovery aids. They can help a user select a candidate, but they
are resolved and pinned before approval.

A receipt never states only `stable`, `v1.4.0`, or `latest`. It records the
complete digest graph that was verified and activated.

## Artifact classes

| Artifact | Typical visibility | Purpose |
|---|---|---|
| Catalog index | Public | Signed discovery, channel, withdrawal, and source descriptors |
| Agent source | Public | Canonical Agent Spec package and declared optional attachments |
| Harness render | Public | Deterministic output for one source, renderer, and parameter set |
| Consumer binding | Private | Digest-pinned, constrained non-authorizing specialization |
| Deployment | Private per consumer/tenant | Source/render plus current consumer-owned policy subdigests and target |
| Runtime release manifest | Private per consumer/runtime | Exact desired deployment set and activation order |
| Signature | Same repository as subject | Cryptographic statement over the local subject digest |
| Provenance attestation | Same repository as subject | Builder, source revision, workflow, inputs, and output evidence |
| Compatibility/evaluation attestation | Same repository as subject | Renderer result and consumer-approved evaluation evidence |
| SBOM | Same repository as subject | Declared content and build/runtime dependency inventory |

Public artifacts are reusable. Private artifacts can contain references to
consumer policy and identity state, but never secret values or reusable bearer
credentials.

## Graph shape

A typical release has the following directed graph:

```text
signed catalog
  -> public source digest
       -> local source signature / provenance / SBOM
  -> public render digest
       -> explicit public source descriptor
       -> explicit renderer descriptor
       -> local render signature / provenance / compatibility

private deployment digest
  -> explicit public source descriptor
  -> explicit public render descriptor
  -> private binding digest
  -> consumer policy, grant, profile, and target subdigests
  -> local deployment signature / provenance / approval

private runtime release digest
  -> exact private deployment digests
  -> rollout and predecessor metadata
  -> local release signature
```

The deployment references consumer state by digest and identifier, not by
embedding secrets. The consumer remains authoritative for the meaning and
current validity of identity, role, MCP grant, and credential subdigests.

## Subjects and referrers

OCI 1.1 subject/referrer relationships are used for evidence attached to a
subject in the **same repository**. A verifier can discover a source artifact's
signature or SBOM in that source repository.

Referrer discovery is not assumed across repositories. A public render and a
private tenant deployment may live under different access policies. Therefore,
cross-repository edges are explicit signed descriptors in the downstream
manifest. The verifier follows each descriptor, fetches the named repository
and digest, checks the media type, and applies that repository's expected signer
policy independently.

An artifact cannot provide a new trust root for the artifact it references.

## Repository topology

A conforming installation separates at least:

- public catalog/source repositories;
- public renderer output repositories;
- private consumer or tenant deployment repositories; and
- private runtime release repositories where access must be narrower.

The exact registry project layout is configurable. Isolation requirements are
not. A host pull identity must not gain access to another consumer's private
deployment merely because both consume the same public definition.

## Deterministic construction

Artifact manifests and layers use canonical serialization and normalized
archives. The build fixes file ordering, path separators, timestamps, modes,
ownership metadata, compression settings, and annotations. Undeclared files
and nondeterministic generated values are forbidden.

Publication performs two clean builds and compares digests. A mismatch blocks
release and emits a diagnostic manifest showing the divergent inputs or files.

## Verification traversal

Before activation, the verifier:

1. Starts from the exact desired release digest.
2. Verifies the local subject media type and signature policy.
3. Parses only the versioned schema for that media type.
4. Walks every explicit descriptor and local required referrer.
5. Verifies repository scope, digest, size, media type, signer, provenance,
   revocation, and withdrawal.
6. Recomputes binding and consumer state subdigests where the consumer contract
   requires it.
7. Confirms predecessor, target runtime, consumer/tenant, profile, and stable
   slot bindings.
8. Rejects extra undeclared layers and incomplete evidence.

Traversal has depth, node-count, byte, and time limits. Cycles and repeated
descriptors are handled deterministically; a cycle in a schema that requires a
DAG is invalid.

## Tags, channels, and immutability

Tags may point to release manifests for human navigation, but registry policy
uses immutable release tags where supported. A channel update creates a signed
catalog change that names a new digest. Installed bindings retain their old
digest until a compatible update proposal is accepted.

No host follows a channel. Hosts receive only an exact desired release digest.

## Retention and garbage collection

Registry garbage collection must preserve every digest reachable from:

- active desired and observed releases;
- last-known-good releases;
- pending rollout or forward-rollback revisions;
- audit and legal-hold records;
- unexpired deployment receipts; and
- catalog retention policy.

These roots include explicit upstream descriptors, not only local referrers.
Deletion planning therefore computes the product graph before registry garbage
collection. A consumer-deletion workflow removes private data only after the
consumer's retention and legal-hold policy permits it.

## Withdrawal and compromise

Withdrawal marks a digest unavailable for new import or activation without
rewriting its identity. Signer compromise and digest compromise are separate
revocation inputs. An already active verified release follows incident policy:
it may be held temporarily during an outage or stopped for confirmed compromise,
but it is never silently replaced by a mutable tag target.

## Conformance requirements

Registry conformance tests prove manifest push/pull, subject/referrer discovery,
immutable tag behavior, access boundaries, signature accessory handling,
quotas, retention, garbage collection, replication, backup, and restore on the
actual supported registry implementation.

## Related pages

- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Runtime deployment](10-hosted-runtime-deployment.md)
- [OCI artifact model](../architecture/oci-artifact-model.md)
