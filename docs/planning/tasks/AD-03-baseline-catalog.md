# AD-03: Publish the baseline ByteDesk agent catalog

- Historical Jira: [BDP-3306](https://bytedesk.atlassian.net/browse/BDP-3306)
- Delivery role: Reference-catalog track, authored in the separate marketplace repository
- Core release gate: No
- Reference gate: Supplies `REFERENCE-CATALOG-CERT`

## Outcome

Prepare the ByteDesk reference catalog as portable Agent Spec packages: 34
selectable employee agents plus one non-selectable `office-orchestrator`
system package. Preparation may run beside core implementation; certification
waits for the released core.

## Inputs

- [ADR-0002](../../architecture/adr/0002-implementation-stack-and-reference-topology.md)
  for released validator/renderer tooling only; catalog content remains portable
  and definition-only.

- Landed marketplace repository and schema/policy from AD-02.
- AD-04 native validator/renderer contract, exact CONTRACTS-FROZEN bundle, and
  generic renderer conformance fixtures.
- Historical `ops/hermes-native` profiles, templates, deployment manifest, and sibling OpenClaw agent files as migration sources.
- Current durable profile slugs, names, role descriptions, and approved role intent.

## Required work

1. Inventory all current definitions and produce a reviewed one-to-one migration map with no silent additions or omissions.
2. Author one Agent or SpecializedAgent package per selectable employee using restricted human-authored YAML or JSON, logical `model_id: default`, empty canonical tools/toolboxes, and harness-neutral instructions. Publish the validated RFC 8785 JCS representation as the semantic source object.
3. Represent specialization relationships explicitly where they add meaning; do not encode organizational grants, MCP requirements, provider access, identity, or credentials.
4. Package portable, non-blocking skills only when their licenses and dependencies permit redistribution. Skills may contain arbitrary declared regular files, including executable code, but publication and delivery never execute them.
5. Publish `office-orchestrator` as a system package that is renderable for Hermes but excluded from selectable catalog results and import defaults.
6. Record source provenance back to legacy files for migration review without retaining those files as authority.
7. Add snapshot/golden tests for IDs, slugs, counts, system/selectable classification, and catalog metadata.
8. Validate every source kind and any functional/file/skill operations against
   the signed offline schemas; bind every included skill to exact consumer-
   approval requirements without treating publication as approval.

## Outputs

- 34 selectable source packages.
- One non-selectable system package.
- Migration inventory and provenance map.
- Generated catalog and OASF indexes.
- Golden tests proving stable IDs and the exact expected count.
- Reproducible REFERENCE-CATALOG-CERT candidate evidence containing exact core,
  contract-bundle, source, skill, renderer, and test digests.

## Acceptance criteria

- Catalog validation reports exactly 34 selectable agents and one system package.
- Every current Hermes employee profile has exactly one marketplace successor.
- No package requires MCP, tool, provider, grant, resource, credential, tenant, engine, organizational identity, or workload identity configuration.
- Instructions preserve role intent while harness-specific operational text is isolated to render adapters.
- A third-party consumer can inspect every package without ByteDesk context.
- Reformatting valid authoring YAML without changing its JSON data model leaves semantic identity unchanged; original YAML remains provenance only.
- Core conformance and GA remain green when this entire catalog is absent.
- REFERENCE-CATALOG-CERT is issued only after CORE-CERT and clean verification
  against the released core succeeds.

## Verification

Run official Agent Spec and offline-schema validation, strict-operation and
source-kind fixtures, count/inventory and duplicate-ID tests, skill approval/
license/SBOM checks, secret scanning, deterministic native rendering, clean-
clone CLI validation against the released core, and human migration diff review.

## Not in scope

Deleting legacy sources, issuing consumer identities or grants, or deploying packages.

## Dependencies

Blocked by AD-02 and AD-04. REFERENCE-CATALOG-CERT additionally waits for
CORE-CERT, but catalog preparation does not.

## Architecture review amendments

- The marketplace remains definition-only and may be consumed without Agent Delivery.
- `office-orchestrator` is explicitly classified as a system package. Non-selectability is portable metadata; the rule that it receives no ByteDesk principal is enforced by the ByteDesk consumer adapter, not by the public package.
- Every redistributed skill remains optional and unexecuted by the publication
  and delivery pipeline. A missing optional skill does not invalidate public
  source discovery/validation, but a consumer must record an explicit binding
  remove operation before compiling without it; a selected unavailable or
  unapproved skill fails closed. Packaged content cannot declare authority, and
  runtime execution requires explicit approval of the exact skill digest under
  current consumer sandbox, network, identity, and call-time authorization
  controls.
