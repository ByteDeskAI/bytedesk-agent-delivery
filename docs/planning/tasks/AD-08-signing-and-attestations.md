# AD-08: Sign agent artifacts and publish supply-chain attestations

- Historical Jira: [BDP-3309](https://bytedesk.atlassian.net/browse/BDP-3309)
- Delivery role: Core product
- Release gate: Blocks trusted import and activation

## Outcome

Establish verifiable publisher identity and policy evidence for source, render, and later private deployment artifacts using Cosign with non-exportable KMS keys and in-toto attestations.

## Inputs

- OCI artifact graph and media types from AD-07.
- AD-01 trust roots, signer roles, rotation/revocation, policy, and break-glass decisions.
- CI workload identity and a supported non-exportable KMS provider; no exported long-lived signing key.

## Required work

1. Implement separate publisher roles and trust policies for marketplace source, harness render, and consumer-private deployment artifacts.
2. Sign exact digests with Cosign using a KMS-backed key reference obtained at runtime.
3. Emit in-toto provenance including source revision, builder, workflow, inputs, renderer, output digest, and tests; attach an SBOM where executable code or dependencies exist, plus compatibility, policy-evaluation, and release-channel attestations as referrers.
4. Implement offline-verifiable trust-policy bundles with key IDs, allowed issuers/builders, media types, consumer/isolation boundaries, validity/rotation state, and minimum evidence.
5. Verify signature, subject, provenance, policy, compatibility, and downgrade constraints before import or activation.
6. Define key rotation, revocation, compromised build/signer response, and re-signing rules without mutating old digests.
7. Add tamper, wrong-signer, revoked-key, missing-attestation, stale-policy, replay, and cross-artifact substitution tests.

## Outputs

- Signing and verification command/library surfaces.
- Versioned trust-policy format and fixtures.
- Signed source and render artifacts with in-toto evidence.
- Key lifecycle and incident runbook.
- Negative supply-chain security test suite.

## Acceptance criteria

- No signing private-key material is exportable, committed, logged, or stored in agent state.
- Verification is digest-first and fails closed for wrong signer, subject, media type, missing required evidence, or revocation.
- Trust policy can rotate keys without losing auditability of historical receipts.
- Build provenance traces every artifact to source revision and builder identity.
- Tags and untrusted annotations never satisfy trust.
- Artifact trust never grants MCP, tools, provider access, organizational role, workload identity, or business approval.

## Verification

Run local or non-production KMS integration, Cosign verification, referrer discovery, all negative fixtures, secret scanning, privacy checks, and audit-log review.

## Not in scope

Production key creation, production registry-policy mutation, consumer identity issuance, or authorization policy.

## Dependencies

Blocked by AD-07.

## Architecture review amendments

- Use separate non-exportable purpose keys and workload identities for public source publication, harness render publication, and consumer-private deployment authority. Existing consumer lifecycle/message authority remains separate.
- Define exact KMS algorithms, immutable key-version names, WIF/OIDC workload identities, least permissions, current/next trust sets, rotation, compromise, digest revocation, and fail-closed KMS behavior.
- Hosts receive trust policy independently; an artifact-supplied key can never bootstrap trust.
- In-toto predicates include source commit, Agent Spec version, renderer identity/digest, tests, policy/binding digest, overlay commit, and required approval evidence. Consumer grant values remain outside public attestations.
- Keep consumer-identifying attestations out of public transparency services unless privacy is explicitly accepted.
- Retention and garbage-collection tests must prove signed artifacts and attestations referenced by active or last-known-good receipts survive.
