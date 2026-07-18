# Release qualification and status v1

**Status:** Accepted normative contract

This standard defines how a product release and every renderer executable it
contains become qualified for use, how later withdrawal or revocation is
represented, and how a caller proves that it observed a fresh, non-rollback
status head immediately before selection or execution. It is an evidence and
eligibility protocol. It does not authorize a consumer, grant a capability,
create an identity, or replace consumer policy.

The source of truth for object shape is the closed Draft 2020-12 schemas in
`contracts/schemas/v1/`. The source of truth for actor operations and failure
semantics is `contracts/ports/v1/port-registry.json`. This document fixes the
cross-object meaning that cannot be expressed by either schema validation or a
single port request alone.

## Three independent decisions

A release is usable only when all three decisions succeed independently:

1. **Trust:** every authoritative object and referenced artifact has an exact
   descriptor, an allowed purpose-specific signature, and an independently
   supplied immutable trust policy.
2. **Qualification:** the exact product release, every declared renderer
   release, and every required executable platform have complete, current,
   policy-satisfying evidence produced by the pinned qualification suite.
3. **Current status:** the caller has a fresh, nonce-bound, authenticated view
   of the append-only status head and has proved that the view is not a fork or
   rollback from its prior accepted head.

A valid signature does not prove qualification. A qualification decision does
not prove that the subject remains current. A current status does not repair a
missing signature, evidence leaf, renderer platform, or consumer authorization.

## Signed release roots

The signed product distribution, product release, renderer allowlist, renderer
release, release qualification, and release status objects each carry a
schema-owned `authorityDigest` and a complete `signingResult`. The authority
digest is SHA-256 over the object's exact RFC 8785 preimage selected by its
schema metadata. Self-referential authority fields are excluded from that
preimage; no object may obtain authority from a digest that contains itself.

The product release pins all of the following by exact descriptor or digest:

- the product distribution and compiled renderer allowlist;
- the contract bundle and schema inventory;
- the qualification policy and qualification suite;
- the minimum required qualification-coverage digest; and
- every renderer release and executable distribution eligible for that product
  release.

Tags, channels, version strings, source commits, and trust-policy references are
discovery or policy-selection metadata. None is a signature or release root.
Verification resolves the complete object, recomputes its schema-owned digest,
verifies the purpose-specific signing result, and recursively verifies every
authoritative descriptor.

## Qualification policy and suite

`bytedesk.release-qualification-policy/1` is immutable and purpose-signed. It
pins exactly one qualification suite, its required-coverage digest, whether
every renderer release and every renderer platform are mandatory, evidence
expiry behavior, the decision rule, and an independently supplied trust-policy
reference. The production profile requires every declared renderer release and
every supported server platform and does not accept expired evidence.

`bytedesk.renderer-qualification-suite/1` fixes the executable test meaning. It
pins:

- the required evidence roles and per-subject coverage matrix;
- the conformance plan and input corpus;
- evaluator and contract-bundle distributions, each with its independently
  resolved trust-policy reference;
- qualification worker and framed-protocol profiles;
- sandbox, resource, and timeout profiles; and
- the trust policy under which its outputs are verified.

The policy, suite, and minimum-coverage values carried by a product release and
release qualification must agree exactly. An evaluator is a separately released
product tool and must resolve under its exact product-release policy scope; it
never acquires or copies the policy of an evaluated contract, renderer, or other
subject. A producer cannot replace a suite, reduce a role matrix, omit a
renderer platform, reinterpret `not_applicable`, or use a policy with a merely
similar name.

## Qualification execution chain

Qualification uses the same Strategy, Adapter, and sandbox boundaries as
rendering but has a separate purpose and evidence graph:

1. The qualifier resolves the signed product release, renderer release,
   executable distribution, policy, suite, conformance plan, input corpus,
   evaluator, contract bundle, and all profile digests.
2. It creates one closed qualification selection for the exact renderer release
   and operating-system/architecture tuple. Selection never uses ambient host
   architecture, a tag, `PATH`, a plugin, or artifact-provided code.
3. A purpose-separated issuer creates and signs one expiring, fenced
   qualification attempt. The exact length-prefixed RFC 8785 request frame and
   input tree are stored and bound by digest.
4. The signed launcher executes the pinned evaluator once in the declared
   networkless sandbox. It returns the exact response frame, typed evidence
   tree, and qualification receipt. The receipt binds the unchanged selection,
   attempt, executable, platform, inputs, outputs, profiles, launcher identity,
   and completion time.
5. Independent authentication evidence proves the attempt and receipt signing
   purposes, subjects, keys, workload identities, repositories, workflows, and
   trust policies. A receipt or evidence-tree digest alone is insufficient.
6. A qualification finalizer validates the complete tree, emits the exact
   evidence objects and predicates, and produces one signed qualification
   decision only after every required matrix cell passes.

The declared ports return complete typed objects, descriptors, framed bytes,
and authentication evidence needed by the next step. A fixture generator or
test-only in-memory object is not a production construction path.

## Typed evidence tree and predicates

The evidence tree contains one signed leaf for each required
`requirementId`/evidence-role/subject-role/subject tuple. Supported evidence
roles are:

- provenance;
- SBOM;
- vulnerability;
- malware;
- secret-scan and scan-completeness;
- license;
- conformance;
- compatibility;
- determinism;
- sandbox;
- executed distribution; and
- product distribution.

Each leaf binds its statement digest, exact signing result, subject descriptor,
role, requirement, result, producer, and time. The tree digest binds the ordered
leaf set, exact qualification selection, suite, attempt authority, platform,
executed distribution, collector, and production time. Leaves are unique and
complete for the required matrix; a passing duplicate cannot mask a missing or
failing cell.

Every `bytedesk.release-qualification-evidence/1` object identifies an exact
leaf index, leaf digest, leaf statement digest, and leaf signing result. Its
predicate is a closed object governed by the exact `predicateContract` and
`predicateSchema` descriptors carried by the evidence. The verifier resolves
that schema offline and proves its exact ID and digest before validation. A
caller cannot substitute another schema that happens to accept the same JSON.

The final `bytedesk.release-qualification/1` decision binds the exact product
release, complete renderer-release set, all evidence descriptors, policy,
decision, qualification time, expiry, trust policy, authority digest, and
purpose-specific signing result. Qualification fails closed on any absent,
expired, duplicated, untrusted, wrong-subject, wrong-platform, wrong-role,
wrong-schema, or non-passing required evidence.

## Append-only release status

Qualification is immutable evidence about an exact subject. Later eligibility
changes are represented by an append-only chain of
`bytedesk.release-status/1` objects. A status subject is an exact product or
renderer release descriptor. Each status binds a monotonic sequence, exact
predecessor digest, state, reason, effective time, trust policy, authority
digest, and `release-status-v1` signing result. The allowed states are
`current`, `withdrawn`, `revoked`, and `end_of_support`.

Changing status never edits or deletes a release, qualification, signature, or
prior status. Recovery, reinstatement, or a replacement is a new forward
revision under policy. A status object supplied by the artifact under
evaluation cannot bootstrap current eligibility.

## Fresh authenticated status heads

Before renderer description, selection, qualification, rendering, compilation,
publication, or activation uses a release, the caller supplies a fresh random
request nonce and its prior accepted state for that subject. The status
authority returns:

- the exact signed current status object;
- a closed `bytedesk.release-status-head-checkpoint/1` bound to that request
  nonce, subject, sequence, status-head descriptor/digest, authority epoch,
  append-only log root, caller prior state, verification time, expiry, and
  trust policy;
- a `release-status-head-v1` authentication-evidence object that binds the
  exact checkpoint digest, request nonce, authority identity, complete signing
  result, and evidence digest; and
- when the head advances, an authenticated consistency proof whose exact
  `from` and `to` endpoints bind the prior and returned subject, sequence,
  epoch, head, and log root.

On first contact, the caller declares `clientPriorState: none`; a valid current
head may have any positive sequence. On refresh with an unchanged head, the
same sequence, epoch, head, and log root must match exactly and no advancement
proof is accepted. On advancement, the sequence and epoch are monotonic, the
proof endpoints match both states exactly, and the proof data demonstrates the
new root is an append-only extension of the accepted root. A different head or
root at the same sequence/epoch is a fork.

The consuming operation verifies that:

- the checkpoint nonce equals the nonce it generated for this operation;
- `verifiedAt` is not in the future and the operation time is strictly before
  `expiresAt`;
- the status, checkpoint, authentication evidence, and optional consistency
  proof resolve by exact descriptor and agree on subject, head, sequence,
  epoch, nonce, trust policy, and signer;
- the status is `current`; and
- the renderer attempt authority binds the exact accepted checkpoint and
  authentication-evidence digests so they cannot be swapped after selection.

A cached status descriptor, a checkpoint for another nonce, an expired or
future checkpoint, an arbitrary boolean assertion, or a proof for different
endpoints is not freshness evidence.

## Signer and workload separation

The six ownership domains in ADR-0001 are implemented as 22 closed wire
purposes rather than one reusable release signer:

- `product-release-v1`, `contract-bundle-release-v1`, `public-source-v1`, and
  `public-render-v1`;
- `consumer-private-skill-v1`, `consumer-authority-v1`,
  `consumer-deployment-v1`, and `consumer-runtime-release-v1`;
- `release-qualification-policy-v1`, `release-qualification-attempt-v1`,
  `release-qualification-receipt-v1`, `release-qualification-evidence-v1`, and
  `release-qualification-decision-v1`;
- `release-status-v1`, `release-status-head-v1`, and
  `release-status-eligibility-v1`;
- `renderer-attempt-v1` and `renderer-execution-v1`; and
- `consumer-compilation-input-v1` and
  `consumer-compilation-evidence-v1`,
  `consumer-release-status-eligibility-v1`, and
  `consumer-activation-authorization-v1`.

Each purpose has an immutable trust policy defining its credential-aware signer
identity, repository, subject media type, issuer/workload identity, workflow,
environment, audience, and validity rules. KMS policies pin exact key version
and public-key digest; keyless policies pin exact signer identity and
trusted-root digest without a static leaf key. The KMS-only
`product-release-v1` policy and
keyless-only `contract-bundle-release-v1` policy are distinct and may not mix
purpose, signer, repository, or media-type scope. Policy, qualification, status,
attempt, receipt, execution, and publication signers are independently
constrained. A conformance key may not satisfy production reachability, and a
single key/workload identity reused across prohibited purpose pairs fails
qualification.

Consumer-authority and consumer approval remain outside Agent Delivery. The
qualification and status services can report what exact product code was
tested and whether it remains eligible; they cannot authorize a consumer,
approve a skill, grant a tool, or weaken a consuming organization's security
controls.

## OCI graph verification

Qualification and current status apply to the complete artifact graph, not only
to a top-level manifest. The verifier walks every authoritative descriptor,
OCI manifest/config/layer descriptor, public render file/archive descriptor,
signature bundle, predicate, evidence tree, and policy/suite reference
recursively by exact digest, media type, size, repository, and expected role.
Each resolved byte sequence is independently hashed before parsing. Descriptor
cycles, duplicate semantic roles, unregistered media/role pairs, missing config
or layer blobs, tag-only references, unbounded traversal, and repository-prefix
type inference fail closed.

Public graph traversal must remain tenant-free. Consumer IDs, private skills,
bindings, secret references, authority snapshots, and private evidence are
permitted only in their consumer-private repositories and are never published
as qualification or public-render evidence.

## Failure behavior

The operation stops without publication, selection, compilation, or activation
when any required object, frame, blob, signature, role, matrix cell, platform,
status proof, or independent trust input is missing or inconsistent. It also
fails on:

- an invalid, unknown, revoked, wrong-purpose, wrong-workload, or reused signer;
- a product/renderer/policy/suite/coverage substitution;
- evidence expiry, a failing required result, duplicate coverage, or a
  predicate-schema substitution;
- an omitted renderer release or `linux/amd64`/`linux/arm64` executable;
- a stale, future-dated, wrong-nonce, rolled-back, forked, withdrawn, revoked,
  or end-of-support status head;
- an unconstructible object available only inside a test generator;
- an incomplete or cyclic OCI graph; or
- any public evidence containing consumer-private information.

There is no fallback to a locally installed renderer, a different platform, an
older qualified release, a mutable tag, a less complete suite, an expired
checkpoint, or an artifact-supplied trust policy.

## Required conformance

Release qualification cannot be represented as frozen until executable tests
prove at least:

- one complete product release with Native Agent Spec, Hermes, and OpenClaw
  renderer releases on both `linux/amd64` and `linux/arm64`;
- byte-identical cross-platform functional output with distinct platform-bound
  selection, execution, and manifest identities;
- complete required-role/subject/platform matrix coverage and every one-cell
  omission, duplicate, failure, expiry, and substitution denial;
- exact framed request/response, attempt, receipt, evidence-tree, predicate,
  decision, public-render, and publication construction through declared ports;
- first-contact, unchanged-head refresh, append-only advancement, wrong-nonce,
  expiry, future-time, rollback, fork, and mismatched consistency-proof cases;
- purpose, key, workload-identity, repository, subject, environment, audience,
  and prohibited signer-reuse denials;
- recursive OCI config/layer/blob closure, digest/size/media/role validation,
  cycle and tag-only denial; and
- tenant-free public qualification and render artifacts plus complete private
  compilation lineage without a public/private evidence leak.

The executable sources are the renderer digest cases, private compilation graph
cases, downstream port fixtures, protocol fixtures, and generated conformance
plan in `contracts/fixtures/`. The full repository gate must rebuild all derived
metadata and the offline contract bundle twice from a clean exact commit and
prove byte identity before the release-readiness evidence is accepted.
