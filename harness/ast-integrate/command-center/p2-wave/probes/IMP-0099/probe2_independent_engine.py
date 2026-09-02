#!/usr/bin/env python3
"""Probe 2: IMP-0070 comparator engine vs advisory intervals, plus controls.

Mechanically different from probe 1: does not walk advisory intervals.
Converts the same OSV events to an npm-like range and evaluates with
``version.satisfies`` (caret/tilde/relational comparator walker).
Also: sibling-package negative control, and open-ended disclosure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.advisory import (  # noqa: E402
    OpenEndedUndisclosedError,
    evaluate_installed,
    from_record,
    is_affected,
)
from marketplace.version import events_to_range, satisfies  # noqa: E402

FIX = REPO / "tools/marketplace/fixtures/imp0099_matrix.json"
ART = REPO / "command-center/receipts/IMP-0099.json"


def main() -> int:
    doc = json.loads(FIX.read_text(encoding="utf-8"))
    adv = from_record(doc["advisory"])
    spec = events_to_range(list(adv.affected_version_ranges))
    if spec != doc["imp0070_range"]:
        print(f"FAILED:IMP-0099-probe2 range {spec!r} != {doc['imp0070_range']!r}")
        return 1
    disagree = []
    for row in doc["cases"]:
        interval = is_affected(adv, row["version"])
        comparator = satisfies(row["version"], spec, include_prerelease=True)
        ok = interval == comparator == row["expected_affected"]
        print(
            f"case {row['id']:02d} version={row['version']:<16} "
            f"interval={interval!s:<5} comparator={comparator!s:<5} "
            f"expected={row['expected_affected']!s:<5} ok={ok}"
        )
        if not ok:
            disagree.append(row["version"])
    if disagree:
        print(f"FAILED:IMP-0099-probe2 engine disagreement {disagree}")
        return 1

    ctrl = doc["negative_control"]
    pkg = doc["package"]
    sib = doc["sibling_package"]
    bad = evaluate_installed(pkg, ctrl["affected_package_version"], [adv])
    good_ver = evaluate_installed(pkg, ctrl["unaffected_sibling_version"], [adv])
    good_pkg = evaluate_installed(sib, ctrl["unaffected_sibling_package_version"], [adv])
    print(
        f"negative_control affected={pkg}@{ctrl['affected_package_version']} "
        f"flagged={bad.affected} installable={bad.installable}"
    )
    print(
        f"negative_control sibling_version={pkg}@{ctrl['unaffected_sibling_version']} "
        f"flagged={good_ver.affected} installable={good_ver.installable}"
    )
    print(
        f"negative_control sibling_package={sib}@"
        f"{ctrl['unaffected_sibling_package_version']} "
        f"flagged={good_pkg.affected} installable={good_pkg.installable}"
    )
    if not (
        bad.affected
        and not bad.installable
        and not good_ver.affected
        and good_ver.installable
        and not good_pkg.affected
        and good_pkg.installable
    ):
        print("FAILED:IMP-0099-probe2 sibling negative control")
        return 1

    open_adv = from_record(doc["open_ended_advisory"])
    future = evaluate_installed(pkg, "99.0.0", [open_adv])
    past = evaluate_installed(pkg, "8.9.9", [open_adv])
    print(
        f"open_ended future_affected={future.affected} "
        f"disclosed={bool(future.open_ended_hits)} notes={len(future.notes)}"
    )
    print(f"open_ended past_affected={past.affected}")
    if not future.affected or not future.open_ended_hits or past.affected:
        print("FAILED:IMP-0099-probe2 open-ended disclosure")
        return 1
    silent = dict(doc["open_ended_advisory"])
    silent["unbounded_future_disclosed"] = False
    refused = False
    try:
        from_record(silent)
    except OpenEndedUndisclosedError:
        refused = True
    print(f"open_ended silent_construct_refused={refused}")
    if not refused:
        print("FAILED:IMP-0099-probe2 silent open-ended range was accepted")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0099" not in text:
            print("FAILED:IMP-0099-probe2 receipt sentinel absent")
            return 1

    summary = {
        "probe": "probe2-independent-engine",
        "unit_id": "IMP-0099",
        "imp0070_range": spec,
        "cases_agreed": 20,
        "negative_control_sibling_installable": True,
        "open_ended_disclosed": True,
        "silent_open_ended_refused": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0099-probe2 independent range engine and controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
