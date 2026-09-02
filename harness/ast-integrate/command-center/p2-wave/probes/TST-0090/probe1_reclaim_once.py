#!/usr/bin/env python3
"""Probe 1: expired lease permits exactly one reclaim; unexpired blocks; concurrent losers lose."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fencing_lease import (  # noqa: E402
    DENIED,
    GRANTED,
    REASON_UNEXPIRED,
    scenario_concurrent_reclaimers,
    scenario_exactly_one_reclaim,
    scenario_unexpired_blocks,
)


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0090-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0090-p1-") as tmp:
        root = Path(tmp)
        once = scenario_exactly_one_reclaim(root / "once")
        both = scenario_unexpired_blocks(root / "both")
        race = scenario_concurrent_reclaimers(
            root / "race", n_workers=8, n_trials=16
        )

    payload = {
        "pass": False,
        "probe": "probe1-reclaim-once",
        "unit_id": "TST-0090",
        "exactly_one": once,
        "both_states": both,
        "concurrent": {
            "n_trials": race["n_trials"],
            "n_workers": race["n_workers"],
            "failed_trials": race["failed_trials"],
            "all_exactly_one": race["all_exactly_one"],
            "distinct_winners": race.get("distinct_winners"),
            "winner_counts": race.get("winner_counts"),
            "sample": race["trials"][:3],
        },
    }
    ok = (
        once["exactly_one"] is True
        and once["grant_count"] == 1
        and once["second_reclaim"]["status"] == DENIED
        and once["second_reclaim"]["reason"] == REASON_UNEXPIRED
        and both["both_states"] is True
        and both["unexpired"]["status"] == DENIED
        and both["expired"]["status"] == GRANTED
        and race["all_exactly_one"] is True
        and race["failed_trials"] == 0
    )
    payload["pass"] = bool(ok)
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return _fail(
            "exactly_one="
            f"{once.get('exactly_one')} both_states={both.get('both_states')} "
            f"race_fail={race.get('failed_trials')}"
        )
    print(
        "SUCCESS:TST-0090-probe1 expired lease permits exactly one reclaim; "
        "unexpired blocks; concurrent reclaimers do not both win"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
