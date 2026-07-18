# Security and trust

## Security objective

Only exact reviewed public source, canonical private functional customization,
approved public/private skills, a current trusted renderer release, current
consumer authority, a Coordinator-published desired revision, fresh canary
evidence, and the intended target may become active. No package, customization,
signer, observation, host, or historical receipt can grant itself authority.

The production reference controls that realize this objective are fixed by
[ADR-0002](adr/0002-implementation-stack-and-reference-topology.md): distinct
least-privilege workload identities, purpose-separated KMS credentials and
contract-release Sigstore keyless identity, PostgreSQL transaction/CAS
authority, default-deny Kubernetes policy, fresh gVisor renderer sandboxes,
closed configuration, redacted OpenTelemetry, and fenced backup/restore.
Conforming alternative Adapters may change vendors, not the controls or denial
evidence.

## Schema and trust roots

Every Agent Delivery-owned authoritative object is validated by its exact JSON
Schema Draft 2020-12 ID/digest from an independently trusted, signed, offline
contract bundle. Unknown schema, remote reference, field, operation, extension,
or closed-enum value fails. Generated models, OpenAPI, AsyncAPI, examples, and
prose cannot override the schema.

Trust policy is also independently configured. It pins exact policy and schema
digests, algorithms, and credential-aware signer identity. KMS uses immutable
`keyVersion` plus `publicKeyDigest`; Sigstore keyless uses exact
`signerIdentityDigest` plus an independently pinned `trustedRootDigest` and
forbids `keyVersion` or a static leaf `publicKeyDigest`. Policy also pins
workload identities, repository/workflow/environment/builder claims, media
types, evidence, freshness, withdrawal, and revocation. An artifact cannot
supply or change its validator, policy, or trust roots.

KMS private keys are non-exportable KMS/HSM keys used through short-lived
WIF/OIDC. Sigstore keyless leaf keys are ephemeral under the independently
pinned trust root. Private material never enters repository/CI secrets, product
secret stores, artifacts, runtime hosts, or workspaces.

### Contract-bundle release trust

Candidate source and every candidate artifact remain untrusted even when they
come from a protected tag. The contract release caller may execute tag code to
test and build a deterministic candidate, but that job has no OIDC or signing
authority. It delegates signing only through an exact-commit reusable-workflow
reference. The called signer has the protected environment and OIDC authority,
does not check out the repository, and never executes a candidate file. It
fetches bounded exact-commit metadata through its own read-only SCM identity,
validates the precise token-free codeload redirect, and retains the source
snapshot without extracting it on the host.

Before and after signing, a protected exact-digest verifier image evaluates the
candidate in a network-disabled, read-only, non-root, capability-dropped,
resource-bounded container. Before extraction it checks the SCM commit metadata
and bounded archive profile; safe extraction rejects non-portable/colliding
paths, links, special files, and member/expanded-size excess. The tool
reconstructs the Git tree object, matches it to the SCM tree, rebuilds with its
trusted implementation, and requires exact candidate bundle/manifest bytes. It
then reconstructs the complete normalized build input; verifies deterministic
archive bytes, portable paths, inventory, JCS
roles, offline schema registry, fixtures, lifecycle and operation semantics,
OpenAPI/AsyncAPI/event closure, trust policy, source claims, and evidence; and
emits the canonical request and final evidence. The release identity is the
exact called-workflow commit. Independent policy additionally pins caller
repository, immutable tag, source commit, workflow trigger, OIDC issuer,
trusted-root digest, sealed-verifier digest, and Cosign digest.
The keyless request has no KMS key version: it signs the exact policy-signer,
sealed-builder, and pre-sign-certification digests. Final evidence may claim
builder execution only after resolving that certification and matching its
executed distribution to the independently pinned sealed image.

The bundle is accepted only under the exact `contract-bundle-release-v1`
policy. That policy is keyless-only and scopes only the contract-bundle
repository and media type. The KMS-only `product-release-v1` policy separately
authorizes product distributions, compiled allowlists, and renderer releases.
A mixed policy, cross-purpose signer, or cross-scoped repository/media type is
denied even when its signature is otherwise cryptographically valid.

The product-release manifest must bind the exact
`contractBundleVerification` receipt produced by the trusted keyless Adapter.
The receipt authenticates evidence but has `authorityIssued: false`; product
authority comes only from the later KMS product signature over the complete
manifest. Every downstream/private acceptance path still replays the keyless
edge independently from the exact bundle, policy, request, Sigstore bundle,
root, certificate identity/claims, workflow, builder, and certification
bindings. Consequently, possession of the product KMS key cannot vouch for a
missing or invalid contract-bundle signature.

The repository verifier cannot issue production authority. Its external
Sigstore path is adapter-conformance evidence, and its local replay ledger is a
test-only single-host mechanism. Production uses a durable shared uniqueness
transaction for request ID, nonce, and request digest before authoritative
evidence is emitted. An unpinned reusable workflow, mutable verifier image,
missing protected value, candidate-supplied verifier, replay, identity/tool/root
substitution, authenticated SCM redirect drift, source commit/tree mismatch,
source archive denial, trusted-rebuild difference, or absent post-sign
certification fails closed.

## Purpose separation and consumer sovereignty

V1 uses the 22 closed wire purposes in
[Trust policy v1](../standards/trust-policy-v1.md). They separate product,
contract-bundle release, source, public render, consumer-private skill,
consumer authority, deployment, runtime release, qualification
policy/attempt/receipt/evidence/decision,
release status/status head, public and consumer-private stage-specific status
eligibility, renderer attempt/execution, private-compilation input/evidence,
and consumer activation authorization. Every consumer-private purpose is
isolated per consumer.
Authority/approval and deployment/compiler keys are different so a compiler
cannot approve itself. A shared provider key for multiple consumers, exported
CI key, provider-controlled
mutable private trust root, or runtime-held private key is forbidden.

The preferred private keys remain in the consumer's cloud/security boundary.
Agent Delivery build/compiler/publication workloads may receive narrow sign
permission only for their exact per-consumer private-artifact or compilation
purpose and cannot administer, export, rotate, or change policy. They never receive
`consumer-authority-v1` sign permission; only the independently authenticated
Consumer Authority Adapter can issue authority/approval evidence. A managed
KMS/HSM key must be tenant-dedicated, explicitly accepted and pinned by the
consumer, independently revocable, auditable, and migratable to a consumer-
owned key without rewriting history.

Supplier signatures prove private-skill provenance only. The unchanged digest
still requires the consumer-isolated `consumer-private-skill-v1` publication
signature, and each exact effective skill separately requires current consumer-
issued approval evidence.

## Renderer trust and execution

A renderer is trusted product code identified primarily by a signed renderer-
release manifest digest. The identity also binds harness/renderer/contract
versions, actual worker or product distribution/platform digest, embedded
allowlist, renderer-owned schemas, source/build/toolchain/dependencies,
normalization, SBOM, vulnerability/license, deterministic-output, and
in-toto/SLSA Build Level 3 evidence.

The compiled allowlist maps each harness/renderer/version tuple to exactly one
release manifest. Independent policy may restrict but no runtime configuration,
binding, catalog, skill, event, artifact, or customization may expand or
redirect it. Rendering never falls back to a tag, PATH executable, local build,
other installed version, or artifact-provided plugin.
Conflicting duplicate harness/renderer/version entries fail the compiled
allowlist, and conflicting duplicate OS/architecture entries fail a release
manifest, so executable selection can never depend on array order.

Signature trust does not establish release eligibility. The exact product and
renderer releases must pass the pinned qualification policy, suite, and full
role/subject/platform matrix. Immediately before selection or execution, the
caller verifies fresh nonce-bound authenticated current status heads and any
required append-only consistency proof. The attempt binds those accepted
checkpoint/evidence digests. Qualification and status are specified by
[Release qualification and status v1](../standards/release-qualification-v1.md).

Each render runs in a fresh sandbox with no network, secrets, cloud metadata,
signing keys, ambient identity, home directory, package manager, or developer
configuration; read-only product roots; a task-only workspace; dropped
privilege; resource/process/syscall/time limits; declared inputs; and bounded
output collection. Renderer code may execute. Agent, skill, archive, and
customization content never does.

A withdrawn renderer blocks new render and compile. A revoked renderer/product
distribution blocks new activation. Historical retention permits verification,
not execution. Forward recovery requires current trusted tooling and a new
public-render lineage.

## Untrusted inputs and archive safety

The following are always untrusted:

- Agent Spec, catalog, source, binding, operation, and metadata objects;
- authored JSON/YAML before parser and schema validation;
- public/private skills and every nested file/archive;
- OCI manifests, layers, annotations, referrers, and cross-repository claims;
- webhook, Git, API, and notification-event input;
- opaque secret references and consumer-supplied functional instructions;
- renderer output before deterministic validation and signing; and
- observations, canary evidence, recovery proposals, and receipts before exact
  actor, nonce, target, revision, policy, and freshness validation.

Parsing and extraction are non-executing and resource-bounded. They reject
duplicate YAML keys, aliases, tags, non-string keys, non-finite/non-JSON values,
unknown schema fields, absolute/traversal/non-NFC/colliding paths, links,
devices, FIFOs, sockets, unsafe modes, file/depth/size/ratio excess, archive
bombs, undeclared media types, secret values, and execution requests. Declared
ordinary executable modes are allowed for regular skill files; setuid, setgid,
sticky, ownership, and device metadata are not.

Operational defaults cap authoritative JSON at 4 MiB and 100,000 JSON-model
nodes. Every schema collection declares `maxItems`; a collection without a
stricter domain limit uses 100,000 as its portable outer ceiling and remains
subject to the complete object's lower effective node and byte ceilings.
Functional operations are capped at 10,000, one source/skill at 10,000 files,
a deployment at 50,000 files and 10 GiB expanded, path depth/length at 32
segments/1,024 UTF-8 bytes, one file/blob at 4 GiB, archive nesting at three,
expansion ratio at 100:1, and renderer execution at ten minutes/4 GiB memory/20
GiB temporary disk. Higher limits need independent policy, capacity proof, and
risk acceptance; artifacts cannot raise them.

## Functional customization versus authority

Private customization may change every functional Agent Spec and renderer-
configuration property, including models, provider endpoints, tools, MCP,
resources, files, skills, harness behavior, and opaque secret references. It
uses closed constrained JSON Patch plus digest-preconditioned file and skill
operations against exact roots.

Customization cannot change source lineage, schema identity, renderer release,
trust, consumer/subject identity, roles, grants, credential values or state,
workload identity, target, desired state, mandatory sandbox/network/isolation,
approval policy, or business decision. Configuring a capability is not
authorization to use it.

## Consumer authority and skill approval

The consumer supplies a signed, short-lived `bytedesk.consumer-authority/1`
snapshot binding operation, consumer, subject, installation, target, candidate,
desired revision, predecessor, nonce, audience, time window, and opaque current
policy/grant/credential/workload-identity/lifecycle/sandbox/network/approval
digests. Compilation requires a current snapshot. Activation and recovery need a
newly verified snapshot no more than five minutes old; v1 maximum lifetime is
fifteen minutes.

Each skill approval binds exact descriptor/package, consumer, subject,
installation, target class, use scope, risk/evaluation/policy, approver,
validity, revocation, and replacement. Any digest, scope, target, policy, or time
change invalidates it. Call-time authorization remains mandatory after
activation.

## Sole desired-state writer and canary actors

There is one `TargetDeliveryState` and one selected `DesiredStateStore` per
consumer/runtime target. The Promotion Coordinator is its sole logical writer
and advances it by the exact absent-or-match revision/digest precondition. Git,
bots, operators, compilers, hosts, observations, capability verifiers, consumer
applications, and recovery planners cannot write desired state. Live dual write
between managed and consumer-native stores is forbidden.

The Host Reconciler has target-scoped desired-read and observation-append
permissions only. It stages without executing package files, performs technical
preflight and harness-safe switching, and reports artifact/file/process/
resource/readback evidence. It has no human, agent, MCP, tool, provider,
capability-probe, promotion, or desired-write authority.

The separately consumer-owned Capability Verifier uses the candidate's normal
short-lived workload identity and authorization path. It proves workload login,
one permitted capability, and one sentinel capability denied with the exact
expected policy class. Timeout, network failure, `404`, parser error, missing
endpoint, or unavailable tool is not denial proof. Neither actor can promote.

Each capability decision resolves an exact
`bytedesk.authorization-decision-proof/1` issued by the independently expected
consumer authorization signer. The closed proof binds the plan and nonce,
consumer/subject/target, release/deployment, capability, current policy/grants/
workload identity, exact decision class/code, signer policy, freshness, and an
authenticated completed and parsed successful transport response. Agent
Delivery validates and records that consumer evidence; the proof never grants
the capability and never becomes package authority.

Authentication results are not represented as bare digest allowlists. For
canary evidence and authorization proofs, the trusted verifier supplies a
digest-keyed record containing the actually verified signer identity, exact
signer policy, verification-evidence digest, and verified signature or
authenticated non-repudiable channel result. Promotion compares that record to
both the independently configured signer and the signed document claim. A
correct document authenticated by the wrong identity or policy fails closed.

All canary evidence binds the Coordinator's signed plan, rollout, nonce,
candidate, desired revision, authority/policy, consumer, subject, target,
slot/generation, expected/actual result classes, actor implementation, time, and
expiry. Stale, late, replayed, wrong-target, or superseded evidence is retained
but cannot promote.

## Verification algorithm

For new import, compilation, desired-state publication, activation, or
recovery, the verifier:

1. resolves exact repository/digest/media-type/size and policy ID/digest;
2. validates the independently trusted offline schema and RFC 8785 identity;
3. verifies signature purpose, per-consumer isolation, and credential-aware
   signer identity: immutable `keyVersion` plus `publicKeyDigest` for KMS, or
   exact `signerIdentityDigest` plus independently pinned `trustedRootDigest`
   and no static leaf or `keyVersion` for Sigstore keyless; it then verifies
   workload claims, effective window, withdrawal, and revocation;
4. verifies the pinned qualification policy/suite, complete typed evidence
   matrix, signed final decision, and fresh nonce/time-bound current status
   heads;
5. verifies required provenance, SBOM, compatibility, evaluation, authority,
   skill approval, canary, and readiness evidence;
6. recursively traverses every explicit upstream descriptor and OCI
   manifest/config/layer/blob independently;
7. confirms source/binding/customization/skill/renderer/execution/file digests,
   consumer, subject, installation, target, slot/generation, candidate, desired
   revision, precondition, nonce, and freshness;
8. rejects any missing, stale, downgraded, cross-consumer, or substituted edge;
   and
9. records the exact graph in append-only evidence.

Only the Promotion Coordinator may convert successful verification and fresh
evidence into a new desired-state revision.

## Forward recovery

Historical known-good content is a selection candidate, not current authority.
Recovery searches prior promoted functional content newest first and requires
available, non-withdrawn source/customization/file/skill descriptors, current
skill approvals, schemas, target compatibility, current trusted renderer/
compiler tooling, current consumer authority, full evaluation, and fresh canary.

Recovery produces a new deployment, release, desired revision, signatures, and
evidence. It records current predecessor, failed rollout, historical
`recoverySource`, current-tooling substitution, and eligibility. It never
reactivates an old deployment, render bundle, desired record, receipt,
signature, authority snapshot, credential state, or revoked renderer. If no
candidate qualifies, the target enters `operator_required`; incident policy may
continue an already active verified release but cannot newly activate prohibited
content.

## Threats and mandatory denial tests

| Threat | Required control |
|---|---|
| Mutable source, policy, schema, renderer, or tag substitution | Exact independently trusted digests; no network or tag fallback |
| Parser/schema differential or unknown field | Restricted YAML, Draft 2020-12 bundle, two-validator fixtures, closed authority objects |
| Cross-repository referrer confusion | Complete signed downstream descriptors and independent traversal |
| Partial/cyclic OCI graph or repository-prefix type confusion | Recursive exact config/layer/blob closure, closed media/role mapping, resource bounds, and cycle denial |
| Signed but unqualified renderer or platform omission | Pinned qualification policy/suite, typed evidence matrix, signed decision, and all renderer/platform coverage |
| Stale, rolled-back, or forked release status | Caller nonce/time-bound authenticated status head and exact append-only consistency proof |
| Renderer/plugin/PATH/library injection | Compiled allowlist, exact worker readback, sandbox, no runtime plugins |
| Input code executes during delivery | Non-executing parser/extractor/compiler/reconciler and execution-spy tests |
| Tool configuration is mistaken for a grant | Functional roots separated from signed current consumer authority and call-time authorization |
| Publisher signature is mistaken for skill approval | Exact consumer-issued approval per skill digest and scope |
| Cross-consumer private signing | Separate per-consumer keys, workload identities, repositories, and trust policies |
| Stale/replayed authority | Audience/operation/candidate/revision/nonce/time binding and activation recheck |
| Desired-state split brain | One Coordinator writer, one store, exact CAS, no live dual write |
| Host or canary actor self-promotes | Separate actors/keys, challenge binding, Coordinator-only transition |
| False denial passes canary | Require exact policy-denial class; transport/absence errors fail |
| Recovery restores revoked authority/tooling | Current-tooling rebuild, current authority/approval/evaluation/canary, new revision |
| Archive escape or resource exhaustion | Portable path/type/mode rules and cumulative hard limits |
| Registry/KMS/control-plane outage | Active verified release may continue; new work fails closed |

## Incident and readiness behavior

A withdrawn/compromised content digest cannot be newly imported or activated.
A revoked signer, schema, renderer, builder, or policy fails new verification.
No incident path authorizes unsigned hotfixes, shared private keys, mutable tags,
CAS bypass, old authority, or skipped canary.

GA requires measured operational evidence, including thirty production-
equivalent days meeting SLOs, capacity/soak/chaos results, zero unresolved
critical/high findings, backup/restore/failover, N-1 upgrade and event replay,
complete audit/redaction, runbooks/on-call, quarterly key and incident drills,
and a signed readiness report. Accepted architecture is not proof these gates
already pass.

See [Trust policy v1](../standards/trust-policy-v1.md),
[Consumer authority and private signing v1](../standards/consumer-authority-v1.md),
[Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md), and
[Operational readiness v1](../standards/operational-readiness-v1.md).
