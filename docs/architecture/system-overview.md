# System overview

## Context flow

```text
Definition-only Git catalog
        |
        | exact commit + Agent Spec validation
        v
Agent Delivery build and catalog plane
        |
        | source digest -> renderer digest -> signed render digest
        v
Public OCI registry
        |
        | exact descriptors and verified trust graph
        v
Consuming platform <---- identity, policy, grants, credentials stay here
        |
        | signed private deployment + desired-state revision
        v
Private OCI scope ----> target-scoped runtime reconciler ----> agent harness
        ^                         |
        |                         | append-only observations
        +--------- receipts ------+
```

## Logical components

### Catalog client

Reads a definition-only Git catalog at an immutable commit, validates its
layout, and projects discovery metadata. Names and channels help discovery;
digests establish authority.

### Policy validator

Validates Agent Spec with the official pinned SDK and applies the stricter
Agent Delivery portability policy. It rejects credentials, required MCP or
provider authority, executable hooks, unsafe archives, and consumer-specific
bindings.

### Renderer registry

Selects a compiled, allowlisted renderer Strategy and delegates harness
translation through an Adapter. It emits a deterministic render plus a complete
compatibility and file-digest manifest.

### OCI publisher and verifier

Builds deterministic artifacts, publishes them by digest, attaches local
signatures/attestations/SBOMs, and verifies explicit cross-repository edges.
Registry and KMS clients are external-system Adapters.

### Installation and promotion controller

Tracks digest-pinned installation intent, evaluates compatible updates, and
uses a durable state machine, idempotency, and compare-and-swap to promote or
reject changes.

### Deployment compiler

Combines verified public source/render content with a consumer's non-authorizing
specialization and opaque authority subdigests. It does not invent, broaden, or
interpret the consumer's permissions. The result is a signed private deployment
artifact and release manifest.

### Runtime reconciler protocol

Defines least-privilege desired-state reads and append-only observations. A
consumer-specific host Adapter stages, verifies, canaries, activates, or
forward-rolls back at a harness-safe boundary.

### API and CLI

Expose the same versioned resources to third parties and first-party consumers.
Public validation/render/verification does not require a ByteDesk identity.

## Deployment shape

The initial implementation should be a modular monolith with explicit internal
ports. It avoids premature service boundaries while preserving Adapters for
catalog Git, registry, KMS, policy/evaluation, consumers, and runtimes. A future
split must follow measured scaling or trust-boundary evidence, not product
branding.

Long-running build, publish, evaluation, compile, and deploy operations use an
asynchronous action resource. Durable workflows use a persisted state machine
and idempotent handlers.

## Pattern choices

- **Strategy:** renderer selection and compatibility policy.
- **Adapter:** harness, Agent Spec SDK, Git, registry, KMS, consumer, and host
  integrations.
- **State / Process Manager:** installation, promotion, and deployment
  lifecycle.
- **Outbox / Inbox / Idempotent Receiver:** reliable integration events.
- **Saga-style compensation:** staged content cleanup and forward recovery.
- **Anti-corruption layer:** consumer-specific identity and authorization stay
  outside the core domain.
