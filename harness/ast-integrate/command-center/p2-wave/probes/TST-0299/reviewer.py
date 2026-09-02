"""Independent statistics re-run from raw per-case scores, not author prose."""
from __future__ import annotations

from typing import Any

from bench.multiple_comparison import correct_family
from bench.paired_test import paired_mean_greater_p
from bench.tournament import (
    ledger_row,
    mixed_tournament,
    null_identical_tournament,
    null_iid_tournament,
)


def _recompute_family(entry: dict) -> dict:
    baseline = entry["baseline"]
    ids = [c["id"] for c in entry["candidates"]]
    ps = [paired_mean_greater_p(baseline, c["scores"]) for c in entry["candidates"]]
    return correct_family(ps, ids=ids, alpha=float(entry["alpha"]))


def _p_match(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= 1e-12


def review_entry(entry: dict) -> dict[str, Any]:
    recomputed = _recompute_family(entry)
    stored = {r["id"]: r for r in entry["comparisons"]}
    mismatches: list[dict] = []
    for row in recomputed["comparisons"]:
        old = stored.get(row["id"])
        if old is None:
            mismatches.append({"id": row["id"], "reason": "missing-from-ledger"})
            continue
        if not _p_match(row["p_uncorrected"], old["p_uncorrected"]):
            mismatches.append(
                {
                    "id": row["id"],
                    "reason": "p-mismatch",
                    "recomputed": row["p_uncorrected"],
                    "stored": old["p_uncorrected"],
                }
            )
        if row["holm_rejected"] != old["holm_rejected"] or row["bh_rejected"] != old["bh_rejected"]:
            mismatches.append({"id": row["id"], "reason": "verdict-mismatch"})
    counts_ok = (
        recomputed["family_size"] == entry["family_size"]
        and recomputed["uncorrected_discovery_count"] == entry["uncorrected_discovery_count"]
        and recomputed["bh_discovery_count"] == entry["bh_discovery_count"]
        and recomputed["holm_certified_count"] == entry["holm_certified_count"]
    )
    return {
        "kind": entry.get("kind"),
        "family_size": recomputed["family_size"],
        "uncorrected_discovery_count": recomputed["uncorrected_discovery_count"],
        "bh_discovery_count": recomputed["bh_discovery_count"],
        "holm_certified_count": recomputed["holm_certified_count"],
        "counts_ok": counts_ok,
        "mismatches": mismatches,
        "ok": counts_ok and not mismatches,
    }


def review_live_runs() -> dict[str, Any]:
    """Re-run the three tournaments and recompute BH/Holm from scores."""
    runs = {
        "null-identical": null_identical_tournament(),
        "null-iid": null_iid_tournament(),
        "mixed": mixed_tournament(),
    }
    reports = {k: review_entry(ledger_row(v)) for k, v in runs.items()}
    ok = all(r["ok"] for r in reports.values())
    return {
        "reviewer_id": "TST-0299-independent-statistics-rerun",
        "independent": True,
        "method": "recompute paired t p-values from raw per-case scores, then BH+Holm",
        "verdict": "PASS" if ok else "FAIL",
        "reports": reports,
    }
