# Scope and authority boundaries

## Product responsibilities

Agent Delivery owns:

- authoring and catalog contracts for portable Agent Spec packages;
- constrained YAML authoring input and RFC 8785 canonical JSON identity for
  authoritative structured objects, with byte-exact binary payloads;
- normative JSON Schema Draft 2020-12 contracts, signed offline contract
  bundles, exact schema identities, and OpenAPI/AsyncAPI projections;
- policy validation that prevents packages from carrying runtime authority;
- signed immutable renderer releases, a product-compiled allowlist, sandboxed
  deterministic execution, and harness Adapters;
- source, skill, public-render, deployment, catalog, and release-manifest
  artifact schemas;
- OCI packaging, digest graphs, signatures, attestations, and SBOM interfaces;
- release channels, withdrawal, compatibility, and update proposals;
- installation intent and deterministic private functional-customization
  deltas;
- effective-Agent-Spec resolution, approved-skill composition, and private
  deployment compilation inputs and outputs;
- one target delivery aggregate and one DesiredStateStore per target, Promotion
  Coordinator commands, technical and consumer-capability canary evidence,
  promotion, current-tooling forward recovery, and append-only receipts;
- public CLI/API contracts and a generic consumer integration protocol;
- conformance, security, failure-injection, and recovery test suites; and
- accepted service, performance, scale, durability, retention, security-
  response, compatibility, and support gates whose measured evidence blocks GA.

## Consumer responsibilities

The consuming platform owns:

- organizations, tenants, users, and human login;
- durable agent employment or organizational identity;
- reporting lines, lifecycle, capacity, and business roles;
- the private functional customization of Agent Spec properties, files, skills,
  models, provider endpoints, tools, MCP servers, and harness settings;
- approval of each exact public or private skill digest and authorization for
  any post-activation execution;
- signed, short-lived consumer-authority snapshots and purpose-separated,
  per-consumer private-skill, approval, and deployment trust roots;
- MCP, tool, and resource grants plus every call-time authorization decision;
- model/provider selection, connections, credential values, opaque secret
  references, and secret storage;
- workload identity, certificate/token issuance, and sender constraints;
- human-in-the-loop and business approval policy;
- conversations, tasks, goals, queues, and work source of truth;
- runtime isolation and the decision to stop a compromised active agent; and
- consumer-specific audit, retention, legal hold, and compliance policy.

## Runtime responsibilities

A runtime or engine owns execution semantics, process isolation, local
workspaces, model sessions, and safe activation boundaries. Its target-scoped
Host Reconciler may read desired state and append technical observations, but it
cannot write desired state, weaken verification, run consumer capability
probes, or promote itself. Skill packages may contain arbitrary regular files,
including scripts, binaries, and archives; the runtime may execute them only
after exact-digest consumer approval and under current consumer sandbox,
network, identity, and call-time authorization policy.

## Public portability and private customization

A public catalog package is an official Agent Spec `Agent` by default. An
intentional complete portable `SpecializedAgent` is also allowed, but it is not
private customization, identity, or organizational authority. Its source kind
is explicit, official validation governs it, and its public harness render is
derived only from the unchanged public source and exact declared public skills.

A consumer binding is a private, deterministic delta against an exact public
source. It may override any functional Agent Spec property; add, replace, or
remove regular files; add, replace, or remove public or private skill
descriptors; and configure functional model, provider, tool, MCP, or harness
behavior. It may carry opaque secret references, but never secret values.

The delta cannot create or weaken tenant identity, roles, grants, call-time
authorization, workload identity, credential values, trust roots, signer policy,
or mandatory sandbox, network, approval, or other security controls. Those are
independent consumer inputs and remain authoritative at compile and activation
time.

## Authoring and semantic identity

JSON-compatible YAML 1.2 is an optional human authoring syntax, not an
authoritative or digest-bearing form. Duplicate keys, aliases, custom tags,
non-string keys, non-finite numbers, and other non-JSON values are rejected.
Accepted input is represented in the JSON data model and serialized with RFC
8785 before hashing or signing. Original YAML may be retained only as separately
identified provenance; a checksum over authored bytes is storage integrity only
and never semantic/artifact authority or an activation input. Contract role,
not filename, selects canonicalization, so arbitrary payloads named `.yaml` and
binary files retain their exact raw bytes.

The [canonical encoding profile](../standards/canonical-encoding-v1.md) fixes
the identity bytes. [Machine contracts v1](../standards/machine-contracts-v1.md)
fixes Draft 2020-12 schema identity, closed fields, constrained JSON Patch,
file/skill operations, absent-or-match concurrency, OpenAPI 3.2, CloudEvents,
and AsyncAPI. These are accepted information contracts; concrete signed schema
artifacts and fixtures remain release-blocking evidence.

## Dual-control activation

Activation requires two independently verifiable decisions:

1. Agent Delivery proves **what** definition and deployment content is being
   activated: exact digests, renderer, provenance, trust, and receipt lineage.
2. The consumer proves **what it may do** through a current, short-lived signed
   authority snapshot and exact skill approvals: tenant, identity, current
   policy, grants, credential set, lifecycle, sandbox/network posture,
   approvals, and runtime target.

No artifact can bootstrap its own trust policy. No consumer can substitute a
different public source after a trusted digest has been approved; an intentional
functional override remains explicit in the signed customization lineage.

## Desired-state and recovery authority

Exactly one `TargetDeliveryState` aggregate and one selected
`DesiredStateStore` exist per consumer/runtime target. The Promotion Coordinator
is the sole logical writer. Git, operators, bots, compilers, hosts, observations,
and recovery planners submit intent, candidates, commands, or evidence; they do
not mutate desired state. Promotion requires fresh, matching technical Host
Reconciler evidence and separate consumer capability-verifier evidence.

Recovery is a new forward revision. It may select eligible historical
functional content, but current trusted tooling must rebuild it and current
schemas, skills, authority, evaluation, and canary gates must pass. An old
deployment, receipt, signature, authority snapshot, credential state, render
bundle, or revoked renderer is never reactivated as authority.

## Explicit non-goals for v1

- An agent chat or work execution runtime.
- A new identity provider or authorization engine.
- A marketplace user interface.
- Runtime-loaded third-party renderer plugins.
- Artifact-, binding-, or operator-configured expansion of the compiled
  renderer allowlist.
- Arbitrary executable package hooks.
- Executing package or skill content during validation, rendering, compilation,
  staging, or activation.
- Embedding required MCP servers or provider credentials in reusable packages.
- Cross-tenant shared runtime isolation claims.
- Production deployment as part of repository bootstrap.
- A GA or scale claim before the operational-readiness evidence exists.

## Marketplace topology

The product repository contains the protocols, reference implementation, CLI,
and delivery control plane. Portable catalog content lives in a definition-only
Git repository behind a replaceable catalog interface. The ByteDesk reference
catalog is planned as `ByteDeskAI/bytedesk-agent-marketplace`; another consumer
can supply a compatible repository. Only test fixtures belong in this product
repository. The protocol never assumes a ByteDesk organization, service, or
hosted marketplace.
