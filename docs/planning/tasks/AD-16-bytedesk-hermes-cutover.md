# AD-16: Cut the ByteDesk Hermes canonical source to marketplace artifacts

- Historical Jira: [BDP-3317](https://bytedesk.atlassian.net/browse/BDP-3317)
- Delivery role: Reference-consumer integration
- Core release gate: No — this task does not block a standalone Agent Delivery release
- Reference gate: Contributes to `REFERENCE-CONSUMER-CERT`
- Integration repositories: `bytedesk-platform` and any managed Hermes deployment repository

## Outcome

Integrate ByteDesk Platform as a reference consumer and remove `ops/hermes-native` definitions as its canonical authoring source after marketplace, renderer, private compilation, and deployment parity are proven. Retain only migration or adapter fixtures explicitly justified by tests.

## Inputs

- [ADR-0002](../../architecture/adr/0002-implementation-stack-and-reference-topology.md)
  for the pinned CORE-CERT host/integration protocol only; the consumer keeps
  its own implementation technology behind the Adapter.

- Pinned CORE-CERT release with Hermes renderer, OCI/trust, control-plane,
  compiler, reconciler, API, CLI, and contract bundles.
- REFERENCE-CATALOG-CERT when the cutover selects ByteDesk's 34+1 catalog.
- Current Platform `ops/hermes-native` inventory and ADR-0180/ADR-0182 behavior.
- Proven last-known-good Agent Delivery deployment receipts.
- A separately approved ByteDesk Platform integration task/worktree; no changes are implemented in the Agent Delivery repository alone.

## Required work

1. Produce a cutover diff for all 34 employees and `office-orchestrator`, including instructions, IDs, model defaults, optional skills, and runtime-binding behavior.
2. Update ByteDesk deployment and provisioning paths to resolve exact marketplace source, public catalog render, private customization/skill set, effective render, and deployment digests through the Agent Delivery consumer adapter rather than reading canonical profiles from `ops/hermes-native`.
3. Migrate non-production ByteDesk desired state to exact pins and compile/reconcile through the new pipeline.
4. Run dual-read/shadow comparison only as a bounded deterministic validation mode; there is one activation writer and no shadow execution.
5. Remove or clearly demote legacy authoring files/scripts after acceptance and update Platform ADRs, rules, runbooks, DTOs, routers, lifecycle paths, and tests that name the old source.
6. Preserve tested forward recovery through a newly compiled rollout using
   eligible historical functional content and current Platform authority and
   tooling, not mutable legacy files or reactivated state.
7. Let ByteDesk privately customize every functional property needed for Hermes, including instructions, behavior, provider/model selection, functional tool/MCP and harness configuration, arbitrary approved files/skills, and opaque secret references. Keep ByteDesk organizational identity, roles, MCP/tool/resource grants, provider authority, credentials, workload login/certificates, trust roots/signers, mandatory security controls, and business approval governed by Platform ADR-0182 and related Platform policy. Agent Delivery only carries signed references and evidence for those security-authority concerns.
8. Verify that the private compiler performs a full Hermes re-render from the effective Agent Spec and approved skills and embeds that render in the deployment. Do not patch the public Hermes render after rendering.
9. Integrate Platform-issued short-lived consumer-authority and skill-approval
   evidence plus consumer-owned or tenant-dedicated per-consumer authority and
   deployment signing keys. Never share private keys across consumers.
10. Use one Promotion Coordinator/DesiredStateStore authority for each engine.
    Platform Git and deployment projections are inputs/read models, the Hermes
    host appends technical observations only, and a distinct Platform
    capability verifier performs workload-login and MCP allow/deny probes.
11. Migrate ByteDesk customization to the strict functional/file/skill
    operation profiles with exact preconditions and no consumer-specific schema
    fork.

## Outputs

- ByteDesk Platform/Hermes source-cutover changes delivered through the Platform's normal Jira, worktree, PR, and landing lifecycle.
- Full parity and cutover report.
- Updated Platform docs/rules/tests with no false legacy source-of-truth claims.
- Verified current-tooling forward-recovery rollout and receipts.
- Reference-consumer integration guide and reusable contract-test results contributed back to Agent Delivery documentation where generic.
- REFERENCE-CONSUMER-CERT evidence linking CORE-CERT and
  REFERENCE-CATALOG-CERT plus exact Adapter, authority, key, rollout, canary,
  cutover, recovery, SLO, and support/runbook digests.

## Acceptance criteria

- Editing a legacy `ops/hermes-native` profile cannot change a deployed agent.
- Every running non-production ByteDesk Hermes profile traces to signed marketplace and OCI receipts.
- All 35 package mappings pass parity or have reviewed intentional differences.
- Platform workload login and allowed/denied MCP behavior remain green under Platform-owned grants.
- Legacy source removal/demotion does not break provisioning or recovery.
- Agent Delivery has no ability to create or broaden a ByteDesk principal, role, grant, credential, or provider connection.
- ByteDesk-approved skill files may be delivered intact, but Agent Delivery validation, rendering, staging, and activation never execute them; later Hermes execution requires Platform-owned approval, sandboxing, identity, and call-time authorization.
- Failure or non-completion of this reference integration does not prevent a core Agent Delivery release satisfying AD-18's core certification.
- Platform projections never become a second target desired-state writer;
  timeout/404/unavailable MCP does not count as denial evidence.

## Verification

Run full-catalog render/compile/deploy, exact renderer and consumer authority/
private-key verification, deterministic shadow comparison, single-writer/no-
dual-store cutover, target-scoped host denial, distinct Platform capability
verifier positive and exact-policy-denial MCP tests, false-denial cases,
restart/recovery/current-tooling rebuild, legacy-mutation denial, Platform SLO/
load/DR/runbook evidence, and forward recovery.

## Not in scope

Production release, unrelated ByteDesk Platform refactoring, changes to Platform authorization semantics, or core Agent Delivery release certification.

## Dependencies

Blocked by CORE-CERT only. REFERENCE-CONSUMER-CERT additionally requires
REFERENCE-CATALOG-CERT when this integration selects the ByteDesk catalog.

## Architecture review amendments

- Remove the compatibility write path for ByteDesk `AgentInstructions`, `HermesAgentId`, `LastSoulHash`, `LastDeployedAt`, and `DeployStatus` after backfill/read migration. Update every affected DTO, service, router, and lifecycle consumer so no second definition source remains.
- Shadow work is limited to deterministic artifact/output comparison; there is never shadow execution or dual activation writers.
- Preserve existing engine/profile slots and Platform workload principals while rebinding them to per-profile deployment subdigests plus the engine release.
- Recovery is a new signed forward rollout built from eligible historical
  functional content with current trusted renderer/compiler, Platform grants,
  lifecycle, approval, slot, credential binding, workload identity, and canary
  evidence. It never uses mutable legacy files or reactivated history.
- The ByteDesk adapter projects Agent Delivery receipts into the existing Platform `AgentDeploymentRevision` and observation model; it must not create a duplicate Platform receipt aggregate.
