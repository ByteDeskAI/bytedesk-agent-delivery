# Implementation-readiness execution plan

**Branch:** `agent/contracts-frozen-readiness`

**Execution rule:** The tasks below are sequential. A task is complete only when
every acceptance criterion has objective evidence, the relevant verification
suite passes, and its commit is pushed. Work on the next task does not begin
before that point.

## Task 1 — Land the accepted architecture baseline

The canonical decision sources for this task are the
[architecture resolution register](../architecture/decision-register.md) and
[ADR-0001](../architecture/adr/0001-independent-agent-delivery-control-plane.md).

### Acceptance criteria

- [x] The architecture resolution register records all ten accepted decisions
  and every related ambiguity closed during review.
- [x] ADR-0001, architecture, product, standards, integration, Confluence, and
  planning documents express the same public/private, authority, signing,
  desired-state, canary, forward-recovery, core/reference, and operational
  boundaries without a known contradiction.
- [x] The legacy rollback page is replaced by the forward-recovery page and no
  active local link references the deleted name.
- [x] Every Markdown local link resolves; every fenced JSON/YAML example parses;
  every structured example SHA-256 value is valid; every repository JSON file
  parses; and the 18-task/7-milestone planning DAG is complete and acyclic.
- [x] `git diff --check` passes and a focused peer audit reports no remaining
  architecture-resolution defect.
- [ ] The complete baseline is committed as one intentional commit and pushed
  to the task branch.

### Evidence

- 64 Markdown files and 307 active local links validated.
- 24 fenced blocks balanced; all structured JSON/YAML examples parsed; 24
  structured SHA-256 examples validated.
- The repository JSON parsed and the 18-task/7-milestone, 25-node combined DAG
  was complete, referentially valid, and acyclic.
- No legacy rollback-page reference or stale issue marker remained.
- Three focused read-only re-audits reported clean after resolving OpenClaw
  migration ownership, Capability Verifier dispatch, Native Agent Spec/WayFlow
  scope, candidate/rollout cancellation, and documentation navigation.
- `git diff --check` passed. Commit and push evidence is recorded after the
  baseline reaches the remote branch.

## Task 2 — Freeze the implementation stack and reference topology

### Acceptance criteria

- [ ] A new accepted ADR fixes the primary implementation language/runtime,
  dependency/build/release toolchain, module boundaries, and supported platform
  matrix without weakening the harness-neutral public contracts.
- [ ] The ADR fixes one production-capable reference topology for relational
  state, durable work, transactional outbox/inbox, object/OCI storage, renderer
  isolation, API/worker deployment, high availability, backup, and disaster
  recovery while preserving Adapter alternatives.
- [ ] The ADR fixes concrete reference profiles for sandboxing, identity between
  components, configuration/secrets, observability, migrations, and local
  development.
- [ ] Every affected architecture, operations, contribution, and task document
  points to the ADR and contains no contradictory implementation guidance.
- [ ] ADR/document validation and `git diff --check` pass, the decision is
  independently reviewed, and the task commit is pushed.

### Evidence

Pending.

## Task 3 — Complete AD-01 and emit executable contracts

### Acceptance criteria

- [ ] Source-controlled JSON Schema Draft 2020-12 files exist for every Agent
  Delivery-owned authoritative object, with stable IDs, closed authority
  boundaries, offline reference closure, and exact canonical digests.
- [ ] Restricted-YAML-to-JSON parsing and RFC 8785 canonicalization have a
  runnable reference implementation plus positive, negative, boundary,
  malicious-input, Unicode, numeric, and parser-differential fixtures.
- [ ] Strict functional JSON, file, and skill operation profiles and all
  lifecycle state machines have executable positive/negative fixtures and
  exhaustive legal/illegal transition verification.
- [ ] OpenAPI 3.2 and AsyncAPI 3.1/CloudEvents documents reference the normative
  schemas rather than copying independent field models and pass lint/closure
  validation.
- [ ] A deterministic offline contract bundle contains schemas, references,
  fixtures, API/event contracts, compatibility metadata, and documentation
  mappings; clean rebuilds are byte-identical and its manifest is identified by
  RFC 8785 SHA-256.
- [ ] Bundle signing and verification are runnable without repository secrets:
  tests use ephemeral non-exported keys, and the release workflow accepts only
  an external/KMS or workload-identity signer.
- [ ] Two independent Draft 2020-12 validators agree on every schema fixture;
  generated projections/examples/docs pass drift checks; unknown schemas,
  fields, references, operations, and illegal transitions fail closed.
- [ ] `development-plan.json` is explicitly repository-internal planning data,
  validated by a repository schema and drift checks, and no longer claims to be
  a released consumer product contract.
- [ ] The complete AD-01 verification command passes from a clean checkout,
  machine-readable evidence is archived, `CONTRACTS-FROZEN` is justified by that
  evidence, and the task commit is pushed.

### Evidence

Pending.

## Task 4 — Freeze downstream ports and conformance contracts

### Acceptance criteria

- [ ] Every externally visible port used by AD-02 through AD-18 has a versioned
  request/result or artifact contract, stable errors, failure semantics,
  security boundary, compatibility rule, and conformance-test ownership.
- [ ] Coverage includes catalog/SCM, Agent Spec validation, renderer Strategy and
  native/Hermes/OpenClaw Adapters, OCI registry, KMS/signing, consumer authority
  and approval, DesiredStateStore, API/events, Promotion Coordinator, private
  compiler, Host Reconciler, Capability Verifier, and CLI automation.
- [ ] Exact renderer capability/output contracts, OCI config/layer/archive
  layout, signing/SBOM/provenance/scanning profiles, durable-action/problem/event
  catalogs, desired-state watch/CAS semantics, and host/capability evidence
  protocols are frozen and represented in contract fixtures where applicable.
- [ ] The native Agent Spec versus WayFlow scope, OpenClaw migration-map owner,
  Capability Verifier trigger owner, Coordinator crash/fencing order, and
  reference host switching/journal behavior are unambiguous.
- [ ] Each AD task identifies its normative contracts and executable conformance
  suite; no task relies on an unpinned "current" external implementation as
  authority.
- [ ] The downstream contract coverage matrix has no missing required port,
  schema, error family, lifecycle, security boundary, or verification owner.
- [ ] Full repository validation, all contract/conformance tests, and focused
  independent audits pass; the task commit is pushed.

### Evidence

Pending.

## Completion condition

The objective is complete only when all four task sections are fully checked,
all evidence is current, every task commit is present on the remote branch, and
the resulting pull request reports the complete verification commands and
results.
