#!/usr/bin/env python3
"""Probe 2: asymmetric cost vs balanced accuracy; versioned threshold.

Evidence B: the chosen point is NOT the balanced-accuracy point. Balanced
accuracy collapses two-directional unique-content pairs (the dangerous
error). The asymmetric-cost point does not.

Both-states: good threshold (chosen) is silent on two-dir pairs; the
balanced-accuracy threshold fires on them.

Independent reviewer: this probe did not author the labelled set; it
re-runs both policies against live scores.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibrate import calibrate  # noqa: E402
from labelled_pairs import labelled_pairs  # noqa: E402

UNIT = "WFA-0098"
ART = REPO / "command-center/wfa/WFA-0098-duplicate-threshold-calibration.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def collapsed_ids(threshold: float, pairs: list[dict]) -> list[str]:
    return [p["pair_id"] for p in pairs if p["jaccard"] >= threshold]


def two_dir_collapsed(threshold: float, pairs: list[dict]) -> list[str]:
    return [
        p["pair_id"]
        for p in pairs
        if p["two_directional_divergence"] and p["jaccard"] >= threshold
    ]


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0098" not in text:
        return fail("sentinel absent")

    cal = calibrate()
    pairs = labelled_pairs()
    chosen_t = float(cal["chosen"]["threshold"])
    ba_t = float(cal["balanced_accuracy_point"]["threshold"])
    art_t = float(
        ((doc.get("calibration") or {}).get("chosen") or {}).get("threshold")
    )
    if art_t != chosen_t:
        return fail(f"artifact threshold {art_t} != live {chosen_t}")

    if chosen_t == ba_t:
        return fail("balanced accuracy and asymmetric cost picked the same threshold")
    if cal["chosen"]["two_dir_false_collapses"] != 0:
        return fail("chosen point still collapses two-dir pairs")
    if cal["balanced_accuracy_point"]["two_dir_false_collapses"] < 1:
        return fail("balanced-accuracy point did not collapse any two-dir pair")

    good_fires = two_dir_collapsed(chosen_t, pairs)
    bad_fires = two_dir_collapsed(ba_t, pairs)
    print(
        f"both_states good_t={chosen_t} two_dir_fires={len(good_fires)} "
        f"bad_t={ba_t} two_dir_fires={len(bad_fires)}"
    )
    if good_fires:
        return fail(f"good state fired on two-dir {good_fires}")
    if not bad_fires:
        return fail("bad state (balanced accuracy) silent on two-dir pairs")

    version = cal["threshold_version"]
    if not version.get("recompute_on_change"):
        return fail("threshold not marked recompute_on_change")
    if not str(version.get("id") or "").endswith(".v1"):
        return fail(f"threshold version {version.get('id')}")

    # Simulate a threshold change: decisions that flip must be re-listed.
    mutant_t = round(chosen_t - 0.05, 4)
    before = set(collapsed_ids(chosen_t, pairs))
    after = set(collapsed_ids(mutant_t, pairs))
    flipped = sorted(before ^ after)
    print(f"versioned_change from={chosen_t} to={mutant_t} flipped={len(flipped)}")
    if not flipped:
        return fail("threshold change produced no flipped collapses (vacuous versioning)")
    newly_two_dir = [p for p in flipped if p in set(two_dir_collapsed(mutant_t, pairs))]
    print(f"change_would_newly_collapse_two_dir={newly_two_dir}")

    art_div = (doc.get("calibration") or {}).get("policy_divergence") or {}
    if not art_div.get("chosen_differs_from_balanced_accuracy"):
        return fail("artifact does not record policy divergence")
    if not art_div.get("two_dir_collapsed_at_balanced_accuracy"):
        return fail("artifact missing two-dir collapses at BA point")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("reviewer block incomplete")
    if reviewer.get("both_states_rerun") is not True:
        return fail("reviewer did not record both-states rerun")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-asymmetric-cost",
                "unit_id": UNIT,
                "reviewer_id": "WFA-0098-probe2-asymmetric-cost",
                "reviewer_verdict": "PASS",
                "independent": True,
                "chosen_threshold": chosen_t,
                "balanced_accuracy_threshold": ba_t,
                "good_state_two_dir_fires": len(good_fires),
                "bad_state_two_dir_fires": len(bad_fires),
                "flipped_on_version_change": len(flipped),
                "false_collapse_rate_chosen": cal["chosen"]["false_collapse_rate"],
                "false_split_rate_chosen": cal["chosen"]["false_split_rate"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0098-probe2 asymmetric cost both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
