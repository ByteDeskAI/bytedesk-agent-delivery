import io
import json
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from transform import (
    RendererInputParameters,
    UnsupportedSemanticsError,
    classify_compatibility,
    render_openclaw,
)

# Real validated Agent Spec 26.1.2 source: the same shape produced by
# bytedesk-agent-marketplace's migrate_hermes_profiles.py for
# agents/backend-development-lead/agent.yaml (portable across harnesses -
# nothing here is Hermes- or OpenClaw-specific).
BACKEND_LEAD = {
    "component_type": "Agent",
    "id": "00000000-0000-0000-0000-5d3bbbc15865",
    "name": "Backend Development Lead",
    "description": "Own backend service design and delivery.",
    "metadata": {},
    "inputs": [],
    "outputs": [],
    "llm_config": {
        "component_type": "LlmConfig",
        "id": "00000000-0000-0000-1000-5d3bbbc15865",
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
    "system_prompt": "Backend Development Lead. Own backend service design and delivery.",
    "tools": [],
    "toolboxes": [],
    "human_in_the_loop": True,
    "transforms": [],
    "agentspec_version": "26.1.2",
}

PARAMS = RendererInputParameters(
    agent_id="backend-development-lead",
    workspace="~/.openclaw/workspace-backend-development-lead",
    model="anthropic/claude-opus-4-6",
)


def test_render_produces_the_four_expected_files():
    result = render_openclaw(BACKEND_LEAD, PARAMS)
    assert result.file_count == 4
    assert {f.path for f in result.files} == {
        "SOUL.md",
        "AGENTS.md",
        "IDENTITY.md",
        "agent.json5",
    }


def test_soul_md_is_the_source_system_prompt():
    result = render_openclaw(BACKEND_LEAD, PARAMS)
    soul = next(f for f in result.files if f.path == "SOUL.md")
    assert soul.origin == "source_payload"


def test_agents_md_is_fixed_renderer_boilerplate_not_derived_from_source():
    document_a = render_openclaw(BACKEND_LEAD, PARAMS)
    changed = dict(BACKEND_LEAD, system_prompt="A completely different persona and mission.")
    document_b = render_openclaw(changed, PARAMS)
    agents_a = next(f for f in document_a.files if f.path == "AGENTS.md")
    agents_b = next(f for f in document_b.files if f.path == "AGENTS.md")
    assert agents_a.digest == agents_b.digest


def test_two_clean_renders_are_byte_identical():
    first = render_openclaw(BACKEND_LEAD, PARAMS)
    second = render_openclaw(BACKEND_LEAD, PARAMS)
    assert first.archive_bytes == second.archive_bytes
    assert first.archive_digest == second.archive_digest
    assert first.tree_digest == second.tree_digest


def test_changing_the_source_changes_every_digest():
    changed = dict(BACKEND_LEAD, system_prompt="A different prompt.")
    baseline = render_openclaw(BACKEND_LEAD, PARAMS)
    mutated = render_openclaw(changed, PARAMS)
    assert baseline.archive_digest != mutated.archive_digest
    assert baseline.tree_digest != mutated.tree_digest


def test_tools_are_rejected_as_unsupported_not_dropped():
    with_tools = dict(BACKEND_LEAD, tools=[{"component_type": "RemoteTool"}])
    with pytest.raises(UnsupportedSemanticsError):
        render_openclaw(with_tools, PARAMS)


def test_toolboxes_are_rejected_as_unsupported_not_dropped():
    with_toolboxes = dict(BACKEND_LEAD, toolboxes=[{"component_type": "ToolBox"}])
    with pytest.raises(UnsupportedSemanticsError):
        render_openclaw(with_toolboxes, PARAMS)


def test_unresolved_specialized_agent_is_rejected_as_unsupported():
    specialized = dict(BACKEND_LEAD, component_type="SpecializedAgent")
    with pytest.raises(UnsupportedSemanticsError):
        render_openclaw(specialized, PARAMS)


def test_classify_compatibility_is_exact_for_the_default_fixture():
    outcome = classify_compatibility(BACKEND_LEAD)
    assert outcome.outcome == "exact"


def test_classify_compatibility_flags_human_in_the_loop_false_as_a_warning():
    document = dict(BACKEND_LEAD, human_in_the_loop=False)
    outcome = classify_compatibility(document)
    assert outcome.outcome == "compatible_with_warnings"


def test_no_tools_md_mcp_or_default_tool_grant_ever_appears():
    result = render_openclaw(BACKEND_LEAD, PARAMS)
    assert not any(f.path == "TOOLS.md" for f in result.files)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        for member in archive.getmembers():
            text = archive.extractfile(member).read().decode("utf-8")
            for forbidden in ("mcp", "MCP", "workloadIdentity", "office-signing-key"):
                assert forbidden not in text, f"{member.name} unexpectedly contains {forbidden!r}"


def test_agent_json5_has_no_default_tool_or_skill_grants():
    result = render_openclaw(BACKEND_LEAD, PARAMS)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        config = json.loads(archive.extractfile("agent.json5").read().decode("utf-8"))
    assert config["skills"] == []
    assert config["tools"]["allow"] == []
    assert config["tools"]["deny"] == []
    assert config["tools"]["profile"] is None
    assert config["sandbox"]["workspaceAccess"] == "none"


def test_archive_is_a_deterministic_ustar_tarball_with_zeroed_metadata():
    result = render_openclaw(BACKEND_LEAD, PARAMS)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        members = archive.getmembers()
        assert len(members) == 4
        for member in members:
            assert member.mtime == 0
            assert member.uid == 0
            assert member.gid == 0
            assert member.mode == 0o644


def test_expanded_size_equals_sum_of_file_sizes():
    result = render_openclaw(BACKEND_LEAD, PARAMS)
    assert result.expanded_size == sum(f.size for f in result.files)
