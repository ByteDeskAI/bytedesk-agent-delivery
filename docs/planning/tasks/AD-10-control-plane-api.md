# AD-10: Expose catalog, inspect, render, and installation APIs

- Historical Jira: [BDP-3311](https://bytedesk.atlassian.net/browse/BDP-3311)
- Delivery role: Core product control plane
- Release gate: Blocks automated consumers and CLI installation flows

## Outcome

Expose authenticated, consumer-neutral APIs that let clients discover public marketplace agents, inspect verified provenance, request a harness render, preview an installation, and bind an exact artifact to a consumer-owned subject and target.

## Inputs

- Public signed catalog/index and OCI artifacts.
- Renderer registry.
- Installation, definition-binding, and receipt persistence from AD-09.
- Consumer authentication, authorization-decision, subject-resolution, and idempotency adapter contracts.

## Required work

1. Add paginated and filterable catalog and package-inspection endpoints using registry/catalog adapters with bounded cache and digest verification.
2. Expose renderer capability/compatibility and deterministic render request/status endpoints. Operations longer than two seconds use an asynchronous operation resource with status, progress, cancellation, correlation, and terminal evidence.
3. Add installation preview and commit endpoints with explicit modes: `create-installation`, `bind-existing-subject`, or a consumer-adapter-mediated `create-consumer-subject`. Core Agent Delivery never creates a consumer identity directly.
4. Require authenticated installation scope, a consumer authorization decision for mutating operations, validation of subject/target ownership, explicit collision/rename handling, and mandatory idempotency keys for commit.
5. Return exact source/render digests, trust/policy evidence, compatibility warnings, required consumer inputs, and no implied MCP, tool, resource, provider, identity, or credential access.
6. Fail closed when registry, trust, policy, or consumer authorization dependencies are unavailable for commit. Bounded read-only cached catalog metadata may be returned only when marked stale and never used as deployment authority.
7. Emit audit and outbox events with stable problem/error codes.

## Outputs

- Versioned API contracts, endpoints, and OpenAPI document.
- Registry/catalog, renderer, consumer-subject, and authorization-decision application adapters.
- Preview/commit installation and binding flow.
- Authentication, authorization-decision, idempotency, failure-mode, and contract tests.

## Acceptance criteria

- Installation/import never grants tools, MCP access, providers, resources, roles, or workload credentials implicitly.
- A caller can create one Agent Delivery installation and bind exactly one explicit consumer subject/target after preview. Consumer subject creation occurs only through an explicit consumer adapter operation.
- Repeating a commit idempotency key returns the original result without duplicate installations, consumer subjects, or bindings.
- Cross-installation and cross-consumer subject binding is denied.
- Responses expose digests and verification state sufficient for independent reproduction.
- API behavior and errors do not assume ByteDesk Platform, Hermes, or any one consumer identity model.

## Verification

Run unit tests, API integration tests, consumer-authorization matrix tests, duplicate/replay and collision tests, registry outage and trust failure tests, adapter unavailability tests, and OpenAPI lint/compatibility checks.

## Not in scope

Marketplace UI, a specific consumer's employee/profile API implementation, issuing identities or grants, or the CLI.

## Dependencies

Blocked by AD-04, AD-08, and AD-09. AD-03 supplies the production-size catalog fixture.

## Architecture review amendments

- Catalog responses derive from a signed content-addressed index; cached metadata is never deployment authority.
- Installation accepts a compile-time allowlisted harness identifier, exact source digest, installation scope, consumer authorization decision, idempotency key, and explicit create-or-bind mode.
- Marketplace name, title, and slug are suggestions only. Updates never change reporting line, employment, capacity, lifecycle, roles, authorization, or a durable consumer subject identifier.
- Slug/name conflicts and renames are resolved explicitly without identity replacement.
- Long-running render, evaluate, publish, import, and installation operations expose a first-class asynchronous operation contract. A ByteDesk consumer adapter may project this into its Tool Action Pattern, but the core API is consumer-neutral.
