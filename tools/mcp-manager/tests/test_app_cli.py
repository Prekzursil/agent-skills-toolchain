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
