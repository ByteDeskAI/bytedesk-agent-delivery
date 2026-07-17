# Runtime reconciliation

## Objective

Converge one runtime target on an exact, verified desired deployment without
giving the host broad platform authority or allowing artifacts to execute
installation logic.

## Identity and permissions

Each reconciler identity is bound to one consumer and one runtime target. It can
read that target's desired state, pull from the matching private registry scope,
and append observations for the same target. It cannot provision identities,
change grants, perform human administration, or invoke agent MCP capabilities.

## Reconciliation loop

1. Read the latest desired-state revision.
2. Compare it to observed active and staged revisions.
3. Pull every artifact by exact digest.
4. Verify media types, full signature/attestation graph, consumer and target
   binding, predecessor, withdrawal, and revocation.
5. Extract inert content with safe archive rules into a fresh staging area.
6. Validate files, ownership, modes, slot, ports, service definition, and disk
   budget.
7. Run static/preflight checks without executing package hooks.
8. Switch only at a harness-safe boundary.
9. Run canary health and consumer-supplied allowed/denied capability checks.
10. Append the observation and retain last-known-good.

## Persisted states

`desired`, `pulling`, `verified`, `staged`, `activating`, `active`, `failed`,
`rollback_requested`, and `rolled_back` are durable facts. Recovery determines
whether a crash happened before or after the activation switch rather than
guessing from files alone.

## Failure and rollback

A failed pre-switch deployment leaves active content untouched. A failed
post-switch canary requests a new forward deployment compiled from the
last-known-good definition and current consumer authority. The old receipt is
never reactivated.

The test matrix includes partial pulls, disk exhaustion, corrupt layers,
registry outage, KMS outage, crash before/after switch, process restart,
credential rotation, unsafe run boundary, canary failure, and observation
delivery retry.

## Stable slots

Any harness mapping agents to UID/GID, port, service, or workspace uses a
durable allocation independent of catalog order. Retired slots are tombstoned.
Reuse requires a separately audited host-reset ceremony.
