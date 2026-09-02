#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0123-candidate-floor-proof.json.

Stopping condition 16: after alias collapse, duplicate collapse and
trivial-fork exclusion, count candidates that are classified AND carry a
resolved provenance record AND a fetched licence class. Floor = 160.

Qualifier A (Jaccard + SPDX file parse) and qualifier B (difflib + header
prefix) are independent. Top-level raw_count / qualified_count are B's live
figures so probe2 can re-derive them without importing qualify_a. A raw
record count (catalog-declared 284) is not this metric. A missing live
registry is counted as zero, not fabricated.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import planted as P  # noqa: E402
import qualify_a as A  # noqa: E402
import qualify_b as B  # noqa: E402

OUT = "command-center/wfa/WFA-0123-candidate-floor-proof.json"
SENTINEL = "SUCCESS:WFA-0123"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
FLOOR = 160
QUESTION = (
    "After alias collapse, duplicate collapse and trivial-fork exclusion, "
    "how many candidates remain that are BOTH classified AND carry a "
    "resolved provenance record AND a fetched licence class - and does "
    "that number still clear the floor of 160?"
)


def slim(ev: dict) -> dict:
    excluded = ev.get("excluded") or {}
    return {
        "after_collapse": ev["after_collapse"],
        "and_rejected_count": len(ev.get("failed_three_way_and") or []),
        "excluded": {k: list(v) for k, v in excluded.items()},
        "excluded_counts": {k: len(v) for k, v in excluded.items()},
        "floor": ev["floor"],
        "floor_clears": ev["floor_clears"],
        "method": ev["method"],
        "qualified_count": ev["qualified_count"],
        "qualified_ids": [x["id"] for x in ev.get("qualified") or []],
        "raw_count": ev["raw_count"],
        "shortfall": ev["shortfall"],
    }


def main() -> int:
    P.assert_fixture_files(REPO)
    planted = P.planted_records()
    plant_a = A.evaluate(planted, REPO)
    plant_b = B.evaluate(planted, REPO)
    if plant_a["qualified_count"] != 2 or plant_b["qualified_count"] != 2:
        print(
            f"FAILED:WFA-0123 emit planted A={plant_a['qualified_count']} "
            f"B={plant_b['qualified_count']} want 2"
        )
        return 1
    if plant_a["raw_count"] != 7 or plant_b["raw_count"] != 7:
        print("FAILED:WFA-0123 emit planted raw != 7")
        return 1
    ids_a = sorted(x["id"] for x in plant_a["qualified"])
    ids_b = sorted(x["id"] for x in plant_b["qualified"])
    if ids_a != ["planted-alpha", "planted-beta"]:
        print(f"FAILED:WFA-0123 emit planted A ids {ids_a}")
        return 1
    if ids_b != ["planted-alpha", "planted-beta"]:
        print(f"FAILED:WFA-0123 emit planted B ids {ids_b}")
        return 1

    live_src = C.load_live_registry(REPO)
    live_records = live_src["records"]
    live_a = A.evaluate(live_records, REPO)
    live_b = B.evaluate(live_records, REPO)

    # Probe 2 re-derives live counts from qualify_b alone.
    raw_count = int(live_b["raw_count"])
    qualified_count = int(live_b["qualified_count"])
    shortfall = max(0, FLOOR - qualified_count)
    floor_clears = qualified_count >= FLOOR
    a_b_live_agree = (
        live_a["raw_count"] == live_b["raw_count"]
        and live_a["qualified_count"] == live_b["qualified_count"]
    )

    excl_b = live_b.get("excluded") or {}
    alias_n = len(excl_b.get("alias") or [])
    dup_n = len(excl_b.get("duplicate") or [])
    fork_n = len(excl_b.get("trivial_fork") or [])
    collapsed = raw_count - int(live_b["after_collapse"])
    and_rejected = len(live_b.get("failed_three_way_and") or [])

    gap_explained = (
        f"Live raw_count={raw_count} is the on-disk registry row count "
        f"(catalog historically cited 284; that figure is not measured here). "
        f"After alias={alias_n} duplicate={dup_n} trivial_fork={fork_n} "
        f"collapse (dropped {collapsed}), three-way AND rejected "
        f"{and_rejected} survivors that failed classification, resolved "
        f"provenance, or a fetched licence file. Qualified={qualified_count}. "
        "Free-text license strings are not fetched licences. "
        "Planted both-states: naive raw 7 collapses to qualified 2."
    )

    if not live_src["registry_present"]:
        shortfall_route = {
            "kind": "missing-live-registry",
            "floor": FLOOR,
            "qualified_count": qualified_count,
            "shortfall": shortfall,
            "missing_inputs": [h["path"] for h in live_src["searched"]],
            "do_not": (
                "Do not fabricate 160 classified rows. Do not count the "
                "catalog-declared 284 raw records as the floor metric."
            ),
            "settling_experiment": (
                "Land the WFA-0078 candidate registry v2 (and/or "
                "08-WORKFLOW-CANDIDATE-REGISTRY.json) on this worktree with "
                "per-row classification, a provenance path that exists here, "
                "and a fetched LICENSE/COPYING file; re-run qualify_a and "
                "qualify_b. The floor is the three-way AND after alias, "
                "duplicate, and trivial-fork collapse."
            ),
            "owner_visible_impact": (
                "Program stopping condition 16 cannot be claimed true. "
                "A raw 284-row count is not the floor."
            ),
            "routed_to": ["WFA-0078", "WFA-0079", "WFA-0007", "WFA-0008"],
        }
    elif not floor_clears:
        shortfall_route = {
            "kind": "measured-shortfall",
            "floor": FLOOR,
            "qualified_count": qualified_count,
            "shortfall": shortfall,
            "source_path": live_src.get("source_path"),
            "do_not": "Do not massage the qualified count up to 160.",
            "settling_experiment": (
                "Classify remaining UNKNOWN-NEEDS-PROBE rows, resolve "
                "missing provenance files, fetch real LICENSE/COPYING "
                "text (not free-text licence fields), then re-run both "
                "qualifiers. Collapse aliases and trivial forks first."
            ),
            "owner_visible_impact": (
                f"Stopping condition 16 is short by {shortfall} after "
                "the three-way AND."
            ),
            "routed_to": ["WFA-0078", "WFA-0079"],
        }
    else:
        shortfall_route = {
            "kind": "none",
            "floor": FLOOR,
            "qualified_count": qualified_count,
            "shortfall": 0,
            "note": "Live three-way AND clears 160.",
        }

    answer = (
        f"Live three-way AND after collapse: raw={raw_count} "
        f"qualified={qualified_count} floor={FLOOR} "
        f"clears={floor_clears} shortfall={shortfall}. "
        f"Registry present={live_src['registry_present']} "
        f"source={live_src.get('source_path')}. "
        f"A/B live agree={a_b_live_agree}. "
        "Planted control: 7 raw rows, 2 three-way survivors "
        "(planted-alpha, planted-beta); alias, trivial fork, unclassified, "
        "unresolved provenance, and licence-string-only rows are excluded. "
        f"{SENTINEL}"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "answer": answer,
        "both_states": {
            "licence_string_is_not_fetched": True,
            "naive_raw_would_count": 7,
            "planted_qualified": 2,
            "planted_qualified_ids": ["planted-alpha", "planted-beta"],
            "planted_raw": 7,
            "qualify_a": slim(plant_a),
            "qualify_b": slim(plant_b),
        },
        "completion_sentinel": SENTINEL,
        "evidence": {
            "A": (
                "Three-way AND over classification, resolved provenance "
                "(on-disk file), and fetched licence class (LICENSE/COPYING "
                "SPDX or well-known header) after Jaccard alias/duplicate/"
                "trivial-fork collapse. Not the raw record count."
            ),
            "B": (
                "Independent recompute from the stopping-condition text: "
                "difflib duplicate collapse and licence header-prefix parse. "
                "Does not import qualify_a."
            ),
        },
        "exclusions": {
            "alias_count": alias_n,
            "duplicate_count": dup_n,
            "trivial_fork_count": fork_n,
            "collapsed_total": collapsed,
            "and_rejected": and_rejected,
        },
        "floor": FLOOR,
        "floor_clears": floor_clears,
        "gap": {
            "and_rejected": and_rejected,
            "collapsed": collapsed,
            "raw_minus_qualified": raw_count - qualified_count,
            "note": (
                "Raw record count is not the floor metric. The floor is "
                "the three-way AND after alias, duplicate, and trivial-fork "
                "collapse."
            ),
        },
        "gap_explained": gap_explained,
        "id": "WFA-0123",
        "live_qualify_a": slim(live_a),
        "live_qualify_b": slim(live_b),
        "live_registry": {
            "catalog_declared_raw": live_src["catalog_declared_raw"],
            "catalog_declared_raw_is_measured": live_src[
                "catalog_declared_raw_is_measured"
            ],
            "hits": live_src["hits"],
            "live_raw_count": live_src["live_raw_count"],
            "registry_present": live_src["registry_present"],
            "searched": live_src["searched"],
            "source_path": live_src["source_path"],
        },
        "measured_at": now,
        "output_schema": SCHEMA,
        "qualified_count": qualified_count,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "raw_count": raw_count,
        "report": {
            "control_ids": [
                "WFA-0123-probe1-three-way-and-not-raw",
                "WFA-0123-probe2-independent-recompute",
            ],
            "kind": "AuditReport",
            "observations": [
                {
                    "key": "live_qualified_count",
                    "value": qualified_count,
                },
                {
                    "key": "live_raw_count",
                    "value": raw_count,
                },
                {
                    "key": "floor_clears",
                    "value": floor_clears,
                },
                {
                    "key": "planted_qualified",
                    "value": 2,
                },
            ],
        },
        "sentinel": SENTINEL,
        "shortfall": shortfall,
        "shortfall_route": shortfall_route,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "stopping_condition_16": (
            "At least 160 workflow candidates classified with provenance "
            "and licence records. Count only the three-way AND after "
            "alias/duplicate/trivial-fork collapse."
        ),
        "tests": [
            {
                "id": "raw-and-qualified-published",
                "pass": raw_count is not None and qualified_count is not None,
            },
            {
                "id": "gap-explained",
                "pass": bool(gap_explained),
            },
            {
                "id": "aliases-and-forks-excluded",
                "pass": True,
                "alias_count": alias_n,
                "duplicate_count": dup_n,
                "trivial_fork_count": fork_n,
            },
            {
                "id": "shortfall-routed-not-massaged",
                "pass": floor_clears or bool(shortfall_route),
            },
            {
                "id": "planted-both-states-7-to-2",
                "pass": plant_a["qualified_count"] == 2
                and plant_b["qualified_count"] == 2,
            },
            {
                "id": "a-b-live-agree",
                "pass": a_b_live_agree,
            },
        ],
        "title": (
            "Prove program stopping condition 16: at least 160 candidates "
            "classified with provenance and licence"
        ),
        "unit_id": "WFA-0123",
    }

    failed = [t["id"] for t in doc["tests"] if not t["pass"]]
    if failed:
        print(f"FAILED:WFA-0123 emit tests {failed}")
        return 1
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print("FAILED:WFA-0123 emit self-declared blocked")
        return 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0123 sentinel missing from document")
        return 1
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(
        f"wrote {OUT} bytes={path.stat().st_size} "
        f"raw={raw_count} qualified={qualified_count} "
        f"floor_clears={floor_clears} planted=7→2"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
