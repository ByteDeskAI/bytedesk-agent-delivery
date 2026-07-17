# Trust policy v1

**Logical contract:** `bytedesk.trust-policy/1`

**Status:** Accepted contract; its Draft 2020-12 schema, profile source, and
contract fixtures are frozen by AD-01. Product and consumer KMS ceremonies,
trust Adapters, key operations, and measured conformance evidence remain
later-task GA gates.

## Purpose

A trust policy tells a verifier which independently configured identity may
sign which exact artifact or evidence type under which claims. An artifact,
binding, renderer, skill, event, or customization cannot supply, extend, or
weaken the policy that validates it.

This contract adopts the consumer-sovereign topology in
[Consumer authority and private signing v1](consumer-authority-v1.md), product
code identity in [Renderer identity v1](renderer-identity-v1.md), and exact
schema distribution in [Machine contracts v1](machine-contracts-v1.md).

> **Non-normative implementation note:**
> [ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
> fixes the first KMS/workload-identity and production deployment profile.
> Alternative KMS Adapters remain conforming only with immutable key-version,
> purpose, workload, consumer-isolation, audit, rotation, and denial evidence.

## Immutable policy record

Every policy is a closed JSON Schema Draft 2020-12 object with:

- stable policy ID and logical version;
- exact schema `$id` and digest;
- RFC 8785 canonical policy digest and effective window;
- allowed repositories, media types, consumers, targets, and artifact scopes;
- immutable KMS key-version resources and accepted algorithms;
- exact workload identities plus WIF/OIDC issuer, audience, subject, repository,
  workflow, ref, environment, builder, and subject constraints;
- required schema, provenance, SBOM, vulnerability/license, compatibility,
  evaluation, authority, skill-approval, canary, and readiness evidence;
- freshness, nonce, predecessor, downgrade, withdrawal, and outage rules;
- revoked key versions, digests, workflows, builders, schemas, renderers, and
  content; and
- fail-closed behavior.

The verifier receives policy through an independently authenticated channel and
checks the exact ID and digest asserted by a descriptor. The artifact cannot
provide policy bytes or redirect the verifier to another version. Runtime
network schema or policy fetching is forbidden.

Changing a key set, claim, repository, predicate, freshness rule, revocation, or
outage rule creates a new immutable policy digest. `current` and `next` are
separate snapshots with explicit overlap windows, not mutable members edited in
place. Historical receipts retain the exact policy digest and evaluation time.
New activation always uses current policy.

If authored in constrained YAML, the authoritative policy is still the
validated JSON data model serialized under
[Canonical encoding v1](canonical-encoding-v1.md). Authored bytes may have a
provenance-only storage checksum but never policy or activation authority.

## Required purpose profiles

Production v1 has six purpose-separated roles:

1. `product-release-v1` signs Agent Delivery product distributions, signed
   contract bundles, compiled renderer allowlists, and renderer releases.
2. `public-source-v1` signs catalogs, public Agent Spec sources, and public
   skill packages.
3. `public-render-v1` signs tenant-free public render outputs.
4. `consumer-private-skill-v1` signs consumer-private skill publication.
5. `consumer-authority-v1` signs consumer authority snapshots, exact skill
   approvals, and consumer business-approval evidence.
6. `consumer-deployment-v1` signs private deployments and runtime releases.

One signature is valid only for its configured purpose, media type, repository,
consumer, subject, target, workflow, and evidence set. A cryptographically valid
signature from another purpose does not satisfy policy.

Roles 4 through 6 are isolated per consumer. Authority/approval and deployment
signing use different keys and workload identities so a compromised compiler
cannot approve itself. A shared provider key for multiple consumers, exported
CI key, runtime-held private key, or provider-controlled mutable private trust
root is forbidden.

## Consumer sovereignty

The preferred private topology uses non-exportable asymmetric KMS keys in the
consumer's cloud account or security boundary. The consumer owns key lifecycle
and policy. An Agent Delivery build/compiler/publication workload may receive
only the exact role-4 private-skill or role-6 deployment sign operation. It
never receives role-5 authority/approval signing; only the independently
authenticated Consumer Authority Adapter may issue that evidence. Short-lived
WIF/OIDC federation supplies identity, and Agent Delivery cannot administer,
export, rotate, or change policy for the key.

A tenant-dedicated managed KMS/HSM key is conforming only when the consumer opts
in, independently pins immutable versions and claims, can revoke trust without
provider cooperation, receives complete audit, and can migrate to a consumer-
owned key without rewriting history. It remains isolated to one consumer.

An independent private-skill supplier may add its own provenance signature only
when the consumer independently configures a policy for the exact repository,
key, media type, evidence, and scope. A supplier signature never satisfies
`consumer-private-skill-v1`: the exact unchanged digest must also be published
or mirrored with the consumer's isolated role-4 signature. Current role-5
consumer-issued skill-approval evidence is independently mandatory; neither
publication signature authorizes execution.

## Product and renderer trust

`product-release-v1` binds product distributions and renderer releases to exact
source, build, dependency, toolchain, schema, platform, executable, embedded
allowlist, normalization, SBOM, vulnerability/license, deterministic-output,
and in-toto/SLSA provenance digests. Renderer releases target SLSA Build Level
3. A version, source commit, image tag, PATH binary, or local build never
satisfies execution trust.

For the v1 keyless contract-bundle release profile, policy identifies the exact
SHA-pinned called reusable signer workflow as the Fulcio certificate identity.
It separately pins the caller repository, immutable release-tag ref, source
commit, `workflow_dispatch` trigger, OIDC issuer, destination repository,
contract trust-policy ID/digest, sealed-verifier image digest, Cosign executable
digest, and trusted-root bytes/digest. The sealed verifier digest is the
`builderDigest`; it is not interchangeable with the Cosign digest. OIDC audience
and protected-environment restrictions are issuance controls and must not be
claimed as post-hoc certificate evidence unless the accepted certificate
profile actually carries them.

Candidate code executes only in an unprivileged build job. The OIDC-capable
signer performs no checkout and accepts only a closed candidate file set plus
independent protected configuration. Through its own read-only SCM authority it
must obtain the exact commit metadata and bounded source snapshot without
forwarding credentials to the snapshot host or extracting on the signer host.
The exact protected verifier image must safely validate source paths, types and
resource bounds, validate commit metadata before extraction, recompute and
match the Git tree, rebuild from source with trusted code, and require exact
candidate bundle/manifest equality in both the pre- and post-signature phases.
Evidence binds commit, tree, snapshot, metadata, rebuild, candidate, and tool
digests. An unpinned called workflow, mutable or absent verifier, caller or
candidate-provided command, source/tree/rebuild mismatch, missing post-sign
certification, or mismatch in any identity, source, tool, root, policy, or
evidence binding is terminal.

The running distribution may restrict its compiled renderer set through
independent policy. No runtime configuration or artifact may broaden it. A
withdrawn renderer blocks new render/compile; a revoked renderer or product
distribution blocks new activation. Forward recovery never executes revoked
tooling and requires a new current trusted public-render lineage.

## Consumer authority and approval verification

Compilation, activation, and recovery verify a short-lived
`bytedesk.consumer-authority/1` snapshot against the per-consumer authority
purpose, including audience, operation, nonce, consumer, subject, installation,
target, candidate, desired revision, predecessor, opaque authority subdigests,
and time window. Activation and recovery require a newly verified snapshot; a
compilation snapshot is not standing authority.

Each effective skill verifies separate `bytedesk.skill-approval/1` evidence for
its exact descriptor, consumer, subject, installation, target class, use scope,
policy, approver, validity, revocation, and replacement state. Call-time
authorization remains mandatory after activation.

## Key lifecycle

- Keys are non-exportable KMS/HSM asymmetric signing keys.
- Workloads authenticate through short-lived WIF/OIDC federation.
- Policies pin immutable key versions, not aliases.
- Private material never enters secret managers, CI variables, build output,
  runtime hosts, agent workspaces, or logs.
- Rotation publishes a distinct `next` snapshot, verifies intended overlap,
  switches publication explicitly, and retires the previous snapshot without
  rewriting historical evidence.
- Compromise revokes key and builder claims, blocks new affected activation,
  evaluates impacted digests, and triggers current-trusted rebuild or
  republication where content remains eligible.
- Consumer-key migration creates new policy and signer lineage while preserving
  old receipts and policy snapshots for historical verification.

## Verification sequence

Before import, compilation, desired-state publication, activation, or recovery,
the verifier:

1. resolves exact repository/digest/media-type/size and policy ID/digest;
2. validates the exact offline schema and RFC 8785 object identity;
3. verifies purpose, consumer isolation, immutable key version, claims,
   signature, effective window, withdrawal, and revocation;
4. verifies required provenance, SBOM, compatibility, evaluation, authority,
   skill approval, canary, and readiness predicates;
5. follows every explicit cross-repository descriptor and repeats validation;
6. checks consumer, subject, installation, target, slot/generation, candidate,
   desired revision, absent-or-match precondition, nonce, and freshness;
7. rejects any unexpected or stale edge; and
8. records the exact trust and evidence graph in append-only receipts.

Repository-local replay files are permitted only for explicit test and Adapter
conformance profiles and never issue production authority. Production signing
or verification atomically and durably consumes request ID, nonce, and request
digest under one shared uniqueness boundary before issuing authoritative
evidence. Reuse of any key, malformed history, or inability to reach that
boundary fails closed; recovery creates a fresh request and nonce.

The Promotion Coordinator alone may use successful evidence to advance target
desired state. A Host Reconciler observation, Consumer Capability Verifier
result, signature, approval, or receipt cannot promote itself.

## Failure and outage behavior

Unknown or revoked keys, wrong purpose, shared private signer, wrong consumer,
repository, workflow, environment, subject, media type, target, schema, renderer,
policy digest, missing evidence, stale snapshot, replay, downgrade, withdrawal,
or content substitution is terminal for new work. Verification never falls back
to authored YAML, a mutable alias, old authority, another installed renderer,
or an artifact-supplied policy.

An already active locally verified release may continue during registry, KMS,
consumer-authority, or control-plane outage only under documented consumer
incident policy. New import, compile, sign, approval, activation, recovery, or
key rotation fails closed.

## Transparency, privacy, retention, and readiness

Public product, contract, source, skill, renderer, and render provenance may use
public transparency services. Consumer-private skills, bindings, authority,
approvals, canary evidence, effective renders, deployments, and runtime targets
remain private unless the consumer explicitly accepts disclosure.

Hosts receive trust policy through an independently authenticated consumer
channel. Contract bundles, renderer manifests, policy snapshots, signatures,
attestations, and receipts needed for historical verification remain available
for at least seven years and never less than consumer evidence retention.

Production readiness requires consumer-owned and tenant-dedicated hosted-key
conformance, cross-consumer denial, key rotation/revocation/migration drills,
restore validation, fifteen-minute authorized compromise blocking, complete
audit, privacy/redaction tests, and the evidence in
[Operational readiness v1](operational-readiness-v1.md).
