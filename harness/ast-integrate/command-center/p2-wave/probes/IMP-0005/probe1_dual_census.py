#!/usr/bin/env python3
"""Named probe 1: two independent archive readings must agree, then the budget gate fires.

Signal 1: budget checker totals (zipfile/tarfile payload + file count).
Signal 2: OS st_size and an independent library (ZIP central directory / ustar).
A count mismatch is a detector failure, not a budget finding.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import fixtures as fx  # noqa: E402
from archive_census import DetectorFailure, census  # noqa: E402
from size_budget import check_archive, derive_budget  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0005.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0005-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0005":
        print("FAILED:IMP-0005-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0005" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0005-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0005-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0005-p1-") as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "previous.zip")
        current = fx.current_ok_zip(tmp / "current.zip")
        bloated = fx.over_budget_zip(tmp / "bloated.zip")
        tar_prev = fx.write_tar(tmp / "previous.tar", fx.PREVIOUS_FILES)

        z = census(previous)
        t = census(tar_prev)
        if z["file_count"] != t["file_count"] or z["payload_bytes"] != t["payload_bytes"]:
            print("FAILED:IMP-0005-probe1 zip/tar disagreement")
            print(json.dumps({"zip": z, "tar": t}, default=str)[:2000])
            return 1
        if z["independent"]["library"] == z["primary"]["library"]:
            print("FAILED:IMP-0005-probe1 independent library is not independent")
            return 1
        if z["os_archive_bytes"] != previous.stat().st_size:
            print("FAILED:IMP-0005-probe1 OS size mismatch")
            return 1
        plant = [e for e in z["primary"]["entries"] if e["path"] == fx.PLANT_PATH]
        plant_i = [e for e in z["independent"]["entries"] if e["path"] == fx.PLANT_PATH]
        if not plant or not plant_i:
            print("FAILED:IMP-0005-probe1 planted control not seen by both readers")
            return 1

        truncated = tmp / "truncated.zip"
        truncated.write_bytes(previous.read_bytes()[:40])
        try:
            census(truncated)
        except DetectorFailure:
            detector_fired = True
        else:
            detector_fired = False
        if not detector_fired:
            print("FAILED:IMP-0005-probe1 truncated zip did not trip detector")
            return 1

        budget = derive_budget(previous)
        ok = check_archive(current, budget)
        bad = check_archive(bloated, budget)
        if not ok["ok"]:
            print("FAILED:IMP-0005-probe1 in-budget current failed", ok)
            return 1
        if bad["ok"] or not any(v.startswith("max_bytes:") for v in bad["violations"]):
            print("FAILED:IMP-0005-probe1 bloated archive did not fail max_bytes", bad)
            return 1
        if ok["independent_file_count"] != ok["file_count"]:
            print("FAILED:IMP-0005-probe1 detector mismatch on current")
            return 1

    summary = {
        "probe": "probe1-dual-census",
        "unit_id": "IMP-0005",
        "pass": True,
        "zip_count": z["file_count"],
        "tar_count": t["file_count"],
        "primary_library": z["primary"]["library"],
        "independent_library": z["independent"]["library"],
        "os_archive_bytes": z["os_archive_bytes"],
        "planted_control_found": True,
        "detector_fired_on_truncated": True,
        "in_budget_ok": ok["ok"],
        "over_budget_fired": (not bad["ok"]),
        "budget_max_bytes": budget.max_bytes,
        "budget_measured_from_previous": budget.derivation["measured_archive_bytes"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"zip_count={z['file_count']} tar_count={t['file_count']} "
        f"indep={z['independent']['library']} os_bytes={z['os_archive_bytes']} "
        f"in_budget={ok['ok']} over_budget_fired={not bad['ok']}"
    )
    print("SUCCESS:IMP-0005-probe1 dual census and budget gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
