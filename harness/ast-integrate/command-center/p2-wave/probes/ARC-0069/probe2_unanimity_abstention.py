#!/usr/bin/env python3
"""Probe 2: instant unanimity, abstention validity, independence of submissions."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import FIXTURE_ENTRIES  # noqa: E402
from judges import (  # noqa: E402
    apply_nameless_abstention_rule,
    dimension_signature,
    forced_dissent,
    score_entry,
)
from round import unanimous_entries  # noqa: E402

ART = REPO / "command-center/phase3/SCORECARDS.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0069-probe2 SCORECARDS.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    indep = doc.get("independence") or {}
    if indep.get("peer_scores_readable_before_submission") is not False:
        print("FAILED:ARC-0069-probe2 peer scores were readable before submission")
        return 1
    isolation = indep.get("isolation") or []
    if len(isolation) < 3:
        print(f"FAILED:ARC-0069-probe2 isolation rows={len(isolation)}")
        return 1
    if isolation[0].get("peer_dirs_unread") != []:
        print("FAILED:ARC-0069-probe2 first judge was not isolated")
        return 1
    if "J-A" not in (isolation[1].get("peer_dirs_unread") or []):
        print("FAILED:ARC-0069-probe2 second judge isolation")
        return 1
    cards = doc.get("scorecards") or []
    if any(c.get("peer_scorecards_in_read_set") for c in cards):
        print("FAILED:ARC-0069-probe2 peer scorecard leaked into a read set")
        return 1
    print("independence peer_unread=True serialized=True")

    dossier = copy.deepcopy(FIXTURE_ENTRIES["E-07"])
    identical = score_entry("J-A", dossier)
    planted = []
    for jid in ("J-A", "J-B", "J-C"):
        planted.append(
            {
                "judge_id": jid,
                "entry_id": "E-SYN",
                "dimensions": copy.deepcopy(identical),
            }
        )
    triggered = unanimous_entries(planted)
    print(f"synthetic_unanimity triggered={triggered}")
    if triggered != ["E-SYN"]:
        print("FAILED:ARC-0069-probe2 planted unanimity did not trigger")
        return 1
    sigs_first = {dimension_signature(c["dimensions"]) for c in planted}
    if len(sigs_first) != 1:
        print("FAILED:ARC-0069-probe2 planted cards were not identical")
        return 1
    reeval = []
    for card in planted:
        card["standing"] = False
        dims = apply_nameless_abstention_rule(
            forced_dissent(card["judge_id"], card["dimensions"])
        )
        reeval.append(dims)
    sigs_after = {dimension_signature(d) for d in reeval}
    print(f"forced_dissent distinct_signatures={len(sigs_after)}")
    if len(sigs_after) < 2:
        print("FAILED:ARC-0069-probe2 forced dissent left scores unanimous")
        return 1
    if unanimous_entries(
        [{"entry_id": "E-SYN", "dimensions": d} for d in reeval]
    ):
        print("FAILED:ARC-0069-probe2 re-eval still unanimous on every dimension")
        return 1

    named = {
        "correctness": {
            "score": None,
            "abstention": True,
            "missing_evidence": "failure_modes section absent from dossier",
            "citation": "failure_modes",
        }
    }
    named_out = apply_nameless_abstention_rule(named)
    if named_out["correctness"].get("recorded_as_zero") or named_out["correctness"].get("score") is not None:
        print("FAILED:ARC-0069-probe2 named abstention was zeroed")
        return 1
    nameless = {
        "correctness": {
            "score": None,
            "abstention": True,
            "missing_evidence": "",
            "citation": "design",
        }
    }
    zeroed = apply_nameless_abstention_rule(nameless)
    if not zeroed["correctness"].get("recorded_as_zero") or zeroed["correctness"].get("score") != 0:
        print(f"FAILED:ARC-0069-probe2 nameless abstention not zeroed {zeroed}")
        return 1
    print("abstention named_preserved=True nameless_zero=True")

    live_trigger = (doc.get("instant_unanimity") or {}).get("entries_triggered")
    print(f"live_round_triggered={live_trigger}")
    print("SUCCESS:ARC-0069-probe2 unanimity abstention independence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
