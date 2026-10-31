#!/usr/bin/env python3
"""Probe 1: revoke the fixture, then install immediately from each source."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0038-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if H.SENTINEL not in text or H.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0038-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0038-probe1 self-declared {st}")
        return 1

    live = H.run_scenario()
    if not live["controls"]["non_revoked_installs_from_every_source"]:
        print("FAILED:ADV-0038-probe1 control package did not install from every source")
        return 1
    silent = live["controls"]["revoked_silent_success_sources"]
    if set(silent) != set(H.SOURCES):
        print("FAILED:ADV-0038-probe1 expected silent success on all four sources", silent)
        return 1
    if not live["controls"]["honouring_mutant_refuses_all"]:
        print("FAILED:ADV-0038-probe1 honouring mutant did not refuse")
        return 1
    art_targets = {t["name"]: t["verdict"] for t in doc.get("enumerated_targets") or []}
    live_targets = {t["name"]: t["verdict"] for t in live["targets"]}
    if art_targets != live_targets:
        print("FAILED:ADV-0038-probe1 target verdict mismatch", art_targets, live_targets)
        return 1
    for name, verdict in live_targets.items():
        if verdict != "CONFIRMED":
            print(f"FAILED:ADV-0038-probe1 {name} verdict {verdict} want CONFIRMED")
            return 1
        if verdict not in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}:
            print("FAILED:ADV-0038-probe1 illegal verdict")
            return 1

    summary = {
        "probe": "probe1-revoke-then-install",
        "unit_id": H.UNIT,
        "sources": list(H.SOURCES),
        "control_ok": True,
        "silent_success": list(silent),
        "honouring_mutant_refuses": True,
        "target_verdicts": live_targets,
        "p1_finding": live["p1_finding"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:ADV-0038-probe1 revoke then silent install from all four sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
