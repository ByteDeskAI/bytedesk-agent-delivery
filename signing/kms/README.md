# Ephemeral KMS signing (AD-08, partial)

Real ECDSA P-256 sign/verify over the exact digest-first contract AD-08
requires, producing a schema-valid `bytedesk.signing-result/1` instance
(validated directly against `contracts/schemas/v1/signing-result.schema.json`
in `tests/test_ephemeral.py`, which caught a real missing-`trustPolicy`-field
bug in the first draft). Keys are ephemeral, in-process, and never exposed —
`EphemeralKeyVersion` has no method that returns private key bytes.

Per [`docs/planning/infra-defaults.md`](../../docs/planning/infra-defaults.md)'s
signing default: this is the pattern applied instead of standing up
production KMS/Sigstore, mirroring `scripts/contracts/sign_test_ephemeral.py`
(already used for contract-bundle release conformance).

## Status

- [x] One credential kind (`kms_key`, `ECDSA_P256_SHA256`), one purpose
      family, real sign/verify, fails closed for wrong key or tampered
      digest.
- [x] Produces a real, schema-valid `signing-result` instance.
- [ ] The other 21 trust-policy purposes from
      [Trust policy v1](../../docs/standards/trust-policy-v1.md).
- [ ] Key rotation/revocation, qualification/status-head binding, evidence
      archive, Sigstore-keyless credential kind (contract-bundle release
      already has its own implementation).

## Local validation

```sh
uv sync --frozen
make test
```
