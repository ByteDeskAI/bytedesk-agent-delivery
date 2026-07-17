# ADR-0002: Implementation stack and production reference topology

- **Status:** Accepted
- **Date:** 2026-07-17
- **Decision owners:** ByteDesk Agent Delivery maintainers
- **Supersedes:** No prior implementation-stack decision
- **Depends on:** [ADR-0001](0001-independent-agent-delivery-control-plane.md)

## Context

ADR-0001 fixes the portable product, authority, artifact, lifecycle, and failure
boundaries. It intentionally does not choose the implementation language,
persistence engine, worker substrate, sandbox, deployment platform, or concrete
reference topology. Leaving those choices implicit would force later tasks to
invent transaction, isolation, release, and operational behavior independently.

This ADR fixes one production-capable reference implementation. It does not make
the selected vendors or deployment substrate part of a portable agent package.
Registry, KMS, Git, consumer, harness, and consumer-native desired-state
alternatives remain versioned Adapters that must pass the same contracts.

Version numbers below identify the initial reproducible build profile. Patch and
security updates within an accepted release line are normal dependency updates
when conformance remains green. A language major/minor, database major,
Kubernetes minor outside the supported matrix, persistence model, sandbox
boundary, or replacement of a named primary component requires an ADR update.

## Decision

### 1. Product implementation languages

The control plane, CLI, reconciliation protocol implementation, OCI/KMS/Git
Adapters, and local contract verifier are implemented in **Go 1.26**. The
initial exact toolchain is **Go 1.26.5** and is declared with `go` and
`toolchain` directives. CI and release builds use a toolchain image pinned by
digest. Go is selected for static cross-platform binaries, strong concurrency
and cancellation, mature OCI/Kubernetes/Sigstore libraries, and a small runtime
surface suitable for host agents and CLIs.

The official Agent Spec validation boundary runs in isolated **Python 3.13**
workers. The initial exact runtime is **Python 3.13.14** with the sole
production Agent Spec dependency `pyagentspec==26.1.2`, mirrored into the
offline dependency store and locked by wheel SHA-256.

WayFlow is not in a production worker. A separate CI/certification-only image
pins `wayflowcore==26.1.2` and consumes Native Agent Spec output to produce
external compatibility evidence. It has no production routing, database,
Registry, KMS, signing, publication, or consumer access. Its result is evidence,
never renderer output, renderer identity, or an Agent Delivery runtime
dependency. The supplied PyAgentSpec and WayFlow wheels are mirrored and their
upstream provenance limitations are recorded rather than represented as
product SLSA provenance.

Python code is never imported into the Go control-plane process. A renderer
worker receives one closed request through a versioned, length-delimited
framed-JSON protocol over anonymous pipes created by the signed product
launcher. The launcher reads request bytes only from the staged input volume,
does not let the worker inherit the container's standard streams, and writes
the bounded response and bounded diagnostic stream only to declared files on
the output volume. Renderer bytes never reach CRI/container stdout or stderr;
those streams are empty or contain only fixed, non-content launcher lifecycle
codes. Diagnostics are untrusted private output, byte-capped, hashed/redacted
for evidence, and destroyed with the attempt volume. The worker has no network
or secrets, writes only to its declared output directory, and is killed after
one request. Hermes and OpenClaw renderers may be implemented in Go or isolated
Python, but every distribution uses the same renderer protocol, trusted
launcher, and sandbox. Artifact input cannot select Python modules, entry
points, plugins, hooks, commands, or logging destinations.

Contract generation and cross-validation may use repository-locked development
tools in Go, Python, or Node, but none becomes runtime authority. The normative
JSON Schemas and canonical bytes remain language-neutral.

### 2. Repository and module shape

The repository is a monorepo with one Go module and explicit domain boundaries:

```text
cmd/
  agent-delivery-api/       public/authenticated HTTP service
  agent-delivery-worker/    durable action and outbox workers
  agent-delivery-renderer/  sandbox worker entry point
  bd-agent/                 supported CLI
internal/
  catalog/ contracts/ rendering/ supplychain/ installations/
  promotion/ deployment/ reconciliation/ evidence/ integrations/
  ports/                    versioned transport-neutral Go port interfaces
  renderers/                compiled Native/Hermes/OpenClaw implementations
contracts/                  normative schemas, API/event descriptions, fixtures
migrations/                 ordered forward SQL migrations
deploy/                     Compose and Helm reference profiles
scripts/                    deterministic developer/release entry points
```

Domain modules expose application commands, queries, and internal ports; they do
not write one another's tables. `internal/ports` and `internal/renderers` are not
a public Go extension API. Only deliberately supported reusable client and
contract packages may live under `pkg/`. Generated code is written to clearly
marked directories and is never edited by hand.

`Makefile` is the stable human/CI entry point. Go tools are pinned through the
module tool dependency set, Python through `uv.lock` plus required hashes, and
any Node development tools through `package-lock.json` and `npm ci`.
`deploy/reference-components.lock.json` records every deployed chart, image,
binary, CNI, CSI, ingress, database operator, sandbox runtime, Collector, and
local emulator by version plus per-platform digest/checksum and configuration
digest. CI rejects an unlocked dependency, unreviewed generated drift,
network-fetched runtime schema, mutable container tag, unpinned action, or
deployment input absent from that signed lock.

### 3. Build and release profile

GitHub Actions is the reference CI/release system. Every external action and
reusable workflow is pinned by full commit SHA and receives minimum permissions.
Pull-request jobs have no production Registry or KMS authority. Release builds
use fresh GitHub-hosted ephemeral builders; persistent self-hosted runners are
excluded unless a later hardened-builder profile passes equivalent
certification. OIDC subjects are restricted to the exact repository, immutable
workflow revision, protected release environment, and signer audience. No
exported signing key or cloud access key is stored in GitHub secrets.

The trusted-builder boundary is the product-owned reusable workflow
`.github/workflows/release-builder.yml`, invoked as
`ByteDeskAI/bytedesk-agent-delivery/.github/workflows/release-builder.yml@<full-builder-commit>`.
Its builder commit is distinct from the source commit being built, is recorded
in the signed component lock, and is reachable from a protected immutable
`builder/v1` release ref. CODEOWNERS requires supply-chain and security approval
for that workflow, its dependency lock, and the ref-creation workflow. The thin
caller supplies only a closed release tag, exact source commit, and enumerated
platform from the workflow schema. It cannot supply a command, action, runner,
environment, secret, output path, registry destination, provenance predicate,
or attestation subject. The called workflow independently checks out the exact
source commit, performs every build and digest step, and creates the attestation
before returning immutable artifact, bundle, and digest outputs. A source change
therefore cannot replace or inject steps into the trusted builder.

The reusable workflow uses **actions/attest 4.2.0** pinned as
`actions/attest@f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6`. Its job permissions are
exactly `contents: read`, `id-token: write`, `attestations: write`, and
`artifact-metadata: write`, plus `packages: write` only for the OCI publication
job; the caller grants the same required permissions but cannot use them in a
caller-controlled build step. Binaries are named and hashed inside the workflow
and attested through an explicit generated SHA-256 checksum file. Each OCI image
is built and pushed once, then attested with the fully qualified repository name
without a tag, the exact `sha256:` manifest digest, and
`push-to-registry: true`. Automatic subject discovery, caller-provided
predicates, tag-only subjects, mutable base images, and post-build replacement
are forbidden.

The action emits an in-toto statement with predicate type
`https://slsa.dev/provenance/v1` and a Sigstore verification bundle. The bundle
path returned by the action is captured before the ephemeral runner exits. The
release gate claims **SLSA v1.0 Build Level 3** only when verification proves the
expected repository, reusable-workflow path and builder commit, exact source
commit and protected release ref, SHA-256 subject, GitHub-hosted runner, and
fresh trusted-builder execution. Artifact attestations without the isolated
reusable workflow are Level 2 evidence, and merely invoking the action is not
certification.

The connected and offline release gates use checksum-pinned **GitHub CLI
2.96.0**, tag commit `b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0`.
`gh attestation verify` is invoked with the exact `--repo`,
`--signer-workflow`, `--signer-digest`, `--source-digest`, `--source-ref`,
`--predicate-type https://slsa.dev/provenance/v1`, and
`--deny-self-hosted-runners` policy. The product wrapper parses JSON output and
also requires the expected subject name/digest, builder identity, build type,
invocation parameters, resolved dependencies, and timestamps; predicate fields
are never trusted without the certificate-bound workflow identity and immutable
builder digest.

The connected gate downloads the complete attestation bundle and obtains a
fresh `gh attestation trusted-root` snapshot. Release evidence archives those
bytes, the action-returned bundle, trusted-root snapshot, source/ref and builder
commit evidence, verifier binary/checksum, OCI copy receipts, and normalized
verification result. The air-gapped gate supplies only the archived
`--bundle` and `--custom-trusted-root` inputs and performs no network lookup.
The product Go verifier and Cosign 3.0.6 cross-check subject/signature/bundle
handling against GitHub CLI. Wrong repository/workflow/builder/source/ref,
self-hosted-runner provenance, a swapped valid transparency-log entry, expired
or missing roots, altered subject bytes, and tag-only OCI references all fail
closed. A future use of user-controlled custom predicates or a different
builder requires a new reviewed profile and malicious-fixture coverage.

The initial signing tool is **Cosign 3.0.6**. Product-release and public-
publication workflows, identities, repositories, and keys are purpose-separated.
Consumer-private skill and deployment signing occurs in separately deployed
production signer modes through the applicable consumer KMS Adapter, never in
the product release workflow. Consumer-private artifacts do not enter a public
transparency log by default. Signatures, verification bundles, SBOMs,
provenance, scanner inputs/results, and trusted-root snapshots are copied to
the locked evidence archive for offline verification.

Release outputs are:

- reproducible Go binaries for Linux `amd64`/`arm64` servers and Linux, macOS,
  and Windows `amd64`/`arm64` CLI clients;
- Linux `amd64`/`arm64` OCI images built from pinned distroless/static bases;
- isolated renderer images for each required server platform;
- SPDX 2.3 SBOMs, vulnerability/license reports, in-toto/SLSA provenance, and
  Cosign signatures bound to exact digests; and
- the signed offline contract bundle.

An output is built once, verified, signed, and promoted by exact digest. No
environment, channel, or release stage rebuilds it. Provenance distribution and
verification are explicit release gates; generating a provenance statement is
not itself certification.

`CGO_ENABLED=0` is the default for Go product binaries. Any required cgo use is
a reviewed exception with a locked toolchain and additional platform evidence.
Release timestamps, archive order, ownership, modes, and compression settings
come from the release profile rather than the build host.

### 4. Authoritative persistence and durable work

**PostgreSQL 18** is the sole reference authoritative application database; the
initial certification-target patch is **18.4**. The Kubernetes reference uses
**CloudNativePG 1.30.0** with one primary and at least two standbys distributed
across three availability zones. `synchronous_commit=on`, `ANY 1`,
`postgresql.synchronous.dataDurability=required`, and
`postgresql.synchronous.failoverQuorum=true` are mandatory for acknowledged
command/evidence writes; neither `remote_write` nor asynchronous-only
acknowledgement is conforming. Loss of all eligible synchronous standbys makes
mutations fail closed instead of silently degrading durability. CloudNativePG's
primary lease serializes promotion but is not treated as a partition fence.
Conformance kills aligned and non-aligned replicas separately and proves a
promotion never loses an acknowledged quorum commit.

A managed PostgreSQL profile is acceptable only when the exact transaction,
isolation, synchronous-durability, fencing, backup, restore, and extension
behavior passes the same suite. PostgreSQL stores aggregates, canonical
structured bytes, revisions, receipts, audit records, idempotency records,
durable actions, leases/fencing tokens, outbox entries, and inbox deduplication.
It stores OCI descriptors, not large OCI payload blobs.

The Go data layer uses pinned `pgx/v5` with `sqlc`-generated, reviewed SQL.
**PgBouncer 1.25.2** runs at least three zone-spread replicas in
transaction-pooling mode;
separate API, Coordinator, worker-mode, event-publisher, and read-model pools
have explicit connection budgets within 80% of PostgreSQL `max_connections`,
leaving reserved operator, migration, backup, and incident capacity. Every
authoritative/current read, read-after-write, target watch, and promotion check
uses the writer endpoint. Replicas serve only explicitly stale-tolerant catalog
and historical queries.

API, Coordinator, compiler, renderer controller, registry publisher, event
publisher, evidence archiver, migration, backup, and read-model processes have
different TLS client identities and non-owner database roles. Tenant tables use
`ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`; each transaction
sets a validated local consumer scope. Migration and backup roles cannot serve
application traffic. SQL migrations are ordered, forward-only source files run
once under a database advisory migration lock by the pinned migration tool.
Schema change uses expand/migrate/contract across N and N-1 application
versions; irreversible contraction requires a verified restore point and the
documented compatibility window.

Command acceptance uses one database transaction:

1. validate the exact input and idempotency record;
2. lock or conditionally update the aggregate by revision and digest;
3. append immutable domain/evidence rows;
4. enqueue durable action work when needed; and
5. append outbox notifications before commit.

Target desired-state CAS uses a conditional update on consumer, target,
revision, and digest. A database transaction or remote consumer-native CAS—not
a process mutex, advisory lock, or lease—is authority. Serializability-sensitive
promotion and store-migration operations run at `SERIALIZABLE` with bounded
whole-transaction retry. Other commands use `READ COMMITTED` plus explicit row
and CAS predicates.

For a consumer-native `DesiredStateStore`, the Agent Delivery transaction
records the durable Coordinator command but never creates a managed desired-
state row. The Coordinator calls the remote Adapter with an idempotency key and
exact absent-or-revision/digest precondition. A successful remote CAS returns a
signed canonical state/receipt that is appended as evidence locally. If the
response is lost, the Coordinator resolves the idempotency key and reads the
remote current revision before deciding retry versus conflict. It never dual-
writes managed and remote stores, and a local operation status cannot override
the remote store's one authoritative target state.

Durable work is a PostgreSQL queue partitioned by queue class and consumer hash.
`SKIP LOCKED` is used only to claim queue rows, never for authority or general
reads. A partial ready index covers non-terminal `(queue_class,
next_attempt_at, effective_priority, created_at, id)` rows. Claims use database
time, a batch of at most 32, a monotonically increasing fencing token, a
30-second lease, and a 10-second heartbeat; long operations renew the same
token. Completion, cancellation, retry, or output collection must match the
current token and attempt. Lease loss makes the attempt's output unusable.

Per-consumer in-flight quotas plus deficit round-robin dispatch prevent a noisy
consumer from starving others. Priority ages at a bounded rate. Retry uses
task-class attempt limits and full-jitter exponential backoff capped at 15
minutes; exhaustion creates durable dead-letter evidence. An operator replay
creates a new linked attempt rather than editing history. Queue depth, oldest
ready age, database saturation, and sandbox capacity drive backpressure. The
API rejects new non-emergency asynchronous work with a retryable RFC 9457
problem before the database is endangered, while withdrawal and security-
response classes retain reserved capacity.

Outbox rows carry an aggregate ordering key and monotonic aggregate sequence.
Only the head unacknowledged sequence for a key may dispatch, while different
keys run concurrently. The initial Event Adapter is an authenticated pull feed
plus signed HTTPS CloudEvent webhook delivery. `published within 60 seconds`
means the event is committed to the resumable feed and its first delivery
attempt is recorded; an unavailable consumer endpoint does not erase the event
or block unrelated aggregates. Delivery is at least once with bounded retries,
an inbox/idempotency key, replay cursor, and dead-letter evidence.
`LISTEN/NOTIFY` may wake queue, outbox, or target-watch processes but is never
durability. Redis, Kafka, NATS, and cloud queues are optional Adapters only
after conformance proves they cannot weaken local transaction, idempotency,
ordering, replay, or evidence rules.

High-volume observation and evidence tables are monthly range partitions with
32-way consumer-hash subpartitions, `(consumer, target, sequence, time)` B-tree
indexes, and time BRIN indexes. Queue/outbox terminal rows are moved out of hot
partitions promptly. Partition-specific autovacuum/fill-factor settings and
bloat/runaway-transaction alerts are load-tested. At least 400 days stays in
the online evidence tier. Older immutable evidence and every historical
contract/trust root required for seven-year verification are written with a
signed archive manifest, digest-verified, then detached; deletion is allowed
only after restore sampling and retention policy permit it. Immutable schema,
descriptor, and trust objects may use bounded in-process digest caches; caches
and replicas are disposable and never serve current authority.

### 5. OCI Registry, blob, and archive storage

The self-hosted production reference is an active and a recovery-region
**Harbor 2.14.4** installation, each deployed with **Harbor Helm 1.18.4**.
Harbor resolves to commit `79a297f760eb9596c8693727b88c3c568f9c6302`;
the chart release resolves to commit
`3db4e9042833b3f620d6dbb72188b8707960aa5a` and chart SHA-256
`f74c4ac6858124d5efee577ff75364cdb05101e50ccabebfb4e85fbaf5fc4e40`.
Every stateless Harbor service has at least three zone-spread replicas, a
disruption budget, explicit resources, internal TLS, database-backed job logs,
and a region-local edge. Harbor supplies private-project RBAC, quotas,
retention, token service, audit, and Registry operations that raw Distribution
does not. Its database, cache,
job state, replication records, and vendor metadata are implementation
metadata, never Agent Delivery artifact, command, approval, or desired-state
authority. The local/protocol profile uses **CNCF Distribution 3.1.1** and
local-only **Adobe S3Mock 5.1.0**; neither local component is production
conformance evidence.

Harbor's internal single-instance database and Redis are forbidden in the HA
profile. Each Harbor region receives its own independent **PostgreSQL 15.18**
cluster under CloudNativePG 1.30.0: one primary, two synchronous standbys across
zones, `synchronous_commit=on`/`ANY 1`,
`postgresql.synchronous.dataDurability=required`,
`postgresql.synchronous.failoverQuorum=true`, TLS `verify-full`, a Harbor-only
role and database, continuous WAL through **Barman Cloud Plugin 0.13.0**,
immutable daily base backups, and tested point-in-time restore into a new
cluster. Aligned/non-aligned replica failure tests prove acknowledged metadata
survives promotion. The cluster shares no
PostgreSQL cluster, pool, role, storage, backup path, resource quota, or failure
domain with the Agent Delivery authority database or the SPIRE datastore.
Harbor migrations and serving connections use the direct writer service rather
than the Agent Delivery PgBouncer pool; migrations run under a maintenance
fence, and the sum of Harbor replica connection limits stays below 80% of the
dedicated database's configured capacity.

The Barman plugin control plane is installed beside the CloudNativePG operator
and requires **cert-manager 1.21.0**, commit
`b8f325e36f49626ba72d7efbe138c01a5e661d96`; the locked upstream
`cert-manager.yaml` SHA-256 is
`6e499c3f1ab356abe79a7853911f80cb09c213885bfdf81092fdff142ba63c4a`
and every referenced image is additionally digest-pinned. A dedicated
namespace-scoped `cnpg-plugin-ca` owns only the operator/plugin control-plane
trust. Its one-year CA key is RBAC-isolated, encrypted at rest, and backed up to
the approved secret manager; client/server leaves live 24 hours and renew by
16 hours. Bootstrap waits for cert-manager readiness, creates the CA and both
closed-name Certificates from locked manifests, and starts the plugin/operator
connection only after mutual verification. Rotation first distributes an
old-plus-new CA bundle, reissues both peers, proves bidirectional TLS, waits at
least two leaf lifetimes, and then removes the old CA. This CA is not the SPIFFE
trust domain and cannot issue application identities.

Each region also has a Harbor-only **Redis 7.2.14** Sentinel deployment from
digest-locked upstream images and product-owned manifests: three persistent
data nodes and three Sentinel voters spread across zones with quorum two, one
named master set, AOF `everysec`, `maxmemory-policy noeviction`, ACL
username/password, TLS server
authentication on client/replication/Sentinel channels, no plaintext listener,
strict network policy, bounded memory/eviction, and tested failover. Redis
Cluster mode is rejected because the chart does not support it. Harbor Helm
1.18.4 does not support Redis client-certificate authentication, so this one
vendor connection is an explicit exception to application mTLS: it requires a
pinned server CA, rotated ACL credentials delivered through the existing-secret
path, no public endpoint, and namespace/identity network isolation. Redis loss
freezes/fails in-flight Harbor background jobs; capacity alerts at 70%, blocks
new non-emergency publication/maintenance work at 80%, and fails writes closed
rather than evicting at the configured limit. A cold restore starts clean Redis
state and lets Agent Delivery durable actions re-read the exact Registry graph
before resubmission. Redis can never authorize or reconstruct a delivery
transition.

Harbor Helm 1.18.4's upstream test matrix stops before Kubernetes 1.35/1.36 and
does not certify Helm 4. The exact chart on Kubernetes 1.36.2/1.35.6 with Helm
4.2.3 is therefore a ByteDesk-owned certification target, not an upstream
compatibility claim. Install, rendered-manifest, upgrade, Gateway, storage,
database, Redis TLS, failover, and restore suites on both minors are blocking
release gates; an untested version substitution is not a fallback.

Because Harbor 2.14 predates Harbor's upstream signed-release-artifact policy,
the reference mirror records that supplier-provenance gap, verifies the release
tag/source and all component digests, produces its own SBOM/scans, and signs the
reviewed mirror as product infrastructure input. It does not mislabel the
upstream artifact as SLSA-qualified or silently resolve a newer image.

Distribution 3.1.1 advertises OCI Distribution Spec 1.0.1, not native 1.1
Referrers API support. The Registry Adapter therefore implements OCI Image and
Distribution 1.1.1 client semantics with the standard referrers-tag fallback
until a locked registry release passes the native Referrers conformance suite.
Fallback index mutation is serialized per repository/subject by a PostgreSQL
ordering key and verified by digest after write. Reference repositories reject
unmanaged writers; reconciliation repairs an interrupted index from the
authoritative exact descriptors. The ADR makes no claim that Harbor's embedded
registry or Distribution 3.1.1 natively implements OCI 1.1 Referrers.

Production Registry and archive storage use the **AWS S3 reference profile**:
strong read-after-write/list behavior, TLS, versioning, SHA-256 checksums,
bounded multipart/range operations, bucket-owner enforced ownership, blocked
public access, and workload-identity IAM. Each Harbor endpoint has exactly one
region-local live Registry bucket and encryption key. The evidence archive uses
separate primary and recovery Object Lock compliance buckets, different KMS
keys, retention-root manifests, legal holds, and cross-account recovery access.
Signing keys and storage-encryption keys are never shared.

The Registry Adapter synchronously pushes every immutable blob, manifest,
signature, referrer/fallback index, and immutable discovery tag through the OCI
HTTPS API of both Harbor endpoints. It then performs authenticated exact-digest
`HEAD`/pull verification from both endpoints before the application database
marks the descriptor graph eligible for publication or promotion, and records
the endpoint, descriptor, graph, and readback receipt for each region. Each
Harbor has a distinct private region-pinned publisher/probe data origin of the
form `https://publish.<region>.registry.<deployment-domain>` and a distinct
token/auth origin of the form
`https://auth.<region>.registry.<deployment-domain>`, which is that Harbor's
configured `externalURL`. Their certificate SANs, issuing CAs, Gateway
identities, AWS accounts, and regions are closed deployment-lock inputs. The
publisher/probe data route and the always-on private listener for its matching
auth origin require mTLS and accept only the publisher and recovery-probe
SPIFFE IDs.

Consumers use the stable data name
`https://registry.<deployment-domain>`, routed to exactly one fenced Harbor
region. That Registry challenges with the matching regional
`https://auth.<region>.registry.<deployment-domain>/service/token` realm. The
active region's consumer auth route permits only the Harbor token/OIDC endpoints
and authenticates approved consumer principals through the configured Harbor
identity/robot policy over TLS; it is not subject to the publisher-only mTLS
allowlist. The recovery consumer auth route is externally closed while its
private publisher/probe listener remains available. `RegionFence` switches the
stable data route, closes the old consumer auth route, opens the new regional
consumer auth route, and verifies the advertised challenge realm as one
operation before serving pulls. No Gateway rewrites a `WWW-Authenticate` realm.
This makes the two writes independently selectable, gives every challenged
client a reachable authorized token service, and proves a receipt was not
produced by resolving the same destination twice. The Adapter never writes
Harbor's internal S3 layout, copies a live bucket as an import mechanism, or
treats Harbor replication as the RPO control. A destination failure leaves the
publication staged and retryable.

Signed deployment configuration independently reconciles the same projects,
immutable-tag, retention, quota, robot-account, scanner, and garbage-collection
policy into both Harbor control planes before artifact writes. Credentials and
service identities remain region-specific. Harbor replication and asynchronous
S3 replication may repair drift as defense in depth, but neither creates
authority. Archive roots follow a separate Archive Adapter: each exact object
and signed root manifest is uploaded and digest-read from both Object Lock
buckets before retention-root advancement.

Each Harbor PostgreSQL cluster writes continuous WAL and daily base backups to
a Harbor-only encrypted regional backup repository through a dedicated Barman
workload identity and KMS key. Backup objects are copied to an immutable,
cross-account recovery-region repository, retain at least 35 days, and are
restore-sampled monthly; the signed ObjectStore configuration identifies the
exact primary/recovery repositories, key ARNs, identity, retention, and backup
set selected for PITR. The live Registry bucket, database backup repository,
and evidence archive are distinct.

Harbor's database-encryption `secretKey` is a non-rotatable recovery input. Its
exact bytes are versioned under KMS in a cross-region approved secret manager
and must be restored before the database is opened; generating a replacement
against an existing database is forbidden. Live-bucket KMS decrypt authority
and the cert-manager CA backup are likewise mandatory recovery inputs. During
a fully fenced cold restore, Harbor TLS, token-signing, core/jobservice,
Registry HTTP, database/Redis, robot, and publisher credentials may instead be
reissued only as one audited ceremony that invalidates old sessions, tokens,
uploads, and credentials and updates every dependent reference before probes.
No secret bytes or private keys enter the repository or signed declarative
configuration.

Public, product, and each consumer's private repositories/projects have
separate authorization scopes, retention roots, and service identities.
Cross-repository blob mounting is denied across those scopes. Private blob
redirects are disabled in the initial profile; public redirects, if enabled,
are HTTPS, exact-digest scoped, and expire within 60 seconds. Tags are immutable
per release and remain discovery only; application records and activation use
digests. Deletion and garbage collection run only in a fenced maintenance
window after the application reachability mark and signed retention root are
complete. Recovery-region publication opens only after `RegionFence` proves the
old endpoint unwritable and the recovery endpoint passes project-policy,
descriptor-graph, signature/referrer, tag, authorization, scanner, and
representative-pull checks. A cold regional rebuild fences writes and garbage
collection, restores Harbor PostgreSQL from the recovery repository to a
selected point, restores the exact `secretKey`, selects an S3 object set that is
a superset at or after that database point, starts Redis empty, reconciles
signed configuration and the audited restored/rotated secret set, and performs
the same checks before publication reopens. Orphan objects are later
garbage-collected; any database-referenced missing object is a hard failure.
Because Harbor schema downgrade/Helm rollback is unsupported, upgrades certify
the recovery stack first and recover forward through regional failover.

The application accesses all registries only through the Registry Adapter.
ECR, ACR, Artifact Registry, GHCR, or another implementation is supported only
after the same subject/referrer, digest, range, corruption, authorization,
quota, retention, replication, garbage-collection, and outage suite passes.
Registry vendor metadata and object-store metadata are never signed authority
and neither replaces PostgreSQL command/CAS state or the OCI manifest graph.

### 6. Signing, KMS, and workload identity

The reference cryptographic profile uses Cosign-compatible signatures and
ECDSA P-256/SHA-256 non-exportable keys. Product/public purposes use dedicated
product keys; roles 4 through 6 remain isolated per consumer as required by the
consumer-authority standard. **Role 5 (`consumer-authority-v1`) is never granted
to any Agent Delivery component.** The Consumer Authority Adapter verifies the
consumer's role-5 evidence; the API, Coordinator, compiler, renderer controller,
publisher, host, and Agent Delivery signers cannot issue it.

The first provider conformance profile is AWS KMS plus GitHub/Kubernetes OIDC
federation. Azure Key Vault and Google Cloud KMS are Adapter profiles, not
weaker fallback modes. Role-4 private-skill and role-6 deployment signers are
separate deployment modes, database roles, queues, and autoscaling/rate-limit
domains. Within each mode, every signing execution runs in an ephemeral
consumer-and-purpose cell with its own Kubernetes service account, SPIFFE ID,
cloud workload role, and KMS grant restricted to that consumer's one immutable
key purpose. Cells are created from product-controlled templates, process only
one consumer and purpose, and scale to zero; an identity or grant is never
reused across consumers or roles 4 and 6. A shared dispatcher may validate and
route an opaque signed request, but has no `Sign`, key-administration, or
assume-signer-role permission. No continuously running generic signer can reach
multiple consumers' keys. Product release, Registry publisher, Coordinator
desired writer, compiler/renderer controller, event publisher, backup, and
evidence archive identities are also distinct.

Every sign request identifies purpose, immutable key version, expected public
key/claims, exact digest, consumer scope where applicable, and a unique audited
request. Workloads receive only `sign` permission for the exact purpose/key and
cannot export, create, rotate, disable, schedule deletion, or edit policy. A
hosted consumer key is tenant-dedicated. Local development uses a process-local
ephemeral key generated for each test run; private key bytes are never written
to the repository or accepted as production conformance.

The hosted-key Adapter preflights provider key-count, alias, grant, IAM-role,
workload-identity, Kubernetes-object, request-rate, regional-availability, and
rotation quotas for 10,000 consumers before acceptance. It maintains
per-consumer/per-purpose rate limits and bounded KMS concurrency, treats
throttling as retryable without changing the requested digest, and prevents one
consumer from exhausting another's signing capacity. Rotation overlaps
immutable public-key versions for verification; it never rewrites prior
signatures. Signing keys, SPIFFE trust-domain keys, database TLS keys, and S3
encryption keys are purpose-distinct.

### 7. Production deployment substrate

The production reference must certify **Kubernetes 1.36.2**, with **1.35.6** as
the required previous-minor target, before either is represented as supported.
Helm is the delivered deployment format. The initial compatible network/edge
profile is **Calico
3.32.1**, **F5 NGINX Gateway Fabric 2.6.7**, and **Kubernetes Gateway API
1.5.1**. They publish a compatible stable matrix for this cluster; legacy
Ingress resources are not the product edge contract. An unverified CNI or
gateway is not substituted merely because a newer Kubernetes minor exists.
Kubernetes is an operations substrate, not product or agent authority.

The reference topology contains:

```text
Gateway API / external load balancer
          |
          v
3+ stateless agent-delivery-api replicas across zones
          |
          +---------- PostgreSQL 18.4 / CloudNativePG 1.30.0
          |             primary + two synchronous standbys
          |                    | WAL + snapshots + recovery replica
          |                    v
          |             fenced recovery region
          |
          +---------- purpose-separated worker-mode deployments
          |                    |
          |             renderer controller -> staged volumes
          |                    |
          |                    v
          |             one networkless gVisor sandbox per render
          |
          +---------- Registry Adapter
          |                +-> active Harbor 2.14.4 HA -> region-A S3
          |                +-> recovery Harbor 2.14.4 HA -> region-B S3
          |                    each -> dedicated PG 15.18 + Redis Sentinel
          |
          +---------- OIDC/WIF -> product or consumer KMS
          |
          +---------- SPIFFE mTLS -> connected application components
          |                +-> 3 SPIRE servers -> dedicated RDS + KMS/PCA
          |
          +---------- OTLP/mTLS -> HA OpenTelemetry gateways
```

API replicas are stateless and require no session affinity. Worker replicas are
stateless between leased actions, but each deployment runs exactly one
least-privilege mode. There is no elected global Promotion Coordinator leader:
the Coordinator is a domain process whose authority is exact target CAS.
Concurrent instances may attempt work, but only one current revision/digest
transition can commit; fencing prevents a stale worker from completing after
lease loss.

Agent Delivery-owned connected workloads use **SPIFFE/SPIRE 1.15.2** and
mutually authenticated TLS. Three `spire-server` replicas run across three
zones behind an internal TCP service in the active region. They share one trust
domain and one dedicated Amazon RDS for **PostgreSQL 15.18 Multi-AZ DB instance**
through the built-in SQL DataStore's `aws_postgres` mode, IAM database
authentication, and TLS `verify-full`; no password is configured. The serving
replicas set `disable_migration=true`. A separately authorized, exact-version
migration job performs schema migration before a rolling server update. The
SPIRE instance, role, storage, connection budget, backups, and failure domain
are isolated from both Agent Delivery and Harbor databases.

The frozen server profile sets X.509-SVID and agent TTL to one hour, CA TTL to
24 hours, `ec-p256`, JWT-SVID issuance disabled, audit logging enabled, and
attested-node staleness to zero. Each server maintains its own intermediate CA
key through `KeyManager "aws_kms"`, using a stable
`prod-<region>-<statefulset-ordinal>` identifier, tag-based key discovery, and a
reviewed exact key policy. Its EKS Pod Identity role has only the plugin's
required KMS create/alias/describe/public-key/sign/tag/delete operations,
`rds-db:connect` for one database user, AWS-IID validation reads, and permission
to assume one exact Private CA signer role; no static AWS credential is stored.

`UpstreamAuthority "aws_pca"` uses a pre-provisioned region-local subordinate
AWS Private CA with path length zero and ECDSA/SHA-256. Active and recovery
subordinate CAs chain to one separately administered root in the security
account, so regional recovery creates new non-exportable KMS keys and
intermediates under the same trust root; KMS/PCA private keys are never backup
artifacts. The product does not claim the SPIRE KMS plugin can select an
existing or multi-region key. Planned root/PCA rollover first publishes the old
and new roots, proves all streaming clients received both, rolls the PCA and
servers, waits longer than all old CA/SVID validity, and only then removes the
old root. Emergency root compromise removes trust immediately and accepts the
resulting outage.

Nodes attest through `NodeAttestor "aws_iid"` with block-device verification,
instance-profile selectors disabled, and membership restricted to the exact
EKS cluster. The initial profile admits only EC2 managed-node-group instances;
Fargate, Karpenter, and self-managed nodes require a separate attestor profile.
The agent is a tightly allowlisted hostPID/hostNetwork DaemonSet, while all
other product workloads are denied host networking and IMDS. Nodes require
IMDSv2 with hop limit one. The design records AWS IID's node-readable,
trust-on-first-use limitation: a compromised node is inside this assurance
boundary.

Each agent persists its key with SPIRE's disk KeyManager on a root-owned
mode-0700 encrypted host volume. AWS IID reports `CanReattest=false`; loss of
that state never enables automatic rebootstrap or `prune_tofu_nodes`. The
recovery runbook proves the exact EC2 instance still belongs to the allowlisted
cluster, evicts its stale attested-node record through the audited admin path,
and only then allows one new attestation. Normal replacement uses a new EC2
instance ID.

The Kubernetes Workload Attestor contacts only the CA-verified secure kubelet
port with a narrowly scoped bearer token; anonymous, read-only-port, and
`skip_kubelet_verification` modes are forbidden. Registration entries require
the exact node alias, namespace, service account, container name, and digest-
form container image selectors. Only selected pods receive the node-local
Workload API Unix socket. Clients maintain the streaming Workload API, consume
SVID and bundle updates together, reject expired material, and authorize an
exact peer-SPIFFE-ID/operation allowlist. The renderer sandbox receives no
SPIRE socket, SVID, Kubernetes token, or cloud identity.

A dedicated product identity-registration reconciler is the sole SPIRE Entry
API writer and sole non-break-glass `admin_ids` member. It reads versioned,
reviewed deployment/IaC identity manifests; portable definitions, skills,
consumer customization, and runtime configuration can never create or broaden
an entry. Registration changes append audit evidence. Bootstrap and break-glass
use separate witnessed local-socket ceremonies. The pre-production SPIRE
Controller Manager is not a hidden GA dependency.

SPIRE readiness must prove datastore access and a synthetic X.509 signing
operation; a conservative process-only liveness probe prevents restart storms
during RDS/KMS incidents. Datastore or signing failure removes a server from
service. Already delivered SVIDs may remain usable only until their one-hour
expiry; new issuance fails closed. Because SPIRE has no instantaneous X.509
revocation, services immediately deny a compromised SPIFFE ID in authorization
policy while the certificate ages out. There is no join-token, self-signed,
stale-SVID, alternate-trust-domain, or renderer-identity fallback.

RDS provides in-region Multi-AZ failover, 35-day point-in-time recovery,
cross-account snapshots, and a continuously monitored cross-region read
replica. Registration mutation stops when replica lag reaches four minutes;
lag alerts at two. Regional recovery is a `RegionFence` operation: fence source
issuance and Entry writes, prove the old endpoint unwritable, promote exactly
one recovery datastore, start recovery-region servers with new regional KMS
keys and the pre-provisioned subordinate PCA, reconcile entries against the
signed manifests, then prove node/workload issuance and bidirectional mTLS
before routing opens. Divergent restored datastores never run concurrently.
Quarterly drills must measure the identity plane inside the product's five-
minute RPO and 60-minute RTO; backup existence alone is not that evidence.

The trust domain assigns a different SPIFFE ID to each namespace, service
account, and deployment mode; authorization checks exact caller ID and
operation, not network location. Provider workload federation is separate for
KMS, S3, and Registry access. The application PostgreSQL profile uses TLS plus
dedicated rotating client-certificate/database roles. These SPIFFE IDs
authenticate Agent Delivery infrastructure only; they are not consumer users,
agents, roles, grants, credentials, or runtime workload identities.

External ingress requires TLS 1.3 and an authentication Adapter that validates
issuer, audience, expiry, sender/consumer binding, and operation scope before a
command enters the domain. Per-principal, per-consumer, and global rate limits
fail closed; forwarded identity headers are stripped at the edge. Agent
Delivery-owned service, PostgreSQL, Registry-gateway, and OTLP connections
reject plaintext, unknown trust domains, expired SVIDs/certificates, and wrong-
purpose audiences. Harbor-internal TLS and its narrowly documented external-
dependency authentication profiles remain governed by section 5; they do not
weaken application service mTLS.

Pods use dedicated service accounts, projected short-lived tokens only where
needed, default-deny CNI policy, restricted pod security, read-only roots,
dropped capabilities, seccomp `RuntimeDefault`, explicit resource limits,
topology spread, disruption budgets, and no automounted token by default. The
reference infrastructure lock pins Helm, NGINX Gateway Fabric, Gateway API,
Calico, CSI, SPIRE, CloudNativePG, Harbor, gVisor, and Collector artifacts by
platform digest.

The reference desired-state delivery path holds up to 25,000 authenticated
HTTP/2 server-sent-event watches, partitioned across API replicas, with exact
revision IDs and `Last-Event-ID` resume. A notification is only a wake hint: the
host performs an ETag conditional read from the writer endpoint and verifies
the canonical target state. On disconnect it makes a jittered conditional read
at least every 30 seconds; no cursor gap is accepted. Three replicas are sized
for at least 8,334 watches each plus reconnect surge, and HPA adds replicas on
connections, request latency, and CPU. This path and fallback are load-tested
against the desired-state p95 detection and 99.95% read-availability targets.

### 8. Renderer sandbox

Production renderer execution uses containerd with **gVisor `runsc`
`release-20260714.0`**, checksum-pinned independently for `amd64` and `arm64`,
through an immutable Kubernetes `RuntimeClass`. The AWS reference node profile
uses the `systrap` platform and `--network=none`; a KVM profile is a separately
tested lock entry, not an automatic fallback. Dedicated tainted sandbox nodes
pre-pull exact renderer image digests. Admission rejects a missing/wrong
RuntimeClass, runtime checksum, image digest, node profile, no-token setting,
volume policy, or network-none control. It never falls back to `runc`.

A connected Go renderer controller owns the data plane:

1. it claims a fenced attempt and verifies every canonical input and payload
   digest;
2. it materializes a content-addressed encrypted per-attempt input volume and
   an empty encrypted output/temp volume, then relinquishes both mounts;
3. a single-container gVisor Pod mounts input read-only/no-exec and output/temp
   writable/no-exec; its signed launcher creates private protocol pipes, caps
   the renderer response/diagnostics into output files, keeps content off
   container stdout/stderr, runs the digest-pinned renderer once, and exits;
4. only after Pod termination, a collector with the same current fencing token
   mounts output read-only, checks the closed inventory, schemas, sizes, modes,
   and digests, and moves verified bytes to staging; and
5. publication commits only after staging and dual-region object verification;
   the per-attempt volumes are cryptographically erased/deleted on success,
   failure, cancellation, timeout, or lease loss.

Stale-attempt output is unusable even if its bytes are otherwise valid. The
sandbox has no init container or sidecar and cannot contact the controller,
OpenTelemetry, PostgreSQL, OCI, KMS, DNS, Kubernetes API, cloud metadata, or any
consumer system. It receives no ingress/egress, service-account token, secret,
SPIFFE socket, host namespace/path, device, socket, or privilege. It runs as a
non-root UID/GID with no privilege escalation, all capabilities dropped,
read-only root, and an explicit seccomp profile. Signed release limits bound
memory, CPU, PIDs, file count, expanded bytes, archive depth, temporary disk,
and wall time; execution-spy tests prove input files and hooks are never invoked,
and canary secrets prove renderer responses and diagnostics never enter CRI,
node, Kubernetes-event, or telemetry logs.

The capacity reference distinguishes accepted/in-flight actions from active
sandboxes. It proves 1,000 concurrent actions with a published workload mix and
admits only the number of simultaneous 4-GiB-memory/20-GiB-disk maximum renders
for which nodes and encrypted staging capacity are reserved; remaining work is
fairly queued without breaching its action SLO. A separate worst-case test
proves admission/backpressure rather than pretending 1,000 maximum renders fit
unboundedly. HPA/node autoscaling uses queue age, eligible ready work, active
sandboxes, staging capacity, and pre-pull readiness.

A self-hosted alternative must provide an equivalent checksum-pinned
`runsc`/microVM isolation and staging profile and pass the same suite. Ordinary
in-process execution, `chroot`, Docker default isolation, and language virtual
environments alone are not conforming.

### 9. Configuration and secrets

Non-secret configuration is a closed, versioned application configuration
object supplied through an immutable mounted file plus explicitly documented
environment overrides. Unknown keys fail startup. Secret values are delivered
through workload identity or read-only secret-store CSI files under
`/run/secrets`; they are never stored in configuration, environment-variable
dumps, command lines, logs, receipts, or repository files.

Consumer functional configuration contains only opaque secret references. Only
the consumer runtime resolves those references. Agent Delivery can validate the
reference syntax and current consumer authority digest but cannot read the
credential value.

### 10. Observability and audit

Connected Go and Python controller components emit OpenTelemetry traces,
metrics, and structured JSON logs through a curated **OpenTelemetry Collector
Contrib 0.156.0** distribution whose component set and image digest are locked.
Renderer sandboxes emit no OTLP and have no network; the connected controller
records attempt lifecycle, resource termination, and verified output telemetry.

At least three zone-spread Collector gateways receive authenticated OTLP/mTLS.
Cluster/node collection uses a separately scoped DaemonSet where required.
Gateways use encrypted persistent file queues, bounded memory, retry/backoff,
load balancing, and health-based disruption budgets sufficient to buffer 24
hours at the required peak rate. Collector administration and diagnostics are
not publicly reachable. The AWS production profile exports metrics to Amazon
Managed Service for Prometheus, traces to AWS X-Ray, and logs to CloudWatch
Logs; a different backend is an operations Adapter and must preserve query,
retention, residency, alert, and outage behavior. Local development uses locked
non-production Prometheus and trace/log viewers.

Trace context, correlation ID, causation ID, action ID, rollout ID, and aggregate
revision propagate across HTTP, PostgreSQL actions/outbox, controller work,
Registry/KMS Adapters, host observations, and capability evidence. Incoming
baggage is discarded unless a key is on a small product-owned allowlist. Metric
names, log fields, and bounded labels are versioned. Consumer IDs use a stable
non-reversible telemetry token where aggregation is required; target IDs,
artifact digests, secret references, raw private payloads, credentials, and
authority envelopes are excluded from labels and ordinary logs. Automated
redaction fixtures and cardinality budgets fail CI and deployment canaries.

The initial operations retention is at least 30 days for metrics, 14 days for
sampled traces, and 30 days for logs; security/administrative audit and delivery
evidence follow the 400-day online/seven-year archive contract instead. Shipped
dashboards and alerts cover every published SLI plus queue age/depth, outbox
lag, target-watch reconnects, Postgres quorum/replication/connection/bloat,
Registry and dual-region object checks, KMS throttling, sandbox admission/
escape signals, Collector drops, and region-fence state.

Telemetry export failure never becomes an alternate control decision. Gateways
buffer and alert; after the bounded queue is exhausted, ordinary telemetry may
be sampled/dropped with an explicit loss counter and incident, while commands
continue only if required append-only product audit was committed in the same
authoritative transaction. Failure to persist required audit blocks the command.

### 11. Availability, backup, and disaster recovery

The reference production profile uses at least three availability zones:

- API and worker replicas are zone-spread with disruption budgets and rolling
  upgrades;
- the Agent Delivery and Harbor PostgreSQL clusters use synchronous in-region
  replication with no acknowledged single-node-only commit, while the SPIRE
  RDS datastore uses Multi-AZ failover;
- Registry publication requires verified OCI API writes to both region-local
  Harbor endpoints; archive storage requires verified writes to both Object
  Lock buckets, with asynchronous replication only as defense in depth;
- a continuously replaying CloudNativePG application recovery cluster and a
  continuously monitored SPIRE RDS cross-region replica supplement continuous
  WAL, daily immutable base backups, and at least 35 days of PITR; and
- KMS key policy, revocation state, contract bundles, trust snapshots, desired
  state, outbox/inbox positions, registry graph, and evidence are restored and
  checked as one graph.

Recovery-cluster replay lag and last verified WAL archive age alert at two
minutes. At four minutes the reference profile stops accepting state-changing
commands and new signing until the recovery path catches up, preserving the
five-minute region-loss RPO. Object/artifact transitions already require both
region copies, so asynchronous S3 replication is never the RPO mechanism.

Regions are active/passive and carry a monotonically increasing `region_epoch`.
Every action claim, signer request, object publication, desired-state write, and
outbox dispatch carries the active epoch. Region failover is a two-person,
signed disaster operation through a `RegionFence` Adapter; CloudNativePG's
primary lease alone is insufficient. The initial AWS fence profile performs,
in order:

1. remove the source region from ingress and deny new external connections;
2. revoke/deny source-region workload roles and KMS grants, S3/Registry writes,
   and database/backup automation through the independent cloud control plane;
3. network-isolate and stop the source application and database nodes;
4. collect AWS control-plane and endpoint probes proving the old writer and
   identities cannot write;
5. verify application and SPIRE recovery positions, both Harbor object graphs,
   trust/revocation roots, inbox/outbox cursors, and the last committed epoch;
6. promote exactly one application database and one SPIRE datastore, append a
   higher KMS-signed fence attestation/epoch, start workloads bound to them,
   verify the already independent recovery Harbor plane, then switch ingress;
   and
7. keep signing and promotion closed until graph, single-writer, consumer-key,
   target-watch, and synthetic transaction gates pass.

An unreachable source region is never assumed dead. If independent cloud
fencing cannot be proven, recovery remains read-only. The old region cannot
rejoin; it is destroyed/reseeded from the new primary and current epoch. KMS or
consumer-authority unavailability permits already active verified releases to
continue under incident policy but does not permit new signing/promotion.

Automated in-region failover and normal regional-service restoration target no
more than 15 minutes so one event does not consume the 99.95% monthly budget;
the published disaster-recovery hard bound remains RTO <=60 minutes. Quarterly
fence/failover and restore drills must demonstrate both, plus RPO <=5 minutes.
Declaring the topology is not evidence that any objective is met.

### 12. Local development and test topology

`docker compose` is the supported developer bootstrap for PostgreSQL 18.4,
Distribution 3.1.1, local-only Adobe S3Mock 5.1.0, OpenTelemetry Collector
0.156.0, and locked lightweight telemetry viewers. It binds only loopback ports
by default, uses generated disposable credentials, has no route to production,
and never reuses production trust. A deterministic `make dev-up`, `make test`,
`make verify`, and `make dev-down` surface is required.

The Go API/worker/CLI may run on the host against local services. Trusted
renderer fixture tests may run in a normal container for developer speed, but
that backend refuses untrusted packages and cannot produce sandbox-conformance
evidence. gVisor isolation conformance runs on dedicated Linux CI. WayFlow
compatibility runs only in its separate certification profile. Local success
cannot satisfy production sandbox, KMS, multi-zone, restore, or scale gates.

### 13. Supported-platform and compatibility policy

- Server and renderer products: Linux `amd64` and Linux `arm64`.
- CLI: Linux, macOS, and Windows on `amd64` and `arm64`. Every platform can
  canonicalize, inspect, verify, manage exact descriptors, call the API, and
  request remote validation/rendering. Local validation/rendering of untrusted
  content requires the locked Linux gVisor Sandbox Adapter. macOS/Windows, or a
  Linux host without that Adapter, returns the stable `sandbox_unavailable`
  failure instead of using host Python or silently degrading isolation.
- PostgreSQL: major 18 reference profile; a future major requires migration and
  compatibility evidence before becoming the default.
- Kubernetes: 1.36.2 and 1.35.6 are the initial certification targets. Support
  activates only after the complete locked component matrix passes upgrade,
  network, storage, identity, sandbox, and restore tests; later security patches
  must pass the same gate.
- Python renderer runtime and every renderer dependency are image- and
  hash-pinned; the control plane never uses the host Python installation.
- Registry, KMS, Git, consumer, and desired-state variants are supported only
  through a named conformance profile with exact version evidence.

### 14. Initial component baseline

The first implementation starts from this reviewed version set. Released
images, charts, binaries, wheels, node images, and CRDs are still consumed by
per-platform digest/checksum from `deploy/reference-components.lock.json`; a
version below is never permission to resolve a mutable tag.

| Component | Initial exact release | Scope |
|---|---:|---|
| Go | 1.26.5 | Control plane, host, CLI, tools |
| CPython | 3.13.14 | Isolated Agent Spec worker |
| PyAgentSpec | 26.1.2 | Production Agent Spec validation |
| WayFlow Core | 26.1.2 | CI/certification compatibility only |
| pgx | 5.10.0 | PostgreSQL driver |
| sqlc | 1.31.1 | Reviewed SQL projection |
| goose | 3.27.2 | Forward migration runner |
| PgBouncer | 1.25.2 | Application PostgreSQL connection pools |
| Cosign | 3.0.6 | Signing and verification |
| actions/attest | 4.2.0 (`f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6`) | SLSA v1 provenance in the trusted reusable workflow |
| GitHub CLI | 2.96.0 | Connected and offline attestation verification |
| PostgreSQL (Agent Delivery) | 18.4 | Application authority |
| CloudNativePG | 1.30.0 | PostgreSQL HA/backup operator |
| Kubernetes | 1.36.2 / 1.35.6 | Current/previous-minor certification targets |
| Helm | 4.2.3 | Deployment packaging/client |
| Calico | 3.32.1 | CNI and default-deny network policy |
| F5 NGINX Gateway Fabric | 2.6.7 | External edge control/data plane |
| Kubernetes Gateway API | 1.5.1 | Stable edge resources |
| AWS EBS CSI driver / chart | 1.62.0 / 2.62.0 | Encrypted staging/database volumes |
| CSI external-snapshotter | 8.6.0 | Volume snapshot controller |
| Secrets Store CSI Driver | 1.6.0 | Read-only secret-file delivery |
| AWS Secrets Store CSI provider | 3.1.1 | AWS secret reference provider |
| cert-manager | 1.21.0 | Barman plugin control-plane certificates |
| SPIRE | 1.15.2 | SPIFFE workload identity/mTLS |
| PostgreSQL (SPIRE RDS) | 15.18 | Dedicated SPIRE registration datastore |
| CloudNativePG PostgreSQL image | 18.4-standard-trixie | Database image |
| Harbor | 2.14.4 | Production self-hosted Registry profile |
| Harbor Helm chart | 1.18.4 | Harbor HA deployment |
| PostgreSQL (Harbor) | 15.18 | Dedicated Harbor metadata database |
| Redis | 7.2.14 | Dedicated Harbor Sentinel cache/job profile |
| Barman Cloud Plugin | 0.13.0 | CloudNativePG WAL/base backup and recovery |
| CNCF Distribution | 3.1.1 | Local/protocol Registry profile |
| Adobe S3Mock | 5.1.0 | Local-only S3 integration profile |
| gVisor | release-20260714.0 | Production renderer sandbox |
| OpenTelemetry Collector Contrib | 0.156.0 | Curated telemetry gateways/agents |

The gVisor lock starts with the upstream SHA-512 values
`75c092fe87d84078f06ac40937cb5207fb5a1a92511b38b4790c915801555daadc59fef33de8db4dd92e1892a6de390c8a2e390a7a3bd0e2d3731d9ed6a3a6e8`
for `x86_64/runsc` and
`ee39fa48121797db60919dacb77145d604c9a54616323a00304f8482fca87af20e8e78b079cb193ab7bef7230ad3f79096a3491e12c09ba11625c7be5130e084`
for `aarch64/runsc`, plus
`7ece190ec2ee5d1218c50a1452baab095e2005553201a0775196a99c095b26b6b7883a6a0fab5745c413dcc0fe050983060cd440bf3b91b9b60143ba57b04599`
for `x86_64/containerd-shim-runsc-v1` and
`88f56fe83636b58f22eb8874132f387ec2b0feafea7c4475f1fd0f86b17e3feade2495e551d5aefe703051fe7bfb910be547cff854f15530186561b05e549c1b`
for `aarch64/containerd-shim-runsc-v1`. CI verifies upstream release
signatures/attestations where available, mirrors the exact bytes, and signs the
complete lock as product release input.

The initial checksum seeds also include Helm 4.2.3 Linux tar SHA-256
`e9b88b4ee95b18c706839c28d3a0220e5bc470e9cd9262410c90793c45ff8b7c`
for `amd64` and
`21abd9354d39b2cd79a8d76be6912cd137a983cbf997193503fb8a6a6e2f2785`
for `arm64`; EBS CSI chart 2.62.0 SHA-256
`19a193081807d18af43871a3735350b0c115c6c240a5bfc990c83e97e85ce460`;
Secrets Store CSI chart 1.6.0 SHA-256
`63a35e803d78a07df990411fc2df66d1f9426ed4508cc5794b5b4f125bb50744`;
and AWS Secrets Store provider chart 3.1.1 SHA-256
`985aaf5c533873d14473aad878f87d1efabb14c6a7570c7e5029572c0e31f64c`.
Per-image platform digests and configuration hashes remain mandatory in the
signed lock.

GitHub CLI 2.96.0 archive SHA-256 values start as
`83d5c2ccad5498f58bf6368acb1ab32588cf43ab3a4b1c301bf36328b1c8bd60`
for Linux `amd64`,
`06f86ec7103d41993b76cd78072f43595c34aaa56506d971d9860e67140bf909`
for Linux `arm64`,
`4bd449df9ad639391bc62b8032546f0fe9edcd8526e06682a4f88abd8c5d163c`
for macOS `amd64`,
`f23a0c37d963aacc3bed703ccbd59b41c5ca22101fab7f00eb2b7cad23aba463`
for macOS `arm64`,
`c2d6acc935cd2f00e2144d7e036d5cd82e6b6bd5594e8c75aa75ef2a4ed6aac3`
for Windows `amd64`, and
`c517e0b32c98a4ba90ac95af8d12cc3ac55781ab4ab72f9a91ce3de0541d2b09`
for Windows `arm64`. The upstream signed checksum file and release metadata are
mirrored with the archives and included in the component lock.

The initial multi-platform CloudNativePG PostgreSQL image descriptor is
`ghcr.io/cloudnative-pg/postgresql@sha256:802cb43a4d482acf1037b418e421c865b16959ba22e07f16fc003e06cb21084c`;
deployments resolve and retain its platform child digest as well.

The initial Harbor metadata database descriptor is
`ghcr.io/cloudnative-pg/postgresql:15.18-standard-trixie@sha256:801cf5563ffdc8d9a988e23a6865851ce2b5e140aa4b21aae430aafad32ed09e`;
the Redis descriptor is
`docker.io/library/redis:7.2.14@sha256:f0707c78ea880b293ccdeb410c9c0a8ccae93fe7128799b751333a698b0a39a7`;
the PgBouncer descriptor is
`ghcr.io/cloudnative-pg/pgbouncer:1.25.2@sha256:3610a667a8965bc87d84381fd16a367e59786b6e172c927d11c8fdce2da61ca5`;
and the backup plugin descriptor is
`ghcr.io/cloudnative-pg/plugin-barman-cloud:v0.13.0@sha256:71589dbac582333442812b07b31f7ea4d00324a8358aac7ca507dabf9f4b6c96`.
Every deployment additionally retains its resolved platform child digest.

## Consequences

### Positive

- PostgreSQL makes command state, durable work, idempotency, evidence, and
  outbox publication atomic without a second distributed authority system.
- Go supplies compact cross-platform binaries and uses the strongest ecosystem
  fit for OCI, Kubernetes, Sigstore, and host reconciliation.
- Python remains isolated where the official Agent Spec ecosystem requires it.
- gVisor provides a materially stronger renderer boundary than process-only or
  default-container isolation.
- One reference topology makes SLO, scale, DR, upgrade, and support evidence
  reproducible while Adapter contracts preserve deployability elsewhere.

### Costs

- The product maintains both Go and a small isolated Python toolchain.
- PostgreSQL queue capacity and table growth require explicit partitioning,
  archival, fairness, and load evidence.
- Fresh gVisor sandboxes add scheduling latency and require warm-node capacity.
- A multi-zone PostgreSQL/registry/object/KMS deployment is operationally
  substantial, but that cost reflects the published durability and sovereignty
  commitments.

## Rejected alternatives

| Alternative | Reason rejected for the reference profile |
|---|---|
| Python control plane | Expands the runtime/dependency surface and weakens the single-binary host/CLI story; Python remains isolated for Agent Spec compatibility |
| Node/TypeScript control plane | Strong API tooling but weaker OCI/Kubernetes/host-agent fit than Go for this product |
| .NET control plane | Viable enterprise stack, but larger runtime/container surface and less direct alignment with the OCI/Sigstore reference implementations |
| Microservices from the start | Creates distributed transactions before measured scale requires them and conflicts with the accepted modular-monolith posture |
| Kafka/NATS/cloud queue as required authority | Adds an avoidable second durable state system; PostgreSQL actions/outbox meet the reference workload and preserve atomic acceptance |
| Redis locks or queue | Cannot be desired-state or command authority and adds failure modes without required durability value |
| Raw Distribution as the production Registry | Sound protocol substrate but does not itself supply the required tenant project policy, quota, retention, replication, audit, and operations plane; retained for local/protocol conformance |
| Asynchronous object replication as the RPO control | Does not guarantee the five-minute region-loss RPO; authoritative object transitions require dual-region digest verification |
| In-process renderer plugins | Violates the compiled allowlist and untrusted-input execution boundary |
| Default container isolation only | Does not provide the defense-in-depth required for hostile archives and renderer inputs |
| WASM-only renderer sandbox | Attractive isolation but cannot host the required pinned Python Agent Spec validation stack without a second execution model |
| SLSA GitHub Generator 2.1.0 plus slsa-verifier 2.7.1 | Emits the historical v0.2 predicate and carries embedded legacy Cosign verification dependencies; the SHA-pinned reusable workflow plus `actions/attest` emits the current SLSA v1 predicate and supports exact connected/offline verification policy |
| One cloud provider as a portable contract | Violates consumer neutrality; AWS is only the first reference KMS/object profile |

## Verification required

Task-specific implementation must prove:

- locked Go/Python/tool dependencies and reproducible clean builds;
- trusted reusable-builder isolation; SLSA v1 subject/source/ref/workflow/digest
  verification; connected/offline parity; and malicious attestation-bundle
  substitution denial;
- module-boundary and generated-drift checks;
- PostgreSQL CAS, serializable retry, RLS, idempotency, job fencing,
  outbox/inbox, migration, backup, restore, and region-fence behavior;
- both Harbor HA regions and their isolated PostgreSQL/Redis dependencies, the
  Distribution local profile, OCI 1.1.1 native/fallback referrer behavior,
  synchronous dual-endpoint digest verification, corruption, authorization,
  retention, garbage collection, restore, and outage behavior;
- KMS/WIF least privilege, purpose/key/consumer isolation, rotation, revocation,
  and cross-consumer denial;
- Kubernetes 1.36/1.35 deployment, upgrade, disruption, SPIRE server/datastore/
  KMS/PCA HA and regional recovery, AWS-IID node-state recovery, exact workload
  identity, database-role isolation, and default-deny network behavior;
- gVisor staged-volume isolation, no-network/no-secret/no-hook, attempt fencing,
  resource, archive, and execution-spy conformance on both server architectures;
- target SSE/resume/ETag fallback and 25,000-host reconnect behavior;
- OpenTelemetry HA/buffering/outage, propagation, label cardinality, redaction,
  and 100% required administrative audit production; and
- the complete capacity, SLO, RPO/RTO, security-response, support, and 30-day
  readiness gates before GA.

## References

- [Go release history](https://go.dev/doc/devel/release)
- [Python 3.13 releases](https://www.python.org/downloads/)
- [PyAgentSpec 26.1.2](https://pypi.org/project/pyagentspec/26.1.2/)
- [WayFlow Core 26.1.2](https://pypi.org/project/wayflowcore/26.1.2/)
- [GitHub: SLSA v1 Build Level 3 with artifact attestations and reusable workflows](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/increase-security-rating)
- [actions/attest 4.2.0](https://github.com/actions/attest/releases/tag/v4.2.0)
- [GitHub CLI 2.96.0](https://github.com/cli/cli/releases/tag/v2.96.0)
- [GitHub CLI attestation verification](https://cli.github.com/manual/gh_attestation_verify)
- [GitHub offline attestation verification](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline)
- [SLSA provenance v1](https://slsa.dev/spec/v1.2/provenance)
- [PostgreSQL 18 documentation](https://www.postgresql.org/docs/18/)
- [CloudNativePG 1.30 release](https://cloudnative-pg.io/releases/cloudnative-pg-1-30.0-released/)
- [Kubernetes 1.36 release](https://kubernetes.io/releases/1.36/)
- [Helm releases](https://github.com/helm/helm/releases)
- [Calico Kubernetes requirements](https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements)
- [NGINX Gateway Fabric technical specifications](https://docs.nginx.com/nginx-gateway-fabric/overview/technical-specifications/)
- [gVisor Kubernetes integration](https://gvisor.dev/docs/user_guide/quick_start/kubernetes/)
- [gVisor installation and version pinning](https://gvisor.dev/docs/user_guide/install/)
- [Harbor 2.14 documentation](https://goharbor.io/docs/2.14.0/)
- [Harbor Helm 1.18.4](https://github.com/goharbor/harbor-helm/releases/tag/v1.18.4)
- [PostgreSQL 15.18 release](https://www.postgresql.org/docs/release/15.18/)
- [Redis 7.2.14 release](https://github.com/redis/redis/releases/tag/7.2.14)
- [PgBouncer 1.25.2 release](https://github.com/pgbouncer/pgbouncer/releases/tag/pgbouncer_1_25_2)
- [Barman Cloud Plugin 0.13.0](https://github.com/cloudnative-pg/plugin-barman-cloud/releases/tag/v0.13.0)
- [cert-manager 1.21.0](https://github.com/cert-manager/cert-manager/releases/tag/v1.21.0)
- [CNCF Distribution 3 deployment](https://distribution.github.io/distribution/about/deploying/)
- [SPIRE 1.15.2 release](https://github.com/spiffe/spire/releases/tag/v1.15.2)
- [SPIRE server HA](https://spiffe.io/docs/latest/planning/scaling_spire/)
- [SPIRE SQL datastore](https://github.com/spiffe/spire/blob/v1.15.2/doc/plugin_server_datastore_sql.md)
- [SPIRE AWS KMS KeyManager](https://github.com/spiffe/spire/blob/v1.15.2/doc/plugin_server_keymanager_aws_kms.md)
- [SPIRE AWS Private CA UpstreamAuthority](https://github.com/spiffe/spire/blob/v1.15.2/doc/plugin_server_upstreamauthority_aws_pca.md)
- [SPIRE AWS IID NodeAttestor](https://github.com/spiffe/spire/blob/v1.15.2/doc/plugin_server_nodeattestor_aws_iid.md)
- [SPIRE Kubernetes WorkloadAttestor](https://github.com/spiffe/spire/blob/v1.15.2/doc/plugin_agent_workloadattestor_k8s.md)
- [AWS S3 Replication Time Control](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-time-control.html)
- [OpenTelemetry Collector deployment](https://opentelemetry.io/docs/collector/deploy/)
