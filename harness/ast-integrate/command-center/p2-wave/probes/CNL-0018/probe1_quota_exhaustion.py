#!/usr/bin/env python3
"""Named probe 1: mid-council quota exhaustion.

Both-states:
  BAD  openai remaining=1, 3 rounds, same-vendor reseat attempted
       -> QUOTA-EXHAUSTED fires, partial artifact preserved, reseat refused
  GOOD both vendors remaining=100
       -> SILENT (zero QUOTA-EXHAUSTED), terminal SUCCESS

Second signal (different mechanism): independent_quota_recount walks the
same declared remaining map without calling simulate_council.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from mechanism import (  # noqa: E402
    EVT_QUOTA_EXHAUSTED,
    EVT_SUBSTITUTION_REFUSED,
    N_ROUNDS,
    QUOTA_BAD,
    QUOTA_GOOD,
    ROSTER_DIVERSE,
    independent_quota_recount,
    simulate_council,
)

ART = REPO / (
    "command-center/design/council/"
    "CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md"
)
FIX = HERE / "fixtures" / "declared.json"


def _load_art() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        raise SystemExit("FAILED:CNL-0018-probe1 artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0018":
        raise SystemExit(f"FAILED:CNL-0018-probe1 unit_id {doc.get('unit_id')}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0018" not in text:
        raise SystemExit("FAILED:CNL-0018-probe1 sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:CNL-0018-probe1 self-declared:{st}")
    return doc


def _loud(result: dict) -> list[dict]:
    return [e for e in (result.get("events") or []) if e.get("type") == EVT_QUOTA_EXHAUSTED]


def main() -> int:
    doc = _load_art()
    declared = json.loads(FIX.read_text(encoding="utf-8"))
    if declared["quota_bad"] != QUOTA_BAD or declared["n_rounds"] != N_ROUNDS:
        print("FAILED:CNL-0018-probe1 fixture drift vs mechanism constants")
        return 1

    bad = simulate_council(
        ROSTER_DIVERSE,
        QUOTA_BAD,
        N_ROUNDS,
        "high-stakes",
        attempt_same_vendor_reseat=True,
    )
    good = simulate_council(
        ROSTER_DIVERSE,
        QUOTA_GOOD,
        N_ROUNDS,
        "high-stakes",
        attempt_same_vendor_reseat=True,
    )
    recount_bad = independent_quota_recount(ROSTER_DIVERSE, QUOTA_BAD, N_ROUNDS)
    recount_good = independent_quota_recount(ROSTER_DIVERSE, QUOTA_GOOD, N_ROUNDS)

    bad_loud = _loud(bad)
    good_loud = _loud(good)
    refused = [
        e for e in (bad.get("events") or []) if e.get("type") == EVT_SUBSTITUTION_REFUSED
    ]

    if len(bad_loud) < 1:
        print("FAILED:CNL-0018-probe1 BAD state did not fire QUOTA-EXHAUSTED")
        print(json.dumps(bad, indent=2, default=str)[:3000])
        return 1
    if not all(e.get("loud") is True for e in bad_loud):
        print("FAILED:CNL-0018-probe1 exhaustion event was not loud")
        return 1
    if bad.get("reseated_same_vendor") is True:
        print("FAILED:CNL-0018-probe1 silently re-seated same vendor")
        return 1
    if not refused:
        print("FAILED:CNL-0018-probe1 substitution was not refused")
        return 1
    partial = bad.get("partial_artifact") or {}
    turns = partial.get("turns") or []
    if len(turns) < 1:
        print("FAILED:CNL-0018-probe1 partial artifact empty")
        return 1
    if not recount_bad.get("would_exhaust"):
        print("FAILED:CNL-0018-probe1 independent recount missed exhaustion")
        return 1
    if int(recount_bad["turns_before"]) != len(turns):
        print(
            "FAILED:CNL-0018-probe1 signal disagreement "
            f"simulate_turns={len(turns)} recount={recount_bad['turns_before']}"
        )
        return 1
    if good_loud:
        print("FAILED:CNL-0018-probe1 GOOD state not silent")
        print(json.dumps(good_loud, indent=2)[:2000])
        return 1
    if good.get("terminal") != "SUCCESS" or good.get("independence_void") is True:
        print("FAILED:CNL-0018-probe1 GOOD terminal not clean")
        return 1
    if recount_good.get("would_exhaust"):
        print("FAILED:CNL-0018-probe1 independent recount false-exhausted GOOD")
        return 1
    want_turns_good = N_ROUNDS * len(ROSTER_DIVERSE)
    got_turns_good = len((good.get("partial_artifact") or {}).get("turns") or [])
    if got_turns_good != want_turns_good:
        print(f"FAILED:CNL-0018-probe1 GOOD turns={got_turns_good} want={want_turns_good}")
        return 1
    vendors_after = bad.get("final_roster_vendors") or []
    if vendors_after.count("anthropic") > 1:
        print("FAILED:CNL-0018-probe1 anthropic seated twice after exhaustion")
        return 1

    recorded = doc.get("quota_exhaustion_control") or {}
    if recorded.get("bad_fired") is not True or recorded.get("good_silent") is not True:
        print("FAILED:CNL-0018-probe1 artifact missing both-states record")
        return 1
    if int(recorded.get("turns_preserved_on_bad") or -1) != len(turns):
        print("FAILED:CNL-0018-probe1 artifact turns_preserved drift")
        return 1

    verbatim = (
        "NEGATIVE CONTROL (quota): the check FIRES on planted exhaustion "
        f"(openai remaining=1, {N_ROUNDS} rounds) with {len(bad_loud)} "
        "QUOTA-EXHAUSTED event(s), preserves the partial transcript "
        f"({len(turns)} turns), and refuses same-vendor reseat "
        f"({len(refused)} SUBSTITUTION-REFUSED). The check is SILENT on the "
        "known-good remaining map (both vendors=100): zero QUOTA-EXHAUSTED "
        f"events, terminal={good.get('terminal')}, independence_void="
        f"{good.get('independence_void')}."
    )
    out = {
        "probe": "probe1-quota-exhaustion",
        "unit_id": "CNL-0018",
        "bad_fired": True,
        "good_silent": True,
        "turns_preserved": len(turns),
        "reseated_same_vendor": False,
        "substitution_refused": True,
        "recount_turns_before": recount_bad["turns_before"],
        "pass": True,
        "negative_control_verbatim": verbatim,
    }
    print(json.dumps(out, sort_keys=True))
    print(verbatim)
    print("SUCCESS:CNL-0018-probe1 quota-exhaustion both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
