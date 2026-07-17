# Terminology

## ByteDesk Agent Delivery

The independent product defined by this repository. It manages the portable
agent supply chain and delivery lifecycle. It is not an agent conversation
runtime.

## Agent Server

Any existing ByteDesk component or generic service called “Agent Server” is a
separate runtime concern. ByteDesk Agent Delivery does not rename, replace,
contain, or inherit the authority of `ByteDesk.AI.AgentServer`. A future
integration may consume a released delivery artifact through an Adapter.

## Agent catalog / marketplace

A definition-only Git repository containing portable Agent Spec packages,
optional skills, and catalog metadata. It contains no delivery control-plane
code and demands no MCP/provider/runtime resources. “Marketplace” describes
discoverability; Git remains the authoring source.

## Portable agent

An Agent Spec definition describing behavior and optional inert content without
consumer identity, credentials, or grants.

## Binding

A digest-pinned, non-authorizing consumer intent that selects a portable source,
harness renderer, and allowed specialization. It is not a runtime grant.

## Render

Deterministic harness-specific output derived from verified portable source and
a compiled renderer Adapter.

## Deployment artifact

A private OCI artifact binding verified source/render content to one consumer
installation, current opaque authority subdigests, and a runtime target. It is
not itself the call-time authorization decision.

## Runtime release

A signed manifest aggregating the exact deployment subdigests intended for one
runtime target.

## Receipt / observation

Append-only evidence describing desired, staged, active, failed, or rolled-back
state. A receipt records history; it cannot activate itself.

## Forward rollback

A new deployment revision using last-known-good definition content plus current
consumer authority. It does not reactivate an old deployment or grant snapshot.

## Consumer

A platform or organization that supplies identity, policy, grants, credentials,
approval, and runtime targets. ByteDesk Platform is the first reference
consumer, not a synonym for Agent Delivery.
