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
schema distribution in [Machine contracts v1](machine-contracts-v1.md). Release
eligibility, evidence roles, and fresh status-head verification are defined in
[Release qualification and status v1](release-qualification-v1.md).

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
- an explicit signer `credentialKind`: immutable KMS key-version and public-key
  digests for `kms_key`, or exact Sigstore trusted-root bytes/digest for
  `sigstore_keyless`, plus accepted algorithms;
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

Production v1 has six organizational ownership domains implemented as 22
closed wire purposes:

1. Product/publication ownership uses `product-release-v1`,
   `contract-bundle-release-v1`, `public-source-v1`, and `public-render-v1`.
2. Consumer-private ownership uses `consumer-private-skill-v1`,
   `consumer-authority-v1`, `consumer-deployment-v1`, and the distinct
   `consumer-runtime-release-v1` root, plus
   `consumer-release-status-eligibility-v1` for private compilation/activation
   freshness and `consumer-activation-authorization-v1` for the Coordinator's
   exact-graph activation capability.
3. Qualification ownership uses `release-qualification-policy-v1`,
   `release-qualification-attempt-v1`,
   `release-qualification-receipt-v1`,
   `release-qualification-evidence-v1`, and
   `release-qualification-decision-v1`.
4. Current-eligibility ownership uses `release-status-v1` for the append-only
   status revision and `release-status-head-v1` for the fresh, nonce-bound head
   checkpoint, plus `release-status-eligibility-v1` for product-owned
   qualification, finalization, and publication stages.
5. Renderer execution ownership uses `renderer-attempt-v1` and the distinct
   `renderer-execution-v1` receipt.
6. Private compilation ownership uses `consumer-compilation-input-v1` for the
   exact locked input and `consumer-compilation-evidence-v1` for the separate
   compiler evidence statement.

One signature is valid only for its configured purpose, media type, repository,
consumer, subject, target, workflow, and evidence set. A cryptographically valid
signature from another purpose does not satisfy policy.

Consumer-private purposes are isolated per consumer. Authority/approval,
private-skill publication, deployment, runtime release, private-stage status
eligibility, activation authorization, compilation input, and compilation
evidence signing use different keys and workload identities so a compromised
compiler or Coordinator cannot approve itself. A shared provider key for multiple consumers, exported
CI key, runtime-held private key, or provider-controlled mutable private trust
root is forbidden.

## Consumer sovereignty

The preferred private topology uses non-exportable asymmetric KMS keys in the
consumer's cloud account or security boundary. The consumer owns key lifecycle
and policy. An Agent Delivery build/compiler/publication workload may receive
only the exact private-skill, deployment, runtime-release, or compilation
purpose explicitly granted to that workload. It never receives
`consumer-authority-v1` signing; only the independently
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
or mirrored with the consumer's isolated private-skill signature. Current
`consumer-authority-v1` consumer-issued skill-approval evidence is independently
mandatory; neither publication signature authorizes execution.

## Product, contract-bundle, and renderer trust

`product-release-v1` binds product distributions, renderer releases, and
product-owned evaluator/build-tool distributions to exact source, build,
dependency, toolchain, schema, platform, executable, embedded allowlist,
normalization, SBOM, vulnerability/license, deterministic-output, and
in-toto/SLSA provenance digests. Renderer releases target SLSA Build Level 3.
A version, source commit, image tag, PATH binary, or local build never satisfies
execution trust.

`product-release-v1` and `contract-bundle-release-v1` always select separate
immutable policy records. The product policy is `kms_key`-only and scopes
product distributions, compiled allowlists, renderer releases, and exact
product-owned evaluator/build-tool media. An evaluator descriptor carries that
independently resolved product-policy ID and digest; it never inherits the
trust policy of the subject it evaluates. The
contract-bundle policy is `sigstore_keyless`-only and scopes only the exact
contract repository and `application/vnd.bytedesk.agent.contract-bundle.v1+json`
media type. A policy that includes both purposes, both credential kinds, or the
other policy's repository/media scope is invalid for either release path.

The product release pins an immutable release-qualification policy and suite.
That policy requires provenance, SBOM, vulnerability, license, compatibility,
conformance, determinism, malware, secret-scan, scan-completeness, sandbox,
executed-distribution, and product-distribution evidence for the applicable
product, renderer, executable, contract, and platform subjects. A requirement
becomes available only after one unique `passed`, typed, purpose-signed evidence
leaf resolves to the exact bytes and its subject, policy, inventory, coverage,
material, evaluator, and cross-report bindings validate. Missing, duplicate,
failed, inapplicable where required, stale, incomplete, or digest-mismatched
evidence fails closed. The repository harness is conformance only and cannot
issue authority; production qualification evidence, predicates, trees,
receipts, decisions, and status heads are independently authenticated and
resolved by exact descriptors.

For the v1 keyless `contract-bundle-release-v1` profile, policy identifies the
exact SHA-pinned called reusable signer workflow as the Fulcio certificate identity.
It separately pins the caller repository, immutable release-tag ref, source
commit, `workflow_dispatch` trigger, OIDC issuer, destination repository,
contract trust-policy ID/digest, sealed-verifier image digest, Cosign executable
digest, and trusted-root bytes/digest. The sealed verifier digest is the
`builderDigest`; it is not interchangeable with the Cosign digest. OIDC audience
and protected-environment restrictions are issuance controls and must not be
claimed as post-hoc certificate evidence unless the accepted certificate
profile actually carries them.

This profile uses `credentialKind: sigstore_keyless`. It has no KMS
`keyVersion` and does not pin the ephemeral Fulcio leaf public key. Instead,
the signed request binds the exact domain-separated `signerIdentityDigest`,
the sealed-verifier `builderDigest`, and the digest of the complete pre-sign
certification. Verification obtains trusted-root bytes independently, matches
their digest to the selected policy signer, authenticates the request through
that root and exact certificate identity, resolves the pre-sign certification,
and requires its executed-distribution builder digest to match both policy and
request. Policy text alone is never reported as authenticated signer or
builder-execution evidence.

The product-release manifest embeds the resulting closed
`contractBundleVerification` receipt and its exact signing-request and Sigstore
bundle evidence-blob descriptors. The receipt has `authorityIssued: false` and
is covered by the later product-release authority digest. Every downstream and
private verifier must resolve the contract bytes and policy independently,
replay the keyless Adapter over the complete identity/root/workflow/claims/
builder/certification/request/bundle context, and require the exact receipt.
The enclosing KMS product signature is not contract-bundle signature evidence.

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

- KMS credentials use non-exportable KMS/HSM asymmetric signing keys. Policy
  pins immutable `keyVersion` and `publicKeyDigest`, never an alias.
- Sigstore keyless credentials bind the exact `signerIdentityDigest` and an
  independently pinned `trustedRootDigest`; they forbid `keyVersion` and a
  static leaf `publicKeyDigest`.
- Workloads authenticate through short-lived WIF/OIDC federation.
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
3. verifies purpose, consumer isolation, and the credential-aware signer
   identity: immutable `keyVersion` plus `publicKeyDigest` for KMS, or exact
   `signerIdentityDigest` plus independently pinned `trustedRootDigest` and no
   static leaf or `keyVersion` for Sigstore keyless; it then verifies claims,
   signature, effective window, withdrawal, and revocation;
4. verifies the exact qualification policy, suite, complete evidence tree,
   predicates, final decision, and required product/renderer/platform matrix;
5. obtains and verifies a caller-nonce-bound, time-valid, authenticated current
   status-head checkpoint and any required append-only consistency proof;
6. verifies authority, skill approval, canary, and readiness predicates;
7. follows every explicit cross-repository descriptor and repeats validation;
8. checks consumer, subject, installation, target, slot/generation, candidate,
   desired revision, absent-or-match precondition, nonce, and freshness;
9. rejects any unexpected or stale edge; and
10. records the exact trust and evidence graph in append-only receipts.

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
policy digest, missing evidence, stale snapshot or status checkpoint, wrong
status nonce, status rollback/fork, replay, downgrade, withdrawal, revocation,
end of support, or content substitution is terminal for new work. Verification never falls back
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
