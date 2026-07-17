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
9. [Evaluation, promotion, updates, and rollback](09-evaluation-promotion-updates-and-rollback.md)
10. [Hosted runtime deployment](10-hosted-runtime-deployment.md)
11. [CLI and headless consumer contract](11-cli-and-headless-consumer-contract.md)
12. [Migration and source cutover](12-migration-and-source-cutover.md)
13. [Verification, operations, and disaster recovery](13-verification-operations-and-disaster-recovery.md)

## Canonical contracts

The pages explain the design; the following documents define its normative
contracts:

- [ADR-0001](../architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [Agent binding v1](../standards/agent-binding-v1.md)
- [OCI media types v1](../standards/oci-media-types-v1.md)
- [Trust policy v1](../standards/trust-policy-v1.md)

Where explanatory text conflicts with a versioned standard, the standard wins.
Where a standard conflicts with ADR-0001's authority boundary, ADR-0001 wins
until a superseding ADR is accepted.

## Vocabulary

- **Definition**: portable, reusable Agent Spec content.
- **Binding**: a digest-pinned, non-authorizing consumer specialization.
- **Render**: deterministic harness-specific output derived from a definition.
- **Deployment**: private, consumer-specific desired content and evidence.
- **Release manifest**: the exact set of deployments desired for one runtime.
- **Consumer**: the platform or organization that supplies identity, policy,
  grants, credentials, and runtime targets.
- **Host reconciler**: the engine-scoped process that stages and activates a
  verified release.

Agent Delivery never turns portable package metadata into runtime authority.
Identity, roles, MCP servers and grants, provider connections, credentials, and
call-time authorization always remain with the consuming platform.
