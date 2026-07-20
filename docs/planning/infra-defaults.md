# Standing infrastructure defaults for AD-04 through AD-18

**Status:** Working defaults for this implementation pass, not an ADR. Revisit
if a task's real requirements outgrow them.

Several remaining AD tasks need infrastructure decisions (sandboxing,
multi-architecture execution, signing) that don't yet exist in this
environment. Rather than pausing on each task to ask, this session applies
the following defaults across AD-04 through AD-18 and flags in each task's
own status notes wherever a default was applied instead of the real thing.

## Sandboxing

Use local Docker with the security profile `contract-release-signer.yml`
already established for the sealed contract verifier: `--network none
--read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit
128 --memory 512m --cpus 1 --user "$(id -u):$(id -g)"`. Reuse this profile
for renderer sandbox execution rather than inventing a second one.

## Platform scope

`linux/amd64` only for this implementation pass. Several task docs (notably
AD-04) specify a paired `linux/amd64` + `linux/arm64` conformance matrix;
per explicit direction, arm64 is out of scope here. Implement the
platform-independent logical transform in a platform-parameterized way (so
arm64 is a follow-up, not a rewrite), but only actually build/execute/test
the amd64 path. Say so plainly in each task's status notes rather than
silently narrowing the acceptance criteria.

## Signing and qualification

Defer to the pattern already established for the contract-bundle release
signer (`docs/planning/tasks/contract-release-signer-tool.md`): implement
the real request/evidence/decision *shapes* against their existing schemas,
verify them with ephemeral, non-exportable test keys the same way
`scripts/contracts/sign_test_ephemeral.py` does, and do not stand up real
production KMS/Sigstore infrastructure. Every signing-shaped output must
say so explicitly (`authorityIssued: false`, `testOnly: true`, or
equivalent) rather than imply a real production signature.

## Upstream artifact descriptors a task's schema requires but no earlier task produced yet

Discovered while scoping AD-04: `render-manifest.schema.json` requires
`productRelease`, `rendererRelease`, and `executedDistribution` fields, each
an `artifactDescriptor` (OCI repository + digest + mediaType + size +
trustPolicy). None of those exist without a working renderer registry,
signed renderer release, and real sandbox execution first - i.e. almost
every AD-04 acceptance criterion is gated on infrastructure several other
required-work items also haven't built yet. This is not unique to AD-04;
expect the same shape (a schema's required fields assuming an artifact only
a later or sibling task produces) elsewhere in AD-05 through AD-14.

Default: build a real, local, non-production "conformance registry" -
locally generated OCI-shaped artifact descriptors (real digests over real
bytes, real trust-policy references) signed only with the ephemeral test-key
pattern above, exactly the way `bytedesk-agent-delivery`'s own
`make verify` already builds two real bundles and signs them with
`sign_test_ephemeral.py` to prove the pipeline end-to-end without a
production release existing. Do not stub these fields with placeholder
strings; compute them for real from locally-produced content so the
schema/digest math is genuinely exercised, just not production-authorized.

## Third-party pinned evidence packages (e.g. `wayflowcore`)

If a pinned evidence-only package used only for CI/certification comparison
(not a runtime dependency) isn't available in the offline cache, treat its
lane as an explicit, documented gap rather than fabricating comparison
output. Say so in the task's status notes; do not simulate its behavior.
