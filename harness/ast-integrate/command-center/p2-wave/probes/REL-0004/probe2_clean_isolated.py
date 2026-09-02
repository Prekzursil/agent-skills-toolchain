#!/usr/bin/env python3
"""Probe 2: isolation loud-fail + clean install, every contracted event observed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from drill import isolation_refuses_owner_home, run_clean_drill  # noqa: E402
from package_spec import CONTRACTED_EVENTS  # noqa: E402

ART = REPO / "command-center/receipts/REL-0004.json"


def main() -> int:
    refusal = isolation_refuses_owner_home()
    clean = run_clean_drill()
    rt = clean["runtime"]
    isolation = clean["isolation"]
    observed = [row["event"] for row in rt["events"] if row["verdict"] == "PASS"]
    not_checked = [row["event"] for row in rt["events"] if row["verdict"] != "PASS"]
    ok = (
        refusal["refused"]
        and rt["silent"]
        and isolation["owner_home_untouched"]
        and isolation["profile_is_throwaway"]
        and isolation["path_home_is_throwaway"]
        and not isolation["writes_under_owner"]
        and observed == list(CONTRACTED_EVENTS)
        and not not_checked
    )
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:REL-0004" not in json.dumps(doc):
            print("FAILED:REL-0004-probe2 sentinel absent from receipt")
            return 1
        if doc.get("state") != "SUCCESS":
            print("FAILED:REL-0004-probe2 receipt state", doc.get("state"))
            return 1
        iso = doc.get("isolation") or {}
        if iso.get("owner_home_untouched") is not True:
            print("FAILED:REL-0004-probe2 receipt isolation overclaim")
            return 1
    summary = {
        "contracted": list(CONTRACTED_EVENTS),
        "isolation_refused_owner_home": refusal["refused"],
        "not_checked": not_checked,
        "observed": observed,
        "owner_home_untouched": isolation["owner_home_untouched"],
        "pass": ok,
        "probe": "probe2-clean-isolated",
        "profile": clean["profile"],
        "runtime_silent": rt["silent"],
        "unit_id": "REL-0004",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"refused_owner={refusal['refused']} silent={rt['silent']} "
        f"observed={observed} untouched={isolation['owner_home_untouched']}"
    )
    if not ok:
        print("FAILED:REL-0004-probe2 isolation or clean runtime observation")
        return 1
    print("SUCCESS:REL-0004-probe2 isolation and clean-profile hook firing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
