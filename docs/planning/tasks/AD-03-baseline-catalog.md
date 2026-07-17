# AD-03: Publish the baseline ByteDesk agent catalog

- Historical Jira: [BDP-3306](https://bytedesk.atlassian.net/browse/BDP-3306)
- Delivery role: Core product seed content, authored in the separate marketplace repository
- Release gate: Supplies the full-catalog fixture

## Outcome

Translate the current ByteDesk workforce into portable Agent Spec packages: 34 selectable employee agents plus one non-selectable Hermes `office-orchestrator` system package.

## Inputs

- Landed marketplace repository and schema/policy from AD-02.
- Historical `ops/hermes-native` profiles, templates, deployment manifest, and sibling OpenClaw agent files as migration sources.
- Current durable profile slugs, names, role descriptions, and approved role intent.

## Required work

1. Inventory all current definitions and produce a reviewed one-to-one migration map with no silent additions or omissions.
2. Author one canonical Agent or SpecializedAgent package per selectable employee using logical `model_id: default`, empty canonical tools/toolboxes, and harness-neutral instructions.
3. Represent specialization relationships explicitly where they add meaning; do not encode organizational grants, MCP requirements, provider access, identity, or credentials.
4. Package portable, non-blocking skills only when their licenses and dependencies permit redistribution.
5. Publish `office-orchestrator` as a system package that is renderable for Hermes but excluded from selectable catalog results and import defaults.
6. Record source provenance back to legacy files for migration review without retaining those files as authority.
7. Add snapshot/golden tests for IDs, slugs, counts, system/selectable classification, and catalog metadata.

## Outputs

- 34 selectable source packages.
- One non-selectable system package.
- Migration inventory and provenance map.
- Generated catalog and OASF indexes.
- Golden tests proving stable IDs and the exact expected count.

## Acceptance criteria

- Catalog validation reports exactly 34 selectable agents and one system package.
- Every current Hermes employee profile has exactly one marketplace successor.
- No package requires MCP, tool, provider, grant, resource, credential, tenant, engine, organizational identity, or workload identity configuration.
- Instructions preserve role intent while harness-specific operational text is isolated to render adapters.
- A third-party consumer can inspect every package without ByteDesk context.

## Verification

Run official schema and marketplace-policy validation, count/inventory tests, duplicate-ID tests, skill license checks, secret scanning, and human diff review against both legacy sources.

## Not in scope

Deleting legacy sources, issuing consumer identities or grants, or deploying packages.

## Dependencies

Blocked by AD-02.

## Architecture review amendments

- The marketplace remains definition-only and may be consumed without Agent Delivery.
- `office-orchestrator` is explicitly classified as a system package. Non-selectability is portable metadata; the rule that it receives no ByteDesk principal is enforced by the ByteDesk consumer adapter, not by the public package.
- Every redistributed skill must remain optional and inert. Missing skills cannot make the agent package invalid, and packaged content cannot declare authority.
