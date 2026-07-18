# AD-09: Persist definition bindings and deployment receipts

- Historical Jira: [BDP-3310](https://bytedesk.atlassian.net/browse/BDP-3310)
- Delivery role: Core product control plane
- Release gate: Starts `CONTROL-PLANE-CERT`

## Outcome

Persist consumer installations, exact renderer-bound definition revisions,
signed consumer-authority/skill-approval evidence, sole-writer target delivery
state, and append-only observations/receipts without copying or interpreting the
consumer's identity, grants, credentials, or authorization state.

Agent Delivery owns delivery lineage and evidence. A consuming platform remains the authority for its tenant, organization, agent/person identity, roles, MCP/tool/resource grants, provider connections, credentials, workload identity, and business approvals. A consumer adapter may project Agent Delivery receipt references into its existing deployment record, but must not introduce a second competing receipt aggregate in that platform.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- AD-01 data model/state machine and consumer-ownership invariants.
- Consumer integration contract, including opaque installation, subject, target, desired-state, and authorization-policy references.
- OCI and trust contracts from AD-07 and AD-08.
- Machine-contract, renderer-identity, consumer-authority/private-signing, and
  delivery-lifecycle schemas from CONTRACTS-FROZEN.
- An exact `bytedesk.external-input-lock/1` artifact for the ByteDesk
  `AgentOrgProfile`, `HermesEngine`, `AgentDeploymentRevision`, observation,
  audit, outbox, and identity behavior used as reference-consumer compatibility
  evidence. The lock binds repository URL, immutable commit, source-tree digest,
  sorted path/digest inventory, and `compatibilityEvidenceOnly: true`; no
  consumer-specific model becomes core contract authority.

## Required work

1. Add a consumer-neutral installation aggregate that identifies the consuming system and isolation scope without becoming that system's tenant or user directory.
2. Implement immutable binding revisions with exact source and complete
   renderer-release descriptors, strict functional/file/skill operations,
   source/output kinds, exact skills/approvals, schema/trust digests, and the
   required absent/match precondition plus immutable predecessor lineage.
3. Implement closed signed consumer-authority and skill-approval evidence
   records with purpose, consumer/subject/installation/target/candidate/desired
   revision, nonce, issue/expiry, policy, and current opaque subdigest binding.
   Credential values and authority subdocuments never enter the store.
4. Define adapter compatibility for consumers with preexisting deployment
   records. The ByteDesk Platform adapter may evolve/project through only the
   exact `AgentDeploymentRevision` behavior named by the accepted external-input
   lock; it must not add a duplicate receipt table or retroactively label legacy
   payloads as verified OCI artifacts.
5. Enforce one active definition binding per installation, consumer subject, harness, and target scope without deleting history.
6. Model installation, candidate preparation, target rollout, host-attempt,
   slot/generation, observation, and receipt facts as separate schemas and
   transition models. Persist one `TargetDeliveryState` aggregate per consumer
   target in exactly one selected DesiredStateStore.
7. Allow the private customization to change any functional Agent Spec property, perform explicit regular-file add/replace/remove operations, select exact skills, and configure functional model/provider/tool/MCP/harness behavior with opaque secret references. Store security authority only as opaque policy, lifecycle, grant-revision, credential-binding, and workload-identity references/digests. Never store or administer underlying grants, secret values, certificates, provider tokens, trust roots, or user roles.
8. Emit auditable domain/outbox events for binding and deployment-receipt transitions.
9. Enforce that only the Promotion Coordinator port can CAS
   `TargetDeliveryState`. Git, compilers, update bots, hosts, observations,
   capability verifiers, and direct operators can submit intent or evidence but
   cannot write desired state.
10. Add append-only receipts that bind schema/trust/renderer/authority/canary
    evidence and distinguish current predecessor from historical
    `recoverySource`. No receipt or observation can promote itself.
11. Resolve complete consumer-authority and skill-approval objects plus their
    exact descriptors and full signing results. Persist the closed sorted
    private-input authentication bundle used by AD-13; a bare digest or
    repository-name classification cannot authenticate a private input.

## Outputs

- Installation, binding, authority/approval, candidate, TargetDeliveryState,
  rollout, host-attempt, canary, recovery, receipt, observation, slot, and
  DesiredStateStore data contracts with migrations and signed bundle entries.
- Domain services/commands for legal state transitions.
- Consumer projection/adapter contract, including the no-duplicate-receipt rule.
- Legacy classification guidance for reference consumers.
- Unit, repository, isolation, concurrency, idempotency, transition, and migration tests.
- Managed and consumer-native DesiredStateStore conformance suites and audited
  single-writer store-migration fixtures.

## Acceptance criteria

- No mutable canonical definition body, consumer identity directory, grant store, credential store, or duplicate consumer receipt table is introduced.
- Every active deployment traces installation and consumer subject → binding/customization → source/public catalog render/skills → embedded private effective render/private deployment digest → signer/policy → append-only receipt.
- Illegal, stale, replayed, and cross-installation/subject/target transitions fail consistently.
- Initial creation requires `absent`; every update requires the exact prior
  revision and digest. Wildcard/null/digest-only/lease-only mutation and ABA
  fail without side effects.
- Renderer semantic version alone is never accepted; binding and receipt
  lineage preserve the exact release manifest and executed product identity.
- Fresh authority evidence is separately required for compile, activate, and
  recover operations. Compile authority signs the complete AD-13 authorized
  private-input digest; that field is forbidden on activate and recover, and a
  compilation snapshot cannot authorize either operation.
- Every private input's role, subject, media type, descriptor, trust policy, and
  complete signing result are reconstructible from the persisted
  authentication bundle; missing or mismatched objects fail before compile.
- There is one desired-state aggregate and one logical writer per target. Store
  migration is quiesced and audited; live dual writing is forbidden.
- History is append-only. Recovery creates a new forward revision with current
  predecessor plus separate historical recoverySource; old receipts and
  authority are never reactivated.
- Existing consumer identity, role, grant, certificate, workload-login, and MCP enforcement remains external and unchanged.
- Product deletion/retention behavior cannot orphan an active, last-known-good, legal-hold, or audit-referenced receipt chain.
- Reading, writing, migrating, and replaying a binding or receipt reproduces the same JCS bytes; forbidden YAML/JSON parser ambiguity is rejected before persistence.

## Verification

Use TDD with invalid transitions and concurrency first. Run schema/offline
bundle, strict operation, source-kind, absent/match/ABA, exhaustive legal/
illegal lifecycle, authority freshness/nonce/replay/cross-consumer, exact
renderer identity, idempotency, managed/consumer-native store, no-dual-write
migration, observation non-authority, retention, isolation, redaction, and
  historical-reference-adapter compatibility tests. Consumer-authority tests
  include compile-only signed authorized-input-digest presence, mismatch,
  non-compile smuggling, and denied-verification-without-success-result cases.
  They also include missing authority/approval objects, signing-result
  substitution, role/media mismatch, and repository-prefix classification
  denial.

## Not in scope

Catalog APIs, consumer organizational-profile creation, authorization/grant administration, private artifact compilation, or hosted reconciliation.

## Dependencies

Blocked by AD-01 and AD-08.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.consumer-authority-approval/1`
  (`resolve-authority-snapshot`, `resolve-skill-approval`,
  `verify-private-authority`), `bytedesk.port.consumer-projection/1`
  (`resolve-consumer-subject`, `project-consumer-receipt`), and
  `bytedesk.port.desired-state-store/1` (`read-target-state`,
  `watch-target-state`, `compare-and-swap-target-state`, `resolve-idempotency`,
  `read-target-history`, `migrate-target-state`) are registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Exact schema IDs include
  `https://schemas.bytedesk.ai/agent-delivery/v1/installation/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-authority/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/skill-approval/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/target-delivery-state/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/deployment-receipt/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/desired-state-store-receipt/1.0.0`,
  and
  `https://schemas.bytedesk.ai/agent-delivery/v1/desired-state-store-migration/1.0.0`,
  under `contracts/schemas/v1/`. Managed/consumer-native store, projection,
  authority, approval, migration, and external-input-lock profiles are in
  `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-09 owns aggregate persistence, absent/match CAS,
  authority/approval evidence, no-duplicate-receipt projection, both
  DesiredStateStore variants, and quiesced migration fixtures. Run
  `make verify-downstream-ports`; the task-specific suite is
  `downstream.consumer-state.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Boundary.** Agent Delivery stores delivery lineage and opaque signed
  references only. Consumer identity, roles, grants, credentials, workload
  identity, business approval, and underlying authorization state remain
  consumer-owned and cannot be copied into core contracts or a duplicate
  consumer receipt aggregate.

## Architecture review amendments

- Binding and receipt state is per consumer subject and target. Record per-target source, public catalog render, customization, exact skills, embedded effective render, and canonical private deployment descriptors under a signed release manifest.
- A consumer may bind its workload principal to `consumer subject + runtime slot + exact profile deployment descriptor + release`, but Agent Delivery only carries the signed reference and evidence; the consumer creates and authorizes the principal.
- Updating one subject must not advance unrelated subjects. A system-package change may require a target-wide release and must be explicit.
- Consumer definition/deployment fields must be migrated away from mutable organizational-profile records. For ByteDesk this includes `AgentInstructions`, `HermesAgentId`, `LastSoulHash`, `LastDeployedAt`, and `DeployStatus`; that migration belongs to AD-16 and its Platform integration, not the core product.
- Persist stable target-slot observations and tombstones only as supplied by the runtime adapter. Never allocate by roster index or silently reuse a retired slot; the consuming runtime remains slot authority.
- Preserve a consumer's deployment-revision/observation aggregate through a
  projection or external reference rather than adding a parallel receipt system
  inside that consumer; reference-consumer behavior must come from an accepted
  exact external-input lock.
