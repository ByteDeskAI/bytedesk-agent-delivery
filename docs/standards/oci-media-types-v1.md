# OCI media types v1

**Status:** Accepted architecture registry; concrete schemas, manifests, and
contract fixtures are release-blocking deliverables

## Artifact and evidence types

| Artifact or evidence | `artifactType` |
|---|---|
| Contract bundle | `application/vnd.bytedesk.agent.contract-bundle.v1+json` |
| Renderer release | `application/vnd.bytedesk.agent.renderer-release.v1+json` |
| Catalog index | `application/vnd.bytedesk.agent.catalog.v1+json` |
| Agent source | `application/vnd.bytedesk.agent.source.v1+json` |
| Skill package | `application/vnd.bytedesk.agent.skill.v1+json` |
| Harness render | `application/vnd.bytedesk.agent.render.v1+json` |
| Consumer authority snapshot | `application/vnd.bytedesk.agent.consumer-authority.v1+json` |
| Skill approval | `application/vnd.bytedesk.agent.skill-approval.v1+json` |
| Consumer deployment | `application/vnd.bytedesk.agent.deployment.v1+json` |
| Runtime release | `application/vnd.bytedesk.agent.release.v1+json` |
| Target delivery state | `application/vnd.bytedesk.agent.target-delivery-state.v1+json` |
| Canary plan | `application/vnd.bytedesk.agent.canary-plan.v1+json` |
| Canary evidence | `application/vnd.bytedesk.agent.canary-evidence.v1+json` |
| Recovery plan | `application/vnd.bytedesk.agent.recovery-plan.v1+json` |
| Render compatibility attestation | `application/vnd.bytedesk.agent.compatibility.v1+json` |
| Evaluation attestation | `application/vnd.bytedesk.agent.evaluation.v1+json` |
| Consumer policy attestation | `application/vnd.bytedesk.agent.policy.v1+json` |
| Deployment receipt | `application/vnd.bytedesk.agent.receipt.v1+json` |
| Operational readiness report | `application/vnd.bytedesk.agent.readiness.v1+json` |

Signatures, in-toto provenance, SLSA provenance, and SBOMs use their ecosystem
media types where possible. ByteDesk-specific predicates use the closed types
above. A media type names a contract family; the exact schema ID and schema
digest still identify the accepted shape.

## Common descriptor

Every explicit edge contains the complete expected identity:

```json
{
  "repository": "registry.example/agents/source/chief-of-staff",
  "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "mediaType": "application/vnd.bytedesk.agent.source.v1+json",
  "size": 12345,
  "trustPolicy": {
    "id": "public-source-v1",
    "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

Repository canonicalization, digest algorithm, size, media type, policy ID, and
immutable policy digest are verified before content is accepted. An annotation,
tag, channel, mutable policy alias, or artifact-supplied trust root never
substitutes for this descriptor.

Every authoritative manifest is a closed JSON Schema Draft 2020-12 object from
an independently trusted signed contract bundle under
[Machine contracts v1](machine-contracts-v1.md). Its validated JSON data model
uses [Canonical encoding v1](canonical-encoding-v1.md). Runtime network schema
fetching and unknown fields fail closed.

## Product contract and renderer releases

The contract bundle contains exact schemas and transitive references, OpenAPI,
AsyncAPI, compatibility metadata, and complete positive/denial fixtures. Its
manifest lists every `$id`, media type, size, schema digest, and trust-policy
digest. It is signed under `product-release-v1` and retained for historical
verification.

The renderer-release manifest is the primary renderer identity. It binds
harness/renderer IDs, immutable semantic and contract versions, source and
build inputs, every platform executable/worker descriptor, compiled allowlist,
renderer-owned schema descriptors, normalization, SBOM, vulnerability/license,
compatibility, deterministic-output, and in-toto/SLSA evidence. The actual
executed distribution/platform digest is also recorded in each render. A
version string or image tag is never renderer authority.

## Catalog, source, and skill

The catalog lists exact source and public-skill descriptors, semantic/display
metadata, release channels, compatibility summaries, publication time, and
withdrawal state. It is discovery data; every referenced object is verified
independently.

An agent-source manifest identifies official Agent Spec version, package ID,
explicit `agent` or `specialized-agent` source kind, selectability/system status,
deterministic source layer, declared public skills, schema identity, and policy
result. `Agent` is the default. A complete public `SpecializedAgent` is portable
source, not private customization or consumer authority.

A skill manifest identifies package/version, public or consumer-private scope,
deterministic content layer, complete file/mode inventory, nested archives,
SBOM/scan/license evidence, and withdrawal. Skills may carry arbitrary regular
files, including executable scripts and binaries, but never grants, secret
values, hooks, or pipeline execution. Publisher trust proves provenance, not
runtime approval. A consumer-private skill must verify under that consumer's
isolated `consumer-private-skill-v1` publication key; an upstream supplier
signature is additional provenance and cannot replace it. Every effective
digest separately requires current consumer `bytedesk.skill-approval/1`
evidence.

## Public harness render

The tenant-free public render references the source and each declared public
skill plus the complete renderer-release descriptor, actual executing product
distribution/platform digest, embedded allowlist digest, renderer-owned schema
digests, normalized parameters, compatibility result, output layer, and file
inventory. It accepts no binding, private skill, consumer identifier, authority
snapshot, opaque secret reference, or private customization.

## Consumer authority, deployment, and runtime release

A consumer-authority snapshot is a signed, short-lived, operation-specific
opaque envelope. It binds exact consumer, subject, installation, target,
candidate, desired revision, predecessor, policy/grant/credential/workload-
identity/lifecycle/sandbox/network/approval digests, nonce, audience, and
validity window. It contains no reusable credential and is signed under the
per-consumer `consumer-authority-v1` purpose.

The consumer deployment is private to one consumer. It references exact public
source/render lineage, binding and customization, approved skills and approval
evidence, compilation authority snapshot, schema/renderer identities, and
current opaque consumer subdigests. It embeds the complete effective render
bundle and manifest. It is signed under a per-consumer
`consumer-deployment-v1` key; a provider-wide shared private-deployment signer
is forbidden.

The effective render reconstructs and revalidates the complete Agent Spec and
fully invokes the same exact current trusted renderer release recorded by its
public lineage. It never patches a public render. V1 has no private-render media
type. Exact public bytes may be reused only when customization is empty and all
schema, source, skill, renderer release, execution variant, allowlist,
parameter, and normalized inputs match.

A runtime release aggregates exact per-agent deployment subdigests for one
target, identifies any system package, and binds activation constraints. A
compiler prepares it but cannot make it desired state.

## Desired state, canary, and recovery evidence

One target-delivery-state object exists for each consumer/runtime target. It
records monotonic revision/digest, exact predecessor, active release, at most one
pending rollout, activation constraints, and target/slot generation. Only the
Promotion Coordinator may advance it in the one selected DesiredStateStore by
the exact absent-or-match precondition.

The signed canary plan binds rollout, nonce, candidate, desired revision,
consumer, subject, target, slot/generation, activation mode, current authority
and policy, required checks, expected result classes, expiry, and evidence
signer policy. Separate canary evidence records:

- Host Reconciler technical artifact/file/process/resource/switch proof; or
- Consumer Capability Verifier workload login, one permitted capability, and
  one exact policy-denied sentinel result.

A timeout, transport failure, `404`, parser error, or unavailable tool is not
denial evidence. Promotion requires fresh matching evidence from both actors,
except a signed `not_applicable` from a certified no-capability profile.

A recovery plan creates a new forward revision. It records the current
predecessor, failed rollout, historical `recoverySource`, reused functional
descriptors, current-tooling substitution, eligibility result, fresh consumer
authority, and new outputs/evidence. It never reactivates an old deployment,
render bundle, desired record, receipt, signature, authority snapshot,
credential state, or revoked renderer.

## Referrers and cross-repository edges

An OCI manifest may set `subject` only to an exact artifact in the same
repository. Signatures and attestations refer to that local subject. Every
cross-repository relationship is a common descriptor in a signed downstream
manifest and is independently verified; referrer discovery never crosses
repositories.

## Deterministic layers and failure behavior

Archive layers fix file order, normalized paths, timestamps, declared safe
modes, ownership class, compression algorithm, and parameters. Contract role
and media type—not `.json`, `.yaml`, or `.yml`—select structured parsing.
Arbitrary payload files preserve exact raw bytes without decoding,
transcoding, or line-ending normalization.

Unknown schema, descriptor, trust-policy digest, signer purpose, renderer
release, executing distribution, authority snapshot, skill approval,
precondition, evidence actor, nonce, or graph edge is terminal. A verifier never
falls back to a tag, alternate renderer, authored YAML, shared private key, old
authority, or historical deployment.

## Retention roots

Garbage collection preserves active and pending releases, historical known-good
and recovery-eligible functional content, contract/renderer releases required
for receipt verification, current and archived trust-policy snapshots,
approvals, observations, incidents, audit, and legal holds. Readiness defaults
retain queryable operational evidence for 400 days and contract, renderer, and
trust history for at least seven years and no less than consumer evidence
retention. Withdrawal may make a digest ineligible for new use while preserving
it as evidence.

See [Renderer identity v1](renderer-identity-v1.md),
[Consumer authority and private signing v1](consumer-authority-v1.md),
[Delivery lifecycle v1](delivery-lifecycle-v1.md), and
[Operational readiness v1](operational-readiness-v1.md) for the complete trust,
actor, recovery, and release-evidence requirements.
