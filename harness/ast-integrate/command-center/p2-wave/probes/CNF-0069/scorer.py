"""Calibration scorer: per-band hit rate + Brier; unsettled excluded; n<5 unscored."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from bands import BAND_ORDER, MAPPING, SETTLED, p_of

MIN_N = 5
FORMULA = "Brier = mean((p_i - y_i)^2) over settled claims only; y=1 CONFIRMED, y=0 REFUTED"


def is_settled(outcome: str | None) -> bool:
    return str(outcome or "").upper() in SETTLED


def y_of(outcome: str) -> float:
    u = str(outcome).upper()
    if u == "CONFIRMED":
        return 1.0
    if u == "REFUTED":
        return 0.0
    raise ValueError(f"not a scored outcome: {outcome}")


def brier_of(items: Iterable[dict[str, Any]]) -> tuple[float | None, int]:
    """Independent of hit-rate grouping. Unsettled rows are skipped, not scored as misses."""
    total = 0.0
    n = 0
    for it in items:
        if not is_settled(it.get("outcome")):
            continue
        band = it["band"]
        p = float(it["p"]) if "p" in it else p_of(band)
        total += (p - y_of(it["outcome"])) ** 2
        n += 1
    if n == 0:
        return None, 0
    return total / n, n


def score(claims: Iterable[dict[str, Any]], *, min_n: int = MIN_N) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unsettled: list[dict[str, Any]] = []
    contemporaneous: list[dict[str, Any]] = []
    scored_items: list[dict[str, Any]] = []
    for raw in claims:
        row = dict(raw)
        row["p"] = float(row["p"]) if "p" in row else p_of(row["band"])
        kind = str(row.get("settlement_kind") or "")
        if kind == "contemporaneous-measurement":
            contemporaneous.append(row)
            continue
        if not is_settled(row.get("outcome")):
            unsettled.append(row)
            by[row["band"]].append(row)
            continue
        by[row["band"]].append(row)
        scored_items.append(row)

    bands_out = []
    for band in BAND_ORDER:
        spec = MAPPING[band]
        rows = by.get(band) or []
        settled_rows = [r for r in rows if is_settled(r.get("outcome"))]
        n_unsettled = sum(1 for r in rows if not is_settled(r.get("outcome")))
        n = len(settled_rows)
        hits = sum(1 for r in settled_rows if str(r["outcome"]).upper() == "CONFIRMED")
        entry: dict[str, Any] = {
            "band": band,
            "p": spec["p"],
            "lo": spec["lo"],
            "hi": spec["hi"],
            "n_settled": n,
            "n_unsettled": n_unsettled,
            "hits": hits,
            "hit_rate": None,
            "brier": None,
            "signed_gap": None,
            "status": "no-settled" if n == 0 else "insufficient-data",
        }
        if n >= min_n:
            rate = hits / n
            b, _ = brier_of(settled_rows)
            entry["hit_rate"] = rate
            entry["brier"] = b
            entry["signed_gap"] = spec["p"] - rate
            entry["status"] = "scored"
            inside = spec["lo"] <= rate <= spec["hi"]
            entry["observed_inside_interval"] = inside
        elif n > 0:
            entry["status"] = "insufficient-data"
            entry["why"] = f"n_settled={n} < {min_n}; reported rather than scored"
        bands_out.append(entry)

    overall, n_scored = brier_of(scored_items)
    # Overall Brier is reported on every settled claim even when a band is
    # below min_n; the per-band table still marks those bands insufficient.
    # The headline overconfidence verdict uses only status=scored bands.
    scored_bands = [b for b in bands_out if b["status"] == "scored"]
    worst = None
    overconfident = None
    if scored_bands:
        worst = max(scored_bands, key=lambda b: abs(float(b["signed_gap"])))
        # Overconfidence on high-p bands: predicted probability exceeds hit rate.
        gaps = [float(b["signed_gap"]) for b in scored_bands]
        overconfident = sum(gaps) / len(gaps) > 0

    return {
        "bands": bands_out,
        "brier": {
            "score": overall,
            "n": n_scored,
            "formula": FORMULA,
            "note": "overall Brier includes every settled claim; per-band scoring still requires n>=5",
        },
        "unsettled": {
            "count": len(unsettled),
            "excluded_from_score": True,
            "not_treated_as_misses": True,
            "ids": [u.get("id") for u in unsettled],
        },
        "contemporaneous_excluded": {
            "count": len(contemporaneous),
            "why": (
                "Band attached to a measurement just executed in the same document "
                "is not a forecast. Scoring it as calibrated would tautologically hit."
            ),
        },
        "scored_items": scored_items,
        "systematic_overconfidence": overconfident,
        "worst_miscalibrated_band": None
        if worst is None
        else {
            "band": worst["band"],
            "p": worst["p"],
            "hit_rate": worst["hit_rate"],
            "signed_gap": worst["signed_gap"],
            "n": worst["n_settled"],
        },
    }
