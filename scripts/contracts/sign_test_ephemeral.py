#!/usr/bin/env python3
"""Sign one test request with an in-memory key that is never serialized."""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from contractlib import ContractToolError, canonical_digest, canonical_json, load_json, write_bytes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TEST ONLY: ephemeral signatures never satisfy release trust policy"
    )
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    request = load_json(args.request)
    if request.get("purpose") != "product-release-v1":
        raise ContractToolError("test signer accepts only product-release-v1 test requests")
    request_bytes = canonical_json(request)
    private_key = ec.generate_private_key(ec.SECP256R1())
    signature = private_key.sign(request_bytes, ec.ECDSA(hashes.SHA256()))
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # The private key remains inside this process and is never serialized.
    envelope = {
        "profile": "bytedesk.test-ephemeral-signature/1",
        "warning": "test-only-not-production-release-evidence",
        "requestDigest": canonical_digest(request),
        "algorithm": "ECDSA_P256_SHA256",
        "publicKeySpkiDer": base64.b64encode(public_key).decode("ascii"),
        "signatureDer": base64.b64encode(signature).decode("ascii"),
    }
    write_bytes(args.output.resolve(), canonical_json(envelope))
    print(f"testSignature={args.output.resolve()} requestDigest={envelope['requestDigest']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"ephemeral test signing failed: {error}", file=sys.stderr)
        raise SystemExit(1)
