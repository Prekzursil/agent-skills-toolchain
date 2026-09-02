"""Live process-table receipt for spawned MCP servers.

Reads /proc (or a fixture tree with the same layout). Command lines are
redacted; secret-shaped arguments are never copied into the result.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from reader import redact_arg

NEEDLES = ("mcp-server", "@modelcontextprotocol", "mcp_server")
SELF_MARKERS = (
    "p2-wave/probes/AUD-0015",
    "AUD-0015-mcp-scope",
    "_measure_one_delivered.py",
)


def _read_cmdline(proc_pid: Path) -> list[str] | None:
    path = proc_pid / "cmdline"
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw:
        return []
    parts = [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]
    return parts


def _read_comm(proc_pid: Path) -> str:
    path = proc_pid / "comm"
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def looks_like_mcp(parts: list[str], joined: str) -> str | None:
    lower = joined.lower()
    if any(marker.lower() in lower for marker in SELF_MARKERS):
        return None
    for needle in NEEDLES:
        if needle.lower() in lower:
            return needle
    return None


def redact_parts(parts: list[str]) -> list[str]:
    return [str(redact_arg(p)) for p in parts]


def scan_proc(proc_root: Path | None = None) -> dict[str, Any]:
    root = Path(proc_root or "/proc")
    matches: list[dict[str, Any]] = []
    scanned = 0
    unreadable = 0
    if not root.is_dir():
        return {
            "proc_root": str(root),
            "status": "ABSENT",
            "scanned_pids": 0,
            "unreadable": 0,
            "matches": [],
            "names": [],
        }
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.name.isdigit():
            continue
        scanned += 1
        parts = _read_cmdline(entry)
        if parts is None:
            unreadable += 1
            continue
        joined = " ".join(parts)
        needle = looks_like_mcp(parts, joined)
        if not needle:
            continue
        comm = _read_comm(entry)
        matches.append(
            {
                "pid": int(entry.name),
                "comm": comm,
                "needle": needle,
                "argv_redacted": redact_parts(parts)[:12],
            }
        )
    names = sorted(
        {
            (m.get("comm") or "")
            for m in matches
            if m.get("comm")
        }
        | {
            next((a for a in m.get("argv_redacted") or [] if "mcp" in a.lower()), "")
            for m in matches
        }
        - {""}
    )
    return {
        "proc_root": str(root),
        "status": "PRESENT",
        "scanned_pids": scanned,
        "unreadable": unreadable,
        "matches": matches,
        "names": names,
        "match_count": len(matches),
    }


def live_active_names(scan: dict, declared_names: list[str]) -> dict[str, bool]:
    blob = " ".join(
        [" ".join(m.get("argv_redacted") or []) for m in scan.get("matches") or []]
        + [m.get("comm") or "" for m in scan.get("matches") or []]
    ).lower()
    out = {}
    for name in declared_names:
        token = str(name).lower()
        out[name] = bool(token) and token in blob
    return out


def join_declared_and_live(servers: list[dict], scan: dict) -> dict[str, Any]:
    names = [s["name"] for s in servers]
    active = live_active_names(scan, names)
    unmatched_live = []
    blob_declared = {n.lower() for n in names}
    for match in scan.get("matches") or []:
        argv = " ".join(match.get("argv_redacted") or []).lower()
        comm = (match.get("comm") or "").lower()
        if not any(n and (n in argv or n in comm) for n in blob_declared):
            unmatched_live.append(match)
    rows = []
    for rec in servers:
        live = bool(active.get(rec["name"]))
        declared_on = rec.get("effective_enabled")
        split = "undeclared"
        if declared_on is True and live:
            split = "active"
        elif declared_on is True and not live:
            split = "exposed-inactive"
        elif declared_on is False and live:
            split = "disabled-but-running"
        elif declared_on is False and not live:
            split = "disabled"
        elif declared_on is None and live:
            split = "live-undeclared"
        elif declared_on is None and not live:
            split = "inert-unmatched"
        rows.append(
            {
                "name": rec["name"],
                "effective_enabled": declared_on,
                "live_active": live,
                "split": split,
                "winning_surface": rec.get("winning_surface"),
            }
        )
    return {
        "rows": rows,
        "unmatched_live_processes": unmatched_live,
        "disabled_but_running": [r for r in rows if r["split"] == "disabled-but-running"],
        "exposed_inactive": [r for r in rows if r["split"] == "exposed-inactive"],
    }
