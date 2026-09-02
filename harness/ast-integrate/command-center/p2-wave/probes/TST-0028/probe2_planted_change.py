#!/usr/bin/env python3
"""Probe 2: a planted behaviour change must show up in the artifact and trace diff.

Verifier measurement (distinct fingerprint from probe 1). Plants PLAN_MARKER
in a second materialised build and requires both the artifact-set diff and
the decision-trace diff to fire. A comment-only plant must stay empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0028.json"
SENTINEL = "SUCCESS:TST-0028"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0028-probe2 {msg}")
    return 1


def main() -> int:
    exp = H.run_experiment()
    planted = exp["planted_behaviour_change"]
    comment = exp["comment_only_control"]
    stats = exp["replayability"]
    reasons = {row["reason"] for row in stats["non_replayable_enumerated_by_reason"]}
    fired = (
        (not planted["empty"])
        and (not planted["artifact_set"]["empty"])
        and (not planted["decision_trace"]["empty"])
    )
    out = {
        "probe": "probe2-planted-behaviour-change",
        "unit_id": "TST-0028",
        "planted_empty": planted["empty"],
        "planted_artifact_empty": planted["artifact_set"]["empty"],
        "planted_trace_empty": planted["decision_trace"]["empty"],
        "planted_replay_marker": planted.get("replay_plan_marker"),
        "record_marker": planted.get("record_plan_marker"),
        "comment_only_empty": comment["empty"],
        "reasons_enumerated": sorted(reasons),
        "pass": bool(
            fired
            and comment["empty"]
            and planted.get("replay_plan_marker") == "accept-v2-planted"
            and planted.get("record_plan_marker") == "accept-v1"
            and reasons >= {"network", "credential", "clock", "GUI"}
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["pass"]:
        return fail("planted change silent, comment control fired, or reasons omitted")
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    rec_plant = ((doc.get("tests_live") or {}).get("planted_behaviour_change")) or {}
    if rec_plant.get("empty") is not False:
        return fail("receipt planted_behaviour_change.empty is not false")
    if (rec_plant.get("artifact_set") or {}).get("empty") is not False:
        return fail("receipt planted artifact diff did not fire")
    if (rec_plant.get("decision_trace") or {}).get("empty") is not False:
        return fail("receipt planted trace diff did not fire")
    rec_comment = ((doc.get("tests_live") or {}).get("comment_only_control")) or {}
    if rec_comment.get("empty") is not True:
        return fail("receipt comment-only control is not empty")
    named = {
        row.get("reason")
        for row in (doc.get("replayability") or {}).get("non_replayable_enumerated_by_reason")
        or []
    }
    if not {"network", "credential", "clock", "GUI"} <= named:
        return fail(f"receipt omitted a non-replayable reason named={sorted(named)}")
    tests = doc.get("tests") or []
    by_id = {t.get("id"): t for t in tests if isinstance(t, dict)}
    t2 = by_id.get("test_a_planted_behaviour_change_shows_up_in_the_diff") or {}
    if t2.get("result") != "PASS":
        return fail("receipt planted test is not PASS")
    print(
        f"planted_fires=True comment_silent=True reasons={sorted(reasons)} "
        f"marker={planted.get('replay_plan_marker')}"
    )
    print("SUCCESS:TST-0028-probe2 planted behaviour change shows in the diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
