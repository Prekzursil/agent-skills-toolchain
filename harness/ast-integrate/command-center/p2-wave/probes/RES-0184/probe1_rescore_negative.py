#!/usr/bin/env python3
"""Probe 1: live re-score of the frozen 20 + high-severity negative control.

Mechanically: recompute scores from live recorded JSON, then check the
emitted artifact matches. A bar that places zero high-severity claims
BELOW is UNINFORMATIVE (status-quo calibration) and fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0184-probe1 {msg}")
    return 1


def main() -> int:
    rows = E.score_all()
    if len(rows) != 20:
        return fail(f"expected 20 scored claims, got {len(rows)}")
    high_below = [
        r for r in rows if r["severity"] in {"P0", "P1"} and r["placement"] == "BELOW"
    ]
    below = [r for r in rows if r["placement"] == "BELOW"]
    sev = E.both_states_severity_control()
    sq = E.status_quo_mutant(rows)
    checks = {
        "n20": len(rows) == 20,
        "high_severity_below": len(high_below) >= 1,
        "any_below": len(below) >= 1,
        "severity_not_flat": sev["fired"] is True,
        "status_quo_rejected": sq["fired"] is True,
        "p3_present": any(r["severity"] == "P3" for r in rows),
        "p0_present": any(r["severity"] == "P0" for r in rows),
    }
    if not E.ARTIFACT.is_file():
        return fail("artifact-absent")
    raw = E.ARTIFACT.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if E.SENTINEL not in raw:
        return fail("sentinel-absent")
    art_below = int((doc.get("rescore") or {}).get("below_bar_count") or -1)
    art_high = list((doc.get("rescore") or {}).get("high_severity_below_ids") or [])
    live_high_ids = [r["claim_id"] for r in high_below]
    checks["artifact_below_matches"] = art_below == len(below)
    checks["artifact_high_matches"] = art_high == live_high_ids
    checks["calibration_informative"] = doc.get("calibration") == "INFORMATIVE"
    checks["state_success"] = doc.get("state") == "SUCCESS"
    bad = [k for k, ok in checks.items() if not ok]
    print(
        json.dumps(
            {
                "probe": "probe1-rescore-negative",
                "checks": checks,
                "below_bar_count": len(below),
                "high_severity_below_ids": live_high_ids,
                "severity_control": {
                    "p3": sev.get("p3_placement"),
                    "p0": sev.get("p0_placement"),
                    "fired": sev.get("fired"),
                },
            },
            sort_keys=True,
        )
    )
    if bad:
        return fail("checks:" + ",".join(bad))
    print(
        f"below={len(below)}/20 high_below={len(high_below)} "
        f"severity_not_flat={sev['fired']} status_quo_rejected={sq['fired']}"
    )
    print("SUCCESS:RES-0184-probe1 live rescore and high-severity negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
