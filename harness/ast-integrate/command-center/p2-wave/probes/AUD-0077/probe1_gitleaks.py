#!/usr/bin/env python3
"""Named probe 1: live gitleaks (metadata only) plus planted-token control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from control import run_control  # noqa: E402
from gitleaks_scan import scan_repo  # noqa: E402
from helpers import OUT_REL, REPO, SENTINEL, UNIT  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:AUD-0077-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        print("FAILED:AUD-0077-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0077-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0077-probe1 self-declared", doc.get("state"))
        return 1

    live = scan_repo()
    recorded = list((doc.get("gitleaks") or {}).get("fingerprints") or [])
    if live["fingerprints"] != recorded:
        print("FAILED:AUD-0077-probe1 fingerprint mismatch")
        print(json.dumps({"live_n": live["hit_count"], "recorded_n": len(recorded)}, sort_keys=True))
        return 1

    ctrl = run_control()
    if not ctrl.get("gitleaks_found") or not ctrl.get("both_found"):
        print("FAILED:AUD-0077-probe1 planted token not found by gitleaks/both")
        print(json.dumps({k: ctrl[k] for k in ("gitleaks_found", "entropy_found", "both_found")}, sort_keys=True))
        return 1

    summary = {
        "probe": "probe1-gitleaks",
        "unit_id": UNIT,
        "pass": True,
        "hit_count": live["hit_count"],
        "rule_counts": live["rule_counts"],
        "version": live["version"],
        "history_scanned": False,
        "control_gitleaks_found": True,
        "control_both_found": True,
        "secret_values_printed": False,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:AUD-0077-probe1 gitleaks working-tree metadata-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
