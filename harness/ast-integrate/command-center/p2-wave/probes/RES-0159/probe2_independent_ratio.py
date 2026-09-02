#!/usr/bin/env python3
"""Named probe 2: independent recount must match the artifact ratio.

Structured Triple subtraction vs integer recount (no Triple objects).
Also kills a skip-subtract mutant that would report novel_n == raw_n.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import subtractor as S  # noqa: E402

ART = S.REPO / S.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0159-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if S.SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("SUCCESS:RES-0159 absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    measured = S.measure()
    live = measured["ratio"]
    recount = measured["recount"]
    reported = doc.get("measurement") or {}
    for key in ("raw_n", "novel_n", "declared_n"):
        if reported.get(key) != live[key] or reported.get(key) != recount[key]:
            return fail(
                f"{key} mismatch artifact={reported.get(key)} "
                f"structured={live[key]} recount={recount[key]}"
            )
    if abs(float(reported.get("novel_over_raw")) - float(live["novel_over_raw"])) > 1e-9:
        return fail("novel_over_raw mismatch")
    if recount["raw_n"] == recount["novel_n"]:
        return fail("recount collapsed to all-novel; subtractor inert")
    if live["raw_n"] == live["novel_n"]:
        return fail("structured collapsed to all-novel; subtractor inert")

    mutant_novel = live["raw_n"]
    mutant_ratio = 1.0
    mutant_killed = mutant_novel != live["novel_n"]
    payload = {
        "probe": "probe2-independent-ratio",
        "unit_id": "RES-0159",
        "structured": live,
        "recount": {
            "raw_n": recount["raw_n"],
            "declared_n": recount["declared_n"],
            "novel_n": recount["novel_n"],
            "by_rel": recount["by_rel"],
            "novel_by_rel": recount["novel_by_rel"],
        },
        "artifact": {
            "raw_n": reported.get("raw_n"),
            "declared_n": reported.get("declared_n"),
            "novel_n": reported.get("novel_n"),
            "novel_over_raw": reported.get("novel_over_raw"),
        },
        "skip_subtract_mutant": {
            "would_report_novel_n": mutant_novel,
            "would_report_ratio": mutant_ratio,
            "killed": mutant_killed,
        },
        "phase0_units": len(measured["units"]),
        "phase0_artifacts_on_disk": len(measured["artifacts_on_disk"]),
        "pass": True,
    }
    if not mutant_killed:
        payload["pass"] = False
        print(json.dumps(payload, sort_keys=True))
        return fail("skip-subtract mutant not distinguishable")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"raw={live['raw_n']} declared={live['declared_n']} "
        f"novel={live['novel_n']} ratio={live['novel_over_raw']}"
    )
    print("SUCCESS:RES-0159-probe2 independent recount matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
