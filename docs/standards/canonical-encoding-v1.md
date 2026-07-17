# Canonical encoding v1

**Profile:** `bytedesk.canonical-json/1`

**Status:** Accepted architecture contract; concrete canonicalization fixtures
are release-blocking

## Purpose

This profile gives every authoritative structured object one semantic identity
before it is hashed, signed, compared, cached, or included in provenance. Human
authoring syntax must not change that identity, and parser-specific YAML
behavior must not create alternate meanings for the same reviewed content.

This profile fixes encoding. [Machine contracts v1](machine-contracts-v1.md)
fixes JSON Schema Draft 2020-12, schema identity and distribution,
customization operations, concurrency preconditions and separate predecessor
lineage, and API/event envelopes.

## Applicability

The profile applies to every Agent Delivery structured object whose content is
authoritative or whose digest is used as semantic or artifact authority,
including Agent Spec documents, catalog and OCI manifests, bindings and
customization values, descriptors, trust-policy records, attestations, desired-
state records, releases, and receipts. A storage-integrity checksum for a
separate provenance attachment is not an authority digest.

The object's declared contract role or media type determines whether this
profile applies. A filename or extension does not. In particular, an arbitrary
regular payload file named `.json`, `.yaml`, or `.yml` is still payload data
unless a contract declares it to be a structured control object.

An implementation may accept JSON directly or YAML as human authoring input.
JSON is the authoritative data model. YAML is never the signed, hashed, or
semantic-identity representation.

## Accepted YAML authoring subset

YAML input MUST use YAML 1.2 syntax restricted to the JSON-compatible data
model: objects with string keys, arrays, strings, finite numbers, booleans, and
`null`. The parser MUST reject the document before schema validation when it
contains:

- duplicate mapping keys, detected before a parser can collapse them;
- aliases;
- custom tags;
- non-string mapping keys;
- non-finite numbers such as positive or negative infinity or NaN; or
- any node that cannot be represented in the JSON data model and serialized by
  RFC 8785.

Implementations MUST NOT use YAML parser behavior, source spelling, comments,
key order, or presentation style as semantic input. YAML merge behavior cannot
be obtained through aliases because aliases are rejected.

## Normalization and canonical output

For either accepted input syntax, the implementation:

1. parses the document into the JSON data model without losing duplicate-key
   detection;
2. validates that data against the exact independently trusted, offline-resolved
   object schema and applicable policy;
3. serializes the validated value with the JSON Canonicalization Scheme in RFC
   8785; and
4. hashes, signs, compares, caches, and records provenance for those canonical
   JSON bytes.

The output is UTF-8 RFC 8785 canonical JSON. Semantically equivalent accepted
JSON and YAML inputs therefore produce the same canonical bytes and digest.
Object-member order, insignificant whitespace, and YAML presentation do not
affect semantic identity. Array order remains significant.

An implementation may preserve the originally authored YAML or JSON only as a
separate provenance attachment or record. A digest over those authored bytes
may verify the attachment's storage integrity, but it is provenance-only: it is
never semantic identity, artifact authority (including source or deployment
authority), a signature target in place of canonical JSON, a promotion
decision, or activation authority or input. It cannot replace or alter the
canonical JSON identity.

## File payloads

Canonical JSON applies to structured control objects, not to arbitrary payload
files merely because they are carried by an artifact or have a JSON/YAML
extension. Arbitrary input payload contents remain exact raw bytes. A payload
file named `example.yaml` is not parsed or canonicalized unless its declared
contract role makes it a structured control object. Binary file content is
likewise preserved exactly; its content digest is over those exact bytes, and
it is never decoded, transcoded, line-ending-normalized, or passed through JSON
or YAML canonicalization.

Deterministic archive construction may normalize container metadata such as
entry order, paths, timestamps, declared modes, ownership, and compression
settings. It must not change the raw content bytes of a payload entry.

## Failure behavior

Unsupported YAML constructs, duplicate keys, invalid JSON-model values,
schema-invalid values, or RFC 8785 serialization failure are terminal
validation errors. The implementation MUST NOT guess a value, accept the first
or last duplicate key, silently coerce a key or scalar, fall back to
non-canonical serialization, or publish, sign, import, compile, or activate the
object.

Unknown schema IDs, schema digests, fields, versions, or unavailable signed
contract bundles fail according to Machine contracts v1. This encoding profile
does not make an unknown shape acceptable.

## Required verification

Contract fixtures MUST prove:

- semantically equivalent accepted JSON and YAML produce byte-identical RFC
  8785 output and the same digest;
- object-key and whitespace variation do not change the digest while array
  reordering does;
- duplicate keys, aliases, custom tags, non-string keys, non-finite numbers,
  and non-JSON nodes fail before publication or signing;
- canonical bytes are the bytes covered by digest, signature, cache identity,
  and provenance references;
- exact schema ID/digest selection and offline contract-bundle validation occur
  before canonical bytes become authority;
- retained authoring input is non-authoritative and separately identified;
- its integrity digest cannot substitute for canonical authority or influence
  promotion or activation;
- arbitrary `.yaml` payload fixtures are not parsed and survive packaging and
  extraction byte-for-byte;
- binary fixtures, including every byte value, survive packaging and extraction
  byte-for-byte with the same content digest.

## Reference

- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785)
