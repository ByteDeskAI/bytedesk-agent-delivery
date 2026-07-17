# Contributing

ByteDesk Agent Delivery is documentation-first while its v1 contracts are being
implemented.

## Before changing a boundary

Read:

- [`AGENTS.md`](AGENTS.md)
- [`docs/product/scope-and-boundaries.md`](docs/product/scope-and-boundaries.md)
- [`docs/architecture/adr/0001-independent-agent-delivery-control-plane.md`](docs/architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [`docs/architecture/security-and-trust.md`](docs/architecture/security-and-trust.md)

Open or amend an ADR before introducing a new trust boundary, authority owner,
artifact class, renderer-loading model, deployment state authority, or
cross-consumer data path.

## Pull requests

- Keep each change scoped to one task and one verifiable outcome.
- Add failing tests before implementation for code changes.
- Include positive, denial, malformed-input, and relevant fault-injection cases.
- Preserve deterministic output and exact-digest authority.
- Update versioned schemas and compatibility documentation together.
- Do not add secrets, private keys, production mutations, or real tenant data.
- Do not make portable packages authoritative for tools, MCP, providers,
  credentials, users, roles, or grants.

## Renderer contributions

Renderers are compiled, allowlisted Adapters. A renderer must publish a
compatibility matrix, deterministic fixtures, file-digest manifest, and explicit
loss behavior. Runtime-loaded renderer plugins are not accepted.

## Catalog contributions

Canonical agent definitions belong in a compatible definition-only catalog
repository, not this product repository. This repository may contain only
minimal test fixtures required to prove contracts.
