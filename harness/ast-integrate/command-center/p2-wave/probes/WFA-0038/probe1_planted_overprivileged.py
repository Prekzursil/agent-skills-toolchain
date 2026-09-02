#!/usr/bin/env python3
"""Probe 1: planted over-privileged candidate fires before any all-clear."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

ART = REPO / "command-center" / "wfa" / "WFA-0038-extract-tool-permissions.json"
OUT = HERE / "probe1-planted-overprivileged.raw.json"


def _check(report: dict, label: str) -> list[str]:
    failed: list[str] = []
    planted = [
        r
        for r in (report.get("records") or [])
        if isinstance(r, dict) and r.get("planted_class") == "over-privileged"
    ]
    if not planted:
        failed.append(f"{label}:planted-row-absent")
        return failed
    rec = planted[0]
    if not (rec.get("estate_would_not_grant") or rec.get("escalation_risk")):
        failed.append(f"{label}:planted-did-not-fire")
    if rec.get("executed") is not False:
        failed.append(f"{label}:planted-executed")
    if report.get("all_clear") is True:
        failed.append(f"{label}:all-clear-true-after-plant")
    if report.get("all_clear_reported_before_planted") is True:
        failed.append(f"{label}:all-clear-before-planted")
    if report.get("planted_evaluated_before_all_clear") is not True:
        failed.append(f"{label}:planted-not-evaluated-first")
    if report.get("planted_overprivileged_fired") is not True:
        failed.append(f"{label}:headline-planted-fired-false")
    tests = {t.get("id"): t for t in (report.get("tests") or []) if isinstance(t, dict)}
    t = tests.get("planted-overprivileged-before-all-clear")
    if not t or t.get("result") != "PASS":
        failed.append(f"{label}:test-row-not-PASS")
    return failed


def main() -> int:
    live = X.extract(REPO)
    failed = _check(live, "live-extract")
    art_ok = False
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        failed.extend(_check(doc, "artifact"))
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:WFA-0038" not in text:
            failed.append("artifact:sentinel-absent")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            failed.append(f"artifact:self-declared:{doc.get('state')}")
        art_ok = True
    payload = {
        "probe": "probe1-planted-overprivileged",
        "unit_id": "WFA-0038",
        "artifact_present": art_ok,
        "planted_fired": live.get("planted_overprivileged_fired"),
        "all_clear": live.get("all_clear"),
        "failed": failed,
        "pass": not failed,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:WFA-0038-probe1 planted-overprivileged")
        print(json.dumps(failed))
        return 1
    rec = next(
        r
        for r in live["records"]
        if r.get("planted_class") == "over-privileged"
    )
    print(
        "planted_fired=True all_clear=False evaluated_first=True "
        f"violations={rec.get('estate_violations')} "
        f"escalation={rec.get('escalation')}"
    )
    print("SUCCESS:WFA-0038-probe1 planted-overprivileged-before-all-clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
