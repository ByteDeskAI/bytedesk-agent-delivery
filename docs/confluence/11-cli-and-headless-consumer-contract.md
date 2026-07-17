# CLI and headless consumer contract

## Headless first

Agent Delivery's first complete surface is a versioned HTTP API plus the
`bd-agent` command-line client. A marketplace UI can be added later as another
client. Public interoperability must never require browser automation, ByteDesk
Platform credentials, or access to an internal database.

## Client modes

The CLI supports two explicit modes:

- **Public/offline mode** for catalog, validation, rendering, artifact
  inspection, and signature verification.
- **Authenticated consumer mode** for installations, bindings, update
  proposals, private deployment, rollout, and receipt retrieval.

Authentication is configured by the invoking consumer. The CLI accepts a
short-lived token or external credential helper and never stores a long-lived
provider, registry, KMS, or MCP credential in its project files.

## Command families

The initial command map is:

```text
bd-agent catalog search|show|releases
bd-agent definition validate|inspect
bd-agent render capabilities|preview|build
bd-agent artifact inspect|verify|graph
bd-agent installation preview|create|show|bind|update|retire
bd-agent operation show|watch|cancel
bd-agent deployment compile|status|rollout|rollback
bd-agent receipt show|verify|export
bd-agent conformance run
```

Exact command names may be frozen with the API, but scripts depend on stable
machine-readable behavior rather than formatted terminal prose.

## Public workflow example

```sh
bd-agent catalog search --catalog registry.example.com/agents/catalog@sha256:... --json
bd-agent definition inspect registry.example.com/agents/source/chief-of-staff@sha256:... --json
bd-agent render preview --source registry.example.com/agents/source/chief-of-staff@sha256:... --harness hermes --renderer 1.0.0 --json
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
profile or bind an existing one. It never creates identity, roles, MCP grants,
provider connections, or credentials implicitly.

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

Human output is concise and may evolve. JSON fields are additive within a
version; breaking changes require a new version.

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

Long-running commands return an operation identifier. `operation watch` polls
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

Update and rollout commands also accept an expected predecessor. This prevents
automation from overwriting a newer human or concurrent decision.

## API versioning and errors

The HTTP API uses explicit resource and schema versions. Errors use a stable
problem shape containing code, safe message, correlation, retryability, field
violations, expected/current revisions where relevant, and documentation link.
Server stack traces, tokens, secret references, and raw provider payloads are
never returned.

CLI and SDK releases publish a compatibility matrix with server API versions.
Unknown security-relevant response fields do not silently alter client
verification.

## Authentication and authorization

Public endpoints are rate-limited but do not require a ByteDesk identity.
Private endpoints authenticate a consumer integration identity and authorize
consumer, tenant, operation, and resource scope. A host identity uses the
separate narrow desired-state/observation contract.

An agent workload token is not valid as a deployment administrator token. An
MCP grant is not an Agent Delivery API role. These authority planes stay
separate.

## Secret handling

The CLI:

- redacts authorization headers, token claims, credential helpers, and signed
  URLs;
- refuses obvious secret values in portable definitions and bindings;
- writes private temporary files with restrictive permissions;
- removes temporary content after completion where safe;
- supports credential input through standard secure helper mechanisms; and
- never embeds a secret in a receipt export.

## SDK and third-party integration

The API schema is sufficient to generate or maintain SDKs without access to the
implementation repository. A conforming consumer can catalog, validate, render,
verify, install, and observe using only published contracts.

Reference conformance proves a clean third party can exercise public commands
and OCI verification with no Platform services. Authenticated conformance uses
a generic consumer Adapter fixture rather than hardcoded ByteDesk identity or
MCP data.

## Related pages

- [Data model and API ownership](07-data-model-api-and-service-ownership.md)
- [Consumer integration contract](../architecture/consumer-integration-contract.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
