"""Both-states leak controls and red/green pattern controls. No shared-tree mutation."""
from __future__ import annotations

import json

import leak_detector as L
from brief_builder import build_brief
from classify import classify
from execute import run_python
from paths import (
    ALREADY,
    AUTHOR_MARKER,
    AUTHOR_TEST,
    CONCLUSION_MARKER,
    DIFF_MARKER,
    OVERFITTED,
    POST_FIX,
    PRE_FIX,
    SYNTH_TEST,
)


def leak_controls() -> dict:
    brief = build_brief()
    clean = json.dumps(brief, indent=2, sort_keys=True)
    return {
        "silent_on_clean_brief": not L.fired(clean),
        "fired_on_injected_author_test": L.fired(clean + "\n" + AUTHOR_MARKER),
        "fired_on_injected_conclusion": L.fired(clean + "\n" + CONCLUSION_MARKER + " planted"),
        "fired_on_injected_diff": L.fired(clean + "\n" + DIFF_MARKER),
        "clean_hits": L.scan(clean),
    }


def pattern_controls(synth_path=None, author_path=None) -> dict:
    synth = synth_path or SYNTH_TEST
    author = author_path or AUTHOR_TEST
    already_pre = run_python(synth, ALREADY)
    post = run_python(synth, POST_FIX)
    already_cls = classify(already_pre["verdict"], post["verdict"])
    over_ind = run_python(synth, OVERFITTED)
    over_auth = run_python(author, OVERFITTED)
    overfitted_caught = over_ind["verdict"] == "RED" and over_auth["verdict"] == "GREEN"
    return {
        "already_satisfied": {
            "pre_fix_stand_in": already_pre,
            "post_fix": {"verdict": post["verdict"], "exit_code": post["exit_code"]},
            "classification": already_cls["classification"],
            "caught": already_cls["classification"] == "requirement-already-satisfied",
        },
        "overfitted_patch": {
            "independent_on_overfitted": over_ind["verdict"],
            "author_on_overfitted": over_auth["verdict"],
            "caught": overfitted_caught,
            "classification": "overfitted-patch" if overfitted_caught else "missed",
        },
        "pre_fix_snapshot": str(PRE_FIX),
    }
