# ByteDesk Agent Delivery documentation

This directory is the canonical product, architecture, protocol, security, and
delivery-planning source of truth.

## Product

- [Story](product/story.md)
- [Scope and authority boundaries](product/scope-and-boundaries.md)
- [Terminology](product/terminology.md)

## Architecture

- [ADR-0001: Independent Agent Delivery control plane](architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [ADR-0002: Implementation stack and reference topology](architecture/adr/0002-implementation-stack-and-reference-topology.md)
- [Architecture decision register](architecture/decision-register.md)
- [System overview](architecture/system-overview.md)
- [C4 model](architecture/c4.md)
- [Security and trust](architecture/security-and-trust.md)
- [Consumer integration contract](architecture/consumer-integration-contract.md)
- [Reference consumer integration guide](architecture/reference-consumer-integration-guide.md)
- [OCI artifact model](architecture/oci-artifact-model.md)
- [Runtime reconciliation](architecture/runtime-reconciliation.md)
- [Downstream contract coverage](architecture/downstream-contract-coverage.md)

## Standards

- [Canonical encoding v1](standards/canonical-encoding-v1.md)
- [Machine contracts v1](standards/machine-contracts-v1.md)
- [Integration ports v1](standards/integration-ports-v1.md)
- [Renderer identity v1](standards/renderer-identity-v1.md)
- [Release qualification and status v1](standards/release-qualification-v1.md)
- [Consumer authority and private signing v1](standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](standards/operational-readiness-v1.md)
- [Agent binding v1](standards/agent-binding-v1.md)
- [OCI media types v1](standards/oci-media-types-v1.md)
- [Trust policy v1](standards/trust-policy-v1.md)

## Planning

- [Development plan](planning/development-plan.md)
- [Detailed task breakdown](planning/task-breakdown.md)
- [Dependency graph](planning/dependency-graph.md)
- [Verification matrix](planning/verification-matrix.md)
- [Implementation-readiness execution plan](planning/implementation-readiness-execution.md)

## Consumer profiles

- [ByteDesk Platform](integrations/bytedesk-platform.md)

## Long-form design pages

The [`confluence/`](confluence/README.md) tree preserves the complete page
hierarchy originally planned for a product knowledge base. Markdown in this
repository is canonical; any future Confluence publication is a projection.

## History

- [Extraction from ByteDesk Platform planning](history/platform-extraction.md)
