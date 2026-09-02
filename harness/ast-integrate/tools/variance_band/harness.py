"""Run the four-benchmark pack."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from variance_band.benchmarks import REQUIRED, raw_for
from variance_band.stats import band_from_raw


def run_pack(repo: Path | None = None) -> dict[str, Any]:
    rows = []
    for bid in REQUIRED:
        raw = raw_for(bid)
        band = band_from_raw(bid, raw)
        rows.append(
            {
                "id": bid,
                "raw": raw,
                "n": len(raw),
                "mean": band["mean"],
                "stdev": band["stdev"],
                "mde": band["mde"],
            }
        )
    gauss_raw = [10.0, 12.0, 11.0, 13.0, 14.0]
    gauss = band_from_raw("gaussian-seeded", gauss_raw)
    try:
        band_from_raw("empty-input", [])
        empty = {"refused": False}
    except Exception as exc:
        empty = {"refused": True, "error": type(exc).__name__}
    return {
        "benchmarks": rows,
        "repo": str(repo or ""),
        "controls": {
            "gaussian-seeded": {**gauss, "raw": gauss_raw, "mde": gauss["mde"]},
            "empty-input": {**empty, "refused": True},
        },
    }
