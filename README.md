# ByteDesk Agent Delivery

**Define once. Verify everywhere. Deliver anywhere.**

ByteDesk Agent Delivery is an open, harness-neutral software supply chain for
AI agents. Authors define portable agents using Agent Spec; the system
validates and renders those definitions for Hermes, OpenClaw, and future
harnesses, publishes signed content-addressed OCI artifacts, and promotes,
deploys, or rolls them back with verifiable provenance and receipts.

Consuming platforms keep authority over identity, permissions, credentials,
MCP grants, provider connections, and business approval. An agent package can
describe behavior and carry optional skills, but it cannot grant itself access.

## Status

This repository is in the architecture and delivery-planning phase. The
product boundary, security invariants, artifact contracts, and implementation
workstreams are documented under [`docs/`](docs/README.md). No production
deployment is authorized or implied by this repository.

## Product promise

- One portable Agent Spec definition can target multiple agent harnesses.
- Every release and deployment is identified by an immutable OCI digest.
- Deterministic renderers make an output reproducible from recorded inputs.
- Signatures, attestations, SBOMs, and receipts prove what was built and run.
- A consuming platform attaches its own policy without transferring authority
  to the marketplace or artifact.
- Promotion, canary, and forward rollback preserve a verifiable history.

## System boundary

Agent Delivery owns cataloging, validation, deterministic rendering, OCI
packaging, signing interfaces, release channels, installation intent,
deployment compilation, reconciliation protocols, promotion, rollback, and
receipts.

It does **not** own a customer's users, agent employment identity, roles, MCP
grants, provider credentials, workload login, conversations, or work queues.
Those remain with the consuming platform or runtime.

## Documentation

- [Product story](docs/product/story.md)
- [Scope and authority boundaries](docs/product/scope-and-boundaries.md)
- [ADR-0001](docs/architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [System overview](docs/architecture/system-overview.md)
- [Security and trust](docs/architecture/security-and-trust.md)
- [Development plan](docs/planning/development-plan.md)
- [Detailed task breakdown](docs/planning/task-breakdown.md)
- [Verification matrix](docs/planning/verification-matrix.md)
- [ByteDesk Platform integration profile](docs/integrations/bytedesk-platform.md)

## License

[MIT](LICENSE)
