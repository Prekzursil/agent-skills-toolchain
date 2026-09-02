#!/usr/bin/env python3
"""Probe 1: re-run planted back-date, timezone, dependency, and healthy controls.

Does not trust the artifact's claimed booleans. Recomputes from fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0167.json"
UNIT = "CNF-0167"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0167-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        return fail("artifact missing or undersized")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNF-0167" not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    ctrl = A.run_required_controls()
    tests = ctrl["tests"]
    tz = ctrl["timezone_control"]
    print(
        json.dumps(
            {
                "probe": "probe1-planted-and-timezone",
                "unit_id": UNIT,
                "tests": tests,
                "timezone_utc_same": tz["same_instant"],
                "naive_civil": tz["naive_civil_result"],
                "backdated_n": ctrl["worlds"]["backdated"]["inversion_count"],
                "dep_n": ctrl["worlds"]["dep-order"]["inversion_count"],
                "healthy_n": ctrl["worlds"]["healthy"]["inversion_count"],
            },
            sort_keys=True,
        )
    )
    if not tests["planted_backdated_caught"]:
        return fail("planted back-dated receipt not caught")
    if not tests["timezone_same_instant_not_flagged"]:
        return fail("timezone pair flagged or not recognized as same instant")
    if not tests["naive_civil_would_flag_timezone_pair"]:
        return fail("naive civil trap did not fire — timezone control is vacuous")
    if not tests["dependency_before_parent_caught"]:
        return fail("dependency-before-parent not caught")
    if not tests["healthy_zero_inversions"]:
        return fail("healthy world produced inversions")
    if tests["healthy_zero_inversions"] == tests["planted_backdated_caught"] and not tests["planted_backdated_caught"]:
        return fail("both-states collapsed")

    kinds = {i["kind"] for i in ctrl["worlds"]["backdated"]["inversions"]}
    if "receipt-before-cited-artifact" not in kinds:
        return fail("backdated world missing receipt-before-cited-artifact")
    planted_rows = [
        i
        for i in ctrl["worlds"]["backdated"]["inversions"]
        if i.get("kind") == "receipt-before-cited-artifact"
    ]
    planted = planted_rows[0]
    if not planted.get("receipt_ts") or not planted.get("artifact_mtime"):
        return fail("planted inversion missing receipt_ts or artifact_mtime")
    if not planted.get("git_commit_ts") and not planted.get("event_ts"):
        return fail("planted inversion missing third timestamp (git or event)")
    if planted.get("classification") != "fabrication":
        return fail(f"planted classified {planted.get('classification')} not fabrication")

    art_tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    for tid in ("planted-backdated", "timezone-same-instant", "dependency-ordering", "healthy-both-states"):
        row = art_tests.get(tid) or {}
        if row.get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    tz_pol = doc.get("timezone_policy") or {}
    pair = tz_pol.get("timezone_pair") or {}
    if pair.get("same_instant") is not True:
        return fail("artifact timezone_pair.same_instant is not true")
    if pair.get("naive_civil_result") != tz["naive_civil_result"]:
        return fail("artifact naive_civil_result != live")
    if str(tz_pol.get("naive_local_comparison") or "").lower() != "forbidden":
        return fail("artifact did not forbid naive local comparison")

    back_art = ((doc.get("controls") or {}).get("planted_backdated") or {}).get("inversions") or []
    if not back_art:
        return fail("artifact planted_backdated inversions empty")
    live_subjects = {i.get("subject") for i in ctrl["worlds"]["backdated"]["inversions"]}
    art_subjects = {i.get("subject") for i in back_art if isinstance(i, dict)}
    if "PLANT-BACKDATE" not in live_subjects or "PLANT-BACKDATE" not in art_subjects:
        return fail("PLANT-BACKDATE subject missing from live or artifact")

    print("SUCCESS:CNF-0167-probe1 planted/timezone/dependency/healthy controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
