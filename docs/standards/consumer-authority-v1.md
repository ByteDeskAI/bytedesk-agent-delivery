# Consumer authority and private signing v1

**Profiles:** `bytedesk.consumer-authority/1`,
`bytedesk.skill-approval/1`, and `bytedesk.private-signing/1`

**Status:** Accepted architecture contract; concrete schemas and profile
conformance are release-blocking AD-08/AD-09 deliverables

## Purpose

Agent Delivery must bind current consumer authority to exact content without
becoming the authority for identity, roles, grants, credentials, workload
identity, security policy, or business approval. This contract defines the
signed opaque envelopes and the consumer-sovereign key topology that preserve
that boundary.

## Consumer authority snapshot

The consumer authority Adapter supplies a signed, short-lived
`bytedesk.consumer-authority/1` snapshot. The snapshot is a closed JSON Schema
object and RFC 8785 identity containing:

- stable consumer, subject, installation, harness, and runtime-target IDs;
- audience and authorized operation (`compile`, `activate`, or `recover`);
- monotonic authority revision and exact predecessor;
- policy, grant-set, credential-set, workload-identity, lifecycle, mandatory-
  sandbox, network, approval-policy, and target-binding digests;
- activation decision or exact business-approval evidence descriptor where
  required;
- signer-policy ID and digest, signer identity, issued-at, not-before,
  expires-at, and unique nonce; and
- binding, deployment candidate, and desired-revision digests to which the
  snapshot applies.

Subdocuments remain consumer-owned and opaque to Agent Delivery. Their digests
prove freshness and binding; they do not invite Agent Delivery to interpret or
grant their contents. The snapshot contains no credential values, tokens,
private keys, connection secrets, or reusable workload credentials.

Compilation requires a currently valid snapshot. Activation and recovery
require a newly verified snapshot bound to the exact candidate and desired
revision; a compilation-time snapshot cannot be assumed current. The v1 default
maximum lifetime is fifteen minutes and the activation check must be no more
than five minutes old. A consumer profile may shorten, but not lengthen, these
limits without a separately reviewed risk profile.

Concrete model/provider choice, endpoints, tool and MCP configuration, and
opaque secret references are functional customization and are already covered
by the binding/effective-render digest. Provider access, tool/MCP grants,
credential-set state, and call-time authorization remain represented only by
consumer authority digests and live consumer decisions. No duplicate provider-
selection authority subdigest is required.

## Skill approval evidence

Publishing or signing a skill does not approve runtime use. Each effective
public or private skill digest has consumer-issued
`bytedesk.skill-approval/1` evidence containing:

- exact skill descriptor and package ID;
- consumer, subject, installation, target class, and permitted use scope;
- scan, SBOM, license, evaluation, and risk-decision digests;
- approval-policy ID and digest;
- approver class and authenticated decision reference;
- issuance, expiry, revocation, and replacement data; and
- signature under the consumer approval purpose.

The consuming organization owns the business decision. Agent Delivery verifies
and records the decision but cannot issue it, infer it from a catalog, or treat
a supplier signature as approval. Any changed descriptor, digest, scope,
consumer, target class, policy, or expiry invalidates the evidence and returns
the skill to quarantine.

## Required private signing topology

Production profiles use purpose-separated signing roles:

1. `product-release-v1` for Agent Delivery distributions, contract bundles,
   allowlists, and renderer releases;
2. `public-source-v1` for catalogs, public sources, and public skills;
3. `public-render-v1` for public render outputs;
4. `consumer-private-skill-v1` for consumer-private skill publication;
5. `consumer-authority-v1` for authority snapshots and skill/business approval;
   and
6. `consumer-deployment-v1` for private deployments and runtime releases.

Roles 4 through 6 are isolated per consumer. Authority/approval and deployment
signing use different keys and workload identities so a compromised compiler
cannot approve itself. One shared provider key cannot sign private artifacts
for multiple consumers.

## Consumer sovereignty and hosted operation

The preferred topology is a non-exportable asymmetric KMS key in the consumer's
cloud account or security boundary. The consumer controls key lifecycle and
trust policy and grants a narrowly scoped Agent Delivery workload only the
specific sign operation needed for private skill or deployment publication.
The workload authenticates with short-lived WIF/OIDC and cannot administer,
export, rotate, or change policy for the key.

A managed Agent Delivery service may offer a tenant-dedicated KMS/HSM key when
customer-managed KMS is unavailable. It is acceptable only when:

- the consumer explicitly opts in and independently pins the immutable key
  version and claims in its trust policy;
- the key and signing workload are isolated to one consumer;
- the consumer can revoke trust without provider cooperation;
- key use is auditable and export remains impossible; and
- migration to a consumer-owned key is supported without rewriting history.

A cross-consumer shared private-deployment key, provider-controlled trust root,
exported signing key, CI secret key, or runtime-held private key is forbidden.
Development fixtures may use ephemeral test keys but can never satisfy
production conformance.

Private skills from an independent supplier may carry an upstream supplier
signature only when the consumer independently configures an exact provenance
policy for that repository, signer, media type, evidence set, and scope. That
signature is additional provenance and never satisfies
`consumer-private-skill-v1`. Before inclusion, the exact unchanged skill digest
must also receive a role-4 signature from the consumer's isolated private-skill
publication key, normally through a consumer-local mirror or publication
descriptor. Separate current consumer skill-approval evidence under role 5
remains mandatory.

## Immutable trust-policy identity

Every trust policy is an immutable structured object with stable policy ID,
logical version, exact schema ID/digest, canonical policy digest, and effective
window. An artifact descriptor carries both the expected policy ID and digest.
The verifier obtains the policy through an independently authenticated channel;
the artifact cannot supply or update it.

Changing a key set, claim, repository, predicate, freshness rule, revocation,
or outage rule creates a new policy digest. `current` and `next` are immutable
snapshots with explicit overlap windows, not mutable members silently edited in
place. Receipts record the exact policy digest and evaluation time. Historical
verification uses archived policy snapshots and the revocation facts applicable
to the verification question; new activation always uses current policy.

## Verification sequence

Before private compilation, activation, or recovery, the verifier:

1. authenticates the consumer Adapter and target audience;
2. validates the authority/approval schemas and canonical digests;
3. verifies purpose, consumer-isolated signer, immutable key version, claims,
   signature, policy ID/digest, and revocation state;
4. verifies consumer, subject, installation, candidate, target, desired
   revision, nonce, operation, predecessor, and time binding;
5. verifies every effective skill approval;
6. compares the current opaque subdigests with the deployment inputs; and
7. records the exact evidence graph in the append-only receipt.

Call-time authorization remains mandatory after activation. A fresh snapshot
does not turn a configured tool into a standing grant.

## Failure and outage behavior

Missing, expired, future-dated, replayed, revoked, wrong-purpose, cross-
consumer, wrong-target, stale-revision, wrong-policy, or mismatched-subdigest
evidence blocks new compilation or activation. The system never reuses a stale
snapshot, asks a deployment signer to issue approval, or accepts an unsigned
consumer assertion.

During consumer authority or KMS outage, an already active verified release may
continue only under the consumer's documented incident policy. New compile,
activation, recovery, key rotation, or skill approval fails closed.

## Required verification

Conformance evidence includes:

- consumer-owned KMS and tenant-dedicated hosted-key profiles;
- attempted cross-consumer signing and shared-key topology denial;
- workload federation, exact key-version, least-IAM, rotation, revocation, and
  migration ceremonies;
- authority snapshot freshness, audience, nonce, binding, predecessor,
  candidate, subdigest, and replay tests;
- separate authority, approval, private-skill, and deployment signer tests;
- exact skill approval, changed digest, expiry, revocation, and scope tests;
- current activation recheck and stale compilation-snapshot denial;
- provider/model functional configuration with independent grant and
  credential-set evidence; and
- outage, historic receipt verification, and privacy/redaction tests.
