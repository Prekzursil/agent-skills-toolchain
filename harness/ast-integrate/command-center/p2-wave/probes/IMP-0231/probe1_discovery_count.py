#!/usr/bin/env python3
"""Probe 1: discovered blueprint count equals registry count (computed, no hand list)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from blueprint_conformance.harness import (  # noqa: E402
    CHECK_IDS,
    DEFAULT_LIBRARY,
    discover_registry,
    run_suite,
)


def main() -> int:
    root = DEFAULT_LIBRARY
    entries = discover_registry(root)
    registry_ids = [e["id"] for e in entries]
    report = run_suite(root)
    discovered = list(report["registry_ids"])
    equal = (
        report["discovery_equals_registry"] is True
        and report["registry_count"] == report["discovered_count"]
        and report["registry_count"] == len(registry_ids)
        and discovered == registry_ids
        and not report["hand_list"]
    )
    payload = {
        "registry_count": report["registry_count"],
        "discovered_count": report["discovered_count"],
        "exercised_count": report["exercised_count"],
        "equal": equal,
        "registry_ids": registry_ids,
        "discovered_ids": discovered,
        "untested_ids": report["untested_ids"],
        "check_ids": report["check_ids"],
        "suite_ok": report["ok"],
        "hand_list": report["hand_list"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, indent=2))
    if not equal:
        print("FAILED:IMP-0231-probe1 discovery != registry")
        return 1
    if report["untested_ids"]:
        print(f"FAILED:IMP-0231-probe1 untested={report['untested_ids']}")
        return 1
    if report["ok"] is not True:
        print("FAILED:IMP-0231-probe1 suite not green")
        return 1
    if list(report["check_ids"]) != list(CHECK_IDS):
        print("FAILED:IMP-0231-probe1 check set mismatch")
        return 1
    if report["registry_count"] < 1:
        print("FAILED:IMP-0231-probe1 empty registry")
        return 1
    print(
        f"registry_count={report['registry_count']} "
        f"discovered_count={report['discovered_count']} equal=True"
    )
    print("SUCCESS:IMP-0231-probe1 discovered count == registry count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
