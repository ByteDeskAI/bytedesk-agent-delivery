# AD-05: Implement the deterministic Hermes agent renderer

- Historical Jira: [BDP-3303](https://bytedesk.atlassian.net/browse/BDP-3303)
- Delivery role: Core product harness adapter
- Release gate: Required for the Hermes reference consumer, not for consumers using another harness

## Outcome

Render canonical marketplace packages into the exact Hermes profile/configuration shape without making Hermes or any consuming platform the source of truth.

## Inputs

- Landed renderer contract from AD-04.
- Current Hermes render scripts, templates, profile files, deployment manifest, and validation/provisioning behavior as compatibility evidence.
- Marketplace baseline catalog and system `office-orchestrator` package.

## Required work

1. Implement a Hermes adapter behind the shared renderer interface.
2. Map canonical instructions, identity-neutral descriptive metadata, model abstraction, optional skills, system/selectable classification, and safe renderer defaults.
3. Keep MCP servers, workload credentials, consumer grants, engine IDs, organizational identities, and tenant bindings out of reusable render output. Consumer-owned runtime inputs may enter only during private deployment compilation.
4. Emit the Hermes profile/configuration bundle and render manifest deterministically.
5. Preserve `office-orchestrator` system behavior while preventing catalog selection as an employee.
6. Create golden parity fixtures for representative roles and all 35 packages; document intentional differences from legacy output.
7. Reject unsupported semantics instead of dropping them.

## Outputs

- Versioned Hermes renderer.
- Deterministic Hermes bundle fixtures for all baseline packages.
- Compatibility matrix and legacy parity report.
- Passing shared renderer contract tests.

## Acceptance criteria

- All 34 employee packages and the system package render successfully.
- Repeated clean renders are byte-identical.
- Rendered content contains no secrets, bearer tokens, tenant IDs, resource grants, provider credentials, workload identities, or runtime certificates.
- Differences from the historical ByteDesk Hermes output are enumerated and reviewed.
- The result is suitable as input to later private deployment compilation for any Hermes consumer.

## Verification

Run shared contract and golden tests, a full-catalog render, secret scanning, archive-safety checks, and the pinned Hermes static validators against rendered fixtures.

## Not in scope

Hosted deployment, ByteDesk source cutover, issuing Hermes workload identity, or deletion of legacy ByteDesk files.

## Dependencies

Blocked by AD-03 and AD-04.

## Architecture review amendments

- The adapter is compile-time allowlisted and treats packages as inert data; it cannot load or execute package-provided renderer code.
- `office-orchestrator` system classification is preserved in portable metadata, while principal issuance and runtime authorization remain consumer-owned.
- Hermes MCP, tool, model-provider, identity, engine, and credential configuration may be referenced only by a consumer-specific deployment compilation step, never emitted from public source or render content.
