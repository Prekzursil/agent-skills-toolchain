#!/usr/bin/env python3
"""Probe 1: both-states inversion for load_mode.

A fixture rule with no frontmatter must resolve ALWAYS-ON. The same body with
paths: ["**/*"] must resolve LAZY. A resolver that returns the same answer
for both states fails. The inspect instrument must independently confirm.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.RECEIPT


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0387-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != S.UNIT:
        print("FAILED:IMP-0387-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() != "SUCCESS":
        print("FAILED:IMP-0387-probe1 state", doc.get("state"))
        return 1
    if S.SENTINEL not in text:
        print("FAILED:IMP-0387-probe1 sentinel absent")
        return 1

    live = S.both_states()
    if live["same_answer_for_both_states"]:
        print("FAILED:IMP-0387-probe1 resolver returned the same load_mode for both states")
        print(json.dumps(live, indent=2))
        return 1
    if not live["inversion_holds"]:
        print("FAILED:IMP-0387-probe1 inversion does not hold")
        print(json.dumps(live, indent=2))
        return 1
    if not live["instrument_agrees"]:
        print("FAILED:IMP-0387-probe1 instrument did not confirm inversion")
        print(json.dumps(live, indent=2))
        return 1
    if not live["other_keys_do_not_demote"]:
        print("FAILED:IMP-0387-probe1 non-paths frontmatter demoted the file")
        return 1

    recorded = doc.get("both_states") or {}
    if recorded.get("no_frontmatter", {}).get("predicted") != S.ALWAYS_ON:
        print("FAILED:IMP-0387-probe1 receipt both_states no_frontmatter")
        return 1
    if recorded.get("with_paths_globstar", {}).get("predicted") != S.LAZY:
        print("FAILED:IMP-0387-probe1 receipt both_states globstar")
        return 1
    if recorded.get("inversion_holds") is not True:
        print("FAILED:IMP-0387-probe1 receipt inversion_holds")
        return 1

    rec = json.dumps(doc)
    if '"load_mode"' not in rec:
        print("FAILED:IMP-0387-probe1 queryable load_mode field absent from receipt")
        return 1

    print(
        f"no_frontmatter={live['no_frontmatter']['predicted']} "
        f"with_paths={live['with_paths_globstar']['predicted']} "
        f"other_keys={live['frontmatter_without_paths']['predicted']} "
        f"inversion={live['inversion_holds']} "
        f"instrument={live['instrument_agrees']}"
    )
    print("SUCCESS:IMP-0387-probe1 both-states inversion ALWAYS-ON vs LAZY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
