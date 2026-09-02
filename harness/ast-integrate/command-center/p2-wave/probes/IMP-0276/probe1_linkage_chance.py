#!/usr/bin/env python3
"""Named probe 1: linkage attack on fully anonymized rounds must sit at chance.

Also: field census of the published artifact must find zero real participant ids,
and per-round HMAC labels must not be stable across rounds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import CHANCE, run_full_anonymity_battery  # noqa: E402


def main() -> int:
    result = run_full_anonymity_battery()
    print(json.dumps(result, sort_keys=True))
    if result["census_hit_count"] != 0:
        print(
            f"FAILED:IMP-0276-probe1 census hits={result['census_hit_count']}"
        )
        return 1
    if result["label_leak_sessions"] != 0:
        print("FAILED:IMP-0276-probe1 HMAC labels reused across rounds")
        return 1
    if result["channel_present_any"]["timing"]:
        print("FAILED:IMP-0276-probe1 timing survived publish")
        return 1
    if result["channel_present_any"]["tokens"]:
        print("FAILED:IMP-0276-probe1 token counts survived publish")
        return 1
    if result["channel_present_any"]["style"]:
        print("FAILED:IMP-0276-probe1 style/text survived publish")
        return 1
    mean = result["mean_order_accuracy"]
    if mean > result["pass_threshold"]:
        print(
            f"FAILED:IMP-0276-probe1 mean_accuracy={mean:.4f} "
            f"chance={CHANCE:.4f} bound={result['pass_threshold']:.4f}"
        )
        return 1
    print(
        f"mean_order_accuracy={mean:.4f} chance={CHANCE:.4f} "
        f"census=0 label_leaks=0"
    )
    print("SUCCESS:IMP-0276-probe1 linkage at chance; census empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
