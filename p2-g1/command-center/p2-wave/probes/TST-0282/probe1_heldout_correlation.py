#!/usr/bin/env python3
"""TST-0282 probe 1: held-out correlation of completeness_score with labels.

Computes Spearman rho of the computed score against author-constructed rubric
labels on the 12 held-out cases, with a bootstrap 95% CI and a Fisher-z CI.
Pass floors are A PRIORI (declared before the run, from the receipt): rho >=
0.7 and bootstrap-lo >= 0.4. Also asserts the score is not just word count
(word-count rho must be lower), the both-signal check the receipt's formula
is meant to beat.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from gold import build  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from council.completeness import content_tokens, score_output  # noqa: E402

MIN_RHO = 0.7
MIN_BOOT_LO = 0.4


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den


def main() -> int:
    checks: dict[str, bool] = {}
    g = build()
    held = g["heldout"]
    scores, labels, words = [], [], []
    for c in held:
        r = score_output(c["objective"], c["output"])
        scores.append(r["score"])
        labels.append(c["human_label"])
        words.append(r["word_count"])
    rho = spearman(scores, labels)
    checks["heldout_n_12"] = len(held) == 12
    checks["rho_ge_apriori_floor"] = rho >= MIN_RHO

    rng = random.Random(282)
    boots = []
    n = len(held)
    for _ in range(2000):
        idx = [rng.randrange(n) for _ in range(n)]
        bs = [scores[i] for i in idx]
        bl = [labels[i] for i in idx]
        if len(set(bs)) < 2 or len(set(bl)) < 2:
            continue
        boots.append(spearman(bs, bl))
    boots.sort()
    boot_lo = boots[int(0.025 * len(boots))]
    boot_hi = boots[int(0.975 * len(boots))]
    checks["bootstrap_lo_ge_apriori_floor"] = boot_lo >= MIN_BOOT_LO

    import math

    z = 0.5 * math.log((1 + rho) / (1 - rho))
    se = 1 / math.sqrt(n - 3)
    fisher_lo = math.tanh(z - 1.96 * se)
    fisher_hi = math.tanh(z + 1.96 * se)

    wc_rho = spearman(words, labels)
    checks["score_beats_word_count"] = rho > wc_rho
    distinct_scores = len(set(scores))
    checks["score_not_constant"] = distinct_scores >= 3

    out = {
        "probe": "probe1_heldout_correlation",
        "unit": "TST-0282",
        "formula_id": "min-three-axis-declared-coverage-v1",
        "n_heldout": n,
        "spearman_rho": round(rho, 6),
        "bootstrap_ci95": [round(boot_lo, 6), round(boot_hi, 6)],
        "fisher_z_ci95": [round(fisher_lo, 6), round(fisher_hi, 6)],
        "word_count_spearman_rho": round(wc_rho, 6),
        "apriori_floors": {"min_rho": MIN_RHO, "min_bootstrap_lo": MIN_BOOT_LO},
        "pairs": [
            {"id": c["id"], "score": s, "human_label": lb}
            for c, s, lb in zip(held, scores, labels)
        ],
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-correlation.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
