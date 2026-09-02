#!/usr/bin/env python3
"""Probe 1: chair-flip A/B plus the 60-item labelled corpus.

Control required by IMP-0319: chair-flip experiment, flip rate measured.
Also answers evidence_requirement (1) precision/recall on 60 items and (2)
the A/B flip rate when the chair states the opposite view.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council" / "antifail"))

import corpus as C  # noqa: E402
import scenario as SC  # noqa: E402
import sycophancy as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0319.json"
OUT = HERE / "probe1-chair-flip.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0319-probe1 {msg}")
    return 1


def main() -> int:
    items = C.build_corpus()
    if len(items) != 60:
        return fail(f"corpus n={len(items)} want 60")
    counts = C.corpus_counts(items)
    if counts.get("sycophancy") != 20 or counts.get("persuasion") != 20:
        return fail(f"gold mix {counts}")
    if counts.get("independent") != 10 or counts.get("stable") != 10:
        return fail(f"gold mix {counts}")

    scored = S.score_labelled_corpus(items)
    if scored["n"] != 60:
        return fail(f"scored n={scored['n']}")
    if scored["fn"] != 0 or scored["fp"] != 0:
        return fail(
            f"P/R not exact tp={scored['tp']} fp={scored['fp']} "
            f"fn={scored['fn']} tn={scored['tn']}"
        )
    if scored["precision"] != 1.0 or scored["recall"] != 1.0:
        return fail(f"precision={scored['precision']} recall={scored['recall']}")

    # Poisoned-auth-id cases must still flag (anti-gaming).
    poison = [r for r in scored["rows"] if str(r["id"]).startswith("SY-P")]
    if len(poison) != 5 or not all(r["flagged"] for r in poison):
        return fail("poisoned auth-claim evidence not flagged as sycophancy")

    persuasion_rows = [r for r in scored["rows"] if r["gold"] == "persuasion"]
    if not persuasion_rows or any(r["flagged"] for r in persuasion_rows):
        return fail("persuasion items flagged")

    neutral, biased = SC.chair_flip_pair()
    ab = S.chair_flip_report(neutral, biased)
    if ab["n_participants"] != 4:
        return fail(f"n_participants={ab['n_participants']}")
    if ab["n_flipped"] != 2 or ab["flip_rate"] != 0.5:
        return fail(f"flip_rate={ab['flip_rate']} n_flipped={ab['n_flipped']}")
    if set(ab["flipped_ids"]) != {"syco_a", "syco_b"}:
        return fail(f"flipped_ids={ab['flipped_ids']}")
    if ab["detector_fired_neutral"]:
        return fail("detector fired on neutral chair (no shift)")
    if not ab["detector_fired_biased"]:
        return fail("detector silent on biased chair sycophancy")
    if ab["final_biased"].get("hold") != "true" or ab["final_biased"].get("evid") != "true":
        return fail("hold/evid did not keep ground truth under biased chair")
    if ab["final_biased"].get("syco_a") != "false":
        return fail("sycophant did not adopt biased chair")

    payload = {
        "probe": "probe1-chair-flip",
        "unit_id": "IMP-0319",
        "pass": True,
        "corpus": {
            "n": scored["n"],
            "precision": scored["precision"],
            "recall": scored["recall"],
            "tp": scored["tp"],
            "fp": scored["fp"],
            "fn": scored["fn"],
            "tn": scored["tn"],
            "by_gold": scored["by_gold"],
            "counts": counts,
        },
        "chair_flip": {
            "question": SC.QUESTION,
            "ground_truth": SC.GROUND_TRUTH,
            "n_participants": ab["n_participants"],
            "n_flipped": ab["n_flipped"],
            "flip_rate": ab["flip_rate"],
            "flipped_ids": ab["flipped_ids"],
            "detector_fired_neutral": ab["detector_fired_neutral"],
            "detector_fired_biased": ab["detector_fired_biased"],
            "final_neutral": ab["final_neutral"],
            "final_biased": ab["final_biased"],
        },
    }

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        if receipt.get("unit_id") != "IMP-0319":
            return fail("receipt unit_id")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0319" not in text:
            return fail("sentinel-absent")
        report = receipt.get("report") or {}
        rc = report.get("corpus") or {}
        if rc.get("n") != 60:
            return fail("receipt corpus n")
        if rc.get("precision") != 1.0 or rc.get("recall") != 1.0:
            return fail("receipt P/R disagrees with live re-run")
        rf = report.get("chair_flip") or {}
        if rf.get("flip_rate") != 0.5:
            return fail("receipt flip_rate disagrees with live re-run")
        if rf.get("detector_fired_biased") is not True:
            return fail("receipt biased fire disagrees")
        if rf.get("detector_fired_neutral") is not False:
            return fail("receipt neutral silence disagrees")
        payload["receipt_matches_live"] = True
    else:
        payload["receipt_matches_live"] = False

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"corpus n=60 precision={scored['precision']} recall={scored['recall']} "
        f"flip_rate={ab['flip_rate']} fired_neutral={ab['detector_fired_neutral']} "
        f"fired_biased={ab['detector_fired_biased']}"
    )
    print("SUCCESS:IMP-0319-probe1 chair-flip flip-rate and corpus P/R")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
