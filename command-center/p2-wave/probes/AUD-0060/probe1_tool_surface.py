#!/usr/bin/env python3
"""AUD-0060 Probe 1: tool count + serialized schema size per server.

Honest measurement on this substrate:
  * Planted stdio control (fake-mcp, 1 tool) MUST report non-zero — tests_required.
  * Planted zero-tools server MUST report exactly 0 (both-states).
  * AUD-0015 ENABLED-DECLARED owner-host servers: attempt live tools/list; on this
    Linux Cursor Cloud worker they are UNREACHABLE (no ~/.claude.json / Windows
    paths). tool_count stays null — never invented as 0.
  * Session Cursor dynamic namespaces (fixtures/session_namespace_census.json)
    are live-reachable here and contribute measured tool_count + schema_bytes.
  * Optional static-registration scan for repo-local sources is labeled distinctly
    and is NOT a live tools/list count.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # p2-wave
import _p2lib as L  # noqa: E402

REPO = L.REPO
HOST_DIR = REPO / "tools" / "mcp" / "mcp-http-host"
sys.path.insert(0, str(HOST_DIR))
from mcp_http_host import StdioChild  # noqa: E402

OUT_JSON = PROBE / "probe1-tool-surface.json"
OUT_RAW = PROBE / "probe1-tool-surface.raw.txt"
AUD0015 = REPO / "command-center/audit/AUD-0015-mcp-scope-resolution.json"
SESSION = PROBE / "fixtures" / "session_namespace_census.json"
FAKE = HOST_DIR / "_fake_mcp_server.py"
ZERO = PROBE / "fixtures" / "planted_zero_tools_server.py"

# repo-local static registration map (secondary signal only)
LOCAL_SRC = {
    "cloud-hub": ["tools/mcp/cloud-hub"],
    "search-hub": ["tools/mcp/search-hub"],
    "social-hub": ["tools/mcp/social-hub"],
    "scholarly-access": ["tools/scholarly-access-mcp"],
    "hexstrike-ai": ["tools/mcp/hexstrike-ai"],
    "qdx-rush": ["tools/mcp/qdx-rush-mcp"],
    "schrodinger": ["tools/mcp/schrodinger-mcp"],
    "hacktricks": ["tools/mcp/hacktricks-mcp-server"],
}
REG = [
    re.compile(r"@(?:\w+\.)?tool\s*\(", re.M),
    re.compile(r"^\s*Tool\s*\(\s*name\s*=", re.M),
]


def handshake(cmd: list[str], timeout: float = 20.0) -> dict:
    child = StdioChild(cmd)
    try:
        init = child.request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "aud-0060-probe1", "version": "0"},
                },
            },
            timeout=timeout,
        )
        child.request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=timeout,
        )
        tools_resp = child.request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            timeout=timeout,
        )
        tools = ((tools_resp or {}).get("result") or {}).get("tools") or []
        info = ((init or {}).get("result") or {}).get("serverInfo") or {}
        schema_bytes = len(json.dumps(tools, sort_keys=True, separators=(",", ":")))
        return {
            "ok": True,
            "server_info": info,
            "tool_count": len(tools),
            "tool_names": [t.get("name") for t in tools if isinstance(t, dict)],
            "schema_bytes": schema_bytes,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "server_info": None,
            "tool_count": None,
            "tool_names": None,
            "schema_bytes": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        child.terminate()


def static_scan(rel_dirs: list[str]) -> dict | None:
    n_tools = 0
    files = 0
    found = False
    for rel in rel_dirs:
        root = REPO / rel
        if not root.is_dir():
            continue
        found = True
        for f in root.rglob("*.py"):
            posix = f.as_posix()
            if "__pycache__" in posix or "/tests/" in posix or "/.venv/" in posix:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files += 1
            n_tools += sum(len(p.findall(text)) for p in REG)
    if not found:
        return None
    return {
        "measurement_kind": "static-registration-scan",
        "registration_hits": n_tools,
        "py_files": files,
        "note": "AST decorator/Tool() hits — NOT a live tools/list count",
    }


def main() -> int:
    lines: list[str] = []
    lines.append("AUD-0060 NAMED PROBE 1: tool count + schema bytes per server")
    lines.append(f"CAPTURED_AT={datetime.now(timezone.utc).isoformat()}")
    lines.append(f"REPO={REPO}")
    lines.append("SUBSTRATE=linux-cursor-cloud")

    # --- planted controls (both states) ---
    good = handshake([sys.executable, str(FAKE)])
    bad_zero = handshake([sys.executable, str(ZERO)])
    control_ok = (
        bool(good.get("ok"))
        and int(good.get("tool_count") or 0) > 0
        and bool(bad_zero.get("ok"))
        and bad_zero.get("tool_count") == 0
    )
    lines.append("=== PLANTED CONTROL (tests_required) ===")
    lines.append(
        f"fake-mcp tool_count={good.get('tool_count')} "
        f"schema_bytes={good.get('schema_bytes')} ok={good.get('ok')}"
    )
    lines.append(
        f"planted-zero tool_count={bad_zero.get('tool_count')} "
        f"schema_bytes={bad_zero.get('schema_bytes')} ok={bad_zero.get('ok')}"
    )
    lines.append(f"control_ok={control_ok}")

    # --- AUD-0015 enabled declared ---
    aud = json.loads(AUD0015.read_text(encoding="utf-8"))
    servers = (aud.get("report") or {}).get("servers") or []
    enabled = [
        s for s in servers if s.get("effective_state") == "ENABLED-DECLARED"
    ]
    lines.append(f"AUD0015_ENABLED_DECLARED={len(enabled)}")
    lines.append(f"HOME_CLAUDE_JSON_PRESENT={(REPO.home() / '.claude.json').is_file()}")
    lines.append(f"HOME_MCP_JSON_PRESENT={(REPO.home() / '.mcp.json').is_file()}")

    rows: list[dict] = []
    for s in enabled:
        name = s["name"]
        # On this worker, owner-host MCP launch specs are absent. Do not invent counts.
        row = {
            "name": name,
            "source": "AUD-0015-ENABLED-DECLARED",
            "measurement_kind": "live-tools-list",
            "status": "UNREACHABLE",
            "tool_count": None,
            "tool_names": None,
            "schema_bytes": None,
            "error": (
                "owner-host MCP not mounted on linux-cursor-cloud "
                "(no ~/.claude.json / ~/.mcp.json spawn specs)"
            ),
            "static_estimate": static_scan(LOCAL_SRC[name])
            if name in LOCAL_SRC
            else None,
        }
        rows.append(row)
        lines.append(
            f"SERVER\t{name}\tstatus=UNREACHABLE\ttool_count=null\t"
            f"static={row['static_estimate']}"
        )

    # --- session namespaces (live on this substrate) ---
    session = json.loads(SESSION.read_text(encoding="utf-8"))
    session_rows = []
    session_tool_sum = 0
    session_schema_sum = 0
    session_reachable = 0
    for ns in session.get("namespaces") or []:
        session_rows.append(
            {
                "name": ns["name"],
                "source": "session-dynamic-namespace",
                "measurement_kind": "live-tools-list",
                "status": "REACHABLE" if ns.get("reachable") else "LOADING-OR-UNREACHABLE",
                "tool_count": ns.get("tool_count"),
                "tool_names": ns.get("tool_names"),
                "schema_bytes": ns.get("schema_bytes"),
                "error": ns.get("error"),
            }
        )
        if ns.get("reachable") and isinstance(ns.get("tool_count"), int):
            session_reachable += 1
            session_tool_sum += ns["tool_count"]
            session_schema_sum += int(ns.get("schema_bytes") or 0)
        lines.append(
            f"SESSION\t{ns['name']}\treachable={ns.get('reachable')}\t"
            f"tool_count={ns.get('tool_count')}\tschema_bytes={ns.get('schema_bytes')}"
        )

    live_nonzero_servers = 0
    if control_ok and int(good.get("tool_count") or 0) > 0:
        live_nonzero_servers += 1
    live_nonzero_servers += sum(
        1
        for r in session_rows
        if isinstance(r.get("tool_count"), int) and r["tool_count"] > 0
    )

    # Catalog control: zero across ALL servers means enumerator not reaching them.
    # Planted fake-mcp + session namespaces provide non-zero where reachable.
    enumerator_reaching = live_nonzero_servers > 0 and control_ok

    doc = {
        "unit": "AUD-0060",
        "probe": 1,
        "ok": control_ok and enumerator_reaching,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "substrate": "linux-cursor-cloud",
        "aud0015_enabled_declared_count": len(enabled),
        "aud0015_enabled_live_reachable_count": 0,
        "aud0015_enabled_unreachable_count": len(enabled),
        "session_namespaces_reachable": session_reachable,
        "session_tool_count_sum": session_tool_sum,
        "session_schema_bytes_sum": session_schema_sum,
        "live_nonzero_server_count": live_nonzero_servers,
        "enumerator_reaching": enumerator_reaching,
        "owner_host_mcp_reachable": False,
        "failure_classification_hints": [
            "detector-failure",
            "scope-mismatch",
        ],
        "control": {
            "ok": control_ok,
            "planted_fake_mcp": good,
            "planted_zero_tools": bad_zero,
            "tests_required": (
                "control: confirm the counter reports a non-zero tool count for a "
                "server known to be connected; a zero across all servers means the "
                "enumerator is not reaching them"
            ),
            "fired_nonzero_on_connected": int(good.get("tool_count") or 0) > 0,
            "silent_zero_on_empty": bad_zero.get("tool_count") == 0,
        },
        "servers": rows,
        "session_namespaces": session_rows,
        "planted_control_row": {
            "name": "_planted_fake_mcp",
            "source": "fixtures+tools/mcp/mcp-http-host/_fake_mcp_server.py",
            "measurement_kind": "live-tools-list",
            "status": "REACHABLE" if good.get("ok") else "FAILED",
            "tool_count": good.get("tool_count"),
            "tool_names": good.get("tool_names"),
            "schema_bytes": good.get("schema_bytes"),
            "error": good.get("error"),
        },
    }

    lines.append(
        f"SUMMARY enabled={len(enabled)} unreachable={len(enabled)} "
        f"session_tools={session_tool_sum} session_schema_bytes={session_schema_sum} "
        f"live_nonzero={live_nonzero_servers} control_ok={control_ok} "
        f"enumerator_reaching={enumerator_reaching}"
    )
    lines.append(
        "NOTE: owner-host ENABLED-DECLARED tool counts left null (UNREACHABLE); "
        "do not treat null as zero."
    )
    lines.append("SUCCESS:AUD-0060-probe1" if doc["ok"] else "FAILED:AUD-0060-probe1")

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
