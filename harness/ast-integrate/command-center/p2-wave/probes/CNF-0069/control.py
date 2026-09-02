"""Synthetic perfectly-calibrated control set and independently computed expected Brier."""
from __future__ import annotations

from bands import BAND_ORDER, MAPPING, p_of

N_PER_BAND = 20


def make_perfect_set(n_per_band: int = N_PER_BAND) -> list[dict]:
    """For each band, hits = round(n * p) so the set is as calibrated as integer n allows."""
    claims = []
    for band in BAND_ORDER:
        p = p_of(band)
        hits = int(round(n_per_band * p))
        for i in range(n_per_band):
            outcome = "CONFIRMED" if i < hits else "REFUTED"
            claims.append(
                {
                    "id": f"CTRL-{band}-{i:02d}",
                    "band": band,
                    "p": p,
                    "outcome": outcome,
                    "settlement_kind": "synthetic-control",
                    "claim": f"synthetic {band} item {i}",
                    "source": "command-center/p2-wave/probes/CNF-0069/control.py",
                }
            )
    return claims


def expected_brier(claims: list[dict]) -> float:
    """Second implementation of Brier. Must not import scorer.brier_of."""
    acc = 0.0
    n = 0
    for it in claims:
        outcome = str(it.get("outcome") or "").upper()
        if outcome not in {"CONFIRMED", "REFUTED"}:
            continue
        y = 1.0 if outcome == "CONFIRMED" else 0.0
        p = float(it["p"]) if "p" in it else float(MAPPING[it["band"]]["p"])
        acc += (p - y) ** 2
        n += 1
    if n == 0:
        raise ValueError("control set has no settled claims")
    return acc / n


def miscalibrated_set(n_per_band: int = N_PER_BAND) -> list[dict]:
    """Negative control: every high-p band is all misses. Must NOT match expected_brier."""
    claims = []
    for band in BAND_ORDER:
        p = p_of(band)
        for i in range(n_per_band):
            claims.append(
                {
                    "id": f"BAD-{band}-{i:02d}",
                    "band": band,
                    "p": p,
                    "outcome": "REFUTED",
                    "settlement_kind": "synthetic-negative",
                    "claim": f"negative {band} item {i}",
                    "source": "command-center/p2-wave/probes/CNF-0069/control.py",
                }
            )
    return claims
