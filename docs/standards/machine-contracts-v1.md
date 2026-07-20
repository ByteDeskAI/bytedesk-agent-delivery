# Machine contracts v1

**Profile:** `bytedesk.machine-contracts/1`

**Status:** Accepted contract; the v1 language-neutral sources, 112 product
schemas, projections, and 312 indexed conformance fixtures—159 valid and 153
invalid—are frozen by the accepted AD-01 through AD-18 contracts. Generated
language bindings and downstream service, runtime, and operational evidence
remain implementation and GA gates.

## Purpose

This profile fixes the machine-readable contract system for Agent Delivery.
It defines which schema language is authoritative, how schemas are identified
and published, how functional customization operations behave, how HTTP APIs
and events reuse the schemas, and which changes are compatible.

It complements [Canonical encoding v1](canonical-encoding-v1.md). Canonical
encoding decides the bytes that carry identity. This profile decides the shape
and evolution of the values represented by those bytes.

> **Non-normative implementation note:**
> [ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
> fixes the Go reference verifier, PostgreSQL-backed service, locked toolchain,
> and offline bundle build used for certification. Those choices do not change
> this portable contract or make generated Go types authoritative.

## Normative schema language

Every Agent Delivery-owned authoritative structured object MUST have a JSON
Schema Draft 2020-12 schema. The schema is the only normative field-and-type
definition for that object. Prose explains intent and security rationale but
cannot silently add fields or contradict the schema.

Each schema MUST:

- declare `https://json-schema.org/draft/2020-12/schema` in `$schema`;
- have a stable, absolute `$id` under
  `https://schemas.bytedesk.ai/agent-delivery/v1/`;
- declare the logical contract name and major version;
- use explicit types, required members, bounds, patterns, and enumerations;
- give every directly typed array an explicit `maxItems`; a collection without
  a stricter contract-specific limit uses the canonical parser's 100,000-node
  ceiling as its outer `maxItems`, while the full-object node and 4 MiB limits
  remain independently mandatory;
- bound directly typed strings with `maxLength` unless `const` or a closed
  `enum` inherently bounds them, bound directly typed integers on both sides
  within the interoperable range, and either close objects to a fixed property
  set or declare `maxProperties`;
- allow the 5,592,406-character ceiling only for the exact
  `base64url-no-padding` byte profile, where canonical decoding independently
  enforces at most 4 MiB of decoded bytes and rejects padding, non-alphabet
  characters, and non-zero unused tail bits; ordinary strings remain capped at
  4 MiB and this wire expansion does not raise the complete product-object
  parser limit;
- bound JSON integers to the interoperable range
  `-9007199254740991..9007199254740991`; larger exact quantities and
  identifiers use canonical decimal strings;
- close every authority-bearing object boundary with
  `unevaluatedProperties: false`;
- identify every intentional extension point explicitly;
- avoid remote runtime references outside the signed schema release; and
- carry examples and positive, negative, boundary, and parser-differential
  fixtures.

The source-controlled schema is authoritative. Generated language models,
validators, SDKs, OpenAPI components, documentation, and examples are derived
outputs and MUST pass drift tests against it.

AD-01 releases the schemas and language-neutral projections only. It does not
release generated Go, Python, or TypeScript bindings. AD-10 owns deterministic
model/client generation after the externally visible ports are frozen and MUST
add clean-tree regeneration and drift checks before any such binding becomes a
released projection.

Agent Spec is an external contract. Agent Delivery validates the pinned Agent
Spec version with its official SDK. A locally written JSON Schema may be used
as a supplemental lint or editor aid but MUST NOT replace or weaken official
SDK validation.

## Schema identity and distribution

Before a contract can appear in a public preview or release, its schema and all
transitive local references are:

1. resolved without network access;
2. validated against Draft 2020-12;
3. serialized as RFC 8785 canonical JSON;
4. identified by a SHA-256 digest;
5. packaged as a signed, immutable release artifact; and
6. listed by `$id`, logical version, media type, size, digest, and required
   immutable trust-policy ID and digest in the release manifest.

The exact product-schema set is independently closed by
[`contracts/bundle/v1/schema-inventory.json`](../../contracts/bundle/v1/schema-inventory.json),
profile `bytedesk.contract-schema-inventory/1`. Its only root fields are
`profile` and `schemas`; each schema entry has only its stable `id`, canonical
repository `path`, and RFC 8785 digest, and entries are ordered by ID. The
current v1 inventory contains 112 schemas. The Go and Python validators, bundle
builder, and offline verifier MUST compare the complete discovered or bundled
registry to these exact triples. An omitted or added schema, path rename, ID
substitution, digest drift, duplicate, unknown field, or reordered entry fails
closed. A reviewed inventory update and matching schema change are one release
change; neither can silently expand or narrow the other.

The inventory enters the signed bundle as exact RFC 8785 JCS bytes, is bound by
its own manifest inventory entry and `buildInputDigest`, and is verified before
the bundled registry can satisfy the release contract. Schemas, transitive
references, OpenAPI, AsyncAPI, compatibility metadata, and
their complete positive and denial fixture set ship together as one signed,
content-addressed contract bundle. Resolution is bundle-local and offline;
runtime network schema fetching is forbidden.

The schema digest, not a mutable documentation URL, is verification authority.
The `$id` remains stable for discovery and reference resolution. Published
schema bytes are immutable. Correcting any byte creates a new schema version
and digest; historical schemas remain available for receipt verification.

Before the first production-authoritative publication of a major, draft bytes
may be replaced only by an explicit readiness decision that proves no
`authorityIssued: true` bundle or receipt exists, invalidates every prior
generated fixture, manifest, digest, and conformance report, and reruns the
complete freeze gate. Test-only or conformance artifacts do not publish a
schema. This narrow pre-publication reset is not a compatibility mechanism and
ceases permanently for that major after its first authoritative release.

The API, CLI, manifests, attestations, and receipts expose the exact schema
`$id` and digest used to validate an object. Implementations MUST NOT fetch a
new schema merely because an artifact names it. The schema must already be
allowed by independently configured product or consumer trust policy.

Every validation operation MUST first select one accepted schema by its exact
`$id` and canonical digest. If the instance has a root `schema` descriptor,
the validator MUST compare that descriptor with the selected schema before
ordinary Draft 2020-12 instance validation: `schema.id` equals the selected
schema's `$id`, and `schema.digest` equals the selected source schema's RFC
8785 canonical SHA-256 digest. A descriptor that is structurally valid but
names a different ID or digest fails closed. Structural validation alone is
not evidence of this binding because a schema cannot normatively assert its
own canonical digest.

## Downstream integration control catalogs

The downstream adapter boundary is closed by ten additional Draft 2020-12
product schemas and their root-bound control documents:

- `action-catalog`, `problem-catalog`, and `event-types` define the stable
  action, failure, and notification vocabulary shared by API, CLI, worker,
  reconciler, storage, registry, signing, and consumer adapters;
- `downstream-port-registry` defines every port, operation, owner, request and
  response contract, protocol profile, failure mapping, and conformance suite;
- `protocol-profiles` and `downstream-conformance-cases` define the closed
  adapter requirements and permitted/denied behavior, while
  `downstream-conformance-plan` deterministically compiles all nine machine
  authorities into adapter-executable steps and closed oracles;
- `protocol-fixtures` binds the byte-exact OCI, supply-chain, and capability
  protocol corpus, complete material set, cross-document chains, and
  single-fault denial mutations used as conformance evidence; and
- `port-type-catalog` and `port-contract-fixtures` contain the complete offline
  field/operation schemas and their valid and structural-denial instances.

The source controls live under `contracts/ports/v1/`, except the notification
registry under `contracts/events/v1/`. Every control MUST carry its accepted
root `$schema`, validate as an indexed positive fixture, and ship in the same
offline bundle as its exact schema. Unknown root or nested fields, omitted
required suites, unresolved contract references, mutable selectors, incomplete
fixture coverage, or source-schema digest drift fail closed.

`type-catalog.json` and `contract-fixtures.json` are deterministically
generated from the reviewed port registry, action/problem/event controls, and
the accepted product-schema set. Their generator is a build mechanism, not a
second contract authority. Once released, the generated catalogs' exact bytes,
embedded schema IDs, and digests are the distributed control. Each embedded
port schema remains bounded and closed, resolves only from the offline catalog,
and cannot expand the 112-entry product-schema inventory or substitute a source
schema. A generated valid fixture proves structural compatibility only; it is
never authentication, authorization, consumer approval, or deployment
authority.

The port catalogs describe Agent Delivery's headless integration surfaces.
They MUST NOT encode consumer users, roles, grants, provider credentials,
workload identity, business approval, or mandatory runtime security policy.
Adapters treat all requests, responses, evidence, payload files, skill files,
and generated instances as untrusted input and apply current call-time
consumer/runtime authorization outside these contracts.

Descriptor roles are closed rather than inferred from a field name. The shared
`artifactDescriptor` binds repository, exact digest, media type, size, and
trust-policy reference; canonical contract-bundle JSON and the fixed
`contract-bundle-release-v1` policy must occur together, and legacy
contract-bundle tar media is invalid. A named contract-bundle role uses the stricter
`contractBundleDescriptor`. The separate `evidenceBlobDescriptor` contains only
repository, exact digest, media type, and size. It is valid only as subordinate
input to an independently verified receipt, carries no trust or authority, and
requires the trusted Adapter to resolve and authenticate its exact bytes.

## Signing and verification-result contract

A signing request binds one exact subject descriptor, including a media type
that uses the shared bounded `type/subtype` grammar. An empty, malformed,
uppercase, parameter-only, or overlong media type is invalid. The signer and
verifier compare that value exactly; content sniffing or substituting a more
general media type cannot authorize different bytes.

A verification result has only the closed outcomes `permitted` and `denied`.
Every result carries at least one exact digest of authenticated or independently
integrity-verified evidence used to reach it. A permitted result has no reason
codes. A denied result has one or more values from the versioned, closed reason
code registry, so a new denial meaning requires an intentional contract change
instead of an ad hoc string. Missing, stale, invalid, or unavailable evidence
uses its specific reason; absence or transport failure MUST NOT be recast as
`policy_denied`.

## Unknown fields and extension points

Commands, bindings, desired-state revisions, trust records, authority
snapshots, artifact manifests, attestations, and receipts fail closed on an
unknown schema version, unknown operation, or unknown field. Silent field
dropping is forbidden because it can change signed meaning.

Extensibility is explicit rather than ambient. There is no generic unversioned
extension bag. A contract may declare a typed `extensions` object whose keys
are reverse-DNS names controlled by the extension owner. Each accepted
namespace has an exact schema descriptor in the trusted contract bundle;
unregistered keys fail. Extension data:

- participates in canonical identity when carried by an authoritative object;
- cannot create identity, grants, credentials, trust roots, approvals, or
  mandatory-policy exceptions;
- cannot alter core-field semantics;
- is ignored by components that do not advertise support; and
- may be rejected by a consumer policy even when structurally valid.

Public API read models and notification-event data may gain optional fields in
a compatible minor release. Clients MUST ignore unknown optional fields in
those non-authoritative projections. This rule does not permit a server to
accept an unknown command field or a verifier to accept an unknown field in a
signed authority object.

## Functional customization operation profile

Agent Spec and harness-configuration customization use
`bytedesk.json-patch/1`, a deliberately constrained profile of RFC 6902 JSON
Patch over the JSON data model with RFC 6901 JSON Pointer paths.

The profile permits only ordered `add`, `replace`, and `remove` operations.
`move`, `copy`, `test`, `from`, vendor operations, and URI-fragment pointer
syntax are forbidden. Each operation object is closed and contains:

- `op` and `path` for every operation;
- `value` for `add` and `replace`; and
- no `value` for `remove`.

Operations apply sequentially to the exact, already validated public baseline.
The empty root pointer cannot be changed. Parent
paths must exist. `add` requires the target not to exist, except that a final
`-` may append to an array. `replace` and `remove` require the target to exist.
Array indices use `0` or a non-zero digit followed by digits, without leading
zeros. A failed precondition aborts the complete delta; partial results are
never published or signed.

Pointers use JSON string representation and the RFC 6901 `~0` and `~1`
escapes. Implementations reject non-canonical array tokens, invalid escapes,
ambiguous Unicode, a target other than one complete functional document, and
the empty root pointer. The JSON Schema `maxLength` ceiling is 4,096 Unicode
characters; semantic validation independently limits the encoded pointer to
4,096 UTF-8 bytes and requires every decoded token to be NFC. This byte ceiling
is intentionally stricter for multibyte input and is applied before traversal.
Independently supplied security or authority objects are not target documents.
After all operations, the complete result is revalidated by the official Agent
Spec SDK, the selected renderer contract, portability policy, and consumer
policy.

The v1 boundary is target-based rather than a blacklist of sensitive property
names. A JSON Patch document targets exactly one complete validated Agent Spec
or one exact renderer-owned functional-configuration document. Every non-root
path within those two functional documents is eligible for customization. They
cannot contain consumer identity, roles, grants, credentials, workload
identity, trust or approval policy, desired runtime state, sandbox or network
policy, or other security authority; those are separate consumer-owned objects
and are never valid patch targets. Revalidation against the exact official or
renderer schema rejects attempts to smuggle authority through unknown fields.
File and skill changes use their separate profiles and may carry arbitrary
bytes, but Agent Delivery never executes artifact-provided content.

JSON Merge Patch is not accepted. Its null/delete behavior and array replacement
semantics are too ambiguous for a digest-pinned customization lineage.

Automatic source updates clone the previous and proposed exact public sources
into separate working trees, then process the accepted operations in order.
Before each operation, the rebase compares its target and complete containing
top-level subtree in the two working trees; a changed target, containing
subtree, parent, or array is a conflict. It then applies the operation to both
trees, allowing a later operation to use a parent created earlier in the same
atomic delta. The document root is deliberately excluded from ancestor
comparison, so an unrelated top-level upstream change survives in the proposed
result. Inputs remain immutable, and canonical parser limits are rechecked
after every operation and over the final result. The controller never blindly
replays an old delta onto a structurally changed target context.

## File operation profile

File changes use a separate closed operation schema; they are not JSON Patch.
Paths are portable POSIX-style relative paths normalized to Unicode NFC. Empty
segments, `.`, `..`, leading slash, backslash, NUL/control characters, Windows
drive or device syntax, Windows-forbidden filename characters, segments longer
than 255 UTF-8 bytes, and names that collide after Unicode normalization or
case folding are rejected. The complete path has both the schema ceiling of
1,024 Unicode characters and a stricter semantic ceiling of 1,024 UTF-8 bytes;
it may contain at most 32 segments.

- `add` requires an absent path and an exact content descriptor plus safe
  regular-file mode.
- `replace` requires an existing path, its expected current content digest,
  and the replacement descriptor and mode.
- `remove` requires an existing path and its expected current content digest.

Only regular files are valid targets. Directories are implied by accepted file
paths and deterministic packaging. Links, devices, FIFOs, sockets, setuid,
setgid, and sticky or host-specific metadata are forbidden. Operations are
ordered, but a path may be the successful target of at most one operation in a
delta. Every content descriptor includes repository, digest, media type, size,
and immutable trust-policy ID and digest.

## Skill operation profile

Skill changes also use a separate closed schema. A skill is addressed by its
stable package identifier and exact descriptor.

- `add` requires that the package identifier is absent and supplies the new
  exact descriptor.
- `replace` requires the identifier and expected current digest, then supplies
  the replacement descriptor.
- `remove` requires the identifier and expected current digest.

Duplicate identifiers, ambiguous replacement, a digest mismatch, or mutable
descriptor fail the entire delta. Every resulting effective skill digest must
have current consumer approval evidence before compilation and activation.

## Source resolution

Public source may be an Agent Spec `Agent` or `SpecializedAgent`. The resolver
first verifies the supplied SHA-256 digest over the exact payload, parses it
under the canonical resource limits, and requires the payload itself to equal
its RFC 8785 bytes. Only then does it call the official Agent Spec `26.1.2`
validator exactly once. The declared `agent` or `specialized-agent` kind must
agree with both that official result and the root `component_type`; no caller-
declared or inferred substitute kind is accepted. After that one official call,
the raw document must contain top-level `agentspec_version: 26.1.2` exactly;
an omitted field, another SDK-supported version, or legacy `air_version`
substitution fails closed.

`Agent` is the default standalone catalog form. A `SpecializedAgent` is allowed
only as an intentional complete portable public specialization governed by the
official contract. It embeds one complete `Agent` object and one complete
`AgentSpecializationParameters` object. A string, generic `$ref`, official
`$component_ref`/`$referenced_components` indirection, remote or
package-relative lookup, embedded `SpecializedAgent`, or another nested
specialization-resolution step fails after official validation. Public
specialization is not private customization, identity, or organizational
authority.

Private customization applies exactly once to the complete validated public
document. It creates no second inheritance system and cannot change source-
lineage metadata. The output kind and source kind are both recorded; a valid
kind-changing result is breaking and requires manual promotion. The complete
privately effective result is revalidated by the official SDK and emitted only
as build output.

## Predecessor and concurrency contract

Every durable aggregate mutation carries a required discriminated
`precondition`. Initial creation uses `{ "kind": "absent" }` and succeeds only
when no current aggregate exists. An update uses `{ "kind": "match", "revision": N, "digest":
"sha256:..." }` and must match both the monotonic revision and canonical digest
of the immediately previous accepted revision. Requiring both prevents an ABA
change from passing a digest-only comparison. Omission, `null`, a wildcard, or
a digest without its revision is invalid, including for break-glass workflows.

Nested file and skill operation elements are not independently durable
aggregates. They execute atomically inside the already CAS-guarded binding
mutation and use the absent-or-current-item-digest preconditions defined in
their profiles. The enclosing aggregate revision is the monotonic ABA guard;
inventing resettable per-item revisions would not provide another safe CAS.

Every accepted immutable record separately carries `predecessor`:
`{ "kind": "none" }` for revision one or the exact prior revision and digest.
A recovery revision uses the current target revision as its predecessor and
records the historical known-good selection separately as `recoverySource`. A
deployment never substitutes a source, render, or receipt digest for the
aggregate predecessor.

HTTP mutation uses the same rule through a strong `ETag` equal to the current
canonical resource digest. Creation requires `If-None-Match: *`; update,
promotion, cancellation, and forward-recovery requests require `If-Match`. A
failed precondition returns `412` without side effects.

The polymorphic command endpoint preserves this rule without making both HTTP
conditionals ambiguous. `source_validate` and `render` have no durable aggregate
precondition and send neither conditional header. For every other command,
`precondition.kind: absent` requires exactly `If-None-Match: *`, while
`precondition.kind: match` requires exactly `If-Match` equal to the quoted
`precondition.digest`; the opposite header is forbidden. Missing, conflicting,
wildcard update, body/header mismatch, or unsupported precondition combinations
return `412` with no accepted action and no side effect.

## HTTP API contract

The normative HTTP description uses OpenAPI 3.2.0 with JSON Schema Draft
2020-12 as its declared dialect. It references the exact same source schemas
rather than copying them into an independent model. The signed OpenAPI document
is versioned with the product release and has a stable `$self` URI and digest.
Release validation first applies the exact vendored official OpenAPI 3.2 schema
identified by its source URI and SHA-256, entirely offline, and then applies the
stricter Agent Delivery projection, reference, authentication, conditional,
header, and source-schema-digest checks. The official schema and its retained
Apache-2.0 license ship as tooling documents in the same signed bundle.

The v1 projection also freezes the complete path, HTTP method, and
`operationId` map. Each operation has one exact security requirement and
accepted response-status set, and each success or default response points to
the required component. Release lint evaluates this closed topology before
per-operation checks, so deleting or renaming an operation cannot bypass its
authentication, conditional-request, or response obligations. A topology
change is an intentional API-contract change, never projection cleanup.

That closed topology includes every operation's ordered parameter references,
the absence or exact required JSON request-body schema, and the complete
semantic definitions of parameter and header components. Response component
names, media types, schema references, and header-name-to-header-component
bindings are exact. Schema component names bind one exact normative `$ref`,
schema `$id`, and canonical digest; substituting another valid source schema
under an existing component name is projection drift. Descriptions and other
prose may change without changing these semantic bindings.

The API uses:

- a major version in the path, beginning with `/v1`;
- resource-oriented nouns and exact opaque identifiers;
- cursor pagination with a documented stable sort and no offset paging for
  mutable collections;
- strong ETags and HTTP conditional requests for mutations;
- `application/problem+json` following RFC 9457, stable problem-type URIs,
  stable machine `code`, correlation ID, and redacted details;
- an idempotency key plus canonical request digest for non-idempotent commands;
  replay returns the original result, while key reuse with a different digest
  returns `409`;
- `202 Accepted`, `Location`, and a durable action resource for work that may
  exceed two seconds; and
- explicit scopes, tenant/consumer binding, rate-limit headers, and no secret
  values in requests, responses, URLs, or diagnostics.

Every command is authenticated; there is no anonymous dispatch path.
`source_validate` and `render` may be authorized under the narrow public-purpose
profile, while every private or state-changing command requires exact consumer
and operation scope. An unknown command or authorization profile fails closed.
Authentication never weakens the independent precondition, idempotency,
canonical-request-digest, trust, or consumer-authority checks.

Every accepted asynchronous command returns the created `Action` in the `202`
body, a required strong `ETag` for that exact action representation, a required
relative `Location` of `/v1/actions/{actionId}`, and required
`RateLimit-Limit`, `RateLimit-Remaining`, and `RateLimit-Reset` headers. The
location cannot name a collection or unrelated resource, and the accepted
response does not imply that the action or requested business transition has
succeeded.

Action resources expose immutable input digest, state, progress, attempts,
timestamps, cancellability, result or problem reference, and append-only
evidence. Cancellation is conditional and cannot erase a side effect; after a
desired revision is published, reversal requires a new forward revision.

Action execution is lease- and fencing-token based. A worker may start,
heartbeat, publish output, retry, cancel, or terminalize an attempt only while
its database lease and monotonically issued fencing token are current. After a
process crash or lease expiry, a sweeper atomically fences the stale attempt,
records that evidence, and discards its output. Recoverable `claimed` or
`running` work advances to `retry_wait` with full-jitter backoff; exhausted work
advances to `dead_lettered`. A cancellation request is never lost during
recovery: expired `cancellation_requested` work remains in that state while a
new fenced attempt is assigned to finish cancellation, or dead-letters when its
budget is exhausted. A stale worker cannot complete, fail, retry, or cancel the
action after fencing. Every transition and outbox notification is appended in
the same durable transaction; retry never edits prior evidence.

## Event contract

Integration events use CloudEvents 1.0.2 and are described by AsyncAPI 3.1.0.
JSON is mandatory. An event carries the exact event-data schema `$id` and
digest, aggregate identifier, aggregate revision digest, per-aggregate
monotonic sequence, correlation and causation identifiers, consumer scope, and
redaction classification.

The AsyncAPI entry document uses the stable
`x-bytedesk-document-uri` specification extension because AsyncAPI 3.1 has no
OpenAPI-style `$self` field. Release validation applies the exact vendored
AsyncAPI 3.1 all-in-one Draft 7 schema and all 113 embedded resources without
network retrieval before applying Agent Delivery's stricter event-registry and
projection checks. The pinned schema, upstream license, and notice ship in the
signed offline bundle.

The event topology is closed to two HTTPS transports: authenticated resumable
`consumerFeed` and independently configured mutual-TLS `consumerWebhook`. The
single `notifications` channel explicitly binds both servers, and the single
`receiveNotifications` operation binds that channel, its exact message, and
the notification-only delivery traits. Server, channel, operation, security
scheme, or reference removal and rename is release-blocking.

The message topology is closed as well. `EventDataEnvelope` binds its exact
normative `$ref`, schema `$id`, and canonical digest, while
`AgentDeliveryNotification` binds the structured CloudEvents content type,
correlation location, CloudEvents version, event-data descriptor, exact
required-member and property sets, closed event-type enum, `dataschema`
constant, and `data` reference. A valid but different schema, media type,
envelope constraint, or component placed under either existing name is
release-blocking projection drift.

Delivery is at least once. Ordering is guaranteed only within one aggregate
partition. Receivers deduplicate by CloudEvent `id`; a sequence gap or unknown
schema causes the receiver to stop applying projections and resynchronize from
the authoritative API. Events are notifications, never desired-state,
promotion, approval, identity, or authorization authority. A receiver fetches
the exact current resource before taking an authoritative action.

Outbox publication and inbox processing are transactional with their local
state. Dead-lettering preserves the original envelope and redacted diagnostic
reference. Event payloads never contain credentials, tokens, raw webhook
bodies, private keys, or unrestricted consumer-private content.

## Compatibility and support

Contract major versions are immutable. The following are breaking and require
a new major version or media type: removing or renaming a field, changing its
type or meaning, adding a required field, narrowing an accepted value, changing
canonicalization or operation semantics, changing security interpretation, or
changing a terminal-state meaning.

Compatible evolution is limited to new optional read-model/event fields, new
operations or resources that do not alter existing behavior, and enum values
only where the schema and client contract explicitly declare an open enum.
Command and authority-object enums are closed.

Every compatibility claim is proved both directions where applicable: old
client against new server, new client against supported old server, event
replay, stored-object replay, and offline historical receipt verification.
Deprecation and support windows follow
[Operational readiness v1](operational-readiness-v1.md).

## Failure behavior

Unknown schema or digest, unavailable schema, closed-inventory mismatch,
unresolved reference, validation difference, unknown field, invalid extension, unsupported patch, failed path
precondition, source-resolution ambiguity, stale predecessor, incompatible API
version, or event gap fails closed. An implementation does not guess, coerce,
drop, partially apply, or fall back to prose or generated code.

## Required verification

Release evidence includes:

- at least two independent Draft 2020-12 validators agreeing on every golden
  and denial fixture, including indexed single-fault wrong-root-schema-ID and
  wrong-root-schema-digest semantic denials performed before ordinary instance
  validation;
- schema metaschema validation, reference closure, digest, signature, and
  offline resolution tests;
- independent exact-inventory comparison proving schema removal, addition,
  path rename, ID substitution, and stale digest are denied by the repository
  validators and authenticated offline bundle verifier;
- recursive schema-resource proofs that reject an unbounded direct array,
  string, integer, or open-ended object before a contract bundle is built;
- schema-to-OpenAPI, examples, documentation, and bundle drift tests, plus
  schema-to-code drift for every language binding released by the current
  milestone;
- unknown-field, extension, open/closed-enum, and compatibility tests;
- RFC 6901/6902 conformance plus the stricter add/replace/remove preconditions;
- operation-order, conflict, array, Unicode, path-collision, and atomic-failure
  fuzz tests;
- the eleven `contracts/fixtures/operations/source-resolution.cases.json`
  cases proved against exact canonical bytes by the pinned official SDK with
  socket access denied, covering Agent and SpecializedAgent resolution,
  official-kind agreement, explicit version binding, and remote,
  package-relative, component-reference, and nested-resolution denial;
- the seven `contracts/fixtures/operations/three-way-rebase.cases.json` cases
  proving ordered dual-tree application, unrelated top-level preservation,
  and changed-target, containing-subtree, parent, and array conflicts;
- ETag, first-create, stale-update, idempotency replay/collision, pagination,
  problem-details, and asynchronous-action tests; and
- duplicate, reorder, gap, replay, dead-letter, redaction, and API-resync event
  tests.

## References

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [RFC 6901: JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901)
- [RFC 6902: JSON Patch](https://www.rfc-editor.org/rfc/rfc6902)
- [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [AsyncAPI Specification 3.1.0](https://www.asyncapi.com/docs/reference/specification/v3.1.0)
- [CloudEvents specification](https://github.com/cloudevents/spec/tree/ce%40v1.0.2)
- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457)
- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110)
