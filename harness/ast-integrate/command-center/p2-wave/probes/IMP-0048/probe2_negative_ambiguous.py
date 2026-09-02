#!/usr/bin/env python3
"""Probe 2: current layout matches zero; hybrid is AMBIGUOUS, never resolved."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.layout_fingerprints import (  # noqa: E402
    COPIED_SKILLS,
    ROOT_DISABLED_MCP,
    STATUS_AMBIGUOUS,
    STATUS_NONE,
    STATUS_UNIQUE,
    classify,
    step_chain_for,
)
from plugin.layout_fixtures import materialize_all  # noqa: E402

FIX = HERE / "fixtures"


def main() -> int:
    trees = materialize_all(FIX)

    current = classify(trees["current"])
    print(
        f"current status={current['status']} match_ids={current['match_ids']} "
        f"selected={current['selected']}"
    )
    if current["status"] != STATUS_NONE or current["match_count"] != 0:
        print(json.dumps(current, indent=2)[:3000])
        print("FAILED:IMP-0048-probe2 current-layout matched a legacy fingerprint")
        return 1
    if step_chain_for(current):
        print("FAILED:IMP-0048-probe2 current produced a step chain")
        return 1

    hybrid = classify(trees["hybrid-ambiguous"])
    print(
        f"hybrid status={hybrid['status']} match_ids={hybrid['match_ids']} "
        f"selected={hybrid['selected']} step_chain={hybrid['step_chain']}"
    )
    want = {COPIED_SKILLS, ROOT_DISABLED_MCP}
    if hybrid["status"] != STATUS_AMBIGUOUS:
        print(json.dumps(hybrid, indent=2)[:3000])
        print("FAILED:IMP-0048-probe2 hybrid was not AMBIGUOUS")
        return 1
    if hybrid["selected"] is not None or hybrid["step_chain"]:
        print("FAILED:IMP-0048-probe2 hybrid silently resolved")
        return 1
    if set(hybrid["match_ids"]) != want or hybrid["match_count"] != 2:
        print("FAILED:IMP-0048-probe2 hybrid match set wrong")
        return 1
    if step_chain_for(hybrid):
        print("FAILED:IMP-0048-probe2 step_chain_for resolved ambiguity")
        return 1

    spoof = classify(trees["version-spoof-copied-skills"])
    claude = json.loads(
        (trees["version-spoof-copied-skills"] / "home" / ".claude.json").read_text(
            encoding="utf-8"
        )
    )
    print(
        f"version-spoof layoutVersion={claude.get('layoutVersion')} "
        f"status={spoof['status']} selected={spoof['selected']}"
    )
    if spoof["status"] != STATUS_UNIQUE or spoof["selected"] != COPIED_SKILLS:
        print("FAILED:IMP-0048-probe2 version string influenced detection")
        return 1
    if spoof.get("version_string_ignored") is not True:
        print("FAILED:IMP-0048-probe2 version_string_ignored flag missing")
        return 1

    out = {
        "probe": "probe2-negative-ambiguous",
        "unit_id": "IMP-0048",
        "current_matches_zero": True,
        "hybrid_status": hybrid["status"],
        "hybrid_selected": hybrid["selected"],
        "hybrid_match_ids": hybrid["match_ids"],
        "ambiguous_not_silently_resolved": True,
        "version_string_ignored": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0048-probe2 current-zero and ambiguous-path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
