# Verification matrix

This is the minimum release evidence set. A task may add stricter checks.

## Portable source and catalog

| Area | Positive evidence | Negative evidence |
|---|---|---|
| Agent Spec | Official SDK accepts pinned `26.1.2` fixtures | Unsupported version, malformed kind, duplicate keys, unknown security fields fail |
| Authority separation | Behavior-only package with logical default model passes | MCP, tools, providers, resources, grants, roles, credentials, tenant bindings, remote code fail |
| Baseline | 34 selectable packages validate; `office-orchestrator` validates as system-only | System package cannot be imported as employee or create a principal |
| Skills | Missing optional skill does not block source validation | New/changed/high-risk skill is quarantined and cannot auto-promote |
| Catalog | Signed index resolves exact source descriptors | Mutable-only reference, withdrawn digest, or substituted source fails |

## Rendering and package safety

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Determinism | Two isolated clean builds emit identical files and digests | Timestamp, order, mode, locale, path, or compression drift is detected |
| Harness compatibility | Native, Hermes, and OpenClaw contract fixtures pass | Unsupported/lossy semantic is explicit and cannot silently pass |
| Archive safety | Bounded regular-file package extracts to staging | Traversal, absolute path, symlink, hardlink, device, FIFO, bomb, excessive depth/count/size fail |
| Non-execution | Validation/render completes with network and execution disabled | Package script, install hook, remote URL, or plugin attempt fails |
| Content policy | Secret, malware, and license gates produce evidence | Known secret/malware/denied-license fixtures block publication |

## OCI and trust

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Artifact graph | Exact source -> render -> deployment -> release edges verify | Wrong/missing subject, media type, size, repository, or source edge fails |
| Signatures | Correct purpose key and workload claims verify | Unknown/revoked/wrong-purpose key or wrong workflow/repo/ref/environment fails |
| Attestations | Required provenance, SBOM, compatibility, evaluation, and policy predicates verify | Missing, stale, tampered, or wrong-subject predicate fails |
| KMS/WIF | Short-lived workload identity signs with non-exportable key | Exported key path, broad identity, KMS outage, or claim mismatch fails closed |
| Registry | Target implementation passes manifest/referrer/immutable-tag/access tests | Cross-project pull, tag mutation, quota breach, or GC of a rooted digest is denied |
| Privacy | Public evidence contains no consumer identifier or private policy data | Leak fixtures fail publication |

## Installation and update

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Binding | Exact digest, allowlisted renderer, strict specialization resolves | Tag/branch, copied base, source substitution, authority field, weaker approval fails |
| Idempotency | Repeated create/bind/update returns one durable result | Same key with different payload conflicts |
| Concurrency | Compare-and-swap advances expected predecessor | Stale, force-pushed, reordered, or conflicting input cannot overwrite human change |
| Reconciliation | Event and scheduled scan converge on same immutable commit | Missed, duplicate, reordered, malformed, or provider-unavailable events preserve safe state |
| Automatic update | Compatible source with unchanged skills can be proposed/promoted | Major, lossy, changed-skill, trust, authority, or approval-weakening change requires human decision |
| Rollback | New forward revision restores last-known-good definition using current authority | Old receipt cannot be reactivated and revoked authority cannot return |

## Deployment and runtime

| Area | Positive evidence | Negative/fault evidence |
|---|---|---|
| Target identity | Reconciler reads/observes exactly one consumer target | Wrong consumer/target or human/agent privilege use is denied |
| Pull and verify | Private artifact is pulled by digest with scoped credential | Tag pull, cross-tenant pull, expired/revoked credential, or trust mismatch fails |
| Stable slot | Agent retains UID/GID/port/service/workspace across reorder/update | Retired slot reuse or another agent's slot is denied |
| Activation | Safe-boundary stage/canary/switch appends observation | Partial pull, disk full, corrupt layer, bad mode/owner, unsafe boundary fails without corrupting active state |
| Recovery | Restart distinguishes pre/post-switch and converges | Crash before/after switch, observation retry, registry outage, and canary failure preserve/recover LKG |
| Receipt reproduction | Stored graph and inputs reproduce exact active file digests | Missing or inconsistent receipt edge is terminal |

## API and CLI

| Area | Positive evidence | Negative evidence |
|---|---|---|
| Public operations | Catalog/validate/render/inspect/verify work without ByteDesk credentials | Public path cannot access private installation/deployment data |
| Authenticated operations | Consumer-scoped import/deploy/status/receipt work with stable JSON | Wrong consumer, target, audience, scope, or stale token fails |
| Async actions | Progress, cancellation, terminal state, retry, and correlation are durable | Duplicate worker, timeout, crash, and cancellation races converge |
| Compatibility | OpenAPI/CLI fixtures and exit codes remain versioned | Breaking response or exit-code drift fails contract tests |

## Core third-party certification

A clean environment performs the complete public and generic consumer flow with
no ByteDesk Platform services. It archives commands, versions, source commits,
digests, signatures, attestations, receipts, and redacted logs.

## Deferred ByteDesk reference certification

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

## Operations and disaster recovery

- Retention and GC preserve active/LKG/rollback/audit/legal-hold roots.
- Withdrawal and signer/digest revocation block new activation.
- Backup/restore converges manifests, blobs, signatures, attestations, catalog,
  trust policy, installation state, desired state, observations, and receipts.
- Quotas and deletion prevent cross-consumer data exposure.
- A control-plane or registry outage leaves already verified active state under
  consumer policy while all new changes fail closed.
