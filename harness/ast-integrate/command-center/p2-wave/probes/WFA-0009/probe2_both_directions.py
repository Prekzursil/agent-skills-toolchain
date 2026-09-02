#!/usr/bin/env python3
"""Probe 2: both set-difference directions, after detector control.

Reporting only one direction is a unit failure. A mutant that drops a
direction object must be rejected. Inverse sweep must catch the
extension-only file AND the frontmatter-only file.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402
import reconcile as R  # noqa: E402

OUT = HERE / "probe2-both-directions.raw.json"


def main() -> int:
    E.build_estate()
    present = R.classify_path(E.present_path())
    absent = R.classify_path(E.absent_path())
    empty = R.classify_path(E.empty_path())
    if (
        present["verdict"] != "HIT"
        or absent["verdict"] != "MISS"
        or empty["verdict"] != "PRESENT-EMPTY"
    ):
        print("FAILED:WFA-0009-probe2 detector control not green; sweep not admissible")
        return 1

    report = R.fixture_reconcile()
    ok, why = R.directions_admissible(report)
    if not ok:
        print(f"FAILED:WFA-0009-probe2 directions not admissible {why}")
        return 1
    a = report["registry_minus_disk"]["count"]
    b = report["disk_minus_registry"]["count"]
    if a < 1 or b < 1:
        print(
            f"FAILED:WFA-0009-probe2 not two-directional "
            f"registry_minus_disk={a} disk_minus_registry={b}"
        )
        return 1
    if report["verdict_counts"]["PRESENT-EMPTY"] < 1:
        print("FAILED:WFA-0009-probe2 PRESENT-EMPTY not reported")
        return 1
    if report["verdict_counts"]["HIT"] < 1:
        print("FAILED:WFA-0009-probe2 no HIT")
        return 1
    if report["path_stale_count"] < 1:
        print("FAILED:WFA-0009-probe2 no path-stale MISS rows")
        return 1

    missed = set(report["disk_minus_registry"]["ids"])
    for needed in (E.MISS_LIVE_ID, E.EXT_ONLY_ID, E.FM_ONLY_ID, E.SKILL_ID, E.CMD_ID):
        if needed not in missed:
            print(f"FAILED:WFA-0009-probe2 inverse sweep missed {needed}")
            return 1
    reasons = report["discovery_reasons"]
    if "github-workflow-extension" not in reasons:
        print("FAILED:WFA-0009-probe2 extension sweep silent")
        return 1
    if "yaml-frontmatter" not in reasons:
        print("FAILED:WFA-0009-probe2 frontmatter sweep silent")
        return 1

    decoy = [r for r in report["disk_rows"] if r["path"] == E.DECOY_REL]
    if not decoy or decoy[0]["bearing"]:
        print("FAILED:WFA-0009-probe2 decoy treated as workflow-bearing")
        return 1

    mutant = copy.deepcopy(report)
    del mutant["disk_minus_registry"]
    mok, mwhy = R.directions_admissible(mutant)
    if mok:
        print("FAILED:WFA-0009-probe2 one-direction mutant was accepted")
        return 1

    mutant2 = copy.deepcopy(report)
    del mutant2["registry_minus_disk"]
    m2ok, m2why = R.directions_admissible(mutant2)
    if m2ok:
        print("FAILED:WFA-0009-probe2 forward-only mutant was accepted")
        return 1

    empty_rows = [
        r for r in report["existence"] if r["id"] == E.CTRL_EMPTY_ID
    ]
    if not empty_rows or empty_rows[0]["verdict"] != "PRESENT-EMPTY":
        print("FAILED:WFA-0009-probe2 empty registry row not PRESENT-EMPTY")
        return 1
    if empty_rows[0]["verdict"] == "HIT":
        print("FAILED:WFA-0009-probe2 empty registry row counted as HIT")
        return 1

    slim = {
        "pass": True,
        "registry_minus_disk": a,
        "disk_minus_registry": b,
        "path_stale_count": report["path_stale_count"],
        "present_empty": report["verdict_counts"]["PRESENT-EMPTY"],
        "hits": report["verdict_counts"]["HIT"],
        "missed_ids": report["disk_minus_registry"]["ids"],
        "stale_ids": report["registry_minus_disk"]["ids"],
        "discovery_reasons": reasons,
        "one_direction_mutant_rejected": True,
        "one_direction_mutant_why": mwhy,
        "forward_only_mutant_why": m2why,
        "n_candidates": report["n_candidates"],
        "n_workflow_bearing": report["n_workflow_bearing"],
    }
    OUT.write_text(json.dumps(slim, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"registry_minus_disk={a} disk_minus_registry={b} "
        f"path_stale={report['path_stale_count']} "
        f"present_empty={report['verdict_counts']['PRESENT-EMPTY']} "
        f"hits={report['verdict_counts']['HIT']} "
        f"ext=True frontmatter=True one_direction_mutant_rejected=True"
    )
    print("SUCCESS:WFA-0009-probe2 both-direction inverse sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
