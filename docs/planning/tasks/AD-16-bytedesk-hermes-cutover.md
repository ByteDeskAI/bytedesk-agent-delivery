# AD-16: Cut the ByteDesk Hermes canonical source to marketplace artifacts

- Historical Jira: [BDP-3317](https://bytedesk.atlassian.net/browse/BDP-3317)
- Delivery role: Reference-consumer integration
- Core release gate: No — this task does not block a standalone Agent Delivery release
- Integration repositories: `bytedesk-platform` and any managed Hermes deployment repository

## Outcome

Integrate ByteDesk Platform as a reference consumer and remove `ops/hermes-native` definitions as its canonical authoring source after marketplace, renderer, private compilation, and deployment parity are proven. Retain only migration or adapter fixtures explicitly justified by tests.

## Inputs

- Published baseline catalog and Hermes renderer from AD-03 and AD-05.
- OCI trust, consumer-private compilation, and hosted reconciliation from AD-08, AD-13, and AD-14.
- Current Platform `ops/hermes-native` inventory and ADR-0180/ADR-0182 behavior.
- Proven last-known-good Agent Delivery deployment receipts.
- A separately approved ByteDesk Platform integration task/worktree; no changes are implemented in the Agent Delivery repository alone.

## Required work

1. Produce a cutover diff for all 34 employees and `office-orchestrator`, including instructions, IDs, model defaults, optional skills, and runtime-binding behavior.
2. Update ByteDesk deployment and provisioning paths to resolve exact marketplace, render, and private deployment digests through the Agent Delivery consumer adapter rather than reading canonical profiles from `ops/hermes-native`.
3. Migrate non-production ByteDesk desired state to exact pins and compile/reconcile through the new pipeline.
4. Run dual-read/shadow comparison only as a bounded deterministic validation mode; there is one activation writer and no shadow execution.
5. Remove or clearly demote legacy authoring files/scripts after acceptance and update Platform ADRs, rules, runbooks, DTOs, routers, lifecycle paths, and tests that name the old source.
6. Preserve a tested rollback to a newly compiled receipt using last-known-good definition content and current Platform authority, not to mutable legacy files or a reactivated receipt.
7. Keep ByteDesk organizational identity, roles, MCP/tool/resource grants, provider connections, credentials, workload login/certificates, and business approval governed by Platform ADR-0182 and related Platform policy. Agent Delivery only carries signed references and evidence.

## Outputs

- ByteDesk Platform/Hermes source-cutover changes delivered through the Platform's normal Jira, worktree, PR, and landing lifecycle.
- Full parity and cutover report.
- Updated Platform docs/rules/tests with no false legacy source-of-truth claims.
- Verified forward-only rollback artifact and receipts.
- Reference-consumer integration guide and reusable contract-test results contributed back to Agent Delivery documentation where generic.

## Acceptance criteria

- Editing a legacy `ops/hermes-native` profile cannot change a deployed agent.
- Every running non-production ByteDesk Hermes profile traces to signed marketplace and OCI receipts.
- All 35 package mappings pass parity or have reviewed intentional differences.
- Platform workload login and allowed/denied MCP behavior remain green under Platform-owned grants.
- Legacy source removal/demotion does not break provisioning or recovery.
- Agent Delivery has no ability to create or broaden a ByteDesk principal, role, grant, credential, or provider connection.
- Failure or non-completion of this reference integration does not prevent a core Agent Delivery release satisfying AD-18's core certification.

## Verification

Run full-catalog render, compile, and deploy; deterministic shadow comparison; local/non-production hosted Hermes certification; legacy-mutation negative test; Platform positive/negative workload-login and MCP authorization tests; restart/recovery; and forward-only rollback.

## Not in scope

Production release, unrelated ByteDesk Platform refactoring, changes to Platform authorization semantics, or core Agent Delivery release certification.

## Dependencies

Blocked by AD-05, AD-14, and AD-15. It is not a dependency of the standalone core release; it is a dependency of the ByteDesk reference appendix in AD-18.

## Architecture review amendments

- Remove the compatibility write path for ByteDesk `AgentInstructions`, `HermesAgentId`, `LastSoulHash`, `LastDeployedAt`, and `DeployStatus` after backfill/read migration. Update every affected DTO, service, router, and lifecycle consumer so no second definition source remains.
- Shadow work is limited to deterministic artifact/output comparison; there is never shadow execution or dual activation writers.
- Preserve existing engine/profile slots and Platform workload principals while rebinding them to per-profile deployment subdigests plus the engine release.
- Rollback is a new signed forward receipt compiled with current Platform grants, lifecycle, slot, credential binding, and workload identity. It never uses mutable legacy files or reactivated history.
- The ByteDesk adapter projects Agent Delivery receipts into the existing Platform `AgentDeploymentRevision` and observation model; it must not create a duplicate Platform receipt aggregate.
