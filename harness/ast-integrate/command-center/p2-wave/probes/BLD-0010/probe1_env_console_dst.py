#!/usr/bin/env python3
"""Probe 1: env triple, cp1252 console, DST fall-back, naive mutant, locale sort."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0010.json"
UNIT = "BLD-0010"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if os.environ.get("PYTHONIOENCODING"):
        return fail("PYTHONIOENCODING is set; catalog test requires it unset")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:BLD-0010" not in text:
        return fail("sentinel absent")

    live = R.run_all()
    env = live["environment_runs"]
    native = env["native"]
    print(
        json.dumps(
            {
                "probe": "probe1-env-console-dst",
                "requested": native["requested"],
                "actual": native["actual"],
                "pythonioencoding_set": native["pythonioencoding_set"],
                "locale_strikes": env["wrapper"]["locale_strikes"],
                "pivoted_after_two_strikes": env["wrapper"]["pivoted_after_two_strikes"],
                "dst_fall_back": live["dst_fall_back"]["pass"],
                "dst_stamps": live["dst_fall_back"]["stamps"],
                "naive_mutant": live["naive_datetime_mutant"]["pass"],
                "cp1252": live["cp1252_console"]["pass"],
                "locale_sort": live["locale_sort"]["pass"],
            },
            sort_keys=True,
        )
    )
    if native["pythonioencoding_set"]:
        return fail("PYTHONIOENCODING set on native run")
    if native["actual"]["stdout_encoding"] == native["requested"]["codepage"]:
        # Linux native stdout is not cp1252; claiming it is would be dishonest.
        return fail("native stdout unexpectedly already cp1252; wrapper control would be vacuous")
    if not env["wrapper"]["pivoted_after_two_strikes"]:
        return fail("expected two setlocale strikes then pivot")
    if not live["dst_fall_back"]["pass"]:
        return fail("DST fall-back not ordered")
    if not live["naive_datetime_mutant"]["pass"]:
        return fail("naive datetime mutant did not turn the suite RED")
    if not live["cp1252_console"]["pass"]:
        return fail("cp1252 console check failed")
    if not live["locale_sort"]["pass"]:
        return fail("locale sort check failed")

    tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    for tid in (
        "T-ENVIRONMENT-TRIPLE",
        "T-CP1252-CONSOLE",
        "T-DST-FALL-BACK",
        "T-NAIVE-DATETIME-MUTANT",
        "T-LOCALE-SORT",
    ):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")
    art_stamps = (doc.get("dst_fall_back") or {}).get("stamps")
    if art_stamps != live["dst_fall_back"]["stamps"]:
        return fail("artifact DST stamps drifted from live rerun")
    if doc.get("reviewer", {}).get("independent") is not True:
        return fail("artifact reviewer.independent is not true")
    print("actual_triple "
          f"codepage={native['actual']['stdout_encoding']} "
          f"locale={native['actual']['locale']} "
          f"TZ={native['actual']['tz']}")
    print("SUCCESS:BLD-0010-probe1 env triple, cp1252, DST fall-back, naive mutant, locale sort")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
