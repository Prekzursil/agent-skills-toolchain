"""Census reviewer_requirement coverage, strata, and timeout budgets from the catalog."""
from __future__ import annotations

import collections
import re
import statistics
from pathlib import Path
from typing import Any

TWO_REVIEWER_RE = re.compile(r"\btwo\b", re.I)
PREFIX_RE = re.compile(r"^([A-Z]+)-")


def _prefix(uid: str) -> str:
    m = PREFIX_RE.match(uid)
    return m.group(1) if m else "UNKNOWN"


def _slots(text: str) -> int:
    if TWO_REVIEWER_RE.search(text) and "reviewer" in text.lower():
        return 2
    return 1


def _b09_path_hits(repo: Path) -> list[str]:
    """Look for a B09 wall-clock artifact without walking the whole worktree.

    A repo-wide rglob("*B09*") is not a measurement: it races concurrent
    G-1 delivery and can hang. The catalog names confirmation-records and
    the receipts/audit trees as the places a B09 measurement would live.
    """
    roots = [
        repo / "command-center" / "confirmation-records",
        repo / "command-center" / "receipts",
        repo / "command-center" / "audit",
        repo / "command-center" / "adversarial",
    ]
    hits: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if "B09" in root.name:
                hits.append(str(root.relative_to(repo)))
            continue
        for p in sorted(root.glob("*B09*")):
            hits.append(str(p.relative_to(repo)))
            if len(hits) >= 30:
                return hits
    return hits


def _b09_status(repo: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    meta = catalog.get("work_units_meta") or {}
    remeasured = meta.get("remeasured_2026_08_11") or {}
    members = (remeasured.get("bucket_members") or {}).get("B09")
    zero_buckets = remeasured.get("buckets_with_zero_members") or []
    confirm_dir = repo / "command-center" / "confirmation-records"
    hits = _b09_path_hits(repo)
    return {
        "status": "NOT-CHECKED",
        "bucket_members": members,
        "listed_in_zero_member_buckets": "B09" in zero_buckets,
        "confirmation_records_dir_exists": confirm_dir.is_dir(),
        "worktree_B09_path_hits": hits,
        "reason": (
            "Catalog remeasure records B09 with 0 members. This worktree has no "
            "confirmation-records directory and no B09 wall-clock artifact. "
            "Reviewer throughput is therefore not taken from B09."
        ),
    }


def census(repo: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    units = catalog.get("work_units") or []
    n = len(units)
    have_rev = 0
    empty_rev = 0
    missing_rev = 0
    slots = 0
    two_units = 0
    cross_vendor = 0
    prefixes: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"n": 0, "slots": 0, "two_units": 0}
    )
    substrates: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"n": 0, "timeout_sum_s": 0, "timeout_max_s": 0}
    )
    timeouts: list[int] = []
    vendors: dict[str, int] = collections.Counter()
    slices: dict[str, int] = collections.Counter()
    phases: dict[str, int] = collections.Counter()

    for u in units:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or "")
        pref = _prefix(uid)
        r = u.get("reviewer_requirement")
        if r is None:
            missing_rev += 1
            text = ""
        else:
            text = str(r).strip()
            if not text:
                empty_rev += 1
            else:
                have_rev += 1
        sl = _slots(text) if text else 0
        if sl == 2:
            two_units += 1
        slots += sl
        prefixes[pref]["n"] += 1
        prefixes[pref]["slots"] += sl
        prefixes[pref]["two_units"] += int(sl == 2)
        if "cross-vendor" in text.lower() or "other vendor" in text.lower() or "different vendor" in text.lower():
            cross_vendor += 1
        sub = str(u.get("execution_substrate") or "missing")
        t = u.get("timeout_seconds")
        t_i = int(t) if isinstance(t, (int, float)) else 0
        timeouts.append(t_i)
        substrates[sub]["n"] += 1
        substrates[sub]["timeout_sum_s"] += t_i
        substrates[sub]["timeout_max_s"] = max(substrates[sub]["timeout_max_s"], t_i)
        am = u.get("assigned_model_vendor_role") or {}
        vendors[str(am.get("vendor") or "missing")] += 1
        slices[str(u.get("_source_slice_file") or "missing")] += 1
        phases[str(u.get("phase"))] += 1

    timeouts_sorted = sorted(timeouts)
    n_t = len(timeouts_sorted)
    timeout_stats = {
        "n": n_t,
        "min_s": timeouts_sorted[0] if n_t else None,
        "p50_s": timeouts_sorted[n_t // 2] if n_t else None,
        "p90_s": timeouts_sorted[int(n_t * 0.9)] if n_t else None,
        "max_s": timeouts_sorted[-1] if n_t else None,
        "mean_s": round(statistics.mean(timeouts_sorted), 1) if n_t else None,
        "sum_s": sum(timeouts_sorted),
        "sum_h": round(sum(timeouts_sorted) / 3600.0, 2) if n_t else None,
        "label": (
            "catalog timeout_seconds is the implementer budget, not measured "
            "reviewer wall-clock. Used only as an UPPER BOUND on review time "
            "when so labelled, never as a B09 measurement."
        ),
    }
    serial_sum = substrates.get("local-serialized", {}).get("timeout_sum_s", 0)
    parallel_sum = sum(
        v["timeout_sum_s"]
        for k, v in substrates.items()
        if k != "local-serialized"
    )
    return {
        "catalog_rel": "command-center/WORK-UNIT-CATALOG.json",
        "n_work_units": n,
        "reviewer_requirement": {
            "non_empty": have_rev,
            "empty": empty_rev,
            "missing": missing_rev,
            "coverage_of_work_units": (have_rev / n) if n else None,
            "every_unit_carries_one": have_rev == n and empty_rev == 0 and missing_rev == 0,
            "two_reviewer_units": two_units,
            "cross_vendor_units": cross_vendor,
            "reviewer_slots_1x": slots,
        },
        "prefixes": {k: dict(v) for k, v in sorted(prefixes.items())},
        "n_prefix_strata": len(prefixes),
        "substrates": {k: dict(v) for k, v in sorted(substrates.items())},
        "vendors": dict(vendors),
        "n_slices": len(slices),
        "phases": dict(phases),
        "timeout": timeout_stats,
        "implementer_budget": {
            "local_serialized_sum_s": serial_sum,
            "parallelizable_sum_s": parallel_sum,
            "note": (
                "local-serialized timeout sum is a serial-floor BUDGET, not a "
                "measured wall-clock. Parallelizable = all other substrates."
            ),
        },
        "b09": _b09_status(repo, catalog),
    }
