#!/usr/bin/env python3
"""Named probe 1: three-dot and two-dot both recorded; fresh control empty."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0029-change-surface.json"
SCHEMA = REPO / "command-center/schema/regression-delta.schema.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0029 emitted only when the artifact at output_path exists"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0029-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0029":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL_PREFIX not in text or "freshly-branched control returned empty" not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema-invalid {errs[0].message}")

    audit = S.run_scenario()
    stale = audit["stale"]
    fresh = audit["fresh"]
    if not audit["control_empty"]:
        return fail("live control not empty")
    if not (fresh["three_dot"]["empty"] and fresh["two_dot"]["empty"]):
        return fail(
            f"control three={fresh['three_dot']['file_count']} two={fresh['two_dot']['file_count']}"
        )
    if stale["three_dot"]["file_count"] < 1:
        return fail("stale three-dot empty")
    if not stale["surfaces_differ"]:
        return fail("three-dot and two-dot did not differ on stale branch")
    if stale["two_dot"]["deletions"] <= stale["three_dot"]["deletions"]:
        return fail("two-dot deletions did not exceed three-dot (mass-deletion class unseen)")
    if not stale.get("two_dot_hides_working_tree"):
        return fail("two-dot worktree noise not observed")

    branches = {b.get("name"): b for b in (doc.get("branches") or []) if isinstance(b, dict)}
    art_stale = branches.get(S.STALE)
    art_fresh = branches.get(S.FRESH)
    if not art_stale or not art_fresh:
        return fail("artifact missing per-branch surfaces")
    for label, live, recorded in (
        ("stale-three", stale["three_dot"], art_stale.get("three_dot") or {}),
        ("stale-two", stale["two_dot"], art_stale.get("two_dot") or {}),
        ("fresh-three", fresh["three_dot"], art_fresh.get("three_dot") or {}),
        ("fresh-two", fresh["two_dot"], art_fresh.get("two_dot") or {}),
    ):
        if recorded.get("file_count") != live["file_count"]:
            return fail(f"{label} file_count live={live['file_count']} art={recorded.get('file_count')}")
        if recorded.get("deletions") != live["deletions"]:
            return fail(f"{label} deletions live={live['deletions']} art={recorded.get('deletions')}")
    if not art_fresh.get("control_empty"):
        return fail("artifact control_empty not true")
    if stale["merge_base_sha"] != art_stale.get("merge_base_sha"):
        return fail("stale merge-base SHA drift vs artifact")
    if fresh["merge_base_sha"] != art_fresh.get("merge_base_sha"):
        return fail("fresh merge-base SHA drift vs artifact")

    out = {
        "probe": "probe1-three-dot-two-dot",
        "unit_id": "CNF-0029",
        "pass": True,
        "stale_three_dot_files": stale["three_dot"]["file_count"],
        "stale_three_dot_deletions": stale["three_dot"]["deletions"],
        "stale_two_dot_files": stale["two_dot"]["file_count"],
        "stale_two_dot_deletions": stale["two_dot"]["deletions"],
        "fresh_three_dot_empty": True,
        "fresh_two_dot_empty": True,
        "worktree_noise": True,
        "merge_base_sha": stale["merge_base_sha"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"stale three-dot files={stale['three_dot']['file_count']} "
        f"deletions={stale['three_dot']['deletions']} "
        f"two-dot files={stale['two_dot']['file_count']} "
        f"deletions={stale['two_dot']['deletions']} "
        f"control empty=True"
    )
    print("SUCCESS:CNF-0029-probe1 three-dot and two-dot recorded; fresh control empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
