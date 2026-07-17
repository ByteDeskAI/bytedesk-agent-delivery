# AD-09: Persist definition bindings and deployment receipts

- Historical Jira: [BDP-3310](https://bytedesk.atlassian.net/browse/BDP-3310)
- Delivery role: Core product control plane
- Release gate: Blocks install/import, reconciliation, compilation, and deployment

## Outcome

Persist consumer installations, immutable agent-definition binding revisions, and append-only deployment receipts without copying a consuming platform's organizational identity, mutable agent definition, grants, or authorization state.

Agent Delivery owns delivery lineage and evidence. A consuming platform remains the authority for its tenant, organization, agent/person identity, roles, MCP/tool/resource grants, provider connections, credentials, workload identity, and business approvals. A consumer adapter may project Agent Delivery receipt references into its existing deployment record, but must not introduce a second competing receipt aggregate in that platform.

## Inputs

- AD-01 data model/state machine and consumer-ownership invariants.
- Consumer integration contract, including opaque installation, subject, target, desired-state, and authorization-policy references.
- OCI and trust contracts from AD-07 and AD-08.
- Historical ByteDesk `AgentOrgProfile`, `HermesEngine`, `AgentDeploymentRevision`, observation, audit, outbox, and identity behavior as reference-consumer compatibility constraints only.

## Required work

1. Add a consumer-neutral installation aggregate that identifies the consuming system and isolation scope without becoming that system's tenant or user directory.
2. Add immutable definition-binding revisions containing marketplace ID/version/channel, source digest, harness ID, render digest, overlay digest, opaque consumer subject and target references, compatibility/policy decision digests, predecessor, and active/superseded state.
3. Add append-only deployment receipts recording private deployment digest, signer/trust-policy version, exact target and desired-state revision, observed rollout/canary state, health evidence, actor/correlation, predecessor, and forward-only rollback linkage.
4. Define adapter compatibility for consumers with existing deployment records. The ByteDesk Platform adapter must evolve/project through its existing `AgentDeploymentRevision`; it must not add a duplicate receipt table or retroactively label legacy payloads as verified OCI artifacts.
5. Enforce one active definition binding per installation, consumer subject, harness, and target scope without deleting history.
6. Model legal transitions explicitly. Duplicate/replayed commands are idempotent; cross-installation, subject, target, revision, signer, and digest mismatches fail closed.
7. Store only opaque authorization-policy, lifecycle, grant-revision, credential-binding, and workload-identity references/digests when they are needed for compilation evidence. Never store or administer the underlying grants, secrets, certificates, provider tokens, or user roles.
8. Emit auditable domain/outbox events for binding and deployment-receipt transitions.

## Outputs

- Installation, definition-binding revision, deployment-receipt, and observation data contracts with migrations.
- Domain services/commands for legal state transitions.
- Consumer projection/adapter contract, including the no-duplicate-receipt rule.
- Legacy classification guidance for reference consumers.
- Unit, repository, isolation, concurrency, idempotency, transition, and migration tests.

## Acceptance criteria

- No mutable canonical definition body, consumer identity directory, grant store, credential store, or duplicate consumer receipt table is introduced.
- Every active deployment traces installation and consumer subject → binding → source/render/private deployment digest → signer/policy → append-only receipt.
- Illegal, stale, replayed, and cross-installation/subject/target transitions fail consistently.
- History is append-only. Rollback creates a new forward receipt pointing at last-known-good content and the failed predecessor; an old receipt is never reactivated.
- Existing consumer identity, role, grant, certificate, workload-login, and MCP enforcement remains external and unchanged.
- Product deletion/retention behavior cannot orphan an active, last-known-good, legal-hold, or audit-referenced receipt chain.

## Verification

Use TDD with invalid transitions and concurrency first. Run focused unit/integration/migration validation, idempotency and replay tests, cross-installation isolation tests, consumer-adapter contract tests, retention tests, and compatibility tests over historical ByteDesk v2 rows in the reference adapter.

## Not in scope

Catalog APIs, consumer organizational-profile creation, authorization/grant administration, private artifact compilation, or hosted reconciliation.

## Dependencies

Blocked by AD-01 and the contracts from AD-07 and AD-08.

## Architecture review amendments

- Binding and receipt state is per consumer subject and target. Record per-target source, render, overlay, and private deployment subdigests under a signed release manifest.
- A consumer may bind its workload principal to `consumer subject + runtime slot + profile deployment subdigest + release`, but Agent Delivery only carries the signed reference and evidence; the consumer creates and authorizes the principal.
- Updating one subject must not advance unrelated subjects. A system-package change may require a target-wide release and must be explicit.
- Consumer definition/deployment fields must be migrated away from mutable organizational-profile records. For ByteDesk this includes `AgentInstructions`, `HermesAgentId`, `LastSoulHash`, `LastDeployedAt`, and `DeployStatus`; that migration belongs to AD-16 and its Platform integration, not the core product.
- Persist stable target-slot observations and tombstones only as supplied by the runtime adapter. Never allocate by roster index or silently reuse a retired slot; the consuming runtime remains slot authority.
- Preserve each consumer's existing deployment-revision/observation aggregate through a projection or external reference rather than adding a parallel receipt system inside that consumer.
