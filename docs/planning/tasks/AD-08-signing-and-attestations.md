# AD-08: Sign agent artifacts and publish supply-chain attestations

- Historical Jira: [BDP-3309](https://bytedesk.atlassian.net/browse/BDP-3309)
- Delivery role: Core product
- Release gate: Blocks trusted import and activation

## Outcome

Establish verifiable product, source, render, qualification, release status,
renderer execution, consumer-authority, private-skill, compilation, deployment,
and runtime-release identity using purpose-separated non-exportable KMS keys,
a separate Sigstore-keyless contract-bundle identity, consumer-sovereign
private signing, Cosign, and in-toto attestations.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- OCI artifact graph and media types from AD-07.
- AD-01 trust roots, signer roles, rotation/revocation, policy, and break-glass decisions.
- CI workload identity, a supported non-exportable KMS provider, and an
  independently pinned Sigstore trusted root for keyless contract-bundle
  release; no exported long-lived signing key.
- Renderer-release manifests and compiled-allowlist/product distribution
  identities from AD-04 through AD-06.
- Frozen consumer-authority, skill-approval, private-signing, machine-contract,
  trust-policy, and operational-readiness schemas.

## Required work

1. Implement exact policies for all 22 purposes in
   [Trust policy v1](../../standards/trust-policy-v1.md), including the distinct
   KMS-only product release, keyless-only contract-bundle release,
   qualification policy/attempt/receipt/evidence/decision, release
   status/status-head and public/private stage-specific eligibility, renderer
   attempt/execution, private-compilation input/evidence, consumer
   runtime-release, and consumer activation-authorization purposes; one
   cryptographically valid key cannot satisfy a different purpose.
2. Sign exact artifact digests with the credential required by the exact
   purpose: a runtime-obtained KMS key version for KMS-backed purposes and the
   exact Sigstore keyless identity/trusted root for
   `contract-bundle-release-v1`. Digest-bearing contract objects are RFC 8785
   JCS bytes; raw authoring YAML is never the Agent Delivery signing input.
3. Emit in-toto provenance including source revision, builder, workflow, exact public/private skill descriptors, inputs, renderer, output digest, and tests; attach an SBOM where executable skill files, code, or dependencies exist, plus compatibility, policy-evaluation, and release-channel attestations as referrers.
4. Implement offline-verifiable trust-policy bundles with key IDs, allowed issuers/builders, media types, consumer/isolation boundaries, validity/rotation state, and minimum evidence.
5. Verify signature, subject, provenance, policy, compatibility, and downgrade constraints before import or activation.
6. Define key rotation, revocation, compromised build/signer response, and re-signing rules without mutating old digests.
7. Add tamper, wrong-signer, revoked-key, missing-attestation, stale-policy, replay, and cross-artifact substitution tests.
8. Implement and certify both allowed consumer-private signing topologies:
   preferred consumer-owned KMS and explicit opt-in tenant-dedicated hosted KMS.
   Authority/approval and deployment keys are separate per consumer; shared
   cross-consumer private keys are rejected.
9. Sign product distributions, compiled allowlists, and exact renderer-release
   manifests under the KMS-only `product-release-v1` policy. Sign contract
   bundles under a separate keyless-only `contract-bundle-release-v1` policy.
   Neither policy may accept the other's purpose, signer, repository, or media
   type; both paths require their applicable SLSA Build Level 3 provenance and
   executed-distribution evidence.
10. Archive immutable trust-policy ID/digest snapshots and distribute host
    policy through an independently authenticated channel.
11. Implement the typed qualification evidence tree, exact predicate-schema
    binding, signed final decision, append-only signed release-status chain, and
    fresh caller-nonce-bound authenticated status-head/consistency-proof flow
    from [Release qualification and status v1](../../standards/release-qualification-v1.md).
12. Implement public and consumer-private stage-specific release-status
    eligibility signing plus the consumer-scoped exact-graph activation
    authorization. Compilation and activation must use independent fresh
    evidence; a Host verifies the complete signed authorization rather than a
    bare digest.
13. Bind the exact non-authority keyless contract-bundle verification receipt
    into every product release. Renderer and private-compilation acceptance
    must independently resolve the bundle, contract policy, signing request,
    and Sigstore bundle and replay the trusted Adapter; the product-release KMS
    signature alone never satisfies contract-bundle verification. Repository
    vectors are conformance-only, while production uses independently operated
    Fulcio/Rekor/Cosign verification.

## Outputs

- Signing and verification command/library surfaces.
- Versioned trust-policy format and fixtures.
- Signed source and render artifacts with in-toto evidence.
- Signed contract/product/renderer releases and embedded-allowlist evidence.
- Signed qualification policy/attempt/receipt/evidence/decision and release
  status/status-head and stage-specific eligibility evidence for every
  renderer/platform matrix cell.
- Signed consumer activation authorization binding the complete immutable
  runtime-release/deployment graph and activation-time eligibility.
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
  private-skill digest also verifies under the consumer-isolated
  `consumer-private-skill-v1` publication signer and separate current
  `consumer-authority-v1` approval.
- Consumers independently pin immutable private key versions and policy
  digests, can revoke trust without provider cooperation, and can migrate
  hosted to consumer-owned keys without rewriting history.
- Renderer and product identity verification binds exact release manifest,
  executable/platform, allowlist, schema, and product trust-policy digests.
- A signed but unqualified, stale-status, rolled-back, forked, withdrawn,
  revoked, or end-of-support release cannot be selected or executed.
- Prohibited purpose pairs cannot share a key/workload identity, and every
  signing result binds the complete request preimage, exact subject media type,
  repository, key version, public key, workflow, environment, and trust policy.

## Verification

Run consumer-owned and tenant-dedicated non-production KMS profiles; WIF/OIDC,
least-IAM, rotation/revocation/migration, cross-consumer/shared-key and
wrong-purpose denial; supplier-provenance substitution denial; Cosign/referrer/
offline policy verification; product/
renderer release, independent downstream/private keyless-receipt replay,
missing/substituted receipt and vector denial, SLSA, SBOM,
vulnerability/license; stale/fresh policy,
qualification matrix/predicate/tree, status nonce/time/consistency,
historical receipt, secret/privacy/redaction, outage, and audit-log tests.

## Not in scope

Production key creation, production registry-policy mutation, consumer identity issuance, or authorization policy.

## Dependencies

Blocked by AD-07.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.kms-signing/1` (`sign-digest`,
  `resolve-signing-request`, `verify-signature`),
  `bytedesk.port.supply-chain-evidence/1` (`generate-sbom`,
  `generate-provenance`, `scan-malware`, `scan-secrets`,
  `attest-scan-completeness`, `scan-vulnerabilities`,
  `evaluate-licenses`), and
  `bytedesk.port.evidence-archive/1` (`put-evidence`, `read-evidence`,
  `advance-archive-root`, `restore-evidence`),
  `bytedesk.port.release-status-head/1` (`append-release-status`,
  `resolve-append-attempt`, `resolve-status-head`),
  `bytedesk.port.trust-policy-provider/1` (`activate-pin-set`,
  `resolve-pin-set`),
  `bytedesk.port.release-qualification-finalizer/1`
  (`finalize-release-qualification`),
  `bytedesk.port.public-render-finalizer/1` (`finalize-public-render`), and
  `bytedesk.port.public-render-publisher/1` (`publish-public-render`) are
  registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** The exact product schema IDs are
  `https://schemas.bytedesk.ai/agent-delivery/v1/signing-request/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/signing-result/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/trust-policy/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/archive-root/1.0.0`, at their
  corresponding paths under `contracts/schemas/v1/`. Exact KMS algorithm,
  provider, signer-purpose, SPDX, in-toto/SLSA, vulnerability, license, scanner,
  and archive profiles are in `contracts/ports/v1/protocol-profiles.json`.
  Signer and request contracts discriminate `kms_key` from
  `sigstore_keyless`: KMS requires an immutable key version/public-key digest;
  keyless contract release forbids both, binds `signerIdentityDigest`, and
  signs the sealed-builder and pre-sign-certification digests while trusted-root
  bytes remain an independent verifier input.
- **Conformance owner.** AD-08 owns consumer-owned and tenant-dedicated KMS,
  contract-release keyless trust, signing replay, purpose/policy separation,
  rotation/revocation, evidence-profile,
  archive, outage, and negative supply-chain fixtures. Run
  `make verify-downstream-ports`; the task-specific suite is
  `downstream.signing-evidence.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Executable protocol acceptance.** `contracts/ports/v1/protocol-fixtures.json`
  contains SPDX 2.3, in-toto SLSA 1.2, vulnerability, malware, secret,
  scan-completeness, and license goldens bound to the exact OCI subject and to
  immutable scanner, database, policy, ruleset, allowlist, sandbox, inventory,
  and evaluation-time pins. `scripts/contracts/test_protocol_fixtures.py`
  recomputes the layer inventory and package verification code, verifies every
  SLSA resource descriptor and scan pin, and proves each declared mutation is
  rejected. The deterministic generator and validator run through
  `make verify-downstream-ports`. License acceptance fixes the strict SPDX 2.3
  expression parser profile, SPDX License List `3.28.0` license and exception
  data digests, and evaluator image digest. It separately proves valid `pass`,
  policy `deny`, unresolved-expression `indeterminate`, invalid-expression
  rejection, and missing-pin rejection. A valid `deny` or `indeterminate`
  report is domain evidence and cannot be rewritten as `pass`; unavailable
  policy/parser inputs return `dependency_unavailable` without a report.
- **Boundary.** Agent Delivery never receives exportable key material and is
  never granted the consumer-authority signing role. Private-skill, authority,
  compilation-input, deployment, compilation-evidence, and runtime-release
  signers are purpose-separated per consumer; evidence proves provenance or
  policy evaluation but cannot grant runtime authority. The one
  authoritative signer-audit reference is
  `signatureEnvelope.providerAuditEvidence.digest` over archived authenticated
  provider-audit bytes; no redundant signer-evidence digest is accepted.

## Architecture review amendments

- Use separate non-exportable purpose keys and workload identities for public source publication, harness render publication, and consumer-private deployment authority. Existing consumer lifecycle/message authority remains separate.
- Use an exact, separate `contract-bundle-release-v1` policy for the keyless
  contract signer. It never shares a policy, signer set, repository, or media
  scope with KMS-only `product-release-v1`.
- Define exact KMS algorithms, immutable key-version names, WIF/OIDC workload identities, least permissions, current/next trust sets, rotation, compromise, digest revocation, and fail-closed KMS behavior.
- Hosts receive trust policy independently; an artifact-supplied key can never bootstrap trust.
- In-toto predicates include source commit, Agent Spec version, renderer identity/digest, tests, exact skill digests, policy/binding/customization digest, customization commit, public-versus-private render scope, and required approval evidence. Consumer grant values and private effective-render evidence remain outside public attestations.
- Keep consumer-identifying attestations out of public transparency services unless privacy is explicitly accepted.
- Retention and garbage-collection tests must prove signed artifacts and attestations referenced by active or last-known-good receipts survive.
