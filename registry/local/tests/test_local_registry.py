"""Real local-registry integration tests (AD-07 required-work item 7).

Starts a real `registry:2` container (Docker Distribution reference
implementation) on an ephemeral local port and proves push/pull/tamper/
tag-retargeting behavior against it - not a mock.
"""

import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client import Registry, RegistryError, pull_and_verify_artifact, push_artifact
from pack import pack_source_artifact

SOURCE = {"component_type": "Agent", "name": "hello-agent", "id": "1"}
CONTAINER_NAME = "bytedesk-ad07-test-registry"
PORT = 15050


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="module")
def registry():
    if not _docker_available():
        pytest.skip("docker is not available in this environment")

    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"{PORT}:5000",
            "registry:2",
        ],
        check=True,
        capture_output=True,
    )
    base_url = f"http://localhost:{PORT}"
    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{base_url}/v2/", timeout=2)
            ready = True
            break
        except Exception:  # noqa: BLE001 - readiness poll, not an assertion
            time.sleep(0.5)
    if not ready:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
        pytest.fail("local registry did not become ready in time")

    yield Registry(base_url=base_url, repository="bytedesk/agent-source")

    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)


def test_push_pull_round_trip_is_byte_exact(registry):
    artifact = pack_source_artifact(SOURCE)
    push_artifact(registry, "v1", artifact)

    result = pull_and_verify_artifact(registry, "v1")
    assert result["manifestDigest"] == artifact.manifest_digest
    assert result["configBytes"] == artifact.config_bytes
    assert result["layerBytes"] == [artifact.layer_bytes]


def test_pull_by_digest_matches_pull_by_tag(registry):
    artifact = pack_source_artifact(SOURCE)
    push_artifact(registry, "v2", artifact)

    by_tag = pull_and_verify_artifact(registry, "v2")
    by_digest = pull_and_verify_artifact(registry, artifact.manifest_digest)
    assert by_tag["manifestDigest"] == by_digest["manifestDigest"]


def test_tag_retargeting_does_not_change_an_existing_digest_pin(registry):
    first_source = dict(SOURCE, name="agent-one")
    second_source = dict(SOURCE, name="agent-two")
    first_artifact = pack_source_artifact(first_source)
    second_artifact = pack_source_artifact(second_source)

    push_artifact(registry, "movable-tag", first_artifact)
    pinned_digest = first_artifact.manifest_digest

    # Retarget the tag to a different artifact - the caller that pinned by
    # digest must be unaffected.
    push_artifact(registry, "movable-tag", second_artifact)

    still_pinned = pull_and_verify_artifact(registry, pinned_digest)
    assert still_pinned["manifestDigest"] == pinned_digest
    assert still_pinned["manifest"] != None  # noqa: E711 - real fetched object, not a stub

    moved_tag = pull_and_verify_artifact(registry, "movable-tag")
    assert moved_tag["manifestDigest"] == second_artifact.manifest_digest


def test_tampered_blob_is_rejected_before_use(registry):
    artifact = pack_source_artifact(SOURCE)
    push_artifact(registry, "v3", artifact)

    # Directly overwrite content addressed by the layer's own digest is not
    # possible through the registry API (content-addressed storage refuses a
    # mismatched digest on push) - prove that guarantee holds.
    tampered_layer = artifact.layer_bytes + b"\x00extra-byte"
    with pytest.raises(RegistryError):
        registry.push_blob(artifact.layer_descriptor.digest, tampered_layer)
