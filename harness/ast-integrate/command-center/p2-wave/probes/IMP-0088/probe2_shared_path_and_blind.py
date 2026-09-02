#!/usr/bin/env python3
"""IMP-0088 probe 2: shared-path refusal + ownership-blind negative control.

The sibling isolation test must FAIL when an ownership-blind remover is
substituted, proving the test can go red.
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
from tools.marketplace.ownership_blind import ownership_blind_remove  # noqa: E402
from tools.marketplace.remove_isolation import (  # noqa: E402
    plant_shared_path,
    plant_two_packages,
)
from tools.marketplace.remove import (  # noqa: E402
    SharedPathRequiresDecision,
    remove_package,
    sibling_isolation_holds,
)

OUT = HERE / "probe2-shared-and-blind.raw.json"


def main() -> int:
    results: dict = {}
    with tempfile.TemporaryDirectory(prefix="imp0088-p2-shared-") as tmp:
        root = Path(tmp)
        live = root / "live"
        ledger = root / "ledger.json"
        planted = plant_shared_path(live, ledger)
        before = census(live)
        refused = False
        claimants = None
        try:
            remove_package(
                live_root=live,
                ledger_path=ledger,
                package_id="pkg-a",
                owner_approval=True,
            )
        except SharedPathRequiresDecision as exc:
            refused = True
            claimants = exc.claimants
        if not refused:
            print("FAILED:IMP-0088-probe2 shared path did not require a decision")
            return 1
        if census(live) != before:
            print("FAILED:IMP-0088-probe2 shared-path refusal mutated the tree")
            return 1
        keep = remove_package(
            live_root=live,
            ledger_path=ledger,
            package_id="pkg-a",
            owner_approval=True,
            shared_path_decisions={planted["shared_path"]: "keep"},
        )
        after = census(live)
        if planted["a_exclusive"] in after:
            print("FAILED:IMP-0088-probe2 exclusive A file survived keep-decision remove")
            return 1
        if after.get(planted["b_exclusive"]) != planted["b_exclusive_sha256"]:
            print("FAILED:IMP-0088-probe2 sibling exclusive file mutated")
            return 1
        if after.get(planted["shared_path"]) != planted["shared_sha256"]:
            print("FAILED:IMP-0088-probe2 shared path mutated under keep")
            return 1
        results["shared"] = {
            "refused_without_decision": True,
            "claimants": claimants,
            "keep_ok": keep.ok,
            "shared_bytes_unchanged": True,
        }

    with tempfile.TemporaryDirectory(prefix="imp0088-p2-blind-") as tmp:
        root = Path(tmp)
        live = root / "live"
        ledger = root / "ledger.json"
        planted = plant_two_packages(live, ledger)
        b_before = subset(census(live), planted["b_paths"])
        ownership_blind_remove(live, "pkg-a")
        signals = sibling_isolation_holds(
            live_root=live,
            ledger_path=ledger,
            sibling_package_id="pkg-b",
            sibling_census_before=b_before,
        )
        if signals.get("census_byte_identical") or signals.get("both_signals"):
            print("FAILED:IMP-0088-probe2 ownership-blind control did not fail isolation")
            print(json.dumps(signals, indent=2)[:2000])
            return 1
        results["negative_control"] = {
            "ownership_blind_fails_sibling_isolation": True,
            "signals": signals,
        }

    OUT.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "shared_refused="
        + str(results["shared"]["refused_without_decision"])
        + " keep_ok="
        + str(results["shared"]["keep_ok"])
        + " blind_fails_isolation=True"
    )
    print("SUCCESS:IMP-0088-probe2 shared-path decision and ownership-blind control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
