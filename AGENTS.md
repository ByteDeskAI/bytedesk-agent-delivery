# Agent instructions

## Product boundary

ByteDesk Agent Delivery is an independent, headless agent supply-chain and
delivery product. It is not ByteDesk Platform and it is not an agent runtime.

The product may describe, validate, render, package, sign, promote, and deliver
agent definitions. It must never make an agent package authoritative for users,
roles, MCP grants, provider access, credentials, workload identity, or business
approval. Those are consuming-platform responsibilities.

## Engineering rules

- Read `docs/architecture/adr/` before introducing a new pattern or boundary.
- Prefer the smallest implementation that satisfies a documented contract.
- Use test-driven development for code changes.
- Use Strategy for renderer selection and Adapter for harness, registry, KMS,
  and consumer integrations.
- Treat every package, archive, OCI layer, catalog entry, and specialization as
  untrusted input.
- Use exact digests for authority. Tags and channels are discovery metadata.
- Do not execute artifact-provided hooks or load renderer plugins at runtime.
- Keep public artifacts free of tenant identifiers and secrets.
- Preserve append-only evidence; rollback creates a new forward revision.
- Never add secrets, private keys, credentials, or production mutations to the
  repository.

## Documentation rules

- `docs/` is the product source of truth.
- Update the relevant contract and ADR in the same change as a boundary change.
- Keep consumer-specific details in `docs/integrations/`; do not leak them into
  the portable definition or core protocol.
- Record inputs, outputs, failure behavior, and verification for every task.
