#!/usr/bin/env python3
"""IMP-0088 probe 1: two-signal sibling isolation after removing pkg-a.

Signal 1: full census of pkg-b paths is byte-identical.
Signal 2: provenance ledger records zero deletions attributed to pkg-b.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.census import census, subset  # noqa: E402
from tools.marketplace.remove_isolation import plant_two_packages  # noqa: E402
from tools.marketplace.remove import (  # noqa: E402
    OwnerGateRequired,
    remove_package,
    sibling_isolation_holds,
)

OUT = HERE / "probe1-isolation.raw.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0088-p1-") as tmp:
        root = Path(tmp)
        live = root / "live"
        ledger = root / "ledger.json"
        planted = plant_two_packages(live, ledger)
        before = census(live)
        b_before = subset(before, planted["b_paths"])

        try:
            remove_package(
                live_root=live,
                ledger_path=ledger,
                package_id="pkg-a",
                owner_approval=False,
            )
            print("FAILED:IMP-0088-probe1 owner gate did not refuse")
            return 1
        except OwnerGateRequired:
            pass
        if census(live) != before:
            print("FAILED:IMP-0088-probe1 owner-gate refusal mutated the tree")
            return 1

        report = remove_package(
            live_root=live,
            ledger_path=ledger,
            package_id="pkg-a",
            owner_approval=True,
        )
        after = census(live)
        for rel in planted["a_paths"]:
            if rel in after:
                print(f"FAILED:IMP-0088-probe1 pkg-a path survived: {rel}")
                return 1
        if after.get(planted["user_path"]) != before.get(planted["user_path"]):
            print("FAILED:IMP-0088-probe1 user-authored file mutated")
            return 1

        signals = sibling_isolation_holds(
            live_root=live,
            ledger_path=ledger,
            sibling_package_id="pkg-b",
            sibling_census_before=b_before,
        )
        payload = {
            "deleted": report.deleted_paths,
            "signals": signals,
            "a_gone": all(p not in after for p in planted["a_paths"]),
            "user_survived": after.get(planted["user_path"]) == before.get(planted["user_path"]),
        }
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not signals.get("both_signals"):
            print("FAILED:IMP-0088-probe1 both isolation signals did not hold")
            print(json.dumps(signals, indent=2)[:2000])
            return 1
        print(
            "census_byte_identical="
            + str(signals["census_byte_identical"])
            + " ledger_zero_deletions_for_B="
            + str(signals["ledger_zero_deletions_attributed_to_sibling"])
            + " user_survived="
            + str(payload["user_survived"])
            + " deleted="
            + str(report.deleted_paths)
        )
        print("SUCCESS:IMP-0088-probe1 sibling isolation two-signal")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
