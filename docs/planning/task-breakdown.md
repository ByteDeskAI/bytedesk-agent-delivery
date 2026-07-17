# Detailed task breakdown

Each linked task is a self-contained implementation contract with outcome,
inputs, required work, outputs, acceptance criteria, verification, exclusions,
dependencies, and security amendments.

| ID | Historical Jira | Workstream | Product phase |
|---|---|---|---|
| [AD-01](tasks/AD-01-architecture.md) | BDP-3302 | Architecture and contracts | Core |
| [AD-02](tasks/AD-02-marketplace-bootstrap.md) | BDP-3304 | Definition-only marketplace bootstrap | Reference catalog |
| [AD-03](tasks/AD-03-baseline-catalog.md) | BDP-3306 | ByteDesk 34+1 catalog | Reference catalog |
| [AD-04](tasks/AD-04-renderer-contract.md) | BDP-3307 | Renderer contract/native output | Core |
| [AD-05](tasks/AD-05-hermes-renderer.md) | BDP-3303 | Hermes Adapter | Core |
| [AD-06](tasks/AD-06-openclaw-renderer.md) | BDP-3305 | OpenClaw Adapter | Core |
| [AD-07](tasks/AD-07-oci-packaging.md) | BDP-3308 | OCI packaging | Core |
| [AD-08](tasks/AD-08-signing-and-attestations.md) | BDP-3309 | Signing, provenance, and trust | Core |
| [AD-09](tasks/AD-09-bindings-and-receipts.md) | BDP-3310 | Consumer-neutral installations and receipts | Core |
| [AD-10](tasks/AD-10-control-plane-api.md) | BDP-3311 | Catalog/import API | Core |
| [AD-11](tasks/AD-11-git-desired-state.md) | BDP-3312 | Git installation/binding intent reconciliation | Core |
| [AD-12](tasks/AD-12-update-promotion.md) | BDP-3313 | Promotion Coordinator, updates, and recovery planning | Core |
| [AD-13](tasks/AD-13-private-deployment-compiler.md) | BDP-3314 | Private deployment compiler | Core |
| [AD-14](tasks/AD-14-runtime-reconciler.md) | BDP-3315 | Host protocol/reference reconciler | Core |
| [AD-15](tasks/AD-15-cli.md) | BDP-3316 | CLI and headless automation | Core |
| [AD-16](tasks/AD-16-bytedesk-hermes-cutover.md) | BDP-3317 | ByteDesk hosted Hermes integration | Reference consumer |
| [AD-17](tasks/AD-17-bytedesk-openclaw-cutover.md) | BDP-3318 | ByteDesk OpenClaw integration | Reference consumer |
| [AD-18](tasks/AD-18-certification.md) | BDP-3319 | Standalone conformance and operational readiness | Core certification |

## Core completion checklist

- AD-01 and AD-04 through AD-15 are landed. AD-02 and AD-03 are not core
  prerequisites.
- CORE-CERT evidence is reproducible from a clean environment.
- CONTRACTS-FROZEN, SUPPLY-CHAIN-CERT, CONTROL-PLANE-CERT, and RUNTIME-CERT
  evidence is linked from the signed CORE-CERT readiness report.
- Normative JSON Schemas, schema references, fixtures, OpenAPI, AsyncAPI, and
  compatibility metadata ship as one signed offline bundle and pass drift tests.
- Human-authored YAML is restricted and non-authoritative; all contract digests
  and signatures cover the validated JSON data model serialized with RFC 8785
  JCS, while arbitrary payload files remain byte-exact.
- A third party needs no ByteDesk Platform account or service for the public
  workflow, and needs neither the ByteDesk marketplace nor its 34+1 packages for
  generic consumer certification.
- Native, Hermes, and OpenClaw renderers are signed product releases selected by
  exact renderer-release manifest digest through the compiled allowlist.
- No portable package can create or demand MCP, provider, identity, role,
  resource, credential, or tenant authority.
- A consumer can override every functional agent property and add, replace, or
  remove arbitrary regular files through a private deterministic delta without
  changing the public source or acquiring security authority from content.
- Public catalog renders remain tenant-free; private effective renders are fully
  rebuilt and embedded in private deployments.
- Fresh consumer-authority snapshots and consumer-isolated private keys are
  required at compile, activation, and recovery boundaries.
- Only the Promotion Coordinator writes target desired state. Hosts append
  technical observations; a separate consumer capability verifier returns
  signed allowed/denied evidence.
- Recovery creates a new forward revision from eligible historical functional
  content plus current tooling, policy, approval, authority, and canary evidence.
- Release and receipt digests reproduce byte-identical content.
- The CLI exposes explicit package/build, publish, pull, inspect, and verify
  commands as well as control-plane operations.
- AD-18 proves the operational SLO, scale, limits, retention, backup/restore,
  regional failover, observability, security response, upgrade, on-call, and
  support requirements.

## Reference-catalog entry checklist

- AD-02 starts only after AD-01.
- AD-03 starts after AD-02 and AD-04 so catalog preparation can run in parallel
  with later core work.
- REFERENCE-CATALOG-CERT waits for CORE-CERT and certifies AD-02/AD-03 output
  against the released core; it is not evidence for core.

## Reference-consumer entry checklist

- CORE-CERT is released and pinned; ByteDesk certification additionally pins
  REFERENCE-CATALOG-CERT.
- The consumer has an approved Adapter design and its own identity/grant
  security foundation.
- Consumer integration work uses separate issues and branches in the consumer
  repository.
- There is one activation writer and an explicit direct-cutover plan.
- Capability tests use a consumer-owned verifier identity; the host never
  receives agent capability credentials.
