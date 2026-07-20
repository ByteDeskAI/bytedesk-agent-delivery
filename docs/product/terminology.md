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

An Agent Spec definition describing reusable, tenant-free behavior and exact
optional public skill descriptors without consumer identity, credentials, or
grants. `Agent` is the default standalone form. A complete, intentional public
Agent Spec `SpecializedAgent` is also portable; the type name does not imply
private consumer customization, identity, or organizational inheritance.

## Machine contract / contract bundle

An Agent Delivery-owned authoritative object is defined by an immutable JSON
Schema Draft 2020-12 `$id` and exact schema digest. Schemas, transitive
references, OpenAPI, AsyncAPI, compatibility metadata, and fixtures ship in one
signed content-addressed contract bundle and resolve without runtime network
access. Generated code and prose are projections of the schema.

## Authoring YAML

Optional human-facing YAML 1.2 input restricted to the JSON-compatible data
model. It cannot contain duplicate keys, aliases, custom tags, non-string keys,
non-finite numbers, or non-JSON values. It may be retained as separate
provenance, but any digest over the authored bytes protects storage only and is
never semantic/artifact authority or an activation input. A `.yaml` extension
alone does not make an arbitrary payload file authoring YAML.

## Canonical JSON identity

The UTF-8 RFC 8785 serialization of a validated authoritative structured
object's JSON data model. These canonical bytes are hashed, signed, compared,
cached, and referenced by provenance. Equivalent accepted JSON and authoring
YAML therefore have the same semantic identity. Arbitrary payload files,
including undeclared `.yaml` files and binary content, are not converted and
preserve their exact raw bytes.

## Skill package

A digest-addressed public or consumer-private package of arbitrary regular
files. It may include instructions, scripts, binaries, archives, data, images,
or dependency manifests. Agent Delivery scans, validates, renders, packages, and
delivers those files without executing them. A consumer must approve the exact
skill digest before a runtime may execute its files under current consumer
sandbox, network, identity, and call-time authorization controls.

## Binding

A private, digest-pinned consumer intent that selects a portable source and
harness plus a complete exact renderer-release descriptor, carries the
authoritative deterministic functional-customization delta, and includes the
required absent-or-match revision/digest precondition. It is not a runtime
grant.

## Consumer customization delta

An ordered set of private changes against one exact public source whose
structured representation has a canonical JSON identity.
It may override any functional Agent Spec property; add, replace, or remove
regular files and exact public/private skill descriptors; and configure
functional model, provider, tool, MCP, and harness behavior. It may include
opaque secret references but cannot define security authority or secret values.

Agent Spec and harness-configuration values use the closed
`bytedesk.json-patch/1` add/replace/remove profile. Regular files and skills use
their separate digest-preconditioned operation contracts.

## Renderer release

The signed immutable product-code identity selected by a binding. Its primary
identity is the renderer-release manifest digest, which binds the semantic
version, actual executing distribution/platform digest, compiled allowlist,
owned schemas, dependencies, provenance, SBOM, compatibility, and
normalization. A version string, tag, PATH binary, or source commit is not a
renderer identity.

## Public render

Deterministic harness-specific output derived from verified portable source and
its exact declared public skill set by an exact allowlisted renderer release.
It contains no consumer customization.

## Effective render

Deterministic harness-specific output produced after resolving a private
customization delta and exact consumer-approved skill set into a complete valid
effective Agent Spec. Its bundle and render manifest are embedded in the private
deployment rather than published as a separate private-render artifact in v1.

## Deployment artifact

A private OCI artifact binding verified public source/render lineage, the
consumer customization delta, approved public/private skill descriptors, and
the exact compilation authority snapshot plus current opaque authority
subdigests to one installation and runtime target. It contains the complete
effective render manifest, exact runtime-file payload descriptor, and
authenticated renderer execution lineage. It is not itself the call-time
authorization decision.

## Runtime release

A `consumer-runtime-release-v1`-signed manifest aggregating, for every subject,
the exact canonical deployment descriptor and its separate exact private-
compilation-evidence descriptor intended for one runtime target. It is prepared
content and becomes desired only through a Promotion Coordinator compare-and-
swap transition.

## Consumer authority snapshot

A short-lived, consumer-signed opaque statement binding current identity,
policy, grant-set, credential-set, workload-identity, lifecycle,
sandbox/network, approval, target, candidate, and desired-revision digests to
one compile, activate, or recover operation. Agent Delivery verifies it but
does not issue or interpret the consumer-owned authority.

## Skill approval evidence

A consumer-issued decision approving one exact skill descriptor for one
consumer, subject, installation, target class, use scope, policy, and validity
window. A public or private supplier signature is provenance, not execution
approval and not the required per-consumer private-skill publication signature.

## Target delivery state

The one authoritative desired-state aggregate for an exact consumer/runtime
target. It has a monotonic revision and digest, exact predecessor, active
release, at most one pending rollout, target/slot binding, and policy/evidence
requirements.

## Promotion Coordinator

The sole logical writer of `TargetDeliveryState`. It validates commands and
consumer authority, advances state by exact compare-and-swap, issues canary
challenges, verifies separate evidence, and records promotion or recovery. Git,
bots, compilers, hosts, observations, and consumer applications cannot write
desired state directly.

## DesiredStateStore

The single durable Adapter selected for one target, either Agent
Delivery-managed or a conforming consumer-native store. Two authoritative
stores or live dual write are forbidden; other copies are disposable read
models.

## Host Reconciler / Consumer Capability Verifier

The Host Reconciler is target-scoped and returns technical staging, process,
identity-readback, and switch evidence without desired-write or agent-capability
authority. The separately owned Consumer Capability Verifier probes the normal
runtime authorization path and returns challenge-bound evidence for one
permitted capability and one explicit policy denial. Neither actor can promote.

## Receipt / observation

Append-only evidence describing commands, desired revisions, staging, active
facts, canary results, failures, and recovery. Evidence records history; it
cannot write desired state or activate itself.

## Forward recovery

A new revision that may reuse eligible historical functional content only after
current trusted tooling rebuilds it and current schemas, content trust, skill
approval, consumer authority, evaluation, and canary gates pass. It never
reactivates an old deployment, render bundle, receipt, signature, authority
snapshot, credential state, or revoked renderer.

## Operational conformance

Measured proof that a declared topology meets the accepted v1 SLO, latency,
scale, safety-limit, durability, restore, retention, observability,
security-response, compatibility, and support gates. Architectural acceptance
alone is not operational conformance or GA readiness.

## Consumer

A platform or organization that supplies identity, policy, grants, credentials,
approval, and runtime targets. ByteDesk Platform is the first reference
consumer, not a synonym for Agent Delivery.
