# AD-14: Reconcile verified deployment artifacts into hosted runtimes

- Historical Jira: [BDP-3315](https://bytedesk.atlassian.net/browse/BDP-3315)
- Delivery role: Core product host protocol and reconciler
- Release gate: Required for managed hosted deployment; harness adapters may be released independently

## Outcome

Safely reconcile one exact target to a prepared private release through a
least-privilege host, certified activation mode, separate technical and
consumer-capability evidence, Coordinator-controlled promotion, and newly
compiled forward recovery.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Prepared canonical runtime-release deployment graph and append-only receipts
  from AD-13, with exact runtime-release descriptor, `releaseDigest`, and
  `deployableGraphDigest`.
- Target-scoped host/reconciler protocol and a compile-time allowlisted harness runtime adapter.
- Fresh `activate`/`recover` consumer-authority snapshots, signed canary-plan
  challenges, Promotion Coordinator commands, and the distinct consumer
  capability-verifier Adapter/signing policy.
- An exact `bytedesk.external-input-lock/1` artifact for the Hermes deployment,
  provisioning, and verification operations used as reference-adapter evidence.
  The lock binds repository URL, immutable commit, source-tree digest, sorted
  path/digest inventory, and `compatibilityEvidenceOnly: true`; an unpinned
  checkout or mutable branch is not an input or authority.

## Required work

1. Pull by exact digest with least-privilege private-registry credentials and verify the deployment's embedded effective render plus explicit public render/source, customization, and skill lineage before extraction.
2. Verify a fresh operation-specific consumer-authority snapshot bound to the
   exact candidate/desired revision and current opaque subdigests. Never reuse
   compilation authority.
3. Apply every canonical per-subject deployment into one isolated target
   generation and validate archive safety, ownership, modes, configuration,
   disk budget, target constraints, and complete graph coverage. Bind all stage
   and preflight results to the same runtime-release descriptor,
   `releaseDigest`, and `deployableGraphDigest`. Skill payloads may contain
   arbitrary declared regular files, including executable files, but the
   reconciler never runs them, package hooks, installers, or dependency scripts
   during staging or activation.
4. Implement the harness Adapter's one certified activation mode:
   isolated-candidate or guarded in-place. Persist host attempt and physical
   slot/switch facts separately from target rollout state.
5. Return technical evidence bound to the canary challenge for exact artifact,
   files, process/readiness, slot/generation, resources, and switch/crash marker.
   The host never handles an agent capability credential or invokes MCP/tool/
   provider capabilities.
6. Implement the capability-verifier dispatch/evidence port used by the
   Promotion Coordinator. After matching Host technical evidence arrives, the
   Coordinator—not the Host Reconciler—dispatches a challenge through the
   consumer-owned capability-verifier Adapter. The provisional candidate
   obtains its normal short-lived identity directly from the consumer. Require
   signed workload-login, permitted-capability, and exact policy-denial
   evidence; timeout, 404, network, parser, or unavailable-tool errors do not
   prove denial.
7. Append observations only. The Promotion Coordinator verifies both evidence
   sets and alone CAS-promotes TargetDeliveryState; physical activation is not
   promotion.
8. Before activation, validate the Coordinator's historical permitted
   eligibility-verification result, then perform and persist a distinct fresh
   Host use-time verification at `operationTime`. Bind one atomic target-wide
   switch journal and marker to `releaseDigest`, `deployableGraphDigest`,
   `activationAuthorizationDigest`, and
   `hostEligibilityVerificationEvidenceDigest`; never use one subject's
   `deploymentDigest` as journal identity.
9. On post-switch failure, enter `recovery_required` and request a separately
   compiled current-tooling recovery rollout. Never reactivate an old release,
   render, receipt, signature, authority snapshot, or revoked renderer.
10. Support idempotent retries, cancellation, timeout, dead-letter/replay, and recovery after reconciler, process, or host restart.
11. Leave any later execution of skill-provided content to the consuming runtime, and only after explicit consumer approval under consumer-owned sandboxing, workload identity, and call-time authorization. Activation of files is not execution approval.

## Outputs

- Digest-pinned host reconciliation protocol and reference reconciler.
- Harness runtime Adapter interface plus a Hermes implementation/profile.
- Per-subject isolated staging/preflight plus one atomic target-wide activation
  mechanism and one graph-bound switch journal.
- Current-tooling forward-recovery request/compiler/reconciler path.
- Technical canary evidence plus consumer capability-verifier Adapter/evidence
  contracts and Coordinator dispatch contract; neither evidence actor can
  promote, and the Host cannot dispatch capability work.
- Isolated-candidate and guarded-in-place conformance fixtures, with each
  harness selecting exactly one mode.
- Non-production E2E and fault-injection tests.
- Complete canonical per-subject active-readback and deployment-receipt sets,
  with one entry for every runtime-release graph subject.

## Acceptance criteria

- No artifact applies before trust and exact installation/subject/target binding pass.
- A successful receipt identifies the exact running digest, target slot/generation, consumer-verdict references, and observed health.
- Canary failure leaves active content unchanged before switch; post-switch
  failure produces `recovery_required` and only a new eligible recovery
  rollout can become promoted.
- Consumer authorization remains fail-closed: the positive capability verdict must succeed and the negative verdict must remain denied, without giving the reconciler broad runtime-agent or human-administrator authority.
- Duplicate and restarted operations converge without duplicate activation.
- Exactly one atomic switch and journal cover the complete runtime-release
  graph; every stage, preflight, canary, promotion-decision, active-readback, and
  deployment-receipt set covers its canonical subjects exactly once.
- The Host validates the Coordinator's historical eligibility-verification
  result and emits a distinct fresh permitted use-time result before committing
  switch intent; both exact evidence digests are durable and auditable.
- The core reconciler does not assume ByteDesk identity, Office roles, MCP grants, or Hermes-specific state outside the Hermes adapter.
- Staging and activation do not execute skill payloads; a consumer-runtime execution verdict is separately attributable to consumer policy and identity.
- The host cannot write desired state, receive human/agent/MCP authority, run
  capability probes, or label a rollout promoted/recovered.
- Missing, stale, wrong-nonce/candidate/target/actor evidence fails. A signed
  `not_applicable` is accepted only for a certified profile with no external
  capability plane.

## Verification

Run isolated-candidate and guarded-in-place conformance; host read/observe-only
and human/agent/MCP/provider denial; fresh authority; technical and distinct
capability actor nonce/freshness/wrong-candidate/false-denial/not-applicable;
pre/post-switch crash, cancellation/supersession/late evidence, partial pull,
disk/memory limits, unsafe boundary, registry/KMS/consumer outage, credential
rotation, observation retry, no-candidate recovery, current-tooling forward
rebuild, restart convergence, runtime-release/graph/authorization/use-time
verification journal substitution, incomplete or reordered per-subject
readback/receipt sets, and SLO/soak/chaos tests.

## Not in scope

Production rollout, consumer identity/grant administration, source-directory deletion, or a specific consumer's canonical-source cutover.

## Dependencies

Blocked by AD-09, AD-10, and AD-13.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.host-reconciler/1`
  (`stage-candidate`, `preflight-candidate`, `activate-candidate`,
  `readback-active-state`, `append-host-observation`,
  `recover-attempt-journal`, `cleanup-candidate`),
  `bytedesk.port.desired-state-store/1` (`read-target-state`,
  `watch-target-state`), `bytedesk.port.capability-verifier/1`
  (`dispatch-capability-check`, `verify-capability-result`),
  `bytedesk.port.control-plane-api-events/1` (`append-host-observation`,
  `append-capability-evidence`), and `bytedesk.port.oci-registry/1`
  (`pull-artifact`, `verify-artifact-graph`) are registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Exact schema IDs include
  `https://schemas.bytedesk.ai/agent-delivery/v1/host-reconciliation-attempt/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-slot/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/observation/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/canary-plan/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/activation-authorization/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-eligibility-evidence/1.0.0`,
  and
  `https://schemas.bytedesk.ai/agent-delivery/v1/host-switch-journal-entry/1.0.0`,
  under `contracts/schemas/v1/`. Activation-mode, phased host-evidence,
  journal/fsync/switch, readback, capability-transport, and external-input-lock
  profiles are in `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-14 owns isolated-candidate and guarded-in-place host
  protocols, crash-at-every-boundary journal recovery, target-scoped identity,
  technical evidence, complete signed activation-authorization and offline
  runtime-release graph verification, single target-wide graph switch,
  per-subject canonical evidence/readback/receipt coverage, distinct
  Coordinator historical and Host use-time eligibility verification,
  activation-time status freshness, false-denial, observation retry, and
  forward-recovery runtime fixtures. Run
  `make verify-downstream-ports`; task suites are
  `downstream.host-reconciler.v1` and `downstream.capability-verifier.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suites' exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Executable protocol acceptance.** `contracts/ports/v1/protocol-fixtures.json`
  contains the exact capability challenge to dispatch request to dispatch
  receipt to capability evidence to accepted canary-evidence chain. Its
  single-fault mutations cover identity, target, candidate, check-profile,
  nonce, authorization-decision, issuance, expiry, request/receipt/evidence,
  authentication-record, exact denial, and certified-not-applicable bindings.
  `CAP-001` transport and `CAP-003` host-dispatch prohibition are requirements
  compiled into exact `conformance-plan.json` harness directives rather than
  protocol-document mutations. `scripts/contracts/test_protocol_fixtures.py`
  verifies every protocol document and digest/time/identity binding; no stale
  verification-result compatibility path is accepted. The Go canary
  verifier separately freezes the internal-to-public problem mapping under
  `internal/canary`.
- **Boundary.** The Promotion Coordinator alone invokes
  `dispatch-capability-check`; the Host Reconciler implements no capability
  trigger and never holds a capability credential. The host reads desired state,
  pulls, stages, switches, reads back, and appends technical evidence only; it
  cannot promote, write desired state, or turn transport failure into policy
  denial.

## Architecture review amendments

- Introduce an exact installation- and target-bound host identity with read-desired, scoped registry-pull, and append-observation authority for one target. It cannot use human administration or a runtime agent/MCP principal.
- Provision scoped private-registry pull credentials per installation and target and rotate/revoke them independently.
- Persist host attempt/slot facts separately from exact target rollout states.
  A failed rollout cannot relabel itself as recovered; only a new forward
  recovery rollout can be promoted and link through `recoveredBy`.
- Preserve stable slots, UID/GID, ports, services, and workspaces during migration. Retired slots are tombstoned and never reused without durable purge plus a host-reset ceremony; system packages use explicitly reserved slots.
- Treat runtime slots as operations/capacity boundaries, not universal security isolation. Consumer policy decides when separate hosts or engines are required.
- Reject unsafe archives; stage by digest; switch only at a harness-safe boundary. Partial pull, disk full, crash, registry outage, credential rotation, unsafe boundary, and observation-delivery retry are mandatory tests.
