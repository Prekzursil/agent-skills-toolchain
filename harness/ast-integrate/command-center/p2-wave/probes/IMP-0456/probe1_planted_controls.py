#!/usr/bin/env python3
"""Probe 1: planted duplicate must block; planted gap must block; clean set merges.

Last-wins on a colliding id is a FAIL. A count-only merger that accepts
FIX-0001, FIX-0002, FIX-0004 because unique==declared is a FAIL. Order of
slice paths must not change the clean merged bytes.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import merge_slices as M  # noqa: E402

FIX = HERE / "fixtures"


def slice_paths(name: str) -> list[Path]:
    d = FIX / name
    paths = sorted(d.glob("slice-*.json"))
    if len(paths) < 2:
        raise SystemExit(f"FAILED:IMP-0456-probe1 missing slices in {d}")
    return paths


def must_block(name: str, *, need_dup: bool, need_gap: bool, need_mech: bool) -> dict:
    out = Path(tempfile.mkdtemp(prefix=f"imp0456-{name}-")) / "merged.json"
    report = M.merge_paths(slice_paths(name), output_path=out)
    if report.get("accepted"):
        print(f"FAILED:IMP-0456-probe1 {name} was accepted")
        print(json.dumps(report, indent=2, default=str)[:2000])
        raise SystemExit(1)
    if out.is_file():
        print(f"FAILED:IMP-0456-probe1 {name} last-wins wrote {out}")
        raise SystemExit(1)
    if report.get("wrote"):
        print(f"FAILED:IMP-0456-probe1 {name} wrote=true on a refuse")
        raise SystemExit(1)
    if need_dup:
        dups = report.get("duplicates") or []
        if not dups:
            print(f"FAILED:IMP-0456-probe1 {name} refused without naming duplicates")
            raise SystemExit(1)
        sources = set()
        for row in dups:
            if row.get("id") == "FIX-0002" or name != "duplicate":
                sources.update(row.get("sources") or [])
        if name == "duplicate":
            if "slice-a.json" not in sources or "slice-b.json" not in sources:
                print("FAILED:IMP-0456-probe1 duplicate did not name both source paths")
                print(dups)
                raise SystemExit(1)
            if not any(r.get("id") == "FIX-0002" for r in dups):
                print("FAILED:IMP-0456-probe1 duplicate id FIX-0002 not listed")
                raise SystemExit(1)
    if need_gap:
        gaps = report.get("gaps") or []
        missing = []
        for g in gaps:
            missing.extend(g.get("missing") or [])
        if "FIX-0003" not in missing:
            print("FAILED:IMP-0456-probe1 gap did not name unfilled FIX-0003")
            print(gaps)
            raise SystemExit(1)
        # Count matches declared (3 unique, declared 3) so a count-only gate
        # would accept. Contiguity must still refuse.
        if report.get("unique_count_in_memory") != 3:
            print(
                "FAILED:IMP-0456-probe1 gap fixture unique_count is not 3; "
                "count-only control is mis-set"
            )
            raise SystemExit(1)
        if "index-gaps" not in " ".join(report.get("blockers") or []):
            print("FAILED:IMP-0456-probe1 gap blockers omit index-gaps")
            print(report.get("blockers"))
            raise SystemExit(1)
    if need_mech:
        mechs = report.get("mechanism_collisions") or []
        expect_id = "FIX-0001" if name == "mechanism-collision" else "FIX-0002"
        if not mechs or not any(m.get("id") == expect_id for m in mechs):
            print(
                f"FAILED:IMP-0456-probe1 {name} mechanism collision "
                f"{expect_id} not enumerated"
            )
            print(mechs)
            raise SystemExit(1)
    return report


def must_merge_clean() -> dict:
    paths = slice_paths("clean")
    tmp = Path(tempfile.mkdtemp(prefix="imp0456-clean-"))
    out_ab = tmp / "ab.json"
    out_ba = tmp / "ba.json"
    r1 = M.merge_paths(paths, output_path=out_ab)
    r2 = M.merge_paths(list(reversed(paths)), output_path=out_ba)
    if not r1.get("accepted") or not r2.get("accepted"):
        print("FAILED:IMP-0456-probe1 clean set did not merge")
        print(r1.get("blockers"), r2.get("blockers"))
        raise SystemExit(1)
    if not out_ab.is_file() or not out_ba.is_file():
        print("FAILED:IMP-0456-probe1 clean merge did not write")
        raise SystemExit(1)
    if out_ab.read_bytes() != out_ba.read_bytes():
        print("FAILED:IMP-0456-probe1 merge is order-dependent")
        raise SystemExit(1)
    back = M.read_back_count(out_ab)
    if back != 4 or r1.get("read_back_count") != 4:
        print(f"FAILED:IMP-0456-probe1 clean read-back is {back} not 4")
        raise SystemExit(1)
    if r1.get("unique_count_in_memory") == 4 and r1.get("read_back_count") is None:
        print("FAILED:IMP-0456-probe1 claimed count without reading the file")
        raise SystemExit(1)
    doc = json.loads(out_ab.read_text(encoding="utf-8"))
    ids = [u["id"] for u in doc["work_units"]]
    if ids != ["FIX-0001", "FIX-0002", "FIX-0003", "FIX-0004"]:
        print("FAILED:IMP-0456-probe1 merged ids not contiguous sorted", ids)
        raise SystemExit(1)
    return r1


def main() -> int:
    dup = must_block("duplicate", need_dup=True, need_gap=False, need_mech=True)
    gap = must_block("gap", need_dup=False, need_gap=True, need_mech=False)
    mech = must_block(
        "mechanism-collision", need_dup=True, need_gap=False, need_mech=True
    )
    clean = must_merge_clean()
    summary = {
        "clean_accepted": True,
        "clean_read_back": clean.get("read_back_count"),
        "duplicate_blocked": True,
        "duplicate_sources": (dup.get("duplicates") or [{}])[0].get("sources"),
        "gap_blocked": True,
        "gap_missing": (gap.get("gaps") or [{}])[0].get("missing"),
        "mechanism_blocked": True,
        "mechanism_id": (mech.get("mechanism_collisions") or [{}])[0].get("id"),
        "order_independent": True,
        "pass": True,
        "probe": "probe1-planted-controls",
        "unit_id": "IMP-0456",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "duplicate_blocked=True gap_blocked=True clean_merged=True "
        "last_wins=False count_only_would_pass_gap=True"
    )
    print("SUCCESS:IMP-0456-probe1 planted duplicate/gap block; clean merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
