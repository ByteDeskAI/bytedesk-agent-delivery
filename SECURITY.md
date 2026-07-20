# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability, leaked credential,
signature bypass, trust-policy bypass, cross-consumer access, unsafe archive,
or supply-chain compromise.

Use this repository's **Security** tab to submit a private vulnerability report
through GitHub Security Advisories. Include the affected commit or release,
artifact media type and digest where applicable, reproduction steps, expected
security invariant, and impact. Redact credentials and tenant data.

## Security-sensitive areas

The production reference implementation and its mandatory identity, secret,
network, sandbox, storage, KMS, backup, and telemetry controls are fixed by
[ADR-0002](docs/architecture/adr/0002-implementation-stack-and-reference-topology.md).
Equivalent Adapter implementations must preserve the normative security
contracts and pass the same denial and isolation suites; a different vendor or
deployment substrate is not an exception to those controls.

Reports are especially valuable for:

- Agent Spec or binding authority smuggling;
- signature, provenance, or trust-policy bypass;
- OCI subject/referrer or cross-repository graph confusion;
- archive traversal, link/device handling, decompression bombs, or code
  execution during validation/rendering;
- execution of skill files during validation, rendering, compilation, staging,
  or activation, or runtime execution without explicit approval of the exact
  skill digest under current consumer sandbox, network, identity, and call-time
  authorization policy;
- private-customization leakage into a public catalog render or registry scope;
- deterministic-build or digest mismatch;
- schema-bundle substitution, remote schema resolution, unknown-field
  acceptance, or drift between a normative schema and a generated projection;
- renderer-release, worker-image, platform, compiled-allowlist, PATH/library,
  or renderer-owned-schema substitution, including execution of a withdrawn or
  revoked renderer;
- YAML parser differentials, duplicate-key or alias confusion, unsupported YAML
  types, or a mismatch between the validated JSON data model and RFC 8785 JCS
  bytes used for hashing or signing;
- cross-consumer installation, deployment, receipt, or registry access;
- shared private signing keys, cross-consumer signing, stale/replayed consumer
  authority snapshots, or supplier signatures treated as the required per-
  consumer private-skill publication or skill approval;
- reconciler privilege escalation or target escape;
- any writer other than the Promotion Coordinator advancing target desired
  state, dual DesiredStateStore authority, canary evidence replay, or a false
  denial treated as authorization evidence;
- recovery that reactivates an old deployment, authority snapshot, signature,
  receipt, or revoked renderer instead of rebuilding with current trusted
  tooling and current consumer authority; and
- secret, private attestation, or tenant-identifier disclosure.

## Supported versions

No implementation release exists yet. The accepted readiness contract requires
at least 24 months of GA-major support, defined previous-major security
support, and measured security-response evidence before v1 can claim GA.

## Key material

Never include private keys, access tokens, secrets, or real credentials in a
report. Signing keys must be non-exportable KMS keys accessed with short-lived
workload federation. Private-skill, consumer-authority/approval, and deployment
signing roles are purpose-separated and isolated per consumer; a provider-wide
shared private-artifact key is not conforming.
