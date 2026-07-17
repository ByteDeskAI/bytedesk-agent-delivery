# Detailed task breakdown

Each linked task is a self-contained implementation contract with outcome,
inputs, required work, outputs, acceptance criteria, verification, exclusions,
dependencies, and security amendments.

| ID | Historical Jira | Workstream | Product phase |
|---|---|---|---|
| [AD-01](tasks/AD-01-architecture.md) | BDP-3302 | Architecture and contracts | Core |
| [AD-02](tasks/AD-02-marketplace-bootstrap.md) | BDP-3304 | Definition-only marketplace bootstrap | Core |
| [AD-03](tasks/AD-03-baseline-catalog.md) | BDP-3306 | Baseline catalog | Core |
| [AD-04](tasks/AD-04-renderer-contract.md) | BDP-3307 | Renderer contract/native output | Core |
| [AD-05](tasks/AD-05-hermes-renderer.md) | BDP-3303 | Hermes Adapter | Core |
| [AD-06](tasks/AD-06-openclaw-renderer.md) | BDP-3305 | OpenClaw Adapter | Core |
| [AD-07](tasks/AD-07-oci-packaging.md) | BDP-3308 | OCI packaging | Core |
| [AD-08](tasks/AD-08-signing-and-attestations.md) | BDP-3309 | Signing, provenance, and trust | Core |
| [AD-09](tasks/AD-09-bindings-and-receipts.md) | BDP-3310 | Consumer-neutral installations and receipts | Core |
| [AD-10](tasks/AD-10-control-plane-api.md) | BDP-3311 | Catalog/import API | Core |
| [AD-11](tasks/AD-11-git-desired-state.md) | BDP-3312 | Git desired-state reconciliation | Core |
| [AD-12](tasks/AD-12-update-promotion.md) | BDP-3313 | Compatible updates and promotion | Core |
| [AD-13](tasks/AD-13-private-deployment-compiler.md) | BDP-3314 | Private deployment compiler | Core |
| [AD-14](tasks/AD-14-runtime-reconciler.md) | BDP-3315 | Host protocol/reference reconciler | Core |
| [AD-15](tasks/AD-15-cli.md) | BDP-3316 | CLI and headless automation | Core |
| [AD-16](tasks/AD-16-bytedesk-hermes-cutover.md) | BDP-3317 | ByteDesk hosted Hermes integration | Deferred integration |
| [AD-17](tasks/AD-17-bytedesk-openclaw-cutover.md) | BDP-3318 | OpenClaw integration | Deferred integration |
| [AD-18](tasks/AD-18-certification.md) | BDP-3319 | Core and reference-consumer certification | Core gate plus deferred appendix |

## Core completion checklist

- AD-01 through AD-15 are landed.
- CORE-CERT evidence is reproducible from a clean environment.
- Public schema/media-type/trust contracts are versioned and frozen.
- A third party needs no ByteDesk Platform account or service for the public
  workflow.
- No portable package can create or demand MCP, provider, identity, role,
  resource, credential, or tenant authority.
- Release and receipt digests reproduce byte-identical content.

## Integration entry checklist

- A standalone version is released and pinned.
- The consumer has an approved Adapter design and its own identity/grant
  security foundation.
- Consumer integration work uses separate issues and branches in the consumer
  repository.
- There is one activation writer and an explicit direct-cutover plan.
