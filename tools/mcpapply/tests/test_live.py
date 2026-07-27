"""The control channel, driven entirely by a FAKE transport.

NOT ONE test in this file spawns a host session. The single real-session smoke is
marked ``live`` and default-deselected (see ``tests/conftest.py`` and the CI step's
``-m "not live"``); the production transport is proven against a short-lived Python
child instead, which exercises the same code path with none of the risk.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator, Sequence

import pytest
from mcpctl.scopes import ScopeId

from mcpapply.live import (
    AFFORDANCES,
    INTENT_OPS,
    Affordance,
    default_live_client,
    render_live,
    run_live,
    ControlError,
    LiveClient,
    LiveOp,
    Proof,
    SubprocessTransport,
    affordance,
    control_frame,
    default_spawn,
    kick_frame,
    liveness_from_status,
    parse_frame,
    session_argv,
    status_servers,
)


class FakeTransport:
    """Replays scripted frames. Records every line the client sends."""

    def __init__(self, script: Sequence[str]) -> None:
        self.script = list(script)
        self.sent: list[str] = []

    def send(self, line: str) -> None:
        self.sent.append(line)

    def lines(self) -> Iterator[str]:
        yield from self.script


def _ok(request_id: str, payload: object = None) -> str:
    body: dict[str, object] = {"subtype": "success", "request_id": request_id}
    if payload is not None:
        body["response"] = payload
    return json.dumps({"type": "control_response", "response": body})


def _err(request_id: str, message: str) -> str:
    return json.dumps(
        {
            "type": "control_response",
            "response": {
                "subtype": "error",
                "request_id": request_id,
                "error": message,
            },
        }
    )


def _ids(*values: str):
    it = iter(values)
    return lambda: next(it)


# --------------------------------------------------------------------------
# Frame shapes
# --------------------------------------------------------------------------


def test_the_session_argv_carries_the_flags_the_protocol_requires():
    argv = session_argv("claude.exe")
    assert argv[1] == "-p"
    assert "--input-format" in argv and "stream-json" in argv
    # --verbose is REQUIRED with stream-json output under -p.
    assert "--verbose" in argv
    assert "--strict-mcp-config" not in argv


def test_strict_isolation_is_opt_in_because_it_breaks_the_persistent_path():
    argv = session_argv("claude.exe", strict_config="empty.json")
    assert argv[-2:] == ("--mcp-config", "empty.json")
    assert "--strict-mcp-config" in argv


def test_the_kick_frame_is_a_plain_user_message():
    frame = json.loads(kick_frame())
    assert frame["type"] == "user"
    assert frame["message"]["role"] == "user"


def test_a_control_frame_is_one_json_line():
    line = control_frame("id-1", {"subtype": "mcp_status"})
    assert "\n" not in line
    assert json.loads(line) == {
        "type": "control_request",
        "request_id": "id-1",
        "request": {"subtype": "mcp_status"},
    }


# --------------------------------------------------------------------------
# Parsing -- the DOUBLE nesting is the documented false-negative trap
# --------------------------------------------------------------------------


def test_the_payload_is_read_from_the_INNER_response_not_the_outer():
    parsed = parse_frame(_ok("x", {"mcpServers": [{"name": "a"}]}))
    assert parsed.is_control is True
    assert parsed.payload == {"mcpServers": [{"name": "a"}]}


def test_a_response_with_no_payload_parses_as_an_empty_payload():
    """reconnect and toggle omit `response` entirely; that is success, not failure."""
    parsed = parse_frame(_ok("x"))
    assert parsed.is_control is True
    assert parsed.payload == {}
    assert parsed.error == ""


def test_an_error_frame_carries_its_message_control_stripped():
    parsed = parse_frame(_err("x", "Server not found: n\x1b[0m"))
    assert parsed.error == "Server not found: n[0m"
    assert "\x1b" not in parsed.error


def test_an_error_frame_without_a_message_still_parses():
    line = json.dumps(
        {
            "type": "control_response",
            "response": {"subtype": "error", "request_id": "x"},
        }
    )
    assert "unspecified control error" in parse_frame(line).error


def test_a_request_id_only_on_the_outer_envelope_is_still_matched():
    line = json.dumps(
        {
            "type": "control_response",
            "request_id": "outer",
            "response": {"subtype": "success"},
        }
    )
    assert parse_frame(line).request_id == "outer"


def test_ordinary_session_traffic_and_junk_are_skipped_not_raised():
    for line in (
        "not json at all",
        "[1, 2, 3]",
        json.dumps({"type": "assistant", "message": {}}),
        json.dumps({"type": "control_response", "response": "not an object"}),
    ):
        assert parse_frame(line).is_control is False


def test_status_servers_is_null_guarded_against_a_shape_change():
    assert status_servers({}) == ()
    assert status_servers({"mcpServers": "nope"}) == ()
    assert status_servers({"mcpServers": [{"name": "a"}, "junk"]}) == ({"name": "a"},)


# --------------------------------------------------------------------------
# Correlation
# --------------------------------------------------------------------------


def test_a_response_is_matched_by_id_through_interleaved_out_of_order_traffic():
    transport = FakeTransport(
        [
            json.dumps({"type": "system", "subtype": "init"}),
            _ok("other-request", {"mcpServers": []}),
            "corrupt half-line",
            _ok("mine", {"mcpServers": [{"name": "a", "tools": [{"name": "t"}]}]}),
        ]
    )
    client = LiveClient(transport, new_id=_ids("mine"))
    assert client.status() == ({"name": "a", "tools": [{"name": "t"}]},)


def test_an_error_response_raises_with_the_servers_own_message():
    transport = FakeTransport([_err("mine", "Server not found: ghost")])
    client = LiveClient(transport, new_id=_ids("mine"))
    with pytest.raises(ControlError, match="Server not found: ghost"):
        client.reconnect("ghost")


def test_a_stream_that_ends_without_an_answer_raises_and_names_the_boot_cost():
    client = LiveClient(FakeTransport([]), new_id=_ids("mine"))
    with pytest.raises(ControlError, match="104-275 s"):
        client.status()


def test_the_frame_budget_stops_an_endless_stream():
    def endless() -> Iterator[str]:
        while True:
            yield json.dumps({"type": "assistant"})

    class Endless(FakeTransport):
        def lines(self) -> Iterator[str]:
            return endless()

    client = LiveClient(Endless([]), new_id=_ids("mine"), max_frames=5)
    with pytest.raises(ControlError, match="no control response"):
        client.status()


def test_the_kick_precedes_control_and_is_recorded():
    transport = FakeTransport([_ok("mine")])
    client = LiveClient(transport, new_id=_ids("mine"))
    client.kick()
    client.toggle("a", enabled=False)
    assert json.loads(transport.sent[0])["type"] == "user"
    assert json.loads(transport.sent[1])["request"] == {
        "subtype": "mcp_toggle",
        "serverName": "a",
        "enabled": False,
    }
    assert client.sent == transport.sent


def test_set_servers_sends_the_whole_replacement_set():
    transport = FakeTransport(
        [_ok("mine", {"added": ["a"], "removed": [], "errors": {}})]
    )
    client = LiveClient(transport, new_id=_ids("mine"))
    result = client.set_dynamic_servers({"a": {"type": "stdio", "command": "x"}})
    assert result == {"added": ["a"], "removed": [], "errors": {}}
    assert json.loads(transport.sent[0])["request"]["servers"] == {
        "a": {"type": "stdio", "command": "x"}
    }


def test_a_partial_failure_is_a_SUCCESS_frame_with_a_populated_errors_map():
    """The untested-in-the-wild shape: it must not be mistaken for a clean success."""
    transport = FakeTransport(
        [_ok("mine", {"added": [], "removed": [], "errors": {"b": "spawn failed"}})]
    )
    client = LiveClient(transport, new_id=_ids("mine"))
    result = client.set_dynamic_servers({"b": {"command": "x"}})
    assert result["errors"] == {"b": "spawn failed"}


# --------------------------------------------------------------------------
# Projection onto mcpctl's liveness seam
# --------------------------------------------------------------------------


def test_a_broken_server_has_an_UNKNOWN_tool_count_not_zero():
    """Measured: `tools` is absent for 4 of 64 servers (failed / needs-auth)."""
    live = liveness_from_status(
        {
            "mcpServers": [
                {"name": "ok", "status": "connected", "tools": [{"name": "t"}]},
                {"name": "broken", "status": "failed"},
                {"name": "unauthed", "status": "needs-auth"},
                {"no": "name"},
            ]
        }
    )
    assert live["ok"].tool_count == 1
    assert live["ok"].last_error is None
    assert live["broken"].tool_count is None
    assert live["broken"].last_error == "failed"
    assert live["unauthed"].last_error == "needs-auth"
    assert set(live) == {"ok", "broken", "unauthed"}


def test_a_hostile_server_name_from_the_wire_is_made_safe():
    live = liveness_from_status({"mcpServers": [{"name": "ev\x1b[31mil", "tools": []}]})
    assert "\x1b" not in next(iter(live))


# --------------------------------------------------------------------------
# Per-scope affordances -- the correction to the "any scope" folklore
# --------------------------------------------------------------------------


def test_project_scope_toggle_is_recorded_as_a_CLEAN_NEGATIVE():
    entry = affordance(ScopeId.MCP_JSON, LiveOp.TOGGLE)
    assert entry.proof is Proof.DISPROVEN
    assert entry.offer is False
    assert "CLEAN NEGATIVE" in entry.note


def test_user_scope_toggle_is_offered_but_labelled_provisional():
    entry = affordance(ScopeId.CLAUDE_USER, LiveOp.TOGGLE)
    assert entry.proof is Proof.PROVISIONAL
    assert entry.offer is True
    assert "n=1" in entry.note


def test_an_unrecorded_pair_defaults_to_unproven_not_to_yes():
    entry = affordance(ScopeId.SETTINGS_DENIED, LiveOp.SET_SERVERS)
    assert entry.proof is Proof.UNPROVEN
    assert entry.offer is False


def test_every_recorded_affordance_carries_evidence():
    assert AFFORDANCES
    assert all(len(a.note) > 20 for a in AFFORDANCES)


# --------------------------------------------------------------------------
# The production transport, against a short-lived Python child
# --------------------------------------------------------------------------

_ECHO = (
    "import sys\n"
    "for line in sys.stdin:\n"
    "    sys.stdout.write(line)\n"
    "    sys.stdout.flush()\n"
    "    break\n"
)


def test_the_real_transport_round_trips_over_real_pipes(tmp_path):
    """Binds the PRODUCTION default_spawn -- to `python -c`, never to the host."""
    transport = SubprocessTransport(
        [sys.executable, "-u", "-c", _ECHO], cwd=str(tmp_path)
    )
    client = LiveClient(transport, new_id=_ids("real-1"))
    with pytest.raises(ControlError):
        # The echo child replays the REQUEST, which is not a control_response, so the
        # correlator must reject it rather than accept its own frame as an answer.
        client.status()
    transport.close()


def test_the_real_transport_parses_a_scripted_response_from_a_real_child(tmp_path):
    script = (
        "import sys, json\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'type':'control_response','response':"
        "{'subtype':'success','request_id':'real-2',"
        "'response':{'mcpServers':[{'name':'probe','tools':[]}]}}}), flush=True)\n"
    )
    transport = SubprocessTransport(
        [sys.executable, "-u", "-c", script], cwd=str(tmp_path)
    )
    client = LiveClient(transport, new_id=_ids("real-2"))
    assert client.status() == ({"name": "probe", "tools": []},)
    transport.close()


def test_the_transport_spawns_in_the_cwd_it_was_given_not_the_callers(tmp_path):
    """mcp_toggle persists to projects[<the CONTROL SESSION's cwd>], so an inherited
    cwd would land the disable under the wrong project row."""
    target = tmp_path / "elsewhere"
    target.mkdir()
    script = "import os, sys; print(os.getcwd(), flush=True); sys.stdin.readline()"
    transport = SubprocessTransport(
        [sys.executable, "-u", "-c", script], cwd=str(target)
    )
    reported = next(transport.lines())
    assert reported.rstrip("\\/").lower().endswith("elsewhere")
    transport.close()


def test_a_transport_with_no_pipes_reports_it_rather_than_crashing():
    class Pipeless:
        stdin = None
        stdout = None

        def kill(self) -> None:
            """Nothing to kill."""

    transport = SubprocessTransport([], cwd=".", spawn=lambda argv, cwd: Pipeless())
    with pytest.raises(ControlError, match="no stdin pipe"):
        transport.send("x")
    with pytest.raises(ControlError, match="no stdout pipe"):
        next(transport.lines())
    transport.close()


def test_default_spawn_is_the_transports_default(tmp_path):
    seen: list[tuple[Sequence[str], str]] = []

    def record(argv: Sequence[str], cwd: str):
        seen.append((argv, cwd))
        return default_spawn([sys.executable, "-c", "pass"], cwd)

    transport = SubprocessTransport(["ignored"], cwd=str(tmp_path), spawn=record)
    assert seen == [(["ignored"], str(tmp_path))]
    transport.close()


@pytest.mark.live
def test_live_control_against_a_real_host_session():  # pragma: no cover
    """DEFAULT-DESELECTED. Spawns a REAL session; a cold fleet boot measured 104-275 s
    and `mcp_toggle` PERSISTS a write to the operator's own ~/.claude.json. Run
    deliberately: `pytest -m live`. This is the settling experiment for the installed
    build -- the transport re-verifies statically, the behaviour does not."""
    import os

    binary = os.environ.get("MCPAPPLY_CLAUDE_BINARY", "claude")
    transport = SubprocessTransport(
        session_argv(binary), cwd=os.getcwd(), spawn=default_spawn
    )
    client = LiveClient(transport, new_id=lambda: "live-1")
    client.kick()
    assert client.status()
    transport.close()


def test_the_live_test_is_actually_deselected_by_default(pytestconfig: pytest.Config):
    """Detector control for the deselection itself: prove the marker is registered AND
    that the collected `live` item is skipped, so its silence means something."""
    root = pytestconfig.rootpath
    manifest = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'markers = ["live:' in manifest

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--no-header",
            "--collect-only",
            "tests/test_live.py::test_live_control_against_a_real_host_session",
        ],
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 test collected" in result.stdout


# --------------------------------------------------------------------------
# The command surface -- what makes this module REACHABLE from production
# --------------------------------------------------------------------------


class _Recorder:
    """A client that records calls, standing in for a real control session."""

    def __init__(self) -> None:
        self.sent: list[str] = ["kick"]
        self.calls: list[tuple[str, object]] = []

    def reconnect(self, name: str) -> None:
        self.calls.append(("reconnect", name))
        self.sent.append("reconnect")

    def toggle(self, name: str, *, enabled: bool) -> None:
        self.calls.append(("toggle", enabled))
        self.sent.append("toggle")

    def status(self) -> tuple[dict[str, object], ...]:
        self.sent.append("status")
        return ({"name": "alpha"}, {"name": 7}, {"nope": "x"})


def test_the_request_id_generator_is_unique_per_call():
    """Responses arrive OUT OF ORDER, so the demultiplexer key must not repeat."""
    from mcpapply.live import _uuid_id

    ids = {_uuid_id() for _ in range(50)}
    assert len(ids) == 50


def test_the_default_client_spawns_kicks_and_is_ready_for_frames(tmp_path):
    """The kick is mandatory: a stream-json session emits no init until it gets one,
    so a caller that waits for init before writing deadlocks forever."""
    seen: list[tuple[Sequence[str], str]] = []

    def record(argv: Sequence[str], cwd: str):
        seen.append((argv, cwd))
        return default_spawn([sys.executable, "-c", "pass"], cwd)

    client = default_live_client(cwd=str(tmp_path), binary="claude", spawn=record)
    assert seen and seen[0][0][0] == "claude"
    assert seen[0][1] == str(tmp_path)
    assert len(client.sent) == 1
    assert json.loads(client.sent[0])["type"] == "user"


def test_only_the_three_control_verbs_map_to_a_frame():
    """add/remove/edit are document mutations; they have no control-channel form."""
    assert set(INTENT_OPS) == {"enable", "disable", "reconnect"}
    assert INTENT_OPS["enable"] is INTENT_OPS["disable"] is LiveOp.TOGGLE
    assert INTENT_OPS["reconnect"] is LiveOp.RECONNECT


def test_a_dry_run_builds_no_session_and_sends_no_frame():
    outcome = run_live(
        intent="disable",
        server="alpha",
        scope=ScopeId.CLAUDE_USER,
        apply=False,
        client_for=lambda: pytest.fail("a dry run built a control session"),
    )
    assert outcome.dry_run is True
    assert outcome.sent == ()
    assert "ZERO frames were sent" in render_live(outcome)


def test_an_offered_toggle_is_executed_then_RE_OBSERVED():
    """toggle/reconnect return no payload, so a follow-up status is the only proof."""
    client = _Recorder()
    outcome = run_live(
        intent="enable",
        server="alpha",
        scope=ScopeId.CLAUDE_USER,
        apply=True,
        client_for=lambda: client,
    )
    assert client.calls == [("toggle", True)]
    assert outcome.dry_run is False
    assert outcome.observed == ("alpha",), "a non-str name must be skipped, not crash"
    assert outcome.proof is Proof.PROVISIONAL
    text = render_live(outcome)
    assert "observed after the change: alpha" in text
    assert "PERSISTS" in text
    assert outcome.to_dict() == {
        "intent": "enable",
        "server": "alpha",
        "scope": ScopeId.CLAUDE_USER.value,
        "op": LiveOp.TOGGLE.value,
        "proof": Proof.PROVISIONAL.value,
        "dry_run": False,
        "frames_sent": 3,
        "observed": ["alpha"],
        "refusal": "",
    }


def test_a_refused_pair_renders_the_recorded_reason_and_sends_nothing():
    outcome = run_live(
        intent="disable",
        server="alpha",
        scope=ScopeId.MCP_JSON,
        apply=True,
        client_for=lambda: pytest.fail("a disproven affordance was attempted"),
    )
    assert outcome.proof is Proof.DISPROVEN
    assert outcome.sent == ()
    text = render_live(outcome)
    assert text.startswith("live mcp_toggle alpha")
    assert "REFUSED:" in text
    assert "CLEAN NEGATIVE" in text


def test_an_UPGRADED_affordance_is_honoured_rather_than_hardcoded_off(monkeypatch):
    """The evidence table is DATA. Reconnect is refused for every scope on today's
    record, so the executor branch is only reachable once a pair is upgraded -- which
    is precisely the behaviour that must not rot. Patch the record, not the logic."""
    monkeypatch.setattr(
        "mcpapply.live.AFFORDANCES",
        (
            Affordance(
                ScopeId.CLAUDE_USER, LiveOp.RECONNECT, Proof.PROVEN, "upgraded by n=5"
            ),
        ),
    )
    client = _Recorder()
    outcome = run_live(
        intent="reconnect",
        server="alpha",
        scope=ScopeId.CLAUDE_USER,
        apply=True,
        client_for=lambda: client,
    )
    assert client.calls == [("reconnect", "alpha")]
    assert outcome.proof is Proof.PROVEN
    assert outcome.refusal == ""


def test_an_empty_status_reports_so_rather_than_an_empty_line():
    class Silent(_Recorder):
        def status(self) -> tuple[dict[str, object], ...]:
            return ()

    outcome = run_live(
        intent="disable",
        server="alpha",
        scope=ScopeId.CLAUDE_USER,
        apply=True,
        client_for=Silent,
    )
    assert "(no servers reported)" in render_live(outcome)
