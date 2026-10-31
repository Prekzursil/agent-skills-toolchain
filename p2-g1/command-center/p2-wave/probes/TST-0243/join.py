"""Mechanical timeout-vs-p99 join for TST-0243 (never eyeballed).

Class = catalog id prefix (ADV, ARC, TST, ...). The class timeout is the
MINIMUM declared timeout_seconds among the class units. The measured p99 is
the nearest-rank percentile over that class's ledger durations. Verdict:
  * NO-SAMPLES when the ledger has no sample for the class;
  * DEFECT when timeout_min < p99 * (1 + margin_ratio), with a proposed new
    timeout rounded up to the next 300s grid point;
  * ADEQUATE otherwise.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

MARGIN_RATIO = 0.1
LOW_N_THRESHOLD = 20
GRID_SECONDS = 300


def nearest_rank(sorted_values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile over an already-sorted list."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(pct / 100.0 * len(sorted_values)))
    return float(sorted_values[rank - 1])


def class_stats(values: list[float]) -> dict[str, Any]:
    s = sorted(float(v) for v in values)
    n = len(s)

    def pct(p: float) -> float | None:
        return nearest_rank(s, p)

    q1, q3 = pct(25), pct(75)
    return {
        "n": n,
        "min": s[0] if n else None,
        "max": s[-1] if n else None,
        "p50": pct(50),
        "p99": pct(99),
        "q1": q1,
        "q3": q3,
        "iqr": (q3 - q1) if (q1 is not None and q3 is not None) else None,
    }


def _round_up_grid(seconds: float, grid: int = GRID_SECONDS) -> int:
    return int(math.ceil(seconds / grid) * grid)


def join(
    catalog_units: list[dict],
    ledger_records: list[dict],
    *,
    margin_ratio: float = MARGIN_RATIO,
    low_n_threshold: int = LOW_N_THRESHOLD,
) -> dict[str, dict[str, Any]]:
    """Per-class join of catalog timeouts against ledger durations."""
    by_class_units: dict[str, list[dict]] = defaultdict(list)
    for u in catalog_units:
        uid = str(u.get("id") or "")
        if not uid:
            continue
        cls = uid.rsplit("-", 1)[0]
        t = u.get("timeout_seconds")
        if isinstance(t, (int, float)) and t > 0:
            by_class_units[cls].append(u)

    by_class_durs: dict[str, list[float]] = defaultdict(list)
    for rec in ledger_records:
        cls = str(rec.get("class") or "")
        d = rec.get("duration_seconds")
        if cls and isinstance(d, (int, float)) and d >= 0:
            by_class_durs[cls].append(float(d))

    rows: dict[str, dict[str, Any]] = {}
    for cls in sorted(set(by_class_units) | set(by_class_durs)):
        timeouts = sorted(float(u["timeout_seconds"]) for u in by_class_units.get(cls, []))
        durs = by_class_durs.get(cls, [])
        row: dict[str, Any] = {
            "class": cls,
            "n_units": len(by_class_units.get(cls, [])),
            "margin_ratio": margin_ratio,
            "low_n": len(durs) < low_n_threshold,
        }
        if timeouts:
            row.update(
                {
                    "timeout_min": int(min(timeouts)),
                    "timeout_max": int(max(timeouts)),
                    "timeout_p50": int(timeouts[len(timeouts) // 2]),
                    "timeout_value_counts": {
                        str(int(v)): timeouts.count(v) for v in sorted(set(timeouts))
                    },
                }
            )
        else:
            row.update({"timeout_min": None, "timeout_max": None, "timeout_p50": None,
                        "timeout_value_counts": {}})
        stats = class_stats(durs)
        row.update(
            {
                "n_samples": stats["n"],
                "min_seconds": stats["min"],
                "max_seconds": stats["max"],
                "p50_seconds": stats["p50"],
                "p99_seconds": stats["p99"],
                "q1_seconds": stats["q1"],
                "q3_seconds": stats["q3"],
                "iqr_seconds": stats["iqr"],
            }
        )
        if stats["n"] == 0 or stats["p99"] is None or row["timeout_min"] is None:
            row.update({"verdict": "NO-SAMPLES", "adequate": None,
                        "required_timeout_seconds": None,
                        "proposed_new_timeout_seconds": None, "reason": "no ledger samples"})
        else:
            required = stats["p99"] * (1.0 + margin_ratio)
            row["required_timeout_seconds"] = required
            if row["timeout_min"] < required:
                row.update(
                    {
                        "verdict": "DEFECT",
                        "adequate": False,
                        "proposed_new_timeout_seconds": _round_up_grid(required),
                        "reason": (
                            f"{cls} p99={stats['p99']:.3f}s exceeds "
                            f"timeout_min={int(row['timeout_min'])}s by declared "
                            f"margin {margin_ratio:.2f} (need>={required:.3f}s)"
                        ),
                    }
                )
            else:
                row.update({"verdict": "ADEQUATE", "adequate": True,
                            "proposed_new_timeout_seconds": None,
                            "reason": "timeout_min meets p99 with declared margin"})
        rows[cls] = row
    return rows
