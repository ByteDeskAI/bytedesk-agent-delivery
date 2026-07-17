# AD-17: Cut the ByteDesk OpenClaw canonical source to marketplace artifacts

- Historical Jira: [BDP-3318](https://bytedesk.atlassian.net/browse/BDP-3318)
- Delivery role: Reference-consumer integration
- Core release gate: No — this task does not block a standalone Agent Delivery release
- Integration repository: `bytedesk-openclaw`

## Outcome

Make marketplace packages and the OpenClaw renderer the canonical source for ByteDesk OpenClaw agent content, eliminating independent edits under the consumer repository's agent directories while keeping runtime authority and configuration consumer-owned.

## Inputs

- Published baseline catalog and OpenClaw renderer from AD-03 and AD-06.
- Current `bytedesk-openclaw/agents` inventory and runtime packaging.
- OCI source/render artifacts and trust verification from AD-07 and AD-08.
- Migration map and parity report.
- A separately approved OpenClaw integration task/branch in the correct repository.

## Required work

1. Generate the expected OpenClaw agent bundle from exact signed source/render digests.
2. Update the consumer repository's packaging, build, and install paths to consume or regenerate verified render artifacts rather than treating generated files as authoring inputs.
3. Preserve runtime-required non-definition configuration, tool/MCP/provider access, identity, credentials, and approvals at the consuming-platform boundary.
4. Add generated-file markers and gates that fail CI when hand edits drift from the pinned digest.
5. Migrate existing slugs/references and document intentional semantic differences.
6. Remove or demote duplicate canonical content only after clean-build and runtime parity.
7. Provide rollback by pinning the prior verified render digest and producing a new forward consumer deployment action where runtime state is managed.

## Outputs

- OpenClaw source-cutover PR(s) in the correct consumer repository.
- Generated-artifact verification and build integration.
- Drift gate and migration documentation.
- Runtime smoke and digest-rollback evidence.
- Reusable OpenClaw adapter contract findings contributed to Agent Delivery where generic.

## Acceptance criteria

- Hand editing generated OpenClaw agent content fails the drift gate and cannot become canonical.
- Clean builds reproduce the pinned rendered bundle byte-for-byte.
- No MCP, tool, provider, resource, identity, role, or credential grant is inferred from marketplace source.
- Existing applicable agents retain reviewed role intent.
- Rollback to prior verified definition content is documented and tested.
- Failure or non-completion of this reference integration does not prevent a core Agent Delivery release satisfying AD-18's core certification.

## Verification

Run renderer golden tests, consumer-repository clean build, drift-mutation test, configuration/runtime smoke, exact-digest rollback, and secret/authority-field scans.

## Not in scope

Production release, unrelated OpenClaw refactoring, consumer authorization redesign, or core Agent Delivery release certification.

## Dependencies

Blocked by AD-06, AD-08, and AD-15. It is not a dependency of the standalone core release; it is a dependency of the OpenClaw reference appendix in AD-18.

## Architecture review amendments

- Generated OpenClaw content is inert output from a compile-time allowlisted adapter; no runtime-loaded renderer/plugin code is accepted from a package.
- OpenClaw tool, MCP, provider, identity, credential, resource, and approval configuration remains consuming-platform-owned and cannot flow back into canonical source.
- Cross-repository render provenance is verified through explicit signed upstream digests, not assumed referrer discovery.
- The cutover uses a consumer integration adapter and cannot introduce OpenClaw-specific fields into the canonical marketplace schema or core control-plane domain.
