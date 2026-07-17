# Operational readiness v1

**Profile:** `bytedesk.operational-readiness/1`

**Status:** Accepted v1 launch targets; measured evidence is required before GA

## Purpose

This profile defines the minimum reliability, performance, scale, recovery,
security-response, observability, retention, compatibility, and support bar for
a consumer-ready Agent Delivery v1. These are release criteria, not claims that
the current documentation-only repository already meets them.

Self-hosted operators own the availability of their infrastructure, but the
product must publish and pass the same reference-topology conformance suite. A
managed service may offer stricter targets and must not silently weaken these
defaults.

The production reference profile is fixed by
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md).
Its declared Go/PostgreSQL/Harbor/S3/Kubernetes/gVisor/KMS/SPIFFE topology is
the first topology that must produce this evidence. Alternative implementations
may claim conformance only after passing the same externally observable
contract, failure, capacity, and recovery suite.

## Service-level indicators and objectives

SLOs are measured monthly at the service boundary, including dependency and
deployment failures controlled by the service. Planned maintenance is excluded
only when announced at least seven days ahead, limited to four hours per month,
and it does not disable already active workloads.

| Capability | V1 objective |
|---|---|
| Public catalog, schema, inspect, and verification reads | 99.95% successful availability |
| Authenticated control-plane reads and command acceptance | 99.9% successful availability |
| Target desired-state reads and observation intake | 99.95% successful availability |
| Durable event publication from committed outbox | 99.9% within 60 seconds |
| Synchronous cached/read-model API latency | p95 <= 300 ms, p99 <= 1 s |
| Durable command/action acceptance | p95 <= 1 s |
| Desired revision publication after all gates pass | p95 <= 5 s |
| Reconciler detection of a new desired revision while connected | p95 <= 30 s |

An Agent Delivery, registry, KMS, Git, or consumer-control-plane outage MUST NOT
terminate or mutate an already active, locally verified runtime release. It
blocks new import, compilation, signing, activation, or recovery according to
the relevant fail-closed rule.

## Reference workload performance

The release benchmark uses a declared standard workload: one Agent Spec
document, up to 2,000 regular files, 25 MiB uncompressed input, ten skills,
three renderer targets, warm metadata caches, and no human-approval delay.

| Operation | V1 objective |
|---|---|
| Parse, schema, Agent Spec, portability, and safety validation | p95 <= 5 s |
| Deterministic render for one harness | p95 <= 30 s |
| Private full compile, rerender, manifest, and local signing request | p95 <= 60 s |
| Exact graph verification with locally available blobs | p95 <= 10 s |
| End-to-end stage, technical preflight, canary, and promote | p95 <= 5 min |

Registry transfer, malware sandbox queue, external evaluation, consumer
approval, and consumer capability latency are measured and reported separately
instead of being hidden in product processing time. Every asynchronous action
reports phase timing, queue time, dependency time, retries, and terminal cause.

## Capacity conformance profile

A production release must demonstrate one deployment of the reference topology
supporting at least:

- 10,000 isolated consumers;
- 100,000 installations;
- 25,000 runtime targets;
- 1,000 concurrent build/evaluation/deployment actions;
- 500 concurrent rollouts without cross-target interference;
- 50,000 read requests and 5,000 accepted commands per minute; and
- 100 million append-only observations/receipts with bounded indexed query
  latency and tested archival.

The test includes noisy-neighbor, per-consumer quota, queue fairness, backpressure,
worker loss, rolling upgrade, and regional dependency failure. Capacity is
published per tested topology; horizontal-scale claims require measured
near-linear evidence and cannot rely on a single-process benchmark.

## Default safety and resource limits

All limits are enforced before allocation where possible and reported through
stable problem codes. A consumer may configure lower limits. Higher limits
require an explicit policy, capacity test, and risk acceptance; they are never
selected from artifact metadata.

| Resource | V1 default maximum |
|---|---|
| Authoritative structured object | 4 MiB canonical JSON |
| Functional customization operations | 10,000 total |
| Files in one source or skill package | 10,000 |
| Files in one private deployment | 50,000 |
| Path depth / normalized UTF-8 path length | 32 segments / 1,024 bytes |
| One regular file or OCI blob | 4 GiB |
| Total expanded private deployment | 10 GiB |
| Archive nesting | 3 levels |
| Decompression expansion ratio | 100:1 and within total byte limit |
| Renderer wall time | 10 minutes absolute |
| Renderer memory / temporary disk | 4 GiB / 20 GiB default worker budget |

Payloads larger than synchronous API limits use exact OCI/file descriptors and
streaming verification. Limits apply cumulatively after nested expansion.
Parsers, scanners, renderers, and extractors stop safely when a bound is
crossed; partial output is not signable.

## Durability, backup, and disaster recovery

Committed authoritative state uses synchronous replicated durability within
the home region, with no acknowledged single-node-only write. Targets are:

- regional committed-state RPO: zero acknowledged transactions;
- region-loss RPO: at most five minutes;
- control-plane and desired-state service RTO: at most sixty minutes;
- complete registry, evidence, and historical-query restoration RTO: at most
  four hours; and
- no dependency on control-plane recovery for continuity of an already active
  verified runtime release.

The production profile uses continuous database/WAL protection, daily immutable
snapshots, cross-region encrypted copies, and at least 35 days of recoverable
backup history. Registry manifests, blobs, referrers, signatures, attestations,
contract bundles, trust-policy snapshots, desired state, observations, and
receipts are restored as one graph and verified by digest before writes resume.

Automated backup integrity is checked daily. A scoped restore is exercised
monthly; a full isolated restore and regional failover are exercised at least
quarterly. Signing and promotion remain disabled after restore until trust,
revocation, single-writer state, outbox/inbox positions, and exact graph
consistency pass.

## Retention

- Active, pending, last-known-good evidence, recovery candidates, withdrawals,
  incidents, and legal holds remain rooted for as long as referenced.
- Deployment observations, receipts, approvals, and administrative audit
  records have a 400-day default online or queryable retention.
- Contract bundles, product/renderer release manifests, and trust-policy
  snapshots needed for historical verification remain available for at least
  seven years and never less than the consumer's evidence-retention period.
- Consumer deletion removes private payload access according to contract while
  preserving the minimum non-secret tombstone and legal/audit evidence required
  to prevent identity or digest reuse.

Retention expiry uses an audited mark-and-sweep preview. A digest cannot be
collected until graph traversal proves it is not active, pending, known-good,
recovery-eligible, held, incident-linked, or referenced by retained evidence.

## Observability and audit

The product emits OpenTelemetry-compatible metrics, traces, and structured logs
for API, action, queue, renderer, registry, KMS, consumer Adapter, desired-state,
host, canary, and recovery boundaries. Every request/action/rollout has stable
correlation and causation IDs across outbox, events, and receipts.

Metrics include availability, latency, saturation, queue age, retries, schema
and policy failures, signature/revocation failures, action transitions, rollout
phase duration, event lag/gaps, reconciliation drift, backup age, restore
results, and consumer quota use. Alerts use error-budget burn rates plus hard
security and durability signals.

One hundred percent of trust, key, policy, approval, schema, renderer,
installation, desired-state, promotion, recovery, withdrawal, retention, and
operator changes produce append-only administrative audit evidence. Logs and
telemetry redact secret values, tokens, raw private payloads, and unrestricted
consumer identifiers. Redaction is tested, not assumed.

## Security response targets

- Confirmed signing-key or builder compromise: publish revocation and block new
  affected activation within 15 minutes of an authorized decision.
- Actively exploitable critical product vulnerability: mitigation or patched
  release within 24 hours.
- High-severity vulnerability with a reachable product path: patched release
  within seven days.
- Medium-severity vulnerability: disposition and planned remediation within 30
  days.
- Critical dependency or malware intelligence affecting an artifact: evaluate
  impacted digests immediately, quarantine new use, and publish consumer-
  visible disposition without rewriting history.

Key rotation, revocation, restore, and incident-contact paths are tested at
least quarterly. A security deadline never authorizes an unsigned hotfix,
shared private key, mutable tag, or bypass of current consumer authority.

## Compatibility, deprecation, and support

- A GA major is supported for at least 24 months.
- After a successor major reaches GA, the previous major receives security and
  critical-correctness support for at least 12 additional months.
- A public field, command, event, media type, CLI command/exit code, or behavior
  is deprecated for at least 12 months and two GA minor releases before removal,
  unless keeping it would create an active security vulnerability.
- Breaking changes ship only in a new major contract/API/media type.
- The current and previous GA minor of a supported major interoperate for
  rolling upgrades; database and stored-object migration is forward compatible
  and has a tested rollback boundary before irreversible steps.
- Published artifact, schema, and receipt identities remain immutable forever;
  end of support affects new operations, not historical verification.

Client SDKs, CLI, API, event, renderer, reconciler, and stored-state
compatibility matrices are published for every release. A version marked end
of support fails new use explicitly rather than silently selecting another
version.

## Release and upgrade readiness

GA requires:

- thirty consecutive days meeting availability and latency objectives in a
  production-equivalent environment;
- capacity, soak, chaos, dependency-outage, and noisy-neighbor evidence;
- zero unresolved critical/high security findings in the released path;
- successful backup restore and regional failover exercises;
- N-1 rolling upgrade, rollback-before-irreversible-migration, and event replay;
- runbooks, dashboards, alerts, on-call ownership, escalation, status, security
  contact, and consumer-facing limits/support documentation; and
- a signed readiness report linking exact product, renderer, schema, test,
  infrastructure-profile, and evidence digests.

## Failure behavior

An unmeasured topology cannot claim conformance. An exhausted error budget
blocks discretionary release and shifts work to reliability remediation.
Capacity or limit breach applies backpressure or rejects new work; it never
drops acknowledged state, bypasses validation, evicts rooted content, or affects
another consumer. Failed backup, stale restore evidence, missing audit, or an
unverified irreversible migration blocks GA or upgrade.

## Required verification

AD-18 archives reproducible availability calculations, latency histograms,
load/soak/chaos results, limit-boundary and decompression tests, quota/fairness
evidence, backup/restore/failover reports, retention/GC proofs, telemetry and
redaction tests, incident exercises, support/upgrade matrices, and the signed
readiness report.
