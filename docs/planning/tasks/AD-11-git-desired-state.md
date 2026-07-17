# AD-11: Reconcile digest-pinned consumer overlays from Git

- Historical Jira: [BDP-3312](https://bytedesk.atlassian.net/browse/BDP-3312)
- Delivery role: Core product control plane
- Release gate: Blocks automated desired-state and update workflows

## Outcome

Use a consumer-designated Git repository as desired-state input containing exact upstream artifact pins and a strictly bounded Agent Spec specialization overlay. Reconcile authenticated events and scheduled scans into verified binding revisions without importing the consuming platform's identity, grant, credential, or authorization stores.

## Inputs

- AD-01 consumer Git and desired-state contract.
- Authenticated webhook-receipt and Git-provider adapter contracts. Historical BDP-3282 is reference-consumer ingress evidence, not a core dependency.
- Binding persistence, OCI verification, and overlay rules.
- Consumer installation, repository, branch/path, and authorization-decision configuration.

## Required work

1. Define the desired-state file contract: canonical marketplace ID, exact source digest, harness/render choice, opaque consumer subject and target reference, specialization overlay, update policy, and expected predecessor.
2. Implement overlay validation with an explicit allowlist. Forbid tools, MCP, grants, resources, credentials, identity mutation, provider endpoints, tenant/consumer escape, approval weakening, and destructive schema changes.
3. Consume authenticated webhook receipts idempotently, fetch the exact commit through a Git-provider Strategy/Adapter boundary, validate numeric repository identity, installation authority, branch/path policy, and ownership, and correlate processing.
4. Resolve and verify pinned artifacts, calculate the overlay digest, preview binding changes, obtain the consumer authorization/policy verdict, and write immutable definition-binding revisions.
5. Handle duplicate, reordered, stale, force-pushed, deleted, conflicting, and superseded commits deterministically.
6. Use outbox, durable inbox, dead-letter, replay, and scheduled-reconciliation conventions. Expose status/errors without leaking Git credentials.
7. Do not activate a runtime deployment in this task; produce verified desired state only.

## Outputs

- Consumer desired-state and overlay schemas/examples.
- Authenticated webhook ingress plus Git-to-binding reconciliation process manager.
- Git-provider adapter and immutable binding writes.
- Audit, status, correlation, inbox/outbox, and dead-letter records.
- Unit/integration tests for ordering, replay, policy, authorization decisions, and installation isolation.

## Acceptance criteria

- Mutable tags are rejected as desired-state identity; exact digests are required.
- Unapproved overlay and authority-bearing fields fail with precise diagnostics.
- Duplicate webhook delivery is side-effect free.
- Stale commits cannot overwrite a newer accepted binding.
- Git-provider outage results in bounded retry and dead-letter, never fail-open.
- Numeric repository identity, immutable commit, and installation authority are verified; repository name alone is not authority.
- No runtime artifact is activated and no consumer grant, identity, or credential is created or changed.

## Verification

Run webhook authentication/receipt tests, Git-provider adapter fixtures, commit ordering/replay and scheduled reconciliation, overlay fuzz/negative tests, consumer-authorization denial tests, outbox/inbox/dead-letter tests, and cross-installation isolation integration tests.

## Not in scope

Automatic successor proposals, private deployment compilation, production Git-provider configuration, or consuming-platform identity and authorization management.

## Dependencies

Blocked by AD-08 and AD-09.

## Architecture review amendments

- Agent Delivery owns its authenticated webhook receipt, immutable commit fetch, candidate/binding process, evaluation/promotion state, and delivery receipts. A consumer adapter owns mapping to that consumer's repository installation, subject, policy, identity, and deployment target.
- Reuse one provider-neutral webhook ingress and event normalizer; do not create a path per consumer or event type. ByteDesk integration should adapt the existing BDP-3282 ingress rather than duplicate it.
- Resolve installation scope + numeric repository ID + immutable commit SHA + provider installation authority + branch/path policy through the verified Git-provider broker.
- Provider ingestion emits signed/versioned candidate signals through a transactional outbox. Reconciliation consumes them through a durable idempotent inbox with correlation, retry, dead-letter, and no cross-service/database reads.
- Candidate lifecycle includes received → fetched → validated → quarantined → evaluating → approved/rejected → rendered → signed → staged → canary → promoted/rolled-back. This task owns receipt through verified desired state; later tasks advance subsequent states.
- Use an installation/subject/target rollout lease and compare-and-swap desired-state revision.
- Scheduled reconciliation covers missed webhooks.
- Fetch, validate, and evaluate work longer than two seconds uses the core asynchronous operation lifecycle; consumer adapters may project it into their native job/tool-action model.
