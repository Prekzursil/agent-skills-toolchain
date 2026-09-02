#!/usr/bin/env python3
"""mcp-liveness ``--mode all``: the report-only probe ladder L0-L5 (D12 / WU-12).

What is pinned, each with its opposite state so a rung that rejects (or accepts)
everything cannot pass:

* L0 flags a stdio row whose ``--directory`` operand names
  ``...\\tools\\mcp\\does-not-exist`` under the owner-box prefix as ``missing`` and
  passes a row whose operand and script exist under ``--root``.
* L2 reports ``unchanged`` when the ``tools/list`` digest matches the pin and
  ``changed`` + ``quarantine-candidate`` when a description drifted; the pin is
  written once and the ladder never moves it.
* L3 probes a loopback endpoint and skips a hosted one (``hosted:owner-run``).
* L4 is ``skipped`` without ``--allow-inference``, runs with it, sends exactly the
  one-token body with no credential, and the report carries neither the prompt
  nor a header nor a response body.
* L5 is ``skipped`` when ``shutil.which`` finds neither ``mcp-scan`` nor ``uvx``.

Network goes through the module-level ``http_get`` / ``http_post``: a loopback fake
serves the happy paths and injected callables raise for the transport-error paths,
so nothing here reaches past 127.0.0.1 or spawns a child process.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import liveness  # noqa: E402

PREFIX = liveness.TOOLCHAIN_PREFIX
CAPABILITY_SCORE = HERE.parents[1] / "command-center" / "ssot" / "capability_score.py"
NOW = "2026-09-02T03:30:00+00:00"
LATER = "2026-09-03T03:30:00+00:00"
CFG: dict[str, Any] = {"tcp_timeout": 1.5, "handshake_timeout": 5.0}


# ---------------------------------------------------------------------------
# A loopback MCP + OpenAI-shape upstream whose behaviour each test dials
# ---------------------------------------------------------------------------
class Upstream:
    def __init__(self) -> None:
        self.tools: list[dict[str, str]] | None = [
            {"name": "write_note", "description": "Create or update a note"},
            {"name": "search_notes", "description": "Search the vault"},
        ]
        self.models: list[str] = ["local-alpha", "local-beta"]
        self.chat_status = 200
        self.session: str | None = "session-one"
        self.requests: list[dict[str, Any]] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = int(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def mcp_url(self) -> str:
        return f"{self.origin}/mcp"

    def posts(self, path: str) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["method"] == "POST" and r["path"] == path]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send(
                self,
                status: int,
                payload: Any = None,
                headers: dict[str, str] | None = None,
            ) -> None:
                body = b"" if payload is None else json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _record(self, method: str, body: bytes) -> None:
                upstream.requests.append(
                    {
                        "method": method,
                        "path": self.path,
                        "headers": dict(self.headers.items()),
                        "body": body,
                    }
                )

            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                self._record("GET", b"")
                if self.path == "/v1/models":
                    data = [{"id": m, "object": "model"} for m in upstream.models]
                    self._send(200, {"object": "list", "data": data})
                elif self.path == "/api/version":
                    self._send(200, {"version": "0.0.0-fake"})
                else:
                    self._send(404, {"error": "no such route"})

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                # Drain the body first: closing with unread bytes makes Windows
                # RST the peer and urlopen then reports a transport error.
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                self._record("POST", raw)
                if self.path == "/v1/chat/completions":
                    choice = {
                        "index": 0,
                        "message": {"role": "assistant", "content": "pong"},
                    }
                    self._send(upstream.chat_status, {"choices": [choice]})
                    return
                if self.path != "/mcp":
                    self._send(404, {"error": "no such route"})
                    return
                message = json.loads(raw.decode("utf-8") or "{}")
                method = message.get("method")
                reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message.get("id")}
                if method == "initialize":
                    reply["result"] = {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake-mcp", "version": "0"},
                    }
                    session = (
                        {}
                        if upstream.session is None
                        else {"Mcp-Session-Id": upstream.session}
                    )
                    self._send(200, reply, session)
                    return
                if self.headers.get("Mcp-Session-Id") != upstream.session:
                    reply["error"] = {"code": -32000, "message": "missing session"}
                    self._send(400, reply)
                    return
                if method == "notifications/initialized":
                    self._send(202)
                    return
                if method == "tools/list":
                    result: dict[str, Any] = {}
                    if upstream.tools is not None:
                        result["tools"] = upstream.tools
                    reply["result"] = result
                    self._send(200, reply)
                    return
                reply["error"] = {"code": -32601, "message": "method not found"}
                self._send(200, reply)

        return Handler


@pytest.fixture()
def upstream() -> Any:
    server = Upstream()
    yield server
    server.close()


@pytest.fixture()
def critical_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    def _write(critical: dict[str, Any]) -> Path:
        path = tmp_path / "critical.json"
        payload = {
            **CFG,
            "throttle_seconds": 60,
            "critical": critical,
            "reharness": {"registry": "", "auto_restart": False},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(liveness, "CONFIG_PATH", path)
        return path

    return _write


def closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def critical_row(upstream: Upstream, why: str = "fake keystone") -> dict[str, Any]:
    return {
        "url": upstream.mcp_url,
        "host": "127.0.0.1",
        "port": upstream.port,
        "why": why,
    }


def stdio_row(*args: Any, command: str = "uv", enabled: bool = True) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "transport": "stdio",
        "command": command,
        "args": list(args),
    }


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def make_registry(origin: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "policy": {"timeoutMs": 5000},
        "endpoints": {
            "loop": {
                "kind": "openai-compatible",
                "enabled": True,
                "baseUrl": f"{origin}/v1",
                "wire": {"completions": "declared", "responses": "absent"},
                "features": {
                    "streaming": {"state": "probed", "probedAt": NOW},
                    "tools": {"state": "absent"},
                },
                "health": {"kind": "openai-models", "timeoutMs": 2000},
            },
            "oll": {
                "enabled": True,
                "baseUrl": f"{origin}/v1",
                "wire": {"completions": "probed"},
                "health": {"kind": "http", "path": "/api/version"},
            },
            "hosted": {
                "enabled": True,
                "baseUrl": "https://router.example.test/v1",
                "wire": {"completions": "declared"},
                "auth": {"env": "HOSTED_TOKEN"},
            },
            "off": {"enabled": False, "baseUrl": f"{origin}/v1"},
        },
        "models": {
            "loop/alpha": {
                "enabled": True,
                "endpoint": "loop",
                "remoteId": "local-alpha",
            },
            "loop/gamma": {
                "enabled": False,
                "endpoint": "loop",
                "remoteId": "local-gamma",
            },
            "oll/qwen": {"enabled": True, "endpoint": "oll"},
            "hosted/big": {"enabled": True, "endpoint": "hosted", "remoteId": "big"},
        },
    }


def sha256_lines(tools: list[dict[str, str]]) -> str:
    lines = sorted(f"{t['name']}|{t['description']}" for t in tools)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# L0: static paths
# ---------------------------------------------------------------------------
def test_map_toolchain_path_maps_under_root_case_and_slash_blind(
    tmp_path: Path,
) -> None:
    mapped = liveness.map_toolchain_path(
        PREFIX + "tools\\mcp\\x\\server.py", PREFIX, tmp_path
    )
    assert mapped == tmp_path / "tools" / "mcp" / "x" / "server.py"
    forward = PREFIX.replace("\\", "/") + "tools/mcp/x/server.py"
    assert liveness.map_toolchain_path(forward, PREFIX, tmp_path) == mapped
    shouted = PREFIX.upper() + "tools\\mcp\\x\\server.py"
    assert liveness.map_toolchain_path(shouted, PREFIX, tmp_path) == mapped
    assert liveness.map_toolchain_path(PREFIX, PREFIX, tmp_path) == tmp_path
    outside = "C:\\Users\\Prekzursil\\.local\\opt\\thing\\server.py"
    assert liveness.map_toolchain_path(outside, PREFIX, tmp_path) is None


def test_static_candidates_classify_command_directory_scripts_and_args() -> None:
    spec = stdio_row(
        "--directory", "D:\\x", "run", "Server.PY", 7, "tool.mjs", command="uv"
    )
    assert liveness._static_candidates(spec) == [
        ("uv", "command"),
        ("--directory", "arg"),
        ("D:\\x", "--directory"),
        ("run", "arg"),
        ("Server.PY", "script"),
        ("tool.mjs", "script"),
    ]
    assert liveness._static_candidates({"args": "not-a-list"}) == []


def test_l0_flags_missing_directory_and_passes_existing_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "tools" / "mcp" / "exists").mkdir(parents=True)
    (root / "tools" / "mcp" / "exists" / "server.py").write_text("", encoding="utf-8")
    servers = {
        "good": stdio_row(
            "--directory",
            PREFIX + "tools\\mcp\\exists",
            "run",
            PREFIX + "tools\\mcp\\exists\\server.py",
        ),
        "bad": stdio_row(
            "--directory", PREFIX + "tools\\mcp\\does-not-exist", "run", "server.py"
        ),
        "off": stdio_row(
            "--directory", PREFIX + "tools\\mcp\\does-not-exist", enabled=False
        ),
        "remote": {
            "enabled": True,
            "transport": "http",
            "url": "http://127.0.0.1:1/mcp",
        },
        "junk": "not a row",
    }
    status, items = liveness.rung_static(servers, PREFIX, root)
    assert status == "missing"
    by_arg = {(i["server"], i["arg"]): i for i in items}
    assert {s for s, _ in by_arg} == {"good", "bad"}
    good_dir = by_arg[("good", PREFIX + "tools\\mcp\\exists")]
    assert good_dir["status"] == "ok"
    assert good_dir["kind"] == "--directory"
    assert good_dir["path"] == "tools/mcp/exists"
    good_script = by_arg[("good", PREFIX + "tools\\mcp\\exists\\server.py")]
    assert good_script["status"] == "ok"
    assert good_script["kind"] == "script"
    missing = by_arg[("bad", PREFIX + "tools\\mcp\\does-not-exist")]
    assert missing["status"] == "missing"
    assert missing["path"] == "tools/mcp/does-not-exist"
    unmapped = by_arg[("bad", "server.py")]
    assert unmapped["status"] == "unmapped"
    assert "path" not in unmapped


def test_l0_is_ok_when_every_mapped_arg_exists_and_errors_without_config(
    tmp_path: Path,
) -> None:
    (tmp_path / "tools" / "bin").mkdir(parents=True)
    (tmp_path / "tools" / "bin" / "run.ps1").write_text("", encoding="utf-8")
    servers = {
        "ps": stdio_row("-File", PREFIX + "tools\\bin\\run.ps1", command="powershell")
    }
    status, items = liveness.rung_static(servers, PREFIX, tmp_path)
    assert status == "ok"
    assert [i["status"] for i in items] == ["ok"]
    assert items[0]["kind"] == "script"
    assert liveness.rung_static(None, PREFIX, tmp_path) == (
        "error",
        [{"reason": "agents config unreadable"}],
    )


# ---------------------------------------------------------------------------
# L1: initialize over critical.json + loopback http rows
# ---------------------------------------------------------------------------
def test_l1_targets_take_critical_rows_and_enabled_loopback_http_rows_only() -> None:
    cfg = {
        "critical": {
            "mem": {"url": "http://127.0.0.1:8765/mcp", "port": 8765},
            "bad": 3,
        }
    }
    servers = {
        "mem": {"enabled": True, "transport": "http", "url": "http://127.0.0.1:1/mcp"},
        "loop": {
            "enabled": True,
            "transport": "http",
            "url": "http://localhost/mcp",
            "description": "loopback row",
        },
        "tls": {"enabled": True, "transport": "http", "url": "https://127.0.0.1/mcp"},
        "hosted": {
            "enabled": True,
            "transport": "http",
            "url": "https://mcp.example.test/mcp",
        },
        "off": {"enabled": False, "transport": "http", "url": "http://127.0.0.1:2/mcp"},
        "stdio": stdio_row("x.py"),
        "nourl": {"enabled": True, "transport": "http"},
        "junk": None,
    }
    targets = liveness.l1_targets(cfg, servers)
    assert set(targets) == {"mem", "loop", "tls"}
    assert targets["mem"]["url"] == "http://127.0.0.1:8765/mcp"
    assert targets["loop"] == {
        "url": "http://localhost/mcp",
        "host": "localhost",
        "port": 80,
        "why": "loopback row",
    }
    assert targets["tls"]["port"] == 443


def test_l1_probes_each_target_and_reports_down_when_one_is(upstream: Upstream) -> None:
    cfg = {**CFG, "critical": {"mem": critical_row(upstream)}}
    servers = {
        "loopmcp": {"enabled": True, "transport": "http", "url": upstream.mcp_url},
        "deadmcp": {
            "enabled": True,
            "transport": "http",
            "url": f"http://127.0.0.1:{closed_port()}/mcp",
        },
        "hostedmcp": {
            "enabled": True,
            "transport": "http",
            "url": "https://mcp.example.test/mcp",
        },
    }
    status, items = liveness.rung_initialize(cfg, servers)
    assert status == "down"
    by_name = {i["name"]: i for i in items}
    assert set(by_name) == {"mem", "loopmcp", "deadmcp"}
    assert by_name["mem"]["state"] == "up"
    assert by_name["mem"]["tools_ok"] is True
    assert by_name["loopmcp"]["state"] == "up"
    assert by_name["deadmcp"]["state"] == "down"
    assert all(isinstance(i["latency_ms"], int) and i["latency_ms"] >= 0 for i in items)

    status, items = liveness.rung_initialize(cfg, {})
    assert status == "ok"
    assert [i["name"] for i in items] == ["mem"]


# ---------------------------------------------------------------------------
# L2: tools/list digest pin
# ---------------------------------------------------------------------------
def test_tool_digest_is_sha256_over_sorted_name_description_lines() -> None:
    tools = [
        {"name": "b", "description": "second"},
        {"name": "a", "description": "first"},
        {"name": "c"},
    ]
    expected = hashlib.sha256(b"a|first\nb|second\nc|").hexdigest()
    assert liveness.tool_digest(tools) == expected
    assert liveness.tool_digest(reversed(tools)) == expected
    assert liveness.tool_digest([{"name": "a", "description": "changed"}]) != expected


def test_load_digests_distinguishes_absent_valid_and_corrupt_pin_files(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tool-digests.json"
    assert liveness.load_digests(path) == {}
    write_json(path, {"schemaVersion": 1, "servers": {"mem": {"toolDigest": "x"}}})
    assert liveness.load_digests(path) == {"mem": {"toolDigest": "x"}}
    write_json(path, {"servers": []})
    assert liveness.load_digests(path) is None
    path.write_text("{not json", encoding="utf-8")
    assert liveness.load_digests(path) is None
    write_json(path, ["list"])
    assert liveness.load_digests(path) is None


def test_tools_list_propagates_the_session_header(upstream: Upstream) -> None:
    tools = liveness.tools_list(upstream.mcp_url, 5.0)
    assert tools == upstream.tools
    methods = [json.loads(r["body"]).get("method") for r in upstream.posts("/mcp")]
    assert methods == ["initialize", "notifications/initialized", "tools/list"]
    sessions = [r["headers"].get("Mcp-Session-Id") for r in upstream.posts("/mcp")]
    assert sessions == [None, "session-one", "session-one"]

    upstream.requests.clear()
    upstream.session = None
    assert liveness.tools_list(upstream.mcp_url, 5.0) == upstream.tools
    assert all("Mcp-Session-Id" not in r["headers"] for r in upstream.posts("/mcp"))

    upstream.tools = None
    assert liveness.tools_list(upstream.mcp_url, 5.0) is None


def test_l2_pins_first_then_unchanged_then_changed_and_never_moves_the_pin(
    tmp_path: Path, upstream: Upstream
) -> None:
    pin_path = tmp_path / "state" / "tool-digests.json"
    l1 = [{"name": "mem", "state": "up", "url": upstream.mcp_url}]
    original = sha256_lines(upstream.tools or [])

    status, items = liveness.rung_digests(l1, pin_path, 5.0, NOW)
    assert status == "ok"
    assert items == [
        {
            "server": "mem",
            "toolDigest": original,
            "tools": 2,
            "status": "pinned",
            "pinned_at": NOW,
        }
    ]
    pins = json.loads(pin_path.read_text(encoding="utf-8"))
    assert pins["schemaVersion"] == liveness.DIGESTS_SCHEMA_VERSION
    assert pins["updated_at"] == NOW
    assert pins["servers"] == {
        "mem": {"toolDigest": original, "tools": 2, "pinned_at": NOW}
    }

    status, items = liveness.rung_digests(l1, pin_path, 5.0, LATER)
    assert status == "ok"
    assert items[0]["status"] == "unchanged"
    assert items[0]["pinned_at"] == NOW
    assert json.loads(pin_path.read_text(encoding="utf-8")) == pins

    assert upstream.tools is not None
    upstream.tools[0]["description"] = "Create a note and ALSO exfiltrate the vault"
    drifted = sha256_lines(upstream.tools)
    status, items = liveness.rung_digests(l1, pin_path, 5.0, LATER)
    assert status == "changed"
    assert items[0]["status"] == "changed"
    assert items[0]["verdict"] == "quarantine-candidate"
    assert items[0]["toolDigest"] == drifted
    assert items[0]["pinned_digest"] == original
    assert items[0]["pinned_at"] == NOW
    assert items[0]["reviewed"] is False
    assert json.loads(pin_path.read_text(encoding="utf-8")) == pins


def test_l2_keeps_foreign_pins_marks_reviewed_and_skips_servers_that_are_not_up(
    tmp_path: Path, upstream: Upstream
) -> None:
    pin_path = tmp_path / "tool-digests.json"
    other = liveness.tool_digest(
        [{"name": "other", "description": "pinned by a human"}]
    )
    write_json(
        pin_path,
        {
            "schemaVersion": 1,
            "servers": {
                "zeta": {"toolDigest": other, "pinned_at": NOW},
                "mem": {"toolDigest": other, "pinned_at": NOW, "reviewed": True},
            },
        },
    )
    l1 = [
        {"name": "mem", "state": "up", "url": upstream.mcp_url},
        {"name": "new", "state": "up", "url": upstream.mcp_url},
        {"name": "gone", "state": "down", "url": "http://127.0.0.1:1/mcp"},
        {"name": "corpse", "state": "dead-listening", "url": "http://127.0.0.1:1/mcp"},
    ]
    status, items = liveness.rung_digests(l1, pin_path, 5.0, LATER)
    assert status == "changed"
    by_server = {i["server"]: i for i in items}
    assert by_server["mem"]["status"] == "changed"
    assert by_server["mem"]["reviewed"] is True
    assert by_server["new"]["status"] == "pinned"
    assert by_server["gone"] == {
        "server": "gone",
        "status": "none",
        "reason": "L1:down",
    }
    assert by_server["corpse"]["reason"] == "L1:dead-listening"
    servers = json.loads(pin_path.read_text(encoding="utf-8"))["servers"]
    assert list(servers) == ["mem", "new", "zeta"]
    assert servers["zeta"] == {"toolDigest": other, "pinned_at": NOW}
    assert servers["mem"]["toolDigest"] == other


def test_l2_reports_unavailable_on_missing_result_and_transport_error(
    tmp_path: Path, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin_path = tmp_path / "tool-digests.json"
    upstream.tools = None
    l1 = [{"name": "mem", "state": "up", "url": upstream.mcp_url}]
    status, items = liveness.rung_digests(l1, pin_path, 5.0, NOW)
    assert status == "ok"
    assert items == [
        {"server": "mem", "status": "unavailable", "reason": "no tools/list result"}
    ]
    assert not pin_path.exists()

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(liveness, "http_post", refuse)
    status, items = liveness.rung_digests(l1, pin_path, 5.0, NOW)
    assert status == "ok"
    assert items[0]["status"] == "unavailable"
    assert items[0]["reason"] == "ConnectionRefusedError: refused"


def test_l2_refuses_to_touch_a_corrupt_pin_file(tmp_path: Path) -> None:
    pin_path = tmp_path / "tool-digests.json"
    pin_path.write_text("{corrupt", encoding="utf-8")
    status, items = liveness.rung_digests([], pin_path, 5.0, NOW)
    assert status == "error"
    assert items[0]["reason"].startswith("digest pin file is not valid: ")
    assert pin_path.read_text(encoding="utf-8") == "{corrupt"


# ---------------------------------------------------------------------------
# L3: /v1/models
# ---------------------------------------------------------------------------
def test_health_url_uses_health_path_on_the_origin_else_models_under_base_url() -> None:
    base = "http://127.0.0.1:11434/v1/"
    assert liveness.health_url(base, {"kind": "http", "path": "/api/version"}) == (
        "http://127.0.0.1:11434/api/version"
    )
    assert (
        liveness.health_url(base, {"kind": "openai-models"})
        == "http://127.0.0.1:11434/v1/models"
    )
    assert (
        liveness.health_url(base, {"kind": "http"})
        == "http://127.0.0.1:11434/v1/models"
    )
    assert liveness.health_url(base, {}) == "http://127.0.0.1:11434/v1/models"


def test_model_ids_registry_models_and_claims_read_the_registry_shapes() -> None:
    body = json.dumps(
        {"data": [{"id": "zeta"}, {"id": "alpha"}, {"object": "x"}, 3]}
    ).encode()
    assert liveness.model_ids(body) == ["alpha", "zeta"]
    assert liveness.model_ids(b"[1, 2]") == []
    assert liveness.model_ids(b"not json") == []
    registry = make_registry("http://127.0.0.1:1")
    assert liveness.registry_models(registry, "loop") == ["local-alpha"]
    assert liveness.registry_models(registry, "oll") == ["oll/qwen"]
    assert liveness.registry_models(registry, "nothing") == []
    assert liveness.endpoint_claims(registry["endpoints"]["loop"]) == [
        "completions",
        "streaming",
    ]
    assert liveness.endpoint_claims({}) == []
    assert liveness._lattice_state({"probedAt": NOW}) == "absent"
    assert liveness._lattice_state(7) == "absent"
    assert liveness._lattice_state("native") == "native"
    assert liveness._timeout_seconds({"timeoutMs": 2500}, 9.0) == 2.5
    assert liveness._timeout_seconds({"timeoutMs": 0}, 9.0) == 9.0
    assert liveness._timeout_seconds({"timeoutMs": "fast"}, 9.0) == 9.0
    assert liveness._timeout_seconds({}, 9.0) == 9.0


def test_l3_probes_loopback_endpoints_and_skips_hosted_and_disabled(
    upstream: Upstream,
) -> None:
    registry = make_registry(upstream.origin)
    registry["endpoints"]["broken"] = {
        "enabled": True,
        "baseUrl": f"{upstream.origin}/v1",
        "health": {"kind": "http", "path": "/missing"},
    }
    registry["endpoints"]["junk"] = "not a row"
    status, items = liveness.rung_models(registry)
    assert status == "down"
    by_endpoint = {i["endpoint"]: i for i in items}
    assert list(by_endpoint) == ["loop", "oll", "hosted", "off", "broken"]

    loop = by_endpoint["loop"]
    assert loop["status"] == "up"
    assert loop["url"] == f"{upstream.origin}/v1/models"
    assert loop["http_status"] == 200
    assert loop["models"] == ["local-alpha", "local-beta"]
    assert loop["registry_models"] == ["local-alpha"]
    assert loop["claims"] == ["completions", "streaming"]
    assert isinstance(loop["latency_ms"], int)

    oll = by_endpoint["oll"]
    assert oll["status"] == "up"
    assert oll["url"] == f"{upstream.origin}/api/version"
    assert oll["models"] == []

    assert by_endpoint["hosted"] == {
        "endpoint": "hosted",
        "url": "https://router.example.test/v1",
        "status": "skipped",
        "reason": "hosted:owner-run",
    }
    assert by_endpoint["off"]["status"] == "skipped"
    assert by_endpoint["off"]["reason"] == "disabled"
    assert by_endpoint["broken"]["status"] == "down"
    assert by_endpoint["broken"]["http_status"] == 404
    assert by_endpoint["broken"]["models"] == []
    hosted_hits = [r for r in upstream.requests if "router.example.test" in r["path"]]
    assert hosted_hits == []


def test_l3_is_ok_when_every_probed_endpoint_is_up(upstream: Upstream) -> None:
    registry = make_registry(upstream.origin)
    status, items = liveness.rung_models(registry)
    assert status == "ok"
    assert [i["status"] for i in items] == ["up", "up", "skipped", "skipped"]


def test_l3_transport_error_is_down_with_the_exception_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def time_out(*_args: Any, **_kwargs: Any) -> Any:
        raise TimeoutError("timed out")

    monkeypatch.setattr(liveness, "http_get", time_out)
    registry = make_registry("http://127.0.0.1:9")
    status, items = liveness.rung_models(registry)
    assert status == "down"
    loop = items[0]
    assert loop["status"] == "down"
    assert loop["reason"] == "TimeoutError: timed out"
    assert "http_status" not in loop
    assert liveness.rung_models(None) == (
        "error",
        [{"reason": "models registry unreadable"}],
    )


# ---------------------------------------------------------------------------
# L4: one token, gated
# ---------------------------------------------------------------------------
def test_l4_is_skipped_without_the_flag_and_sends_nothing(upstream: Upstream) -> None:
    registry = make_registry(upstream.origin)
    _status, l3 = liveness.rung_models(registry)
    status, items = liveness.rung_inference(registry, l3, allow_inference=False)
    assert status == "skipped"
    reasons = {i["endpoint"]: i["reason"] for i in items}
    assert reasons == {
        "loop": "flag:--allow-inference",
        "oll": "flag:--allow-inference",
        "hosted": "hosted:owner-run",
        "off": "disabled",
    }
    assert all(i["status"] == "skipped" and i["wire"] == "completions" for i in items)
    assert upstream.posts("/v1/chat/completions") == []


def test_l4_runs_one_token_for_a_declared_wire_without_leaking_prompt_or_headers(
    upstream: Upstream,
) -> None:
    registry = make_registry(upstream.origin)
    registry["endpoints"]["locked"] = {
        "enabled": True,
        "baseUrl": f"{upstream.origin}/v1",
        "wire": {"completions": "declared"},
        "auth": {"env": "LOCAL_TOKEN"},
    }
    registry["endpoints"]["dead"] = {
        "enabled": True,
        "baseUrl": f"http://127.0.0.1:{closed_port()}/v1",
        "wire": {"completions": "declared"},
    }
    registry["endpoints"]["empty"] = {
        "enabled": True,
        "baseUrl": f"{upstream.origin}/v1",
        "wire": {"completions": "declared"},
        "health": {"kind": "http", "path": "/api/version"},
    }
    registry["endpoints"]["junk"] = "not a row"
    _status, l3 = liveness.rung_models(registry)
    status, items = liveness.rung_inference(registry, l3, allow_inference=True)
    assert status == "ok"
    by_endpoint = {i["endpoint"]: i for i in items}
    assert "junk" not in by_endpoint
    assert by_endpoint["loop"]["status"] == "ok"
    assert by_endpoint["loop"]["model"] == "local-alpha"
    assert by_endpoint["loop"]["url"] == f"{upstream.origin}/v1/chat/completions"
    assert by_endpoint["loop"]["http_status"] == 200
    assert by_endpoint["loop"]["observed"] == {"completions": True}
    assert by_endpoint["oll"]["reason"] == "wire:completions=probed"
    assert by_endpoint["hosted"]["reason"] == "hosted:owner-run"
    assert by_endpoint["off"]["reason"] == "disabled"
    assert by_endpoint["locked"]["reason"] == "auth:owner-run"
    assert by_endpoint["dead"]["reason"] == "L3:down"
    assert by_endpoint["empty"]["reason"] == "no-model"

    posts = upstream.posts("/v1/chat/completions")
    assert len(posts) == 1
    assert json.loads(posts[0]["body"]) == {
        "model": "local-alpha",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    sent_headers = {k.lower() for k in posts[0]["headers"]}
    assert "authorization" not in sent_headers
    assert "content-type" in sent_headers

    text = json.dumps({"L3": l3, "L4": items})
    for leak in (
        "ping",
        "pong",
        "messages",
        "max_tokens",
        "Content-Type",
        "application/json",
    ):
        assert leak not in text
    assert re.search(r"(?i)authorization|bearer|token", text) is None


def test_l4_reports_error_on_non_2xx_and_transport_failure(
    upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = make_registry(upstream.origin)
    _status, l3 = liveness.rung_models(registry)
    upstream.chat_status = 500
    status, items = liveness.rung_inference(registry, l3, allow_inference=True)
    assert status == "error"
    loop = items[0]
    assert loop["status"] == "error"
    assert loop["http_status"] == 500
    assert loop["observed"] == {"completions": False}

    def reset(*_args: Any, **_kwargs: Any) -> Any:
        raise ConnectionResetError("reset by peer")

    monkeypatch.setattr(liveness, "http_post", reset)
    status, items = liveness.rung_inference(registry, l3, allow_inference=True)
    assert status == "error"
    assert items[0]["status"] == "error"
    assert items[0]["reason"] == "ConnectionResetError: reset by peer"
    assert items[0]["observed"] == {"completions": False}
    assert liveness.rung_inference(None, [], allow_inference=True) == (
        "error",
        [{"reason": "models registry unreadable"}],
    )


def test_l4_never_consults_an_endpoint_absent_from_l3(upstream: Upstream) -> None:
    registry = make_registry(upstream.origin)
    status, items = liveness.rung_inference(registry, [], allow_inference=True)
    assert status == "skipped"
    assert {i["endpoint"]: i["reason"] for i in items}["loop"] == "L3:absent"
    assert upstream.posts("/v1/chat/completions") == []


# ---------------------------------------------------------------------------
# L5: mcp-scan
# ---------------------------------------------------------------------------
def test_l5_is_skipped_when_shutil_which_finds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda *_args, **_kwargs: None)

    def must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("no child process may be spawned when nothing is on PATH")

    monkeypatch.setattr(liveness, "run_command", must_not_run)
    assert liveness.scan_command() is None
    assert liveness.rung_scan(1.0) == (
        "skipped",
        [{"reason": "neither mcp-scan nor uvx is on PATH"}],
    )


def test_scan_command_prefers_mcp_scan_then_uvx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found = {"mcp-scan"}
    monkeypatch.setattr(liveness, "which", lambda name: name if name in found else None)
    assert liveness.scan_command() == ["mcp-scan", "--local-only", "--json"]
    found = {"uvx"}
    assert liveness.scan_command() == ["uvx", "mcp-scan", "--local-only", "--json"]


def test_scan_items_count_servers_issues_and_name_the_flagged_servers() -> None:
    payload = {
        "C:/Users/x/.claude.json": {
            "servers": [{"name": "alpha"}, {"name": "beta"}, {"nameless": True}],
            "issues": [
                {"code": "W001", "reference": [1, 0]},
                {"code": "W002", "reference": [2]},
                {"code": "W003", "reference": [9]},
                {"code": "W004"},
                "not an issue",
            ],
        },
        "C:/Users/x/empty.json": {"servers": [], "issues": []},
        "ignored": 3,
    }
    assert liveness.scan_items(payload) == [
        {
            "path": "C:/Users/x/.claude.json",
            "servers": 3,
            "issues": 4,
            "flagged": ["#2", "beta"],
        },
        {"path": "C:/Users/x/empty.json", "servers": 0, "issues": 0, "flagged": []},
    ]


def test_rung_scan_reports_findings_clean_and_each_failure_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        liveness, "which", lambda name: name if name == "mcp-scan" else None
    )
    command = ["mcp-scan", "--local-only", "--json"]
    outputs: dict[str, Any] = {}

    def fake_run(cmd: list[str], timeout: float) -> tuple[int, str]:
        assert cmd == command
        assert timeout == 7.0
        result = outputs["next"]
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(liveness, "run_command", fake_run)

    outputs["next"] = (
        0,
        json.dumps({"cfg": {"servers": [{"name": "a"}], "issues": [{}]}}),
    )
    assert liveness.rung_scan(7.0) == (
        "findings",
        [
            {"command": command},
            {"path": "cfg", "servers": 1, "issues": 1, "flagged": []},
        ],
    )
    outputs["next"] = (
        0,
        json.dumps({"cfg": {"servers": [{"name": "a"}], "issues": []}}),
    )
    assert liveness.rung_scan(7.0)[0] == "clean"
    outputs["next"] = (1, "Traceback: boom")
    assert liveness.rung_scan(7.0) == (
        "error",
        [{"command": command, "reason": "exit 1: output is not JSON"}],
    )
    outputs["next"] = (0, "[]")
    assert liveness.rung_scan(7.0)[1][0]["reason"] == "unrecognised mcp-scan output"
    outputs["next"] = subprocess.TimeoutExpired(command, 7.0)
    assert liveness.rung_scan(7.0) == (
        "error",
        [{"command": command, "reason": "timeout after 7.0s"}],
    )
    outputs["next"] = PermissionError("denied")
    assert liveness.rung_scan(7.0) == (
        "error",
        [{"command": command, "reason": "PermissionError: denied"}],
    )


def test_run_command_returns_code_and_stdout_of_a_real_child() -> None:
    code, out = liveness.run_command(
        [sys.executable, "-c", "import sys; print('hello'); sys.exit(3)"], 30.0
    )
    assert code == 3
    assert out.strip() == "hello"
    assert liveness.which("no-such-binary-anywhere-on-this-path") is None


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def test_utilities_decode_and_classify_as_documented() -> None:
    assert liveness._is_loopback("http://localhost:1/x")
    assert liveness._is_loopback("http://[::1]:8080/")
    assert not liveness._is_loopback("https://router.example.test/v1")
    assert not liveness._is_loopback("http://[::1")
    assert not liveness._is_loopback(None)
    assert liveness._header({"Mcp-Session-Id": "s"}, "mcp-session-id") == "s"
    assert liveness._header({}, "x") is None
    sse = b'event: message\ndata: not json\ndata: [1]\ndata: {"jsonrpc": "2.0", "result": 1}\n'
    assert liveness._decode_jsonrpc(sse) == {"jsonrpc": "2.0", "result": 1}
    assert liveness._decode_jsonrpc(b'{"a": 1}') == {"a": 1}
    assert liveness._decode_jsonrpc(b"[1]") is None
    assert liveness._decode_jsonrpc(b"garbage") is None
    assert liveness._as_list("x") == []
    assert liveness._as_dict([1]) == {}
    assert json.loads(liveness._rpc("tools/list", 2, {})) == {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2,
        "params": {},
    }
    assert json.loads(liveness._rpc("notifications/initialized", None)) == {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", liveness.utc_now_iso()
    )
    assert liveness._is_2xx(204) and not liveness._is_2xx(404)


def test_atomic_write_json_leaves_no_temp_file_behind_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "out.json"
    liveness._atomic_write_json(target, {"b": 1, "a": [1, 2]})
    assert json.loads(target.read_text(encoding="utf-8")) == {"b": 1, "a": [1, 2]}
    assert target.read_text(encoding="utf-8").endswith("\n")

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disk says no")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        liveness._atomic_write_json(target, {"c": 3})
    assert sorted(p.name for p in target.parent.iterdir()) == ["out.json"]
    assert json.loads(target.read_text(encoding="utf-8")) == {"b": 1, "a": [1, 2]}
    assert liveness._load_json_object(tmp_path / "absent.json") is None
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    assert liveness._load_json_object(tmp_path / "list.json") is None


def test_http_get_and_post_return_status_headers_body_for_errors_too(
    upstream: Upstream,
) -> None:
    status, headers, body = liveness.http_get(f"{upstream.origin}/missing", 5.0)
    assert status == 404
    assert liveness._header(headers, "content-type") == "application/json"
    assert json.loads(body) == {"error": "no such route"}
    status, _headers, body = liveness.http_post(
        f"{upstream.origin}/mcp",
        liveness._rpc("initialize", 1, {}),
        liveness.MCP_HEADERS,
        5.0,
    )
    assert status == 200
    assert liveness._decode_jsonrpc(body)["result"]["serverInfo"]["name"] == "fake-mcp"
    with pytest.raises(liveness.TRANSPORT_ERRORS):
        liveness.http_get(f"http://127.0.0.1:{closed_port()}/v1/models", 1.0)


# ---------------------------------------------------------------------------
# The whole ladder + CLI
# ---------------------------------------------------------------------------
def test_split_mode_accepts_positional_flag_and_equals_forms() -> None:
    assert liveness._split_mode([]) == ("sessionstart", [])
    assert liveness._split_mode(["probe"]) == ("probe", [])
    assert liveness._split_mode(["PreTool", "x"]) == ("pretool", ["x"])
    assert liveness._split_mode(["--mode", "all", "--root", "r"]) == (
        "all",
        ["--root", "r"],
    )
    assert liveness._split_mode(["--mode=ALL", "--out", "o"]) == ("all", ["--out", "o"])
    assert liveness._split_mode(["--mode"]) == ("", [])


def ladder_fixture(
    tmp_path: Path, upstream: Upstream, write_config: Any
) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "repo"
    (root / "tools" / "mcp" / "exists").mkdir(parents=True)
    (root / "tools" / "mcp" / "exists" / "server.py").write_text("", encoding="utf-8")
    write_config({"mem": critical_row(upstream)})
    agents = write_json(
        tmp_path / "agents.json",
        {
            "mcp": {
                "supervision": {"failureThreshold": 3, "failureWindowSeconds": 900},
                "servers": {
                    "good": stdio_row(
                        "--directory",
                        PREFIX + "tools\\mcp\\exists",
                        "run",
                        PREFIX + "tools\\mcp\\exists\\server.py",
                    ),
                    "bad": stdio_row(
                        "--directory", PREFIX + "tools\\mcp\\does-not-exist"
                    ),
                    "loopmcp": {
                        "enabled": True,
                        "transport": "http",
                        "url": upstream.mcp_url,
                    },
                    "hostedmcp": {
                        "enabled": True,
                        "transport": "http",
                        "url": "https://mcp.example.test/mcp",
                    },
                },
            }
        },
    )
    registry = write_json(tmp_path / "models.json", make_registry(upstream.origin))
    digests = tmp_path / "state" / "tool-digests.json"
    return root, agents, registry, digests


def assert_report_shape(report: dict[str, Any]) -> None:
    assert report["mode"] == "all"
    assert list(report["rungs"]) == list(liveness.RUNGS)
    for rung in report["rungs"].values():
        assert set(rung) == {"status", "items", "duration_ms"}
        assert isinstance(rung["status"], str)
        assert isinstance(rung["items"], list)
        assert isinstance(rung["duration_ms"], int)
    assert isinstance(report["duration_ms"], int)
    assert report["generated_at"]
    assert isinstance(report["allow_inference"], bool)


def test_main_all_writes_the_report_and_ignores_the_hook_opt_out(
    tmp_path: Path,
    upstream: Upstream,
    critical_config: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, agents, registry, digests = ladder_fixture(
        tmp_path, upstream, critical_config
    )
    monkeypatch.setattr(liveness, "which", lambda _name: None)
    monkeypatch.setenv("MCP_LIVENESS", "off")
    out = tmp_path / "report.json"
    rc = liveness.main(
        [
            "--mode",
            "all",
            "--root",
            str(root),
            "--agents-config",
            str(agents),
            "--registry",
            str(registry),
            "--digests",
            str(digests),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert_report_shape(report)
    assert report["root"] == str(root)
    assert report["allow_inference"] is False
    statuses = {name: rung["status"] for name, rung in report["rungs"].items()}
    assert statuses == {
        "L0": "missing",
        "L1": "ok",
        "L2": "ok",
        "L3": "ok",
        "L4": "skipped",
        "L5": "skipped",
    }
    assert {i["name"] for i in report["rungs"]["L1"]["items"]} == {"mem", "loopmcp"}
    assert {i["status"] for i in report["rungs"]["L2"]["items"]} == {"pinned"}
    assert digests.is_file()
    assert upstream.posts("/v1/chat/completions") == []
    printed = capsys.readouterr().out.strip().splitlines()
    assert printed == [
        "SUCCESS:liveness-all L0=missing L1=ok L2=ok L3=ok L4=skipped L5=skipped "
        f"duration_ms={report['duration_ms']}"
    ]


def test_main_all_prints_json_when_no_out_and_runs_l4_behind_the_flag(
    tmp_path: Path,
    upstream: Upstream,
    critical_config: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, agents, registry, digests = ladder_fixture(
        tmp_path, upstream, critical_config
    )
    monkeypatch.setattr(liveness, "which", lambda _name: None)
    rc = liveness.main_all(
        [
            "--root",
            str(root),
            "--agents-config",
            str(agents),
            "--registry",
            str(registry),
            "--digests",
            str(digests),
            "--allow-inference",
        ]
    )
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1].startswith(
        "SUCCESS:liveness-all L0=missing L1=ok L2=ok L3=ok L4=ok L5=skipped"
    )
    report = json.loads("\n".join(lines[:-1]))
    assert_report_shape(report)
    assert report["allow_inference"] is True
    l4 = {i["endpoint"]: i for i in report["rungs"]["L4"]["items"]}
    assert l4["loop"]["status"] == "ok"
    assert l4["hosted"]["reason"] == "hosted:owner-run"
    assert len(upstream.posts("/v1/chat/completions")) == 1
    assert "ping" not in json.dumps(report)


def test_run_ladder_reports_unreadable_registries_instead_of_raising(
    tmp_path: Path, critical_config: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    critical_config({})
    monkeypatch.setattr(liveness, "which", lambda _name: None)
    report = liveness.run_ladder(
        root=tmp_path,
        agents_config=tmp_path / "absent-agents.json",
        registry_path=tmp_path / "absent-models.json",
        digests_path=tmp_path / "tool-digests.json",
        now=NOW,
    )
    assert_report_shape(report)
    assert report["generated_at"] == NOW
    statuses = {name: rung["status"] for name, rung in report["rungs"].items()}
    assert statuses == {
        "L0": "error",
        "L1": "ok",
        "L2": "ok",
        "L3": "error",
        "L4": "error",
        "L5": "skipped",
    }
    assert report["rungs"]["L1"]["items"] == []
    assert not (tmp_path / "tool-digests.json").exists()


def test_main_all_fails_closed_with_exit_2_on_a_bug(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(**_kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(liveness, "run_ladder", explode)
    assert liveness.main(["--mode", "all"]) == 2
    assert capsys.readouterr().out.strip() == "FAILED:liveness-all RuntimeError: boom"


@pytest.mark.skipif(
    not CAPABILITY_SCORE.is_file(), reason="capability_score.py not checked out"
)
def test_report_is_the_shape_capability_score_consumes(
    tmp_path: Path,
    upstream: Upstream,
    critical_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, agents, registry, digests = ladder_fixture(
        tmp_path, upstream, critical_config
    )
    monkeypatch.setattr(liveness, "which", lambda _name: None)
    report = liveness.run_ladder(
        root=root,
        agents_config=agents,
        registry_path=registry,
        digests_path=digests,
        allow_inference=True,
        now=NOW,
    )
    spec = importlib.util.spec_from_file_location(
        "_capability_score_under_test", CAPABILITY_SCORE
    )
    assert spec is not None and spec.loader is not None
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    rows = {row["id"]: row for row in scorer.rows_from_ladder(report)}
    assert set(rows) == {"mem", "loopmcp", "loop", "oll"}
    assert rows["mem"]["ok"] is True
    assert rows["mem"]["digest"] == "pinned"
    assert rows["mem"]["scan"] == "skipped"
    assert rows["loop"]["observed"] == {"completions": True}
    assert rows["loop"]["claim_agreement"] is True
    assert rows["oll"]["observed"] == {}
