#!/usr/bin/env python3
"""Named probe 2: first-speaker effect (20 matched runs) + biased-order control.

Independent of the author's summary: re-runs the public experiment APIs and
re-tallies the unique-preference fixture by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.order import (  # noqa: E402
    EXPERIMENT_N,
    first_speaker_experiment,
    negative_control_biased_order,
)

ART = REPO / "command-center/receipts/IMP-0337.json"


def hand_tally_biased() -> dict:
    """Recompute the negative-control fixture without calling decide_anchored.

    W,X,Y adopt; Z reject. Round-robin sequence W,X,Y,Z. Biased Z,W,X,Y.
    Bonus 3. Each speaker 1 vote; first speaker +3.
    """
    rr_adopt = 1 + 3 + 1 + 1  # W first
    rr_reject = 1
    biased_adopt = 1 + 1 + 1  # W,X,Y after Z
    biased_reject = 1 + 3  # Z first
    blind_adopt = 3
    blind_reject = 1
    return {
        "rr_winner": "adopt" if rr_adopt > rr_reject else "reject",
        "biased_winner": "reject" if biased_reject > biased_adopt else "adopt",
        "blind_winner": "adopt" if blind_adopt > blind_reject else "reject",
        "rr_scores": {"adopt": rr_adopt, "reject": rr_reject},
        "biased_scores": {"adopt": biased_adopt, "reject": biased_reject},
        "blind_scores": {"adopt": blind_adopt, "reject": blind_reject},
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0337-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0337" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0337-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0337-probe2 self-declared", doc.get("state"))
        return 1

    exp = first_speaker_experiment()
    neg = negative_control_biased_order()
    hand = hand_tally_biased()

    reasons = []
    if exp["n_matched_pairs"] != EXPERIMENT_N:
        reasons.append(f"n={exp['n_matched_pairs']} want={EXPERIMENT_N}")
    if not exp["all_prefs_matched"]:
        reasons.append("a matched pair mutated prefs")
    if not exp["all_first_speakers_differ"]:
        reasons.append("a matched pair kept the same first speaker")
    if any(p["order_a"] == p["order_b"] for p in exp["pairs"]):
        reasons.append("a matched pair reused the same order")
    if not neg["fired_on_biased_order"]:
        reasons.append("biased order did not change the winner")
    if not neg["silent_on_order_blind"]:
        reasons.append("order-blind aggregator still flipped (detector failure)")
    if not neg["detectable_effect"]:
        reasons.append("negative control not detectable")
    if hand["rr_winner"] != neg["winner_round_robin"]:
        reasons.append(
            f"hand rr {hand['rr_winner']} != module {neg['winner_round_robin']}"
        )
    if hand["biased_winner"] != neg["winner_biased"]:
        reasons.append(
            f"hand biased {hand['biased_winner']} != module {neg['winner_biased']}"
        )
    if hand["blind_winner"] != neg["winner_round_robin_order_blind"]:
        reasons.append("hand order-blind disagrees")
    if hand["rr_winner"] == hand["biased_winner"]:
        reasons.append("hand tally itself shows no biased-order effect")

    published = {
        "probe": "probe2-first-speaker",
        "unit_id": "IMP-0337",
        "n_matched_pairs": exp["n_matched_pairs"],
        "flip_count": exp["flip_count"],
        "flip_rate": exp["flip_rate"],
        "pearson_first_speaker_vs_alignment": exp[
            "pearson_first_speaker_vs_alignment"
        ],
        "alignment_rate_first_speaker": exp["alignment_rate_first_speaker"],
        "alignment_rate_not_first": exp["alignment_rate_not_first"],
        "first_speaker_alignment_delta": exp["first_speaker_alignment_delta"],
        "counts": exp["counts"],
        "negative_control": {
            "fired_on_biased_order": neg["fired_on_biased_order"],
            "silent_on_order_blind": neg["silent_on_order_blind"],
            "winner_round_robin": neg["winner_round_robin"],
            "winner_biased": neg["winner_biased"],
            "hand": hand,
        },
        "pass": not reasons,
        "reasons": reasons,
    }
    print(json.dumps(published, sort_keys=True))
    if reasons:
        print("FAILED:IMP-0337-probe2", "; ".join(reasons))
        return 1
    print(
        "SUCCESS:IMP-0337-probe2 first-speaker effect published; "
        "biased-order negative control fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
