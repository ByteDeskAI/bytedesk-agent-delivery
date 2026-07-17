# Product story

## The problem

Agent definitions are commonly trapped inside a harness or SaaS platform. The
same employee or specialist agent becomes a different hand-maintained bundle in
Hermes, OpenClaw, and each future runtime. A consumer cannot reliably answer:

- Which portable definition produced this running agent?
- Which renderer and policy were used?
- Was the artifact altered after publication?
- What authority came from the package versus the consuming organization?
- Can the deployment be reproduced or safely rolled back?

This is a software-distribution problem with a dangerous authorization edge.
Reusability requires portable content; enterprise use requires immutable
identity, provenance, policy separation, and operational recovery.

## The product

ByteDesk Agent Delivery is the open supply chain between agent authors and
agent runtimes.

An author publishes an Agent Spec package. Agent Delivery validates it as inert,
non-authorizing content, renders it deterministically for a declared harness,
packages the source and render as content-addressed OCI artifacts, verifies the
required signatures and attestations, and exposes stable catalog, inspection,
installation, promotion, deployment, rollback, and receipt interfaces.

A consuming platform selects an exact digest and attaches its own identity,
policy, resources, credentials, and grants. Agent Delivery compiles that intent
into a private deployment artifact without allowing the public package to
demand or create authority. A runtime reconciler activates only a fully verified
desired state and reports what actually happened.

## The promise

**Define once. Verify everywhere. Deliver anywhere.**

The same definition can be consumed by ByteDesk Platform, another SaaS
platform, a private enterprise control plane, or a local CLI workflow. Each
consumer chooses its harness and retains its own security model.

## Why Agent Spec and OCI

Agent Spec supplies a portable semantic definition instead of another
ByteDesk-only YAML dialect. OCI supplies immutable digests, familiar registry
distribution, subjects/referrers, and an ecosystem for signing, provenance,
SBOMs, retention, and replication.

Neither standard alone solves the full problem. Agent Spec does not define a
digest-pinned, non-authorizing consumer binding. OCI referrers are
repository-local and do not prove cross-repository edges. Agent Delivery adds
small, versioned contracts for those gaps without replacing either standard.

## Who it is for

- Agent authors who want a reusable definition rather than a harness-specific
  bundle.
- Harness maintainers who want a deterministic Adapter contract.
- Platforms that want a marketplace and deployment mechanism without
  surrendering identity or policy authority.
- Operators who need promotion, canary, rollback, audit, and disaster-recovery
  evidence for agent releases.

## Initial reference consumer

ByteDesk Platform is the first integration profile and supplies the baseline
catalog of 34 employee agents plus one non-selectable system package. It is not
part of the product's core authority model. A clean third party must be able to
validate, render, package, and verify public agents without ByteDesk Platform.
