#!/usr/bin/env python3
"""IMP-0005 probe2: OS st_size + independent entry count via Info-ZIP unzip.

Uses a *different* archive library than the budget checker (stdlib zipfile).
Mismatch between budget-checker totals and these independent measurements is
a detector failure.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import pack as pack_mod  # noqa: E402
import size_budget as budget_mod  # noqa: E402
import inventory_diff as inv_mod  # noqa: E402

PROBE = Path(__file__).resolve().parent
WORK = PROBE / "work" / "probe2"
CURRENT_ZIP = WORK / "current.zip"
PREV_ZIP = WORK / "previous.zip"
EVIDENCE = (
    "TWO independent signals: (1) the budget checker's computed totals; "
    "(2) the OS-reported artifact size and an independent entry count from a "
    "different archive library. A mismatch between the two counts is a "
    "detector failure and blocks the unit."
)


def _unzip_file_count(archive: Path) -> tuple[int, str]:
    """Count non-directory members via Info-ZIP ``unzip -Z1`` (not zipfile)."""
    proc = subprocess.run(
        ["unzip", "-Z1", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0,):
        # Some unzip builds return 0 always for -Z1; treat non-zero as failure.
        raise RuntimeError(
            f"unzip -Z1 failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )
    names = [ln for ln in (proc.stdout or "").splitlines() if ln and not ln.endswith("/")]
    return len(names), "unzip-Z1"


def _unzip_l_file_count(archive: Path) -> int:
    """Fallback parser for ``unzip -l`` listing (still Info-ZIP, not zipfile)."""
    proc = subprocess.run(
        ["unzip", "-l", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"unzip -l failed: {(proc.stderr or '').strip()}")
    # Final summary line: "   N files"
    m = re.search(r"(\d+)\s+files?\s*$", (proc.stdout or ""), re.MULTILINE)
    if not m:
        raise RuntimeError("unzip -l: could not parse file count summary")
    return int(m.group(1))


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "NAMED PROBE 2: OS SIZE + INDEPENDENT UNZIP ENTRY COUNT + INVENTORY DIFF",
        "PROBE-2-BEGIN:IMP-0005",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        "independent_archive_library=Info-ZIP unzip (not stdlib zipfile)",
    ]

    # Current release artifact via packer.
    pack_mod.pack(
        repo=REPO,
        rev="HEAD",
        allowlist=REPO / "tools/plugin/payload-allowlist.json",
        out=CURRENT_ZIP,
        prefix="tools/plugin",
        use_real_mtimes=False,
    )

    # Signal 1 (budget checker / zipfile).
    max_bytes, max_files = budget_mod.load_budget(
        REPO / "tools/plugin/payload-allowlist.json"
    )
    checker = budget_mod.check_budget(
        CURRENT_ZIP, max_bytes=max_bytes, max_files=max_files
    )

    # Signal 2: OS-reported size + Info-ZIP entry count.
    os_size = os.stat(CURRENT_ZIP).st_size
    try:
        unzip_count, unzip_method = _unzip_file_count(CURRENT_ZIP)
    except RuntimeError as exc:
        lines.append(f"unzip_Z1_error={exc}")
        unzip_count = _unzip_l_file_count(CURRENT_ZIP)
        unzip_method = "unzip-l"

    size_match = checker.size_bytes == os_size
    count_match = checker.file_count == unzip_count
    detector_ok = size_match and count_match

    # Inventory diff: previous = current minus one member grown/removed/added
    # Simulate previous release by building inventories from two zips.
    # previous: pack again then strip conceptually via inventory mutation.
    pack_mod.pack(
        repo=REPO,
        rev="HEAD",
        allowlist=REPO / "tools/plugin/payload-allowlist.json",
        out=PREV_ZIP,
        prefix="tools/plugin",
        use_real_mtimes=False,
    )
    cur_inv = inv_mod.inventory_from_zip(CURRENT_ZIP, version="0.0.2")
    prev_inv = inv_mod.inventory_from_zip(PREV_ZIP, version="0.0.1")
    # Plant classification: remove one path from prev, shrink one, add phantom to prev
    # so current shows added+removed+grown relative to a synthetic previous.
    if len(prev_inv["entries"]) < 2:
        raise SystemExit("need >=2 members for inventory classification plant")
    entries_prev = list(prev_inv["entries"])
    grown_target = dict(entries_prev[0])
    removed_only_in_prev = dict(entries_prev[1])
    # Previous: smaller grown_target, includes removed_only_in_prev, lacks a new path
    grown_target["size"] = max(0, int(grown_target["size"]) - 1) if grown_target["size"] else 0
    # Force growth: ensure previous size is strictly less than current for that path
    for e in cur_inv["entries"]:
        if e["path"] == grown_target["path"]:
            if e["size"] <= grown_target["size"]:
                grown_target["size"] = max(0, e["size"] - 1)
            break
    prev_entries = [
        grown_target,
        removed_only_in_prev,
        *[
            e
            for e in entries_prev
            if e["path"] not in {grown_target["path"], removed_only_in_prev["path"]}
        ],
    ]
    # Drop one current-only path from previous → it becomes "added"
    # Ensure removed_only_in_prev is NOT in current inventory for "removed"
    cur_entries = [e for e in cur_inv["entries"] if e["path"] != removed_only_in_prev["path"]]
    # Add a brand-new path only in current
    cur_entries.append(
        {
            "path": "__imp0005_added__.txt",
            "size": 42,
            "sha256": "f" * 64,
            "rule": "plant",
        }
    )
    prev_doc = {
        **prev_inv,
        "entries": prev_entries,
        "file_count": len(prev_entries),
        "total_bytes": sum(e["size"] for e in prev_entries),
    }
    cur_doc = {
        **cur_inv,
        "entries": cur_entries,
        "file_count": len(cur_entries),
        "total_bytes": sum(e["size"] for e in cur_entries),
    }
    diff = inv_mod.inventory_diff(prev_doc, cur_doc)
    class_ok = (
        "__imp0005_added__.txt" in diff["added"]
        and removed_only_in_prev["path"] in diff["removed"]
        and any(g["path"] == grown_target["path"] for g in diff["grown"])
    )

    ok = detector_ok and class_ok and checker.within_budget
    meas = {
        "ok": ok,
        "budget_checker_size_bytes": checker.size_bytes,
        "budget_checker_file_count": checker.file_count,
        "os_stat_size_bytes": os_size,
        "unzip_entry_count": unzip_count,
        "unzip_method": unzip_method,
        "independent_library": "Info-ZIP unzip",
        "budget_library": "stdlib zipfile",
        "size_match": size_match,
        "count_match": count_match,
        "detector_ok": detector_ok,
        "inventory_diff": {
            "added": diff["added"],
            "removed": diff["removed"],
            "grown_paths": [g["path"] for g in diff["grown"]],
            "classification_ok": class_ok,
        },
        "mismatch_is_detector_failure": True,
    }
    (PROBE / "probe2-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (PROBE / "inventory-diff.json").write_text(
        json.dumps(diff, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines.extend(
        [
            f"budget_checker_size_bytes={checker.size_bytes}",
            f"budget_checker_file_count={checker.file_count}",
            f"os_stat_size_bytes={os_size}",
            f"unzip_entry_count={unzip_count}",
            f"unzip_method={unzip_method}",
            f"size_match={size_match}",
            f"count_match={count_match}",
            f"detector_ok={detector_ok}",
            f"inventory_added={diff['added']}",
            f"inventory_removed={diff['removed']}",
            f"inventory_grown={[g['path'] for g in diff['grown']]}",
            f"classification_ok={class_ok}",
            f"probe_2_confirmed={ok}",
            "PROBE-2-COMPLETE:IMP-0005",
            "SUCCESS:IMP-0005-probe2" if ok else "FAILED:IMP-0005-probe2",
        ]
    )
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe2-os-unzip.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
