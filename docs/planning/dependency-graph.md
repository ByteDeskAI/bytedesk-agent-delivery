# Dependency graph

## Standalone core

```text
AD-01 Architecture
  |
AD-02 Marketplace/catalog bootstrap
  |-------------------|
  v                   v
AD-03 Baseline       AD-04 Renderer contract
  |-------------------|
  |                   |
  v                   v
AD-05 Hermes         AD-06 OpenClaw
  |-------------------|
              v
            AD-07 OCI packaging
              |
            AD-08 Trust and attestations
              |
            AD-09 Installations and receipts
              |-------------------|
              v                   v
            AD-10 APIs           AD-11 Git reconciliation
              |-------------------|
                         v
                       AD-12 Updates/promotion

AD-05 + AD-06 + AD-08 + AD-09 + AD-11
                         |
                       AD-13 Deployment compiler
                         |
          AD-10 + AD-12 + AD-13
                         |
                       AD-14 Host protocol/reconciler

AD-07 + AD-10 + AD-13 -> AD-15 CLI

AD-08 + AD-10 + AD-12 + AD-13 + AD-14 + AD-15
                         |
                    AD-18 core / CORE-CERT
                         |
               standalone v1 release
```

AD-03 and AD-04 may run in parallel after AD-02. AD-05 and AD-06 may run in
parallel once both AD-03 and AD-04 are ready. AD-10 and AD-11 may run in
parallel after AD-09. AD-15 may run in parallel with late AD-14 work after its
own prerequisites are available.

## Deferred reference-consumer integrations

```text
standalone v1 release
       |----------------------|
       v                      v
AD-16 ByteDesk/Hermes     AD-17 OpenClaw
       |----------------------|
                  v
                AD-18 reference appendices
```

The original transferred plan placed AD-16 and AD-17 directly on core internal
tasks. The independent-product boundary adds `CORE-CERT` and a released version
as the required predecessor. This prevents consumer integration from becoming
an implicit product-host dependency.

## Machine-readable plan

See [`development-plan.json`](development-plan.json).
