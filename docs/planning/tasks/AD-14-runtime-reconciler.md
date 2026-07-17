# AD-14: Reconcile verified deployment artifacts into hosted runtimes

- Historical Jira: [BDP-3315](https://bytedesk.atlassian.net/browse/BDP-3315)
- Delivery role: Core product host protocol and reconciler
- Release gate: Required for managed hosted deployment; harness adapters may be released independently

## Outcome

Safely apply an exact verified private deployment artifact to a hosted runtime through staging, canary, health gates, atomic activation, observations, and forward-only compensation rollback. The core protocol is harness-neutral; Hermes support is one target adapter.

## Inputs

- Prepared consumer deployment artifact and append-only receipt from AD-13.
- Target-scoped host/reconciler protocol and a compile-time allowlisted harness runtime adapter.
- Consumer integration hooks for current subject/target/lifecycle/binding validation and optional allowed/denied capability checks.
- Existing Hermes deployment, provision, and verification operations as reference-adapter evidence.

## Required work

1. Pull by exact digest with least-privilege private-registry credentials and verify deployment → render → source trust before extraction.
2. Re-check installation, consumer subject, target, runtime slot/generation, desired-state revision, lifecycle, opaque workload-identity/credential/authorization references, and consumer approval verdict against current consumer state through the adapter.
3. Apply inert content into an isolated staging revision, validate archive safety, ownership, modes, configuration, disk budget, and target constraints, and never execute package hooks.
4. Run a bounded canary proving process health, correct subject/target binding, and consumer-supplied positive and negative capability checks. For ByteDesk this can include workload login plus one granted and one denied MCP operation; Agent Delivery records the signed verdict but never makes the authorization decision or receives broad MCP authority.
5. Atomically activate only after every gate passes and append observed evidence to the deployment receipt.
6. On failure, request compilation and application of a new forward receipt targeting last-known-good definition content with current consumer authority references. Never reactivate an old receipt or rewrite Git/deployment history.
7. Support idempotent retries, cancellation, timeout, dead-letter/replay, and recovery after reconciler, process, or host restart.

## Outputs

- Digest-pinned host reconciliation protocol and reference reconciler.
- Harness runtime Adapter interface plus a Hermes implementation/profile.
- Isolated staging and atomic activation mechanism.
- Forward-only rollback request/compiler/reconciler path.
- Health/certification observations attached to deployment receipts.
- Non-production E2E and fault-injection tests.

## Acceptance criteria

- No artifact applies before trust and exact installation/subject/target binding pass.
- A successful receipt identifies the exact running digest, target slot/generation, consumer-verdict references, and observed health.
- Canary failure leaves active content unchanged before switch or restores last-known-good definition content through a new signed forward receipt after switch.
- Consumer authorization remains fail-closed: the positive capability verdict must succeed and the negative verdict must remain denied, without giving the reconciler broad runtime-agent or human-administrator authority.
- Duplicate and restarted operations converge without duplicate activation.
- The core reconciler does not assume ByteDesk identity, Office roles, MCP grants, or Hermes-specific state outside the Hermes adapter.

## Verification

Run baseline deployment, consumer-supplied positive/negative capability proof, wrong signer/digest/installation/subject/target/revision tests, canary fault, interrupted activation recovery, forward-only rollback, restart verification, partial pull, disk-full, registry outage, and credential-rotation tests.

## Not in scope

Production rollout, consumer identity/grant administration, source-directory deletion, or a specific consumer's canonical-source cutover.

## Dependencies

Blocked by AD-10, AD-12, and AD-13.

## Architecture review amendments

- Introduce an exact installation- and target-bound host identity with read-desired, scoped registry-pull, and append-observation authority for one target. It cannot use human administration or a runtime agent/MCP principal.
- Provision scoped private-registry pull credentials per installation and target and rotate/revoke them independently.
- Persist and reconcile desired, pulling, verified, staged, activating, active, last-known-good, failed, rollback-requested, and rolled-back facts. Crash recovery distinguishes pre-switch from post-switch and appends observation evidence.
- Preserve stable slots, UID/GID, ports, services, and workspaces during migration. Retired slots are tombstoned and never reused without durable purge plus a host-reset ceremony; system packages use explicitly reserved slots.
- Treat runtime slots as operations/capacity boundaries, not universal security isolation. Consumer policy decides when separate hosts or engines are required.
- Reject unsafe archives; stage by digest; switch only at a harness-safe boundary. Partial pull, disk full, crash, registry outage, credential rotation, unsafe boundary, and observation-delivery retry are mandatory tests.
