# ByteDesk Platform integration profile

## Status

Planned reference integration. It is intentionally not implemented as part of
the standalone repository extraction.

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
  remain reusable foundations; its Platform-owned baseline/overlay assumption
  is replaced for this integration.
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
references source, render, specialization, compatibility, trust, and policy
digests rather than copying the portable definition.

The existing `AgentDeploymentRevision` and `AgentDeploymentObservation` remain
the Platform aggregate; integration evolves them instead of introducing a
second receipt authority.

## V3 deployment binding

The Platform deployment projection adds:

- a per-profile deployment subdigest;
- a durable Hermes runtime slot;
- an engine release manifest containing exact active profile subdigests;
- explicit source, render, private deployment, overlay, policy, grant, and
  profile descriptors; and
- predecessor, rollout, canary, activation, failure, and forward-rollback
  evidence.

ADR-0182's runtime tuple must bind:

`AgentOrgProfileId + TenantId + HermesEngineId + stable profile slot + profile deployment subdigest + current engine release`.

Updating one employee definition changes that profile subdigest and the engine
release without rotating unrelated principals or credentials. A change to the
system package is explicitly engine-wide.

## Stable Hermes slots

Each `HermesEngine` maintains:

`AgentOrgProfileId -> slot ID -> Hermes profile name + UID + GID + API port + systemd service + workspace + generation`.

Allocation is independent of roster order. Existing employee slots are
backfilled without creating new profiles or workload principals. Retired slots
are tombstoned and not reused without an audited host reset.

## Tenant Git and GitHub App

Tenant Git stores `bytedesk.agent-binding/1` with an exact upstream digest and
non-authorizing specialization. It does not copy the base agent.

The Development service owns numeric repository ID, installation authority,
default branch/path policy, exact commit resolution, HMAC webhook receipt, and
scheduled reconciliation. Repository names are never authority.

Development publishes a signed, sanitized, versioned candidate event through a
transactional outbox. Office consumes through an idempotent inbox. Raw payloads
and GitHub installation tokens do not cross the service boundary.

## Platform process

The Platform projection follows:

`received -> fetched -> validated -> quarantined -> evaluating -> approved|rejected -> rendered -> signed -> staged -> canary -> promoted|rolled_back`.

Long-running operations use the Platform Tool Action lifecycle. One
tenant/profile or engine rollout lease plus compare-and-swap desired state
prevents competing writers. Scheduled reconciliation covers missed events.

## Hosted Hermes Adapter

The host identity is certificate-bound to one tenant and `HermesEngineId` and
may only read desired deployment and append observations for that engine. It is
not a human `OfficeWorkforceProvisionProduction` actor and not an agent MCP
principal. Its private-registry pull credential is separately scoped and
rotated.

Canary evidence proves process health, exact profile identity, Platform
workload login, one granted MCP discovery/invocation, and denial of one
ungranted capability.

Rollback creates a new forward Platform revision using last-known-good
definition content plus **current** grants, lifecycle, credentials, policy, and
slot state.

## Source cutover

Hermes and OpenClaw integrations become deterministic generated outputs. Their
legacy files stop being canonical after a direct, evidence-backed cutover.
There is no dual activation writer and no silent fallback to legacy content.

Hermes definition delivery changes do not change ADR-0180's executable-work
authority. OpenClaw tools, MCP, and provider configuration remain consuming-
platform concerns.

## Future Platform work

The historical BDP-3301 through BDP-3319 items are transfer records, not an
active Platform implementation epic. A future Platform integration should be a
new, explicitly scoped epic that begins only after core Agent Delivery
contracts are implemented and released. It should consume published versions,
not copy product code back into Platform.
