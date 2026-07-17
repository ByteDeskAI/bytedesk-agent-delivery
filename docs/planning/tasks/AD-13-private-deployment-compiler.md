# AD-13: Compile private consumer deployment artifacts

- Historical Jira: [BDP-3314](https://bytedesk.atlassian.net/browse/BDP-3314)
- Delivery role: Core product control plane
- Release gate: Blocks runtime reconciliation

## Outcome

Compile verified public content, strict private customization, exact approved
skills, fresh consumer authority, and runtime binding into a private
`application/vnd.bytedesk.agent.deployment.v1+json` artifact. Reconstruct the
effective Agent Spec and rerender with the exact signed renderer release while
remaining harness/consumer-neutral and non-authorizing.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Verified source/render descriptors and trust evidence.
- Active installation definition binding; canonical customization document; declared file add/replace/remove operations; and exact public/private skill descriptors and digests.
- Prepared candidate/target revision from the Promotion Coordinator and a fresh
  signed `compile` consumer-authority snapshot binding the exact consumer,
  subject, installation, harness, target, candidate, desired revision,
  predecessor, policy/grant/credential/workload-identity/lifecycle/sandbox/
  network/approval digests, nonce, and expiry.
- OCI packaging, consumer-private registry, and deployment-signing policy.
- Exact renderer-release descriptor accepted by the compiled allowlist, plus
  strict functional/file/skill operation and current skill-approval evidence.
- Historical `bytedesk.hermes-deployment/2` and ByteDesk `AgentDeploymentRevision` as AD-16 reference-adapter migration inputs, not core schema authority.

## Required work

1. Implement the versioned consumer deployment artifact with exact schema,
   source, public render, renderer release, executing distribution/platform,
   allowlist, customization, file, skill/approval, installation, subject,
   target, consumer-authority/policy, desired revision, and predecessor
   descriptors. Cross-repository parents are explicit signed descriptors.
2. Define an adapter migration contract for prior consumer formats. Do not silently reinterpret historical payloads as verified current OCI state. ByteDesk Hermes v2 backward-read behavior is implemented and certified in AD-16.
3. Permit the private customization to change any functional Agent Spec property and to add, replace, or remove declared regular files and skills. This includes instructions and behavior, logical or concrete model/provider selection, tools/MCP functional configuration, harness settings, and opaque secret references. Reject tenant/organization identity, roles or grants, call-time authorization, workload identity or token issuance, raw credentials/private keys/secret values, trust roots or signers, and changes that weaken mandatory sandbox, security, or approval controls.
4. Atomically apply the strict functional/file/skill operations exactly once,
   reconstruct and revalidate the full effective Agent Spec, and perform a
   complete deterministic render with the exact renderer release recorded in
   public lineage. Embed the private manifest/bundle; never post-patch or create
   a separate private-render OCI type.
5. Reuse public render bytes only when the customization and private skill set are empty and every normalized renderer input, including the exact public skill set, is identical. Otherwise generate the effective render from the complete private inputs.
6. Treat every skill payload as untrusted data. Skills may contain any declared regular files, including scripts, binaries, archives, data, and dependencies, but validation, compilation, rendering, publication, staging, and activation never execute them or artifact-provided hooks. Reject unsafe paths and entry types, secret material, undeclared content, resource-limit violations, and malicious archives.
7. Verify the short-lived consumer-authority snapshot, current skill approvals,
   exact policy digests, target/candidate/predecessor, and snapshot freshness
   immediately before compilation and publication. The deployment signer cannot
   issue authority or approval.
8. Publish and sign through a consumer-owned or explicitly opted-in tenant-
   dedicated KMS key under `consumer-deployment-v1`. Enforce per-consumer key,
   workload, registry, and trust isolation; no cross-consumer shared private key.
9. Enforce cross-installation registry isolation, least pull scope, retention, legal hold, and garbage-collection roots.
10. Reject stale or revoked inputs, wrong target, untrusted parents, mutable tag
    references, cross-installation subjects, renderer/harness mismatch,
    forbidden authority customization, changed/unapproved skills, or invalid
    signed consumer-authority/approval evidence.
11. Return an immutable prepared-candidate descriptor and evidence to the
    Promotion Coordinator. The compiler never writes TargetDeliveryState,
    promotes, or assumes a compilation snapshot can authorize activation.

## Outputs

- Consumer deployment v1 compiler and versioned compatibility/migration adapter contract.
- Private registry publisher and installation/target authorization policy.
- Prepared-state deployment-receipt integration.
- Fresh consumer-authority/skill-approval verifier, consumer-private signing
  Adapter, and prepared-candidate command contract.
- Migration fixtures plus security, determinism, idempotency, and isolation tests.

## Acceptance criteria

- The artifact is valid only for the exact installation, consumer subject, harness, runtime target, slot generation, and desired-state revision.
- The artifact contains the complete effective render manifest and bundle produced from the exact public source, deterministic customization, exact skills, and pinned renderer identity; it is not a patched public render.
- Any functional property may be customized privately, while every security-authority and mandatory-control mutation is rejected.
- Arbitrary declared regular skill files are preserved without being executed anywhere in Agent Delivery's pipeline.
- No private key, bearer/refresh token, provider credential, certificate, or reusable secret is present.
- Verification traverses deployment → explicit effective/public render lineage → source and skill exact digests plus required attestations; it does not infer a cross-repository parent from OCI referrers.
- Repeating compilation returns the existing prepared receipt without duplicates.
- Equivalent allowed authoring YAML and JSON compile to the same canonical deployment inputs and digest; raw YAML never enters the signature calculation.
- Historical consumer payloads remain honestly classified by their adapters; cross-installation, stale, revoked, or denied input fails closed.
- The artifact references consumer authority but cannot grant, broaden, or restore it.
- Renderer semantic version alone, stale compile authority, deployment-key
  self-approval, shared private key, direct desired-state write, or unapproved
  skill fails closed.

## Verification

Run schema/offline-bundle and strict-operation atomicity/fuzz tests; exact
renderer/public-private lineage; consumer-authority freshness/nonce/audience/
candidate/subdigest/replay; skill approval expiry/revocation; consumer-owned and
tenant-dedicated KMS signing, wrong-purpose/shared-key/self-approval denial;
private-registry isolation; deterministic rebuild; secret/archive/resource
limits; idempotency/concurrency; no-desired-write; and legacy Adapter tests.

## Not in scope

Applying the artifact to a runtime, creating consumer identity or grants, storing credential values, or implementing ByteDesk Hermes v2 migration.

## Dependencies

Blocked by AD-04, AD-07, AD-08, AD-09, and AD-12. It does not depend on Git or
every harness Adapter; a deployment requires only its selected released
renderer.

## Architecture review amendments

- The deployment contract carries per-subject deployment subdigests and a signed runtime-release manifest aggregating exact target digests. Updating one agent does not rotate unrelated workload identities or advance unrelated receipts.
- The signed target includes the consumer-supplied durable slot allocation: subject reference, profile name, UID/GID, port, service, workspace, slot generation, and tombstone-policy digest where the harness needs them. Never derive slots from catalog or roster order.
- Cross-repository parents are explicit signed digest descriptors because OCI referrers cannot discover subjects in another repository.
- Compilation always re-resolves the consumer's current lifecycle,
  authorization-policy/grant revision, workload-identity/certificate binding,
  runtime slot, and approval verdict. Forward recovery cannot reuse stale
  authority from an old artifact.
- Package extraction and build enforce count, size, depth, mode, path, link, device, and decompression limits and never execute packaged scripts, binaries, hooks, or dependencies.
- The runtime-release manifest defines whether a system-package change is target-wide while ordinary agent changes remain subject-scoped.
