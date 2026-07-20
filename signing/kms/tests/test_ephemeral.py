import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from ephemeral import SigningError, generate_key_version, sign, verify

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = REPOSITORY_ROOT / "contracts" / "schemas" / "v1"


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sign_sample(key):
    return sign(
        key,
        request_id="test-request-000001",
        request_digest=_digest(b"request-preimage"),
        purpose="product-release-v1",
        repository="registry.example.invalid/bytedesk/product",
        subject_digest=_digest(b"subject-bytes"),
        subject_media_type="application/vnd.bytedesk.agent.product-distribution.v1+json",
        trust_policy_id="product-release-v1",
        trust_policy_digest=_digest(b"trust-policy"),
        signed_at="2026-07-20T00:00:00Z",
    )


def test_sign_then_verify_succeeds():
    key = generate_key_version("test-key-v1")
    result = _sign_sample(key)
    assert verify(key, result)


def test_verification_fails_closed_for_a_different_key():
    key = generate_key_version("test-key-v1")
    other_key = generate_key_version("test-key-v2")
    result = _sign_sample(key)
    assert not verify(other_key, result)


def test_verification_fails_closed_when_the_claimed_digest_is_wrong():
    key = generate_key_version("test-key-v1")
    result = _sign_sample(key)
    tampered = result.document.copy()
    tampered["subjectDigest"] = _digest(b"a-different-subject")
    from ephemeral import SigningResult

    tampered_result = SigningResult(signature=result.signature, document=tampered)
    assert not verify(key, tampered_result)


def test_private_key_material_is_never_exposed():
    key = generate_key_version("test-key-v1")
    public_attrs = {name for name in dir(key) if not name.startswith("_")}
    assert public_attrs == {"key_version_id", "public_key_digest", "sign_digest", "verify_digest"}


def test_rejects_a_malformed_subject_digest():
    key = generate_key_version("test-key-v1")
    with pytest.raises(SigningError):
        sign(
            key,
            request_id="r",
            request_digest=_digest(b"x"),
            purpose="product-release-v1",
            repository="registry.example.invalid/bytedesk/product",
            subject_digest="not-a-digest",
            subject_media_type="application/vnd.bytedesk.agent.product-distribution.v1+json",
            trust_policy_id="product-release-v1",
            trust_policy_digest=_digest(b"trust-policy"),
            signed_at="2026-07-20T00:00:00Z",
        )


def test_signing_result_validates_against_the_real_schema():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    resources = []
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = json.loads(path.read_text())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)

    schema = json.loads((SCHEMA_ROOT / "signing-result.schema.json").read_text())
    validator = Draft202012Validator(schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER)

    key = generate_key_version("test-key-v1")
    result = _sign_sample(key)
    document = dict(result.document)
    document["schema"] = dict(document["schema"], digest=_digest(b"schema-bytes-placeholder"))

    errors = list(validator.iter_errors(document))
    assert not errors, [str(e) for e in errors]
