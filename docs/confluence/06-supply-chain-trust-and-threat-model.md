# Supply-chain trust and threat model

## Security objective

Agent Delivery must prove that the intended, reviewed content reached the
intended runtime without letting portable content acquire consumer authority.
The design assumes source packages, public registries, networks, and runtime
inputs may be hostile. Trust comes from independently configured policy,
workload identity, exact digests, signatures, attestations, and consumer-owned
authorization.

Normative signer and verifier requirements are in
[Trust policy v1](../standards/trust-policy-v1.md).

## Assets to protect

- integrity and provenance of definitions, renders, deployments, and releases;
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
3. Build workload identity to signing KMS.
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

At least three artifact purposes use separate signing roles:

1. public marketplace source and catalog publication;
2. public harness render publication; and
3. private consumer deployment and runtime release authority.

Consumer login, workload tokens, business messages, and MCP authorization use
the consumer's separate identity and policy systems. Artifact keys must not be
reused for those purposes.

Each signer policy identifies the KMS algorithm and immutable key version, the
allowed workload identity, repository/workflow/environment claims, allowed
artifact repository and media types, current and next key set, rotation
ceremony, revocation path, and fail-closed behavior.

Private keys are non-exportable. They are not committed, stored in ordinary
secret managers, written to hosts, or exposed to agents. CI authenticates to
KMS through short-lived workload federation or an equivalent platform
identity.

## Attestations

In-toto-style provenance records, as appropriate to the artifact, include:

- source repository and immutable commit;
- Agent Spec version and validator identity;
- builder workload, workflow, and isolated build environment;
- renderer version and implementation digest;
- normalized inputs and upstream artifact descriptors;
- tests, scans, compatibility, and evaluation results;
- consumer binding, policy, grant, profile, and target subdigests;
- approval identity and policy result; and
- output repository, media type, and digest.

Private tenant identifiers and policy evidence remain in private repositories.
They are not sent to a public transparency service without a separate privacy
decision.

## Package-content defenses

Source and render processing treats every file as untrusted data:

- no scripts, hooks, binaries, macros, or package-directed remote fetches run;
- absolute paths, traversal, links, devices, FIFOs, sockets, and unsafe modes
  are rejected;
- file count, path depth, individual size, total expanded size, compression
  ratio, and processing time are bounded;
- declared media types are checked against content;
- secrets, malware indicators, and license policy are scanned; and
- rendering occurs without ambient credentials and with network access denied.

Optional skill content receives separate scanning and approval. A definition
can remain usable while an unapproved skill is omitted.

## Threats and controls

| Threat | Primary controls |
|---|---|
| Mutable tag or channel substitution | Digest-only approval and activation; signed catalog for discovery |
| Source copied or replaced in a tenant binding | Exact upstream descriptor; reconstructed base; binding schema forbids copied base |
| Package requests MCP or provider authority | Strict non-authority validator; consumer performs independent mapping and call-time authorization |
| Malicious renderer plugin | Compile-time allowlist; pinned implementation digest; no runtime-loaded plugins |
| Renderer drops behavior silently | Structured compatibility matrix; lossy/unsupported gates |
| Archive traversal or bomb | Path/link/device rejection plus expansion limits and confined workspace |
| CI credential theft | Short-lived workload identity and non-exportable KMS keys |
| Artifact-supplied trust root | Independent verifier trust policy; unknown signers fail closed |
| Cross-repository referrer confusion | Explicit signed upstream descriptors and independent verification per repository |
| Cross-tenant private artifact use | Repository scope plus consumer, tenant, profile, runtime, and slot binding |
| Stale policy restored by rollback | New forward compile from current consumer authority |
| Host promotes arbitrary content | Engine-scoped desired-state read and observation write only; no promotion permission |
| Slot reuse transfers files or credentials | Durable allocation, tombstones, audited purge/reset before any reuse |
| Registry or KMS outage causes fail-open | Existing verified active state may continue; all new changes fail closed |
| Compromised signer remains trusted | Purpose-specific revocation, current/next rotation, incident withdrawal, audit |
| Receipt alteration | Append-only records, signed digest lineage, immutable correlation IDs |

## Consumer authority isolation

Identity, organizational roles, workload principals, MCP servers, tools,
resources, grants, provider connections, credentials, and call-time decisions
are consumer-owned. Agent Delivery may bind a deployment to their current
digests and identifiers, but it does not define their semantics or issue their
tokens.

The deployment compiler receives a minimal signed projection from the consumer.
It does not query another consumer's state or copy reusable credentials into an
OCI layer. At activation and token issuance, the consumer can re-check that the
deployment subdigest and runtime release remain current.

## Host identity

The host reconciler uses a certificate-bound or equivalent short-lived identity
scoped to one consumer and runtime. It can read desired state and append
observations for that runtime. It cannot impersonate a human, invoke agent MCP
tools, change grants, select another tenant, or promote a release.

Registry pull credentials are independently scoped and rotated. A leaked host
credential cannot sign a deployment or read unrelated private repositories.

## Key rotation and compromise response

Normal rotation publishes a trust policy with `current` and `next` keys,
validates dual-verification, changes the signer, observes new artifacts, and
then retires the old key. Emergency revocation skips normal overlap and blocks
new verification immediately.

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

## Required negative proofs

Release certification includes tampered layers, wrong subject, missing
attestation, unknown or revoked signer, wrong workflow claims, media-type
confusion, downgrade, source substitution, cross-tenant reuse, archive attacks,
stale consumer policy, wrong runtime/slot, and ungranted MCP invocation. Each
must produce a stable denial reason and no partial activation.

## Related pages

- [OCI artifact graph](05-oci-artifact-graph.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
