#!/usr/bin/env python3
"""Probe 2: identical versions produce no precedence signal (negative control).

Both-states: the same detector MUST fire when marketplace is mutated to 9.9.9.
This reviewer does not read RES-0008.json claims.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture import ensure_snapshots  # noqa: E402
from common import (  # noqa: E402
    MARKET_ONLY_BUMP,
    PINNED,
    UID,
    load_fixture,
    resolve_plugin_version,
)


def main() -> int:
    ensure_snapshots(force=False)
    fx = load_fixture("identical")
    v = fx["verdict"]
    mutant_entry = copy.deepcopy(fx["entry"])
    mutant_entry["version"] = MARKET_ONLY_BUMP
    mutant = resolve_plugin_version(fx["plugin"], mutant_entry)

    ok = (
        v["plugin_json_version"] == PINNED
        and v["marketplace_version"] == PINNED
        and v["identical"] is True
        and v["precedence_signal"] is False
        and v["honoured_version"] == PINNED
        and v["honoured_source"] == "plugin.json"
        and mutant["precedence_signal"] is True
        and mutant["honoured_version"] == PINNED
        and mutant["marketplace_version"] == MARKET_ONLY_BUMP
        and mutant["identical"] is False
    )
    out = {
        "unit_id": UID,
        "probe": "probe2-identical-negative",
        "pass": ok,
        "identical_precedence_signal": v["precedence_signal"],
        "identical_honoured_version": v["honoured_version"],
        "mutant_precedence_signal": mutant["precedence_signal"],
        "mutant_marketplace_version": mutant["marketplace_version"],
        "mutant_honoured_version": mutant["honoured_version"],
        "detector_silent_in_both_states": (
            v["precedence_signal"] == mutant["precedence_signal"]
        ),
        "observed_installed_version": v["honoured_version"],
        "reviewer": True,
    }
    print(json.dumps(out, sort_keys=True))
    if not ok:
        print("FAILED:RES-0008-probe2 identical versions still produced a signal")
        return 1
    print(
        "SUCCESS:RES-0008-probe2 identical 0.2.0: no precedence signal; "
        "marketplace-only bump mutant fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
