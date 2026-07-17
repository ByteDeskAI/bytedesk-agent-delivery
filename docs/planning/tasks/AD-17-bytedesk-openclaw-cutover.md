# AD-17: Cut the ByteDesk OpenClaw canonical source to marketplace artifacts

- Historical Jira: [BDP-3318](https://bytedesk.atlassian.net/browse/BDP-3318)
- Delivery role: Reference-consumer integration
- Core release gate: No — this task does not block a standalone Agent Delivery release
- Reference gate: Contributes to `REFERENCE-CONSUMER-CERT`
- Integration repository: `bytedesk-openclaw`

## Outcome

Make marketplace packages and the OpenClaw renderer the canonical source for ByteDesk OpenClaw agent content, eliminating independent edits under the consumer repository's agent directories while keeping runtime authority and configuration consumer-owned.

## Inputs

- Pinned CORE-CERT release with OpenClaw renderer, OCI/trust, control-plane,
  compiler, reconciler, API, CLI, and contract bundles.
- REFERENCE-CATALOG-CERT when the cutover selects ByteDesk's 34+1 catalog.
- Current `bytedesk-openclaw/agents` inventory and runtime packaging.
- OCI source/render artifacts and trust verification from AD-07 and AD-08.
- Migration map and parity report.
- A separately approved OpenClaw integration task/branch in the correct repository.

## Required work

1. Generate the expected public OpenClaw catalog bundle from exact signed source/render digests and each private effective OpenClaw bundle from the exact public source, deterministic consumer customization, and approved skill digests.
2. Update the consumer repository's packaging, build, and install paths to consume or regenerate verified render artifacts rather than treating generated files as authoring inputs.
3. Allow private consumer customization of all functional OpenClaw definition properties, configuration, arbitrary files/skills, and opaque secret references. Preserve tool/MCP/provider authority, identity, credentials, trust/signing, mandatory security controls, and approvals at the consuming-platform boundary.
4. Add generated-file markers and gates that fail CI when hand edits drift from the pinned digest.
5. Migrate existing slugs/references and document intentional semantic differences.
6. Remove or demote duplicate canonical content only after clean-build and runtime parity.
7. Provide forward recovery by selecting eligible historical functional
   content and producing a newly compiled consumer rollout under current
   trusted tooling and authority.
8. Require a full pinned-Adapter re-render for every non-empty customization or private skill set and embed the effective render in the private deployment; never post-patch the public render.
9. Use exact renderer-release, current consumer-authority/skill-approval, and
   consumer-isolated private-signing evidence. Where runtime desired state is
   managed, only the Promotion Coordinator writes it; the host and consumer
   capability verifier remain distinct.
10. Migrate ByteDesk customization to the strict functional/file/skill
    operation profiles with exact preconditions and no OpenClaw-specific core
    schema fork.

## Outputs

- OpenClaw source-cutover PR(s) in the correct consumer repository.
- Generated-artifact verification and build integration.
- Drift gate and migration documentation.
- Runtime smoke and current-tooling forward-recovery evidence.
- Reusable OpenClaw adapter contract findings contributed to Agent Delivery where generic.
- REFERENCE-CONSUMER-CERT evidence linking exact core/catalog, Adapter,
  authority, key, rollout, cutover, recovery, SLO, and support/runbook digests.

## Acceptance criteria

- Hand editing generated OpenClaw agent content fails the drift gate and cannot become canonical.
- Clean builds reproduce the pinned rendered bundle byte-for-byte.
- No MCP, tool, provider, resource, identity, role, or credential grant is inferred from marketplace source.
- Arbitrary declared skill files are reproduced without Agent Delivery executing them; any later OpenClaw execution requires consumer approval and consumer-owned runtime controls.
- Existing applicable agents retain reviewed role intent.
- Current-tooling forward recovery from eligible historical functional content
  is documented and tested.
- Failure or non-completion of this reference integration does not prevent a core Agent Delivery release satisfying AD-18's core certification.
- No consumer repository, generated directory, host, observation, or capability
  verifier becomes a second desired-state writer.

## Verification

Run exact renderer-release and contract fixtures, consumer clean build, drift
mutation, authority/private-key/skill-approval, single-writer, distinct canary-
actor and false-denial tests where capability-bearing, configuration/runtime
smoke, current-tooling forward recovery, SLO/DR/runbook evidence, and
secret/authority-field scans.

## Not in scope

Production release, unrelated OpenClaw refactoring, consumer authorization redesign, or core Agent Delivery release certification.

## Dependencies

Blocked by CORE-CERT only. REFERENCE-CONSUMER-CERT additionally requires
REFERENCE-CATALOG-CERT when this integration selects the ByteDesk catalog.

## Architecture review amendments

- Generated OpenClaw content is untrusted output from a compile-time allowlisted adapter; no runtime-loaded renderer/plugin code is accepted from a package, and Agent Delivery never executes delivered skill content.
- OpenClaw tool, MCP, provider, identity, credential, resource, and approval configuration remains consuming-platform-owned and cannot flow back into canonical source.
- Cross-repository render provenance is verified through explicit signed upstream digests, not assumed referrer discovery.
- The cutover uses a consumer integration adapter and cannot introduce OpenClaw-specific fields into the canonical marketplace schema or core control-plane domain.
