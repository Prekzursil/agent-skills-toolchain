#!/usr/bin/env python3
"""Probe 1: every negotiate() refuse reason is triggered at least once.

Captures the user-facing CLI stderr (and the matching library message). Does
not score the rubric; that is probe 2, against the captured text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import UNIT, capture_all  # noqa: E402

ART = REPO / "command-center" / "receipts" / f"{UNIT}.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    cap = capture_all()
    rows = cap["rows"]
    print(
        json.dumps(
            {
                "probe": "probe1-every-error-path-triggered",
                "unit_id": UNIT,
                "source_refuse_reasons": cap["source_refuse_reasons"],
                "triggered_reasons": cap["triggered_reasons"],
                "inventory_complete": cap["inventory_complete"],
                "n_rows": len(rows),
            },
            sort_keys=True,
        )
    )
    if not cap["inventory_complete"]:
        return fail(
            "inventory incomplete "
            f"source={cap['source_refuse_reasons']} "
            f"triggered={cap['triggered_reasons']}"
        )
    if len(rows) < 2:
        return fail("need at least two error paths")
    for row in rows:
        if not row["triggered"]:
            return fail(f"{row['id']} not triggered")
        if row["library_allowed"]:
            return fail(f"{row['id']} library allowed a refuse path")
        if row["cli_exit_code"] == 0:
            return fail(f"{row['id']} CLI exit 0 on refuse")
        if row["cli_installed"] or row["cli_dest_has_payload"] or row["cli_dest_existed"]:
            return fail(f"{row['id']} wrote destination payload on refuse")
        if not row["library_matches_stderr"]:
            return fail(
                f"{row['id']} library message != CLI stderr: "
                f"{row['library_text']!r} vs {row['cli_stderr']!r}"
            )
        if not row["stderr_matches_stdout_message"]:
            return fail(f"{row['id']} CLI stderr != stdout negotiation.message")
        if not row["captured_text"]:
            return fail(f"{row['id']} empty captured text")
        print(f"triggered {row['id']} reason={row['library_reason']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if f"SUCCESS:{UNIT}" not in text:
        return fail("sentinel absent from receipt")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t1 = tests.get("test_every_error_path_is_triggered_at_least_once") or {}
    if t1.get("result") != "PASS":
        return fail("receipt test_every_error_path_is_triggered_at_least_once not PASS")
    live_ids = {r["id"] for r in rows}
    rec_ids = {p.get("id") for p in (doc.get("triggered_paths") or [])}
    if live_ids != rec_ids:
        return fail(f"receipt triggered_paths drifted: {rec_ids} vs {live_ids}")
    for row in rows:
        rec = next(p for p in doc["triggered_paths"] if p["id"] == row["id"])
        if rec.get("captured_text") != row["captured_text"]:
            return fail(f"{row['id']} receipt captured_text drifted from live CLI")

    print(f"paths={len(rows)} complete={cap['inventory_complete']}")
    print(f"SUCCESS:{UNIT}-probe1 every error path triggered at least once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
