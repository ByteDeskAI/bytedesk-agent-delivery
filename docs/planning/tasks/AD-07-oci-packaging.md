# AD-07: Package source and harness renders as OCI artifacts

- Historical Jira: [BDP-3308](https://bytedesk.atlassian.net/browse/BDP-3308)
- Delivery role: Core product
- Release gate: Blocks signing, import, and deployment compilation

## Outcome

Publish immutable, content-addressed OCI artifacts for canonical source packages and deterministic harness-render bundles using OCI 1.1 subjects/referrers.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Frozen source, artifact, descriptor, canonical-encoding, and media-type
  schemas from AD-01 plus the native/generic render contract from AD-04.
- Registry and ORAS capability findings from AD-01.
- Generic source, skill, and render fixtures; AD-05/AD-06 add certification
  fixtures later but are not implementation dependencies.

## Required work

1. Implement the frozen JSON Schemas and media types for source manifests, skill
   manifests/layers, source layers, public render manifests/bundles, catalog
   indexes, compatibility evidence, common descriptors, and release manifests.
   Validate from the signed offline bundle and use RFC 8785 bytes.
2. Build source and public skill artifacts from canonical public inputs only. Build public catalog renders from an exact source descriptor and exact declared public skill set. Use an OCI `subject` only when the subject is in the same repository; otherwise carry an explicit signed source descriptor.
3. Use ORAS-compatible JCS manifests, exact digest references, deterministic archives, and annotations that are descriptive but never trusted for identity or authority. Preserve arbitrary payload and binary layer bytes exactly; do not interpret a payload as contract YAML based on its filename.
4. Publish public source/skill/catalog-render artifacts to an isolated repository layout with immutable tags used only for discovery. Consumer customization and private effective renders never enter this scope.
5. Implement pull, inspect, and recursive graph traversal by digest. Resolve and
   independently hash every authoritative descriptor plus every OCI manifest,
   config, layer, and blob; verify exact repository, media type, size, semantic
   role, policy, signature, and subject consistency before extraction. Reject
   cycles, duplicate roles, missing content, tag-only edges, unregistered
   media/role pairs, repository-prefix classification, and traversal-limit
   excess.
6. Establish retention rules so any artifact referenced by an active binding or receipt remains reachable.
7. Add local registry integration tests for push, pull, referrers, digest stability, corruption, missing subject, and tag retargeting.
8. Carry the exact renderer-release manifest, executing distribution/platform,
   allowlist, and renderer-owned schema digests in render lineage; a renderer
   version string is never sufficient.
9. Implement explicit local and registry-backed package/build, publish, pull,
   inspect, and verify library/command surfaces for AD-15.
10. Package the complete qualification/status evidence graph and signed
    tenant-free HarnessRender lineage, including exact attempt/execution,
    render-manifest, archive/layer, and `public-render-v1` signing evidence.
11. Keep finalization separate from publication. Accept the complete finalized
    root/config/ordered-layer graph plus mandatory idempotency key and canonical
    request digest; publish by exact descriptor; and return a closed
    `bytedesk.publication-evidence/1` object binding registry identity/request,
    committed and read-back descriptors/raw digests, graph digest, subject,
    artifact type, and timestamps. A lost response enters explicit
    commit-unknown resolution and never produces an invented success receipt.

## Outputs

- Versioned OCI artifact contract and media types.
- Canonical JCS manifest bytes plus byte-exact payload-layer fixtures.
- Deterministic package, publish, and inspect command/library surfaces.
- Public source-to-render artifact graph fixtures.
- Exact renderer-release lineage fixtures and offline contract-bundle
  resolution for every manifest.
- Public skill artifact fixtures containing arbitrary declared regular files, including executable files, without publication-time execution.
- Local registry integration tests and documented retention requirements.
- Typed registry publication evidence and exact idempotent commit/readback
  resolution for every published root.

## Acceptance criteria

- Identical canonical inputs produce the same source digest; identical source, exact skill set, renderer, and normalized parameters produce the same render digest.
- Equivalent restricted YAML/JSON authoring inputs produce identical canonical source objects, while any changed payload byte changes its file/layer digest.
- A public catalog render content-addressably references one exact source descriptor and exact declared public skill set; cross-repository edges never rely on `subject` discovery.
- Consumers activate by digest, never by mutable tag.
- Tag retargeting does not change an existing binding or receipt.
- Malformed or missing layers, wrong media types, or subject mismatch fail closed.
- Direct and transitive config/layer/blob tampering, missing content, cycles,
  duplicate semantic roles, and wrong media/role mappings fail closed; verifying
  only the top-level manifest is never sufficient.
- Public artifacts contain no consuming-platform identities, customization, grants, credentials, tenant data, or private MCP/provider configuration.
- An artifact with an unknown schema, renderer release, trust-policy digest, or
  cross-repository edge fails before payload extraction.
- Finalization performs no registry side effect. `push-artifact` rejects a
  different request under the same idempotency key, never accepts a naked root
  digest, and returns success only when committed and read-back root/config/
  layers equal the complete expected graph byte for byte.

## Verification

Run schema-bundle/offline resolution, deterministic clean rebuilds, JCS
cross-implementation, byte-exact payload, package/publish/pull/inspect, local-
registry push/pull/referrer, recursive config/layer/blob closure,
renderer-lineage substitution, tamper, archive
safety, retention-root, quota/backpressure, and ORAS interoperability tests.

## Not in scope

Signing and attestation, consumer-private deployment artifacts, operating a
production registry service, or mutating a production registry from repository
tests. AD-07 still owns the transport-neutral publication contract, Adapter,
idempotent commit/readback semantics, and local/integration conformance.

## Dependencies

Blocked by AD-01 and AD-04. Full Hermes and OpenClaw certification fixtures come
from AD-05 and AD-06 without changing this implementation dependency.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.oci-registry/1`
  (`head-artifact`, `pull-artifact`, `push-artifact`, `list-referrers`,
  `verify-artifact-graph`) is the transport-neutral Registry Adapter, while
  `bytedesk.port.public-render-publisher/1` (`publish-public-render`) is the
  purpose-separated product protocol that verifies fresh publication-stage
  authority before delegating an opaque authorization context and exact graph
  to that Adapter. Both are registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Exact product schema IDs include
  `https://schemas.bytedesk.ai/agent-delivery/v1/agent-source/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/skill-package/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-release/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/catalog-index/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/publication-evidence/1.0.0`, at their
  corresponding paths under `contracts/schemas/v1/`. The closed OCI
  config/layer/archive layout and named Registry Adapter profiles are in
  `contracts/ports/v1/protocol-profiles.json`; the public media-type registry is
  `docs/standards/oci-media-types-v1.md`.
- **Conformance owner.** AD-07 owns deterministic layout, graph, ORAS,
  push/pull/referrer, retention, corruption, and registry-profile fixtures. Run
  `make verify-downstream-ports`; the task-specific suite is
  `downstream.oci-registry.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Executable protocol acceptance.** `contracts/ports/v1/protocol-fixtures.json`
  contains the byte-exact OCI config, manifest, deterministic tar/gzip layer,
  and bounded chunk-stream goldens plus digest, ordering, gap, overlap, and
  aggregate-digest mutations. `scripts/contracts/test_protocol_fixtures.py`
  reconstructs the layer from contiguous chunks, enforces the 4 MiB chunk and
  64 MiB aggregate limits, verifies every descriptor and archive member, and
  rejects any non-deterministic or unsafe archive. The catalog is generated by
  `scripts/contracts/generate_protocol_fixtures.py`; both scripts run through
  `make verify-downstream-ports`.
- **Boundary.** Registry tags and annotations are discovery metadata. Exact
  descriptors and verified digests are authority; cross-repository edges are
  explicit, and no payload is parsed or executed before graph and archive
  verification.

## Architecture review amendments

- OCI subject/referrer discovery is repository-local. Use `subject` and referrers for signatures, SBOMs, provenance, compatibility, and policy evidence in the same repository only.
- Public render and private deployment manifests contain explicit, signed upstream digest descriptors for cross-repository edges; consumers verify every edge and referenced artifact independently. A private deployment embeds its effective render rather than naming a public render in another repository as its OCI subject.
- Publish a signed, content-addressed catalog index. Semantic version, channel, and tags are discovery metadata only.
- Define repository/project layout, quotas, immutable-tag policy, active/last-known-good/legal-hold garbage-collection roots, backup/restore, withdrawal, compromised-digest revocation, and cached active-agent behavior during outage.
- Add conformance tests against every pinned registry implementation before assuming OCI 1.1 behavior.
