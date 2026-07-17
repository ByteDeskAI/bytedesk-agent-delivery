# ByteDesk Platform integration profile

## Status

Planned reference-consumer integration. It is intentionally outside standalone
core completion and cannot begin cutover until a released core has passed
`CORE-CERT`. ByteDesk catalog content has its separate
`REFERENCE-CATALOG-CERT`; this integration closes only after
`REFERENCE-CONSUMER-CERT`.

The Agent Delivery core reference stack is fixed by
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md),
but it is not imposed on ByteDesk Platform. Platform may implement its Consumer
Authority, Capability Verifier, host, and consumer-native desired-state Adapters
with its own language, persistence, identity, and runtime services, provided it
passes the same versioned port contracts and preserves the one-writer,
purpose-separated authority boundary.

## Boundary

ByteDesk Platform consumes Agent Delivery through an Adapter. It remains the
authority for organizations, tenants, users, `AgentOrgProfile`, employment and
reporting relationships, lifecycle, roles, MCP grants, provider connections,
credentials, workload identity, conversations, and Hermes Kanban work.

Agent Delivery owns portable definitions, deterministic renders, OCI graph,
delivery lifecycle, and evidence contracts. The marketplace does not become a
Platform microservice or database-owned definition plane.

## Existing Platform foundations retained

- ADR-0180 remains the Hermes Kanban executable-work authority and shared-host
  trust boundary.
- ADR-0182 remains workload identity, role/grant, MCP call-time authorization,
  sender-constrained token, and fail-closed security authority.
- ADR-0174 remains the skill quarantine, evaluation, approval, revocation, and
  high-risk human-gate authority.
- ADR-0187's HMAC ingress, numeric repository binding, immutable commit
  resolution, quarantine/review, no host `git pull`, and credential boundaries
  remain reusable foundations; its legacy Platform-owned baseline-plus-local-
  patch assumption is replaced for this integration.
- BDP-3282 delivered relevant webhook-ingress foundation. It does not make
  Platform the Agent Delivery product owner.
- BDP-3235 remains the separate identity and MCP-grant security program.

## Identity binding

`AgentOrgProfile.Id` is the durable organizational identity. A catalog slug is
only a definition identifier. Import requires an explicit choice:

- create a new profile through Platform's authorized workflow; or
- bind the definition to an existing profile.

Import never creates grants, roles, provider connections, or credentials.
`office-orchestrator` is a non-selectable system package and never creates an
`AgentOrgProfile` or workload principal.

Office should persist append-only `AgentDefinitionBindingRevision` data that
references source, public catalog render, deterministic private customization,
exact renderer-release/executed-distribution/contract-bundle descriptors,
effective render, compatibility, trust, authority, and policy digests rather
than copying the portable definition as an unexplained mutable profile field.

The first binding uses the exact `absent` precondition. Every later binding uses
`match` with both current revision and canonical digest. Functional property
operations use the strict JSON Pointer add/replace/remove profile; file and
skill replace/remove operations bind the expected current digest. Unknown
fields, partial patches, unstable three-way rebase, and stale/ABA updates fail.

The private customization may override any functional Agent Spec property and
add, replace, or remove arbitrary regular files and public/private skills. It may
configure Platform-selected models, providers, tools, MCP servers, harness
settings, and opaque secret references. Platform identity, roles, grants,
credential values, workload identity, trust roots, and mandatory security policy
remain separate Platform authority inputs.

The existing `AgentDeploymentRevision` family implements the one
`TargetDeliveryState` DesiredStateStore Adapter for this profile; integration
evolves it instead of introducing a second desired-state or receipt authority.
The Agent Delivery Promotion Coordinator is the sole logical writer and writes
through that Adapter by revision-and-digest CAS. Other Platform tables and
events are read models or intent/evidence sources, never competing writers.

## V3 deployment binding

The Platform deployment projection adds:

- a per-profile deployment subdigest;
- a durable Hermes runtime slot;
- an engine release manifest containing exact active profile subdigests;
- explicit source, public render, private customization, exact skill, embedded
  effective render, private deployment, policy, grant, and profile descriptors;
  and
- predecessor, rollout, canary, activation, failure, and forward-recovery
  evidence.

ADR-0182's runtime tuple must bind:

`AgentOrgProfileId + TenantId + HermesEngineId + stable profile slot + profile deployment subdigest + current engine release`.

Updating one employee definition changes that profile subdigest and the engine
release without rotating unrelated principals or credentials. A change to the
system package is explicitly engine-wide.

## Platform authority and private signing

Office exposes the consumer authority Adapter. For compile, activation, and
recovery it emits a signed, short-lived snapshot bound to tenant,
`AgentOrgProfileId`, installation, candidate, desired revision,
`HermesEngineId`, slot/generation, operation, nonce, predecessor, expiry, and
current policy, grant, credential-set, workload-identity, lifecycle, mandatory-
control, approval, and target-binding subdigests. It contains no secret or
workload credential and is refreshed before activation.

ADR-0174 remains the skill/business approval authority. Platform emits exact-
digest approval evidence; neither the marketplace publisher nor Agent Delivery
can approve a skill for a tenant.

Production private-skill, authority/approval, and deployment/release signing
use separate non-exportable tenant-scoped KMS key versions and workload
identities. Platform controls their immutable trust-policy IDs/digests and
revocation. A
shared cross-tenant private signer is forbidden. Agent Delivery may receive a
narrow WIF/OIDC grant to use the tenant deployment key but cannot administer or
export it; the compiler's deployment key can never sign Platform authority or
approval evidence.

## Stable Hermes slots

Each `HermesEngine` maintains:

`AgentOrgProfileId -> slot ID -> Hermes profile name + UID + GID + API port + systemd service + workspace + generation`.

Allocation is independent of roster order. Existing employee slots are
backfilled without creating new profiles or workload principals. Retired slots
are tombstoned and not reused without an audited host reset.

## Tenant Git and GitHub App

Tenant Git stores `bytedesk.agent-binding/1` with an exact upstream digest and
a deterministic private functional-customization delta, exact renderer-release
descriptor, and revision/digest precondition. It may modify any functional
property and declare strict file/skill add/replace/remove operations without
mutating the public base. Security authority remains outside the binding. Git
is reviewed binding intent, not runtime desired state.

Platform authors may use YAML for this Git-facing document, but Development
accepts only the YAML 1.2 JSON-compatible subset and rejects duplicate keys,
aliases, custom tags, non-string keys, and non-finite numbers. It converts the
validated object to the JSON data model and RFC 8785 JCS bytes before calculating
the binding digest or requesting a signature. The original YAML remains Git
provenance and never determines semantic identity. Arbitrary skill payload files
are still preserved as exact bytes regardless of extension.

The Development service owns numeric repository ID, installation authority,
default branch/path policy, exact commit resolution, HMAC webhook receipt, and
scheduled reconciliation. Repository names are never authority.

Development publishes a signed, sanitized, versioned candidate event through a
transactional outbox. Office consumes through an idempotent inbox. Raw payloads
and GitHub installation tokens do not cross the service boundary.

The event is CloudEvents 1.0.2 structured JSON described by AsyncAPI 3.1.0 and
references an exact Draft 2020-12 data-schema digest. It is an at-least-once
wake-up notification, not authority. Office deduplicates by source/id, enforces
per-binding sequence, and fetches exact authoritative state on a gap.

## Platform process

Platform keeps installation, candidate preparation, target rollout, host
attempt, and active-slot facts separate. Candidate preparation fetches,
validates, quarantines/evaluates, awaits ADR-0174 approval where required,
fully compiles/rerenders, signs, and yields an immutable prepared candidate.
Rollout then stages, preflights, follows the certified Hermes activation mode,
collects technical and capability evidence, and is promoted only by the
Promotion Coordinator.

`compiled` includes the full Hermes effective render embedded in the private
deployment; it does not create a separate private-render artifact. There is no
direct `canary -> rolled_back` state. Pre-switch failure leaves the predecessor
active; post-switch failure becomes `recovery_required` until a separately
compiled forward revision is promoted.

Long-running operations project into the Platform Tool Action lifecycle without
using it as domain-state authority. One target rollout lease prevents duplicate
workers, while exact CAS remains authoritative. Scheduled reconciliation covers
missed events and always resolves current intent/state rather than replaying a
stale event as a command.

## Hosted Hermes Adapter

The host identity is certificate-bound to one tenant and `HermesEngineId` and
may only read desired deployment and append observations for that engine. It is
not a human `OfficeWorkforceProvisionProduction` actor and not an agent MCP
principal. Its private-registry pull credential is separately scoped and
rotated.

The host returns technical evidence for artifact/file/slot/process identity,
resources, readiness, and switch state. It does not perform Platform login or
invoke MCP. A distinct Platform Capability Verifier drives the candidate
through the normal workload-login and MCP authorization path using a short-
lived candidate-bound identity that is never given to the host. It proves one
non-destructive granted discovery/invocation and one known ungranted sentinel.
Only ADR-0182's expected authorization-denial result counts; timeout, transport
failure, missing MCP, or `404` does not.

The Agent Delivery Promotion Coordinator issues the nonce-bound plan and
requires fresh matching host and Platform evidence for the exact tenant,
profile, engine, candidate, desired revision, slot, and current authority
digests before CAS promotion.

The private compiler resolves the customization plus the exact Platform-approved
public/private skill set, reconstructs the complete effective Agent Spec, and
fully rerenders it with the exact signed Hermes renderer release recorded by
public lineage and present in the product's compiled allowlist. The deployment
records the renderer-release, executed worker/distribution, allowlist, and
schema digests. The effective manifest and files are embedded in the private
deployment artifact; they are never published
as a public render and are never produced by patching an already rendered public
bundle. An exact public bundle may be reused only when customization is empty and
all normalized source, renderer, parameter, and skill inputs match.

Skill packages may contain arbitrary regular files, including executable code.
Agent Delivery and the host do not execute them during validation, rendering,
compilation, staging, or activation. Hermes may execute a skill only after
Platform explicitly approves its exact digest and under current Platform-owned
runtime isolation, network, workload identity, and call-time authorization. Any
changed skill digest returns to quarantine.

Forward recovery searches prior promoted functional content newest first. It
rejects withdrawn/compromised/unavailable content, expired skill approval, and
content that current trusted Hermes tooling cannot rebuild. It never executes a
revoked renderer or reactivates an old deployment, receipt, signature, or
authority snapshot. The new Platform revision uses the current target revision
as predecessor and binds **current** grants, lifecycle, credential references,
policy, controls, target, and slot state. If no candidate qualifies, Platform
fails closed to its explicit isolate/stop/temporary-hold incident policy.
Recovery creation does not wait for Git; a reviewed Git back-sync follows.

## Source cutover

Hermes and OpenClaw integrations become deterministic generated outputs. Their
legacy files stop being canonical after a direct, evidence-backed cutover.
There is no dual activation writer and no silent fallback to legacy content.

Hermes definition delivery changes do not change ADR-0180's executable-work
authority. OpenClaw tools, MCP, and provider configuration remain consuming-
platform concerns.

## Contract and operational conformance

Platform consumes the released signed contract bundle: JSON Schema Draft
2020-12, canonical JCS objects, OpenAPI 3.2.0, RFC 9457 errors, CloudEvents
1.0.2, and AsyncAPI 3.1.0. Generated Platform models cannot diverge from those
schemas. Unknown command/authority fields, renderer/schema/policy digests, and
illegal transitions fail closed.

The reference integration must meet the Agent Delivery availability, latency,
desired-state propagation, scale, limits, retention, RPO/RTO, backup/restore,
telemetry/audit, security-response, upgrade, and support profile or publish an
explicitly stricter Platform profile. It must prove tenant noisy-neighbor and
cross-tenant signing/registry/desired-state isolation.

## Future Platform work

The historical BDP-3301 through BDP-3319 items are transfer records, not an
active Platform implementation epic. A future Platform integration should be a
new, explicitly scoped epic that begins only after core Agent Delivery
contracts are implemented, certified, and released. It should consume published
versions, not copy product code back into Platform. The ByteDesk catalog and
Platform cutovers close separate reference certifications and cannot be used to
claim that standalone core is ready.
