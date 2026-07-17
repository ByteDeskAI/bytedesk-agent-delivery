# Data model, API, and service ownership

## Architectural posture

Agent Delivery is independently deployable and consumer-neutral. Version one
should favor a modular monolith with explicit domain modules, one public API,
one worker surface, and one relational persistence boundary unless measured
scale or isolation needs justify a split. Logical ownership is defined now so a
future process split does not change contracts.

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

### Binding revision

An append-only normalized instance of [Agent binding v1](../standards/agent-binding-v1.md).
It records predecessor, source descriptor, renderer selection, non-authorizing
specialization, and actor/correlation evidence. A stable installation points to
its current accepted binding revision.

### Render receipt

Records source, binding, skills, renderer, parameters, compatibility outcome,
output manifest, and published render descriptor. A deterministic cache can
reuse an exact receipt only when every normalized input digest matches.

### Deployment revision

Records the private compiled artifact and all current consumer-provided
subdigests: organizational profile, policy, grants, provider configuration,
credentials version references, runtime target, and stable slot. Secret values
are never stored in the record or artifact.

### Runtime release

Aggregates the exact desired deployment revisions for one runtime. It has a
monotonic revision, predecessor, rollout policy, system package descriptor, and
signed release manifest digest.

### Promotion process

Owns the durable state machine from candidate receipt through validation,
evaluation, rendering, signing, staging, canary, promotion, rejection, or
forward rollback. It stores retry, deadline, approval, and compensation state.

### Deployment observation

An append-only host report of desired, fetched, verified, staged, active,
healthy, failed, or rolled-back facts. Observations never overwrite desired
state and cannot promote a release.

### Stable slot allocation

Binds a consumer-owned profile identifier to one runtime-local slot and
allocation generation. A retired slot is tombstoned to prevent identity and
filesystem reuse.

## Ownership matrix

| Module | Owns | Does not own |
|---|---|---|
| Catalog | Sources, releases, channels, withdrawal | Consumer installations or identity |
| Validation | Schemas, policy results, package safety | Human approval policy |
| Rendering | Renderer registry and render receipts | Runtime credentials or grants |
| Installations | Bindings and update intent | Organizational profile lifecycle |
| Supply chain | OCI publication, signatures, attestations | Consumer token issuance |
| Promotion | Candidate process, evaluation evidence, rollout decision | Business task execution |
| Deployment | Compiled deployment and runtime release desired state | Runtime process internals |
| Reconciliation | Host protocol and observations | Consumer MCP authorization |
| Integration | Consumer/SCM/registry/KMS Adapters | Portable definition semantics |

Modules access one another through application contracts. They do not write
another module's tables.

## Consumer contract

A consumer supplies stable opaque identifiers and signed or mutually
authenticated projections for:

- consumer and tenant scope;
- organizational profile and lifecycle;
- target runtime and stable slot assignment;
- current policy and approval result;
- current MCP/tool/resource grant digest;
- model/provider configuration digest;
- credential-version references, never secret material; and
- workload-binding constraints used at activation/login time.

Agent Delivery stores these as evidence and compilation inputs. The consumer
remains the semantic authority and can invalidate them. Integration details are
specified in the [consumer integration contract](../architecture/consumer-integration-contract.md).

## Public API families

The versioned API provides:

- catalog search, release, inspect, and withdrawal status;
- definition validate and policy-check;
- renderer capabilities, preview, and render;
- artifact inspect and graph verification;
- installation preview, create, bind, update, and retire;
- candidate and promotion status, approval input, and cancellation;
- deployment compile, desired release, rollout, and forward rollback;
- runtime desired-state fetch and observation append; and
- receipt and evidence query.

Public catalog, validation, rendering, inspection, and verification can operate
without a ByteDesk Platform account. Private installation and deployment
operations require a consumer integration identity and scope.

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

Binding updates and desired releases use expected predecessors. One rollout
lease exists per installation/profile or runtime, depending on operation scope.
Human or concurrent consumer changes win over an automation proposal that no
longer matches its expected predecessor.

## State transitions

The promotion process uses explicit legal transitions:

```text
received -> fetched -> validated -> quarantined -> evaluating
evaluating -> approved | rejected
approved -> rendered -> signed -> staged -> canary
canary -> promoted | rolled_back
```

Failures capture whether retry is safe, the retry budget, terminal state,
dead-letter evidence, and any compensation. Reordered or duplicate messages
cannot move an aggregate backward.

## Events and integration

When modules or processes are separated, durable domain events are written with
the authoritative change through a transactional outbox. Consumers use an
idempotent inbox. Events include schema version, correlation, causation,
aggregate revision, and sanitized references; they do not contain SCM tokens,
secret values, or raw private payloads.

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
consumer scope, correlation and causation identifiers, expected predecessor,
input and output digests, policy result, and terminal outcome. Sensitive values
are redacted at ingestion rather than masked only in presentation.

## Related pages

- [Tenant Git and reconciliation](08-tenant-git-and-reconciliation.md)
- [Evaluation and promotion](09-evaluation-promotion-updates-and-rollback.md)
- [CLI and headless contract](11-cli-and-headless-consumer-contract.md)
