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
- An exact `bytedesk.external-input-lock/1` artifact for the Platform
  `ops/hermes-native` inventory and ADR-0180/ADR-0182 behavior. The lock binds
  repository URL, immutable commit, source-tree digest, sorted path/digest
  inventory, and `compatibilityEvidenceOnly: true`; an unpinned checkout or
  mutable branch is not an input or authority.
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

## Normative contracts and conformance

- **Ports and operations.** The reference integration uses
  `bytedesk.port.consumer-authority-approval/1`
  (`resolve-authority-snapshot`, `resolve-skill-approval`,
  `verify-private-authority`), `bytedesk.port.consumer-projection/1`
  (`resolve-consumer-subject`, `project-consumer-receipt`),
  `bytedesk.port.private-compiler/1` (`compile-private-deployment`,
  `resolve-compile-attempt`), `bytedesk.port.renderer-strategy/1`
  (`select-renderer`, `render`), `bytedesk.port.desired-state-store/1`
  (`read-target-state`, `watch-target-state`,
  `compare-and-swap-target-state`, `resolve-idempotency`),
  `bytedesk.port.host-reconciler/1` (`stage-candidate`,
  `preflight-candidate`, `activate-candidate`, `readback-active-state`,
  `append-host-observation`, `recover-attempt-journal`, `cleanup-candidate`), and
  `bytedesk.port.capability-verifier/1` (`dispatch-capability-check`,
  `verify-capability-result`) as registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Exact schema IDs include
  `https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-authority/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/skill-approval/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-release/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/target-delivery-state/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/host-reconciliation-attempt/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0`,
  and `https://schemas.bytedesk.ai/agent-delivery/v1/deployment-receipt/1.0.0`,
  under `contracts/schemas/v1/`. The Hermes renderer, Platform consumer Adapter,
  desired-store, capability, cutover, and `bytedesk.external-input-lock/1`
  profiles are in `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-16 owns ByteDesk Hermes 34+1 parity, locked-input
  migration, single-writer cutover, projection, full private rerender, distinct
  canary actors, runtime, drift, and current-tooling recovery evidence. Run
  `make verify-downstream-ports`; the task-specific suite is
  `downstream.bytedesk-hermes.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Boundary.** Platform remains authoritative for organization identity, roles,
  grants, MCP/tool/provider access, credentials, workload identity, approval,
  and mandatory security policy. The Promotion Coordinator alone writes desired
  state and triggers capability verification. ByteDesk-specific fields, models,
  and policies stay in the reference integration and never leak into core.

## Architecture review amendments

- Remove the compatibility write path for ByteDesk `AgentInstructions`, `HermesAgentId`, `LastSoulHash`, `LastDeployedAt`, and `DeployStatus` after backfill/read migration. Update every affected DTO, service, router, and lifecycle consumer so no second definition source remains.
- Shadow work is limited to deterministic artifact/output comparison; there is never shadow execution or dual activation writers.
- Preserve the engine/profile slots and Platform workload principals identified
  by the accepted external-input lock while rebinding them to per-profile
  canonical deployment descriptors plus the engine release.
- Recovery is a new signed forward rollout built from eligible historical
  functional content with current trusted renderer/compiler, Platform grants,
  lifecycle, approval, slot, credential binding, workload identity, and canary
  evidence. It never uses mutable legacy files or reactivated history.
- The ByteDesk adapter projects Agent Delivery receipts into the locked Platform
  `AgentDeploymentRevision` and observation model; it must not create a
  duplicate Platform receipt aggregate.
