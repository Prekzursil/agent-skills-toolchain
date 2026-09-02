#!/usr/bin/env python3
"""Probe 1: mutation during capture forces SAMPLED and refuses baseline.

Both-states: the same fixture without the mid-capture rewrite stays FROZEN.
A start-only hasher would label both FROZEN; this probe fails if start_hash
equals end_hash after the planted rewrite.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import (  # noqa: E402
    ADDED_REL,
    MUTATED_REL,
    assert_mutated,
    assert_quiescent,
    compact,
    run_mutated,
    run_quiescent,
)

ART = REPO / "command-center/receipts/TST-0030.json"
SENTINEL = "SUCCESS:TST-0030"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0030-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0030":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="tst0030-p1-") as tmp:
        work = Path(tmp)
        quiet = run_quiescent(work / "quiet")
        mutated = run_mutated(work / "mutated")

    q_err = assert_quiescent(quiet)
    m_err = assert_mutated(mutated)
    if q_err or m_err:
        print(json.dumps({"quiet": compact(quiet), "mutated": compact(mutated)}, sort_keys=True))
        return fail("; ".join(q_err + m_err))

    rec = (doc.get("freeze_sample") or {}).get("mutated") or {}
    if rec.get("label") != "SAMPLED":
        return fail(f"receipt mutated label={rec.get('label')}")
    if rec.get("start_tree_hash") != mutated["start_tree_hash"]:
        return fail("receipt mutated start_tree_hash != live")
    if rec.get("end_tree_hash") != mutated["end_tree_hash"]:
        return fail("receipt mutated end_tree_hash != live")
    rec_names = list(rec.get("changed_path_names") or [])
    live_names = list(mutated["changed_path_names"])
    if rec_names != live_names:
        return fail(f"changed_path_names receipt={rec_names} live={live_names}")
    if MUTATED_REL not in rec_names or ADDED_REL not in rec_names:
        return fail(f"receipt did not enumerate planted paths {rec_names}")
    if rec.get("baseline_eligible") is not False:
        return fail("receipt calls mutated capture baseline-eligible")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_mutation_during_capture_forces_the_sampled_label")
    if not row or row.get("result") != "PASS":
        return fail("receipt test_mutation_during_capture_forces_the_sampled_label not PASS")

    print(
        json.dumps(
            {
                "probe": "probe1-mutation-sampled",
                "unit_id": "TST-0030",
                "label": mutated["label"],
                "start_tree_hash": mutated["start_tree_hash"],
                "end_tree_hash": mutated["end_tree_hash"],
                "changed_path_names": live_names,
                "baseline_refused": True,
                "quiet_control_frozen": quiet["label"] == "FROZEN",
            },
            sort_keys=True,
        )
    )
    print(
        f"sampled start={mutated['start_tree_hash'][:12]} "
        f"end={mutated['end_tree_hash'][:12]} "
        f"changed={live_names} quiet={quiet['label']}"
    )
    print("SUCCESS:TST-0030-probe1 mutation during capture forces SAMPLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
