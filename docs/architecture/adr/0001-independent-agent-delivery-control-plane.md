# ADR-0001: Independent Agent Delivery control plane

**Date:** 2026-07-16

**Status:** Accepted

**Decider:** Ryan Helms

**Repository:** `ByteDeskAI/bytedesk-agent-delivery`

## Context

Agent definitions are commonly authored in the format of the harness that runs
them. A single conceptual agent is copied into Hermes, OpenClaw, platform
database records, and other runtime-specific bundles. The copies drift, the
authoring authority becomes unclear, and a consumer cannot reproduce the exact
definition that produced a running workload.

A portable marketplace solves only discovery. A secure delivery mechanism must
also prove the source, renderer, policy inputs, tenant specialization, and
running output. At the same time, a public package must never acquire the power
to grant itself tools, credentials, resources, roles, or workload identity.

The product must support two equally important modes:

1. a clean third party can discover, validate, render, package, and verify an
   agent without any ByteDesk Platform service; and
2. a consuming platform can bind an exact agent definition to its own identity
   and policy, compile a private deployment, activate it safely, and reproduce
   the exact running state from receipts.

Agent Spec `26.1.2` is the selected portable definition standard. It provides
`Agent` and `SpecializedAgent`, but does not define the digest-pinned,
non-authorizing installation envelope required by a multi-tenant consumer.

OCI 1.1 supplies content addressing, subjects, and referrers. Referrer
discovery is repository-local, so public source artifacts and private consumer
deployments need explicit signed cross-repository descriptors.

## Decision

### 1. Independent product and repository

ByteDesk Agent Delivery is an independently deployable, headless product in
`ByteDeskAI/bytedesk-agent-delivery`. It exposes protocols, a reference control
plane, renderer tooling, a CLI, and runtime reconciliation interfaces.

Agent catalog content remains a replaceable Git source. The ByteDesk baseline
catalog will live in the definition-only
`ByteDeskAI/bytedesk-agent-marketplace` repository when its bootstrap workstream
is executed. Agent Delivery must accept another compatible catalog without code
changes. Only test fixtures belong in the product repository.

The product is usable without ByteDesk Platform. ByteDesk Platform is the first
consumer integration profile, not the product host or source of truth.

### 2. Authority boundary

| Concern | Authority |
|---|---|
| Reusable Agent Spec source, optional portable skills, catalog metadata | Catalog Git repository |
| Source and public-render publication | Catalog/delivery build identity |
| Catalog validation, deterministic rendering, OCI graph, promotion protocol | Agent Delivery |
| Installation identity, tenant specialization, desired runtime target | Consuming platform |
| Users, organizational agent identity, lifecycle, roles, grants, credentials | Consuming platform |
| Workload certificate/token and sender constraint | Consuming identity system |
| Call-time MCP/tool/provider/resource decision | Consuming authorization system |
| Artifact staging, activation, health evidence | Consumer-authorized runtime reconciler |
| Conversations, goals, tasks, and executable work | Consuming platform/runtime |

Agent Delivery signs and proves **what is deployed**. The consumer proves **what
that deployment may do**. Both decisions are required for activation.

Catalog identifiers, names, titles, and slugs are definition metadata. They do
not create an employee, workload principal, role, grant, credential, or
reporting relationship.

### 3. Canonical Agent Spec source

V1 accepts Agent Spec `26.1.2` `Agent` and `SpecializedAgent` documents. The
exact version is pinned and every document is validated with the official Agent
Spec SDK. A hand-written approximation is not accepted because a patch release
may be incompatible.

Portable packages use a logical default model. The consumer selects a concrete
model and provider. Public packages may contain behavior, descriptive metadata,
and optional inert skills. They may not contain:

- API keys, credentials, secret values, or secret references;
- tenant or consumer-specific identifiers;
- provider endpoints or provider grants;
- MCP servers, tool/resource grants, additional runtime tools, or toolboxes;
- workload, engine, profile, role, or identity bindings;
- remote executable URLs, install scripts, or artifact-provided hooks; or
- fields that weaken a consumer's approval policy.

Optional skills never block discovery, validation, or import. A consumer may
quarantine, omit, evaluate, or require approval for them independently.

OASF may be emitted as a signed discovery projection. It is never an authoring,
installation, or deployment authority.

The ByteDesk reference catalog contains 34 selectable employee-agent packages
and one non-selectable `office-orchestrator` system package. The system package
does not create an organizational identity or workload principal.

### 4. Constrained installation binding

A consumer stores `bytedesk.agent-binding/1`, not a copied base definition and
not a mutable branch or tag. The envelope includes:

- exact source repository and digest;
- exact Agent Spec version;
- allowlisted harness identifier and renderer version;
- non-authorizing additional instructions and metadata;
- release channel and compatible-update preference; and
- expected predecessor for compare-and-swap updates.

The allowlist rejects tools, MCP, resources, providers, roles, grants,
credentials, secrets, remote code, tenant escape fields, caller-supplied base
copies, mutable authority, or weaker human-in-the-loop behavior.

The renderer resolves the pinned source plus envelope into a complete official
Agent Spec `SpecializedAgent`. A full base copy exists only in deterministic
build output.

### 5. Renderer Strategy and Adapter boundary

Renderer selection uses Strategy. Each harness integration is an Adapter. The
initial Adapters are:

- native Agent Spec/WayFlow;
- Hermes; and
- OpenClaw.

The allowlisted registry is compiled into the trusted distribution. Runtime
plugin loading is forbidden. Adding a harness adds an Adapter and contract
tests; it does not modify canonical agent packages.

Every render emits a manifest containing source digest, Agent Spec version,
renderer identifier/version/digest, normalized parameters, compatibility
result, explicit loss/warnings, and output file digests. Unsupported semantics
fail or are reported as an explicitly approved lossy mapping; they are never
silently dropped.

Identical normalized inputs produce byte-identical output. Normalization fixes
file ordering, UTF-8 encoding, line endings, modes, ownership metadata,
timestamps, archive structure, and compression settings.

Packages, skills, archives, and OCI layers are untrusted inert data. Validators
and renderers never execute package content or fetch package-directed code.
They enforce file-count, path-depth, compressed/uncompressed-size, media-type,
mode, and decompression limits and reject absolute paths, traversal, symlinks,
hardlinks, devices, FIFOs, and archive bombs.

### 6. OCI artifact graph

Deployment authority is always an exact digest. SemVer, tags, and release
channels are discovery metadata.

V1 defines:

| Artifact | Visibility | Evidence |
|---|---|---|
| Signed catalog index | Public | Catalog digest, source descriptors, channel and withdrawal metadata |
| Agent source | Public | Canonical manifest and deterministic source layer |
| Harness render | Public | Source descriptor, renderer descriptor, deterministic render bundle |
| Consumer deployment | Private to consumer/tenant | Source/render descriptors plus binding, policy, authority, identity, and target subdigests |
| Signature, attestation, SBOM | Same repository as subject | OCI referrer to the exact local subject |
| Runtime release manifest | Private to consumer/runtime | Exact deployment subdigests and system-package digest |

The media-type namespace is `application/vnd.bytedesk.agent.*.v1`. Concrete
schemas and media types are frozen by contract tests before publication.

Subjects/referrers are used within one repository. Every cross-repository edge
is an explicit signed descriptor containing repository, digest, media type, and
expected signer policy. Verification independently traverses and validates
each edge. Cross-repository referrer discovery is never assumed.

Public source/render artifacts and private deployments use separate registry
projects and credentials. Active, last-known-good, rollback-source, audit, and
legal-hold digests are garbage-collection roots.

### 7. Supply-chain trust

Cosign signatures use non-exportable KMS keys through exact workload identity.
Private key material is never exported, committed, logged, placed in a secret
store, or delivered to a runtime.

Purpose-separated signer roles cover:

1. public source/catalog publication;
2. harness render publication; and
3. private deployment authority.

A consumer may have additional lifecycle or business-authority signers, but
those are outside the public artifact trust root.

Every signer policy defines the KMS algorithm, immutable key-version resource,
allowed WIF/OIDC principal, repository/workflow/environment claims, least IAM
permissions, current/next trust set, rotation ceremony, revocation, compromise
response, and fail-closed behavior. An artifact-supplied key or policy cannot
bootstrap trust; runtimes receive trust policy independently.

In-toto predicates record source commit, Agent Spec version, builder identity,
workflow, renderer version/digest, tests/evaluations, policy and consumer
authority digests, specialization commit, approval, and output digest. Private
tenant identifiers and attestations are not published to a public transparency
service without an explicit privacy decision.

Unknown or revoked keys, wrong workflow/repository/subject/media type, missing
evidence, withdrawal, downgrade, stale policy, or a substituted source fail
closed. A registry or catalog outage may leave an already active, locally
verified release running, but blocks new import, compilation, and activation.

### 8. Installation and deployment records

The product defines append-only installation, desired-state, deployment, and
observation contracts. A consumer can persist them natively or use the Agent
Delivery control plane, but it must expose the same immutable identifiers and
state transitions.

A deployment records:

- source, render, binding, specialization, trust, policy, consumer-authority,
  and runtime-target descriptors;
- per-agent deployment subdigest;
- stable runtime slot where a harness needs one;
- release manifest aggregating the exact active subdigests;
- predecessor and compare-and-swap version;
- staging, canary, activation, failure, and rollback evidence; and
- desired versus observed state.

An agent-definition update changes only that agent's subdigest. Unchanged
agents retain their identity and credentials. A system-package change is
explicitly runtime-wide.

Rollback never reactivates an old receipt. It creates a new forward deployment
from last-known-good definition content plus the consumer's **current** policy,
grants, credentials, lifecycle, and runtime binding. Revoked authority cannot
return through rollback.

### 9. Stable runtime slots

Harnesses that assign OS identities, ports, services, or workspaces maintain a
durable mapping:

`consumer agent identity -> slot ID -> harness profile + UID/GID + port + service + workspace + generation`.

Allocation is independent of catalog or roster order. Retired slots are
tombstoned and are not reused without an audited purge and runtime-reset
ceremony proving that files, credentials, processes, sockets, caches, and
observations are gone.

Slots are operational boundaries, not security-sandbox claims. Consumers must
document whether profiles share a host trust boundary.

### 10. Durable process and idempotency

The installation and promotion process is a persisted state machine:

`received -> fetched -> validated -> quarantined -> evaluating -> approved|rejected -> rendered -> signed -> staged -> canary -> promoted|rolled_back`.

Legal transitions, terminal states, retry bounds, correlation, dead-letter,
replay, and compensation are explicit. Idempotency keys and compare-and-swap
desired-state revisions make duplicate, reordered, stale, force-pushed, and
conflicting inputs converge deterministically.

Integrations use an outbox/inbox boundary and sanitized versioned events. Raw
webhook payloads, installation tokens, credentials, and direct cross-service
database reads are forbidden.

Operations likely to exceed two seconds expose an asynchronous action resource
with durable status, progress, cancellation, and terminal evidence.

### 11. Update and skill governance

A stable-channel update may be proposed automatically only when:

- source, catalog, signer, channel, and predecessor are trusted;
- Agent Spec and renderer compatibility are non-lossy;
- the specialization rebases cleanly;
- the skill digest set is unchanged;
- no authority, credential, remote-code, provider, or weaker approval field
  appears;
- consumer evaluation and policy permit it; and
- compilation, canary, and health gates pass.

Changed skills are quarantined. High-risk skills require human approval.
Breaking, major, lossy, trust-policy, skill-changing, authority-bearing, or
approval-weakening changes cannot auto-promote.

The update bot uses compare-and-swap against the expected predecessor. Human or
concurrent changes win. History is never rewritten.

### 12. Runtime reconciliation

The runtime reconciler has a certificate-bound identity scoped to one consumer
and runtime target. It may read desired deployment and append observations for
that target. It cannot use a human provisioning role, an agent MCP principal,
or broad platform permissions. Registry pull credentials are independently
scoped and rotated.

The reconciler pulls by digest, verifies the full explicit trust graph, stages
safe content into the bound slot, checks modes and ownership, and switches only
at a harness-safe boundary. It never runs package hooks.

It persists `desired`, `staged`, `active`, `last-known-good`, `failed`, and
`rolled-back` facts. Recovery distinguishes a crash before versus after the
activation switch. Canary evidence includes process health, exact identity,
consumer workload login, one permitted capability, and denial of one forbidden
capability when the consumer exposes those checks.

### 13. API and CLI

The versioned API covers catalog, inspect, renderer capabilities, validation,
rendering, verification, import preview/apply, installations, update proposals,
deployments, promotion, rollback, status, and receipts.

The CLI exposes public catalog/validate/render/inspect/verify commands and
authenticated installation/deployment operations. It has stable JSON, stable
exit codes, redacted authentication, exact-digest previews, and asynchronous
action polling. Public operations require no ByteDesk account.

An import requires an exact source digest, declared harness, idempotency key,
and an explicit consumer-owned identity binding. It never creates grants,
credentials, roles, or provider connections implicitly.

### 14. Retention, withdrawal, and recovery

The actual target registry must pass conformance tests for OCI manifests,
referrers, immutable tags, signature accessories, retention, replication, and
garbage collection. Documentation claims are not evidence.

Registry policy covers project layout, quotas, immutable tags, pull roles,
active/last-known-good/audit/legal-hold roots, consumer deletion, withdrawal,
signer and digest revocation, backup, and restore. Restore testing converges
manifests, blobs, signatures, attestations, catalog indexes, and deployment
references.

A withdrawn or compromised digest cannot be newly imported or activated. The
consumer's incident policy decides whether an already running digest is stopped
or held while a replacement is compiled.

### 15. Delivery and integration sequence

The implementation order is:

`architecture -> product/bootstrap -> catalog contract -> baseline catalog + renderer contract -> harness adapters -> OCI -> trust -> installation/receipts -> consumer reconciliation -> API/update/compiler -> runtime host + CLI -> consumer cutovers -> certification`.

Core work lands in this repository. A consumer integration is a separate PR in
the consumer repository. Deterministic output comparison is allowed during
cutover; dual activation writers and silent fail-open fallback are forbidden.

No production registry, KMS, runtime, or consumer deployment is authorized by
this ADR.

## Required verification

The program cannot close without evidence for:

- official Agent Spec validation and forbidden authority-field fixtures;
- the 34 selectable ByteDesk reference agents plus one non-selectable/no-
  principal system package;
- deterministic source, render, and private deployment digests across clean
  rebuilds;
- wrong/missing subject, tampered layer, unknown/revoked signer, missing
  attestation, downgrade, cross-tenant, and source-substitution denial;
- traversal, link, device, archive-bomb, secret, malware, and license gates;
- duplicate, reordered, missed, stale, force-pushed, and conflicting Git inputs
  plus scheduled reconciliation;
- idempotent create/bind, slug collision, rename, retirement, and lifecycle
  races;
- unchanged-skill automatic update and changed/high-risk skill quarantine;
- forward rollback that cannot restore revoked authority;
- stable slot preservation and denied retired-slot reuse;
- reconciler denial outside its target and pull-credential rotation;
- partial pull, disk full, crash before/after switch, registry outage, canary
  failure, and restart recovery;
- registry retention/GC, quota, legal hold, backup, and restore;
- positive permitted-capability and negative forbidden-capability evidence for
  a reference consumer;
- clean third-party catalog, validation, rendering, packaging, and verification
  without ByteDesk Platform; and
- exact receipt-based reproduction of running content.

## Consequences

### Positive

- One definition can serve multiple platforms and harnesses.
- Exact digests and purpose-separated signatures make provenance reproducible.
- Specialization remains reviewable without acquiring runtime authority.
- Per-agent subdigests and stable slots reduce unrelated deployment churn.
- Consumers retain identity and authorization sovereignty.
- Forward rollback cannot resurrect revoked credentials or grants.

### Trade-offs

- Source, render, and private deployment planes add operational complexity.
- Agent Spec does not express the digest-plus-specialization contract, so a
  small versioned binding envelope is required.
- Per-agent deployments plus runtime releases are more complex than one
  engine-wide payload.
- Registry retention, KMS trust, update automation, and host recovery need
  integration and failure testing before production use.
- Changed skills move more slowly than definition-only updates by design.

## Alternatives rejected

| Alternative | Reason |
|---|---|
| Keep a platform or harness as definition source | Prevents neutral consumption and preserves divergent copies |
| Put product code and the canonical marketplace in one required repository | Violates the definition-only marketplace boundary and prevents replacement |
| Store complete consumer `SpecializedAgent` copies | Hides upstream provenance and permits authority-bearing changes |
| Use branches or tags as deployment identity | Mutable and not reproducible |
| Depend on cross-repository OCI referrer discovery | Referrer discovery is repository-local |
| Embed MCP or provider requirements in packages | Lets content demand consuming-platform authority |
| Export signing PEMs to CI or runtimes | Broadens compromise and violates non-exportable-key posture |
| Load arbitrary renderer plugins | Turns inert package handling into code execution |
| Reuse list order for OS slots | Reordering can transfer files and credentials between agents |
| Reactivate an old deployment for rollback | Can restore revoked authority and breaks append-only evidence |
| Build a marketplace UI in v1 | Adds scope without proving the portable delivery contract |

## Extraction note

This ADR is the canonical successor to the unlanded ByteDesk Platform draft
`ADR-0188: Open Agent Marketplace and OCI Agent Delivery`. Platform-specific
identity, MCP authorization, GitHub ingress, Hermes, and organizational-profile
details are retained in the ByteDesk consumer integration profile. The draft
was never accepted on the Platform `develop` branch.

## References

- [Agent Spec](https://github.com/oracle/agent-spec)
- [Agent Spec documentation](https://oracle.github.io/agent-spec/)
- [OCI Image and Distribution 1.1](https://opencontainers.org/posts/blog/2024-03-13-image-and-distribution-1-1/)
- [ORAS artifact and referrer concepts](https://oras.land/docs/1.1/concepts/reftypes/)
- [Cosign](https://docs.sigstore.dev/cosign/overview/)
- [In-toto](https://in-toto.io/)
