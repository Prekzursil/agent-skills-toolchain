"""Tests for the Desktop Commander interactive-stdin MCP server.

Coverage strategy mirrors tools/search-expansion: the whole module is gated at
100% line+branch. The subprocess/thread I/O is exercised against REAL short-lived
child processes (a `python -q` REPL, `python -c` one-shots) so the gate measures
behaviour, not mocks. The two genuinely timing-dependent branches (output arriving
mid-read; a child that ignores SIGTERM) are driven with an injected clock and a
`# pragma: no cover` respectively.
"""

from __future__ import annotations

import io
import json
import sys
import time

import pytest

import stdin_server as ss

# A portable, unbuffered, quiet Python REPL. `-q` drops the banner, `-i` forces
# interactive mode even though stdin is a pipe (isatty() is False), `-u`
# unbuffers stdout so prompts/results arrive without an explicit flush.
REPL = [sys.executable, "-I", "-q", "-u", "-i"]


def _drain_reader(mp: ss.ManagedProcess, timeout: float = 5.0) -> None:
    """Block until the child exits and its reader thread hits EOF."""
    mp._proc.wait(timeout=timeout)
    mp._reader.join(timeout=timeout)


# --------------------------------------------------------------------------- #
# ManagedProcess — real child processes
# --------------------------------------------------------------------------- #


def test_managed_process_drive_repl_roundtrip():
    mp = ss.ManagedProcess(REPL)
    try:
        assert isinstance(mp.pid, int)
        assert mp.poll() is None  # alive
        assert mp.send("print(2 + 2)\n") is True
        deadline = time.monotonic() + 5.0
        seen = ""
        while "4" not in seen and time.monotonic() < deadline:
            out, _more = mp.read(4096, 200)
            seen += out
        assert "4" in seen
    finally:
        mp.terminate()
    assert mp.poll() is not None  # dead after terminate


def test_send_returns_false_after_stdin_closed():
    mp = ss.ManagedProcess(REPL)
    try:
        mp._proc.stdin.close()  # simulate a child that closed its stdin
        assert mp.send("noop\n") is False
    finally:
        mp.terminate()


def test_read_times_out_with_no_output():
    # A child that produces nothing for a while: read must return ("", False)
    # after ~timeout_ms without hanging.
    mp = ss.ManagedProcess([sys.executable, "-I", "-c", "import time; time.sleep(3)"])
    try:
        t0 = time.monotonic()
        out, more = mp.read(4096, 50)
        elapsed = time.monotonic() - t0
        assert out == ""
        assert more is False
        assert 0.03 <= elapsed < 2.0
    finally:
        mp.terminate()


def test_read_returns_when_output_appears_midwait(monkeypatch):
    # Deterministically exercise the "no output -> sleep -> output present" branch
    # with an injected clock and a snapshot that is empty on the first poll and
    # non-empty on the second. No real timing race.
    mp = ss.ManagedProcess([sys.executable, "-I", "-c", "pass"])
    _drain_reader(mp)
    calls = {"n": 0}

    def fake_snapshot(_max_chars):
        calls["n"] += 1
        return ("", False) if calls["n"] == 1 else ("late", False)

    ticks = iter([0.0, 0.0, 0.001])  # start, first check, second check (< deadline)

    monkeypatch.setattr(mp, "_snapshot", fake_snapshot)
    out, more = mp.read(4096, 1000, _clock=lambda: next(ticks), _sleep=lambda _s: None)
    assert out == "late"
    assert more is False
    assert calls["n"] == 2


def test_ring_buffer_drops_oldest_and_flags_truncation():
    # 2000 chars of output into a 100-char ring: only the tail survives and the
    # drop flag is set.
    mp = ss.ManagedProcess(
        [sys.executable, "-I", "-c", "import sys; sys.stdout.write('X' * 2000)"],
        buffer_cap=100,
    )
    try:
        _drain_reader(mp)
        assert mp.take_dropped() is True
        out, more = mp.read(4096, 50)
        assert out == "X" * 100
        assert more is False
        # flag resets after being taken
        assert mp.take_dropped() is False
    finally:
        mp.terminate()


def test_snapshot_reports_more_when_over_max_chars():
    mp = ss.ManagedProcess(
        [sys.executable, "-I", "-c", "import sys; sys.stdout.write('abcdefghij')"],
    )
    try:
        _drain_reader(mp)
        out, more = mp.read(4, 50)
        assert out == "abcd"
        assert more is True
        rest, more2 = mp.read(4096, 50)
        assert rest == "efghij"
        assert more2 is False
    finally:
        mp.terminate()


def test_terminate_is_idempotent_on_dead_process():
    mp = ss.ManagedProcess([sys.executable, "-I", "-c", "pass"])
    _drain_reader(mp)
    assert mp.poll() is not None
    mp.terminate()  # already dead: must be a no-op, not raise
    mp.terminate()


# --------------------------------------------------------------------------- #
# Server — registry + 3 verbs
# --------------------------------------------------------------------------- #


def test_start_process_registers_and_returns_ids():
    srv = ss.Server()
    try:
        res = srv.start_process(REPL)
        assert res["session_id"] == "proc-1"
        assert isinstance(res["pid"], int)
        assert srv.start_process(REPL)["session_id"] == "proc-2"
    finally:
        srv.cleanup()


def test_start_process_rejects_empty_command():
    srv = ss.Server()
    with pytest.raises(ValueError):
        srv.start_process([])


def test_start_process_enforces_session_cap():
    srv = ss.Server(max_sessions=1, proc_factory=_FakeProc)
    try:
        srv.start_process(["x"])
        with pytest.raises(RuntimeError):
            srv.start_process(["y"])
    finally:
        srv.cleanup()


def test_interact_with_process_roundtrip():
    srv = ss.Server()
    try:
        sid = srv.start_process(REPL)["session_id"]
        res = srv.interact_with_process(sid, "print(6 * 7)\n", wait_ms=600)
        assert "42" in res["output"]
        assert res["alive"] is True
        assert res["exit_code"] is None
    finally:
        srv.cleanup()


def test_interact_reports_exit_after_repl_quits():
    srv = ss.Server()
    try:
        sid = srv.start_process(REPL)["session_id"]
        res = srv.interact_with_process(sid, "exit()\n", wait_ms=800)
        assert res["alive"] is False
        assert res["exit_code"] == 0
    finally:
        srv.cleanup()


def test_interact_unknown_session_raises():
    srv = ss.Server()
    with pytest.raises(KeyError):
        srv.interact_with_process("nope", "x\n")


def test_read_process_output_reports_more_and_alive():
    srv = ss.Server()
    try:
        sid = srv.start_process(
            [
                sys.executable,
                "-I",
                "-u",
                "-c",
                "import sys,time; sys.stdout.write('0123456789'); sys.stdout.flush(); time.sleep(2)",
            ]
        )["session_id"]
        # let the reader thread drain the flushed bytes into the ring
        time.sleep(0.3)
        res = srv.read_process_output(sid, max_chars=4, timeout_ms=500)
        assert res["output"] == "0123"
        assert res["more"] is True
        assert res["truncated"] is False
        assert res["alive"] is True
    finally:
        srv.cleanup()


def test_read_process_output_flags_truncated_on_overflow():
    srv = ss.Server(
        proc_factory=lambda cmd, cwd: ss.ManagedProcess(cmd, cwd, buffer_cap=50)
    )
    try:
        sid = srv.start_process(
            [sys.executable, "-I", "-c", "import sys; sys.stdout.write('Y' * 500)"]
        )["session_id"]
        srv._get(sid)._reader.join(timeout=5)
        res = srv.read_process_output(sid, max_chars=4096, timeout_ms=100)
        assert res["truncated"] is True
        assert res["output"] == "Y" * 50
    finally:
        srv.cleanup()


def test_read_process_output_unknown_session_raises():
    srv = ss.Server()
    with pytest.raises(KeyError):
        srv.read_process_output("ghost")


def test_cleanup_terminates_all_children():
    srv = ss.Server()
    sid = srv.start_process(REPL)["session_id"]
    proc = srv._get(sid)
    srv.cleanup()
    assert proc.poll() is not None
    assert srv._sessions == {}


# --------------------------------------------------------------------------- #
# JSON-RPC dispatch
# --------------------------------------------------------------------------- #


class _FakeProc:
    """A cheap stand-in for ManagedProcess where a real child is unnecessary."""

    _next = 0

    def __init__(self, command, cwd=None, *, buffer_cap=ss.BUFFER_CAP):
        type(self)._next += 1
        self.pid = 1000 + type(self)._next
        self.command = command
        self.cwd = cwd
        self.terminated = False

    def send(self, data):
        return True

    def read(self, max_chars, timeout_ms):
        return ("", False)

    def _snapshot(self, max_chars):
        return ("", False)

    def take_dropped(self):
        return False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True


def _server_with_fakes():
    return ss.Server(proc_factory=_FakeProc)


def test_handle_initialize():
    srv = _server_with_fakes()
    resp = ss.handle_request(srv, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == ss.PROTOCOL_VERSION
    assert resp["result"]["serverInfo"]["name"] == ss.SERVER_NAME


def test_handle_initialized_notification_has_no_response():
    srv = _server_with_fakes()
    assert (
        ss.handle_request(
            srv, {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        is None
    )


def test_handle_tools_list_exposes_only_three_verbs():
    srv = _server_with_fakes()
    resp = ss.handle_request(srv, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"start_process", "interact_with_process", "read_process_output"}


def test_handle_tools_call_start_process():
    srv = _server_with_fakes()
    resp = ss.handle_request(
        srv,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "start_process",
                "arguments": {"command": ["echo", "hi"]},
            },
        },
    )
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["session_id"] == "proc-1"
    assert "isError" not in resp["result"]


def test_handle_tools_call_interact_and_read():
    srv = _server_with_fakes()
    ss.handle_request(
        srv,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "start_process", "arguments": {"command": ["x"]}},
        },
    )
    r_int = ss.handle_request(
        srv,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "interact_with_process",
                "arguments": {"session_id": "proc-1", "input": "hi\n", "wait_ms": 0},
            },
        },
    )
    assert json.loads(r_int["result"]["content"][0]["text"])["alive"] is True
    r_read = ss.handle_request(
        srv,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "read_process_output",
                "arguments": {"session_id": "proc-1", "timeout_ms": 0},
            },
        },
    )
    assert json.loads(r_read["result"]["content"][0]["text"])["more"] is False


def test_handle_tools_call_unknown_tool_is_error():
    srv = _server_with_fakes()
    resp = ss.handle_request(
        srv,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "does_not_exist", "arguments": {}},
        },
    )
    assert resp["result"]["isError"] is True
    assert "unknown tool" in json.loads(resp["result"]["content"][0]["text"])["error"]


def test_handle_tools_call_tool_error_is_reported():
    srv = _server_with_fakes()
    resp = ss.handle_request(
        srv,
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "start_process", "arguments": {"command": []}},
        },
    )
    assert resp["result"]["isError"] is True


def test_handle_unknown_method_is_jsonrpc_error():
    srv = _server_with_fakes()
    resp = ss.handle_request(srv, {"jsonrpc": "2.0", "id": 8, "method": "no/such"})
    assert resp["error"]["code"] == -32601


# --------------------------------------------------------------------------- #
# serve() / main() — the stdio loop
# --------------------------------------------------------------------------- #


def test_serve_processes_lines_skips_blanks_and_notifications():
    srv = _server_with_fakes()
    lines = (
        "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
                "",  # blank -> skipped
                json.dumps(
                    {"jsonrpc": "2.0", "method": "notifications/initialized"}
                ),  # no response
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            ]
        )
        + "\n"
    )
    reader = io.StringIO(lines)
    writer = io.StringIO()
    ss.serve(srv, reader, writer)
    responses = [json.loads(x) for x in writer.getvalue().splitlines() if x]
    ids = [r.get("id") for r in responses]
    assert ids == [1, 2]  # notification produced no line


def test_serve_reports_parse_error_on_bad_json():
    srv = _server_with_fakes()
    reader = io.StringIO("this is not json\n")
    writer = io.StringIO()
    ss.serve(srv, reader, writer)
    resp = json.loads(writer.getvalue())
    assert resp["error"]["code"] == -32700
    assert resp["id"] is None


def test_main_runs_serve_over_std_streams(monkeypatch):
    line = json.dumps({"jsonrpc": "2.0", "id": 99, "method": "tools/list"}) + "\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(line))
    fake_out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_out)
    monkeypatch.setattr(ss, "_SERVER", _server_with_fakes())
    rc = ss.main()
    assert rc == 0
    assert json.loads(fake_out.getvalue())["id"] == 99
