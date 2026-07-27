"""The CLI, end to end against tmp_path configs. Every seam injected."""

from __future__ import annotations

import json
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from mcpctl.sources import SourcePaths

from mcpapply import server as gui
from mcpapply.apply import MemoryFileStore, RealFileStore
from mcpapply.apply import ApplyResult
from mcpapply.cli import _run_gui, build_change, load_costs, main
from mcpapply.impact import Regime, preview
from mcpapply.plan import build_plan
from mcpapply.impact import TokenBasis
from conftest import FIXED_NOW, PROJECT_KEY, STAMP, write_home

QUIET = '"explorer.exe","4","Console","1","1 K"\n'


def _quiet(argv: Sequence[str]) -> str:
    assert argv
    return QUIET


def _busy(argv: Sequence[str]) -> str:
    assert argv
    return '"claude.exe","1","Console","1","1 K"\n'


class Sink:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _run(home: Path, *argv: str, runner=_quiet, **kwargs) -> tuple[int, Sink]:
    sink = Sink()
    code = main(
        [*argv, "--home", str(home), "--project", PROJECT_KEY],
        now=FIXED_NOW,
        runner=runner,
        write=sink,
        **kwargs,
    )
    return code, sink


# --------------------------------------------------------------------------
# DRY RUN IS THE DEFAULT
# --------------------------------------------------------------------------


def test_without_apply_nothing_on_disk_changes(home: Path, paths: SourcePaths):
    before = {label: p.read_bytes() for label, p in paths.as_tuple()}
    code, sink = _run(home, "disable", "cloud-hub")
    assert code == 0
    assert "DRY RUN -- nothing was written" in sink.text
    assert "SUCCESS:mcpapply-disable" in sink.text
    assert {label: p.read_bytes() for label, p in paths.as_tuple()} == before
    assert list(home.glob("**/*.bak")) == []


def test_the_dry_run_prints_the_plan_the_impact_and_the_diff(home: Path):
    _, sink = _run(home, "disable", "cloud-hub")
    assert "DISABLE cloud-hub (was: enabled)" in sink.text
    assert "+ claude_json:projects" in sink.text
    assert "tokens saved:  -" in sink.text  # nothing measured -> '-', never 0
    assert "next: re-run with --apply" in sink.text


def test_apply_writes_backs_up_and_prints_the_restore_command(
    home: Path, paths: SourcePaths
):
    original = paths.claude_json.read_bytes()
    code, sink = _run(home, "disable", "cloud-hub", "--apply")
    assert code == 0
    updated = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    assert "cloud-hub" in updated["projects"][PROJECT_KEY]["disabledMcpServers"]
    backup = home / f".claude.json.mcpapply-{STAMP}.bak"
    assert backup.read_bytes() == original
    assert "restore with:" in sink.text
    assert "Copy-Item" in sink.text
    assert "SUCCESS:mcpapply-disable 1 file(s) written" in sink.text


def test_a_running_host_blocks_the_write_and_exits_nonzero(
    home: Path, paths: SourcePaths
):
    before = paths.claude_json.read_bytes()
    code, sink = _run(home, "disable", "cloud-hub", "--apply", runner=_busy)
    assert code == 1
    assert "FAILED:mcpapply-disable" in sink.text
    assert "close every Claude Code window" in sink.text
    assert paths.claude_json.read_bytes() == before


def test_force_accepts_the_race_for_a_project_scope_write(home: Path):
    code, _ = _run(home, "disable", "cloud-hub", "--apply", "--force", runner=_busy)
    assert code == 0


def test_the_user_scope_promotion_gate_is_not_bypassed_by_force(home: Path):
    """`add` writes ~/.claude.json -> mcpServers, i.e. USER scope. That gate is human."""
    code, sink = _run(
        home,
        "add",
        "brand-new",
        "--spec",
        '{"command": "x"}',
        "--apply",
        "--force",
        runner=_busy,
    )
    assert code == 1
    assert "HUMAN step" in sink.text
    assert "--force does not apply here" in sink.text


# --------------------------------------------------------------------------
# Verbs
# --------------------------------------------------------------------------


def test_enable_clears_every_suppressor(tmp_path: Path):
    paths = write_home(
        tmp_path,
        claude_json={
            "mcpServers": {"z": {"command": "x"}},
            "disabledMcpServers": ["z"],
            "projects": {PROJECT_KEY: {"disabledMcpServers": ["z"]}},
        },
        settings={"deniedMcpServers": [{"serverName": "z"}]},
    )
    code, _ = _run(tmp_path, "enable", "z", "--apply")
    assert code == 0
    claude = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    settings = json.loads(paths.settings.read_text(encoding="utf-8"))
    assert claude["disabledMcpServers"] == []
    assert claude["projects"][PROJECT_KEY]["disabledMcpServers"] == []
    assert settings["deniedMcpServers"] == []


def test_add_and_edit_take_a_json_spec(home: Path, paths: SourcePaths):
    _run(
        home,
        "add",
        "fresh",
        "--scope",
        "mcp-json",
        "--spec",
        '{"command": "node"}',
        "--apply",
    )
    mcp = json.loads(paths.mcp_json.read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["fresh"] == {"command": "node"}
    # The unknown top-level key in that file survived the write.
    assert mcp["someUnknownTopLevelKey"] == {"nested": [1, 2, 3]}


def test_edit_replaces_an_existing_definition_in_place(home: Path, paths: SourcePaths):
    code, _ = _run(
        home,
        "edit",
        "cloud-hub",
        "--spec",
        '{"command": "python3"}',
        "--apply",
        "--force",
    )
    assert code == 0
    claude = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    assert claude["mcpServers"]["cloud-hub"] == {"command": "python3"}
    # Sibling definitions and the unknown top-level keys are untouched.
    assert claude["mcpServers"]["chrome-devtools"]["command"] == "npx"
    assert claude["oauthAccount"]["keep"] == "me"


def test_remove_deletes_the_definition(home: Path, paths: SourcePaths):
    _run(home, "remove", "ghidra-mcp", "--apply", "--force", runner=_quiet)
    claude = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    assert "ghidra-mcp" not in claude["mcpServers"]


def test_reconnect_without_live_is_a_usage_error_not_a_silent_success(
    home: Path, paths: SourcePaths
):
    """`reconnect` has no on-disk form, so it must never report a bare SUCCESS.

    Regression: it used to print ``SUCCESS:mcpapply-reconnect 0 file(s) written`` and
    exit 0 while doing nothing whatsoever -- no config write (correct: it has none)
    and no control frame either, because no production path built a client.
    """
    before = paths.claude_json.read_bytes()
    code, sink = _run(home, "reconnect", "cloud-hub", "--apply")
    assert code == 1
    assert paths.claude_json.read_bytes() == before
    assert "FAILED:mcpapply-reconnect" in sink.text
    assert "needs --live" in sink.text
    assert "SUCCESS" not in sink.text


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


def test_a_missing_server_name_is_a_usage_error_not_a_crash(home: Path):
    code, sink = _run(home, "disable")
    assert code == 1
    assert "needs a server name" in sink.text
    assert "FAILED:mcpapply-disable" in sink.text


def test_a_bad_spec_is_reported_with_a_recovery_path(home: Path):
    code, sink = _run(home, "add", "x", "--spec", "{not json")
    assert code == 1
    assert "not valid JSON" in sink.text
    assert "stop:" in sink.text


def test_a_non_object_spec_is_refused(home: Path):
    code, sink = _run(home, "edit", "cloud-hub", "--spec", "[1,2]")
    assert code == 1
    assert "must be a JSON object" in sink.text


def test_an_unreadable_source_is_surfaced_as_a_warning_not_hidden(
    home: Path, paths: SourcePaths
):
    paths.settings.write_text("{ broken", encoding="utf-8")
    code, sink = _run(home, "disable", "cloud-hub")
    assert code == 0
    assert "UNREADABLE settings" in sink.text


def test_a_problem_during_apply_downgrades_to_a_warning(home: Path, paths: SourcePaths):
    """A hand-edited list-shaped key holding a string: report it, never clobber it."""
    paths.claude_json.write_text(
        json.dumps(
            {
                "mcpServers": {"a": {"command": "x"}},
                "projects": {PROJECT_KEY: {"disabledMcpServers": "hand-edited"}},
            }
        ),
        encoding="utf-8",
    )
    code, sink = _run(home, "disable", "a", "--apply")
    assert code == 0
    assert "SUCCESS:mcpapply-disable" in sink.text
    assert "problem(s)" in sink.text
    assert "not a list" in sink.text
    claude = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    assert claude["projects"][PROJECT_KEY]["disabledMcpServers"] == "hand-edited"


# --------------------------------------------------------------------------
# JSON output
# --------------------------------------------------------------------------


def test_json_output_carries_the_envelope_plan_impact_and_result(home: Path):
    _, sink = _run(home, "disable", "cloud-hub", "--json")
    payload = json.loads(sink.text)
    assert payload["envelope"]["status"] == "success"
    assert payload["plan"]["changes"][0]["server"] == "cloud-hub"
    assert payload["impact"]["token_delta"] is None
    assert payload["result"]["dry_run"] is True
    assert payload["terminal"].startswith("SUCCESS:")


def test_json_output_on_the_error_path_exits_one(home: Path):
    code, sink = _run(home, "disable", "cloud-hub", "--apply", "--json", runner=_busy)
    assert code == 1
    assert json.loads(sink.text)["envelope"]["status"] == "error"


# --------------------------------------------------------------------------
# Costs
# --------------------------------------------------------------------------


def test_measured_costs_turn_the_dash_into_a_number(home: Path, tmp_path: Path):
    costs = tmp_path / "costs.json"
    costs.write_text(
        json.dumps(
            {
                "cloud-hub": {
                    "tool_count": 409,
                    "token_cost": 77198,
                    "token_basis": "exact-count-tokens",
                    "commit_bytes": 17400000,
                    "proc_count": 2,
                    "measured_at": "2026-07-27",
                }
            }
        ),
        encoding="utf-8",
    )
    _, sink = _run(
        home, "disable", "cloud-hub", "--costs", str(costs), "--tool-search", "auto:5"
    )
    assert "tokens saved:  77198" in sink.text
    assert "regime:        deferred" in sink.text
    assert "DEFERRED tool loading" in sink.text


def test_the_costs_reader_keeps_unknown_and_bad_fields_unmeasured():
    parsed = load_costs(
        json.dumps(
            {
                "a": {"token_cost": 5, "token_basis": "made-up", "remote": True},
                "b": {"token_cost": "not an int", "commit_bytes": True},
                "c": "not even an object",
            }
        )
    )
    assert parsed["a"].token_basis is TokenBasis.NOT_MEASURED
    assert parsed["a"].remote is True
    assert parsed["b"].token_cost is None
    # `True` is an int in Python; it must NOT be read as 1 byte of commit.
    assert parsed["b"].commit_bytes is None
    assert parsed["c"].tool_count is None


def test_a_non_object_costs_file_is_refused():
    with pytest.raises(ValueError, match="keyed by server name"):
        load_costs("[]")


# --------------------------------------------------------------------------
# GUI command
# --------------------------------------------------------------------------


def test_the_gui_command_wires_every_port(home: Path):
    captured: list[gui.GuiPorts] = []

    def fake_serve(ports: gui.GuiPorts, port: int) -> int:
        captured.append(ports)
        assert port == 8123
        return 0

    code, _ = _run(home, "gui", "--port", "8123", serve_fn=fake_serve)
    assert code == 0
    (ports,) = captured
    assert len(ports.token) >= 32
    names = {row.name for row in ports.rows()}
    assert "cloud-hub" in names
    plan = ports.plan_for("disable", "cloud-hub")
    assert plan.changes[0].intent.value == "disable"
    assert ports.impact_for(plan).token_delta is None
    assert ports.apply_plan(plan, False).dry_run is True


def test_the_gui_apply_port_honours_the_confirm_flag(home: Path, paths: SourcePaths):
    captured: list[gui.GuiPorts] = []
    _run(home, "gui", serve_fn=lambda p, _port: (captured.append(p), 0)[1])
    ports = captured[0]
    plan = ports.plan_for("disable", "cloud-hub")

    before = paths.claude_json.read_bytes()
    assert ports.apply_plan(plan, False).written == ()
    assert paths.claude_json.read_bytes() == before

    assert ports.apply_plan(plan, True).written != ()
    assert paths.claude_json.read_bytes() != before


def test_the_gui_plan_port_rejects_an_unknown_intent(home: Path):
    captured: list[gui.GuiPorts] = []
    _run(home, "gui", serve_fn=lambda p, _port: (captured.append(p), 0)[1])
    with pytest.raises(ValueError, match="not offered by the GUI"):
        captured[0].plan_for("rm -rf", "cloud-hub")


@pytest.mark.parametrize("intent", ["add", "edit", "remove", "reconnect"])
def test_the_gui_api_refuses_every_verb_its_form_does_not_offer(
    home: Path, intent: str
):
    """The dropdown and the API allowlist are ONE list, so they cannot drift.

    Regression: the form offered three intents while the API accepted all six, so
    ``edit`` was reachable over HTTP with no spec field to fill -- and an ``edit`` with
    no spec replaced a live definition with ``{}``.
    """
    captured: list[gui.GuiPorts] = []
    _run(home, "gui", serve_fn=lambda p, _port: (captured.append(p), 0)[1])
    assert intent not in gui.GUI_INTENTS
    with pytest.raises(ValueError, match="not offered by the GUI"):
        captured[0].plan_for(intent, "cloud-hub")


# --------------------------------------------------------------------------
# Defaults and wiring
# --------------------------------------------------------------------------


def test_build_change_dispatches_every_verb(top):
    for verb in ("enable", "disable", "remove", "reconnect"):
        assert (
            build_change(verb, top, "cloud-hub", "", "claude-user").intent.value == verb
        )
    spec = '{"command": "npx"}'
    assert build_change("add", top, "n", spec, "claude-user").edits[0].spec == {
        "command": "npx"
    }
    assert build_change("edit", top, "cloud-hub", spec, "claude-user").edits[
        0
    ].spec == {"command": "npx"}


@pytest.mark.parametrize("verb", ["add", "edit"])
def test_a_definition_verb_with_no_spec_REFUSES_instead_of_writing_an_empty_object(
    top, verb: str
):
    """The one-word wipe: ``mcpapply edit cloud-hub --apply`` with no --spec.

    ``--spec`` defaults to ``""`` -> ``json.loads("{}")`` -> ``{}`` -> the whole
    definition (command, args and the entire env block) replaced with an empty object,
    reported as SUCCESS. The curation is LOAD-BEARING, so this must REFUSE.
    """
    with pytest.raises(ValueError, match="EMPTY spec"):
        build_change(verb, top, "cloud-hub", "", "claude-user")


def test_the_default_store_and_clock_are_real(tmp_path: Path):
    """Binds the PRODUCTION defaults (RealFileStore + the wall clock) once."""
    write_home(tmp_path)
    sink = Sink()
    code = main(
        ["disable", "cloud-hub", "--home", str(tmp_path), "--project", PROJECT_KEY],
        runner=_quiet,
        write=sink,
    )
    assert code == 0
    assert "DRY RUN" in sink.text


def test_a_loader_can_be_injected_for_a_hermetic_read(home: Path):
    seen: list[SourcePaths] = []

    def loader(paths: SourcePaths):
        seen.append(paths)
        from mcpctl.sources import load_sources

        return load_sources(paths)

    code, _ = _run(home, "disable", "cloud-hub", loader=loader)
    assert code == 0
    assert len(seen) == 1


def test_an_injected_store_is_used_instead_of_the_real_one(home: Path):
    store = MemoryFileStore()
    code, sink = _run(home, "disable", "cloud-hub", store=store)
    assert code == 0
    # The MemoryFileStore knows about no files, so every scope reads as absent.
    assert "created" not in sink.text or store.writes == []


def test_run_as_a_module_executes_main_and_exits(monkeypatch, capsys, home: Path):
    monkeypatch.setattr(sys, "argv", ["mcpapply", "disable", "--home", str(home)])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("mcpapply", run_name="__main__")
    assert excinfo.value.code == 1
    assert "needs a server name" in capsys.readouterr().out


def test_importing_the_entry_point_does_not_execute_it():
    import mcpapply.__main__ as entry

    assert callable(entry.main)


def test_the_package_declares_its_version():
    import mcpapply

    assert mcpapply.__version__ == "0.1.0"


def test_the_real_store_is_the_default_type():
    assert isinstance(RealFileStore(), RealFileStore)


def test_the_gui_shell_prints_its_url_and_closes_cleanly_on_ctrl_c(home: Path):
    """Covers the blocking shell WITHOUT asserting that a blocking call blocks:
    `make_server` is injected, so the real serve()/serve_forever() pair stays in
    tests/test_server.py where it runs against a live loopback socket."""
    events: list[str] = []

    class FakeServer:
        server_address = ("127.0.0.1", 54321)

        def serve_forever(self) -> None:
            events.append("served")
            raise KeyboardInterrupt

        def server_close(self) -> None:
            events.append("closed")

    sink = Sink()
    code = _run_gui(
        gui.GuiPorts(
            rows=lambda: (),
            plan_for=lambda intent, server: build_plan([], project_key=None),
            impact_for=lambda plan: preview(plan, {}, regime=Regime.UNKNOWN),
            apply_plan=lambda plan, confirmed: ApplyResult(dry_run=True),
            token="t",
        ),
        port=0,
        write=sink,
        make_server=lambda ports, port: FakeServer(),
    )
    assert code == 0
    assert events == ["served", "closed"]
    assert "http://127.0.0.1:54321/" in sink.text
    assert "stopped" in sink.text


def test_the_default_gui_shell_binds_the_real_server(home: Path, monkeypatch):
    """One binding of the PRODUCTION default make_server, shut down immediately."""
    import threading

    started = threading.Event()
    captured: list[object] = []

    def stop_soon(ports, port):
        server = gui.serve(ports, port=port)
        captured.append(server)
        threading.Timer(0.05, server.shutdown).start()
        started.set()
        return server

    captured_ports: list[gui.GuiPorts] = []
    _run(home, "gui", serve_fn=lambda p, _n: (captured_ports.append(p), 0)[1])
    sink = Sink()
    code = _run_gui(captured_ports[0], port=0, write=sink, make_server=stop_soon)
    assert code == 0
    assert started.is_set()
    assert "mcpapply GUI on http://127.0.0.1:" in sink.text
