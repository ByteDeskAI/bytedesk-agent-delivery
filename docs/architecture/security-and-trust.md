# Security and trust

## Security objective

Only exact reviewed public source, canonical private functional customization,
approved public/private skills, a current trusted renderer release, current
consumer authority, a Coordinator-published desired revision, fresh canary
evidence, and the intended target may become active. No package, customization,
signer, observation, host, or historical receipt can grant itself authority.

## Schema and trust roots

Every Agent Delivery-owned authoritative object is validated by its exact JSON
Schema Draft 2020-12 ID/digest from an independently trusted, signed, offline
contract bundle. Unknown schema, remote reference, field, operation, extension,
or closed-enum value fails. Generated models, OpenAPI, AsyncAPI, examples, and
prose cannot override the schema.

Trust policy is also independently configured. It pins exact policy and schema
digests, immutable KMS key versions, algorithms, workload identities,
repository/workflow/environment/builder claims, media types, evidence,
freshness, withdrawal, and revocation. An artifact cannot supply or change its
validator, policy, or trust roots.

Keys are non-exportable KMS/HSM keys used through short-lived WIF/OIDC. Private
material never enters repository/CI secrets, product secret stores, artifacts,
runtime hosts, or workspaces.

## Purpose separation and consumer sovereignty

V1 uses distinct signer purposes for product releases, public source, public
render, consumer-private skills, consumer authority/approval, and consumer
deployments. The last three are isolated per consumer. Authority/approval and
deployment keys are different so a compiler cannot approve itself. A shared
provider key for multiple consumers, exported CI key, provider-controlled
mutable private trust root, or runtime-held private key is forbidden.

The preferred private keys remain in the consumer's cloud/security boundary.
Agent Delivery build/compiler/publication workloads may receive narrow sign
permission only for the per-consumer private-skill or deployment purpose and
cannot administer, export, rotate, or change policy. They never receive
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

Operational defaults cap authoritative JSON at 4 MiB, functional operations at
10,000, one source/skill at 10,000 files, a deployment at 50,000 files and 10
GiB expanded, path depth/length at 32 segments/1,024 UTF-8 bytes, one file/blob
at 4 GiB, archive nesting at three, expansion ratio at 100:1, and renderer
execution at ten minutes/4 GiB memory/20 GiB temporary disk. Higher limits need
independent policy, capacity proof, and risk acceptance; artifacts cannot raise
them.

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
3. verifies signature purpose, per-consumer isolation, key version, workload
   claims, effective window, withdrawal, and revocation;
4. verifies required provenance, SBOM, compatibility, evaluation, authority,
   skill approval, canary, and readiness evidence;
5. traverses every explicit upstream descriptor independently;
6. confirms source/binding/customization/skill/renderer/execution/file digests,
   consumer, subject, installation, target, slot/generation, candidate, desired
   revision, precondition, nonce, and freshness;
7. rejects any missing, stale, downgraded, cross-consumer, or substituted edge;
   and
8. records the exact graph in append-only evidence.

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
