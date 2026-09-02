#!/usr/bin/env python3
"""Probe 1: corrupted-judge fixture; compute how many roles must be corrupted.

One bad judge must not determine the outcome under separation. The threshold
is recomputed here by enumerating role subsets, then compared to the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import separation as S  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0026-judge-and-juror-separation-to-remove-the-single-epistemic-.md"
)
FIX = HERE / "fixtures" / "corrupted-judge-separated.json"


def load_fixture() -> dict:
    return json.loads(FIX.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNL-0026-probe1 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0026":
        print("FAILED:CNL-0026-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0026" not in text:
        print("FAILED:CNL-0026-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0026-probe1 self-declared", doc.get("state"))
        return 1

    fx = load_fixture()
    ballots = list(fx["juror_ballots"])
    judge_wrong = fx["judge_value"]
    if fx["mode"] != "separated" or judge_wrong != S.REJECT:
        print("FAILED:CNL-0026-probe1 fixture is not corrupted-judge-separated")
        return 1
    published = S.publish_separated(ballots, judge_wrong)
    if published["outcome"] != S.SUPPORT:
        print("FAILED:CNL-0026-probe1 bad judge determined outcome", published)
        return 1
    if published["certification_accepted"] is True:
        print("FAILED:CNL-0026-probe1 bad certification was accepted")
        return 1

    honest_ballots, honest_judge = S.honest_unanimous_panel()
    cut = S.min_corrupting_sets("separated", honest_ballots, honest_judge)
    fused = S.min_corrupting_sets("fused", honest_ballots, honest_judge)
    if cut["min_k"] != S.majority_need(S.N_JURORS):
        print("FAILED:CNL-0026-probe1 brute-force min_k != floor(N/2)+1", cut)
        return 1
    if cut["judge_alone_flips"] is True:
        print("FAILED:CNL-0026-probe1 judge-alone flips under separation")
        return 1
    if cut["judge_in_any_min_set"] is True:
        print("FAILED:CNL-0026-probe1 judge sits in a minimum corrupting set")
        return 1
    if fused["min_k"] != 1 or fused["judge_alone_flips"] is not True:
        print("FAILED:CNL-0026-probe1 fused baseline broken", fused)
        return 1

    claimed = doc.get("corruption_threshold") or {}
    if claimed.get("value") != cut["min_k"]:
        print(
            "FAILED:CNL-0026-probe1 artifact threshold drift "
            f"claimed={claimed.get('value')} live={cut['min_k']}"
        )
        return 1
    if claimed.get("computed_not_asserted") is not True:
        print("FAILED:CNL-0026-probe1 threshold was not marked computed")
        return 1
    if not claimed.get("formula_matches_brute_force"):
        print("FAILED:CNL-0026-probe1 formula/brute-force disagreement")
        return 1

    hung = S.hung_control()
    if not hung["pass"]:
        print("FAILED:CNL-0026-probe1 hung control", hung)
        return 1
    dissent = S.dissent_control()
    if not dissent["pass"]:
        print("FAILED:CNL-0026-probe1 dissent control", dissent)
        return 1

    out = {
        "probe": "probe1-corrupted-judge",
        "unit_id": "CNL-0026",
        "bad_judge_outcome": published["outcome"],
        "bad_judge_cert_accepted": published["certification_accepted"],
        "min_k_separated": cut["min_k"],
        "min_k_fused": fused["min_k"],
        "subsets_examined": cut["subsets_examined"],
        "judge_in_any_min_set": cut["judge_in_any_min_set"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"corrupted_judge_separated outcome={published['outcome']} "
        f"cert_accepted={published['certification_accepted']} "
        f"min_k={cut['min_k']} fused_min_k={fused['min_k']} "
        f"examined={cut['subsets_examined']}"
    )
    print("SUCCESS:CNL-0026-probe1 corrupted-judge fixture and computed threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
