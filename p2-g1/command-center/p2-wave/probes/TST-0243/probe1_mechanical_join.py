#!/usr/bin/env python3
"""TST-0243 probe 1: the mechanical join over catalog x ledger, live.

Per class: is the declared timeout above the measured p99 by the declared
margin? Every number below is computed by join.py from the catalog and the
captured run ledger - never eyeballed. A class whose p99 exceeds its
timeout_min is reported as a catalog DEFECT with a proposed new value.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import join as join_mod  # noqa: E402
import ledger as ledger_mod  # noqa: E402

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SNAPSHOT = HERE / "captures" / "run-ledger.jsonl"


def ensure_snapshot() -> dict:
    """Load the ledger snapshot; rebuild it deterministically if absent."""
    if SNAPSHOT.is_file():
        records = [
            json.loads(ln)
            for ln in SNAPSHOT.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        return {"records": records, "rebuilt": False}
    records = ledger_mod.capture_from_receipts(REPO / "command-center" / "receipts")
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"records": records, "rebuilt": True}


def independent_p99(values: list[float], pct: float) -> float | None:
    """A second, deliberately different percentile implementation."""
    if not values:
        return None
    ordered = sorted(values)
    k = int(pct / 100.0 * len(ordered) + 0.999999)
    k = min(max(k, 1), len(ordered))
    return float(ordered[k - 1])


def main() -> int:
    checks: dict[str, bool] = {}
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = [u for u in cat.get("work_units") or [] if isinstance(u, dict)]
    snap = ensure_snapshot()
    records = snap["records"]
    checks["snapshot_present_or_rebuilt"] = len(records) > 0

    classes = sorted({str(u["id"]).rsplit("-", 1)[0] for u in units if u.get("id")})
    rows = join_mod.join(units, records)
    checks["every_catalog_class_has_a_row"] = sorted(rows) == classes

    sampled = [r for r in rows.values() if r["n_samples"] > 0]
    nosamp = [r for r in rows.values() if r["n_samples"] == 0]
    checks["sampled_classes_have_verdicts"] = all(
        r["verdict"] in ("ADEQUATE", "DEFECT") for r in sampled
    )
    checks["unsampled_classes_are_no_samples"] = all(
        r["verdict"] == "NO-SAMPLES" and r["adequate"] is None for r in nosamp
    )
    checks["margin_rule_recomputed_inline"] = all(
        r["adequate"] == (r["timeout_min"] >= r["p99_seconds"] * (1.0 + r["margin_ratio"]))
        for r in sampled
    )
    defects = [r for r in sampled if r["verdict"] == "DEFECT"]
    checks["defects_carry_proposed_value_and_reason"] = all(
        r["proposed_new_timeout_seconds"] >= r["required_timeout_seconds"] and r["class"] in r["reason"]
        for r in defects
    )
    checks["every_row_has_timeout_stats"] = all(
        r["timeout_min"] is not None and r["n_units"] > 0 for r in rows.values()
    )

    # independent p99 cross-check on every sampled class
    by_class: dict[str, list[float]] = {}
    for rec in records:
        by_class.setdefault(rec["class"], []).append(float(rec["duration_seconds"]))
    cross = all(
        abs(independent_p99(by_class[r["class"]], 99.0) - r["p99_seconds"]) < 1e-9
        for r in sampled
    )
    checks["independent_p99_crosscheck_agrees"] = cross
    rows_again = join_mod.join(units, records)
    checks["join_is_deterministic"] = json.dumps(rows, sort_keys=True) == json.dumps(
        rows_again, sort_keys=True
    )

    n_defects = len(defects)
    out = {
        "probe": "probe1-mechanical-join",
        "unit_id": "TST-0243",
        "ledger_source": sorted({r["source"] for r in records}),
        "n_records": len(records),
        "snapshot_rebuilt_this_run": snap["rebuilt"],
        "n_classes": len(rows),
        "n_compared": len(sampled),
        "n_adequate": sum(1 for r in sampled if r["verdict"] == "ADEQUATE"),
        "n_no_samples": len(nosamp),
        "n_defects": n_defects,
        "defects": [
            {"class": r["class"], "p99_seconds": r["p99_seconds"],
             "timeout_min": r["timeout_min"], "n_samples": r["n_samples"],
             "required_timeout_seconds": r["required_timeout_seconds"],
             "proposed_new_timeout_seconds": r["proposed_new_timeout_seconds"],
             "reason": r["reason"]}
            for r in defects
        ],
        "rows": rows,
        "eyeballed": False,
        "checks": checks,
        "pass": all(checks.values()),
    }
    (HERE / "probe1_mechanical_join.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, sort_keys=True))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
