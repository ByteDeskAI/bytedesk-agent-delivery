# AD-10: Expose catalog, inspect, render, and installation APIs

- Historical Jira: [BDP-3311](https://bytedesk.atlassian.net/browse/BDP-3311)
- Delivery role: Core product control plane
- Release gate: Blocks automated consumers and CLI installation flows

## Outcome

Expose the normative consumer-neutral HTTP and event contracts for public
artifact operations, installations, commands, asynchronous actions, desired
state, observations, and receipts without making notification events or API
clients an authority source.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Installation, definition-binding, and receipt persistence from AD-09.
- CONTRACTS-FROZEN OpenAPI 3.2.0, AsyncAPI 3.1.0, CloudEvents 1.0.2,
  JSON Schema, RFC 9457, ETag/CAS, idempotency, pagination, and compatibility
  profiles.
- Consumer authentication, authorization-decision, subject-resolution, and idempotency adapter contracts.

## Required work

1. Add paginated and filterable catalog and package-inspection endpoints using registry/catalog adapters with bounded cache and digest verification.
2. Expose renderer capability/compatibility and deterministic render request/status endpoints. Anonymous public endpoints accept only public source and declared public skill inputs and reject consumer bindings/customization. Local-private preview and authenticated consumer operations may accept private customization and private skills. Operations longer than two seconds use an asynchronous operation resource with status, progress, cancellation, correlation, and terminal evidence.
3. Add installation preview and commit endpoints with explicit modes: `create-installation`, `bind-existing-subject`, or a consumer-adapter-mediated `create-consumer-subject`. Preview shows the deterministic functional property/file delta, exact public/private skills, effective render inputs, and separate security-authority requirements. Core Agent Delivery never creates a consumer identity directly.
4. Require authenticated installation scope, a consumer authorization decision for mutating operations, validation of subject/target ownership, explicit collision/rename handling, and mandatory idempotency keys for commit.
5. Return exact source/render digests, trust/policy evidence, compatibility warnings, required consumer inputs, and no implied MCP, tool, resource, provider, identity, or credential access.
6. Fail closed when registry, trust, policy, or consumer authorization dependencies are unavailable for commit. Bounded read-only cached catalog metadata may be returned only when marked stale and never used as deployment authority.
7. Emit audit and outbox events with stable problem/error codes.
8. Accept authoritative request objects as strict JSON. Any explicit YAML authoring/import surface applies the restricted YAML profile before the API domain model. Digest-bearing request/response resources expose or reproduce RFC 8785 JCS bytes; duplicate JSON member names and non-finite numbers fail closed.
9. Generate the signed OpenAPI document from the normative schemas; implement
   strong ETags, `If-None-Match: *` creation, `If-Match` mutation, cursor
   pagination, RFC 9457 problems, stable codes, explicit scopes/rate limits, and
   idempotency-key plus canonical-request-digest collision behavior.
10. Publish notification-only CloudEvents through a transactional outbox and
    describe them in AsyncAPI. Events carry exact data-schema ID/digest,
    aggregate revision/sequence, correlation/causation, consumer scope, and
    redaction; gaps or unknown schemas stop projections and force API resync.
11. Expose Promotion Coordinator commands and TargetDeliveryState reads without
    adding a second desired writer. API credentials, events, operators, and
    generated clients cannot bypass revision-plus-digest CAS.
12. Generate deterministic Go, Python, and TypeScript models/clients from the
    frozen language-neutral schemas and API contracts. Pin every generator and
    configuration input, keep generated output non-authoritative, and fail a
    clean-tree regeneration check on any drift. Generated clients must preserve
    strict unknown-field behavior, exact digest/revision types, conditional
    request headers, idempotency semantics, and closed error/result variants.

## Outputs

- Versioned API contracts, endpoints, and OpenAPI document.
- Signed OpenAPI/AsyncAPI artifacts derived from the offline schema bundle;
  deterministic Go, Python, and TypeScript models/clients; the
  CloudEvents/outbox/inbox contract; pinned generation manifests; and
  clean-tree drift tests.
- Registry/catalog, renderer, consumer-subject, and authorization-decision application adapters.
- Preview/commit installation and binding flow.
- Authentication, authorization-decision, idempotency, failure-mode, and contract tests.

## Acceptance criteria

- Installation/import never grants tools, MCP access, providers, resources, roles, or workload credentials implicitly.
- A caller can create one Agent Delivery installation and bind exactly one explicit consumer subject/target after preview. Consumer subject creation occurs only through an explicit consumer adapter operation.
- Repeating a commit idempotency key returns the original result without duplicate installations, consumer subjects, or bindings.
- Cross-installation and cross-consumer subject binding is denied.
- Responses expose digests and verification state sufficient for independent reproduction.
- Public responses never contain consumer customization or private skill evidence; authenticated private responses expose exact redacted customization/effective-render lineage.
- API behavior and errors do not assume ByteDesk Platform, Hermes, or any one consumer identity model.
- Every mutation enforces strong ETag plus absent/match preconditions; event
  replay cannot mutate authority and a sequence gap triggers exact API resync.
- Commands and authority objects reject unknown fields while optional read-model
  and notification additions follow explicit compatibility rules.
- Equivalent allowed YAML imported through an authoring surface and strict JSON submitted through the API resolve to the same canonical object and digest; presentation formatting is never authority.
- A clean checkout can regenerate every released Go, Python, and TypeScript
  model/client byte-for-byte with pinned tooling, and no generated artifact can
  add authority, weaken validation, or bypass preconditions present in the
  normative schemas and API contract.

## Verification

Run schema-to-OpenAPI/AsyncAPI/generated-client drift, OpenAPI 3.2 and AsyncAPI
3.1 lint, ETag/absent/match/412, idempotency replay/collision, RFC 9457,
pagination/sort, scope/rate-limit, async cancellation, consumer authority,
duplicate/reorder/gap/dead-letter/API-resync CloudEvents, redaction, availability
and p95 command/read latency, outage, and current/previous minor compatibility
tests.

## Not in scope

Marketplace UI, a specific consumer's employee/profile API implementation, issuing identities or grants, or the CLI.

## Dependencies

Blocked by AD-09 only.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.control-plane-api-events/1`
  (`submit-command`, `read-resource`, `append-host-observation`,
  `append-capability-evidence`, `subscribe-events`, `resynchronize-events`),
  `bytedesk.port.catalog/1` (`list-catalog-releases`,
  `resolve-catalog-release`, `fetch-catalog-object`),
  `bytedesk.port.renderer-strategy/1` (`describe-capabilities`, `render`),
  `bytedesk.port.consumer-projection/1` (`resolve-consumer-subject`,
  `project-consumer-receipt`), and
  `bytedesk.port.consumer-authority-approval/1`
  (`verify-private-authority`) are registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Exact schema IDs include
  `https://schemas.bytedesk.ai/agent-delivery/v1/command-request/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/action/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/problem-details/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/event-data/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/installation/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/observation/1.0.0`. Versioned
  transport projections are `contracts/openapi/v1/agent-delivery.openapi.json`
  and `contracts/asyncapi/v1/agent-delivery.asyncapi.json`; they are derived from
  and drift-checked against the normative product and port schemas. Durable
  action, problem, and event authority is in
  `contracts/ports/v1/action-catalog.json`,
  `contracts/ports/v1/problem-catalog.json`, and
  `contracts/events/v1/event-types.json`. Authentication, pagination, and
  idempotency profiles are in `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-10 owns HTTP/event topology, authentication,
  conditional requests, idempotency, durable actions, stable problems,
  pagination, replay/resync, generated-client drift, and compatibility fixtures.
  Run `make verify-downstream-ports`; the task-specific suite is
  `downstream.api-events.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Boundary.** The API accepts intent and evidence but cannot bypass the
  Promotion Coordinator, create consumer identity directly, or make an event a
  desired-state/authorization source. Public results remain tenant-free; private
  results are consumer-scoped and redacted.

## Architecture review amendments

- Catalog responses derive from a signed content-addressed index; cached metadata is never deployment authority.
- Installation accepts an exact source descriptor, complete renderer-release
  descriptor verified by the compiled allowlist, installation scope, current
  consumer decision, idempotency key, absent/match precondition, and explicit
  create-or-bind mode.
- Marketplace name, title, and slug are suggestions only. Updates never change reporting line, employment, capacity, lifecycle, roles, authorization, or a durable consumer subject identifier.
- Slug/name conflicts and renames are resolved explicitly without identity replacement.
- Long-running render, evaluate, publish, import, and installation operations expose a first-class asynchronous operation contract. A ByteDesk consumer adapter may project this into its Tool Action Pattern, but the core API is consumer-neutral.
