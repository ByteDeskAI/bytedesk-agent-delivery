#!/usr/bin/env python3
"""Exercise exact signed-request bindings, freshness, and replay denial."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Callable

from contractlib import ContractToolError, load_json, write_json
from verify_bundle import (
    MANIFEST_ARCHIVE_PATH,
    build_bundle_registry,
    consume_replay_ledger,
    load_canonical_request,
    read_archive,
    strict_json_bytes,
    validate_signing_request,
    verify_ephemeral_signature,
)


def expect_denial(case_id: str, operation: Callable[[], Any]) -> dict[str, str]:
    try:
        operation()
    except ContractToolError as error:
        return {"id": case_id, "outcome": "denied", "reason": str(error)}
    raise ContractToolError(f"signing denial case unexpectedly passed: {case_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--expected-request-id", required=True)
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--expected-purpose", required=True)
    parser.add_argument("--expected-key-version", required=True)
    parser.add_argument("--expected-nonce", required=True)
    parser.add_argument("--expected-issued-at", required=True)
    parser.add_argument("--expected-expires-at", required=True)
    parser.add_argument("--verification-time", required=True)
    parser.add_argument("--expected-trust-policy-id", required=True)
    parser.add_argument("--expected-trust-policy-digest", required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    members = read_archive(args.bundle.resolve())
    manifest_bytes = members[MANIFEST_ARCHIVE_PATH]
    manifest = strict_json_bytes(manifest_bytes, MANIFEST_ARCHIVE_PATH)
    policy = {
        "id": args.expected_trust_policy_id,
        "digest": args.expected_trust_policy_digest,
    }
    registry, schemas = build_bundle_registry(manifest, members, policy)
    request, _ = load_canonical_request(args.request.resolve())
    signature = load_json(args.signature.resolve())
    if not isinstance(signature, dict):
        raise ContractToolError("test signature is not an object")
    expected = {
        "requestId": args.expected_request_id,
        "repository": args.expected_repository,
        "purpose": args.expected_purpose,
        "keyVersion": args.expected_key_version,
        "nonce": args.expected_nonce,
        "issuedAt": args.expected_issued_at,
        "expiresAt": args.expected_expires_at,
        "trustPolicy": policy,
    }

    verify_ephemeral_signature(request, signature)
    request_digest = validate_signing_request(
        request,
        manifest_bytes,
        expected,
        args.verification_time,
        registry,
        schemas,
    )
    cases: list[dict[str, str]] = [{"id": "baseline", "outcome": "permitted"}]

    signed_mutations: dict[str, Any] = {
        "requestId": "contract-test-request-000002",
        "purpose": "public-source-v1",
        "keyVersion": "test-ephemeral-memory-v2",
        "repository": "registry.example.invalid/bytedesk/substituted-contracts",
        "digest": "sha256:" + "b" * 64,
        "mediaType": "application/vnd.bytedesk.substituted+json",
        "nonce": "contracttestnonce000002",
        "issuedAt": "2026-07-17T00:00:01Z",
        "expiresAt": "2026-07-17T00:04:59Z",
    }
    for field, replacement in signed_mutations.items():
        candidate = deepcopy(request)
        candidate[field] = replacement
        cases.append(
            expect_denial(
                f"signed-{field}-substitution",
                lambda candidate=candidate: verify_ephemeral_signature(candidate, signature),
            )
        )
    for policy_field, replacement in (
        ("id", "substituted-product-release-v1"),
        ("digest", "sha256:" + "b" * 64),
    ):
        candidate = deepcopy(request)
        candidate["trustPolicy"][policy_field] = replacement
        cases.append(
            expect_denial(
                f"signed-trust-policy-{policy_field}-substitution",
                lambda candidate=candidate: verify_ephemeral_signature(candidate, signature),
            )
        )

    independent_substitutions: dict[str, Any] = {
        "requestId": "contract-test-request-000002",
        "purpose": "public-source-v1",
        "keyVersion": "test-ephemeral-memory-v2",
        "repository": "registry.example.invalid/bytedesk/substituted-contracts",
        "nonce": "contracttestnonce000002",
        "issuedAt": "2026-07-17T00:00:01Z",
        "expiresAt": "2026-07-17T00:04:59Z",
    }
    for field, replacement in independent_substitutions.items():
        candidate_expected = deepcopy(expected)
        candidate_expected[field] = replacement
        cases.append(
            expect_denial(
                f"expected-{field}-substitution",
                lambda candidate_expected=candidate_expected: validate_signing_request(
                    request,
                    manifest_bytes,
                    candidate_expected,
                    args.verification_time,
                    registry,
                    schemas,
                ),
            )
        )
    for policy_field, replacement in (
        ("id", "substituted-product-release-v1"),
        ("digest", "sha256:" + "b" * 64),
    ):
        candidate_expected = deepcopy(expected)
        candidate_expected["trustPolicy"][policy_field] = replacement
        cases.append(
            expect_denial(
                f"expected-trust-policy-{policy_field}-substitution",
                lambda candidate_expected=candidate_expected: validate_signing_request(
                    request,
                    manifest_bytes,
                    candidate_expected,
                    args.verification_time,
                    registry,
                    schemas,
                ),
            )
        )

    cases.append(
        expect_denial(
            "expired-request",
            lambda: validate_signing_request(
                request,
                manifest_bytes,
                expected,
                args.expected_expires_at,
                registry,
                schemas,
            ),
        )
    )
    long_window_request = deepcopy(request)
    long_window_request["expiresAt"] = "2026-07-17T00:05:01Z"
    long_window_expected = deepcopy(expected)
    long_window_expected["expiresAt"] = long_window_request["expiresAt"]
    cases.append(
        expect_denial(
            "validity-window-over-five-minutes",
            lambda: validate_signing_request(
                long_window_request,
                manifest_bytes,
                long_window_expected,
                args.verification_time,
                registry,
                schemas,
            ),
        )
    )

    with TemporaryDirectory(prefix="bytedesk-signing-ledger-") as directory:
        ledger = Path(directory) / "replay-ledger.jsonl"
        consume_replay_ledger(
            ledger,
            request_id=args.expected_request_id,
            nonce=args.expected_nonce,
            request_digest=request_digest,
            verified_at=args.verification_time,
        )
        cases.append({"id": "first-ledger-consumption", "outcome": "permitted"})
        cases.append(
            expect_denial(
                "same-request-replay",
                lambda: consume_replay_ledger(
                    ledger,
                    request_id=args.expected_request_id,
                    nonce=args.expected_nonce,
                    request_digest=request_digest,
                    verified_at=args.verification_time,
                ),
            )
        )

    result = {
        "profile": "bytedesk.signing-request-binding-conformance/1",
        "requestDigest": request_digest,
        "caseCount": len(cases),
        "cases": cases,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError) as error:
        print(f"signing binding conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
