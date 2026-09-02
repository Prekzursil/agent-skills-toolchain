"""Today's two independent process-multiplication probes.

1. PowerShell process-table enumeration (pwsh when present, else /proc twin).
2. Per-session count derived from MCP configuration JSON (stdio servers).

Does not cite 23 x 65 = 2037 as today's number. Reports both readings even
when they disagree. Does not print secrets from command lines.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ceiling import stdio_servers_from_mcp

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PS1 = HERE / "enumerate.ps1"
ESTATE_CITED = {"sessions": 23, "mcp_per_session": 65, "product": 2037}

REDACT = re.compile(r"(?i)(api[_-]?key|token|secret|bearer|sk-)[=: ]\S+")


def redact(raw: str) -> str:
    s = REDACT.sub(r"\1=<redacted>", raw or "")
    return s[:180]


def _which_pwsh() -> str | None:
    for name in ("pwsh", "pwsh.exe", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


def python_proc_enum(limit: int = 8000) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    scanned = 0
    proc = Path("/proc")
    if not proc.is_dir():
        return {
            "engine": "cpython-proc-fallback",
            "scanned": 0,
            "count": 0,
            "hits": [],
            "note": "/proc absent",
        }
    with os.scandir(proc) as it:
        for entry in it:
            if not entry.name.isdigit():
                continue
            scanned += 1
            if scanned > limit:
                break
            cmd_path = Path("/proc") / entry.name / "cmdline"
            try:
                raw = cmd_path.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            except OSError:
                continue
            low = raw.lower()
            if "mcp" in low or "/usr/bin/npx" in low:
                hits.append({"pid": entry.name, "cmd": redact(raw)})
    return {
        "engine": "cpython-proc-fallback",
        "scanned": scanned,
        "count": len(hits),
        "hits": hits[:40],
    }


def powershell_enum() -> dict[str, Any]:
    pwsh = _which_pwsh()
    if not pwsh:
        out = python_proc_enum()
        out["powershell_binary"] = None
        out["powershell_attempted"] = True
        out["note"] = (
            "pwsh/powershell not on PATH; used /proc cmdline walk with the "
            "same mcp|npx heuristic the .ps1 uses."
        )
        return out
    try:
        p = subprocess.run(
            [pwsh, "-NoProfile", "-File", str(PS1)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        out = python_proc_enum()
        out["powershell_binary"] = pwsh
        out["powershell_error"] = type(exc).__name__
        out["note"] = "pwsh invoked but failed; fell back to /proc twin"
        return out
    text = (p.stdout or "").strip()
    if p.returncode != 0 or not text:
        out = python_proc_enum()
        out["powershell_binary"] = pwsh
        out["powershell_exit"] = p.returncode
        out["note"] = "pwsh non-zero or empty JSON; fell back to /proc twin"
        return out
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        out = python_proc_enum()
        out["powershell_binary"] = pwsh
        out["note"] = "pwsh JSON parse failed; fell back to /proc twin"
        return out
    if not isinstance(parsed, dict):
        out = python_proc_enum()
        out["note"] = "pwsh JSON was not an object"
        return out
    hits = parsed.get("hits") or []
    if isinstance(hits, list):
        for row in hits:
            if isinstance(row, dict) and "cmd" in row:
                row["cmd"] = redact(str(row.get("cmd") or ""))
    parsed["powershell_binary"] = pwsh
    parsed["engine"] = parsed.get("engine") or "pwsh"
    parsed["hits"] = hits[:40] if isinstance(hits, list) else []
    return parsed


def live_mcp_config_paths() -> list[Path]:
    home = Path.home()
    return [
        REPO / ".mcp.json",
        REPO / ".cursor" / "mcp.json",
        home / ".cursor" / "mcp.json",
        home / ".config" / "cursor" / "mcp.json",
        home / ".config" / "Cursor" / "User" / "globalStorage" / "cursor.mcp.json",
        home / ".claude.json",
        home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        REPO / ".claude-plugin" / "plugin.json",
    ]


def parse_mcp_file(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "ok": False,
            "error": type(exc).__name__,
            "stdio_ids": [],
        }
    if not isinstance(doc, dict):
        return {"path": str(path), "ok": False, "error": "not-object", "stdio_ids": []}
    servers = doc.get("mcpServers")
    if not isinstance(servers, dict):
        return {
            "path": str(path.as_posix() if path.is_relative_to(REPO) else str(path)),
            "ok": True,
            "has_mcpServers": False,
            "stdio_ids": [],
        }
    names = stdio_servers_from_mcp(doc)
    rel = path.as_posix()
    try:
        rel = path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    return {
        "path": rel,
        "ok": True,
        "has_mcpServers": True,
        "stdio_ids": names,
        "stdio_count": len(names),
        "server_key_count": len(servers),
    }


def mcp_config_derived() -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    ids: list[str] = []
    for path in live_mcp_config_paths():
        if not path.is_file():
            continue
        row = parse_mcp_file(path)
        found.append(row)
        ids.extend(str(x) for x in (row.get("stdio_ids") or []))
    unique = sorted(set(ids))
    per_session = len(unique)
    return {
        "files_present": found,
        "stdio_ids": unique,
        "per_session_count": per_session,
        "derived_for_one_session": per_session,
        "note": (
            "Per-session count is the number of stdio (command, not url) "
            "MCP servers declared in live config files found today. Session "
            "cardinality is not invented; this box has no Windows session table."
        ),
    }


def remeasure_today() -> dict[str, Any]:
    ps = powershell_enum()
    cfg = mcp_config_derived()
    ps_count = int(ps.get("count") or 0)
    cfg_count = int(cfg.get("per_session_count") or 0)
    return {
        "powershell_process_count": ps_count,
        "mcp_config_per_session_count": cfg_count,
        "cited_estate_figure_as_today": False,
        "estate_figure_named_not_used": ESTATE_CITED,
        "agreement": ps_count == cfg_count,
        "disagreement_expected": ps_count != cfg_count,
        "disagreement_reason": (
            None
            if ps_count == cfg_count
            else (
                "Process-table heuristic (mcp|npx in cmdline) is not a parse of "
                "mcpServers; the two probes are required to be independent and "
                "are reported separately rather than combined or picked."
            )
        ),
        "powershell": ps,
        "mcp_config": cfg,
        "combined_process_count_forbidden": True,
    }
