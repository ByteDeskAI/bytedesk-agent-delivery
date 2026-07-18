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
- [x] The complete baseline is committed as one intentional commit and pushed
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
- `git diff --check` passed.
- Baseline commit `ea9bb1e` (`docs: freeze agent delivery architecture`) was
  pushed to `origin/agent/contracts-frozen-readiness`.

## Task 2 — Freeze the implementation stack and reference topology

### Acceptance criteria

- [x] A new accepted ADR fixes the primary implementation language/runtime,
  dependency/build/release toolchain, module boundaries, and supported platform
  matrix without weakening the harness-neutral public contracts.
- [x] The ADR fixes one production-capable reference topology for relational
  state, durable work, transactional outbox/inbox, object/OCI storage, renderer
  isolation, API/worker deployment, high availability, backup, and disaster
  recovery while preserving Adapter alternatives.
- [x] The ADR fixes concrete reference profiles for sandboxing, identity between
  components, configuration/secrets, observability, migrations, and local
  development.
- [x] Every affected architecture, operations, contribution, and task document
  points to the ADR and contains no contradictory implementation guidance.
- [x] ADR/document validation and `git diff --check` pass, the decision is
  independently reviewed, and the task commit is pushed.

### Evidence

- Accepted [ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
  fixes the Go/Python implementation boundary, monorepo/module shape, locked
  trusted-builder/SLSA v1 release profile, supported platform matrix,
  PostgreSQL transaction/action/outbox authority, dual-region Harbor/S3 and
  evidence archive, KMS/SPIFFE identity, Kubernetes deployment, gVisor renderer
  isolation, configuration/secrets, OpenTelemetry, migrations, local Compose,
  and fenced regional recovery.
- All 52 affected tracked architecture, standards, operations, integration,
  contribution, and AD task documents were aligned to the ADR; together with
  ADR-0002, the content commit covered 53 paths. Focused contradiction scans
  found no conflicting language/runtime, Agent Spec/WayFlow, persistence/queue,
  Harbor/Distribution, Kubernetes support-target, sandbox, or Adapter guidance.
- Independent architecture, authority-boundary, supply-chain, Harbor, SLSA,
  SPIRE/KMS, and renderer-isolation reviews accepted the final profile. Review
  findings about legacy SLSA v0.2 dependencies and the Harbor consumer token
  realm were resolved with a SHA-pinned `actions/attest` SLSA v1 trusted builder
  and separate region-pinned publisher versus fenced consumer-auth routes.
- Validation covered 65 Markdown files, 362 local links, 54 fence markers, all
  structured fences and repository JSON, 42 SHA-256 tokens, and the complete
  acyclic 18-task/7-milestone (25-node) planning graph with zero errors.
  `git diff --check` and the untracked-ADR no-index whitespace check passed
  before commit.
- Content commit `d174300` (`docs: freeze implementation reference topology`)
  was pushed to `origin/agent/contracts-frozen-readiness`; local and remote
  commit IDs matched exactly after the push.

## Task 3 — Complete AD-01 and emit executable contracts

### Acceptance criteria

- [x] Source-controlled JSON Schema Draft 2020-12 files exist for every Agent
  Delivery-owned authoritative object, with stable IDs, closed authority
  boundaries, offline reference closure, and exact canonical digests.
- [x] Restricted-YAML-to-JSON parsing and RFC 8785 canonicalization have a
  runnable reference implementation plus positive, negative, boundary,
  malicious-input, Unicode, numeric, and parser-differential fixtures.
- [x] Strict functional JSON, file, and skill operation profiles and all
  lifecycle state machines have executable positive/negative fixtures and
  exhaustive legal/illegal transition verification.
- [x] OpenAPI 3.2 and AsyncAPI 3.1/CloudEvents documents reference the normative
  schemas rather than copying independent field models and pass lint/closure
  validation.
- [x] A deterministic offline contract bundle contains schemas, references,
  fixtures, API/event contracts, compatibility metadata, and documentation
  mappings; clean rebuilds are byte-identical and its manifest is identified by
  RFC 8785 SHA-256.
- [x] Bundle signing and verification are runnable without repository secrets:
  tests use ephemeral non-exported keys, and the contract release workflow
  accepts only its exact `contract-bundle-release-v1` Sigstore keyless workload
  identity under an independently pinned contract-bundle policy.
- [x] Two independent Draft 2020-12 validators agree on every schema fixture;
  generated projections/examples/docs pass drift checks; unknown schemas,
  fields, references, operations, and illegal transitions fail closed.
- [x] `development-plan.json` is explicitly repository-internal planning data,
  validated by a repository schema and drift checks, and no longer claims to be
  a released consumer product contract.
- [x] The complete AD-01 verification command passes from a clean checkout,
  machine-readable evidence is archived, `CONTRACTS-FROZEN` is justified by that
  evidence, and the task commit is pushed.

### Evidence

- The closed source inventory contains 49 product JSON Schemas and 136 indexed
  positive, denial, malicious-input, and boundary fixtures. Go and Python Draft
  2020-12 validators agreed on every result and denial proof. The canonical
  schema-inventory digest is
  `sha256:f73ec940f9d247c2a8de4f155eb8051de773a7f7f28793a354eb2c295e79e5ef`.
- The Go reference implementation passed race-enabled unit tests, 22 strict-JSON
  resource cases, 45 operation/source/rebase fixtures, and exhaustive checks of
  73 states and 86 transitions across seven lifecycle models. Seven live fuzz
  campaigns completed 3,101,157 executions without a failing corpus, including
  Unicode/pointer, operation-order, array, changed-target rebase, file-collision,
  skill-conflict, invalid-UTF-8, and custom-serializer execution boundaries.
- The exact `pyagentspec==26.1.2` wheel is locked by SHA-256
  `26b65d5afc440d904877ffa68efbbedd028339314e4d1120922a0267e4051449`.
  Eleven official-SDK source-resolution cases ran offline with socket creation
  denied; local exact-version, inline-source, and authority restrictions were
  applied after exactly one official validation call where required.
- Pinned official OpenAPI 3.2 and AsyncAPI 3.1 validators accepted the
  projections. The topology/drift suite passed all 44 cases; bundle-source and
  documentation-map closure passed all 59 cases; and offline schema authority
  passed all 17 cases.
- Two clean builds produced byte-identical 1,228,800-byte, 257-entry bundles
  containing 49 schemas and 204 other documents. The bundle digest is
  `sha256:39a289fda8189fd8ce8747459efe047e6ea9da6a1b5579477fa21babed3e5740`;
  its 62,366-byte RFC 8785 manifest digest is
  `sha256:00ef23c1421b100243de74adf01a2b8f13c717f81f984ec90e07054729c5e56b`.
- Ephemeral in-memory test signing, external-verifier isolation, 25 signing-
  binding cases, 33 supply-chain cases, replay/tamper/trailing-byte and
  repository-only-member denials all passed without issuing authority. The
  production caller delegates only to the sealed external/workload-identity
  signer workflow pinned at reviewed content commit
  `bc5257b9ec44e572fd75bf02bb7c40de52aa6d85`; 17 workflow-boundary cases prove
  the activated pin, full-history availability, minimum permissions, hermetic
  verifier phases, exact source rebuild, and denial mutations. Production use
  remains gated by an immutable release tag, protected environment, and
  independently configured digest-pinned verifier, trust policy, and signer.
- Repository validation covered 69 Markdown files, 366 local links, four
  structured fences, two validated contract examples, three YAML files, 220
  JSON files, 12 SHA-pinned workflow actions, and the complete acyclic
  18-task/7-milestone plan. Repository-only plan fixtures were validated and
  excluded from the 204-document product bundle.
- Content commit `bc5257b9ec44e572fd75bf02bb7c40de52aa6d85` and signer-activation commit
  `0fc2c5f199a567e71d41b820e7d2031af416ebf4` were pushed to
  `origin/agent/contracts-frozen-readiness`. A detached clean checkout at the
  activation commit passed `make verify` with no tracked changes.
- GitHub Actions [contracts run 29586713741](https://github.com/ByteDeskAI/bytedesk-agent-delivery/actions/runs/29586713741)
  passed the exact activation commit and archived artifact
  `contract-verification-0fc2c5f199a567e71d41b820e7d2031af416ebf4` with artifact
  digest
  `sha256:4ca1daab97d74867f1a2df1895ac6fcdcf1fe98a8f7dd27d7303c3d8834c66d8`.
  Focused contract, official-validator, operation/fuzz, supply-chain, and
  landing audits reported no remaining Task 3 correctness blocker.

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

> **Evidence invalidated during final audit hardening (2026-07-17).** The
> numerical snapshot below describes commit `2d03ae0` only. It is not current
> Task 4 acceptance evidence and must not be used to claim completion. The
> active source change adds trust-policy provider, Merkle status, stage-specific
> eligibility, finalizer/publication, private-compilation, activation, KMS, and
> OCI-closure contracts. This section and every checkbox above will be refreshed
> from the final generated fixed point and clean detached verification before
> Task 4 is accepted.

- The closed downstream registry contains 21 versioned ports and 76 operations.
  Its generated type authority contains 85 reusable base types, 511 unique
  field-value schemas, 93 semantic field refinements, 152 closed request/result
  contracts, and 152 valid contract fixture groups. The denial corpus contains
  456 structural mutations and 11 operation-semantic mutations.
- Every AD-02 through AD-18 task cites its exact normative schemas, port
  operations, protocol profiles, and executable task suite. The mechanically
  checked coverage matrix cites every registry contract path, request/result
  contract ID, promised schema ID, and applicable profile; deleting any one
  required authority token is rejected by the generic coverage mutation.
- The compiled adapter conformance plan binds nine exact machine-authority
  inputs by digest, 76 operation goldens, and all 108 cases into 187
  deterministic steps. It executes all 152 valid contract fixtures and 467
  adversarial mutations. Its RFC 8785 digest is
  `sha256:178a7eb0982e867561f35183795c3472858cedf3a4335f7f3bb6e6a510b2552b`.
- The protocol corpus covers 49 frozen protocol documents and 11 independent
  materials with 71 denial mutations. Exact renderer preimage validation passes
  three public/private renderer chains, one selection-to-execution receipt
  binding, and one two-platform functional-output equivalence case while
  rejecting 19 digest, exposure, allowlist, compatibility, and fallback
  substitutions.
- The source inventory contains 75 product schemas and 216 indexed fixtures.
  Deterministic metadata refresh manages 153 files with zero drift while
  preserving two intentional semantic denials. The Go and Python Draft 2020-12
  validators agree on every fixture; both enforce bounded schema resources.
- Final repository-wide and detached-checkout verification, including the exact
  content-commit bundle and manifest identities, will be recorded after the
  content commit exists so the evidence names an immutable source revision.
- Release-evidence conformance passes one exact baseline and 20 independent
  denial cases without authenticating the test attestation or issuing
  authority. Repository verification covers 71 Markdown files, 576 local
  links, three YAML files, 328 JSON files, and the complete acyclic
  18-task/7-milestone planning graph.
- Full-gate integration found and closed an authorization-proof binding defect:
  a schema-required `candidateDigest` was not compared with the canary plan.
  A red substitution test proved the gap, the verifier now binds the field, and
  the complete canary and repository suites pass.
- Focused independent audit, content commit, remote push, detached-checkout
  verification, pull-request reporting, and GitHub Actions evidence remain
  required before the final acceptance item is checked.

## Completion condition

The objective is complete only when all four task sections are fully checked,
all evidence is current, every task commit is present on the remote branch, and
the resulting pull request reports the complete verification commands and
results.
