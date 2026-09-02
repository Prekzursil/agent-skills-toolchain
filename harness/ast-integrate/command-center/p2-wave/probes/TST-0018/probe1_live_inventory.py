#!/usr/bin/env python3
"""Probe 1: live inventory scan. Enumerator must find a known-present detector.
Identical good/broken output is named INERT; never summarised as all clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scanner import DISK_KNOWN_PRESENT, scan  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0018-probe1 {msg}")
    return 1


def main() -> int:
    result = scan()
    print(json.dumps(
        {
            "enumerator": {
                k: result["enumerator"][k]
                for k in (
                    "known_present",
                    "found_known_present",
                    "count",
                    "disk_known_present",
                    "found_disk_known_present",
                    "found_census_constant",
                    "enumerator_live",
                )
                if k in result["enumerator"]
            },
            "counts": result["counts"],
            "inert": result["inert"],
            "measures_nothing": result["measures_nothing"],
            "not_checked_count": len(result["not_checked"]),
            "all_clean_claim": result["all_clean_claim"],
            "summary": result["summary"],
            "pass": False,
        },
        indent=2,
        sort_keys=True,
    ))

    enum = result["enumerator"]
    if not enum.get("enumerator_live"):
        return fail(
            "enumerator missed known-present detector "
            f"{DISK_KNOWN_PRESENT} (census constant={enum.get('known_present')})"
        )
    if result["counts"]["checked"] < 1:
        return fail("zero shipped detectors exercised")
    if result["all_clean_claim"] and result["measures_nothing"]:
        return fail("all-clean summary while inert detectors named")
    if result["inert"] and "all clean" in result["summary"].lower():
        return fail("summary says all clean while inert list is non-empty")

    print(
        f"inventory={result['counts']['inventory']} "
        f"checked={result['counts']['checked']} "
        f"inert={result['counts']['inert']} "
        f"not_checked={result['counts']['not_checked']}"
    )
    print(result["summary"])
    print("SUCCESS:TST-0018-probe1 live inventory both-states scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
