# AD-18: Certify end-to-end agent portability and delivery

- Historical Jira: [BDP-3319](https://bytedesk.atlassian.net/browse/BDP-3319)
- Delivery role: Core product release certification plus non-blocking reference-consumer appendices
- Core release gate: Yes, for the core matrix only

## Outcome

Prove the complete standalone product from public authoring through third-party validation, rendering, signed OCI distribution, installation, desired-state reconciliation, private compilation, hosted activation, receipt verification, managed update, and forward-only rollback. Leave an operationally supportable core release candidate.

Separately certify ByteDesk Hermes and OpenClaw integrations as reference-consumer appendices. Those appendices prove the product against ByteDesk Platform identity and MCP authorization, but they do not block the standalone core release.

## Inputs

- Landed core tasks AD-01 through AD-15.
- The 34 selectable baseline agents plus one non-selectable system package.
- Non-production registry, KMS/WIF, Git provider, Agent Delivery control plane, consumer-adapter fixture, and hosted runtime fixture.
- AD-01 threat model, test matrix, runbooks, and trust controls.
- For optional reference appendices: landed AD-16 and/or AD-17, non-production ByteDesk Platform/Hermes/OpenClaw environments, Platform ADR-0182/BDP-3235 security controls, and the existing BDP-3282 ingress adapter.

## Required work

### Core certification

1. Execute a clean third-party workflow: clone the separate definition marketplace; validate a package; inspect the signed catalog/OASF projection; render for native Agent Spec, Hermes, and OpenClaw; build and pull by exact digest; and verify signatures/attestations without ByteDesk Platform.
2. Execute a consumer-neutral control-plane workflow: create an installation, preview and bind a consumer-owned subject, commit/reconcile a digest-pinned overlay from Git, compile a private artifact with opaque current consumer-policy references, stage/canary/activate it, inspect the receipt, auto-propose a compatible stable update, force failure, and complete forward-only rollback.
3. Run supply-chain, registry, Git, control-plane, and host fault injection including duplicate/reordered/missed events, scheduled reconciliation, crash/restart, signer rotation/revocation, registry outage, credential rotation, and retained-receipt reproduction.
4. Certify all 34 selectable packages and the non-selectable system package; record every exception as a blocking core defect.
5. Update repository architecture, ADR status, runbooks, diagrams, API/CLI documentation, threat/compatibility matrix, and release evidence.

### Reference-consumer certification

6. When AD-16 is landed, execute the ByteDesk workflow: catalog/import create and bind modes through the adapter, tenant overlay reconciliation, private compilation, hosted Hermes canary, activation, receipt projection, compatible stable update, forced failure, and automatic forward-only rollback.
7. Prove Platform-owned workload login and grant-governed MCP execution: granted discovery/call succeeds; ungranted discovery/call, wrong tenant/profile/revision/signer/digest, stale or revoked binding, and human-login substitution fail. Agent Delivery records results but never makes the authorization decision.
8. When AD-17 is landed, execute OpenClaw clean-build, drift-gate, runtime-smoke, and digest-rollback certification.
9. Credit BDP-3282 only as the ByteDesk reference webhook foundation and close superseded Platform planning only when linked integration evidence exists. Historical Jira closure is not core product evidence.

## Outputs

- Reproducible core E2E certification report and evidence bundle.
- Completed core threat, failure, portability, and compatibility matrix.
- Updated product architecture, runbooks, API/CLI documentation, and release evidence.
- Supersession and cleanup report for product-owned legacy paths.
- Go/no-go recommendation for a separately authorized production release.
- Optional, clearly separated ByteDesk Hermes and OpenClaw reference-consumer appendices with their own go/no-go results.

## Acceptance criteria

### Core release

- Every core definition-of-done statement for AD-01 through AD-15 is demonstrated with linked evidence.
- No marketplace repository, harness output, control-plane store, or runtime fixture remains an undocumented competing canonical definition source.
- Exact running state is reproducible from Git revision, OCI digest graph, trust policy, overlay, installation/consumer binding references, current consumer-policy digest, target/slot, and receipt.
- Automatic rollback restores last-known-good definition content through a new artifact and receipt without history rewrite or restoration of stale authority.
- All consumer identity, roles, MCP/tool/resource grants, provider connections, credentials, workload authentication, and business approvals remain external to Agent Delivery and are represented only by opaque current references/verdicts.
- Production has not been mutated.

### Reference appendices

- ByteDesk Hermes certification proves all 35 mappings, no principal for `office-orchestrator`, existing Platform identity continuity, and allowed/denied MCP behavior under Platform-owned grants.
- OpenClaw certification proves byte-identical generation, drift rejection, no inferred authority, and exact-digest rollback.
- A missing or failed reference appendix blocks only that integration, not the standalone core release.

## Verification

Run all applicable unit, integration, contract, E2E, security, architecture, clean-machine, and disaster-recovery gates. Archive command outputs, exact digests, signatures, attestations, receipts, canonical test fixtures, and redacted logs. Run each reference-consumer suite independently and label its evidence so it cannot be mistaken for core proof.

## Not in scope

Production deployment or release. Every production consumer requires its own separate authorization and delivery mechanism; ByteDesk production remains subject to TeamCity/Fleet and Platform release policy.

## Dependencies

- Core certification is blocked by AD-01 through AD-15 only.
- The ByteDesk Hermes reference appendix is blocked by AD-16.
- The ByteDesk OpenClaw reference appendix is blocked by AD-17.
- AD-16, AD-17, and ByteDesk-specific AD-18 evidence do not block the standalone core release.

## Architecture review amendments — mandatory certification matrix

Core evidence must cover:

- all 35 packages, including portable system/non-selectable classification for `office-orchestrator`;
- official Agent Spec validation and rejection of forbidden authority fields;
- deterministic source, render, deployment, and release OCI digests across clean rebuilds;
- tampered layer, wrong or missing subject, unknown/revoked key, missing attestation, cross-installation/consumer, downgrade, and source-substitution denial;
- duplicate, reordered, missed, and conflicting Git events plus scheduled reconciliation;
- installation create/bind idempotency, consumer-subject adapter failures, and lifecycle races;
- unchanged-skill automatic update and changed/high-risk skill quarantine;
- rollback recompilation with current consumer authority references so revoked authority cannot return;
- partial pull, disk full, crash before/after switch, registry outage, host credential rotation, observation retry, and safe-boundary recovery;
- stable slot preservation and no retired-slot reuse without host-reset ceremony;
- host identity denial outside its one installation and runtime target;
- registry conformance, retention/garbage-collection roots, backup, restore, quotas, legal hold, withdrawal, and revocation;
- architecture/C4 drift checks and clean third-party reproduction with no ByteDesk dependency.

The ByteDesk reference appendix, when run, must additionally cover:

- all 35 ByteDesk mappings and `office-orchestrator` non-selectability with no Platform workload principal;
- exact positive Platform workload login plus granted MCP discovery/invocation;
- negative ungranted, wrong-tenant, wrong-profile, wrong-revision, wrong-subdigest, stale-binding, revoked-binding, and human-login-substitution cases;
- ByteDesk GitHub event ingestion through the existing authenticated ingress and scheduled reconciliation;
- projection into the existing Platform deployment revision/observation model without a duplicate receipt store; and
- Platform architecture sync/C4 drift plus clean Hermes and OpenClaw integration reproduction.
