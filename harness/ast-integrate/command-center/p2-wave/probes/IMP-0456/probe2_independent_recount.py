#!/usr/bin/env python3
"""Probe 2: independent recount of each slice from files on disk.

Does not trust merge_slices.inspect_records for the expected numbers. Parses
each fixture JSON with json.load, counts ids, finds duplicates and 1..max
holes, then compares the merger's report to that independent tally.

A merger that reports unique=declared without walking the files fails here
when the independent walk disagrees.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import merge_slices as M  # noqa: E402

ID_RE = re.compile(r"^([A-Z]{2,5})-(\d{4})$")
FIX = HERE / "fixtures"


def independent_walk(slice_dir: Path) -> dict:
    """Recount from bytes on disk. No import of inspect_records."""
    by_id: dict[str, list[str]] = defaultdict(list)
    per_slice: dict[str, int] = {}
    declared: set[int] = set()
    for path in sorted(slice_dir.glob("slice-*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        units = doc.get("work_units")
        if not isinstance(units, list):
            raise SystemExit(f"FAILED:IMP-0456-probe2 {path.name} has no work_units")
        per_slice[path.name] = len(units)
        if "declared_program_count" in doc:
            declared.add(int(doc["declared_program_count"]))
        for unit in units:
            uid = str(unit.get("id") or "")
            by_id[uid].append(path.name)
    dups = {uid: srcs for uid, srcs in by_id.items() if len(srcs) > 1}
    by_prefix: dict[str, set[int]] = defaultdict(set)
    malformed = []
    for uid in by_id:
        m = ID_RE.match(uid)
        if not m:
            malformed.append(uid)
            continue
        by_prefix[m.group(1)].add(int(m.group(2), 10))
    holes = []
    for prefix, nums in sorted(by_prefix.items()):
        mx = max(nums)
        for n in range(1, mx + 1):
            if n not in nums:
                holes.append(f"{prefix}-{n:04d}")
    if len(declared) != 1:
        raise SystemExit(f"FAILED:IMP-0456-probe2 declared votes {declared}")
    return {
        "declared": next(iter(declared)),
        "duplicates": dups,
        "holes": holes,
        "malformed": malformed,
        "per_slice": per_slice,
        "unique": len(by_id),
    }


def compare(name: str) -> dict:
    indep = independent_walk(FIX / name)
    report = M.merge_paths(sorted((FIX / name).glob("slice-*.json")))
    merger_dups = {d["id"] for d in (report.get("duplicates") or [])}
    indep_dups = set(indep["duplicates"])
    if merger_dups != indep_dups:
        print(f"FAILED:IMP-0456-probe2 {name} duplicate set mismatch")
        print("independent", sorted(indep_dups))
        print("merger", sorted(merger_dups))
        raise SystemExit(1)
    merger_holes = []
    for g in report.get("gaps") or []:
        merger_holes.extend(g.get("missing") or [])
    if set(merger_holes) != set(indep["holes"]):
        print(f"FAILED:IMP-0456-probe2 {name} gap set mismatch")
        print("independent", indep["holes"])
        print("merger", merger_holes)
        raise SystemExit(1)
    if report.get("unique_count_in_memory") != indep["unique"]:
        print(
            f"FAILED:IMP-0456-probe2 {name} unique "
            f"merger={report.get('unique_count_in_memory')} indep={indep['unique']}"
        )
        raise SystemExit(1)
    merger_per = {row["source"]: row["count"] for row in (report.get("per_slice") or [])}
    if merger_per != indep["per_slice"]:
        print(f"FAILED:IMP-0456-probe2 {name} per-slice count mismatch")
        print("independent", indep["per_slice"])
        print("merger", merger_per)
        raise SystemExit(1)
    expect_accept = (
        not indep["duplicates"]
        and not indep["holes"]
        and not indep["malformed"]
        and indep["unique"] == indep["declared"]
    )
    if bool(report.get("accepted")) != expect_accept:
        print(
            f"FAILED:IMP-0456-probe2 {name} accepted={report.get('accepted')} "
            f"independent expect_accept={expect_accept}"
        )
        raise SystemExit(1)
    return {
        "name": name,
        "declared": indep["declared"],
        "unique": indep["unique"],
        "per_slice": indep["per_slice"],
        "duplicates": sorted(indep_dups),
        "holes": indep["holes"],
        "accepted": bool(report.get("accepted")),
    }


def main() -> int:
    rows = [
        compare("clean"),
        compare("duplicate"),
        compare("gap"),
        compare("mechanism-collision"),
    ]
    by = {r["name"]: r for r in rows}
    if not by["clean"]["accepted"]:
        print("FAILED:IMP-0456-probe2 independent recount expected clean accept")
        return 1
    if by["duplicate"]["accepted"] or by["gap"]["accepted"]:
        print("FAILED:IMP-0456-probe2 independent recount expected refuse")
        return 1
    if by["gap"]["unique"] != by["gap"]["declared"]:
        print("FAILED:IMP-0456-probe2 gap unique!=declared; control is broken")
        return 1
    if "FIX-0003" not in by["gap"]["holes"]:
        print("FAILED:IMP-0456-probe2 independent walk missed FIX-0003")
        return 1
    summary = {
        "pass": True,
        "probe": "probe2-independent-recount",
        "rows": rows,
        "unit_id": "IMP-0456",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "independent_recount_agrees=True clean_accept=True "
        "duplicate_refuse=True gap_refuse=True"
    )
    print("SUCCESS:IMP-0456-probe2 independent slice recount from disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
