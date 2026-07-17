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
- Treat every package, archive, OCI layer, catalog entry, specialization, and
  customization as untrusted input.
- Treat consumer customization as a private, deterministic functional delta. It
  may override any functional agent property and add, replace, or remove
  arbitrary regular files, but it must not become authority for identity,
  grants, credentials, trust, or mandatory security policy.
- Use only the closed `bytedesk.json-patch/1` add/replace/remove profile and the
  separate digest-preconditioned file and skill operations. Every durable
  aggregate mutation uses `precondition.kind: absent` for create or `match`
  with both exact revision and digest; omission, `null`, wildcard, force, and
  digest-only aggregate comparison fail. Nested file and skill delta items use
  their documented absent-or-current-item-digest preconditions under that outer
  aggregate compare-and-swap.
- Use exact digests for authority. Tags and channels are discovery metadata.
- Define every Agent Delivery-owned authoritative object with the accepted JSON
  Schema Draft 2020-12 contract, exact schema digest, closed authority-bearing
  objects, and offline signed contract-bundle resolution. Generated code,
  OpenAPI, AsyncAPI, examples, and prose are projections, not competing schema
  authorities.
- Treat YAML as a human-authoring format only. Contract YAML must use the YAML
  1.2 JSON-compatible subset and must reject duplicate keys, aliases, custom
  tags, non-string keys, and non-finite numbers. Convert authoritative objects
  to the JSON data model and RFC 8785 JCS bytes before hashing or signing;
  original YAML is provenance, not semantic identity. Arbitrary payload files
  and binary content remain byte-exact.
- Select renderers only through the compiled allowlist and the complete exact
  signed renderer-release descriptor. Do not execute artifact-provided hooks,
  load renderer plugins at runtime, or fall back to a tag, PATH binary, local
  build, or different installed renderer.
- Skill packages may contain arbitrary regular files, including executable code.
  Validation, rendering, compilation, staging, and activation must never execute
  those files. A consuming runtime may execute a skill only after explicit
  approval of its exact digest and under current consumer sandbox, network,
  identity, and call-time authorization policy.
- Keep public catalog renders tenant-free. Apply consumer customization and the
  exact approved public/private skill set through a full private rerender, and
  embed that effective render in the consumer deployment artifact.
- Keep public artifacts free of tenant identifiers and secrets.
- Accept private authority only through current, consumer-signed authority and
  exact-skill-approval evidence. Production private-skill, authority, and
  deployment signers are purpose-separated and isolated per consumer.
- Keep exactly one `TargetDeliveryState` and one selected `DesiredStateStore`
  per consumer/runtime target. The Promotion Coordinator is its sole logical
  writer; hosts, Git, compilers, bots, observations, and consumer applications
  submit intent or evidence and never write desired state directly.
- Keep Host Reconciler technical evidence separate from consumer-owned
  capability evidence. Promotion requires a fresh nonce-bound permitted check
  and exact policy-denial result; transport failure or absence is not denial.
- Preserve append-only evidence. Recovery creates a new revision from eligible
  historical functional content using current trusted tooling, current consumer
  authority, fresh evaluation, and fresh canary evidence; it never reactivates
  an old deployment, receipt, signature, authority snapshot, or renderer.
- Treat the accepted reliability, scale, recovery, retention, compatibility,
  security-response, and support targets as GA gates. Do not claim operational
  conformance without the measured evidence required by the readiness profile.
- Never add secrets, private keys, credentials, or production mutations to the
  repository.

## Documentation rules

- `docs/` is the product source of truth.
- Update the relevant contract and ADR in the same change as a boundary change.
- Keep consumer-specific details in `docs/integrations/`; do not leak them into
  the portable definition or core protocol.
- Record inputs, outputs, failure behavior, and verification for every task.
