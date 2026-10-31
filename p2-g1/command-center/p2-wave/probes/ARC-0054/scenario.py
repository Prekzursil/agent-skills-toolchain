"""Both-states demonstration of every ARC-0054 criterion on real artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import criteria as C
import repair as R

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def both_states(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    live_err = C.live_measure_error()
    pass_err = C.contract_rewrite_of_measure_error()
    trap_err = C.reviewer_trap_error()
    e_fail, e_fail_why = C.error_names_next_action(live_err)
    e_pass, e_pass_why = C.error_names_next_action(pass_err)
    trap_author, trap_author_why = C.error_names_next_action(trap_err)
    trap_reach, trap_reach_why = C.next_action_reachable(trap_err, repo)
    pass_reach, pass_reach_why = C.next_action_reachable(pass_err, repo)

    wf = C.load_a1_workflow(repo)
    stop_live, stop_live_why = C.stopping_documented(wf)
    wf_doc = C.documented_copy(wf)
    stop_doc, stop_doc_why = C.stopping_documented(wf_doc)

    cat = C.catalog_stats(repo)
    cat_ok, cat_why = C.catalog_browseable(
        cat["n_items"], cat["largest_bucket"], cat["has_job_index"], cat["page_budget"]
    )
    roster = C.phase3_roster(repo)
    ros_ok, ros_why = C.catalog_browseable(
        roster["n_items"],
        roster["largest_bucket"],
        roster["has_job_index"],
        roster["page_budget"],
    )

    rel = "wf.catalog-class.discovery-only.json"
    honest_plan = R.plan_repair(wf, rel=rel)
    repaired, apply_res = R.apply_repair(wf, rel=rel)
    honest_obs = {
        "files": apply_res.get("files") or [],
        "bytes": apply_res.get("bytes_written") or 0,
    }
    dry_ok, dry_why = C.dryrun_honest(honest_plan, honest_obs)
    lie_ok, lie_why = C.dryrun_honest(R.lying_plan(wf), honest_obs)

    healthy_res = R.apply_repair(wf_doc, rel=rel)[1]
    healthy_ok, healthy_why = C.repair_status_ok(healthy_res, expect_healthy=True)
    broken_ok, broken_why = C.repair_status_ok(apply_res, expect_healthy=False)
    mislabel_ok, mislabel_why = C.repair_status_ok(
        R.mislabel_success(wf_doc), expect_healthy=True
    )
    silent_ok, silent_why = C.repair_status_ok(R.silent_repair(wf), expect_healthy=False)

    checks = {
        "error_fail_rejected": (not e_fail) and e_fail_why == "happened-missing",
        "error_pass_accepted": e_pass,
        "error_pass_reachable": pass_reach,
        "stopping_live_undocumented": (not stop_live)
        and stop_live_why == "stopping-undocumented",
        "stopping_repaired_documented": stop_doc,
        "catalog_live_unbrowseable": not cat_ok,
        "catalog_phase3_browseable": ros_ok,
        "dryrun_honest_matches_apply": dry_ok,
        "dryrun_lie_detected": not lie_ok,
        "repair_healthy_noop": healthy_ok,
        "repair_broken_repaired": broken_ok,
        "repair_success_on_healthy_rejected": not mislabel_ok,
        "repair_silent_detected": not silent_ok,
        "reviewer_trap_author_would_pass": trap_author,
        "reviewer_trap_reachable_fails": not trap_reach,
    }
    failed = [k for k, v in checks.items() if not v]
    return {
        "pass": not failed,
        "failed": failed,
        "checks": checks,
        "details": {
            "live_error": live_err,
            "pass_error": pass_err,
            "trap_error": trap_err,
            "error_fail_why": e_fail_why,
            "error_pass_why": e_pass_why,
            "pass_reach_why": pass_reach_why,
            "trap_author_why": trap_author_why,
            "trap_reach_why": trap_reach_why,
            "stop_live_why": stop_live_why,
            "stop_doc_why": stop_doc_why,
            "catalog": cat,
            "catalog_why": cat_why,
            "roster": roster,
            "roster_why": ros_why,
            "honest_plan": honest_plan,
            "apply": {
                k: apply_res.get(k) for k in ("status", "bytes_written", "files", "reason")
            },
            "dry_why": dry_why,
            "lie_why": lie_why,
            "healthy_why": healthy_why,
            "broken_why": broken_why,
            "mislabel_why": mislabel_why,
            "silent_why": silent_why,
            "a8_design_present": (repo / "command-center/phase3/A8/DESIGN.json").is_file(),
            "repaired_stopping": repaired.get("stopping"),
        },
    }
