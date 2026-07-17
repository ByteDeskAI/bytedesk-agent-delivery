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

## Product story

Agent definitions are frequently trapped in one runtime's file layout. The
same employee or specialist is then maintained as unrelated Hermes, OpenClaw,
and SaaS-specific bundles. Operators cannot reliably reproduce which source,
renderer, policy, and tenant input produced a running process.

Agent Delivery treats an agent like a software release:

1. An author commits a portable definition.
2. Publication validates, normalizes, signs, and addresses it by digest.
3. A consumer selects that exact digest and a supported harness.
4. The consumer attaches a constrained binding plus its current policy.
5. Agent Delivery compiles and signs a private deployment artifact.
6. An engine-scoped reconciler verifies, stages, activates, and observes it.
7. A receipt records the complete evidence chain.

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
| Runtime | Execute an activated definition | Treat package metadata as permission |

## Logical components

- **Catalog** exposes signed discovery metadata, release channels, withdrawal,
  and compatibility. Tags and channels help discovery; they are never
  deployment identity.
- **Validator** checks the pinned Agent Spec version, the product's
  non-authority policy, archive safety, and package limits.
- **Renderer registry** selects a compile-time allowlisted Strategy and Adapter
  by harness identifier and renderer version.
- **Artifact publisher** emits deterministic source, render, deployment, and
  release-manifest artifacts plus attestations and SBOMs.
- **Installation and binding service** records the consumer's exact source
  choice and constrained specialization.
- **Promotion coordinator** applies compatibility, evaluation, approval,
  canary, concurrency, and rollback rules.
- **Desired-state service** exposes one monotonic release for each runtime.
- **Host reconciler** verifies the full graph and performs safe activation.
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
| Installation and exact source digest | Consumer-approved binding in Agent Delivery |
| Organization, user, agent employment, reporting, lifecycle | Consuming platform |
| Human and workload login | Consuming platform identity system |
| Roles, MCP tools/resources, grants, provider access | Consuming platform policy system |
| Credentials, secret references, token issuance | Consuming platform secret and identity systems |
| Call-time authorization | Consuming platform or its MCP authorization service |
| Deterministic render and package evidence | Agent Delivery |
| Runtime process and workspace behavior | Harness/runtime |
| Desired release and deployment receipts | Agent Delivery |
| Business tasks, goals, queues, and conversations | Consuming platform |

## Dual-control activation

Activation requires two independent decisions:

1. Agent Delivery proves **what content** is being activated: exact source,
   renderer, binding, deployment, release, signer, and provenance digests.
2. The consumer proves **what the workload may do**: current tenant, identity,
   lifecycle, grants, credentials, policy, and target engine.

Neither side can impersonate the other. A valid artifact with no current
consumer authorization cannot run. A valid consumer principal cannot substitute
an unapproved artifact.

## End-to-end trust boundaries

The main boundaries are:

- untrusted author input into the validator;
- public Git into publication CI;
- CI workload identity into non-exportable signing keys;
- public registry artifacts into private consumer compilation;
- consumer policy input into deployment compilation;
- control plane desired state into an engine-scoped host identity; and
- activated files into the runtime process.

Every boundary has an exact subject, expected signer, size and content limits,
and a fail-closed outcome. Trust policy is distributed independently of the
artifact it verifies.

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
- A package cannot demand MCP, tools, resources, roles, credentials, or provider
  access.
- Renderer selection is allowlisted and version-pinned.
- The host pulls by digest and verifies before unpacking or activating.
- A failed change leaves or restores a known-good state through a new forward
  revision; history is not rewritten.
- An outage may preserve an already verified active release, but blocks new
  imports, compilations, and activations.
- Cross-tenant deployment reuse is denied even when public source is shared.
- Receipts are append-only and sufficient to reproduce the exact decision.

## Non-goals

Version one does not include a marketplace UI, general chat runtime, identity
provider, policy engine, arbitrary executable hooks, runtime-loaded renderer
plugins, or shared-host isolation claims. A consumer-specific integration is an
Adapter around the product, not product core.

## Related pages

- [Agent Spec and binding](02-agent-spec-and-binding-profile.md)
- [OCI artifact graph](05-oci-artifact-graph.md)
- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Consumer integration contract](../architecture/consumer-integration-contract.md)
