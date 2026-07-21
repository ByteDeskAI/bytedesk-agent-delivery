import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render_marketplace_catalog import default_params, render_catalog  # noqa: E402

MARKETPLACE_AGENTS_ROOT = Path(
    "/home/ryan/Documents/GitHub/ByteDeskAI/bytedesk-agent-marketplace/agents"
)
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _skip_if_marketplace_unavailable():
    import pytest

    if not MARKETPLACE_AGENTS_ROOT.is_dir():
        pytest.skip("bytedesk-agent-marketplace checkout not available in this environment")


def test_renders_every_marketplace_package_with_no_unsupported_entries():
    _skip_if_marketplace_unavailable()
    manifest = render_catalog(MARKETPLACE_AGENTS_ROOT, default_params)
    assert manifest["packageCount"] == 35
    assert manifest["renderedCount"] == 35
    assert manifest["unsupportedCount"] == 0


def test_render_is_deterministic_across_runs():
    _skip_if_marketplace_unavailable()
    first = render_catalog(MARKETPLACE_AGENTS_ROOT, default_params)
    second = render_catalog(MARKETPLACE_AGENTS_ROOT, default_params)
    assert first == second


def test_checked_in_manifest_matches_a_fresh_render():
    _skip_if_marketplace_unavailable()
    checked_in = json.loads((REPOSITORY_ROOT / "catalog-render/manifest.json").read_text())
    fresh = render_catalog(MARKETPLACE_AGENTS_ROOT, default_params)
    assert checked_in == fresh
