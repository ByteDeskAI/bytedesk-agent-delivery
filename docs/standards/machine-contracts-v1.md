# Machine contracts v1

**Profile:** `bytedesk.machine-contracts/1`

**Status:** Accepted architecture contract; concrete schema artifacts are a
release-blocking AD-01 deliverable

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

Schemas, transitive references, OpenAPI, AsyncAPI, compatibility metadata, and
their complete positive and denial fixture set ship together as one signed,
content-addressed contract bundle. Resolution is bundle-local and offline;
runtime network schema fetching is forbidden.

The schema digest, not a mutable documentation URL, is verification authority.
The `$id` remains stable for discovery and reference resolution. Published
schema bytes are immutable. Correcting any byte creates a new schema version
and digest; historical schemas remain available for receipt verification.

The API, CLI, manifests, attestations, and receipts expose the exact schema
`$id` and digest used to validate an object. Implementations MUST NOT fetch a
new schema merely because an artifact names it. The schema must already be
allowed by independently configured product or consumer trust policy.

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
ambiguous Unicode, paths outside the contract-specific functional allowlist,
and paths into independently supplied security or authority inputs. After all
operations, the complete result is revalidated by the official Agent Spec SDK,
the selected renderer contract, portability policy, and consumer policy.

JSON Merge Patch is not accepted. Its null/delete behavior and array replacement
semantics are too ambiguous for a digest-pinned customization lineage.

Automatic source updates perform a three-way rebase using the previous exact
public source, its accepted delta, and the proposed exact public source. A
changed target node, changed ancestor, removed parent, or unstable array
position is a conflict. The controller never blindly replays an old delta onto
a structurally changed source.

## File operation profile

File changes use a separate closed operation schema; they are not JSON Patch.
Paths are portable POSIX-style relative paths normalized to Unicode NFC. Empty
segments, `.`, `..`, leading slash, backslash, NUL/control characters, Windows
drive or device syntax, and names that collide after Unicode normalization or
case folding are rejected.

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

Public source may be an Agent Spec `Agent` or `SpecializedAgent`, with an
explicit source-kind discriminator that agrees with the official document.
`Agent` is the default standalone catalog form. `SpecializedAgent` is allowed
only as an intentional, complete portable public specialization governed by
the official Agent Spec contract; it is not private customization, identity,
or organizational authority. The complete public document is independently
validated and digested. Mutable, missing, cyclic, remote-implicit, or package-
escaping references fail.

Private customization applies exactly once to the complete validated public
document. It creates no second inheritance system and cannot change source-
lineage metadata. The output kind and source kind are both recorded; a valid
kind-changing result is breaking and requires manual promotion. The complete
privately effective result is revalidated by the official SDK and emitted only
as build output.

## Predecessor and concurrency contract

Every mutation carries a required discriminated `precondition`. Initial
creation uses `{ "kind": "absent" }` and succeeds only when no current aggregate
exists. An update uses `{ "kind": "match", "revision": N, "digest":
"sha256:..." }` and must match both the monotonic revision and canonical digest
of the immediately previous accepted revision. Requiring both prevents an ABA
change from passing a digest-only comparison. Omission, `null`, a wildcard, or
a digest without its revision is invalid, including for break-glass workflows.

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

## HTTP API contract

The normative HTTP description uses OpenAPI 3.2.0 with JSON Schema Draft
2020-12 as its declared dialect. It references the exact same source schemas
rather than copying them into an independent model. The signed OpenAPI document
is versioned with the product release and has a stable `$self` URI and digest.

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

Action resources expose immutable input digest, state, progress, attempts,
timestamps, cancellability, result or problem reference, and append-only
evidence. Cancellation is conditional and cannot erase a side effect; after a
desired revision is published, reversal requires a new forward revision.

## Event contract

Integration events use CloudEvents 1.0.2 and are described by AsyncAPI 3.1.0.
JSON is mandatory. An event carries the exact event-data schema `$id` and
digest, aggregate identifier, aggregate revision digest, per-aggregate
monotonic sequence, correlation and causation identifiers, consumer scope, and
redaction classification.

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

Unknown schema or digest, unavailable schema, unresolved reference, validation
difference, unknown field, invalid extension, unsupported patch, failed path
precondition, source-resolution ambiguity, stale predecessor, incompatible API
version, or event gap fails closed. An implementation does not guess, coerce,
drop, partially apply, or fall back to prose or generated code.

## Required verification

Release evidence includes:

- at least two independent Draft 2020-12 validators agreeing on every golden
  and denial fixture;
- schema metaschema validation, reference closure, digest, signature, and
  offline resolution tests;
- schema-to-code, schema-to-OpenAPI, examples, and documentation drift tests;
- unknown-field, extension, open/closed-enum, and compatibility tests;
- RFC 6901/6902 conformance plus the stricter add/replace/remove preconditions;
- operation-order, conflict, array, Unicode, path-collision, and atomic-failure
  fuzz tests;
- Agent and SpecializedAgent resolution equivalence and escape/cycle denials;
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
