PYTHON_RUN := uv run --frozen --offline --no-sync python
CONTRACT_EVIDENCE_DIR ?= dist/evidence
CONTRACT_BUNDLE_OUTPUT_DIR ?= dist/contracts
CONTRACT_BUNDLE_VERSION ?= 1.0.0
CONTRACT_PRODUCT_VERSION ?= 0.1.0-contracts-frozen
CONTRACT_CREATED_AT ?= 1970-01-01T00:00:00Z
CONTRACT_TEST_TRUST_POLICY_ID := contract-bundle-release-v1
CONTRACT_TEST_TRUST_POLICY_DIGEST := sha256:3613503d06b2d2cb00797144e7034554bc169c2dc5a36f226e8013e316c3774b
CONTRACT_TRUST_POLICY_ID ?= $(CONTRACT_TEST_TRUST_POLICY_ID)
CONTRACT_TRUST_POLICY_DIGEST ?= $(CONTRACT_TEST_TRUST_POLICY_DIGEST)
CONTRACT_TEST_TRUST_POLICY_SOURCE ?= contracts/fixtures/signing/test-trust-policy.source.json
CONTRACT_TEST_TRUST_POLICY ?= $(CONTRACT_EVIDENCE_DIR)/test-trust-policy.json
CONTRACT_TEST_RELEASE_EVIDENCE_DIR ?= $(CONTRACT_EVIDENCE_DIR)/test-release-evidence
CONTRACT_TEST_RELEASE_EVIDENCE_ATTESTATION ?= $(CONTRACT_TEST_RELEASE_EVIDENCE_DIR)/attestation.json
CONTRACT_TEST_REQUEST_ID ?= contract-test-request-000001
CONTRACT_TEST_REPOSITORY ?= registry.example.invalid/bytedesk/agent-delivery-contracts
CONTRACT_TEST_PURPOSE ?= contract-bundle-release-v1
CONTRACT_TEST_CREDENTIAL_KIND ?= sigstore_keyless
CONTRACT_TEST_SIGNER_IDENTITY_DIGEST ?= sha256:1eb0e14ab8a2a20a79c5ff9f19e9c9b3367667d93eb549480f8d79b98ffe28eb
CONTRACT_TEST_BUILDER_DIGEST ?= sha256:c522266ffc7d4eb7e5ba5a9383107ff1969e54ad431ad55d80de9005bb6b78e9
CONTRACT_TEST_NONCE ?= contracttestnonce000001
CONTRACT_TEST_ISSUED_AT ?= 2026-07-17T00:00:00Z
CONTRACT_TEST_EXPIRES_AT ?= 2026-07-17T00:05:00Z
CONTRACT_TEST_VERIFICATION_TIME ?= 2026-07-17T00:01:00Z
OPERATION_FUZZ_TIME ?= 2s
OPERATION_FUZZ_TARGETS := FuzzJSONPatchAtomicityAndUnicode FuzzJSONPointerUnicodeAndEscapes FuzzJSONPatchOperationOrder FuzzJSONArrayOperations FuzzThreeWayRebaseChangedTargetDenial FuzzFileOperationCollisionIsAtomic FuzzSkillOperationConflictIsAtomic
CONTRACT_TEST_SOURCE_COMMIT ?= 2222222222222222222222222222222222222222
CONTRACT_TEST_REPLAY_DIR ?= $(CONTRACT_EVIDENCE_DIR)/test-local-replay
CONTRACT_TEST_REPLAY_LEDGER ?= $(CONTRACT_TEST_REPLAY_DIR)/signing-request-replay-ledger.jsonl
CONTRACT_TEST_DENIED_LEDGER ?= $(CONTRACT_TEST_REPLAY_DIR)/denied-signing-request-replay-ledger.jsonl
CONTRACT_TEST_SIGNED_BINDINGS = --expected-request-id $(CONTRACT_TEST_REQUEST_ID) --expected-repository $(CONTRACT_TEST_REPOSITORY) --expected-purpose $(CONTRACT_TEST_PURPOSE) --expected-credential-kind $(CONTRACT_TEST_CREDENTIAL_KIND) --expected-signer-identity-digest $(CONTRACT_TEST_SIGNER_IDENTITY_DIGEST) --expected-builder-digest $(CONTRACT_TEST_BUILDER_DIGEST) --expected-nonce $(CONTRACT_TEST_NONCE) --expected-issued-at $(CONTRACT_TEST_ISSUED_AT) --expected-expires-at $(CONTRACT_TEST_EXPIRES_AT) --verification-time $(CONTRACT_TEST_VERIFICATION_TIME)
CONTRACT_TEST_POLICY_ARGS = --trust-policy $(CONTRACT_TEST_TRUST_POLICY) --release-evidence-attestation $(CONTRACT_TEST_RELEASE_EVIDENCE_ATTESTATION) --release-evidence-dir $(CONTRACT_TEST_RELEASE_EVIDENCE_DIR) --allow-test-local-replay-ledger

.PHONY: sync-contract-tools test verify-repository verify-downstream-ports verify-contracts bundle-contracts verify

sync-contract-tools:
	uv sync --frozen

test: sync-contract-tools
	mkdir -p $(CONTRACT_EVIDENCE_DIR)
	go mod verify
	go test -count=1 -race ./...
	go test -count=1 -json ./... > $(CONTRACT_EVIDENCE_DIR)/go-test-events.json
	@bash -o pipefail -c 'set -eu; : > "$(CONTRACT_EVIDENCE_DIR)/operation-fuzz-events.json"; for target in $(OPERATION_FUZZ_TARGETS); do go test -json -run "^$$" -fuzz "^$${target}$$" -fuzztime "$(OPERATION_FUZZ_TIME)" ./internal/operations | tee -a "$(CONTRACT_EVIDENCE_DIR)/operation-fuzz-events.json"; done'
	go vet ./...

verify-repository: sync-contract-tools
	$(PYTHON_RUN) scripts/verify_repository.py --evidence $(CONTRACT_EVIDENCE_DIR)/repository-validation.json

verify-downstream-ports: sync-contract-tools
	mkdir -p $(CONTRACT_EVIDENCE_DIR)
	$(PYTHON_RUN) scripts/contracts/generate_downstream_port_types.py --check
	$(PYTHON_RUN) scripts/contracts/generate_protocol_fixtures.py --check
	$(PYTHON_RUN) scripts/contracts/generate_renderer_digest_fixtures.py
	$(PYTHON_RUN) scripts/contracts/generate_private_compilation_graph_fixtures.py
	$(PYTHON_RUN) scripts/contracts/generate_conformance_plan.py --check
	$(PYTHON_RUN) scripts/contracts/refresh_contract_metadata.py
	$(PYTHON_RUN) scripts/contracts/test_contract_metadata_refresh.py
	$(PYTHON_RUN) scripts/contracts/test_downstream_ports.py --evidence $(CONTRACT_EVIDENCE_DIR)/downstream-port-validation.json
	$(PYTHON_RUN) scripts/contracts/test_protocol_fixtures.py --evidence $(CONTRACT_EVIDENCE_DIR)/protocol-fixture-validation.json
	$(PYTHON_RUN) scripts/contracts/test_fixture_generator_ownership.py
	$(PYTHON_RUN) scripts/contracts/test_contract_bundle_role_closure.py --evidence $(CONTRACT_EVIDENCE_DIR)/contract-bundle-role-closure.json
	$(PYTHON_RUN) scripts/contracts/test_renderer_digests.py --evidence $(CONTRACT_EVIDENCE_DIR)/renderer-digest-validation.json
	$(PYTHON_RUN) scripts/contracts/test_private_compilation_graph.py --evidence $(CONTRACT_EVIDENCE_DIR)/private-compilation-graph-validation.json
	$(PYTHON_RUN) scripts/contracts/test_conformance_plan.py --evidence $(CONTRACT_EVIDENCE_DIR)/downstream-conformance-plan-validation.json

verify-contracts: test verify-repository verify-downstream-ports
	mkdir -p $(CONTRACT_EVIDENCE_DIR)
	go run ./cmd/schema-validator --evidence $(CONTRACT_EVIDENCE_DIR)/go-schema-validation.json
	$(PYTHON_RUN) scripts/contracts/test_strict_json.py --evidence $(CONTRACT_EVIDENCE_DIR)/strict-json-resource-conformance.json
	$(PYTHON_RUN) scripts/contracts/test_agent_spec_source_resolution.py --evidence $(CONTRACT_EVIDENCE_DIR)/agent-spec-source-resolution-conformance.json
	$(PYTHON_RUN) scripts/contracts/validate_schemas.py --evidence $(CONTRACT_EVIDENCE_DIR)/python-schema-validation.json
	$(PYTHON_RUN) scripts/contracts/test_schema_inventory.py --evidence $(CONTRACT_EVIDENCE_DIR)/schema-inventory-conformance.json
	$(PYTHON_RUN) scripts/contracts/test_schema_descriptor_validation.py
	$(PYTHON_RUN) scripts/contracts/compare_validator_evidence.py --go $(CONTRACT_EVIDENCE_DIR)/go-schema-validation.json --python $(CONTRACT_EVIDENCE_DIR)/python-schema-validation.json --evidence $(CONTRACT_EVIDENCE_DIR)/validator-agreement.json
	$(PYTHON_RUN) scripts/contracts/test_bundle_safety.py --evidence $(CONTRACT_EVIDENCE_DIR)/bundle-source-exclusions.json
	$(PYTHON_RUN) scripts/contracts/lint_projections.py --evidence $(CONTRACT_EVIDENCE_DIR)/projection-validation.json
	$(PYTHON_RUN) scripts/contracts/test_projection_validation.py --evidence $(CONTRACT_EVIDENCE_DIR)/projection-validator-conformance.json
	$(PYTHON_RUN) scripts/test_architecture_validation.py
	$(PYTHON_RUN) scripts/verify_architecture.py --output-dir $(CONTRACT_EVIDENCE_DIR)/architecture --evidence $(CONTRACT_EVIDENCE_DIR)/architecture-validation.json
	$(PYTHON_RUN) scripts/contracts/test_release_workflow_structure.py --evidence $(CONTRACT_EVIDENCE_DIR)/release-workflow-boundary.json
	$(PYTHON_RUN) scripts/contracts/test_reproducible_builds.py --evidence $(CONTRACT_EVIDENCE_DIR)/reproducible-build-comparator-conformance.json
	$(PYTHON_RUN) scripts/contracts/create_test_trust_policy.py --source $(CONTRACT_TEST_TRUST_POLICY_SOURCE) --schema contracts/schemas/v1/trust-policy.schema.json --output $(CONTRACT_TEST_TRUST_POLICY) --expected-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST)

bundle-contracts: verify-contracts
	$(PYTHON_RUN) scripts/contracts/build_bundle.py --output-dir $(CONTRACT_BUNDLE_OUTPUT_DIR) --bundle-version $(CONTRACT_BUNDLE_VERSION) --product-version $(CONTRACT_PRODUCT_VERSION) --created-at $(CONTRACT_CREATED_AT) --trust-policy-id $(CONTRACT_TRUST_POLICY_ID) --trust-policy-digest $(CONTRACT_TRUST_POLICY_DIGEST)

verify: verify-contracts
	$(PYTHON_RUN) scripts/contracts/build_bundle.py --output-dir dist/contracts-a --bundle-version $(CONTRACT_BUNDLE_VERSION) --product-version $(CONTRACT_PRODUCT_VERSION) --created-at $(CONTRACT_CREATED_AT) --trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST)
	$(PYTHON_RUN) scripts/contracts/build_bundle.py --output-dir dist/contracts-b --bundle-version $(CONTRACT_BUNDLE_VERSION) --product-version $(CONTRACT_PRODUCT_VERSION) --created-at $(CONTRACT_CREATED_AT) --trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST)
	cmp dist/contracts-a/agent-delivery-contracts-v1.tar dist/contracts-b/agent-delivery-contracts-v1.tar
	cmp dist/contracts-a/agent-delivery-contracts-v1.manifest.json dist/contracts-b/agent-delivery-contracts-v1.manifest.json
	$(PYTHON_RUN) scripts/contracts/compare_reproducible_builds.py --bundle-a dist/contracts-a/agent-delivery-contracts-v1.tar --bundle-b dist/contracts-b/agent-delivery-contracts-v1.tar --manifest-a dist/contracts-a/agent-delivery-contracts-v1.manifest.json --manifest-b dist/contracts-b/agent-delivery-contracts-v1.manifest.json --evidence $(CONTRACT_EVIDENCE_DIR)/reproducible-build.json
	$(PYTHON_RUN) scripts/contracts/create_test_release_evidence.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --repository $(CONTRACT_TEST_REPOSITORY) --trust-policy $(CONTRACT_TEST_TRUST_POLICY) --verification-evidence-dir $(CONTRACT_EVIDENCE_DIR) --output-dir $(CONTRACT_TEST_RELEASE_EVIDENCE_DIR) --evaluated-at $(CONTRACT_TEST_ISSUED_AT)
	$(PYTHON_RUN) scripts/contracts/test_release_evidence.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --trust-policy $(CONTRACT_TEST_TRUST_POLICY) --repository $(CONTRACT_TEST_REPOSITORY) --release-evidence-dir $(CONTRACT_TEST_RELEASE_EVIDENCE_DIR) --verification-time $(CONTRACT_TEST_VERIFICATION_TIME) --evidence $(CONTRACT_EVIDENCE_DIR)/release-evidence-conformance.json
	$(PYTHON_RUN) scripts/contracts/test_bundle_self_containment.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --evidence $(CONTRACT_EVIDENCE_DIR)/offline-bundle-schema-authority.json
	$(PYTHON_RUN) scripts/contracts/verify_payload_round_trip.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --evidence $(CONTRACT_EVIDENCE_DIR)/payload-round-trip.json
	$(PYTHON_RUN) scripts/contracts/create_signing_request.py --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --output $(CONTRACT_EVIDENCE_DIR)/signing-request.json --request-id $(CONTRACT_TEST_REQUEST_ID) --signer-identity-digest $(CONTRACT_TEST_SIGNER_IDENTITY_DIGEST) --builder-digest $(CONTRACT_TEST_BUILDER_DIGEST) --pre-sign-certification $(CONTRACT_TEST_RELEASE_EVIDENCE_ATTESTATION) --repository $(CONTRACT_TEST_REPOSITORY) --trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) --nonce $(CONTRACT_TEST_NONCE) --issued-at $(CONTRACT_TEST_ISSUED_AT) --expires-at $(CONTRACT_TEST_EXPIRES_AT)
	$(PYTHON_RUN) scripts/contracts/sign_test_ephemeral.py --request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --output $(CONTRACT_EVIDENCE_DIR)/test-signature.json
	$(PYTHON_RUN) scripts/contracts/test_signing_bindings.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --signature $(CONTRACT_EVIDENCE_DIR)/test-signature.json $(CONTRACT_TEST_SIGNED_BINDINGS) --expected-pre-sign-certification $(CONTRACT_TEST_RELEASE_EVIDENCE_ATTESTATION) --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) --evidence $(CONTRACT_EVIDENCE_DIR)/signing-binding-conformance.json
	$(PYTHON_RUN) scripts/contracts/test_supply_chain_security.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --trust-policy $(CONTRACT_TEST_TRUST_POLICY) --request $(CONTRACT_EVIDENCE_DIR)/signing-request.json $(CONTRACT_TEST_SIGNED_BINDINGS) --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) --release-evidence-attestation $(CONTRACT_TEST_RELEASE_EVIDENCE_ATTESTATION) --release-evidence-dir $(CONTRACT_TEST_RELEASE_EVIDENCE_DIR) --evidence $(CONTRACT_EVIDENCE_DIR)/supply-chain-security-conformance.json
	install -d -m 700 $(CONTRACT_TEST_REPLAY_DIR)
	rm -f $(CONTRACT_TEST_DENIED_LEDGER)
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) $(CONTRACT_TEST_POLICY_ARGS) --test-signing-request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --test-signature $(CONTRACT_EVIDENCE_DIR)/test-signature.json --allow-test-signature $(CONTRACT_TEST_SIGNED_BINDINGS) --expected-request-id contract-test-request-substituted --replay-ledger $(CONTRACT_TEST_DENIED_LEDGER); then echo "wrong expected request ID was accepted" >&2; exit 1; fi
	test ! -e $(CONTRACT_TEST_DENIED_LEDGER)
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) $(CONTRACT_TEST_POLICY_ARGS) --test-signing-request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --test-signature $(CONTRACT_EVIDENCE_DIR)/test-signature.json --allow-test-signature $(CONTRACT_TEST_SIGNED_BINDINGS) --verification-time $(CONTRACT_TEST_EXPIRES_AT) --replay-ledger $(CONTRACT_TEST_DENIED_LEDGER); then echo "expired signed request was accepted" >&2; exit 1; fi
	test ! -e $(CONTRACT_TEST_DENIED_LEDGER)
	rm -f $(CONTRACT_TEST_REPLAY_LEDGER)
	$(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) $(CONTRACT_TEST_POLICY_ARGS) --test-signing-request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --test-signature $(CONTRACT_EVIDENCE_DIR)/test-signature.json --allow-test-signature $(CONTRACT_TEST_SIGNED_BINDINGS) --replay-ledger $(CONTRACT_TEST_REPLAY_LEDGER) --evidence $(CONTRACT_EVIDENCE_DIR)/bundle-verification.json
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --manifest dist/contracts-a/agent-delivery-contracts-v1.manifest.json --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) $(CONTRACT_TEST_POLICY_ARGS) --test-signing-request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --test-signature $(CONTRACT_EVIDENCE_DIR)/test-signature.json --allow-test-signature $(CONTRACT_TEST_SIGNED_BINDINGS) --replay-ledger $(CONTRACT_TEST_REPLAY_LEDGER); then echo "same signed request replay was accepted" >&2; exit 1; fi
	$(PYTHON_RUN) scripts/contracts/mutate_bundle_for_test.py --source dist/contracts-a/agent-delivery-contracts-v1.tar --output $(CONTRACT_EVIDENCE_DIR)/tampered.tar
	rm -f $(CONTRACT_TEST_DENIED_LEDGER)
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle $(CONTRACT_EVIDENCE_DIR)/tampered.tar --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) $(CONTRACT_TEST_POLICY_ARGS) --test-signing-request $(CONTRACT_EVIDENCE_DIR)/signing-request.json --test-signature $(CONTRACT_EVIDENCE_DIR)/test-signature.json --allow-test-signature $(CONTRACT_TEST_SIGNED_BINDINGS) --replay-ledger $(CONTRACT_TEST_DENIED_LEDGER); then echo "tampered bundle was accepted" >&2; exit 1; fi
	test ! -e $(CONTRACT_TEST_DENIED_LEDGER)
	$(PYTHON_RUN) scripts/contracts/mutate_bundle_for_test.py --source dist/contracts-a/agent-delivery-contracts-v1.tar --output $(CONTRACT_EVIDENCE_DIR)/trailing-bytes.tar --append-trailing-bytes
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle $(CONTRACT_EVIDENCE_DIR)/trailing-bytes.tar --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) --allow-unsigned-structure; then echo "trailing archive bytes were accepted" >&2; exit 1; fi
	$(PYTHON_RUN) scripts/contracts/mutate_bundle_for_test.py --source dist/contracts-a/agent-delivery-contracts-v1.tar --output $(CONTRACT_EVIDENCE_DIR)/repository-only.tar --inject-repository-only contracts/fixtures/schema/repository-index.json
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle $(CONTRACT_EVIDENCE_DIR)/repository-only.tar --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) --allow-unsigned-structure; then echo "repository-only bundle member was accepted" >&2; exit 1; fi
	$(PYTHON_RUN) scripts/contracts/mutate_bundle_for_test.py --source dist/contracts-a/agent-delivery-contracts-v1.tar --output $(CONTRACT_EVIDENCE_DIR)/repository-schema.tar --inject-repository-only contracts/schemas/repository/development-plan.schema.json
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle $(CONTRACT_EVIDENCE_DIR)/repository-schema.tar --expected-trust-policy-id $(CONTRACT_TEST_TRUST_POLICY_ID) --expected-trust-policy-digest $(CONTRACT_TEST_TRUST_POLICY_DIGEST) --allow-unsigned-structure; then echo "repository-only schema member was accepted" >&2; exit 1; fi
	@if $(PYTHON_RUN) scripts/contracts/verify_bundle.py --bundle dist/contracts-a/agent-delivery-contracts-v1.tar --expected-trust-policy-id substituted-policy --expected-trust-policy-digest sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb --allow-unsigned-structure; then echo "trust-policy substitution was accepted" >&2; exit 1; fi
