# System overview

## Context flow

```text
Signed contract bundle + product/renderer releases
        |
        | exact schema, allowlist, executable, and trust-policy digests
        v
Definition-only Git catalog
        |
        | exact commit + Agent Spec/declared-skill validation
        v
Agent Delivery build and catalog plane ----> signed public OCI artifacts
        |
        | binding + skill approvals + short-lived consumer authority
        v
Private deployment compiler ----> prepared per-consumer deployment/release
        |
        v
Promotion Coordinator ----> one TargetDeliveryState / DesiredStateStore
        |                                      |
        | signed canary challenge              | exact desired revision
        v                                      v
Consumer Capability Verifier       target-scoped Host Reconciler ---> harness
        |                                      |
        +------ signed evidence + observations-+
                               |
                               v
                 Coordinator-only promotion or forward recovery
```

## Logical components

### Contract bundle and catalog client

The signed product contract bundle carries every Agent Delivery-owned JSON
Schema Draft 2020-12 schema, transitive references, OpenAPI, AsyncAPI,
compatibility metadata, and fixtures. Resolution is offline and exact by schema
ID/digest. Source-controlled schemas are normative; generated models and prose
are drift-checked projections.

The catalog client reads a definition-only Git catalog at an immutable commit,
validates its layout against those contracts and the official Agent Spec SDK,
rejects ambiguous YAML, creates RFC 8785 identities, and projects discovery
metadata. Original authoring bytes are provenance-only. Contract role rather
than extension determines parsing, so arbitrary `.yaml` and binary payloads
remain byte-exact.

### Policy validator

The validator applies official pinned Agent Spec semantics plus the stricter
Agent Delivery portability policy. It rejects credentials, required public
MCP/provider authority, hooks, unsafe package structure, and consumer bindings.
Skill packages may contain executable regular files but are scanned and handled
without execution. Unknown schema, schema digest, field, operation, extension,
or closed-enum value fails.

### Renderer registry

Renderer selection uses Strategy and harness integrations use Adapter. The
signed product distribution contains a compiled registry that maps the
harness/renderer/version tuple to one exact renderer-release manifest. A render
verifies that manifest, actual executing distribution/platform, embedded
allowlist, trust policy, and renderer-owned schemas before running in a fresh
no-network, no-secret, resource-bounded sandbox.

Public renders accept only unchanged tenant-free source and exact declared
public skills. Private compilation performs a full rerender with the same exact
renderer release recorded by public lineage. Runtime plugins and fallback to a
tag, PATH binary, local build, or different installed version are forbidden.

### OCI publisher and trust verifier

The publisher builds deterministic artifacts, publishes by digest, attaches
same-repository signatures/attestations/SBOMs, and records explicit descriptors
for every cross-repository edge. Authoritative objects use RFC 8785 canonical
JSON and arbitrary payloads preserve exact bytes.

Product, public-source, public-render, consumer-private-skill,
consumer-authority, and consumer-deployment signer purposes are distinct. All
private purposes are isolated per consumer, preferably with non-exportable keys
in the consumer's KMS boundary. Publisher provenance is not consumer skill
approval.

### Installation and Promotion Coordinator

An installation is digest-pinned consumer intent, not consumer identity. The
Promotion Coordinator evaluates prepared candidates and is the sole logical
writer of one `TargetDeliveryState` per consumer/runtime target. It advances the
one selected Agent Delivery-managed or conforming consumer-native
`DesiredStateStore` through the exact absent-or-match revision/digest
precondition, issues canary challenges, verifies evidence, and records promotion
or recovery.

Git, update bots, operators, consumer applications, compilers, hosts,
observations, and recovery planners submit intent, commands, prepared content,
or evidence. They never write desired state. A second authoritative row and
live dual write are forbidden; other copies are disposable read models.

### State separation

Installation lifecycle, candidate preparation, target desired state, runtime
rollout, asynchronous action, Host Reconciler attempt, observed active-slot
facts, and append-only evidence are separate contracts. They do not share one
catch-all status enum. Candidate `prepared` means signed content exists;
rollout `promoted` means the Coordinator completed a target CAS transition; a
host `active` observation reports physical fact only. A post-switch failure is
`recovery_required`, and only a separately prepared forward recovery rollout
can later become `promoted`.

### Deployment compiler

The compiler applies the closed, ordered functional property/file/skill delta
to verified source, verifies exact consumer skill approvals, and reconstructs a
complete Agent Spec. It validates a current consumer-signed authority snapshot,
resolves the exact renderer release through the compiled allowlist, performs a
full sandboxed render, and embeds the effective bundle and manifest in a
per-consumer-signed deployment. It prepares a runtime release but cannot make it
desired state.

The private delta may configure functional models, providers, tools, MCP,
files, harness settings, and opaque secret references. Consumer identity,
grants, credential state, workload identity, trust, mandatory sandbox/network
policy, approvals, lifecycle, and target arrive as separately signed opaque
authority. Activation and recovery require a newly verified snapshot bound to
the exact candidate and desired revision.

The compiler never patches public render output. V1 has no separate private-
render artifact. Exact public output is reusable only for empty customization
when every schema, source, skill, renderer release, execution variant,
allowlist, parameter, and normalized input matches.

### Host Reconciler protocol

The target-scoped Host Reconciler reads desired state, verifies and stages exact
content without executing package files, performs local technical preflight,
switches at the certified harness-safe boundary, and appends observations. It
cannot write desired state, promote, hold human or agent-capability credentials,
or invoke MCP/tool/provider probes.

### Consumer Capability Verifier protocol

The separately consumer-owned Adapter exercises an isolated or provisional
candidate through its normal workload identity and authorization path. It
returns challenge-bound evidence for workload login, one policy-selected
permitted capability, and one sentinel capability denied by the exact expected
policy class. Timeout, transport failure, missing endpoint, `404`, parser error,
or unavailable tool is not denial evidence. The verifier cannot promote.

### API, CLI, and events

The versioned API and CLI expose public validation/render/verification without a
ByteDesk identity and authenticated private operations without leaking private
inputs publicly. OpenAPI 3.2.0 and AsyncAPI 3.1.0 reuse the normative schemas;
CloudEvents 1.0.2 events are at-least-once notifications, never desired-state,
approval, identity, or authorization authority. Long work uses durable action
resources. Every mutation uses idempotency plus exact HTTP and domain
preconditions.

## Deployment and recovery shape

V1 starts as a modular monolith with explicit ports, a durable store, work
queue, transactional outbox/inbox, and isolated renderer workers. Logical
boundaries permit a measured future split without changing contracts.

The harness certifies isolated-candidate or guarded-in-place activation. Fresh
Host Reconciler technical evidence and separate consumer capability evidence
must match the Coordinator's nonce-bound canary plan before promotion. A
post-switch failure enters `recovery_required`; it is never relabeled as rolled
back.

Forward recovery selects eligible historical functional content only. Current
trusted schemas and renderer/compiler tooling rebuild it, and current content
trust, skill approvals, consumer authority, evaluation, and canary gates run
again. Historical deployments, render bundles, desired records, receipts,
signatures, authority snapshots, credential state, and revoked tooling are
never reactivated.

The information architecture is accepted. GA still requires the measured SLO,
latency, scale, safety-limit, durability, restore, retention, observability,
security-response, compatibility, and support evidence in
[Operational readiness v1](../standards/operational-readiness-v1.md).

## Pattern choices

- **Strategy:** exact renderer-release selection and compatibility policy.
- **Adapter:** harness, Agent Spec SDK, Git, registry, KMS, consumer authority,
  capability verifier, DesiredStateStore, and host integrations.
- **State / Process Manager:** installation, candidate, rollout, promotion, and
  recovery with one Coordinator writer.
- **Outbox / Inbox / Idempotent Receiver:** reliable notification events.
- **Saga-style compensation:** staged cleanup and new forward recovery actions.
- **Anti-corruption layer:** consumer identity and authorization stay outside
  the core domain.
