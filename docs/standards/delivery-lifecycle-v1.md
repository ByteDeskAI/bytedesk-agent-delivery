# Delivery lifecycle v1

**Profiles:** `bytedesk.target-delivery-state/1`,
`bytedesk.canary-plan/1`, `bytedesk.canary-evidence/1`, and
`bytedesk.recovery-plan/1`

**Status:** Accepted architecture contract; concrete schemas and transition
fixtures are release-blocking AD-09/AD-12/AD-14 deliverables

## Purpose

This contract separates installation lifecycle, candidate preparation,
target desired state, host reconciliation, canary verification, promotion, and
forward recovery. It prevents one ambiguous enum or actor from acquiring
authority it should not have.

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

The Coordinator issues a signed/digested `bytedesk.canary-plan/1` challenge
containing rollout ID, nonce, candidate and desired-revision digests, consumer,
subject, target, slot/generation, activation mode, current authority/policy
digests, required checks, expected result classes, expiry, and evidence signer
policies.

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

The denied check passes only when the normal consumer authorization engine
returns the exact expected policy-denial class. A timeout, network failure,
missing endpoint, `404`, parser error, or unavailable tool is not proof of
denial. Evidence records the authorization decision reference but redacts
credentials and private response data.

Both evidence objects bind rollout, nonce, desired revision, release and
deployment digests, consumer, subject, target, slot/generation, actor identity
and implementation version, policy/grant/workload-identity/canary-plan digests,
expected and actual result classes, timestamps, expiry, and redacted trace
digests. They are signed or returned over an equivalently authenticated,
non-repudiable consumer channel.

Promotion requires fresh matching technical and capability evidence. A
consumer may return signed `not_applicable` only when its certified profile has
no external capability plane. Omission is failure. Reference integrations and
every capability-bearing production profile require positive and negative
proof.

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
