#!/usr/bin/env python3
"""Probe 1: PowerShell Get-Command Source for every invoked CLI tool.

PATHEXT/.cmd/.exe lookup. This host has no pwsh; the resolver is the Windows
Get-Command application algorithm, not a forged pwsh transcript.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402

UID = "AUD-0028"
ART = REPO / C.OUT_REL
RAW = HERE / "probe1-get-command.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0028-probe1 {msg}")
    return 1


def slim(live: dict) -> dict:
    ctl = live.get("control") or {}
    return {
        "control": ctl,
        "instrument": live.get("instrument"),
        "pass": live.get("pass"),
        "probe": live.get("probe"),
        "pwsh": live.get("pwsh"),
        "scan": live.get("scan"),
        "summary": live.get("summary"),
        "unit_id": live.get("unit_id"),
    }


def main() -> int:
    live = C.probe1_live(REPO)
    payload = slim(live)
    RAW.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not live.get("pass"):
        return fail("get-command census or both-states control did not pass")
    ctl = live.get("control") or {}
    if not ctl.get("bash_paths_differ"):
        return fail("planted WSL vs MSYS bash paths agreed — same-shell pair")
    if not ctl.get("naive_agree"):
        return fail("naive same-PATH command -v pair did not agree")
    if not ctl.get("git_cmd_shim_won_get_command"):
        return fail("Get-Command missed the planted git.cmd shim")
    if not ctl.get("git_paths_differ"):
        return fail("git.cmd vs git-bash git path did not diverge")
    scan = live.get("scan") or {}
    if int(scan.get("tool_count") or 0) <= 0:
        return fail("invocation scan found zero tools")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")
    recorded = ((doc.get("report") or {}).get("probe1") or {}).get("scan") or {}
    if int(recorded.get("tool_count") or -1) != int(scan["tool_count"]):
        return fail(
            f"artifact tool_count {recorded.get('tool_count')} != live {scan['tool_count']}"
        )
    rec_ctl = ((doc.get("report") or {}).get("control") or {})
    if rec_ctl.get("bash_paths_differ") is not True:
        return fail("artifact control bash_paths_differ is not true")
    print(
        "SUCCESS:AUD-0028-probe1 get-command; "
        f"tools={scan['tool_count']} hits={scan['hit_count']} "
        f"host_path_div={live['summary']['path_divergence_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
