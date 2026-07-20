# Supply-chain trust and threat model

## Security objective

Agent Delivery must prove that the intended, reviewed content reached the
intended runtime without letting public content or private functional
customization acquire consumer authority. A private binding may describe tools,
MCP/provider/model/harness configuration, opaque secret references, file deltas,
and public or private skills; none is proof of a grant, credential, or execution
right. The design assumes source packages, bindings, skills, public registries,
networks, and runtime inputs may be hostile. Trust comes from independently
configured policy, workload identity, exact digests, signatures, attestations,
and consumer-owned authorization.

Normative signer and verifier requirements are in
[Trust policy v1](../standards/trust-policy-v1.md).
Authority snapshots, approvals, policies, manifests, attestations, desired
state, and receipts use closed Draft 2020-12 schemas from the signed contract
bundle; an unknown field, schema digest, or runtime-fetched schema fails closed.

The concrete production controls are fixed by
[ADR-0002](../architecture/adr/0002-implementation-stack-and-reference-topology.md):
purpose- and consumer-separated KMS credentials, a separate contract-release
Sigstore keyless identity, distinct workload identities and database roles, a
compiled renderer allowlist, fresh gVisor sandboxes with no network or
credentials, PostgreSQL transaction/CAS authority, and append-only evidence.
Vendor-substitute Adapters must pass the same negative, isolation, outage,
rotation, and recovery evidence.

## Assets to protect

- integrity and provenance of definitions, tenant-free public renders, private
  customization, embedded effective renders, deployments, and releases;
- consumer and tenant isolation;
- signing and workload identities;
- current identity, role, grant, policy, and credential decisions;
- runtime slot ownership and active files;
- deployment receipt completeness;
- private consumer metadata and evaluation evidence; and
- the ability to recover a known-good release without restoring revoked
  authority.

## Trust boundaries

1. Contributor workstation to source control.
2. Source control to isolated publication build.
3. Build or signer workload identity to purpose-specific KMS or Sigstore trust.
4. Publisher to public registry.
5. Public registry to consumer import and private compilation.
6. Consumer policy systems to deployment compiler.
7. Control plane to private registry and desired-state API.
8. Desired state to engine-scoped host reconciler.
9. Staged filesystem to runtime process.
10. Runtime request to consumer-owned MCP and provider authorization.

Each boundary is authenticated independently. Passing one boundary does not
grant access at the next.

## Signer separation

Production uses six organizational ownership domains implemented as 22
closed signing purposes:

1. product/publication: `product-release-v1`,
   `contract-bundle-release-v1`, `public-source-v1`, and `public-render-v1`;
2. consumer-private: `consumer-private-skill-v1`, `consumer-authority-v1`,
   `consumer-deployment-v1`, `consumer-runtime-release-v1`,
   `consumer-release-status-eligibility-v1`, and
   `consumer-activation-authorization-v1`;
3. qualification: `release-qualification-policy-v1`,
   `release-qualification-attempt-v1`,
   `release-qualification-receipt-v1`,
   `release-qualification-evidence-v1`, and
   `release-qualification-decision-v1`;
4. current eligibility: `release-status-v1`,
   `release-status-head-v1`, and `release-status-eligibility-v1`;
5. renderer execution: `renderer-attempt-v1` and
   `renderer-execution-v1`; and
6. private compilation: `consumer-compilation-input-v1` and
   `consumer-compilation-evidence-v1`.

Consumer-private purposes are isolated per consumer, and authority/approval uses a
different key and workload identity from deployment signing. The preferred
private key is a non-exportable KMS key in the consumer's security boundary. An
explicitly opted-in managed profile may use a tenant-dedicated KMS/HSM key, but
a shared cross-consumer private signer or provider-controlled trust root is
forbidden.

Agent Delivery build/compiler/publication workloads may invoke only the narrow
private-artifact or compilation sign operation assigned to their workload; the
Consumer Authority Adapter alone invokes `consumer-authority-v1`. An independent
supplier signature is upstream provenance only. The unchanged private-skill
digest still needs the consumer-isolated `consumer-private-skill-v1`
publication signature and separate current `consumer-authority-v1` approval.

Consumer login, workload tokens, business messages, and MCP authorization use
the consumer's separate identity and policy systems. Artifact keys must not be
reused for those purposes.

Each signer policy is an immutable canonical object identified by stable ID,
logical version, schema digest, policy digest, and effective window. It
identifies the credential kind and algorithm. KMS signers use immutable
`keyVersion` plus `publicKeyDigest`. Sigstore keyless signers use exact
`signerIdentityDigest` plus an independently pinned `trustedRootDigest` and
forbid `keyVersion` and a static leaf `publicKeyDigest`. Policy also identifies
the allowed workload identity, repository/workflow/environment claims, allowed
artifact repository and media types, current and next trust set, rotation
ceremony, revocation path, and fail-closed behavior.

The `product-release-v1` policy is KMS-only and accepts product distributions,
compiled allowlists, and renderer releases. The distinct
`contract-bundle-release-v1` policy is Sigstore-keyless-only and accepts only
the exact contract-bundle repository and media type. Mixing the two purposes,
credential kinds, signer sets, repositories, or media types in either policy
is a fail-closed configuration error.

KMS private keys are non-exportable and are not committed, stored in ordinary
secret managers, written to hosts, or exposed to agents. Sigstore leaf keys are
ephemeral and never persisted. CI and signer workloads authenticate through
short-lived workload federation to the exact KMS or keyless purpose.

## Attestations

In-toto-style provenance records, as appropriate to the artifact, include:

- source repository and immutable commit;
- Agent Spec version and validator identity;
- builder workload, workflow, and isolated build environment;
- renderer-release manifest, actual executed product distribution/worker,
  platform, embedded allowlist, and renderer-owned schema digests;
- normalized public inputs, binding customization, file operations, selected
  public/private skills, embedded effective render, and upstream descriptors;
- tests, scans, compatibility, and evaluation results;
- signed consumer-authority snapshot, policy, grant, profile, and target
  subdigests;
- every signed exact-skill approval plus approval identity/policy digest; and
- output repository, media type, and digest.

Private tenant identifiers and policy evidence remain in private repositories.
They are not sent to a public transparency service without a separate privacy
decision.

## Release qualification and current status

A valid product/renderer signature is necessary but not sufficient. The product
release pins one exact qualification policy, suite, and minimum coverage
digest. Qualification produces purpose-signed attempts, receipts, typed
evidence leaves and predicates, an evidence tree, and a final decision for every
required renderer release and executable platform. Predicate schemas resolve
offline by exact descriptor; a compatible substitute schema cannot reinterpret
evidence.

Current eligibility is a separate append-only signed status chain. Each
selection or execution supplies a fresh caller nonce and operation time and
verifies an authenticated status-head checkpoint. Advancement requires an
exact consistency proof from the caller's accepted subject/sequence/epoch/head/
root to the returned state. Wrong nonce, expiry, future time, rollback, fork,
withdrawal, revocation, or end of support fails closed. The exact contract is
[Release qualification and status v1](../standards/release-qualification-v1.md).

## Package-content defenses

Source, customization, skill, and render processing treats every file as
untrusted data:

- declared structured contract-authoring input is parsed only as JSON or the
  YAML 1.2 JSON-compatible subset; duplicate YAML keys, aliases, custom tags,
  non-string mapping keys, and non-finite numbers fail closed;
- signing and structured-object digests use RFC 8785 canonical JSON bytes,
  while arbitrary payload files, including `.yaml` and `.json` files, use their
  exact raw bytes and are not contract-parsed by extension;
- no scripts, binaries, macros, install commands, hooks, or package-directed
  remote fetches run in publication, rendering, or private compilation;
- absolute paths, traversal, links, devices, FIFOs, sockets, and unsafe modes
  are rejected;
- file count, path depth, individual size, total expanded size, compression
  ratio, and processing time are bounded;
- declared media types are checked against content;
- secrets, malware indicators, and license policy are scanned; and
- rendering occurs without ambient credentials and with network access denied.

Skills may contain arbitrary regular files, including scripts and binaries.
Every new or changed skill digest returns to quarantine for separate scanning,
evaluation, and signed consumer approval under an immutable policy digest. A
consumer may keep the definition usable by explicitly removing an optional
skill through the canonical binding operation before compilation; the exact
effective set is recorded. An unapproved selected skill fails closed and is
never silently dropped. A runtime may execute skill content only after verified
`bytedesk.skill-approval/1` evidence for that exact digest and under current
consumer sandbox, network, identity, and call-time authorization. Raw secrets,
embedded grants, hooks, and unsafe entries are rejected.

## Threats and controls

| Threat | Primary controls |
|---|---|
| Mutable tag or channel substitution | Complete exact descriptor plus independently configured immutable trust-policy ID/digest for approval and activation; signed tags/channels are discovery only |
| Source copied or replaced in a tenant binding | Exact upstream descriptor; reconstructed base; binding schema forbids copied base |
| YAML ambiguity or alternate serialization changes signed meaning | Restricted YAML 1.2 JSON-compatible authoring parser; ambiguous constructs rejected; RFC 8785 canonical JSON is the sole structured-object digest/signature input |
| Payload content is parsed, transcoded, or normalized under the same digest | Arbitrary payloads, including files named `.yaml` or `.json`, are opaque exact bytes; file extensions do not invoke contract parsing and any byte change changes identity |
| Private functional config claims MCP/tool/provider authority | Content is treated only as desired configuration; consumer independently maps, grants, resolves opaque references, and authorizes every call |
| Malicious renderer plugin | Compile-time allowlist; pinned implementation digest; no runtime-loaded plugins |
| Renderer name/version points to different executable bytes | Signed renderer-release manifest, embedded allowlist, and executed distribution/worker digest readback |
| Renderer drops behavior silently | Structured compatibility matrix; lossy/unsupported gates |
| Archive traversal or bomb | Path/link/device rejection plus expansion limits and confined workspace |
| Skill script/binary executes during delivery or without approval at runtime | Delivery pipeline never executes content; changed digests quarantine; runtime requires exact-digest approval, sandbox, and current authorization |
| Public render leaks tenant customization | Public endpoints reject customization/private skills/opaque references; tenant-free conformance fixtures |
| Private deployment is patched after rendering | Full effective rerender before deployment packaging; signed embedded bundle/manifest; no post-render patch path |
| CI credential theft | Short-lived workload identity, non-exportable KMS keys, ephemeral keyless leaf keys, and exact policy separation |
| Artifact-supplied trust root | Independent verifier trust policy; unknown signers fail closed |
| Cross-repository edge confusion | Explicit signed upstream descriptors and independent verification per repository; OCI `subject` is not used across repositories |
| Signed but unqualified renderer or missing platform | Product-pinned qualification policy/suite, complete typed role/subject/platform matrix, and signed decision |
| Stale, rolled-back, or forked release status | Fresh caller-nonce/time-bound authenticated head checkpoint and exact append-only consistency proof |
| Partial or cyclic OCI graph | Recursive exact manifest/config/layer/blob closure, closed media/role map, resource bounds, and cycle denial |
| Cross-tenant private artifact use | Repository scope plus consumer, tenant, profile, runtime, and slot binding |
| Stale policy restored by rollback | New forward compile from current consumer authority |
| Host promotes arbitrary content | Engine-scoped desired-state read and observation write only; no promotion permission |
| Host receives an agent capability credential for canary | Separate consumer Capability Verifier uses the normal candidate runtime/authorization path; host returns technical evidence only |
| Consumer or Git writes around rollout concurrency | Sole Promotion Coordinator writer, one DesiredStateStore, exact revision-and-digest CAS; events and Git are non-authoritative intent |
| Shared private signer crosses consumer scope | Consumer-owned or tenant-dedicated purpose keys; cross-consumer signer topology denied |
| Slot reuse transfers files or credentials | Durable allocation, tombstones, audited purge/reset before any reuse |
| Registry or KMS outage causes fail-open | Existing verified active state may continue; all new changes fail closed |
| Compromised signer remains trusted | Purpose-specific revocation, current/next rotation, incident withdrawal, audit |
| Receipt alteration | Append-only records, signed digest lineage, immutable correlation IDs |

## Consumer authority isolation

Identity, organizational roles, workload principals, grants, provider access,
credential values, execution approval, and call-time decisions are
consumer-owned. A private binding may describe desired MCP servers, tools,
resources, provider/model/harness configuration, and opaque secret references.
Agent Delivery may bind a deployment to those functional inputs and to the
consumer's independently supplied current authority digests, but it does not
grant capabilities, resolve raw secret values into artifacts, define policy
semantics, or issue tokens.

The deployment compiler receives a short-lived signed
`bytedesk.consumer-authority/1` snapshot from the consumer, bound to operation,
candidate, target, desired revision, predecessor, nonce, and immutable signer-
policy digest. It separately verifies signed `bytedesk.skill-approval/1`
evidence for every effective skill. Compilation, activation, and recovery use
fresh operation-specific snapshots; approval and deployment signing keys are
separate. The compiler does not query another consumer's state or copy reusable
credentials into an OCI layer. At activation and token issuance, the consumer
can re-check that the exact canonical deployment descriptor and runtime release remain current.

## Host identity

The host reconciler uses a certificate-bound or equivalent short-lived identity
scoped to one consumer and runtime. It can read desired state and append
observations for that runtime. It cannot impersonate a human, invoke agent MCP
tools, change grants, select another tenant, or promote a release.

Canary capability checks are performed by a distinct consumer-owned Capability
Verifier. It returns signed challenge-bound evidence for workload login, one
non-destructive permitted capability, and one known forbidden sentinel. Only an
explicit policy denial counts as the negative result; timeout, unavailable,
not-found, or transport errors do not. The Promotion Coordinator verifies that
evidence but does not make the authorization decision.

Registry pull credentials are independently scoped and rotated. A leaked host
credential cannot sign a deployment or read unrelated private repositories.

## Key rotation and compromise response

Normal rotation publishes distinct immutable `current` and `next` policy
snapshots with exact digests and an explicit overlap window, validates both,
changes the signer, observes new artifacts, and then retires the old snapshot.
Emergency revocation skips normal overlap and blocks new verification
immediately.

Compromise response distinguishes:

- key compromise;
- publisher workflow compromise;
- artifact digest compromise;
- registry access compromise;
- consumer identity/policy compromise; and
- host/runtime compromise.

Each has an explicit owner, revocation action, affected-digest query, runtime
decision, replacement compile, and evidence-preservation step.

## Availability posture

Security does not require stopping a healthy, previously verified workload for
every control-plane outage. Hosts retain the active and last-known-good verified
state. They do not import, compile, stage, or activate new content when required
registry, signer, policy, or KMS evidence is unavailable.

A confirmed malicious active digest is different from an outage. Consumer
incident policy decides whether to stop it immediately or hold it in isolation
while a replacement is produced.

Forward recovery treats known-good receipts as history, not automatic
eligibility. It excludes withdrawn or content-revoked dependencies, never
executes revoked renderer/compiler tooling, and builds a new lineage with
current trusted tooling, current signed authority, current skill approvals,
full evaluation, and canary. If no candidate qualifies, recovery fails closed.

Security-response timing, GA evidence, audit completeness, support windows, and
operational exercises are fixed by
[Operational readiness v1](../standards/operational-readiness-v1.md), including
the 15-minute target after an authorized signing-key or builder-compromise
decision to publish revocation and block new affected activation.

## Required negative proofs

Release certification includes tampered layers, wrong subject, missing
attestation, unknown or revoked signer, wrong workflow claims, media-type
confusion, downgrade, source substitution, cross-tenant reuse, public
customization leakage, unsafe file operations, raw secrets, artifact hooks,
unapproved skill execution, post-render patching, archive attacks, stale
consumer policy, wrong runtime/slot, ungranted MCP invocation, disallowed YAML
constructs, non-canonical structured contract bytes, and modified opaque payload
bytes.
Each must produce a stable denial reason and no partial activation.

## Related pages

- [OCI artifact graph](05-oci-artifact-graph.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
