# Agent Delivery event profile v1

## Contract

The event transport is CloudEvents 1.0.2 structured JSON with content type
`application/cloudevents+json`. The signed AsyncAPI 3.1.0 projection is
`contracts/asyncapi/v1/agent-delivery.asyncapi.json`; the normative event data
is `contracts/schemas/v1/event-data-envelope.schema.json`. The event-type
registry in `event-types.json` closes the v1 projection set.
AsyncAPI projects that exact set as a closed message-type enum, and every
registered type has one structured example.

The v1 AsyncAPI topology is closed. `consumerFeed` is the authenticated
resumable HTTPS pull surface; `consumerWebhook` is the independently configured
mutual-TLS HTTPS delivery surface. The `notifications` channel explicitly
names both servers and the `receiveNotifications` operation names exactly that
channel and message. Neither transport, its security scheme, nor any topology
reference is optional release metadata.

## Inputs and outputs

The transactional outbox receives only an already committed aggregate change,
its exact revision digest and sequence, correlation and causation IDs, consumer
scope, the current event-data schema descriptor, and a redacted exact API
resource reference. It emits one structured CloudEvent. Raw webhook bodies,
credentials, tokens, authority envelopes, private keys, unrestricted private
payloads, desired state, approvals, and authorization decisions are forbidden.

The CloudEvent `id` is the receiver deduplication key. Ordering is guaranteed
only for one aggregate key and its monotonically increasing `data.aggregate.sequence`.
`data.resource.etag` is the strong ETag the receiver uses for authoritative API
resynchronization. It is not permission to mutate the referenced resource.

## Failure behavior

Delivery is at least once. An unavailable webhook is retried with bounded
backoff and may dead-letter without blocking another aggregate. The original
envelope and a redacted diagnostic reference remain append-only evidence.
Duplicate IDs are acknowledged without reapplying a projection. Reordered or
late events cannot move a projection backward.

An unknown event type, unknown schema ID or digest, sequence gap, mismatched
outer/data event type, wrong consumer scope, malformed envelope, or invalid
signature stops projection for that aggregate. The receiver fetches the exact
resource URI from the authenticated v1 API, verifies its strong ETag and
normative schema, records the resynchronization cursor, and only then resumes.
Absence or transport failure is never interpreted as a policy denial or state
transition.

## Verification

`scripts/contracts/lint_projections.py` resolves every API/event reference
offline, verifies schema IDs and RFC 8785 digests, checks AsyncAPI delivery and
authority traits, freezes the exact server/channel/operation/security topology,
requires exact event-registry/AsyncAPI-enum/example agreement,
requires each example URI to resolve to one authoritative OpenAPI GET, and
validates all seven examples against the CloudEvents envelope and normative
event-data schema. Seven closed consumer/inbox conformance cases
cover next-sequence projection, duplicate/replay, reorder, gap resynchronization,
unknown-schema resynchronization, sensitive-payload redaction, and dead-letter
evidence preservation. No case permits an authoritative write.
