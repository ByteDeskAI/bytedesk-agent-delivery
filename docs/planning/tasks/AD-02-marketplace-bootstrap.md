# AD-02: Bootstrap the public Agent Spec marketplace repository

- Historical Jira: [BDP-3304](https://bytedesk.atlassian.net/browse/BDP-3304)
- Delivery role: Core product dependency, delivered in a separate definition-only Git repository
- Release gate: Blocks baseline catalog publication

## Outcome

Create `ByteDeskAI/bytedesk-agent-marketplace` as a public, MIT-licensed, third-party-consumable authoring repository with Agent Spec 26.1.2 as the canonical contract. The marketplace is a separate Git source containing definitions and portable skills; it contains no Agent Delivery control-plane code and demands no MCP or runtime resources.

## Inputs

- Accepted AD-01 architecture and repository/package layout.
- Official Agent Spec 26.1.2 schema, SDK, and validation behavior.
- ByteDesk organization repository standards that do not introduce ByteDesk Platform or Agent Delivery runtime coupling.

## Required work

1. Create the public repository with a protected default branch, CODEOWNERS, security policy, contribution guide, release/versioning policy, changelog, and reproducible local/CI commands.
2. Establish a minimal directory contract for agents, specialized agents, optional portable skills, generated discovery projections, schemas/policies, tests, and examples. Renderer/control-plane code stays in this product repository.
3. Pin Agent Spec 26.1.2 and validate every source definition with the official validator for that exact version.
4. Add marketplace policy validation that rejects MCP servers, tool grants, resource grants, provider credentials, tenant identifiers, workload bindings, and other runtime requirements.
5. Define stable IDs, semantic versions, channel metadata, deprecation, compatibility declarations, and deterministic package inputs.
6. Generate an OASF discovery projection without making it authoritative.
7. Add CI fixtures for valid Agent and SpecializedAgent packages and forbidden runtime-coupled packages.

## Outputs

- Public MIT-licensed definition-only repository with a clean-clone contributor workflow.
- Versioned schema and policy fixtures.
- Deterministic catalog index and generated OASF projection.
- CI proving validation, policy rejection, deterministic output, and absence of secrets.
- Contributor documentation sufficient for a third party to publish an agent without ByteDesk services.

## Acceptance criteria

- A clean clone can validate and build the empty/sample catalog with one documented command.
- Changing any canonical input changes the calculated source content digest; timestamps and machine paths do not.
- Forbidden MCP, grant, resource, credential, provider, tenant, or identity fields fail with actionable paths.
- Optional portable skills may be absent without blocking validation or import.
- Validation requires no dependency on `bytedesk-platform`, Agent Delivery services, private credentials, or a runtime harness.
- The catalog repository contains definitions and distributable assets only; publishing, rendering, signing, deployment, and authorization remain outside it.

## Verification

Run repository tests and linters twice from clean state and compare outputs byte-for-byte. Run secret scanning, license checks, negative-policy fixtures, and a dependency audit proving no control-plane or consumer-platform runtime dependency.

## Not in scope

Migrating all employee agents, OCI publication, harness renderers, Agent Delivery APIs, consuming-platform APIs, or runtime authorization.

## Dependencies

Blocked by AD-01.

## Architecture review amendments

- Add and validate `bytedesk.agent-binding/1` examples/schema separately from canonical packages. The envelope contains the exact source OCI digest, exact Agent Spec version, allowlisted specialization instructions/metadata, and no executable base copy.
- Pin and invoke the official Agent Spec 26.1.2 SDK; do not approximate the schema.
- Reject `additional_tools`, toolboxes, remote/provider endpoints, embedded credentials/API keys, MCP, permission metadata, and any human-in-the-loop change that weakens a consuming platform's posture.
- Canonical `LlmConfig` uses logical `model_id: default`; the harness or consumer resolves a real model.
- Treat packages and skills as inert data. Enforce path, symlink/hardlink/device/FIFO, depth, count, size, decompression, secret, malware, license, and dependency policies. Never execute packaged scripts during validation.
- `office-orchestrator` is a system package. In the ByteDesk reference consumer it never creates an organizational profile or workload principal; other consumers must express equivalent non-selectability through their own policy.
