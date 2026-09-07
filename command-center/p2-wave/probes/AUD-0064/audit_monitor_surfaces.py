#!/usr/bin/env python3
"""AUD-0064 Probe 1 + Probe 2: monitor dispatcher inventory and route reachability.

Probe 1: fail-closed tomllib parse of the four monitors.toml locations that
matter (repo-export, repo-agents, live-home, live-claude) plus entry-script
resolution under the matching skills root.

Probe 2: launch each export route once (twice for clock-stripped change
detection). LIVE requires nonempty render bytes and two distinct digests after
volatile clock text is stripped. Tracebacks / import failures are EMPTY, not
renders. Stall detection from mtimes alone is banned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# .../command-center/p2-wave/probes/AUD-0064/<this> → parents[4] = repo root
REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
UNIT = "AUD-0064"

TABLES = (
    ("repo-export", REPO / "skills/monitor-launcher/monitors.toml", REPO / "skills"),
    (
        "repo-agents",
        REPO / ".agents/skills/monitor-launcher/monitors.toml",
        REPO / ".agents/skills",
    ),
    (
        "live-home",
        Path.home() / ".agents/skills/monitor-launcher/monitors.toml",
        Path.home() / ".agents/skills",
    ),
    (
        "live-claude",
        Path.home() / ".claude/skills/monitor-launcher/monitors.toml",
        Path.home() / ".claude/skills",
    ),
)

# One-shot argv per export route. Prefer --once / --list when the entry supports
# a non-interactive frame; otherwise launch bare and let the classifier treat
# Traceback / FileNotFound as EMPTY.
ROUTE_ARGS: dict[str, list[str]] = {
    "agentmon": ["--list"],
    "cockpit": ["--once"],
    "codexmon": ["--once"],
    "crcp": [],
    "csmon": ["--once", "--deadline", "3"],
    "p2r2e": [],
    "wfmon": ["--once"],
}

CLOCK_RE = re.compile(
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b|"
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b|"
    r"\b\d+s\s+ago\b|"
    r"\bage=[^\s]+|"
    r"\blast activity \d+s ago\b",
    re.IGNORECASE,
)

ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError:",
    "FileNotFoundError:",
    "ImportError:",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_clock(text: str) -> str:
    return CLOCK_RE.sub("<t>", text)


def digest(text: str) -> str:
    return hashlib.sha256(strip_clock(text).encode("utf-8", errors="replace")).hexdigest()


def write_json(path: Path, doc: Any) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_raw(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def parse_table(label: str, path: Path, skills_root: Path) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "skills_root": str(skills_root),
        "status": "ABSENT",
        "routes": 0,
        "names": [],
        "entries": [],
        "parse_error": None,
    }
    if not path.is_file():
        return row
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — fail-closed inventory
        row["status"] = "PARSE-ERROR"
        row["parse_error"] = f"{type(exc).__name__}: {exc}"
        return row
    names = sorted(data.keys())
    entries = []
    for name in names:
        spec = data[name] or {}
        directory = str(spec.get("dir") or "")
        entry = str(spec.get("entry") or "")
        abs_entry = skills_root / directory / entry if directory and entry else None
        entries.append(
            {
                "name": name,
                "dir": directory,
                "entry": entry,
                "trigger_tool": spec.get("trigger_tool"),
                "autolaunch": spec.get("autolaunch", "open"),
                "entry_path": str(abs_entry) if abs_entry else None,
                "entry_exists": bool(abs_entry and abs_entry.is_file()),
            }
        )
    row.update(
        {
            "status": "PRESENT",
            "routes": len(names),
            "names": names,
            "entries": entries,
        }
    )
    return row


def run_probe1(raw_path: Path, json_path: Path) -> dict[str, Any]:
    lines: list[str] = [
        "Probe 1: the dispatcher routing table enumerated statically.",
        "method=fail-closed tomllib parse of live and repo monitors.toml plus entry presence",
        "scope_rule=repo-export is the catalog table; live-home is authoritative when present",
        "mtime_stall_used=false",
    ]
    tables = [parse_table(label, path, root) for label, path, root in TABLES]
    for t in tables:
        names = ",".join(t["names"])
        lines.append(
            f"CURRENT_TABLE|label={t['label']}|path={t['path']}|"
            f"status={t['status']}|routes={t['routes']}|names={names}"
        )
        for e in t["entries"]:
            lines.append(
                f"ROUTE|table={t['label']}|name={e['name']}|dir={e['dir']}|"
                f"entry={e['entry']}|trigger_tool={e['trigger_tool']}|"
                f"autolaunch={e['autolaunch']}|entry_exists={e['entry_exists']}|"
                f"entry_path={e['entry_path']}"
            )

    mon = shutil.which("mon")
    pwsh = shutil.which("pwsh")
    mon_cmd = REPO / "skills/monitor-launcher/mon.cmd"
    lines.append(f"CURRENT_DISPATCHER|command=mon|resolved={'PRESENT' if mon else 'ABSENT'}")
    lines.append(f"RUNTIME|pwsh={'PRESENT' if pwsh else 'ABSENT'}")
    lines.append(f"RUNTIME|python={sys.executable}")
    lines.append(f"RUNTIME|mon_cmd_in_repo={mon_cmd.is_file()}")

    present = [t for t in tables if t["status"] == "PRESENT"]
    export = next(t for t in tables if t["label"] == "repo-export")
    agents = next(t for t in tables if t["label"] == "repo-agents")
    live_home = next(t for t in tables if t["label"] == "live-home")
    live_claude = next(t for t in tables if t["label"] == "live-claude")

    result = {
        "unit_id": UNIT,
        "probe": "probe1",
        "measured_at": utc_now(),
        "mtime_stall_used": False,
        "tables": tables,
        "current_table_count": len(present),
        "repo_export_status": export["status"],
        "repo_agents_status": agents["status"],
        "live_home_status": live_home["status"],
        "live_claude_status": live_claude["status"],
        "route_count_export": export["routes"],
        "export_route_names": list(export["names"]),
        "route_count_live_home": live_home["routes"],
        "live_home_route_names": list(live_home["names"]),
        "mon_on_path": bool(mon),
        "mon_cmd_in_repo": mon_cmd.is_file(),
        "pwsh": "PRESENT" if pwsh else "ABSENT",
        "python": sys.executable,
        "all_export_entry_scripts_resolved": bool(export["entries"])
        and all(e["entry_exists"] for e in export["entries"]),
    }
    lines.append(f"route_count_live={result['route_count_live_home']}")
    lines.append(f"route_count_export={result['route_count_export']}")
    lines.append(f"current_table_count={result['current_table_count']}")
    lines.append(f"PROBE-1-COMPLETE:{UNIT}")
    raw = "\n".join(lines) + "\n"
    write_raw(raw_path, raw)
    write_json(json_path, result)
    print(raw, end="")
    return result


def classify_render(stdout: str, stderr: str, exit_code: int, timed_out: bool) -> str:
    combined = (stdout or "") + (stderr or "")
    if timed_out and not (stdout or "").strip():
        return "UNREACHABLE"
    if any(m in combined for m in ERROR_MARKERS):
        return "EMPTY"
    render = stdout or ""
    if not render.strip():
        return "EMPTY"
    return "CANDIDATE"  # refined after pair compare


def launch_once(entry: Path, args: list[str], timeout: float) -> dict[str, Any]:
    cmd = [sys.executable, "-B", str(entry), *args]
    env = {
        **os.environ,
        "TERM": "dumb",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(entry.parent),
    }
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO),
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "command": cmd,
            "exit_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        return {
            "command": cmd,
            "exit_code": 124,
            "stdout": out,
            "stderr": err + "\nTIMEOUT",
            "timed_out": True,
        }
    except OSError as exc:
        return {
            "command": cmd,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "timed_out": False,
        }


def run_probe2(
    raw_path: Path,
    json_path: Path,
    probe1: dict[str, Any] | None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    if probe1 is None:
        p1_path = PROBE / "probe1-dispatcher-table.json"
        probe1 = json.loads(p1_path.read_text(encoding="utf-8"))

    export = next(t for t in probe1["tables"] if t["label"] == "repo-export")
    routes = list(export.get("entries") or [])
    lines: list[str] = [
        "Probe 2: launch each route once and assert a non-empty, changing render.",
        "launch_policy=direct python one-shot of each export entry; WT/start windows are not opened",
        "render_rule=LIVE requires nonempty render bytes and two distinct clock-stripped payloads",
        "error_text_is_not_a_render=true",
        "volatile_clock_text_is_not_liveness=true",
        "mtime_stall_used=false",
    ]

    inventory: list[dict[str, Any]] = []
    counts = {"LIVE": 0, "NONEMPTY_STATIC": 0, "EMPTY": 0, "UNREACHABLE": 0}

    for route in routes:
        name = route["name"]
        entry_path = Path(route["entry_path"] or "")
        args = list(ROUTE_ARGS.get(name, []))
        if not route.get("entry_exists") or not entry_path.is_file():
            row = {
                "name": name,
                "entry": str(entry_path),
                "command": [],
                "exit_a": 127,
                "exit_b": 127,
                "timed_out_a": False,
                "timed_out_b": False,
                "render_bytes_a": 0,
                "render_bytes_b": 0,
                "digest_a": hashlib.sha256(b"").hexdigest(),
                "digest_b": hashlib.sha256(b"").hexdigest(),
                "changed": False,
                "classification": "UNREACHABLE",
                "stderr_a": "entry script ABSENT",
                "args": args,
            }
            counts["UNREACHABLE"] += 1
            inventory.append(row)
            lines.append(
                f"ROUTE_LAUNCH|name={name}|attempt=1|command=[]|exit_code=127|"
                f"render_bytes=0|render_changed=false|classification=UNREACHABLE|"
                f'stderr="entry script ABSENT"'
            )
            continue

        a = launch_once(entry_path, args, timeout)
        time.sleep(0.35)
        b = launch_once(entry_path, args, timeout)

        cls_a = classify_render(a["stdout"], a["stderr"], a["exit_code"], a["timed_out"])
        cls_b = classify_render(b["stdout"], b["stderr"], b["exit_code"], b["timed_out"])
        dig_a = digest(a["stdout"])
        dig_b = digest(b["stdout"])
        changed = dig_a != dig_b
        render_a = len(a["stdout"] or "")
        render_b = len(b["stdout"] or "")

        if cls_a == "UNREACHABLE" or cls_b == "UNREACHABLE":
            classification = "UNREACHABLE"
        elif cls_a == "EMPTY" or cls_b == "EMPTY":
            classification = "EMPTY"
        elif render_a > 0 and render_b > 0 and changed:
            classification = "LIVE"
        elif render_a > 0 and render_b > 0:
            classification = "NONEMPTY_STATIC"
        else:
            classification = "EMPTY"

        counts[classification] += 1
        stderr_preview = (a["stderr"] or "").replace("\n", "\\n")[:200]
        row = {
            "name": name,
            "entry": str(entry_path),
            "command": a["command"],
            "exit_a": a["exit_code"],
            "exit_b": b["exit_code"],
            "timed_out_a": a["timed_out"],
            "timed_out_b": b["timed_out"],
            "render_bytes_a": render_a,
            "render_bytes_b": render_b,
            "digest_a": dig_a,
            "digest_b": dig_b,
            "changed": changed,
            "classification": classification,
            "stderr_a": (a["stderr"] or "")[:2000],
            "args": args,
        }
        inventory.append(row)
        lines.append(
            f"ROUTE_LAUNCH|name={name}|attempt=1|command={json.dumps(a['command'])}|"
            f"exit_code={a['exit_code']}|render_bytes={render_a}|"
            f"render_changed={str(changed).lower()}|classification={classification}|"
            f'stderr="{stderr_preview}"'
        )
        lines.append(
            f"ROUTE_LAUNCH|name={name}|attempt=2|exit_code={b['exit_code']}|"
            f"render_bytes={render_b}|digest_a={dig_a[:16]}|digest_b={dig_b[:16]}|"
            f"classification={classification}"
        )

    result = {
        "unit_id": UNIT,
        "probe": "probe2",
        "measured_at": utc_now(),
        "mtime_stall_used": False,
        "routes_attempted": len(inventory),
        "all_routes_attempted_once": True,
        "LIVE": counts["LIVE"],
        "NONEMPTY_STATIC": counts["NONEMPTY_STATIC"],
        "EMPTY": counts["EMPTY"],
        "UNREACHABLE": counts["UNREACHABLE"],
        "classifications": {r["name"]: r["classification"] for r in inventory},
        "route_inventory": inventory,
        "export_route_names": [r["name"] for r in inventory],
    }
    lines.append(f"route_attempt_count={result['routes_attempted']}")
    lines.append(f"all_routes_attempted_once={str(result['all_routes_attempted_once']).lower()}")
    lines.append(f"live_route_count={result['LIVE']}")
    lines.append(f"nonempty_static_route_count={result['NONEMPTY_STATIC']}")
    lines.append(f"empty_route_count={result['EMPTY']}")
    lines.append(f"unreachable_route_count={result['UNREACHABLE']}")
    lines.append(f"PROBE-2-COMPLETE:{UNIT}")
    raw = "\n".join(lines) + "\n"
    write_raw(raw_path, raw)
    write_json(json_path, result)
    print(raw, end="")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AUD-0064 monitor surface probes")
    ap.add_argument("mode", choices=["probe1", "probe2", "all"])
    ap.add_argument("--raw-output", type=Path, default=None)
    ap.add_argument("--result-json", type=Path, default=None)
    ap.add_argument("--probe1-json", type=Path, default=PROBE / "probe1-dispatcher-table.json")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args(argv)

    if args.mode in {"probe1", "all"}:
        raw = args.raw_output or PROBE / "probe1-dispatcher-table.raw.txt"
        js = args.result_json or PROBE / "probe1-dispatcher-table.json"
        if args.mode == "all":
            raw = PROBE / "probe1-dispatcher-table.raw.txt"
            js = PROBE / "probe1-dispatcher-table.json"
        run_probe1(raw, js)

    if args.mode in {"probe2", "all"}:
        raw = args.raw_output or PROBE / "probe2-route-renders.raw.txt"
        js = args.result_json or PROBE / "probe2-route-renders.json"
        if args.mode == "all":
            raw = PROBE / "probe2-route-renders.raw.txt"
            js = PROBE / "probe2-route-renders.json"
        p1 = None
        if args.probe1_json.is_file():
            p1 = json.loads(args.probe1_json.read_text(encoding="utf-8"))
        run_probe2(raw, js, p1, timeout=args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
