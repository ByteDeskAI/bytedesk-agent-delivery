# ByteDesk Agent Delivery

**Define once. Verify everywhere. Deliver anywhere.**

ByteDesk Agent Delivery is an open, harness-neutral software supply chain for
AI agents. Authors define portable agents using Agent Spec; the system
validates and renders those definitions for Hermes, OpenClaw, and future
harnesses, publishes signed content-addressed OCI artifacts, and promotes,
deploys, or recovers them forward with verifiable provenance and receipts.

Consuming platforms may privately customize every functional part of an agent,
including its files, skills, model, provider, tools, MCP configuration, and
harness settings. They keep separate authority over identity, permissions,
credential values, call-time access, mandatory security policy, and business
approval. Neither a public package nor a private customization can grant itself
access.

## Status

This repository is in the architecture and delivery-planning phase. The product
boundary, information contracts, implementation stack, and production reference
topology are accepted architecturally, and the implementation workstreams are
documented under [`docs/`](docs/README.md).
Concrete schemas, manifests, conformance fixtures, and measured operational
evidence remain release-blocking. No production deployment is authorized or
implied by this repository.

## Product promise

- One portable Agent Spec definition can target multiple agent harnesses.
- Every release and deployment is identified by an immutable OCI digest.
- Human-authored YAML is constrained input; RFC 8785 canonical JSON determines
  the semantic identity of every authoritative structured object. Retained
  authoring bytes are provenance-only; arbitrary payloads named `.yaml` and
  binary payload bytes remain exact.
- Signed JSON Schema Draft 2020-12 contract bundles make exact field, operation,
  API, and event behavior independently consumable and offline-verifiable.
- A renderer is a signed immutable product release, compiled into the allowlist
  and recorded with the exact executing distribution and owned schema digests.
- A deterministic private delta can adapt public content without obscuring its
  provenance or moving security authority into the artifact.
- Signatures, attestations, SBOMs, and receipts prove what was built and run.
- A consuming platform attaches its own policy without transferring authority
  to the marketplace or artifact.
- Short-lived consumer-signed authority and exact skill-approval evidence bind
  current consumer decisions without making Agent Delivery their issuer.
- One Promotion Coordinator advances one desired-state aggregate per target;
  separate host and consumer capability evidence gates promotion.
- Forward recovery rebuilds eligible historical functional content with current
  trusted tooling, current authority, and fresh canary evidence.

## System boundary

Agent Delivery owns cataloging, validation, deterministic public rendering,
private functional-customization contracts, OCI packaging, signing interfaces,
release channels, installation intent, effective deployment compilation,
reconciliation protocols, promotion, forward recovery, and receipts. It treats
every skill file as untrusted and never executes artifact-provided code in its
build or delivery pipeline.

It does **not** own a customer's users, agent employment identity, roles, MCP or
tool grants, credential values, workload login, mandatory security policy,
conversations, or work queues. Those remain with the consuming platform or
runtime. A runtime may execute a skill only after activation, explicit approval
of its exact digest, and validation under current consumer sandbox, network,
identity, and call-time authorization controls.

## Documentation

- [Product story](docs/product/story.md)
- [Scope and authority boundaries](docs/product/scope-and-boundaries.md)
- [ADR-0001](docs/architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [ADR-0002: Implementation stack and reference topology](docs/architecture/adr/0002-implementation-stack-and-reference-topology.md)
- [Architecture decision register](docs/architecture/decision-register.md)
- [System overview](docs/architecture/system-overview.md)
- [Security and trust](docs/architecture/security-and-trust.md)
- [Canonical encoding v1](docs/standards/canonical-encoding-v1.md)
- [Machine contracts v1](docs/standards/machine-contracts-v1.md)
- [Renderer identity v1](docs/standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](docs/standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](docs/standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](docs/standards/operational-readiness-v1.md)
- [Development plan](docs/planning/development-plan.md)
- [Detailed task breakdown](docs/planning/task-breakdown.md)
- [Verification matrix](docs/planning/verification-matrix.md)
- [ByteDesk Platform integration profile](docs/integrations/bytedesk-platform.md)

## License

[MIT](LICENSE)
