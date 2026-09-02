#!/usr/bin/env python3
"""Census live claimed-improvement inputs. Does not recompute."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CNF0027 = "command-center/confirmation/CNF-0027-baseline-variance.json"
BASELINE = "command-center/BASELINE-SNAPSHOT.json"
# Phase 0 snapshot is a freeze document, not a raw repetition series.
# CNF-0033 recomputes from raw measurement files; those files are still absent.
PHASE0_RAW = "command-center/confirmation/raw/phase0-improvement-repetitions.json"
INDEX = HERE / "fixtures" / "claims_index.json"


def _exists(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def live_census() -> dict[str, Any]:
    confirmation = REPO / "command-center" / "confirmation"
    summaries: list[str] = []
    raw_hits: list[str] = []
    if confirmation.is_dir():
        for p in sorted(confirmation.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            if rel.endswith("CNF-0033-metric-recompute.json"):
                continue
            name = p.name.lower()
            if "summary" in name:
                summaries.append(rel)
            if "raw" in name or name.endswith(".csv"):
                raw_hits.append(rel)

    live_claims = [
        {
            "id": "live.phase0-baseline-snapshot",
            "source": "live-census",
            "metric": "phase0-baseline",
            "precision_decimals": 3,
            "raw_file": PHASE0_RAW,
            "kind": "level",
            "claimed_value": None,
            "claimed_delta": None,
        },
        {
            "id": "live.cnf-0027-noise-floor",
            "source": "live-census",
            "metric": "noise-floor",
            "precision_decimals": 3,
            "raw_file": CNF0027,
            "kind": "level",
            "claimed_value": None,
            "claimed_delta": None,
        },
    ]
    return {
        "baseline_snapshot_present": _exists(BASELINE),
        "cnf0027_present": _exists(CNF0027),
        "implementer_summary_tables_found": summaries,
        "raw_measurement_files_found": raw_hits,
        "live_claim_specs": live_claims,
        "cnf0027_path": CNF0027,
        "baseline_path": BASELINE,
        "phase0_raw_path": PHASE0_RAW,
    }


def control_specs() -> list[dict[str, Any]]:
    doc = json.loads(INDEX.read_text(encoding="utf-8"))
    rows = doc.get("claims") if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("fixtures/claims_index.json has no claims")
    return [r for r in rows if isinstance(r, dict)]


def claimed_from_table(summary: dict[str, Any], claim_id: str) -> tuple[float | None, float | None]:
    """Read claimed numbers for COMPARISON only. Never for the recompute input."""
    rows = summary.get("rows") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return None, None
    for row in rows:
        if isinstance(row, dict) and row.get("id") == claim_id:
            val = row.get("median_ms")
            delta = row.get("delta")
            v = float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None
            d = float(delta) if isinstance(delta, (int, float)) and not isinstance(delta, bool) else None
            return v, d
    return None, None
