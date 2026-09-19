"""Pin the fake Streamable-HTTP daemon's contract before any transport trusts it.

Every failure window a Basic Memory transport must survive is reproduced here
with plain ``urllib`` so the fixture's behaviour is proven independently of the
bridge under test: session issuance, the SDK-exact 404 ``Session not found``
body on a stale id, restart (sessions gone, generation bumps), the
connection-refused window, JSON and SSE (chunked, with prelude notifications)
response modes, and the GET server->client SSE stream.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from _fake_streamable_http_daemon import (  # noqa: E402
    FakeStreamableHttpDaemon,
    session_not_found_body,
)

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _post(
    url: str, message: dict, session_id: str | None = None, timeout: float = 10
) -> tuple[int, dict, bytes]:
    headers = dict(HEADERS)
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        url, data=json.dumps(message).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read()


def _initialize(url: str, rid: int = 1) -> tuple[str, dict]:
    status, headers, body = _post(
        url,
        {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )
    assert status == 200
    return headers["Mcp-Session-Id"], json.loads(body)


def _http_error(
    url: str, message: dict, session_id: str | None
) -> urllib.error.HTTPError:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(url, message, session_id)
    return exc.value


@pytest.fixture
def daemon():
    with FakeStreamableHttpDaemon() as fake:
        yield fake


PING = {"jsonrpc": "2.0", "id": 7, "method": "ping"}


def test_initialize_issues_a_session_and_later_posts_need_it(daemon):
    sid, resp = _initialize(daemon.url)
    assert sid and sid in daemon.live_sessions()
    assert resp["result"]["serverInfo"]["name"] == "fake-mcp"
    assert resp["result"]["serverInfo"]["generation"] == 1
    assert resp["result"]["capabilities"]["tools"] == {"listChanged": True}

    status, headers, body = _post(daemon.url, PING, sid)
    assert status == 200
    assert headers["Content-Type"] == "application/json"
    assert headers["Mcp-Session-Id"] == sid
    assert json.loads(body) == {"jsonrpc": "2.0", "id": 7, "result": {}}

    missing = _http_error(daemon.url, PING, None)
    assert missing.code == 400
    assert json.loads(missing.read())["error"]["code"] == -32600


def test_stale_session_id_gets_the_sdk_exact_404_body(daemon):
    err = _http_error(daemon.url, PING, "not-a-session")
    assert err.code == 404
    assert err.read() == session_not_found_body()
    assert json.loads(session_not_found_body()) == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32600, "message": "Session not found"},
    }


def test_restart_forgets_sessions_and_bumps_generation(daemon):
    sid, _ = _initialize(daemon.url)
    daemon.restart()

    err = _http_error(daemon.url, PING, sid)
    assert err.code == 404
    assert json.loads(err.read())["error"]["message"] == "Session not found"

    new_sid, resp = _initialize(daemon.url, rid=2)
    assert new_sid != sid
    assert resp["result"]["serverInfo"]["generation"] == 2
    assert daemon.sessions_issued == [sid, new_sid]


def test_stop_opens_a_connection_refused_window_and_start_rebinds_the_same_port(daemon):
    port = daemon.port
    sid, _ = _initialize(daemon.url)
    daemon.stop()
    assert not daemon.running

    with pytest.raises(urllib.error.URLError) as exc:
        _post(daemon.url, PING, sid, timeout=2)
    assert isinstance(exc.value.reason, ConnectionRefusedError)

    daemon.start()
    assert daemon.port == port
    err = _http_error(daemon.url, PING, sid)  # a new process: old session is gone
    assert err.code == 404
    _, resp = _initialize(daemon.url, rid=3)
    assert resp["result"]["serverInfo"]["generation"] == 2


def test_sse_mode_streams_prelude_notifications_then_the_response_chunked():
    prelude = [
        {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"level": "info", "data": "warming"},
        }
    ]
    with FakeStreamableHttpDaemon(response_mode="sse", sse_prelude=prelude) as fake:
        status, headers, body = _post(
            fake.url,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    assert status == 200
    assert headers["Content-Type"] == "text/event-stream"
    assert headers.get("Transfer-Encoding") == "chunked"
    text = body.decode("utf-8")
    events = [block for block in text.split("\n\n") if block.strip()]
    assert len(events) == 2
    assert all(block.startswith("event: message\ndata: ") for block in events)
    first = json.loads(events[0].split("data: ", 1)[1])
    second = json.loads(events[1].split("data: ", 1)[1])
    assert first["method"] == "notifications/message"
    assert second["result"]["serverInfo"]["name"] == "fake-mcp"


def test_notifications_and_client_responses_are_accepted_with_202(daemon):
    sid, _ = _initialize(daemon.url)
    status, _, body = _post(
        daemon.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid
    )
    assert (status, body) == (202, b"")

    status, _, body = _post(
        daemon.url, {"jsonrpc": "2.0", "id": "srv-1", "result": {}}, sid
    )
    assert (status, body) == (202, b"")
    assert daemon.client_responses == [{"jsonrpc": "2.0", "id": "srv-1", "result": {}}]


def test_get_stream_requires_sse_accept_and_relays_pushed_messages(daemon):
    sid, _ = _initialize(daemon.url)

    bare = urllib.request.Request(
        daemon.url, headers={"Mcp-Session-Id": sid}, method="GET"
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(bare, timeout=5)
    assert exc.value.code == 406  # the on-box health probe's "healthy" answer

    stream_req = urllib.request.Request(
        daemon.url,
        headers={"Accept": "text/event-stream", "Mcp-Session-Id": sid},
        method="GET",
    )
    resp = urllib.request.urlopen(stream_req, timeout=5)
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "text/event-stream"
    assert resp.readline() == b": stream open\n"
    assert resp.readline() == b"\n"

    delivered = daemon.push(
        sid, {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}
    )
    assert delivered == 1
    assert resp.readline() == b"event: message\n"
    payload = json.loads(resp.readline().split(b"data: ", 1)[1])
    assert payload["method"] == "notifications/tools/list_changed"
    assert resp.readline() == b"\n"

    daemon.restart()  # the daemon died: the stream must end, not hang
    assert resp.readline() == b""
    resp.close()


def test_get_stream_on_unknown_session_is_404_and_can_be_disabled(daemon):
    stream_req = urllib.request.Request(
        daemon.url,
        headers={"Accept": "text/event-stream", "Mcp-Session-Id": "stale"},
        method="GET",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(stream_req, timeout=5)
    assert exc.value.code == 404
    assert exc.value.read() == session_not_found_body()

    with FakeStreamableHttpDaemon(allow_get_stream=False) as fake:
        sid, _ = _initialize(fake.url)
        req = urllib.request.Request(
            fake.url,
            headers={"Accept": "text/event-stream", "Mcp-Session-Id": sid},
            method="GET",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)
        assert exc.value.code == 405


def test_delete_terminates_the_session_unless_the_server_refuses(daemon):
    sid, _ = _initialize(daemon.url)
    req = urllib.request.Request(
        daemon.url, headers={"Mcp-Session-Id": sid}, method="DELETE"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
    assert _http_error(daemon.url, PING, sid).code == 404

    with FakeStreamableHttpDaemon(delete_status=405) as fake:
        sid, _ = _initialize(fake.url)
        req = urllib.request.Request(
            fake.url, headers={"Mcp-Session-Id": sid}, method="DELETE"
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)
        assert exc.value.code == 405


def test_extra_tools_and_response_delay_are_observable(daemon):
    daemon.extra_tools = [
        {
            "name": "new_tool",
            "description": "added by an upgrade",
            "inputSchema": {"type": "object"},
        }
    ]
    daemon.response_delay = 0.3
    sid, _ = _initialize(daemon.url)
    started = threading.Event()
    result: dict[str, object] = {}

    def call() -> None:
        started.set()
        _, _, body = _post(
            daemon.url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid
        )
        result["names"] = [tool["name"] for tool in json.loads(body)["result"]["tools"]]

    thread = threading.Thread(target=call)
    thread.start()
    started.wait(1)
    thread.join(timeout=5)
    assert result["names"] == ["whoami", "new_tool"]
    assert [r["method"] for r in daemon.requests if r["verb"] == "POST"] == [
        "initialize",
        "tools/list",
    ]


def test_wrong_accept_or_content_type_is_rejected_like_the_sdk(daemon):
    req = urllib.request.Request(
        daemon.url,
        data=json.dumps(PING).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 406

    req = urllib.request.Request(
        daemon.url,
        data=b"ping",
        headers={"Content-Type": "text/plain", "Accept": HEADERS["Accept"]},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 415

    req = urllib.request.Request(
        daemon.url, data=b"{not json", headers=HEADERS, method="POST"
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400
    assert json.loads(exc.value.read())["error"]["code"] == -32700


def test_port_is_free_after_close():
    fake = FakeStreamableHttpDaemon().start()
    port = fake.port
    fake.close()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        assert probe.connect_ex(("127.0.0.1", port)) != 0


# --- behaviours added for the session-healing reverse proxy -----------------


def test_initialize_params_and_protocol_header_are_recorded(daemon):
    params = {
        "protocolVersion": "2025-06-18",
        "capabilities": {"roots": {}},
        "clientInfo": {"name": "cursor", "version": "1.2.3"},
    }
    status, headers, _ = _post(
        daemon.url,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params},
    )
    assert status == 200
    sid = headers["Mcp-Session-Id"]
    req = urllib.request.Request(
        daemon.url,
        data=json.dumps(PING).encode("utf-8"),
        headers={
            **HEADERS,
            "Mcp-Session-Id": sid,
            "MCP-Protocol-Version": "2025-06-18",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200

    init_entry, ping_entry = [r for r in daemon.requests if r["verb"] == "POST"]
    assert init_entry["params"] == params  # a proxy must replay these on heal
    assert init_entry["protocol_version_header"] is None
    assert "params" not in ping_entry
    assert ping_entry["protocol_version_header"] == "2025-06-18"


def test_session_not_found_can_be_reported_in_band_with_http_200():
    """Some servers answer a stale id as a JSON-RPC error on a 200, not a 404."""
    with FakeStreamableHttpDaemon(session_not_found_status=200) as fake:
        sid, _ = _initialize(fake.url)
        fake.restart()
        status, headers, body = _post(fake.url, PING, sid)
    assert status == 200
    assert headers["Content-Type"] == "application/json"
    assert body == session_not_found_body()


def test_force_session_not_found_rejects_valid_requests_but_not_notifications(
    daemon,
):
    """Rehearse a daemon that flaps again in the middle of a client's heal."""
    sid, _ = _initialize(daemon.url)
    daemon.force_session_not_found = 2

    first = _http_error(daemon.url, PING, sid)
    assert first.code == 404 and first.read() == session_not_found_body()
    # a notification is not a request: it is accepted and does not use a strike
    status, _, _ = _post(
        daemon.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid
    )
    assert status == 202
    assert daemon.force_session_not_found == 1
    assert _http_error(daemon.url, PING, sid).code == 404
    assert daemon.force_session_not_found == 0

    status, _, body = _post(daemon.url, PING, sid)  # strikes spent: back to normal
    assert status == 200
    assert json.loads(body)["result"] == {}
    assert sid in daemon.live_sessions()  # the session itself was never dropped


def test_sse_prelude_delay_flushes_each_event_as_it_is_produced():
    prelude = [
        {"jsonrpc": "2.0", "method": "notifications/message", "params": {"n": n}}
        for n in range(3)
    ]
    with FakeStreamableHttpDaemon(
        response_mode="sse", sse_prelude=prelude, sse_prelude_delay=0.15
    ) as fake:
        _, init_headers, _ = _post(  # SSE mode: the initialize body is SSE too
            fake.url,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        req = urllib.request.Request(
            fake.url,
            data=json.dumps(PING).encode("utf-8"),
            headers={**HEADERS, "Mcp-Session-Id": init_headers["Mcp-Session-Id"]},
            method="POST",
        )
        started = time.monotonic()
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.headers.get("Transfer-Encoding") == "chunked"
        first_event = resp.readline()  # arrives before the later events exist
        first_arrival = time.monotonic() - started
        rest = resp.read()
        total = time.monotonic() - started
    assert first_event == b"event: message\n"
    assert first_arrival < 0.12, first_arrival
    assert total >= 0.4, total
    events = [
        json.loads(line[6:]) for line in rest.split(b"\n") if line.startswith(b"data: ")
    ]
    assert [e.get("params", {}).get("n") for e in events[:3]] == [0, 1, 2]
    assert events[3]["result"] == {}
