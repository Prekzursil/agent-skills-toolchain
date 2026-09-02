#!/usr/bin/env python3
"""Probe 2: Git Bash `command -v` for every invoked CLI tool.

Mechanically independent of Get-Command: live bash --noprofile --norc
`command -v`. Re-runs the planted WSL vs MSYS bash control so a same-shell
reviewer cannot rubber-stamp probe 1.
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
RAW = HERE / "probe2-command-v.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0028-probe2 {msg}")
    return 1


def slim(live: dict) -> dict:
    ctl = live.get("control") or {}
    return {
        "control": ctl,
        "host_bash_command_v": live.get("host_bash_command_v"),
        "instrument": live.get("instrument"),
        "pass": live.get("pass"),
        "probe": live.get("probe"),
        "scan": {
            "files_scanned": (live.get("scan") or {}).get("files_scanned"),
            "hit_count": (live.get("scan") or {}).get("hit_count"),
            "tool_count": (live.get("scan") or {}).get("tool_count"),
        },
        "summary": live.get("summary"),
        "unit_id": live.get("unit_id"),
    }


def main() -> int:
    live = C.probe2_live(REPO)
    payload = slim(live)
    RAW.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not live.get("pass"):
        return fail("command -v census or both-states control did not pass")
    ctl = live.get("control") or {}
    if not ctl.get("bash_paths_differ"):
        return fail("planted WSL vs MSYS bash paths agreed — same-shell pair")
    if not ctl.get("naive_agree"):
        return fail("naive same-PATH command -v pair did not agree")
    if not ctl.get("git_paths_differ"):
        return fail("git.cmd vs command -v git did not diverge")
    if not ctl.get("git_bash_resolved_non_cmd"):
        return fail("command -v git resolved to a .cmd shim (unexpected on POSIX)")
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
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    recorded = ((doc.get("report") or {}).get("probe2") or {}).get("scan") or {}
    if int(recorded.get("tool_count") or -1) != int(scan["tool_count"]):
        return fail(
            f"artifact tool_count {recorded.get('tool_count')} != live {scan['tool_count']}"
        )
    rec_ctl = (doc.get("report") or {}).get("control") or {}
    if rec_ctl.get("bash_paths_differ") is not True:
        return fail("artifact control bash_paths_differ is not true")
    if int(recorded.get("hit_count") or -1) != int(scan["hit_count"]):
        return fail(
            f"artifact hit_count {recorded.get('hit_count')} != live {scan['hit_count']}"
        )
    print(
        "SUCCESS:AUD-0028-probe2 command-v; "
        f"tools={scan['tool_count']} present={live['summary']['present']} "
        f"host_bash={live.get('host_bash_command_v')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
