#!/usr/bin/env python3
"""Create the canonical request consumed by an external release signer.

This command never accepts private-key material and never invokes a signer. A
production workflow sends its output to the purpose-scoped KMS/workload-
identity Signer Adapter and verifies the returned Cosign bundle independently.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from contractlib import (
    SCHEMAS_ROOT,
    ContractToolError,
    canonical_digest,
    canonical_json,
    load_json,
    load_json_bytes,
    sha256_bytes,
    validation_error_key,
    write_bytes,
)
from validate_schemas import build_registry


SIGNING_REQUEST_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/signing-request/1.0.0"
)
CONTRACT_BUNDLE_MEDIA_TYPE = "application/vnd.bytedesk.agent.contract-bundle.v1+json"
MAX_SIGNING_REQUEST_VALIDITY = timedelta(minutes=5)


def parse_timestamp(value: str, description: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractToolError(f"{description} is not a valid date-time") from error
    if parsed.tzinfo is None:
        raise ContractToolError(f"{description} must include an offset")
    return parsed.astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--key-version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--trust-policy-id", required=True)
    parser.add_argument("--trust-policy-digest", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--issued-at", required=True)
    parser.add_argument("--expires-at", required=True)
    args = parser.parse_args()

    issued_at = parse_timestamp(args.issued_at, "issued-at")
    expires_at = parse_timestamp(args.expires_at, "expires-at")
    if issued_at >= expires_at:
        raise ContractToolError("signing request validity window is empty or reversed")
    if expires_at - issued_at > MAX_SIGNING_REQUEST_VALIDITY:
        raise ContractToolError("signing request validity exceeds the five-minute profile")

    manifest, manifest_bytes = load_json_bytes(args.manifest.resolve())
    if not isinstance(manifest, dict) or manifest_bytes != canonical_json(manifest):
        raise ContractToolError("contract bundle manifest is not an exact canonical object")
    expected_policy = {
        "id": args.trust_policy_id,
        "digest": args.trust_policy_digest,
    }
    if manifest.get("contract") != "bytedesk.contract-bundle/1":
        raise ContractToolError("input is not a contract bundle manifest")
    if manifest.get("trustPolicy") != expected_policy:
        raise ContractToolError("manifest trust policy differs from independent signer input")

    schema = load_json(SCHEMAS_ROOT / "signing-request.schema.json")
    request = {
        "contract": "bytedesk.signing-request/1",
        "schema": {"id": SIGNING_REQUEST_SCHEMA_ID, "digest": canonical_digest(schema)},
        "requestId": args.request_id,
        "purpose": "product-release-v1",
        "keyVersion": args.key_version,
        "repository": args.repository,
        "digest": sha256_bytes(manifest_bytes),
        "mediaType": CONTRACT_BUNDLE_MEDIA_TYPE,
        "trustPolicy": expected_policy,
        "nonce": args.nonce,
        "issuedAt": args.issued_at,
        "expiresAt": args.expires_at,
    }
    registry, schemas = build_registry()
    errors = sorted(
        Draft202012Validator(
            schemas[SIGNING_REQUEST_SCHEMA_ID][1],
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(request),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"generated signing request is invalid: {errors[0].message}")
    write_bytes(args.output.resolve(), canonical_json(request))
    print(f"request={args.output.resolve()} requestDigest={canonical_digest(request)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"signing request creation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
