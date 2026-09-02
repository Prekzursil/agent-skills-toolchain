#!/usr/bin/env python3
"""Probe 2: independent recount, threshold-adversary, named blind spot.

Reviewer path is BFS connected components (not the author's union-find).
The adversarial generator's last at-or-above-threshold pair must merge
under S1. Deep paraphrase and a genuine distinct control must occupy the
same lexical band. Schema must reject garbage. Stripping the recorded
gamed unique_count (or claiming it is 100) must make the honesty check
fail — a probe silent in both states measures nothing.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import counter as C  # noqa: E402
import fixtures as F  # noqa: E402
import measure as M  # noqa: E402
from payload import payload  # noqa: E402
from schema_check import load_validator, schema_errors  # noqa: E402

ART = REPO / "command-center/research/RES-0084.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def honesty(doc: dict) -> tuple[bool, str]:
    pay = payload(doc)
    rec_g = (pay.get("recorded_runs") or {}).get("known_broken") or {}
    rec_d = (pay.get("recorded_runs") or {}).get("known_good") or {}
    g = rec_g.get("author_union_find")
    d = rec_d.get("author_union_find")
    if g is None or d is None:
        return False, "missing-recorded-counts"
    if g >= 100:
        return False, "gamed-accepted-100"
    if d < 100:
        return False, "distinct-rejected-100"
    if not (pay.get("both_states") or {}).get("discriminates"):
        return False, "both-states-not-discriminating"
    bs = pay.get("blind_spot") or {}
    if bs.get("id") != "RES-0084-DEEP-PARAPHRASE-BAND":
        return False, "blind-spot-id-absent"
    if pay.get("measured_threshold") is None:
        return False, "threshold-absent"
    return True, "ok"


def _plant_gamed_100(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    report = mutant.get("report") if isinstance(mutant.get("report"), dict) else None
    target = report if report is not None else mutant
    runs = target.setdefault("recorded_runs", {})
    broken = runs.setdefault("known_broken", {})
    broken["author_union_find"] = 100
    both = target.setdefault("both_states", {})
    both["discriminates"] = True
    return mutant


def main() -> int:
    live = M.run()
    gamed_ideas = F.gamed_corpus(100)
    distinct_ideas = F.distinct_corpus()
    thresh = live["measured_threshold"]

    author_g = C.unique_count_union_find(gamed_ideas, thresh)
    review_g = C.unique_count_connected_components(gamed_ideas, thresh)
    author_d = C.unique_count_union_find(distinct_ideas, thresh)
    review_d = C.unique_count_connected_components(distinct_ideas, thresh)
    if author_g != review_g or author_d != review_d:
        print(
            f"FAILED:RES-0084-probe2 reviewer mismatch "
            f"gamed {author_g}/{review_g} distinct {author_d}/{review_d}"
        )
        return 1
    if author_g >= 100 or author_d < 100:
        print("FAILED:RES-0084-probe2 reviewer both-states failed")
        return 1

    adv = live["adversarial_generator"]
    if adv["survives_at_threshold"] is not True:
        print("FAILED:RES-0084-probe2 generator pair at threshold did not merge")
        return 1
    last = adv["last_at_or_above_threshold"]
    if last is None or last["jaccard_vs_seed"] < thresh:
        print("FAILED:RES-0084-probe2 no at-threshold ladder step")
        return 1
    if C.unique_count_jaccard_only([F.SEED, last["text"]], thresh) != 1:
        print("FAILED:RES-0084-probe2 S1 did not merge the at-threshold pair")
        return 1

    settle = live["blind_spot"]["settling_experiment"]
    if not settle["same_lexical_band"]:
        print("FAILED:RES-0084-probe2 deep paraphrase not in the distinct band")
        return 1
    if settle["deep_pair_unique_count"] != 2 or settle["control_pair_unique_count"] != 2:
        print("FAILED:RES-0084-probe2 counter split the blind-spot pairs unequally")
        return 1

    rename = live["lexical_bands"]["two_gamed_variants"]
    if rename["raw_jaccard"] < thresh:
        print(
            f"FAILED:RES-0084-probe2 lexical Jaccard silent on rename pair "
            f"({rename['raw_jaccard']})"
        )
        return 1
    deep = live["lexical_bands"]["deep_paraphrase"]
    ctrl = live["lexical_bands"]["genuine_distinct_control"]
    if deep["raw_jaccard"] >= thresh or ctrl["raw_jaccard"] >= thresh:
        print("FAILED:RES-0084-probe2 deep/control unexpectedly above threshold")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0084-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next(u for u in catalog["work_units"] if u.get("id") == "RES-0084")
    sentinel = unit["completion_sentinel"]
    if sentinel not in text:
        print("FAILED:RES-0084-probe2 catalog sentinel absent")
        return 1
    if "RES-0084-DEEP-PARAPHRASE-BAND" not in text:
        print("FAILED:RES-0084-probe2 named settling experiment absent")
        return 1
    pay = payload(doc)
    if pay.get("measured_threshold") is None:
        print("FAILED:RES-0084-probe2 artifact threshold absent")
        return 1
    if abs(float(pay["measured_threshold"]) - float(thresh)) > 1e-9:
        print("FAILED:RES-0084-probe2 artifact threshold drifted")
        return 1

    validator = load_validator()
    errs = schema_errors(validator, doc)
    if errs:
        print("FAILED:RES-0084-probe2 schema-invalid", errs[0])
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not schema_errors(validator, g):
            print("FAILED:RES-0084-probe2 schema accepted garbage")
            return 1

    ok, why = honesty(doc)
    if not ok:
        print(f"FAILED:RES-0084-probe2 honesty on live artifact: {why}")
        return 1
    mutant = _plant_gamed_100(doc)
    mok, mwhy = honesty(mutant)
    if mok:
        print("FAILED:RES-0084-probe2 honesty silent on gamed-count=100 mutant")
        return 1
    print(f"honesty_control mutant_reason={mwhy}")

    print(
        json.dumps(
            {
                "reviewer_gamed": review_g,
                "reviewer_distinct": review_d,
                "threshold": thresh,
                "at_threshold_merges": True,
                "blind_spot": "RES-0084-DEEP-PARAPHRASE-BAND",
                "same_lexical_band": True,
                "honesty_live": why,
                "honesty_mutant": mwhy,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0084-probe2 recount, threshold adversary, blind spot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
