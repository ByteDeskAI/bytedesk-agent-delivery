# Scope and authority boundaries

## Product responsibilities

Agent Delivery owns:

- authoring and catalog contracts for portable Agent Spec packages;
- policy validation that prevents packages from carrying runtime authority;
- deterministic renderer selection and harness Adapters;
- source, render, deployment, catalog, and release-manifest artifact schemas;
- OCI packaging, digest graphs, signatures, attestations, and SBOM interfaces;
- release channels, withdrawal, compatibility, and update proposals;
- installation intent and non-authorizing specialization envelopes;
- deployment compilation inputs and outputs;
- desired-state reconciliation, canary, promotion, forward rollback, and
  append-only receipts;
- public CLI/API contracts and a generic consumer integration protocol; and
- conformance, security, failure-injection, and recovery test suites.

## Consumer responsibilities

The consuming platform owns:

- organizations, tenants, users, and human login;
- durable agent employment or organizational identity;
- reporting lines, lifecycle, capacity, and business roles;
- MCP servers, tools, resources, grants, and call-time authorization;
- model/provider selection, connections, credentials, and secret storage;
- workload identity, certificate/token issuance, and sender constraints;
- human-in-the-loop and business approval policy;
- conversations, tasks, goals, queues, and work source of truth;
- runtime isolation and the decision to stop a compromised active agent; and
- consumer-specific audit, retention, legal hold, and compliance policy.

## Runtime responsibilities

A runtime or engine owns execution semantics, process isolation, local
workspaces, model sessions, and safe activation boundaries. It implements the
Agent Delivery host protocol but cannot weaken artifact verification or promote
itself.

## Dual-control activation

Activation requires two independently verifiable decisions:

1. Agent Delivery proves **what** definition and deployment content is being
   activated: exact digests, renderer, provenance, trust, and receipt lineage.
2. The consumer proves **what it may do**: tenant, identity, current policy,
   current grants, credentials, lifecycle, and runtime target.

No artifact can bootstrap its own trust policy. No consumer can substitute a
different source after a trusted digest has been approved.

## Explicit non-goals for v1

- An agent chat or work execution runtime.
- A new identity provider or authorization engine.
- A marketplace user interface.
- Runtime-loaded third-party renderer plugins.
- Arbitrary executable package hooks.
- Embedding required MCP servers or provider credentials in reusable packages.
- Cross-tenant shared runtime isolation claims.
- Production deployment as part of repository bootstrap.

## Marketplace topology

The product repository contains the protocols, reference implementation, CLI,
and delivery control plane. Portable catalog content lives in a definition-only
Git repository behind a replaceable catalog interface. The ByteDesk reference
catalog is planned as `ByteDeskAI/bytedesk-agent-marketplace`; another consumer
can supply a compatible repository. Only test fixtures belong in this product
repository. The protocol never assumes a ByteDesk organization, service, or
hosted marketplace.
