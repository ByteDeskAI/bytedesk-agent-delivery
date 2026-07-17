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
- consumer organizational identity or lifecycle;
- consumer authorization or credentials;
- harness-specific generated output;
- runtime-local state; or
- obsolete projection.

Only portable definition content moves into marketplace packages. Identity,
roles, MCP grants, provider connections, credentials, workload login, tasks,
and conversations remain with the consumer.

## Phase 0: Freeze contracts and evidence

Before publishing artifacts:

1. Accept [ADR-0001](../architecture/adr/0001-independent-agent-delivery-control-plane.md).
2. Freeze the pinned Agent Spec version and binding schema.
3. Freeze v1 OCI media types and canonical encodings through contract tests.
4. Define independent trust policies and key-rotation procedure.
5. Define renderer capability matrices and deterministic fixtures.
6. Record the current source inventory and expected reference roster.
7. Define source-of-truth cutover and rollback gates for each consumer.

No production runtime changes occur in this phase.

## Phase 1: Marketplace bootstrap

Create the public authoring source with one minimal valid package, strict policy
fixtures, deterministic build, and clean-room verification. Prove that a third
party can validate and render the sample without a consumer platform.

The repository is licensed and governed independently. Publication CI receives
only the public source signer identity and cannot sign private deployments.

## Phase 2: Baseline extraction

Migrate the reviewed reference content into exactly:

- 34 selectable employee-agent packages; and
- one non-selectable `office-orchestrator` reference system package.

Extraction preserves behavioral instructions and inspectable portable skills
while removing consumer-specific identity, reporting, credentials, provider
configuration, tools, MCP servers, grants, runtime slots, and generated files.

Each package receives provenance back to its reviewed source, official Agent
Spec validation, non-authority policy fixtures, and deterministic package tests.
The catalog asserts the expected 34-plus-one composition explicitly.

## Phase 3: Renderer parity

Implement native Agent Spec, Hermes, and OpenClaw Adapters in that order. For
each legacy profile:

1. Render from the canonical portable package.
2. Compare normalized files and supported semantics with reviewed legacy
   output.
3. Classify every difference as intended, warning, lossy, or defect.
4. Obtain approval for intended/lossy changes.
5. Record the renderer version and golden manifest.

Byte comparison is evidence, not authority. Legacy files remain authoritative
until the renderer and consumer cutover gates pass.

## Phase 4: OCI and trust publication

Publish source and render artifacts by digest. Prove clean rebuild
reproducibility, signature purpose separation, provenance, SBOM, registry
referrers, cross-repository descriptor verification, retention, and restore.

Use non-production registry namespaces and non-exportable test KMS keys during
development. Production key, registry, or runtime mutation requires a separate
consumer authorization and rollout plan.

## Phase 5: Product control plane

Implement catalog, validation, rendering, inspection, installation, binding,
promotion, private compilation, desired state, observation, receipt, API, and
CLI contracts. Certify them with a generic consumer Adapter before the first
product-specific integration.

This gate prevents the first consumer's database or identity model from
becoming hidden product core.

## Phase 6: Consumer integration

The consuming platform adds an Adapter that:

- maps an import choice to a new or existing consumer-owned profile;
- supplies current lifecycle, policy, approval, grant, provider, credential
  version, workload, runtime, and stable-slot subdigests;
- authenticates control-plane and host calls;
- enforces call-time MCP and provider authorization independently; and
- stores the product installation/deployment references needed for audit.

Existing organizational profile IDs and workload principals are preserved.
Binding a marketplace definition must not create duplicate employee identities
or rotate unrelated credentials.

## Phase 7: Hosted runtime certification

Introduce the engine-scoped host reconciler while legacy content remains the
active source. Exercise pull, verify, stage, safe-boundary switch, canary,
observation, crash recovery, and forward rollback with non-production runtimes.

Stable slots are backfilled from actual profile-to-runtime ownership, not
derived from the current roster order. Retired slots are tombstoned. The
reference system package receives a reserved system slot where required.

## Phase 8: Per-harness source cutover

Hermes and OpenClaw cut over separately. Each cutover requires:

- all expected definitions rendered and target-parser valid;
- exact source/render/deployment/release digest traceability;
- one active desired-state writer;
- stable-slot and profile identity proof;
- positive workload login plus granted MCP invocation;
- negative ungranted, wrong-tenant, stale-revision, and wrong-subdigest tests;
- canary and forward-rollback drill; and
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

## Rollback during migration

Before source cutover, rollback means leaving the legacy source authoritative
and correcting the candidate. After source cutover, rollback follows the normal
forward-rollback process and recompiles last-known-good definition content with
current consumer policy, grants, credentials, and lifecycle.

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

## Related pages

- [Marketplace and baseline catalog](03-marketplace-repository-and-baseline-catalog.md)
- [Harness adapters](04-harness-adapters-and-renderers.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
