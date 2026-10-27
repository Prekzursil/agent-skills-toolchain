#!/usr/bin/env python3
"""Independent skip-reason reviewer for TST-0332.

Re-derives executed/unexecuted from the workflow YAML and the run log without
reading harness.analyze() output or any receipt conclusion. Probe 1 compares
this derivation to the harness.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import harness as H


def review(workflow_path: Path, run_path: Path, log_path: Path | None = None) -> dict:
    wf = H.yaml_load(workflow_path)
    run = H.load_run(run_path)
    event = str(run.get("event") or "push")
    log_names = H.parse_log_executed(log_path) if log_path and log_path.is_file() else set()
    jobs_log = H.log_jobs(run)

    unexecuted: list[dict[str, Any]] = []
    executed: list[dict[str, Any]] = []
    jobs = wf.get("jobs") or {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        included, excluded = H.matrix_included_excluded(job)
        steps = job.get("steps") or []
        for excluded_flag, legs in ((False, included), (True, excluded)):
            for leg in legs:
                mk = H.matrix_key(leg)
                log_job = jobs_log.get(f"{job_id}::{mk}") or jobs_log.get(job_id)
                for idx, raw in enumerate(steps):
                    if not isinstance(raw, dict):
                        continue
                    step = {
                        k: H.expand_templates(v, leg) if isinstance(v, str) else v
                        for k, v in raw.items()
                    }
                    if not H.is_test_step(step):
                        continue
                    name = step.get("name") or f"step-{idx}"
                    log_step = H.find_log_step(log_job, name)
                    conclusion = log_step.get("conclusion") if log_step else None
                    ran = conclusion in H.EXECUTED_CONCLUSIONS or (
                        name in log_names and conclusion not in {"skipped", "cancelled"}
                    )
                    rec = {
                        "job": job_id,
                        "name": name,
                        "matrix_key": mk,
                    }
                    if ran:
                        executed.append(rec)
                        continue
                    if excluded_flag:
                        rec["skip_reason"] = "matrix_exclusion"
                    elif (log_job and log_job.get("conclusion") == "cancelled") or (
                        conclusion == "cancelled"
                    ):
                        rec["skip_reason"] = "cancelled"
                    elif H.prior_hard_failure(log_job, idx):
                        rec["skip_reason"] = "earlier_failure"
                    elif H.condition_false(step.get("if"), event) or H.condition_false(
                        job.get("if"), event
                    ):
                        rec["skip_reason"] = "conditional_false"
                    elif conclusion == "skipped":
                        rec["skip_reason"] = "conditional_false"
                    elif log_job is None:
                        rec["skip_reason"] = (
                            "conditional_false"
                            if H.condition_false(job.get("if"), event)
                            else "cancelled"
                        )
                    else:
                        rec["skip_reason"] = "conditional_false"
                    unexecuted.append(rec)

    reasons = sorted({r["skip_reason"] for r in unexecuted})
    return {
        "reviewer_id": "TST-0332-independent-skip-reason-reviewer",
        "independent": True,
        "saw_conclusion_first": False,
        "method": (
            "Walked workflow YAML jobs/steps (with matrix include/exclude) and "
            "the run job-summary independently of harness.analyze. Did not read "
            "the receipt or the harness unexecuted list first."
        ),
        "declared_count": len(executed) + len(unexecuted),
        "executed_count": len(executed),
        "unexecuted_count": len(unexecuted),
        "skip_reasons_present": reasons,
        "unexecuted": unexecuted,
        "executed_names": sorted(r["name"] for r in executed),
        "verdict": "PASS"
        if (
            len(executed) + len(unexecuted) >= 1
            and all(r.get("skip_reason") in H.SKIP_REASONS for r in unexecuted)
            and set(reasons) == set(H.SKIP_REASONS)
        )
        else "FAIL",
    }
