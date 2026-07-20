# Data model, API, and service ownership

## Architectural posture

Agent Delivery is independently deployable and consumer-neutral. Version one is
a Go modular monolith with explicit domain modules, one public API, one durable
worker binary deployed in purpose-separated modes, isolated Python Agent Spec
workers, and one PostgreSQL 18 persistence boundary. WayFlow runs only in its
CI compatibility lane. PostgreSQL also owns durable actions and the transactional
outbox/inbox; notification or work Adapters cannot become authority. Logical
ownership is defined now so a measured future process split does not change
contracts. The complete production profile is
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md).

Consumer integrations use Adapters. Product core contains no direct dependency
on a consumer's user, organization, MCP, credential, or business-work schema.

## Core aggregates

### Catalog release

Records a signed catalog digest, publisher policy, channel mapping, withdrawal
state, and the immutable source descriptors visible in that release. It is a
discovery snapshot, not a deployment.

### Installation

Represents one consumer's decision to track a portable definition. It records
consumer namespace, definition identifier, exact installed digest, selected
harness, update policy, and lifecycle. It does not create a consumer identity
or copy the definition as mutable database content.

Its legal lifecycle is:

```text
provisioning -> active | rejected
active <-> suspended
active | suspended -> retirement_pending
retirement_pending -> active | suspended | retiring
retiring -> retired
```

`rejected` and `retired` are terminal; a retired installation is never
resurrected.

### Binding revision

An append-only normalized instance of [Agent binding v1](../standards/agent-binding-v1.md).
It records predecessor, source descriptor, renderer selection, the deterministic
functional Agent Spec and regular-file customization delta, exact public/private
skill selection, and actor/correlation evidence. It may describe private
functional configuration and opaque secret references, but never grants,
identity assignments, raw secrets, or approval weakening. A stable installation
points to its current accepted binding revision.

The persisted authoritative representation is the JSON data model serialized
as RFC 8785 JCS bytes. Human-authored YAML may be retained for provenance, but
any integrity reference to it is provenance or storage-integrity evidence only,
never semantic identity, artifact authority, or activation authority.

Creation requires an `absent` precondition. Updates require both the exact
current revision and canonical digest; accepted records separately carry
immutable predecessor lineage. Digest-only, null, wildcard, or administrative
force preconditions are invalid.

### Render receipt

Records source, public skills, renderer, public parameters, compatibility
outcome, output manifest, and tenant-free published render descriptor. A
deterministic cache can reuse an exact receipt only when every normalized public
input digest matches. Private effective-render evidence belongs to the
deployment revision rather than a separate private-render artifact.

### Deployment revision

Records the private compiled artifact, tenant-free public-render lineage,
binding/customization digest, selected public/private skill descriptors,
embedded effective render manifest, exact payload descriptor, authenticated
renderer execution lineage, public-byte reuse decision, and
all current consumer-provided subdigests: organizational profile, policy,
grants, provider access, credential-version references, execution/sandbox
approval, runtime target, and stable slot. Raw secret values are never stored in
the record or artifact. V1 has no separate private-render artifact.

### Runtime release

Aggregates the exact canonical deployment descriptor and separate exact
private-compilation-evidence descriptor for every subject intended for one
runtime. It has a monotonic revision, predecessor, rollout policy, system
package descriptor, `consumer-runtime-release-v1` signing result, and signed
release manifest digest.

### Target delivery state

There is one `bytedesk.target-delivery-state/1` aggregate per exact consumer
and runtime target. It stores a monotonic revision/canonical digest, current
active release or explicit absence, at most one pending rollout, exact
predecessor, target/slot/generation, and required authority, trust, canary, and
recovery policy digests. The Promotion Coordinator is its sole logical writer.
Exactly one `DesiredStateStore` Adapter is selected per target; an additional
copy is only a disposable read model, and live dual write is forbidden.

### Promotion process

Owns candidate preparation and target rollout as separate durable state
machines. It stores retry, deadline, approval, compensation, signed canary-plan,
technical-evidence, capability-evidence, and forward-recovery state without
mixing them into the installation aggregate or host observation enum.

### Deployment observation

An append-only host report of desired, fetched, verified, staged, active,
healthy, failed, active-slot, or recovery-attempt facts. Observations never
overwrite desired state and cannot promote a release.

### Stable slot allocation

Binds a consumer-owned profile identifier to one runtime-local slot and
allocation generation. A retired slot is tombstoned to prevent identity and
filesystem reuse.

## Ownership matrix

| Module | Owns | Does not own |
|---|---|---|
| Catalog | Sources, releases, channels, withdrawal | Consumer installations or identity |
| Validation | Schemas, policy results, package safety | Human approval policy |
| Rendering | Renderer registry, tenant-free public render receipts, and full effective rendering inside private compilation | Runtime authority, raw credentials, or grants |
| Installations | Bindings and update intent | Organizational profile lifecycle |
| Supply chain | OCI publication, signatures, attestations | Consumer token issuance |
| Promotion | Candidate process, sole target-state CAS writer, canary verification, recovery decision | Consumer business approval or capability decision |
| Deployment | Compiled deployment and runtime release preparation | Runtime process internals or desired-state publication |
| Reconciliation | Host protocol and technical observations | Consumer MCP authorization or desired-state mutation |
| Integration | Consumer/SCM/registry/KMS Adapters | Portable definition semantics |

Modules access one another through application contracts. They do not write
another module's tables.

## Consumer contract

A consumer supplies stable opaque identifiers plus short-lived signed
`bytedesk.consumer-authority/1` snapshots and signed
`bytedesk.skill-approval/1` decisions for:

- consumer and tenant scope;
- organizational profile and lifecycle;
- target runtime and stable slot assignment;
- current policy and approval result;
- current MCP/tool/resource and provider-access grant-set digest;
- credential-set state, version references, and resolution authority for
  binding-supplied opaque references, never raw secret material;
- exact-skill execution approval and sandbox-policy digest; and
- workload-binding constraints used at activation/login time.

Agent Delivery stores these as evidence and compilation inputs. The consumer
remains the semantic authority and can invalidate them. Integration details are
specified in the [consumer integration contract](../architecture/consumer-integration-contract.md).
Concrete model/provider selection and endpoints are functional values already
covered by the binding and effective-render identity; the authority snapshot
does not duplicate them as a second selection digest.

Authority/approval and private-deployment signing use purpose-separated
consumer-owned non-exportable keys, or explicitly opted-in tenant-dedicated
managed keys. Cross-consumer shared private signing is forbidden.

## Public API families

The versioned API provides:

- catalog search, release, inspect, and withdrawal status;
- public definition validate and policy-check, rejecting customization;
- tenant-free public renderer capabilities, preview, and render, rejecting
  bindings, private skills, opaque references, and tenant metadata;
- artifact inspect and graph verification;
- installation preview, create, bind, update, and retire;
- candidate and promotion status, approval input, and cancellation;
- authenticated deployment compile with full effective rerender, desired
  release, rollout, and forward recovery;
- runtime desired-state fetch and observation append; and
- receipt and evidence query.

The normative HTTP contract is OpenAPI 3.2.0 using JSON Schema Draft 2020-12
as its dialect and referencing the same closed schemas shipped in the signed
offline contract bundle. It uses `/v1`, cursor pagination with a stable sort,
strong ETags and conditional mutations, RFC 9457 `application/problem+json`,
stable machine codes, and durable action resources for work that may exceed two
seconds. Schema `$id` and digest, rather than a mutable documentation URL, are
validation authority.

Public catalog, validation, rendering, inspection, and verification can operate
without a ByteDesk Platform account. Private installation and deployment
operations require a consumer integration identity and scope.

HTTP authority-bearing request and resource objects use JSON. A CLI or SCM
Adapter may accept human-authored YAML only through the restricted YAML 1.2
JSON-compatible parser, then submits the equivalent JSON data model. RFC 8785
JCS bytes define digests, signatures, normalized idempotency input, and semantic
equality; ordinary pretty-printed API JSON is only a presentation of that same
object. Arbitrary payload bodies remain exact bytes, including bodies for files
named `.yaml` or `.json`; only declared contract objects enter the structured
parser.

## Commands, queries, and long-running work

Queries are side-effect free. Commands use explicit idempotency keys and return
the durable resource or operation they created. Validation, evaluation, render,
publication, import, compilation, and deployment may exceed an interactive
request and therefore return an operation resource with stable states,
progress, cancellation, errors, and terminal evidence.

Client disconnect does not cancel work. Cancellation is an explicit command and
may be rejected after a safe activation boundary.

## Idempotency and concurrency

Idempotency scope includes consumer, operation type, target resource, and
caller-provided key. Replaying the same key and normalized input returns the
same result. Reusing it with different input is a conflict.

For structured inputs, normalized equality means equality of RFC 8785 JCS
bytes, not equality of an uploaded YAML document or pretty-printed JSON text.

Binding updates and target-state mutations use the required `absent` or exact
revision-and-digest `match` precondition. HTTP creation maps this to
`If-None-Match: *`; update, promotion, cancellation, and recovery use strong
`If-Match`, returning `412` without effects on mismatch. One rollout
lease exists per installation/profile or runtime, depending on operation scope.
Human or concurrent consumer changes win over an automation proposal that no
longer matches its exact revision-and-digest precondition.

## State transitions

Installation, candidate, target rollout, and host reconciliation are separate
aggregates under [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md).
Candidate preparation runs from `received` through fetch, validation,
quarantine, evaluation/approval, compilation, and signing to terminal
`prepared`, with separate rejected, cancelled, superseded, and failed outcomes.

A prepared rollout runs `pending -> staging -> staged -> preflight_passed`, then
uses the harness's certified isolated-candidate or guarded in-place activation
mode. Promotion requires matching Host technical evidence and Consumer
Capability Verifier evidence. A pre-switch failure is
`failed_pre_activation`; a post-switch failure is `recovery_required`, never a
direct `rolled_back` state. Only a separately compiled forward-recovery rollout
can be promoted and link the failed rollout through `recoveredBy`.

Failures capture whether retry is safe, bounded attempts/backoff, terminal
state, dead-letter evidence, and compensation. Cancellation is legal only
before activation authorization. Reordered, duplicate, late, or superseded
messages cannot move an aggregate backward or promote it.

## Events and integration

When modules or processes are separated, durable domain events are written with
the authoritative change through a transactional outbox. Consumers use an
idempotent inbox. Events use CloudEvents 1.0.2 over mandatory JSON and are
described by AsyncAPI 3.1.0 using the same exact signed event-data schemas.
They include event-data schema ID/digest, correlation, causation, aggregate
revision/digest, per-aggregate sequence, consumer scope, and sanitized
references; they do not contain SCM tokens, secret values, raw webhook bodies,
or raw private payloads.

Delivery is at least once and ordered only within one aggregate partition. A
sequence gap or unknown schema stops projection and triggers API resynchronization.
Events are notifications, never desired-state, promotion, identity, approval,
or authorization authority.

No integration reads another service's database. Webhooks are receipt signals,
not trusted state; the integration fetches the immutable source through the
authorized provider Adapter.

## Retention and deletion

Append-only revisions and receipts are retained according to consumer policy,
audit, and legal hold. Deleting a consumer first prevents new work, revokes host
and registry access, computes artifact roots, and then purges private records
when retention permits. Public definitions and catalog provenance are governed
separately.

## Audit fields

Every state-changing record includes actor or workload identity, timestamp,
consumer scope, correlation and causation identifiers, exact CAS precondition,
immutable predecessor lineage, input and output digests, policy result, and terminal outcome. Sensitive values
are redacted at ingestion rather than masked only in presentation.

Production sizing, API/action latency, desired-state availability, event lag,
capacity, durability, retention, audit completeness, and support windows are
release criteria from
[Operational readiness v1](../standards/operational-readiness-v1.md), not values
left to each implementation to invent after launch.

## Related pages

- [Tenant Git and reconciliation](08-tenant-git-and-reconciliation.md)
- [Evaluation, promotion, and forward recovery](09-evaluation-promotion-updates-and-forward-recovery.md)
- [CLI and headless contract](11-cli-and-headless-consumer-contract.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
- [ADR-0002: Implementation stack and reference topology](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
