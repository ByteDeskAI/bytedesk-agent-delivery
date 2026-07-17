# OCI media types v1

**Status:** Draft registry; contract tests freeze exact values before publishing

## Artifact types

| Artifact | Proposed `artifactType` |
|---|---|
| Catalog index | `application/vnd.bytedesk.agent.catalog.v1+json` |
| Agent source | `application/vnd.bytedesk.agent.source.v1+json` |
| Harness render | `application/vnd.bytedesk.agent.render.v1+json` |
| Consumer deployment | `application/vnd.bytedesk.agent.deployment.v1+json` |
| Runtime release | `application/vnd.bytedesk.agent.release.v1+json` |
| Render compatibility attestation | `application/vnd.bytedesk.agent.compatibility.v1+json` |
| Evaluation attestation | `application/vnd.bytedesk.agent.evaluation.v1+json` |
| Consumer policy attestation | `application/vnd.bytedesk.agent.policy.v1+json` |
| Deployment receipt | `application/vnd.bytedesk.agent.receipt.v1+json` |

Signatures, in-toto provenance, and SBOMs use their ecosystem-standard media
types where possible. ByteDesk-specific predicates use the versioned types
above.

## Common descriptor

Every explicit artifact edge contains:

```json
{
  "repository": "registry.example/agents/source/chief-of-staff",
  "digest": "sha256:...",
  "mediaType": "application/vnd.bytedesk.agent.source.v1+json",
  "size": 12345,
  "trustPolicy": "public-source-v1"
}
```

Repository canonicalization, digest algorithm, size, expected media type, and
trust policy are verified before content is accepted. An annotation is never a
substitute for this signed descriptor.

## Catalog index

The catalog lists exact source descriptors, semantic/display metadata, release
channels, compatibility summaries, skill digests, publication time, and
withdrawal state. It is discovery data. A consumer verifies the referenced
source independently.

## Agent source

The source manifest identifies Agent Spec version, package identifier,
selectability/system status, deterministic source-layer digest, optional skill
descriptors, and policy-validation result. Layers are inert data and never
contain install scripts.

## Harness render

The render manifest explicitly references the source descriptor and includes
renderer identifier/version/digest, normalized parameters, compatibility
result, warnings/loss decision, output layer, and a file-digest inventory.

## Consumer deployment

The private deployment explicitly references public source and render plus the
binding, specialization, consumer-policy, authority, credential-set, identity,
slot, and runtime-target subdigests. Sensitive values are not embedded.

## Runtime release

The release aggregates exact per-agent deployment subdigests for one runtime
target and identifies any system package. It carries predecessor, desired-state
revision, rollout policy, and activation constraints.

## Referrers

Signatures and attestations refer to an exact subject in the same repository.
The verifier does not attempt to discover a source artifact's referrers from a
different repository. Downstream artifacts carry signed upstream descriptors.

## Canonical encoding

JSON contracts use a defined canonical JSON profile. Archive layers fix file
order, paths, timestamps, modes, ownership, compression algorithm, and
compression parameters. Empty optional values are represented consistently;
unknown fields are rejected for security-relevant manifests.
