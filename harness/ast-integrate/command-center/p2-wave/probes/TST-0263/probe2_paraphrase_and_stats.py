#!/usr/bin/env python3
"""Probe 2: paraphrase resistance + independent statistical recompute."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.gain import (  # noqa: E402
    bootstrap_mean_diff_ci,
    cohens_d,
    mean,
    score_transcript,
    strip_scores,
)
from simulator import SEED, measure  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0263-probe2 {msg}")
    return 1


def main() -> int:
    live = measure()
    if live["metric_kind"] != "structured-identity":
        return fail(f"metric_kind={live['metric_kind']}")
    if live["metric_is_lexical"]:
        return fail("metric reported as lexical")
    if not live["paraphrase_structured_near_zero"]:
        return fail("paraphrase still scores structured gain")
    if not live["paraphrase_lexical_positive"]:
        return fail("paraphrase lexical control was silent (wording did not change)")
    if not live["structured_does_stop"]:
        return fail("structured stop did not fire on paraphrase restatement")
    if not live["lexical_would_not_stop"]:
        return fail(
            "lexical evaluator fired on paraphrase; cannot distinguish identity from wording"
        )

    prod: list[float] = []
    loop: list[float] = []
    for run in live["bundle"]["runs"]:
        raw = strip_scores(run["rounds"])
        recomputed = score_transcript(raw)
        stored = [float(x["gain"]) for x in run["rounds"]]
        again = [float(x["gain"]) for x in recomputed]
        if stored != again:
            return fail(f"{run['protocol_id']}/{run['cast']} independent rescore mismatch")
        if run["cast"] == "productive":
            prod.extend(again[2:])
        elif run["cast"] == "looping":
            loop.extend(again[2:])

    d = cohens_d(prod, loop)
    lo, hi = bootstrap_mean_diff_ci(prod, loop, random.Random(SEED))
    reported = live["stats"]
    if abs(d - float(reported["cohens_d"])) > 1e-12:
        return fail(f"cohens_d mismatch live={d} reported={reported['cohens_d']}")
    if abs(mean(prod) - float(reported["mean_productive"])) > 1e-12:
        return fail("mean_productive mismatch")
    if abs(mean(loop) - float(reported["mean_looping"])) > 1e-12:
        return fail("mean_looping mismatch")
    rlo, rhi = reported["bootstrap_ci95_mean_difference"]
    if abs(lo - float(rlo)) > 1e-12 or abs(hi - float(rhi)) > 1e-12:
        return fail(f"CI mismatch independent=[{lo},{hi}] reported=[{rlo},{rhi}]")
    if not (lo > 0.0):
        return fail(f"CI does not exclude zero: [{lo}, {hi}]")
    if d <= 0.8:
        return fail(f"effect size {d} is not large")

    print(
        json.dumps(
            {
                "probe": "probe2-paraphrase-and-stats",
                "metric_kind": live["metric_kind"],
                "paraphrase": live["paraphrase_rows"],
                "independent_cohens_d": d,
                "independent_ci95_mean_difference": [lo, hi],
                "n_productive": len(prod),
                "n_looping": len(loop),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"paraphrase_structured_near_zero=True lexical_positive=True "
        f"cohens_d={d:.6f} ci95=[{lo:.6f},{hi:.6f}]"
    )
    print("SUCCESS:TST-0263-probe2 paraphrase resistance and independent stats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
