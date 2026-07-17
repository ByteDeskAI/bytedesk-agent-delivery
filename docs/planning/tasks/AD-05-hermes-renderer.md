# AD-05: Implement the deterministic Hermes agent renderer

- Historical Jira: [BDP-3303](https://bytedesk.atlassian.net/browse/BDP-3303)
- Delivery role: Core product harness adapter
- Release gate: Required renderer product for `SUPPLY-CHAIN-CERT`

## Outcome

Render canonical marketplace packages into the exact Hermes profile/configuration shape without making Hermes or any consuming platform the source of truth.

## Inputs

- [ADR-0002 reference implementation stack and topology](../../architecture/adr/0002-implementation-stack-and-reference-topology.md).

- Landed renderer contract from AD-04.
- Current Hermes render scripts, templates, profile files, deployment manifest, and validation/provisioning behavior as compatibility evidence.
- Generic public/private Agent Spec, strict customization, file, skill, and
  unsupported-semantics fixtures from AD-04.

## Required work

1. Implement a Hermes adapter behind the shared renderer interface.
2. Map canonical instructions, identity-neutral descriptive metadata, model abstraction, optional skills, system/selectable classification, and safe renderer defaults for the public catalog scope; support a complete resolved private effective definition for the private scope.
3. Keep MCP servers, workload credentials, consumer grants, engine IDs, organizational identities, tenant bindings, and private customization out of reusable public render output. Consumer functional MCP/tool/provider/model/harness configuration and opaque secret references may enter only during private deployment compilation; security authority remains separate.
4. Emit the Hermes profile/configuration bundle and render manifest deterministically.
5. Preserve generic system/selectable metadata without assigning a consumer
   principal or making ByteDesk's `office-orchestrator` a core fixture.
6. Create generic golden fixtures spanning representative portable semantics;
   keep ByteDesk 34+1 parity in AD-03/AD-16.
7. Reject unsupported semantics instead of dropping them.
8. Fully rerender the resolved private effective definition and exact approved public/private skills. Embed the effective Hermes bundle and manifest in the private deployment; do not post-patch a public bundle.
9. Produce the Hermes renderer-release manifest and supported platform
   distribution descriptors, pass the compiled-allowlist and sandbox contract,
   and record the actual executed digest in every render.

## Outputs

- Versioned Hermes renderer.
- Deterministic Hermes bundle fixtures for the complete generic conformance
  corpus.
- Compatibility matrix and explicit semantic-loss report.
- Passing shared renderer contract tests.
- Immutable Hermes renderer-release candidate, schema descriptors, sandbox
  evidence, SBOM, and deterministic cross-platform evidence for AD-08 signing.

## Acceptance criteria

- The complete generic Hermes conformance fixture suite renders successfully
  without a ByteDesk catalog.
- Repeated clean renders are byte-identical.
- Rendered content contains no secrets, bearer tokens, tenant IDs, resource grants, provider credentials, workload identities, or runtime certificates.
- Arbitrary approved skill regular files are preserved by digest without execution during delivery; Hermes runtime execution requires explicit approval of the exact skill digest under current consumer sandbox, network, identity, and call-time authorization controls.
- Every supported, unsupported, or policy-permitted lossy mapping is explicitly
  enumerated and reviewed against the generic contract.
- The result is suitable as input to later private deployment compilation for any Hermes consumer.
- Renderer version, release manifest, executing distribution/platform,
  allowlist, and schema digests are exact and substitution-safe.

## Verification

Run shared schema/contract/golden tests, generic semantic coverage, clean
cross-platform deterministic renders, exact renderer/distribution/allowlist
readback, sandbox and input-execution-spy tests, secret and archive-safety
checks, and pinned Hermes static validators.

## Not in scope

Hosted deployment, ByteDesk source cutover, issuing Hermes workload identity, or deletion of legacy ByteDesk files.

## Dependencies

Blocked by AD-04 only.

## Architecture review amendments

- The adapter is compile-time allowlisted and treats packages as untrusted data; it cannot load or execute package-provided renderer code.
- Hermes functional MCP, tool, model-provider, and harness configuration plus opaque secret references may be supplied only by a consumer-specific customization/deployment compilation step, never emitted from public source or catalog-render content. Identity, grants, credential values, engine authority, and security policy remain external.
