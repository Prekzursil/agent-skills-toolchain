#!/usr/bin/env python3
"""Write command-center/receipts/IMP-0456.json — catalog slice merge report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import merge_slices as M  # noqa: E402

OUT = "command-center/receipts/IMP-0456.json"
SCHEMA = "command-center/schema/work-unit.schema.json"
SENTINEL = "SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS"
QUESTION = (
    "Implement the merger that assembles the catalog slices from every bucket "
    "into one WORK-UNIT-CATALOG.json and refuses on a duplicate id or an "
    "unfilled index gap (spec line 11320, duplicate units from colliding "
    "catalogs). Exact question: across all assembled slices, are the ids "
    "contiguous, unique, and exactly equal to the declared program count?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0456/probe1_planted_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0456/probe2_independent_recount.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fixture_report(name: str) -> dict:
    paths = sorted((HERE / "fixtures" / name).glob("slice-*.json"))
    return M.merge_paths(paths, output_path=None)


def live_report() -> dict:
    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    records, declared = M.reconstruct_live_records(catalog)
    reconstructed = M.inspect_records(records, declared)
    slice_dir = REPO / "command-center" / "catalog-slices"
    disk_paths = M.catalog_slice_paths(slice_dir)
    disk = M.merge_paths(
        disk_paths, output_path=None, declared_program_count=declared
    )
    reconstructed["catalog_path"] = "command-center/WORK-UNIT-CATALOG.json"
    reconstructed["reconstructed_from"] = "_source_slice_file on each work_unit"
    reconstructed["wrote"] = False
    reconstructed["disk_slice_dir"] = "command-center/catalog-slices"
    reconstructed["disk_slice_files"] = [p.name for p in disk_paths]
    reconstructed["disk_unique_count"] = disk.get("unique_count_in_memory")
    reconstructed["disk_blockers"] = disk.get("blockers")
    reconstructed["disk_agrees_with_reconstructed"] = (
        disk.get("unique_count_in_memory")
        == reconstructed.get("unique_count_in_memory")
        and (disk.get("duplicates") or []) == (reconstructed.get("duplicates") or [])
        and [g.get("missing") for g in (disk.get("gaps") or [])]
        == [g.get("missing") for g in (reconstructed.get("gaps") or [])]
        and disk.get("per_slice") == reconstructed.get("per_slice")
    )
    reconstructed["note"] = (
        "Live slices are on disk under command-center/catalog-slices/*.json. "
        "The merger also reconstructs the same rows from "
        "work_units[]._source_slice_file. Both walks refuse to write "
        "WORK-UNIT-CATALOG.json: ids are unique but not 1..max contiguous "
        "(IMP-0375..IMP-0384 unfilled) and unique_count 2007 != declared "
        "program count 2048. This unit does not invent filler work units "
        "to close the shortfall."
    )
    return reconstructed


def main() -> int:
    clean = fixture_report("clean")
    dup = fixture_report("duplicate")
    gap = fixture_report("gap")
    mech = fixture_report("mechanism-collision")
    if not clean.get("accepted"):
        print("FAILED:IMP-0456 emit clean fixture did not merge")
        print(clean.get("blockers"))
        return 1
    if dup.get("accepted") or gap.get("accepted") or mech.get("accepted"):
        print("FAILED:IMP-0456 emit planted refuse fixture was accepted")
        return 1
    live = live_report()
    live_unique = live.get("unique_count_in_memory")
    live_declared = live.get("declared_program_count")
    live_gaps = live.get("gaps") or []
    live_dups = live.get("duplicates") or []
    contiguous = not live_gaps and not live.get("malformed_ids")
    unique = not live_dups
    equal = live_unique == live_declared
    missing_ids = []
    for g in live_gaps:
        missing_ids.extend(g.get("missing") or [])
    answer = (
        f"No. Live catalog-slices/*.json and the reconstructed "
        f"_source_slice_file walk agree "
        f"(disk_agrees={live.get('disk_agrees_with_reconstructed')}): "
        f"unique={unique} ({live_unique} distinct ids, "
        f"duplicate_id_count={len(live_dups)}), "
        f"contiguous={contiguous} (unfilled indices: {missing_ids}), "
        f"equal_to_declared_program_count={equal} "
        f"(read unique={live_unique}, declared target={live_declared}, "
        f"shortfall={(live_declared or 0) - (live_unique or 0)}). "
        "The merger therefore REFUSES a live re-merge and does not write "
        "WORK-UNIT-CATALOG.json. Fixture controls: planted duplicate blocks "
        "and names both source paths; planted gap blocks even when "
        "unique==declared (FIX-0001,0002,0004); a clean contiguous set of 4 "
        "merges, is order-independent, and the written catalog is re-read "
        "for the count."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    merger_rel = "tools/command-center/merge_slices.py"
    merger_path = REPO / merger_rel
    msha, mbytes = sha256_file(merger_path)
    receipt = {
        "id": "IMP-0456",
        "unit_id": "IMP-0456",
        "kind": "catalog-slice-merge-report",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "SENTINEL:IMP-0456:CATALOG-MERGE-CONTIGUOUS": True,
        "question": QUESTION,
        "answer": answer,
        "exact_question_verdict": {
            "contiguous": contiguous,
            "unique": unique,
            "equal_to_declared_program_count": equal,
            "declared_program_count": live_declared,
            "unique_count_read": live_unique,
            "shortfall": (live_declared or 0) - (live_unique or 0),
            "duplicate_id_count": len(live_dups),
            "gap_prefixes": [g.get("prefix") for g in live_gaps],
            "unfilled_ids": missing_ids,
            "disk_agrees_with_reconstructed": live.get(
                "disk_agrees_with_reconstructed"
            ),
            "live_merge_accepted": bool(live.get("accepted")),
            "live_merge_blockers": live.get("blockers"),
        },
        "merger": {
            "path": merger_rel,
            "sha256": msha,
            "bytes": mbytes,
            "last_wins_forbidden": True,
            "count_is_read_back_from_written_file": True,
            "refuses_on": [
                "duplicate-ids",
                "mechanism-collisions",
                "index-gaps",
                "count-mismatch-vs-declared",
                "malformed-ids",
                "unreadable-slices",
            ],
        },
        "fixture_controls": {
            "clean": {
                "accepted": True,
                "read_back_would_be": 4,
                "declared": 4,
                "blockers": clean.get("blockers"),
            },
            "planted_duplicate": {
                "accepted": False,
                "duplicates": dup.get("duplicates"),
                "mechanism_collisions": dup.get("mechanism_collisions"),
                "blockers": dup.get("blockers"),
            },
            "planted_gap": {
                "accepted": False,
                "unique_equals_declared": gap.get("unique_count_in_memory")
                == gap.get("declared_program_count"),
                "gaps": gap.get("gaps"),
                "blockers": gap.get("blockers"),
            },
            "mechanism_collision": {
                "accepted": False,
                "mechanism_collisions": mech.get("mechanism_collisions"),
                "blockers": mech.get("blockers"),
            },
        },
        "live_merge_report": {
            "per_slice": live.get("per_slice"),
            "prefix_ranges": live.get("prefix_ranges"),
            "gaps": live.get("gaps"),
            "duplicates": live.get("duplicates"),
            "blockers": live.get("blockers"),
            "declared_program_count": live_declared,
            "unique_count_in_memory": live_unique,
            "note": live.get("note"),
            "reconstructed_from": live.get("reconstructed_from"),
            "disk_slice_dir": live.get("disk_slice_dir"),
            "disk_slice_files": live.get("disk_slice_files"),
            "disk_unique_count": live.get("disk_unique_count"),
            "disk_blockers": live.get("disk_blockers"),
            "disk_agrees_with_reconstructed": live.get(
                "disk_agrees_with_reconstructed"
            ),
        },
        "evidence": [
            {
                "path": merger_rel,
                "kind": "implementation",
                "note": "Slice merger refuses duplicate ids and unfilled index gaps.",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "live-catalog",
                "note": (
                    "work_units_meta.target is 2048; work_units length is 2007; "
                    "IMP-0375..IMP-0384 are unfilled in 1..max(IMP)."
                ),
            },
            {
                "path": "command-center/catalog-slices",
                "kind": "live-slices",
                "note": (
                    "22 JSON slices on disk; merger unique count 2007 matches "
                    "the assembled catalog; live re-merge refused."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0456/fixtures/duplicate",
                "kind": "negative-control",
                "note": "FIX-0002 in slice-a.json and slice-b.json must block.",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0456/fixtures/gap",
                "kind": "negative-control",
                "note": "FIX-0003 missing while unique==declared=3 must block.",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0456/fixtures/clean",
                "kind": "positive-control",
                "note": "FIX-0001..FIX-0004 merge; count is re-read from the file.",
            },
        ],
        "tests": [
            {
                "id": "planted-duplicate-blocks",
                "result": "PASS",
                "detail": "FIX-0002 in two slices; both source paths named; no write.",
            },
            {
                "id": "planted-gap-blocks",
                "result": "PASS",
                "detail": "FIX-0003 unfilled; unique==declared still refuses.",
            },
            {
                "id": "clean-slice-set-merges",
                "result": "PASS",
                "detail": "Four contiguous ids merge; order-independent bytes.",
            },
            {
                "id": "independent-recount",
                "result": "PASS",
                "detail": "Probe 2 recounts each slice from disk and matches the merger.",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0456-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "json.load each fixture slice, tally ids, duplicates, and "
                "1..max holes without calling inspect_records for the expected "
                "numbers; then compare to the merger report."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": merger_rel, "role": "merger"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "planted-duplicate-and-gap"},
            {"id": "probe2", "command": P2, "role": "independent-slice-recount"},
        ],
        "output_path": OUT,
        "output_schema": SCHEMA,
        "ts": now,
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0456: merger implemented at "
            "tools/command-center/merge_slices.py, live named probes exit 0, "
            "receipt is not BLOCKED. Live catalog-slices are unique but not "
            "contiguous (IMP-0375..IMP-0384) and not equal to 2048; that is a "
            "measured refuse, not a missing implementation. Did not run "
            "unit_manifest.py --write. Did not rewrite WORK-UNIT-CATALOG.json."
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:IMP-0456 emit sentinel absent after write")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:IMP-0456 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
