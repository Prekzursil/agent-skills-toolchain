"""Tests for app.py — the CLI surface (status/duplicates/consolidate/json)."""

import json
import runpy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app  # noqa: E402

_FAKE_INV = {
    "server_count": 3,
    "duplicated_servers": ["exa"],
    "servers": [
        {
            "name": "exa",
            "planes": ["claude", "codex"],
            "enabled_in": ["claude"],
            "disabled_in": ["codex"],
            "duplicated": True,
        },
        {
            "name": "tavily",
            "planes": ["claude"],
            "enabled_in": ["claude"],
            "disabled_in": [],
            "duplicated": False,
        },
        {
            "name": "ghost",
            "planes": ["codex"],
            "enabled_in": [],
            "disabled_in": [],
            "duplicated": False,
        },
    ],
}


@pytest.fixture
def patched_inventory(monkeypatch):
    monkeypatch.setattr(app, "build_inventory", lambda *a, **k: _FAKE_INV)


def test_cmd_status(capsys, patched_inventory):
    app.cmd_status()
    out = capsys.readouterr().out
    assert "MCP servers across planes: 3" in out
    assert "*DUP*" in out  # duplicated row marker
    assert "disabled:codex" in out  # disabled_in branch
    assert "ghost" in out  # enabled_in-empty (else) branch


def test_cmd_duplicates(capsys, patched_inventory):
    app.cmd_duplicates()
    out = capsys.readouterr().out
    assert "exa" in out
    assert "Total: 1 of 3" in out


def test_cmd_json(capsys, patched_inventory):
    app.cmd_json()
    assert json.loads(capsys.readouterr().out)["server_count"] == 3


def test_cmd_consolidate(monkeypatch, capsys):
    monkeypatch.setattr(app.consolidation, "analyze_skills", lambda roots: {"n": 1})
    monkeypatch.setattr(app.consolidation, "render_report", lambda a: "REPORT-OK")
    app.cmd_consolidate()
    assert "REPORT-OK" in capsys.readouterr().out


def test_main_default_is_status(capsys, patched_inventory):
    assert app.main(["app.py"]) == 0
    assert "MCP servers across planes" in capsys.readouterr().out


def test_main_named_command(capsys, patched_inventory):
    assert app.main(["app.py", "duplicates"]) == 0
    assert "Total:" in capsys.readouterr().out


def test_main_unknown_command_prints_help(capsys):
    assert app.main(["app.py", "__nope__"]) == 2
    assert "Usage" in capsys.readouterr().out


def test_dunder_main_entrypoint(monkeypatch):
    """Execute app.py as __main__ to cover the SystemExit guard."""
    monkeypatch.setattr(sys, "argv", ["app.py", "__nope__"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(Path(app.__file__)), run_name="__main__")
    assert exc.value.code == 2


# ── preset / apply CLI ─────────────────────────────────────────────────────────

from core.presets import (  # noqa: E402
    ApplyResult,
    PresetCatalog,
    ResolveResult,
)
from core import live_macro as _lm  # noqa: E402


def _empty_resolve() -> ResolveResult:
    return ResolveResult(
        to_disable=[],
        to_enable=[],
        matched={},
        unmatched_members=[],
        unknown_presets=[],
    )


@pytest.fixture
def fake_catalog(monkeypatch):
    cat = PresetCatalog(
        core=["basic-memory", "tavily"], presets={"re": ["ida-pro-mcp"]}
    )
    monkeypatch.setattr(app.presets_mod, "ensure_catalog_file", lambda *a, **k: cat)
    return cat


@pytest.fixture
def live_inv(monkeypatch):
    ids = ["basic-memory", "tavily", "ida-pro-mcp", "docker"]
    monkeypatch.setattr(app, "get_live_inventory_ids", lambda pp: list(ids))
    return ids


# _split_flags ------------------------------------------------------------------


def test_split_flags_all_kinds():
    pos, valued, bare = app._split_flags(
        ["a", "--from-paste", "f.txt", "--dry-run", "b", "--project", "P"]
    )
    assert pos == ["a", "b"]
    assert valued == {"from-paste": "f.txt", "project": "P"}
    assert bare == {"dry-run"}


def test_split_flags_valued_at_end_ignored():
    pos, valued, bare = app._split_flags(["--from-paste"])
    assert pos == [] and valued == {} and bare == set()


# current_project_path ----------------------------------------------------------


def test_current_project_path_normalised():
    p = app.current_project_path()
    assert "\\" not in p


# _read_paste -------------------------------------------------------------------


def test_read_paste_from_file(tmp_path):
    f = tmp_path / "dump.txt"
    f.write_text("hello", encoding="utf-8")
    assert app._read_paste(str(f)) == "hello"


def test_read_paste_from_stdin(monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("piped"))
    assert app._read_paste(None) == "piped"


# get_live_inventory_ids --------------------------------------------------------


def test_get_live_inventory_ids(monkeypatch):
    from core.models import ServerRow

    monkeypatch.setattr(
        app.claude_adapter,
        "get_server_universe",
        lambda cj, proj: [ServerRow(id="a", name="a"), ServerRow(id="b", name="b")],
    )
    assert app.get_live_inventory_ids("C:/x") == ["a", "b"]


# _resolve_inventory ------------------------------------------------------------


def test_resolve_inventory_paste_success(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("tavily · ✔ connected", encoding="utf-8")
    inv = app._resolve_inventory(str(f), "C:/x")
    assert inv is not None and inv[0] == ["tavily"]


def test_resolve_inventory_paste_read_error(capsys):
    assert app._resolve_inventory("Z:/nope/missing.txt", "C:/x") is None
    assert "Could not read paste" in capsys.readouterr().out


def test_resolve_inventory_paste_empty(tmp_path, capsys):
    f = tmp_path / "d.txt"
    f.write_text("74 servers\n↑/↓ to navigate", encoding="utf-8")
    assert app._resolve_inventory(str(f), "C:/x") is None
    assert "No servers parsed" in capsys.readouterr().out


def test_resolve_inventory_live_error(monkeypatch, capsys):
    def _boom(pp):
        raise RuntimeError("cli down")

    monkeypatch.setattr(app, "get_live_inventory_ids", _boom)
    assert app._resolve_inventory(None, "C:/x") is None
    assert "Could not query live inventory" in capsys.readouterr().out


def test_resolve_inventory_live_empty(monkeypatch, capsys):
    monkeypatch.setattr(app, "get_live_inventory_ids", lambda pp: [])
    assert app._resolve_inventory(None, "C:/x") is None
    assert "Live inventory is empty" in capsys.readouterr().out


# cmd_use -----------------------------------------------------------------------


def test_use_no_selection(capsys):
    assert app.cmd_use(["--dry-run"]) == 2
    assert "Usage: use" in capsys.readouterr().out


def test_use_inventory_failure_returns_1(monkeypatch):
    monkeypatch.setattr(app, "get_live_inventory_ids", lambda pp: [])
    assert app.cmd_use(["re"]) == 1


def test_use_unknown_preset(fake_catalog, live_inv, capsys):
    assert app.cmd_use(["bogus"]) == 2
    assert "Unknown preset" in capsys.readouterr().out


def test_use_dry_run(fake_catalog, live_inv, capsys):
    assert app.cmd_use(["re", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "DISABLE" in out


def test_use_apply_writes(fake_catalog, live_inv, monkeypatch, capsys):
    monkeypatch.setattr(
        app.presets_mod,
        "apply_selection",
        lambda *a, **k: ApplyResult(
            resolve=_empty_resolve(), newly_disabled=["docker"], newly_enabled=[]
        ),
    )
    assert app.cmd_use(["re"]) == 0
    out = capsys.readouterr().out
    assert "newly disabled" in out
    assert "NEXT session" in out


def test_use_unmatched_note(monkeypatch, live_inv, capsys):
    cat = PresetCatalog(core=["ghostserver"], presets={})
    monkeypatch.setattr(app.presets_mod, "ensure_catalog_file", lambda *a, **k: cat)
    assert app.cmd_use(["core", "--dry-run"]) == 0
    assert "no live match" in capsys.readouterr().out


def test_use_project_override(fake_catalog, live_inv, capsys):
    assert app.cmd_use(["re", "--project", "C:/custom", "--dry-run"]) == 0
    assert "C:/custom" in capsys.readouterr().out


# cmd_preset --------------------------------------------------------------------


def test_preset_list_default(fake_catalog, capsys):
    assert app.cmd_preset([]) == 0
    out = capsys.readouterr().out
    assert "core" in out and "re" in out


def test_preset_list_explicit(fake_catalog, capsys):
    assert app.cmd_preset(["list"]) == 0
    assert "Presets" in capsys.readouterr().out


def test_preset_apply_routes_to_use(fake_catalog, live_inv, capsys):
    assert app.cmd_preset(["apply", "re", "--dry-run"]) == 0
    assert "dry-run" in capsys.readouterr().out


def test_preset_save_too_few_args(capsys):
    assert app.cmd_preset(["save", "onlyname"]) == 2
    assert "Usage: preset save" in capsys.readouterr().out


def test_preset_save_success(monkeypatch, capsys):
    monkeypatch.setattr(app.presets_mod, "save_preset", lambda *a, **k: True)
    assert app.cmd_preset(["save", "foo", "a", "b"]) == 0
    assert "saved" in capsys.readouterr().out


def test_preset_delete_no_name(capsys):
    assert app.cmd_preset(["delete"]) == 2
    assert "Usage: preset delete" in capsys.readouterr().out


def test_preset_delete_found(monkeypatch, capsys):
    monkeypatch.setattr(app.presets_mod, "delete_preset", lambda *a, **k: True)
    assert app.cmd_preset(["delete", "foo"]) == 0
    assert "deleted" in capsys.readouterr().out


def test_preset_delete_missing(monkeypatch, capsys):
    monkeypatch.setattr(app.presets_mod, "delete_preset", lambda *a, **k: False)
    assert app.cmd_preset(["delete", "foo"]) == 0
    assert "not found" in capsys.readouterr().out


def test_preset_unknown_sub(capsys):
    assert app.cmd_preset(["frobnicate"]) == 2
    assert "Unknown preset subcommand" in capsys.readouterr().out


# cmd_parse_list ----------------------------------------------------------------


def test_parse_list_read_error(capsys):
    assert app.cmd_parse_list(["Z:/nope/missing.txt"]) == 1
    assert "Could not read" in capsys.readouterr().out


def test_parse_list_table(tmp_path, capsys):
    f = tmp_path / "d.txt"
    f.write_text("apktool-mcp · ✔ connected · 16 tools", encoding="utf-8")
    assert app.cmd_parse_list([str(f)]) == 0
    out = capsys.readouterr().out
    assert "apktool-mcp" in out and "connected" in out


def test_parse_list_json(tmp_path, capsys):
    f = tmp_path / "d.txt"
    f.write_text("tavily · ✔ connected", encoding="utf-8")
    assert app.cmd_parse_list([str(f), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["name"] == "tavily"


def test_parse_list_stdin(monkeypatch, capsys):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("exa · ✔ connected"))
    assert app.cmd_parse_list([]) == 0
    assert "exa" in capsys.readouterr().out


# cmd_try_live ------------------------------------------------------------------


def test_try_live_prints_warning_and_needs_selection(capsys):
    assert app.cmd_try_live([]) == 2
    assert "EXPERIMENTAL" in capsys.readouterr().out


def test_try_live_requires_paste(capsys):
    assert app.cmd_try_live(["re"]) == 2
    assert "REQUIRES --from-paste" in capsys.readouterr().out


def test_try_live_read_error(capsys):
    assert app.cmd_try_live(["re", "--from-paste", "Z:/nope.txt"]) == 1
    assert "Could not read paste" in capsys.readouterr().out


def test_try_live_no_servers(tmp_path, capsys):
    f = tmp_path / "d.txt"
    f.write_text("74 servers", encoding="utf-8")
    assert app.cmd_try_live(["re", "--from-paste", str(f)]) == 1
    assert "No servers parsed" in capsys.readouterr().out


def test_try_live_unknown_preset(tmp_path, fake_catalog, capsys):
    f = tmp_path / "d.txt"
    f.write_text("tavily · ✔ connected", encoding="utf-8")
    assert app.cmd_try_live(["bogus", "--from-paste", str(f)]) == 2
    assert "Unknown preset" in capsys.readouterr().out


def test_try_live_dry_run(tmp_path, fake_catalog, capsys):
    f = tmp_path / "d.txt"
    f.write_text(
        "tavily · ✔ connected\nida-pro-mcp · ◯ disabled\ndocker · ✔ connected",
        encoding="utf-8",
    )
    rc = app.cmd_try_live(["re", "--from-paste", str(f), "--window", "Terminal"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Plan" in out
    assert "dry-run" in out
    assert "check /mcp manually" in out


def test_sender_for_dry_is_noop():
    sender = app._sender_for(True)
    assert sender is app._noop_sender
    assert app._noop_sender(_lm.NavStep(_lm.ENTER)) is None


# main dispatch for new verbs ---------------------------------------------------


def test_main_routes_preset(fake_catalog, capsys):
    assert app.main(["app.py", "preset", "list"]) == 0
    assert "core" in capsys.readouterr().out


def test_main_routes_use(fake_catalog, live_inv, capsys):
    assert app.main(["app.py", "use", "re", "--dry-run"]) == 0
    assert "dry-run" in capsys.readouterr().out
