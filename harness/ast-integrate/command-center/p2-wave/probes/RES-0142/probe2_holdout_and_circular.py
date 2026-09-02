#!/usr/bin/env python3
"""Probe 2: holdout of 8, circularity, both-states control. Defaults to FAIL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    diverse_sources,
    mutant_report,
    near_identical_sources,
)
from score import (  # noqa: E402
    load_fields,
    load_labels,
    load_prereg,
    score_issue,
    score_run,
    score_run_string_equality,
    split_and_score,
    token_counter_fire,
)

ART = REPO / (
    "command-center/research/sources-frontier/"
    "RES-0142-issue-tracker-blocker-signal-model.json"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def independent_fire(yields, window, floor, min_sources):
    """Inline rolling-mean recount. Deliberately not score.fire_index_from_yields."""
    n = len(yields)
    start = max(int(min_sources), int(window))
    for t in range(start, n + 1):
        chunk = yields[t - window : t]
        if len(chunk) < window:
            continue
        mean = sum(chunk) / float(window)
        if mean <= float(floor) + 1e-12:
            return t
    return None


def main() -> int:
    prereg = load_prereg()
    window = int(prereg["window"])
    floor = float(prereg["floor"])
    min_sources = int(prereg["min_sources"])
    early_max = int(prereg["early_max_index"])
    budget = int(prereg["token_counter_foil_budget_tokens"])

    split = split_and_score()
    hold = split["holdout"]["metrics"]
    train = split["train"]["metrics"]
    if hold["n"] != 8:
        print("REFUTED:RES-0142-probe2 holdout n != 8")
        return 1
    if train["n"] != 17:
        print("REFUTED:RES-0142-probe2 train n != 17")
        return 1
    if hold["positives"] != 0:
        print("REFUTED:RES-0142-probe2 unexpected holdout positives")
        return 1
    if split["in_sample_only_status"] != "NOT VALIDATED":
        print("REFUTED:RES-0142-probe2 in-sample-only was not marked NOT VALIDATED")
        return 1

    # Circularity: dummy titles must not change scores.
    fields = load_fields()
    labels = load_labels()
    if len(labels.get("labels") or {}) != 25:
        print("REFUTED:RES-0142-probe2 label count != 25")
        return 1
    for iid, issue in fields.items():
        a = score_issue(issue, prereg)
        shuffled = dict(issue)
        shuffled["dummy_title"] = f"shuffled-title-for-{iid}"
        shuffled["body"] = "this body must not affect the score"
        shuffled["title"] = "BLOCKER BLOCKER BLOCKER"
        b = score_issue(shuffled, prereg)
        if a != b:
            print(f"REFUTED:RES-0142-probe2 title/body changed score for {iid}")
            return 1

    near = score_run(near_identical_sources(), prereg)
    div = score_run(diverse_sources(), prereg)
    near_idx = independent_fire(near["yields"], window, floor, min_sources)
    div_idx = independent_fire(div["yields"], window, floor, min_sources)
    near_str = score_run_string_equality(near_identical_sources(), prereg)
    token_near = token_counter_fire(near_identical_sources(), budget)
    token_div = token_counter_fire(diverse_sources(), budget)
    mutants = mutant_report()

    if near_idx != near["fire_index"] or not near["early"] or near_idx is None or near_idx > early_max:
        print(f"REFUTED:RES-0142-probe2 near-identical early fire failed idx={near_idx}")
        return 1
    if div["fired"] or div_idx is not None:
        print(f"REFUTED:RES-0142-probe2 diverse fired idx={div_idx}")
        return 1
    if near_str["fired"]:
        print("REFUTED:RES-0142-probe2 string-equality fired on paraphrases")
        return 1
    if token_near is None or token_div is None:
        print("REFUTED:RES-0142-probe2 token foil silent on a corpus")
        return 1
    if not mutants["pass"]:
        print("REFUTED:RES-0142-probe2 mutants failed")
        return 1

    if not ART.is_file():
        print("REFUTED:RES-0142-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"REFUTED:RES-0142-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0142" not in text:
        print("REFUTED:RES-0142-probe2 sentinel-absent")
        return 1
    if "NOT VALIDATED" not in text:
        print("REFUTED:RES-0142-probe2 artifact omits NOT VALIDATED")
        return 1
    art_hold = ((doc.get("split") or {}).get("holdout_metrics") or {})
    if int(art_hold.get("n") or -1) != 8:
        print("REFUTED:RES-0142-probe2 artifact holdout n != 8")
        return 1
    if art_hold.get("fp") != hold["fp"] or art_hold.get("tn") != hold["tn"]:
        print(
            f"REFUTED:RES-0142-probe2 holdout metrics drifted art={art_hold} live={hold}"
        )
        return 1
    art_in = (doc.get("split") or {}).get("in_sample_only_status")
    if art_in != "NOT VALIDATED":
        print("REFUTED:RES-0142-probe2 artifact in-sample status drifted")
        return 1
    nc = doc.get("negative_controls") or {}
    if (nc.get("near_identical") or {}).get("early") is not True:
        print("REFUTED:RES-0142-probe2 artifact near-identical not early")
        return 1
    if (nc.get("diverse") or {}).get("fired") is True:
        print("REFUTED:RES-0142-probe2 artifact diverse fired")
        return 1

    print(
        json.dumps(
            {
                "holdout_n": hold["n"],
                "holdout_fp": hold["fp"],
                "holdout_tn": hold["tn"],
                "train_fp": train["fp"],
                "in_sample_only_status": split["in_sample_only_status"],
                "near_fired": near["fired"],
                "near_index": near["fire_index"],
                "near_recount": near_idx,
                "diverse_fired": div["fired"],
                "string_equality_fired": near_str["fired"],
                "token_near": token_near,
                "token_div": token_div,
                "mutants": mutants["pass"],
                "title_shuffle_invariant": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"holdout n=8 fp={hold['fp']} tn={hold['tn']} "
        f"in_sample_only=NOT VALIDATED near_early={near['early']} "
        f"diverse_silent={not div['fired']}"
    )
    print("SUCCESS:RES-0142-probe2 holdout, circularity, both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
