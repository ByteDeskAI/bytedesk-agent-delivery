# AD-08: Sign agent artifacts and publish supply-chain attestations

- Historical Jira: [BDP-3309](https://bytedesk.atlassian.net/browse/BDP-3309)
- Delivery role: Core product
- Release gate: Blocks trusted import and activation

## Outcome

Establish verifiable product, source, render, consumer-authority, private-skill,
and deployment identity using purpose-separated non-exportable KMS keys,
consumer-sovereign private signing, Cosign, and in-toto attestations.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- OCI artifact graph and media types from AD-07.
- AD-01 trust roots, signer roles, rotation/revocation, policy, and break-glass decisions.
- CI workload identity and a supported non-exportable KMS provider; no exported long-lived signing key.
- Renderer-release manifests and compiled-allowlist/product distribution
  identities from AD-04 through AD-06.
- Frozen consumer-authority, skill-approval, private-signing, machine-contract,
  trust-policy, and operational-readiness schemas.

## Required work

1. Implement exact policies for `product-release-v1`,
   `public-source-v1`, `public-render-v1`,
   `consumer-private-skill-v1`, `consumer-authority-v1`, and
   `consumer-deployment-v1`; one cryptographically valid key cannot satisfy a
   different purpose.
2. Sign exact artifact digests with Cosign using a KMS-backed key reference obtained at runtime. Digest-bearing contract objects are RFC 8785 JCS bytes; raw authoring YAML is never the Agent Delivery signing input.
3. Emit in-toto provenance including source revision, builder, workflow, exact public/private skill descriptors, inputs, renderer, output digest, and tests; attach an SBOM where executable skill files, code, or dependencies exist, plus compatibility, policy-evaluation, and release-channel attestations as referrers.
4. Implement offline-verifiable trust-policy bundles with key IDs, allowed issuers/builders, media types, consumer/isolation boundaries, validity/rotation state, and minimum evidence.
5. Verify signature, subject, provenance, policy, compatibility, and downgrade constraints before import or activation.
6. Define key rotation, revocation, compromised build/signer response, and re-signing rules without mutating old digests.
7. Add tamper, wrong-signer, revoked-key, missing-attestation, stale-policy, replay, and cross-artifact substitution tests.
8. Implement and certify both allowed consumer-private signing topologies:
   preferred consumer-owned KMS and explicit opt-in tenant-dedicated hosted KMS.
   Authority/approval and deployment keys are separate per consumer; shared
   cross-consumer private keys are rejected.
9. Sign product distributions, contract bundles, compiled allowlists, and exact
   renderer-release manifests under product-release policy with SLSA Build
   Level 3 provenance and executed-distribution evidence.
10. Archive immutable trust-policy ID/digest snapshots and distribute host
    policy through an independently authenticated channel.

## Outputs

- Signing and verification command/library surfaces.
- Versioned trust-policy format and fixtures.
- Signed source and render artifacts with in-toto evidence.
- Signed contract/product/renderer releases and embedded-allowlist evidence.
- Signed public skill artifacts and non-execution evidence for arbitrary skill payloads.
- Consumer-owned and tenant-dedicated hosted KMS Adapter profiles, authority/
  approval/private-skill/deployment signer separation, rotation/migration
  ceremonies, and denial fixtures for every forbidden topology.
- Key lifecycle and incident runbook.
- Negative supply-chain security test suite.

## Acceptance criteria

- No signing private-key material is exportable, committed, logged, or stored in agent state.
- Verification is digest-first and fails closed for wrong signer, subject, media type, missing required evidence, or revocation.
- Trust policy can rotate keys without losing auditability of historical receipts.
- Build provenance traces every artifact to source revision and builder identity.
- Signature verification reproduces the validated JSON data model and exact JCS bytes; parser-equivalent but byte-different authoring YAML cannot alter the semantic object.
- Tags and untrusted annotations never satisfy trust.
- Artifact trust never grants MCP, tools, provider access, organizational role, workload identity, or business approval.
- No shared provider key signs private artifacts for multiple consumers; a
  compiler cannot use its deployment key to approve itself.
- An independent supplier signature is upstream provenance only; the unchanged
  private-skill digest also verifies under the consumer-isolated role-4
  publication signer and separate current role-5 approval.
- Consumers independently pin immutable private key versions and policy
  digests, can revoke trust without provider cooperation, and can migrate
  hosted to consumer-owned keys without rewriting history.
- Renderer and product identity verification binds exact release manifest,
  executable/platform, allowlist, schema, and product trust-policy digests.

## Verification

Run consumer-owned and tenant-dedicated non-production KMS profiles; WIF/OIDC,
least-IAM, rotation/revocation/migration, cross-consumer/shared-key and
wrong-purpose denial; supplier-provenance substitution denial; Cosign/referrer/
offline policy verification; product/
renderer release, SLSA, SBOM, vulnerability/license; stale/fresh policy,
historical receipt, secret/privacy/redaction, outage, and audit-log tests.

## Not in scope

Production key creation, production registry-policy mutation, consumer identity issuance, or authorization policy.

## Dependencies

Blocked by AD-07.

## Architecture review amendments

- Use separate non-exportable purpose keys and workload identities for public source publication, harness render publication, and consumer-private deployment authority. Existing consumer lifecycle/message authority remains separate.
- Define exact KMS algorithms, immutable key-version names, WIF/OIDC workload identities, least permissions, current/next trust sets, rotation, compromise, digest revocation, and fail-closed KMS behavior.
- Hosts receive trust policy independently; an artifact-supplied key can never bootstrap trust.
- In-toto predicates include source commit, Agent Spec version, renderer identity/digest, tests, exact skill digests, policy/binding/customization digest, customization commit, public-versus-private render scope, and required approval evidence. Consumer grant values and private effective-render evidence remain outside public attestations.
- Keep consumer-identifying attestations out of public transparency services unless privacy is explicitly accepted.
- Retention and garbage-collection tests must prove signed artifacts and attestations referenced by active or last-known-good receipts survive.
