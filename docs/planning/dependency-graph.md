# Dependency graph

This graph follows product risk and contract authority. It does not place the
ByteDesk reference catalog or consumer cutovers on the standalone release path.

## Standalone core task DAG

```text
AD-01 architecture and machine contracts
  |
  +---------------------> AD-04 renderer contract/native product
  |                         |-------------------|
  |                         v                   v
  |                       AD-05 Hermes         AD-06 OpenClaw
  |                         renderer product     renderer product
  |
  +------ AD-04 ---------> AD-07 OCI packaging
                              |
                            AD-08 trust/signing/attestations
                              |
AD-01 ---------------------- AD-09 bindings, authority, lifecycle, receipts
                              |
                            AD-10 API/events
                              |
                 AD-09 + AD-10 -> AD-11 Git intent reconciliation

AD-08 + AD-09 + AD-10 ------> AD-12 update/promotion/recovery planning

AD-04 + AD-07 + AD-08 + AD-09 + AD-12
                              |
                            AD-13 private compiler
                              |
                 AD-09 + AD-10 + AD-13
                              |
                            AD-14 reference reconciler
                              |
AD-04 + AD-07 + AD-10 + AD-13 + AD-14
                              |
                            AD-15 CLI

AD-01 + AD-04 through AD-15
                              |
                            AD-18 core certification
```

AD-05 and AD-06 run in parallel after AD-04. AD-07 does not wait for either
harness renderer because it uses the native/generic render contract; AD-05 and
AD-06 are nevertheless required products for supply-chain and core
certification. AD-11 consumes API and binding contracts but is not an authority
dependency of the private compiler. AD-13 consumes prepared update/promotion
decisions from AD-12 and never depends on Git. AD-14 and AD-15 are both core
products.

## Core milestone DAG

```text
AD-01
  |
CONTRACTS-FROZEN
  |
AD-04 + AD-05 + AD-06 + AD-07 + AD-08
  |
SUPPLY-CHAIN-CERT
  |
AD-09 + AD-10 + AD-11 + AD-12 + AD-13
  |
CONTROL-PLANE-CERT
  |
AD-14 + AD-15
  |
RUNTIME-CERT
  |
AD-18
  |
CORE-CERT / standalone GA
```

- **CONTRACTS-FROZEN** freezes the signed offline JSON Schema bundle, canonical
  encoding, strict operation profiles, renderer identity, consumer authority,
  lifecycle, API/event, trust, and operational-readiness contracts.
- **SUPPLY-CHAIN-CERT** proves generic source plus native, Hermes, and OpenClaw
  renderer products through deterministic OCI publication and trust.
- **CONTROL-PLANE-CERT** proves installation, current consumer authority,
  single-writer desired state, API/events, Git intent, updates, and private
  compilation.
- **RUNTIME-CERT** proves the reference reconciler, separate technical and
  capability canary actors, forward recovery, and complete CLI path.
- **CORE-CERT / standalone GA** requires the signed AD-18 readiness report,
  including SLO, scale, security, retention, disaster-recovery, upgrade, and
  support evidence. It requires neither the ByteDesk 34+1 catalog nor a ByteDesk
  consumer.

## Reference tracks

```text
AD-01 --------------------------> AD-02 marketplace bootstrap

AD-02 + AD-04 ------------------> AD-03 ByteDesk 34+1 catalog
                                      |
CORE-CERT ---------------------> REFERENCE-CATALOG-CERT

CORE-CERT ----------------------> AD-16 ByteDesk Hermes cutover
        \-----------------------> AD-17 ByteDesk OpenClaw cutover

CORE-CERT + AD-16 + AD-17
        + REFERENCE-CATALOG-CERT when the ByteDesk catalog is selected
                                      |
                              REFERENCE-CONSUMER-CERT
```

AD-02 and AD-03 are the reference-catalog track. AD-16 and AD-17 are the
reference-consumer track. They may not redefine or copy core contracts. A
different consumer can certify against its own compatible catalog without the
ByteDesk reference catalog; the named ByteDesk certification requires
`REFERENCE-CATALOG-CERT`.

## Exact task dependencies

| Task | Prerequisites |
|---|---|
| AD-01 | None |
| AD-02 | AD-01 |
| AD-03 | AD-02, AD-04 |
| AD-04 | AD-01 |
| AD-05 | AD-04 |
| AD-06 | AD-04 |
| AD-07 | AD-01, AD-04 |
| AD-08 | AD-07 |
| AD-09 | AD-01, AD-08 |
| AD-10 | AD-09 |
| AD-11 | AD-09, AD-10 |
| AD-12 | AD-08, AD-09, AD-10 |
| AD-13 | AD-04, AD-07, AD-08, AD-09, AD-12 |
| AD-14 | AD-09, AD-10, AD-13 |
| AD-15 | AD-04, AD-07, AD-10, AD-13, AD-14 |
| AD-16 | CORE-CERT |
| AD-17 | CORE-CERT |
| AD-18 core | AD-01 and AD-04 through AD-15 |

See [`development-plan.json`](development-plan.json) for the machine-readable
form.
