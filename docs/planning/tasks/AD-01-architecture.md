# AD-01: Accept the Agent Spec and OCI delivery architecture

- Historical Jira: [BDP-3302](https://bytedesk.atlassian.net/browse/BDP-3302)
- Delivery role: Core product
- Release gate: Emits `CONTRACTS-FROZEN`

## Outcome

Freeze the complete machine-readable, security, lifecycle, integration, and
operational contract set needed to implement ByteDesk Agent Delivery without
inventing authority or state semantics later.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- The decisions extracted from historical epic BDP-3301.
- Agent Spec 26.1.2 language, schema, and official validator.
- OCI Image and Distribution 1.1 subject/referrer behavior, ORAS artifact conventions, registry capabilities, purpose-specific Cosign KMS and Sigstore keyless signing, and in-toto attestations.
- The [architecture package](../../README.md) in this repository, including
  [ADR-0001](../../architecture/adr/0001-independent-agent-delivery-control-plane.md),
  the [decision register](../../architecture/decision-register.md), consumer
  integration contract, OCI artifact model, runtime reconciliation, and
  security/trust documents.
- Canonical encoding, machine contracts, renderer identity, consumer authority
  and private signing, delivery lifecycle, and operational-readiness v1
  profiles.
- Historical ByteDesk Platform ADR-0174, ADR-0180, ADR-0182, and ADR-0187 as reference-consumer context only.
- Current Hermes and OpenClaw definitions and delivery behavior as migration evidence, not as Agent Delivery source code or authority.

## Required work

1. Accept ADR-0001 with explicit product and consumer ownership boundaries, artifact graph and media types, public-render/private-effective-render rules, deterministic functional-customization rules, trust policy, promotion state machine, forward recovery, retention, and supersession language.
2. Add C4 views for authoring, publication, import, private functional customization, compilation, reconciliation, activation, and forward recovery.
3. Complete the documentation hierarchy covering overview, schema, catalog, adapters, OCI graph, supply-chain trust, product data/API ownership, consumer Git, promotion, hosted deployment, CLI, migration/cutover, and test/operations.
4. Maintain runnable task specifications and a dependency manifest for AD-01 through AD-18.
5. Record threats and fail-closed behavior for digest substitution, signer compromise, replay, cross-consumer binding, malicious customization deltas, downgrade, missing referrers, stale receipts, registry outage, and webhook duplication.
6. Define the integration seam through which a consuming platform supplies identity, roles, MCP/tool/resource grants, provider connections, credentials, workload authentication, and business approvals. Agent Delivery must not become the authority for any of them.
7. Define the canonical encoding boundary: restricted YAML 1.2 JSON-compatible authoring input, authoritative JSON data-model objects serialized with RFC 8785 JCS before hashing/signing, provenance-only original YAML, and byte-exact arbitrary payload files.
8. Create authoritative JSON Schema Draft 2020-12 sources for every
   Agent Delivery-owned object; close authority boundaries, resolve all
   references offline, and package schemas, fixtures, OpenAPI, AsyncAPI,
   compatibility metadata, and documentation mappings as one signed,
   content-addressed contract bundle. The machine-readable development plan is
   instead validated by a repository-only schema and drift checks, remains
   explicitly non-product planning data, and is excluded from that bundle.
9. Freeze `bytedesk.json-patch/1`, file-operation, and skill-operation
   semantics; Agent versus portable `SpecializedAgent` resolution; and
   absent/match revision-plus-digest preconditions.
10. Freeze exact renderer-release identity and compiled-allowlist rules,
    consumer-authority/skill-approval/private-signing envelopes, the sole
    Promotion Coordinator desired-state writer, separate installation,
    candidate, rollout, host-attempt and slot facts, distinct technical and
    capability canary actors, and newest-first current-tooling recovery.
11. Freeze API/event compatibility and the measurable SLO, scale, limits,
    retention, disaster-recovery, observability, security-response, upgrade,
    support, and readiness evidence that blocks GA.

## Outputs

- Accepted ADR-0001 in `docs/architecture/adr/`.
- Validated architecture workspace and views.
- Complete repository documentation hierarchy linked from the ADR and task plan.
- Task specifications and dependency manifest with historical Jira keys.
- An explicit supersession matrix showing which historical Platform decisions become consumer-adapter concerns and which remain authoritative in the Platform.
- A versioned canonical-encoding contract and parser/canonicalizer denial fixtures.
- Normative schema sources and a reproducible signed offline contract bundle
  with schema IDs/digests, two-validator fixtures, OpenAPI/AsyncAPI/example/
  documentation drift tests, and historical-resolution policy. Task AD-01
  releases no generated language binding; deterministic Go, Python, and
  TypeScript models/clients and their clean-tree drift checks are owned by
  AD-10 after the externally visible ports are frozen.
- A repository-only development-plan schema, positive and denial fixtures, and
  Markdown/JSON/DAG drift test, with explicit exclusion from the released
  product contract bundle.
- Accepted renderer-release, consumer-authority, skill-approval,
  private-signing, target-delivery-state, canary, recovery, and operational-
  readiness contracts.
- The product-grade task/milestone DAG defining CONTRACTS-FROZEN,
  SUPPLY-CHAIN-CERT, CONTROL-PLANE-CERT, RUNTIME-CERT, CORE-CERT,
  REFERENCE-CATALOG-CERT, and REFERENCE-CONSUMER-CERT.
- The current acceptance evidence is recorded in the
  [implementation-readiness execution plan](../implementation-readiness-execution.md).

## Acceptance criteria

- A developer can implement every later task without inventing an ownership, schema, media-type, state-transition, security, or forward-recovery decision.
- No marketplace package contains required MCP, tool, grant, resource, provider, credential, tenant, or workload-identity fields.
- A consumer customization can change every functional Agent Spec property and add, replace, or remove arbitrary regular files, while security authority and raw secret values remain external consumer inputs.
- Public catalog renders contain no consumer customization; the resolved private effective render is rebuilt in full and embedded in the private deployment.
- Agent Delivery stores content-addressed references, bindings, state, and receipts, not a second mutable consumer agent definition or organizational identity.
- Artifact activation requires an exact digest, trusted signature, required policy evidence, an exact consumer/subject/target binding, and the current desired-state revision.
- Equivalent restricted YAML and JSON produce identical JCS bytes and semantic digests; unsupported YAML constructs and raw-YAML signing fail closed.
- Every authority-bearing object validates from the offline bundle and fails
  closed for unknown versions, fields, operations, references, or schemas.
- `development-plan.json` validates against the exact repository-only schema,
  matches the Markdown plan and DAG, carries the `repository-internal` marker,
  and is absent from the released product contract bundle.
- Exact renderer release identity, fresh consumer authority, per-consumer
  private keys, sole-writer desired state, separate canary actors, and forward
  recovery have one non-contradictory normative contract each.
- The standalone release has no dependency on ByteDesk's 34+1 catalog or
  ByteDesk consumer cutovers.
- Architecture and ADR validation are green.

## Verification

Run ADR validation, constrained C4/Mermaid validation and deterministic source
export, documentation link
checking, JSON Schema metaschema/reference closure and two-validator fixtures,
RFC 8785/parser differentials, OpenAPI/AsyncAPI generation and drift checks,
task/milestone DAG validation, transition-model checks, and peer architecture
review against requirements, dependencies, authority, failure modes,
migration/compatibility, and verification/operations.

## Not in scope

Marketplace repository creation, runtime code, registry mutation outside non-production test fixtures, consumer integration implementation, or production release.

## Dependencies

None.

## Architecture review amendments

ADR-0001 and its architecture package must close all nine findings carried forward from the review:

1. Define `bytedesk.agent-binding/1` as an exact source/harness binding plus a deterministic private functional-customization delta. The delta may change any functional property and perform explicit file add/replace/remove operations, but may not supply identity, grants, credential values, trust roots, or mandatory security policy. Require official Agent Spec validation before and after resolution.
2. Define per-target definition/runtime subdigests under a signed release. A consuming platform may bind its workload identity tuple to those digests, but Agent Delivery neither issues nor authorizes that identity.
3. Prevent consumer organizational-profile definition or deployment fields from becoming a second source of truth; migration of such fields belongs in each consumer adapter.
4. Permit automatic update only when skill digests are unchanged; retain quarantine and approval for changed or high-risk skills. Skills may contain arbitrary regular files, including executable code, but delivery stages never execute them and runtime execution requires explicit approval of the exact skill digest under current consumer sandbox, identity, network, and call-time authorization controls.
5. Keep OCI subjects/referrers repository-local and represent cross-repository edges as explicit signed digest descriptors. A private deployment embeds its effective render and does not claim a cross-repository public render as its OCI subject.
6. Use purpose-separated KMS/WIF trust plus a separately pinned Sigstore-keyless
   `contract-bundle-release-v1` policy, with rotation, revocation, least
   privilege, exact repository/media scope, and privacy controls.
7. Define durable runtime slots and tombstones plus a target-bound host identity; slot ownership remains with the consuming runtime.
8. Define control-plane-to-host ownership, outbox/inbox delivery, async operation status, rollout lease/CAS, and complete failure/recovery states without importing consumer authorization.
9. Treat YAML as human authoring only. Reject duplicate keys, aliases, custom tags, non-string keys, and non-finite numbers; hash and sign RFC 8785 JCS bytes from the validated JSON data model. Preserve arbitrary payload files byte-for-byte, even when a payload filename ends in `.yaml`.

The architecture must also define archive safety; signed catalog, release, and withdrawal semantics; import identity rules; registry retention, garbage collection, backup, and restore; and the complete positive, negative, and fault-injection test matrix. Runtime tasks remain blocked until these decisions are explicit.
