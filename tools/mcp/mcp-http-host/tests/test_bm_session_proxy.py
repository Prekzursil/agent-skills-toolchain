"""The session-healing reverse proxy, proven against the fake Basic Memory daemon.

Every window measured on the box in ``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``
is driven through the proxy with a plain ``http.client`` client that behaves like
Cursor's TypeScript SDK transport (keeps one ``Mcp-Session-Id`` forever, never
re-initializes on its own):

* a watchdog restart (port healthy, every upstream session id stale) is healed
  with the client's own ``initialize`` params and the failed request is replayed
  exactly once, under a client session id that never changes;
* the dead-port window answers a clean ``503`` + ``Retry-After`` that keeps the
  client session valid, never a connection refused;
* JSON and SSE bodies stream through event by event, GET streams survive an
  upstream restart, DELETE ends both legs;
* ``/healthz`` reports the upstream state, restarts land in a JSONL file, and
  memory stays flat across restart / refused / recover cycles (tracemalloc).
"""

from __future__ import annotations

import gc
import http.client
import json
import os
import sys
import threading
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import bm_session_proxy as bsp  # noqa: E402
from _fake_streamable_http_daemon import (  # noqa: E402
    FakeStreamableHttpDaemon,
    session_not_found_body,
)

SESSION = "Mcp-Session-Id"
ACCEPT_BOTH = "application/json, text/event-stream"
INIT_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {"roots": {"listChanged": True}},
    "clientInfo": {"name": "cursor", "version": "1.2.3"},
}
WHOAMI = {"name": "whoami", "arguments": {}}


def rpc(rid: Any, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        message["params"] = params
    return message


def whoami_pid(body: bytes) -> int:
    payload = json.loads(body)
    return json.loads(payload["result"]["content"][0]["text"])["pid"]


def posts(daemon: FakeStreamableHttpDaemon, generation: int | None = None) -> list[str]:
    return [
        r["method"]
        for r in daemon.requests
        if r["verb"] == "POST" and (generation is None or r["generation"] == generation)
    ]


def wait_until(predicate, timeout: float = 5.0, what: str = "condition") -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.02)


class Reply:
    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body

    def json(self) -> Any:
        return json.loads(self.body)


class Client:
    """A Cursor-shaped Streamable-HTTP client: one session id, no self-healing."""

    def __init__(self, base: str, timeout: float = 10.0) -> None:
        host_port = base.split("//", 1)[1]
        self.host, port = host_port.rsplit(":", 1)
        self.port = int(port)
        self.timeout = timeout

    def _open(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Reply:
        conn = self._open()
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return Reply(resp.status, dict(resp.getheaders()), resp.read())
        finally:
            conn.close()

    def post(
        self,
        message: dict[str, Any],
        session_id: str | None = None,
        headers: dict[str, str] | None = None,
        path: str = "/mcp",
    ) -> Reply:
        return self.request(
            "POST",
            path,
            json.dumps(message).encode("utf-8"),
            self._headers(session_id, headers),
        )

    def post_stream(
        self, message: dict[str, Any], session_id: str | None
    ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        conn = self._open()
        conn.request(
            "POST",
            "/mcp",
            json.dumps(message).encode("utf-8"),
            self._headers(session_id),
        )
        return conn, conn.getresponse()

    def get_stream(
        self, session_id: str | None, accept: str = "text/event-stream"
    ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        conn = self._open()
        headers = {"Accept": accept}
        if session_id:
            headers[SESSION] = session_id
        conn.request("GET", "/mcp", headers=headers)
        return conn, conn.getresponse()

    def delete(self, session_id: str) -> Reply:
        return self.request("DELETE", "/mcp", headers={SESSION: session_id})

    def initialize(
        self, params: dict[str, Any] | None = None, rid: Any = 1
    ) -> tuple[str, Reply]:
        reply = self.post(
            rpc(rid, "initialize", INIT_PARAMS if params is None else params)
        )
        assert reply.status == 200, reply.body
        return reply.headers[SESSION], reply

    @staticmethod
    def _headers(
        session_id: str | None, extra: dict[str, str] | None = None
    ) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": ACCEPT_BOTH}
        if session_id:
            headers[SESSION] = session_id
        headers.update(extra or {})
        return headers


def read_event(resp: http.client.HTTPResponse, timeout: float = 5.0) -> dict[str, Any]:
    """Next SSE event carrying a JSON message; comments / keepalives are skipped."""
    deadline = time.monotonic() + timeout
    data: list[bytes] = []
    while time.monotonic() < deadline:
        line = resp.readline()
        if not line:
            raise AssertionError("stream ended before an event arrived")
        line = line.rstrip(b"\r\n")
        if not line:
            if data:
                return json.loads(b"\n".join(data))
            continue
        if line.startswith(b"data:"):
            data.append(line[5:].lstrip())
    raise AssertionError("no SSE event within the timeout")


class RunningProxy:
    def __init__(self, server: Any) -> None:
        self.server = server
        self.core = server.proxy
        self.port = server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.client = Client(self.base)


@contextmanager
def running_proxy(upstream_url: str, **kwargs: Any) -> Iterator[RunningProxy]:
    kwargs.setdefault("retry_after", 7)
    kwargs.setdefault("reconnect_delay", 0.05)
    server = bsp.build_server(upstream_url, port=0, **kwargs)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}
    )
    thread.daemon = True
    thread.start()
    try:
        yield RunningProxy(server)
    finally:
        server.proxy.stop()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def daemon() -> Iterator[FakeStreamableHttpDaemon]:
    with FakeStreamableHttpDaemon() as fake:
        yield fake


@pytest.fixture
def proxy(daemon: FakeStreamableHttpDaemon, tmp_path: Path) -> Iterator[RunningProxy]:
    with running_proxy(daemon.url, restart_log=tmp_path / "restarts.jsonl") as running:
        yield running


# --- sessions and forwarding ---------------------------------------------------


def test_initialize_issues_a_proxy_session_id_distinct_from_upstream(daemon, proxy):
    csid, reply = proxy.client.initialize()
    assert reply.json()["result"]["serverInfo"]["name"] == "fake-mcp"
    assert reply.headers["Content-Type"] == "application/json"
    [usid] = daemon.live_sessions()
    assert csid and csid != usid  # the client never learns the upstream id
    assert proxy.core.sessions.get(csid).upstream_id == usid
    assert proxy.core.sessions.get(csid).init_params == INIT_PARAMS
    assert daemon.requests[0]["session_id"] is None  # initialize opens a fresh session


def test_requests_are_forwarded_under_the_upstream_id_and_answered_under_the_clients(
    daemon, proxy
):
    csid, _ = proxy.client.initialize()
    [usid] = daemon.live_sessions()
    reply = proxy.client.post(
        rpc(2, "ping"), csid, headers={"MCP-Protocol-Version": "2025-06-18"}
    )
    assert reply.status == 200
    assert reply.json() == {"jsonrpc": "2.0", "id": 2, "result": {}}
    assert reply.headers[SESSION] == csid
    ping = daemon.requests[-1]
    assert ping["session_id"] == usid
    assert ping["protocol_version_header"] == "2025-06-18"
    assert whoami_pid(proxy.client.post(rpc(3, "tools/call", WHOAMI), csid).body) == (
        os.getpid()
    )


def test_notifications_and_client_responses_pass_through_as_202(daemon, proxy):
    csid, _ = proxy.client.initialize()
    reply = proxy.client.post(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}, csid
    )
    assert (reply.status, reply.body) == (202, b"")
    assert reply.headers[SESSION] == csid
    reply = proxy.client.post(
        {"jsonrpc": "2.0", "id": "srv-1", "result": {"roots": []}}, csid
    )
    assert reply.status == 202
    assert daemon.client_responses == [
        {"jsonrpc": "2.0", "id": "srv-1", "result": {"roots": []}}
    ]


def test_upstream_protocol_errors_pass_through_unchanged(daemon, proxy):
    csid, _ = proxy.client.initialize()
    only_json = proxy.client.post(
        rpc(2, "ping"), csid, headers={"Accept": "application/json"}
    )
    assert only_json.status == 406
    assert only_json.json()["error"]["code"] == -32600
    wrong_type = proxy.client.request(
        "POST",
        "/mcp",
        b"ping",
        {"Content-Type": "text/plain", "Accept": ACCEPT_BOTH, SESSION: csid},
    )
    assert wrong_type.status == 415
    no_session = proxy.client.post(rpc(3, "ping"))
    assert no_session.status == 400
    assert "Missing session ID" in no_session.json()["error"]["message"]
    # the on-box health probe: a bare GET answers 406 while everything is healthy
    bare = proxy.client.request("GET", "/mcp")
    assert bare.status == 406
    assert proxy.client.request("GET", "/nope").status == 404
    assert proxy.client.request("POST", "/nope", b"{}").status == 404


# --- healing -------------------------------------------------------------------


def test_watchdog_restart_is_healed_with_the_clients_params_and_replayed_once(
    daemon, proxy
):
    csid, _ = proxy.client.initialize()
    proxy.client.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, csid)
    assert (
        whoami_pid(proxy.client.post(rpc(2, "tools/call", WHOAMI), csid).body)
        == os.getpid()
    )
    [usid1] = daemon.live_sessions()

    daemon.restart()  # port healthy, every upstream session id now stale

    healed = proxy.client.post(
        rpc(3, "tools/call", WHOAMI),
        csid,
        headers={"MCP-Protocol-Version": "2025-06-18"},
    )
    assert healed.status == 200
    assert whoami_pid(healed.body) == os.getpid()
    assert healed.headers[SESSION] == csid  # the client's id never changes
    assert posts(daemon) == [
        "initialize",
        "notifications/initialized",
        "tools/call",
        "tools/call",  # 404 Session not found ...
        "initialize",  # ... re-initialize with the CLIENT's params ...
        "notifications/initialized",
        "tools/call",  # ... and replay exactly once
    ]
    heal_init = [r for r in daemon.requests if r.get("method") == "initialize"][1]
    assert heal_init["params"] == INIT_PARAMS
    replay = daemon.requests[-1]
    assert replay["protocol_version_header"] == "2025-06-18"
    [usid2] = daemon.live_sessions()
    assert usid2 != usid1
    assert replay["session_id"] == usid2
    assert proxy.core.sessions.get(csid).upstream_id == usid2
    assert proxy.core.sessions.count() == 1


def test_in_band_session_not_found_on_a_200_is_healed_too(tmp_path):
    with FakeStreamableHttpDaemon(session_not_found_status=200) as daemon:
        with running_proxy(daemon.url) as proxy:
            csid, _ = proxy.client.initialize()
            daemon.restart()
            healed = proxy.client.post(rpc(2, "tools/call", WHOAMI), csid)
            assert healed.status == 200
            assert whoami_pid(healed.body) == os.getpid()
            assert posts(daemon, generation=2) == [
                "tools/call",
                "initialize",
                "notifications/initialized",
                "tools/call",
            ]


def test_a_second_loss_inside_one_request_is_a_503_not_a_loop(daemon, proxy):
    csid, _ = proxy.client.initialize()
    daemon.force_session_not_found = 3  # the daemon keeps flapping under the heal
    reply = proxy.client.post(rpc(2, "tools/call", WHOAMI), csid)
    assert reply.status == 503
    assert reply.headers["Retry-After"] == "7"
    assert reply.headers[SESSION] == csid
    assert reply.json()["id"] == 2
    assert "twice" in reply.json()["error"]["message"]
    assert posts(daemon) == [
        "initialize",
        "tools/call",  # lost
        "initialize",
        "notifications/initialized",
        "tools/call",  # lost again: stop, do not loop
    ]
    assert daemon.force_session_not_found == 1
    # the client session is still valid: once the daemon settles, the same id works
    assert proxy.client.post(rpc(3, "ping"), csid).status == 200


def test_concurrent_requests_after_a_restart_heal_the_upstream_session_once(
    daemon, proxy
):
    csid, _ = proxy.client.initialize()
    daemon.restart()
    results: dict[int, Reply] = {}

    def worker(rid: int) -> None:
        results[rid] = Client(proxy.base).post(rpc(rid, "tools/call", WHOAMI), csid)

    threads = [threading.Thread(target=worker, args=(100 + i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert len(results) == 6
    assert all(
        r.status == 200 and whoami_pid(r.body) == os.getpid() for r in results.values()
    )
    assert posts(daemon, generation=2).count("initialize") == 1
    assert len(daemon.live_sessions()) == 1


def test_initialized_notification_after_a_heal_is_not_replayed(daemon, proxy):
    csid, _ = proxy.client.initialize()
    daemon.restart()  # between the client's initialize and its initialized notification
    reply = proxy.client.post(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}, csid
    )
    assert reply.status == 202
    assert posts(daemon, generation=2) == [
        "notifications/initialized",  # stale: 404
        "initialize",  # heal ...
        "notifications/initialized",  # ... which already announces initialized once
    ]


# --- the dead-port window ------------------------------------------------------


def test_dead_port_window_answers_503_with_retry_after_and_keeps_the_client_session(
    daemon, proxy
):
    csid, _ = proxy.client.initialize()
    assert (
        whoami_pid(proxy.client.post(rpc(2, "tools/call", WHOAMI), csid).body)
        == os.getpid()
    )

    daemon.stop()  # the daemon died: the upstream port refuses connections
    reply = proxy.client.post(rpc(5, "tools/call", WHOAMI), csid)
    assert reply.status == 503
    assert reply.headers["Retry-After"] == "7"
    assert reply.headers["Content-Type"] == "application/json"
    assert reply.headers[SESSION] == csid  # the client session stays valid
    body = reply.json()
    assert body["id"] == 5
    assert body["error"]["code"] == -32000
    assert "unavailable" in body["error"]["message"].lower()
    assert daemon.url in body["error"]["message"]
    health = proxy.client.request("GET", "/healthz")
    assert health.status == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["upstream"]["state"] == "down"
    assert "refused" in health.json()["upstream"]["last_error"].lower()

    daemon.start()  # watchdog relaunch: a new process, no sessions
    healed = proxy.client.post(rpc(6, "tools/call", WHOAMI), csid)
    assert healed.status == 200
    assert whoami_pid(healed.body) == os.getpid()
    assert posts(daemon, generation=2) == [
        "initialize",
        "notifications/initialized",
        "tools/call",
    ]
    health = proxy.client.request("GET", "/healthz").json()
    assert health["status"] == "ok" and health["upstream"]["state"] == "up"
    assert health["requests"]["unavailable_503"] == 1


def test_hung_upstream_is_a_503_after_the_timeout(daemon):
    daemon.response_delay = 0.8
    with running_proxy(
        daemon.url, upstream_timeout=0.2, handshake_timeout=0.2
    ) as proxy:
        started = time.monotonic()
        reply = proxy.client.post(rpc(1, "initialize", INIT_PARAMS))
        elapsed = time.monotonic() - started
    assert reply.status == 503
    assert elapsed < 0.7, elapsed
    assert "timed out" in reply.json()["error"]["message"].lower()
    assert SESSION not in reply.headers


def test_initialize_during_the_dead_window_is_a_503_without_a_session(daemon, proxy):
    daemon.stop()
    reply = proxy.client.post(rpc(1, "initialize", INIT_PARAMS))
    assert reply.status == 503
    assert reply.headers["Retry-After"] == "7"
    assert SESSION not in reply.headers
    assert reply.json()["id"] == 1
    assert proxy.core.sessions.count() == 0


# --- streaming -----------------------------------------------------------------


def test_sse_responses_are_relayed_event_by_event_not_buffered():
    prelude = [
        {"jsonrpc": "2.0", "method": "notifications/message", "params": {"n": n}}
        for n in range(3)
    ]
    with FakeStreamableHttpDaemon(
        response_mode="sse", sse_prelude=prelude, sse_prelude_delay=0.25
    ) as daemon:
        with running_proxy(daemon.url) as proxy:
            csid, init = proxy.client.initialize()
            assert init.headers["Content-Type"] == "text/event-stream"
            conn, resp = proxy.client.post_stream(rpc(2, "tools/list"), csid)
            started = time.monotonic()
            try:
                assert resp.status == 200
                assert resp.getheader("Content-Type") == "text/event-stream"
                assert resp.getheader("Transfer-Encoding") == "chunked"
                assert resp.getheader(SESSION) == csid
                first = read_event(resp)
                first_arrival = time.monotonic() - started
                rest = [read_event(resp) for _ in range(3)]
                total = time.monotonic() - started
                assert resp.read() == b""  # a clean end of the chunked body
            finally:
                conn.close()
    assert first["params"] == {"n": 0}
    assert first_arrival < 0.2, first_arrival  # relayed before the later events existed
    assert total >= 0.7, total
    assert [e.get("params", {}).get("n") for e in rest[:2]] == [1, 2]
    assert [t["name"] for t in rest[2]["result"]["tools"]] == ["whoami"]


def test_large_json_responses_keep_their_content_length(daemon, proxy):
    daemon.extra_tools = [
        {
            "name": f"tool_{i}",
            "description": "x" * 2000,
            "inputSchema": {"type": "object"},
        }
        for i in range(20)
    ]
    csid, _ = proxy.client.initialize()
    reply = proxy.client.post(rpc(2, "tools/list"), csid)
    assert reply.status == 200
    assert "Transfer-Encoding" not in reply.headers
    assert int(reply.headers["Content-Length"]) == len(reply.body) > 40_000
    assert len(reply.json()["result"]["tools"]) == 21


# --- GET server->client streams -----------------------------------------------


def test_get_stream_relays_pushed_messages_and_survives_an_upstream_restart(
    daemon, proxy
):
    csid, _ = proxy.client.initialize()
    proxy.client.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, csid)
    [usid1] = daemon.live_sessions()
    conn, resp = proxy.client.get_stream(csid)
    try:
        assert resp.status == 200
        assert resp.getheader("Content-Type") == "text/event-stream"
        assert resp.getheader(SESSION) == csid
        wait_until(
            lambda: (
                daemon.push(usid1, {"jsonrpc": "2.0", "method": "notifications/ping"})
                == 1
            ),
            what="the proxy to open its upstream GET stream",
        )
        assert read_event(resp)["method"] == "notifications/ping"

        daemon.restart()  # the upstream stream ends; the client's must not
        wait_until(
            lambda: any(
                r["verb"] == "GET"
                and r["generation"] == 2
                and r["session_id"] in daemon.live_sessions()
                for r in daemon.requests
            ),
            what="the proxy to heal and re-open the upstream stream",
        )
        [usid2] = daemon.live_sessions()
        assert usid2 != usid1
        assert (
            daemon.push(
                usid2, {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}
            )
            == 1
        )
        assert read_event(resp)["method"] == "notifications/tools/list_changed"
        # the stream's heal also serves the client's next POST: no second initialize
        assert (
            whoami_pid(proxy.client.post(rpc(2, "tools/call", WHOAMI), csid).body)
            == os.getpid()
        )
        assert posts(daemon, generation=2).count("initialize") == 1
        heal_init = [r for r in daemon.requests if r.get("method") == "initialize"][-1]
        assert heal_init["params"] == INIT_PARAMS
    finally:
        conn.close()


def test_get_stream_opened_while_the_daemon_is_down_attaches_on_recovery(
    daemon, tmp_path
):
    with running_proxy(daemon.url, keepalive=0.2) as proxy:
        csid, _ = proxy.client.initialize()
        daemon.stop()
        conn, resp = proxy.client.get_stream(csid)
        try:
            assert (
                resp.status == 200
            )  # the client sees a live stream, not a refused socket
            assert resp.getheader("Content-Type") == "text/event-stream"
            first = resp.readline()
            assert first.startswith(b":")  # an SSE comment keeps the stream warm
            daemon.start()
            wait_until(
                lambda: any(
                    r["verb"] == "GET" and r["generation"] == 2 for r in daemon.requests
                ),
                what="the proxy to attach the upstream stream after recovery",
            )
            [usid] = daemon.live_sessions()
            assert (
                daemon.push(usid, {"jsonrpc": "2.0", "method": "notifications/ping"})
                == 1
            )
            assert read_event(resp)["method"] == "notifications/ping"
        finally:
            conn.close()
        assert posts(daemon, generation=2)[:2] == [
            "initialize",
            "notifications/initialized",
        ]


def test_get_stream_405_upstream_is_passed_through():
    with FakeStreamableHttpDaemon(allow_get_stream=False) as daemon:
        with running_proxy(daemon.url) as proxy:
            csid, _ = proxy.client.initialize()
            conn, resp = proxy.client.get_stream(csid)
            try:
                assert resp.status == 405
                resp.read()
            finally:
                conn.close()


# --- DELETE --------------------------------------------------------------------


def test_delete_terminates_both_legs_and_tolerates_405(daemon, proxy):
    csid, _ = proxy.client.initialize()
    [usid] = daemon.live_sessions()
    reply = proxy.client.delete(csid)
    assert reply.status == 200
    assert (
        daemon.requests[-1]["verb"] == "DELETE"
        and daemon.requests[-1]["session_id"] == usid
    )
    assert daemon.live_sessions() == []
    assert proxy.core.sessions.get(csid) is None

    with FakeStreamableHttpDaemon(delete_status=405) as stubborn:
        with running_proxy(stubborn.url) as other:
            csid, _ = other.client.initialize()
            assert other.client.delete(csid).status == 405
            assert (
                other.core.sessions.get(csid) is None
            )  # the client is done either way


# --- unknown client sessions (the proxy itself restarted) ----------------------


def test_unknown_client_session_is_adopted_after_a_proxy_restart(daemon, proxy):
    stale = "client-id-issued-by-a-previous-proxy-process"
    reply = proxy.client.post(
        rpc(9, "tools/call", WHOAMI),
        stale,
        headers={"MCP-Protocol-Version": "2025-06-18"},
    )
    assert reply.status == 200
    assert whoami_pid(reply.body) == os.getpid()
    assert reply.headers[SESSION] == stale  # the client keeps the id it already holds
    assert posts(daemon) == ["initialize", "notifications/initialized", "tools/call"]
    adopted_init = daemon.requests[0]
    assert adopted_init["params"]["protocolVersion"] == "2025-06-18"
    assert adopted_init["params"]["clientInfo"]["name"] == bsp.PROXY_CLIENT_INFO["name"]
    assert proxy.core.sessions.get(stale).adopted is True
    health = proxy.client.request("GET", "/healthz").json()
    assert health["sessions"] == {
        "client": 1,
        "with_upstream": 1,
        "adopted": 1,
        "max": 128,
    }


def test_adoption_can_be_disabled_to_answer_the_sdk_404(daemon):
    with running_proxy(daemon.url, adopt_unknown_sessions=False) as proxy:
        reply = proxy.client.post(rpc(9, "ping"), "never-issued")
        assert reply.status == 404
        assert reply.body == session_not_found_body()
        assert reply.headers["Content-Type"] == "application/json"
        conn, resp = proxy.client.get_stream("never-issued")
        try:
            assert resp.status == 404
            resp.read()
        finally:
            conn.close()
        assert proxy.client.delete("never-issued").status == 404
        assert daemon.requests == []  # nothing reached the daemon


# --- health, logging, memory ---------------------------------------------------


def test_healthz_reports_upstream_state_and_probe_refreshes_it(daemon, proxy):
    health = proxy.client.request("GET", "/healthz")
    assert health.status == 200
    body = health.json()
    assert body["status"] == "starting"
    assert body["proxy"]["version"] == bsp.PROXY_VERSION
    assert body["proxy"]["pid"] == os.getpid()
    assert body["proxy"]["port"] == proxy.port
    assert body["upstream"]["url"] == daemon.url
    assert body["upstream"]["state"] == "unknown"

    probed = proxy.client.request("GET", "/healthz?probe=1").json()
    assert probed["status"] == "ok" and probed["upstream"]["state"] == "up"
    assert probed["upstream"]["last_ok_at"] is not None
    assert daemon.live_sessions() == []  # the probe never opens a session
    assert posts(daemon) == []  # a bare GET is answered 406 before anything is recorded

    daemon.stop()
    down = proxy.client.request("GET", "/healthz?probe=1")
    assert down.status == 200  # the PROXY is healthy; the upstream state is data
    assert down.json()["status"] == "degraded"
    assert down.json()["upstream"]["state"] == "down"
    assert down.json()["upstream"]["consecutive_failures"] == 1
    assert "refused" in down.json()["upstream"]["last_error"].lower()


def test_restarts_are_logged_as_jsonl(daemon, tmp_path):
    log_path = tmp_path / "logs" / "restarts.jsonl"  # the directory is created
    with running_proxy(daemon.url, restart_log=log_path) as proxy:
        csid, _ = proxy.client.initialize()
        [usid1] = daemon.live_sessions()
        daemon.restart()
        assert proxy.client.post(rpc(2, "ping"), csid).status == 200
        [usid2] = daemon.live_sessions()
        daemon.stop()
        assert proxy.client.post(rpc(3, "ping"), csid).status == 503
        daemon.start()
        assert proxy.client.post(rpc(4, "ping"), csid).status == 200
        upstream = proxy.client.request("GET", "/healthz").json()["upstream"]
        assert upstream["sessions_lost"] == 1
        assert upstream["reinitialized"] == 2
        assert upstream["downtime_windows"] == 1
    lines = log_path.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines]
    assert all(e["ts"].endswith("+00:00") and e["pid"] == os.getpid() for e in entries)
    assert [e["event"] for e in entries] == [
        "proxy_started",
        "session_lost",
        "session_reinitialized",
        "upstream_down",
        "upstream_recovered",
        "session_reinitialized",
    ]
    lost = entries[1]
    assert lost["client_session"] == csid and lost["upstream_session"] == usid1
    assert lost["detail"] == "Session not found"
    healed = entries[2]
    assert healed["upstream_session_old"] == usid1
    assert healed["upstream_session_new"] == usid2
    assert healed["server_generation"] == 2
    assert "refused" in entries[3]["detail"].lower()
    assert entries[5]["upstream_session_old"] is None  # the refused window dropped it


def test_memory_stays_flat_over_restart_refused_recover_cycles(daemon, tmp_path):
    with running_proxy(daemon.url, restart_log=tmp_path / "restarts.jsonl") as proxy:
        client = proxy.client
        csid, _ = client.initialize()

        def cycle(rid: int) -> None:
            assert client.post(rpc(rid, "tools/call", WHOAMI), csid).status == 200
            daemon.restart()
            assert client.post(rpc(rid + 1, "tools/call", WHOAMI), csid).status == 200
            daemon.stop()
            assert client.post(rpc(rid + 2, "tools/call", WHOAMI), csid).status == 503
            daemon.start()
            assert client.post(rpc(rid + 3, "tools/list"), csid).status == 200

        proxy_only = [tracemalloc.Filter(True, bsp.__file__, all_frames=True)]
        tracemalloc.start(25)
        try:
            for i in range(3):  # warm-up: caches, thread locals, the log file handle
                cycle(1000 + 10 * i)
            daemon.requests.clear()
            gc.collect()
            before = tracemalloc.take_snapshot().filter_traces(proxy_only)
            for i in range(12):
                cycle(2000 + 10 * i)
            daemon.requests.clear()
            gc.collect()
            after = tracemalloc.take_snapshot().filter_traces(proxy_only)
        finally:
            tracemalloc.stop()
        growth = sum(stat.size_diff for stat in after.compare_to(before, "filename"))
        print(f"tracemalloc: proxy-attributed growth over 12 cycles = {growth} bytes")
        assert proxy.core.sessions.count() == 1
        health = client.request("GET", "/healthz").json()
        assert health["upstream"]["sessions_lost"] >= 15
        assert health["upstream"]["downtime_windows"] == 15
    assert growth < 96 * 1024, f"proxy retained {growth} bytes over 12 cycles"


def test_session_table_is_capped_with_lru_eviction(daemon):
    with running_proxy(daemon.url, max_sessions=2) as proxy:
        first, _ = proxy.client.initialize(rid=1)
        second, _ = proxy.client.initialize(rid=2)
        assert (
            proxy.client.post(rpc(3, "ping"), first).status == 200
        )  # first is now the newest
        third, _ = proxy.client.initialize(rid=4)
        assert proxy.core.sessions.get(second) is None  # least recently used went
        assert proxy.core.sessions.get(first) is not None
        assert proxy.core.sessions.get(third) is not None
        assert proxy.core.sessions.count() == 2
        deletes = [r for r in daemon.requests if r["verb"] == "DELETE"]
        assert len(deletes) == 1  # the evicted upstream session was released
        assert len(daemon.live_sessions()) == 2


# --- hygiene and CLI -----------------------------------------------------------


def test_names_avoid_the_daemons_process_match_tokens():
    """The fleet supervisor budgets the daemon by these tokens; the kill-stale
    filters in the launcher / watchdog match ``*basic-memory*``. The proxy must
    never be mistaken for the daemon by any of them."""
    names = [
        Path(bsp.__file__).name,
        bsp.DEFAULT_RESTART_LOG_NAME,
        bsp.PROXY_CLIENT_INFO["name"],
        bsp.DEFAULT_UPSTREAM_URL,
    ]
    for name in names:
        for token in ("basic_memory", "basic-memory", "streamable-http"):
            assert token not in name.lower(), (name, token)


def test_main_serves_and_rejects_non_loopback_binds(daemon, monkeypatch, capsys):
    assert bsp.main(["--port", "0", "--upstream", daemon.url, "--host", "0.0.0.0"]) == 2
    assert "loopback" in capsys.readouterr().err
    served = {}
    monkeypatch.setattr(
        bsp.ThreadingHTTPServer,
        "serve_forever",
        lambda self, **kw: served.setdefault("ok", True),
    )
    rc = bsp.main(["--port", "0", "--upstream", daemon.url, "--restart-log", ""])
    assert rc == 0
    assert served["ok"] is True
    err = capsys.readouterr().err
    assert "bm-session-proxy" in err and daemon.url in err
