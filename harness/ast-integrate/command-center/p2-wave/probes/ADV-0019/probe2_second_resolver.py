#!/usr/bin/env python3
"""Probe 2: second inventory — POSIX command -v / Get-Command, plus live MCP tool schema."""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def bash_command_v(name: str) -> dict:
    if "/" in name or name.startswith("mcp__") or name == C.PLUGIN_NAME:
        return {"ok": False, "source": None, "method": "skipped-non-binary"}
    try:
        p = subprocess.run(
            ["bash", "-lc", "command -v " + shlex.quote(name)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "source": None, "method": "command -v", "error": str(exc)}
    src = (p.stdout or "").strip().splitlines()
    hit = src[0] if src else ""
    return {
        "ok": p.returncode == 0 and bool(hit),
        "source": hit or None,
        "method": "bash command -v",
        "exit_code": p.returncode,
    }


def powershell_get_command(name: str) -> dict:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        return {
            "ok": False,
            "available": False,
            "method": "Get-Command",
            "reason": "powershell-not-installed-on-this-linux-worktree",
        }
    # Names that are not command identifiers would make Get-Command noisy.
    if name.startswith("mcp__") or name == C.PLUGIN_NAME:
        return {"ok": False, "available": True, "method": "Get-Command", "skipped": True}
    try:
        p = subprocess.run(
            [
                exe,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"Get-Command -Name {name} -ErrorAction SilentlyContinue | "
                "Select-Object -ExpandProperty Source",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "available": True,
            "method": "Get-Command",
            "error": str(exc),
        }
    src = (p.stdout or "").strip().splitlines()
    hit = src[0] if src else ""
    return {
        "ok": bool(hit),
        "available": True,
        "method": "Get-Command",
        "source": hit or None,
        "exe": exe,
    }


def mcp_live(name: str, tool_names: set[str]) -> bool:
    if name in tool_names:
        return True
    if name.startswith("mcp__"):
        return name in tool_names
    return False


def main() -> int:
    corpus = C.load_corpus()
    schema = C.load_mcp_schema()
    mcp_names = C.mcp_tool_names(schema)
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    dead = []
    live = []
    resolutions = []
    for rec in corpus["tokens"]:
        name = rec["name"]
        posix = bash_command_v(name)
        ps = powershell_get_command(name)
        mcp = mcp_live(name, mcp_names)
        present = bool(posix.get("ok") or ps.get("ok") or mcp)
        row = {
            **rec,
            "posix_command_v": posix,
            "powershell_get_command": ps,
            "mcp_schema_live": mcp,
            "present": present,
            "resolver": "command -v + Get-Command + MCP tool schema",
        }
        resolutions.append(
            {
                "name": name,
                "present": present,
                "posix": posix.get("ok"),
                "get_command": ps.get("ok"),
                "mcp": mcp,
            }
        )
        (live if present else dead).append(row)

    dead_names = [r["name"] for r in dead]
    live_names = [r["name"] for r in live]
    known_absent_flagged = all(n in dead_names for n in C.RETIRED)
    known_present_clean = C.KNOWN_PRESENT not in dead_names
    python_extracted = C.KNOWN_PRESENT in corpus["token_names"]
    python_posix = any(
        r["name"] == C.KNOWN_PRESENT and r["posix_command_v"].get("ok") for r in live
    )

    doc = {
        "probe": "probe2-second-resolver",
        "unit_id": C.UNIT,
        "resolver": "bash command -v (POSIX) and Get-Command when PowerShell exists, plus MCP tool schema",
        "not_shutil_which": True,
        "powershell_binary": pwsh,
        "powershell_present": bool(pwsh),
        "mcp_tool_names": sorted(mcp_names),
        "file_count": corpus["file_count"],
        "extracted": corpus["token_names"],
        "resolutions": resolutions,
        "dead": dead,
        "live": live,
        "dead_names": dead_names,
        "live_names": live_names,
        "controls": {
            "known_absent_get_budget_check_budget_flagged": known_absent_flagged,
            "known_present_python3_not_flagged": known_present_clean,
            "python3_extracted": python_extracted,
            "python3_resolved_via_command_v": python_posix,
            "ghost_mcp_dead": C.GHOST_MCP in dead_names,
            "ghost_cli_dead": C.GHOST_CLI in dead_names,
        },
    }
    print(json.dumps(doc, indent=1, sort_keys=True))
    if not python_extracted or not python_posix:
        print("FAILED:ADV-0019-probe2 python3 not resolved via command -v")
        return 1
    if not known_present_clean:
        print("FAILED:ADV-0019-probe2 known-present python3 was flagged")
        return 1
    if not known_absent_flagged:
        print("FAILED:ADV-0019-probe2 retired budget tools were not flagged")
        return 1
    if C.GHOST_MCP not in dead_names:
        print("FAILED:ADV-0019-probe2 ghost MCP still considered live")
        return 1
    print(
        "SUCCESS:ADV-0019-probe2 second-resolver "
        f"powershell={'yes' if pwsh else 'absent'} "
        f"dead={','.join(dead_names)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
