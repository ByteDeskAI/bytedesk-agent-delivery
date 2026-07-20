# Native Agent Spec renderer (AD-04, partial)

Implements the reference native-renderer transform: a validated Agent Spec
JSON model → its own RFC 8785 canonical bytes as the single `agent.json`
output file, packaged in a deterministic USTAR archive. This is genuinely
lossless by construction (native output *is* the canonical source), not an
approximation, and `tests/test_transform.py` proves the load-bearing
properties directly: byte-identical repeated renders, key-order
independence, and digest sensitivity to real content changes.

Isolated as its own `uv` project per
[ADR-0002](../../docs/architecture/adr/0002-implementation-stack-and-reference-topology.md)'s
Python renderer-runtime isolation ("Python code is never imported into the
Go control-plane process").

## Status

This is a slice of AD-04, not the complete task. See the `ponytail:` note at
the top of `transform.py` and
[`docs/planning/infra-defaults.md`](../../docs/planning/infra-defaults.md)
for what's deliberately not built yet:

- [x] Native transform: source → output file(s) → tree/archive digests.
- [ ] Full `bytedesk.render-manifest/1` instance assembly — needs a real
      renderer registry (`rendererRelease`, `compiledAllowlistDigest`),
      `renderer-input-parameters`, `harness-configuration`, and
      `renderer-compatibility-result` objects, each with their own deep
      required-field chains.
- [ ] Sandbox execution (Docker, per the infra-defaults security profile).
- [ ] Qualification flow, status-head binding, and public-render finalizer
      signing (ephemeral test keys only, per infra-defaults).

## Local validation

```sh
uv sync --frozen
make test
```
