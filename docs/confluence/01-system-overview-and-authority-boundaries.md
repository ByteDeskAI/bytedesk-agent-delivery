# System overview and authority boundaries

## Purpose

ByteDesk Agent Delivery is a headless, harness-neutral supply chain for portable
AI agents. It accepts reusable Agent Spec definitions, validates that they are
non-authorizing content, renders them for a declared harness, packages the
results as content-addressed OCI artifacts, and manages promotion to hosted
runtimes with verifiable receipts.

The product solves distribution and deployment. It does not become the
consumer's identity provider, policy engine, MCP broker, work system, or agent
runtime.

The governing decision is [ADR-0001](../architecture/adr/0001-independent-agent-delivery-control-plane.md).
Its production reference implementation is fixed separately by
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md):
a Go modular monolith and CLI, PostgreSQL transaction/durable-work authority,
OCI Registry and archive Adapters, isolated render workers, and Kubernetes
deployment. The stack is not part of an agent definition and creates no
consumer identity, grant, credential, approval, or runtime authority.

## Product story

Agent definitions are frequently trapped in one runtime's file layout. The
same employee or specialist is then maintained as unrelated Hermes, OpenClaw,
and SaaS-specific bundles. Operators cannot reliably reproduce which source,
renderer, policy, and tenant input produced a running process.

Agent Delivery treats an agent like a software release:

1. An author commits a portable definition.
2. Publication validates it, converts structured authoring input to canonical
   JSON, signs the canonical identity, and addresses it by digest.
3. A consumer selects that exact digest and a supported harness.
4. The consumer attaches a deterministic functional customization delta,
   selects exact public or private skill digests, and supplies current policy.
5. The consumer supplies a fresh signed authority snapshot and exact signed
   approval evidence for every effective skill digest.
6. Agent Delivery resolves those private inputs, performs a complete render
   with an exact trusted renderer release, embeds the effective bundle and
   manifest in a private deployment, and signs it with a consumer-dedicated
   deployment key.
7. The Promotion Coordinator publishes one exact target revision through the
   target's sole `DesiredStateStore`; an engine-scoped reconciler verifies,
   stages, activates, and observes it.
8. Separate Host Reconciler and Consumer Capability Verifier evidence gates
   promotion, and a receipt records the complete evidence chain.

The product promise is: **Define once. Verify everywhere. Deliver anywhere.**

## Main actors

| Actor | Responsibility | Explicitly cannot do |
|---|---|---|
| Definition author | Create portable Agent Spec content and optional skills | Grant tenant authority or choose consumer credentials |
| Marketplace publisher | Validate, catalog, sign, and publish public artifacts | Bind an agent to a consumer identity |
| Agent Delivery control plane | Render, package, inspect, promote, reconcile, and record receipts | Authenticate humans or make call-time MCP decisions |
| Consuming platform | Own organizations, identity, policy, grants, credentials, and approvals | Substitute mutable source after a digest is approved |
| Harness adapter | Translate supported semantics into one runtime format | Silently discard unsupported semantics |
| Host reconciler | Activate verified desired state for one engine | Promote itself or broaden its engine scope |
| Promotion Coordinator | Advance one target aggregate through exact compare-and-swap | Create consumer authority or accept self-promotion |
| Consumer Capability Verifier | Prove permitted and denied behavior through the normal consumer authorization path | Write desired state or promote a rollout |
| Runtime | Execute an activated definition | Treat package metadata as permission |

## Logical components

- **Catalog** exposes signed discovery metadata, release channels, withdrawal,
  and compatibility. Tags and channels help discovery; they are never
  deployment identity.
- **Validator** checks the pinned Agent Spec version, the applicable public or
  private content profile, archive safety, and package limits. Private
  functional configuration is accepted as untrusted desired data, never
  executed by Agent Delivery, and never treated as proof of authority.
- **Renderer registry** selects a compile-time allowlisted Strategy and Adapter
  by the exact signed renderer-release manifest. The running product records
  the actual executed distribution or worker digest, platform, embedded
  allowlist digest, and renderer-owned schema digests; a name or semantic
  version alone is never execution authority.
- **Artifact publisher** emits deterministic public source and tenant-free
  catalog render artifacts. The private compiler embeds a fully resolved render
  bundle and manifest in each deployment; v1 has no separate private-render
  artifact.
- **Installation and binding service** records the consumer's exact source
  choice, deterministic functional customization, file operations, and exact
  public/private skill selection.
- **Promotion Coordinator** applies compatibility, evaluation, signed consumer
  authority, canary, concurrency, and forward-recovery rules. It is the only
  logical writer of one `TargetDeliveryState` aggregate per target.
- **Desired-state service** exposes that monotonic aggregate through exactly
  one selected `DesiredStateStore` Adapter. A consumer-native store may
  implement the port, but a second authoritative row and live dual write are
  forbidden.
- **Host reconciler** verifies the full graph and performs safe activation.
- **Consumer Capability Verifier** supplies separately signed workload-login,
  permitted-capability, and explicit policy-denial evidence. The Host
  Reconciler performs only local technical checks and never receives an agent
  capability credential.
- **Receipt ledger** records append-only inputs, transitions, observations, and
  terminal outcomes.
- **API and CLI** expose the same versioned headless contract to first-party and
  third-party consumers.

These components can begin in a modular monolith. Their boundaries are
contractual, not a requirement to create premature microservices.

## Authority matrix

| Concern | Authoritative owner |
|---|---|
| Reusable Agent Spec source and portable skills | Marketplace Git source |
| Public source/render provenance | Agent Delivery publisher |
| Catalog channels and withdrawal | Agent Delivery catalog |
| Installation, exact source digest, and functional customization intent | Consumer-approved binding in Agent Delivery |
| Organization, user, agent employment, reporting, lifecycle | Consuming platform |
| Human and workload login | Consuming platform identity system |
| Roles, MCP/tool/resource grants, and provider access authorization | Consuming platform policy system |
| Credential values, opaque-reference resolution, token issuance | Consuming platform secret and identity systems |
| Call-time authorization | Consuming platform or its MCP authorization service |
| Deterministic render and package evidence | Agent Delivery |
| Runtime process and workspace behavior | Harness/runtime |
| Runtime target intent and current security authority | Consuming platform |
| Serialized desired release, rollout CAS, and deployment receipts | Agent Delivery Promotion Coordinator through the one selected store |
| Business tasks, goals, queues, and conversations | Consuming platform |

## Dual-control activation

Activation requires two independent decisions:

1. Agent Delivery proves **what content** is being activated: exact source,
   renderer-release manifest, executed product distribution, binding,
   selected skills, embedded effective render, deployment, release, signer,
   schema, and provenance digests. That proof independently requires trusted
   signatures, complete pinned qualification for every selected
   renderer/platform, and fresh nonce-bound authenticated current release
   status.
2. The consumer proves **what the workload may do** through a fresh signed
   `bytedesk.consumer-authority/1` snapshot and exact
   `bytedesk.skill-approval/1` evidence. Activation rechecks those inputs; a
   compilation-time snapshot is not reused as current authority.

Neither side can impersonate the other. A valid artifact with no current
consumer authorization cannot run. A valid consumer principal cannot substitute
an unapproved artifact.

## End-to-end trust boundaries

The main boundaries are:

- untrusted author input into the validator;
- public Git into publication CI;
- CI or signer workload identity into purpose-specific non-exportable KMS keys
  or the separately pinned contract-release Sigstore trust service;
- public registry artifacts into private consumer compilation;
- signed consumer authority and skill approval into deployment compilation;
- the sole Promotion Coordinator writer into one selected desired-state store;
- control plane desired state into an engine-scoped host identity;
- candidate runtime behavior into a separate consumer Capability Verifier; and
- activated files into the runtime process.

Every boundary has an exact subject, expected signer, size and content limits,
and a fail-closed outcome. Trust policy is distributed independently of the
artifact it verifies.

Every Agent Delivery-owned authority object has a closed JSON Schema Draft
2020-12 schema distributed offline in the signed contract bundle. HTTP uses
OpenAPI 3.2.0 over those same schemas; integration events use AsyncAPI 3.1.0
and CloudEvents 1.0.2 and remain notifications rather than authority. Exact
contract rules are in
[Machine contracts v1](../standards/machine-contracts-v1.md).
Release qualification, typed evidence, append-only status, and fresh head
verification are defined by
[Release qualification and status v1](../standards/release-qualification-v1.md).

Declared structured contract objects cross these boundaries in one authority
representation: the JSON data model serialized as RFC 8785 JCS bytes. Contract-
authoring YAML is accepted only as human-authored YAML 1.2 JSON-compatible input
and is rejected when it contains duplicate keys, aliases, custom tags,
non-string mapping keys, or non-finite numbers. Original YAML can be retained;
an integrity reference to it is provenance/storage-integrity evidence only and
is never semantic identity, artifact authority, or activation authority.
Arbitrary payload files,
including files named `.yaml`, retain their exact raw bytes and are not parsed
as contracts based on filename.

## Reference catalog

The initial reference catalog preserves the reviewed ByteDesk roster as:

- exactly **34 selectable employee-agent definitions**; and
- one non-selectable **`office-orchestrator` reference system package**.

The system package demonstrates runtime coordination content. Importing it does
not create an employee, organizational profile, workload principal, MCP grant,
or credential. Its non-selectable status is part of signed catalog metadata.

The reference catalog bootstraps interoperability; the product architecture
does not depend on ByteDesk Platform.

## Operational invariants

- Activation is by immutable digest, never by tag or branch.
- Identical normalized inputs produce byte-identical outputs.
- Semantically identical accepted YAML and JSON authoring input produces the
  same RFC 8785 canonical JSON identity; YAML presentation bytes never affect
  an authoritative digest.
- No definition, binding, skill, or generated file can make itself authoritative
  for MCP/tool/resource grants, roles, credentials, or provider access. A
  private binding may describe desired functional configuration and opaque
  secret references, but current consumer authorization is still required.
- Public catalog renders are tenant-free and reject customization input.
- Private deployment compilation performs a complete render after resolving the
  customization delta and approved skills; it never patches a public render
  after rendering.
- Renderer selection is bound to an exact renderer-release manifest and actual
  executed product-distribution digest under an immutable product-release
  trust-policy ID and digest.
- The host pulls by digest and verifies before unpacking or activating.
- Git is reviewed binding intent, never runtime desired state. Only the
  Promotion Coordinator advances the one target aggregate by revision-and-
  digest CAS; a lease, observation, host, or event cannot bypass it.
- Installation, candidate preparation, runtime rollout, and host observation
  state are separate. A post-switch failure becomes `recovery_required`, never
  an immediate `rolled_back` transition.
- Forward recovery searches previously promoted functional content newest
  first, rejects withdrawn content and revoked tooling, rebuilds with current
  trusted tooling and current signed consumer authority, and creates a new
  revision. Historical known-good evidence is not automatic eligibility.
- An outage may preserve an already verified active release, but blocks new
  imports, compilations, and activations.
- Cross-tenant deployment reuse is denied even when public source is shared.
- Receipts are append-only and sufficient to reproduce the exact decision.
- Production private skill, authority/approval, deployment, and release signing
  uses purpose-separated consumer-owned or tenant-dedicated non-exportable
  keys. Cross-consumer shared private keys are forbidden.
- General availability is gated by the measured SLO, capacity, recovery,
  retention, security-response, compatibility, and support objectives in
  [Operational readiness v1](../standards/operational-readiness-v1.md).

## Non-goals

Version one does not include a marketplace UI, general chat runtime, identity
provider, policy engine, artifact-provided executable hooks, runtime-loaded
renderer plugins, or shared-host isolation claims. Skills may contain arbitrary
regular files, including scripts and binaries, but the delivery pipeline never
executes them and a runtime may do so only under explicit consumer approval,
sandboxing, and authorization. A consumer-specific integration is an Adapter
around the product, not product core.

## Related pages

- [Agent Spec and binding](02-agent-spec-and-binding-profile.md)
- [OCI artifact graph](05-oci-artifact-graph.md)
- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Consumer integration contract](../architecture/consumer-integration-contract.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
