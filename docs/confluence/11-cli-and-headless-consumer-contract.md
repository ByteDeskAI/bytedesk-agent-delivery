# CLI and headless consumer contract

## Headless first

Agent Delivery's first complete surface is a versioned HTTP API plus the
`bd-agent` command-line client. A marketplace UI can be added later as another
client. Public interoperability must never require browser automation, ByteDesk
Platform credentials, or access to an internal database.

The normative HTTP description is OpenAPI 3.2.0 with JSON Schema Draft 2020-12
as its declared dialect. It references the same closed source schemas shipped
with their transitive references, fixtures, AsyncAPI 3.1.0 document, and
CloudEvents 1.0.2 event schemas in the signed offline contract bundle. Generated
SDKs and documentation are drift-checked outputs, not competing schemas.

The supported `bd-agent` Go client, server build, release platforms, locked
toolchain, API deployment, and local development profile are fixed by
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md).
HTTP and event contracts remain language-neutral; third-party clients do not
need Go and consumer integrations do not inherit the server topology.

## Client modes

The CLI supports two explicit modes:

- **Public/offline mode** for tenant-free catalog, validation, rendering,
  artifact inspection, and signature verification. Public operations reject
  bindings, customization, private skills, opaque secret references, and tenant
  metadata.
- **Authenticated consumer mode** for installations, bindings, update
  proposals, private deployment, rollout, and receipt retrieval.

Authentication is configured by the invoking consumer. The CLI accepts a
short-lived token or external credential helper and never stores a long-lived
provider, registry, KMS, or MCP credential in its project files.

Private commands obtain fresh operation-bound signed consumer-authority
snapshots and verify signed exact-digest skill approvals. They never ask a
deployment signer to approve itself. Production private signing uses
purpose-separated consumer-owned or explicitly opted-in tenant-dedicated
non-exportable keys; a shared cross-consumer private key is rejected.

For a declared contract such as a binding or trust policy, YAML is accepted
only as human-authored local input. The CLI uses the YAML 1.2 JSON-compatible
subset and rejects duplicate keys, aliases, custom tags, non-string mapping
keys, and non-finite numbers. It converts accepted input to the JSON data model
before sending an authority-bearing request. If original authoring YAML is
retained with an integrity
reference, that reference is provenance/storage-integrity evidence only and
never semantic identity, artifact authority, or activation authority. Arbitrary
payload files, including files
named `.yaml` or `.json`, remain opaque exact bytes and are not contract-parsed
based on extension.

## Command families

The initial command map is:

```text
bd-agent contract verify
bd-agent catalog search|show|releases
bd-agent definition validate|inspect
bd-agent render capabilities|preview|build
bd-agent package validate|build
bd-agent artifact publish|pull|inspect|verify|graph
bd-agent installation preview|create|show|bind|update|retire
bd-agent operation show|watch|cancel
bd-agent deployment compile|status|rollout|recover
bd-agent receipt show|verify|export
bd-agent conformance run
```

Exact command names may be frozen with the API, but scripts depend on stable
machine-readable behavior rather than formatted terminal prose.

`package build` creates deterministic local OCI content without a remote side
effect. `artifact publish` is the only publication command and is explicit and
authenticated; `render` never publishes implicitly. `artifact pull` always
resolves and verifies an exact digest.

`deployment recover` creates a forward-recovery request. It never reactivates an
old artifact or receipt and does not depend on Git availability; status exposes
the failed rollout, current predecessor, selected `recoverySource`, eligibility
report, current-tooling lineage, and new revision.

## Public workflow example

```sh
bd-agent catalog search --catalog registry.example.com/agents/catalog@sha256:... --json
bd-agent definition inspect registry.example.com/agents/source/chief-of-staff@sha256:... --json
bd-agent render preview --source registry.example.com/agents/source/chief-of-staff@sha256:... --harness hermes --renderer-release registry.example.com/agent-delivery/renderers/hermes@sha256:... --json
bd-agent artifact verify registry.example.com/agents/render/hermes/chief-of-staff@sha256:... --policy ./trust/public.yaml --json
```

These commands can run without a ByteDesk account. A local trust policy is
configured independently of the artifact.

## Authenticated workflow example

```sh
bd-agent installation preview --consumer acme --binding ./chief-of-staff.binding.yaml --json
bd-agent installation create --consumer acme --binding ./chief-of-staff.binding.yaml --idempotency-key 7d0f... --json
bd-agent operation watch op_01... --json
bd-agent deployment status --consumer acme --runtime runtime_01 --json
bd-agent receipt verify receipt_01 --json
```

Import requires an explicit consumer choice to create a new consumer-owned
profile or bind an existing one. A private binding may describe functional
tools/MCP/provider/model/harness configuration, opaque secret references, safe
regular-file operations, and public/private skills. Import never turns those
descriptions into identity, roles, MCP/tool grants, provider access, credentials,
skill-execution approval, or sandbox authority implicitly.

## Output contract

Every command supports stable JSON. JSON output includes:

- schema version;
- command and request/correlation identifier;
- normalized inputs with secrets redacted;
- resource or operation state;
- exact artifact descriptors and compatibility result;
- warnings and denial codes;
- links or identifiers for follow-up resources; and
- terminal success or failure evidence.

Installation, candidate preparation, target rollout, and host reconciliation
states are separate objects. CLI output never collapses them into one status or
reports `rolled_back` directly from canary. A post-switch failure is
`recovery_required` until a separately compiled forward rollout is promoted.

Human output is concise and may evolve. Optional fields may be additive only in
declared non-authoritative read models and notification data. Commands, signed
authority objects, manifests, desired state, attestations, and receipts are
closed; an unknown field fails. Breaking changes require a new major schema.

Pretty-printed command output is not a canonical byte format. Whenever a
structured resource is hashed or signed, the resource's JSON data model is
serialized as RFC 8785 JCS bytes. Original YAML may be included only as
provenance under the non-authoritative rule above, and arbitrary payload inputs
or outputs retain exact raw-byte identity.

The CLI sends logs and progress to standard error and the requested result to
standard output so pipelines can parse output safely.

## Exit codes

Exit codes distinguish at least:

- success;
- validation or policy denial;
- authentication or authorization failure;
- conflict/predecessor mismatch;
- unavailable dependency or retryable operation failure;
- terminal operation failure;
- unsupported compatibility; and
- client usage or local configuration error.

A non-terminal asynchronous operation is not reported as completed merely
because the initial request was accepted.

## Asynchronous operations

Work that may exceed two seconds returns `202 Accepted`, `Location`, and a
durable action identifier. `operation watch` polls
with backoff or uses a supported authenticated event stream, resumes after
disconnect, and terminates only on a durable terminal state. Timeout stops the
client wait, not server work. Cancellation is an explicit request.

Progress fields are phase, completed work, total work when known, and last
durable checkpoint. Clients do not scrape log text to infer state.

## Idempotency

State-changing commands accept an idempotency key. Retrying the same normalized
request returns the original resource or operation. Reusing a key with changed
input returns a conflict and identifies the original request without revealing
sensitive values.

Structured request normalization compares RFC 8785 JCS bytes. YAML whitespace,
comments, key order, scalar spelling, and quoting therefore do not create a new
request when they produce the same accepted JSON data model.

Creation commands require the `absent` precondition and HTTP
`If-None-Match: *`. Updates, promotion, cancellation, and recovery require the
exact current revision and canonical digest through `match` plus strong
`If-Match`; a mismatch returns `412` without effects. The accepted record
separately names immutable predecessor lineage. Omitted, null, wildcard,
digest-only, lease-based, or break-glass bypasses are invalid.

## API versioning and errors

The HTTP API uses `/v1`, cursor pagination with stable documented sort, strong
ETags, and exact resource/schema versions. Errors use RFC 9457
`application/problem+json` with a stable problem-type URI, machine code, safe
message, correlation, retryability, field
violations, expected/current revisions where relevant, and documentation link.
Server stack traces, tokens, secret references, and raw provider payloads are
never returned.

CLI and SDK releases publish a compatibility matrix with server API versions.
Unknown security-relevant response fields do not silently alter client
verification.

The HTTP wire contract uses JSON for authority-bearing objects. API schema
validation and RFC 8785 canonicalization are separate steps: successful schema
validation does not make a non-canonical wire serialization the signed or
digest-bearing byte sequence.

## Authentication and authorization

Public endpoints are rate-limited but do not require a ByteDesk identity. They
fail closed on any customization or private input. Private endpoints
authenticate a consumer integration identity and authorize consumer, tenant,
operation, and resource scope. Only authenticated private deployment compilation
accepts a binding/customization and produces the fully rerendered effective
bundle embedded in a deployment. A host identity uses the separate narrow
desired-state/observation contract.

All target mutations are commands to the Promotion Coordinator, the sole
logical writer of one target aggregate through its one selected
`DesiredStateStore`. The CLI, Git, consumer application, compiler, host, and
event stream cannot write desired state directly. Events are at-least-once
CloudEvents notifications; unknown schemas or sequence gaps require API resync.

An agent workload token is not valid as a deployment administrator token. An
MCP grant is not an Agent Delivery API role. These authority planes stay
separate.

## Secret handling

The CLI:

- redacts authorization headers, token claims, credential helpers, and signed
  URLs;
- refuses customization in public commands and raw secret values in portable
  definitions or private bindings while allowing validated opaque references in
  authenticated private workflows;
- writes private temporary files with restrictive permissions;
- removes temporary content after completion where safe;
- supports credential input through standard secure helper mechanisms; and
- never embeds a raw secret in a receipt export; and
- never executes a package or skill script, binary, install command, or hook.

## SDK and third-party integration

The API schema is sufficient to generate or maintain SDKs without access to the
implementation repository. A conforming consumer can catalog, validate, render
tenant-free public content, verify, install, privately compile a fully customized
deployment, and observe using only published contracts.

Reference conformance proves a clean third party can exercise public commands
and OCI verification with no Platform services. Authenticated conformance uses
a generic consumer Adapter fixture rather than hardcoded ByteDesk identity or
MCP data.

GA API/CLI readiness uses the published availability and latency objectives,
24-month major support, previous-major overlap, 12-month/two-minor deprecation
window, current/previous minor rolling interoperability, and signed readiness
evidence in [Operational readiness v1](../standards/operational-readiness-v1.md).

## Related pages

- [Data model and API ownership](07-data-model-api-and-service-ownership.md)
- [Consumer integration contract](../architecture/consumer-integration-contract.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
