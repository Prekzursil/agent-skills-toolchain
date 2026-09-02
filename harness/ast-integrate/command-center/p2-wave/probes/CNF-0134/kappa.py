#!/usr/bin/env python3
"""Unweighted Cohen's kappa, agreement table, bootstrap CI.

Threshold and seeds are loaded from threshold_prereg.json. That file must not
contain a computed kappa (contamination guard).
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "threshold_prereg.json"
FORBIDDEN_PREREG_KEYS = frozenset(
    {
        "kappa",
        "observed_kappa",
        "point_estimate",
        "computed_kappa",
        "agreement_table",
        "raw_table",
    }
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_prereg() -> dict:
    doc = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("threshold_prereg.json is not an object")
    hit = sorted(FORBIDDEN_PREREG_KEYS.intersection(doc))
    if hit:
        raise ValueError(f"prereg contaminated with computed fields {hit}")
    if doc.get("recorded_before_any_kappa_computation") is not True:
        raise ValueError("prereg missing recorded_before_any_kappa_computation=true")
    if "kappa_threshold" not in doc:
        raise ValueError("prereg missing kappa_threshold")
    cats = doc.get("categories")
    if not isinstance(cats, list) or len(cats) < 2:
        raise ValueError("prereg categories invalid")
    return doc


def labels_from_prereg(prereg: dict | None = None) -> list[str]:
    doc = prereg if prereg is not None else load_prereg()
    return [str(x) for x in doc["categories"]]


def confusion(rater_a: list[str], rater_b: list[str], labels: list[str]) -> list[list[int]]:
    if len(rater_a) != len(rater_b):
        raise ValueError("rater vectors differ in length")
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)
    mat = [[0] * k for _ in range(k)]
    for x, y in zip(rater_a, rater_b):
        if x not in idx or y not in idx:
            raise ValueError(f"label outside declared categories: {x!r} {y!r}")
        mat[idx[x]][idx[y]] += 1
    return mat


def kappa_from_counts(counts: list[list[int]]) -> dict:
    """Return kappa, po, pe, n from a square raw-count table."""
    if not counts or any(len(row) != len(counts) for row in counts):
        raise ValueError("counts must be a square matrix")
    n = sum(sum(row) for row in counts)
    if n <= 0:
        raise ValueError("empty agreement table")
    k = len(counts)
    po = sum(counts[i][i] for i in range(k)) / n
    row_m = [sum(counts[i]) / n for i in range(k)]
    col_m = [sum(counts[i][j] for i in range(k)) / n for j in range(k)]
    pe = sum(row_m[i] * col_m[i] for i in range(k))
    if abs(1.0 - pe) < 1e-15:
        kappa = 1.0 if abs(po - 1.0) < 1e-15 else 0.0
    else:
        kappa = (po - pe) / (1.0 - pe)
    return {
        "kappa": kappa,
        "n": n,
        "pe": pe,
        "po": po,
        "row_marginals": row_m,
        "col_marginals": col_m,
    }


def cohen_kappa(rater_a: list[str], rater_b: list[str], labels: list[str]) -> dict:
    counts = confusion(rater_a, rater_b, labels)
    out = kappa_from_counts(counts)
    out["counts"] = counts
    out["labels"] = list(labels)
    return out


def bootstrap_percentile_ci(
    rater_a: list[str],
    rater_b: list[str],
    labels: list[str],
    *,
    seed: int,
    n_boot: int,
    alpha: float,
) -> dict:
    n = len(rater_a)
    if n != len(rater_b) or n < 2:
        raise ValueError("bootstrap needs paired vectors of length >= 2")
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_boot):
        ix = [rng.randrange(n) for _ in range(n)]
        aa = [rater_a[i] for i in ix]
        bb = [rater_b[i] for i in ix]
        samples.append(cohen_kappa(aa, bb, labels)["kappa"])
    samples.sort()
    lo_i = int(alpha / 2.0 * n_boot)
    hi_i = min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot))
    lo_i = max(0, min(lo_i, n_boot - 1))
    return {
        "alpha": alpha,
        "high": samples[hi_i],
        "low": samples[lo_i],
        "method": "bootstrap_percentile",
        "n_boot": n_boot,
        "seed": seed,
    }


def permute(labels_vec: list[str], seed: int) -> list[str]:
    out = list(labels_vec)
    rng = random.Random(seed)
    rng.shuffle(out)
    return out


def forced_agree_vector(labels: list[str], per_cat: int = 10) -> list[str]:
    vec: list[str] = []
    for lab in labels:
        vec.extend([lab] * per_cat)
    return vec


DOMAIN_KEYS = (
    "confidence_interval",
    "demotion_rule",
    "n",
    "pe",
    "po",
    "point_estimate",
    "raw_table",
    "reviewer_recompute",
    "statistic",
    "threshold_preregistration",
)


def domain_view(rec: dict) -> dict:
    """Calibration fields: receipt_core `report` (preferred) or legacy top-level."""
    view = dict(rec)
    ext = rec.get("extensions")
    if isinstance(ext, dict):
        cal = ext.get("calibration")
        if isinstance(cal, dict):
            for k in DOMAIN_KEYS:
                if k in cal:
                    view[k] = cal[k]
        for k in DOMAIN_KEYS:
            if k in ext:
                view[k] = ext[k]
    report = rec.get("report")
    if isinstance(report, dict):
        for k in DOMAIN_KEYS:
            if k in report:
                view[k] = report[k]
    return view
