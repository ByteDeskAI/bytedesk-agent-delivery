# Offline contract bundle v1

## Build input and output

`bundle-source.json` is the closed source expansion policy. Its exact
`schemaInventory` field names `schema-inventory.json`, the sole reviewed v1
product-schema inventory. That JCS control has exactly the root fields
`profile` and `schemas`; every entry has exactly `id`, repository-relative
`path`, and RFC 8785 SHA-256 `digest`, in ascending ID order. The current
inventory closes the set at 112 schemas. The builder accepts
the exact product version, deterministic creation time, and independently
configured immutable `contract-bundle-release-v1` trust-policy ID and digest. It
resolves only repository files, classifies every JSON member by its closed v1
semantic role, expands schema fixtures only from the primary fixture index, and
emits:

- `agent-delivery-contracts-v1.tar`, an uncompressed deterministic tar with
  sorted regular files, mode `0444`, UID/GID zero, empty owner names, and epoch
  timestamps;
- `agent-delivery-contracts-v1.manifest.json`, the exact RFC 8785 manifest
  bytes also stored at `bundle/manifest.json`; and
- the manifest SHA-256 checksum file.

The manifest lists every schema by stable ID, logical contract, version, path,
size, canonical digest, and trust policy. It separately binds the exact signed
schema-inventory control, every other document, the fixture index,
compatibility policy, and documentation map. The
fixture index closes the fixture inventory. `buildInputDigest` commits to the
complete normalized build input and the verifier independently reconstructs it
from authenticated members. It also revalidates the fixture index, expected
schema or semantic-denial outcome, compatibility profile, documentation map,
and bundled-schema registry rather than trusting those manifest claims. An
extra, missing, linked, non-regular, path-escaping, noncanonical structured
control, semantically inconsistent index, or metadata-varying tar member fails
verification.

The 312-entry fixture index—159 valid instances and 153 invalid instances—
includes the exact live action, problem, event, port-registry, protocol-profile,
protocol-fixture, conformance-case, port-type, conformance-plan, and port-contract
fixture controls as valid instances of their ten product schemas, plus a
minimal positive and a closed-boundary denial for each schema. The generated
`type-catalog.json` and `contract-fixtures.json` bind the exact registry and
source-schema digests used to derive every embedded downstream contract. The
builder and verifier accept those catalogs only as authenticated bundle
members: they never execute generated content, resolve an embedded schema from
the network, or treat a passing fixture as runtime or consumer authority.

The deterministic metadata refresh manages 230 schema fixtures across 242
files, preserves the 2 intentional semantic-denial outcomes, and recomputes
the 25-document inventory. Those managed fixtures are a refresh surface within
the complete 312-entry index, not a competing fixture authority.

The documentation map closes its schema references over one strictly sorted,
unique document inventory. Every inventory entry binds a portable repository
path to the SHA-256 digest of that file's exact raw bytes. The builder rejects
a missing, unreferenced, stale, linked, non-regular, noncanonical, or
digest-malformed document entry. The offline verifier authenticates the map as
a bundle member and independently checks its closed shape, digest grammar,
path portability, ordering, uniqueness, and exact reference closure. It does
not consult a checkout or network source to reinterpret an authenticated
document digest.

The builder and both independent repository validators compare the complete
discovered schema set with `schema-inventory.json` by exact ID, path, and
canonical digest. Removing or adding a schema, renaming its file, substituting
its `$id`, or changing its semantic bytes without the reviewed inventory change
fails before a bundle can be published. Their evidence records the inventory
path, semantic digest, count, and outcome.

The offline verifier bootstraps no schema authority from the checkout. It first
matches each manifest schema entry to an exact canonical archive member,
verifies member path, size, digest, embedded `$id`, dialect, and independently
supplied trust policy, checks each schema against the Draft 2020-12 metaschema,
and resolves every `$ref` and `$dynamicRef` through a registry containing only
those bundle members. It then requires the authenticated JCS schema inventory
to equal that complete registry by ID, archive path, and canonical digest. It
validates the manifest and signing request with that
authenticated bundled registry. A checkout schema, network resolver, or
caller-provided replacement is never a fallback.

Repository-maintenance schemas and fixtures are not product contracts. The
builder and the independent verifier both reject every schema under
`contracts/schemas/repository/`, the repository schema index, and the positive
or denial `development-plan__*` fixtures even if a future source glob or fixture
index accidentally names them. Authoritative lifecycle models and the
functional-customization compatibility profile are indexed and shipped by
their real `contracts/` paths, so the release tests the exact objects consumers
receive instead of byte-for-byte fixture copies that could drift later.

Every `.json` member has a path-declared role; a future JSON namespace is
rejected until this profile classifies it. Schemas, the bundle policy,
compatibility controls, lifecycle and operation models, OpenAPI, AsyncAPI,
CloudEvents, and indexed fixtures are strict JSON controls and enter the bundle
as RFC 8785 JCS bytes. Presentation-only whitespace, member ordering, and
equivalent number spelling therefore cannot change their semantic identity.
Files under `contracts/fixtures/encoding/` and pinned material under
`contracts/vendor/` are raw-byte roles because their spelling is the subject of
verification. Non-JSON files are raw-byte roles as well.

Every structured control is parsed as untrusted input before it can enter or
pass verification of a bundle. The accepted parser profile permits at most
4 MiB of input and 4 MiB of canonical output, 64 JSON model levels, and 100,000
total values and member-name nodes. It rejects duplicate member names, integers
outside `-9007199254740991..9007199254740991`, non-finite results such as an
overflowing exponent, invalid UTF-8, and lone Unicode surrogates. Byte, depth,
and node preflight runs before general decoder allocation and the decoded model
must reproduce the same accounting.

Arbitrary raw payload files, including YAML and executable or binary content,
are byte-exact data: bundle construction and verification do not parse,
normalize, import, or execute them. Every path must be relative NFC POSIX
syntax with at most 32 segments, 1,024 UTF-8 bytes overall, and 255 UTF-8 bytes
per segment. Empty, dot, parent, control/format/private-use/unassigned,
backslash, Windows-forbidden/device, trailing-dot/space, and NFC-casefold-
colliding paths are denied. Archives are uncompressed deterministic PAX tar,
contain at most 20,000 regular members and 48 MiB of member content, cap one
member at 16 MiB and the exact archive at 64 MiB, and reject links, special
members, trailing bytes, or any second encoding of the same content.

## Signing and production release boundary

`create_signing_request.py` accepts the exact canonical bundle manifest and
explicit release identity fields and emits canonical
`bytedesk.signing-request/1`. The signed object is this complete request, not a
bare manifest. It binds request ID, the `contract-bundle-release-v1` purpose,
`credentialKind: sigstore_keyless`, exact `signerIdentityDigest`, repository,
canonical-manifest digest, media type, trust-policy ID/digest, sealed
`builderDigest`, pre-sign-certification digest, nonce, and issue/expiry
timestamps. The independently selected contract-bundle policy pins
`trustedRootDigest` and forbids KMS `keyVersion` or a static Fulcio-leaf
`publicKeyDigest`. The request validity window is at most five minutes. The
creator has no private-key option, reads no credential, invokes no signer, and
cannot sign.

Production deliberately separates code execution from signing authority:

1. `contract-release.yml` checks out the immutable tag, runs `make verify`,
   builds the production-policy bundle twice, compares it byte for byte, and
   uploads a closed unsigned candidate. This job has no OIDC token or signing
   authority. Its unsigned structural evidence is diagnostic only.
2. The signer job calls `contract-release-signer.yml` by an exact 40-hex commit
   SHA. That reusable workflow has the protected `contract-release` environment
   and OIDC permission, but it never checks out the repository, runs candidate
   code, or imports a candidate-provided verifier. Through its own read-only SCM
   token, it obtains bounded commit/tree metadata from the exact caller-commit
   endpoint, obtains the corresponding snapshot only from an exact validated
   `https://codeload.github.com/<owner>/<repo>/legacy.tar.gz/<commit>` redirect,
   and downloads that snapshot without forwarding the Bearer token. It does not
   extract or interpret the source archive on the OIDC-capable host.
3. A protected, digest-pinned
   `ghcr.io/bytedesk/agent-delivery-contract-release-tool@sha256:...` image
   performs two network-disabled, read-only, capability-dropped phases. The
   tool first bounds the source archive, member count, member and expanded
   bytes, and portable paths; rejects links and special members; validates the
   expected commit metadata before extraction; safely reconstructs the Git tree
   object; and requires the recomputed tree to equal the SCM-supplied tree. Its
   trusted implementation then rebuilds the bundle and manifest from that exact
   snapshot and requires byte-for-byte equality with the candidate. Only then
   does the first phase verify the deterministic archive, inventory,
   `buildInputDigest`, JCS roles, schema descriptors and offline references,
   fixture semantics, lifecycle and operation models, OpenAPI, AsyncAPI,
   CloudEvents, trust policy, and evidence obligations before producing the
   canonical request. After Cosign signs and verifies that exact request, the
   second phase repeats source-tree and rebuild equality plus signed-input
   checks and emits final release evidence. Neither phase executes source or
   candidate content.

The protected environment supplies the exact destination repository, policy
bytes and digest, keyless signer-identity digest, sealed-verifier image digest,
Cosign executable digest, and Sigstore trusted-root bytes and digest. The sealed
verifier digest is recorded as `builderDigest`; it is distinct from the Cosign
binary digest.
Release automation rejects PEM, PKCS#12, raw private-key, generic-command,
environment-secret-key, mutable image, or caller-selected signer inputs.

The accepted Fulcio identity is the called reusable workflow itself:
`https://github.com/ByteDeskAI/bytedesk-agent-delivery/.github/workflows/contract-release-signer.yml@<exact-commit>`.
Cosign 3.0.6 additionally verifies the caller repository, immutable tag ref,
source commit, `workflow_dispatch` trigger, exact OIDC issuer, and independently
pinned trusted root. Policy-only token constraints such as audience and
protected environment remain issuance controls; they are not misrepresented as
post-hoc certificate assertions.

The contract-bundle request declares `credentialKind: sigstore_keyless`, binds
the complete policy signer by `signerIdentityDigest`, and forbids `keyVersion`
and a static leaf `publicKeyDigest`. It also signs the sealed `builderDigest`
and the exact pre-sign-certification digest. Finalization must resolve that
certification and match its executed distribution before claiming builder
execution; repository conformance evidence keeps that claim false.

The independently configured contract-bundle policy is purpose-, repository-,
and media-type-scoped to `contract-bundle-release-v1` and the contract-bundle
artifact only. It contains exactly the accepted keyless signer and no KMS
signer. The separate `product-release-v1` policy remains KMS-only for product
distributions, compiled allowlists, and renderer releases. A policy that mixes
these purposes or signer credential kinds, or scopes either policy to the
other's artifact media or repository, fails closed.

The repository `verify_bundle.py` is a conformance and development verifier,
not production authority. Its Sigstore mode is explicitly
`external_adapter_conformance`; successful cryptographic verification still
sets `authorityIssued: false`, cannot emit a permitted
`bytedesk.verification-result/1`, and fails if legacy result-output arguments
are supplied. Its append-only, owner-only, locked and `fsync`ed file replay
ledger is available only with `--allow-test-local-replay-ledger`. It proves
single-host test behavior but is neither global nor production replay
authority. A production Signer/Verification Adapter must atomically consume
request ID, nonce, and request digest in durable shared storage before issuing
authoritative evidence; reuse of any key is denied, and a post-consumption
crash requires a new signed request.

Structural-only verification requires `--allow-unsigned-structure`, emits no
authority, and is never a release gate. The contract bundle never supplies its
own trusted key or policy; expected policy bytes, ID, and digest arrive through
an independent channel and any mismatch fails closed.

The release workflow uses a two-revision bootstrap. Its reviewed content
revision deliberately retains the all-zero reusable-workflow reference and
therefore cannot sign. After that exact revision passes verification, the
activation revision replaces the sentinel with the immutable content-revision
commit containing the reviewed signer workflow. Activation also requires an
independently certified sealed-verifier image, every protected value above,
and environment approval. Leaving any prerequisite absent or mutable makes
release signing fail closed.

`sign_test_ephemeral.py` is a deliberately separate test-only tool. It creates
an ECDSA P-256 key inside one process, never serializes the private key, and
marks its detached envelope `test-only-not-production-release-evidence`.
`verify_bundle.py` refuses this envelope unless all test inputs and the
explicit `--allow-test-signature` flag are present. No release job may set that
flag, and the release signer signs only the sealed verifier's canonical
request.

## Failure behavior

Unknown or unclassified JSON roles, schema IDs, a missing/added/renamed/
ID-substituted/digest-stale schema relative to the closed inventory, unresolved references,
duplicate JSON members, parser/resource/path-limit violations, unsafe integers,
invalid Unicode, non-finite numbers, `buildInputDigest` or manifest differences,
trust-policy substitution, archive traversal/collision/special members, missing
or semantically inconsistent fixtures, extra archive bytes, detached-manifest
mismatch, malformed signing requests, overlong or expired request windows,
request/nonce replay, independently substituted request, identity, tool, root,
source, workflow, or builder fields, authenticated SCM redirect drift, source
archive limit/path/type violations, commit/tree mismatch, trusted rebuild
difference, invalid signatures, and absent release configuration fail without
output authority. A failed build may replace only a
private temporary output; atomic publication is absent-or-exclusive and never
mutates a Registry, KMS key, trust policy, or production service.

## Verification

From a clean checkout, `make verify` runs the independent Go and Python Draft
2020-12 validators, canonical/parser fixtures, lifecycle models,
OpenAPI/AsyncAPI/event closure lint, two independent bundle builds and byte
comparison, bundled-schema self-containment and reference-closure tests,
byte-exact arbitrary-YAML/binary round trips, signing-binding and replay tests,
and the supply-chain adversarial suite. That suite covers presentation
invariance, portable-path collisions, archive limits, concurrent mutation,
exclusive publication, replay concurrency and corruption, policy/revocation
substitution, stale descriptors, hermetic fake-Cosign verification with no
private key, exact caller/workflow/source/tool/root bindings, and the explicit
non-authority external-adapter result. A separate workflow-structure suite
proves the unprivileged-build/privileged-signer split, exact workflow pin,
absence of candidate-code execution in the signer, protected digest-pinned
sealed tool, token-safe exact-commit source acquisition, read-only source mounts,
bounded safe source extraction, twice-enforced tree/rebuild equality, two
hermetic phases, and exact Cosign caller-claim flags.

Production release evidence archives the exact SCM commit metadata and source
snapshot with their digests and recomputed tree, candidate and trusted-rebuild
digests/equality, canonical request, Sigstore bundle, independent trust-policy
and trusted-root snapshots, signer-binding and pre-sign certification, exact
sealed-verifier and Cosign digests, Cosign verification output, and final sealed
certification. Repository conformance evidence remains explicitly
non-authoritative.
