"""Targeted tests closing the remaining line/branch gaps in core/*.

Covers CLI/subprocess wrappers, defensive fall-throughs, and the
external-mtime reload path that the feature-focused suites don't exercise.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import (  # noqa: E402
    adapters,
    claude_adapter,
    codex_adapter,
    consolidation,
    funnel_adapter,
    inventory,
)
from core import status as sm  # noqa: E402


# ── adapters.py: backup=False short-circuits ──────────────────────────────────


def test_claude_set_disabled_without_backup(tmp_path: Path):
    cj = tmp_path / ".claude.json"
    proj = "C:/p"
    cj.write_text(
        json.dumps({"projects": {proj: {"disabledMcpServers": []}}}), encoding="utf-8"
    )
    assert adapters.claude_set_disabled(cj, proj, "srv", True, backup=False) is True
    assert not cj.with_suffix(".json.bak").exists()


def test_codex_set_enabled_without_backup(tmp_path: Path):
    pytest.importorskip("tomlkit")
    ct = tmp_path / "config.toml"
    ct.write_text("[mcp_servers.github]\nenabled = true\n", encoding="utf-8")
    assert adapters.codex_set_enabled(ct, "github", False, backup=False) is True
    assert not ct.with_suffix(".toml.bak").exists()


# ── claude_adapter.py ─────────────────────────────────────────────────────────


def test_run_mcp_list_invokes_cli(monkeypatch):
    class _R:
        stdout = "claude.ai X: cmd - ✔ Connected\n"

    monkeypatch.setattr(claude_adapter.subprocess, "run", lambda *a, **k: _R())
    assert "claude.ai X" in claude_adapter._run_mcp_list(timeout=5)


def test_mtime_missing_file_returns_zero(tmp_path: Path):
    assert claude_adapter._mtime(tmp_path / "nope.json") == 0.0


def test_save_claude_json_explicit_backup_dir_missing_file(tmp_path: Path):
    target = tmp_path / "new.json"  # absent -> no backup copy made
    bdir = tmp_path / "mybackups"
    claude_adapter._save_claude_json(target, {"a": 1}, backup_dir=bdir)
    assert target.exists()
    assert bdir.is_dir()
    assert list(bdir.glob("*.bak")) == []


def test_set_server_disabled_reloads_on_external_mtime_change(
    tmp_path: Path, monkeypatch
):
    cj = tmp_path / ".claude.json"
    proj = "C:/p"
    cj.write_text(
        json.dumps({"projects": {proj: {"disabledMcpServers": []}}}), encoding="utf-8"
    )
    times = iter([100.0, 200.0])  # before != after -> reload + re-apply branch
    monkeypatch.setattr(claude_adapter, "_mtime", lambda _p: next(times))
    assert claude_adapter.set_server_disabled(cj, proj, "srv", True) is True
    data = json.loads(cj.read_text(encoding="utf-8"))
    assert data["projects"][proj]["disabledMcpServers"] == ["srv"]


# ── codex_adapter.py ──────────────────────────────────────────────────────────


def test_toml_servers_without_tomllib(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(codex_adapter, "tomllib", None)
    assert codex_adapter._toml_servers(tmp_path / "c.toml") == {}


def test_toml_servers_invalid_toml(tmp_path: Path):
    p = tmp_path / "c.toml"
    p.write_text("not = = valid", encoding="utf-8")
    assert codex_adapter._toml_servers(p) == {}


def test_parse_codex_skips_non_dict_and_nameless_items():
    rows = codex_adapter.parse_codex_mcp_list(
        json.dumps(["not-a-dict", {"enabled": True}, {"name": "ok"}])
    )
    assert [r.name for r in rows] == ["ok"]


def test_get_server_universe_uses_cli(tmp_path: Path, monkeypatch):
    class _R:
        stdout = json.dumps([{"name": "cli-srv", "enabled": True}])

    monkeypatch.setattr(codex_adapter.subprocess, "run", lambda *a, **k: _R())
    rows = codex_adapter.get_server_universe(tmp_path / "c.toml")
    assert rows[0].name == "cli-srv"


def test_get_server_universe_cli_empty_falls_back_to_toml(tmp_path: Path, monkeypatch):
    class _R:
        stdout = "[]"  # CLI ran but returned no servers -> fall through to config.toml

    monkeypatch.setattr(codex_adapter.subprocess, "run", lambda *a, **k: _R())
    p = tmp_path / "c.toml"
    p.write_text("[mcp_servers.local]\nenabled = true\n", encoding="utf-8")
    rows = codex_adapter.get_server_universe(p)
    assert rows[0].name == "local"


def test_get_server_universe_cli_error_falls_back_to_toml(tmp_path: Path, monkeypatch):
    def _boom(*_a, **_k):
        raise FileNotFoundError

    monkeypatch.setattr(codex_adapter.subprocess, "run", _boom)
    p = tmp_path / "c.toml"
    p.write_text("[mcp_servers.fb]\nenabled = false\n", encoding="utf-8")
    rows = codex_adapter.get_server_universe(p)
    assert rows[0].name == "fb" and rows[0].enabled is False


def test_get_server_universe_empty_json_falls_back(tmp_path: Path):
    p = tmp_path / "c.toml"
    p.write_text("[mcp_servers.cfg]\nenabled = true\n", encoding="utf-8")
    rows = codex_adapter.get_server_universe(p, json_output="[]")
    assert rows[0].name == "cfg"


def test_set_server_enabled_empty_config_raises(tmp_path: Path):
    pytest.importorskip("tomlkit")
    with pytest.raises(KeyError):
        codex_adapter.set_server_enabled(tmp_path / "missing.toml", "x", True)


def test_set_server_enabled_without_tomllib_skips_validation(
    tmp_path: Path, monkeypatch
):
    pytest.importorskip("tomlkit")
    p = tmp_path / "c.toml"
    p.write_text("[mcp_servers.s]\nenabled = true\n", encoding="utf-8")
    monkeypatch.setattr(codex_adapter, "tomllib", None)
    assert codex_adapter.set_server_enabled(p, "s", False) is True
    assert "enabled = false" in p.read_text(encoding="utf-8")


def test_set_server_enabled_without_backup(tmp_path: Path):
    pytest.importorskip("tomlkit")
    p = tmp_path / "c.toml"
    p.write_text("[mcp_servers.s]\nenabled = true\n", encoding="utf-8")
    assert codex_adapter.set_server_enabled(p, "s", False, backup=False) is True
    assert not (p.parent / ".mcp-manager-backups").exists()


# ── consolidation.py ──────────────────────────────────────────────────────────


def test_analyze_skills_missing_root_and_no_description(tmp_path: Path):
    root = tmp_path / "skills"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")
    missing = tmp_path / "does-not-exist"
    res = consolidation.analyze_skills([root, missing])
    assert res["skills_scanned"] == 1
    assert any(d["issue"] == "no description" for d in res["description_issues"])


def test_render_report_with_collisions_and_desc_issues():
    analysis = {
        "skills_scanned": 3,
        "unique_names": 2,
        "exact_duplicate_groups": [],
        "name_collisions": [{"name": "dup", "paths": ["/a", "/b"]}],
        "description_issues": [{"skill": "x", "path": "/x", "issue": "no description"}],
    }
    out = consolidation.render_report(analysis)
    assert "Name collisions" in out and "`dup`" in out
    assert "Description fixes" in out and "`x`" in out


# ── funnel_adapter.py ─────────────────────────────────────────────────────────


def _write_profiles(tmp_path: Path, profiles: dict) -> Path:
    pj = tmp_path / "profiles.json"
    pj.write_text(json.dumps({"profiles": profiles}), encoding="utf-8")
    return pj


def test_get_profile_servers_scalar_value(tmp_path: Path):
    pj = _write_profiles(tmp_path, {"solo": "only-one"})
    assert funnel_adapter.get_profile_servers("solo", pj) == ["only-one"]


def test_get_server_universe_skips_sentinel_and_scalar(tmp_path: Path):
    pj = _write_profiles(
        tmp_path, {"default": "*ALL*", "web": ["tavily", "exa"], "weird": "scalar"}
    )
    rows = funnel_adapter.get_server_universe(pj)
    assert sorted(r.name for r in rows) == ["exa", "tavily"]


def test_switch_profile_success(tmp_path: Path, monkeypatch):
    pj = _write_profiles(tmp_path, {"re": ["x"]})

    class _R:
        returncode = 0
        stdout = "switched\n"
        stderr = ""

    monkeypatch.setattr(funnel_adapter.subprocess, "run", lambda *a, **k: _R())
    ok, msg = funnel_adapter.switch_profile("re", profiles_json=pj)
    assert ok and msg == "switched"


def test_switch_profile_nonzero_exit(tmp_path: Path, monkeypatch):
    pj = _write_profiles(tmp_path, {"re": ["x"]})

    class _R:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(funnel_adapter.subprocess, "run", lambda *a, **k: _R())
    ok, msg = funnel_adapter.switch_profile("re", profiles_json=pj)
    assert not ok and msg == "boom"


def test_switch_profile_timeout(tmp_path: Path, monkeypatch):
    pj = _write_profiles(tmp_path, {"re": ["x"]})

    def _boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(funnel_adapter.subprocess, "run", _boom)
    ok, msg = funnel_adapter.switch_profile("re", profiles_json=pj, timeout=1)
    assert not ok and "timed out" in msg


def test_switch_profile_subprocess_error(tmp_path: Path, monkeypatch):
    pj = _write_profiles(tmp_path, {"re": ["x"]})

    def _boom(*_a, **_k):
        raise FileNotFoundError("nope")

    monkeypatch.setattr(funnel_adapter.subprocess, "run", _boom)
    ok, msg = funnel_adapter.switch_profile("re", profiles_json=pj)
    assert not ok and "failed to run" in msg


# ── inventory.py ──────────────────────────────────────────────────────────────


def test_scan_codex_without_tomllib(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(inventory, "tomllib", None)
    assert inventory.scan_codex(tmp_path / "config.toml") == {}


def test_scan_funnel_skips_nameless_specs(tmp_path: Path):
    mj = tmp_path / "master.json"
    mj.write_text(
        json.dumps({"servers": [{"name": "ok"}, {"noname": 1}, "str"]}),
        encoding="utf-8",
    )
    assert list(inventory.scan_funnel(mj)) == ["ok"]


def test_find_duplicate_skill_packs_ignores_empty_packs(tmp_path: Path):
    root = tmp_path / "skills"
    (root / "emptypack").mkdir(parents=True)  # no SKILL.md -> skipped
    for pack in ("packA", "packB"):
        (root / pack / "s1").mkdir(parents=True)
        (root / pack / "s1" / "SKILL.md").write_text(pack, encoding="utf-8")
    groups = inventory.find_duplicate_skill_packs([root, tmp_path / "missing"])
    assert any(len(g) == 2 for g in groups)


# ── status.py ─────────────────────────────────────────────────────────────────


def test_refresh_defaults_project_path():
    rows = asyncio.run(
        sm.refresh(
            claude_json=Path("nope"),
            codex_toml=Path("nope"),
            funnel_profiles=Path("nope"),
            mcp_list_output="",
            codex_json_output="[]",
        )
    )
    assert rows == []


def test_refresh_safe_fetch_swallows_errors(monkeypatch):
    async def _boom(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(sm, "_fetch_claude", _boom)
    monkeypatch.setattr(sm, "_fetch_codex", _boom)
    monkeypatch.setattr(sm, "_fetch_funnel", _boom)
    rows = asyncio.run(
        sm.refresh(project_path="P", mcp_list_output="x", codex_json_output="[]")
    )
    assert rows == []
