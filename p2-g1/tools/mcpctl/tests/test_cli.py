"""Tests for the read-only CLI.

Every test injects the source loader and the writer, so no test reads the real
``~/.claude.json`` and no test writes to stdout. The suite also asserts the two
non-negotiables: a terminal ``SUCCESS:``/``FAILED:`` line on every path, and no
credential value anywhere in the output.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from mcpctl import cli, sources, topology

FAKE_TOKEN = "ghp_" + "Q" * 36


def docs() -> topology.SourceDocs:
    return topology.SourceDocs(
        claude_json={
            "mcpServers": {
                "alpha": {"command": "node", "env": {"ALPHA_TOKEN": FAKE_TOKEN}},
                "beta": {"type": "sse", "url": "https://x.invalid"},
            },
            "disabledMcpServers": ["beta"],
            "projects": {"C:/proj": {"disabledMcpServers": ["alpha"]}},
        },
        mcp_json={"mcpServers": {"gamma": {"command": "uvx"}}},
        settings={"deniedMcpServers": [{"serverName": "delta"}]},
        settings_local={"enabledMcpjsonServers": ["gamma"]},
        disabled_defaults={"disabledMcpServers": ["beta"]},
    )


def loader(problems: tuple[sources.SourceProblem, ...] = ()):
    def _load(paths: sources.SourcePaths, **_kw: object):
        return docs(), problems

    return _load


def run(argv: list[str], **kw) -> tuple[int, str]:
    out: list[str] = []
    code = cli.main(
        argv,
        loader=kw.pop("loader", loader()),
        write=out.append,
        **kw,
    )
    return code, "\n".join(out)


# ------------------------------------------------------------------ happy paths


def test_no_subcommand_defaults_to_the_matrix():
    code, text = run([])
    assert code == 0
    assert "SERVER" in text
    assert "alpha" in text


def test_matrix_subcommand_prints_the_table_and_a_success_terminal_line():
    code, text = run(["matrix"])
    assert code == 0
    assert text.splitlines()[-1].startswith("SUCCESS:mcpctl-matrix")
    assert "4 server" in text.splitlines()[-1]


def test_topology_subcommand_prints_the_scope_report():
    code, text = run(["topology"])
    assert code == 0
    assert "MCP configuration topology" in text
    assert text.splitlines()[-1].startswith("SUCCESS:mcpctl-topology")


def test_credentials_subcommand_prints_names_only():
    code, text = run(["credentials"])
    assert code == 0
    assert "ALPHA_TOKEN" in text
    assert FAKE_TOKEN not in text


def test_conflicts_subcommand_reports_the_advisory_loadout_note():
    code, text = run(["conflicts"])
    assert code == 0
    assert text.startswith("beta")
    assert "advisory only" in text


def test_conflicts_subcommand_says_so_when_there_are_none():
    def clean_loader(paths: sources.SourcePaths, **_kw: object):
        return topology.SourceDocs(
            claude_json={"mcpServers": {"solo": {"command": "c"}}}
        ), ()

    code, text = run(["conflicts"], loader=clean_loader)
    assert code == 0
    assert "no scope conflicts" in text


def test_project_flag_selects_the_project_row_and_changes_the_verdict():
    _code, without = run(["matrix"])
    _code, with_proj = run(["matrix", "--project", "C:/proj"])
    alpha_without = next(ln for ln in without.splitlines() if ln.startswith("alpha"))
    alpha_with = next(ln for ln in with_proj.splitlines() if ln.startswith("alpha"))
    assert "enabled" in alpha_without
    assert "disabled" in alpha_with


def test_json_flag_emits_the_envelope_plus_rows_and_nothing_else():
    code, text = run(["matrix", "--json"])
    assert code == 0
    payload = json.loads(text)
    assert payload["envelope"]["status"] == "success"
    assert payload["envelope"]["next_actions"]
    assert payload["counts"]["total"] == 4
    assert [r["name"] for r in payload["rows"]] == ["alpha", "beta", "delta", "gamma"]
    assert FAKE_TOKEN not in text


def test_json_output_carries_the_terminal_line_as_a_field():
    _code, text = run(["matrix", "--json"])
    assert json.loads(text)["terminal"].startswith("SUCCESS:mcpctl-matrix")


def test_json_topology_reports_precedence_and_the_project_row_flag():
    _code, text = run(["topology", "--json"])
    payload = json.loads(text)
    assert payload["precedence"][0] == "settings-denied"
    assert payload["project_row_found"] is False


# -------------------------------------------------------------- degraded paths


def test_an_unreadable_source_degrades_to_a_warning_not_a_failure():
    problems = (
        sources.SourceProblem(
            label="settings", path="H:/x", reason="PermissionError: x"
        ),
    )
    code, text = run(["matrix"], loader=loader(problems))
    assert code == 0
    assert text.splitlines()[-1].startswith("SUCCESS:mcpctl-matrix")
    assert "1 source unreadable" in text
    assert "settings" in text


def test_a_warning_envelope_lists_the_problem_in_json_mode():
    problems = (
        sources.SourceProblem(
            label="settings", path="H:/x", reason="PermissionError: x"
        ),
    )
    _code, text = run(["matrix", "--json"], loader=loader(problems))
    payload = json.loads(text)
    assert payload["envelope"]["status"] == "warning"
    assert payload["problems"][0]["label"] == "settings"


def test_every_source_unreadable_is_an_error_with_the_full_recovery_triple():
    problems = tuple(
        sources.SourceProblem(label=label, path="H:/x", reason="PermissionError: x")
        for label, _ in sources.source_paths(Path("H:/home")).as_tuple()
    )

    def empty_loader(paths: sources.SourcePaths, **_kw: object):
        return topology.SourceDocs(), problems

    code, text = run(["matrix"], loader=empty_loader)
    assert code == 1
    assert text.splitlines()[-1].startswith("FAILED:mcpctl-matrix")
    assert "root cause:" in text
    assert "retry:" in text
    assert "stop:" in text


def test_the_error_path_in_json_mode_carries_root_cause_retry_and_stop():
    problems = tuple(
        sources.SourceProblem(label=label, path="H:/x", reason="OSError: x")
        for label, _ in sources.source_paths(Path("H:/home")).as_tuple()
    )

    def empty_loader(paths: sources.SourcePaths, **_kw: object):
        return topology.SourceDocs(), problems

    code, text = run(["matrix", "--json"], loader=empty_loader)
    assert code == 1
    env = json.loads(text)["envelope"]
    assert env["status"] == "error"
    assert env["root_cause"]
    assert env["retry"]
    assert env["stop_condition"]


def test_no_sources_at_all_and_no_problems_is_an_empty_but_successful_read():
    def empty_loader(paths: sources.SourcePaths, **_kw: object):
        return topology.SourceDocs(), ()

    code, text = run(["matrix"], loader=empty_loader)
    assert code == 0
    assert "no MCP servers found" in text


# ------------------------------------------------------------------ invariants


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["matrix"],
        ["topology"],
        ["credentials"],
        ["conflicts"],
        ["matrix", "--json"],
    ],
)
def test_every_subcommand_ends_in_a_terminal_state_line(argv):
    _code, text = run(argv)
    if "--json" in argv:
        assert json.loads(text)["terminal"].startswith(("SUCCESS:", "FAILED:"))
    else:
        assert text.splitlines()[-1].startswith(("SUCCESS:", "FAILED:"))


def test_an_unknown_subcommand_exits_nonzero_via_argparse():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["frobnicate"], loader=loader(), write=lambda _s: None)
    assert excinfo.value.code == 2


def test_home_flag_is_threaded_into_the_source_paths():
    seen: list[Path] = []

    def recording_loader(paths: sources.SourcePaths, **_kw: object):
        seen.append(paths.claude_json)
        return docs(), ()

    run(["matrix", "--home", "H:/elsewhere"], loader=recording_loader)
    assert seen == [Path("H:/elsewhere/.claude.json")]


def test_default_home_is_used_when_the_flag_is_absent():
    seen: list[Path] = []

    def recording_loader(paths: sources.SourcePaths, **_kw: object):
        seen.append(paths.claude_json)
        return docs(), ()

    run(["matrix"], loader=recording_loader)
    assert seen[0] == sources.default_home() / ".claude.json"


#: Calls that would give the package a write or an out-of-process capability.
#:
#: Matched against the AST, NOT the file text. Two false-positive classes made a
#: substring scan useless here and both are recorded defect classes in this repo:
#:   * use-vs-mention -- a plain scan fires on the module docstrings that *describe*
#:     this very prohibition;
#:   * bare-attribute ambiguity -- `s.replace("\\", "/")` is a str method and
#:     `write(...)` is this CLI's injected stdout sink; neither touches a file.
#: So bare method names are restricted to ones that are unambiguous on any receiver,
#: and everything else must be qualified by an `os`/`shutil`/`subprocess` receiver.
_BARE_BANNED = frozenset({"open", "eval", "exec", "compile", "__import__"})
_METHOD_BANNED = frozenset(
    {
        "write_text",
        "write_bytes",
        "writelines",
        "mkdir",
        "makedirs",
        "rmtree",
        "unlink",
        "rmdir",
        "touch",
        "copyfile",
        "copytree",
        "check_output",
        "Popen",
    }
)
_BANNED_RECEIVERS = frozenset({"os", "shutil", "subprocess", "socket"})
_BANNED_IMPORTS = frozenset(
    {"subprocess", "shutil", "socket", "urllib", "http", "ctypes"}
)


def _write_capabilities(source: str) -> set[str]:
    import ast

    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names} & _BANNED_IMPORTS
        elif isinstance(node, ast.ImportFrom) and node.module:
            found |= {node.module.split(".")[0]} & _BANNED_IMPORTS
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BARE_BANNED:
                found.add(func.id)
            elif isinstance(func, ast.Attribute):
                if func.attr in _METHOD_BANNED:
                    found.add(func.attr)
                elif (
                    isinstance(func.value, ast.Name)
                    and func.value.id in _BANNED_RECEIVERS
                ):
                    found.add(f"{func.value.id}.{func.attr}")
    return found


def test_the_detector_fires_on_every_write_shape_it_claims_to_catch():
    """Detector control: prove the probe CAN see a write before trusting its silence."""
    assert _write_capabilities("p.write_text('x')") == {"write_text"}
    assert _write_capabilities("open('f', 'w')") == {"open"}
    assert _write_capabilities("import os\nos.replace(a, b)") == {"os.replace"}
    assert _write_capabilities("import subprocess") == {"subprocess"}
    assert _write_capabilities("from shutil import copy") == {"shutil"}
    # ...and stays silent on the three shapes that are NOT writes.
    assert _write_capabilities('"""never call open() or os.replace()."""') == set()
    assert _write_capabilities("s.replace('a', 'b')") == set()
    assert _write_capabilities("import os\nos.path.expanduser('~')") == set()


def test_the_package_makes_no_write_or_out_of_process_call():
    """Read-only + hermetic are hard properties of this unit; assert them over the AST."""
    package = Path(cli.__file__).parent
    offenders = {
        path.name: sorted(_write_capabilities(path.read_text(encoding="utf-8")))
        for path in sorted(package.glob("*.py"))
    }
    assert {name: hits for name, hits in offenders.items() if hits} == {}


def test_run_as_a_module_executes_main_and_exits(monkeypatch, capsys):
    """Covers __main__.py in BOTH directions: imported, and run as __main__."""
    monkeypatch.setattr(sys, "argv", ["mcpctl", "topology", "--home", "H:/nope"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("mcpctl", run_name="__main__")
    assert excinfo.value.code == 0
    assert "MCP configuration topology" in capsys.readouterr().out


def test_main_module_import_does_not_execute():
    import mcpctl.__main__ as entry

    assert callable(entry.main)
