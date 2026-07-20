"""Ephemeral, non-exportable KMS-shaped signing (AD-08 core primitive).

AD-08 required-work items 1-2 and acceptance criteria: "No signing
private-key material is exportable" and "Verification is digest-first and
fails closed for wrong signer, subject, media type, ... or revocation."

# ponytail: implements one credential kind (kms_key, ECDSA_P256_SHA256) for
# one purpose family, in-process only - a real stand-in for a KMS key
# version's sign/verify surface, never a real KMS client. Per
# docs/planning/infra-defaults.md's signing default, this is the pattern the
# whole session applies instead of standing up production KMS/Sigstore:
# real cryptography, real digests, ephemeral non-exportable keys.
# Does NOT implement: the other 21 trust-policy purposes, key rotation/
# revocation, qualification/status-head binding, or the Sigstore-keyless
# credential kind (already implemented separately for contract-bundle
# release - see scripts/contracts/sign_test_ephemeral.py).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.exceptions import InvalidSignature

ALGORITHM = "ECDSA_P256_SHA256"


class SigningError(RuntimeError):
    pass


@dataclass(frozen=True)
class EphemeralKeyVersion:
    """A single in-memory, non-exportable ECDSA P-256 key version.

    The private key never leaves this object: there is no method that
    returns private key bytes, matching "no signing private-key material is
    exportable."
    """

    key_version_id: str
    _private_key: ec.EllipticCurvePrivateKey

    @property
    def public_key_digest(self) -> str:
        public_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return "sha256:" + hashlib.sha256(public_bytes).hexdigest()

    def sign_digest(self, subject_digest: str) -> bytes:
        """Sign the exact 32 raw digest bytes behind a 'sha256:<hex>' string."""

        digest_bytes = bytes.fromhex(_strip_sha256_prefix(subject_digest))
        return self._private_key.sign(digest_bytes, ec.ECDSA(Prehashed(hashes.SHA256())))

    def verify_digest(self, subject_digest: str, signature: bytes) -> bool:
        digest_bytes = bytes.fromhex(_strip_sha256_prefix(subject_digest))
        try:
            self._private_key.public_key().verify(
                signature, digest_bytes, ec.ECDSA(Prehashed(hashes.SHA256()))
            )
            return True
        except InvalidSignature:
            return False


def _strip_sha256_prefix(digest: str) -> str:
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise SigningError(f"not an exact sha256: digest: {digest!r}")
    return digest[len("sha256:") :]


def generate_key_version(key_version_id: str) -> EphemeralKeyVersion:
    private_key = ec.generate_private_key(ec.SECP256R1())
    return EphemeralKeyVersion(key_version_id=key_version_id, _private_key=private_key)


def _reencode_signature_deterministically(signature: bytes) -> bytes:
    """DSS signatures aren't canonical DER by default; re-encode for stability."""

    r, s = decode_dss_signature(signature)
    return encode_dss_signature(r, s)


@dataclass(frozen=True)
class SigningResult:
    signature: bytes
    document: dict[str, Any]


def sign(
    key: EphemeralKeyVersion,
    *,
    request_id: str,
    request_digest: str,
    purpose: str,
    repository: str,
    subject_digest: str,
    subject_media_type: str,
    trust_policy_id: str,
    trust_policy_digest: str,
    signed_at: str,
) -> SigningResult:
    if not subject_digest.startswith("sha256:"):
        raise SigningError("subject digest must be an exact sha256: digest")

    signature = _reencode_signature_deterministically(key.sign_digest(subject_digest))
    signature_digest = "sha256:" + hashlib.sha256(signature).hexdigest()

    audit_evidence = {
        "profile": "bytedesk.ephemeral-kms-provider-audit/1",
        "keyVersion": key.key_version_id,
        "publicKeyDigest": key.public_key_digest,
        "purpose": purpose,
        "requestDigest": request_digest,
        "authorityIssued": False,
    }
    import rfc8785

    audit_bytes = rfc8785.dumps(audit_evidence)
    audit_digest = "sha256:" + hashlib.sha256(audit_bytes).hexdigest()

    document = {
        "contract": "bytedesk.signing-result/1",
        "schema": {
            "id": "https://schemas.bytedesk.ai/agent-delivery/v1/signing-result/1.0.0",
        },
        "requestId": request_id,
        "requestDigest": request_digest,
        "purpose": purpose,
        "keyVersion": key.key_version_id,
        "algorithm": ALGORITHM,
        "publicKeyDigest": key.public_key_digest,
        "repository": repository,
        "subjectDigest": subject_digest,
        "subjectMediaType": subject_media_type,
        "signatureBundle": {
            "repository": repository,
            "digest": signature_digest,
            "mediaType": "application/vnd.bytedesk.agent.ecdsa-signature.v1+der",
            "size": len(signature),
            "trustPolicy": {"id": trust_policy_id, "digest": trust_policy_digest},
        },
        "trustPolicy": {"id": trust_policy_id, "digest": trust_policy_digest},
        "providerAuditEvidence": {
            "repository": repository,
            "digest": audit_digest,
            "mediaType": "application/vnd.bytedesk.ephemeral-kms-provider-audit.v1+json",
            "size": len(audit_bytes),
            "trustPolicy": {"id": trust_policy_id, "digest": trust_policy_digest},
        },
        "signedAt": signed_at,
    }
    return SigningResult(signature=signature, document=document)


def verify(key: EphemeralKeyVersion, result: SigningResult) -> bool:
    """Independent re-verification using only the public key, digest-first.

    Fails closed: any mismatch between the claimed subject digest and what
    was actually signed is caught by signature verification itself, since
    the signature only validates against the exact digest bytes it was
    produced over.
    """

    return key.verify_digest(result.document["subjectDigest"], result.signature)
