#!/usr/bin/env python3
"""Probe 1: documented-command coverage computed; planted broken command caught.

Both-states:
  good.md  — every claimed command runs, coverage == 1.0, broken == []
  planted  — planted command is executed and recorded non-zero
Execute-disabled control — coverage drops and untested > 0, so coverage is not a constant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center/library/knowledge_blueprints"
sys.path.insert(0, str(LIB))

import docverify  # noqa: E402
from registry import load_library  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0252.json"
GOOD = HERE / "fixtures/docs/good.md"
BAD = HERE / "fixtures/docs/planted-broken.md"
PLANTED = "not-a-real-command-imp0252"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0252-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0252":
        return fail(f"unit_id={doc.get('unit_id')}")
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0252" not in blob:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    lib = load_library()
    if "documentation-verification" not in lib["fingerprints"]:
        return fail("documentation-verification not registered")

    good = docverify.run_example(GOOD, execute=True)
    bad = docverify.run_example(BAD, execute=True)
    skipped = docverify.run_example(GOOD, execute=False)

    if good["claimed"] < 3:
        return fail(f"good claimed={good['claimed']} want>=3")
    if good["executed"] != good["claimed"]:
        return fail(f"good executed={good['executed']} claimed={good['claimed']}")
    if good["untested"] != 0 or good["broken"]:
        return fail(f"good untested={good['untested']} broken={good['broken']}")
    if good["coverage"] != 1.0 or not good["coverage_computed"]:
        return fail(f"good coverage={good['coverage']}")
    if not good["pass_clean"]:
        return fail("good not pass_clean")

    planted_rows = [
        c
        for c in bad["commands"]
        if PLANTED in c["command"]
    ]
    if len(planted_rows) != 1:
        return fail(f"planted extract count={len(planted_rows)}")
    planted = planted_rows[0]
    if not planted["executed"] or planted["exit_code"] in (None, 0):
        return fail(f"planted not caught executed={planted['executed']} rc={planted['exit_code']}")
    if not any(PLANTED in b["command"] for b in bad["broken"]):
        return fail(f"planted missing from broken list {bad['broken']}")
    if bad["claimed"] < 4:
        return fail(f"bad claimed={bad['claimed']} want>=4 (incl NOT-EXECUTABLE)")
    if bad["marked"] < 1:
        return fail("NOT-EXECUTABLE fence was not marked")
    if bad["untested"] != 0:
        return fail(f"bad untested={bad['untested']} (skipped instead of executed)")
    if not bad["coverage_computed"]:
        return fail("bad coverage not computed")
    if not (0.0 <= bad["coverage"] <= 1.0):
        return fail(f"bad coverage out of range {bad['coverage']}")

    if skipped["execute"] is not False:
        return fail("skip-execute flag lost")
    if skipped["executed"] != 0:
        return fail(f"skip-execute still ran {skipped['executed']}")
    if skipped["untested"] != skipped["claimed"] or skipped["claimed"] < 1:
        return fail(f"skip-execute untested={skipped['untested']}")
    if skipped["coverage"] != 0.0:
        return fail(f"skip-execute coverage={skipped['coverage']} (not computed from zeros)")

    recorded = ((doc.get("evidence") or [{}])[0].get("measurements") or {})
    # Receipt may nest the live numbers; if present they must match this rerun.
    live_cov = None
    for ev in doc.get("evidence") or []:
        m = ev.get("measurements") if isinstance(ev, dict) else None
        if isinstance(m, dict) and "good_coverage" in m:
            live_cov = m
            break
    if live_cov is not None:
        if live_cov.get("good_coverage") != good["coverage"]:
            return fail("receipt good_coverage drifted from live rerun")
        if live_cov.get("planted_exit_code") != planted["exit_code"]:
            return fail("receipt planted_exit_code drifted from live rerun")

    out = {
        "probe": "probe1-doc-commands",
        "unit_id": "IMP-0252",
        "good": {
            "claimed": good["claimed"],
            "executed": good["executed"],
            "coverage": good["coverage"],
            "broken": 0,
        },
        "bad": {
            "claimed": bad["claimed"],
            "executed": bad["executed"],
            "marked": bad["marked"],
            "planted_exit_code": planted["exit_code"],
            "planted_caught": True,
        },
        "skip_execute_coverage": skipped["coverage"],
        "coverage_is_computed": True,
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"good coverage={good['coverage']} executed={good['executed']}/{good['claimed']} "
        f"bad planted_rc={planted['exit_code']} marked={bad['marked']} "
        f"skip_coverage={skipped['coverage']}"
    )
    print("SUCCESS:IMP-0252-probe1 documented-command coverage and planted-broken both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
