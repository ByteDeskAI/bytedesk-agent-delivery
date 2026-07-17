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
product-schema registry and currently contains 49 entries. Its root is closed
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
| `consumer-deployment.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0` | Consumer-private deployment manifest embedding the full effective private rerender and exact approved public/private skill set. It is functional deployment content, not a credential or authorization grant. |
| `runtime-release.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-release/1.0.0` | Prepared runtime release identity binding the deployment, runtime artifact, inventory, and verification evidence used by reconciliation. |
| `catalog-index.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/catalog-index/1.0.0` | Signed public discovery index. Tags and channels help discovery but never replace exact subject digests. Public entries remain tenant-free. |
| `component-lock.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/component-lock/1.0.0` | Signed exact lock for reference implementation components, configuration, and dependency identities. |
| `renderer-release.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-release/1.0.0` | Complete renderer execution identity: platform, executable, schemas, allowlist, dependencies, toolchain, provenance, and output contract. Artifact-provided hooks and incomplete or fallback renderer identities are invalid. |
| `renderer-allowlist.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/renderer-allowlist/1.0.0` | Compiled set of accepted exact renderer-release digests. Selection cannot fall back to tags, `PATH`, a local build, or another installed renderer. |
| `contract-bundle.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/contract-bundle/1.0.0` | Manifest for the signed, content-addressed, offline contract bundle containing exact schemas, transitive references, lifecycle models, compatibility metadata, and derived API/event descriptions. |

### Trust, approval, verification, and retained-evidence contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `trust-policy.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy/1.0.0` | Immutable independently distributed verification policy, including tag-free OCI repository scopes, accepted schemas, signers, builders, evidence, revocations, and purpose separation. It is selected by exact identity and cannot be supplied by an untrusted artifact. |
| `signing-request.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/signing-request/1.0.0` | Closed request to a purpose-specific signing adapter binding request ID, exact subject digest, OCI repository, purpose, key version, nonce, a media type accepted by the shared bounded grammar, a profile-bounded validity window, and trust-policy ID/digest. The request does not itself confer signing authority, and public signing scopes cannot contain consumer identity. |
| `verification-result.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0` | Deterministic result of exact graph, policy, signature, and evidence verification. Every result binds nonempty exact evidence digests; `permitted` has no reasons, while `denied` has one or more values from the closed stable reason registry. Missing, invalid, stale, or unavailable evidence has a specific reason and cannot be represented as `policy_denied`. |
| `compatibility-attestation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/compatibility-attestation/1.0.0` | Evidence that exact source and render identities satisfy declared Agent Spec, harness, and consumer compatibility profiles. |
| `evaluation-attestation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/evaluation-attestation/1.0.0` | Closed artifact evaluation evidence tied to an exact subject and evaluator identity. It records evidence; it does not independently authorize promotion. |
| `policy-attestation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/policy-attestation/1.0.0` | Consumer policy evaluation result bound to exact subject, policy, nonce, and time. Consumer policy remains consumer authority. |
| `consumer-authority.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-authority/1.0.0` | Short-lived, consumer-signed opaque authority snapshot bound to exact consumer, target, revision, predecessor, candidate, audience, and nonce. Agent Delivery validates and binds it but does not interpret itself as the authority for consumer grants. |
| `skill-approval.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/skill-approval/1.0.0` | Consumer-issued approval for an exact skill digest and declared execution conditions. It cannot be inferred from package presence, a mutable tag, or prior approval of different bytes. |
| `deployment-receipt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/deployment-receipt/1.0.0` | Append-only receipt linking exact source, private delta, render, skills, authority, deployment, rollout, and verification evidence. A historical receipt is evidence, never standing reactivation authority. |
| `operational-readiness-report.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/operational-readiness-report/1.0.0` | Signed GA-readiness evidence for the accepted reliability, scale, recovery, retention, compatibility, security-response, and support gates. |
| `archive-root.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/archive-root/1.0.0` | Signed immutable evidence-archive and retention root for offline verification and disaster recovery. Archive metadata does not become current desired state. |

### Lifecycle, desired-state, and reconciliation contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `transition-model.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0` | Closed machine-readable lifecycle model for states, transitions, actors, guards, compare-and-swap rules, effects, events, and retryability. The seven source models in `contracts/lifecycle/` validate directly against this schema. |
| `installation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/installation/1.0.0` | Durable relationship between a consumer and a public agent source, with lifecycle and exact predecessor identity. It carries no consumer credentials or grants. |
| `candidate.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/candidate/1.0.0` | Immutable candidate preparation record linking fetched, validated, evaluated, compiled, and signed exact content. |
| `target-delivery-state.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/target-delivery-state/1.0.0` | The single desired-state aggregate for one consumer/runtime target. The Promotion Coordinator is its sole logical writer; hosts, Git, compilers, bots, observations, and consumer applications only submit intent or evidence. |
| `rollout.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/rollout/1.0.0` | Target-scoped rollout from prepared candidate through staging, canary, activation, verification, promotion, or forward-recovery requirement. |
| `runtime-slot.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-slot/1.0.0` | Durable mapping between a target, slot generation, exact runtime release, and observed slot lifecycle. It is not a second desired-state store. |
| `action.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/action/1.0.0` | Durable asynchronous work item with leases, stale-attempt fencing evidence, bounded retry, cancellation, and append-only terminal evidence. Losing a lease moves recoverable work to `retry_wait`; it does not create a terminal action state or domain authority. |
| `canary-plan.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/canary-plan/1.0.0` | Fresh nonce-bound promotion challenge that fixes the exact target, revision, release, checks, audience, and expiry. |
| `canary-evidence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0` | Purpose-separated technical and consumer capability evidence for the exact canary challenge. A transport error or absence is never an authorization denial. |
| `authorization-decision-proof.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0` | Consumer-owned authenticated authorization decision bound to the exact canary plan, capability, current policy/grants/workload identity, signer policy, successful transport, and freshness. It is evidence only, never package or grant authority. |
| `host-reconciliation-attempt.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/host-reconciliation-attempt/1.0.0` | Host Reconciler attempt bound to exact desired revision, slot generation, lease, fencing token, and technical observations. The host cannot emit consumer capability authority. |
| `observation.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/observation/1.0.0` | Append-only target observation about staged or active technical reality. Observation can trigger reconciliation decisions but cannot write desired state. |
| `recovery-plan.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/recovery-plan/1.0.0` | Forward-recovery plan that derives new functional content from eligible history using current trusted tooling, authority, evaluation, and canary evidence. It never reactivates an old deployment or signature. |
| `region-fence.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/region-fence/1.0.0` | Two-person signed regional single-writer fence evidence used during controlled failover. It cannot be replaced by infrastructure reachability or an informal operator flag. |
| `command-request.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/command-request/1.0.0` | Closed command bodies for validation, rendering, importing, installation changes, proposals, promotion, recovery, cancellation, and publication. A valid body is intent; current authentication, authorization, preconditions, and policy still gate acceptance. |

### API, event, configuration, and product-workload contracts

| Source | Stable `$id` | Role and authority boundary |
| --- | --- | --- |
| `problem-details.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/problem-details/1.0.0` | Closed Agent Delivery profile of RFC 9457 problem details. Error output is explanatory and redacted, not authority. |
| `event-data-envelope.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/event-data/1.0.0` | Agent Delivery data carried inside a CloudEvents envelope. Events are notifications and projection triggers only; a receiver must read the exact current authoritative resource before acting. |
| `application-config.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/application-config/1.0.0` | Closed non-secret process configuration containing endpoints, workload identity, and resource limits only. Raw credentials, private keys, and secret values are invalid; environment configuration cannot override contract or trust authority. |
| `identity-registration-manifest.schema.json` | `https://schemas.bytedesk.ai/agent-delivery/v1/identity-registration-manifest/1.0.0` | Product-owned registration manifest for Agent Delivery workload identities. It governs product workloads only and does not issue or encode consumer-agent roles, grants, provider access, or credentials. |

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

AD-01 freezes the language-neutral schemas, OpenAPI, AsyncAPI, examples,
documentation mappings, and deterministic offline-bundle contract. The closed
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
current baseline contains 136 indexed cases. Every one of the 49 v1 schema IDs
has at least one valid instance, and every instance-bearing schema has an
indexed denial; the common definitions library is explicitly exempt. The index
directly validates all seven authoritative
`contracts/lifecycle/*.json` files and
`contracts/compatibility/functional-customization.v1.json`; no duplicate source
copies are used.

The denial corpus covers, at minimum, unknown fields, authority smuggling,
consumer identity in public artifacts, raw credentials, force/wildcard writes,
missing or invalid exact revisions and digests, mutable/tagged/schemed OCI
references, out-of-range registry ports, unsafe paths and file types,
unsupported JSON Patch operations, artifact-provided renderer plugins,
unfenced regional authority, and tag-only publication.

Required verification is:

1. validate every schema against Draft 2020-12;
2. load the closed 49-entry machine schema inventory and require exact equality
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
