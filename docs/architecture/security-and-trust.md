# Security and trust

## Security objective

Only the exact reviewed definition, deterministic renderer, current consumer
policy inputs, and intended runtime target may become active. Public content
must never grant itself authority.

## Trust roots

Trust is configured independently of artifacts. A trust policy names exact
signer key versions, identities, repository/workflow/environment claims,
artifact media types, required attestations, and revocations. Artifact-supplied
keys or policy are untrusted data.

Signing keys are non-exportable KMS keys accessed through WIF/OIDC workload
identity. Private key material is never stored in repository secrets,
Infisical, build artifacts, hosts, or agent workspaces.

## Purpose separation

Public sources, public harness renders, and private consumer deployments use
separate signing identities. A compromise of one role must not authorize
another artifact class. Consumer lifecycle or authorization signatures remain
outside Agent Delivery's public trust root.

## Untrusted-input model

The following are always untrusted:

- Agent Spec documents and metadata;
- portable skills and all archive entries;
- catalogs and release-channel pointers;
- consumer binding envelopes and additional instructions;
- OCI manifests, layers, annotations, and referrers;
- webhook and repository events; and
- renderer outputs before deterministic validation and signing.

Validation is non-executing and resource-bounded. It rejects traversal,
absolute paths, links, devices, FIFOs, unexpected executable modes, excessive
files/depth/sizes, archive bombs, undeclared media types, remote execution, and
secret patterns. Malware and license policy are explicit gates.

## Authorization separation

Portable source and render artifacts contain no credentials, MCP grants,
provider connections, tenant resource authority, or workload identity. Private
deployment artifacts may bind opaque consumer-generated subdigests and target
identifiers but cannot replace the consumer's call-time authorization check.

The consumer re-evaluates current authority at compile and activation time.
Forward rollback also recompiles current authority; it never restores an old
grant snapshot.

## Verification algorithm

For every desired deployment, the verifier:

1. resolves only exact repository + digest descriptors;
2. confirms expected media type and artifact schema;
3. verifies the signature against an independently supplied purpose policy;
4. verifies required provenance, SBOM, compatibility, evaluation, and policy
   attestations;
5. follows each explicit upstream descriptor and repeats verification;
6. confirms consumer, installation, runtime target, predecessor, and desired
   revision binding;
7. rejects withdrawals, revocations, downgrades, stale inputs, unexpected
   cross-tenant reuse, or any missing edge; and
8. records the verified graph in an append-only receipt.

## Threats and mandatory denial tests

| Threat | Required control |
|---|---|
| Mutable tag substitution | Digest-only authority; channels are discovery |
| Catalog points to malicious source | Independently verify source signature and provenance |
| Cross-repository referrer confusion | Explicit signed upstream descriptors |
| Tool or credential smuggling | Portable policy denylist plus consumer call-time authorization |
| Renderer code injection | Compiled allowlist; packages are inert data |
| Archive escape or bomb | Link/path/type/size/depth/decompression limits |
| Signer compromise | Purpose keys, immutable versions, rotation, revocation, claim constraints |
| Cross-tenant activation | Private scope and exact consumer/installation/target binding |
| Rollback revives revoked access | New forward compile with current authority |
| Slot identity transfer | Durable allocation and tombstones |
| Reconciler overreach | Certificate-bound target-scoped read/observe permissions |
| Registry or KMS outage | Active verified state may continue; new change fails closed |
| Sensitive transparency disclosure | Keep private attestations out of public logs by default |

## Incident behavior

- A withdrawn digest cannot be newly imported or activated.
- A revoked signer fails all new verification.
- Last-known-good content remains locally available subject to consumer incident
  policy.
- The control plane never silently falls back to an unsigned artifact or
  mutable source.
- Recovery and rollback append evidence; history is not rewritten.
