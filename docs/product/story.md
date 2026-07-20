# Product story

## The problem

Agent definitions are commonly trapped inside a harness or SaaS platform. The
same employee or specialist agent becomes a different hand-maintained bundle in
Hermes, OpenClaw, and each future runtime. A consumer cannot reliably answer:

- Which portable definition produced this running agent?
- Which renderer and policy were used?
- Was the artifact altered after publication?
- What authority came from the package versus the consuming organization?
- Can the deployment be reproduced or recovered safely under current policy?

This is a software-distribution problem with a dangerous authorization edge.
Reusability requires portable content; enterprise use requires immutable
identity, provenance, policy separation, and operational recovery.

## The product

ByteDesk Agent Delivery is the open supply chain between agent authors and
agent runtimes.

An author publishes a tenant-free Agent Spec package and may declare exact skill
packages. Skills may contain arbitrary regular files, including scripts,
binaries, and archives, but Agent Delivery always handles them as untrusted,
non-executing input. Agent Delivery validates the package, renders the unchanged
public source and declared public skills deterministically for a harness,
packages the source, skills, and public render as content-addressed OCI
artifacts, verifies the required signatures and attestations, and exposes stable
catalog, inspection, installation, promotion, deployment, recovery, and receipt
interfaces.

A consuming platform selects an exact digest and authors a deterministic private
functional-customization delta. The delta may change any functional Agent Spec
property, compose public or private skills, add or remove files, and configure
models, providers, tools, MCP, and the selected harness. It may reference
consumer secrets opaquely but cannot carry their values or create identity,
grants, workload authority, trust roots, or weaker mandatory security policy.

Agent Delivery applies the delta to the verified public source, resolves the
consumer-approved skill set, reconstructs and validates the full effective Agent
Spec, and performs a complete deterministic render with the same exact signed
renderer release recorded by the public-render lineage. The renderer release is
selected from the product-compiled allowlist and records its manifest, actual
executing distribution, platform, schema, and normalization digests. Agent
Delivery embeds the effective render and its manifest in the private
deployment; it does not patch
public rendered files or publish a separate private-render artifact in v1. A
Promotion Coordinator is the only writer of one target desired-state aggregate.
A target-scoped Host Reconciler reports technical evidence and a separate
consumer capability verifier proves one permitted and one explicitly denied
capability before promotion. The runtime may execute skill files only after
activation, explicit approval of the exact skill digest, and validation under
current consumer sandbox, network, identity, and call-time authorization
controls.

Current consumer authority arrives as a short-lived signed opaque snapshot;
every skill has separate consumer approval. Private-skill, authority/approval,
and deployment signers are purpose-separated and isolated per consumer. If a
rollout fails, Agent Delivery creates a new forward recovery revision from
eligible historical functional content using current trusted schemas and
renderer/compiler tooling, current authority and approvals, full evaluation,
and fresh canary evidence. It never reactivates an old deployment, receipt,
signature, authority snapshot, credential state, render bundle, or revoked
renderer.

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

Authors may still use JSON-compatible YAML 1.2 as a human-facing input syntax.
Agent Delivery rejects ambiguous YAML features and converts every authoritative
structured object to the JSON data model and RFC 8785 canonical JSON before it
is hashed or signed. The original authoring document may remain as provenance,
but canonical JSON is its semantic identity. A checksum over retained authored
bytes protects provenance storage only and cannot authorize promotion or
activation. Arbitrary payload files—including files named `.yaml` that are not
declared control objects—and binary payloads retain their exact raw bytes.

Neither standard alone solves the full problem. Agent Spec does not define a
digest-pinned, non-authorizing consumer customization delta. An OCI `subject`
and its referrers apply only within the subject repository and do not prove
cross-repository edges. Agent Delivery uses explicit signed descriptors for
cross-repository relationships and adds small, versioned contracts for those
gaps without replacing either standard.

See [Canonical encoding v1](../standards/canonical-encoding-v1.md) for the exact
identity bytes and [Machine contracts v1](../standards/machine-contracts-v1.md)
for the normative Draft 2020-12 schemas, operations, API, events, and
compatibility rules. The accepted information architecture is not a release
claim: signed contract and renderer artifacts plus measured readiness evidence
remain mandatory before GA.

## Who it is for

- Agent authors who want a reusable definition rather than a harness-specific
  bundle.
- Harness maintainers who want a deterministic Adapter contract.
- Platforms that want a marketplace and deployment mechanism without
  surrendering identity or policy authority.
- Operators who need promotion, canary, forward recovery, audit, and disaster-
  recovery evidence for agent releases.

## Initial reference tracks

The independent ByteDesk marketplace is the first reference-catalog profile and
supplies 34 employee definitions plus one non-selectable system package.
ByteDesk Platform is the first reference-consumer integration profile. Neither
track is part of the product's core authority or certification path. A clean
third party must be able to validate, render, package, and verify public agents
without the ByteDesk catalog or Platform.
