# AD-11: Reconcile digest-pinned installation and binding intent from Git

- Historical Jira: [BDP-3312](https://bytedesk.atlassian.net/browse/BDP-3312)
- Delivery role: Core product control plane
- Release gate: Required for `CONTROL-PLANE-CERT` Git profile

## Outcome

Use a consumer-designated Git repository as reviewed installation and binding
intent containing exact pins and strict private customization. Reconcile
authenticated events and scans into candidate commands without treating Git as
runtime desired state or allowing it to bypass the Promotion Coordinator.

## Inputs

- AD-09 installation/binding/candidate/TargetDeliveryState contracts and AD-10
  API/event/action resources.
- Authenticated webhook-receipt and Git-provider adapter contracts. Historical BDP-3282 is reference-consumer ingress evidence, not a core dependency.
- Binding persistence, OCI verification, and private customization rules.
- Consumer installation, repository, branch/path, and authorization-decision configuration.

## Required work

1. Define the Git intent file using the normative binding schema: exact source
   and renderer-release descriptors, source kind, strict ordered functional/file/
   skill operations, exact skills, update policy, and absent/match precondition.
   Accepted intent is the RFC 8785 object; Git/YAML representation is provenance.
2. Apply the exact JSON Patch, file-operation, and skill-operation profiles
   atomically, including path/digest/source-kind/rebase rules. Forbid raw
   secrets, authority, trust, identity, approval weakening, ambiguous paths, or
   partial results.
3. Consume authenticated webhook receipts idempotently, fetch the exact commit through a Git-provider Strategy/Adapter boundary, validate numeric repository identity, installation authority, branch/path policy, and ownership, and correlate processing.
4. Resolve and verify exact artifacts, renderer release, skills, and operation
   preconditions; preview binding/effective-render changes; obtain current
   consumer verdicts; and submit idempotent candidate/binding commands through
   AD-10. Do not write TargetDeliveryState.
5. Handle duplicate, reordered, stale, force-pushed, deleted, conflicting, and superseded commits deterministically.
6. Use outbox, durable inbox, dead-letter, replay, and scheduled-reconciliation conventions. Expose status/errors without leaking Git credentials.
7. Produce verified Git intent and candidate input only. The Promotion
   Coordinator is the sole target desired-state writer; Git is unavailable to
   and unnecessary for runtime forward recovery.

## Outputs

- Git installation/binding-intent examples that reference, but do not fork, the
  normative schemas.
- Authenticated webhook ingress plus Git-to-binding reconciliation process manager.
- Git-provider Adapter and idempotent API commands/candidate signals.
- Audit, status, correlation, inbox/outbox, and dead-letter records.
- Unit/integration tests for ordering, replay, policy, authorization decisions, and installation isolation.

## Acceptance criteria

- Mutable tags are rejected as desired-state identity; exact digests are required.
- Invalid functional patches, file conflicts, raw secrets, and security-authority mutations fail with precise diagnostics.
- Duplicate keys, aliases, custom tags, non-string keys, non-finite numbers, and any attempt to make raw YAML representation affect the binding digest fail closed.
- Duplicate webhook delivery is side-effect free.
- Stale commits cannot overwrite a newer accepted binding.
- Git-provider outage results in bounded retry and dead-letter, never fail-open.
- Numeric repository identity, immutable commit, and installation authority are verified; repository name alone is not authority.
- No runtime artifact is activated and no consumer grant, identity, credential value, trust root, or mandatory security policy is created or changed.
- Git, webhooks, scheduled scans, and bot commits cannot write runtime desired
  state or override revision-plus-digest CAS.

## Verification

Run webhook authentication, provider Adapter, signed bundle and strict-operation
fixtures, YAML/JCS differentials, commit duplicate/reorder/gap/force-push/
deletion/replay, scheduled scan, API idempotency/ETag, stale-precondition,
no-direct-desired-write, Git-outage forward-recovery independence,
outbox/inbox/dead-letter, redaction, and cross-installation isolation tests.

## Not in scope

Automatic successor proposals, private deployment compilation, production Git-provider configuration, or consuming-platform identity and authorization management.

## Dependencies

Blocked by AD-09 and AD-10.

## Architecture review amendments

- Agent Delivery owns its authenticated webhook receipt, immutable commit fetch, candidate/binding process, evaluation/promotion state, and delivery receipts. A consumer adapter owns mapping to that consumer's repository installation, subject, policy, identity, and deployment target.
- Reuse one provider-neutral webhook ingress and event normalizer; do not create a path per consumer or event type. ByteDesk integration should adapt the existing BDP-3282 ingress rather than duplicate it.
- Resolve installation scope + numeric repository ID + immutable commit SHA + provider installation authority + branch/path policy through the verified Git-provider broker.
- Provider ingestion emits signed/versioned candidate signals through a transactional outbox. Reconciliation consumes them through a durable idempotent inbox with correlation, retry, dead-letter, and no cross-service/database reads.
- Candidate preparation, target rollout, host attempt, and observations use the
  separate delivery-lifecycle state machines; this task advances only the
  ingestion/candidate portion through coordinator commands.
- A rollout lease may deduplicate work but cannot override the Promotion
  Coordinator's revision-plus-digest CAS.
- Scheduled reconciliation covers missed webhooks.
- Fetch, validate, and evaluate work longer than two seconds uses the core asynchronous operation lifecycle; consumer adapters may project it into their native job/tool-action model.
