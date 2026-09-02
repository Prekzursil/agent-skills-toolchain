#!/usr/bin/env python3
"""Probe 2: touching a held-out case during development is detected.

Both-states: a development read of a visible case is silent; a development read
of a held-out case records the access and raises. Evaluation may read held-out.
A convention label of 'visible' on a hash-held-out case still fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.rows import (  # noqa: E402
    DEVELOPMENT,
    EVALUATION,
    HELD_OUT,
    VISIBLE,
    AccessLog,
    HeldOutTouchError,
    build_corpus,
    development_run,
    get_case,
    partition_of,
    visible_cases,
)


def main() -> int:
    corpus = build_corpus()
    held = [c for c in corpus if partition_of(c) == HELD_OUT]
    vis = [c for c in corpus if partition_of(c) == VISIBLE]
    if not held or not vis:
        print("FAILED:IMP-0198-probe2 corpus missing a slice")
        return 1

    vis_dev = visible_cases(corpus, mode=DEVELOPMENT)
    if any(partition_of(c) == HELD_OUT for c in vis_dev):
        print("FAILED:IMP-0198-probe2 visible_cases leaked held-out into development")
        return 1
    if len(vis_dev) != len(vis):
        print("FAILED:IMP-0198-probe2 visible_cases count mismatch")
        return 1

    silent_log = AccessLog()
    got = get_case(corpus, vis[0]["id"], mode=DEVELOPMENT, log=silent_log)
    if got["id"] != vis[0]["id"]:
        print("FAILED:IMP-0198-probe2 visible fetch returned the wrong case")
        return 1
    try:
        silent_log.assert_no_held_out_development()
    except HeldOutTouchError:
        print("FAILED:IMP-0198-probe2 detector fired on a visible development read")
        return 1
    if silent_log.held_out_development_touches():
        print("FAILED:IMP-0198-probe2 access log recorded a held-out visible read")
        return 1

    fire_log = AccessLog()
    fired = False
    try:
        get_case(corpus, held[0]["id"], mode=DEVELOPMENT, log=fire_log)
    except HeldOutTouchError as exc:
        fired = True
        if exc.case_id != held[0]["id"]:
            print(f"FAILED:IMP-0198-probe2 wrong case_id on detector {exc.case_id}")
            return 1
    if not fired:
        print("FAILED:IMP-0198-probe2 detector silent on held-out development read")
        return 1
    if not fire_log.held_out_development_touches():
        print("FAILED:IMP-0198-probe2 access log missing the held-out development read")
        return 1

    eval_log = AccessLog()
    eval_got = get_case(corpus, held[0]["id"], mode=EVALUATION, log=eval_log)
    if eval_got["id"] != held[0]["id"]:
        print("FAILED:IMP-0198-probe2 evaluation could not read held-out")
        return 1
    if eval_log.held_out_development_touches():
        print("FAILED:IMP-0198-probe2 evaluation read mis-tagged as development")
        return 1

    labelled = dict(held[1] if len(held) > 1 else held[0])
    labelled["partition_cached"] = VISIBLE
    conv_log = AccessLog()
    conv_fired = False
    try:
        get_case([labelled, *corpus], labelled["id"], mode=DEVELOPMENT, log=conv_log)
    except HeldOutTouchError:
        conv_fired = True
    if not conv_fired:
        print("FAILED:IMP-0198-probe2 convention label hid a held-out development read")
        return 1

    run_log = AccessLog()
    try:
        development_run(corpus, [vis[0]["id"], vis[1]["id"]], run_log)
    except HeldOutTouchError:
        print("FAILED:IMP-0198-probe2 development_run fired on visible ids")
        return 1
    mixed_log = AccessLog()
    mixed_fired = False
    try:
        development_run(corpus, [vis[0]["id"], held[0]["id"]], mixed_log)
    except HeldOutTouchError:
        mixed_fired = True
    if not mixed_fired:
        print("FAILED:IMP-0198-probe2 development_run did not fire on mixed ids")
        return 1

    print(
        json.dumps(
            {
                "fired_on_held_out_development": True,
                "silent_on_visible_development": True,
                "evaluation_may_read_held_out": True,
                "convention_label_cannot_hide": True,
                "access_log_recorded_violation": True,
                "held_out_ids_sampled": [held[0]["id"]],
                "visible_ids_sampled": [vis[0]["id"]],
            },
            sort_keys=True,
        )
    )
    print(
        "fired_on_bad=True silent_on_good=True eval_held_out_ok=True "
        "convention_cannot_hide=True"
    )
    print("SUCCESS:IMP-0198-probe2 touching a held-out case during development is detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
