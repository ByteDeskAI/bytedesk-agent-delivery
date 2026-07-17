# AD-01: Accept the Agent Spec and OCI delivery architecture

- Historical Jira: [BDP-3302](https://bytedesk.atlassian.net/browse/BDP-3302)
- Delivery role: Core product
- Release gate: Blocks implementation work

## Outcome

Land the architectural source of truth for ByteDesk Agent Delivery and its separate, open Agent Spec marketplace before implementation begins.

## Inputs

- The decisions extracted from historical epic BDP-3301.
- Agent Spec 26.1.2 language, schema, and official validator.
- OCI Image and Distribution 1.1 subject/referrer behavior, ORAS artifact conventions, registry capabilities, Cosign KMS signing, and in-toto attestations.
- The architecture package in this repository, including ADR-0001, the consumer integration contract, the OCI artifact model, runtime reconciliation, and security/trust documents.
- Historical ByteDesk Platform ADR-0174, ADR-0180, ADR-0182, and ADR-0187 as reference-consumer context only.
- Current Hermes and OpenClaw definitions and delivery behavior as migration evidence, not as Agent Delivery source code or authority.

## Required work

1. Accept ADR-0001 with explicit product and consumer ownership boundaries, artifact graph and media types, binding rules, overlay rules, trust policy, promotion state machine, rollback, retention, and supersession language.
2. Add C4 views for authoring, publication, import, specialization, compilation, reconciliation, activation, and rollback.
3. Complete the documentation hierarchy covering overview, schema, catalog, adapters, OCI graph, supply-chain trust, product data/API ownership, consumer Git, promotion, hosted deployment, CLI, migration/cutover, and test/operations.
4. Maintain runnable task specifications and a dependency manifest for AD-01 through AD-18.
5. Record threats and fail-closed behavior for digest substitution, signer compromise, replay, cross-consumer binding, malicious overlays, downgrade, missing referrers, stale receipts, registry outage, and webhook duplication.
6. Define the integration seam through which a consuming platform supplies identity, roles, MCP/tool/resource grants, provider connections, credentials, workload authentication, and business approvals. Agent Delivery must not become the authority for any of them.

## Outputs

- Accepted ADR-0001 in `docs/architecture/adr/`.
- Validated architecture workspace and views.
- Complete repository documentation hierarchy linked from the ADR and task plan.
- Task specifications and dependency manifest with historical Jira keys.
- An explicit supersession matrix showing which historical Platform decisions become consumer-adapter concerns and which remain authoritative in the Platform.

## Acceptance criteria

- A developer can implement every later task without inventing an ownership, schema, media-type, state-transition, security, or rollback decision.
- No marketplace package contains required MCP, tool, grant, resource, provider, credential, tenant, or workload-identity fields.
- Agent Delivery stores content-addressed references, bindings, state, and receipts, not a second mutable consumer agent definition or organizational identity.
- Artifact activation requires an exact digest, trusted signature, required policy evidence, an exact consumer/subject/target binding, and the current desired-state revision.
- Architecture and ADR validation are green.

## Verification

Run ADR validation, C4/Structurizr validation and export, documentation link checking, task-manifest validation, and peer architecture review against the five hole buckets: requirements, dependencies, failure modes, migration/compatibility, and verification/operations.

## Not in scope

Marketplace repository creation, runtime code, registry mutation outside non-production test fixtures, consumer integration implementation, or production release.

## Dependencies

None.

## Architecture review amendments

ADR-0001 and its architecture package must close all eight findings carried forward from the review:

1. Define a constrained `bytedesk.agent-binding/1` envelope and require official Agent Spec validation.
2. Define per-target definition/runtime subdigests under a signed release. A consuming platform may bind its workload identity tuple to those digests, but Agent Delivery neither issues nor authorizes that identity.
3. Prevent consumer organizational-profile definition or deployment fields from becoming a second source of truth; migration of such fields belongs in each consumer adapter.
4. Permit automatic update only when skill digests are unchanged; retain quarantine and approval for changed or high-risk skills.
5. Keep OCI referrers repository-local and represent cross-repository edges as explicit signed digest descriptors.
6. Use purpose-separated, non-exportable KMS/WIF trust with rotation, revocation, least privilege, and privacy controls.
7. Define durable runtime slots and tombstones plus a target-bound host identity; slot ownership remains with the consuming runtime.
8. Define control-plane-to-host ownership, outbox/inbox delivery, async operation status, rollout lease/CAS, and complete failure/recovery states without importing consumer authorization.

The architecture must also define archive safety; signed catalog, release, and withdrawal semantics; import identity rules; registry retention, garbage collection, backup, and restore; and the complete positive, negative, and fault-injection test matrix. Runtime tasks remain blocked until these decisions are explicit.
