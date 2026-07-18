# Long-form product design

This directory preserves the complete knowledge-base page hierarchy for
ByteDesk Agent Delivery. The Markdown files in this repository are canonical.
If these pages are projected into Confluence later, Confluence is a rendered
view and must link back to the repository revision that produced it.

## Suggested reading order

1. [System overview and authority boundaries](01-system-overview-and-authority-boundaries.md)
2. [Agent Spec and the binding profile](02-agent-spec-and-binding-profile.md)
3. [Marketplace repository and baseline catalog](03-marketplace-repository-and-baseline-catalog.md)
4. [Harness adapters and deterministic renderers](04-harness-adapters-and-renderers.md)
5. [OCI artifact graph](05-oci-artifact-graph.md)
6. [Supply-chain trust and threat model](06-supply-chain-trust-and-threat-model.md)
7. [Data model, API, and service ownership](07-data-model-api-and-service-ownership.md)
8. [Tenant Git and reconciliation](08-tenant-git-and-reconciliation.md)
9. [Evaluation, promotion, updates, and forward recovery](09-evaluation-promotion-updates-and-forward-recovery.md)
10. [Hosted runtime deployment](10-hosted-runtime-deployment.md)
11. [CLI and headless consumer contract](11-cli-and-headless-consumer-contract.md)
12. [Migration and source cutover](12-migration-and-source-cutover.md)
13. [Verification, operations, and disaster recovery](13-verification-operations-and-disaster-recovery.md)

## Reference implementation

[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md)
fixes the Go/PostgreSQL/Harbor/S3/Kubernetes/gVisor production reference
profile used to implement and certify these contracts. That profile is
deliberately non-portable: consumer integrations and conforming Adapters may
use different technology without changing the portable definitions, protocols,
authority boundaries, or verification obligations.

## Canonical contracts

The pages explain the design; the following documents define its normative
contracts:

- [ADR-0001](../architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [Canonical encoding v1](../standards/canonical-encoding-v1.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
- [Agent binding v1](../standards/agent-binding-v1.md)
- [OCI media types v1](../standards/oci-media-types-v1.md)
- [Trust policy v1](../standards/trust-policy-v1.md)

Where explanatory text conflicts with a versioned standard, the standard wins.
Where a standard conflicts with ADR-0001's authority boundary, ADR-0001 wins
until a superseding ADR is accepted.

## Canonical encoding

YAML is a human-authoring convenience for declared structured contracts, not an
authority format. Contract-authoring YAML uses only the YAML 1.2 JSON-compatible
subset and rejects duplicate keys, aliases, custom tags, non-string mapping
keys, and non-finite numbers. Before an authoritative structured object is
hashed or signed, it is converted to the JSON data model and serialized as RFC
8785 JSON Canonicalization Scheme (JCS) bytes. Those canonical JSON bytes define
semantic identity.

Original contract-authoring YAML may be retained for review. If it has an
integrity digest or descriptor, that reference is provenance/storage-integrity
evidence only: it is never semantic identity, artifact authority, or activation
authority. Arbitrary package and skill payload files remain opaque, byte-exact
content even when a filename ends in `.yaml` or `.json`; a file extension never
opts a payload into contract parsing or canonicalization.

## Vocabulary

- **Definition**: portable, reusable Agent Spec content.
- **Binding**: a private, digest-pinned functional customization delta. It may
  change behavior and configuration, but it cannot create security authority.
- **Public render**: deterministic, tenant-free harness output derived only from
  public inputs.
- **Deployment**: private, consumer-specific desired content that embeds the
  effective render manifest, exact runtime-file payload descriptor, and
  authenticated execution lineage.
- **Release manifest**: the exact set of deployments desired for one runtime.
- **Consumer**: the platform or organization that supplies identity, policy,
  grants, credentials, and runtime targets.
- **Host reconciler**: the engine-scoped process that stages and activates a
  verified release.
- **Promotion Coordinator**: the sole logical writer of one target's delivery
  state; it validates evidence and advances the target through exact CAS.
- **Consumer Capability Verifier**: a consumer-owned actor that proves allowed
  and explicitly denied runtime behavior without giving the Host Reconciler an
  agent capability credential.

Git binding files express reviewed installation intent. They are not runtime
desired state. Each runtime target has exactly one authoritative
`TargetDeliveryState`, one selected `DesiredStateStore` Adapter, and no dual
writer. Installation, candidate preparation, rollout, and host observations
use the separate state machines in
[Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md).

Agent Delivery never turns package or binding content into runtime authority. A
private binding may describe tools, MCP, provider/model/harness configuration,
and opaque secret references, but the consuming platform must independently
authorize those capabilities and resolve those references. Identity, roles,
grants, credential values, and call-time authorization always remain with the
consuming platform.

The standalone core release and consumer-specific reference integrations have
separate milestones. A ByteDesk, Hermes, or OpenClaw reference appendix can
fail without redefining the core release result. General availability still
requires the measured reliability, scale, recovery, security-response, and
support evidence in
[Operational readiness v1](../standards/operational-readiness-v1.md).
