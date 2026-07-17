# Evaluation, promotion, updates, and rollback

## Promotion is a durable process

An artifact becoming available does not make it active. Promotion is an
observable, retryable, idempotent process whose complete evidence is retained.
The process separates portable compatibility, consumer evaluation, artifact
trust, runtime canary, and final promotion.

The canonical state progression is:

```text
received -> fetched -> validated -> quarantined -> evaluating
evaluating -> approved | rejected
approved -> rendered -> signed -> staged -> canary
canary -> promoted | rolled_back
```

Every transition records actor, correlation, expected predecessor, input and
output digests, policy result, and time. Illegal, stale, and duplicate
transitions are denied deterministically.

## Validation gate

Before evaluation, the candidate must pass:

- catalog and source trust policy;
- official pinned Agent Spec validation;
- non-authority and package safety policy;
- source, binding, renderer, and skill digest integrity;
- withdrawal and revocation checks;
- consumer, tenant, target, and predecessor scope; and
- schema compatibility with the installed binding.

A candidate that attempts to add MCP servers, tools, roles, credentials,
provider connections, workload identity, or approval weakening is rejected,
not sent to evaluation for an override.

## Quarantine

Quarantine isolates unapproved content while scans and evaluations run. Source
instructions can be inspected and rendered in a confined build environment,
but cannot reach a consumer runtime.

Skills are evaluated independently. A new or changed skill remains quarantined
even if the base definition change is compatible. The definition can continue
without the skill when its semantics make the skill optional.

## Compatibility classification

The renderer produces a signed compatibility result:

- **exact**: target representation preserves the selected semantics;
- **compatible with warnings**: approved equivalent behavior with visible
  structured warnings;
- **lossy**: behavior cannot be preserved exactly and requires explicit human
  acceptance; or
- **unsupported**: no valid target can be produced.

Automatic promotion permits only policy-approved exact or non-lossy compatible
results. A renderer version change is part of the candidate and is never hidden
inside a source-only update.

## Evaluation contract

Product evaluation can include deterministic schema, policy, safety, render,
and regression checks. Consumer-specific evaluation is supplied through an
Adapter and may include role behavior, tone, task fixtures, model policy,
business approval, and compliance checks.

Evaluation input names exact source, binding, skill, renderer, model-policy,
and fixture digests. Output is a signed or authenticated attestation with:

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
- the expected predecessor still matches;
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
declares the currently installed digest as `expectedPredecessor`. Acceptance
fails if a human, another update, or lifecycle change has advanced the binding.

The system does not rebase over an unknown concurrent change or overwrite a
human edit. A new proposal must be generated from the new current state.

## Private deployment compilation

After approval, the compiler resolves current consumer state rather than using
the state captured when the catalog candidate first appeared. It binds:

- exact source and public render;
- accepted binding and optional skills;
- current organizational profile and lifecycle;
- current policy and approval result;
- current MCP/tool/resource grant digest;
- current provider and credential-version references;
- target runtime and stable slot; and
- exact renderer and compiler identity.

The resulting private deployment is signed under the private deployment trust
purpose. A policy or grant change during compilation invalidates or supersedes
the candidate according to consumer policy.

## Canary and promotion

Staging proves artifact verification and filesystem safety before switching.
Canary then proves at least:

- process starts with the expected profile and stable slot;
- observed source, render, deployment, and release digests match desired;
- consumer workload login binds to the expected current deployment;
- one explicitly granted MCP capability can be discovered and invoked in the
  test scope;
- an ungranted capability is denied;
- health remains within configured thresholds; and
- no unrelated profile or runtime changes.

Only the promotion coordinator may mark a canary promoted. Host observations
are evidence, not self-approval.

## Forward rollback

Rollback never reactivates an old deployment artifact or rewrites desired-state
history. It creates a new binding/deployment/release revision using the
last-known-good **definition content** while recompiling current identity,
policy, grants, credentials, lifecycle, target, and trust state.

This prevents a revoked grant or credential from returning merely because the
definition bytes are old. The new revision records which failed release caused
the rollback and which content was selected as last known good.

If current policy no longer permits the old content, rollback fails closed and
the consumer chooses another safe definition or stops the workload.

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

## Related pages

- [Tenant Git and reconciliation](08-tenant-git-and-reconciliation.md)
- [Hosted runtime deployment](10-hosted-runtime-deployment.md)
- [Verification and recovery](13-verification-operations-and-disaster-recovery.md)
