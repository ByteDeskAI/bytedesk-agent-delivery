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
5. Implement pull, inspect, and graph traversal by digest and verify layer, media-type, and subject consistency before extraction.
6. Establish retention rules so any artifact referenced by an active binding or receipt remains reachable.
7. Add local registry integration tests for push, pull, referrers, digest stability, corruption, missing subject, and tag retargeting.
8. Carry the exact renderer-release manifest, executing distribution/platform,
   allowlist, and renderer-owned schema digests in render lineage; a renderer
   version string is never sufficient.
9. Implement explicit local and registry-backed package/build, publish, pull,
   inspect, and verify library/command surfaces for AD-15.

## Outputs

- Versioned OCI artifact contract and media types.
- Canonical JCS manifest bytes plus byte-exact payload-layer fixtures.
- Deterministic package, publish, and inspect command/library surfaces.
- Public source-to-render artifact graph fixtures.
- Exact renderer-release lineage fixtures and offline contract-bundle
  resolution for every manifest.
- Public skill artifact fixtures containing arbitrary declared regular files, including executable files, without publication-time execution.
- Local registry integration tests and documented retention requirements.

## Acceptance criteria

- Identical canonical inputs produce the same source digest; identical source, exact skill set, renderer, and normalized parameters produce the same render digest.
- Equivalent restricted YAML/JSON authoring inputs produce identical canonical source objects, while any changed payload byte changes its file/layer digest.
- A public catalog render content-addressably references one exact source descriptor and exact declared public skill set; cross-repository edges never rely on `subject` discovery.
- Consumers activate by digest, never by mutable tag.
- Tag retargeting does not change an existing binding or receipt.
- Malformed or missing layers, wrong media types, or subject mismatch fail closed.
- Public artifacts contain no consuming-platform identities, customization, grants, credentials, tenant data, or private MCP/provider configuration.
- An artifact with an unknown schema, renderer release, trust-policy digest, or
  cross-repository edge fails before payload extraction.

## Verification

Run schema-bundle/offline resolution, deterministic clean rebuilds, JCS
cross-implementation, byte-exact payload, package/publish/pull/inspect, local-
registry push/pull/referrer, renderer-lineage substitution, tamper, archive
safety, retention-root, quota/backpressure, and ORAS interoperability tests.

## Not in scope

Signing and attestation, consumer-private deployment artifacts, or production registry publication.

## Dependencies

Blocked by AD-01 and AD-04. Full Hermes and OpenClaw certification fixtures come
from AD-05 and AD-06 without changing this implementation dependency.

## Architecture review amendments

- OCI subject/referrer discovery is repository-local. Use `subject` and referrers for signatures, SBOMs, provenance, compatibility, and policy evidence in the same repository only.
- Public render and private deployment manifests contain explicit, signed upstream digest descriptors for cross-repository edges; consumers verify every edge and referenced artifact independently. A private deployment embeds its effective render rather than naming a public render in another repository as its OCI subject.
- Publish a signed, content-addressed catalog index. Semantic version, channel, and tags are discovery metadata only.
- Define repository/project layout, quotas, immutable-tag policy, active/last-known-good/legal-hold garbage-collection roots, backup/restore, withdrawal, compromised-digest revocation, and cached active-agent behavior during outage.
- Add conformance tests against every pinned registry implementation before assuming OCI 1.1 behavior.
