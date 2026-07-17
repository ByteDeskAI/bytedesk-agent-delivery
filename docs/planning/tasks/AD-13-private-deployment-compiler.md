# AD-13: Compile private consumer deployment artifacts

- Historical Jira: [BDP-3314](https://bytedesk.atlassian.net/browse/BDP-3314)
- Delivery role: Core product control plane
- Release gate: Blocks runtime reconciliation

## Outcome

Compile a verified public source/render artifact, bounded specialization overlay, and consumer-supplied runtime binding references into a private, consumer-scoped `application/vnd.bytedesk.agent.deployment.v1+json` artifact. The compiler remains harness- and consumer-neutral and never becomes the authority for identity, roles, MCP/tool/resource grants, providers, credentials, or business approval.

## Inputs

- Verified source/render descriptors and trust evidence.
- Active installation definition binding and overlay digest.
- Exact opaque consumer, subject, harness, runtime target, stable slot/generation, desired-state revision, authorization-policy/grant revision, lifecycle, credential-set, and workload-identity binding references/digests supplied and authorized by the consumer.
- OCI packaging, consumer-private registry, and deployment-signing policy.
- Historical `bytedesk.hermes-deployment/2` and ByteDesk `AgentDeploymentRevision` as AD-16 reference-adapter migration inputs, not core schema authority.

## Required work

1. Implement the versioned consumer deployment artifact whose subject is the exact public render digest and whose manifest references source digest, overlay digest, installation/subject/harness/target binding, compiled runtime-configuration subdigests, opaque current policy/authority/credential/identity references, desired-state revision, and predecessor.
2. Define an adapter migration contract for prior consumer formats. Do not silently reinterpret historical payloads as verified current OCI state. ByteDesk Hermes v2 backward-read behavior is implemented and certified in AD-16.
3. Compile consuming-platform concerns only at this private boundary: endpoint references, workload-identity binding references, authorization-policy/grant revision identifiers, and credential-set references. Never copy reusable secrets, private keys, bearer/refresh tokens, certificates, or provider credentials into layers.
4. Ask the consumer adapter to revalidate the effective subject, target, lifecycle, desired-state revision, and opaque authorization/binding references immediately before publication. A stale, unavailable, or denied verdict fails closed.
5. Package deterministically, publish to an isolated private registry namespace, sign with the consumer-deployment purpose role, attach policy/provenance evidence, and advance the receipt to prepared idempotently.
6. Enforce cross-installation registry isolation, least pull scope, retention, legal hold, and garbage-collection roots.
7. Reject stale or revoked inputs, wrong target, untrusted parents, mutable tag references, cross-installation subjects, renderer/harness mismatch, or an invalid consumer authorization verdict.

## Outputs

- Consumer deployment v1 compiler and versioned compatibility/migration adapter contract.
- Private registry publisher and installation/target authorization policy.
- Prepared-state deployment-receipt integration.
- Migration fixtures plus security, determinism, idempotency, and isolation tests.

## Acceptance criteria

- The artifact is valid only for the exact installation, consumer subject, harness, runtime target, slot generation, and desired-state revision.
- No private key, bearer/refresh token, provider credential, certificate, or reusable secret is present.
- Verification traverses deployment → render → source exact digests and required attestations.
- Repeating compilation returns the existing prepared receipt without duplicates.
- Historical consumer payloads remain honestly classified by their adapters; cross-installation, stale, revoked, or denied input fails closed.
- The artifact references consumer authority but cannot grant, broaden, or restore it.

## Verification

Run compiler unit tests, legacy-adapter compatibility fixtures, layer secret scan, archive-safety tests, private-registry integration, signature/referrer verification, idempotency/concurrency, stale-verdict, and cross-installation isolation tests.

## Not in scope

Applying the artifact to a runtime, creating consumer identity or grants, storing credential values, or implementing ByteDesk Hermes v2 migration.

## Dependencies

Blocked by AD-05, AD-06, AD-08, AD-09, and AD-11. A consumer only requires the renderer for its selected harness; it does not require every harness adapter.

## Architecture review amendments

- The deployment contract carries per-subject deployment subdigests and a signed runtime-release manifest aggregating exact target digests. Updating one agent does not rotate unrelated workload identities or advance unrelated receipts.
- The signed target includes the consumer-supplied durable slot allocation: subject reference, profile name, UID/GID, port, service, workspace, slot generation, and tombstone-policy digest where the harness needs them. Never derive slots from catalog or roster order.
- Cross-repository parents are explicit signed digest descriptors because OCI referrers cannot discover subjects in another repository.
- Compilation always re-resolves the consumer's current lifecycle, authorization-policy/grant revision, workload-identity/certificate binding reference, runtime slot, and approval verdict. Rollback cannot reuse stale authority from an old artifact.
- Package extraction and build enforce count, size, depth, mode, path, link, device, and decompression limits and never execute packaged scripts.
- The runtime-release manifest defines whether a system-package change is target-wide while ordinary agent changes remain subject-scoped.
