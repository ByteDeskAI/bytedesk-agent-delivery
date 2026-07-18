# AD-18: Certify end-to-end agent portability and delivery

- Historical Jira: [BDP-3319](https://bytedesk.atlassian.net/browse/BDP-3319)
- Delivery role: Standalone core certification and operational readiness
- Release gate: Emits `CORE-CERT / standalone GA`

## Outcome

Prove the complete standalone product from offline contracts and generic source
through native/Hermes/OpenClaw renderer products, signed OCI distribution,
installation, current consumer authority, sole-writer desired state, private
compilation, separate canary actors, promotion, receipt verification, update,
and current-tooling forward recovery. Produce the signed operational-readiness
report required for standalone GA.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Landed AD-01 and AD-04 through AD-15.
- Generic Agent and portable SpecializedAgent catalogs, strict operation,
  skill, native, Hermes, OpenClaw, consumer, and runtime fixtures.
- Production-equivalent registry, KMS/WIF, Sigstore keyless contract-release,
  Git provider, Agent Delivery control
  plane, consumer Adapter, capability verifier, DesiredStateStore, and runtime
  topology dedicated to certification.
- AD-01 threat model, test matrix, runbooks, and trust controls.

## Required work

1. Rebuild and verify the signed offline contract bundle; prove two-validator,
   generated-code/OpenAPI/AsyncAPI/doc drift, strict operation, source-kind,
   parser, canonical-encoding, compatibility, and historical-resolution
   conformance.
2. Run a clean third-party workflow using a generic definition-only catalog:
   validate, render with exact native/Hermes/OpenClaw renderer releases,
   qualify every renderer/platform, obtain fresh authenticated current status
   heads, finalize signed tenant-free public renders, package, publish, pull,
   inspect, and recursively verify product/artifact trust without
   ByteDesk Platform or ByteDesk's marketplace.
3. Run the generic consumer workflow: install with exact CAS, verify fresh
   consumer authority and skill approvals, compile/sign through both allowed
   private-key topologies, prepare a release, have the sole Coordinator publish
   desired state, collect separate host technical and consumer capability
   evidence, promote, update, force pre/post-switch failures, and complete a
   current-tooling forward recovery.
4. Run complete supply-chain, API/event, Git-intent, control-plane,
   DesiredStateStore, compiler, host, capability-verifier, registry, KMS,
   Sigstore keyless contract-release,
   cancellation, concurrency, crash/restart, outage, revocation, retention, and
   exact receipt-reproduction fault matrices.
5. Measure and archive every Operational readiness v1 SLO, reference-workload
   latency, default limit, capacity, fairness/backpressure, soak/chaos,
   dependency-outage, retention/GC, backup/restore/failover, observability/
   audit/redaction, security-response, N-1 upgrade/event replay, support, and
   thirty-day production-equivalent requirement.
6. Update architecture, schemas, runbooks, diagrams, API/event/CLI
   documentation, compatibility/support matrices, release notes, security
   contacts, on-call/escalation/status ownership, and sign the readiness report
   linking exact product, renderer, schema, infrastructure, and evidence
   digests.

## Outputs

- Reproducible core E2E certification report and evidence bundle.
- Completed core threat, failure, portability, and compatibility matrix.
- Updated product architecture, runbooks, API/CLI documentation, and release evidence.
- Supersession and cleanup report for product-owned legacy paths.
- CONTRACTS-FROZEN, SUPPLY-CHAIN-CERT, CONTROL-PLANE-CERT, and RUNTIME-CERT
  evidence indexes.
- Signed Operational readiness v1 report and CORE-CERT/standalone-GA go/no-go
  decision.
- Published SLO/latency/capacity/limits, topology, compatibility/support, and
  operator documentation.

## Acceptance criteria

### Core release

- Every definition-of-done statement for AD-01 and AD-04 through AD-15 is
  demonstrated with linked evidence.
- Core proof uses generic fixtures and succeeds with AD-02, AD-03, AD-16,
  AD-17, ByteDesk Platform, and the ByteDesk 34+1 catalog absent.
- No marketplace repository, harness output, control-plane store, or runtime fixture remains an undocumented competing canonical definition source.
- Exact running state is reproducible from Git revision, OCI digest graph, trust policy, canonical customization, exact public/private skill set, embedded effective render, installation/consumer binding references, current consumer-policy digest, target/slot, and receipt.
- Forward recovery selects eligible historical functional content newest-first,
  rebuilds it with current trusted source, renderer/compiler, approval,
  authority, policy, and canary evidence, and never reactivates historical
  deployment state.
- All consumer identity, roles, MCP/tool/resource grants, provider access authority, credentials, workload authentication, and business approvals remain external to Agent Delivery and are represented only by opaque current references/verdicts. Functional provider/model selection and configuration may be part of the private customization.
- Private customization proves that every functional property and declared regular file can be extended or replaced while attempts to change security authority, trust, secret values, workload identity, or mandatory controls fail closed.
- Skill fixtures include scripts, binaries, archives, data, and dependencies; validation through activation preserves approved files without executing them, while an optional consumer-runtime test proves execution requires separate consumer approval, sandboxing, identity, and call-time authorization.
- Restricted YAML is provenance-only authoring input; the complete running lineage reproduces from canonical JCS contract objects plus byte-exact payloads.
- Exact renderer-release manifests, executed distributions/platforms, compiled
  allowlists, and schema digests are present in every relevant lineage.
- Native Agent Spec, Hermes, and OpenClaw each pass the complete qualification
  role/subject matrix on `linux/amd64` and `linux/arm64`; every qualification
  object and signed public-render lineage is constructible through a declared
  production port.
- Selection and execution prove fresh caller-nonce/time-bound authenticated
  current product and renderer status heads. First contact, unchanged refresh,
  append-only advancement, rollback, fork, expiry, wrong nonce, withdrawal,
  revocation, and end-of-support are certified.
- Consumer authority is fresh at compile, activation, and recovery; authority/
  approval and deployment keys are separate and private keys are isolated per
  consumer.
- Only the Promotion Coordinator writes target desired state. The host returns
  technical evidence and the consumer capability verifier returns signed
  allowed/exact-denial evidence without either actor promoting.
- All published operational SLOs, scale targets, RPO/RTO, retention, security
  response, upgrade/support, runbook, on-call, and thirty-day readiness
  requirements pass with no unresolved critical/high finding.
- No production consumer deployment is authorized by this certification.

## Verification

Run all unit, schema/contract, integration, E2E, security, architecture,
clean-machine, performance, capacity, soak, chaos, dependency-outage, limit,
retention, backup/restore/failover, upgrade/replay, audit/redaction, incident,
and support-readiness gates. Archive commands, calculations, histograms, exact
digests, signatures, attestations, receipts, fixtures, and redacted telemetry
in a reproducible signed evidence bundle.

## Not in scope

ByteDesk catalog certification, ByteDesk Hermes/OpenClaw cutover, or any
production consumer mutation. AD-02/AD-03 produce REFERENCE-CATALOG-CERT and
AD-16/AD-17 produce REFERENCE-CONSUMER-CERT separately.

## Dependencies

Blocked by AD-01 and AD-04 through AD-15 only.

## Normative contracts and conformance

- **Ports and operations.** CORE-CERT covers every registered operation under
  `bytedesk.port.catalog/1`, `bytedesk.port.scm/1`,
  `bytedesk.port.agent-spec-validator/1`,
  `bytedesk.port.renderer-strategy/1`, `bytedesk.port.renderer-adapter/1`,
  `bytedesk.port.renderer-sandbox/1`,
  `bytedesk.port.wayflow-compatibility/1`,
  `bytedesk.port.oci-registry/1`, `bytedesk.port.kms-signing/1`,
  `bytedesk.port.supply-chain-evidence/1`,
  `bytedesk.port.evidence-archive/1`,
  `bytedesk.port.consumer-authority-approval/1`,
  `bytedesk.port.consumer-projection/1`,
  `bytedesk.port.desired-state-store/1`,
  `bytedesk.port.control-plane-api-events/1`,
  `bytedesk.port.promotion-coordinator/1`,
  `bytedesk.port.private-compiler/1`,
  `bytedesk.port.host-reconciler/1`,
  `bytedesk.port.capability-verifier/1`,
  `bytedesk.port.cli-automation/1`, and `bytedesk.port.region-fence/1`. The
  certification inventory also covers `bytedesk.port.release-status-head/1`,
  `bytedesk.port.trust-policy-provider/1`,
  `bytedesk.port.release-qualification-finalizer/1`,
  `bytedesk.port.public-render-finalizer/1`, and
  `bytedesk.port.public-render-publisher/1`. The
  closed operation IDs for each port are authoritative in
  `contracts/ports/v1/port-registry.json`; omission or an additional unreviewed
  operation fails certification. Exact field-value and closed request/result
  schemas are distributed in `contracts/ports/v1/type-catalog.json`; canonical
  valid and structural-denial payloads are in
  `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Certification binds the exact closed
  inventory at `contracts/bundle/v1/schema-inventory.json`, every source schema
  under `contracts/schemas/v1/`, OpenAPI and AsyncAPI projections, the port,
  action, problem, event, OCI, renderer, signer/evidence, DesiredStateStore,
  host/capability, CLI, region-fence, and external-input-lock profiles under
  `contracts/ports/v1/protocol-profiles.json`, and the signed offline bundle
  manifest and exact digest.
- **Conformance owner.** AD-18 owns whole-product negative-path, version-skew,
  provider-profile, restore/failover, scale, chaos, security, and signed evidence
  aggregation. Run `make verify-downstream-ports`; the task-specific suite is
  `downstream.certification.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute its exact compiled steps
  from `contracts/ports/v1/conformance-plan.json`; schema-valid structural
  samples are not semantic implementation goldens. Every task-owned suite from
  AD-02 through AD-17 must pass without waiver.
- **Boundary.** Native Agent Spec is the only selectable native output and
  WayFlow 26.1.2 remains evidence-only. AD-17 owns the ByteDesk OpenClaw
  migration map; the Promotion Coordinator alone triggers Capability Verifier
  work and writes target desired state. No reference-consumer identity, grant,
  credential, policy, runtime detail, or business approval may enter core
  contracts or generic certification fixtures.

## Architecture review amendments — mandatory certification matrix

Core evidence must cover:

- signed offline schema bundles, two-validator agreement, generated contract
  drift, strict functional/file/skill operations, Agent/portable
  SpecializedAgent resolution, and official Agent Spec validation;
- generic selectable/system fixtures without a ByteDesk catalog dependency;
- deterministic source, render, deployment, and release OCI digests across clean rebuilds;
- complete signed product/renderer inline authority, qualification policy/suite,
  typed evidence tree/predicates/final decision, and all required
  renderer/platform matrix cells;
- fresh signed status revisions, nonce/time-bound head checkpoints,
  authentication evidence, and exact append-only consistency proofs, including
  rollback/fork/staleness denials;
- RFC 8785 JCS golden bytes across independent implementations, YAML/JSON semantic equivalence, forbidden YAML/duplicate-JSON-member denial, and byte-exact arbitrary payload preservation;
- tampered layer, wrong or missing subject, unknown/revoked key, missing attestation, cross-installation/consumer, downgrade, and source-substitution denial;
- exact renderer-release manifest, executed distribution/platform, compiled
  allowlist, schema, sandbox, withdrawal, and substitution evidence for native,
  Hermes, and OpenClaw on both server architectures;
- duplicate, reordered, missed, and conflicting Git events plus scheduled reconciliation;
- installation create/bind idempotency, consumer-subject adapter failures, and lifecycle races;
- absent/match revision-plus-digest CAS and ABA denial; one Coordinator writer
  across managed/consumer-native stores; no Git/compiler/host/observation/event
  desired-state authority; and separate lifecycle transition models;
- fresh compile/activate/recover authority snapshots, exact skill approvals,
  consumer-owned and tenant-dedicated private-key profiles, purpose/key
  separation, and shared-key/self-approval denial;
- unchanged-skill automatic update and changed/high-risk skill quarantine;
- tenant-free public catalog rendering, public-endpoint rejection of private inputs, complete private effective re-rendering, no post-render patching, and the exact-input-only public-render reuse rule;
- arbitrary declared regular skill files preserved without execution in validation, rendering, compilation, publication, staging, or activation, plus rejection of unsafe entries, secrets, and resource bombs;
- private customization of every functional Agent Spec property, file, skill, model/provider choice, tool/MCP functional configuration, harness setting, and opaque secret reference, with negative tests for every forbidden security-authority or mandatory-control mutation;
- explicit cross-repository parent descriptors and no reliance on cross-repository OCI subject/referrer discovery;
- recursive OCI manifest/config/layer/blob closure with exact media/role
  mapping, bounded traversal, missing-content/cycle/duplicate-role/tag denial;
- full authenticated private-input bundle, compilation-input/deployment/
  compilation-evidence/runtime-release signer separation, and an acyclic
  lock → deployment → evidence → release proof in which each runtime-release
  entry binds both exact deployment and compilation-evidence descriptors;
- newest-first forward-recovery eligibility, current-tooling rebuild, revoked
  renderer and withdrawn-content denial, separate recoverySource, no Git
  dependency, and no historical authority/deployment reactivation;
- partial pull, disk full, crash before/after switch, registry outage, host credential rotation, observation retry, and safe-boundary recovery;
- stable slot preservation and no retired-slot reuse without host-reset ceremony;
- host identity denial outside its one installation and runtime target;
- separate target-host technical and consumer capability evidence, exact
  permitted and expected policy-denial results, false-denial cases, nonce/
  freshness/candidate binding, and certified activation mode;
- registry conformance, retention/garbage-collection roots, backup, restore, quotas, legal hold, withdrawal, and revocation;
- explicit CLI package/build/publish/pull commands and API/event compatibility;
- all Operational readiness v1 SLO, performance, capacity, default-limit,
  fairness/backpressure, thirty-day, retention, RPO/RTO, restore/failover,
  telemetry/audit/redaction, security-response, upgrade/replay, runbook,
  on-call, status, and support evidence; and
- architecture/C4 drift checks and clean third-party reproduction with no
  ByteDesk dependency.

ByteDesk 34+1, Platform identity/MCP, and source-cutover evidence belongs only
to REFERENCE-CATALOG-CERT and REFERENCE-CONSUMER-CERT.
