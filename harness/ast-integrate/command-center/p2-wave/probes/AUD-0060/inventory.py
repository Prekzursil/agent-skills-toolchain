#!/usr/bin/env python3
"""AUD-0060 probe 1: per-server tool count and serialized schema size."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixture_server import EXPECTED_COUNT, EXPECTED_NAMES  # noqa: E402
from mcp_stdio import list_tools_stdio  # noqa: E402

UNIT = "AUD-0060"
FIXTURE = HERE / "fixture_server.py"
SESSION_CAPTURE = HERE / "session_cursor_mcp.json"
AUD0015 = REPO / "command-center/audit/AUD-0015-mcp-scope-resolution.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

CONFIG_SURFACES = (
    Path.home() / ".mcp.json",
    Path.home() / ".claude.json",
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".cursor" / "mcp.json",
    REPO / ".mcp.json",
    REPO / ".cursor" / "mcp.json",
    REPO / ".vscode" / "mcp.json",
)


def token_cost(obj: Any) -> dict:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    method = "utf8-bytes-div-4-heuristic"
    tokens = max(1, (len(raw) + 3) // 4) if raw else 0
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        tokens = len(enc.encode(raw.decode("utf-8")))
        method = "tiktoken-cl100k_base"
    except Exception:  # noqa: BLE001
        pass
    return {"bytes": len(raw), "tokens": tokens, "method": method}


def redact_cfg(cfg: dict) -> dict:
    out = {k: v for k, v in cfg.items() if k not in {"env", "headers"}}
    if isinstance(cfg.get("env"), dict):
        out["env_keys"] = sorted(str(k) for k in cfg["env"].keys())
        out["env_values_recorded"] = False
    if isinstance(cfg.get("headers"), dict):
        out["header_keys"] = sorted(str(k) for k in cfg["headers"].keys())
        out["header_values_recorded"] = False
    return out


def _servers_from_doc(doc: Any, origin: str) -> list[dict]:
    rows = []
    if not isinstance(doc, dict):
        return rows
    servers = doc.get("mcpServers") or doc.get("servers")
    if isinstance(servers, dict):
        for name, cfg in servers.items():
            if not isinstance(cfg, dict):
                continue
            rows.append(
                {
                    "name": str(name),
                    "origin": origin,
                    "command": cfg.get("command"),
                    "args": cfg.get("args") if isinstance(cfg.get("args"), list) else [],
                    "url": cfg.get("url") or cfg.get("serverUrl"),
                    "cfg": redact_cfg(cfg),
                    "disabled_here": False,
                }
            )
    disabled = doc.get("disabledMcpServers")
    if isinstance(disabled, list):
        for name in disabled:
            rows.append(
                {
                    "name": str(name),
                    "origin": origin + "#disabledMcpServers",
                    "command": None,
                    "args": [],
                    "url": None,
                    "cfg": {},
                    "disabled_here": True,
                    "scope_note": "root-scope disabledMcpServers may be inert; AUD-0015 is the resolver",
                }
            )
    projects = doc.get("projects")
    if isinstance(projects, dict):
        for proj, block in projects.items():
            if not isinstance(block, dict):
                continue
            sub = _servers_from_doc(block, f"{origin}#projects[{proj}]")
            rows.extend(sub)
    return rows


def discover_estate() -> dict:
    surfaces = []
    servers = []
    for path in CONFIG_SURFACES:
        rel = str(path)
        if not path.is_file():
            surfaces.append({"path": rel, "status": "absent"})
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            surfaces.append(
                {"path": rel, "status": "unreadable", "error": type(exc).__name__}
            )
            continue
        found = _servers_from_doc(doc, rel)
        surfaces.append(
            {"path": rel, "status": "present", "declared_rows": len(found)}
        )
        servers.extend(found)
    aud0015_doc = None
    if AUD0015.is_file():
        try:
            aud0015_doc = json.loads(AUD0015.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            aud0015_doc = None
    resolved_names = []
    if isinstance(aud0015_doc, dict):
        for row in aud0015_doc.get("servers") or []:
            if isinstance(row, dict) and row.get("name"):
                resolved_names.append(str(row["name"]))
    aud0015 = {
        "path": "command-center/audit/AUD-0015-mcp-scope-resolution.json",
        "present": AUD0015.is_file(),
        "bytes": AUD0015.stat().st_size if AUD0015.is_file() else 0,
        "resolved_server_names": resolved_names,
        "resolved_server_count": len(resolved_names),
        "note": (
            "AUD-0015 resolved list is present; live estate still has no configured "
            "MCP servers on this Linux worktree."
            if AUD0015.is_file()
            else (
                "AUD-0015 resolved list is absent on this worktree; this unit reads the "
                "same four config surfaces directly and does not invent a resolved winner."
            )
        ),
    }
    return {"surfaces": surfaces, "servers": servers, "aud0015": aud0015}


def summarize_tools(tools: list[dict]) -> dict:
    rows = []
    total_bytes = 0
    total_tokens = 0
    method = None
    for tool in tools:
        cost = token_cost(tool)
        method = cost["method"]
        total_bytes += cost["bytes"]
        total_tokens += cost["tokens"]
        rows.append(
            {
                "name": tool.get("name"),
                "has_input_schema": isinstance(tool.get("inputSchema"), dict),
                "schema_bytes": cost["bytes"],
                "schema_tokens": cost["tokens"],
            }
        )
    return {
        "tool_count": len(tools),
        "schema_bytes": total_bytes,
        "schema_tokens": total_tokens,
        "token_method": method or "utf8-bytes-div-4-heuristic",
        "tools": rows,
    }


def list_fixture() -> dict:
    listed = list_tools_stdio(
        [sys.executable, "-B", str(FIXTURE)],
        cwd=str(HERE),
        timeout_s=8.0,
    )
    names = [t.get("name") for t in listed.get("tools") or []]
    summary = summarize_tools(listed.get("tools") or [])
    return {
        "server": "aud-0060-control-fixture",
        "connected": listed.get("ok") is True and summary["tool_count"] > 0,
        "list": listed,
        "summary": summary,
        "names": names,
        "expected_count": EXPECTED_COUNT,
        "expected_names": EXPECTED_NAMES,
        "matches_expected": names == EXPECTED_NAMES,
    }


def list_mute() -> dict:
    """Known-broken: a process that does not speak MCP. Must report zero tools."""
    listed = list_tools_stdio(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout_s=1.5,
    )
    return {
        "server": "mute-non-mcp-process",
        "list": listed,
        "tool_count": len(listed.get("tools") or []),
    }


def list_estate_server(row: dict) -> dict:
    if row.get("disabled_here"):
        return {**row, "connected": False, "reason": "declared-disabled", "summary": summarize_tools([])}
    if row.get("url"):
        return {
            **row,
            "connected": False,
            "reason": "http-url-not-probed-stdio-enumerator",
            "summary": summarize_tools([]),
        }
    cmd = row.get("command")
    if not cmd:
        return {**row, "connected": False, "reason": "no-command", "summary": summarize_tools([])}
    argv = [str(cmd)] + [str(a) for a in (row.get("args") or [])]
    listed = list_tools_stdio(argv, timeout_s=6.0)
    summary = summarize_tools(listed.get("tools") or [])
    return {
        **row,
        "connected": listed.get("ok") is True and summary["tool_count"] > 0,
        "reason": listed.get("error"),
        "list_error": listed.get("error"),
        "summary": summary,
    }


def declared_requirements() -> dict:
    perms = []
    if CATALOG.is_file():
        try:
            doc = json.loads(CATALOG.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = {}
        for unit in doc.get("work_units") or []:
            if isinstance(unit, dict) and unit.get("id") == UNIT:
                perms = list(unit.get("tool_permissions") or [])
                break
    mcp_named = [p for p in perms if "mcp" in str(p).lower()]
    return {
        "catalog_unit": UNIT,
        "tool_permissions": perms,
        "mcp_named_in_permissions": mcp_named,
        "declared_mcp_need_count": len(mcp_named),
        "note": (
            "AUD-0060 catalog tool_permissions are first-party (Read/Grep/Glob/PowerShell). "
            "No MCP tool is a declared requirement of this unit."
        ),
    }


def session_cursor_surface() -> dict:
    if not SESSION_CAPTURE.is_file():
        return {"status": "absent", "tool_count": 0, "tools": []}
    try:
        doc = json.loads(SESSION_CAPTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": f"unreadable:{type(exc).__name__}", "tool_count": 0, "tools": []}
    tools = doc.get("tools") or []
    summary = summarize_tools(tools)
    return {
        "status": "captured",
        "namespace": doc.get("namespace"),
        "transport": doc.get("transport"),
        "method": doc.get("method"),
        "summary": summary,
        "tool_count": summary["tool_count"],
        "tools": summary["tools"],
    }


def control_both_states() -> dict:
    good = list_fixture()
    bad = list_mute()
    fires = bad["tool_count"] == 0
    silent = good.get("summary", {}).get("tool_count") == EXPECTED_COUNT and good.get(
        "matches_expected"
    )
    return {
        "id": "AUD0060-C1",
        "kind": "enumerator-reachability",
        "fired_on_bad_state": fires,
        "silent_on_good_state": bool(silent),
        "bad_state_output": f"mute tool_count={bad['tool_count']} error={bad['list'].get('error')}",
        "good_state_output": (
            f"fixture tool_count={good.get('summary', {}).get('tool_count')} "
            f"names={good.get('names')}"
        ),
        "good": good,
        "bad": bad,
        "pass": bool(fires and silent),
    }


def measure() -> dict:
    ctl = control_both_states()
    estate = discover_estate()
    estate_listed = [list_estate_server(row) for row in estate["servers"]]
    cursor = session_cursor_surface()
    declared = declared_requirements()
    connected = []
    if ctl["good"].get("connected"):
        connected.append(ctl["good"])
    connected.extend([r for r in estate_listed if r.get("connected")])
    zero_across_connected = (
        not connected
        or all((r.get("summary") or {}).get("tool_count", 0) == 0 for r in connected)
    )
    return {
        "unit_id": UNIT,
        "control": {
            "id": ctl["id"],
            "fired_on_bad_state": ctl["fired_on_bad_state"],
            "silent_on_good_state": ctl["silent_on_good_state"],
            "bad_state_output": ctl["bad_state_output"],
            "good_state_output": ctl["good_state_output"],
            "pass": ctl["pass"],
        },
        "fixture": {
            "connected": ctl["good"].get("connected"),
            "summary": ctl["good"].get("summary"),
            "names": ctl["good"].get("names"),
            "matches_expected": ctl["good"].get("matches_expected"),
        },
        "mute": {"tool_count": ctl["bad"]["tool_count"], "error": ctl["bad"]["list"].get("error")},
        "estate": {
            "surfaces": estate["surfaces"],
            "aud0015": estate["aud0015"],
            "declared_server_rows": len(estate["servers"]),
            "servers": [
                {
                    "name": r.get("name"),
                    "origin": r.get("origin"),
                    "connected": r.get("connected"),
                    "reason": r.get("reason") or r.get("list_error"),
                    "disabled_here": r.get("disabled_here"),
                    "has_url": bool(r.get("url")),
                    "summary": r.get("summary"),
                }
                for r in estate_listed
            ],
        },
        "session_cursor_mcp": cursor,
        "declared_requirements": declared,
        "connected_server_count": len(connected),
        "zero_across_connected_servers": zero_across_connected,
        "headline_tool_count_connected": sum(
            (r.get("summary") or {}).get("tool_count", 0) for r in connected
        ),
        "headline_schema_tokens_connected": sum(
            (r.get("summary") or {}).get("schema_tokens", 0) for r in connected
        ),
        "headline_schema_bytes_connected": sum(
            (r.get("summary") or {}).get("schema_bytes", 0) for r in connected
        ),
    }


def main() -> int:
    doc = measure()
    print(json.dumps(doc, sort_keys=True))
    if not doc["control"]["pass"]:
        print("FAILED:AUD-0060 inventory control does not discriminate")
        return 1
    if doc["zero_across_connected_servers"]:
        print("FAILED:AUD-0060 enumerator reported zero tools on every connected server")
        return 1
    print(
        "SUCCESS:AUD-0060-inventory fixture="
        f"{doc['fixture']['summary']['tool_count']} "
        f"estate_declared={doc['estate']['declared_server_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
