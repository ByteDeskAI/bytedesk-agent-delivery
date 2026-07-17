# Architecture resolution register

**Decision date:** 2026-07-17

**Status:** Accepted; implementation and certification evidence remain required

This register summarizes the architecture questions closed during the initial
product review. The linked standards and ADR are normative if summary wording
is ever incomplete.

## 1. Public artifacts and private consumer customization

Public source and public harness renders remain tenant-free. A consumer may
change every functional Agent Spec and harness property, configure models,
providers, tools, MCP servers and opaque secret references, and add, replace,
or remove arbitrary regular files and exact skills. The private compiler
reconstructs and validates the complete effective agent, performs a full
rerender, and embeds it in the private deployment. It never patches a public
render or lets functional content create identity, grants, credentials, trust,
approval, or mandatory security policy.

Normative sources: [ADR-0001](adr/0001-independent-agent-delivery-control-plane.md),
[Agent binding v1](../standards/agent-binding-v1.md).

## 2. Canonical encoding and machine-readable contracts

YAML is restricted human authoring only. Authoritative structured identity is
the validated JSON data model serialized with RFC 8785 JCS; arbitrary payload
bytes remain exact. Agent Delivery-owned objects use closed JSON Schema Draft
2020-12 schemas with stable `$id`, exact schema digest, signed offline contract
bundle, and cross-validator fixtures. Functional object changes use a strict
RFC 6901/6902-derived add/replace/remove profile; files and skills have separate
exact-digest operations. HTTP uses OpenAPI 3.2.0 and RFC 9457. Events use
CloudEvents 1.0.2 and AsyncAPI 3.1.0 and are notifications, never authority.

Normative sources: [Canonical encoding v1](../standards/canonical-encoding-v1.md),
[Machine contracts v1](../standards/machine-contracts-v1.md).

## 3. Immutable renderer and execution identity

A renderer version is not authority. Bindings pin a signed renderer-release
manifest covering exact executable/worker variants, product distribution,
compiled allowlist, schemas, source/toolchain/dependencies, SBOM, conformance,
and SLSA Build Level 3 provenance. Render evidence records the actual executing
digest and platform. The allowlist is embedded in a signed product release and
can be restricted but never expanded by runtime input. Renderer execution is
no-network, no-secret, privilege-dropped, read-only-root, and resource-bounded.

Normative source: [Renderer identity v1](../standards/renderer-identity-v1.md).

## 4. Canary actor and evidence boundary

The Host Reconciler performs technical artifact, slot, process, resource, and
readiness checks only. A consumer-owned Capability Verifier runs one
non-destructive permitted probe and one known denied sentinel through the
candidate's normal identity and authorization path. The Promotion Coordinator
issues a nonce-bound plan, verifies both fresh evidence sets, and is the only
actor that can promote. A timeout or missing endpoint is never proof of denial.

Normative source: [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md).

## 5. Desired-state authority

There is one `TargetDeliveryState` aggregate and one logical writer per target:
the Promotion Coordinator. One DesiredStateStore Adapter is configured—managed
or consumer-native—not both. Git is binding intent, the compiler produces a
prepared candidate, and the host appends observations. None writes desired
state. Store migration is quiesced and digest-checkpointed; live dual write is
forbidden.

Normative sources: [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md),
[Consumer integration contract](consumer-integration-contract.md).

## 6. Lifecycle, predecessor, and forward recovery

Installation, candidate preparation, target rollout, host attempt, and active-
slot facts use separate legal state machines. Creation uses an explicit
`absent` precondition; updates match both monotonic revision and exact digest to
prevent ABA. There is no direct `rolled_back` transition. Post-switch failure
requires a new forward recovery revision. Recovery selects only currently
eligible historical functional content, binds current consumer authority, and
uses current trusted tooling. If nothing qualifies, it fails closed.

Normative sources: [Machine contracts v1](../standards/machine-contracts-v1.md),
[Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md).

## 7. Private signing and consumer sovereignty

Consumer-private skill, consumer authority/approval, and private deployment
signing use separate non-exportable keys and workloads isolated per consumer.
The preferred key lives in the consumer's KMS; an opted-in hosted alternative
must be tenant-dedicated and independently pinned/revocable. Shared cross-
consumer private signing is forbidden. Trust policies are immutable exact-
digest objects. The consumer, not Agent Delivery or a supplier, issues skill
and business approval.

Normative source:
[Consumer authority and private signing v1](../standards/consumer-authority-v1.md).

## 8. Dependencies and milestones

Delivery is gated by `CONTRACTS-FROZEN`, `SUPPLY-CHAIN-CERT`,
`CONTROL-PLANE-CERT`, `RUNTIME-CERT`, and `CORE-CERT`. Reference catalog and
consumer work have separate `REFERENCE-CATALOG-CERT` and
`REFERENCE-CONSUMER-CERT` gates. Dependencies follow contract and authority
needs rather than repository history; Git ingestion is not a compiler or
recovery prerequisite.

Normative source: [Dependency graph](../planning/dependency-graph.md).

## 9. Standalone core versus reference completion

Standalone core includes generic fixtures, native/Hermes/OpenClaw renderer
products, deterministic OCI and trust, consumer-neutral control plane, private
compiler, reference reconciler, API/events, CLI, forward recovery, and
operational certification. It requires no ByteDesk Platform service or ByteDesk
catalog. The 34 selectable ByteDesk packages plus one system package form a
separate reference catalog. Platform/Hermes/OpenClaw cutovers are separate
reference-consumer certification.

Normative source: [Development plan](../planning/development-plan.md).

## 10. Operational and support targets

GA requires measured monthly availability/latency SLOs, the declared 10,000-
consumer/100,000-installation capacity profile, bounded packages and renderer
resources, noisy-neighbor/backpressure tests, regional RPO/RTO, immutable
backup/restore/failover exercises, complete audit and OpenTelemetry, security-
response deadlines, 400-day evidence retention, seven-year historical contract
verification, N-1 upgrades, and defined deprecation/support windows. Thirty
production-equivalent days and a signed readiness report gate GA.

Normative source:
[Operational readiness v1](../standards/operational-readiness-v1.md).

## Related ambiguities also closed

- Consumer authority subdigests travel in a signed, fresh, candidate-bound
  opaque snapshot; Agent Delivery verifies but does not interpret them.
- Provider/model configuration is functional and covered by binding/effective-
  render identity; provider access and credentials remain consumer authority.
- Public `Agent` and `SpecializedAgent` are both official Agent Spec source
  forms; private customization is applied once and adds no new inheritance.
- Changed skill publication and consumer runtime approval are separate. A
  supplier signature is upstream provenance only; a private skill still needs
  the per-consumer role-4 publication signature and exact role-5 consumer
  approval for every effective digest.
- The CLI has explicit `package` and `publish` commands. Render never publishes
  implicitly.
- Trust-policy ID is discovery; exact immutable policy digest is authority and
  remains archived for historical receipt verification.
- `development-plan.json` is an explicitly marked bootstrap planning format
  until AD-01 either publishes and validates the `plan/2` schema and drift
  fixtures or removes its schema claim before `CONTRACTS-FROZEN`.

## Implementation baseline

[ADR-0002](adr/0002-implementation-stack-and-reference-topology.md) fixes the
reference implementation as a Go 1.26 modular monolith and CLI with isolated
Python 3.13 Agent Spec workers, PostgreSQL 18 authoritative state/durable work,
active and recovery-region Harbor HA endpoints with synchronous OCI API
verification, purpose-separated KMS/WIF signing, SPIFFE mTLS, Kubernetes
1.36/1.35 deployment, staged gVisor renderer isolation, and HA OpenTelemetry.
Distribution 3 remains the local/protocol Registry profile.
These are product implementation and certification choices, not fields or
authority that portable agent packages may select.
