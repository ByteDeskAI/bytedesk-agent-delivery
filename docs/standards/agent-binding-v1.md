# Agent binding v1

**Logical schema:** `bytedesk.agent-binding/1`

**Status:** Draft contract; freeze before the first public artifact

## Purpose

The binding records a consumer's intent to install an exact portable agent for
a declared harness without copying the upstream definition or granting runtime
authority.

## Minimum document

```yaml
schema: bytedesk.agent-binding/1
agentId: chief-of-staff
agentSpecVersion: 26.1.2
source:
  repository: registry.example/agents/source/chief-of-staff
  digest: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
harness:
  id: hermes
  rendererVersion: 1.0.0
specialization:
  additionalInstructions: |
    Customer-specific, non-authorizing context.
  metadata:
    customerLabel: Example Customer
updatePolicy:
  channel: stable
  automaticCompatibleUpdates: true
expectedPredecessor: sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd
```

## Required invariants

- `schema` is exact and unknown versions fail closed.
- `agentId` matches the verified source package identifier.
- `agentSpecVersion` is explicitly supported by the selected renderer.
- `source.repository` is canonicalized before policy comparison.
- `source.digest` is a full `sha256` digest; tags and branches are forbidden.
- `harness.id` and `rendererVersion` resolve through the compiled allowlist.
- `expectedPredecessor` is required for updates and compare-and-swap.
- Serialization used for the binding digest is canonical and versioned.

## Allowed specialization

V1 permits only:

- additional behavioral instructions that do not request or imply authority;
- non-authorizing display or classification metadata; and
- a human-in-the-loop change that makes the consumer stricter.

Consumers may define a narrower metadata allowlist. Unknown fields fail closed.

## Forbidden fields and semantics

The binding rejects:

- tools, `additional_tools`, toolboxes, MCP servers, or resource grants;
- providers, model credentials, API keys, endpoints, or secret references;
- users, roles, permissions, business grants, or workload identity;
- tenant escape fields or a consumer/runtime target not supplied separately by
  the authenticated consumer Adapter;
- remote executable URLs, package hooks, install commands, or renderer plugins;
- a copied or caller-substituted base definition;
- mutable Git or OCI references; and
- any approval change that weakens consumer policy.

Instruction text is also scanned for known authority-smuggling patterns. Text
cannot be treated as a grant even when it claims permission.

## Resolution

Resolution performs these steps:

1. validate the envelope and canonicalize it;
2. fetch and verify the exact source descriptor;
3. validate the source with the official pinned Agent Spec SDK;
4. apply the specialization to a verified in-memory base;
5. reject any forbidden effective field or weakened approval behavior;
6. emit a complete valid Agent Spec `SpecializedAgent` as deterministic build
   output; and
7. record binding, source, renderer, compatibility, and output digests.

The resolved full definition is output, never installation source of truth.

## Compatible update

An automatic proposal may advance `source.digest` only when the expected
predecessor still matches, the skill digest set is unchanged, compatibility is
non-lossy, no forbidden authority appears, and consumer evaluation permits it.
The proposal is a new signed commit or append-only revision; history is not
rewritten.

## Test fixtures

Contract tests must include valid minimal/full bindings plus denial fixtures for
every forbidden category, unknown fields, malformed/case-confused repositories,
tag references, digest mismatch, predecessor mismatch, source substitution,
approval weakening, YAML aliases/duplicate keys, and oversized instructions.
