"""Named probe 1: rollback uses no network; census + health-check agree.

Signal 1: owned-file census after rollback equals the census recorded when
that version was originally installed.
Signal 2: the installed plugin's own health-check reports the requested
version. Egress is blocked at the socket layer (reviewer requirement).
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
    test_rollback_then_forward_install_restores_original_census,
    test_rollback_uses_no_network,
)

ART = REPO / "command-center/receipts/IMP-0089.json"


def main() -> int:
    live = test_rollback_uses_no_network()
    roundtrip = test_rollback_then_forward_install_restores_original_census()
    if not live.get("pass") or not live.get("census_match"):
        print("FAILED:IMP-0089-probe1 live offline rollback")
        return 1
    if live.get("healthcheck_version") != "1.0.0":
        print("FAILED:IMP-0089-probe1 health-check version", live.get("healthcheck_version"))
        return 1
    if live.get("egress_attempts"):
        print("FAILED:IMP-0089-probe1 egress", live.get("egress_attempts"))
        return 1
    if not roundtrip.get("pass"):
        print("FAILED:IMP-0089-probe1 forward-install round-trip")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0089-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0089":
        print("FAILED:IMP-0089-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0089" not in text:
        print("FAILED:IMP-0089-probe1 sentinel absent")
        return 1
    recorded = ((doc.get("evidence") or [{}])[0].get("measured") or {})
    rec_census = recorded.get("census_v1")
    if rec_census and rec_census != live["census"]:
        print("FAILED:IMP-0089-probe1 receipt census drift")
        print(json.dumps({"live": live["census"], "recorded": rec_census}, indent=2)[:2000])
        return 1
    rec_health = recorded.get("healthcheck_version")
    if rec_health and rec_health != live["healthcheck_version"]:
        print("FAILED:IMP-0089-probe1 receipt health-check drift")
        return 1
    out = {
        "probe": "probe1-offline-rollback",
        "unit_id": "IMP-0089",
        "pass": True,
        "healthcheck_version": live["healthcheck_version"],
        "census_match": True,
        "egress_blocked": True,
        "forward_install_census_match": True,
        "fetch_calls": live.get("fetch_calls", 0),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"healthcheck={live['healthcheck_version']} census_match=True "
        f"egress_attempts=0 foreign_survived={live.get('foreign_survived')}"
    )
    print("SUCCESS:IMP-0089-probe1 offline rollback census and health-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
