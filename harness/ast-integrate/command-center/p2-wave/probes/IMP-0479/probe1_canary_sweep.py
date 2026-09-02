#!/usr/bin/env python3
"""Named probe 1: canary sweep across every emission point.

Plants a secret-shaped token, an absolute home path, and a project name at
each named point. Pass = every class absent from the durable emitted stream.
Canary VALUES are never printed; only class names and pass/fail leave stdout.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from telemetry.sweep import run_canary_sweep  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0479.json"
SENTINEL = "SENTINEL:IMP-0479:TELEMETRY-REDACTION-PROVEN"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0479-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0479":
        print("FAILED:IMP-0479-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0479-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0479-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0479-p1-") as tmp:
        result = run_canary_sweep(Path(tmp) / "store")

    if not result.get("pass"):
        failed = [r["emission_point"] for r in result["rows"] if not r["pass"]]
        print(f"FAILED:IMP-0479-probe1 canary leak classes-or-points={failed}")
        return 1
    if result.get("canary_values_printed"):
        print("FAILED:IMP-0479-probe1 printed canary values")
        return 1
    if result["point_count"] < 3:
        print("FAILED:IMP-0479-probe1 too few emission points")
        return 1
    for row in result["rows"]:
        if not (
            row["secret_shaped_absent"]
            and row["home_path_absent"]
            and row["project_name_absent"]
        ):
            print(f"FAILED:IMP-0479-probe1 class present at {row['emission_point']}")
            return 1

    summary = {
        "probe": "probe1-canary-sweep",
        "unit_id": "IMP-0479",
        "point_count": result["point_count"],
        "emission_points": result["emission_points"],
        "all_canary_classes_absent": True,
        "canary_values_printed": False,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0479-probe1 canary sweep all emission points redacted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
