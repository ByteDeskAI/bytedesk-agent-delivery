# Contributing

ByteDesk Agent Delivery is documentation-first while its v1 contracts are being
implemented.

## Before changing a boundary

Read:

- [`AGENTS.md`](AGENTS.md)
- [`docs/product/scope-and-boundaries.md`](docs/product/scope-and-boundaries.md)
- [`docs/architecture/adr/0001-independent-agent-delivery-control-plane.md`](docs/architecture/adr/0001-independent-agent-delivery-control-plane.md)
- [`docs/architecture/adr/0002-implementation-stack-and-reference-topology.md`](docs/architecture/adr/0002-implementation-stack-and-reference-topology.md)
- [`docs/architecture/security-and-trust.md`](docs/architecture/security-and-trust.md)
- [`docs/standards/machine-contracts-v1.md`](docs/standards/machine-contracts-v1.md)
- [`docs/standards/renderer-identity-v1.md`](docs/standards/renderer-identity-v1.md)
- [`docs/standards/consumer-authority-v1.md`](docs/standards/consumer-authority-v1.md)
- [`docs/standards/delivery-lifecycle-v1.md`](docs/standards/delivery-lifecycle-v1.md)
- [`docs/standards/operational-readiness-v1.md`](docs/standards/operational-readiness-v1.md)

Open or amend an ADR before introducing a new trust boundary, authority owner,
artifact class, renderer-loading model, deployment state authority, or
cross-consumer data path.

## Reference implementation toolchain

ADR-0002 is authoritative for implementation technology. The control plane,
CLI, and host protocol use Go 1.26; official Agent Spec validation runs in
hash-locked Python 3.13 sandbox workers, while WayFlow compatibility is a
separate CI-only lane. PostgreSQL 18 is the reference authoritative store and
durable action/outbox boundary. Production conformance uses Kubernetes
1.36/1.35, synchronous publication to active and recovery-region Harbor HA
endpoints, non-exportable KMS/WIF signing, SPIFFE mTLS, and gVisor renderer
isolation.

Use only repository entry points and locked tools. Do not rely on a host Go,
Python, Node, container, schema, or CLI version that is not declared by the
repository. Development may use Compose, but production sandbox, multi-zone,
KMS, restore, and scale claims require their dedicated conformance profiles.

## Pull requests

- Keep each change scoped to one task and one verifiable outcome.
- Add failing tests before implementation for code changes.
- Include positive, denial, malformed-input, and relevant fault-injection cases.
- Preserve deterministic output and exact-digest authority.
- Accept YAML only as restricted human authoring input. Tests must prove that
  the YAML 1.2 JSON-compatible subset converts to the same RFC 8785 JCS bytes as
  equivalent JSON and that duplicate keys, aliases, custom tags, non-string
  keys, and non-finite numbers fail closed.
- Treat the source-controlled JSON Schema Draft 2020-12 files as normative.
  Update their immutable identity, signed contract bundle, compatibility
  metadata, fixtures, generated models, OpenAPI, AsyncAPI, examples, and prose
  together; runtime schema references must resolve offline from the trusted
  bundle.
- Use the accepted closed `bytedesk.json-patch/1`, file-operation, and
  skill-operation profiles. Unknown fields, operations, paths, mutable
  descriptors, and failed existence/digest preconditions fail atomically.
- Do not add secrets, private keys, production mutations, or real tenant data.
- Do not make portable packages authoritative for tools, MCP, providers,
  credentials, users, roles, or grants.
- Public catalog renders must contain only public source and the exact declared
  public skill set. Consumer customization is compiled and rendered only inside
  a private boundary.

## Renderer contributions

Renderers are compiled, allowlisted Adapters. A renderer must publish a
signed immutable renderer-release manifest, actual executing distribution
digests, owned schema digests, SLSA Build Level 3 provenance, SBOM and policy
evidence, compatibility matrix, deterministic cross-platform fixtures,
file-digest manifest, sandbox evidence, and explicit loss behavior. Runtime-
loaded renderer plugins are not accepted. The same exact renderer release must
fully rerender the resolved private effective definition; a post-render file
patch is not an accepted customization mechanism.

## Delivery lifecycle contributions

There is one `TargetDeliveryState` and one selected `DesiredStateStore` per
consumer/runtime target. Only the Promotion Coordinator advances it by the
discriminated revision-and-digest precondition. Host observations, consumer
capability evidence, Git intent, prepared releases, and recovery proposals are
separate inputs. Changes must preserve actor separation, fresh canary evidence,
current consumer authority, and current-tooling forward recovery without dual
desired-state writers.

Operational claims require the reproducible SLO, scale, limit, restore,
retention, security-response, compatibility, and support evidence defined by
the readiness contract. Architecture acceptance alone is not release evidence.

## Catalog contributions

Canonical agent definitions belong in a compatible definition-only catalog
repository, not this product repository. This repository may contain only
minimal test fixtures required to prove contracts.

Skill packages may contain arbitrary regular files, including scripts, binaries,
archives, data, and dependency manifests. Publication and delivery treat them as
untrusted bytes and never execute them. Contributions must include declared-file
manifests, deterministic digests, applicable SBOM/license/malware evidence, and
fixtures proving that unsafe filesystem entries and secret values are rejected.
Arbitrary payload files, including files named `.yaml`, remain byte-exact and
are not interpreted as contract documents unless their declared media type says
they are one.
