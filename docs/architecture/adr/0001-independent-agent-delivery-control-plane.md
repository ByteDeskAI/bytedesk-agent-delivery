# ADR-0001: Independent Agent Delivery control plane

**Date:** 2026-07-16

**Last amended:** 2026-07-17

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
also prove the source, renderer, policy inputs, consumer-private functional
customization, exact skill set, and running output. At the same time, neither a
public package nor private functional customization may acquire the power to
grant identity, credentials, resources, roles, workload identity, or call-time
access.

The product must support two equally important modes:

1. a clean third party can discover, validate, render, package, and verify an
   agent without any ByteDesk Platform service; and
2. a consuming platform can bind an exact agent definition to its own identity
   and policy, compile a private deployment, activate it safely, and reproduce
   the exact running state from receipts.

Agent Spec `26.1.2` is the selected portable definition standard. It provides
`Agent` and `SpecializedAgent`, but does not define the digest-pinned,
deterministic private customization delta and separate authority inputs required
by a multi-tenant consumer.

OCI 1.1 supplies content addressing, subjects, and referrers. A subject edge and
its referrers are repository-local, so public source artifacts and private
consumer deployments need explicit signed descriptors for every
cross-repository relationship.

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
| Private functional customization, private skills, installation identity, desired runtime target | Consuming platform |
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

`Agent` is the default standalone catalog form. A `SpecializedAgent` is allowed
as an intentional, complete public specialization governed by Agent Spec; it is
not a private customization or organizational identity. Source kind and
effective output kind are recorded. Private customization applies once to the
complete validated public document and introduces no second inheritance model.
A kind-changing effective result is breaking and requires manual promotion.

Every authoritative or digest-bearing structured object uses the JSON data
model and RFC 8785 JSON Canonicalization Scheme bytes as its semantic identity.
JSON-compatible YAML 1.2 may be accepted only as human authoring input. Parsers
reject duplicate keys before collapse, aliases, custom tags, non-string keys,
non-finite numbers, and every other value that cannot be represented in the
JSON data model and serialized by RFC 8785. YAML source spelling, comments,
presentation, and key order are never signed or hashed as authority. An original
authoring document may be retained only as a separate provenance attachment or
record. Any digest over its authored bytes protects storage integrity only; it
is never semantic or artifact authority, a substitute signature target, a
promotion decision, or an activation input.

The declared contract role or media type, not a filename extension, determines
whether content is a structured object. Arbitrary payload files, including a
regular file named `.yaml`, preserve their exact raw bytes and are not parsed as
control objects. Binary payload digests are over those exact bytes; the content
is never decoded, transcoded, line-ending-normalized, or passed through
JSON/YAML canonicalization. Deterministic archive metadata does not alter a
payload entry's content. The full input, output, failure, and verification
contract is
[Canonical encoding v1](../../standards/canonical-encoding-v1.md). Exact object
shape and evolution follow
[Machine contracts v1](../../standards/machine-contracts-v1.md): Agent
Delivery-owned authoritative objects use closed JSON Schema Draft 2020-12
schemas with stable `$id`, exact digest, offline bundle-local references, signed
immutable contract bundles, and release-blocking cross-validator fixtures.
Generated code, OpenAPI, AsyncAPI, documentation, and SDKs are projections;
schemas are the source of truth. Agent Spec remains governed by its pinned
official SDK.

Portable packages use a logical default model. The consumer may select a
concrete model and provider through private functional customization. Public
packages may contain behavior, descriptive metadata, and exact descriptors for
tenant-free public skills. A public Agent Spec `SpecializedAgent` remains
portable catalog source and is not a private consumer customization. Public
packages may not contain:

- API keys, credentials, secret values, or secret references;
- tenant or consumer-specific identifiers;
- provider endpoints or provider grants;
- MCP servers, tool/resource grants, additional runtime tools, or toolboxes;
- workload, engine, profile, role, or identity bindings;
- remote executable URLs, automatic install/build directives, or
  artifact-provided hooks; or
- fields that claim to set or weaken consumer approval or mandatory oversight
  policy. The official Agent Spec `human_in_the_loop` value remains functional
  configuration and never overrides separate consumer policy.

Public and private skill packages may contain arbitrary regular files, including
instructions, scripts, binaries, archives, data, images, models, and dependency
manifests. Agent Delivery treats them as untrusted, non-executing input. Optional
public skills never block discovery or source validation. A consumer may
quarantine, explicitly remove or replace them through canonical binding
operations, extend, evaluate, or require approval for them independently and
may add its own exact private skill packages. A selected unapproved skill is
never silently omitted.

OASF may be emitted as a signed discovery projection. It is never an authoring,
installation, or deployment authority.

The ByteDesk reference catalog contains 34 selectable employee-agent packages
and one non-selectable `office-orchestrator` system package. The system package
does not create an organizational identity or workload principal.

### 4. Deterministic private customization binding

A consumer stores `bytedesk.agent-binding/1`, not a copied base definition and
not a mutable branch or tag. The private envelope includes:

- exact source repository and digest;
- exact Agent Spec version;
- allowlisted harness identifier and exact signed renderer-release descriptor;
- ordered functional Agent Spec and harness-configuration patch operations;
- explicit add, replace, and remove operations for arbitrary regular files;
- exact add, replace, and remove operations for public/private skill
  descriptors;
- release channel and compatible-update preference; and
- a required discriminated compare-and-swap precondition: `absent` for initial
  creation or `match` with the exact current revision and digest.

Functional property changes use the closed `bytedesk.json-patch/1` profile:
ordered RFC 6901 JSON Pointer operations limited to strict `add`, `replace`,
and `remove` existence semantics. Empty-root changes, move/copy/test, unknown
members, invalid/non-canonical pointers, partial application, and any patch into
lineage or security inputs fail. The complete result is revalidated.

File and skill operations use separate closed schemas. File paths are relative
portable Unicode-NFC POSIX paths with traversal, control, reserved-name, case-
fold, and normalization-collision denial. Replace/remove bind the expected
current content or skill digest. A source update uses a three-way rebase;
changed targets, ancestors, parents, or unstable array positions conflict
instead of being blindly replayed.

The delta may override any functional Agent Spec property and configure models,
provider endpoints, tools, MCP servers, resources, and harness behavior. It may
carry opaque references to consumer-managed secrets or credentials, but never
their values. Configuring a capability does not authorize its use.

Tenant or organizational identity, roles, grants, call-time authorization,
workload identity, credential values, trust roots, signer policy, and mandatory
sandbox, network, approval, isolation, or other security controls are separate
authenticated consumer inputs. The delta cannot define or weaken them. The
validator also rejects caller-supplied base copies, mutable references, tenant
escape fields, package hooks, and renderer plugins.

The compiler resolves the pinned source plus delta and approved skills into a
complete official effective Agent Spec. A full effective copy exists only in
deterministic build output; the public source plus canonical private delta remain
the authoring lineage.

The exact field, operation, path, predecessor, source-resolution, failure, and
compatibility rules are normative in
[Machine contracts v1](../../standards/machine-contracts-v1.md).

### 5. Renderer Strategy and Adapter boundary

Renderer selection uses Strategy. Each harness integration is an Adapter. The
initial Adapters are:

- native Agent Spec;
- Hermes; and
- OpenClaw.

The native Adapter emits a normalized, version-pinned Agent Spec package with
no runtime-specific translation. WayFlow is Oracle's reference Agent Spec
runtime, not a distinct Agent Delivery renderer format or authority source.
AD-04 pins `wayflowcore==26.1.2` only as an external compatibility lane that
loads the native output for supported components; Agent Delivery does not emit
WayFlow-specific content, require WayFlow at runtime, or fuse WayFlow identity
into the native renderer identity.

The allowlisted registry is generated at product build time, serialized
canonically, and embedded by digest in the signed Agent Delivery distribution.
Runtime plugin loading is forbidden. Adding a harness or renderer release
requires a reviewed product release and contract tests; it does not modify
canonical agent packages. Operators may restrict the compiled allowlist but no
runtime input can expand it.

A renderer version is not execution identity. The accepted binding pins a
signed renderer-release manifest descriptor. That manifest binds source and
tree digests, contract/capability/configuration schemas, supported Agent Spec
and harness versions, exact platform executable/worker images, product
distribution and allowlist digests, locked toolchain/dependencies, SBOM,
vulnerability/license results, deterministic conformance, and SLSA Build Level
3 provenance. One version permanently maps to one manifest digest.

Every render emits a manifest containing source digest, Agent Spec version,
renderer-release manifest digest, actual executed distribution/worker digest
and platform, embedded allowlist and schema digests, normalized parameters,
compatibility result, explicit loss/warnings, and output file digests.
Unsupported semantics fail or are reported as an explicitly approved lossy
mapping; they are never silently dropped.

Identical normalized inputs produce byte-identical output. Authoritative
structured inputs normalize to RFC 8785 canonical JSON. Renderer-produced text
fixes UTF-8 encoding and LF endings; file ordering, safe declared modes,
ownership metadata, timestamps, archive structure, and compression settings are
also deterministic. Binary input payloads remain byte-exact.

A public render is derived only from the unchanged tenant-free source and the
exact public skill set declared by that source. Public render endpoints reject
consumer bindings, private skills, and customizations. Binding-aware preview and
compilation are available only through an authenticated private path or a local
private workflow that does not publish private inputs or outputs.

The private deployment compiler reconstructs the full effective Agent Spec,
resolves the exact consumer-approved skill set, and performs a complete render
with the same exact resolved Adapter implementation recorded by the public-
render lineage. It embeds the effective render bundle and full manifest in the
signed private deployment. It never patches a public render, and
v1 defines no separate private-render artifact type. Verified public output may
be reused only when the customization is empty, the effective skill set exactly
matches the declared public set, and every normalized source, skill, renderer,
and parameter input matches.

Packages, skills, archives, and OCI layers are untrusted data. Validators,
renderers, compilers, and reconcilers never execute package content or fetch
package-directed code. They enforce file-count, path-depth,
compressed/uncompressed-size, media-type, mode, and decompression limits and
reject absolute paths, traversal, symlinks, hardlinks, devices, FIFOs,
privileged modes, and archive bombs. Declared executable modes are allowed for
regular skill files. No artifact can register a build, install, migration,
render, or activation hook. A runtime may execute an exact-digest-approved skill
only after activation and under current consumer sandbox, network, identity, and
call-time authorization policy.

Renderer execution uses a fresh no-network, no-secret, read-only-root,
privilege-dropped, resource-bounded sandbox. Only allowlisted product code may
execute. Input code, libraries, scripts, hooks, and package managers never do.
Withdrawal or revocation blocks new renderer execution and activation; forensic
retention does not make a renderer eligible. The complete identity,
distribution, execution, failure, and verification rules are in
[Renderer identity v1](../../standards/renderer-identity-v1.md).

### 6. OCI artifact graph

Deployment authority is always an exact digest. SemVer, tags, and release
channels are discovery metadata.

V1 defines:

| Artifact | Visibility | Evidence |
|---|---|---|
| Product/contract bundle and renderer release | Public | Product distribution, compiled allowlist, exact schemas, fixtures, executable variants, SBOM, and provenance |
| Signed catalog index | Public | Catalog digest, source descriptors, channel and withdrawal metadata |
| Agent source | Public | Canonical manifest and deterministic source layer |
| Skill package | Public catalog or private consumer scope | Canonical manifest, deterministic regular-file layer, file inventory, SBOM/scan evidence, and exact digest |
| Harness render | Public | Tenant-free source descriptor, exact declared public skill descriptors, renderer descriptor, deterministic render bundle |
| Consumer deployment | Private to consumer/tenant | Public lineage, binding/customization and approved skill descriptors, embedded effective render bundle/manifest, and separate policy, authority, identity, and target subdigests |
| Consumer authority, skill approval, canary, and recovery evidence | Private to consumer/tenant | Exact candidate/target/revision binding, signer-policy digest, freshness, decisions, and redacted evidence references |
| Signature, attestation, SBOM | Same repository as subject | OCI referrer to the exact local subject |
| Runtime release manifest | Private to consumer/runtime | Exact deployment subdigests and system-package digest |

The media-type namespace is `application/vnd.bytedesk.agent.*.v1`. The v1 names
are reserved by the accepted media registry; their closed schemas, schema
digests, and signed contract bundle must pass contract tests before publication.
Every ByteDesk authoritative JSON manifest is serialized under
`bytedesk.canonical-json/1` before hashing and signing; accepting YAML authoring
input does not create a YAML artifact identity.

An OCI manifest may use `subject` only for an exact artifact in the same
repository, and referrer discovery remains local to that repository. Every
cross-repository relationship MUST instead be an explicit descriptor in a
signed downstream manifest containing repository, digest, media type, size, and
expected immutable trust-policy ID and digest. Verification independently
traverses and validates each descriptor. Cross-repository subject/referrer
discovery is never assumed.

V1 defines no private-render media type. The effective private render is a
bundle and manifest embedded in the consumer deployment artifact.

Public source/skill/render artifacts and private deployments use separate
registry projects and credentials. Active, last-known-good, recovery-source,
audit, and legal-hold digests are garbage-collection roots.

### 7. Supply-chain trust

Cosign signatures use non-exportable KMS keys through exact workload identity.
Private key material is never exported, committed, logged, placed in a secret
store, or delivered to a runtime.

Purpose-separated signer roles cover:

1. product distribution, contract bundle, allowlist, and renderer release;
2. public source/catalog/skill publication;
3. harness render publication;
4. consumer-private skill publication;
5. consumer authority, skill approval, and business approval; and
6. private deployment/release authority.

Roles 4 through 6 are isolated per consumer. Authority/approval and deployment
use different keys and workload identities. The preferred production topology
uses non-exportable consumer-owned KMS keys. Agent Delivery build/compiler/
publication workloads may receive narrow role-4 private-skill or role-6
deployment signing only; they never receive role-5 authority/approval signing,
which belongs to the independently authenticated Consumer Authority Adapter. A
hosted service may use an explicitly opted-in tenant-dedicated KMS/HSM key whose
immutable version is independently pinned and revocable by the consumer. A
shared cross-consumer private signer or provider-controlled consumer trust root
is forbidden.

Publishing or signing a skill does not approve its use. The consumer owns the
business decision and issues exact-digest skill-approval evidence. Agent
Delivery verifies and records that evidence but cannot issue or infer it.

Every signer policy is an immutable canonical object identified by stable ID,
logical version, exact schema digest, policy digest, and effective window. A
descriptor carries both policy ID and digest, while the verifier obtains policy
independently. Every policy defines the KMS algorithm, immutable key-version resource,
allowed WIF/OIDC principal, repository/workflow/environment claims, least IAM
permissions, current/next trust set, rotation ceremony, revocation, compromise
response, and fail-closed behavior. An artifact-supplied key or policy cannot
bootstrap trust; runtimes receive trust policy independently.

The consumer supplies signed short-lived authority snapshots bound to consumer,
subject, installation, candidate, desired revision, target, operation, current
policy/grant/credential/workload-identity/lifecycle/security-control subdigests,
nonce, predecessor, and expiry. Compilation and activation verify fresh
snapshots independently; no credential values are embedded. The exact topology
and envelopes are defined by
[Consumer authority and private signing v1](../../standards/consumer-authority-v1.md).

In-toto predicates record source commit, Agent Spec version, builder identity,
workflow, renderer-release/executed-distribution/allowlist/schema digests,
tests/evaluations, policy and consumer
authority digests, binding/customization digest, exact skill descriptors,
approvals, and output digest. Private tenant identifiers, skill attestations,
functional configuration, and deployment attestations are not published to a
public transparency service without an explicit privacy decision.

Unknown or revoked keys, wrong workflow/repository/subject/media type, missing
evidence, withdrawal, downgrade, stale policy, or a substituted source fail
closed. A registry or catalog outage may leave an already active, locally
verified release running, but blocks new import, compilation, and activation.

### 8. Installation and deployment records

The product defines append-only installation, candidate, target desired-state,
deployment, rollout, and observation contracts. There is one
`TargetDeliveryState` aggregate per consumer/runtime target and one logical
writer: the Agent Delivery Promotion Coordinator. It alone advances desired
state by exact revision-and-digest CAS after verifying consumer authority and
rollout evidence.

Each target selects one `DesiredStateStore` Adapter: Agent Delivery-managed or
a consumer-native implementation of the same atomic CAS/history contract.
There is never a second authoritative row or live dual write. Git and consumer
systems submit installation/binding intent; the compiler submits a prepared
release; the host appends observations. None writes runtime desired state
directly. Store migration is quiesced, audited, and digest-checkpointed.

A deployment records:

- source, public render, binding/customization, approved public/private skill,
  trust, policy, consumer-authority, and runtime-target descriptors;
- the embedded effective render bundle, manifest, and complete file inventory;
- per-agent deployment subdigest;
- stable runtime slot where a harness needs one;
- release manifest aggregating the exact active subdigests;
- exact revision-and-digest predecessor and compare-and-swap precondition;
- staging, canary, activation, failure, and forward-recovery evidence; and
- desired versus observed state.

An agent-definition update changes only that agent's subdigest. Unchanged
agents retain their identity and credentials. A system-package change is
explicitly runtime-wide.

Forward recovery never reactivates an old receipt. Last-known-good is
historical evidence, not automatic eligibility. Recovery searches prior promoted
functional-content sets newest first and rejects unavailable, withdrawn,
compromised, unapproved, incompatible, or currently unbuildable inputs. It
creates a new deployment from eligible historical functional content plus the
consumer's **current** policy, grants, credential references, lifecycle,
security controls, target, and runtime binding.

A revoked historical renderer or builder is never executed. Current trusted
tooling must establish a new render lineage, with full compatibility,
evaluation, approval where output differs, and canary evidence. If no eligible
candidate exists, recovery fails closed and incident policy chooses isolation,
stop, or temporary continuation of already active verified content. Recovery
does not depend on Git availability and never restores revoked authority.

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

Installation lifecycle, candidate preparation, target rollout, host attempt,
and active-slot facts are separate persisted models. One enum cannot overwrite
the fact that a predecessor is active while a candidate is staged.

- Installation has `provisioning`, `active`, `suspended`,
  `retirement_pending`, `retiring`, and terminal `rejected`/`retired` states.
- Candidate preparation proceeds through fetch, validate, quarantine,
  evaluate/approval, full compile, sign, and terminal `prepared`, with explicit
  `rejected`, `cancelled`, `superseded`, and `failed` outcomes.
- Runtime rollout has separate staging/preflight and certified isolated-
  candidate or guarded-in-place activation paths. A physical switch is not
  promotion; the Coordinator promotes only after current evidence passes.
- Pre-switch failure leaves the predecessor active. Post-switch failure is
  `recovery_required`; there is no direct `rolled_back` transition. A new
  forward recovery rollout must be prepared and promoted.

Legal transitions, terminal states, retry bounds/backoff, cancellability,
correlation, dead-letter, replay, and compensation are exact schema contracts.
Idempotency keys and revision-plus-digest CAS make duplicate, reordered, stale,
force-pushed, ABA, and conflicting inputs converge deterministically. A lease
never overrides CAS.

Integrations use an outbox/inbox boundary and sanitized versioned events. Raw
webhook payloads, installation tokens, credentials, and direct cross-service
database reads are forbidden.

Operations likely to exceed two seconds expose an asynchronous action resource
with durable status, progress, cancellation, and terminal evidence.

The normative actors, states, transitions, target authority, canary evidence,
and recovery algorithm are in
[Delivery lifecycle v1](../../standards/delivery-lifecycle-v1.md).

### 11. Update and skill governance

A stable-channel update may be proposed automatically only when:

- source, catalog, signer, channel, and predecessor are trusted;
- Agent Spec and renderer compatibility are non-lossy;
- the functional customization delta rebases cleanly;
- the skill digest set is unchanged;
- no identity, grant, credential value, trust-root, mandatory-security-policy,
  or weaker approval field appears;
- consumer evaluation and policy permit it; and
- compilation, canary, and health gates pass.

Every changed public or private skill digest returns to quarantine. High-risk
skills require explicit consumer-issued approval under current consumer policy;
the consuming organization, not Agent Delivery or the catalog publisher, owns
the business decision.
Breaking, major, lossy, trust-policy, skill-changing, authority-bearing, or
approval-weakening changes cannot auto-promote.

The update bot uses the exact absent/match revision-and-digest precondition.
Human or concurrent changes win. History is never rewritten. Automated rebase
is three-way and conflicts on changed targets, ancestors, parents, or unstable
array positions.

### 12. Runtime reconciliation

The runtime reconciler has a certificate-bound identity scoped to one consumer
and runtime target. It may read desired deployment and append observations for
that target. It cannot use a human provisioning role, an agent MCP principal,
or broad platform permissions. Registry pull credentials are independently
scoped and rotated.

The reconciler pulls by digest, verifies the full explicit trust graph and exact
approved skill set, stages untrusted content without execution into the bound
slot, checks modes and ownership, and switches only at a harness-safe boundary.
It never runs package or skill content or artifact-provided hooks. After
activation, the harness may expose a skill to the agent only after explicit
approval of its exact digest and under current consumer sandbox, network,
identity, and call-time authorization policy.

It persists target-scoped technical attempts and observations separately from
the Coordinator's desired/rollout state and active-slot fact. Recovery
distinguishes a crash before versus after the activation switch. The host
cannot self-promote or label a candidate rolled back.

Canary responsibility is purpose-separated. The Coordinator issues a
nonce-bound plan and verifies fresh matching evidence. The Host Reconciler
proves artifact/slot/file/process/resource/readiness facts. A consumer-owned
Capability Verifier exercises a non-destructive permitted operation and a
known denied sentinel through the normal candidate runtime and authorization
path; the candidate receives its own short-lived workload identity directly
from the consumer. The host never handles that identity or invokes a
capability. Timeout, transport error, missing endpoint, or `404` is not proof of
denial. Omission is not success; only a signed `not_applicable` is valid for a
certified no-capability profile.

### 13. API and CLI

The versioned API covers catalog, inspect, renderer capabilities, validation,
rendering, verification, import preview/apply, installations, update proposals,
deployments, promotion, forward recovery, status, and receipts.

The normative description is signed OpenAPI 3.2.0 and references the exact
Draft 2020-12 source schemas. Mutations use strong ETags, HTTP preconditions,
domain revision-and-digest CAS, and idempotency key plus canonical input digest.
Errors use RFC 9457 problem details. Long work returns `202`, `Location`, and a
durable action resource. Events use CloudEvents 1.0.2 structured JSON,
AsyncAPI 3.1.0, exact data-schema digests, at-least-once delivery, per-aggregate
sequence, inbox deduplication, and API resynchronization on gaps. Events are
notifications, never authority.

The CLI exposes public `catalog`, `validate`, `render`, `package`, `publish`,
`inspect`, and `verify` commands plus authenticated installation/deployment
operations. `package`
builds deterministic local OCI content; `publish` is an explicit authenticated
side effect and never occurs implicitly during render. The CLI has stable JSON,
stable exit codes, redacted authentication, exact-digest previews, and
asynchronous action polling. Public/local operations require no ByteDesk
account and reject consumer bindings, private skills, or customizations.
Private preview and compilation require authenticated consumer scope or remain
local and non-publishing.

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

### 15. Operational readiness

V1 GA is blocked on measured
[Operational readiness v1](../../standards/operational-readiness-v1.md)
evidence. The accepted launch profile fixes availability and latency SLOs,
reference workload and capacity targets, input/resource ceilings, backpressure,
regional RPO/RTO, backup/restore/failover exercises, retention, OpenTelemetry
and complete administrative audit, security-response deadlines, compatibility,
deprecation, and support windows.

Documentation or a successful happy-path demo is not operational evidence. GA
requires thirty consecutive days meeting the production-equivalent SLOs, load/
soak/chaos and noisy-neighbor results, a full isolated restore and regional
failover, N-1 rolling upgrade, zero unresolved critical/high findings in the
released path, consumer-facing limits/runbooks, and a signed readiness report.
An already active verified runtime remains independent of control-plane
availability.

### 16. Delivery and integration sequence

The product delivery milestones are:

1. `CONTRACTS-FROZEN` — architecture, closed schema/contract bundle, renderer,
   trust/authority, lifecycle, and operational contracts;
2. `SUPPLY-CHAIN-CERT` — native and harness renderers, deterministic OCI,
   signed product/renderer releases, and trust conformance;
3. `CONTROL-PLANE-CERT` — installations, API/events, intent ingestion, updates,
   private compilation, exact authority, and single-writer desired state;
4. `RUNTIME-CERT` — reference reconciler, both declared activation modes where
   supported, canary evidence, forward recovery, CLI, and failure recovery;
5. `CORE-CERT` — independent security, deterministic, compatibility,
   operational-readiness, DR, API/CLI, and clean third-party certification,
   followed by the standalone v1 GA release;
6. `REFERENCE-CATALOG-CERT` — the separate ByteDesk definition catalog and its
   34 selectable plus one system package; and
7. `REFERENCE-CONSUMER-CERT` — ByteDesk/Hermes and OpenClaw consumer cutovers
   against the released core.

The standalone core does not depend on the ByteDesk catalog, ByteDesk Platform,
or consumer cutovers. It does include generic fixtures plus native, Hermes, and
OpenClaw renderer products, the generic control plane, reference reconciler,
API, events, and CLI. Reference catalog and consumer work may prepare in
parallel but certification pins a released core.

Core work lands in this repository. A consumer integration is a separate PR in
the consumer repository. Deterministic output comparison is allowed during
cutover; dual activation writers and silent fail-open fallback are forbidden.

No production registry, KMS, runtime, or consumer deployment is authorized by
this ADR.

## Required verification

The program cannot close without evidence for:

- official Agent Spec validation and forbidden authority-field fixtures;
- signed Draft 2020-12 contract bundle, closed-schema/unknown-field behavior,
  cross-validator agreement, offline resolution, OpenAPI 3.2.0, AsyncAPI 3.1.0,
  CloudEvents 1.0.2, RFC 9457, strict patch/path/file/skill operations, and
  absent/match revision-plus-digest CAS;
- Agent and public SpecializedAgent source handling with no private inheritance
  ambiguity;
- exact renderer-release/executed-distribution/allowlist/schema identity,
  sandbox isolation, SLSA Build Level 3 provenance, cross-platform deterministic
  output, and revoked-renderer denial;
- the 34 selectable ByteDesk reference agents plus one non-selectable/no-
  principal system package as a separate reference-catalog certification, not
  a standalone-core dependency;
- deterministic source, public render, customization resolution, effective
  render, and private deployment digests across clean rebuilds;
- accepted semantically equivalent JSON and YAML yielding byte-identical RFC
  8785 output and digests; rejection of duplicate YAML keys, aliases, custom
  tags, non-string keys, non-finite numbers, and other non-JSON values; proof
  that a provenance-only authoring digest cannot influence authority, promotion,
  or activation; and byte-for-byte preservation of arbitrary `.yaml` and binary
  payload fixtures;
- wrong/missing subject, tampered layer, unknown/revoked signer, missing
  attestation, downgrade, cross-tenant, and source-substitution denial;
- traversal, link, device, privileged-mode, archive-bomb, secret, malware, and
  license gates;
- duplicate, reordered, missed, stale, force-pushed, and conflicting Git inputs
  plus scheduled reconciliation;
- idempotent create/bind, slug collision, rename, retirement, and lifecycle
  races;
- arbitrary regular-file skills, including executable scripts and binaries,
  that never execute in the Agent Delivery pipeline;
- exact-digest-approved post-activation skill execution under consumer runtime
  policy, unchanged-skill automatic update, and changed/high-risk skill
  quarantine;
- private functional Agent Spec/file/skill operations, full effective rerender,
  rejection of post-render patches, and empty-customization public-output reuse;
- consumer-owned or tenant-dedicated private keys, purpose separation,
  immutable trust-policy digests, fresh consumer-authority snapshots, and exact
  consumer-issued skill approval;
- one Promotion Coordinator desired-state writer, managed and consumer-native
  store conformance, Git-intent separation, and no dual-write migration;
- exhaustive installation/candidate/rollout transitions, terminal states,
  cancellation, retries, ABA/concurrency, and pre/post-switch facts;
- separate host technical and consumer capability evidence, including true
  permitted and policy-denied results with false-denial denial fixtures;
- forward recovery that selects only currently eligible historical functional
  content, uses current trusted tooling and authority, works without Git, and
  cannot restore withdrawn content or revoked authority;
- stable slot preservation and denied retired-slot reuse;
- reconciler denial outside its target and pull-credential rotation;
- partial pull, disk full, crash before/after switch, registry outage, canary
  failure, and restart recovery;
- registry retention/GC, quota, legal hold, backup, and restore;
- positive permitted-capability and negative forbidden-capability evidence for
  a reference consumer;
- clean third-party catalog, validation, rendering, packaging, and verification
  without ByteDesk Platform;
- exact receipt-based reproduction of running content; and
- measured SLO, capacity, limit, noisy-neighbor, load/soak/chaos, RPO/RTO,
  backup/restore/failover, telemetry/redaction, support, upgrade, and signed GA
  readiness evidence.

## Consequences

### Positive

- One definition can serve multiple platforms and harnesses.
- Exact digests and purpose-separated signatures make provenance reproducible.
- Canonical JSON makes semantic identity independent of accepted authoring
  syntax while byte-exact binary handling prevents payload mutation.
- Consumer customization remains reviewable without acquiring runtime
  authority.
- Per-agent subdigests and stable slots reduce unrelated deployment churn.
- Consumers retain identity and authorization sovereignty.
- Forward recovery cannot resurrect revoked credentials or grants.
- Closed signed schemas, exact renderer releases, and one target-state writer
  remove parser, executable, and split-brain ambiguity.
- Core GA is independently certifiable while ByteDesk catalog and consumer
  integrations retain their own honest readiness gates.

### Trade-offs

- Source, skill, public-render, effective-render, and private-deployment planes
  add operational complexity.
- Agent Spec does not express the digest-plus-private-delta contract, so a small
  versioned binding envelope is required.
- Per-agent deployments plus runtime releases are more complex than one
  engine-wide payload.
- Registry retention, KMS trust, update automation, and host recovery need
  integration and failure testing before production use.
- Changed skills move more slowly than definition-only updates by design.
- Consumer-isolated signing, SLSA-hardened renderer builds, capability canaries,
  multi-year historical verification, and the accepted operational SLO/DR bar
  require substantial production engineering and recurring evidence.

## Alternatives rejected

| Alternative | Reason |
|---|---|
| Keep a platform or harness as definition source | Prevents neutral consumption and preserves divergent copies |
| Put product code and the canonical marketplace in one required repository | Violates the definition-only marketplace boundary and prevents replacement |
| Store a complete consumer Agent Spec copy as authoring truth | Hides upstream provenance and makes exact private changes difficult to review or rebase |
| Hash or sign authored YAML bytes as semantic identity | Equivalent documents can differ by presentation or parser behavior, and ambiguous YAML features create review and verification gaps |
| Use branches or tags as deployment identity | Mutable and not reproducible |
| Accept unknown fields in authority objects | A producer and verifier can assign different signed meaning |
| Use JSON Merge Patch or unconstrained JSON Patch | Ambiguous null/array behavior and unsafe operations weaken deterministic review |
| Depend on cross-repository OCI referrer discovery | Referrer discovery is repository-local |
| Embed MCP or provider requirements in reusable public packages | Lets public content demand consuming-platform functionality or authority; private configuration must remain explicit and non-authorizing |
| Export signing PEMs to CI or runtimes | Broadens compromise and violates non-exportable-key posture |
| Use one provider private signer across consumers | Expands compromise scope and removes consumer trust sovereignty |
| Load arbitrary renderer plugins | Turns a non-executing artifact pipeline into package-controlled code execution |
| Treat a renderer version or source commit as execution identity | Does not prove the executable, schemas, allowlist, or toolchain that produced output |
| Patch public renderer output for private deployments | Breaks semantic validation, compatibility evidence, and deterministic renderer provenance |
| Publish a separate private-render artifact in v1 | Adds an unnecessary artifact/signing/retention surface when the effective bundle belongs to one deployment |
| Reuse list order for OS slots | Reordering can transfer files and credentials between agents |
| Reactivate an old deployment for rollback | Can restore revoked authority and breaks append-only evidence |
| Let Git, consumer storage, host, and control plane all write desired state | Creates split brain and makes promotion authority ambiguous |
| Let the host reconciler invoke capability canaries | Gives a deployment actor agent authority and makes denial evidence untrustworthy |
| Make ByteDesk catalog or cutovers a core release prerequisite | Reintroduces the consumer dependency the independent product exists to remove |
| Build a marketplace UI in v1 | Adds scope without proving the portable delivery contract |

## Normative companions and delivery plan

This ADR is implemented and constrained by the
[architecture resolution register](../decision-register.md),
[system overview](../system-overview.md), [C4 model](../c4.md),
[consumer integration contract](../consumer-integration-contract.md),
[OCI artifact model](../oci-artifact-model.md),
[runtime reconciliation contract](../runtime-reconciliation.md), and
[security and trust model](../security-and-trust.md). The normative standards
index and accepted execution order are linked from the
[documentation index](../../README.md),
[development plan](../../planning/development-plan.md), and
[implementation-readiness execution plan](../../planning/implementation-readiness-execution.md).

## Extraction note

This ADR is the canonical successor to the unlanded ByteDesk Platform draft
`ADR-0188: Open Agent Marketplace and OCI Agent Delivery`. Platform-specific
identity, MCP authorization, GitHub ingress, Hermes, and organizational-profile
details are retained in the ByteDesk consumer integration profile. The draft
was never accepted on the Platform `develop` branch.

## References

- [Agent Spec](https://github.com/oracle/agent-spec)
- [Agent Spec documentation](https://oracle.github.io/agent-spec/)
- [WayFlow reference runtime](https://oracle.github.io/wayflow/)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785)
- [RFC 6901: JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901)
- [RFC 6902: JSON Patch](https://www.rfc-editor.org/rfc/rfc6902)
- [OpenAPI 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [AsyncAPI 3.1.0](https://www.asyncapi.com/docs/reference/specification/v3.1.0)
- [CloudEvents 1.0.2](https://github.com/cloudevents/spec/tree/ce%40v1.0.2)
- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457)
- [OCI Image and Distribution 1.1](https://opencontainers.org/posts/blog/2024-03-13-image-and-distribution-1-1/)
- [ORAS artifact and referrer concepts](https://oras.land/docs/1.1/concepts/reftypes/)
- [Cosign](https://docs.sigstore.dev/cosign/overview/)
- [In-toto](https://in-toto.io/)
- [SLSA v1.2](https://slsa.dev/spec/v1.2/)
