"""Tests for safe toggle adapters (Claude set-membership, Codex tomlkit flip)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import adapters  # noqa: E402


def test_claude_disable_then_enable_preserves_other_keys(tmp_path: Path):
    cj = tmp_path / ".claude.json"
    proj = "C:/Users/x"
    cj.write_text(json.dumps({
        "numStartups": 7,  # volatile key that MUST survive
        "projects": {proj: {"disabledMcpServers": [], "volatile": 1}},
    }), encoding="utf-8")

    assert adapters.claude_set_disabled(cj, proj, "plugin:semgrep:semgrep", True) is True
    data = json.loads(cj.read_text(encoding="utf-8"))
    assert data["projects"][proj]["disabledMcpServers"] == ["plugin:semgrep:semgrep"]
    assert data["numStartups"] == 7            # unrelated key preserved
    assert data["projects"][proj]["volatile"] == 1
    assert (cj.with_suffix(".json.bak")).exists()  # backup made

    # idempotent: disabling again is a no-op
    assert adapters.claude_set_disabled(cj, proj, "plugin:semgrep:semgrep", True) is False

    # re-enable removes it
    assert adapters.claude_set_disabled(cj, proj, "plugin:semgrep:semgrep", False) is True
    assert json.loads(cj.read_text(encoding="utf-8"))["projects"][proj]["disabledMcpServers"] == []


def test_claude_namespaced_id_is_exact(tmp_path: Path):
    cj = tmp_path / ".claude.json"
    proj = "C:/p"
    cj.write_text(json.dumps({"projects": {proj: {"disabledMcpServers": ["claude.ai PubMed"]}}}), encoding="utf-8")
    # a different namespaced id is added, the existing one untouched
    adapters.claude_set_disabled(cj, proj, "chrome-devtools", True)
    arr = json.loads(cj.read_text(encoding="utf-8"))["projects"][proj]["disabledMcpServers"]
    assert arr == ["claude.ai PubMed", "chrome-devtools"]


def test_codex_toggle_enabled(tmp_path: Path):
    pytest.importorskip("tomlkit")
    ct = tmp_path / "config.toml"
    ct.write_text(
        '# my codex config\n[mcp_servers.github]\ncommand = "gh-cli-mcp"  # keep me\nenabled = true\n',
        encoding="utf-8",
    )
    assert adapters.codex_set_enabled(ct, "github", False) is True
    text = ct.read_text(encoding="utf-8")
    assert "enabled = false" in text
    assert "# my codex config" in text       # comments preserved
    assert "# keep me" in text
    # validates as TOML
    import tomllib
    assert tomllib.loads(text)["mcp_servers"]["github"]["enabled"] is False
    # no-op when already in target state
    assert adapters.codex_set_enabled(ct, "github", False) is False


def test_codex_missing_server_raises(tmp_path: Path):
    pytest.importorskip("tomlkit")
    ct = tmp_path / "config.toml"
    ct.write_text('[mcp_servers.github]\nenabled = true\n', encoding="utf-8")
    with pytest.raises(KeyError):
        adapters.codex_set_enabled(ct, "nonexistent", False)
