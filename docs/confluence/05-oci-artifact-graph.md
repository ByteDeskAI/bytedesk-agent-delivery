# OCI artifact graph

## Why OCI

Agent Delivery uses OCI because distribution needs immutable content addressing,
registry replication, subject/referrer relationships, signatures, provenance,
SBOMs, retention, and access control. OCI is the transport and evidence graph;
it does not define Agent Spec semantics or consumer authorization.

The normative artifact names, schemas, and content types are defined in
[OCI media types v1](../standards/oci-media-types-v1.md).

[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
fixes the first production Registry Adapter, encrypted versioned object profile,
and separate locked evidence archive. They implement this graph but do not
replace it: exact OCI digests remain authority, tags remain discovery, and
object storage never becomes command, desired-state, or approval authority.

## Digest-first identity

Every authoritative edge names an OCI repository, exact digest, expected media
type and size, and immutable trust-policy ID and digest. Tags, semantic versions, and catalog channels
are mutable discovery aids. They can help a user select a candidate, but they
are resolved and pinned before approval.

A receipt never states only `stable`, `v1.4.0`, or `latest`. It records the
complete digest graph that was verified and activated.

## Artifact classes

| Artifact | Typical visibility | Purpose |
|---|---|---|
| Catalog index | Public | Signed discovery, channel, withdrawal, and source descriptors |
| Agent source | Public | Canonical Agent Spec package and declared optional attachments |
| Qualification decision/evidence | Public | Product-pinned typed proof for every renderer release and executable platform |
| Release status/head | Public | Append-only status plus fresh nonce-bound authenticated current-head proof |
| Harness render | Public | Purpose-signed tenant-free source/skill/qualification/selection/execution/output lineage |
| Consumer binding | Private | Digest-pinned functional customization delta and exact public/private skill selection; never security authority |
| Deployment | Private per consumer/tenant | Effective render bundle and manifest plus binding, signed current consumer authority/skill approvals, and target |
| Runtime release manifest | Private per consumer/runtime | Exact deployment/private-compilation-evidence pairs and activation order |
| Signature | Same repository as subject | Cryptographic statement over the local subject digest |
| Provenance attestation | Same repository as subject | Builder, source revision, workflow, inputs, and output evidence |
| Compatibility/evaluation attestation | Same repository as subject | Renderer result and consumer-approved evaluation evidence |
| SBOM | Same repository as subject | Declared content and build/runtime dependency inventory |

Public artifacts are reusable and contain no tenant customization. Private
artifacts can contain functional tools/MCP/provider/model/harness configuration,
opaque secret references, and references to consumer policy and identity state,
but never raw secret values, embedded grants, or reusable bearer credentials.

## Graph shape

A typical release has the following directed graph:

```text
signed catalog
  -> public source digest
       -> local source signature / provenance / SBOM
  -> tenant-free public render digest
       -> explicit public source descriptor
       -> explicit product/renderer/qualification descriptors
       -> fresh authenticated product/renderer status heads
       -> exact public skill descriptors
       -> selection + issued attempt + authenticated actual execution
       -> render manifest + exact archive/layer/files
       -> `public-render-v1` signature / provenance / compatibility

private deployment digest
  -> explicit public source descriptor
  -> explicit tenant-free public render descriptor as renderer/provenance lineage
  -> private binding digest
  -> exact selected public/private skill descriptors
  -> signed consumer-authority snapshot and exact skill approvals
  -> current policy, grant, profile, and target subdigests
  -> renderer-release manifest, executed distribution, allowlist, and schema digests
  -> embedded effective render manifest and exact runtime-file payload descriptor
  -> issued-attempt and authenticated-execution preimages
  -> explicit reuse decision and evidence when public render bytes were reused
  -> local deployment signature / provenance / linked approval evidence

private compilation-evidence digest
  -> exact input-lock and private-deployment descriptors

private runtime release digest
  -> exact canonical private-deployment descriptors
  -> one exact private-compilation-evidence descriptor per deployment
  -> target identity, system-package membership, and activation constraints
  -> `consumer-runtime-release-v1` signature

TargetDeliveryState digest
  -> active runtime release descriptor and at most one pending rollout descriptor
  -> monotonic revision, exact predecessor, target/slot generation, and policy digests
  -> separate canary plan/evidence and forward-recovery plan/evidence descriptors
```

The deployment references consumer state by digest and identifier, not by
embedding raw secrets. The consumer remains authoritative for the meaning and
current validity of identity, role, MCP grant, provider access, credential,
execution-approval, and sandbox-policy subdigests.

Private compilation resolves the customization and approved skills, performs a
complete render, and embeds the effective bundle and manifest in the deployment.
V1 does not publish a separate private-render artifact. It never applies a
post-render patch. The public render descriptor records tenant-free renderer and
provenance lineage; it is an explicit signed cross-repository descriptor, not an
OCI `subject` edge and not the effective private output. Its exact bytes may be
reused only when customization has no operations, the effective skill set
exactly equals the source-declared public skill set, and every normalized source,
skill, renderer, and parameter input matches.

## Subjects and referrers

An OCI `subject` descriptor identifies a manifest by digest, size, and media
type; it does not encode a repository locator. Registry referrer discovery is
repository-scoped, so evidence intended to be discoverable for a subject is
published in that subject's repository and located through that repository's
referrers API.

OCI `subject` is not used to express a cross-repository relationship. A public
source or render and a private tenant deployment may live under different access
policies. Cross-repository edges therefore use explicit signed descriptors in
the downstream payload that include the repository locator, digest, size, media
type, and expected immutable trust-policy ID and digest. The verifier fetches
and verifies each repository independently.

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

Private skill publication, consumer authority/approval, and private deployment
or release publication use separate non-exportable keys and workload
identities isolated per consumer. The preferred keys live in the consumer's
security boundary; a managed profile may use an explicitly opted-in tenant-
dedicated KMS/HSM key. A cross-consumer private signer is non-conforming.

## Deterministic construction

Authoritative declared contract objects and product-authored manifests use
closed JSON Schema Draft 2020-12 contracts from the signed offline-resolvable
contract bundle. They use the
JSON data model serialized as RFC 8785 JCS bytes before hashing or signing. YAML
is permitted only before construction as a contract-authoring format; its
original bytes may be retained, but any integrity reference to those bytes is
provenance/storage-integrity evidence only and never semantic identity,
artifact authority, or activation authority. The contract YAML reader accepts
only the YAML 1.2 JSON-compatible subset
and rejects duplicate keys, aliases, custom tags, non-string mapping keys, and
non-finite numbers. Arbitrary layer payloads retain their exact raw bytes,
including payload files named `.yaml` or `.json`; extensions do not trigger
contract parsing.

Archives are normalized independently. The build fixes customization operation
ordering, file ordering, path separators, timestamps, modes, ownership
metadata, compression settings, and annotations. Undeclared files, post-render
patches, and nondeterministic generated values are forbidden.

Publication performs two clean builds and compares digests. A mismatch blocks
release and emits a diagnostic manifest showing the divergent inputs or files.

## Verification traversal

Before activation, the verifier:

1. Starts from the exact desired release digest.
2. Verifies the local subject media type and signature policy.
3. Resolves the exact allowed schema ID/digest from the signed contract bundle,
   validates the closed Draft 2020-12 schema without network access, and
   verifies the RFC 8785 bytes for authoritative structured contracts.
4. Recursively walks every explicit descriptor, OCI manifest/config/layer/blob,
   and local required referrer.
5. Verifies repository scope, digest, size, media type, semantic role, signer, provenance,
   revocation, and withdrawal.
6. Verifies the complete pinned qualification matrix and fresh nonce/time-bound
   authenticated current status heads, including any exact consistency proof.
7. Recomputes binding, selected-skill, embedded effective-render, and consumer
   state subdigests where the consumer contract requires it.
8. Confirms that the signed public-render lineage is tenant-free and that any byte
   reuse satisfied the exact empty-customization/input-match rule.
9. Confirms the target aggregate revision/digest precondition, immutable
   predecessor lineage, target runtime, consumer/tenant, profile, and stable
   slot bindings.
10. Rejects missing/extra layers, duplicate semantic roles, unregistered
    media/role pairs, tag-only edges, cycles, and incomplete evidence.

Traversal has depth, node-count, byte, and time limits. Every resolved byte
sequence is hashed before parsing. Repeated acyclic descriptors are handled
deterministically; every cycle is invalid, and a repository-name prefix never
classifies an artifact.

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
- pending rollout or forward-recovery revisions;
- audit and legal-hold records;
- unexpired deployment receipts; and
- catalog retention policy.

Known-good is an evidence classification, not automatic recovery eligibility.
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

Forward recovery never activates a retained historical artifact merely because
it is rooted. It requalifies the functional content under current signed
consumer authority and skill approval, uses current trusted renderer/compiler
tooling, creates a new public-render lineage when tooling changed, and emits a
new deployment and target revision. Withdrawn or content-revoked bytes and
revoked executable tooling are ineligible.

## Conformance requirements

Registry conformance tests prove manifest push/pull, subject/referrer discovery,
immutable tag behavior, access boundaries, signature accessory handling,
quotas, retention, garbage collection, replication, backup, and restore on the
actual supported registry implementation. Artifact conformance separately
proves RFC 8785 structured contract bytes, rejection of disallowed YAML
authoring constructs, semantic equivalence of accepted YAML and JSON, and exact
raw-byte identity for arbitrary `.yaml`, `.json`, and binary payload layers.

## Related pages

- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Runtime deployment](10-hosted-runtime-deployment.md)
- [OCI artifact model](../architecture/oci-artifact-model.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
