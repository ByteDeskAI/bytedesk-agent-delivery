# Consumer integration contract

## Purpose

The consumer protocol lets a platform use Agent Delivery without surrendering
identity, authorization, credential, workload-identity, security-policy, or
business-approval authority. The core exchanges exact identifiers, canonical
functional intent, content descriptors, signed opaque authority evidence,
desired revisions, commands, and observations—not secret values or broad
consumer domain objects.

The normative details are split across:

- [Machine contracts v1](../standards/machine-contracts-v1.md);
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md);
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md); and
- [Operational readiness v1](../standards/operational-readiness-v1.md).

The Agent Delivery core reference implementation is fixed by
[ADR-0002](adr/0002-implementation-stack-and-reference-topology.md). Its Go,
PostgreSQL, Harbor/Distribution, Kubernetes, and gVisor choices do not cross this
port. A consumer Adapter, consumer-owned Capability Verifier, or
consumer-native `DesiredStateStore` may use the consumer's technology as long
as it implements the versioned contract, single-writer/CAS behavior, identity
separation, and complete conformance suite.

## Authority and actors

The consumer owns agent identity, lifecycle, target intent, roles, grants,
credential values, workload identity, mandatory controls, skill/business
approval, and call-time authorization. Agent Delivery owns deterministic
content compilation, verification, rollout coordination, and append-only
delivery evidence.

Three runtime actors are purpose-separated:

- the Agent Delivery Promotion Coordinator is the only logical desired-state
  writer and the only actor that can record promotion;
- the target-scoped Host Reconciler stages, checks, switches when authorized,
  and appends technical observations but has no capability or desired-write
  authority; and
- the consumer-owned Capability Verifier tests the candidate through the
  normal consumer identity/runtime/authorization path and returns signed
  evidence but cannot promote.

## Consumer Adapter inputs

A consumer Adapter supplies:

- stable consumer, subject/agent, installation, and runtime-target identifiers;
- an explicit create-new or bind-existing consumer identity decision;
- exact source, public-render, and renderer-release descriptors;
- a canonical private functional-customization binding and exact revision-plus-
  digest precondition;
- exact public/private skill descriptors and consumer-issued approval evidence
  for every effective skill digest;
- a signed, short-lived consumer-authority snapshot with current policy, grant-
  set, credential-set, workload-identity, lifecycle, mandatory-control,
  approval-policy, and target-binding subdigests; compile snapshots also sign
  the complete AD-13 authorized-private-input digest, which is forbidden on
  activate and recover snapshots;
- a consumer activation/business-approval reference when required;
- one configured DesiredStateStore Adapter for the target;
- a consumer Capability Verifier endpoint or authenticated event contract; and
- desired-state watch and observation/evidence intake endpoints where storage
  is consumer-native.

The Adapter never sends reusable credentials, tokens, private keys, secret
values, or an agent workload credential to Agent Delivery or the host.

## Machine and encoding boundary

All Agent Delivery-owned authoritative objects use closed JSON Schema Draft
2020-12 schemas from a signed, exact-digest contract bundle. Unknown schema IDs,
digests, fields, operations, discriminators, and closed-enum values fail.
Generated SDKs and integration models are projections, not contract authority.

Authoritative values use the JSON data model and RFC 8785 canonical JSON for
digest, signature, comparison, and idempotency identity. An Adapter may accept
restricted JSON-compatible YAML 1.2 as human input but rejects duplicate keys,
aliases, custom tags, non-string keys, non-finite numbers, and non-JSON values
before core submission. Retained authoring bytes are provenance/storage
integrity only. Arbitrary payload files, including `.yaml` and binaries, remain
byte-exact according to declared contract role.

## Import and binding

Import has private preview and apply operations. Both require exact source and
renderer-release descriptors, the canonical binding, effective skill set,
current contract bundle, and consumer scope. Apply additionally requires an
idempotency key, canonical request digest, revision-and-digest precondition, and
explicit consumer identity action.

Initial creation uses `{ "kind": "absent" }`. Every update uses
`{ "kind": "match", "revision": N, "digest": "sha256:..." }`. Omitted,
null, wildcard, digest-only, source-digest, or stale values fail without side
effects. HTTP strong ETags and conditional headers mirror but do not weaken the
domain CAS rule.

Public catalog and render endpoints reject consumer bindings, private skills,
authority snapshots, and customizations. Private preview/apply requires
authenticated consumer scope or a local non-publishing workflow. Import never
infers or creates grants, credential values, workload identity, roles,
reporting relationships, or provider connections.

## Functional customization and authority inputs

The private delta may change every functional Agent Spec or renderer-owned
harness property; configure models, provider endpoints, tools, MCP servers,
resources, and opaque secret references; add/replace/remove regular files; and
add/replace/remove exact public/private skills.

Agent Spec and harness values use ordered strict add/replace/remove JSON Pointer
operations. Files and skills use separate operation schemas with portable paths,
exact descriptors, and expected current digests for replace/remove. A failed
operation aborts the complete delta. A source update applies the ordered
operations to cloned old and proposed working trees. It conflicts on a changed
target or containing top-level subtree, including changed parents and arrays,
but excludes the document root so unrelated top-level upstream changes survive.
Canonical parser limits are rechecked after each operation and on the final
result.

Functional model/provider selection is already covered by the binding and
effective-render digest. Provider access, MCP/tool/resource grants, credential
state, workload identity, trust, business approval, and mandatory sandbox/
network/security controls remain separate current consumer inputs. A configured
capability never authorizes itself.

## Consumer authority and skill approval

Compilation, activation, and recovery each verify an operation-bound, short-
lived `bytedesk.consumer-authority/1` snapshot. It binds consumer, subject,
installation, candidate, desired revision, target, operation, nonce,
predecessor, expiry, and current opaque authority subdigests. Activation never
assumes the compilation snapshot is still current.

Each effective skill digest requires current `bytedesk.skill-approval/1`
evidence issued by the consuming organization. Supplier/publication signatures
and scans are inputs to that decision, not substitutes. Agent Delivery verifies
and records approval but cannot issue it. Changed, expired, revoked, or wrong-
scope evidence returns the skill to quarantine.

## Compilation output

The compiler:

1. verifies contract bundle, purpose-signed source/public render, exact product
   and renderer releases, pinned qualification decision, fresh authenticated
   current status heads, binding, skills, approvals, consumer authority, and
   trust, and requires the
   permitted compile authority's signed complete-input digest to match its own
   independently recomputed value;
2. verifies the exact source digest and RFC 8785 bytes before exactly one
   official Agent Spec `26.1.2` validation; requires the declared kind to match
   root `component_type`, explicit top-level `agentspec_version: 26.1.2`, and no
   legacy version substitute; and permits a public `SpecializedAgent` only with
   one complete embedded `Agent`, one complete parameters object, and no
   remote, package-relative, component-reference, or nested specialization
   resolution;
3. applies the private delta atomically to the complete public document and
   isolated filesystem view;
4. revalidates Agent Spec, renderer configuration, portability, content safety,
   and current consumer policy;
5. fully rerenders with the exact allowlisted renderer release in its trusted
   sandbox;
6. freezes the exact sorted private-input authentication bundle, signs the
   complete input lock under `consumer-compilation-input-v1`, and embeds that
   full signing result in the deployment;
7. embeds the effective render manifest, exact payload descriptor, and complete
   issued-attempt/authenticated-execution lineage in a consumer-private deployment;
8. commits the canonical deployment descriptor as the sole deployment identity;
9. signs a separate compilation statement under the consumer-isolated
   compilation-evidence role, with no backlink from the deployment; and
10. emits the exact lock, deployment, and compilation-evidence descriptors plus
    append-only evidence, then prepares a separately signed runtime-release
    subject entry containing the exact deployment/evidence pair.

The compiler never patches public render output, writes runtime desired state,
executes package/skill content, resolves secret values, or approves itself.
V1 defines no separate private-render artifact. Public bytes may be reused only
for empty customization and byte-identical normalized source/skill/renderer/
parameter inputs.

## One desired-state authority

Each consumer/runtime target has one `TargetDeliveryState` aggregate and one
logical writer: the Promotion Coordinator. One DesiredStateStore Adapter is
configured—Agent Delivery-managed or consumer-native—not both. A second copy is
a non-authoritative read model. Store migration is quiesced and checkpointed;
live dual write is forbidden.

Git contains reviewed installation/binding intent, not runtime desired state.
The compiler produces a prepared candidate, the consumer supplies authority and
approval, and the host supplies observations. The Coordinator alone validates
all gates and advances the target revision by CAS. A rollout lease prevents
duplicate work but cannot authorize a stale write.

Desired state includes exact active and optional pending release descriptors,
predecessor, slot/generation, target, and trust/authority/canary/recovery-policy
digests. At most one rollout is pending per target.

## Canary and promotion

The Coordinator creates a nonce-bound `bytedesk.canary-plan/1`. The harness
Adapter declares a certified isolated-candidate or guarded-in-place mode.

The Host Reconciler returns technical evidence for artifact/file/slot/process
identity, resources, readiness, and switch phase. It never runs an agent
capability. The consumer Capability Verifier exercises one policy-selected
non-destructive allowed capability and one forbidden sentinel through the
candidate's normal runtime path. The candidate receives a short-lived workload
identity directly from the consumer.

A negative probe passes only on the expected authorization-policy denial.
Timeout, transport error, missing endpoint, parser failure, or `404` is not
denial evidence. Omission is failure; signed `not_applicable` is accepted only
for a certified no-capability profile.

The Coordinator promotes only when both fresh evidence sets match the current
candidate, desired revision, authority digests, nonce, target, slot, and policy.
An observation cannot promote itself.

## Observation contract

Observations are append-only and include:

- target and desired revision/digest;
- deployment/release and renderer-execution descriptors;
- verifier contract/trust-policy/authority snapshot digests;
- staged and active file/slot/generation facts;
- actor, attempt, transition, and timestamps;
- technical/capability canary evidence descriptors;
- failure category and redacted diagnostic reference; and
- active predecessor, known-good history, failed rollout, and forward-recovery
  lineage.

Host attempt state, rollout state, and active-slot state remain distinct. Late
or duplicate observations are retained and deduplicated but cannot advance a
superseded revision.

## Forward recovery

Forward recovery uses the current target revision as CAS predecessor and
records historical content separately as `recoverySource`. It selects the
newest prior promoted functional-content set that remains available,
unwithdrawn, uncompromised, approved, valid, target-compatible, and buildable by
current trusted tooling.

It never reactivates an old deployment, desired record, receipt, signature,
authority snapshot, or revoked renderer. If historical tooling is revoked, a
current renderer must establish a new public lineage and pass full evaluation,
approval where semantics differ, and canary. No skill or functional dependency
is silently removed or substituted. If no candidate is eligible, recovery fails
closed and consumer incident policy chooses isolate, stop, or temporary
continuation of already active verified content. Recovery does not depend on
Git availability; Git back-sync is a later projection.

## API and event profile

HTTP uses signed OpenAPI 3.2.0 that references the normative schemas, RFC 9457
problem details, strong ETags, idempotency keys plus request digests, cursor
pagination, and durable `202` action resources. Events use CloudEvents 1.0.2
structured JSON described by AsyncAPI 3.1.0.

Events are sanitized at-least-once notifications with aggregate revision,
predecessor, sequence, schema digest, correlation, and causation. They never
carry authority. Receivers deduplicate and fetch exact API state on a gap.

## Authentication profile requirements

Every implementation profile defines workload authentication/audience,
sender-constrained or mTLS identity, consumer/target authorization, Adapter and
evidence signer policies, replay/idempotency, correlation/audit, credential and
key rotation, quotas, rate limits, redaction, and outage behavior.

Human login, candidate workload identity, Capability Verifier, Host Reconciler,
Promotion Coordinator, compiler, and deployment signer are distinct purposes.

## Failure semantics

Missing or stale authority, wrong consumer/target/audience, unapproved skill,
schema or renderer mismatch, customization conflict, unknown trust, invalid
precondition, illegal lifecycle transition, capability-evidence mismatch,
cross-consumer descriptor, and unavailable verification dependency fail new
work closed. An already active verified release may continue only under
consumer incident policy.

No failure path falls back to a tag, legacy writer, stale receipt, shared key,
old renderer, unsigned content, or direct consumer database read.

## Required verification

Consumer Adapter conformance proves:

- closed schemas, canonical encoding, exact renderer and contract identity;
- create/bind, absent/match CAS, idempotency, ABA, conflict, and replay;
- complete functional patch/file/skill freedom with security-authority denial;
- fresh authority and exact consumer skill approval, including rotation,
  expiry, revocation, and wrong-scope denial;
- one DesiredStateStore, one logical writer, no host/compiler/Git promotion,
  and quiesced store migration;
- isolated and guarded activation, true allowed/denied canary evidence, false-
  denial rejection, and reconciler least privilege;
- current-tooling forward recovery and no-eligible-candidate behavior;
- API/event duplication, reorder, gap, redaction, and authoritative resync; and
- operational SLO, limit, quota, outage, backup/restore, and audit evidence.
