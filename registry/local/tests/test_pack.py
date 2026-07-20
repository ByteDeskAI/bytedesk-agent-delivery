import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pack import extract_layer_payload, pack_source_artifact

SOURCE = {"component_type": "Agent", "name": "hello-agent", "id": "1"}


def test_identical_source_produces_identical_manifest_digest():
    first = pack_source_artifact(SOURCE)
    second = pack_source_artifact(SOURCE)
    assert first.manifest_digest == second.manifest_digest
    assert first.layer_bytes == second.layer_bytes


def test_changed_source_changes_the_manifest_and_layer_digest():
    changed = dict(SOURCE, name="different-agent")
    baseline = pack_source_artifact(SOURCE)
    mutated = pack_source_artifact(changed)
    assert baseline.manifest_digest != mutated.manifest_digest
    assert baseline.layer_descriptor.digest != mutated.layer_descriptor.digest


def test_layer_round_trips_to_the_exact_source_payload():
    artifact = pack_source_artifact(SOURCE)
    payload = extract_layer_payload(artifact.layer_bytes, "agent-source.json")
    import rfc8785

    assert payload == rfc8785.dumps(SOURCE) + b"\n"


def test_extract_rejects_wrong_path():
    artifact = pack_source_artifact(SOURCE)
    try:
        extract_layer_payload(artifact.layer_bytes, "wrong-path.json")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_manifest_declares_exact_descriptor_sizes():
    artifact = pack_source_artifact(SOURCE)
    assert artifact.config_descriptor.size == len(artifact.config_bytes)
    assert artifact.layer_descriptor.size == len(artifact.layer_bytes)
