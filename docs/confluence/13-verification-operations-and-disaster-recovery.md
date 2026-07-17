# Verification, operations, and disaster recovery

## Completion standard

Agent Delivery is complete only when a release can be reproduced, verified,
activated, observed, failed, rolled forward to known-good content, and restored
from backup with the same digest evidence. Passing unit tests alone is not
sufficient for a supply-chain and deployment product.

## Verification layers

### Contract tests

Contract suites freeze:

- Agent Spec `26.1.2` validation behavior;
- [Agent binding v1](../standards/agent-binding-v1.md) canonicalization and
  denial fixtures;
- [OCI media types v1](../standards/oci-media-types-v1.md), descriptor shape,
  and canonical encoding;
- [Trust policy v1](../standards/trust-policy-v1.md) purpose and claim rules;
- renderer input, output, compatibility, and warning codes;
- API resources, errors, operations, JSON, and exit codes; and
- host desired-state and observation protocol.

Unknown security-relevant fields and versions fail closed.

### Unit and property tests

Unit and property tests cover normalization, canonical serialization, digest
calculation, state transitions, predecessor comparison, idempotency,
compatibility classification, graph traversal bounds, slot allocation, and
retention-root calculation.

Property tests generate malformed paths, Unicode, duplicate keys, archive
headers, descriptor graphs, event ordering, and concurrent candidates.

### Integration tests

Integration suites use real supported versions of Git, registry/Harbor, OCI
client/ORAS, signature verifier/Cosign, KMS emulator or non-production KMS,
database, provider Adapter, and target harness parser. Mocks are limited to
failure injection that cannot be produced safely otherwise.

### End-to-end tests

End-to-end certification starts from an immutable source commit and ends with a
host observation and verified receipt. It covers public discovery, source
verification, binding, private compile, release, safe activation, workload
login, allowed/denied capability checks, and forward rollback.

## Baseline catalog gate

CI and release certification assert:

- exactly 34 selectable employee-agent definitions;
- exactly one non-selectable `office-orchestrator` reference system package;
- official Agent Spec validation for all 35 packages;
- absence of authority-bearing fields;
- deterministic source and supported harness renders; and
- the system package never requests or creates an employee profile, workload
  identity, MCP grant, role, or credential.

Counts are checked against a reviewed expected manifest, not inferred from what
happens to be present.

## Reproducibility gate

Source, render, deployment, and release artifacts are built twice from clean
isolated environments. Exact digests must match. The test perturbs locale,
timezone, checkout path, file discovery order, cache availability, and host
identity to expose accidental nondeterminism.

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
- authority fields, secret leakage, provider/MCP/grant smuggling, and approval
  weakening;
- cross-consumer, cross-tenant, wrong-profile, wrong-runtime, and wrong-slot
  deployment reuse;
- stale policy/grant/profile/credential and wrong deployment subdigest;
- archive traversal, absolute paths, links, devices, FIFOs, sockets, size bombs,
  and excessive graph depth; and
- renderer or package-directed code execution attempts.

Denial must leave no partial active state.

## Reconciliation and concurrency matrix

SCM and process tests include duplicate, reordered, delayed, missed, and stale
events; force pushes; repository rename/transfer; installation removal;
scheduled reconciliation; bot/human conflicts; profile retirement; policy
revocation during compilation; desired-state advance during staging; and host
observation replay.

Every sequence converges to one legal state using idempotency, expected
predecessors, monotonic revisions, and bounded rollout leases.

## Host failure-injection matrix

Host tests inject:

- partial and corrupt pulls;
- registry authorization loss;
- disk full and inode exhaustion;
- crash before unpack, during staging, immediately before switch, immediately
  after switch, and during canary;
- malformed file inventory or wrong ownership/mode;
- runtime parser/start failure;
- workload login failure;
- granted MCP invocation failure and unexpected ungranted success;
- canary threshold breach;
- control-plane outage and stale desired state; and
- host restart with desired, staged, active, and LKG combinations.

Each test proves active/LKG preservation, exact recovery decision, bounded
retry, append-only observation, and no unauthorized self-promotion.

## Clean-room portability test

A release candidate is tested in an environment with no ByteDesk Platform
services or credentials. Using only published documentation, API schema, CLI,
trust policy, and registry access, a third party must be able to:

1. fetch and verify the signed catalog;
2. inspect and validate a portable definition;
3. render it with a supported Adapter;
4. build or fetch the deterministic OCI artifact;
5. verify signatures, provenance, SBOM, and explicit graph edges; and
6. integrate a generic consumer fixture without adopting ByteDesk identity or
   MCP semantics.

This test protects the independent-product boundary.

## Consumer authorization proof

An integrated runtime additionally proves current consumer authority:

- positive workload login for the intended profile/runtime/deployment;
- positive discovery and invocation of one explicitly granted MCP capability;
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
- stage, switch, canary, rollback, and convergence duration;
- active and LKG artifact digests as non-secret identifiers;
- host protocol and trust-policy version; and
- retention roots, quota, and backup freshness.

Logs carry correlation and causation IDs but redact tokens, signed URLs, raw
webhook bodies, instruction content where private, tenant secrets, and
credential references.

## Service objectives and alerts

Before production, operators define measurable targets for API availability,
catalog freshness, operation queue age, deployment convergence, observation
freshness, and restore point/recovery time. Alerts distinguish a control-plane
outage from an unhealthy active runtime.

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
- canary failure and forward rollback;
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
- binding, deployment, release, slot, and observation records;
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
6. Reconciles catalog, database descriptors, registry referrers, and receipts.
7. Verifies signer/revocation state without recreating private keys.
8. Connects a test host and proves active/LKG and desired-state behavior.
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
- **SCM outage:** new candidates pause; scheduled reconciliation resumes later.
- **Consumer identity/policy outage:** new private compilation, workload login,
  or activation requiring current authority fails closed.
- **Host outage:** control plane retains desired state; rebuilt host verifies
  from scratch before activation.

## Release checklist

A releasable increment has:

- frozen contract fixtures and migration notes;
- deterministic clean builds;
- dependency, license, secret, and vulnerability scans;
- required signatures, attestations, and SBOMs;
- positive, negative, failure-injection, and clean-room results;
- registry/KMS/provider conformance evidence;
- forward-rollback and restore drill evidence;
- updated API/CLI and operator documentation; and
- no unresolved critical threat or ambiguous authority ownership.

## Program exit criteria

The first complete delivery system exits development when all 35 reference
packages are portable, Hermes and OpenClaw renders are deterministic, public
and private OCI graphs verify, a generic third party passes the clean-room path,
an integrated consumer proves current identity/MCP authorization, host
activation and forward rollback survive injected failures, and restore
reproduces the exact receipt graph.

## Related pages

- [Supply-chain trust](06-supply-chain-trust-and-threat-model.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Migration and cutover](12-migration-and-source-cutover.md)
