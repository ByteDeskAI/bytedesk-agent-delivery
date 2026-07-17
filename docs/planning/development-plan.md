# Development plan

## Objective

Deliver a standalone, open, harness-neutral Agent Spec and OCI supply chain that
a clean third party can run without ByteDesk Platform. Only after the core
product passes its conformance gate do ByteDesk Platform, Hermes, and OpenClaw
integration work begin.

## Definition of core completion

A clean consumer can:

1. clone a definition-only catalog at an exact commit;
2. validate Agent Spec packages and the non-authorizing binding profile;
3. render deterministically for native Agent Spec, Hermes, and OpenClaw;
4. build, sign, publish, pull, and verify source/render artifacts by OCI digest;
5. create a digest-pinned installation without creating runtime authority;
6. compile a private consumer deployment from opaque current-policy inputs;
7. reconcile it into a reference runtime target with canary and forward
   rollback;
8. inspect append-only receipts and reproduce the exact active content; and
9. exercise all of this through stable API and CLI contracts.

The core is not complete if it requires ByteDesk Platform identity, Office,
MCP, Hermes Kanban, or a ByteDesk tenant to perform the public workflow.

## Delivery tranches

### Tranche 1 — Contracts and portable catalog

- **AD-01:** accept architecture, authority boundary, threat model, and plan.
- **AD-02:** bootstrap the independent definition-only marketplace repository
  and catalog contract.
- **AD-03:** migrate the 34 selectable ByteDesk reference agents plus the
  non-selectable `office-orchestrator` package.
- **AD-04:** implement the renderer contract and native Agent Spec output.

### Tranche 2 — Harness rendering and OCI

- **AD-05:** implement the deterministic Hermes Adapter.
- **AD-06:** implement the deterministic OpenClaw Adapter.
- **AD-07:** implement deterministic OCI source and render packaging.
- **AD-08:** implement purpose-separated signing, provenance, SBOM, trust, and
  registry conformance.

### Tranche 3 — Independent control plane

- **AD-09:** implement consumer-neutral installation, binding, deployment, and
  observation records.
- **AD-10:** expose catalog, inspect, renderer, validation, render, verify, and
  import APIs.
- **AD-11:** implement digest-pinned Git desired-state and scheduled/event
  reconciliation through generic repository ports.
- **AD-12:** implement compatibility evaluation, update proposals, promotion,
  skill quarantine, and forward rollback policy.
- **AD-13:** compile private consumer deployment artifacts and release
  manifests from opaque current-authority inputs.
- **AD-14:** implement the target-scoped host protocol and reference runtime
  reconciler.
- **AD-15:** deliver the public/authenticated CLI and headless automation
  contract.

### Core conformance gate

The core track of **AD-18** runs after AD-01 through AD-15. It executes the
third-party, deterministic-build, supply-chain, authorization-separation,
registry, failure-injection, recovery, API, and CLI matrix. The machine-readable
plan names this milestone `CORE-CERT`. A versioned standalone release is cut
only when this gate passes.

### Tranche 4 — Reference-consumer integrations (deferred until core release)

- **AD-16:** integrate ByteDesk hosted Hermes and cut its definition source to
  released Agent Delivery artifacts without changing Hermes Kanban work
  authority.
- **AD-17:** integrate OpenClaw and cut its definition source to released Agent
  Delivery artifacts while leaving tools/MCP/providers consumer-owned.
- **AD-18 reference appendices:** extend the already completed core
  certification with the ByteDesk reference-consumer flow, including workload
  login and grant-governed MCP positive and negative tests.

This tranche is deliberately not part of standalone-product completion. It is
preserved here so the integration can be planned without moving the product
back into Platform.

## Execution rules

- One task is one independently reviewable branch/PR and one runnable goal.
- A dependent task does not begin until its prerequisite contract is landed.
- Public contracts are versioned before the first external artifact is
  published.
- Use TDD and denial fixtures before implementation for every trust boundary.
- No production registry, KMS, runtime, or consuming-platform mutation is part
  of these tasks without separate authorization.
- Core code lives here. Catalog content lives in a definition-only Git
  repository. Consumer Adapters live in their consumer repositories where
  practical.
- Cross-repository work pins a released contract; it does not copy unversioned
  product internals.

## Cross-cutting acceptance gates

Every relevant task supplies:

- exact input and output schemas;
- deterministic serialization/build evidence;
- positive, negative, and malformed-input tests;
- idempotency, retry, terminal-state, and cancellation behavior;
- redaction and tenant/privacy evidence;
- upgrade, downgrade, withdrawal, and revocation behavior;
- observability and append-only receipt fields; and
- operator documentation and reproducible commands.

## Historical traceability

The AD identifiers retain their original Jira mapping from the transferred
ByteDesk Platform epic BDP-3301. Those Jira issues are historical planning
records, not the active product backlog. The full adapted specifications are in
[`tasks/`](tasks/).
