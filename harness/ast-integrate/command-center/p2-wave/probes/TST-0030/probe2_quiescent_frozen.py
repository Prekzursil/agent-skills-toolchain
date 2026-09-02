#!/usr/bin/env python3
"""Probe 2: a quiescent capture earns FROZEN and is eligible as a baseline.

Re-runs the planted fixture with no mid-capture rewrite and checks that
command-center/receipts/TST-0030.json recorded the same start and end tree
hashes. Independent of probe 1's mutation arm.
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
    assert_quiescent,
    compact,
    run_live_product_file,
    run_quiescent,
)

ART = REPO / "command-center/receipts/TST-0030.json"
SENTINEL = "SUCCESS:TST-0030"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0030-probe2 {msg}")
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

    with tempfile.TemporaryDirectory(prefix="tst0030-p2-") as tmp:
        quiet = run_quiescent(Path(tmp) / "quiet")
    q_err = assert_quiescent(quiet)
    if q_err:
        print(json.dumps(compact(quiet), sort_keys=True))
        return fail("; ".join(q_err))

    rec = (doc.get("freeze_sample") or {}).get("quiescent") or {}
    if rec.get("label") != "FROZEN":
        return fail(f"receipt quiescent label={rec.get('label')}")
    if rec.get("start_tree_hash") != quiet["start_tree_hash"]:
        return fail("receipt quiescent start_tree_hash != live")
    if rec.get("end_tree_hash") != quiet["end_tree_hash"]:
        return fail("receipt quiescent end_tree_hash != live")
    if rec.get("start_tree_hash") != rec.get("end_tree_hash"):
        return fail("receipt quiescent hashes differ")
    if rec.get("changed_paths"):
        return fail(f"receipt quiescent changed_paths={rec.get('changed_paths')}")
    if rec.get("baseline_eligible") is not True:
        return fail("receipt quiescent not baseline_eligible")

    live_rec = (doc.get("freeze_sample") or {}).get("live_product_file") or {}
    live = run_live_product_file()
    if live_rec.get("start_tree_hash") != live["start_tree_hash"]:
        return fail("receipt live_product_file start_tree_hash != live rehash")
    if live_rec.get("end_tree_hash") != live["end_tree_hash"]:
        return fail("receipt live_product_file end_tree_hash != live rehash")
    if live["label"] != "FROZEN":
        return fail(f"live product file capture label={live['label']}")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_quiescent_capture_earns_the_frozen_label")
    if not row or row.get("result") != "PASS":
        return fail("receipt test_quiescent_capture_earns_the_frozen_label not PASS")

    print(
        json.dumps(
            {
                "probe": "probe2-quiescent-frozen",
                "unit_id": "TST-0030",
                "label": quiet["label"],
                "start_tree_hash": quiet["start_tree_hash"],
                "end_tree_hash": quiet["end_tree_hash"],
                "baseline_eligible": True,
                "live_product_label": live["label"],
            },
            sort_keys=True,
        )
    )
    print(
        f"frozen hash={quiet['start_tree_hash'][:16]} "
        f"live_product={live['label']} files={quiet['snapshot']['file_count']}"
    )
    print("SUCCESS:TST-0030-probe2 quiescent capture earns FROZEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
