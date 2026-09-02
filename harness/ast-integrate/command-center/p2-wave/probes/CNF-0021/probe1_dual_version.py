#!/usr/bin/env python3
"""Probe 1: re-run pinned vs ambient ruff on identical bytes and check the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import parity as P  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0021-version-parity.json"


def main() -> int:
    live = P.dual_run_ruff()
    printable = {
        "input_sha256": live["input_sha256"],
        "input_bytes": live["input_bytes"],
        "pinned_version": live["pinned"]["version_verbatim"],
        "ambient_version": live["ambient"]["version_verbatim"],
        "pinned_verdicts": live["pinned_check_verdicts"],
        "ambient_verdicts": live["ambient_check_verdicts"],
        "verdicts_differ": live["verdicts_differ"],
    }
    print(json.dumps(printable, sort_keys=True))
    if "0.15.17" not in str(live["pinned"]["version_verbatim"]):
        print("FAILED:CNF-0021-probe1 pinned binary is not 0.15.17")
        return 1
    if "0.15.22" not in str(live["ambient"]["version_verbatim"]):
        print("FAILED:CNF-0021-probe1 ambient binary is not 0.15.22")
        return 1
    if live["input_bytes"] < 1:
        print("FAILED:CNF-0021-probe1 empty input")
        return 1
    if not live.get("identical_bytes"):
        print("FAILED:CNF-0021-probe1 not identical bytes")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0021-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0021-probe1 self-declared {doc.get('state')}")
        return 1
    if P.SENTINEL not in text:
        print("FAILED:CNF-0021-probe1 sentinel absent")
        return 1
    runs = doc.get("dual_version_runs") or []
    if not runs:
        print("FAILED:CNF-0021-probe1 no dual_version_runs")
        return 1
    rec = runs[0]
    if rec.get("input_sha256") != live["input_sha256"]:
        print("FAILED:CNF-0021-probe1 input sha256 drift")
        return 1
    if rec.get("verdicts_differ") != live["verdicts_differ"]:
        print("FAILED:CNF-0021-probe1 verdicts_differ drift")
        return 1
    if "0.15.17" not in str((rec.get("pinned") or {}).get("version_verbatim")):
        print("FAILED:CNF-0021-probe1 artifact pinned version")
        return 1
    if "0.15.22" not in str((rec.get("ambient") or {}).get("version_verbatim")):
        print("FAILED:CNF-0021-probe1 artifact ambient version")
        return 1
    pchecks = (rec.get("pinned") or {}).get("checks") or []
    achecks = (rec.get("ambient") or {}).get("checks") or []
    if len(pchecks) < 1 or len(achecks) < 1:
        print("FAILED:CNF-0021-probe1 missing version checks")
        return 1
    tools = doc.get("tools") or []
    ruff = next((t for t in tools if t.get("tool") == "ruff"), None)
    if not ruff:
        print("FAILED:CNF-0021-probe1 ruff row missing")
        return 1
    if not ruff.get("pinned_verdict") or not ruff.get("ambient_verdict"):
        print("FAILED:CNF-0021-probe1 ruff verdicts missing")
        return 1
    print(
        f"pinned={live['pinned']['version_verbatim']} "
        f"ambient={live['ambient']['version_verbatim']} "
        f"verdicts_differ={live['verdicts_differ']} "
        f"sha256={live['input_sha256']}"
    )
    print("SUCCESS:CNF-0021-probe1 dual-version identical-bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
