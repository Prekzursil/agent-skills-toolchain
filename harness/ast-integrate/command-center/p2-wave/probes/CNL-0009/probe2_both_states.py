#!/usr/bin/env python3
"""Probe 2: both-states control + negative control, independently re-run.

Coverage check must FIRE on the planted-empty-category fixture and stay SILENT
on the known-good four-bin run. The negative control records verbatim what the
check does on the state it is meant to reject.

Second signal (different mechanism from probe1's per-target gaming table):
independent unique-idea recount via set(slugs) versus Jaccard components on
the known-good run, compared with the artifact both_states.good_unique field.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import ops as O  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0009-target-block-which-of-the-8-targets-are-measurable-as-writ.md"
)


def main() -> int:
    live = O.both_states()
    print(f"check={live['check']}")
    print(f"fired_on_bad={live['fired_on_bad']} silent_on_good={live['silent_on_good']}")
    print(f"bad_reason={live['bad_reason']}")
    print(f"good_reason={live['good_reason']}")
    print(f"negative_control_on_reject_state={live['negative_control']['on_that_state']}")
    print(f"bad_state_output={live['negative_control']['bad_state_output']}")
    print(f"good_state_output={live['negative_control']['good_state_output']}")

    if not live["discriminates"]:
        print("FAILED:CNL-0009-probe2 both-states did not discriminate")
        return 1

    good_ideas = O.good_run()["ideas"]
    recount = O.unique_idea_count(good_ideas)
    print(
        f"recount slug_count={recount['slug_count']} "
        f"jaccard_cluster_count={recount['jaccard_cluster_count']} "
        f"agree={recount['signals_agree']}"
    )
    if not (
        recount["signals_agree"]
        and recount["slug_count"] == 4
        and recount["jaccard_cluster_count"] == 4
    ):
        print("FAILED:CNL-0009-probe2 unique-idea recount on good run")
        return 1

    if not OUT.is_file():
        print("FAILED:CNL-0009-probe2 artifact missing")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    rec = art.get("both_states") or {}
    if rec.get("fired_on_bad") is not True or rec.get("silent_on_good") is not True:
        print("FAILED:CNL-0009-probe2 artifact both_states drift")
        return 1
    if rec.get("bad_reason") != live["bad_reason"]:
        print(
            f"FAILED:CNL-0009-probe2 bad_reason drift artifact={rec.get('bad_reason')!r} live={live['bad_reason']!r}"
        )
        return 1
    neg = (art.get("negative_controls") or [{}])[0]
    if not neg.get("fired_on_bad_state") or not neg.get("silent_on_good_state"):
        print("FAILED:CNL-0009-probe2 negative control flags")
        return 1
    if "empty_categories" not in str(neg.get("on_the_state_it_rejects") or ""):
        print("FAILED:CNL-0009-probe2 negative control missing verbatim reject state")
        return 1
    print("SUCCESS:CNL-0009-probe2 both-states and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
