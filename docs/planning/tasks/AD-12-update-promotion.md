# AD-12: Automate compatible stable update proposals and promotion policy

- Historical Jira: [BDP-3313](https://bytedesk.atlassian.net/browse/BDP-3313)
- Delivery role: Core product control plane
- Release gate: Required for managed automatic updates

## Outcome

Detect compatible stable marketplace successors, evaluate them, and advance consumer desired state through signed compare-and-swap bot commits and a durable promotion process. This task stops at verified/reconciled desired state; AD-13 compiles and AD-14 stages, activates, and performs forward-only rollback.

## Inputs

- Catalog release/channel and compatibility metadata.
- Git desired-state and reconciliation from AD-11.
- Trust/policy verification and definition-binding state.
- AD-01 promotion states and per-installation update policy.
- Consumer-supplied authorization-impact and approval verdicts. Agent Delivery never evaluates or mutates the underlying consumer grants, roles, MCP access, or credentials.

## Required work

1. Detect stable successor releases for each exact consumer pin and compare Agent Spec version, package compatibility, renderer compatibility, overlay applicability, trust policy, skill digest set, and installation update policy.
2. Produce human-readable and machine-verifiable change/evaluation reports.
3. Create a narrowly scoped bot branch/commit changing only the expected digest/version and containing predecessor, evaluation digest, and correlation metadata.
4. Verify bot commit signature/identity and use compare-and-swap against the expected predecessor so human edits or concurrent updates win safely.
5. Classify breaking/major, lossy, trust-policy, consumer-authorization-impact, approval-posture, or overlay-invalid changes as approval-required; do not auto-merge them.
6. Persist proposed → evaluated → committed → reconciled → ready-to-compile transitions idempotently. Publish explicit commands/events consumed by AD-13 and AD-14.
7. Define compensation input/output so AD-14 can request a signed rollback commit that points to last-known-good definition content. Never rewrite history or reactivate an old deployment receipt.

## Outputs

- Compatibility and update-policy evaluator.
- Signed bot-commit adapter and compare-and-swap controls.
- Durable pre-deployment promotion state machine.
- Evaluation report and attestation contract.
- Approval-required classification and rollback-command contract.
- Concurrency, replay, crash/restart, and policy tests.

## Acceptance criteria

- No proposal comes from a mutable tag or untrusted release.
- Only policy-compatible stable successors with unchanged skill digests and a valid consumer policy verdict auto-progress to ready-to-compile.
- Concurrent consumer edits prevent unsafe overwrite.
- Rollback intent is a new signed commit/revision request referencing last-known-good definition content and the failed successor.
- Replays and restarts resume without duplicate commits or state transitions.
- This task does not claim runtime canary or rollback proof; AD-14 owns that proof.
- No evaluation result grants, revokes, or restores consumer authority.

## Verification

Run state-transition, idempotency, concurrency, bot-signature, compatibility matrix, consumer-verdict, human-edit race, rollback-command, skill-change quarantine, and crash/restart tests.

## Not in scope

Private artifact compilation, runtime canary, activation, runtime rollback, or consuming-platform grant/identity administration.

## Dependencies

Blocked by AD-10 and AD-11. AD-13 and AD-14 consume this process contract.

## Architecture review amendments

- Automatic update is permitted only when the skill digest set is unchanged, no authority-bearing field appears, schema and renderer compatibility pass, the overlay rebases cleanly, trust/evaluation passes, consumer authorization posture is unchanged or explicitly approved, and installation policy allows it.
- New or changed skills always enter quarantine, evaluation, and promotion; high-risk skills require human approval. No automatic skill promotion.
- Breaking, lossy, human-in-the-loop-weakening, tool/authority-bearing, signer/policy, or skill-changing proposals stop for approval or rejection.
- Rollback requests identify last-known-good definition content only. AD-13 and AD-14 build a new artifact and receipt using the consumer's current lifecycle, target slot, authorization-policy/grant revision, credential binding, and workload identity references so revoked authority cannot return.
