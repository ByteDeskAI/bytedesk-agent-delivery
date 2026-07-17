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
Every Agent Delivery-owned authority object, including the binding envelope,
has a closed JSON Schema Draft 2020-12 schema shipped with its transitive
references and fixtures in the signed contract bundle. The official Agent Spec
SDK remains normative for the embedded Agent Spec document.

Source resolution verifies the exact payload SHA-256 digest and requires those
payload bytes to equal their RFC 8785 representation before exactly one call to
the official Agent Spec `26.1.2` validator. The binding's declared source kind
must match both the official result and root `component_type`. The raw document
must then prove explicit top-level `agentspec_version: 26.1.2`; another or
implicit version and legacy `air_version` fail. A `SpecializedAgent` embeds one
complete `Agent` and one complete `AgentSpecializationParameters` object;
remote, package-relative, generic `$ref`, official `$component_ref` or
`$referenced_components`, and nested-specialization resolution are not
accepted.

## Authoring and authority encoding

Definitions and bindings may be written as YAML for people to review. That
authoring surface accepts only the YAML 1.2 JSON-compatible subset. Parsing
fails on duplicate keys, aliases, custom tags, non-string mapping keys, and
non-finite numbers; a parser must not resolve those constructs differently and
continue.

Accepted YAML is converted to the JSON data model. Before any structured object
is hashed or signed, it is serialized as RFC 8785 JSON Canonicalization Scheme
(JCS) bytes. Canonical JSON, rather than an author's YAML whitespace, comments,
key order, scalar spelling, or quoting, defines semantic identity. Original
YAML may be retained alongside provenance for review. Any integrity reference
to that authoring file is provenance/storage-integrity evidence only, never
semantic identity, artifact authority, or activation authority. Arbitrary
package attachments and skill payload
files are not transcoded or parsed as contracts based on extension: even a
payload named `.yaml` or `.json` has identity over its exact raw bytes.

## Portable definition profile

A reusable package contains only content that can travel safely between
consumers:

- stable definition identifier and descriptive catalog metadata;
- instructions, persona, goals, response guidance, and supported Agent Spec
  semantics;
- a logical `LlmConfig` such as `model_id: default`, not a concrete credentialed
  provider connection;
- optional, separately addressed skills containing arbitrary regular files,
  including scripts and binaries that Agent Delivery never executes; and
- compatibility metadata that describes requirements without granting them.

Packages must remain useful when optional skills are unavailable. Discovery and
validation do not approve or execute them. A consumer that does not select an
optional skill explicitly removes it through the canonical binding skill
operation before private compilation; the resulting exact effective set is
recorded. A selected unapproved, quarantined, unavailable, or unsupported skill
fails closed and is never silently omitted.

## Public definition profile and non-authority rule

Portable public content may describe behavior, but it may not create authority
or carry tenant customization. Public definition, catalog-render, validation,
preview, and build endpoints reject fields or attachments that attempt to
supply:

- MCP server configuration or required MCP grants;
- tools, toolboxes, `additional_tools`, or resource entitlements;
- organization, tenant, role, employment, or reporting-line identity;
- provider endpoints, account identifiers, API keys, credentials, secret
  references, or tenant-specific model/harness configuration;
- workload principals, certificates, token audiences, or sender constraints;
- fields that claim to set or weaken consumer approval or mandatory oversight
  policy;
- engine/profile bindings or runtime filesystem identities; or
- package-directed executable hooks or remote code URLs.

A catalog entry may state a non-binding capability hint for discovery, but the
consumer must explicitly map and authorize every runtime capability. Absence of
that mapping does not invalidate the portable definition; it means the runtime
does not receive that capability.

## Why a binding envelope is needed

Agent Spec's `SpecializedAgent` contains a complete base agent. Storing a full
consumer copy would duplicate upstream content, hide provenance, and allow a
caller to substitute a modified base. Agent Delivery therefore stores a
deterministic delta that references an exact upstream source digest. The delta
may customize any functional Agent Spec property, add, replace, or remove
arbitrary regular files under the package safety rules, and select exact public
or private skills without copying the base.

The binding is private desired configuration, not a grant. It may describe
tools, MCP endpoints and tool selection, provider/model/harness configuration,
and opaque secret references. The consumer independently validates and
authorizes each effective capability, resolves opaque references through its
secret system, and makes every call-time decision. Raw secret values, identity
or role assignments, embedded grants, and approval weakening remain forbidden.

An illustrative binding is:

```yaml
contract: bytedesk.agent-binding/1
schema:
  id: https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0
  digest: sha256:3c2b7490e808d3dd33ba6dea497a0b83b82545caa2b981b05ca997640490a2e7
agentId: chief-of-staff
agentSpecVersion: 26.1.2
sourceKind: agent
source:
  repository: registry.example.com/agents/source/chief-of-staff
  digest: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  mediaType: application/vnd.bytedesk.agent.source.v1+json
  size: 12345
  trustPolicy:
    id: public-source-v1
    digest: sha256:1111111111111111111111111111111111111111111111111111111111111111
renderer:
  harnessId: hermes
  rendererId: hermes
  version: 1.0.0
  release:
    repository: registry.example.com/agent-delivery/renderers/hermes
    digest: sha256:2222222222222222222222222222222222222222222222222222222222222222
    mediaType: application/vnd.bytedesk.agent.renderer-release.v1+json
    size: 16384
    trustPolicy:
      id: product-release-v1
      digest: sha256:3333333333333333333333333333333333333333333333333333333333333333
customization:
  agentSpec:
    profile: bytedesk.json-patch/1
    operations:
      - op: replace
        path: /llm_config/model_id
        value: acme-approved-model
      - op: replace
        path: /system_prompt
        value: Follow Acme operating guidance and escalation procedures.
  harnessConfiguration:
    profile: bytedesk.json-patch/1
    operations:
      - op: add
        path: /workspaceLayout
        value: acme-chief-of-staff
  files:
    contract: bytedesk.file-operations/1
    operations:
      - op: add
        path: guidance/escalation.md
        precondition:
          kind: absent
        content:
          repository: registry.example.com/acme/files
          digest: sha256:4444444444444444444444444444444444444444444444444444444444444444
          mediaType: application/octet-stream
          size: 2048
          trustPolicy:
            id: acme-private-file-v1
            digest: sha256:5555555555555555555555555555555555555555555555555555555555555555
        mode: "0644"
      - op: remove
        path: guidance/default-escalation.md
        precondition:
          kind: match
          digest: sha256:6666666666666666666666666666666666666666666666666666666666666666
  skills:
    contract: bytedesk.skill-operations/1
    operations:
      - op: add
        packageId: acme.escalation
        precondition:
          kind: absent
        descriptor:
          repository: registry.example.com/acme/skills/escalation
          digest: sha256:7777777777777777777777777777777777777777777777777777777777777777
          mediaType: application/vnd.bytedesk.agent.skill.v1+json
          size: 8192
          trustPolicy:
            id: consumer-private-skill-v1
            digest: sha256:8888888888888888888888888888888888888888888888888888888888888888
updatePolicy:
  channel: stable
  automaticCompatibleUpdates: true
precondition:
  kind: match
  revision: 7
  digest: sha256:9999999999999999999999999999999999999999999999999999999999999999
```

This non-normative example is human-authored YAML; its presentation bytes are
not authority. [Agent binding v1](../standards/agent-binding-v1.md) records the
binding invariants. [Machine contracts v1](../standards/machine-contracts-v1.md)
closes the schema, operation, path, extension, and predecessor semantics. AD-01
freezes the concrete schema and fixtures, including
`contracts/fixtures/operations/source-resolution.cases.json` and
`contracts/fixtures/operations/three-way-rebase.cases.json`; the private
compiler, consumer and KMS Adapters, runtime integration, and operational
evidence remain later workstreams.

## Deterministic functional customization

The v1 envelope can select:

- one exact source repository and digest;
- one exact Agent Spec version;
- one compile-time allowlisted harness and complete exact renderer-release
  descriptor, including immutable manifest digest and trust-policy ID/digest;
- a canonical delta over any functional Agent Spec property;
- desired tools, MCP, provider, model, and harness configuration;
- opaque secret references whose values are resolved only by the consumer;
- add, replace, and remove operations for arbitrary regular files under the
  declared package root;
- exact public and private skill descriptors;
- non-authorizing labels and customer metadata;
- a compatible update channel and automation preference; and
- a required revision-and-digest CAS `precondition`: `absent` for initial
  creation or `match` for an update. The accepted record separately carries
  immutable predecessor lineage.

Consumer approval and mandatory oversight policy are not binding fields or
patchable roots, even when a proposed value would appear stricter. The official
Agent Spec `human_in_the_loop` property remains functional and may be
customized, but it never satisfies, weakens, or replaces the consumer's
separate current signed authority/approval requirements.

File operations use normalized relative paths and explicit content digests. They
reject traversal, absolute paths, links, devices, FIFOs, sockets, unsafe archive
entries, undeclared remote fetches, and package hooks. Files may be scripts or
binaries, but their presence does not authorize execution.

Agent Spec and harness-configuration changes use the ordered
`bytedesk.json-patch/1` profile: only RFC 6902 `add`, `replace`, and `remove`
over RFC 6901 JSON Pointer are accepted. Root replacement, `move`, `copy`,
`test`, `from`, URI-fragment pointers, missing parents, non-canonical array
indices, paths outside functional allowlists, and partial application fail.
`add` requires absence; `replace` and `remove` require presence. The complete
result is revalidated.

An automatic source update clones the old and proposed exact sources into
working trees, then applies the operations in order to both. It conflicts when
an operation's target or complete containing top-level subtree differs,
including a changed parent or containing array. The document root is excluded
from that comparison, preserving unrelated top-level upstream changes. This
also permits a later operation to use a parent created earlier in the same
atomic delta. Inputs stay unchanged, and canonical parser limits are rechecked
after each operation and over the final proposed result.

File and skill operations use their own closed schemas rather than JSON Patch.
File paths are NFC-normalized portable POSIX relative paths. An add requires an
absent path; replace/remove require the expected current digest; and one path
may be targeted only once. Skill operations address a stable package ID: add
requires absence, while replace/remove require the expected current digest.
Every descriptor includes repository, digest, media type, size, and immutable
trust-policy ID and digest. Any mismatch aborts the whole delta.

The binding rejects mutable source references, copied base definitions, raw
secret values, identity/role/grant assignments, caller-selected trust roots,
approval weakening, and arbitrary unversioned extension objects. Unknown fields
fail validation instead of being ignored.

## Resolution and render

Resolution is deterministic:

1. Parse JSON or the permitted YAML 1.2 JSON-compatible authoring subset and
   validate the closed Draft 2020-12 binding schema from the exact trusted
   contract bundle, rejecting ambiguous YAML constructs and unknown fields.
2. Convert the accepted envelope to the JSON data model and produce its RFC
   8785 JCS bytes for semantic identity, hashing, and signing.
3. Resolve the source by repository, verify the SHA-256 digest over the exact
   payload, and require the payload itself to be RFC 8785 bytes.
4. Verify media type, signer policy, provenance, and withdrawal state.
5. Call the official Agent Spec `26.1.2` validator exactly once, require the
   declared kind to match its result and root `component_type`, require the raw
   source's explicit exact version field with no legacy substitute, and resolve
   an accepted `SpecializedAgent` only from its one embedded complete `Agent`
   and one embedded complete parameters object without component references.
6. Apply the public definition policy.
7. Normalize and apply the ordered private functional Agent Spec and harness
   configuration operations.
8. Apply the ordered add/replace/remove regular-file operations.
9. Resolve the ordered effective public/private skill set and verify every skill
   by exact digest.
10. Verify a current signed `bytedesk.skill-approval/1` decision for every
    effective skill digest and a fresh signed consumer-authority snapshot for
    the requested compilation operation. Approval and deployment signing use
    separate consumer-isolated keys.
11. Construct a complete effective Agent Spec package in memory.
12. Validate the resolved document again with the official SDK.
13. Verify the exact renderer-release manifest against the product's embedded
    allowlist, execute the declared product distribution/worker digest in its
    sandbox, and perform the complete deterministic render.
14. Embed the effective render bundle and manifest in the private deployment and
    record the tenant-free public-render lineage used to resolve the renderer.

The complete copied base exists only in deterministic private build output. It
is never accepted as tenant-authored source. File customization is applied
before the full render; post-render patching is forbidden. V1 does not publish a
separate private-render artifact.

The compiler may reuse the exact bytes of a public catalog render only when the
customization has no operations, the effective skill set exactly equals the
source-declared public skill set, and every normalized source, skill, renderer,
and parameter input matches. It still verifies and embeds that bundle and
manifest in the private deployment.

## Skills

Skills are separately addressed public or private attachments containing
arbitrary regular files, including scripts and binaries. Their digest set
participates in compatibility and update decisions. Every new or changed skill
digest returns to quarantine and requires scanning, evaluation, and explicit
signed consumer approval under the exact approval-policy digest; it is never
silently activated as part of another update.

The delivery pipeline treats every skill as untrusted data and never executes
its files. A runtime may execute skill content only when consumer policy explicitly approves
that exact digest, supplies the required sandbox and runtime authorization, and
continues to authorize the invocation. Skills cannot contain raw secrets,
embedded grants, package hooks, install commands, unsafe archive entries, or
package-directed remote fetches. Opaque secret references may appear only in a
private binding and are resolved externally by the consumer.

## Compatibility outcomes

Validation and rendering distinguish:

- **exact**: all selected semantics are represented without change;
- **compatible with warnings**: representation differs but approved behavior is
  preserved;
- **lossy**: one or more semantics cannot be preserved and promotion requires
  explicit human acceptance; and
- **unsupported**: the selected renderer cannot produce a valid target.

No Adapter silently drops an unsupported field. Compatibility output is signed
and bound to the source digest, exact renderer-release manifest, actual
executed distribution/worker digest, embedded allowlist and schema digests, and
normalized parameters.

## Reference catalog conformance fixture

After `CORE-CERT`, the `REFERENCE-CATALOG-CERT` fixtures contain exactly 34
selectable employee-agent packages and one non-selectable
`office-orchestrator` package. Tests prove that each
valid definition passes official Agent Spec validation, contains no authority
fields, has the same semantic digest when equivalent accepted YAML and JSON are
used, and renders deterministically. Negative fixtures reject duplicate YAML
keys, aliases, custom tags, non-string mapping keys, and non-finite numbers.
The orchestrator fixture additionally
proves that importing a system package does not request or create an identity,
MCP grant, role, or credential.

## Consumer-owned runtime configuration

The private binding may state desired model, provider, harness, tool, and MCP
configuration plus opaque secret references. During deployment compilation the
consumer supplies independent current authority projections for identity,
policy, grants, credential versions, target, and execution approvals. Desired
configuration never substitutes for those projections, and raw credential
values are never copied into the binding or artifact. Forward recovery selects
only currently eligible previously promoted functional content, never executes
revoked tooling, creates a new public-render lineage when current tooling must
change, and recompiles against fresh signed consumer authority rather than
restoring stale grants or credentials.

## Related pages

- [Marketplace and baseline catalog](03-marketplace-repository-and-baseline-catalog.md)
- [Harness adapters and renderers](04-harness-adapters-and-renderers.md)
- [Consumer integration contract](../architecture/consumer-integration-contract.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
