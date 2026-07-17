# Verification, operations, and disaster recovery

## Completion standard

Agent Delivery is complete only when a release can be reproduced, verified,
activated, observed, failed, rolled forward to known-good content, and restored
from backup with the same digest evidence. Passing unit tests alone is not
sufficient for a supply-chain and deployment product.

## Verification layers

### Contract tests

Contract suites freeze:

- [Machine contracts v1](../standards/machine-contracts-v1.md): closed JSON
  Schema Draft 2020-12 authority schemas and signed offline contract bundle;
  strict JSON Patch/file/skill/source/predecessor semantics; OpenAPI 3.2.0;
  AsyncAPI 3.1.0; CloudEvents 1.0.2; ETags; RFC 9457 errors; and event resync;
- [Renderer identity v1](../standards/renderer-identity-v1.md): exact renderer-
  release manifest, executed distribution/worker, platform, product/allowlist/
  schema digests, sandbox, withdrawal, and current-tooling recovery;
- [Consumer authority v1](../standards/consumer-authority-v1.md): fresh signed
  authority snapshots, signed exact-skill approvals, immutable policy digests,
  and consumer-owned or tenant-dedicated purpose-separated private keys;
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md): one sole
  Promotion Coordinator writer and DesiredStateStore, separate lifecycle
  machines, Host/Capability Verifier evidence, and forward recovery;
- Agent Spec `26.1.2` validation behavior;
- the encoding boundary: YAML 1.2 JSON-compatible human authoring only;
  rejection of duplicate keys, aliases, custom tags, non-string mapping keys,
  and non-finite numbers; JSON data-model authority; RFC 8785 JCS hashing and
  signing bytes; original YAML retained only as provenance or storage-integrity
  evidence and never semantic identity, artifact authority, or activation
  authority; and exact raw bytes for arbitrary payload files, including `.yaml`
  and `.json` payloads;
- [Agent binding v1](../standards/agent-binding-v1.md) canonicalization,
  arbitrary functional Agent Spec overrides, safe regular-file operations,
  public/private skill selection, opaque secret references, and denial fixtures;
- [OCI media types v1](../standards/oci-media-types-v1.md), descriptor shape,
  and canonical encoding;
- [Trust policy v1](../standards/trust-policy-v1.md) purpose and claim rules;
- tenant-free public renderer input/output, private full-rerender compilation,
  exact public-render reuse, compatibility, and warning codes;
- API resources, errors, operations, JSON, and exit codes; and
- host desired-state and observation protocol.

Unknown security-relevant fields and versions fail closed.

### Unit and property tests

Unit and property tests cover normalization, canonical serialization, digest
calculation, state transitions, predecessor comparison, idempotency,
customization/file-operation ordering, compatibility classification, exact
public-render reuse, graph traversal bounds, slot allocation, and retention-root
calculation.

State properties cover installation, candidate, rollout, host-attempt, and
active-slot facts independently; `absent`/revision-plus-digest CAS, ABA,
lease expiry, supersession, and illegal transitions; plus the prohibition on a
direct canary-to-`rolled_back` path.

Property tests generate malformed paths, Unicode, YAML duplicate keys, aliases,
custom tags, non-string keys, non-finite numbers, archive headers, descriptor
graphs, event ordering, and concurrent candidates. Golden fixtures assert exact
RFC 8785 bytes. Opaque payload fixtures prove that bytes are neither transcoded
nor normalized and that a one-byte change changes identity. They also prove
that a `.yaml` or `.json` filename alone never invokes contract parsing.

### Integration tests

Integration suites use real supported versions of Git, registry/Harbor, OCI
client/ORAS, signature verifier/Cosign, KMS emulator or non-production KMS,
database, provider Adapter, and target harness parser. Mocks are limited to
failure injection that cannot be produced safely otherwise.

They include product and renderer executable readback, consumer-owned and
tenant-dedicated KMS profiles, authority/approval versus deployment signer
separation, DesiredStateStore managed/consumer-native conformance, and store
migration with no dual write.

### End-to-end tests

End-to-end certification starts from an immutable source commit and ends with a
host observation and verified receipt. It covers public discovery, source
verification, binding/customization, signed public/private skill approval, private full
rerender and compile, release, safe activation, workload login, allowed/denied
capability and skill-execution checks, and forward recovery.

Host technical evidence and Consumer Capability Verifier evidence are separate,
challenge-bound objects. Negative capability proof must be the exact expected
consumer authorization denial; timeout, unavailable, missing endpoint, parser
error, or `404` is a failed canary, not a successful denial.

## Reference catalog gate after CORE-CERT

`REFERENCE-CATALOG-CERT`, not standalone GA or `CORE-CERT`, asserts:

- exactly 34 selectable employee-agent definitions;
- exactly one non-selectable `office-orchestrator` reference system package;
- official Agent Spec validation for all 35 packages;
- absence of tenant customization, opaque secret references, and
  authority-bearing fields in public artifacts;
- deterministic source and tenant-free supported-harness catalog renders; and
- the system package never requests or creates an employee profile, workload
  identity, MCP grant, role, or credential.

Counts are checked against a reviewed expected manifest, not inferred from what
happens to be present.

## Reproducibility gate

Source, tenant-free public render, private deployment with embedded effective
render, and release artifacts are built twice from clean isolated environments.
Exact digests must match. Private tests cover arbitrary functional deltas,
regular-file operation order, public/private skill selection, full rerendering,
and the exact no-operation customization/public-skill/input-match reuse rule. The test perturbs locale,
timezone, checkout path, file discovery order, cache availability, and host
identity to expose accidental nondeterminism. It also varies accepted YAML
comments, whitespace, quoting, scalar spelling, and key order and confirms the
same semantic JSON produces the same canonical digest. Original YAML may differ
as provenance without changing semantic identity; even an integrity reference
to the original authoring bytes is provenance or storage-integrity evidence
only and cannot establish semantic identity, artifact authority, or activation
authority.

On mismatch, the build reports differing normalized inputs, manifest fields,
and files without exposing secrets.

## Security-negative matrix

Certification denies and records stable codes for:

- wrong or missing subject and tampered layer;
- unknown, expired, wrong-purpose, or revoked signer;
- wrong repository, workflow, ref, environment, builder, or media type;
- missing provenance, compatibility, evaluation, policy, or SBOM evidence;
- withdrawn digest, downgrade, and mutable-reference substitution;
- source or base-definition substitution;
- unknown schema/contract-bundle digest, remote schema fetch, unknown authority
  field, invalid extension, patch/path/file/skill precondition failure, and
  partial-delta application;
- renderer manifest/version/executed distribution/platform/allowlist/schema
  substitution, PATH/library injection, sandbox escape, and revoked-tooling use;
- unsigned, stale, replayed, wrong-purpose, cross-consumer, or wrong-policy
  authority/skill approval plus shared-private-signer topology;
- disallowed YAML constructs, non-canonical structured signing input, and
  structured-object digest disagreement across parsers;
- payload parsing-by-extension, transcoding, normalization, or a byte change
  presented under an old digest;
- public customization leakage; raw secrets; embedded identity, role, grant, or
  provider-access claims; caller-selected trust roots; and approval weakening;
- unsafe add/replace/remove paths, artifact hooks, install commands,
  package-directed fetches, post-render patches, and undeclared files;
- changed skill digests that bypass quarantine and script/binary execution by
  the pipeline or runtime without exact-digest approval, sandbox, and current
  authorization;
- cross-consumer, cross-tenant, wrong-profile, wrong-runtime, and wrong-slot
  deployment reuse;
- stale policy/grant/profile/credential and wrong deployment subdigest;
- archive traversal, absolute paths, links, devices, FIFOs, sockets, size bombs,
  and excessive graph depth; and
- renderer, compiler, or package-directed code execution attempts.

Denial must leave no partial active state.

## Reconciliation and concurrency matrix

SCM and process tests include duplicate, reordered, delayed, missed, and stale
events; force pushes; repository rename/transfer; installation removal;
scheduled reconciliation; bot/human conflicts; profile retirement; policy
revocation during compilation; desired-state advance during staging; and host
observation replay.

Every sequence converges to one legal state using idempotency, expected
revision-and-digest CAS preconditions, monotonic revisions, one sole Promotion
Coordinator writer/DesiredStateStore, and bounded rollout leases. Git and
events remain intent/notification inputs and cannot write target state.

## Host failure-injection matrix

Host tests inject:

- partial and corrupt pulls;
- registry authorization loss;
- disk full and inode exhaustion;
- crash before unpack, during staging, immediately before switch, immediately
  after switch, and during canary;
- malformed file inventory, unsafe customized entry, wrong ownership/mode,
  missing executable-skill approval, or wrong sandbox-policy digest;
- runtime parser/start failure;
- workload login failure;
- granted MCP invocation failure and unexpected ungranted success;
- false negative evidence where timeout, network failure, missing endpoint,
  parser error, or `404` is presented as policy denial;
- canary threshold breach;
- control-plane outage and stale desired state; and
- host restart with desired, staged, active, and LKG combinations.

Each test proves active/LKG preservation, exact recovery decision, bounded
retry, append-only observation, and no unauthorized self-promotion.

Recovery tests search promoted functional content newest first, reject
withdrawn/content-revoked dependencies and revoked renderer/compiler tooling,
exercise current-tooling public-lineage rebuild and semantic mismatch, prove
fresh signed recovery authority and skill approvals, run during Git outage, and
fail closed when no candidate is eligible.

## Clean-room portability test

A release candidate is tested in an environment with no ByteDesk Platform
services or credentials. Using only published documentation, API schema, CLI,
trust policy, and registry access, a third party must be able to:

1. fetch and verify the signed catalog;
2. inspect and validate a portable definition;
3. render its tenant-free public inputs with a supported Adapter while proving
   that customization and private inputs are rejected;
4. build or fetch the deterministic OCI artifact;
5. verify signatures, provenance, SBOM, and explicit graph edges; and
6. integrate a generic consumer fixture without adopting ByteDesk identity or
   MCP semantics.

This test protects the independent-product boundary.

## Consumer authorization proof

An integrated runtime additionally proves current consumer authority:

- positive workload login for the intended profile/runtime/deployment;
- positive discovery and invocation of one explicitly granted MCP capability;
- positive execution of one exact-digest approved skill in its declared sandbox
  and denial of the same content without approval or outside that sandbox;
- denial of an ungranted capability;
- denial for wrong consumer/tenant/profile/runtime;
- denial for stale release or deployment subdigest; and
- denial after a grant or credential is revoked.

These are integration proofs against consumer-owned systems. Agent Delivery
does not issue the grant or decide the MCP call.

## Observability

Operational telemetry includes:

- operation counts, phase duration, queue age, retries, and terminal outcomes;
- validation and denial codes by safe category;
- render reproducibility and compatibility outcomes;
- registry/KMS/provider latency and failure;
- desired-versus-observed runtime revision;
- stage, switch, canary, forward-recovery, and convergence duration;
- active and LKG source, binding/customization, selected-skill, embedded-render,
  deployment, and release digests as non-secret identifiers;
- host protocol and trust-policy version; and
- retention roots, quota, and backup freshness.

Logs carry correlation and causation IDs but redact tokens, signed URLs, raw
webhook bodies, instruction content where private, tenant secrets, and
credential references.

## GA service objectives and alerts

[Operational readiness v1](../standards/operational-readiness-v1.md) fixes the
launch targets; operators may make them stricter but cannot defer or silently
weaken them. The primary monthly objectives are 99.95% for public reads and
target desired-state reads/observation intake, 99.9% for authenticated reads/
command acceptance, 99.9% of committed-outbox events within 60 seconds, cached
read p95 at 300 ms/p99 at 1 second, command acceptance p95 at 1 second, desired-
revision publication p95 at 5 seconds, and connected reconciler detection p95
at 30 seconds. The reference-workload end-to-end stage/preflight/canary/promote
target is p95 at five minutes.

GA capacity evidence covers 10,000 isolated consumers, 100,000 installations,
25,000 runtime targets, 1,000 concurrent actions, 500 concurrent rollouts,
50,000 reads and 5,000 accepted commands per minute, and 100 million queryable
observations/receipts. An unmeasured topology cannot claim conformance.

Durability targets are zero acknowledged-transaction RPO in-region, at most
five-minute region-loss RPO, at most 60-minute control-plane/desired-state RTO,
and at most four-hour complete registry/evidence restoration RTO. Backup
integrity is checked daily, scoped restore monthly, and full isolated restore/
regional failover at least quarterly.

Observations, receipts, approvals, and administrative audit default to 400 days
online/queryable retention. Contract bundles, product/renderer manifests, and
trust-policy snapshots needed for historical verification remain available at
least seven years and never less than consumer evidence retention. A GA major
is supported at least 24 months; after a successor GA, the previous major gets
at least 12 additional months of security/critical-correctness support. Public
deprecation lasts at least 12 months and two GA minors unless an active security
vulnerability requires removal.

GA requires 30 consecutive production-equivalent days meeting objectives,
capacity/soak/chaos/noisy-neighbor proof, zero unresolved critical/high findings
in the released path, successful restore/failover, N-1 rolling upgrade and
event replay, complete runbooks/on-call/support surfaces, and a signed readiness
report binding exact product, renderer, schema, infrastructure, and evidence
digests.

After an authorized decision, confirmed signing-key or builder compromise must
publish revocation and block new affected activation within 15 minutes. An
actively exploitable critical product vulnerability requires mitigation or a
patched release within 24 hours; reachable high severity within seven days;
medium severity disposition within 30 days.

High-priority alerts include signature/trust failure spikes, unexpected
ungranted capability success, cross-scope denial, active-versus-desired drift,
host identity misuse, registry quota exhaustion, missing LKG, backup failure,
and revoked digest still being newly activated.

## Runbooks

Runbooks must cover:

- failed publication or nondeterministic build;
- signer rotation and emergency revocation;
- artifact withdrawal and affected-release discovery;
- registry/KMS/SCM/consumer Adapter outage;
- stuck promotion or dead-letter replay;
- changed-skill quarantine, executable-skill approval, sandbox failure, and
  revocation;
- false-denial, canary failure, and forward recovery;
- host compromise, credential rotation, and rebuild;
- runtime slot purge/reset ceremony;
- consumer deletion and legal hold; and
- backup restore and post-restore reconciliation.

Each runbook states authority required, safe read-only diagnostics, mutation
steps, evidence to retain, communications, and verification of closure.

## Backup scope

Backups include:

- product database and append-only receipt history;
- catalog and channel state;
- contract bundles, immutable trust-policy snapshots, target desired state,
  binding, deployment, release, slot, canary, and observation records;
- registry manifests, blobs, signatures, attestations, and SBOMs;
- independently managed trust policy and revocation data; and
- configuration needed to reconstruct provider/registry/KMS integrations,
  excluding export of non-exportable private keys.

Source Git remains independently backed up according to marketplace governance.
Consumer identity, grants, and credentials remain in consumer backup scope.

## Restore procedure

A restore drill:

1. Establishes a clean isolated recovery environment.
2. Restores product persistence to the declared recovery point.
3. Restores registry content and verifies manifests/blobs.
4. Restores trust policy through its independent authenticated channel.
5. Recomputes graph integrity and retention roots.
6. Reconciles catalog, database descriptors, registry referrers, contract
   bundles, the sole target-state writer/store, outbox/inbox cursors, and
   receipts.
7. Verifies signer/revocation state without recreating private keys.
8. Connects a test host and proves active/historical-known-good facts, the sole
   desired-state writer/store, and fresh recovery eligibility behavior.
9. Runs clean-room and consumer authorization smoke tests.
10. Records actual recovery point and time against objectives.

Restore does not automatically reactivate every historical desired state. The
consumer confirms current lifecycle and authority before new activation.

## Outage behavior

- **Registry outage:** active verified content continues; pulls and new stages
  wait or fail closed.
- **KMS outage:** unsigned new artifacts cannot publish; existing verified
  active content continues according to cached policy.
- **Control-plane outage:** hosts retain active state and do not invent desired
  changes.
- **SCM outage:** new Git candidates pause; scheduled reconciliation resumes
  later, while eligible forward recovery from already accepted functional
  history remains available without Git.
- **Consumer identity/policy outage:** new private compilation, workload login,
  or activation requiring current authority fails closed.
- **Host outage:** control plane retains desired state; rebuilt host verifies
  from scratch before activation.

## Release checklist

A releasable increment has:

- frozen public/private split, customization, skill-execution, contract
  fixtures, canonical-encoding fixtures, and migration notes;
- deterministic clean builds;
- dependency, license, secret, and vulnerability scans;
- required signatures, attestations, and SBOMs;
- positive, negative, failure-injection, and clean-room results;
- registry/KMS/provider conformance evidence;
- forward-recovery, Git-outage recovery, and restore drill evidence;
- updated API/CLI and operator documentation; and
- no unresolved critical threat or ambiguous authority ownership.

## Program exit criteria

The standalone core exits development when generic Agent and portable
SpecializedAgent fixtures cover every supported semantic, native/Hermes/
OpenClaw public renderer contracts are tenant-free and deterministic,
customized private deployments embed a fully rerendered bundle, the exact-input
public-render reuse rule passes, public/private OCI graphs verify, a generic
third party passes the clean-room path, the generic consumer fixture proves
signed authority/approval and Host/Capability Verifier separation, lifecycle
and forward recovery survive injected failures, restore reproduces the exact
graph, and every GA readiness criterion above passes.

The 34 selectable ByteDesk definitions plus `office-orchestrator` gate only
`REFERENCE-CATALOG-CERT`. ByteDesk hosted Hermes and OpenClaw cutovers gate only
`REFERENCE-CONSUMER-CERT`. They prove reference catalog breadth and real
Platform identity/MCP authorization integration, but do not block or redefine
the standalone core milestone.

## Related pages

- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Migration and cutover](12-migration-and-source-cutover.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
