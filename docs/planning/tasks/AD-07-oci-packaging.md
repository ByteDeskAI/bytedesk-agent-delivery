# AD-07: Package source and harness renders as OCI artifacts

- Historical Jira: [BDP-3308](https://bytedesk.atlassian.net/browse/BDP-3308)
- Delivery role: Core product
- Release gate: Blocks signing, import, and deployment compilation

## Outcome

Publish immutable, content-addressed OCI artifacts for canonical source packages and deterministic harness-render bundles using OCI 1.1 subjects/referrers.

## Inputs

- Marketplace package contract and render manifest from AD-02 and AD-04.
- Registry and ORAS capability findings from AD-01.
- Baseline source packages and renderer fixtures.

## Required work

1. Define and version media types and artifact types for source manifests, source layers, render manifests, render bundles, catalog indexes, and compatibility metadata.
2. Build source artifacts from canonical inputs only and render artifacts whose subject is the exact source digest.
3. Use ORAS-compatible manifests, exact digest references, deterministic archives, and annotations that are descriptive but never trusted for identity or authority.
4. Publish public source/render artifacts to an isolated repository layout with immutable tags used only for discovery.
5. Implement pull, inspect, and graph traversal by digest and verify layer, media-type, and subject consistency before extraction.
6. Establish retention rules so any artifact referenced by an active binding or receipt remains reachable.
7. Add local registry integration tests for push, pull, referrers, digest stability, corruption, missing subject, and tag retargeting.

## Outputs

- Versioned OCI artifact contract and media types.
- Deterministic package, publish, and inspect command/library surfaces.
- Public source-to-render artifact graph fixtures.
- Local registry integration tests and documented retention requirements.

## Acceptance criteria

- Identical canonical inputs produce the same source digest; identical source, renderer, and parameters produce the same render digest.
- A render artifact content-addressably references one exact source subject.
- Consumers activate by digest, never by mutable tag.
- Tag retargeting does not change an existing binding or receipt.
- Malformed or missing layers, wrong media types, or subject mismatch fail closed.
- Public artifacts contain no consuming-platform identities, grants, credentials, tenant data, or MCP configuration.

## Verification

Run deterministic clean rebuilds, local-registry push/pull/referrer tests, tamper tests, archive safety tests, and ORAS interoperability checks.

## Not in scope

Signing and attestation, consumer-private deployment artifacts, or production registry publication.

## Dependencies

Blocked by AD-02 and AD-04. Full harness fixtures come from AD-05 and AD-06.

## Architecture review amendments

- OCI referrer discovery is repository-local. Use `subject` and referrers for signatures, SBOMs, provenance, compatibility, and policy evidence in the same repository only.
- Render and private deployment manifests contain explicit, signed upstream digest descriptors for cross-repository edges; consumers verify every edge and referenced artifact independently.
- Publish a signed, content-addressed catalog index. Semantic version, channel, and tags are discovery metadata only.
- Define repository/project layout, quotas, immutable-tag policy, active/last-known-good/legal-hold garbage-collection roots, backup/restore, withdrawal, compromised-digest revocation, and cached active-agent behavior during outage.
- Add conformance tests against every pinned registry implementation before assuming OCI 1.1 behavior.
