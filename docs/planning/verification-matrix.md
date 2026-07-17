# Verification matrix

This is the minimum release evidence set. A task may add stricter checks.

The concrete topology used for core production certification is
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md).
Its PostgreSQL transaction/queue/outbox, Distribution/object storage, KMS,
Kubernetes, gVisor, identity, telemetry, migration, and restore claims require
executable evidence in addition to the portable contract evidence below.

## Contracts and portable source

| Area | Positive evidence | Negative evidence |
|---|---|---|
| Contract bundle | Every normative Draft 2020-12 schema and transitive reference resolves offline from one signed bundle; two validators agree; generated models, OpenAPI, AsyncAPI, examples, and docs match | Network schema fetch, unknown schema/digest/field, unresolved reference, validator disagreement, or generated-contract drift fails |
| Agent Spec | Official SDK accepts pinned `26.1.2` fixtures | Unsupported version, malformed kind, duplicate keys, unknown security fields fail |
| Contract encoding | Restricted YAML and equivalent JSON produce the same RFC 8785 JCS bytes and semantic digest; arbitrary payload bytes are unchanged | Duplicate keys/member names, aliases, custom tags, non-string keys, non-finite numbers, or signing raw authoring YAML fails |
| Functional operations | Ordered strict add/replace/remove operations apply atomically to an exact validated baseline; Agent and portable SpecializedAgent sources resolve once | Move/copy/test, root mutation, unknown path, changed ancestor, ambiguous array, partial patch, source escape, cycle, or security path fails |
| File and skill operations | Exact descriptors and current skill approvals produce deterministic effective content | Traversal/case-fold collision, unsafe type/mode, missing expected digest, duplicate skill ID, mutable descriptor, stale approval, or partial delta fails |
| Authority separation | Behavior-only package with logical default model passes | MCP, tools, providers, resources, grants, roles, credentials, tenant bindings, remote code fail |
| Skills | Missing optional skill does not block public source discovery/validation; an explicit binding remove records a consumer's exact effective set | New/changed/high-risk or selected-unapproved skill is quarantined and cannot auto-promote; silent omission fails |
| Generic catalog | A definition-only generic fixture index resolves exact source descriptors | Mutable-only reference, withdrawn digest, substituted source, or ByteDesk service dependency fails |

## Rendering and package safety

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Determinism | Two isolated clean builds emit identical files and digests from identical JCS objects and byte-exact payloads | Timestamp, object-key order, YAML spelling, mode, locale, path, or compression drift changes semantic output or escapes detection |
| Harness compatibility | Native, Hermes, and OpenClaw contract fixtures pass | Unsupported/lossy semantic is explicit and cannot silently pass |
| Renderer release identity | Binding, render, and deployment record the signed renderer-release manifest, executing distribution/platform, schema, and embedded allowlist digests | Version-only selection, tag/PATH fallback, wrong executable/platform/allowlist/schema, runtime allowlist expansion, or withdrawn renderer fails |
| Renderer sandbox | Trusted product renderer runs in a fresh no-network, no-secret, resource-bounded sandbox and emits only declared output | Input execution, hook/plugin/library injection, ambient identity, network, home/config access, timeout, memory, process, or disk escape fails |
| Archive safety | Bounded regular-file package extracts to staging | Traversal, absolute path, symlink, hardlink, device, FIFO, bomb, excessive depth/count/size fail |
| Non-execution | Validation/render completes with network and execution disabled | Package script, install hook, remote URL, or plugin attempt fails |
| Content policy | Secret, malware, and license gates produce evidence | Known secret/malware/denied-license fixtures block publication |
| Skill payloads | Arbitrary declared regular files, including executable files, are preserved by digest without execution | Pipeline execution, unsafe entries, undeclared files, raw secrets, or runtime execution without exact-digest approval and current consumer controls fails |
| Render scope | Public catalog render contains only public inputs; private effective render reflects the exact customization and approved skill set | Consumer instructions/files/identifiers in public output or post-render patching fails |

## OCI and trust

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Artifact graph | Exact source -> render -> deployment -> release edges verify | Wrong/missing subject, media type, size, repository, or source edge fails |
| Signatures | Correct purpose key and workload claims verify | Unknown/revoked/wrong-purpose key or wrong workflow/repo/ref/environment fails |
| Attestations | Required provenance, SBOM, compatibility, evaluation, and policy predicates verify | Missing, stale, tampered, or wrong-subject predicate fails |
| KMS/WIF | Short-lived workload identity signs with non-exportable key | Exported key path, broad identity, KMS outage, or claim mismatch fails closed |
| Registry | Target implementation passes manifest/referrer/immutable-tag/access tests | Cross-project pull, tag mutation, quota breach, or GC of a rooted digest is denied |
| Privacy | Public evidence contains no consumer identifier or private policy data | Leak fixtures fail publication |
| Consumer private keys | Consumer-owned KMS and tenant-dedicated hosted-key profiles sign with separate private-skill, authority/approval, and deployment roles | Cross-consumer shared key, exported key, supplier provenance substituted for private-skill publication or approval, compiler self-approval, wrong purpose, broad IAM, or consumer-unpinned hosted trust fails |

## Installation and update

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Binding | Exact digest, exact renderer-release descriptor, strict functional/file/skill delta, exact skills, and absent/match precondition resolve | Version-only renderer, tag/branch, source substitution, missing revision, wildcard/null precondition, raw secret, security-authority mutation, or ambiguous operation fails |
| Idempotency | Repeated create/bind/update returns one durable result | Same key with different payload conflicts |
| Concurrency | Revision-plus-digest compare-and-swap advances the exact predecessor and rejects ABA | Stale, force-pushed, reordered, wildcard, lease-only, or conflicting input cannot overwrite accepted state |
| Git reconciliation | Event and scheduled scan converge on the same immutable installation/binding intent | Git writes runtime desired state; missed, duplicate, reordered, malformed, or provider-unavailable events mutate safe state |
| Automatic update | Compatible source with unchanged skills can be proposed/promoted | Major, lossy, changed-skill, trust, authority, or approval-weakening change requires human decision |
| Authority snapshot | Fresh signed compile/activate/recover snapshots bind consumer, subject, target, candidate, desired revision, nonce, predecessor, current subdigests, and skill approvals | Expired, replayed, wrong-audience/purpose/consumer/target/candidate/policy/subdigest, compilation-snapshot reuse, or unsigned assertion fails |
| Desired writer | Promotion Coordinator alone advances one TargetDeliveryState aggregate in either managed or consumer-native storage | Git, compiler, host, observation, update bot, capability verifier, duplicate store, dual write, stale lease, or direct operator mutation fails |
| Lifecycle | Installation, candidate, rollout, host-attempt, and slot states pass exhaustive legal transition models | Unknown/coerced/backward transition, terminal-state reuse, observation self-promotion, or failed rollout claiming recovery fails |
| Forward recovery | Newest eligible historical functional content is rebuilt with current source trust, renderer/compiler, authority, approval, policy, and canary evidence | Old deployment/render/receipt/signature/authority/tooling reactivation, withdrawn content, revoked renderer execution, silent dependency substitution, or Git dependency fails |

## Deployment and runtime

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Target identity | Reconciler reads/observes exactly one consumer target | Wrong consumer/target or human/agent privilege use is denied |
| Pull and verify | Private artifact is pulled by digest with scoped credential | Tag pull, cross-tenant pull, expired/revoked credential, or trust mismatch fails |
| Effective render | Private deployment contains a complete deterministic effective render and manifest | Missing customization/skill edge, public/private mismatch, or post-render mutation fails |
| Stable slot | Agent retains UID/GID/port/service/workspace across reorder/update | Retired slot reuse or another agent's slot is denied |
| Technical canary | Target-scoped host returns signed/digested artifact, file, process, slot, readiness, resource, and switch evidence | Host desired write, human/agent/MCP credential, wrong nonce/candidate/target, stale evidence, or process-only false positive fails |
| Capability canary | Separate consumer verifier proves workload login, one permitted action, and the expected policy denial for a forbidden sentinel | Host execution of a capability probe fails; accepting timeout, 404, unavailable endpoint, parser/network error, wrong actor, or missing evidence as denial evidence also fails |
| Activation modes | Certified isolated-candidate or guarded-in-place mode follows its exact transition graph and appends observations | Unsupported mode, physical switch treated as promotion, pre-switch corruption, or late evidence promoting a superseded revision fails |
| Recovery | Restart distinguishes pre/post-switch and a separately compiled recovery rollout converges | Crash before/after switch, observation retry, registry outage, canary failure, or no eligible recovery candidate causes silent content selection |
| Receipt reproduction | Stored graph and inputs reproduce exact active file digests | Missing or inconsistent receipt edge is terminal |

## API and CLI

| Area | Positive evidence | Negative evidence |
|---|---|---|
| Public operations | Catalog/validate/render/package/publish/pull/inspect/verify work without ByteDesk credentials where local/public | Public path cannot access private installation/deployment data or publish tenant content |
| Authenticated operations | Consumer-scoped import/deploy/status/receipt work with stable JSON | Wrong consumer, target, audience, scope, or stale token fails |
| Async actions | Progress, cancellation, terminal state, retry, and correlation are durable | Duplicate worker, timeout, crash, and cancellation races converge |
| API/events | Signed OpenAPI 3.2 references normative schemas; CloudEvents 1.0.2 and AsyncAPI 3.1 notifications carry exact schema/revision/sequence and resync on gaps | Copied schema drift, unknown command field, missing ETag, offset paging, idempotency collision, event authority, sequence gap continuation, or secret payload fails |
| Compatibility | API/CLI/current-and-previous minor fixtures, exit codes, stored objects, event replay, and offline receipts remain versioned | Breaking response, command, event, media type, state meaning, or exit-code drift fails contract tests |

## Core third-party certification

A clean environment performs the complete public and generic consumer flow with
no ByteDesk Platform services. It archives commands, versions, source commits,
schema/renderer/product digests, signatures, attestations, receipts, and
redacted logs. Generic certification does not use the ByteDesk marketplace or
its 34+1 catalog.

## Reference catalog certification

After CORE-CERT:

- the marketplace repository builds from a clean clone against the released
  signed contract bundle;
- 34 selectable packages validate and `office-orchestrator` validates as
  system-only; and
- system-package metadata cannot create a ByteDesk profile or principal.

## Reference consumer certification

After a standalone release, the ByteDesk Adapter additionally proves:

- explicit create-profile and bind-existing-profile paths;
- no implicit roles, grants, credentials, or provider connections;
- exact `AgentOrgProfile`, tenant, engine, slot, profile-subdigest, and engine-
  release binding;
- workload Platform login;
- granted MCP discovery/invocation success;
- ungranted, wrong-tenant, wrong-profile, stale-revision, wrong-signer, and
  wrong-subdigest denial; and
- Hermes and OpenClaw direct source cutover with no dual activation writer.

REFERENCE-CONSUMER-CERT requires REFERENCE-CATALOG-CERT when the integration
selects the ByteDesk catalog.

## Operational readiness

- Monthly availability and latency evidence meets every
  `bytedesk.operational-readiness/1` SLO, including thirty consecutive
  production-equivalent days before GA.
- Reference workload p95 validation, render, compile, graph verification, and
  rollout timings meet their objectives with dependency time reported
  separately.
- Capacity proves 10,000 consumers, 100,000 installations, 25,000 targets,
  1,000 concurrent actions, 500 concurrent rollouts, stated request rates, and
  100 million observations with quota, fairness, backpressure, noisy-neighbor,
  worker-loss, and regional-dependency tests.
- Default object, operation, file, archive, renderer-time, memory, and disk
  limits pass boundary and cumulative-expansion tests.
- Retention and GC preserve active/pending/known-good/recovery/audit/legal-hold
  roots.
- Withdrawal and signer/digest revocation block new activation.
- Backup/restore meets regional RPO/RTO, converges the complete content and
  evidence graph, and passes monthly scoped restore plus quarterly full restore
  and regional failover.
- Quotas and deletion prevent cross-consumer data exposure.
- A control-plane or registry outage leaves already verified active state under
  consumer policy while all new changes fail closed.
- OpenTelemetry metrics/traces/logs, append-only administrative audit, redaction,
  dashboards, burn-rate/security alerts, runbooks, on-call/escalation/status and
  security contacts, compatibility/support matrices, incident exercises, and
  N-1 upgrade/event replay are archived in the signed readiness report.
