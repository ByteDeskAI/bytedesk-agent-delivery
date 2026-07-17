# Tenant Git and reconciliation

## Role of tenant Git

Tenant Git is an optional, reviewable source of installation intent. It stores
versioned [Agent binding v1](../standards/agent-binding-v1.md) envelopes, not
copied base definitions, runtime credentials, MCP grants, or full private
deployments.

Git does not become consumer identity or policy authority. A merge says the
consumer intends to use a digest-pinned definition; the current consuming
platform still decides whether that intent is authorized and deployable.

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
8. Parse only allowlisted paths and produce a sanitized candidate.

A webhook payload is a notification, not authoritative file content. The
system never deploys a branch head named only by the sender.

## Scheduled reconciliation

Webhooks can be delayed, duplicated, reordered, or lost. A scheduled reconciler
enumerates authorized bindings, resolves the configured branch to an immutable
commit, and compares it with the last processed state. This path uses the same
fetch, validation, candidate, and idempotency contracts as webhook processing.

Webhook and scheduled paths converge on the same candidate identity:

`provider + installation + numeric repository + exact commit + binding path + binding digest`.

## Candidate validation

For each changed binding, reconciliation verifies:

- expected provider installation and numeric repository;
- allowed branch and path;
- immutable commit existence and reachability under configured policy;
- strict schema and unknown-field rejection;
- exact public source digest and Agent Spec version;
- allowlisted harness and renderer version;
- non-authorizing specialization;
- expected predecessor; and
- signature/approval requirements for the Git change.

It rejects tools, MCP configuration, grants, roles, credentials, secret
references, provider authority, remote code, copied base definitions, and
approval weakening even if the repository reviewers accepted them.

## Sanitized handoff

The SCM integration emits only a versioned candidate containing stable scope,
immutable commit, binding path/digest, normalized envelope, actor metadata, and
correlation. Raw webhook bodies, installation tokens, unrelated repository
files, and secrets do not cross into core product modules.

The receiving promotion process uses an idempotent inbox. Duplicate, stale, and
reordered candidates cannot overwrite a newer accepted predecessor.

## Bot update proposals

Compatible catalog updates can be proposed through a signed bot branch and pull
request. The bot:

1. Starts from the current protected branch commit.
2. Verifies the current binding digest and expected predecessor.
3. Changes only the source digest and required compatibility metadata.
4. Includes evaluation and compatibility evidence in the proposal.
5. Signs the commit using a dedicated automation identity.
6. Uses branch protection and required checks.
7. Auto-merges only when consumer policy allows every gate.

The bot cannot add permissions, skills, provider settings, or executable
content. Human or concurrent changes cause compare-and-swap failure and win.

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

The system resolves them by rechecking current consumer authority before
compilation and activation, using expected predecessor and rollout leases, and
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
rename/transfer; path escape; oversized payload; wrong signature; conflicting
bot/human changes; and scheduled convergence. Every case proves no raw token or
secret appears in logs or downstream events.

## Related pages

- [Evaluation and promotion](09-evaluation-promotion-updates-and-rollback.md)
- [Data and API ownership](07-data-model-api-and-service-ownership.md)
- [Security and trust](06-supply-chain-trust-and-threat-model.md)
