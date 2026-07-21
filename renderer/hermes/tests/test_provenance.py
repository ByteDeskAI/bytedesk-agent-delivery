import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


def _load_lock() -> dict:
    return json.loads((REPOSITORY_ROOT / "provenance/external-input-lock.json").read_text())


def test_external_input_lock_is_structurally_valid():
    lock = _load_lock()
    assert lock["contract"] == "bytedesk.external-input-lock/1"
    assert lock["role"] == "compatibility_evidence"
    assert lock["compatibilityEvidenceOnly"] is True
    assert _COMMIT_PATTERN.fullmatch(lock["commit"])
    assert _SHA256_PATTERN.fullmatch(lock["treeDigest"])
    assert len(lock["validators"]) >= 1


def test_external_input_lock_covers_exactly_the_renderer_logic_and_templates():
    lock = _load_lock()
    paths = {entry["path"] for entry in lock["paths"]}
    assert paths == {
        "ops/hermes-native/render-profiles.py",
        "ops/hermes-native/templates/.env.template",
        "ops/hermes-native/templates/config.yaml",
        "ops/hermes-native/templates/distribution.yaml",
    }
    # Never lock the credential/workload-data files that sit alongside the
    # renderer logic in the same source tree.
    for forbidden in ("office-signing-key.json", "workload-credential.py", "deployment.json"):
        assert not any(forbidden in path for path in paths)


def test_external_input_lock_paths_are_sorted_unique_and_real():
    lock = _load_lock()
    paths = [entry["path"] for entry in lock["paths"]]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    for entry in lock["paths"]:
        assert _SHA256_PATTERN.fullmatch(entry["digest"])
        assert entry["size"] > 0
