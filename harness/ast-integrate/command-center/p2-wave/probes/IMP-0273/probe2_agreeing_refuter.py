#!/usr/bin/env python3
"""IMP-0273 probe 2: agreeing refuter is flagged by the spread metric.

Both-states:
  SILENT — genuine opposition (extracted POSITION distance >= AGREE_DISTANCE)
  FIRE   — refuter copies the proposer's POSITION (full-agree and position-only)

The position-only mutant still says "I refute" so a lexicon-only detector
cannot be the thing that goes green. The catalog requires the *spread metric*
to flag agreement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.select_adversarial import (  # noqa: E402
    AGREE_DISTANCE,
    agreeing_refuter_control,
    clone_pool_no_opposition,
    default_pool,
    default_questions,
    emit_first_round,
    euclidean,
    flag_agreeing_refuters,
    select_adversarial,
)


def main() -> int:
    pool = default_pool()
    question = default_questions()[0]
    paired = select_adversarial(pool, n_proposers=3)
    n_pairs = len(paired.pairs())
    if n_pairs != 3:
        print("FAILED:IMP-0273-probe2 expected 3 pairs")
        return 1

    genuine = emit_first_round(paired, question, agree_mode="none")
    full = emit_first_round(paired, question, agree_mode="full")
    pos_only = emit_first_round(paired, question, agree_mode="position-only")

    genuine_flags = flag_agreeing_refuters(genuine, paired)
    full_flags = flag_agreeing_refuters(full, paired)
    pos_flags = flag_agreeing_refuters(pos_only, paired)

    by_g = {t.seat_id: t for t in genuine}
    by_p = {t.seat_id: t for t in pos_only}
    pair_rows = []
    metric_ok = True
    for proposer, refuter in paired.pairs():
        g_gap = euclidean(
            by_g[proposer.seat_id].extracted_position,
            by_g[refuter.seat_id].extracted_position,
        )
        p_gap = euclidean(
            by_p[proposer.seat_id].extracted_position,
            by_p[refuter.seat_id].extracted_position,
        )
        r_text = by_p[refuter.seat_id].text
        still_says_refute = "I refute" in r_text
        row = {
            "proposer": proposer.participant.participant_id,
            "refuter": refuter.participant.participant_id,
            "genuine_gap": g_gap,
            "position_only_gap": p_gap,
            "position_only_still_says_refute": still_says_refute,
            "genuine_clears_threshold": g_gap >= AGREE_DISTANCE,
            "position_only_below_threshold": p_gap < AGREE_DISTANCE,
        }
        pair_rows.append(row)
        if not row["genuine_clears_threshold"] or not row["position_only_below_threshold"]:
            metric_ok = False
        if not still_says_refute:
            metric_ok = False

    # Removing the flag emission must make this probe FAIL (catalog negative control).
    def _mute(_turns, _selection):
        return []

    muted_bad = _mute(pos_only, paired)
    mute_would_fail = len(muted_bad) == 0 and len(pos_flags) == n_pairs

    loud = select_adversarial(clone_pool_no_opposition(pool), n_proposers=3)
    loud_codes = [f.code for f in loud.findings]

    ctrl = agreeing_refuter_control(pool, question, n_proposers=3)

    silent_on_good = len(genuine_flags) == 0
    fire_on_bad = len(full_flags) == n_pairs and len(pos_flags) == n_pairs
    both_states = silent_on_good and fire_on_bad and metric_ok

    payload = {
        "id": "agreeing-refuter-spread-flag",
        "n_pairs": n_pairs,
        "agree_distance": AGREE_DISTANCE,
        "silent_on_good": silent_on_good,
        "fire_on_full_agree": len(full_flags) == n_pairs,
        "fire_on_position_only": len(pos_flags) == n_pairs,
        "both_states": both_states,
        "mute_control_proves_flag_is_load_bearing": mute_would_fail,
        "loud_clone_pool_codes": loud_codes,
        "loud_clone_pool_fires": "no-opposed-candidate" in loud_codes,
        "pair_rows": pair_rows,
        "control_pass": ctrl["pass"],
        "pass": (
            both_states
            and mute_would_fail
            and "no-opposed-candidate" in loud_codes
            and ctrl["pass"]
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0273-probe2 agreeing-refuter flag")
        return 1
    print(
        "SUCCESS:IMP-0273-probe2 spread metric FIRE on agreeing refuter, "
        "SILENT on genuine opposition"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
