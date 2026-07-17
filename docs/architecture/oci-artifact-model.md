# OCI artifact model

## Principles

- Exact digests are identity and authority.
- Tags, SemVer, and channels aid discovery only.
- Each artifact has one versioned media type and canonical serialization.
- Referrers are local to the subject repository.
- Cross-repository edges are explicit, signed descriptors.
- Public and private artifact scopes are separated.

## Graph

```text
signed catalog index
        |
        +--> public agent source digest
                  |
                  +--> public harness render digest
                              |
                              +--> private consumer deployment digest
                                           |
                                           +--> private runtime release digest

Each node <- same-repository signature / provenance / SBOM / policy referrers
```

The arrow is not inferred from referrer discovery when repositories differ.
The downstream signed manifest carries the upstream repository, digest, media
type, and expected signer-policy identifier.

## Determinism

Canonical builders fix JSON/YAML normalization, file order, UTF-8, LF endings,
archive timestamps, modes, ownership, compression, and annotation ordering.
Two clean builds with the same normalized inputs must produce the same digest.

## Public artifacts

Source and render artifacts contain no tenant identifiers, private policy,
credentials, or secret references. Public attestations contain no private
consumer data.

## Private deployment artifacts

A private deployment binds public content to one consumer installation and
runtime target. It carries opaque consumer-owned policy/authority subdigests,
not reusable grants. The release manifest aggregates exact deployment
subdigests for a target and makes changes to a system package explicitly
runtime-wide.

## Retention roots

Registry garbage collection must preserve all digests referenced by active,
last-known-good, rollback-source, audit, incident, or legal-hold records. A
withdrawn digest may remain retained for evidence while becoming ineligible for
new activation.

See [OCI media types v1](../standards/oci-media-types-v1.md) for the contract
registry.
