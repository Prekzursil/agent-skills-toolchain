#!/usr/bin/env python3
"""Named probe 2: control (two different units) + catalog collision at load.

Re-derives those verdicts from live runs before checking the artifact. Last-wins
merge of the colliding pair must collapse the shared id to one unit; the loader
must refuse at load instead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog_load import run_collision_experiment  # noqa: E402
from dispatch import fixture_catalogs, run_control  # noqa: E402
from schema_ctl import iter_errors, payload_of, validate_or_raise  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0031-duplicate-dispatch.json"
SCHEMA = REPO / "command-center/schema/coordination-report.schema.json"
SENTINEL_NEEDLE = "the execution count is exactly one for the contested unit and exactly two for the non-contested control"


def main() -> int:
    live = run_control()
    print(
        "live_control "
        f"receipts={live['execution_count']} "
        f"returns={live['executed_from_returns']} "
        f"denied={live['denied_count']} "
        f"units={live['unit_ids']}"
    )
    if live["execution_count"] != 2:
        print(f"FAILED:CNF-0031-probe2 control execution_count={live['execution_count']}")
        return 1
    if live["denied_count"] != 0:
        print("FAILED:CNF-0031-probe2 distinct units were denied (over-serialised)")
        return 1
    if not live["signals_agree"]:
        print("FAILED:CNF-0031-probe2 control receipt/return disagreement")
        return 1

    collision = run_collision_experiment(fixture_catalogs())
    print(
        "live_collision "
        f"refused={collision['refused']} "
        f"detected_at_load={collision['detected_at_load']} "
        f"silent_one={collision['silent_merge_would_yield_one_unit']} "
        f"disjoint={collision['disjoint_merge_count']}"
    )
    if not collision["refused"] or not collision["detected_at_load"]:
        print("FAILED:CNF-0031-probe2 colliding catalogs were not refused at load")
        return 1
    if not collision["silent_merge_would_yield_one_unit"]:
        print("FAILED:CNF-0031-probe2 last-wins control did not yield one colliding unit")
        return 1
    if collision["disjoint_merge_count"] < 3:
        print("FAILED:CNF-0031-probe2 disjoint catalogs did not merge cleanly")
        return 1
    if not collision.get("collisions"):
        print("FAILED:CNF-0031-probe2 collision list empty")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0031-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL_NEEDLE not in text:
        print("FAILED:CNF-0031-probe2 completion sentinel fragment absent")
        return 1
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:CNF-0031-probe2 output_schema missing")
        return 1
    validate_or_raise(doc)
    if not iter_errors({"totally": "unrelated"}):
        print("FAILED:CNF-0031-probe2 schema accepted garbage")
        return 1

    payload = payload_of(doc)
    control = payload.get("control") or doc.get("control") or {}
    counts = payload.get("execution_counts") or doc.get("execution_counts") or {}
    if control.get("execution_count") != 2:
        print("FAILED:CNF-0031-probe2 artifact control count")
        return 1
    if counts.get("control") != 2:
        print("FAILED:CNF-0031-probe2 execution_counts.control")
        return 1
    cc = payload.get("catalog_collision") or doc.get("catalog_collision") or {}
    if cc.get("detected_at_load") is not True or cc.get("refused") is not True:
        print("FAILED:CNF-0031-probe2 artifact catalog_collision")
        return 1
    reviewers = payload.get("reviewers") or doc.get("reviewers") or []
    if len(reviewers) < 2:
        print("FAILED:CNF-0031-probe2 need two reviewers")
        return 1
    if any(r.get("saw_peer_verdict_before_filing") is not False for r in reviewers):
        print("FAILED:CNF-0031-probe2 reviewers were anchored")
        return 1
    print("SUCCESS:CNF-0031-probe2 control two-executions catalog-collision-at-load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
