"""Synthetic calibration fixture.

A perfectly-calibrated arm (hit rates inside the written intervals) plus
unadjudicated plants that the scorer must exclude and count. Labels are
independent of the scorer. Seed is recorded; there is no RNG.
"""

from __future__ import annotations

from typing import Any

from bands import BAND_ORDER

SEED = 35

# (confirmed, refuted) per band. Rates sit inside the written intervals
# and near the interval midpoint. n=20 >= MIN_N_TO_SCORE.
CALIBRATED_COUNTS: dict[str, tuple[int, int]] = {
    "almost-certain": (19, 1),  # 0.95 in [0.87, 0.99]
    "likely": (14, 6),  # 0.70 in [0.55, 0.80]
    "roughly-even": (10, 10),  # 0.50 in [0.40, 0.60]
    "unlikely": (5, 15),  # 0.25 in [0.13, 0.40]
    "remote": (1, 19),  # 0.05 in [0.01, 0.13]
}

UNADJUDICATED_PER_BAND = 2

SLUG = {
    "almost-certain": "ac",
    "likely": "lk",
    "roughly-even": "re",
    "unlikely": "un",
    "remote": "rm",
}


def _row(
    claim_id: str,
    band: str,
    oracle_label: str,
    confirmer_verdict: str,
    set_id: str,
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "band": band,
        "oracle_label": oracle_label,
        "confirmer_verdict": confirmer_verdict,
        "set_id": set_id,
        "seed": SEED,
    }


def synthetic_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for band in BAND_ORDER:
        slug = SLUG[band]
        n_hit, n_miss = CALIBRATED_COUNTS[band]
        for i in range(n_hit):
            rows.append(
                _row(
                    f"SYN-0035-SYN-{slug}-HIT-{i:02d}",
                    band,
                    "true",
                    "CONFIRMED",
                    "synthetic-perfect",
                )
            )
        for i in range(n_miss):
            rows.append(
                _row(
                    f"SYN-0035-SYN-{slug}-MIS-{i:02d}",
                    band,
                    "false",
                    "REFUTED",
                    "synthetic-perfect",
                )
            )
        for i in range(UNADJUDICATED_PER_BAND):
            # Mixed oracle labels: imputing from oracle would move the rate.
            oracle = "true" if i % 2 == 0 else "false"
            rows.append(
                _row(
                    f"SYN-0035-UNA-{slug}-{i:02d}",
                    band,
                    oracle,
                    "NOT-CHECKED",
                    "synthetic-unadjudicated",
                )
            )
    return rows
