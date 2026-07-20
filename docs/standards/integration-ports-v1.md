# Integration ports v1

**Profile:** `bytedesk.integration-ports/1`

**Status:** Accepted downstream contract. The machine-readable registries,
profiles, schemas, conformance requirements, and compiled execution plan
referenced here are the v1 authority.

## Purpose and authority

This profile freezes every externally visible port used to implement Agent
Delivery. It defines how callers select an operation, validate requests and
results, resolve uncertain commits, enforce trust and consumer isolation, and
prove provider conformance. It complements
[Machine contracts v1](machine-contracts-v1.md): that profile governs product
objects and canonical bytes, while this profile governs interactions across
process, provider, host, and consumer boundaries.

The authority order is:

1. [`port-registry.json`](../../contracts/ports/v1/port-registry.json), profile
   `bytedesk.downstream-port-registry/1`, owns the 26 closed port IDs, 86
   operation IDs, request and result contract names and fields, each field's
   exact `valueType`, operation-specific `{code, sideEffectState}` error mappings,
   idempotency, failure and uncertainty semantics, authentication,
   authorization, compatibility, ownership, type-catalog path, and owner-suite
   assignment.
2. [`type-catalog.json`](../../contracts/ports/v1/type-catalog.json), profile
   `bytedesk.port-type-catalog/1`, owns 137 reusable base-type schemas, 761
   unique field-value schemas, 172 closed request/result schemas, every schema
   ID and canonical digest, the 68-source offline registry, and the exact
   registry and fixture-catalog digest bindings. Its 111 field-level semantic
   refinements and operation-level discriminated aggregate contracts are closed
   and cannot be inferred from the registry's presentation-only `type` labels.
3. [`contract-fixtures.json`](../../contracts/ports/v1/contract-fixtures.json),
   profile `bytedesk.port-contract-fixtures/1`, owns one canonical valid fixture
   group for each of the 172 contracts, 516 structural-denial payloads, and 14
   aggregate semantic-denial payloads: 530 denial mutations in total.
4. [`problem-catalog.json`](../../contracts/ports/v1/problem-catalog.json),
   profile `bytedesk.problem-catalog/1`, owns all 60 stable problem codes, RFC
   9457 type and status, retryability, the closed set of side-effect states that
   may be assigned to each code by operations, and CLI exit code. The
   `problem-details` projection closes all 60 per-code tuples and 86
   per-operation variants. It does not choose one global side-effect state for
   a code used by different operations.
5. [`action-catalog.json`](../../contracts/ports/v1/action-catalog.json), profile
   `bytedesk.action-catalog/1`, owns each durable action's port operation,
   request, terminal result class, cancellation boundary, idempotency identity,
   owner, and terminal failure codes.
6. [`event-types.json`](../../contracts/events/v1/event-types.json), profile
   `bytedesk.event-types/1`, owns the closed event names, aggregate bindings,
   payload schema descriptors, and sequence semantics. AsyncAPI is its transport
   projection, not a second event registry.
7. [`protocol-profiles.json`](../../contracts/ports/v1/protocol-profiles.json),
   profile `bytedesk.protocol-profiles/1`, owns the cross-operation ordering,
   transport, persistence, recovery, and compatibility rules described below.
8. [`conformance-cases.json`](../../contracts/ports/v1/conformance-cases.json),
   profile `bytedesk.downstream-conformance-cases/1`, owns the positive, denial,
   recovery, task-suite, and port-owner-suite requirements. Its prose fixture
   descriptions are requirements, not executable adapter inputs by themselves.
9. [`conformance-plan.json`](../../contracts/ports/v1/conformance-plan.json),
   profile `bytedesk.downstream-conformance-plan/1`, is the deterministic
   adapter-consumable compilation of those requirements. It binds all nine input
   catalogs by exact digest, provides one request/result schema golden for every
   operation, compiles every case into ordered harness actions and fault phases,
   and gives every step a closed outcome/problem/side-effect oracle. Every
   referenced `contract-fixtures.json` valid payload is explicitly labeled
   `schema-valid-structural-sample`; neither it nor the plan is semantic
   implementation evidence. An Adapter must execute the named directive before
   it can claim the case passed.
10. [`protocol-fixtures.json`](../../contracts/ports/v1/protocol-fixtures.json),
   profile `bytedesk.protocol-fixtures/1`, owns the byte-exact OCI,
   supply-chain, and capability protocol corpus: 49 protocol documents, 11
   required materials, their cross-document chains, and 71 single-fault denial
   mutations. Its accepted shape is
   [`protocol-fixtures.schema.json`](../../contracts/schemas/v1/protocol-fixtures.schema.json).
   The corpus is executable conformance evidence only; it cannot authorize an
   operation, approve a capability, or grant promotion or deployment authority.
11. The exact product schema selected by ID and canonical digest owns the shape
   of every referenced product object. Generated interfaces, OpenAPI, AsyncAPI,
   CLI help, examples, and this prose are projections and cannot contradict or
   expand those authorities.

Each authority document is itself validated by its exact closed Draft 2020-12
control schema and canonical schema digest from the signed offline contract
bundle. A checked-out file, same-shape replacement, generated type, or prose
copy cannot replace an authenticated bundle member.

An implementation MUST reject a port, operation, request field, result variant,
error code, provider behavior, or protocol sequence that is absent from those
closed authorities. There is no prose-only extension mechanism.

## Universal request and result contract

Every call selects one exact `bytedesk.port.<name>/<major>` and one exact
operation ID from the port registry. The selected registry entry determines the
logical request and result contract names. Callers and providers MUST NOT infer
an operation from a URL, executable name, provider method, mutable tag, payload
shape, or local implementation type.

A standard consumer resolves the contract without repository tooling:

1. authenticate the signed offline bundle and its manifest;
2. load and validate the exact registry member, then follow only its declared
   `typeCatalog` path;
3. compute the registry's RFC 8785 SHA-256 digest and require it to equal the
   type catalog's registry digest;
4. require the catalog's exact 137 base types, 761 one-field `valueType`
   schemas, 172 request/result schemas, and 68 embedded offline schema sources,
   with no orphan, duplicate, cyclic, open, or network-resolved schema;
5. resolve every registry field through its unique `valueType`, and every
   logical request/result name through its exact closed contract schema ID and
   digest; and
6. verify the catalog-bound fixture path, profile, canonical digest, 172 fixture
   groups, 516 structural denials, 14 aggregate semantic denials, their exact
   530-mutation total, and registry digest before using fixtures; and
7. verify the conformance plan schema and its exact port, type, contract-fixture,
   problem, action, event, protocol-profile, case, and protocol-corpus input
   digests before dispatching a harness step. Every operation step repeats the
   exact protocol-profile applicability list from its port. A future Adapter
   consumes the closed directive ID, action, phase, profiles, contract
   references, and oracle; it does not reinterpret the source prose.

The released JSON documents and a conforming Draft 2020-12 validator are
sufficient. Consumers do not run the repository generator, import repository
Python, fetch a schema from the network, or treat generated Go, Python, or
TypeScript bindings as authority.

The following rules apply to every operation:

- A request contains exactly the fields declared by its registry operation.
  Required fields cannot be omitted or `null` unless their declared type
  explicitly includes null. Unknown fields fail before a side effect.
- A product object is accepted only under its exact schema ID and independently
  trusted schema digest from the signed offline bundle. A same-shape schema or
  network-fetched replacement is not equivalent.
- Digest-bearing JSON uses the JSON data model and RFC 8785 JCS bytes. Arbitrary
  file, archive-member, and binary payload bytes remain byte-exact.
- A logical `bytes` value uses canonical unpadded base64url in contract and
  conformance JSON: at most 4 MiB decoded and 5,592,406 encoded characters.
  Decoders enforce both bounds and canonical tail bits before the value can
  influence authority. A transport Adapter may stream the same raw bytes, but
  it must preserve the declared size, digest, ordering, and exact logical
  request/result binding; streaming is not an alternate contract.
- Each request binds the authenticated caller, authorization scope, consumer and
  target where applicable, canonical request digest, exact input descriptors,
  and current time or nonce when the operation contract requires them.
- A non-idempotent operation uses the registry-declared idempotency key. The key
  is permanently bound to the canonical request digest and isolation scope.
  Reuse for different bytes is `idempotency_collision` and has no side effect.
- A successful replay returns the original result or exact committed evidence;
  it does not repeat the external side effect or create a second aggregate,
  signature, projection, switch, receipt, or publication.
- Read results identify the exact authoritative revision/digest, immutable
  object digest, cursor snapshot, or readback evidence that was actually read.
  A cache, watch, event, tag, channel, local status, or intent record cannot be
  represented as authoritative state.
- Results are closed to the selected result variant. A provider cannot return a
  partial success, warning-only substitute, unverified descriptor, or a domain
  denial encoded as a transport failure.
- Cancellation is effective only before the action catalog's named commit
  boundary. A client disconnect, watch timeout, lease expiry, or cancellation
  request never erases an acknowledged side effect.

## Stable failures and uncertain commits

Every operational failure uses one code from the problem catalog and the closed
Agent Delivery RFC 9457 shape. The catalog, rather than adapter text, fixes the
problem type, HTTP status, retryable flag, permitted side-effect-state set, and
CLI exit code. The problem carries the exact `portId` and `operationId`; that
selected registry operation fixes the one exact `{code, sideEffectState}` pair
returned for the failure. A provider cannot copy a state from another operation
merely because it uses the same code. Diagnostics are explanatory, bounded,
and redacted; they are not authority.

The stable side-effect states are:

- `none`: the operation is read-only or the client stopped waiting; no mutation
  conclusion follows.
- `not-committed`: the operation proved that its intended mutation did not
  commit.
- `committed-unchanged`: a durable terminal fact already exists and was not
  changed by the failed or cancelled request.
- `commit-unknown`: the transport ended without proving whether the external
  commit occurred.

Every failure on a `fail-closed-read-only` or
`fail-closed-no-side-effect` operation maps to `none`, including a stable code
that maps to a mutation state elsewhere. A mutating operation uses
`not-committed` only when it proves its declared commit did not occur.
`committed-unchanged` is restricted to a durable terminal fact that the failed
request did not change. `commit-unknown` is allowed only when that operation has
a real commit boundary and declares an exact resolution procedure in
`commitUncertainty`.

The registry's operation-specific `failureSemantics`, `commitUncertainty`, and
error mappings are mandatory. `commit-unknown` MUST NOT be retried blindly. The
caller first performs the declared resolution operation, such as resolving the
idempotency key, reading the exact artifact digest, reading the archive root,
reading the region epoch, or recovering the host journal and active pointer. It
retries only after resolution proves the original commit absent and the
original preconditions remain current.

Failure to receive a schema-valid, authenticated problem is not evidence that a
mutation failed before commit. A disconnect or malformed response at a mutating
boundary invokes that operation's `commitUncertainty` procedure even when no
problem object is available. `dependency_unavailable` may be mapped to
`not-committed` only when the provider proves the declared commit did not occur;
otherwise it must return the operation's registered uncertainty code when it
can respond, or let the caller resolve the missing response as uncertain.

A problem marked retryable means that the caller may retry through that exact
resolution and idempotency procedure. It does not authorize a different
renderer, registry, key, store, region, schema, provider, source commit, or
weaker policy. Unknown operations or codes, a code/state pair absent from the
selected operation, a state outside the code's catalog permission set,
mismatched code/type/status tuples, missing operation or side-effect identity,
or unredacted diagnostics are protocol violations.

Consumer authorization outcomes remain domain evidence. In particular,
`policy_denied` requires an authenticated, current, nonce-bound consumer
decision. A timeout, `404`, connection failure, malformed response, absent
result, unknown signer, expired result, or unavailable capability is an
operational failure and can never be converted into denial evidence.

Domain results and operational failures are disjoint. `permitted` and `denied`
are authenticated domain outcomes. Transport failure, dependency unavailability,
malformed or stale evidence, and indeterminate commit state use the registered
problem and uncertainty contracts; they are never synthetic domain outcomes.

## Security, trust, and redaction

Each registry operation's `authentication` and `authorization` fields are
minimum requirements. A provider profile may narrow them but cannot broaden
them. Workload identities are purpose- and scope-specific; a CLI user, API
client, renderer, Git broker, compiler, host, capability verifier, signer,
archive worker, or regional recovery actor cannot reuse another actor's
identity or authority.

Public catalog and public-render operations are tenant-free. Private operations
are isolated by exact consumer, installation, subject, target, repository,
purpose, and key scope as applicable. Logs, events, CLI stderr, problems,
diagnostics, traces, receipts, and telemetry MUST NOT expose credential values,
private keys, bearer or refresh tokens, opaque secret values, raw private
payloads, unrestricted consumer customization, or authority subdocuments.

Every package, skill, file, archive, renderer output, OCI graph, event, external
input, provider response, and restored byte stream is untrusted until its exact
contract, digest, bounds, policy, and provenance pass. Validation, rendering,
compilation, scanning, packaging, staging, activation, and archive restore never
execute artifact- or skill-provided code, hooks, installers, or dependency
lifecycle commands.

Agent Delivery owns functional delivery lineage. It does not become authority
for a consumer's users, organizations, roles, grants, MCP/tool/resource access,
provider authority, credential issuance, workload identity, call-time
authorization, or business approval. Consumer adapters return opaque signed
references and decisions; consumer-specific fields remain outside core
contracts.

## Compatibility and provider profiles

The port major, operation ID, request contract, result contract, stable
operation-specific problem/state mapping, side-effect meaning, security
interpretation, and commit point are immutable. Removing or renaming any of
them, changing a field's meaning, adding a required request field, narrowing
accepted input, or changing a terminal outcome requires a new port major.

An additive result field is compatible only when the registry declares minor
compatibility for that result and supported old clients are proved to ignore it
safely. Requests, authority objects, mutation results, denial variants, and
security-sensitive enums remain closed. Old-client/new-provider,
new-client/supported-old-provider, replay, uncertain-commit recovery, stored
object replay, and offline receipt verification are mandatory compatibility
directions.

Registry, SCM, KMS, renderer, consumer, DesiredStateStore, host, capability,
archive, and regional implementations are supported only through a named
profile with exact implementation version, configuration digest, dependency
digests, and passing conformance evidence. A missing or unavailable supported
profile fails closed without fallback.

## Renderer, worker, and compatibility boundary

Renderer selection uses `bytedesk.port.renderer-strategy/1`, execution uses the
adapter and sandbox ports, and every release promises the five renderer-owned
schemas for capability, input parameters, harness configuration, compatibility
result, and render manifest. The normative schema sources are:

- [`renderer-capability.schema.json`](../../contracts/schemas/v1/renderer-capability.schema.json)
- [`renderer-input-parameters.schema.json`](../../contracts/schemas/v1/renderer-input-parameters.schema.json)
- [`harness-configuration.schema.json`](../../contracts/schemas/v1/harness-configuration.schema.json)
- [`renderer-compatibility-result.schema.json`](../../contracts/schemas/v1/renderer-compatibility-result.schema.json)
- [`render-manifest.schema.json`](../../contracts/schemas/v1/render-manifest.schema.json)

The product-owned cross-port authority objects are
[`renderer-selection.schema.json`](../../contracts/schemas/v1/renderer-selection.schema.json)
and
[`renderer-execution-receipt.schema.json`](../../contracts/schemas/v1/renderer-execution-receipt.schema.json).
`select-renderer` requires the target platform and exact release descriptor and
returns one closed selection. Strategy render, Adapter render and validation,
and sandbox execution all consume that same object. Sandbox execution returns
the closed actual-execution receipt, its independently computed digest, and an
exact authentication-evidence descriptor; output validation cross-checks all
three against the selection, framed bytes, collected output, and render
manifest. Ambient host architecture, `PATH`, tags, runtime configuration, and
artifact content are never selection inputs.

Profile `bytedesk.renderer-contract/1` requires a complete exact signed renderer
release selected through the compiled allowlist. Artifact hooks, runtime
plugins, tags, `PATH`, local builds, another installed renderer, and fallback are
forbidden. Public rendering receives only public source and declared public
skills and emits tenant-free output. Private compilation reconstructs the
complete effective functional definition and exact approved skill set, performs
a full rerender with the exact public-lineage renderer release, and embeds the
effective result in the private deployment. It never post-patches public output.

Profile `bytedesk.worker-framing/1` fixes one request per process, unsigned
32-bit big-endian length-prefixed RFC 8785 JSON frames, a 4 MiB request limit, a
4 MiB response limit, and 64 KiB of bounded untrusted diagnostics. The signed
launcher creates private anonymous pipes for the worker's framed stdin/stdout
and diagnostic stderr; they are not the container standard streams. It writes
the bounded response and diagnostics only to declared attempt-output files,
then hashes/redacts evidence and destroys the private diagnostics with the
attempt. Launcher container stdout and stderr are empty or contain only fixed,
non-content lifecycle codes. Renderer-derived bytes are forbidden from CRI,
node, Kubernetes-event, and telemetry logs. The launcher uses a monotonic
deadline; closes inherited descriptors except its private worker pipes and
owned directories; denies network and secrets; uses read-only input and root
filesystems; and permits writes only to empty launcher-owned, bounded output and
temporary directories. Malformed, oversized, timed-out, or extra frames are
`worker_protocol_failed`; any renderer-derived container/platform log content
is `artifact_unsafe`; invalid collected output is `renderer_output_invalid`.

Native rendering emits Native Agent Spec only. WayFlow 26.1.2 is invoked solely
through `bytedesk.port.wayflow-compatibility/1` against exact native output and
an accepted external-input lock. It produces compatibility evidence only. It is
not a selectable output, renderer identity, production route, runtime
dependency, or replacement for Native Agent Spec authority.

## Private compilation boundary

`bytedesk.port.private-compiler/1#compile-private-deployment` accepts exactly
one closed
[`private-compilation-input.schema.json`](../../contracts/schemas/v1/private-compilation-input.schema.json)
lock, an idempotency key, and the caller-computed `compileRequestDigest`. The
lock binds the complete consumer/subject/installation/harness/target and
candidate/revision/predecessor/runtime-slot/activation-mode scope; public,
binding, customization, effective
skill and exact approval inputs; current authority snapshot and authorized
input digest; exact contract bundle and renderer selection; and all current
consumer policy/security-control subdigests. Collections are unique and
canonically ordered. The compiler independently recomputes every nested digest
and the complete lock before work or idempotency state is committed.

The authorized-input preimage is exactly
`{"profile":"bytedesk.authorized-private-compilation-input/1","contract":lock.contract,"schema":lock.schema,"inputs":inputs-minus-authoritySnapshot-and-authorizedPrivateInputDigest}`.
The resolved `bytedesk.consumer-authority/1` snapshot is closed and requires a
consumer-signed `authorizedPrivateInputDigest` only when `operation` is
`compile`; activate and recover snapshots forbid it. The authority Adapter
returns a successful verification result only for a permitted current snapshot
whose signed digest equals `expectedPrivateInputDigest`. A denied decision is
`authority_denied`, while a mismatch is `digest_mismatch`; neither returns a
success result or an authorized digest.

`compileRequestDigest` is SHA-256 over RFC 8785 JCS of exactly
`{"profile":"bytedesk.private-compilation-request/1","consumerId":...,"idempotencyKey":...,"compilationInputDigest":...}`.
It is required on the request and supplied to `resolve-compile-attempt`.
Success returns role-constrained exact descriptors for the canonical full lock,
consumer deployment, and separately signed compilation evidence; it does not
return ambiguous bare deployment/evidence digests. Resolve returns all three
descriptors only for `committed`, no artifacts for every other outcome, and a
closed problem for `denied` or `indeterminate`. A changed expanded input under the
same consumer/key pair is `idempotency_collision`; uncertain commit is resolved
by the exact request digest and never by guessing dynamically resolved inputs.
These policy and authority digests constrain compilation but do not grant
users, roles, credentials, workload identity, MCP/tool/provider access, or
business approval.

## OCI, archive, signing, and evidence

Profile `bytedesk.oci-archive-layout/1` makes repository plus SHA-256 digest the
only reference authority. Tags and channels are discovery metadata. Structured
manifests are JCS JSON. Layers have the fixed role order `portable-definition`,
`public-skills`, `public-render`, `private-customization`,
`approved-private-skills`, `effective-private-render`, `evidence`. Public
artifacts are tenant- and secret-free; private artifacts are consumer-scoped and
contain the complete effective render with redacted lineage.

Archives are deterministic POSIX ustar. UID and GID are zero, owner names are
empty, mtime is zero, only regular files and directories are accepted, portable
paths are unique, and links and special files are rejected. Expanded content is
limited to 64 MiB, one member to 16 MiB, and the archive to 20,000 members.
Archive-root create uses `absent`; update uses exact prior revision and digest.
Restore verifies exact bytes and current trust before republication and never
activates a deployment.

Profile `bytedesk.supply-chain-pins/1` requires full workflow commit SHAs,
container digests, exact language versions and lock digests, schema ID plus
schema digest, policy ID plus policy digest, complete signed renderer release
plus executable digest, scanner image plus rules/database snapshot digest, and
source repository plus immutable commit and tree digest. Floating tags, ranges,
branch heads, ambient installations, path binaries, and unversioned plugins are
forbidden.

Every paginated catalog, OCI-referrer, and desired-state-history read carries an
explicit snapshot digest. The first request has both cursor and snapshot digest
`null`; a continuation has both non-null and MUST present the exact digest
returned by the first page. A cursor alone, a digest alone, or a cursor replayed
against another snapshot fails. `head-artifact` returns a success body only for
an exact digest that exists and therefore fixes `exists: true`; absence is the
`resource_not_found` problem and never a success body with contradictory
descriptor metadata.

`bytedesk.port.kms-signing/1#sign-digest` accepts only the closed
[`kms-signing-request.schema.json`](../../contracts/schemas/v1/kms-signing-request.schema.json)
refinement of the general signing request. That refinement requires
`credentialKind: kms_key` and independently forbids
`contract-bundle-release-v1` plus both authoritative contract-bundle JSON and
tar media types. A keyless or contract-bundle request is `invalid_request` and
MUST be rejected before signer selection, a provider call, evidence creation,
or any signing side effect. Accepted requests sign an exact digest under one
immutable key version and purpose. The result validates against
[`signing-result.schema.json`](../../contracts/schemas/v1/signing-result.schema.json)
and binds the request digest, purpose, algorithm, public-key digest, subject,
signature bundle, trust policy, and provider audit evidence. Private skill,
consumer authority, and deployment purposes use isolated consumer keys; Agent
Delivery never possesses the consumer-authority signing role. Uncertain signing
is resolved by request ID and canonical request digest before any retry.
`resolve-signing-request` is a closed aggregate: `signed` requires the complete
signature envelope, while `not-seen`, `denied`, and `indeterminate` require that
envelope to be `null`. A status and payload from different variants is a
contract violation. The authoritative signer-audit reference is exactly
`signatureEnvelope.providerAuditEvidence.digest`, computed over the archived,
authenticated provider-audit bytes. A second top-level signer-evidence digest
is forbidden because two independently populated references could disagree.

SBOM, provenance, vulnerability, and license operations run read-only over
exact artifact and tool inputs. Every operation uses the closed request/result
envelope from the type catalog; the result's report object MUST hash to its
declared report digest and MUST bind the exact request inputs. SPDX,
in-toto/SLSA, scanner/advisory snapshot, severity policy, and license policy
versions are exact profile inputs.

License evaluation uses the strict SPDX 2.3 expression profile
`spdx-license-expression-2.3-strict/1` and SPDX License List data version
`3.28.0`. The exact SHA-256 pins over the tagged upstream JSON file bytes are
`sha256:f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee`
for `json/licenses.json` and
`sha256:bd145bb558f44432fcd6f0d7e956ed0124dff72af7641a7cfcb1b557dc390a5b`
for `json/exceptions.json`; the parser distribution is independently fixed by
`evaluatorImageDigest`. A valid policy evaluation returns one authenticated
domain result: `pass`, `deny`, or `indeterminate`. Unknown or unresolved
license expressions are `indeterminate` and cannot promote. A policy or pinned
parser input that cannot be loaded returns the operation problem
`dependency_unavailable` with no report; syntactically invalid evidence returns
`evidence_invalid` with no report. A policy denial is a valid `deny` report,
not an operation error. `LicenseRef` and `DocumentRef` expressions resolve only
from extracted licensing information in the exact SBOM bytes and dispositions
in the exact license-policy bytes; an absent or unknown reference is
indeterminate.

Evidence records provenance or evaluation and does not authorize deployment.
Archive operations are append-only and content addressed; history and legal
holds are never edited in place.

## DesiredStateStore protocol

There is exactly one `TargetDeliveryState` and one selected DesiredStateStore
class—managed or consumer-native—for each consumer/runtime target. The Promotion
Coordinator is the sole logical writer. Hosts, Git, compilers, bots,
observations, consumer applications, API clients, events, and watches are not
writers.

`bytedesk.port.desired-state-store/1` freezes these operations:

- `read-target-state` is an authoritative read returning state, exact revision,
  canonical digest, and current region epoch.
- `watch-target-state` is an authenticated notification hint. Its token is
  opaque and scoped to the target and port major. Every notification, reconnect,
  unknown token, or gap causes an authoritative conditional read. A disconnected
  host polls at least every 30 seconds. The watch payload is never state
  authority. A normal page has `resyncRequired: false` and a non-null next
  token. A gap has `resyncRequired: true`, an empty changes array, and a null
  token; a provider cannot return partial changes across a gap.
- `compare-and-swap-target-state` accepts create only with explicit
  `precondition.kind: absent`. Update requires `kind: match` plus exact current
  revision and digest. Omitted, null, wildcard, force, digest-only, wrong writer,
  and stale region epoch forms fail without side effects.
- `resolve-idempotency` returns only the closed not-seen, committed, rejected,
  or indeterminate variants for the exact target, key, and canonical request
  digest. `committed` requires the exact commit receipt; every other resolution
  requires a null receipt.
- `read-target-history` returns immutable digest-addressed revisions and fails
  on a history gap.
- `migrate-target-state` requires Coordinator quiescence, checkpointed
  copy/verify/cutover, and exact schema identity. Dual write is forbidden. The
  old source is read-only after cutover; reversal is a new audited migration
  from current authority. Its durable migration object validates against
  [`desired-state-store-migration.schema.json`](../../contracts/schemas/v1/desired-state-store-migration.schema.json).
  The request and result carry one durable migration ID, idempotency key, and
  canonical request digest; the result migration ID MUST equal its checkpoint's
  migration ID. A retry or uncertain response resolves that same identity and
  never starts an unnamed second copy.

Every CAS and resolution result is authenticated evidence. The canonical
receipt schema is
[`desired-state-store-receipt.schema.json`](../../contracts/schemas/v1/desired-state-store-receipt.schema.json).
For a lost CAS response, the Coordinator MUST call `resolve-idempotency`, read
the authoritative target state, and compare the exact intended digest. It may
retry only if the request is proved not committed and the same exact
precondition and region epoch remain current.

## Promotion Coordinator ordering and crash recovery

The Promotion Coordinator persists the canonical command and idempotency record,
claims one attempt with a monotonically increasing fencing token, reads current
target state and consumer authority from authoritative sources, and revalidates
every target, digest, region epoch, rollout generation, slot generation, nonce,
and validity interval before a commit-capable step. A stale attempt cannot
complete, publish evidence, authorize activation, or write desired state.

For isolated-candidate activation, the exact order is:

1. read and fence target state;
2. compile and verify every deployment in the canonical runtime-release graph;
3. stage every canonical deployment under the same runtime-release descriptor,
   `releaseDigest`, and `deployableGraphDigest`;
4. preflight every staged deployment in the isolated candidate;
5. append the complete canonical per-subject candidate-ready evidence set;
6. dispatch every nonce-bound capability check required by policy;
7. verify the complete consumer capability result set;
8. evaluate the complete canonical per-subject technical, capability, consumer
   authority, and authorization-decision sets;
9. resolve and authenticate fresh activation-stage status eligibility for the
   exact product release and every renderer release in the runtime-release
   graph;
10. issue one signed exact-graph activation authorization;
11. have the Host validate the Coordinator's historical eligibility
    verification, produce a distinct fresh use-time verification, and perform
    one atomic target-wide switch with one graph-bound journal;
12. read back every deployment in canonical subject order and require exact
    graph coverage;
13. compare-and-swap target state using the complete evidence set; and
14. append the complete canonical per-subject deployment-receipt set.

For guarded-in-place activation, the exact order is:

1. read and fence target state;
2. compile and verify every deployment in the canonical runtime-release graph;
3. stage every canonical deployment under the same runtime-release descriptor,
   `releaseDigest`, and `deployableGraphDigest`;
4. preflight every staged deployment without a capability claim;
5. evaluate the complete canonical pre-switch technical, consumer-authority,
   and authorization-decision sets;
6. resolve and authenticate fresh activation-stage status eligibility for the
   exact product release and every renderer release in the runtime-release
   graph;
7. issue one signed exact-graph provisional activation authorization;
8. have the Host validate the Coordinator's historical eligibility
   verification, produce a distinct fresh use-time verification, and perform
   one atomic target-wide switch with one graph-bound journal;
9. read back every deployment in canonical subject order and require exact
   graph coverage;
10. dispatch every nonce-bound capability check required by policy;
11. verify the complete consumer capability result set;
12. evaluate the complete canonical per-subject evidence set;
13. compare-and-swap target state using that complete set; and
14. append the complete canonical per-subject deployment-receipt set.

The successful target-state CAS is the managed promotion commit point. Registry
publication, consumer projection, host switch, and region-epoch activation are
separate external commit points and use their declared idempotency/readback
resolution. Cancellation is allowed only before the next irreversible commit
point. Client timeout does not cancel an action. After target-state CAS, reversal
is a new forward-recovery revision.

`evaluate-evidence` has three non-overlapping aggregate results. `permitted`
requires a passed evaluation attestation and an empty missing-evidence set;
`denied` requires a failed attestation and an empty missing-evidence set; and
`indeterminate` requires `manual_review` plus at least one missing-evidence ID.
Missing evidence can never coexist with permission. `authorize-activation`,
`cancel-rollout`, and `prepare-region-fence` each carry a mandatory idempotency
key and canonical request digest because their registry entries promise
idempotent uncertain-commit resolution; prose alone is not an idempotency
identity.

`authorize-activation` resolves the submitted immutable runtime-release
descriptor and the complete `RR -> CE -> D -> L/render` closure itself. It does
not accept a caller's eligibility conclusion. The Coordinator generates new
status nonces, applies its persisted high-water state, authenticates a fresh
`bytedesk.release-status-eligibility-evidence/1` object for the product release
and the canonically ordered set of every renderer release actually reachable
from that graph, and issues a short-lived
`bytedesk.activation-authorization/1` through the consumer-scoped trusted-KMS
Adapter. The authorization binds the exact rollout and host attempt, runtime
release, `releaseDigest`, complete ordered deployable graph, and
`deployableGraphDigest`. Its candidate-ready evidence, consumer-authority
snapshots, and authorization-decision proofs are separate canonical per-subject
arrays, are strictly ordered by subject identity, and each cover the deployable
graph exactly once with no missing, duplicate, reordered, or substituted entry.
It also binds status eligibility, expected and next generations, fencing token,
region epoch, operation time, expiry, and every canonical digest.
The successful result echoes `activationAuthorizationDigest`, `releaseDigest`,
`deployableGraphDigest`, the exact release-eligibility descriptor and semantic
digest, its full permitted verification result and evidence digest,
`authorizationNonce`, `slotId`, and `operationTime`. Every echo must equal the
signed authorization and canonical request; none is an independently mutable
claim.

`activate-candidate` receives the complete signed activation authorization and
its canonical digest, not a naked digest. The Host first resolves and validates
the Coordinator's historical permitted eligibility-verification result and its
binding inside the authorization. At the supplied `operationTime` it then
independently resolves the current authenticated status heads and active trust
pin set, re-verifies the exact activation-stage eligibility against the complete
graph, and produces a distinct Host use-time `bytedesk.verification-result/1`.
That fresh result normally has a different digest from the Coordinator's
historical result. Missing, stale, withdrawn, revoked, wrong-nonce,
wrong-subject, wrong-pin, or substituted status or graph evidence fails before
the switch intent is committed. This is a use-time safety verification, not a
Host product-policy decision.

One successful `activate-candidate` call switches the complete runtime-release
graph atomically. Its result and durable journal bind `releaseDigest`,
`deployableGraphDigest`, `activationAuthorizationDigest`, and
`hostEligibilityVerificationEvidenceDigest`. A per-subject `deploymentDigest`
is never the switch-journal identity. Staging, preflight, canary evidence,
promotion-decision evidence, active readback, and deployment receipts remain
per subject: the Coordinator must invoke or collect each one exactly once for
every canonical graph entry before committing target state.

`resolve-compile-attempt` is also discriminated. `committed` requires both the
consumer-deployment digest and compilation-evidence digest. `not-seen`,
`denied`, and `indeterminate` require both digests to be null. A public render,
partial publication, or one digest without the other is not a committed private
compilation.

Crash recovery is exact:

- before a remote commit, resume or retry with the same idempotency identity;
- after a lost commit response, resolve idempotency and perform authoritative
  readback before deciding;
- after host switch but before desired-state CAS, recover the exact
  runtime-release/deployable-graph journal and the complete canonical
  per-subject active-readback set, then resume evidence evaluation;
- after desired-state CAS but before receipt append, append every missing
  per-subject receipt from committed state using new append-only sequences; and
- fence a stale Coordinator without permitting any write.

The durable promotion decision is validated by
[`promotion-decision.schema.json`](../../contracts/schemas/v1/promotion-decision.schema.json).
Recovery always creates a new revision from eligible historical functional
content using current tooling, authority, approval, evaluation, and canary
evidence. It never reactivates a historical deployment, receipt, signature,
authority snapshot, or renderer.

## Capability trigger and evidence protocol

Only the Promotion Coordinator may call
`dispatch-capability-check`. The Host Reconciler, artifact, skill, renderer, and
CLI cannot dispatch it. The consumer-owned Capability Verifier performs the
check through the candidate's normal short-lived consumer identity and returns
separately authenticated evidence. The dispatch binds consumer, target,
candidate digest, check-profile digest, nonce, authorization-decision digest,
issue time, and expiry.

In isolated mode the sequence is candidate ready, dispatch, execute the isolated
check, verify the result, evaluate, then authorize the production switch. In
guarded mode the sequence is candidate ready, authorize provisional switch,
switch and read back, dispatch, verify the result, then evaluate before target-
state CAS.

The closed capability domain outcomes are `permitted` and `denied`. Denial
requires explicit current consumer-signed policy denial for the exact
nonce-bound request. Transport failure, timeout, missing or malformed result,
expiry, unknown signer, and indeterminate processing are operational failures
represented by stable problems, not capability outcomes, and cannot prove
denial. Host technical evidence and consumer capability evidence use different
identities, schemas, and append operations; neither actor can promote.

## Host journal, switch, and crash protocol

The Host Reconciler has one target-scoped identity and cannot write desired
state, dispatch capability work, use a human or runtime-agent identity, or emit
consumer authorization evidence. It stages and validates untrusted content
without execution, follows one certified activation mode, performs one safe
switch primitive, reads back actual state, and appends technical observations.

The journal identity binds consumer, target, attempt, target revision/digest,
deployment digest, and slot generation. Records are append-only, monotonically
sequenced, checksum-linked, and fenced by the attempt, generation, and region
epoch. The closed persisted switch-entry schema is
[`host-switch-journal-entry.schema.json`](../../contracts/schemas/v1/host-switch-journal-entry.schema.json).
Its phases are `accepted`, `artifact_verified`, `staged`,
`preflight_passed`, `candidate_ready_recorded`, `activation_authorized`,
`switch_intent_durable`, `switched`, `readback_verified`,
`observation_accepted`, `cleanup_eligible`, and `completed`. The durable
`switched` marker binds the exact predecessor and candidate generations,
release digests, and active pointer. `readback_verified` and later entries
also contain the exact active-pointer, process, file-inventory, serving, and
readback-time facts.

Before a dependent physical side effect, the host appends the required record,
fsyncs it, and fsyncs its parent directory. The `switch_intent_durable` entry
is durable before the switch. The switch is one same-filesystem atomic pointer operation or a
consumer-Adapter equivalent with the same semantics. The post-switch marker is
durable and binds old/new generations and digests. Exact active readback, not
intent or filenames, determines physical reality.

Crash disposition is:

- before switch intent: resume staging or preflight;
- after intent but before switch: read the active pointer and switch only if the
  old generation is still active and authorization remains fresh;
- during switch: read active pointer and digest and never guess;
- after switch but before marker: append the marker only if readback proves the
  exact new generation, otherwise report `host_switch_indeterminate`;
- after marker but before observation: verify readback and resubmit the
  observation idempotently; and
- after fencing: quarantine output and retain the journal until the Coordinator
  authorizes cleanup.

Cleanup never removes active content, a required predecessor, retained evidence,
or unresolved-attempt output. Observation-delivery retry never repeats the
physical switch.

## API, events, and CLI automation

HTTP uses the exact OpenAPI major as a transport projection over authoritative
product and port schemas. Events use CloudEvents 1.0.2, the exact
[`event-types.json`](../../contracts/events/v1/event-types.json) registry, and
the AsyncAPI transport projection. Delivery is at least once and ordered only
by aggregate sequence. Events are notification-only. Receivers deduplicate by
event and aggregate identity; an unknown schema or sequence gap stops projection
and invokes `resynchronize-events` against the authoritative API.

Server-sent events accept `Last-Event-ID` only on the event subscription. A
heartbeat is a comment frame. Disconnect does not cancel an action. Mutations
use strong ETags plus explicit absent or exact match preconditions.

`read-resource` is authoritative and has only `found` and `not-modified`
results. `found` carries the complete resource and an ETag equal to
`sha256(JCS(resource))`; `not-modified` carries the same strong digest and a
null resource. No stale result variant exists and cached public metadata cannot
become deployment, promotion, or desired-state authority.

Each `subscribe-events` result contains one SSE event whose `eventId` is the
only resume cursor. That exact value is emitted as the SSE `id` field and is the
only value accepted in `Last-Event-ID`; there is no separate resume token that
can drift. The event data digest is `sha256(JCS(data))`, and its aggregate
sequence equals the embedded event-data aggregate sequence. Resynchronization
returns an authoritative resource and one `lastEventId` from the same boundary.

Profile `bytedesk.cli-automation/1` freezes the `bd-agent` command tree. Human
output is presentation only. Machine output validates against
[`cli-result.schema.json`](../../contracts/schemas/v1/cli-result.schema.json);
progress validates against
[`cli-stream-event.schema.json`](../../contracts/schemas/v1/cli-stream-event.schema.json).
Authoritative and digest-bearing JSON is JCS.

Stdout contains the result only. Stderr contains progress, warnings, and bounded
redacted diagnostics only. Secrets are neither printed nor persisted by
default. A mutation requires an exact-digest interactive preview or an explicit
non-interactive acknowledgement. Polling uses bounded exponential backoff capped
at 30 seconds. Wait timeout does not cancel remote work unless an explicit
cancel request is accepted before the action's commit point.

`watch-action` fixes the exit code from the observed aggregate. A non-terminal
timeout has a null `terminalAction`, a non-terminal `lastObservedAction`, and
exit 12. A terminal result repeats the exact terminal action as both fields and
uses exit 0 for `succeeded`, 10 for `failed` or `dead_lettered`, and 11 for
`cancelled`. A terminal state and mismatched exit class is rejected.

The stable exit map is:

| Exit | Meaning |
| ---: | --- |
| 0 | Success |
| 2 | Usage or configuration |
| 3 | Validation |
| 4 | Compatibility |
| 5 | Trust |
| 6 | Authentication |
| 7 | Authorization or policy |
| 8 | Conflict or precondition |
| 9 | Unavailable, retryable, or commit resolution required |
| 10 | Terminal operation failure |
| 11 | Cancelled |
| 12 | Client wait timeout; remote action may still run |
| 13 | Protocol or contract failure |

Command names, JSON result variants, problem mappings, and exit meanings are
stable within the CLI major.

## External input locks

Any external repository content used for migration, parity, validation, or
compatibility evidence MUST validate against
[`external-input-lock.schema.json`](../../contracts/schemas/v1/external-input-lock.schema.json)
and profile `bytedesk.external-input-lock/1`. Its closed contract binds the
lock ID and evidence role, canonical HTTPS repository, full 40-64 hex immutable
commit, recomputed SHA-256 tree digest, strictly sorted portable
path/digest/size inventory, exact digest-addressed validator artifacts,
retrieval time, and `compatibilityEvidenceOnly: true`.

Fetching is bounded and read-only with hooks, submodules, LFS smudge, package
lifecycle, and input execution disabled. Branches, tags, channels, `latest`,
`HEAD`, path binaries, and ambient caches without digest proof are forbidden.
Every listed byte is verified, and missing, extra, duplicate, reordered, or
changed paths fail closed. An unavailable lock cannot be replaced with a local
checkout or another version. Locked implementation content is evidence only;
it never becomes renderer code, runtime dependency, core schema authority, or
consumer authority.

## Conformance and release gate

Every registry entry names one implementation owner and one executable
port-owner suite. Each source conformance case separately names one
task-composition `suite` and the exact closed `portSuites` derived from its
covered operations. The 143 cases close all 19 task suites and all 26
port-owner suites; a case cannot claim an owner suite that is absent from its
covered operations or omit one that is present.

The generated execution plan contains 86 operation schema goldens and compiles
the 143 cases into 235 deterministic steps. The repository validator executes
all 172 valid request/result fixtures, all 516 structural denials, all 14
aggregate semantic denials, protocol-mutation bindings, and every closed
oracle mapping. That proves the plan and contracts are internally executable;
it does not prove an Adapter's business behavior. Provider conformance requires
the exact implementation version/profile to execute every applicable plan
directive and retain its result. A structural sample, validator-only pass, or
unexecuted directive cannot be reported as a semantic golden or provider pass.

The complete port-to-task and port-to-suite closure is recorded in
[Downstream contract coverage](../architecture/downstream-contract-coverage.md).
An absent port, operation, request/result field, error family, protocol profile,
security boundary, lifecycle rule, task owner, or executable case blocks the
release. Conformance evidence is append-only and binds exact product, schema,
profile, implementation, dependency, and test digests.
