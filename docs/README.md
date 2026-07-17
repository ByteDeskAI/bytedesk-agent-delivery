# ByteDesk Agent Delivery documentation

This directory is the canonical product, architecture, protocol, security, and
delivery-planning source of truth.

## Product

- [Story](product/story.md)
- [Scope and authority boundaries](product/scope-and-boundaries.md)
- [Terminology](product/terminology.md)

## Architecture

- [ADR-0001: Independent Agent Delivery control plane](architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [System overview](architecture/system-overview.md)
- [C4 model](architecture/c4.md)
- [Security and trust](architecture/security-and-trust.md)
- [Consumer integration contract](architecture/consumer-integration-contract.md)
- [OCI artifact model](architecture/oci-artifact-model.md)
- [Runtime reconciliation](architecture/runtime-reconciliation.md)

## Standards

- [Agent binding v1](standards/agent-binding-v1.md)
- [OCI media types v1](standards/oci-media-types-v1.md)
- [Trust policy v1](standards/trust-policy-v1.md)

## Planning

- [Development plan](planning/development-plan.md)
- [Detailed task breakdown](planning/task-breakdown.md)
- [Dependency graph](planning/dependency-graph.md)
- [Verification matrix](planning/verification-matrix.md)

## Consumer profiles

- [ByteDesk Platform](integrations/bytedesk-platform.md)

## Long-form design pages

The [`confluence/`](confluence/README.md) tree preserves the complete page
hierarchy originally planned for a product knowledge base. Markdown in this
repository is canonical; any future Confluence publication is a projection.

## History

- [Extraction from ByteDesk Platform planning](history/platform-extraction.md)
