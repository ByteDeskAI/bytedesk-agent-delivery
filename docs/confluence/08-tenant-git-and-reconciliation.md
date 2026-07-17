# Tenant Git and reconciliation

## Role of tenant Git

Tenant Git is an optional, reviewable source of installation and binding
intent. It stores
versioned [Agent binding v1](../standards/agent-binding-v1.md) envelopes, not
copied base definitions, raw runtime credentials, authoritative grants, or full
private deployments. A binding may contain deterministic functional Agent Spec
and regular-file customization, exact public/private skill descriptors,
tools/MCP/provider/model/harness configuration, and opaque secret references.

Git does not become consumer identity, policy, or runtime desired-state
authority. A merge says the consumer intends to use a digest-pinned definition;
the current consuming platform still decides whether that intent is authorized
and deployable, and only the Promotion Coordinator may publish the resulting
target revision through the target's one selected `DesiredStateStore`.

## Repository binding

A repository connection is identified by immutable provider installation and
numeric repository identifiers, expected owner/account, allowed default branch,
and allowlisted binding paths. A repository name alone is never authority
because names can be transferred or reused.

The provider Adapter brokers installation tokens and immutable fetches. Tokens
remain inside that Adapter and are never included in events, operation records,
or downstream compilation.

## Ingress path

The webhook path is intentionally small:

1. Receive the raw request under strict byte and time limits.
2. Verify provider signature against the exact raw body.
3. Validate event type, delivery identifier, and installation scope.
4. Persist an idempotent receipt and transactional outbox item.
5. Return promptly.
6. Resolve the installation and repository binding asynchronously.
7. Fetch the exact commit through the provider API.
8. Parse only allowlisted paths, accepting YAML only through the YAML 1.2
   JSON-compatible subset and rejecting duplicate keys, aliases, custom tags,
   non-string mapping keys, and non-finite numbers.
9. Validate the closed Draft 2020-12 binding schema from the exact signed
   contract bundle, convert accepted objects to the JSON data model, serialize
   RFC 8785 JCS bytes for identity, and produce a sanitized candidate.

A webhook payload is a notification, not authoritative file content. The
system never deploys a branch head named only by the sender.

## Scheduled reconciliation

Webhooks can be delayed, duplicated, reordered, or lost. A scheduled reconciler
enumerates authorized bindings, resolves the configured branch to an immutable
commit, and compares it with the last processed state. This path uses the same
fetch, validation, candidate, and idempotency contracts as webhook processing.

Webhook and scheduled paths converge on the same candidate identity:

`provider + installation + numeric repository + exact commit + binding path + binding digest`.

The binding digest is over RFC 8785 canonical JSON, not the Git file's YAML
presentation. Equivalent accepted YAML and JSON authoring therefore converge on
the same binding identity. Original YAML may be retained as provenance, while
an integrity reference to it is provenance/storage-integrity evidence only,
never semantic identity, artifact authority, or activation authority. Arbitrary
payload files referenced by a
binding keep exact raw-byte identity, including files named `.yaml` or `.json`.

## Candidate validation

For each changed binding, reconciliation verifies:

- expected provider installation and numeric repository;
- allowed branch and path;
- immutable commit existence and reachability under configured policy;
- exact schema ID/digest, offline contract-bundle resolution, and closed-schema
  unknown-field rejection;
- restricted YAML-authoring and RFC 8785 canonical-JSON rules;
- exact public source digest and Agent Spec version;
- allowlisted harness and complete exact renderer-release descriptor, including
  immutable manifest digest and trust-policy ID/digest;
- deterministic `bytedesk.json-patch/1` functional customization plus strict
  file/skill add-replace-remove preconditions, canonical path rules, and atomic
  failure;
- exact public/private skill descriptors and current signed approval evidence;
- no raw secret, embedded grant, identity/role assignment, hook, unsafe entry,
  caller-selected trust root, or approval weakening;
- required `absent` or exact revision-and-digest `match` precondition; and
- signature/approval requirements for the Git change.

It permits private desired tools/MCP/provider/model/harness configuration and
opaque secret references but treats them as untrusted desired data, never as
authority or content Agent Delivery may execute. It rejects
raw secrets, embedded grants, identity or role assignments, provider-access
claims, copied base definitions, package hooks, install commands, unsafe file
entries, undeclared remote fetches, and approval weakening even if repository
reviewers accepted them. Any new or changed skill digest enters quarantine.

## Sanitized handoff

The SCM integration emits only a versioned candidate containing stable scope,
immutable commit, binding path/digest, normalized envelope, actor metadata, and
correlation. The normalized envelope is the JSON data model and its digest is
computed from RFC 8785 JCS bytes. Raw webhook bodies, installation tokens, unrelated repository
files, and secrets do not cross into core product modules.

The notification uses CloudEvents 1.0.2 and a signed event-data schema described
by AsyncAPI 3.1.0. Events are at-least-once notifications; an unknown schema or
sequence gap stops the projection and forces authoritative API resynchronization.
The receiving promotion process uses an idempotent inbox. Duplicate, stale, and
reordered candidates cannot overwrite a newer accepted predecessor.

## Bot update proposals

Compatible catalog updates can be proposed through a signed bot branch and pull
request. The bot:

1. Starts from the current protected branch commit.
2. Verifies the current binding revision/digest and exact `match` precondition.
3. Changes only the source digest and required compatibility metadata.
4. Includes evaluation and compatibility evidence in the proposal.
5. Signs the commit using a dedicated automation identity.
6. Uses branch protection and required checks.
7. Auto-merges only when consumer policy allows every gate.

The compatible-update bot cannot add permissions, change the skill digest set,
alter private provider/model/MCP/harness configuration, or add executable
content. Human or concurrent changes cause compare-and-swap failure and win.
Initial creation uses an explicit `absent` precondition; omission, null,
wildcard, or a digest without its revision is invalid.

Git reconciliation owns candidate intent only. Installation lifecycle,
candidate preparation, target rollout, and host observations remain separate
state machines. A successful Git merge cannot stage, activate, promote, or
recover content. Forward recovery does not wait for Git: the sole Promotion
Coordinator first creates the authoritative append-only target revision from a
currently eligible historical functional-content set, then may project that
decision back through a reviewed reconciliation change.

## Force pushes and history rewrites

A force push can remove a previously observed commit, but it cannot erase a
durable candidate, binding revision, or deployment receipt. Reconciliation
processes the new immutable head as another candidate and applies predecessor
rules. It never rewrites product history to match Git history.

If policy requires commits to remain reachable from a protected branch, an
orphaned candidate is rejected or withdrawn from promotion while existing
audit evidence remains.

## Conflicts and lifecycle races

Common races include a profile being retired while a PR merges, a grant being
revoked during compilation, a second update being approved during canary, or a
repository installation being removed during fetch.

The system resolves them by rechecking a fresh signed consumer-authority
snapshot before compilation and activation, using exact revision-and-digest
CAS plus rollout leases, and
failing closed when the provider or consumer no longer authorizes the action.

## Provider portability

GitHub is the first reference Adapter, but core candidates use provider-neutral
identifiers and immutable commit concepts. Adding GitLab or another provider
requires an Adapter that proves equivalent webhook authenticity, installation
scope, numeric repository binding, immutable fetch, protected-change evidence,
and token isolation.

## Recovery behavior

Provider outage blocks new candidate fetch and update proposals. It does not
stop an already verified active runtime release. Receipts remain pending with a
bounded retry policy and dead-letter evidence. Scheduled reconciliation resumes
from the last durable cursor after recovery.

## Required tests

Tests cover valid push and PR flows; duplicate, missed, delayed, and reordered
deliveries; stale commits; force pushes; installation removal; repository
rename/transfer; path escape; unsafe file entries; raw secret values; changed
skill quarantine; equivalent YAML/JSON contract identity; duplicate YAML keys,
aliases, custom tags, non-string mapping keys, and non-finite numbers; byte-exact
`.yaml`, `.json`, and binary payload changes; oversized payload; wrong
signature; conflicting bot/human changes; and scheduled convergence. Every case
proves no raw token or secret appears in logs or downstream events.

Contract tests also cover closed-schema and unknown-field denial, strict JSON
Patch/file/skill preconditions, `absent` first creation, revision-plus-digest
ABA protection, CloudEvent duplicate/reorder/gap/API-resync behavior, denial of
direct target-state writes, and forward recovery during a Git outage.

## Related pages

- [Evaluation, promotion, and forward recovery](09-evaluation-promotion-updates-and-forward-recovery.md)
- [Data and API ownership](07-data-model-api-and-service-ownership.md)
- [Security and trust](06-supply-chain-trust-and-threat-model.md)
- [Machine contracts v1](../standards/machine-contracts-v1.md)
- [Consumer authority and private signing v1](../standards/consumer-authority-v1.md)
- [Delivery lifecycle v1](../standards/delivery-lifecycle-v1.md)
