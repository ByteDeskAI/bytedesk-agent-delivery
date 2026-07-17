# Consumer integration contract

## Purpose

The consumer protocol lets a platform use Agent Delivery without surrendering
its identity or authorization model. The core exchanges identifiers, digests,
desired state, and evidence—not credentials or broad internal objects.

## Consumer port

A consumer Adapter supplies:

- a stable consumer/tenant identifier;
- a stable consumer-owned agent identity or explicit create/bind choice;
- an exact installation binding and predecessor;
- harness and runtime-target selection;
- non-authorizing specialization;
- opaque current-policy, authority, credential-set, and lifecycle digests;
- an activation decision or approval reference; and
- endpoints or events for desired-state publication and observation intake.

The Adapter may expose reference checks for workload login, one allowed
capability, and one denied capability. Agent Delivery records their results but
does not become the authorization engine.

## Import contract

Import is split into preview and apply. Both require an exact source digest and
renderer choice. Apply also requires an idempotency key and an explicit
consumer-owned identity action:

- bind to an existing agent identity; or
- ask the consumer to create a new identity under its own rules.

Agent Delivery never infers roles, grants, tools, credentials, or reporting
relationships from catalog metadata.

## Desired deployment contract

The consumer publishes a compare-and-swap desired-state revision containing
the verified public descriptors, installation binding digest, current opaque
authority subdigests, exact runtime target, and previous active revision.

Agent Delivery compiles and signs the private artifact. A target-scoped host
reads only its desired deployment and appends observations for that target.

## Observation contract

Observations are append-only and include:

- desired revision and deployment digest;
- verifier policy and trust-set digest;
- staged and active content digests;
- target slot/generation;
- state transition and timestamps;
- health/canary evidence references;
- failure category and redacted diagnostic reference; and
- last-known-good and forward-rollback lineage.

An observation cannot mutate desired state or promote itself.

## Authentication profiles

The protocol is transport-neutral. An implementation profile must define:

- workload authentication and token audience;
- sender constraints or mTLS binding;
- tenant/consumer and runtime-target authorization;
- replay and idempotency handling;
- audit correlation; and
- key/credential rotation.

Human login and agent workload login are distinct paths. A host reconciler is
neither a human administrator nor a runtime agent principal.

## Failure semantics

Missing or stale authority inputs, unknown trust, mismatched predecessor,
cross-consumer descriptors, and unavailable verification dependencies fail new
changes closed. An already active verified release may continue under consumer
policy while the control plane is unavailable.
