#!/usr/bin/env python
"""WAVE 4 follow-up: SETTLE the one place my independent measurement diverged from the
lane's self-report - the negative/abstention rate.

The divergence: `platform/routing/MEASUREMENTS.json` reports L3 `abstain_rate` 0.6667
(4 of 6). My independently authored 6 negatives (QS-C) measured 0.1667 (1 of 6). Both
samples are n=6, so NEITHER number settles anything - 4/6 vs 1/6 is not distinguishable
at that size. So this probe does the settling experiment instead of arguing:

  * 36 negatives, authored as ordinary requests a person might type at a coding agent's
    prompt that NO capability in this inventory should answer. The lane's own 6 are
    included verbatim so the two sets are directly comparable inside one measurement.
  * Every negative is tagged with whether it contains a token that is DISCRIMINATIVE in
    this corpus (idf above the corpus median). "Does the router false-fire on nonsense"
    and "does it false-fire on nonsense that happens to share a rare word with the
    corpus" are different questions, and averaging them hides which one is failing.
  * A FLOOR SWEEP, because a complaint without a number is not actionable: for each
    candidate `SCORE_FLOOR` it reports the abstain rate on the 36 negatives AND the
    gold-hit rate on 76 positives (the lane's 54 + my 22), so the trade is visible rather
    than asserted. `Router.route(..., floor=)` takes the override directly.

BOTH-STATES CONTROL: floor=0.0 must make the router fire on EVERY negative (abstain 0.0)
and floor=1.0 must make it fire on none (abstain 1.0). A sweep that does not move between
those extremes is not actually applying the floor, and its middle rows would be fiction.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "platform"
OUT = HERE / "WAVE4-ABSTAIN-PROBE.json"
sys.path.insert(0, str(BUILD))

from routing import index as ridx  # noqa: E402
from routing import queries as rq  # noqa: E402
from routing.descriptions import tokens  # noqa: E402
from routing.router import Router  # noqa: E402

# The lane's own six, verbatim from platform/routing/queries.py:411-452.
LANE_NEGATIVES = [
    "what is the capital of Mongolia and how many people live there",
    "please book me a dentist appointment for next Tuesday afternoon",
    "my houseplant leaves are turning yellow at the edges",
    "translate this sentence into French for a birthday card",
    "what did I have for lunch yesterday",
    "recommend a good pair of running shoes under a hundred euros",
]

# Thirty more, authored here. No attempt was made either to include or to avoid corpus
# vocabulary - they are just ordinary non-tasks. Whether each one happens to carry a
# discriminative corpus term is MEASURED below rather than curated.
MY_NEGATIVES = [
    "how do I get red wine out of a wool carpet",
    "what year did the bridge at Cernavoda open",
    "my cat keeps knocking things off the counter at four in the morning",
    "convert two hundred and fifty grams of flour into cups",
    "which train goes from Bucharest to Brasov on Sunday morning",
    "remind me to call my mother on Thursday",
    "is it going to rain in Cluj this weekend",
    "who won the football match last night",
    "what is a good gift for a nephew turning seven",
    "my knee hurts when I climb stairs, should I see someone",
    "how long do I boil an egg for a soft yolk",
    "what does the red triangle light on my dashboard mean",
    "spell the Romanian word for pomegranate",
    "how much does a passport renewal cost",
    "my neighbour parks across my gate every evening",
    "what time does the pharmacy on the corner close",
    "how do I fold a fitted sheet without it looking terrible",
    "is oat milk actually better for you than cow milk",
    "what is the difference between a viola and a violin",
    "my sourdough starter smells like acetone",
    "how many days of annual leave am I owed",
    "which houseplant survives a room with no window",
    "what is the going rate for a plumber call-out here",
    "my headphones only play sound on one side now",
    "how do I say happy birthday in Hungarian",
    "what should I do with a kilo of overripe plums",
    "is it worth insuring a fifteen year old car",
    "the tap in the bathroom drips all night",
    "how do I stop my glasses fogging under a mask",
    "what is the tallest mountain in Romania",
]


def main() -> int:
    raw = ridx.discover()
    router = Router.build(raw)
    lane_qs = rq.build(ridx.discover())

    # corpus discriminativeness: idf above the median idf
    idfs = sorted(router.model.idf.values())
    med_idf = statistics.median(idfs) if idfs else 0.0

    def discriminative(text: str) -> list[str]:
        return sorted(
            {t for t in tokens(text) if router.model.idf.get(t, 0.0) > med_idf}
        )

    negatives = [{"text": t, "src": "lane"} for t in LANE_NEGATIVES] + [
        {"text": t, "src": "mine"} for t in MY_NEGATIVES
    ]
    for n in negatives:
        n["discriminative_terms"] = discriminative(n["text"])
        n["has_discriminative_term"] = bool(n["discriminative_terms"])

    positives = [
        {"text": q.text, "gold": sorted(q.gold), "src": "lane"}
        for q in lane_qs.queries
        if q.gold
    ]
    # my authored positives, imported from the main probe so the two files cannot drift
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "w4probe", HERE / "wave4_routing_probe.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    known = set(raw.by_id())
    for text, gold in mod.QS_C:
        g = [x for x in gold if x in known]
        if g:
            positives.append({"text": text, "gold": g, "src": "mine"})

    # ---------------------------------------------------------------- headline at default
    def abstain_block(rows: list[dict], floor: float | None, k: int = 5) -> dict:
        fired, ab = [], 0
        for n in rows:
            d = router.route(n["text"], k=k, floor=floor)
            if d.fits:
                fired.append(
                    {
                        "query": n["text"],
                        "src": n["src"],
                        "has_discriminative_term": n["has_discriminative_term"],
                        "discriminative_terms": n["discriminative_terms"],
                        "got": d.ids[:3],
                        "top_final": round(d.candidates[0].final, 4)
                        if d.candidates
                        else None,
                        "threshold": round(
                            max(
                                d.threshold_stats.get("floor", 0.0),
                                d.threshold_stats.get("adaptive", 0.0),
                            ),
                            4,
                        ),
                        "binding": d.threshold_stats.get("binding"),
                        "confidence": round(d.confidence, 3),
                        "confidence_band": d.confidence_band,
                    }
                )
            else:
                ab += 1
        return {
            "n": len(rows),
            "abstained": ab,
            "abstain_rate": round(ab / len(rows), 4) if rows else None,
            "false_fires": fired,
        }

    out: dict = {
        "unit": "close/audit-probe-repair (abstention settling experiment)",
        "corpus": {"records": len(raw.records), "median_idf": round(med_idf, 4)},
        "default_floor": None,
        "at_default_threshold": {},
        "floor_sweep": {},
        "both_states_control": {},
    }
    from routing import router as rmod

    out["default_floor"] = rmod.SCORE_FLOOR
    out["default_z"] = rmod.Z_THRESHOLD

    lane_rows = [n for n in negatives if n["src"] == "lane"]
    mine_rows = [n for n in negatives if n["src"] == "mine"]
    out["at_default_threshold"] = {
        "ALL_36": abstain_block(negatives, None),
        "lane_6_only": abstain_block(lane_rows, None),
        "my_30_only": abstain_block(mine_rows, None),
    }
    d_yes = [n for n in negatives if n["has_discriminative_term"]]
    d_no = [n for n in negatives if not n["has_discriminative_term"]]
    out["at_default_threshold"]["split_by_discriminative_term"] = {
        "with_discriminative_term": abstain_block(d_yes, None),
        "without_discriminative_term": abstain_block(d_no, None),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------- sweep + control
    def gold_hit(floor: float | None, k: int = 5) -> dict:
        hits = {"lane": [0, 0], "mine": [0, 0]}
        byts = 0
        for p in positives:
            d = router.route(p["text"], k=k, floor=floor)
            ok = 1 if set(d.ids) & set(p["gold"]) else 0
            hits[p["src"]][0] += ok
            hits[p["src"]][1] += 1
            byts += d.injected_bytes
        tot_ok = hits["lane"][0] + hits["mine"][0]
        tot_n = hits["lane"][1] + hits["mine"][1]
        return {
            "gold_hit_rate_all_positives": round(tot_ok / tot_n, 4),
            "n_positives": tot_n,
            "gold_hit_lane_54": round(hits["lane"][0] / max(1, hits["lane"][1]), 4),
            "gold_hit_mine_22": round(hits["mine"][0] / max(1, hits["mine"][1]), 4),
            "mean_injected_bytes": round(byts / tot_n, 1),
        }

    for f in (0.18, 0.22, 0.26, 0.30, 0.35, 0.40):
        neg = abstain_block(negatives, f)
        out["floor_sweep"][f"floor={f}"] = {
            "abstain_rate_36_negatives": neg["abstain_rate"],
            "false_fires": len(neg["false_fires"]),
            **gold_hit(f),
        }
        OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lo = abstain_block(negatives, 0.0)
    hi = abstain_block(negatives, 1.0)
    out["both_states_control"] = {
        "floor=0.0_must_fire_on_everything": {
            "abstain_rate": lo["abstain_rate"],
            "fires_on_all": lo["abstained"] == 0,
        },
        "floor=1.0_must_fire_on_nothing": {
            "abstain_rate": hi["abstain_rate"],
            "fires_on_none": hi["abstained"] == len(negatives),
        },
        "sweep_is_really_applying_the_floor": lo["abstained"] == 0
        and hi["abstained"] == len(negatives),
        "note": "if the sweep did not move between these extremes the floor override is "
        "inert and every middle row would be fiction",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"SUCCESS:wave4-abstain-probe -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
