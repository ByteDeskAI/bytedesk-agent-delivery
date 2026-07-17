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
- Historical ByteDesk `AgentOrgProfile`, `HermesEngine`, `AgentDeploymentRevision`, observation, audit, outbox, and identity behavior as reference-consumer compatibility constraints only.

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
4. Define adapter compatibility for consumers with existing deployment records. The ByteDesk Platform adapter must evolve/project through its existing `AgentDeploymentRevision`; it must not add a duplicate receipt table or retroactively label legacy payloads as verified OCI artifacts.
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
  recover operations; a compilation snapshot cannot authorize activation.
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
historical-reference-adapter compatibility tests.

## Not in scope

Catalog APIs, consumer organizational-profile creation, authorization/grant administration, private artifact compilation, or hosted reconciliation.

## Dependencies

Blocked by AD-01 and AD-08.

## Architecture review amendments

- Binding and receipt state is per consumer subject and target. Record per-target source, public catalog render, customization, exact skills, embedded effective render, and private deployment subdigests under a signed release manifest.
- A consumer may bind its workload principal to `consumer subject + runtime slot + profile deployment subdigest + release`, but Agent Delivery only carries the signed reference and evidence; the consumer creates and authorizes the principal.
- Updating one subject must not advance unrelated subjects. A system-package change may require a target-wide release and must be explicit.
- Consumer definition/deployment fields must be migrated away from mutable organizational-profile records. For ByteDesk this includes `AgentInstructions`, `HermesAgentId`, `LastSoulHash`, `LastDeployedAt`, and `DeployStatus`; that migration belongs to AD-16 and its Platform integration, not the core product.
- Persist stable target-slot observations and tombstones only as supplied by the runtime adapter. Never allocate by roster index or silently reuse a retired slot; the consuming runtime remains slot authority.
- Preserve each consumer's existing deployment-revision/observation aggregate through a projection or external reference rather than adding a parallel receipt system inside that consumer.
