# Agent Delivery contract inventory

**Status:** Source-controlled v1 inventory

## Purpose and authority boundary

This inventory identifies every JSON Schema owned by Agent Delivery, the
authoritative source file for each schema, and the authority boundary of the
instances it validates. It implements the schema rules in
[Machine contracts v1](../standards/machine-contracts-v1.md) and the product
boundary in
[ADR-0001](adr/0001-independent-agent-delivery-control-plane.md).

An Agent Delivery-owned schema is authoritative for the shape and interpretation
of its object. It does not transfer business authority to Agent Delivery. In
particular, schemas for consumer authority, skill approval, policy evidence,
private bindings, and deployments preserve the consuming organization's
authority over identity, grants, credentials, workload identity, provider
access, and business approval. Agent packages and functional customization
cannot manufacture that authority.

The authoritative v1 schema source is `contracts/schemas/v1/`. Every schema:

- declares JSON Schema Draft 2020-12;
- has an immutable ID below
  `https://schemas.bytedesk.ai/agent-delivery/v1/`;
- closes authority-bearing object boundaries;
- explicitly bounds every directly typed array, non-enumerated string,
  integer, and open-ended object; and
- uses only stable, bundle-local Agent Delivery IDs for cross-schema `$ref`
  resolution;
- is selected by its exact canonical digest as well as its `$id`; and
- is resolved from a signed contract bundle without a runtime network fetch.

The `$id` is a stable name and discovery key. The canonical schema digest is
verification authority. Reusing an ID for different schema bytes is forbidden.

The machine-readable source of this exact set is
[`contracts/bundle/v1/schema-inventory.json`](../../contracts/bundle/v1/schema-inventory.json),
profile `bytedesk.contract-schema-inventory/1`. It is the sole reviewed v1
product-schema registry and currently contains 112 entries. Its root is closed
to `profile` and `schemas`; each entry is closed to the stable `id`, canonical
repository `path`, and RFC 8785 SHA-256 `digest`, ordered by ID. The prose table
below explains boundaries but is not a competing inventory. Both independent
validators, the bundle builder, and the offline bundle verifier compare the
complete schema set with those exact triples. Missing, additional, renamed,
ID-substituted, or digest-stale schemas fail closed. The inventory is itself a
JCS control separately bound by the signed bundle manifest and
`buildInputDigest`.

## V1 product schemas

### Core identity and functional-delta contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `common.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0` | Reusable digest, identifier, timestamp, bounded media type, descriptor, path, inventory, and evidence definitions. The shared media-type grammar is closed to one nonempty lowercase `type/subtype` with an optional bounded printable parameter suffix. It does not define a separately signed instance. |
| `schema-descriptor.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/schema-descriptor/1.0.0` | Exact schema ID-and-digest selector. A schema name without its accepted digest is insufficient authority. |
| `precondition.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/precondition/1.0.0` | Closed aggregate mutation precondition: create only when absent, or update only on exact revision and digest match. Null, omitted, wildcard, force, and digest-only forms are invalid. |
| `predecessor.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/predecessor/1.0.0` | Immutable aggregate predecessor identity: explicitly none or exact revision and digest. |
| `json-patch.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/json-patch/1.0.0` | Closed `bytedesk.json-patch/1` functional operation set. Only `add`, `replace`, and `remove` are accepted; copy, move, test, root replacement, and authority targets are denied. |
| `file-operations.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/file-operations/1.0.0` | Separate byte-exact regular-file add, replace, and remove operations inside an outer revision-and-digest-guarded binding mutation. Creates require absence; replace/remove require the exact prior item digest. Traversal, nested item revisions, and non-regular file types are denied. |
| `skill-operations.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/skill-operations/1.0.0` | Separate exact-skill add, replace, and remove operations inside an outer revision-and-digest-guarded binding mutation. Replace/remove bind the exact prior package digest. An operation changes functional content only and cannot approve execution or grant runtime authority. |
| `functional-customization-profile.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/functional-customization-profile/1.0.0` | Closed product compatibility profile naming functional Agent Spec and harness targets that private customization may change. Security and authority targets are explicitly outside the profile. |

### Supply-chain, package, and render contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `agent-source.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/agent-source/1.0.0` | Signed public source manifest that binds a portable Agent Spec document to exact content and provenance. Agent Spec semantics remain owned by the pinned external Agent Spec contract. |
| `agent-binding.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0` | Consumer-private, deterministic functional delta over an exact public source. It may customize any functional property and regular file, but cannot carry identity, grants, credentials, trust, or mandatory security policy. |
| `skill-package.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/skill-package/1.0.0` | Manifest for an untrusted skill package containing arbitrary regular files, including executable code. Validation, rendering, staging, and activation never execute those files; runtime execution requires separate exact-digest consumer approval and current sandbox policy. |
| `harness-render.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0` | Tenant-free public render emitted by an exact allowlisted renderer release. It contains portable functional output and no consumer identifiers, secrets, or grants. |
| `harness-configuration.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/harness-configuration/1.0.0` | Closed public/private functional harness configuration. Private values may include opaque secret references, but never secret values, grants, credentials, or authorization decisions. |
| `render-manifest.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/render-manifest/1.0.0` | Deterministic full-render manifest binding exact inputs, skill lineage, renderer execution identity, compatibility, file inventory, archive profile, and output digest. Public manifests are tenant-free; private manifests record functional lineage without becoming authority. |
| `consumer-deployment.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0` | Consumer-private deployment manifest embedding the full effective private rerender and exact approved public/private skill set. It is functional deployment content, not a credential or authorization grant. |
| `runtime-release.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-release/1.0.0` | Prepared runtime release identity binding the deployment, runtime artifact, inventory, and verification evidence used by reconciliation. |
| `catalog-index.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/catalog-index/1.0.0` | Signed public discovery index. Tags and channels help discovery but never replace exact subject digests. Public entries remain tenant-free. |
| `component-lock.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/component-lock/1.0.0` | Signed exact lock for reference implementation components, configuration, and dependency identities. |
| `renderer-release.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-release/1.0.0` | Complete renderer execution identity: platform, executable, schemas, allowlist, dependencies, toolchain, provenance, and output contract. Artifact-provided hooks and incomplete or fallback renderer identities are invalid. |
| `renderer-capability.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-capability/1.0.0` | Exact functional semantic capability matrix for one signed renderer release. Capability metadata cannot grant runtime capability, identity, provider access, or approval. |
| `renderer-input-parameters.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-input-parameters/1.0.0` | Normalized, digest-bound render invocation parameters with explicit public/private and lossy-mapping policy boundaries. |
| `renderer-compatibility-result.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-compatibility-result/1.0.0` | Stable exact/warning/lossy/unsupported semantic result bound to the executed renderer distribution and input. Eligibility is evidence for policy, never business approval. |
| `renderer-allowlist.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-allowlist/1.0.0` | Compiled set of accepted exact renderer-release digests. Selection cannot fall back to tags, `PATH`, a local build, or another installed renderer. |
| `contract-bundle.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/contract-bundle/1.0.0` | Manifest for the signed, content-addressed, offline contract bundle containing exact schemas, transitive references, lifecycle models, compatibility metadata, and derived API/event descriptions. |

### Release, compilation, renderer, publication, and provider contracts

The role labels in this table reproduce each authoritative schema's `title`
verbatim. The exact schema selected by inventory ID and digest remains the
normative contract.

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `private-compilation-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/private-compilation-evidence/1.0.0` | Consumer-private compilation statement and purpose-separated signing evidence |
| `private-compilation-input.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/private-compilation-input/1.0.0` | Closed exact-input lock for private deployment compilation |
| `private-input-authentication-bundle.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/private-input-authentication-bundle/1.0.0` | Private Input Authentication Bundle |
| `product-distribution-manifest.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/product-distribution-manifest/1.0.0` | Immutable Agent Delivery product distribution identity |
| `product-release-manifest.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/product-release-manifest/1.0.0` | Closed signed Agent Delivery product release manifest binding the exact contract-bundle descriptor and non-authority keyless verification receipt; downstream/private consumers replay the receipt independently rather than relying on the product KMS signature. |
| `public-source-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/public-source-authentication-evidence/1.0.0` | Detached public source or skill authentication evidence |
| `publication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/publication-evidence/1.0.0` | Authenticated OCI publication and readback evidence |
| `release-qualification-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-evidence/1.0.0` | Typed exact-subject release qualification evidence binding |
| `release-qualification-finalization-matrix.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-finalization-matrix/1.0.0` | Complete release-qualification finalization matrix |
| `release-qualification-policy.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-policy/1.0.0` | Closed release qualification policy |
| `release-qualification-predicate.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification-predicate/1.0.0` | Closed typed qualification predicate |
| `release-qualification.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-qualification/1.0.0` | Signed production release qualification |
| `release-status-append-resolution.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-append-resolution/1.0.0` | Release-status append attempt resolution |
| `release-status-head-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-head-authentication-evidence/1.0.0` | Detached release-status head checkpoint authentication evidence |
| `release-status-head-checkpoint.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-head-checkpoint/1.0.0` | Nonce-bound current release-status head checkpoint |
| `release-status-log-consistency-proof.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-log-consistency-proof/1.0.0` | Signed release-status log consistency proof |
| `release-status-log-inclusion-proof.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-log-inclusion-proof/1.0.0` | Release-status Merkle head inclusion proof |
| `release-status.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status/1.0.0` | Append-only current release status referrer |
| `renderer-attempt-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-attempt-authentication-evidence/1.0.0` | Purpose-bound renderer attempt issuer authentication |
| `renderer-attempt-authority.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-attempt-authority/1.0.0` | Caller-issued fenced renderer attempt authority |
| `renderer-execution-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-execution-authentication-evidence/1.0.0` | Purpose-bound renderer execution authentication evidence |
| `renderer-execution-receipt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-execution-receipt/1.0.0` | Renderer sandbox actual-execution receipt |
| `renderer-qualification-attempt-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-attempt-authentication-evidence/1.0.0` | Qualification attempt issuer authentication |
| `renderer-qualification-attempt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-attempt/1.0.0` | Fenced qualification-only renderer attempt |
| `renderer-qualification-evidence-tree.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-evidence-tree/1.0.0` | Closed qualification collector evidence tree |
| `renderer-qualification-receipt-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-receipt-authentication-evidence/1.0.0` | Qualification receipt authentication |
| `renderer-qualification-receipt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-receipt/1.0.0` | Qualification-only actual execution receipt |
| `renderer-qualification-selection.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-selection/1.0.0` | Non-deployable renderer qualification selection |
| `renderer-qualification-suite.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-qualification-suite/1.0.0` | Closed renderer release qualification suite |
| `renderer-selection.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-selection/1.0.0` | Closed renderer selection authority |
| `signer-authentication-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/signer-authentication-evidence/1.0.0` | Resolved provider signer authentication evidence |
| `signer-identity.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/signer-identity/1.0.0` | Exact purpose-separated signing identity |
| `trust-policy-pin-set-descriptor.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set-descriptor/1.0.0` | Provider-authenticated trust-policy pin-set descriptor |
| `trust-policy-pin-set-provider-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set-provider-evidence/1.0.0` | Trust-policy pin-set activation and readback evidence |
| `trust-policy-pin-set-resolution-query.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set-resolution-query/1.0.0` | Trust-policy provider resolution query |
| `trust-policy-pin-set-resolution.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set-resolution/1.0.0` | Trust-policy provider resolution |
| `trust-policy-pin-set.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy-pin-set/1.0.0` | Externally authenticated trust-policy pin set |

### Trust, approval, verification, and retained-evidence contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `trust-policy.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy/1.0.0` | Immutable independently distributed verification policy, including tag-free OCI repository scopes, accepted schemas, signers, builders, evidence, revocations, and purpose separation. It is selected by exact identity and cannot be supplied by an untrusted artifact. |
| `kms-signing-request.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/kms-signing-request/1.0.0` | Closed role-specific refinement consumed by `kms-signing#sign-digest`. It requires `kms_key`, forbids the contract-bundle signing purpose and both contract-bundle JSON/tar media representations, and therefore rejects keyless contract authority before provider access or side effects. |
| `signing-request.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/signing-request/1.0.0` | Closed request to a purpose-specific signing adapter binding request ID, exact subject digest, OCI repository, purpose, credential kind, exact signer-identity digest, nonce, a bounded media type/window, and trust-policy ID/digest. KMS requests require an immutable key version. Sigstore keyless requests forbid it. Product-release and contract-bundle-release requests additionally sign the sealed-builder and pre-sign-certification digests; contract-bundle media is valid only for keyless `contract-bundle-release-v1`, never KMS `product-release-v1`. The request does not itself confer signing authority. |
| `signing-result.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/signing-result/1.0.0` | Purpose-bound non-exportable KMS result binding the exact request, subject, immutable key version, ECDSA P-256 signature bundle, public verification material, trust policy, and redacted provider audit evidence. |
| `release-status-eligibility-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/release-status-eligibility-evidence/1.0.0` | Signed stage-specific eligibility proof binding fresh nonce-authenticated status heads for one exact product release and every renderer release actually used. Selection evidence cannot substitute for compilation or activation freshness. |
| `activation-authorization.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/activation-authorization/1.0.0` | Short-lived consumer-scoped signed authorization binding the exact rollout/host attempt, complete runtime-release/deployment graph, current authority and candidate-ready evidence, activation-stage status eligibility, generations, fencing, epoch, operation time, and expiry. A digest alone is not authority. |
| `external-input-lock.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/external-input-lock/1.0.0` | Immutable full-commit, tree, path, and validator lock for compatibility, migration, or reference-consumer evidence. External bytes remain evidence-only and never become core contract or package authority. |
| `verification-result.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0` | Deterministic result of exact graph, policy, signature, and evidence verification. Every result binds nonempty exact evidence digests; `permitted` has no reasons, while `denied` has one or more values from the closed stable reason registry. Missing, invalid, stale, or unavailable evidence has a specific reason and cannot be represented as `policy_denied`. |
| `compatibility-attestation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/compatibility-attestation/1.0.0` | Evidence that exact source and render identities satisfy declared Agent Spec, harness, and consumer compatibility profiles. |
| `evaluation-attestation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/evaluation-attestation/1.0.0` | Closed artifact evaluation evidence tied to an exact subject and evaluator identity. It records evidence; it does not independently authorize promotion. |
| `policy-attestation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/policy-attestation/1.0.0` | Consumer policy evaluation result bound to exact subject, policy, nonce, and time. Consumer policy remains consumer authority. |
| `consumer-authority.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-authority/1.0.0` | Short-lived, consumer-signed opaque authority snapshot bound to exact consumer, target, revision, predecessor, candidate, audience, and nonce. Compile snapshots additionally sign the complete authorized-private-input digest; the field is compile-only. Agent Delivery validates and binds it but does not interpret itself as the authority for consumer grants. |
| `skill-approval.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/skill-approval/1.0.0` | Consumer-issued approval for an exact skill digest and declared execution conditions. It cannot be inferred from package presence, a mutable tag, or prior approval of different bytes. |
| `deployment-receipt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/deployment-receipt/1.0.0` | One append-only receipt per runtime-release subject, linking exact source, private delta, render, skills, consumer authority, complete target-wide activation-authorization descriptor and raw digest, deployment, rollout, and verification evidence. A historical receipt is evidence, never standing reactivation authority. |
| `operational-readiness-report.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/operational-readiness-report/1.0.0` | Signed GA-readiness evidence for the accepted reliability, scale, recovery, retention, compatibility, security-response, and support gates. |
| `archive-root.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/archive-root/1.0.0` | Signed immutable evidence-archive and retention root for offline verification and disaster recovery. Archive metadata does not become current desired state. |

### Lifecycle, desired-state, and reconciliation contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `transition-model.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0` | Closed machine-readable lifecycle model for states, transitions, actors, guards, compare-and-swap rules, effects, events, and retryability. The seven source models in `contracts/lifecycle/` validate directly against this schema. |
| `installation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/installation/1.0.0` | Durable relationship between a consumer and a public agent source, with lifecycle and exact predecessor identity. It carries no consumer credentials or grants. |
| `candidate.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/candidate/1.0.0` | Immutable candidate preparation record linking fetched, validated, evaluated, compiled, and signed exact content. |
| `target-delivery-state.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/target-delivery-state/1.0.0` | The single desired-state aggregate for one consumer/runtime target. The Promotion Coordinator is its sole logical writer; hosts, Git, compilers, bots, observations, and consumer applications only submit intent or evidence. |
| `desired-state-store-receipt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/desired-state-store-receipt/1.0.0` | Authenticated read/CAS/idempotency-resolution receipt from the selected DesiredStateStore. A commit-unknown result requires authoritative resolution and cannot be guessed or retried as an ordinary failure. |
| `desired-state-store-migration.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/desired-state-store-migration/1.0.0` | Quiesced, checkpointed source-to-target history migration with one explicit verified cutover. Live dual writing and informal failover are invalid. |
| `rollout.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/rollout/1.0.0` | Target-scoped rollout from prepared candidate through staging, canary, activation, verification, promotion, or forward-recovery requirement. |
| `runtime-slot.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-slot/1.0.0` | Durable mapping between a target, slot generation, exact runtime release, and observed slot lifecycle. It is not a second desired-state store. |
| `action.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/action/1.0.0` | Durable asynchronous work item with leases, stale-attempt fencing evidence, bounded retry, cancellation, and append-only terminal evidence. Losing a lease moves recoverable work to `retry_wait`; it does not create a terminal action state or domain authority. |
| `promotion-decision.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/promotion-decision/1.0.0` | Coordinator decision binding the canonical complete per-subject authority/canary/capability/activation evidence set, canonical complete per-subject deployment-receipt reference set, exact precondition, fencing token, and DesiredStateStore receipt. Only the referenced successful CAS is the managed desired-state commit point. |
| `canary-plan.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/canary-plan/1.0.0` | Fresh nonce-bound promotion challenge that fixes the exact target, revision, release, checks, audience, and expiry. |
| `canary-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0` | Purpose-separated technical and consumer capability evidence for the exact canary challenge. A transport error or absence is never an authorization denial. |
| `authorization-decision-proof.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0` | Consumer-owned authenticated authorization decision bound to the exact canary plan, capability, current policy/grants/workload identity, signer policy, successful transport, and freshness. It is evidence only, never package or grant authority. |
| `host-reconciliation-attempt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/host-reconciliation-attempt/1.0.0` | Host Reconciler attempt bound to exact desired revision, slot generation, lease, fencing token, and technical observations. The host cannot emit consumer capability authority. |
| `host-switch-journal-entry.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/host-switch-journal-entry/1.0.0` | Fenced, digest-chained host journal entry with durable pre-switch intent, exact old/new switch marker, active readback, and crash-resolution phases. Candidate content cannot write the journal or infer promotion. |
| `observation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/observation/1.0.0` | Append-only target observation about staged or active technical reality. Observation can trigger reconciliation decisions but cannot write desired state. |
| `recovery-plan.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/recovery-plan/1.0.0` | Forward-recovery plan that derives new functional content from eligible history using current trusted tooling, authority, evaluation, and canary evidence. It never reactivates an old deployment or signature. |
| `region-fence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/region-fence/1.0.0` | Two-person signed regional single-writer fence evidence used during controlled failover. It cannot be replaced by infrastructure reachability or an informal operator flag. |
| `command-request.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/command-request/1.0.0` | Closed command bodies for validation, rendering, importing, installation changes, proposals, promotion, recovery, cancellation, and publication. A valid body is intent; current authentication, authorization, preconditions, and policy still gate acceptance. |

### API, event, configuration, and product-workload contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `problem-details.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/problem-details/1.0.0` | Closed Agent Delivery profile of RFC 9457 problem details. Every problem identifies its exact port and operation and validates that operation's stable code/side-effect-state pair. Error output remains explanatory and redacted, not authority. |
| `cli-result.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/cli-result/1.0.0` | Stable single-document machine output for `bd-agent`, with mutually exclusive succeeded, accepted, denied, and failed result shapes. |
| `cli-stream-event.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/cli-stream-event/1.0.0` | Ordered JSON Lines start/progress/warning/result events. A client timeout or disconnect never implies cancellation of durable server work. |
| `event-data-envelope.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/event-data/1.0.0` | Agent Delivery data carried inside a CloudEvents envelope. Events are notifications and projection triggers only; a receiver must read the exact current authoritative resource before acting. |
| `application-config.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/application-config/1.0.0` | Closed non-secret process configuration containing endpoints, workload identity, and resource limits only. Raw credentials, private keys, and secret values are invalid; environment configuration cannot override contract or trust authority. |
| `identity-registration-manifest.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/identity-registration-manifest/1.0.0` | Product-owned registration manifest for Agent Delivery workload identities. It governs product workloads only and does not issue or encode consumer-agent roles, grants, provider access, or credentials. |

### Downstream integration control catalogs

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `action-catalog.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/action-catalog/1.0.0` | Closed registry for durable action kinds, terminal results, and retry/failure mappings exposed by the downstream ports. It standardizes orchestration vocabulary without granting permission to run an action. |
| `problem-catalog.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/problem-catalog/1.0.0` | Closed mapping from stable product problems to RFC 9457 types, HTTP statuses, CLI exit codes, retryability, and permitted side-effect states. The port registry selects the exact state per operation; no code has a global mutation conclusion. Problem output explains a decision or failure; it is not authority. |
| `event-types.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/event-types/1.0.0` | Closed notification-type registry binding each CloudEvent type to its exact data schema, source resource, and delivery semantics. Events remain non-authoritative notifications. |
| `downstream-port-registry.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/downstream-port-registry/1.0.0` | Closed inventory of downstream ports, operations, owners, request/response contracts, protocol profiles, failure mappings, and conformance suites. It describes integration surfaces; it does not transfer consumer or runtime authority. |
| `protocol-profiles.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/protocol-profiles/1.0.0` | Closed, versioned protocol requirements for every downstream adapter boundary, including framing, exact reference selection, failure behavior, evidence, and safety rules. |
| `protocol-fixtures.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/protocol-fixtures/1.0.0` | Closed executable OCI, supply-chain, and capability protocol corpus binding exact fixture bytes, materials, cross-document chains, and single-fault mutations. Passing fixtures are compatibility evidence only and cannot authorize execution, promotion, or deployment. |
| `downstream-conformance-cases.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/downstream-conformance-cases/1.0.0` | Closed conformance-requirement catalog covering permitted behavior and fail-closed denials across every owner and port suite. Prose fixture descriptions require compilation before an Adapter can execute them. |
| `downstream-conformance-plan.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/downstream-conformance-plan/1.0.0` | Closed adapter-consumable plan binding every source catalog, operation request/result schema and fixture, harness action, fault phase, and outcome/problem/side-effect oracle by exact digest. Structural fixtures are explicitly not semantic implementation goldens, and a compiled directive is not passing evidence until an exact Adapter executes it. |
| `port-type-catalog.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/port-type-catalog/1.0.0` | Closed offline catalog of generated field and operation schemas, exact source-schema digests, wire bindings, refinements, and per-type examples. Embedded schemas are accepted only through the catalog's exact released bytes. |
| `port-contract-fixtures.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/port-contract-fixtures/1.0.0` | Closed generated valid and denial fixture catalog for every downstream operation contract, with exact schema digests and required structural-denial coverage. Fixtures prove validator behavior but cannot authorize an operation. |

The ten catalog documents are product controls under `contracts/ports/v1/`
and `contracts/events/v1/`; each document binds its own schema at the root and
is indexed as a valid fixture. `type-catalog.json` and
`contract-fixtures.json` are deterministic projections of the reviewed port
registry and product schemas. `conformance-plan.json` is the deterministic
projection of the nine exact machine-authority inputs named in its root. Their exact
released bytes are distributed controls; a generator or explanatory prose is
not alternate schema authority. All embedded port schemas, fixtures, and plan
directives resolve offline and remain bounded, closed, and untrusted until
validated.

## External contracts and projections

The inventory deliberately does not create shadow schemas for externally owned
standards:

- Agent Spec documents are validated by the pinned official Agent Spec SDK.
  `agent-source` binds their exact bytes and validation evidence, but Agent
  Delivery does not redefine Agent Spec fields.
- OCI image/index manifests, SPDX SBOMs, in-toto statements, SLSA provenance,
  Cosign verification bundles, and Sigstore trusted-root material retain their
  external normative contracts. Agent Delivery schemas bind exact digests,
  media types, purpose profiles, and verification results around them.
- CloudEvents 1.0.2 owns the outer event envelope. Agent Delivery owns only the
  `data` contract above. RFC 9457 owns the base problem format; the closed
  product profile above narrows its use.
- The JSON Schema Draft 2020-12 metaschema URI identifies the compiled validator
  dialect. It is not a runtime network dependency. Every product `$ref` resolves
  from the signed local bundle.

OpenAPI, AsyncAPI, generated Go/Python/TypeScript models, SDKs, OASF discovery
views, read models, examples, documentation, and authored YAML are projections.
They must be generated or checked against the source schemas and cannot add,
remove, or reinterpret authoritative fields. YAML is accepted only through the
JSON-compatible authoring subset; canonical JSON data and RFC 8785 bytes define
semantic identity.

The API projections are checked as closed semantic graphs rather than bags of
individually valid references. OpenAPI freezes operation-to-parameter,
request-body, response, media-type, schema, and header bindings together with
the semantic parameter/header component definitions. AsyncAPI freezes the
server/channel/operation/message chain and the complete structured CloudEvents
envelope binding. In both documents, every schema component name maps to one
exact normative reference, schema ID, and canonical digest; a same-shape or
otherwise valid component substitution fails release validation.

The accepted v1 task set freezes the language-neutral schemas, OpenAPI,
AsyncAPI, downstream control catalogs, examples, documentation mappings, and
the deterministic offline-bundle contract. The closed
documentation map inventories every schema-referenced document path exactly
once, in sorted order, with the SHA-256 digest of its raw bytes. Repository
construction verifies those bytes; authenticated offline verification checks
the map's closed structure, digest grammar, portable paths, and exact reference
closure without consulting a checkout or network source. Production signing
and publication remain later release gates.

AD-01 intentionally releases no Go, Python, or TypeScript model/client
projection. AD-10 owns those language bindings after the externally visible
ports are frozen; from the first release that contains them, deterministic
regeneration and a clean-tree drift check are release-blocking.

Projection syntax is checked offline against exact upstream validator inputs,
not a mutable package or network URL. The bundle vendors the official OpenAPI
3.2 Draft 2020-12 schema dated `2025-11-23` at SHA-256
`7d48f01f37eeae4799041b371ad5f533f9f533fd2b0caa1011a8ba27c5b48b70`
and the AsyncAPI 3.1 all-in-one Draft 7 schema from `spec-json-schemas`
`v6.11.1` commit `e609fc2341007395d75df5756fc6fccf662c2087` at SHA-256
`51d3274899ad2875f25c18fd1aef4d5512f0a97be785d519740bde55a4162f61`.
Their licenses and the AsyncAPI notice are retained beside the schema bytes.
Those third-party schemas validate projection syntax only and do not become
Agent Delivery-owned object authority.

## Repository-only planning contract

`contracts/schemas/repository/development-plan.schema.json` has the internal ID
`https://schemas.bytedesk.ai/agent-delivery/repository/development-plan/1` and
validates the repository's executable development plan. It is intentionally
outside the `/v1/` product namespace and is not a product contract-bundle
member. `contracts/fixtures/schema/repository-index.json` contains its positive
and denial fixtures. Repository verification must also prove that the positive
fixture is byte-identical to `docs/planning/development-plan.json` and that the
repository schema, index, and fixtures are absent from product bundle-source
expansion.

## Fixtures and verification

`contracts/fixtures/schema/index.json` is the product fixture registry. The
current baseline contains 312 indexed cases. Every one of the 112 v1 schema IDs
has at least one valid instance, and every instance-bearing schema has an
indexed denial; the common definitions library is explicitly exempt. The index
directly validates all seven authoritative
`contracts/lifecycle/*.json` files and
`contracts/compatibility/functional-customization.v1.json`, plus all ten
downstream control documents; no duplicate source copies are used.

The denial corpus covers, at minimum, unknown fields, authority smuggling,
consumer identity in public artifacts, raw credentials, force/wildcard writes,
missing or invalid exact revisions and digests, mutable/tagged/schemed OCI
references, out-of-range registry ports, unsafe paths and file types,
unsupported JSON Patch operations, artifact-provided renderer plugins,
unfenced regional authority, and tag-only publication.

Required verification is:

1. validate every schema against Draft 2020-12;
2. load the closed 112-entry machine schema inventory and require exact equality
   with the discovered ID/path/canonical-digest triples; reject removal,
   addition, rename, ID substitution, digest drift, duplicate IDs or paths, and
   unresolved or non-bundle `$ref` values;
3. recursively prove that every directly typed array has bounded `maxItems`,
   every non-enumerated string has bounded `maxLength`, every integer has safe
   lower and upper bounds, and every object is fixed-shape closed or has
   bounded `maxProperties`; archive the counts and accepted ceilings in
   validator evidence;
4. validate the fixture index independently with the Go validator and Python
   `jsonschema` validator; before ordinary instance validation, each validator
   must bind any root `schema` descriptor to the fixture's selected schema ID
   and that source schema's exact canonical digest;
5. prove every schema has an indexed valid `positive` fixture, every
   separately instantiable product schema has an indexed denial fixture, and
   both validator engines observe each denial's indexed `expectedKeyword`
   subset or exact `expectedSemanticError`; the semantic corpus contains
   separate structurally valid wrong-ID and wrong-digest descriptor cases, and
   ordinary structural denials carry the correct descriptor so each remains a
   single-fault proof; `common.schema.json` is the sole denial-coverage
   exemption because its exact root is a reusable definitions library rather
   than an instance contract, and that exemption is emitted in validator
   evidence;
6. canonicalize each schema, record its exact digest, and build the signed
   offline contract bundle with the JCS schema inventory as a separately
   inventoried control;
7. validate lifecycle-model graph semantics and the functional customization
   profile in addition to structural schema validation; and
8. prove generated OpenAPI, AsyncAPI, examples, documentation, and bundle
   inventories have not drifted from the source contracts, plus every generated
   language binding released by the current milestone. AD-01 releases no such
   binding; AD-10 must add deterministic Go, Python, and TypeScript generation
   and clean-tree drift verification before it releases them.

Any invalid schema, closed-inventory mismatch, duplicate ID or path, unresolved
reference, unknown schema digest,
unknown authority-bearing field, fixture disagreement, or projection drift is a
release-blocking failure. Validation never falls back to a network schema,
mutable tag, local renderer, authored YAML, or generated type.
