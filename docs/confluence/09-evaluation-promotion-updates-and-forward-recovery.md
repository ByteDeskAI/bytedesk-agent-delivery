# Evaluation, promotion, updates, and forward recovery

## Promotion is a durable process

An artifact becoming available does not make it active. Promotion is an
observable, retryable, idempotent process whose complete evidence is retained.
The process separates portable compatibility, consumer evaluation, artifact
trust, runtime canary, and final promotion.

Installation, candidate preparation, target rollout, and host reconciliation
use separate state machines defined by
[Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md). Candidate
preparation is:

```text
received -> fetching -> fetched -> validating -> validated
validated -> quarantined -> evaluating
evaluating -> awaiting_approval | approved | rejected
awaiting_approval -> approved | rejected
approved -> compiling -> compiled -> signing -> prepared
```

`prepared`, `rejected`, `cancelled`, `superseded`, and `failed` are terminal for
that candidate. A distinct rollout begins `pending -> staging -> staged ->
preflight_passed` and follows the harness's certified isolated-candidate or
guarded in-place mode. A pre-switch failure is `failed_pre_activation`; a
post-switch failure is `recovery_required`, never a direct `rolled_back`
transition.

Every transition records actor, correlation, exact revision-and-digest CAS
precondition, immutable predecessor, input/output and schema digests, policy
result, and time. Illegal, stale, duplicate, or backward transitions are denied
deterministically. Retryable failures remain in phase with bounded attempts and
backoff. Candidate cancellation is legal only before signing begins. Rollout
cancellation is legal only before activation authorization.

## Validation gate

Before evaluation, the candidate must pass:

- closed Draft 2020-12 schemas from the exact signed offline contract bundle;
- catalog and source trust policy;
- official pinned Agent Spec validation;
- non-authority and package safety policy;
- source, binding/customization, renderer, and public/private skill digest
  integrity;
- withdrawal and revocation checks;
- consumer, tenant, target, and predecessor scope; and
- schema compatibility with the installed binding.

Functional Agent Spec and harness changes use only the ordered
`bytedesk.json-patch/1` add/replace/remove profile. File and skill operations
use their separate closed schemas with canonical paths/package IDs and exact
absence/current-digest preconditions. Any path, schema, operation, or digest
failure rejects the complete delta without partial output.

Structured candidate identity is computed only after conversion to the JSON
data model and RFC 8785 JCS serialization. Contract-authoring YAML is accepted
only through the restricted YAML 1.2 JSON-compatible parser and never supplies
the semantic digest or signed bytes; any integrity reference to retained
authoring YAML is provenance/storage-integrity evidence only, never semantic
identity, artifact authority, or activation authority.
Referenced arbitrary payload files, including files named `.yaml` or `.json`,
are verified as exact raw bytes rather than parsed based on extension.

A private binding may describe desired MCP servers, tools, provider/model/harness
configuration, opaque secret references, and safe regular-file operations. It is
rejected before evaluation if it attempts to make that configuration
authoritative, embeds a raw secret, grant, role, workload identity, hook, unsafe
entry, or undeclared fetch, selects an untrusted skill, or weakens approval.

## Quarantine

Quarantine isolates unapproved content while scans and evaluations run. Source
instructions can be inspected and rendered in a confined build environment,
but cannot reach a consumer runtime.

Skills are evaluated independently. Every new or changed public or private skill
digest remains quarantined even if the base definition change is compatible.
Skills may contain arbitrary regular files, including scripts and binaries, but
the delivery pipeline never executes them. Runtime execution requires signed
`bytedesk.skill-approval/1` evidence for the exact digest plus a declared sandbox and current
authorization. The definition can continue without the skill when its semantics
make the skill optional only after an explicit canonical binding remove
operation records the resulting effective set. An unapproved selected skill
fails closed and is never silently omitted.

## Compatibility classification

The renderer produces a signed compatibility result over the complete effective
input, including private customization and selected skills when applicable:

- **exact**: target representation preserves the selected semantics;
- **compatible with warnings**: approved equivalent behavior with visible
  structured warnings;
- **lossy**: behavior cannot be preserved exactly and requires explicit human
  acceptance; or
- **unsupported**: no valid target can be produced.

Automatic promotion permits only policy-approved exact or non-lossy compatible
results. An exact renderer-release manifest or executed product-distribution
change is part of the candidate and is never hidden inside a source-only
update. The candidate records the executing worker/platform, embedded allowlist,
renderer schema, and immutable `product-release-v1` policy digests.

## Evaluation contract

Product evaluation can include deterministic schema, policy, safety, render,
and regression checks. Consumer-specific evaluation is supplied through an
Adapter and may include role behavior, tone, task fixtures, model policy,
business approval, and compliance checks.

Evaluation input names exact source, binding/customization, regular-file delta,
public/private skill, renderer, model-policy, sandbox-policy, and fixture
digests. Output is a signed or authenticated attestation with:

- evaluator identity and version;
- fixtures and environment;
- scores, thresholds, warnings, and failed cases;
- reproducibility information;
- human approval where required; and
- expiration or freshness constraints.

Evaluation does not grant runtime authority. A successful tool-use fixture
uses consumer-provided test grants in an isolated scope and cannot become a
production MCP grant.

## Automatic compatible updates

A stable-channel update can be proposed automatically only when all conditions
hold:

- catalog, source, signer, and channel are trusted;
- the exact current binding revision and canonical digest match;
- Agent Spec and renderer compatibility are non-lossy;
- the renderer itself is approved for automatic updates;
- the optional skill digest set is unchanged;
- no authority, credential, remote code, provider, or approval-weakening field
  appears;
- consumer evaluation and policy explicitly permit automation;
- protected change and signed bot identity requirements pass; and
- later compilation, staging, canary, and health gates pass.

Breaking, major, lossy, trust-policy, skill-changing, system-package, or
authority-adjacent updates require human approval. A consumer can require human
approval for every change.

## Update proposal and compare-and-swap

Automation produces a reviewable proposal or append-only binding revision. It
uses the required `{kind: match, revision, digest}` precondition; initial
creation uses `{kind: absent}`. The accepted immutable record separately names
its predecessor. Omitted, null, wildcard, digest-only, lease-based, or
break-glass bypasses are invalid. Acceptance fails if a human, another update,
or lifecycle change has advanced the binding.

The system does not rebase over an unknown concurrent change or overwrite a
human edit. A new proposal must be generated from the new current state.

## Private deployment compilation

After approval, the compiler verifies a fresh signed
`bytedesk.consumer-authority/1` snapshot rather than using the state captured
when the catalog candidate first appeared. It binds:

- exact public source, tenant-free public-render lineage, and accepted
  binding/customization;
- exact public and private skills plus signed approval evidence for every
  effective digest;
- current organizational profile and lifecycle;
- current policy and approval result;
- current MCP/tool/resource grant digest;
- desired private tools/MCP/provider/model/harness configuration and opaque
  secret references from the binding;
- current provider authorization and credential-version references resolved by
  the consumer, never raw secret values;
- current executable-skill approval and sandbox policy;
- target runtime and stable slot; and
- exact renderer-release manifest, actual executed distribution/worker,
  platform, embedded allowlist, renderer-schema, compiler, and immutable
  product-release policy identities.

The compiler applies the functional Agent Spec delta and safe regular-file
operations, resolves and verifies the approved skills, constructs the complete
effective package, and performs a full deterministic render. It embeds the
effective render bundle and manifest in the resulting private deployment, which
is signed under the private deployment trust purpose. There is no post-render
patch and no separate private-render artifact in v1.

The exact tenant-free public render may be reused only when customization has no
operations, the effective skill set exactly equals the source-declared public
skill set, and every normalized source, skill, renderer, and parameter input
matches. Its bundle and manifest are still verified and embedded in the private
deployment. A policy, grant, credential, skill-approval, or sandbox-policy
change during compilation invalidates the current authority evidence and blocks
further advancement. Before signing, the consumer may submit current binding
and authority inputs; in one atomic decision, the Promotion Coordinator records
the newer candidate and transitions the older candidate to `superseded` only if
it has no publication or rollout side effect. If signing has begun, the older
candidate completes or fails normally and the replacement proceeds separately.

Private skill, authority/approval, and deployment/release signatures use
purpose-separated consumer-owned or explicitly opted-in tenant-dedicated
non-exportable keys. Authority/approval and deployment signing use different
keys and workload identities; a shared cross-consumer deployment signer is
never accepted.

## Canary and promotion

The Promotion Coordinator is the sole logical writer of the target's
`TargetDeliveryState`. It publishes a pending rollout through exact CAS to the
one selected `DesiredStateStore`; Git, compiler, host, consumer application,
event, observation, and lease cannot write around it. A harness certifies either
isolated-candidate or guarded in-place activation.

The Coordinator issues a signed `bytedesk.canary-plan/1` nonce challenge bound
to the exact rollout, candidate, target revision, consumer, subject, slot,
authority/policy digests, activation mode, expiry, and evidence signer policies.
Two independent actors answer it:

- the Host Reconciler returns only local technical evidence: artifact/file/slot
  readback, process/parser health, resource thresholds, switch marker, and
  unrelated-profile invariants; and
- the consumer-owned Capability Verifier exercises the candidate through the
  normal runtime and authorization path, proving workload login, one
  policy-selected non-destructive permitted capability, and one known forbidden
  sentinel.

The host never receives the candidate's agent capability credential. The
negative check passes only for the expected authorization-policy denial;
timeout, network failure, unavailable/missing endpoint, parser failure, or
`404` is not denial evidence. Both evidence objects bind the same nonce,
desired revision, release/deployment digests, actor/version, policy/grant/
workload identity, timestamps, expiry, and redacted traces. Omission fails;
signed `not_applicable` is permitted only for a certified profile with no
external capability plane.

Only fresh matching technical and capability evidence lets the Coordinator
promote by CAS. The physical switch is not self-promotion. Late evidence for a
superseded revision remains auditable but cannot change state.

## Forward recovery

Known-good is historical evidence, not automatic activation eligibility. A
recovery planner searches prior successfully promoted functional-content sets
newest first and requalifies exact source, customization, files, and skills
against current schemas, availability, withdrawal/content-revocation state,
skill approvals, target/system compatibility, and signed consumer authority.

Recovery reuses functional content only. It never reactivates the old
deployment, public/private render, desired record, receipt, signature,
authority snapshot, credentials, or tooling merely because they once worked.
A withdrawn or compromised content digest is ineligible. Revoked renderer or
compiler tooling is never executed; independently trusted source must pass the
current publication pipeline and a current compatible renderer must create a
new evaluated public-render lineage. Semantic or output changes require manual
approval. No skill, file, tool, model, provider configuration, or other
dependency is silently dropped or substituted.

The new revision records the current CAS predecessor, failed rollout,
historical `recoverySource`, reused functional descriptors, current-tooling
substitution, eligibility report, fresh recovery authority snapshot, and every
new output/evidence digest. Recovery does not depend on Git availability; the
authoritative append-only revision is created first and may be projected back
to Git later. If no candidate is eligible, recovery fails closed and incident
policy chooses isolation, stop, or temporary continuation only where the
already active digest is not prohibited.

## System-package changes

The non-selectable `office-orchestrator` reference package is engine-wide for
the reference runtime profile. Its change is never treated as an ordinary
single employee update. It receives explicit impact analysis, full release
manifest rebuild, broad canary coverage, and human approval.

## Withdrawal and emergency response

A withdrawn or compromised digest cannot be newly imported, compiled, staged,
or activated. For an already active digest, incident policy chooses among
continue-under-observation, isolate, stop, or forward-roll to replacement.
Every decision is recorded and does not mutate historical receipts.

Promotion and recovery latency, action acceptance, desired-revision
publication, event delivery, canary duration, capacity, incident response, and
GA soak evidence use the targets in
[Operational readiness v1](../standards/operational-readiness-v1.md).

## Related pages

- [Tenant Git and reconciliation](08-tenant-git-and-reconciliation.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Renderer identity v1](../standards/renderer-identity-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
- [Operational readiness v1](../standards/operational-readiness-v1.md)
