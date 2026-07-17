# AD-02: Bootstrap the public Agent Spec marketplace repository

- Historical Jira: [BDP-3304](https://bytedesk.atlassian.net/browse/BDP-3304)
- Delivery role: Reference-catalog track, delivered in a separate definition-only Git repository
- Core release gate: No
- Reference gate: Prepares `REFERENCE-CATALOG-CERT`

## Outcome

Create `ByteDeskAI/bytedesk-agent-marketplace` as a public, MIT-licensed, third-party-consumable authoring repository with Agent Spec 26.1.2 as the canonical contract. The marketplace is a separate Git source containing definitions and portable skills; it contains no Agent Delivery control-plane code and demands no MCP or runtime resources.

## Inputs

- Accepted AD-01 architecture and repository/package layout.
- The exact `CONTRACTS-FROZEN` schema bundle, canonical-encoding profile,
  source-kind rules, strict operation profiles, and generic catalog contract.
- Official Agent Spec 26.1.2 schema, SDK, and validation behavior.
- ByteDesk organization repository standards that do not introduce ByteDesk Platform or Agent Delivery runtime coupling.

## Required work

1. Create the public repository with a protected default branch, CODEOWNERS, security policy, contribution guide, release/versioning policy, changelog, and reproducible local/CI commands.
2. Establish a minimal directory contract for agents, specialized agents,
   optional portable skills, generated discovery projections, signed contract-
   bundle pins, tests, and examples. Normative Agent Delivery schemas and all
   renderer/control-plane code stay in the product release.
3. Pin Agent Spec 26.1.2 and validate every source definition with the official validator for that exact version.
4. Add public-marketplace policy validation that rejects required MCP servers, tool grants, resource grants, provider credentials, tenant identifiers, workload bindings, and other consumer authority. This restriction does not prevent a consumer from adding functional configuration later through its private customization.
5. Define stable IDs, semantic versions, channel metadata, deprecation, compatibility declarations, and deterministic package inputs.
6. Generate an OASF discovery projection without making it authoritative.
7. Add CI fixtures for valid Agent and SpecializedAgent packages and forbidden runtime-coupled packages.
8. Accept human-authored YAML only through the YAML 1.2 JSON-compatible subset, convert valid documents to the JSON data model, and use RFC 8785 JCS bytes as the canonical source object for semantic digests. Retain original YAML only in Git provenance, not as artifact authority.
9. Add examples for `Agent` and intentional portable `SpecializedAgent`
   source kinds plus strict functional/file/skill operations, without
   representing private authority or making catalog examples normative.

## Outputs

- Public MIT-licensed definition-only repository with a clean-clone contributor workflow.
- Exact signed contract-bundle descriptor plus catalog-owned policy and example
  fixtures; no forked normative Agent Delivery schema.
- Deterministic catalog index and generated OASF projection.
- CI proving validation, policy rejection, deterministic output, and absence of secrets.
- YAML/JSON equivalence plus parser-differential and JCS golden fixtures.
- Contributor documentation sufficient for a third party to publish an agent without ByteDesk services.

## Acceptance criteria

- A clean clone can validate and build the empty/sample catalog with one documented command.
- Changing any canonical input changes the calculated source content digest; timestamps and machine paths do not.
- Forbidden MCP, grant, resource, credential, provider, tenant, or identity fields fail with actionable paths.
- Optional portable skills may be absent without blocking validation or import.
- Validation requires no dependency on `bytedesk-platform`, Agent Delivery services, private credentials, or a runtime harness.
- Failure or non-completion of this repository does not block CORE-CERT.
- The catalog repository contains definitions and distributable assets only; publishing, rendering, signing, deployment, and authorization remain outside it.
- Duplicate keys, aliases, custom tags, non-string keys, and non-finite numbers fail before validation; arbitrary payload files remain byte-exact and are not parsed merely because of their extension.

## Verification

Run repository tests and linters twice from clean state and compare outputs
byte-for-byte. Resolve the pinned contract bundle offline, run official Agent
Spec plus schema/policy fixtures under two validators, prove YAML/JSON JCS
identity, reject forbidden constructs, and run secret, license, link, drift, and
dependency checks proving no control-plane or consumer-platform runtime
dependency.

## Not in scope

Migrating all employee agents, OCI publication, harness renderers, Agent Delivery APIs, consuming-platform APIs, or runtime authorization.

## Dependencies

Blocked by AD-01 only.

## Architecture review amendments

- Validate non-normative `bytedesk.agent-binding/1` examples against the
  released contract bundle. They pin the exact source and complete renderer-
  release descriptors plus strict functional/file/skill operations; the
  marketplace does not own or fork the binding schema.
- Pin and invoke the official Agent Spec 26.1.2 SDK; do not approximate the schema.
- Reject `additional_tools`, toolboxes, remote/provider endpoints, embedded credentials/API keys, MCP, permission metadata, and approval weakening in public packages. Private customization may add functional tool, MCP, provider, model, and harness configuration plus opaque secret references, but security authority and raw secret values remain consumer-owned and external.
- Canonical `LlmConfig` uses logical `model_id: default`; the harness or consumer resolves a real model.
- Agent Delivery artifact digests/signatures never cover the YAML representation directly. Commit provenance may identify the authored file, while canonical JSON determines semantic identity.
- Treat packages and skills as untrusted data throughout publication and delivery. Skills may contain arbitrary declared regular files, including scripts, binaries, archives, data, and dependency manifests. Enforce path, symlink/hardlink/device/FIFO, depth, count, size, decompression, secret, malware, license, and dependency policies. Never execute skill files or hooks during validation, rendering, compilation, staging, or activation; a consumer runtime may execute them only after explicit approval of the exact skill digest under current consumer sandbox, network, identity, and call-time authorization controls.
- `office-orchestrator` is a system package. In the ByteDesk reference consumer it never creates an organizational profile or workload principal; other consumers must express equivalent non-selectability through their own policy.
