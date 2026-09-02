#!/usr/bin/env python3
"""Probe 1: git merge-base --is-ancestor. Never HEAD==pinned-SHA equality."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = REPO / "command-center/audit/AUD-0008-commit-authorship-integrity.json"
SENTINEL = E.SENTINEL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0008-probe1 {msg}")
    return 1


def main() -> int:
    ctl = E.build_ancestor_fixture()
    live = E.census_live(E.load_unit_ids())
    if not ctl["pass"]:
        return fail(f"ancestor fixture failed {json.dumps(ctl, sort_keys=True)}")
    if ctl["owner_scratch_head_equals_baseline"]:
        return fail("owner scratch SHA equals baseline; fixture did not advance HEAD")
    if not ctl["invariant_green_on_owner_scratch"]:
        return fail("owner scratch must stay GREEN under is-ancestor")
    if not ctl["invariant_red_on_rewrite"]:
        return fail("history rewrite must go RED under is-ancestor")
    if not ctl["equality_strawman_would_fail_owner_scratch"]:
        return fail("equality strawman did not disagree with is-ancestor on owner scratch")

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    art_ctl = doc.get("probe1_control") or doc.get("probe1_control") or {}
    if art_ctl.get("pass") is not True:
        return fail("artifact probe1_control.pass is not true")
    if art_ctl.get("owner_scratch_head_equals_baseline") is True:
        return fail("artifact recorded equality as the invariant")
    instrument = str(doc.get("probe1_instrument") or doc.get("probe1_instrument") or "")
    if "merge-base" not in instrument or "is-ancestor" not in instrument:
        return fail("artifact did not record merge-base --is-ancestor as probe 1")
    if "rev-parse HEAD ==" in instrument or "equality" in instrument.lower() and "never" not in instrument.lower():
        # Allow mentioning equality only as the forbidden strawman.
        if "forbidden" not in instrument.lower() and "never" not in instrument.lower() and "strawman" not in instrument.lower():
            return fail("probe 1 instrument looks like SHA equality")

    payload = {
        "probe": "probe1-ancestor",
        "unit_id": "AUD-0008",
        "instrument": "git merge-base --is-ancestor",
        "not_instrument": "rev-parse HEAD == 53c37c6c",
        "control_pass": True,
        "owner_scratch_green": True,
        "rewrite_red": True,
        "equality_strawman_false_on_owner_scratch": True,
        "live_worktree_is_git": live["worktree_is_git"],
        "live_repos_in_scope": live["repos_in_scope"],
        "pinned_baseline": E.PINNED_BASELINE,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0008-probe1 is-ancestor green on owner scratch, "
        "red on rewrite, not SHA equality"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
