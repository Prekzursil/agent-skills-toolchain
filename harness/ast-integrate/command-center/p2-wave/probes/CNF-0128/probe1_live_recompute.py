#!/usr/bin/env python3
"""Probe 1: recompute the live gate from receipts; match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gate import OWN_OUTPUT, compute  # noqa: E402
from schema_val import errors as schema_errors  # noqa: E402

SENTINEL_PREFIX = "SUCCESS:CNF-0128 emitted only when"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0128-probe1 {msg}")
    return 1


def payload(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged = dict(doc)
    merged.update(report)
    return merged


def main() -> int:
    art_path = REPO / OWN_OUTPUT
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("artifact missing")
    text = art_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if SENTINEL_PREFIX not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    errs = schema_errors(doc)
    if errs:
        return fail(f"schema:{errs[0]}")
    if not schema_errors({}):
        return fail("schema-accepted-empty")
    if not isinstance(doc.get("report"), dict):
        return fail("report-absent")
    if doc["report"].get("kind") != "phase-gate-report":
        return fail("report.kind")

    view = payload(doc)
    live = compute(REPO)
    if view.get("gate_verdict") != live["gate_verdict"]:
        return fail(
            f"gate_verdict artifact={view.get('gate_verdict')} live={live['gate_verdict']}"
        )
    if bool(view.get("phase_finished")) != bool(live["phase_finished"]):
        return fail("phase_finished mismatch")
    if view.get("computed_from_receipts") is not True:
        return fail("computed_from_receipts not true")

    art_conds = {
        c["id"]: c for c in view.get("conditions") or [] if isinstance(c, dict)
    }
    for cond in live["conditions"]:
        got = art_conds.get(cond["id"])
        if not got:
            return fail(f"condition-absent:{cond['id']}")
        if got.get("computed_state") != cond["computed_state"]:
            return fail(
                f"{cond['id']} artifact={got.get('computed_state')} live={cond['computed_state']}"
            )
        if bool(got.get("blocks_exit")) != bool(cond.get("blocks_exit")):
            return fail(f"{cond['id']} blocks_exit mismatch")

    residuals = view.get("residuals") or []
    if not isinstance(residuals, list):
        return fail("residuals-not-list")
    for r in residuals:
        if not isinstance(r, dict):
            return fail("residual-not-object")
        if not str(r.get("settling_experiment") or "").strip():
            return fail(f"residual-no-settling:{r.get('id')}")
        if not str(r.get("statement") or "").strip():
            return fail(f"residual-no-statement:{r.get('id')}")

    live_ids = {r["id"] for r in live["residuals"]}
    art_ids = {r.get("id") for r in residuals if isinstance(r, dict)}
    if live_ids != art_ids:
        return fail(
            f"residual-id-mismatch missing={live_ids-art_ids} extra={art_ids-live_ids}"
        )

    inv = live["inventory"]
    if inv["claims_state"] == "ABSENT" and view.get("gate_verdict") == "GREEN":
        return fail("absent-inventory-read-as-pass")
    if (
        inv["p0p1_count"] == 0
        and inv["claims_state"] != "PRESENT"
        and view.get("gate_verdict") == "GREEN"
    ):
        return fail("empty-census-read-as-pass")

    print(
        json.dumps(
            {
                "probe": "probe1-live-recompute",
                "gate_verdict": live["gate_verdict"],
                "phase_finished": live["phase_finished"],
                "conditions": {
                    c["id"]: c["computed_state"] for c in live["conditions"]
                },
                "residuals": len(residuals),
                "schema_ok": True,
                "matched_artifact": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"gate={live['gate_verdict']} residuals={len(residuals)} "
        f"blocking={live['blocking_condition_ids']}"
    )
    print("SUCCESS:CNF-0128-probe1 live recompute matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
