# AD-14: Reconcile verified deployment artifacts into hosted runtimes

- Historical Jira: [BDP-3315](https://bytedesk.atlassian.net/browse/BDP-3315)
- Delivery role: Core product host protocol and reconciler
- Release gate: Required for managed hosted deployment; harness adapters may be released independently

## Outcome

Safely reconcile one exact target to a prepared private release through a
least-privilege host, certified activation mode, separate technical and
consumer-capability evidence, Coordinator-controlled promotion, and newly
compiled forward recovery.

## Inputs

- Prepared consumer deployment artifact and append-only receipt from AD-13.
- Target-scoped host/reconciler protocol and a compile-time allowlisted harness runtime adapter.
- Fresh `activate`/`recover` consumer-authority snapshots, signed canary-plan
  challenges, Promotion Coordinator commands, and the distinct consumer
  capability-verifier Adapter/signing policy.
- Existing Hermes deployment, provision, and verification operations as reference-adapter evidence.

## Required work

1. Pull by exact digest with least-privilege private-registry credentials and verify the deployment's embedded effective render plus explicit public render/source, customization, and skill lineage before extraction.
2. Verify a fresh operation-specific consumer-authority snapshot bound to the
   exact candidate/desired revision and current opaque subdigests. Never reuse
   compilation authority.
3. Apply untrusted content into an isolated staging revision and validate archive safety, ownership, modes, configuration, disk budget, and target constraints. Skill payloads may contain arbitrary declared regular files, including executable files, but the reconciler never runs them, package hooks, installers, or dependency scripts during staging or activation.
4. Implement the harness Adapter's one certified activation mode:
   isolated-candidate or guarded in-place. Persist host attempt and physical
   slot/switch facts separately from target rollout state.
5. Return technical evidence bound to the canary challenge for exact artifact,
   files, process/readiness, slot/generation, resources, and switch/crash marker.
   The host never handles an agent capability credential or invokes MCP/tool/
   provider capabilities.
6. Implement the capability-verifier dispatch/evidence port used by the
   Promotion Coordinator. After matching Host technical evidence arrives, the
   Coordinator—not the Host Reconciler—dispatches a challenge through the
   consumer-owned capability-verifier Adapter. The provisional candidate
   obtains its normal short-lived identity directly from the consumer. Require
   signed workload-login, permitted-capability, and exact policy-denial
   evidence; timeout, 404, network, parser, or unavailable-tool errors do not
   prove denial.
7. Append observations only. The Promotion Coordinator verifies both evidence
   sets and alone CAS-promotes TargetDeliveryState; physical activation is not
   promotion.
8. On post-switch failure, enter `recovery_required` and request a separately
   compiled current-tooling recovery rollout. Never reactivate an old release,
   render, receipt, signature, authority snapshot, or revoked renderer.
9. Support idempotent retries, cancellation, timeout, dead-letter/replay, and recovery after reconciler, process, or host restart.
10. Leave any later execution of skill-provided content to the consuming runtime, and only after explicit consumer approval under consumer-owned sandboxing, workload identity, and call-time authorization. Activation of files is not execution approval.

## Outputs

- Digest-pinned host reconciliation protocol and reference reconciler.
- Harness runtime Adapter interface plus a Hermes implementation/profile.
- Isolated staging and atomic activation mechanism.
- Current-tooling forward-recovery request/compiler/reconciler path.
- Technical canary evidence plus consumer capability-verifier Adapter/evidence
  contracts and Coordinator dispatch contract; neither evidence actor can
  promote, and the Host cannot dispatch capability work.
- Isolated-candidate and guarded-in-place conformance fixtures, with each
  harness selecting exactly one mode.
- Non-production E2E and fault-injection tests.

## Acceptance criteria

- No artifact applies before trust and exact installation/subject/target binding pass.
- A successful receipt identifies the exact running digest, target slot/generation, consumer-verdict references, and observed health.
- Canary failure leaves active content unchanged before switch; post-switch
  failure produces `recovery_required` and only a new eligible recovery
  rollout can become promoted.
- Consumer authorization remains fail-closed: the positive capability verdict must succeed and the negative verdict must remain denied, without giving the reconciler broad runtime-agent or human-administrator authority.
- Duplicate and restarted operations converge without duplicate activation.
- The core reconciler does not assume ByteDesk identity, Office roles, MCP grants, or Hermes-specific state outside the Hermes adapter.
- Staging and activation do not execute skill payloads; a consumer-runtime execution verdict is separately attributable to consumer policy and identity.
- The host cannot write desired state, receive human/agent/MCP authority, run
  capability probes, or label a rollout promoted/recovered.
- Missing, stale, wrong-nonce/candidate/target/actor evidence fails. A signed
  `not_applicable` is accepted only for a certified profile with no external
  capability plane.

## Verification

Run isolated-candidate and guarded-in-place conformance; host read/observe-only
and human/agent/MCP/provider denial; fresh authority; technical and distinct
capability actor nonce/freshness/wrong-candidate/false-denial/not-applicable;
pre/post-switch crash, cancellation/supersession/late evidence, partial pull,
disk/memory limits, unsafe boundary, registry/KMS/consumer outage, credential
rotation, observation retry, no-candidate recovery, current-tooling forward
rebuild, restart convergence, and SLO/soak/chaos tests.

## Not in scope

Production rollout, consumer identity/grant administration, source-directory deletion, or a specific consumer's canonical-source cutover.

## Dependencies

Blocked by AD-09, AD-10, and AD-13.

## Architecture review amendments

- Introduce an exact installation- and target-bound host identity with read-desired, scoped registry-pull, and append-observation authority for one target. It cannot use human administration or a runtime agent/MCP principal.
- Provision scoped private-registry pull credentials per installation and target and rotate/revoke them independently.
- Persist host attempt/slot facts separately from exact target rollout states.
  A failed rollout cannot relabel itself as recovered; only a new forward
  recovery rollout can be promoted and link through `recoveredBy`.
- Preserve stable slots, UID/GID, ports, services, and workspaces during migration. Retired slots are tombstoned and never reused without durable purge plus a host-reset ceremony; system packages use explicitly reserved slots.
- Treat runtime slots as operations/capacity boundaries, not universal security isolation. Consumer policy decides when separate hosts or engines are required.
- Reject unsafe archives; stage by digest; switch only at a harness-safe boundary. Partial pull, disk full, crash, registry outage, credential rotation, unsafe boundary, and observation-delivery retry are mandatory tests.
