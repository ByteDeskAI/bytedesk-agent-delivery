# Delivery lifecycle v1

**Profiles:** `bytedesk.target-delivery-state/1`,
`bytedesk.canary-plan/1`, `bytedesk.canary-evidence/1`,
`bytedesk.authorization-decision-proof/1`, and `bytedesk.recovery-plan/1`

**Status:** Accepted contract; its lifecycle schemas and contract fixtures are
frozen by AD-01. Promotion Coordinator, desired-state store, Host Reconciler,
consumer Adapter, runtime, recovery, and measured operational evidence remain
AD-09/AD-12/AD-14 and later-task GA gates.

## Purpose

This contract separates installation lifecycle, candidate preparation,
target desired state, host reconciliation, canary verification, promotion, and
forward recovery. It prevents one ambiguous enum or actor from acquiring
authority it should not have.

> **Non-normative implementation note:**
> [ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
> realizes the reference lifecycle with PostgreSQL transactions, durable
> actions, transactional outbox/inbox, revision/digest CAS, database-clock
> leases, and fencing. A consumer-native store may use other technology but
> cannot introduce a second writer or weaken these observable semantics.

## Actors and authority

### Promotion Coordinator

The Agent Delivery Promotion Coordinator owns the rollout process and is the
only logical writer allowed to advance a `TargetDeliveryState` aggregate. It
validates consumer commands and authority evidence, publishes exact desired
revisions by compare-and-swap, issues canary challenges, verifies evidence, and
records promotion or recovery outcomes.

It does not create identity, grants, credentials, workload identity, security
policy, or business approval. Those arrive as current signed consumer inputs.

### Host Reconciler

The target-scoped Host Reconciler reads desired state, pulls and verifies exact
artifacts, stages content without execution, performs local technical checks,
switches at a harness-safe boundary when authorized, and appends observations.
It never writes desired state, promotes itself, obtains a human role, receives
an agent capability credential, or invokes MCP/tool/provider capabilities.

### Consumer Capability Verifier

The consumer owns a distinct capability-verifier Adapter and signer. It runs
non-destructive authorization probes through the normal consumer runtime and
authorization path. The isolated or provisional candidate obtains its normal
short-lived candidate-bound workload identity directly from the consumer; the
Host Reconciler and Promotion Coordinator never handle that credential.

The verifier cannot promote. It returns signed evidence bound to one challenge
and candidate.

## One target desired-state authority

There is exactly one `TargetDeliveryState` aggregate for each exact consumer
and runtime target. It contains:

- monotonic revision and canonical digest;
- exact predecessor revision/digest;
- current active release descriptor, or explicit absence;
- at most one pending rollout descriptor;
- activation constraints and required trust, authority, canary, and recovery
  policy digests;
- stable target/slot/generation binding; and
- append-only transition and command correlation references.

The Promotion Coordinator is the sole logical writer. Git, update bots,
operators, consumer applications, compilers, hosts, observations, and recovery
planners submit intent, commands, prepared candidates, or evidence; none writes
the aggregate directly.

One `DesiredStateStore` Adapter is selected per target:

- Agent Delivery-managed durable storage; or
- a consumer-native store that implements the same schema, atomic CAS,
  append-only history, read, watch, backup, and audit contract.

There is never a simultaneous Agent Delivery authority row and consumer
authority row. Any additional copy is explicitly a disposable read model. A
store change requires a quiesced, audited migration with exact revision/digest
checkpoint, validation, and single-writer cutover. Live dual write is forbidden.

Git stores reviewed installation and binding intent. It is not runtime desired
state. A compiler creates a prepared signed release but cannot publish it as
desired. A rollout lease prevents duplicate work but never overrides CAS or
authorizes a stale write.

## Concurrency and lineage

All creates and mutations use the discriminated revision-and-digest
precondition from [Machine contracts v1](machine-contracts-v1.md). CAS controls
the command. Immutable `predecessor` records lineage. Recovery additionally
records `recoverySource`; historical content is never disguised as the current
predecessor.

An idempotent replay of the same key and canonical input returns the original
result. A stale or different input fails without side effects. No force,
wildcard, lease, administrator, or break-glass path bypasses exact CAS.

## Installation lifecycle

An installation is Agent Delivery's binding relationship, not the consumer's
organizational identity. Its legal states are:

```text
provisioning -> active | rejected
active <-> suspended
active | suspended -> retirement_pending
retirement_pending -> active | suspended | retiring
retiring -> retired
```

- `rejected` and `retired` are terminal.
- `suspended` blocks new compilation and activation. Whether already active
  runtime content continues is an explicit consumer incident decision.
- retirement may be cancelled only before `retiring`.
- a retired installation cannot be resurrected; reinstalling creates a new
  installation ID and an absent precondition.
- state changes never create, suspend, or retire the consumer-owned agent
  identity unless the consumer separately performs that action.

## Candidate preparation lifecycle

One immutable candidate proceeds through:

```text
received -> fetching -> fetched -> validating -> validated
validated -> quarantined -> evaluating
evaluating -> awaiting_approval | approved | rejected
awaiting_approval -> approved | rejected
approved -> compiling -> compiled -> signing -> prepared
```

`rejected`, `cancelled`, `superseded`, `failed`, and `prepared` are terminal for
that candidate process. An unchanged candidate may be retried through a new
action that references it; history is not rewritten.

Policy may allow an immediate zero-dwell `validated -> quarantined ->
evaluating` progression, but it may not skip the recorded quarantine,
validation, or evaluation transitions. `awaiting_approval` is required whenever
consumer policy requires a human or business decision. A changed skill digest
always enters quarantine and cannot be auto-approved. A candidate cannot move
backward.

Retryable dependency errors retain the current phase, increment a bounded
attempt counter, apply exponential backoff with jitter, and record the redacted
failure. Exhaustion becomes `failed`. Cancellation is allowed only before
signing begins. Once a side-effecting publication exists, reversal is a new
compensating action and never deletion of evidence.

`superseded` is allowed from any non-terminal phase from `received` through
`compiled`, but never from `signing` or `prepared`. Its sole trigger is an
atomic Promotion Coordinator decision that records a newer candidate for the
same installation and target and confirms that the older candidate has no
publication or rollout side effect. Merely discovering a newer catalog version
does not supersede a candidate. If signing has begun, the candidate completes
or fails normally and any replacement proceeds as a new candidate and, where
needed, a compensating forward action.

## Runtime rollout lifecycle

Every prepared candidate creates a distinct rollout under the target aggregate:

```text
pending -> staging -> staged -> preflight_passed
```

The harness Adapter declares exactly one certified activation mode.

### Isolated-candidate mode

```text
preflight_passed -> canary_running -> canary_passed
canary_passed -> activation_authorized -> activating
activating -> verifying_active -> promoted
```

The candidate can be exercised without replacing the predecessor. Promotion
authorization and the physical switch occur only after canary evidence passes.

### Guarded in-place mode

```text
preflight_passed -> activation_authorized -> activating
activating -> provisional_active -> canary_running
canary_running -> canary_passed -> promoted
```

The predecessor remains the recovery source while a provisional candidate is
checked. The physical switch is not promotion; promotion occurs only after all
evidence passes and the Coordinator advances the aggregate by CAS.

Before `activation_authorized`, an operator may cancel and a newer desired
revision may mark the rollout `superseded`. A pre-switch failure becomes
`failed_pre_activation` and leaves the predecessor active. A failure after the
physical switch becomes `recovery_required`. It never becomes `rolled_back`.
Only a separately compiled forward recovery rollout can become `promoted` and
link the failed rollout through `recoveredBy`.

If recovery cannot be produced, the target enters `operator_required` and the
consumer incident policy chooses isolation, stop, or temporary continuation of
an already active verified predecessor. No state transition silently selects
content.

Host reconciliation-attempt state and active-slot facts are stored separately
from rollout state. A candidate may be staged while a predecessor remains
active, and a retry may be running while the last observation remains valid.

## Canary plan and evidence

The Coordinator issues a signed/digested `bytedesk.canary-plan/1` challenge.
Its validity window is at most 30 minutes; consumer policy may require a
shorter window. The plan binds rollout, nonce, candidate, desired revision,
release, deployment, consumer, subject, target, slot/generation, activation
mode, current authority, policy, grant-set and workload-identity digests, and
the exact Host Reconciler, Capability Verifier, and authorization-decision
signer policies.

The plan has one closed expected-check map for each evidence actor. The Host
Reconciler map contains exactly `artifact_readback`, `file_inventory`,
`slot_generation`, `service_process`, `resource_thresholds`,
`harness_readiness`, and `switch_marker`, all expected to pass. The capability
map is exactly one of:

- `required`, with `workload_login`, `permitted_capability`, and
  `denied_sentinel`, the exact permitted and sentinel capability IDs and
  digests, and the exact expected sentinel policy-denial code; or
- `certified_not_applicable`, with one `certified_not_applicable` result and
  an exact certification digest and signer policy.

The Host Reconciler returns technical evidence for:

- exact artifact, file inventory, slot, generation, service, and process
  identity readback;
- filesystem, ownership, mode, port, disk, memory, and resource thresholds;
- harness parser/startup/readiness and unrelated-profile invariants; and
- switch phase and crash-recovery marker.

The Consumer Capability Verifier returns separate evidence for:

- workload login through the normal candidate runtime path;
- one policy-selected non-destructive permitted capability; and
- one known forbidden sentinel capability.

Each evidence object has an actor-discriminated, closed result object. Host
evidence contains exactly the seven technical results above. Required
capability evidence contains exactly the three capability results above. A
certified no-capability profile contains exactly one non-applicability result.
Actual results may be `failed` so incidents remain observable, but a failed
actual result never promotes.

The capability decision results reference exact
`bytedesk.authorization-decision-proof/1` digests. That consumer-owned proof
binds the plan digest and nonce; consumer, subject, and target; release and
deployment; capability ID and digest; current policy, grant-set, and
workload-identity digests; exact decision class and code; signer identity and
policy; freshness; and a redacted trace. Its transport is an authenticated,
completed, parsed, response-digested successful authorization response: HTTPS
2xx, gRPC OK, or consumer-native success. A network error, timeout, missing
endpoint, HTTP `404`, parser failure, or unavailable dependency cannot be
encoded as `policy_denied` proof.

Both evidence objects bind rollout, plan digest, nonce, candidate, desired
revision, release and deployment digests, consumer, subject, target,
slot/generation, actor identity and implementation version,
authority/policy/grant/workload-identity digests, signer policy, timestamps,
expiry, and redacted trace digests. They are signed or returned over an
equivalently authenticated, non-repudiable consumer channel.

Promotion verification receives the current plan, consumer authority, policy,
grant set, workload identity, time, signer expectations, authenticated
evidence/proof sets, and exact schema digests from independent trusted inputs.
Each authenticated-set entry is a verification record keyed by the exact
subject digest and binds the actually verified signer identity, exact signer
policy, verification-evidence digest, and either a verified signature or a
verified authenticated non-repudiable channel result. A bare digest membership
or a signer claim copied from the document is insufficient; the authenticated
record, independent expectation, plan policy, and document claim must all
match.
An authenticated non-applicability certification is paired with its independently
verified certification policy; an artifact cannot select that policy. The
verifier resolves each proof by digest, validates it offline against the
independently pinned schema, recomputes its canonical digest, and checks every
binding and nested freshness window.
Missing, unresolvable, unauthenticated, stale, wrong-target, wrong-signer, or
substituted proofs fail closed. A transport failure remains distinguishable
from an authorization denial.

Promotion requires fresh matching technical and capability evidence. A
consumer may return `not_applicable` only when the exact certification digest
is independently authenticated under the plan's certification policy.
Omission is failure. Reference integrations and every capability-bearing
production profile require positive and negative proof. Canary plans, evidence,
decision proofs, and certifications are consumer evidence; none grants a
capability or becomes package authority.

## Forward recovery selection

Last-known-good is historical evidence, not automatic activation eligibility.
The recovery planner searches prior successfully promoted functional-content
sets newest first. A candidate is eligible only when:

- consumer, installation, subject, harness, and target lineage match;
- exact source, customization, file, and skill descriptors remain available;
- no content digest is withdrawn, compromised, or content-revoked;
- every skill has current approval;
- Agent Spec, customization, schemas, and current target/system compatibility
  validate;
- current trusted renderer/compiler tooling can rebuild the content;
- current identity, lifecycle, policy, grant, credential reference, sandbox,
  network, trust, target, slot, and approval inputs pass; and
- full current evaluation and canary requirements can run.

Recovery reuses historical functional content only. It never reactivates the
old deployment, render bundle, desired record, receipt, signature, authority
snapshot, credential state, or tooling merely because it was once valid.

If the historical renderer or builder is revoked, it is never executed. The
source must pass the current trusted publication pipeline and a current
compatible renderer must create a new public-render lineage. A changed renderer
requires full compatibility, evaluation, and manual approval when output or
semantics differ. If no current renderer preserves required semantics,
automatic recovery is unavailable.

A revoked old signature alone does not make bytes current authority. Rebuild or
republish is allowed only from independently trusted source provenance under
current policy. A content digest explicitly withdrawn or compromised is
ineligible. The planner never silently drops or substitutes a skill, file,
tool, model, provider configuration, or other functional dependency.

The recovery revision records the exact current predecessor, failed rollout,
historical `recoverySource`, reused functional descriptors, current-tooling
substitution, eligibility-report digest, current consumer authority snapshot,
and all new output/evidence digests.

If no candidate is eligible, recovery fails closed. For a non-compromise
availability incident, policy may temporarily continue the already active
verified release; it cannot newly activate a prohibited digest. Recovery does
not depend on Git availability. The Coordinator creates the authoritative
append-only revision first and may later project it back to Git through a
reviewed reconciliation change.

## Observations and promotion

Observations are append-only evidence and can never mutate desired state. The
Coordinator evaluates them against the current target revision and challenge.
Late evidence for a superseded revision is retained but cannot promote it.

A successful promotion atomically replaces `activeRelease`, clears the pending
rollout, advances revision/digest, records the predecessor and evidence graph,
and designates the prior active content as historical known-good evidence.
Physical host state that disagrees with the aggregate is a reconciliation
incident, not permission for either side to guess.

## Failure behavior

Wrong actor, store, consumer, target, revision, digest, predecessor, nonce,
challenge, signer, freshness, mode, transition, or evidence fails closed.
Unknown or illegal transitions are never coerced. A lease cannot override CAS,
an observation cannot self-promote, and a failed rollout cannot label itself
recovered.

## Required verification

Release evidence includes:

- exhaustive legal/illegal transition and terminal-state model tests;
- absent/match CAS, ABA, idempotency, concurrency, lease-expiry, replay, and
  supersession tests;
- managed and consumer-native DesiredStateStore conformance and audited store
  migration without dual writing;
- Git intent versus runtime desired-state separation;
- isolated-candidate and guarded-in-place activation, pre/post-switch crash,
  cancellation, and recovery tests;
- host denial of human, agent, MCP, tool, provider, and desired-write authority;
- nonce, freshness, wrong-candidate, wrong-target, stale-policy, evidence-
  signer, positive-capability, explicit-denial, and false-denial tests;
- signed `not_applicable` only for certified no-capability profiles;
- newest-first recovery eligibility, withdrawn content, revoked tooling,
  current-tooling rebuild, semantic mismatch, no-candidate, and Git-outage
  recovery tests; and
- append-only observation, late evidence, active/read-model drift, and exact
  receipt reproduction tests.
