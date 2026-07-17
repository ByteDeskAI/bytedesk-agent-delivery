# Hosted runtime deployment

## Deployment model

Agent Delivery deploys through a small host reconciler that is independently
authenticated, scoped to one consumer runtime, and designed to converge desired
state safely. The reconciler is not an agent, human operator, policy engine, or
general remote-execution channel.

Hermes is the first hosted reference Adapter. The host protocol remains generic
enough for another runtime to implement the same verify, stage, activate, and
observe contract.

## Desired state

The control plane publishes one monotonic desired release for a runtime. It
contains:

- consumer, tenant, and runtime target identifiers;
- desired-state revision and expected predecessor;
- exact signed runtime release descriptor;
- exact per-profile deployment descriptors;
- stable slot bindings and allocation generations;
- activation constraints and rollout policy; and
- required trust policy identifiers.

The host never follows a Git branch, catalog channel, semantic version, or OCI
tag. It pulls only the exact descriptors in desired state.

## Host identity and permissions

The host uses a certificate-bound or equivalent short-lived identity scoped to
one runtime. Its minimal permissions are:

- read desired deployment for that runtime;
- obtain repository pull authorization for that runtime's private project; and
- append deployment observations for the same runtime.

It cannot change desired state, approve or promote a release, read another
consumer, impersonate a human, request an agent workload token, invoke MCP
tools, alter grants, or access general consumer credentials.

## Reconciliation sequence

For each new desired revision, the host:

1. Authenticates the desired-state response and rejects stale/replayed state.
2. Acquires a local runtime reconciliation lock.
3. Pulls manifests and layers by exact digest into a bounded cache.
4. Verifies the complete explicit OCI graph and independently distributed
   trust policy.
5. Re-checks consumer/runtime/profile/slot bindings and predecessor.
6. Unpacks into a fresh staging directory under safe archive rules.
7. Validates the declared file inventory, modes, ownership, and target layout.
8. Runs harness-specific offline validation.
9. Waits for an approved safe activation boundary.
10. Switches atomically or through a documented recoverable sequence.
11. Starts or reloads the target profile.
12. Performs canary and health checks.
13. Appends observations and retains active plus last-known-good content.

No package hook is executed at any stage.

## Stable runtime slots

Each runtime maintains a durable mapping:

`consumer profile ID -> slot ID -> runtime profile name, local identity, port, service, workspace, allocation generation`.

Slot allocation is independent of catalog order and selected roster subset. The
34 reference employee definitions can be imported in any order without moving
an existing profile into another profile's filesystem or process identity.

The `office-orchestrator` reference system package has a reserved system slot
where the harness requires one. It is not an employee identity.

A retired slot is tombstoned. It is not reused within the runtime lineage unless
an explicitly audited purge and host-reset ceremony proves that processes,
files, credentials, caches, sockets, observations, and local identities are
gone.

Slots are operational boundaries, not security sandboxes. A runtime that cannot
isolate mutually untrusted consumers must use separate hosts or equivalent hard
isolation.

## Filesystem layout and switching

Desired, staged, active, last-known-good, failed, and observation state are
persisted separately. Immutable content directories are named by deployment
digest; mutable runtime state is outside them. An active pointer or
harness-specific switch selects one fully verified directory.

The switching design must state its crash points. If a truly atomic filesystem
rename is unavailable, the host journal records each step so recovery can
distinguish pre-switch from post-switch state.

## Safe activation boundary

Agent content must not change in the middle of a non-idempotent run. The harness
Adapter defines how the host determines that a profile is idle, drains it, or
starts the new content in a guarded canary slot. A deadline and consumer policy
decide whether to wait, cancel the rollout, or request an approved interruption.

There is never more than one active writer for the same profile slot.

## Canary evidence

Canary evidence includes:

- process and harness parser health;
- exact runtime profile and stable slot identity;
- active content and release digest readback;
- consumer workload login bound to the current deployment;
- granted MCP discovery/invocation in a dedicated test scope;
- denial of an ungranted or wrong-tenant capability;
- resource and error thresholds over a defined window; and
- no unintended restart or file change for unrelated profiles.

MCP configuration and grants are supplied by the consumer. The host checks the
result but does not grant them.

## Crash and failure recovery

The reconciler handles:

- partial pull or corrupt cache by deleting only unverified staged content;
- disk full by preserving active/LKG and refusing the new stage;
- crash before switch by resuming or discarding staging;
- crash after switch by identifying active digest, restoring service, and
  reporting canary status;
- process start or canary failure by retaining evidence and requesting a
  forward rollback;
- desired-state race by stopping work that no longer matches the current
  revision; and
- registry/control-plane outage by continuing the already verified active
  release without accepting new state.

The host does not create a rollback revision itself. It reports failure; the
control plane creates and signs the new forward revision.

## Runtime observations

Each observation contains runtime and profile scope, desired revision, artifact
digests, phase, timestamps, host identity, health evidence, error code, and
local active/LKG facts. Observations are append-only, idempotent, and ordered by
host sequence. They do not contain secret values or unrestricted logs.

## Host upgrade

Host protocol and implementation versions are reported in observations and
checked by desired-state policy. Upgrades are separate from agent-content
deployment. A package cannot request a host binary or runtime image upgrade.

## Related pages

- [Runtime reconciliation](../architecture/runtime-reconciliation.md)
- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Evaluation and promotion](09-evaluation-promotion-updates-and-rollback.md)
