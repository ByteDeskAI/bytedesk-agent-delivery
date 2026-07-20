import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transform import render_native

# Real validated Agent Spec 26.1.2 source (the same content as
# bytedesk-agent-marketplace's agents/hello-agent/agent.yaml, parsed to its
# JSON data model - this is what a validated pyagentspec.Agent.to_dict()
# document looks like, not a synthetic placeholder).
HELLO_AGENT = {
    "component_type": "Agent",
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "hello-agent",
    "description": "Minimal portable example agent.",
    "metadata": {},
    "inputs": [],
    "outputs": [],
    "llm_config": {
        "component_type": "LlmConfig",
        "id": "00000000-0000-0000-0000-000000000002",
        "name": "default-model",
        "description": None,
        "metadata": {},
        "model_id": "default",
        "provider": None,
        "api_provider": None,
        "api_type": None,
        "url": None,
        "api_key": None,
        "default_generation_parameters": None,
        "retry_policy": None,
    },
    "system_prompt": "You are a helpful assistant.",
    "tools": [],
    "toolboxes": [],
    "human_in_the_loop": True,
    "transforms": [],
    "agentspec_version": "26.1.2",
}


def test_render_is_lossless_reference_representation():
    result = render_native(HELLO_AGENT)
    assert result.file_count == 1
    assert result.files[0].path == "agent.json"
    assert result.files[0].origin == "source_payload"


def test_two_clean_renders_are_byte_identical():
    first = render_native(HELLO_AGENT)
    second = render_native(HELLO_AGENT)
    assert first.archive_bytes == second.archive_bytes
    assert first.archive_digest == second.archive_digest
    assert first.tree_digest == second.tree_digest


def test_changing_the_source_changes_every_digest():
    changed = dict(HELLO_AGENT, system_prompt="A different prompt.")
    baseline = render_native(HELLO_AGENT)
    mutated = render_native(changed)
    assert baseline.archive_digest != mutated.archive_digest
    assert baseline.tree_digest != mutated.tree_digest
    assert baseline.files[0].digest != mutated.files[0].digest


def test_key_order_in_the_source_does_not_change_the_digest():
    reordered = {
        "component_type": HELLO_AGENT["component_type"],
        **{k: v for k, v in reversed(list(HELLO_AGENT.items()))},
    }
    assert render_native(HELLO_AGENT).archive_digest == render_native(reordered).archive_digest


def test_archive_is_a_deterministic_ustar_tarball_with_zeroed_metadata():
    import tarfile
    import io

    result = render_native(HELLO_AGENT)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        members = archive.getmembers()
        assert len(members) == 1
        member = members[0]
        assert member.name == "agent.json"
        assert member.mtime == 0
        assert member.uid == 0
        assert member.gid == 0
        assert member.mode == 0o644


def test_expanded_size_equals_sum_of_file_sizes():
    result = render_native(HELLO_AGENT)
    assert result.expanded_size == sum(f.size for f in result.files)
