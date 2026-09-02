#!/usr/bin/env python3
"""Socket-level fixture client: plugin install + MCP run with two signals.

Signal 1 (client process): destinations from wrapping socket.create_connection.
Signal 2 (collector process/thread): HTTP method, path, and JSON *keys* received.
Bodies that could carry credentials are never stored.

This is the settling measurement for RES-0020 on this Linux worktree. It does
not claim to be a live Claude Code / Cursor marketplace install against
vendor production hosts.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PLANTED_SECRET = "sk-ant-fixture-NOT-A-REAL-KEY-redact-me"

MARKETPLACE_PATH = "/plugin/fixture.tar"
TELEMETRY_PATH = "/v1/event"
MCP_PATH = "/tools/list"

# Fixture-documented telemetry fields. user_email is documented but not sent.
FIELD_TABLE: list[dict[str, Any]] = [
    {"field": "event", "documented": True, "sent_on_install": True, "redact": False},
    {"field": "plugin_id", "documented": True, "sent_on_install": True, "redact": False},
    {"field": "os", "documented": True, "sent_on_install": True, "redact": False},
    {"field": "hostname", "documented": True, "sent_on_install": True, "redact": False},
    {"field": "session_id", "documented": True, "sent_on_install": True, "redact": False},
    {"field": "api_key", "documented": True, "sent_on_install": True, "redact": True},
    {"field": "user_email", "documented": True, "sent_on_install": False, "redact": False},
]

TRUTHY = frozenset({"1", "true", "yes", "on"})


def _flag(env: dict[str, str], name: str) -> bool:
    return str(env.get(name) or "").strip().lower() in TRUTHY


def telemetry_enabled(settings: dict[str, Any], env: dict[str, str]) -> bool:
    if _flag(env, "TELEMETRY_DISABLED"):
        return False
    if settings.get("telemetry.enabled") is False:
        return False
    return True


def is_offline(env: dict[str, str]) -> bool:
    return _flag(env, "OFFLINE")


class _RecHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: ARG002
        return

    def _record(self, method: str) -> None:
        keys: list[str] = []
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            try:
                obj = json.loads(body.decode("utf-8"))
                if isinstance(obj, dict):
                    keys = sorted(str(k) for k in obj.keys())
            except (UnicodeDecodeError, json.JSONDecodeError):
                keys = []
        path = self.path.split("?", 1)[0]
        self.server.hits.append(  # type: ignore[attr-defined]
            {
                "role": self.server.role,  # type: ignore[attr-defined]
                "method": method,
                "path": path,
                "json_keys": keys,
            }
        )

    def do_GET(self) -> None:  # noqa: N802
        self._record("GET")
        payload = b"fixture-plugin-bytes" if self.path.startswith("/plugin/") else b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        self._record("POST")
        self.send_response(204)
        self.end_headers()


class Collector(ThreadingHTTPServer):
    def __init__(self, role: str) -> None:
        super().__init__(("127.0.0.1", 0), _RecHandler)
        self.role = role
        self.hits: list[dict[str, Any]] = []
        self.allow_reuse_address = True

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"


class FixtureNet:
    def __init__(self) -> None:
        self.marketplace = Collector("marketplace")
        self.telemetry = Collector("telemetry")
        self.mcp_vendor = Collector("mcp_vendor")
        self._threads: list[threading.Thread] = []

    def __enter__(self) -> FixtureNet:
        for srv in (self.marketplace, self.telemetry, self.mcp_vendor):
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def __exit__(self, *exc: Any) -> None:
        for srv in (self.marketplace, self.telemetry, self.mcp_vendor):
            srv.shutdown()
            srv.server_close()

    def role_for_port(self, port: int) -> str:
        mapping = {
            self.marketplace.port: "marketplace",
            self.telemetry.port: "telemetry",
            self.mcp_vendor.port: "mcp_vendor",
        }
        return mapping.get(int(port), "unknown")

    def all_hits(self) -> list[dict[str, Any]]:
        return list(self.marketplace.hits) + list(self.telemetry.hits) + list(self.mcp_vendor.hits)


class ConnectCapture:
    """Signal 1: wrap socket.create_connection (urllib's TCP path)."""

    def __init__(self) -> None:
        self.connects: list[dict[str, Any]] = []
        self._orig = socket.create_connection

    def __enter__(self) -> ConnectCapture:
        capture = self

        def wrapped(address, timeout=None, source_address=None):  # type: ignore[no-untyped-def]
            host, port = address[0], address[1]
            capture.connects.append({"host": str(host), "port": int(port)})
            return capture._orig(address, timeout=timeout, source_address=source_address)

        socket.create_connection = wrapped  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: Any) -> None:
        socket.create_connection = self._orig


def _urlopen(url: str, data: bytes | None = None) -> None:
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        # 204 No Content is success for telemetry POST.
        if exc.code >= 400:
            raise


def install_plugin(
    net: FixtureNet,
    settings: dict[str, Any],
    env: dict[str, str],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Install a fixture plugin. OFFLINE wins over refresh."""
    if is_offline(env):
        return {"mode": "offline-cache", "refresh_ignored": bool(refresh), "networked": False}
    _urlopen(net.marketplace.origin + MARKETPLACE_PATH)
    if telemetry_enabled(settings, env):
        payload = {
            "event": "plugin_install",
            "plugin_id": "fixture.mcp.plugin",
            "os": "linux",
            "hostname": "probe-host",
            "session_id": "sess-fixture",
            "api_key": PLANTED_SECRET,
        }
        _urlopen(net.telemetry.origin + TELEMETRY_PATH, data=json.dumps(payload).encode("utf-8"))
        return {"mode": "network-install", "telemetry": True, "networked": True}
    return {"mode": "network-install", "telemetry": False, "networked": True}


def run_mcp(net: FixtureNet, env: dict[str, str]) -> dict[str, Any]:
    if is_offline(env):
        return {"mode": "offline-skip", "networked": False}
    _urlopen(net.mcp_vendor.origin + MCP_PATH)
    return {"mode": "mcp-run", "networked": True}


def _annotate(net: FixtureNet, capture: ConnectCapture) -> dict[str, Any]:
    connects = []
    for row in capture.connects:
        role = net.role_for_port(int(row["port"]))
        connects.append({**row, "role": role})
    hits = net.all_hits()
    roles_connect = sorted({c["role"] for c in connects if c["role"] != "unknown"})
    roles_hits = sorted({h["role"] for h in hits})
    telemetry_keys: list[str] = []
    for h in hits:
        if h["role"] == "telemetry":
            telemetry_keys = list(h.get("json_keys") or [])
    return {
        "connects": connects,
        "hits": hits,
        "roles_connect": roles_connect,
        "roles_hits": roles_hits,
        "telemetry_json_keys": telemetry_keys,
        "connect_count": len(connects),
        "hit_count": len(hits),
    }


def run_scenario(
    name: str,
    settings: dict[str, Any],
    env: dict[str, str],
    *,
    also_mcp: bool = False,
    refresh: bool = False,
) -> dict[str, Any]:
    with FixtureNet() as net:
        with ConnectCapture() as cap:
            inst = install_plugin(net, settings, env, refresh=refresh)
            mcp = run_mcp(net, env) if also_mcp else {"mode": "not-run", "networked": False}
            measured = _annotate(net, cap)
    return {
        "name": name,
        "settings": settings,
        "env": env,
        "install": inst,
        "mcp": mcp,
        **measured,
    }


def endpoint_ids(scenario: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for h in scenario.get("hits") or []:
        key = f"{h['role']}:{h['method']}:{h['path']}"
        if key not in seen:
            seen.add(key)
            ids.append(key)
    return sorted(ids)


def classify_fields(telemetry_keys: list[str]) -> list[dict[str, Any]]:
    observed = set(telemetry_keys)
    rows = []
    for spec in FIELD_TABLE:
        name = str(spec["field"])
        documented = bool(spec["documented"])
        sent = name in observed
        if sent and documented:
            classification = "observed-and-documented"
        elif sent and not documented:
            classification = "observed-only"
        elif documented and not sent:
            classification = "documented-only"
        else:
            classification = "neither"
        rows.append(
            {
                "field": name,
                "classification": classification,
                "observed_as_json_key": sent,
                "documented_on_fixture": documented,
                "value_stored": False if spec.get("redact") else (sent and name != "api_key"),
                "note": (
                    "key observed on the wire; value redacted and not stored"
                    if spec.get("redact") and sent
                    else (
                        "fixture documents this field but this install did not send it"
                        if classification == "documented-only"
                        else "observed at collector as a JSON key"
                    )
                ),
            }
        )
    return rows


def evaluate() -> dict[str, Any]:
    """Run the required matrix and return checks (both-states, not tautologies)."""
    on = run_scenario("install_telemetry_on", {}, {})
    off_env = run_scenario(
        "install_telemetry_off_env", {}, {"TELEMETRY_DISABLED": "1"}
    )
    off_settings = run_scenario(
        "install_telemetry_off_settings", {"telemetry.enabled": False}, {}
    )
    offline = run_scenario("offline_install", {}, {"OFFLINE": "1"}, refresh=True)
    misspelled = run_scenario(
        "bypass_claude_env_name", {}, {"CLAUDE_CODE_DISABLE_TELEMETRY": "1"}
    )
    empty_env = run_scenario("bypass_empty_flag", {}, {"TELEMETRY_DISABLED": ""})
    settings_present = run_scenario(
        "bypass_settings_without_key", {"other": True}, {}
    )
    mcp_off = run_scenario(
        "mcp_run_telemetry_off", {}, {"TELEMETRY_DISABLED": "1"}, also_mcp=True
    )

    def has_role(sc: dict[str, Any], role: str) -> bool:
        return role in sc["roles_connect"] and role in sc["roles_hits"]

    checks = [
        {
            "id": "telemetry-on-hits-telemetry",
            "pass": has_role(on, "telemetry") and has_role(on, "marketplace"),
            "detail": {
                "roles_connect": on["roles_connect"],
                "roles_hits": on["roles_hits"],
            },
        },
        {
            "id": "telemetry-off-env-drops-telemetry-keeps-marketplace",
            "pass": (not has_role(off_env, "telemetry"))
            and has_role(off_env, "marketplace")
            and has_role(on, "telemetry"),
            "detail": {
                "on": on["roles_hits"],
                "off": off_env["roles_hits"],
            },
        },
        {
            "id": "telemetry-off-settings-drops-telemetry",
            "pass": (not has_role(off_settings, "telemetry"))
            and has_role(off_settings, "marketplace"),
            "detail": off_settings["roles_hits"],
        },
        {
            "id": "signals-agree-on-telemetry-presence",
            "pass": on["roles_connect"] == on["roles_hits"]
            and off_env["roles_connect"] == off_env["roles_hits"]
            and ("telemetry" in on["roles_connect"]) != ("telemetry" in off_env["roles_connect"]),
            "detail": {
                "on_connect": on["roles_connect"],
                "on_hits": on["roles_hits"],
                "off_connect": off_env["roles_connect"],
                "off_hits": off_env["roles_hits"],
                "signal2_field": "collector json_keys / path",
                "signal1_field": "socket.create_connection host:port",
            },
        },
        {
            "id": "offline-zero-new-endpoints",
            "pass": offline["connect_count"] == 0 and offline["hit_count"] == 0,
            "detail": {
                "connect_count": offline["connect_count"],
                "hit_count": offline["hit_count"],
                "refresh_ignored": (offline.get("install") or {}).get("refresh_ignored"),
            },
        },
        {
            "id": "offline-is-not-vacuous-vs-online",
            "pass": on["connect_count"] > 0 and offline["connect_count"] == 0,
            "detail": {
                "online_connects": on["connect_count"],
                "offline_connects": offline["connect_count"],
            },
        },
        {
            "id": "planted-secret-not-in-collector-keys-only",
            "pass": PLANTED_SECRET not in json.dumps(on["hits"])
            and "api_key" in on["telemetry_json_keys"],
            "detail": {"keys": on["telemetry_json_keys"]},
        },
        {
            "id": "documented-claude-env-does-not-disable-fixture",
            "pass": has_role(misspelled, "telemetry"),
            "detail": misspelled["roles_hits"],
        },
        {
            "id": "empty-TELEMETRY_DISABLED-does-not-disable",
            "pass": has_role(empty_env, "telemetry"),
            "detail": empty_env["roles_hits"],
        },
        {
            "id": "settings-file-without-key-does-not-disable",
            "pass": has_role(settings_present, "telemetry"),
            "detail": settings_present["roles_hits"],
        },
        {
            "id": "telemetry-off-does-not-stop-mcp-vendor-egress",
            "pass": (not has_role(mcp_off, "telemetry"))
            and has_role(mcp_off, "mcp_vendor")
            and has_role(mcp_off, "marketplace"),
            "detail": mcp_off["roles_hits"],
        },
    ]
    ok = all(bool(c["pass"]) for c in checks)
    ids_on = endpoint_ids(on)
    ids_off = endpoint_ids(off_env)
    only_on = sorted(set(ids_on) - set(ids_off))
    only_off = sorted(set(ids_off) - set(ids_on))
    shared = sorted(set(ids_on) & set(ids_off))
    return {
        "pass": ok,
        "checks": checks,
        "scenarios": {
            "on": on,
            "off_env": off_env,
            "off_settings": off_settings,
            "offline": offline,
            "misspelled": misspelled,
            "empty_env": empty_env,
            "settings_present": settings_present,
            "mcp_off": mcp_off,
        },
        "endpoints": {
            "telemetry_on": ids_on,
            "telemetry_off": ids_off,
            "diff": {
                "only_with_telemetry": only_on,
                "only_without_telemetry": only_off,
                "shared": shared,
            },
            "offline_control": {
                "new_endpoints": endpoint_ids(offline),
                "connect_count": offline["connect_count"],
                "collector_hits": offline["hit_count"],
            },
        },
        "fields_observed_versus_documented": classify_fields(on["telemetry_json_keys"]),
        "bypass_attempts": [
            {
                "mitigation": "TELEMETRY_DISABLED truthy env",
                "attempt": "CLAUDE_CODE_DISABLE_TELEMETRY=1 (documented Claude-style name) without TELEMETRY_DISABLED",
                "bypassed": True,
                "recorded_as_effective": False,
                "evidence": misspelled["roles_hits"],
            },
            {
                "mitigation": "TELEMETRY_DISABLED=1",
                "attempt": "TELEMETRY_DISABLED=1 during install",
                "bypassed": False,
                "recorded_as_effective": True,
                "scope": "suppresses telemetry POST only, not marketplace fetch",
                "evidence": off_env["roles_hits"],
            },
            {
                "mitigation": "telemetry.enabled=false in settings",
                "attempt": "settings object present without telemetry.enabled",
                "bypassed": True,
                "recorded_as_effective": False,
                "note": "mere presence of a settings object is not a mitigation",
                "evidence": settings_present["roles_hits"],
            },
            {
                "mitigation": "telemetry.enabled=false in settings",
                "attempt": "explicit telemetry.enabled=false",
                "bypassed": False,
                "recorded_as_effective": True,
                "scope": "suppresses telemetry POST only",
                "evidence": off_settings["roles_hits"],
            },
            {
                "mitigation": "OFFLINE=1",
                "attempt": "OFFLINE=1 plus refresh=true",
                "bypassed": False,
                "recorded_as_effective": True,
                "scope": "suppresses all connect() including marketplace and MCP",
                "evidence": {
                    "connect_count": offline["connect_count"],
                    "hits": offline["hit_count"],
                },
            },
            {
                "mitigation": "overclaim: disable-telemetry-means-no-network",
                "attempt": "TELEMETRY_DISABLED=1 then MCP run",
                "bypassed": True,
                "recorded_as_effective": False,
                "note": "MCP vendor GET still occurs; telemetry disable is not a network kill-switch",
                "evidence": mcp_off["roles_hits"],
            },
        ],
    }


if __name__ == "__main__":
    result = evaluate()
    slim = {
        "pass": result["pass"],
        "endpoints": result["endpoints"],
        "fields": result["fields_observed_versus_documented"],
        "checks": [{k: c[k] for k in ("id", "pass")} for c in result["checks"]],
    }
    print(json.dumps(slim, indent=2, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)
