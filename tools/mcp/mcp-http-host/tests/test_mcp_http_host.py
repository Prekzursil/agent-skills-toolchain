"""TDD proof for mcp-http-host: one shared child serves many HTTP clients.

The load-bearing claims, each asserted mechanically:
  * an MCP ``initialize`` handshake completes over the HTTP endpoint;
  * TWO (and N concurrent) clients are served by the SAME child pid;
  * the child is spawned exactly ONCE regardless of request count;
  * a CONTROL proves the status quo we replace - spawning the stdio server N
    times yields N DISTINCT pids (== N processes, the multiplication bug).
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import mcp_http_host as mhh  # noqa: E402

FAKE = [sys.executable, str(ROOT / "_fake_mcp_server.py")]


def _post(url: str, obj: dict) -> tuple[int, dict, dict | None]:
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        return resp.status, dict(resp.headers), (json.loads(body) if body else None)


def _get(url: str) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.status, json.loads(resp.read())


def _init(base: str, rid: int = 1) -> tuple[int, dict, dict | None]:
    return _post(
        base + "/mcp",
        {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        },
    )


def _whoami(base: str, rid: int) -> int:
    status, _, resp = _post(
        base + "/mcp",
        {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {"name": "whoami"},
        },
    )
    assert status == 200
    return json.loads(resp["result"]["content"][0]["text"])["pid"]


@pytest.fixture
def host():
    httpd, child = mhh.build_server(FAKE, port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        yield base, child
    finally:
        httpd.shutdown()
        child.terminate()
        thread.join(timeout=5)


def test_initialize_handshake(host):
    base, _ = host
    status, headers, resp = _init(base)
    assert status == 200
    assert resp["result"]["serverInfo"]["name"] == "fake-mcp"
    assert "protocolVersion" in resp["result"]
    assert "Mcp-Session-Id" in headers  # issued on initialize per Streamable-HTTP


def test_two_clients_share_one_child(host):
    base, child = host
    pid_a = (_init(base, 10), _whoami(base, 11))[1]
    pid_b = (_init(base, 20), _whoami(base, 21))[1]
    assert pid_a == pid_b  # SAME child process serves both clients
    assert child.spawn_count == 1  # only ONE child ever spawned
    _, health = _get(base + "/healthz")
    assert health["child_pid"] == pid_a
    assert health["child_spawn_count"] == 1


def test_concurrent_clients_same_child(host):
    base, child = host
    results: dict[int, int] = {}

    def worker(rid: int) -> None:
        _init(base, rid)
        results[rid] = _whoami(base, rid + 1000)

    threads = [threading.Thread(target=worker, args=(200 + i,)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert len(results) == 5
    assert len(set(results.values())) == 1  # 5 concurrent clients -> ONE pid
    assert child.spawn_count == 1


def test_many_requests_never_respawn(host):
    base, child = host
    for i in range(6):
        status, _, _ = _init(base, 100 + i)
        assert status == 200
    assert child.spawn_count == 1
    _, health = _get(base + "/healthz")
    assert health["requests_served"] >= 6


def test_notification_returns_202(host):
    base, _ = host
    status, _, resp = _post(
        base + "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert status == 202
    assert resp is None


def test_tools_list_over_http(host):
    base, _ = host
    status, _, resp = _post(
        base + "/mcp", {"jsonrpc": "2.0", "id": 5, "method": "tools/list"}
    )
    assert status == 200
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "whoami" in names


def test_unknown_path_404(host):
    base, _ = host
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base + "/nope")
    assert exc.value.code == 404


def test_bad_json_400(host):
    base, _ = host
    req = urllib.request.Request(
        base + "/mcp",
        data=b"not json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 400


def test_wrong_post_path_404(host):
    base, _ = host
    req = urllib.request.Request(
        base + "/wrong",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 404


def test_eager_spawn_reports_pid_before_traffic():
    httpd, child = mhh.build_server(FAKE, port=0, eager=True)
    try:
        assert child.pid is not None
        assert child.spawn_count == 1
    finally:
        child.terminate()
        httpd.server_close()


def test_control_direct_stdio_spawns_are_distinct():
    """The status quo we replace: N direct stdio spawns == N DISTINCT pids."""
    pids: set[int] = set()
    procs: list[subprocess.Popen] = []
    try:
        for _ in range(3):
            proc = subprocess.Popen(
                FAKE,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
            procs.append(proc)
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "whoami"},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            line = proc.stdout.readline()
            pids.add(
                json.loads(json.loads(line)["result"]["content"][0]["text"])["pid"]
            )
        assert len(pids) == 3  # three separate processes == the multiplication
    finally:
        for proc in procs:
            proc.terminate()


def test_stdiochild_requires_cmd():
    with pytest.raises(ValueError):
        mhh.StdioChild([])


def test_main_requires_command():
    assert mhh.main(["--port", "0"]) == 2


def test_batch_returns_list(host):
    base, _ = host
    status, _, resp = _post(
        base + "/mcp",
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ],
    )
    assert status == 200
    assert isinstance(resp, list)
    assert {r["id"] for r in resp} == {1, 2}


def test_batch_all_notifications_202(host):
    base, _ = host
    status, _, resp = _post(
        base + "/mcp",
        [
            {"jsonrpc": "2.0", "method": "notifications/a"},
            {"jsonrpc": "2.0", "method": "notifications/b"},
        ],
    )
    assert status == 202
    assert resp is None


def test_child_request_notification_returns_none():
    child = mhh.StdioChild(FAKE)
    try:
        assert (
            child.request({"jsonrpc": "2.0", "method": "notifications/initialized"})
            is None
        )
    finally:
        child.terminate()


def test_child_pid_none_before_start_and_after_terminate():
    child = mhh.StdioChild(FAKE)
    assert child.pid is None  # not spawned yet
    child.start()
    assert child.pid is not None
    child.terminate()
    assert child.pid is None  # dead after terminate


def test_child_request_raises_on_eof():
    dies = [sys.executable, "-c", "import sys; sys.exit(0)"]
    child = mhh.StdioChild(dies)
    try:
        with pytest.raises((RuntimeError, BrokenPipeError, OSError)):
            child.request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    finally:
        child.terminate()


def test_child_request_times_out_on_silent_child():
    silent = [sys.executable, "-c", "import sys\nfor _ in sys.stdin:\n    pass"]
    child = mhh.StdioChild(silent)
    try:
        with pytest.raises(TimeoutError):
            child.request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, timeout=0.5)
    finally:
        child.terminate()


def test_noise_line_before_response_is_skipped():
    httpd, child = mhh.build_server(FAKE, port=0, env={"FAKE_NOISE": "1"})
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        status, _, resp = _init(f"http://127.0.0.1:{port}")
        assert status == 200
        assert resp["result"]["serverInfo"]["name"] == "fake-mcp"  # noise skipped
    finally:
        httpd.shutdown()
        child.terminate()
        thread.join(timeout=5)


def test_child_cmd_strips_double_dash():
    assert mhh._child_cmd(["--", "python", "x"]) == ["python", "x"]
    assert mhh._child_cmd(["python", "x"]) == ["python", "x"]
    assert mhh._child_cmd([]) == []


def test_main_runs_server_and_terminates(monkeypatch):
    served = {}
    monkeypatch.setattr(
        mhh.ThreadingHTTPServer,
        "serve_forever",
        lambda self: served.setdefault("ok", True),
    )
    monkeypatch.setattr(mhh.ThreadingHTTPServer, "shutdown", lambda self: None)
    rc = mhh.main(["--host", "127.0.0.1", "--port", "0", "--", *FAKE])
    assert rc == 0
    assert served.get("ok") is True


def test_http_500_on_child_error():
    dies = [sys.executable, "-c", "import sys; sys.exit(0)"]
    httpd, child = mhh.build_server(dies, port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(
                f"http://127.0.0.1:{port}/mcp",
                {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )
        assert exc.value.code == 500
        body = json.loads(exc.value.read())
        assert body["error"]["code"] == -32000
    finally:
        httpd.shutdown()
        child.terminate()
        thread.join(timeout=5)


def test_child_respawns_after_death():
    child = mhh.StdioChild(FAKE)
    child.start()
    pid1 = child.pid
    assert child.spawn_count == 1
    child.terminate()
    # a fresh request must transparently respawn the child (auto-recovery)
    resp = child.request({"jsonrpc": "2.0", "id": 9, "method": "ping"})
    assert resp["id"] == 9
    assert child.spawn_count == 2
    assert child.pid != pid1
    child.terminate()
