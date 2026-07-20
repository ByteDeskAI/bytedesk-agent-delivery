# AD-13: Compile private consumer deployment artifacts

- Historical Jira: [BDP-3314](https://bytedesk.atlassian.net/browse/BDP-3314)
- Delivery role: Core product control plane
- Release gate: Blocks runtime reconciliation

## Outcome

Compile verified public content, strict private customization, exact approved
skills, fresh consumer authority, and runtime binding into a private
`application/vnd.bytedesk.agent.consumer-deployment.v1+json` artifact. Reconstruct the
effective Agent Spec and rerender with the exact signed renderer release while
remaining harness/consumer-neutral and non-authorizing.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Verified, purpose-signed source/public-render descriptors; exact release
  qualification; and fresh nonce-bound authenticated current product/renderer
  status-head evidence.
- Active installation definition binding; canonical customization document; declared file add/replace/remove operations; and exact public/private skill descriptors and digests.
- Prepared candidate/target revision from the Promotion Coordinator and a fresh
  signed `compile` consumer-authority snapshot binding the exact consumer,
  subject, installation, harness, target, candidate, desired revision,
  predecessor, policy/grant/credential/workload-identity/lifecycle/sandbox/
  network/approval digests, nonce, and expiry.
- OCI packaging, consumer-private registry, and deployment-signing policy.
- Exact renderer-release descriptor accepted by the compiled allowlist, plus
  strict functional/file/skill operation and current skill-approval evidence.
- One complete `bytedesk.private-compilation-input/1` lock validated under its
  exact schema ID and digest. The lock is the only compilation-input identity;
  callers cannot submit a convenient subset of its public, private, authority,
  policy, renderer, or contract fields.
- One complete `bytedesk.private-input-authentication-bundle/1` resolving every
  public/private source, skill, approval, authority, binding, candidate, and
  renderer input to its exact role, object descriptor, and full signing result.
- An exact `bytedesk.external-input-lock/1` artifact for historical
  `bytedesk.hermes-deployment/2` and ByteDesk `AgentDeploymentRevision`
  migration inputs. The lock binds repository URL, immutable commit,
  source-tree digest, sorted path/digest inventory, and
  `compatibilityEvidenceOnly: true`; AD-16 owns this reference adapter and the
  locked inputs never become core schema authority.

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
   public lineage. Embed the private manifest and bind its exact payload; never post-patch or create
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
11. Commit and return exact descriptors for the canonical input lock, consumer
    deployment, and separately signed private-compilation evidence to the
    Promotion Coordinator. The compiler never writes TargetDeliveryState,
    promotes, or assumes a compilation snapshot can authorize activation.
12. Require the compilation-input signer to authenticate the complete frozen
    lock under `consumer-compilation-input-v1`; carry that full signing result
    in the deployment so verification reaches the exact lock without ambient
    request state. Sign the separate evidence under
    `consumer-compilation-evidence-v1`.
13. Prepare the runtime-release subject entry with both the exact canonical
    deployment and exact compilation-evidence descriptors and sign the root
    under `consumer-runtime-release-v1`. The deployment has no evidence or
    runtime-release backlink.

## Outputs

- Consumer deployment v1 compiler and versioned compatibility/migration adapter contract.
- Private registry publisher and installation/target authorization policy.
- Prepared-state deployment-receipt integration.
- Exact private-compilation evidence statement/envelope and its consumer-
  isolated signing profile.
- Fresh consumer-authority/skill-approval verifier, consumer-private signing
  Adapter, and prepared-candidate command contract.
- Migration fixtures plus security, determinism, idempotency, and isolation tests.

## Acceptance criteria

- The artifact is valid only for the exact installation, consumer subject, harness, runtime target, slot generation, and desired-state revision.
- The artifact contains the complete effective render manifest, exact payload descriptor, and closed issued-attempt/authenticated-execution lineage produced from the exact public source, deterministic customization, exact skills, and pinned renderer identity; it is not a patched public render.
- Any functional property may be customized privately, while every security-authority and mandatory-control mutation is rejected.
- Arbitrary declared regular skill files are preserved without being executed anywhere in Agent Delivery's pipeline.
- No private key, bearer/refresh token, provider credential, certificate, or reusable secret is present.
- Verification traverses lock → issued and authenticated renderer attempt → authenticated execution receipt → effective render manifest/payload → canonical deployment descriptor → separately signed compilation evidence. It does not infer a cross-repository parent from OCI referrers.
- Verification also traverses the private-input authentication bundle and full
  `consumer-compilation-input-v1` signing result; no bare digest can replace an
  authenticated input object. Each entry binds the exact subject to an exact
  detached signing-result object. That object may live in a distinct evidence
  repository only when the current purpose policy permits that repository; the
  verifier still checks the signed subject digest/media type, policy, signing
  repository, provider evidence, and trusted-KMS result exactly and never
  infers an authentication edge from a tag or registry referrer listing.
- The runtime release binds each exact deployment/compilation-evidence pair and
  all consumer/target/revision/slot/generation fields under the distinct
  `consumer-runtime-release-v1` purpose.
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
candidate/exact-descriptor/replay; skill approval expiry/revocation; consumer-owned and
tenant-dedicated KMS signing, wrong-purpose/shared-key/self-approval denial;
full input-authentication bundle and compilation-input signing-result closure;
qualification/status freshness and deployment/evidence/runtime-release graph closure;
private-registry isolation; deterministic rebuild; secret/archive/resource
limits; idempotency/concurrency; no-desired-write; and legacy Adapter tests.

## Not in scope

Applying the artifact to a runtime, creating consumer identity or grants, storing credential values, or implementing ByteDesk Hermes v2 migration.

## Dependencies

Blocked by AD-04, AD-07, AD-08, AD-09, and AD-12. It does not depend on Git or
every harness Adapter; a deployment requires only its selected released
renderer.

## Normative contracts and conformance

- **Ports and operations.** `bytedesk.port.private-compiler/1`
  (`compile-private-deployment`, `resolve-compile-attempt`),
  `bytedesk.port.agent-spec-validator/1` (`validate-agent-spec`),
  `bytedesk.port.renderer-strategy/1` (`select-renderer`, `render`),
  `bytedesk.port.renderer-adapter/1` (`render`, `validate-output`),
  `bytedesk.port.renderer-sandbox/1` (`execute-renderer`),
  `bytedesk.port.oci-registry/1` (`push-artifact`, `verify-artifact-graph`),
  `bytedesk.port.kms-signing/1` (`sign-digest`,
  `resolve-signing-request`), and
  `bytedesk.port.consumer-authority-approval/1`
  (`resolve-authority-snapshot`, `resolve-skill-approval`,
  `verify-private-authority`) are registered in
  `contracts/ports/v1/port-registry.json`. Exact field-value and closed
  request/result schemas are distributed in
  `contracts/ports/v1/type-catalog.json`; canonical valid and structural-denial
  payloads are in `contracts/ports/v1/contract-fixtures.json`.
- **Schemas, artifacts, and profiles.** Exact schema IDs include
  `https://schemas.bytedesk.ai/agent-delivery/v1/private-compilation-input/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/private-compilation-evidence/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/runtime-release/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/candidate/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/deployment-receipt/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/consumer-authority/1.0.0`,
  `https://schemas.bytedesk.ai/agent-delivery/v1/skill-approval/1.0.0`, and
  `https://schemas.bytedesk.ai/agent-delivery/v1/agent-binding/1.0.0`, under
  `contracts/schemas/v1/`. Compiler, full-private-rerender, signing,
  prepared-candidate, and external-input-lock profiles are in
  `contracts/ports/v1/protocol-profiles.json`.
- **Conformance owner.** AD-13 owns deterministic compilation, exact-input
  idempotency, private rerender, authority/approval freshness, signing/isolation,
  prepared-candidate, no-desired-write, and generic migration-adapter fixtures.
  Run `make verify-downstream-ports`; the task-specific suite is
  `downstream.private-compiler.v1` in
  `contracts/ports/v1/conformance-cases.json`. Execute the suite's exact harness
  steps and closed oracles from `contracts/ports/v1/conformance-plan.json`;
  schema-valid structural fixtures alone are not semantic implementation goldens.
- **Boundary.** The compiler may customize every functional Agent Spec property
  and add, replace, or remove arbitrary regular files and skills, but cannot
  alter identity, grants, credentials, trust, approval, workload identity, or
  mandatory security controls. It never executes delivered content or writes
  desired state, and consumer-specific migration details remain in AD-16/17.

### Exact private-compilation input lock

`contracts/schemas/v1/private-compilation-input.schema.json` is the sole
authoritative shape for a private compiler input lock. Its contract is
`bytedesk.private-compilation-input/1`; the root and every nested object are
closed. The root contains exactly `contract`, `schema`, `inputs`, and
`compilationInputDigest`. `inputs` contains exactly:

- `consumerId`, `subjectId`, `installationId`, `harnessId`, and `targetId`;
- the exact candidate artifact descriptor, desired revision and digest, exact
  predecessor, runtime slot ID/generation, activation mode, and Coordinator-
  assigned `reproducibleEpoch`;
- the exact verified public artifact descriptor, binding artifact descriptor,
  and canonical customization digest;
- `effectiveSkillSet`, containing the exact public and private skill descriptor
  arrays and their `bytedesk.renderer-effective-skill-set/1` digest;
- `skillApprovals`, containing one `{skill, approval}` exact-descriptor pair
  for every effective skill;
- the exact signed compile-authority snapshot descriptor and its separately
  signed `authorizedPrivateInputDigest`;
- the exact signed offline contract-bundle descriptor;
- the complete renderer selection and `rendererSelectionDigest`. The selection
  is the exact closed `bytedesk.renderer-selection/1` object: harness
  ID/version, renderer ID/version, signed renderer-release descriptor, selected
  platform, exact executable-distribution descriptor, product-distribution and
  compiled-allowlist digests, the closed five-schema map, worker-profile
  digest, normalization profile, and its own `selectionDigest`; and
- all current consumer policy/security-control subdigests: policy, grant set,
  credential set, workload identity, lifecycle, mandatory sandbox, network,
  approval policy, and target binding.

The public and private skill arrays are each unique and strictly increasing by
`(repository UTF-8 bytes, digest)`. `skillApprovals` is unique and strictly
increasing by the same key on `skill`; the union of its `skill` descriptors
equals the effective public/private skill union exactly once, and its approval
descriptors are unique. JSON Schema enforces closed shapes and exact descriptor
types; the compiler enforces cross-item ordering, key uniqueness, set equality,
and digest equality procedurally. A duplicate skill key with a different
approval and an otherwise valid reordered approval array therefore both fail
before any render, publication, or idempotency record is committed.

The effective-skill-set and renderer-selection digests are lowercase
`sha256:` digests over these exact RFC 8785 JCS preimages:

Angle-bracket tokens in the preimage notation below mean the named exact JSON
value; they are notation, not literal JSON strings or omitted data.

```text
{"profile":"bytedesk.renderer-effective-skill-set/1","publicSkills":<effectiveSkillSet.publicSkills>,"privateSkills":<effectiveSkillSet.privateSkills>}
```

```text
{"profile":"bytedesk.renderer-selection-digest/1","targetHarness":...,"targetHarnessVersion":...,"rendererId":...,"rendererVersion":...,"rendererRelease":...,"targetPlatform":...,"executableDistribution":...,"productDistributionDigest":...,"compiledAllowlistDigest":...,"rendererSchemas":...,"workerProfileDigest":...,"normalizationProfile":...}
```

`authorizedPrivateInputDigest` deliberately does not include authority evidence
that contains that digest. Its preimage binds the lock contract, its exact
schema descriptor, and the complete `inputs` object after removing only
`authoritySnapshot` and `authorizedPrivateInputDigest`:

```text
{"profile":"bytedesk.authorized-private-compilation-input/1","contract":<lock.contract>,"schema":<lock.schema>,"inputs":<inputs-with-only-authoritySnapshot-and-authorizedPrivateInputDigest-removed>}
```

The resolved closed `bytedesk.consumer-authority/1` snapshot must have
`operation: compile`, a permitted decision, and carry that exact consumer-signed
digest; the field is schema-required for compile and forbidden for activate or
recover. It must also match every explicit identity, candidate, revision,
predecessor, policy, and security-control field. `verify-private-authority`
returns a success result only after matching the caller's independently computed
expected digest to that signed field; a denied decision is `authority_denied`
and returns no authorized digest. The compiler then authenticates the snapshot
descriptor and computes the final lock digest over the complete evidence-bound
input:

```text
{"profile":"bytedesk.private-compilation-input-digest/1","contract":<lock.contract>,"schema":<lock.schema>,"inputs":<lock.inputs>}
```

`compilationInputDigest` is SHA-256 over those JCS bytes. It does not include
itself, authored YAML bytes, an input subset, or a host serialization. Schema
descriptor equality, all four digest invariants, descriptor resolution,
authority freshness, approval freshness/revocation, ordering, and cross-object
identity equality are checked before work begins.

The compile command carries the complete lock, a caller-chosen
`idempotencyKey`, and caller-computed `compileRequestDigest`. That digest is not
part of its own preimage. Its canonical request identity is:

```text
{"profile":"bytedesk.private-compilation-request/1","consumerId":<inputs.consumerId>,"idempotencyKey":<idempotencyKey>,"compilationInputDigest":<lock.compilationInputDigest>}
```

The compiler independently recomputes `sha256(JCS(<that object>))`, rejects an
omitted or mismatched caller value, echoes the exact digest in every accepted
result, and atomically binds `(consumerId, idempotencyKey)` to both it and
`compilationInputDigest`. An identical replay returns the original immutable
lock, deployment, and compilation-evidence descriptors without repeating
rendering, signing, or publication. Reusing the key with a different lock or request digest returns
`idempotency_collision` with no side effect. After an uncertain response,
`resolve-compile-attempt` uses `(consumerId, idempotencyKey,
compileRequestDigest)`; `not-seen` may be retried with the exact same lock,
`committed` returns all three exact descriptors as one all-or-none closed
artifact set. `denied` or `indeterminate` returns no artifacts and a closed
problem; `not-seen` returns neither artifacts nor a problem. No resolution
causes a second request under a different input identity.

### Acyclic private output proof

The private compiler commits an acyclic graph. `L` is the exact canonical
`bytedesk.private-compilation-input/1` object. Its role-constrained descriptor
uses `application/vnd.bytedesk.agent.private-compilation-input.v1+json` and
`consumer-compilation-input-v1`. The consumer deployment `D` binds that
descriptor and `L.compilationInputDigest`, the locked
`rendererSelectionDigest`, and the complete closed renderer-attempt authority,
attempt-authentication evidence, execution receipt, and execution-
authentication evidence objects. It also embeds the private render manifest,
its canonical JCS digest, and the exact payload descriptor. Every repeated
identity and selected/actual distribution is compared byte-for-byte after
offline resolution.

The payload digest is the digest of payload bytes only. The payload is built
from the manifest's ordered `files` inventory before the manifest exists and
excludes the render manifest, compatibility or authentication envelopes, `D`,
private-compilation evidence, and any enclosing OCI config or manifest. The
payload descriptor digest, media type, and size equal `manifest.output`.
Self-inventory and delivery-metadata paths fail before publication.

The canonical artifact descriptor of all of `D` is the sole deployment
identity. There is no `deploymentSubdigest`; a second digest with a different
preimage would create ambiguous authority. `D` is closed and cannot contain a
compilation-evidence or runtime-release backlink.

`D.deploymentId` is deterministic rather than a wall-clock or random compiler
output. It is `deployment-` plus the lowercase hexadecimal SHA-256 of this JCS
preimage:

```text
{"profile":"bytedesk.consumer-deployment-id/1","consumerId":<L.inputs.consumerId>,"subjectId":<L.inputs.subjectId>,"targetId":<L.inputs.targetId>,"candidateDigest":<L.inputs.candidate.digest>,"desiredRevisionDigest":<L.inputs.desiredRevision.digest>,"compilationInputDigest":<L.compilationInputDigest>}
```

After `D` is committed, the compiler creates `CE`, a closed
`bytedesk.private-compilation-evidence/1` envelope. Its statement binds
the idempotency key and `compileRequestDigest`, exact `L` and `D` descriptors, `L`'s internal digest,
all renderer attempt/execution evidence digests, manifest digest, payload,
actual compiler and renderer distributions, compiler workload/profile
digests, outcome, epoch, and compilation signing policy. `statementDigest` is:

```text
sha256(JCS({"profile":"bytedesk.private-compilation-statement/1","statement":<CE.statement>}))
```

A consumer-isolated `consumer-compilation-evidence-v1` signing result signs
that statement digest and is embedded in `CE`; the exact CE descriptor then
binds the complete envelope without a self-cycle. `D` never references `CE`.
Both `CE.statement.reproducibleEpoch` and `completedAt` equal the locked
Coordinator-assigned epoch; operational wall-clock completion belongs only in
append-only telemetry. An idempotent replay therefore returns byte-identical
L, D, and CE descriptors.
The runtime release later references the exact canonical `D` descriptor and
exact `CE` descriptor as one subject entry and must equal their resolved
consumer, target, candidate, revision, predecessor, activation mode, epoch,
subject, slot, and generation. It never substitutes a parallel subdigest and is
signed under `consumer-runtime-release-v1`.

## Architecture review amendments

- The deployment contract uses each exact canonical consumer-deployment artifact descriptor as the sole per-subject deployment identity; the signed runtime-release manifest aggregates that descriptor with its separate exact private-compilation-evidence descriptor. Updating one agent does not rotate unrelated workload identities or advance unrelated receipts.
- The signed target includes the consumer-supplied durable slot allocation: subject reference, profile name, UID/GID, port, service, workspace, slot generation, and tombstone-policy digest where the harness needs them. Never derive slots from catalog or roster order.
- Cross-repository parents are explicit signed digest descriptors because OCI referrers cannot discover subjects in another repository.
- Compilation always re-resolves the consumer's current lifecycle,
  authorization-policy/grant revision, workload-identity/certificate binding,
  runtime slot, and approval verdict. Forward recovery cannot reuse stale
  authority from an old artifact.
- Package extraction and build enforce count, size, depth, mode, path, link, device, and decompression limits and never execute packaged scripts, binaries, hooks, or dependencies.
- The runtime-release manifest defines whether a system-package change is target-wide while ordinary agent changes remain subject-scoped.
