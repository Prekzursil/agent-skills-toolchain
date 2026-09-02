#!/usr/bin/env python3
"""Shared TST-0195 measurements over one on-disk plugin fixture."""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import lookup as L  # noqa: E402

ROOT = HERE / "fixtures" / "plugin-root"

EXACT = "./skills/"
MISMATCH = "./Skills/"
EXACT_FILE = "skills/skill.probe/SKILL.md"
MISMATCH_FILE = "Skills/skill.probe/SKILL.md"


def listing(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir())


def measure(root: Path | None = None) -> dict:
    root = Path(root) if root is not None else ROOT
    names = listing(root)
    linux_exact = L.lookup(root, EXACT, L.LINUX)
    linux_mis = L.lookup(root, MISMATCH, L.LINUX)
    win_exact = L.lookup(root, EXACT, L.WINDOWS)
    win_mis = L.lookup(root, MISMATCH, L.WINDOWS)
    linux_file = L.lookup(root, EXACT_FILE, L.LINUX)
    linux_file_mis = L.lookup(root, MISMATCH_FILE, L.LINUX)
    win_file = L.lookup(root, EXACT_FILE, L.WINDOWS)
    win_file_mis = L.lookup(root, MISMATCH_FILE, L.WINDOWS)
    live_exact = L.live_os_exists(root, EXACT)
    live_mis = L.live_os_exists(root, MISMATCH)
    silent = L.silent_windows_lookup(root, MISMATCH)
    exact_ok, exact_why = L.contract_exact(linux_exact, win_exact)
    mis_ok, mis_why = L.contract_mismatch(linux_mis, win_mis)
    silent_ok, silent_why = L.contract_mismatch(linux_mis, silent)
    host_cs = live_exact and not live_mis
    return {
        "root": str(root),
        "host": {
            "system": platform.system(),
            "platform": platform.platform(),
            "case_sensitive_skills_dir": host_cs,
            "listdir": names,
            "live_os_exists_skills": live_exact,
            "live_os_exists_Skills": live_mis,
        },
        "linux": {
            "exact": _pack(linux_exact),
            "mismatch": _pack(linux_mis),
            "exact_file": _pack(linux_file),
            "mismatch_file": _pack(linux_file_mis),
        },
        "windows": {
            "exact": _pack(win_exact),
            "mismatch": _pack(win_mis),
            "exact_file": _pack(win_file),
            "mismatch_file": _pack(win_file_mis),
            "mismatch_warnings": list(win_mis.warnings),
        },
        "silent_mutant": _pack(silent),
        "contract": {
            "both_states_exact_silent": exact_ok,
            "both_states_why": exact_why,
            "mismatch_declared": mis_ok,
            "mismatch_why": mis_why,
            "silent_mutant_rejected": not silent_ok,
            "silent_mutant_why": silent_why,
        },
        "plugin_json_skills": _plugin_field(root / "plugin.json"),
        "plugin_Skills_json_skills": _plugin_field(root / "plugin-Skills.json"),
        "pwsh": os.environ.get("TST0195_PWSH", "absent"),
        "pass": bool(
            exact_ok
            and mis_ok
            and not silent_ok
            and host_cs
            and "skills" in names
            and "Skills" not in names
            and linux_file.ok
            and not linux_file_mis.ok
            and win_file.ok
            and win_file_mis.ok
            and win_file_mis.names_mismatch("Skills", "skills")
        ),
    }


def _pack(result: L.LookupResult) -> dict:
    return {
        "ok": result.ok,
        "platform": result.platform,
        "requested": result.requested,
        "resolved": result.resolved,
        "warnings": list(result.warnings),
        "reason": result.reason,
        "matched_components": list(result.matched_components),
    }


def _plugin_field(path: Path) -> str | None:
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    val = doc.get("skills")
    return val if isinstance(val, str) else None


def second_shell_windows(root: Path | None = None) -> dict:
    """Second Windows-policy pass using NT separators (pwsh/Git Bash stand-in)."""
    root = Path(root) if root is not None else ROOT
    posix = L.lookup(root, "Skills/", L.WINDOWS)
    nt = L.lookup(root, "Skills\\", L.WINDOWS)
    agree = (
        posix.ok == nt.ok
        and posix.resolved == nt.resolved
        and posix.warnings == nt.warnings
    )
    return {
        "posix": _pack(posix),
        "nt": _pack(nt),
        "agree": agree,
        "pwsh_present": False,
        "git_bash_present": False,
        "note": (
            "pwsh7 and Git Bash are absent on this Linux host; the second "
            "Windows shell is simulated by re-running the Windows policy with "
            "backslash separators on the same fixture."
        ),
    }
