"""Labelled matcher-fusion corpus, histogram calibrator and reliability evaluator (IMP-0391).

The corpus is 80 labelled queries.  Each row records the two stage scores the
router saw for the gold candidate (``det`` from the deterministic matcher,
``sem`` from the semantic matcher) and whether selecting it was correct
(``label``).  Rows come in three regimes - strong agreement (40), weak/mixed
(20) and clear miss (20) - so every reliability bin the router can report is
exercised.

Confidence is NOT the raw fused score.  :func:`fit_calibrator` bins the
production fused score and records, per bin, the observed accuracy on the
labelled corpus; :func:`calibrate` maps a fused score to its bin's value.  That
calibrator is *held fixed* when :func:`evaluate` is run with other weights, so a
miscalibrated fusion (the sign-flipped mutant) reports confidences its outcomes
do not support and the reliability diagram turns red.  Reliability is in-sample
(fit and audited on the same corpus); the mutation control, not the in-sample
fit, is what makes the calibration test falsifiable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parent
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import fusion  # noqa: E402

__all__ = [
    "CALIBRATION_TOLERANCE",
    "FIXTURES_DIR",
    "MUTANT_WEIGHTS",
    "PROD_WEIGHTS",
    "calibrate",
    "dump_fixtures",
    "evaluate",
    "fit_calibrator",
    "labelled_rows",
    "production_report",
]

PROD_WEIGHTS: dict[str, float] = dict(fusion.DEFAULT_WEIGHTS)
MUTANT_WEIGHTS: dict[str, float] = {"w_det": -PROD_WEIGHTS["w_det"], "w_sem": -PROD_WEIGHTS["w_sem"]}
CALIBRATION_TOLERANCE: float = fusion.CALIBRATION_TOLERANCE
FIXTURES_DIR = PKG / "fixtures"
LABELLED_REL = "tools/router/fixtures/labelled-queries.json"


# -- corpus --------------------------------------------------------------------
def labelled_rows() -> list[dict[str, Any]]:
    """The 80 labelled rows: ``query_id``, ``regime``, ``det``, ``sem``, ``label``."""
    rows: list[dict[str, Any]] = []
    for i in range(40):
        rows.append(
            {
                "query_id": f"agree-{i:02d}",
                "regime": "both-stages-agree",
                "det": round(0.85 + (i % 5) * 0.02, 4),
                "sem": round(0.80 + (i % 4) * 0.03, 4),
                "label": 1,
            }
        )
    for i in range(20):
        rows.append(
            {
                "query_id": f"mixed-{i:02d}",
                "regime": "weak-or-mixed",
                "det": round(0.55 + (i % 5) * 0.02, 4),
                "sem": round(0.50 + (i % 4) * 0.03, 4),
                "label": 1 if i % 5 else 0,
            }
        )
    for i in range(20):
        rows.append(
            {
                "query_id": f"miss-{i:02d}",
                "regime": "clear-miss",
                "det": round(0.15 + (i % 5) * 0.02, 4),
                "sem": round(0.10 + (i % 4) * 0.02, 4),
                "label": 0,
            }
        )
    return rows


def _pairs() -> list[tuple[float, float, int]]:
    return [(r["det"], r["sem"], r["label"]) for r in labelled_rows()]


# -- calibrator ----------------------------------------------------------------
def fit_calibrator(
    w_det: float = PROD_WEIGHTS["w_det"],
    w_sem: float = PROD_WEIGHTS["w_sem"],
    edges: tuple[float, ...] = fusion.BIN_EDGES,
) -> dict[str, Any]:
    """Histogram calibrator: per fused-score bin, the observed accuracy."""
    scored = fusion.score_pairs(_pairs(), w_det, w_sem)
    values: list[float] = []
    counts: list[int] = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        bucket = [y for p, y in scored if lo <= p < hi]
        counts.append(len(bucket))
        values.append(sum(bucket) / len(bucket) if bucket else (lo + hi) / 2)
    return {
        "method": "histogram-binning on the production fused score",
        "fit_on": f"the {len(scored)}-row labelled corpus (in-sample reliability)",
        "fit_weights": {"w_det": w_det, "w_sem": w_sem},
        "edges": [float(e) for e in edges],
        "values": values,
        "counts": counts,
    }


def calibrate(fused: float, calibrator: dict[str, Any]) -> float:
    """Map a fused score to the calibrated confidence of its bin."""
    edges = calibrator["edges"]
    values = calibrator["values"]
    p = fusion.clip01(fused)
    for i in range(len(edges) - 1):
        if edges[i] <= p < edges[i + 1]:
            return float(values[i])
    return float(values[-1])


# -- evaluation ----------------------------------------------------------------
def evaluate(
    w_det: float = PROD_WEIGHTS["w_det"],
    w_sem: float = PROD_WEIGHTS["w_sem"],
    calibrator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reliability of the calibrated confidence when fusion uses ``w_det``/``w_sem``.

    The calibrator defaults to the one fitted on the *production* weights and
    is held fixed, so evaluating mutant weights measures what the router would
    display against what actually happened.
    """
    cal = calibrator or fit_calibrator()
    rows = labelled_rows()
    per_query: list[dict[str, Any]] = []
    scored: list[tuple[float, int]] = []
    for row in rows:
        fused = fusion.linear_fuse(row["det"], row["sem"], w_det, w_sem)
        conf = calibrate(fused, cal)
        scored.append((conf, int(row["label"])))
        per_query.append(
            {
                "query_id": row["query_id"],
                "regime": row["regime"],
                "det": row["det"],
                "sem": row["sem"],
                "fused": fused,
                "confidence": conf,
                "label": row["label"],
                "selected": conf >= fusion.DECISION_THRESHOLD,
                "correct": (conf >= fusion.DECISION_THRESHOLD) == bool(row["label"]),
            }
        )
    report = fusion.calibration_report(scored)
    report["weights"] = {"w_det": w_det, "w_sem": w_sem}
    report["calibrator"] = cal
    report["per_query"] = per_query
    return report


def production_report() -> dict[str, Any]:
    cal = fit_calibrator(**PROD_WEIGHTS)
    prod = evaluate(**PROD_WEIGHTS, calibrator=cal)
    mut = evaluate(**MUTANT_WEIGHTS, calibrator=cal)
    return {
        "production": prod,
        "mutant": mut,
        "mutation": fusion.mutation_control(prod, mut, PROD_WEIGHTS, MUTANT_WEIGHTS),
    }


def dump_fixtures() -> Path:
    """Mirror the labelled corpus to JSON so a reviewer can read it without Python."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIXTURES_DIR / "labelled-queries.json"
    doc = {
        "unit_id": "IMP-0391",
        "columns": ["query_id", "regime", "det", "sem", "label"],
        "production_weights": PROD_WEIGHTS,
        "mutant_weights": MUTANT_WEIGHTS,
        "tolerance": CALIBRATION_TOLERANCE,
        "rows": labelled_rows(),
    }
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out
