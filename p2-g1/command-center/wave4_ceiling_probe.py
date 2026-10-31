#!/usr/bin/env python
"""WAVE 4 follow-up: MEASURE the mechanism behind the false fires instead of asserting it.

Hypothesis to be confirmed or refuted: `SemanticModel.score` divides a candidate's BM25
mass by `ceiling(bag)` - the sum of the QUERY's own IDF-weighted term weights
(`semantic.py:278`). That is candidate-independent and absolute, which is what makes
abstention expressible at all. But the divisor is a property of the QUERY, so a query whose
vocabulary is largely ABSENT from the corpus has a LOW ceiling, and any record that happens
to contain one of its few known terms saturates `min(1.0, b/ceil)` toward 1.0 - producing a
high absolute score for an out-of-domain query.

If that is the mechanism, then for false-firing negatives we should see BOTH:
  (a) a LOW ceiling relative to real positives, AND
  (b) a HIGH saturation ratio `b_max / ceiling`.

If negatives show ceilings comparable to positives, the hypothesis is REFUTED and the
false fires are ordinary lexical collisions instead.

BOTH-STATES CONTROL: the same statistic is computed for the positives, which do NOT
false-fire in the pathological way. A statistic that looks the same on both populations
distinguishes nothing and must not be reported as an explanation.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "platform"
OUT = HERE / "WAVE4-CEILING-PROBE.json"
sys.path.insert(0, str(BUILD))

from routing import index as ridx  # noqa: E402
from routing import queries as rq  # noqa: E402
from routing import semantic as rsem  # noqa: E402
from routing.descriptions import tokens  # noqa: E402
from routing.router import Router  # noqa: E402

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("w4ab", HERE / "wave4_abstain_probe.py")
ab = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(ab)  # type: ignore[union-attr]


def stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean": round(statistics.mean(vals), 4),
        "median": round(statistics.median(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
    }


def main() -> int:
    raw = ridx.discover()
    router = Router.build(raw)
    m = router.model
    lane_qs = rq.build(ridx.discover())

    negatives = ab.LANE_NEGATIVES + ab.MY_NEGATIVES
    positives = [q.text for q in lane_qs.queries if q.gold]

    def probe(text: str) -> dict:
        toks = tokens(text)
        bag = {t: 1.0 for t in toks}
        ceil = m.ceiling(bag)
        b = m.bm25(bag)
        bmax = max(b) if b else 0.0
        known = [t for t in toks if t in m.idf]
        d = router.route(text, k=5)
        return {
            "query": text,
            "n_tokens": len(toks),
            "n_tokens_KNOWN_to_corpus": len(known),
            "frac_tokens_known": round(len(known) / len(toks), 3) if toks else 0.0,
            "ceiling": round(ceil, 4),
            "bm25_max": round(bmax, 4),
            "saturation_bmax_over_ceiling": round(bmax / ceil, 4) if ceil else None,
            "saturated_at_1_0": bool(ceil and bmax / ceil >= 1.0),
            "final_top": round(d.candidates[0].final, 4) if d.candidates else 0.0,
            "fits": d.fits,
        }

    neg_rows = [probe(t) for t in negatives]
    pos_rows = [probe(t) for t in positives]
    neg_fire = [r for r in neg_rows if r["fits"]]
    neg_quiet = [r for r in neg_rows if not r["fits"]]

    out = {
        "unit": "close/audit-probe-repair (score-ceiling mechanism)",
        "hypothesis": "out-of-domain queries have a LOW ceiling, so a single matching term "
        "saturates min(1.0, b/ceil) and yields a high ABSOLUTE score",
        "populations": {
            "negatives_that_FIRED": {
                "ceiling": stats([r["ceiling"] for r in neg_fire]),
                "saturation": stats(
                    [r["saturation_bmax_over_ceiling"] or 0.0 for r in neg_fire]
                ),
                "frac_tokens_known": stats([r["frac_tokens_known"] for r in neg_fire]),
                "n_saturated_at_1_0": sum(1 for r in neg_fire if r["saturated_at_1_0"]),
            },
            "negatives_that_ABSTAINED": {
                "ceiling": stats([r["ceiling"] for r in neg_quiet]),
                "saturation": stats(
                    [r["saturation_bmax_over_ceiling"] or 0.0 for r in neg_quiet]
                ),
                "frac_tokens_known": stats([r["frac_tokens_known"] for r in neg_quiet]),
                "n_saturated_at_1_0": sum(
                    1 for r in neg_quiet if r["saturated_at_1_0"]
                ),
            },
            "POSITIVES_control": {
                "ceiling": stats([r["ceiling"] for r in pos_rows]),
                "saturation": stats(
                    [r["saturation_bmax_over_ceiling"] or 0.0 for r in pos_rows]
                ),
                "frac_tokens_known": stats([r["frac_tokens_known"] for r in pos_rows]),
                "n_saturated_at_1_0": sum(1 for r in pos_rows if r["saturated_at_1_0"]),
            },
        },
        "BM25_constants": {
            "K1": rsem.BM25_K1,
            "B": rsem.BM25_B,
            "W_BM25": rsem.W_BM25,
            "W_NGRAM": rsem.W_NGRAM,
        },
        "rows": {"negatives": neg_rows, "positives": pos_rows[:20]},
    }

    nf = out["populations"]["negatives_that_FIRED"]
    pc = out["populations"]["POSITIVES_control"]
    ceil_lower = (nf["ceiling"].get("median", 0) or 0) < (
        pc["ceiling"].get("median", 0) or 0
    )
    sat_higher = (nf["saturation"].get("median", 0) or 0) >= (
        pc["saturation"].get("median", 0) or 0
    )
    out["verdict"] = {
        "firing_negatives_have_LOWER_median_ceiling_than_positives": ceil_lower,
        "firing_negatives_have_HIGHER_OR_EQUAL_median_saturation": sat_higher,
        "hypothesis": "CONFIRMED"
        if (ceil_lower and sat_higher)
        else ("PARTIAL" if (ceil_lower or sat_higher) else "REFUTED"),
        "both_states_note": "the positives population is the contrast arm; if the two "
        "populations looked alike this statistic would explain nothing",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))
    print(f"SUCCESS:wave4-ceiling-probe -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
