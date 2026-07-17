# AD-12: Implement promotion coordination, compatible updates, and recovery planning

- Historical Jira: [BDP-3313](https://bytedesk.atlassian.net/browse/BDP-3313)
- Delivery role: Core product control plane
- Release gate: Blocks private compilation and `CONTROL-PLANE-CERT`

## Outcome

Implement the sole Promotion Coordinator for target desired state, then use it
to evaluate compatible updates, issue canary challenges, verify separate
evidence, promote prepared releases, and plan current-tooling forward recovery.
Git and bots are optional intent producers, not desired-state writers.

## Inputs

- Catalog release/channel and compatibility metadata.
- Trust/policy verification and definition-binding state.
- AD-09 installation/candidate/TargetDeliveryState/receipt schemas and AD-10
  commands, actions, events, ETags, and consumer Adapter ports.
- Delivery-lifecycle transition models, canary plans/evidence, forward-recovery
  rules, and per-installation update policy.
- Consumer-supplied authorization-impact and approval verdicts. Agent Delivery never evaluates or mutates the underlying consumer grants, roles, MCP access, or credentials.

## Required work

1. Detect stable successors and perform the normative three-way rebase of strict
   JSON Patch, file, and skill operations over exact prior/proposed sources.
   Changed targets/ancestors, removed parents, unstable arrays, descriptor
   mismatches, or changed skill digests conflict or quarantine.
2. Produce human-readable and machine-verifiable change/evaluation reports.
3. Accept operator/API/Git/update-bot intent as commands and enforce exact
   absent/match revision-plus-digest preconditions. A bot may propose a reviewed
   Git change, but only the Coordinator CAS-writes TargetDeliveryState.
4. Implement one logical Coordinator writer over either a managed or
   consumer-native DesiredStateStore. Leases deduplicate work but never override
   CAS; store migration is quiesced and never dual-written.
5. Classify breaking/major, lossy, trust-policy, consumer-authorization-impact, approval-posture, or customization-invalid changes as approval-required; do not auto-merge them.
6. Implement the exact installation, candidate-preparation, and target-rollout
   transitions. Compilers submit prepared candidates, hosts append technical
   observations, and consumer capability verifiers submit separate signed
   evidence; none can promote itself.
7. Issue exact canary-plan challenges, verify nonce/freshness/candidate/target/
   policy binding for both actors, and promote only after matching technical and
   capability evidence. Timeout, 404, network or parser failure is not denial
   evidence.
8. Implement newest-first recovery eligibility over historical functional
   content. Reject withdrawn content, revoked tooling, stale authority or
   approval, semantic mismatch, or missing dependencies; request a newly
   compiled rollout with current source trust, renderer/compiler, authority,
   policy, skill approval, and canary evidence. Recovery never requires Git.

## Outputs

- Compatibility and update-policy evaluator.
- Signed bot-commit adapter and compare-and-swap controls.
- Promotion Coordinator, DesiredStateStore ports, and exhaustive lifecycle
  transition implementation.
- Evaluation report and attestation contract.
- Approval-required classification, canary-plan/evidence verification, and
  forward-recovery eligibility/command contracts.
- Concurrency, replay, crash/restart, and policy tests.

## Acceptance criteria

- No proposal comes from a mutable tag or untrusted release.
- Only policy-compatible stable successors whose customization reapplies deterministically, whose skill digests are unchanged, and whose consumer policy verdict is valid auto-progress to ready-to-compile.
- Concurrent consumer edits prevent unsafe overwrite.
- Recovery intent identifies eligible historical functional content and the
  failed rollout, then requests a new current-tooling revision.
- Replays and restarts resume without duplicate commits or state transitions.
- This task does not claim runtime canary or physical recovery proof; AD-14 owns
  that proof.
- No evaluation result grants, revokes, or restores consumer authority.
- Only the Coordinator advances TargetDeliveryState; observations, Git, bots,
  compilers, hosts, capability verifiers, leases, and operators cannot bypass
  exact CAS.
- Promotion requires fresh matching evidence from both the target-scoped host
  and distinct consumer capability verifier, or signed `not_applicable` only
  for a certified no-capability profile.
- Recovery records current predecessor separately from historical
  `recoverySource` and fails closed when no eligible current-tooling rebuild
  exists.

## Verification

Run exhaustive legal/illegal transition, terminal state, absent/match/ABA,
idempotency, concurrency/lease/supersession, managed/consumer-native store and
no-dual-write migration, compatibility/rebase, bot/API/Git intent, skill
quarantine/approval, authority freshness, canary nonce/actor/false-denial/late-
evidence, promotion CAS, newest-first recovery, revoked tooling/withdrawn
content/current-tooling rebuild/no-candidate/Git-outage, and crash/restart tests.

## Not in scope

Private artifact compilation, runtime canary, physical activation/recovery, or
consuming-platform grant/identity administration.

## Dependencies

Blocked by AD-08, AD-09, and AD-10. AD-11 is an optional Git intent producer,
not a prerequisite. AD-13 and AD-14 consume this process contract.

## Architecture review amendments

- Automatic update is permitted only when the skill digest set is unchanged, no security-authority mutation or raw secret appears, schema and renderer compatibility pass, the functional customization reapplies cleanly, trust/evaluation passes, consumer authorization posture is unchanged or explicitly approved, and installation policy allows it.
- New or changed skills always enter quarantine, evaluation, and promotion; high-risk skills require human approval. No automatic skill promotion.
- Breaking, lossy, human-in-the-loop-weakening, tool/authority-bearing, signer/policy, or skill-changing proposals stop for approval or rejection.
- Recovery requests identify historical functional content separately from the
  current predecessor. AD-13 and AD-14 build a new artifact and rollout using
  current lifecycle, slot, policy/grant revision, credential binding, workload
  identity, trusted tooling, approval, and canary evidence.
