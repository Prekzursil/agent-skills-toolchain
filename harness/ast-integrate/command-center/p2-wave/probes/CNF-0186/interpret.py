#!/usr/bin/env python3
"""Silence / missing-run / killed-mid-run adjudication for CNF-0186.

A watchdog that produces no output is FAILED, not green.
A missing scheduled run is FAILED, not a pass.
A package with no terminal-state line after a run is FAILED:no-terminal-line.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TERMINAL_RE = re.compile(r"^(SUCCESS|FAILED):(\S+)(?:\s+(.*))?$")


def parse_terminal_lines(stdout: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    parsed: dict[str, dict[str, str]] = {}
    noise: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = TERMINAL_RE.match(line)
        if not m:
            noise.append(line)
            continue
        status, pkg_id, reason = m.group(1), m.group(2), (m.group(3) or "").strip()
        parsed[pkg_id] = {
            "status": status,
            "package_id": pkg_id,
            "reason": reason,
            "terminal": line,
        }
    return parsed, noise


def adjudicate(stdout: str, expected_ids: list[str]) -> dict[str, Any]:
    """Turn watchdog stdout into per-package terminals.

    Empty stdout → FAILED:<pkg> silence for every expected package.
    Missing id → FAILED:<id> no-terminal-line.
    """
    parsed, noise = parse_terminal_lines(stdout)
    packages: dict[str, Any] = {}
    stripped = stdout.strip()
    silence = stripped == ""
    for pkg_id in expected_ids:
        if silence:
            packages[pkg_id] = {
                "status": "FAILED",
                "package_id": pkg_id,
                "reason": "silence",
                "terminal": f"FAILED:{pkg_id} silence",
            }
            continue
        if pkg_id not in parsed:
            packages[pkg_id] = {
                "status": "FAILED",
                "package_id": pkg_id,
                "reason": "no-terminal-line",
                "terminal": f"FAILED:{pkg_id} no-terminal-line",
            }
            continue
        packages[pkg_id] = parsed[pkg_id]
    overall = "SUCCESS"
    if silence or any(p["status"] != "SUCCESS" for p in packages.values()):
        overall = "FAILED"
    return {
        "overall": overall,
        "silence": silence,
        "noise_lines": noise,
        "packages": packages,
        "parsed_count": len(parsed),
    }


def run_complete(state_dir: Path, date: str) -> bool:
    final = state_dir / "runs" / f"{date}.json"
    if not final.is_file():
        return False
    try:
        doc = json.loads(final.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and doc.get("complete") is True


def missing_run(state_dir: Path, date: str, expected_ids: list[str]) -> dict[str, Any]:
    """A scheduled day with no complete run is FAILED, never SUCCESS."""
    if run_complete(state_dir, date):
        doc = json.loads((state_dir / "runs" / f"{date}.json").read_text(encoding="utf-8"))
        lines = "\n".join(doc.get("terminal_lines") or [])
        return adjudicate(lines, expected_ids)
    packages = {
        pkg_id: {
            "status": "FAILED",
            "package_id": pkg_id,
            "reason": "missing-run",
            "terminal": f"FAILED:{pkg_id} missing-run",
        }
        for pkg_id in expected_ids
    }
    return {
        "overall": "FAILED",
        "silence": False,
        "missing_run": True,
        "noise_lines": [],
        "packages": packages,
        "parsed_count": 0,
    }


def incomplete_kill(
    stdout: str,
    expected_ids: list[str],
    state_dir: Path,
    date: str,
) -> dict[str, Any]:
    """Watchdog killed mid-run: missing terminals are FAILED, never implied SUCCESS."""
    adj = adjudicate(stdout, expected_ids)
    adj["killed_mid_run"] = True
    adj["run_complete"] = run_complete(state_dir, date)
    if adj["run_complete"] and adj["overall"] == "SUCCESS":
        # A complete green run cannot be a mid-run kill.
        adj["kill_path_credible"] = False
    else:
        adj["kill_path_credible"] = True
        adj["overall"] = "FAILED"
    return adj
