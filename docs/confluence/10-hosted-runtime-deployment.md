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

The Promotion Coordinator is the sole logical writer of one monotonic
`bytedesk.target-delivery-state/1` aggregate for an exact consumer/runtime
target. Exactly one `DesiredStateStore` Adapter is selected for that target,
either Agent Delivery-managed or consumer-native; a second authoritative row
or live dual write is forbidden. The aggregate contains:

- consumer, tenant, and runtime target identifiers;
- desired-state revision/digest and immutable predecessor;
- exact signed runtime release descriptor;
- exact per-profile deployment descriptors;
- stable slot bindings and allocation generations;
- activation constraints and rollout policy; and
- required immutable trust-policy identifiers and digests.

Every create/mutation uses the required `absent` or exact revision-and-digest
`match` precondition. The immutable accepted record separately carries its
predecessor. A rollout lease only prevents duplicate work and never overrides
CAS. Git, compiler, consumer application, host, observation, and event are not
runtime desired-state writers.

The host never follows a Git branch, catalog channel, semantic version, or OCI
tag. It pulls only the exact descriptors in desired state.

Desired-state and product manifest objects are JSON data-model values whose
authority bytes use RFC 8785 JCS. A host never reparses retained authoring YAML
as authority or activation input; an integrity reference to it is provenance or
storage-integrity evidence only, never semantic identity, artifact authority,
or activation authority. Arbitrary payload files, including files named `.yaml`
or `.json`, remain byte-exact and fail verification after any transcoding or
byte change.

Those objects use closed Draft 2020-12 schemas from the exact signed contract
bundle, resolved without network access. The desired revision binds immutable
schema/trust-policy digests, a fresh activation-scoped signed consumer-authority
snapshot, and signed approval evidence for every effective skill digest.

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
4. Verifies the complete explicit OCI graph, binding/customization, selected
   skills, embedded effective render bundle/manifest, and independently
   distributed trust policy, including the renderer-release manifest, actual
   executed product distribution, embedded allowlist, and schema digests.
5. Recomputes authoritative structured-object digests from RFC 8785 canonical
   JSON and arbitrary payload-file digests from exact raw bytes.
6. Re-checks consumer/runtime/profile/slot bindings, exact target revision and
   predecessor, a fresh activation-scoped signed authority snapshot, and every
   signed exact-skill approval.
7. Unpacks into a fresh staging directory under safe archive rules.
8. Validates the declared file inventory, modes, ownership, target layout,
   executable-skill approval, and sandbox-policy bindings.
9. Runs harness-specific offline validation and local technical preflight.
10. Follows the Adapter's certified isolated-candidate or guarded in-place
    state machine and waits for explicit Coordinator activation authorization
    before any production-slot switch.
11. Switches atomically or through the declared recoverable sequence and starts
    or reloads the target profile when authorized.
12. Returns challenge-bound technical observations. The consumer-owned
    Capability Verifier independently runs workload-login and allowed/denied
    probes; the host never invokes those capabilities.
13. Retains active and historical known-good content while the Promotion
    Coordinator alone decides promotion by target-state CAS.

No package, binding, or skill hook is executed at any stage. Skills may contain
scripts or binaries as regular files; staging and activation do not authorize
their execution. The runtime may execute them only when the private deployment
binds signed consumer approval for the exact skill digest, the required
sandbox, and current call-time authorization.

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

The active-slot fact, rollout state, and each host reconciliation attempt are
persisted separately. A candidate can be staged while its predecessor remains
active, and a retry can run without rewriting the last valid observation.
Immutable content directories are named by deployment digest and contain the
embedded effective render rather than a mutable patch of a public bundle;
mutable runtime state is outside them. An active pointer or harness-specific
switch selects one fully verified directory.

The switching design must state its crash points. If a truly atomic filesystem
rename is unavailable, the host journal records each step so recovery can
distinguish pre-switch from post-switch state.

## Safe activation boundary

Agent content must not change in the middle of a non-idempotent run. Each
harness Adapter certifies exactly one activation mode from Delivery lifecycle
v1: isolated-candidate or guarded in-place. It defines how the host determines
that a profile is idle, drains it, or starts a candidate without business
traffic. A deadline and consumer policy decide whether to wait, cancel before
activation authorization, or request an approved interruption.

There is never more than one active writer for the same profile slot.

## Canary evidence

The Promotion Coordinator issues a signed/digested canary challenge containing
the rollout, nonce, candidate/desired revision, consumer, subject, target,
slot/generation, activation mode, current authority/policy digests, expected
result classes, expiry, and evidence signer policies.

The Host Reconciler returns technical evidence only: exact artifact/file/slot/
service/process readback, parser/readiness state, filesystem/mode/resource
thresholds, switch marker, and unrelated-profile invariants.

A separate consumer-owned Capability Verifier runs through the normal candidate
runtime and authorization path and returns signed evidence for workload login,
one non-destructive permitted capability, and one known forbidden sentinel. The
candidate obtains its own short-lived candidate-bound workload identity; the
host never receives or invokes it. A negative result requires the exact expected
consumer policy-denial class. Timeout, network error, unavailable/missing tool,
parser failure, or `404` is not proof of denial.

Both evidence sets bind the same nonce, target revision, release/deployment
digests, actor/version, authority/policy/plan digests, time window, and redacted
trace. Omission fails; signed `not_applicable` is limited to a certified profile
with no external capability plane. Only the Coordinator can promote by CAS.

## Crash and failure recovery

The reconciler handles:

- partial pull or corrupt cache by deleting only unverified staged content;
- disk full by preserving active/LKG and refusing the new stage;
- crash before switch by resuming or discarding staging;
- crash after switch by identifying the provisional active digest, restoring
  safe service state, and reporting exact switch/canary status;
- process start or canary failure before switch as `failed_pre_activation`, or
  after switch as `recovery_required`;
- desired-state race by stopping work that no longer matches the current
  revision; and
- registry/control-plane outage by continuing the already verified active
  release without accepting new state.

The host does not create a recovery revision itself and never labels a rollout
`rolled_back`. It reports failure. The Promotion Coordinator searches prior
successfully promoted functional content newest first, rejects withdrawn/
content-revoked inputs and revoked tooling, revalidates current signed authority
and skill approvals, and creates a new public-render/deployment/target lineage
with current trusted renderer/compiler tooling. No historical artifact,
receipt, signature, authority snapshot, or Git state is reactivated. If no
candidate qualifies, recovery fails closed and incident policy chooses isolate,
stop, or an explicitly permitted temporary continuation.

## Runtime observations

Each host observation contains runtime and profile scope, desired revision,
artifact digests, host-attempt phase, timestamps, host identity, technical
health evidence, switch marker, error code, and local active/known-good facts.
Consumer capability evidence is a separate signed object. Observations are
append-only, idempotent, and ordered by host sequence. They cannot mutate
desired state or self-promote and do not contain secret values or unrestricted
logs.

## Host upgrade

Host protocol and implementation versions are reported in observations and
checked by desired-state policy. Upgrades are separate from agent-content
deployment. A definition, binding, or skill cannot request a host binary or
runtime image upgrade or install itself through a hook.

The host/reconciliation service is certified against the v1 desired-state
availability and observation-intake objective of 99.95%, connected detection
p95 of 30 seconds, five-minute p95 end-to-end reference rollout target, default
resource bounds, capacity profile, and recovery exercises in
[Operational readiness v1](../standards/operational-readiness-v1.md).

## Related pages

- [Runtime reconciliation](../architecture/runtime-reconciliation.md)
- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Evaluation, promotion, and forward recovery](09-evaluation-promotion-updates-and-forward-recovery.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
