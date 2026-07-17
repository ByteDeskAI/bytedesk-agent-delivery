# Runtime reconciliation

## Objective

Converge one runtime target on the exact desired release without giving the
host desired-state, promotion, human, or agent-capability authority and without
executing artifact-provided installation logic.

The normative actor, state, canary, and recovery rules are in
[Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md).

The reference Host Reconciler is the Go binary and production deployment
profile defined by
[ADR-0002](adr/0002-implementation-stack-and-reference-topology.md). The
reference control plane uses PostgreSQL transactions, durable actions,
outbox/inbox, leases, fencing tokens, and exact CAS; a consumer-native
`DesiredStateStore` may use different technology only through its Adapter and
must remain the one authority for that target. The host never acquires a
capability-verifier identity or executes package-provided hooks.

## Identity and permissions

Each Host Reconciler identity is certificate/sender-bound to one consumer and
one runtime target. It may:

- read that target's one authoritative `TargetDeliveryState` revision;
- pull exact descriptors from the matching private registry scope;
- use the host Adapter's local staging and guarded activation operations; and
- append observations and technical canary evidence for that target.

It cannot create or change installations, bindings, desired state, approvals,
grants, credentials, identities, trust policy, rollout policy, or promotion. It
cannot use a human role, candidate workload credential, agent principal, MCP/
tool/provider capability, broad platform API, or cross-target registry pull.

Rollout leases prevent duplicate host work but do not grant authority and never
override revision-and-digest CAS.

## Desired-state read

The host reads from exactly one configured DesiredStateStore. It never merges
Git, consumer database, Agent Delivery database, event, or local file opinions.
Events or watches are wake-up hints; the host fetches the exact current revision
and verifies its canonical digest before acting.

Desired state contains the target/slot/generation, exact active and optional
pending release descriptors, predecessor, rollout ID, activation mode, and
required contract/trust/authority/canary policy digests. An unknown field,
schema, revision, digest, predecessor, target, or policy is terminal for the
candidate.

## Reconciliation loop

1. Read and authenticate the current target revision.
2. Compare it with separately persisted active-slot facts, staged candidates,
   and reconciliation attempts.
3. Pull every artifact and contract bundle by exact repository and digest.
4. Verify closed schemas, RFC 8785 bytes, explicit graph edges, signatures,
   attestations, exact renderer release/execution lineage, approved skills,
   effective-render inventory, consumer/target/slot binding, current trust,
   withdrawal/revocation, and desired predecessor.
5. Extract untrusted content without execution into a new generation staging
   area with path/type/count/size/decompression controls. Preserve arbitrary
   `.yaml` and binary payload bytes exactly.
6. Verify complete inventory, ownership, safe modes, disk/memory budget, ports,
   service definition, slot isolation, tombstones, and unrelated profiles.
7. Run renderer/harness-declared static and parser preflight without invoking
   package hooks or skill code.
8. Append `staged` and `preflight_passed` technical observations.
9. Follow the Adapter's certified isolated-candidate or guarded-in-place path
   only after the Coordinator publishes the matching activation challenge or
   authorization.
10. Switch atomically at a harness-safe boundary, persist an fsync/durable
    switch marker, and read back the exact active generation.
11. Return technical canary evidence; wait for the consumer Capability
    Verifier and Promotion Coordinator rather than invoking capabilities.
12. Append final observed facts and retain predecessor content according to
    recovery/retention policy.

No renderer, agent, skill, script, binary, package manager, build, install,
migration, or artifact hook executes during pull, verify, extraction, staging,
preflight, or the host's activation mechanics. After the consumer authorizes
activation, the harness may run the candidate and exact-digest-approved skills
under current consumer sandbox, network, workload identity, and call-time
authorization. The host still does not hold or use that authority.

## Activation modes

### Isolated candidate

The host starts the candidate in an isolated non-serving slot after technical
preflight. The candidate obtains its short-lived identity directly from the
consumer. Capability evidence completes before the Coordinator authorizes the
production switch. A failed canary removes the candidate and leaves the
predecessor active.

### Guarded in-place

For harnesses that cannot exercise an isolated candidate, the Coordinator
authorizes a guarded switch after preflight. The host marks the new generation
`provisional_active`; this is not promotion. The consumer runs capability
checks immediately. Failure enters `recovery_required` and triggers a separate
forward recovery rollout.

An Adapter must certify one mode and its safe boundary, traffic behavior,
workspace/slot isolation, credential issuance path, timeout, and crash markers.
It cannot choose a mode from agent content.

## Technical canary evidence

The host responds to a nonce-bound `bytedesk.canary-plan/1` with signed or
authenticated technical evidence binding rollout, desired revision, release,
deployment, consumer, target, slot/generation, authority/policy digests,
reconciler identity/version, timestamps, and expiry.

Checks cover exact artifact and file readback, service/process identity,
readiness, resource thresholds, port/socket ownership, filesystem/slot
invariants, unrelated profiles, and switch phase. The host does not report
workload login or capability allow/deny; those belong to the consumer-owned
Capability Verifier.

## Persisted facts

The host persists separate records for:

- current active slot and generation;
- staged candidate generations;
- physical switch marker and predecessor;
- each reconciliation attempt and retry budget;
- technical observations/evidence; and
- cleanup/tombstone status.

It does not persist a self-authored desired state, `promoted`, or `rolled_back`
fact. The Promotion Coordinator owns rollout/promotion state. A candidate may
remain staged while the predecessor is active, and a failed attempt does not
erase the last successful active fact.

## Crash recovery

Recovery reads the durable switch marker, actual service/process generation,
slot contents, and current desired revision:

- before switch, discard or resume the exact staged candidate and leave the
  predecessor active;
- during an indeterminate switch, stop serving until exact generation readback
  proves one state—never guess from filenames or timestamps;
- after switch but before promotion, report `provisional_active` and resume the
  matching canary/recovery path; and
- after a superseding desired revision, retain late evidence but do not act on
  or promote the old candidate.

Observation-delivery failure is retried from the append-only local outbox. It
does not cause a repeated physical switch.

## Failure and forward recovery

A pull, trust, schema, contract, inventory, limit, slot, resource, or preflight
failure before switch records `failed_pre_activation` and leaves active content
untouched. Cancellation is valid only before `activation_authorized`.

A post-switch process or canary failure records `recovery_required`. The host
cannot select last-known-good or directly restore it. The Promotion Coordinator
must requalify historical functional content under current trust, renderer,
authority, approval, target, and canary policy, compile and sign a new forward
revision, and publish it through the same CAS path.

If no recovery candidate is eligible, the host follows the explicit consumer
incident state: isolate, stop, or temporarily hold already active verified
content for a non-compromise availability incident. It never pulls a tag, runs
a revoked renderer, reinstalls an old deployment/receipt, drops a skill, or
falls back to a legacy writer.

## Stable slots

Harness mappings to UID/GID, port, service, workspace, or credential scope use
a durable consumer-agent-to-slot/generation record independent of catalog
order. Retired slots are tombstoned. Reuse requires a separately authorized,
audited reset proving files, processes, sockets, caches, credentials, staged
generations, and pending observations are gone.

Slots are operational boundaries. A consumer must separately define process,
container, VM, network, and credential isolation appropriate to its threat
model.

## Operational behavior

The host meets the desired-read and detection SLOs, resource limits, offline
continuity, telemetry, audit, backup, and upgrade rules in
[Operational readiness v1](../standards/operational-readiness-v1.md). It uses
backpressure and per-target isolation under load. Exhaustion cannot evict active
or known-good rooted content or corrupt another target.

## Required verification

The matrix includes:

- wrong consumer/target/audience, expired identity, cross-registry pull, and
  desired-write/capability privilege denial;
- one-store read, event-gap authoritative refetch, lease/CAS separation, and
  stale/superseded revision handling;
- partial pull, corrupt layer, contract/schema/trust mismatch, disk/memory
  exhaustion, archive bomb, unsafe mode/owner/path, port collision, and
  tombstoned slot;
- execution-spy proof across extraction, preflight, switch, cleanup, and crash
  recovery;
- isolated and guarded activation, exact switch/readback, crash before/during/
  after switch, worker restart, and observation retry without double switch;
- nonce/freshness/current-policy technical evidence and host refusal to run
  allowed/denied capability probes;
- canary failure, recovery-required, current-tooling forward recovery, no
  eligible candidate, registry/KMS/Git/consumer outage, and incident hold/stop;
- credential and trust rotation while active; and
- SLO, scale, soak, noisy-neighbor, limit, telemetry/redaction, backup/restore,
  and N-1 upgrade evidence.
