# Trust policy v1

**Status:** Draft contract

## Purpose

A trust policy tells a verifier which independently configured identity may
sign which artifact under which build claims. Artifacts cannot extend the
policy that validates them.

## Policy record

Each purpose record includes:

- stable policy identifier and version;
- allowed artifact media types and repository patterns;
- immutable KMS key-version resource identifiers;
- accepted signature algorithms;
- exact workload identities and WIF/OIDC claim constraints;
- repository, workflow, ref, environment, builder, and subject constraints;
- required provenance, SBOM, compatibility, evaluation, and policy predicates;
- current and next key sets with activation windows;
- revoked key versions, digests, workflows, and builders;
- downgrade and freshness rules; and
- fail-closed and outage behavior.

## Purpose profiles

V1 requires distinct policies for:

1. `public-source-v1` — catalog and canonical source publication;
2. `public-render-v1` — allowlisted harness renders; and
3. `private-deployment-v1` — consumer-bound deployments and releases.

One key or workload identity must not satisfy multiple purposes merely because
its signature is cryptographically valid.

## Key management

- Keys are non-exportable KMS asymmetric signing keys.
- CI authenticates through short-lived WIF/OIDC federation.
- Policy pins immutable key versions, not only a mutable key alias.
- Private material is never copied to secret managers, CI variables, hosts, or
  developer machines.
- Rotation introduces `next`, verifies dual trust, switches publication, waits
  through the defined overlap, then retires `current`.
- Compromise revokes the affected key and builder claims, withdraws impacted
  digests as policy requires, and triggers rebuild/republication.

## Verification failures

Unknown/revoked key, wrong purpose, wrong repository/workflow/ref/environment,
missing predicate, unexpected media type, stale policy, downgrade, withdrawn
digest, or mismatched subject is terminal for new activation.

## Transparency and privacy

Public source and render provenance may use public transparency services.
Private deployment attestations default to private registry storage because
tenant identifiers, repository commits, policy digests, or runtime targets may
be sensitive.

## Host distribution

Hosts receive trust policy through an independently authenticated consumer
channel. A deployment artifact may name the required policy identifier but
cannot supply or alter the trusted key material or claim rules.
