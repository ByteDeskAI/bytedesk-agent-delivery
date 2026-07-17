# Extraction from ByteDesk Platform planning

## Decision

On 2026-07-16, the Agent Spec marketplace and OCI delivery design was extracted
from ByteDesk Platform into the independent **ByteDesk Agent Delivery** product.

The product repository is:

`https://github.com/ByteDeskAI/bytedesk-agent-delivery`

## What moved

- The unlanded Platform draft ADR-0188.
- The planned C4 relationships for catalog, OCI, trust, and runtime delivery.
- The delivery-specific engineering rules and invariants.
- The machine-readable 18-workstream dependency plan.
- The complete Jira task inputs, outputs, acceptance criteria, verification,
  dependencies, and architecture-review amendments.
- The 13-page product documentation hierarchy that had been planned for
  Confluence but had not been published.

The material was adapted so the standalone product is consumer-neutral. The
Platform-specific portions are preserved in
[`docs/integrations/bytedesk-platform.md`](../integrations/bytedesk-platform.md).

## What did not move

Platform's legitimate identity, MCP authorization, GitHub webhook ingress,
organizational identity, Hermes work, and skill-governance foundations remain
Platform concerns. The extraction does not delete or supersede their landed
code or ADRs.

## Source state

The Platform product artifacts existed only as uncommitted files in the managed
worktree `BDP-3302-agent-delivery-architecture`. They were never committed,
pushed, reviewed, or landed on Platform `develop`. No corresponding Confluence
pages existed.

Jira BDP-3301 and its 18 children remain as auditable historical planning
records and are marked transferred, not implemented. A future ByteDesk Platform
integration receives a new integration-specific epic after this product has a
versioned release.
