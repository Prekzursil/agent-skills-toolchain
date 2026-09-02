#!/usr/bin/env python3
"""Probe 2: independent recount, UNSCOREABLE marking, negative control.

Reviewer re-tabulates from fixtures with recount.py (set membership + expanded
Brier). A disagreement with the author scorer or with the published artifact
blocks the unit. The negative control is a mutant that counts UNSCOREABLE as
calibrated; the check must fire on that mutant and stay silent on the deferred
scoreable fixture.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mutant as M  # noqa: E402
import recount as R  # noqa: E402
import score as S  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0074-confidence-trajectory-and-the-post-run-calibration-report.md"


def close(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=1e-12)


def counts_match(a: dict, b: dict) -> bool:
    keys = (
        "n_statements",
        "n_resolved",
        "n_pending",
        "n_unscoreable",
        "n_rejected_resolution",
    )
    return all(a.get(k) == b.get(k) for k in keys) and close(
        a.get("mean_brier"), b.get("mean_brier")
    )


def score_fix(name: str, with_res: bool) -> tuple[dict, dict]:
    base = HERE / "fixtures" / name
    res = (base / "resolution.json") if with_res else None
    author = S.score_paths(base / "trajectory.json", res)
    indep = R.recount_paths(base / "trajectory.json", res)
    return author, indep


def main() -> int:
    deferred_a, deferred_i = score_fix("deferred_scoreable", True)
    unscore_a, unscore_i = score_fix("unscoreable", False)
    pending_a, pending_i = score_fix("pending", False)
    mismatch_a, mismatch_i = score_fix("mismatch_source", True)

    print(
        f"deferred author={deferred_a['n_resolved']}/{deferred_a['n_statements']} "
        f"indep={deferred_i['n_resolved']}/{deferred_i['n_statements']} "
        f"mean_a={deferred_a['mean_brier']} mean_i={deferred_i['mean_brier']}"
    )
    print(
        f"unscoreable author_status={[r['status'] for r in unscore_a['rows']]} "
        f"indep_status={[r['status'] for r in unscore_i['rows']]} "
        f"mean_a={unscore_a['mean_brier']}"
    )
    print(
        f"pending author={pending_a['n_pending']} indep={pending_i['n_pending']} "
        f"mismatch author_rej={mismatch_a['n_rejected_resolution']} "
        f"indep_rej={mismatch_i['n_rejected_resolution']}"
    )

    recount_ok = (
        counts_match(deferred_a, deferred_i)
        and counts_match(unscore_a, unscore_i)
        and counts_match(pending_a, pending_i)
        and counts_match(mismatch_a, mismatch_i)
    )
    unscoreable_marked = (
        unscore_a["n_unscoreable"] == unscore_a["n_statements"] == 2
        and unscore_a["n_resolved"] == 0
        and unscore_a["mean_brier"] is None
        and all(r["status"] == "UNSCOREABLE" for r in unscore_a["rows"])
        and all(r["status"] == "UNSCOREABLE" for r in unscore_i["rows"])
    )
    pending_not_unscoreable = (
        pending_a["n_pending"] == 1
        and pending_a["n_unscoreable"] == 0
        and pending_a["mean_brier"] is None
    )
    mismatch_rejected = mismatch_a["n_rejected_resolution"] == 1 and mismatch_a[
        "mean_brier"
    ] is None

    traj_bad = S.load_json(HERE / "fixtures" / "unscoreable" / "trajectory.json")
    cheat = M.score_run(traj_bad, None)
    # The check: honest scorer must not accept a population that includes UNSCOREABLE.
    fired_on_bad = (
        cheat.get("unscoreable_counted_as_calibrated") is True
        and cheat.get("mean_brier") is not None
        and cheat.get("n_unscoreable") == 0
        and unscore_a["mean_brier"] is None
        and unscore_a["n_unscoreable"] == 2
    )
    # Silent on known-good: deferred fixture has a real Brier and zero UNSCOREABLE.
    silent_on_good = (
        deferred_a["n_unscoreable"] == 0
        and deferred_a["mean_brier"] is not None
        and deferred_a["n_resolved"] == 3
    )
    print(
        f"recount_ok={recount_ok} unscoreable_marked={unscoreable_marked} "
        f"pending_not_unscoreable={pending_not_unscoreable} "
        f"mismatch_rejected={mismatch_rejected}"
    )
    print(
        f"negative_control fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"cheat_mean={cheat.get('mean_brier')} cheat_n_resolved={cheat.get('n_resolved')}"
    )
    print(
        "negative_control_verbatim: the check rejects a scorer that assigns Brier "
        "to UNSCOREABLE rows by treating them as resolved-correct (y=1); it stays "
        "silent when every statement has a named EXTERNAL_OBSERVABLE and a matching "
        "later resolution."
    )

    if not OUT.is_file():
        print("FAILED:CNL-0074-probe2 artifact missing")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    pub = art.get("fixture_tabulation") or {}
    pub_un = pub.get("unscoreable") or {}
    pub_def = pub.get("deferred_scoreable") or {}
    artifact_ok = (
        art.get("state") == "SUCCESS"
        and "SUCCESS:CNL-0074" in json.dumps(art)
        and pub_un.get("n_unscoreable") == unscore_i["n_unscoreable"]
        and pub_un.get("n_resolved") == unscore_i["n_resolved"]
        and pub_un.get("mean_brier") is None
        and close(pub_def.get("mean_brier"), deferred_i["mean_brier"])
        and pub_def.get("n_resolved") == deferred_i["n_resolved"]
    )
    print(
        f"artifact_ok={artifact_ok} pub_unscoreable={pub_un} "
        f"pub_deferred_mean={pub_def.get('mean_brier')}"
    )
    if not (
        recount_ok
        and unscoreable_marked
        and pending_not_unscoreable
        and mismatch_rejected
        and fired_on_bad
        and silent_on_good
        and artifact_ok
    ):
        print("FAILED:CNL-0074-probe2 independent recount or negative control")
        return 1
    print("SUCCESS:CNL-0074-probe2 independent recount UNSCOREABLE negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
