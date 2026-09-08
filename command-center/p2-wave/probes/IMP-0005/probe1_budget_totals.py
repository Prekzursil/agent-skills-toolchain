#!/usr/bin/env python3
"""IMP-0005 probe1: budget checker's computed totals on a packed artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import pack as pack_mod  # noqa: E402
import size_budget as budget_mod  # noqa: E402

PROBE = Path(__file__).resolve().parent
WORK = PROBE / "work" / "probe1"
OUT = WORK / "artifact.zip"
EVIDENCE = (
    "TWO independent signals: (1) the budget checker's computed totals; "
    "(2) the OS-reported artifact size and an independent entry count from a "
    "different archive library. A mismatch between the two counts is a "
    "detector failure and blocks the unit."
)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "NAMED PROBE 1: BUDGET CHECKER COMPUTED TOTALS",
        "PROBE-1-BEGIN:IMP-0005",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"repo={REPO}",
        "prefix=tools/plugin",
    ]
    result = pack_mod.pack(
        repo=REPO,
        rev="HEAD",
        allowlist=REPO / "tools/plugin/payload-allowlist.json",
        out=OUT,
        prefix="tools/plugin",
        use_real_mtimes=False,
    )
    # Re-measure via the budget checker (signal 1) — not a copy of PackResult.
    max_bytes, max_files = budget_mod.load_budget(
        REPO / "tools/plugin/payload-allowlist.json"
    )
    totals = budget_mod.check_budget(
        OUT, max_bytes=max_bytes, max_files=max_files
    )
    # Detector self-consistency: packer size_bytes must match checker.
    pack_vs_checker = result.size_bytes == totals.size_bytes
    member_vs_checker = len(result.members) == totals.file_count
    ok = (
        totals.within_budget
        and pack_vs_checker
        and member_vs_checker
        and totals.size_bytes > 0
        and totals.file_count > 0
    )
    meas = {
        "ok": ok,
        "archive": str(OUT.relative_to(REPO)) if OUT.is_relative_to(REPO) else str(OUT),
        "budget_checker": totals.as_dict(),
        "pack_size_bytes": result.size_bytes,
        "pack_member_count": len(result.members),
        "pack_vs_checker_size_equal": pack_vs_checker,
        "pack_vs_checker_count_equal": member_vs_checker,
        "max_bytes_source": "tools/plugin/payload-allowlist.json#budget.max_bytes",
        "max_files_source": "tools/plugin/payload-allowlist.json#budget.max_files",
        "max_bytes_declared": max_bytes,
        "max_files_declared": max_files,
        "budget_copied_from_artifact_size": False,
        "note": (
            "max_bytes/max_files come from the allowlist declaration; "
            "totals.size_bytes/file_count are measured from the archive"
        ),
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines.extend(
        [
            f"archive={meas['archive']}",
            f"budget_checker_size_bytes={totals.size_bytes}",
            f"budget_checker_file_count={totals.file_count}",
            f"max_bytes_declared={max_bytes}",
            f"max_files_declared={max_files}",
            f"within_budget={totals.within_budget}",
            f"pack_vs_checker_size_equal={pack_vs_checker}",
            f"pack_vs_checker_count_equal={member_vs_checker}",
            "budget_copied_from_artifact_size=False",
            f"probe_1_confirmed={ok}",
            "PROBE-1-COMPLETE:IMP-0005",
            "SUCCESS:IMP-0005-probe1" if ok else "FAILED:IMP-0005-probe1",
        ]
    )
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-budget-totals.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
