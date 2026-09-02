#!/usr/bin/env python3
"""Probe 1: leak detector both-states + synthesizer must not open author test/diff."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import brief_builder as B  # noqa: E402
import controls as C  # noqa: E402
import leak_detector as L  # noqa: E402
import synthesizer as S  # noqa: E402
from paths import SYNTH_TEST, UNIT  # noqa: E402


def main() -> int:
    leaks = C.leak_controls()
    if not leaks["silent_on_clean_brief"] or leaks["clean_hits"]:
        print("FAILED:CNF-0038-probe1 clean brief not silent", leaks)
        return 1
    if not leaks["fired_on_injected_author_test"]:
        print("FAILED:CNF-0038-probe1 detector silent on injected author test")
        return 1
    if not leaks["fired_on_injected_conclusion"]:
        print("FAILED:CNF-0038-probe1 detector silent on injected conclusion")
        return 1
    if not leaks["fired_on_injected_diff"]:
        print("FAILED:CNF-0038-probe1 detector silent on injected diff")
        return 1
    B.build_brief()
    synth = S.synthesise()
    forbidden = [row for row in synth["access_log"] if not row.get("allowed", True)]
    if forbidden:
        print("FAILED:CNF-0038-probe1 forbidden paths opened", forbidden)
        return 1
    source = SYNTH_TEST.read_text(encoding="utf-8")
    if L.scan(source):
        print("FAILED:CNF-0038-probe1 synthesised test contains leak markers")
        return 1
    doc = {
        "silent_on_clean": True,
        "fired_on_author_test": True,
        "fired_on_conclusion": True,
        "fired_on_diff": True,
        "forbidden_opened": 0,
        "pass": True,
        "probe": "probe1-leak-control",
        "unit_id": UNIT,
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        "silent_on_clean=True fired_on_injected=True forbidden_opened=0 "
        "both_states=True"
    )
    print("SUCCESS:CNF-0038-probe1 leak detector both-states and access guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
