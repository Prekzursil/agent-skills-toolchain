#!/usr/bin/env python3
"""IMP-0005 probe1: dual-library census + measurement-derived budget.

Rebuilt 2026-10-26 (shard-6 wave-4 resume): the original probe was lost with
the mid-flight host death; this re-derivation anchors on the same receipts.

Two independent signals per the unit's evidence_requirement:
  S1: the budget checker's own computed totals (size_budget.derive_budget
      over a measured previous-release archive).
  S2: the OS-reported archive size and an independent entry count from a
      DIFFERENT archive library (zip_cd raw central-directory reader and the
      ustar reader on a tar twin -- not zipfile/tarfile).
A count mismatch between the two libraries is a detector failure: exit non-zero.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import fixtures as fx  # noqa: E402
from archive_census import census  # noqa: E402
from size_budget import (  # noqa: E402
    budget_copied_from_current,
    check_archive,
    derive_budget,
)
from ustar import read_entries as ustar_read  # noqa: E402
from zip_cd import read_entries as zip_cd_read  # noqa: E402


def main() -> int:
    facts: dict = {"unit_id": "IMP-0005", "probe": "probe1-dual-census"}
    checks: list[dict] = []

    def chk(name: str, ok: bool) -> bool:
        checks.append({"check": name, "ok": bool(ok)})
        return bool(ok)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "prev.zip")
        tar_prev = fx.write_tar(tmp / "prev.tar", fx.PREVIOUS_FILES)

        # S1: budget checker's computed totals (derived, not asserted).
        budget = derive_budget(previous)

        # S2: OS-reported size + independent-library entry counts.
        os_bytes = os.stat(previous).st_size
        zc_rows = zip_cd_read(previous)
        ut_rows = ustar_read(tar_prev)
        z = census(previous)
        t = census(tar_prev)

        chk("budget_derived_from_measurement", budget.derivation["measured_archive_bytes"] == os_bytes)
        chk("budget_max_bytes_formula", budget.max_bytes == os_bytes + max(4096, os_bytes // 2))
        chk("budget_max_file_count_formula", budget.max_file_count == z["file_count"] + 8)
        chk("primary_and_zip_cd_agree", len(zc_rows) == z["file_count"])
        chk("tarfile_and_ustar_agree", len(ut_rows) == t["file_count"])
        chk("zip_and_tar_censuses_agree", z["file_count"] == t["file_count"] and z["payload_bytes"] == t["payload_bytes"])
        chk("independent_library_is_not_primary", z["independent"]["library"] != z["primary"]["library"])
        chk("census_os_bytes_match_stat", z["os_archive_bytes"] == os_bytes)
        chk("previous_release_within_its_budget", check_archive(previous, budget)["ok"])
        chk("budget_not_copied_from_current", not budget_copied_from_current(budget, fx.current_ok_zip(tmp / "curr.zip")))

        facts["signal1_budget_totals"] = {
            "max_bytes": budget.max_bytes,
            "max_file_count": budget.max_file_count,
            "derivation": budget.derivation,
        }
        facts["signal2_census"] = {
            "os_archive_bytes": os_bytes,
            "zipfile_count": z["file_count"],
            "zip_cd_count": len(zc_rows),
            "tarfile_count": t["file_count"],
            "ustar_count": len(ut_rows),
            "payload_bytes_zip": z["payload_bytes"],
            "payload_bytes_tar": t["payload_bytes"],
            "primary_library": z["primary"]["library"],
            "independent_library": z["independent"]["library"],
        }
        facts["checks"] = checks
        facts["all_ok"] = all(c["ok"] for c in checks)
        print(json.dumps(facts, indent=1))
        if not facts["all_ok"]:
            print("FAILED:IMP-0005-probe1 dual-census or budget-derivation check failed")
            return 1
    print("SUCCESS:IMP-0005-probe1 dual-library census agrees; budget derived from measurement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
