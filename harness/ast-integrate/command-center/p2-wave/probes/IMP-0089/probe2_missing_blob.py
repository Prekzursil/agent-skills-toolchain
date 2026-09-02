"""Named probe 2: missing blob refuses; substituting mutant does not.

Different field from probe 1: refusal vs substitution, not census/health-check
of a successful rollback. The known-broken implementation must land on a
version other than the requested one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "marketplace" / "tests"))

from test_rollback_offline import (  # noqa: E402
    test_missing_blob_refuses_rather_than_substitutes,
)

ART = REPO / "command-center/receipts/IMP-0089.json"


def main() -> int:
    live = test_missing_blob_refuses_rather_than_substitutes()
    if not live.get("pass") or not live.get("refused"):
        print("FAILED:IMP-0089-probe2 missing blob was not refused")
        return 1
    if live.get("live_version_after_refuse") != "3.0.0":
        print("FAILED:IMP-0089-probe2 refuse mutated live version")
        return 1
    if not live.get("mutant_substituted"):
        print("FAILED:IMP-0089-probe2 substituting mutant refused (control silent)")
        return 1
    if live.get("mutant_landed_version") == "1.0.0":
        print("FAILED:IMP-0089-probe2 mutant landed on v1; control does not discriminate")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0089-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0089" not in json.dumps(doc):
        print("FAILED:IMP-0089-probe2 sentinel absent")
        return 1
    recorded = None
    for ev in doc.get("evidence") or []:
        if ev.get("anchor") == "missing-blob-refuse":
            recorded = ev.get("measured") or {}
    if recorded:
        if recorded.get("mutant_landed_version") != live.get("mutant_landed_version"):
            print("FAILED:IMP-0089-probe2 mutant version drift vs receipt")
            return 1
    out = {
        "probe": "probe2-missing-blob-refuse",
        "unit_id": "IMP-0089",
        "pass": True,
        "refused": True,
        "live_version_after_refuse": live["live_version_after_refuse"],
        "mutant_substituted": True,
        "mutant_landed_version": live["mutant_landed_version"],
        "mutant_census_equals_v1": live.get("mutant_census_equals_v1"),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"refused=True stayed={live['live_version_after_refuse']} "
        f"mutant_landed={live['mutant_landed_version']}"
    )
    print("SUCCESS:IMP-0089-probe2 missing blob refuses rather than substitutes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
