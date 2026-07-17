# Agent Spec and the binding profile

## Why Agent Spec is canonical

Agent Delivery uses Agent Spec as the portable semantic source instead of
creating another harness-specific agent dialect. Version one pins Agent Spec
`26.1.2`; publication, import, and rendering use the official SDK for that
exact version. A later Agent Spec release is a deliberate compatibility change,
not a floating dependency.

The accepted top-level forms are `Agent` and `SpecializedAgent`. Their semantic
meaning remains defined by Agent Spec. Product-specific distribution and
consumer binding are defined separately in [Agent binding v1](../standards/agent-binding-v1.md).

## Portable definition profile

A reusable package contains only content that can travel safely between
consumers:

- stable definition identifier and descriptive catalog metadata;
- instructions, persona, goals, response guidance, and supported Agent Spec
  semantics;
- a logical `LlmConfig` such as `model_id: default`, not a concrete credentialed
  provider connection;
- optional, inspectable, non-executing skill content; and
- compatibility metadata that describes requirements without granting them.

Packages must remain useful when optional skills are unavailable. A consumer
can discover, validate, import, and render the definition while omitting a skill
that is unapproved, quarantined, or unsupported.

## Non-authority rule

Portable content may describe behavior, but it may not create authority. The
validator rejects fields or attachments that attempt to supply:

- MCP server configuration or required MCP grants;
- tools, toolboxes, `additional_tools`, or resource entitlements;
- organization, tenant, role, employment, or reporting-line identity;
- provider endpoints, account identifiers, API keys, credentials, or secret
  references;
- workload principals, certificates, token audiences, or sender constraints;
- consumer approval policy that becomes less strict;
- engine/profile bindings or runtime filesystem identities; or
- package-directed executable hooks or remote code URLs.

A catalog entry may state a non-binding capability hint for discovery, but the
consumer must explicitly map and authorize every runtime capability. Absence of
that mapping does not invalidate the portable definition; it means the runtime
does not receive that capability.

## Why a binding envelope is needed

Agent Spec's `SpecializedAgent` contains a complete base agent. Storing a full
consumer copy would duplicate upstream content, hide provenance, and allow a
caller to substitute a modified base. Agent Delivery therefore stores a small
envelope that references an exact upstream source digest and adds only
non-authorizing specialization.

An illustrative binding is:

```yaml
schema: bytedesk.agent-binding/1
agentId: chief-of-staff
agentSpecVersion: 26.1.2
source:
  repository: registry.example.com/agents/source/chief-of-staff
  digest: sha256:0123456789abcdef...
harness:
  id: hermes
  rendererVersion: 1.0.0
specialization:
  additionalInstructions: |
    Use the customer's approved terminology and escalation paths.
  metadata:
    customerLabel: Example Customer
updatePolicy:
  channel: stable
  automaticCompatibleUpdates: true
expectedPredecessor: sha256:fedcba9876543210...
```

The normative field set, constraints, and canonicalization rules live in
[Agent binding v1](../standards/agent-binding-v1.md).

## Allowlisted specialization

The v1 envelope can select:

- one exact source repository and digest;
- one exact Agent Spec version;
- one compile-time allowlisted harness and renderer version;
- additional natural-language instructions;
- non-authorizing labels and customer metadata;
- a compatible update channel and automation preference; and
- an expected predecessor for compare-and-swap updates.

If an approval field is supported, it can only make the consumer's separate
approval policy stricter. The envelope cannot weaken human-in-the-loop policy.

The binding rejects mutable source references, copied base definitions,
authority-bearing fields, caller-selected trust roots, and arbitrary extension
objects. Unknown fields fail validation instead of being ignored.

## Resolution and render

Resolution is deterministic:

1. Parse the envelope with a versioned, strict schema.
2. Resolve the source by repository plus exact digest.
3. Verify media type, signer policy, provenance, and withdrawal state.
4. Validate the source with the official pinned Agent Spec SDK.
5. Apply the product's non-authority policy.
6. Normalize the allowlisted specialization.
7. Construct a complete Agent Spec `SpecializedAgent` in memory.
8. Validate the resolved document again with the official SDK.
9. Select the exact renderer and emit its render manifest.

The complete copied base exists only in deterministic build output. It is never
accepted as tenant-authored source.

## Skills

Skills are separately addressed attachments. Their digest set participates in
compatibility and update decisions. A new or changed skill is never silently
activated as part of an otherwise compatible instruction update. Consumers may
quarantine, scan, evaluate, approve, omit, or revoke skills according to local
policy.

Skills cannot carry secrets, provider connections, grants, or executable
installation hooks. If a runtime needs a package manager or code dependency,
that dependency belongs to a separately governed runtime image or consumer
deployment layer.

## Compatibility outcomes

Validation and rendering distinguish:

- **exact**: all selected semantics are represented without change;
- **compatible with warnings**: representation differs but approved behavior is
  preserved;
- **lossy**: one or more semantics cannot be preserved and promotion requires
  explicit human acceptance; and
- **unsupported**: the selected renderer cannot produce a valid target.

No Adapter silently drops an unsupported field. Compatibility output is signed
and bound to the source digest, renderer digest, and normalized parameters.

## Baseline conformance fixture

The reference fixtures contain exactly 34 selectable employee-agent packages
and one non-selectable `office-orchestrator` package. Tests prove that each
valid definition passes official Agent Spec validation, contains no authority
fields, and renders deterministically. The orchestrator fixture additionally
proves that importing a system package does not request or create an identity,
MCP grant, role, or credential.

## Consumer-owned runtime configuration

After render, the consumer may attach concrete model configuration, provider
connections, runtime identity, and MCP access in its private deployment compile.
Those inputs are independently sourced from current consumer state. They are
not copied from the definition or binding, and a rollback recompiles them from
current state rather than restoring stale authority.

## Related pages

- [Marketplace and baseline catalog](03-marketplace-repository-and-baseline-catalog.md)
- [Harness adapters and renderers](04-harness-adapters-and-renderers.md)
- [Consumer integration contract](../architecture/consumer-integration-contract.md)
