# Agent binding v1

**Logical contract:** `bytedesk.agent-binding/1`

**Status:** Accepted architecture contract; concrete Draft 2020-12 schema and
fixtures are release-blocking deliverables

## Purpose

The binding records a consumer's private intent to install an exact portable
agent through one exact renderer release. It carries a deterministic functional
customization delta against verified public source rather than a copied base
definition. It is not identity, a credential, a role, a grant, a trust policy,
a business approval, desired runtime state, or a call-time authorization
decision.

Public catalog and render endpoints reject bindings. An authenticated private
path or non-publishing local private workflow may accept one. A public Agent
Spec `SpecializedAgent` remains portable source and is never shorthand for this
private delta.

This contract uses [Canonical encoding v1](canonical-encoding-v1.md), the
schemas and operation profiles in
[Machine contracts v1](machine-contracts-v1.md), the renderer descriptor in
[Renderer identity v1](renderer-identity-v1.md), and separate authority and
approval evidence from
[Consumer authority and private signing v1](consumer-authority-v1.md).

## Representative document

The YAML below is non-authoritative authoring input. The accepted object is
validated by the exact independently trusted schema ID/digest and its RFC 8785
JSON serialization carries semantic identity.

```yaml
contract: bytedesk.agent-binding/1
schema:
  id: https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0
  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
agentId: chief-of-staff
agentSpecVersion: 26.1.2
sourceKind: agent
source:
  repository: registry.example/agents/source/chief-of-staff
  digest: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  mediaType: application/vnd.bytedesk.agent.source.v1+json
  size: 16384
  trustPolicy:
    id: public-source-v1
    digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
renderer:
  harnessId: hermes
  rendererId: hermes
  version: 1.0.0
  release:
    repository: registry.example/bytedesk/product/renderers/hermes
    digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
    mediaType: application/vnd.bytedesk.agent.renderer-release.v1+json
    size: 32768
    trustPolicy:
      id: product-release-v1
      digest: sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
customization:
  profile: bytedesk.json-patch/1
  agentSpecOperations:
    - op: replace
      path: /llm_config/model_id
      value: acme-approved-model
    - op: replace
      path: /system_prompt
      value: Follow Acme operating guidance and escalation procedures.
  harnessConfigurationOperations:
    - op: add
      path: /workspaceLayout
      value: acme-chief-of-staff
  fileOperations:
    - op: add
      path: guidance/acme-escalation.md
      content:
        repository: registry.acme.example/agent-inputs/files
        digest: sha256:1111111111111111111111111111111111111111111111111111111111111111
        mediaType: application/octet-stream
        size: 2048
        trustPolicy:
          id: acme-private-file-v1
          digest: sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
      mode: "0644"
    - op: remove
      path: guidance/default-escalation.md
      expectedContentDigest: sha256:3333333333333333333333333333333333333333333333333333333333333333
  skillOperations:
    - op: add
      packageId: acme-escalation
      descriptor:
        repository: registry.acme.example/agent-skills/escalation
        digest: sha256:2222222222222222222222222222222222222222222222222222222222222222
        mediaType: application/vnd.bytedesk.agent.skill.v1+json
        size: 8192
        trustPolicy:
          id: consumer-private-skill-v1
          digest: sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
updatePolicy:
  channel: stable
  automaticCompatibleUpdates: true
precondition:
  kind: match
  revision: 7
  digest: sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd
```

Initial creation instead requires:

```yaml
precondition:
  kind: absent
```

Omission, `null`, wildcard, force, digest-only, and revision-only
preconditions are invalid. An accepted immutable binding revision separately
records `predecessor: { kind: none }` for revision one or the exact prior
revision and digest.

## Required invariants

- `contract`, schema `$id`, and schema digest are exact. The schema must already
  exist in the independently trusted signed contract bundle; the binding cannot
  nominate a new validator.
- `agentId` identifies verified public-package lineage even when functional
  customization changes effective display or semantic fields.
- `sourceKind` is `agent` or `specialized-agent` and agrees with the official
  Agent Spec document. `Agent` is the default standalone form.
- The complete source descriptor is immutable. Tags, branches, missing sizes,
  and mutable repository aliases are forbidden.
- The complete renderer-release descriptor is required and must map exactly to
  the running product distribution's compiled allowlist. A version string,
  source commit, image tag, PATH binary, or local build is insufficient.
- `agentSpecVersion` and every renderer-owned schema digest must be supported by
  that exact renderer release.
- The required `precondition` is `absent` for create or `match` with both the
  current monotonic revision and canonical digest for update.
- Every object is closed except an explicitly registered typed extension point.
  Unknown schemas, fields, operations, extension namespaces, and enum values
  fail closed.
- Accepted YAML is authoring input only. Binding, operation, descriptor, and
  opaque-reference identity uses the validated JSON data model and RFC 8785.

## Functional property operations

Agent Spec and harness configuration use ordered `bytedesk.json-patch/1`:

- only closed `add`, `replace`, and `remove` operation objects are valid;
- paths are RFC 6901 JSON Pointers without URI-fragment form;
- the empty root pointer cannot be changed;
- parent paths must exist;
- object `add` requires absence, while final `-` may append to an array;
- `replace` and `remove` require an existing target;
- canonical array indices have no leading zero; and
- one failed operation rejects the complete delta without a partial result.

The Agent Spec and renderer-owned harness-configuration roots contain only
functional values. Source lineage, schema identity, renderer selection, trust,
consumer identity, grants, credentials, target, desired state, and mandatory
security controls are not patchable roots.

The consumer may override any functional Agent Spec or renderer-configuration
property, including instructions, behavior, metadata, model selection, provider
endpoints, tools, MCP servers, resources, and opaque references to consumer-
managed secrets. Configuration describes desired function; it never grants the
configured capability. The complete output is revalidated by the official
pinned Agent Spec SDK, exact renderer schemas, portability policy, and consumer
policy. A valid kind-changing result records both source and effective kinds and
is breaking, requiring manual promotion.

An automatic source update performs a three-way rebase against the previous
exact source, accepted delta, and proposed exact source. A changed target,
ancestor, parent, or unstable array position conflicts. An old delta is never
blindly replayed.

## File operations

File operations are a separate closed contract, not JSON Patch:

- portable paths are relative POSIX-style Unicode NFC paths;
- empty segments, `.`, `..`, leading slash, backslash, controls, Windows drive
  or device syntax, and normalization/case-fold collisions fail;
- `add` requires absence, exact content descriptor, and safe regular-file mode;
- `replace` requires existence, expected current digest, replacement
  descriptor, and mode;
- `remove` requires existence and expected current digest; and
- a normalized path is targeted at most once in one delta.

Only regular files are valid. Links, devices, FIFOs, sockets, setuid, setgid,
sticky bits, host ownership, automatic hooks, and package-directed fetch or
execution are forbidden. Declared ordinary executable modes are allowed for
skill files. Signed skill contents are not patched internally; replace the
skill descriptor or add a separate regular file.

## Skill operations

Skill operations address a stable package ID and exact descriptor:

- `add` requires an absent ID and new descriptor;
- `replace` requires the ID, expected current digest, and replacement
  descriptor; and
- `remove` requires the ID and expected current digest.

Duplicate IDs, mutable descriptors, ambiguous replacement, or digest mismatch
reject the delta. Every effective public or private skill requires current
consumer-issued `bytedesk.skill-approval/1` evidence for the exact consumer,
subject, installation, target class, use scope, policy, and validity window.
Publisher trust is not execution approval.

Skill packages may contain arbitrary regular files, including instructions,
scripts, binaries, archives, data, images, models, and dependency manifests.
Agent Delivery never executes them during validation, rendering, compilation,
staging, reconciliation, or activation. A runtime may execute approved content
only after activation and under current consumer sandbox, network, workload
identity, and call-time authorization policy.

## Security and authority boundary

The following arrive separately in a current, signed, short-lived
`bytedesk.consumer-authority/1` snapshot and cannot be created, changed, or
weakened by the binding:

- consumer, tenant, organization, user, or durable agent identity;
- roles, permissions, business grants, MCP/tool/resource grants, and call-time
  decisions;
- workload identity, token/certificate issuance, and sender constraints;
- credential values, API keys, tokens, private keys, and credential-set state;
- trust roots, signer policy, key material, and required evidence policy; and
- mandatory sandbox, network, human/business approval, isolation, malware,
  license, lifecycle, and runtime-target controls.

Compilation requires a current snapshot. Activation and recovery require a
fresh snapshot bound to the exact candidate and desired revision. Agent
Delivery verifies opaque subdigests and signatures but does not interpret or
issue consumer authority.

## Resolution and effective rendering

Resolution:

1. parses accepted input, validates the exact binding schema, and creates its
   RFC 8785 identity;
2. verifies the exact public source, source kind, and declared public skills;
3. validates source through the official pinned Agent Spec SDK and portability
   policy;
4. verifies and quarantines every effective file/skill descriptor and current
   consumer skill approval;
5. applies all ordered property, file, and skill operations atomically in a
   confined workspace;
6. validates the complete effective Agent Spec and renderer configuration;
7. verifies a current consumer-authority snapshot independently;
8. resolves the exact renderer release through the compiled allowlist and
   performs a complete sandboxed render from the beginning;
9. embeds the effective render bundle and full manifest in a consumer-private,
   per-consumer-signed deployment; and
10. records every schema, source, binding, customization, skill, renderer
    release, actual executing distribution, authority, compatibility, file, and
    output digest.

The compiler never patches public rendered output. V1 has no separate private-
render OCI type. It may reuse verified public output only when the customization
is empty, effective skill set equals the declared public set, and every schema,
source, skill, renderer release, execution variant, allowlist, parameter, and
normalized input matches exactly.

If the public-lineage renderer is withdrawn or revoked, private compilation does
not fall back. A new public-render lineage under a current trusted compatible
renderer is required.

## Compatible update

An automatic proposal may advance the source only when the exact `match`
precondition succeeds, three-way rebase is conflict-free, the effective skill
set is unchanged, source and renderer compatibility are non-lossy, all schemas
and trust remain supported, consumer authority is current, and policy permits
the update. Renderer or output-kind changes are separate evaluated candidates
and cannot hide inside a source/channel update. Changed skills return to
quarantine and require new consumer approval.

## Failure behavior and verification

Unknown or mismatched schema, source kind, source descriptor, renderer release,
allowlist, executing distribution, trust policy, operation, path, expected
digest, skill approval, consumer authority, precondition, or effective output
fails closed. The system never guesses, drops fields, partially applies a
delta, loads package code, chooses another renderer, or accepts caller-supplied
effective output.

Release fixtures cover minimal/full bindings, `Agent` and `SpecializedAgent`,
both precondition variants, every operation, three-way conflicts, Unicode and
case-fold paths, exact renderer substitution denials, public/private skill
approval, authority-smuggling and secret denials, full rerender, exact public-
output reuse, post-render-patch rejection, archive/resource attacks, YAML/JSON
canonical equivalence, byte-exact arbitrary payloads, and execution spies that
prove input code never runs in Agent Delivery.
