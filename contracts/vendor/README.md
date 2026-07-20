# Vendored projection validators

These files are tooling inputs, not Agent Delivery-owned contract authority.
They ship inside the signed offline contract bundle so a verifier can validate
the API and event projections without the network. Release lint checks their
exact bytes before using them.

## OpenAPI 3.2

- source: `https://spec.openapis.org/oas/3.2/schema/2025-11-23`
- file: `openapi/3.2.0/schema-2025-11-23.json`
- SHA-256: `7d48f01f37eeae4799041b371ad5f533f9f533fd2b0caa1011a8ba27c5b48b70`
- dialect: JSON Schema Draft 2020-12
- license: Apache-2.0, retained in `openapi/3.2.0/LICENSE`

## AsyncAPI 3.1

- source repository: `https://github.com/asyncapi/spec-json-schemas`
- release tag: `v6.11.1`
- commit: `e609fc2341007395d75df5756fc6fccf662c2087`
- source path: `schemas/3.1.0.json`
- file: `asyncapi/3.1.0/schema-e609fc2341007395d75df5756fc6fccf662c2087.json`
- SHA-256: `51d3274899ad2875f25c18fd1aef4d5512f0a97be785d519740bde55a4162f61`
- dialect: JSON Schema Draft 7 with 113 embedded resources
- license: Apache-2.0, with the upstream `LICENSE` and `NOTICE` retained beside
  the schema

Updating either validator is a reviewed dependency change. It requires a new
immutable source identity, exact digest, retained attribution, offline
validation evidence, and projection conformance before bundle release.
