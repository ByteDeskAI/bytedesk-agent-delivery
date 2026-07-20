# OCI packaging (AD-07, partial)

Deterministic ORAS-compatible artifact construction (`pack.py`) and a
minimal OCI Distribution API v2 client (`client.py`), proven against a real
local `registry:2` container in `tests/test_local_registry.py` — genuine
push/pull round-trips, tag-vs-digest consistency, tag-retargeting isolation,
and content-addressed tamper rejection, not mocks.

## Status

- [x] Deterministic single-layer source artifact (manifest + empty config +
      one gzip/tar layer), byte-identical across repeated builds, digest-
      sensitive to real content changes.
- [x] Real local-registry push/pull/verify round-trip
      (`tests/test_local_registry.py`, requires Docker).
- [x] Tag retargeting doesn't affect an existing digest-pinned reference.
- [x] Content-addressed tamper rejection (registry refuses a blob whose
      bytes don't match the pushed digest).
- [ ] Multi-layer public-render bundles (source + skills), referrers/subject
      graph construction, retention rules, and the
      `bytedesk.publication-evidence/1` idempotent-commit protocol — see the
      `ponytail:` note in `pack.py`.

## Local validation

Requires Docker for the integration suite (skipped automatically if
unavailable):

```sh
uv sync --frozen
make test
```
