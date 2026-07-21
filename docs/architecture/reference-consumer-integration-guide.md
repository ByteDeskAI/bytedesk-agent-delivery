# Reference consumer integration guide

## Purpose

[Consumer integration contract](consumer-integration-contract.md) is the
normative, harness-neutral specification. This guide is its practical
companion: it maps each phase of that contract to the real, tested code
already built in this repository, so a reference-consumer integration
(AD-16 for ByteDesk Hermes, AD-17 for ByteDesk OpenClaw, or any future
consumer) starts from "here is the exact package/type to call" rather than
re-deriving the wiring from the abstract contract alone.

This guide is itself a generic, reusable output — not ByteDesk-specific.
Per AD-16/AD-17's own task docs, a "reference-consumer integration guide...
contributed back to Agent Delivery documentation where generic" is a
listed output of both tasks, and this repository is the right place for
it. The actual ByteDesk cutover work (touching `bytedesk-platform` or
`bytedesk-openclaw`) is separate, gated on CORE-CERT, and happens through
those repositories' own review process — this guide does not, and cannot,
substitute for that.

## What already exists, by contract phase

| Contract phase | Real implementation | Status |
|---|---|---|
| Desired-state CAS store, single writer | `internal/desiredstate.Store` (`CompareAndSwap`, absent/match preconditions) | Merged, race-tested (AD-09) |
| Control-plane HTTP surface over desired state | `internal/api.DesiredStateHandler` (strong ETags, `If-None-Match`/`If-Match`, RFC 9457 problems from the real problem catalog) | Merged, tested (AD-10) |
| Git/webhook intent intake, idempotent | `internal/scmintake.Inbox` (dedup by provider+deliveryId), `ValidateCommitRef`, `RepositoryIdentity` | Merged, tested (AD-11) |
| Update compatibility classification, sole-writer promotion | `internal/promotion.ClassifyUpdate` (reuses `internal/operations.RebaseJSONPatch` from AD-04), `internal/promotion.Coordinator` | Merged, tested (AD-12) |
| Private compilation: raw-secret rejection, atomic customization apply, deterministic deployment id | `internal/privatecompile.ScanPatchForRawSecrets`, `ApplyCustomization`, `ComputeDeploymentID` | Merged, tested (AD-13) |
| Host switch journal, post-switch recovery | `internal/hostreconciler.Journal` (`Activate`/`MarkPostSwitchFailure`/`RecoverTo`, four-digest binding) | Merged, tested (AD-14) |
| CLI foundation: stable exit codes, canonical JSON output | `internal/clioutput`, `cmd/bd-agent` (`contract digest` command) | Merged, tested (AD-15) |
| Hermes rendering | `renderer/hermes.transform.render_hermes` — grounded in Hermes Agent's public docs, not any one deployment's config | Merged, tested (AD-05) |
| OpenClaw rendering | `renderer/openclaw.transform.render_openclaw` — grounded in OpenClaw's public docs | Merged, tested (AD-06) |
| Native/reference rendering | `renderer/native.transform.render_native` | Merged, tested (AD-04) |
| OCI packaging, local registry push/pull/verify | `registry/local/pack.py`, `registry/local/client.py` | Merged, tested (AD-07) |
| Ephemeral test signing | `signing/kms/ephemeral.py` | Merged, tested (AD-08) |
| Canary evidence verification (technical + capability actor freshness/nonce binding) | `internal/canary.Verifier.VerifyPromotion` | Merged (predates this pass's summary; still real and load-bearing) |
| Portable Agent Spec source catalog | `bytedesk-agent-marketplace` `agents/*/agent.yaml` (34 selectable + `office-orchestrator`), validated against the official `pyagentspec` SDK | Merged (AD-03) |

## What a reference consumer still has to bring

None of the above includes, and none of it should include, anything the
contract reserves to the consumer:

- **Identity, roles, grants, credentials, workload identity.** The
  Coordinator/compiler/reconciler code above only ever consumes opaque
  signed references to these (`bytedesk.consumer-authority/1` snapshots,
  `bytedesk.skill-approval/1` evidence) — it never resolves or stores the
  underlying values. A consumer Adapter has to issue those snapshots from
  its own identity/policy system.
- **A running Capability Verifier.** `internal/canary` verifies
  capability-evidence *shape and freshness*; it does not dispatch the
  actual workload-login/MCP-allow-probe. That's consumer-owned
  infrastructure exercising the candidate through the consumer's real
  runtime path.
- **A real KMS/Sigstore signer for `consumer-deployment-v1`,
  `consumer-compilation-input-v1`, and `consumer-compilation-evidence-v1`.**
  Every signing surface in this repository (`signing/kms/ephemeral.py`,
  `scripts/contracts/sign_test_ephemeral.py`) is explicitly test-only —
  see [`docs/planning/infra-defaults.md`](../planning/infra-defaults.md).
  A reference consumer needs a real per-consumer key topology (consumer-
  owned or tenant-dedicated, never shared).
- **A private OCI registry with real retention/GC/legal-hold policy.**
  `registry/local` proves the push/pull/verify protocol against a real
  `registry:2` instance; it is not a production registry deployment.
- **The harness-specific runtime itself.** `renderer/hermes` and
  `renderer/openclaw` produce the *files* a Hermes or OpenClaw deployment
  needs; actually running Hermes Agent or OpenClaw, wiring their real
  model-provider credentials, and operating them is entirely consumer-side.
- **Full `bytedesk.render-manifest/1` assembly, sandbox execution, and
  renderer qualification.** Every renderer above implements the pure
  transform only; the full manifest/qualification chain needs a real
  renderer registry, documented as a gap in each renderer's own README.

## Suggested integration order

1. Stand up a real desired-state store (managed, via `internal/desiredstate`
   wired behind `internal/api`, or a consumer-native equivalent implementing
   the same CAS contract) and a real Promotion Coordinator deployment.
2. Wire the consumer's own authority/approval issuance to produce
   `bytedesk.consumer-authority/1` and `bytedesk.skill-approval/1` objects
   matching the real schemas in `contracts/schemas/v1/`.
3. Stand up a real private OCI registry and real per-consumer signing keys;
   replace every `ephemeral`/test-signer call site with the real
   equivalent.
4. Implement the consumer's Capability Verifier against
   `bytedesk.port.capability-verifier/1`'s real request/result schemas.
5. Point a Host Reconciler implementation at the target harness
   (Hermes/OpenClaw/other), using `internal/hostreconciler.Journal`'s
   switch-journal pattern as the reference for the atomic-switch/recovery
   invariants it must preserve.
6. Only after 1-5 are real and independently verified does a cutover away
   from a legacy canonical source (AD-16/AD-17's actual scope) become safe
   to attempt — and that attempt happens in the consumer's own repository,
   through its own review process, per those tasks' explicit "no changes
   are implemented in the Agent Delivery repository alone" boundary.
