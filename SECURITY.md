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

Reports are especially valuable for:

- Agent Spec or binding authority smuggling;
- signature, provenance, or trust-policy bypass;
- OCI subject/referrer or cross-repository graph confusion;
- archive traversal, link/device handling, decompression bombs, or code
  execution during validation/rendering;
- deterministic-build or digest mismatch;
- cross-consumer installation, deployment, receipt, or registry access;
- reconciler privilege escalation or target escape;
- rollback restoring revoked authority; and
- secret, private attestation, or tenant-identifier disclosure.

## Supported versions

No implementation release exists yet. Supported release lines and security
update policy will be added before v1.0.0.

## Key material

Never include private keys, access tokens, secrets, or real credentials in a
report. Signing keys for this product must be non-exportable KMS keys accessed
with short-lived workload federation.
