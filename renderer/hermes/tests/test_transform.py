import io
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from transform import (
    RendererInputParameters,
    UnsupportedSemanticsError,
    classify_compatibility,
    render_hermes,
)

# Real validated Agent Spec 26.1.2 source: the same shape produced by
# bytedesk-agent-marketplace's migrate_hermes_profiles.py for
# agents/backend-development-lead/agent.yaml.
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
    workspace="/work/backend-development-lead",
    api_host="127.0.0.1",
    api_port=8801,
    kanban_db="/var/lib/hermes/kanban.db",
    model_provider="openrouter",
    model_default="anthropic/claude-opus-4-6",
    orchestrator_profile="orchestrator",
    default_assignee="orchestrator",
    hermes_requires=">=0.18.0",
)


def test_render_produces_the_four_expected_files():
    result = render_hermes(BACKEND_LEAD, PARAMS)
    assert result.file_count == 4
    assert {f.path for f in result.files} == {
        ".env.template",
        "SOUL.md",
        "config.yaml",
        "distribution.yaml",
    }


def test_soul_md_is_the_source_system_prompt():
    result = render_hermes(BACKEND_LEAD, PARAMS)
    soul = next(f for f in result.files if f.path == "SOUL.md")
    assert soul.origin == "source_payload"


def test_two_clean_renders_are_byte_identical():
    first = render_hermes(BACKEND_LEAD, PARAMS)
    second = render_hermes(BACKEND_LEAD, PARAMS)
    assert first.archive_bytes == second.archive_bytes
    assert first.archive_digest == second.archive_digest
    assert first.tree_digest == second.tree_digest


def test_changing_the_source_changes_every_digest():
    changed = dict(BACKEND_LEAD, system_prompt="A different prompt.")
    baseline = render_hermes(BACKEND_LEAD, PARAMS)
    mutated = render_hermes(changed, PARAMS)
    assert baseline.archive_digest != mutated.archive_digest
    assert baseline.tree_digest != mutated.tree_digest


def test_changing_renderer_parameters_changes_the_archive_but_not_soul():
    other_params = RendererInputParameters(
        workspace="/work/other",
        api_host="0.0.0.0",
        api_port=9000,
        kanban_db="/tmp/kanban.db",
        model_provider="openrouter",
        model_default="google/gemini-3-flash-preview",
        orchestrator_profile="orchestrator",
        default_assignee="orchestrator",
        hermes_requires=">=0.18.0",
    )
    baseline = render_hermes(BACKEND_LEAD, PARAMS)
    reparametrized = render_hermes(BACKEND_LEAD, other_params)
    assert baseline.archive_digest != reparametrized.archive_digest
    baseline_soul = next(f for f in baseline.files if f.path == "SOUL.md")
    reparam_soul = next(f for f in reparametrized.files if f.path == "SOUL.md")
    assert baseline_soul.digest == reparam_soul.digest


def test_tools_are_rejected_as_unsupported_not_dropped():
    with_tools = dict(BACKEND_LEAD, tools=[{"component_type": "RemoteTool"}])
    with pytest.raises(UnsupportedSemanticsError):
        render_hermes(with_tools, PARAMS)


def test_toolboxes_are_rejected_as_unsupported_not_dropped():
    with_toolboxes = dict(BACKEND_LEAD, toolboxes=[{"component_type": "ToolBox"}])
    with pytest.raises(UnsupportedSemanticsError):
        render_hermes(with_toolboxes, PARAMS)


def test_unresolved_specialized_agent_is_rejected_as_unsupported():
    specialized = dict(BACKEND_LEAD, component_type="SpecializedAgent")
    with pytest.raises(UnsupportedSemanticsError):
        render_hermes(specialized, PARAMS)


def test_classify_compatibility_flags_human_in_the_loop_as_a_warning():
    outcome = classify_compatibility(BACKEND_LEAD)
    assert outcome.outcome == "compatible_with_warnings"
    assert any("human_in_the_loop" in note for note in outcome.notes)


def test_classify_compatibility_is_exact_without_lossy_fields():
    document = dict(BACKEND_LEAD, human_in_the_loop=False)
    outcome = classify_compatibility(document)
    assert outcome.outcome == "exact"
    assert outcome.notes == ()


def test_no_office_signing_or_mcp_or_org_content_ever_appears():
    result = render_hermes(BACKEND_LEAD, PARAMS)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        for member in archive.getmembers():
            text = archive.extractfile(member).read().decode("utf-8")
            for forbidden in (
                "office-signing-key",
                "mcp_servers",
                "workloadIdentity",
                "## Organization",
                "office-orchestrator",
                "chief-of-staff",
            ):
                assert forbidden not in text, f"{member.name} unexpectedly contains {forbidden!r}"


def test_archive_is_a_deterministic_ustar_tarball_with_zeroed_metadata():
    result = render_hermes(BACKEND_LEAD, PARAMS)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        members = archive.getmembers()
        assert len(members) == 4
        for member in members:
            assert member.mtime == 0
            assert member.uid == 0
            assert member.gid == 0
            assert member.mode == 0o644


def test_config_yaml_is_valid_yaml_and_carries_no_mcp_block():
    import yaml

    result = render_hermes(BACKEND_LEAD, PARAMS)
    with tarfile.open(fileobj=io.BytesIO(result.archive_bytes)) as archive:
        config_text = archive.extractfile("config.yaml").read().decode("utf-8")
    parsed = yaml.safe_load(config_text)
    assert "mcp_servers" not in parsed
    assert "plugins" not in parsed
    assert "onboarding" not in parsed
    assert parsed["kanban"]["orchestrator_profile"] == PARAMS.orchestrator_profile
    assert parsed["model"]["provider"] == PARAMS.model_provider
    assert parsed["model"]["default"] == PARAMS.model_default
    assert parsed["agent"]["disabled_toolsets"] == []
    assert parsed["max_concurrent_sessions"] == PARAMS.max_concurrent_sessions


def test_expanded_size_equals_sum_of_file_sizes():
    result = render_hermes(BACKEND_LEAD, PARAMS)
    assert result.expanded_size == sum(f.size for f in result.files)
