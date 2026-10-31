"""Cohen kappa + error-direction for TST-0309."""
from __future__ import annotations

from collections import Counter
import random
from typing import Any

LABELS = ("match", "mismatch")


def confusion_counts(oracle: list[str], judge: list[str]) -> dict[str, Any]:
    n = min(len(oracle), len(judge))
    grid = {a: {b: 0 for b in LABELS} for a in LABELS}
    for i in range(n):
        o = oracle[i]
        j = judge[i]
        if o not in grid:
            grid[o] = {b: 0 for b in LABELS}
        grid[o][j] = grid[o].get(j, 0) + 1
    return {"n": n, "grid": grid, "method": "confusion-matrix"}


def cohen_kappa_from_matrix(grid: dict[str, Any]) -> dict[str, Any]:
    table = grid.get("grid") or grid
    n = int(grid.get("n") or 0)
    if n <= 0:
        n = sum(sum(row.values()) for row in table.values() if isinstance(row, dict))
    agree = 0
    row_m: dict[str, int] = {}
    col_m: dict[str, int] = {}
    for o, row in table.items():
        if not isinstance(row, dict):
            continue
        for j, c in row.items():
            c = int(c)
            if o == j:
                agree += c
            row_m[o] = row_m.get(o, 0) + c
            col_m[j] = col_m.get(j, 0) + c
    po = agree / n if n else 0.0
    pe = 0.0
    if n:
        labels = set(row_m) | set(col_m)
        pe = sum((row_m.get(k, 0) / n) * (col_m.get(k, 0) / n) for k in labels)
    kappa = (po - pe) / (1.0 - pe) if pe < 1.0 else 0.0
    return {"kappa": kappa, "po": po, "pe": pe, "n": n, "method": "confusion-matrix"}


def cohen_kappa_pairwise(oracle: list[str], judge: list[str]) -> dict[str, Any]:
    n = min(len(oracle), len(judge))
    agree = sum(1 for i in range(n) if oracle[i] == judge[i])
    po = agree / n if n else 0.0
    o_counts = Counter(oracle[:n])
    j_counts = Counter(judge[:n])
    labels = set(o_counts) | set(j_counts)
    pe = sum((o_counts[k] / n) * (j_counts[k] / n) for k in labels) if n else 0.0
    kappa = (po - pe) / (1.0 - pe) if pe < 1.0 else 0.0
    return {"kappa": kappa, "po": po, "pe": pe, "n": n, "method": "pairwise-marginals"}


def error_direction(oracle: list[str], judge: list[str]) -> dict[str, Any]:
    n = min(len(oracle), len(judge))
    false_match = 0
    false_mismatch = 0
    per_class = {
        "match": {"n": 0, "errors": 0},
        "mismatch": {"n": 0, "errors": 0},
    }
    for i in range(n):
        o, j = oracle[i], judge[i]
        per_class[o]["n"] += 1
        if o != j:
            per_class[o]["errors"] += 1
            if j == "match":
                false_match += 1
            else:
                false_mismatch += 1
    errors = false_match + false_mismatch
    accuracy = (n - errors) / n if n else 0.0
    if errors and false_mismatch == 0:
        direction = "toward-match"
        one_way = True
    elif errors and false_match == 0:
        direction = "toward-mismatch"
        one_way = True
    else:
        direction = "mixed" if errors else "none"
        one_way = errors == 0 or false_match == 0 or false_mismatch == 0
    return {
        "n": n,
        "errors": errors,
        "false_match": false_match,
        "false_mismatch": false_mismatch,
        "accuracy": accuracy,
        "direction": direction,
        "all_errors_one_way": one_way and errors > 0 and (false_match == 0 or false_mismatch == 0),
        "per_class": per_class,
    }


def permute_labels(labels: list[str], seed: int) -> list[str]:
    rng = random.Random(seed)
    out = list(labels)
    rng.shuffle(out)
    return out


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = (z * ((p * (1 - p) + z2 / (4 * n)) / n) ** 0.5) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_kappa(oracle: list[str], judge: list[str], *, seed: int = 0, n_boot: int = 200) -> dict[str, Any]:
    rng = random.Random(seed)
    n = min(len(oracle), len(judge))
    point = cohen_kappa_pairwise(oracle, judge)["kappa"]
    samples = []
    idx = list(range(n))
    for _ in range(n_boot):
        draw = [rng.choice(idx) for _ in range(n)]
        samples.append(
            cohen_kappa_pairwise([oracle[i] for i in draw], [judge[i] for i in draw])["kappa"]
        )
    samples.sort()
    lo = samples[int(0.025 * n_boot)]
    hi = samples[int(0.975 * n_boot)]
    return {"kappa": point, "ci95": (lo, hi), "n": n, "n_boot": n_boot}
