# Migration and source cutover

## Objective

Migration establishes Agent Delivery as the single reusable definition and
delivery authority without changing a consuming platform's organizational
identity, MCP grants, business work, or runtime semantics accidentally.

The migration is a sequence of verified source-of-truth cuts. It is not a
permanent dual-write system and does not use shadow execution of real work.

## Starting conditions

A consuming platform may begin with definitions spread across runtime profile
directories, database instruction fields, generated configuration, deployment
scripts, or another agent repository. Before implementation, inventory every
reader and writer and classify each field as:

- portable definition content;
- private functional customization and opaque configuration references;
- consumer organizational identity or lifecycle;
- consumer authorization or credentials;
- harness-specific generated output;
- runtime-local state; or
- obsolete projection.

Only tenant-free portable definition content and public skills move into
marketplace packages. Private functional Agent Spec/file customization,
tools/MCP/provider/model/harness configuration, opaque secret references, and
private skill selection move into digest-pinned private bindings. Identity,
roles, authoritative grants, provider access, raw credentials, workload login,
skill-execution approval, sandbox policy, tasks, and conversations remain with
the consumer.

## Phase 0: Freeze contracts and evidence

Before publishing artifacts:

1. Accept [ADR-0001](../architecture/adr/0001-independent-agent-delivery-control-plane.md).
2. Freeze the pinned Agent Spec version and every Agent Delivery authority
   object as a closed JSON Schema Draft 2020-12 schema in the signed offline
   contract bundle. Freeze the strict JSON Patch, file, skill, source-resolution,
   predecessor, OpenAPI 3.2.0, AsyncAPI 3.1.0, and CloudEvents 1.0.2 contracts.
3. Freeze v1 OCI media types and the encoding boundary through contract tests:
   restricted YAML 1.2 JSON-compatible human authoring; JSON data-model
   authority; RFC 8785 JCS hashing/signing bytes; provenance or storage-
   integrity evidence only for original authoring YAML; and exact arbitrary
   payload bytes.
4. Define immutable trust-policy digests, signed consumer-authority and skill-
   approval envelopes, and purpose-separated product/public/consumer-private
   signing. Production private keys are consumer-owned or explicitly opted-in
   tenant-dedicated, never shared across consumers.
5. Define exact renderer-release manifests, executed distribution/worker and
   allowlist identities, capability matrices, deterministic fixtures, and
   sandbox/withdrawal behavior.
6. Record the current source inventory and expected reference roster.
7. Define source-of-truth cutover and forward-recovery gates, the sole
   Promotion Coordinator writer, one DesiredStateStore per target, separate
   lifecycle state machines, and Host versus Consumer Capability Verifier
   evidence for each consumer.

No production runtime changes occur in this phase.

## Phase 1: Marketplace bootstrap

Create the public authoring source with one minimal valid package, strict policy
fixtures, deterministic tenant-free build, and clean-room verification. Prove
that a third party can validate and render the sample without a consumer
platform, and that public endpoints reject customization and private inputs.

The repository is licensed and governed independently. Publication CI receives
only the public source signer identity and cannot sign private deployments.

## Phase 2: Baseline extraction

Migrate the reviewed reference content into exactly:

- 34 selectable employee-agent packages; and
- one non-selectable `office-orchestrator` reference system package.

Extraction preserves public behavioral instructions and portable skill files
while removing tenant customization, identity, reporting, raw credentials,
provider/model/harness configuration, tools, MCP servers, grants, opaque secret
references, private skills, runtime slots, and generated files from public
packages. Skills may include scripts or binaries, but migration and publication
never execute them.

Each package receives provenance back to its reviewed source, official Agent
Spec validation, non-authority policy fixtures, and deterministic package tests.
The catalog asserts the expected 34-plus-one composition explicitly.

If migrated definitions were authored as YAML, reject duplicate keys, aliases,
custom tags, non-string mapping keys, and non-finite numbers before migration.
Retain source YAML only as provenance and compare semantic identity through RFC
8785 canonical JSON. Any integrity reference to the retained YAML remains
provenance/storage-integrity evidence only and is never semantic identity,
artifact authority, or activation authority. Copy arbitrary payload attachments
without transcoding or byte normalization,
including payload files named `.yaml` or `.json`.

## Phase 3: Renderer parity

Implement native Agent Spec, Hermes, and OpenClaw Adapters in that order. For
each legacy profile, separate the tenant-free public baseline from its private
functional customization and authority before comparing output:

1. Render the canonical portable package and public skills with no
   customization, proving that the catalog render is tenant-free.
2. Resolve the private Agent Spec/file delta and exact public/private skill set
   in a private compiler fixture.
3. Fully rerender the effective package and compare its normalized embedded
   bundle with reviewed legacy output.
4. Prove there is no post-render patch and that public-render reuse occurs only
   when customization has no operations, the effective skills exactly equal the
   source-declared public set, and all normalized inputs match.
5. Classify every difference as intended, warning, lossy, or defect.
6. Obtain approval for intended/lossy changes and every executable skill digest.
7. Record the exact renderer-release manifest, executed distribution/worker,
   platform, product distribution, embedded allowlist, renderer schemas,
   immutable trust-policy ID/digest, and golden public/private manifests.

Byte comparison is evidence, not authority. Legacy files remain authoritative
until the renderer and consumer cutover gates pass.

## Phase 4: OCI and trust publication

Publish public source and tenant-free catalog render artifacts by digest. Prove clean rebuild
reproducibility, signature purpose separation, provenance, SBOM, registry
referrers, cross-repository descriptor verification, retention, and restore.
The reproducibility gate includes equivalent accepted YAML/JSON inputs,
rejection of disallowed YAML constructs, fixed RFC 8785 bytes, and exact raw-
byte preservation for arbitrary payload files.

Use non-production registry namespaces and non-exportable test KMS keys during
development. Production key, registry, or runtime mutation requires a separate
consumer authorization and rollout plan.

## Phase 5: Product control plane

Implement catalog, public validation/rendering, inspection, installation,
binding, promotion, private compilation with full effective rerender and
embedded bundle/manifest, desired state, observation, receipt, API, and CLI
contracts. V1 does not publish a separate private-render artifact. Certify the
contracts with a generic consumer Adapter before the first product-specific
integration.

The control plane implements the separate installation, candidate, rollout,
and host-attempt machines; one target aggregate and one selected
DesiredStateStore; exact revision-and-digest CAS; Host technical evidence;
Consumer Capability Verifier evidence; and current-tooling forward recovery.
Its HTTP and event surfaces conform to the signed OpenAPI/AsyncAPI/CloudEvents
contract bundle rather than inventing consumer-specific wire shapes.

This gate prevents the first consumer's database or identity model from
becoming hidden product core.

The standalone core is certified and versioned after this generic product
phase, including the core catalog, renderer, supply-chain, generic consumer,
runtime, API/CLI, failure, and operational-readiness matrices. Phases 6 through
8 are deferred reference-consumer integrations. Their evidence is reported as
separate appendices and cannot change a passed or failed standalone core result.

## Phase 6: Consumer integration

The consuming platform adds an Adapter that:

- maps an import choice to a new or existing consumer-owned profile;
- validates desired private tools/MCP/provider/model/harness configuration and
  resolves opaque secret references without returning raw values to artifacts;
- supplies current lifecycle, policy, approval, grant, provider-access,
  credential-version, executable-skill approval, sandbox, workload, runtime,
  and stable-slot subdigests;
- authenticates control-plane and host calls;
- issues fresh operation-bound signed consumer-authority snapshots and signed
  exact-digest skill approvals with immutable policy digests;
- supplies a distinct Capability Verifier for workload login, one safe
  permitted probe, and one explicit policy-denial sentinel without giving the
  Host Reconciler an agent credential;
- implements the sole DesiredStateStore port when consumer-native persistence
  is selected, with no parallel authoritative Agent Delivery row;
- enforces call-time MCP and provider authorization independently; and
- stores the product installation/deployment references needed for audit.

Existing organizational profile IDs and workload principals are preserved.
Binding a marketplace definition must not create duplicate employee identities
or rotate unrelated credentials.

## Phase 7: Hosted runtime certification

Introduce the engine-scoped host reconciler while legacy content remains the
active source. Exercise pull, verification of the embedded effective render and
skill approvals, stage, safe-boundary switch, canary, observation, crash
recovery, and forward recovery with non-production runtimes. Prove that staging
does not execute skill content and that runtime execution requires signed
exact-digest consumer approval, sandboxing, and current authorization.

Certify the Adapter's declared isolated-candidate or guarded in-place activation
mode. Persist rollout, host attempt, and active-slot facts separately. A
post-switch failure is `recovery_required`; the host reports evidence and never
self-promotes or writes a `rolled_back` state.

Stable slots are backfilled from actual profile-to-runtime ownership, not
derived from the current roster order. Retired slots are tombstoned. The
reference system package receives a reserved system slot where required.

## Phase 8: Per-harness source cutover

Hermes and OpenClaw cut over separately. Each cutover requires:

- all expected definitions rendered and target-parser valid;
- exact source, binding/customization, selected-skill, embedded-effective-render,
  deployment, and release digest traceability;
- one Promotion Coordinator writer and one selected DesiredStateStore with
  exact CAS and no live dual write;
- stable-slot and profile identity proof;
- separate signed Host technical and Consumer Capability Verifier evidence,
  including positive workload login/granted invocation and explicit policy
  denial for ungranted, wrong-tenant, stale-revision, and wrong-subdigest cases;
- canary and forward-recovery drill; and
- a cleanup list for legacy writers and files.

At the cutover transaction, the consumer changes its definition source to the
verified Agent Delivery release. It does not run both legacy and new activation
writers. Shadow comparison of deterministic output is allowed; shadow execution
of business work is not.

## Legacy removal

After a harness cutover is stable:

- disable and remove legacy definition writers;
- remove or clearly archive copied runtime definitions;
- make generated output read-only or regeneration-only;
- remove compatibility write paths from old database fields;
- update operator commands and source-of-truth documentation;
- retain migration mappings and receipts for audit; and
- add a test that changing the legacy source cannot change deployment.

Consumer fields that mixed identity and instruction content are split. Identity
and lifecycle stay in the consumer; instruction projections are removed only
after all readers cut over.

## Forward recovery during migration

Before source cutover, recovery means leaving the legacy source authoritative
and correcting the candidate. After source cutover, recovery searches prior
successfully promoted functional content newest first and requalifies it under
current schemas, withdrawal/revocation state, signed skill approvals, signed
consumer authority, target compatibility, and trust. It never executes revoked
renderer/compiler tooling; changed tooling creates a new evaluated public-render
lineage. It emits a new deployment and target revision and never reactivates an
old artifact, receipt, signature, or authority snapshot.

Known-good history is not automatic eligibility. Recovery does not depend on
Git availability and never silently drops or substitutes a functional
dependency. If no candidate qualifies, it fails closed and invokes consumer
incident policy.

Re-enabling a legacy writer after cutover is not an approved rollback because
it creates two authorities and can restore stale configuration.

## No-confusion completion gate

A migration is complete only when:

- canonical product documents and contracts live in this repository;
- consumer repositories contain only explicit integration profiles and no
  duplicate product architecture;
- legacy source files cannot affect an active deployment;
- Jira or knowledge-base planning records point to this repository as the
  transferred product source, rather than claiming consumer implementation;
- the 34 selectable plus one system reference catalog is certified;
- clean-room third-party verification passes; and
- each integrated harness has an exact receipt and recovery drill.

## First consumer note

ByteDesk Platform is the first reference consumer. Its integration is documented
in [the consumer profile](../integrations/bytedesk-platform.md), but its internal
identity, MCP, and runtime decisions are not normative for other consumers.

No integration is GA until the measured availability, latency, capacity,
durability, restore, security-response, compatibility, support, and 30-day
production-equivalent evidence in
[Operational readiness v1](../standards/operational-readiness-v1.md) passes.

## Related pages

- [Marketplace and baseline catalog](03-marketplace-repository-and-baseline-catalog.md)
- [Harness adapters](04-harness-adapters-and-renderers.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
