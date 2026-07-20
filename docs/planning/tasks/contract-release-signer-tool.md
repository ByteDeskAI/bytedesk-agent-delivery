# Scoping note: the sealed contract-release signer tool

**Status:** Scoping only. Not yet a numbered AD task or wired into the
18-task/7-milestone planning DAG (`docs/planning/development-plan.json`,
`docs/planning/task-breakdown.md`, `docs/planning/dependency-graph.md`,
`docs/planning/verification-matrix.md`). That is a deliberate, separate
follow-up decision once this scope is reviewed, because those documents and
their validators assert an exact task/milestone count.

## Why this exists

`.github/workflows/contract-release-signer.yml` (added in `bc5257b`, revised
in `d917502`, activated in `ec9e14d`/PR #20) already calls a container image
`ghcr.io/bytedesk/agent-delivery-contract-release-tool@sha256:...` running an
entrypoint `/usr/local/bin/bytedesk-contract-release-tool` with two
subcommands, `certify-contract-release-v1` and `finalize-contract-release-v1`.

**Neither the image, the binary, nor any of its five JSON output profiles
exist yet.** No AD-01 through AD-18 task document names this tool (checked by
grep). This means the release workflow activated in PR #20 is real and
CI-green, but structurally unable to ever sign a release until this tool is
built — the workflow currently fails closed at
`docker pull "$CONTRACT_RELEASE_VERIFIER_IMAGE"` for lack of an image.

This is the narrow, self-contained slice of AD-08's `contract-bundle-release-v1`
keyless policy (AD-08 required-work item 9, item 13) that the contract-freeze
work front-loaded into CI ahead of AD-08 itself, because contract releases
don't depend on the renderer/OCI-packaging chain (AD-04 through AD-07) that
blocks the rest of AD-08.

## Outcome

A container image, published to `ghcr.io/bytedeskai/agent-delivery-contract-release-tool`,
whose `bytedesk-contract-release-tool` entrypoint implements exactly the CLI
contract already asserted by `contract-release-signer.yml`'s two `docker run`
invocations, runnable network-isolated, read-only, capability-dropped, as a
fixed non-root UID.

## Inputs

- The exact, already-frozen CLI contract in
  `.github/workflows/contract-release-signer.yml` steps "Certify candidate
  semantics and create the canonical request in the sealed tool" and
  "Finalize signature evidence in the same sealed verifier" — every flag name,
  mount path, resource limit, and output filename there is normative; this
  scoping note does not restate them, it points at the exact lines.
- `scripts/contracts/test_release_workflow_structure.py`, which already
  encodes structural/denial invariants this tool's *caller* must preserve
  (e.g. `--expected-credential-kind sigstore_keyless` appearing exactly twice,
  no `keyVersion` field, purpose bound to `contract-bundle-release-v1`).
- The existing Go canonicalization/schema/portable-path logic in
  `internal/contracts/canonical`, `internal/contracts/schema`, and the
  `bytedesk.portable-path/1` profile already defined in
  `contracts/ports/v1/protocol-profiles.json` — the archive-safety and
  canonicalization behavior this tool needs should reuse that logic rather
  than reimplementing it.
- AD-08 (`docs/planning/tasks/AD-08-signing-and-attestations.md`), which is
  the eventual home for the broader signing/attestation system this tool is
  one purpose-scoped instance of.

## Required work

1. **Formalize the five JSON output profiles as JSON Schemas** under
   `contracts/schemas/v1/` (or determine which are legitimately CI-internal
   and belong under `contracts/schemas/repository/` instead), replacing the
   informal `jq` boolean assertions in the workflow with real schema
   validation on both sides (tool output, workflow consumption). This closes
   the normative-authority gap: today these five shapes exist nowhere as
   schemas.
2. Implement `certify-contract-release-v1`: fetch/verify the source snapshot
   (already partly done by the calling workflow before invocation; confirm
   exactly which checks belong in the tool vs. the workflow to avoid
   duplicated or, worse, divergent logic), rebuild the bundle from source,
   require byte-for-byte match against the candidate, and emit the
   `contract-release-candidate`/`signing-request`/`signer-binding`/
   `pre-sign-certification` outputs.
3. Implement `finalize-contract-release-v1`: verify the Cosign signature,
   trust policy, trusted root, and source lineage together, then emit
   `bytedesk.contract-bundle-release-signing-evidence/1`.
4. Enforce the full portable-path/archive-safety profile
   (`bytedesk.portable-path/1`) against the fetched source archive inside the
   tool, reusing `internal/contracts/canonical` rather than reimplementing
   path/symlink/decompression checks a second time.
5. Package as a minimal, pinned-base-image container; the image digest itself
   becomes `CONTRACT_RELEASE_VERIFIER_IMAGE` and is asserted as
   `--expected-builder-digest` inside its own output, so the build must be
   reproducible from a clean checkout the same way `make bundle-contracts` is.
6. Add the same caliber of adversarial fixtures this repo requires elsewhere:
   tampered source archive, wrong tree SHA, wrong builder digest, forged
   signer identity, replayed request, and the "trust-policy substitution"
   family of denials already proven at the *workflow* boundary by
   `test_release_workflow_structure.py` — this tool must independently prove
   the same denials at the *tool* boundary, since the workflow's assertions
   alone are not implementation goldens.
7. Publish the image to `ghcr.io/bytedeskai/agent-delivery-contract-release-tool`
   and update the pinned digest at the two call sites
   (`.github/workflows/contract-release-signer.yml` line 55's regex literal,
   and the `CONTRACT_RELEASE_VERIFIER_IMAGE` repo variable).

## Outputs

- `bytedesk-contract-release-tool` source, Dockerfile, and reproducible build.
- Five new (or explicitly repository-internal) JSON Schemas plus fixtures.
- A published, digest-pinned image under `ghcr.io/bytedeskai/`.
- A negative/adversarial test suite proving the tool itself fails closed,
  independent of the workflow-level structural tests that already exist.

## Acceptance criteria

- A clean local build of the image is reproducible (two builds, compared by
  image digest or exported layer digests).
- Every flag, mount, and output file the workflow already asserts is
  satisfied exactly; `make verify`-equivalent local invocation of both
  subcommands against a real candidate bundle succeeds without the workflow.
- All five output JSON documents validate against real schemas (not just jq
  assertions).
- Tamper/substitution/replay denial fixtures fail closed with the exact error
  shape the workflow's `jq -e` checks expect.
- `scripts/contracts/test_release_workflow_structure.py` continues to pass
  unmodified (this task changes the tool, not the caller's structural
  contract) — see `docs/planning/implementation-readiness-execution.md` for
  the existing evidence baseline that must not regress.

## Not in scope

- KMS-backed `product-release-v1` signing, qualification/status-head
  machinery, renderer/private-compilation signing purposes — all remaining
  AD-08 scope, blocked by AD-04 through AD-07.
- Provisioning a production Sigstore/KMS identity beyond what GitHub Actions'
  own OIDC-to-Fulcio keyless flow already provides.
- Deciding whether/how to formally insert this into the 18-task DAG.

## Dependencies

None from the formal DAG (front-loaded ahead of AD-08). Practically depends
on the `ghcr.io/ByteDeskAI` registry decision already made for this work.

## Normative contracts and conformance

Pending — item 1 above (formalizing the five profiles as JSON Schemas) must
land before this task can cite normative schema paths the way every other AD
task document does. Until then, `.github/workflows/contract-release-signer.yml`
itself is the only normative source for this tool's CLI/output contract.
