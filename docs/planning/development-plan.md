# Development plan

The accepted architecture decisions are summarized in the
[architecture resolution register](../architecture/decision-register.md), with
normative architecture and standards linked from the
[documentation index](../README.md). The sequential evidence gates for the
current implementation-readiness work are maintained in the
[implementation-readiness execution plan](implementation-readiness-execution.md).

## Bootstrap contract status

[`development-plan.json`](development-plan.json) is the authoritative planning
projection, but `bytedesk.agent-delivery.plan/2` is currently a bootstrap
format rather than a released product contract. Its
`contractStatus: bootstrap-pre-contract` marker means consumers MUST NOT treat
the file as a validated runtime, API, artifact, or release object. AD-01 must
publish the closed Draft 2020-12 plan schema, positive and denial fixtures, and
Markdown/JSON drift validation in the signed offline contract bundle, then
replace the marker with the released exact schema ID and digest before
`CONTRACTS-FROZEN`. If the plan is not retained as a product contract, AD-01
must instead remove the schema claim and keep it explicitly informational.

## Objective

Deliver a standalone, open, harness-neutral Agent Spec and OCI supply chain that
a clean third party can run without ByteDesk Platform. Native Agent Spec,
Hermes, and OpenClaw renderer products are core. The ByteDesk 34+1 catalog and
ByteDesk consumer cutovers are separate reference tracks and cannot block the
standalone release.

## Definition of core completion

A clean consumer can:

1. resolve the signed offline schema bundle and validate a generic
   definition-only fixture catalog at an exact commit;
2. validate Agent Spec packages and apply the strict functional, file, and skill
   operation profiles without creating authority;
3. select an exact signed renderer release and render deterministically with the
   native Agent Spec, Hermes, and OpenClaw renderer products;
4. build, sign, package, publish, pull, and verify source/render artifacts by
   exact OCI digest;
5. create a digest-pinned installation using absent/match revision-and-digest
   preconditions;
6. compile a private deployment from a fresh signed consumer-authority snapshot
   and consumer-isolated private signing key;
7. advance one target through the sole Promotion Coordinator, while the
   target-scoped host only reads desired state and appends technical evidence;
8. obtain separate signed capability evidence from the consumer capability
   verifier, promote, and exercise current-tooling forward recovery;
9. inspect append-only receipts and reproduce exact active content; and
10. exercise the complete local and service workflow through stable API, event,
    and CLI contracts, including explicit package and publish commands.

Public catalog renders are tenant-free compatibility artifacts. A consumer may
apply a deterministic private functional-customization delta that changes any
functional Agent Spec property, adds/replaces/removes arbitrary regular files,
and selects exact public/private skills. The private compiler fully rerenders the
effective agent and embeds that render in the private deployment. It never
post-patches a public render or publishes consumer customization publicly.

Human authors may use restricted YAML, but every authoritative contract object
is the validated JSON data model serialized as RFC 8785 JCS before hashing or
signing. YAML contract input is limited to the YAML 1.2 JSON-compatible subset;
duplicate keys, aliases, custom tags, non-string keys, and non-finite numbers
fail closed. Original YAML is retained only as provenance. Arbitrary payload
files and binaries retain their exact bytes.

The core is not complete if it requires ByteDesk Platform identity, Office,
MCP, Hermes Kanban, a ByteDesk tenant, the ByteDesk marketplace repository, or
the ByteDesk 34+1 catalog to perform either the public workflow or generic
consumer certification.

## Product-grade milestone DAG

### CONTRACTS-FROZEN

AD-01 freezes the normative JSON Schema Draft 2020-12 sources and signed offline
contract bundle, RFC 8785 and restricted-YAML encoding, strict JSON/file/skill
operations, Agent/Portable SpecializedAgent resolution, renderer-release
identity, consumer authority/private signing, trust, lifecycle, OpenAPI,
AsyncAPI/CloudEvents, and operational-readiness contracts. Later tasks implement
those contracts and may not invent incompatible shapes.

### SUPPLY-CHAIN-CERT

- **AD-04:** implement the renderer contract, signed renderer-release identity,
  compiled allowlist, sandbox, and native Agent Spec renderer product.
- **AD-05:** implement the deterministic Hermes Adapter.
- **AD-06:** implement the deterministic OpenClaw Adapter.
- **AD-07:** implement deterministic OCI source and render packaging.
- **AD-08:** implement purpose-separated signing, provenance, SBOM, trust, and
  public/consumer-private key topology.

This milestone proves all three renderer products using generic conformance
fixtures. It does not wait for the ByteDesk catalog.

### CONTROL-PLANE-CERT

- **AD-09:** implement consumer-neutral installation, binding, deployment, and
  observation records, exact consumer-authority evidence, and separate
  installation/candidate/target/host state contracts.
- **AD-10:** expose the normative API, asynchronous actions, generated schemas,
  and CloudEvents/AsyncAPI notification contract.
- **AD-11:** reconcile digest-pinned Git installation/binding intent through
  generic repository ports. Git is never runtime desired-state authority.
- **AD-12:** implement compatibility evaluation, update proposals, the sole
  Promotion Coordinator, skill quarantine, canary challenges, and forward
  recovery planning.
- **AD-13:** compile private consumer deployment artifacts and release
  manifests containing a fully rerendered effective agent from private
  customization, approved skills, fresh consumer authority, and exact
  consumer-isolated signing policy.

### RUNTIME-CERT

- **AD-14:** implement the target-scoped host protocol and reference runtime
  reconciler plus the separate consumer capability-verifier Adapter.
- **AD-15:** deliver the public/authenticated CLI and headless automation
  contract, including local package/build/publish/verify commands.

### CORE-CERT / standalone GA

The core track of **AD-18** runs after AD-01 and AD-04 through AD-15. It executes
the generic third-party, deterministic-build, supply-chain,
authorization-separation, registry, failure-injection, forward-recovery,
API/event, reconciler, and CLI matrix. It also archives measured SLO, latency,
capacity, soak, chaos, dependency-outage, retention, backup/restore/failover,
upgrade, audit/redaction, security-response, runbook, on-call, support, and
thirty-day production-equivalent evidence required by
`bytedesk.operational-readiness/1`. A signed readiness report is the
`CORE-CERT` and standalone-GA decision.

### REFERENCE-CATALOG-CERT

- **AD-02:** bootstrap the independent definition-only ByteDesk marketplace
  against the frozen contract. It may proceed after AD-01.
- **AD-03:** after AD-02 and AD-04, prepare the 34 selectable ByteDesk agents
  plus non-selectable `office-orchestrator` using the frozen contracts and
  native validator. Publication preparation may run in parallel with later core
  work; `REFERENCE-CATALOG-CERT` waits for `CORE-CERT` and certifies the
  catalog against the released core.

### REFERENCE-CONSUMER-CERT

- **AD-16:** after `CORE-CERT`, integrate ByteDesk hosted Hermes without
  changing Hermes Kanban or Platform authorization authority.
- **AD-17:** after `CORE-CERT`, integrate ByteDesk OpenClaw while leaving
  tools, MCP, providers, credentials, identity, and approval consumer-owned.

The ByteDesk certification requires `REFERENCE-CATALOG-CERT` because those
cutovers select the ByteDesk catalog. Another consumer can certify against its
own compatible catalog. Neither reference milestone can change the standalone
GA result.

## Execution rules

- One task is one independently reviewable branch/PR and one runnable goal.
- A dependent task does not begin until its prerequisite contract is landed.
- Public contracts are versioned before the first external artifact is
  published.
- Every authoritative object resolves its exact schema ID and digest from the
  signed offline contract bundle; generated code, OpenAPI, AsyncAPI, examples,
  and docs pass drift checks.
- Use TDD and denial fixtures before implementation for every trust boundary.
- No production registry, KMS, runtime, or consuming-platform mutation is part
  of these tasks without separate authorization.
- Core code lives here. Catalog content lives in a definition-only Git
  repository. Consumer Adapters live in their consumer repositories where
  practical.
- Cross-repository work pins a released contract; it does not copy unversioned
  product internals.
- Git, compilers, hosts, observations, and capability verifiers submit intent or
  evidence; only the Promotion Coordinator writes `TargetDeliveryState`.

## Cross-cutting acceptance gates

Every relevant task supplies:

- exact input and output schemas;
- schema-bundle, offline-resolution, two-validator, generated-code, OpenAPI,
  AsyncAPI, and documentation drift evidence;
- deterministic serialization/build evidence;
- YAML-to-JSON-data-model equivalence and RFC 8785 JCS digest/signature evidence;
- public-render privacy plus deterministic private-customization and effective-
  render evidence;
- positive, negative, and malformed-input tests;
- idempotency, retry, terminal-state, and cancellation behavior;
- absent/match revision-plus-digest preconditions, sole-writer desired state,
  and legal/illegal transition evidence;
- exact renderer-release manifest, executed distribution, compiled allowlist,
  sandbox, and withdrawal identity;
- fresh signed consumer authority, per-consumer private keys, exact skill
  approval, and separate technical/capability canary evidence;
- newest-first forward recovery using current trusted tooling and authority;
- redaction and tenant/privacy evidence;
- upgrade, downgrade, withdrawal, and revocation behavior;
- observability and append-only receipt fields; and
- OpenTelemetry observability, resource-limit, SLO/scale/DR/upgrade evidence
  proportional to the task; and
- operator documentation and reproducible commands.

## Historical traceability

The AD identifiers retain their original Jira mapping from the transferred
ByteDesk Platform epic BDP-3301. Those Jira issues are historical planning
records, not the active product backlog. The full adapted specifications are in
[`tasks/`](tasks/).
