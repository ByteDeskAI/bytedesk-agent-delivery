# OCI media types v1

**Status:** Accepted contract registry; its media types, manifest schemas, and
contract fixtures are frozen by AD-01. Registry publication, OCI and signing
Adapters, KMS integration, lifecycle services, and measured operational
evidence remain later-task GA gates.

## Artifact and evidence types

| Artifact or evidence | `artifactType` |
|---|---|
| Contract bundle | `application/vnd.bytedesk.agent.contract-bundle.v1+json` |
| Product distribution | `application/vnd.bytedesk.agent.product-distribution.v1+json` |
| Product release manifest | `application/vnd.bytedesk.agent.product-release-manifest.v1+json` |
| Renderer allowlist | `application/vnd.bytedesk.agent.renderer-allowlist.v1+json` |
| Renderer release | `application/vnd.bytedesk.agent.renderer-release.v1+json` |
| Release-qualification policy | `application/vnd.bytedesk.agent.release-qualification-policy.v1+json` |
| Renderer-qualification suite | `application/vnd.bytedesk.agent.renderer-qualification-suite.v1+json` |
| Renderer-qualification selection | `application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json` |
| Renderer-qualification attempt | `application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json` |
| Qualification-attempt authentication | `application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json` |
| Renderer-qualification evidence tree | `application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json` |
| Renderer-qualification receipt | `application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json` |
| Qualification-receipt authentication | `application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json` |
| Release-qualification evidence | `application/vnd.bytedesk.agent.release-qualification-evidence.v1+json` |
| Release-qualification finalization matrix | `application/vnd.bytedesk.agent.release-qualification-finalization-matrix.v1+json` |
| Release-qualification predicate | `application/vnd.bytedesk.agent.release-qualification-predicate.v1+json` |
| Release-qualification decision | `application/vnd.bytedesk.agent.release-qualification.v1+json` |
| Release status | `application/vnd.bytedesk.agent.release-status.v1+json` |
| Status-log inclusion proof | `application/vnd.bytedesk.agent.release-status-log-inclusion-proof.v1+json` |
| Status-log consistency proof | `application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json` |
| Status-head checkpoint | `application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json` |
| Status-head authentication | `application/vnd.bytedesk.agent.release-status-head-authentication-evidence.v1+json` |
| Stage-specific release-status eligibility | `application/vnd.bytedesk.agent.release-status-eligibility-evidence.v1+json` |
| Status-append resolution | `application/vnd.bytedesk.agent.release-status-append-resolution.v1+json` |
| Catalog index | `application/vnd.bytedesk.agent.catalog.v1+json` |
| Agent source | `application/vnd.bytedesk.agent.source.v1+json` |
| Skill package | `application/vnd.bytedesk.agent.skill.v1+json` |
| Renderer selection | `application/vnd.bytedesk.agent.renderer-selection.v1+json` |
| Renderer attempt authority | `application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json` |
| Renderer-attempt authentication | `application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json` |
| Renderer execution receipt | `application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json` |
| Renderer-execution authentication | `application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json` |
| Render manifest | `application/vnd.bytedesk.agent.render-manifest.v1+json` |
| Harness render | `application/vnd.bytedesk.agent.render.v1+json` |
| Registry publication evidence | `application/vnd.bytedesk.agent.publication-evidence.v1+json` |
| Consumer authority snapshot | `application/vnd.bytedesk.agent.consumer-authority.v1+json` |
| Skill approval | `application/vnd.bytedesk.agent.skill-approval.v1+json` |
| Private-compilation input | `application/vnd.bytedesk.agent.private-compilation-input.v1+json` |
| Private-input authentication bundle | `application/vnd.bytedesk.agent.private-input-authentication.v1+json` |
| Consumer deployment | `application/vnd.bytedesk.agent.consumer-deployment.v1+json` |
| Private-compilation evidence | `application/vnd.bytedesk.agent.private-compilation-evidence.v1+json` |
| Runtime release | `application/vnd.bytedesk.agent.runtime-release.v1+json` |
| Activation authorization | `application/vnd.bytedesk.agent.activation-authorization.v1+json` |
| Target delivery state | `application/vnd.bytedesk.agent.target-delivery-state.v1+json` |
| Canary plan | `application/vnd.bytedesk.agent.canary-plan.v1+json` |
| Canary evidence | `application/vnd.bytedesk.agent.canary-evidence.v1+json` |
| Authorization decision proof | `application/vnd.bytedesk.agent.authorization-decision-proof.v1+json` |
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
digest. It is signed only under the Sigstore-keyless
`contract-bundle-release-v1` purpose and its exact contract-bundle policy, then
retained for historical verification. That policy is separate from the
KMS-only `product-release-v1` policy used by product distributions, compiled
allowlists, and renderer releases; neither policy may accept the other's
purpose, signer, repository, or media type.

The shared artifact-descriptor grammar enforces this split even inside
polymorphic subject and evidence fields: canonical contract-bundle JSON and
`contract-bundle-release-v1` must occur together, and the legacy tar media type
is invalid for every artifact descriptor. Every named `contractBundle` role uses the closed
`contractBundleDescriptor`; the bundle manifest root and each schema member
also carry that fixed policy ID. Exact signing-request and signature-bundle
payloads inside independent verification receipts use the closed four-field
`evidenceBlobDescriptor`; it has no trust-policy reference, confers no
authority, and must be resolved and authenticated by the trusted Adapter. The
tar media type remains a fail-closed legacy classification and is never an
authoritative descriptor.

The renderer-release manifest is the primary renderer identity. It binds
harness/renderer IDs, immutable semantic and contract versions, source and
build inputs, every platform executable/worker descriptor, compiled allowlist,
renderer-owned schema descriptors, normalization, SBOM, vulnerability/license,
compatibility, deterministic-output, and in-toto/SLSA evidence. The actual
executed distribution/platform digest is also recorded in each render. A
version string or image tag is never renderer authority.

The product release pins the exact qualification policy, suite, minimum
coverage, renderer releases, and executable platforms. Qualification attempts,
receipts, evidence trees, predicates, and the final decision are separate
purpose-authenticated objects. Release status is a separate append-only chain;
each consuming operation obtains a fresh nonce-bound status-head checkpoint and
authentication evidence. The exact graph and freshness rules are in
[Release qualification and status v1](release-qualification-v1.md).

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
skill plus the exact product release, qualification decision, renderer release,
selection, issued attempt, authenticated actual execution, render manifest,
actual executing product distribution/platform, embedded allowlist,
renderer-owned schemas, normalized parameters, compatibility result, output
archive/layer, and file inventory. It carries a schema-owned authority digest
and complete `public-render-v1` signing result. It accepts no binding, private
skill, consumer identifier, authority snapshot, opaque secret reference, or
private customization.

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
manifest, exact runtime-file payload descriptor, and authenticated renderer
execution lineage. It is signed under a per-consumer
`consumer-deployment-v1` key; a provider-wide shared private-deployment signer
is forbidden.

The effective render reconstructs and revalidates the complete Agent Spec and
fully invokes the same exact current trusted renderer release recorded by its
public lineage. It never patches a public render. V1 has no private-render media
type. Exact public bytes may be reused only when customization is empty and all
schema, source, skill, renderer release, execution variant, allowlist,
parameter, and normalized inputs match.

A runtime release aggregates, for each subject, the exact canonical deployment
descriptor and the separate exact private-compilation-evidence descriptor for
one target, identifies any system package, and binds activation constraints. It
is signed with `consumer-runtime-release-v1`. A compiler prepares it but cannot
make it desired state.

Compilation and activation obtain independent fresh release-status eligibility;
they never reuse selection or render checkpoints. Private-stage eligibility is
signed with the consumer-scoped `consumer-release-status-eligibility-v1`
purpose. Immediately before activation, the Promotion Coordinator resolves the
complete runtime-release graph and issues a short-lived
`consumer-activation-authorization-v1` signature over the exact rollout,
attempt, graph, authority, candidate-ready evidence, eligibility, generations,
fencing token, region epoch, and expiry. The Host verifies the complete object;
the authorization digest alone is not a resolvable or sufficient authority.

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

A capability decision references an exact consumer-private authorization
decision proof. The proof binds the plan, capability, current policy, grants,
workload identity, exact decision, signer policy, freshness, and an explicitly
authenticated, completed, parsed successful transport response. A timeout,
transport failure, `404`, parser error, or unavailable tool is not denial
evidence. Promotion requires fresh matching evidence from both actors, except
an independently authenticated `not_applicable` certification from a certified
no-capability profile.

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

Verification recursively resolves every authoritative descriptor and every OCI
manifest/config/layer/blob edge. It verifies repository, digest, media type,
size, expected semantic role, exact policy, schema, signature, and resolved
bytes before following children. A repository-name prefix is never a type
system. Missing config or layer content, an unregistered media/role pair,
duplicate semantic role, cycle, tag-only edge, or bounded-traversal violation
fails closed.

## Deterministic layers and failure behavior

Archive layers fix file order, normalized paths, timestamps, declared safe
modes, ownership class, compression algorithm, and parameters. Contract role
and media type—not `.json`, `.yaml`, or `.yml`—select structured parsing.
Arbitrary payload files preserve exact raw bytes without decoding,
transcoding, or line-ending normalization.

Unknown schema, descriptor, trust-policy digest, signer purpose, renderer
release, qualification evidence, status checkpoint, executing distribution,
authority snapshot, skill approval, precondition, evidence actor, nonce, or
graph edge is terminal. A verifier never
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
[Release qualification and status v1](release-qualification-v1.md),
[Consumer authority and private signing v1](consumer-authority-v1.md),
[Delivery lifecycle v1](delivery-lifecycle-v1.md), and
[Operational readiness v1](operational-readiness-v1.md) for the complete trust,
actor, recovery, and release-evidence requirements.
