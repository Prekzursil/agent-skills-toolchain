"""Both-states controls for the WFA-0069 adoption smoke harness."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smoke import ADOPT, UNKNOWN, run_one

HERE = Path(__file__).resolve().parent
GOOD = HERE / "fixtures" / "adopted-good.json"


def run_both_states(scratch: Path) -> dict[str, Any]:
    scratch.mkdir(parents=True, exist_ok=True)
    receipts = scratch / "receipts"
    good_src = scratch / "good.json"
    broken_src = scratch / "broken.json"
    empty_src = scratch / "unconstructable.json"

    good_doc = json.loads(GOOD.read_text(encoding="utf-8"))
    good_src.write_text(json.dumps(good_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    broken = json.loads(json.dumps(good_doc))
    broken["id"] = "wfa-0069-control-broken"
    broken["smoke_case"]["steps"][-1]["equals"] = "MUST-FAIL"
    broken_src.write_text(json.dumps(broken, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    empty_src.write_text("{}\n", encoding="utf-8")

    good = run_one("wfa-0069-control-adopted", str(good_src), receipts)
    broken_row = run_one("wfa-0069-control-broken", str(broken_src), receipts)
    missing = run_one("wfa-0069-control-unconstructable", str(empty_src), receipts)

    good_pass = (
        good["disposition"] == ADOPT
        and good["smoke_run"]["terminal"] == "PASS"
        and good["smoke_run"]["constructed"] is True
    )
    broken_fail = (
        broken_row["disposition"] == UNKNOWN
        and broken_row["smoke_run"]["terminal"] == "FAIL"
        and broken_row["smoke_run"]["constructed"] is True
    )
    unconstructable_ok = (
        missing["disposition"] == UNKNOWN
        and missing["smoke_run"]["constructed"] is False
        and missing["smoke_run"]["terminal"] == "NOT-CONSTRUCTED"
    )
    return {
        "good_passed": good_pass,
        "broken_copy_failed_same_smoke": broken_fail,
        "unconstructable_reclassified": unconstructable_ok,
        "good_candidate_id": good["candidate_id"],
        "broken_candidate_id": broken_row["candidate_id"],
        "unconstructable_disposition": missing["disposition"],
        "good": good,
        "broken": broken_row,
        "unconstructable": missing,
        "ok": good_pass and broken_fail and unconstructable_ok,
    }
