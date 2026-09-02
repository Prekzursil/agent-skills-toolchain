#!/usr/bin/env python3
"""Probe 2: distinct check-run names reported on a recent merged PR.

Live path: commits/main.atom -> merged PR id, quality.yml Actions run job
pages (streaming-graph-job.name). Independently loads every origin workflow
YAML so produced-not-required is not flattened to the quality workflow alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

UNIT = "AUD-0044"


def main() -> int:
    commit = C.latest_commit_atom()
    runs = C.quality_workflow_runs()
    run_id = (runs.get("run_ids") or [None])[0]
    run = C.job_ids_for_run(run_id) if run_id else {"ok": False, "job_ids": []}
    job_rows = []
    check_names: list[str] = []
    for jid in run.get("job_ids") or []:
        row = C.job_display_name(str(run_id), jid)
        job_rows.append(row)
        if row.get("name") and row["name"] not in check_names:
            check_names.append(row["name"])

    produced_yaml = C.produced_from_all_workflows()
    yaml_names = produced_yaml.get("check_names") or []
    quality_names = []
    for wf in produced_yaml.get("workflows") or []:
        if str(wf.get("file") or "").endswith("quality.yml"):
            quality_names = list(wf.get("check_names") or [])

    docs = C.fetch_automation_md()
    # Probe 2 does not claim the API list; it compares PR-reported checks
    # against YAML-emitted names and the documented required cardinality.
    vs_yaml_quality = C.compare(set(quality_names), set(check_names))
    extra_vs_quality = sorted(set(yaml_names) - set(quality_names))

    payload = {
        "probe": "probe2-merged-pr-check-runs",
        "unit_id": UNIT,
        "repo": f"{C.OWNER}/{C.REPO}",
        "merged_commit": commit,
        "quality_run": {
            "run_id": run_id,
            "ok": run.get("ok"),
            "title": run.get("title"),
            "job_count": len(run.get("job_ids") or []),
        },
        "check_run_names": check_names,
        "check_run_count": len(check_names),
        "jobs": [
            {"job_id": r.get("job_id"), "name": r.get("name"), "status": r.get("status")}
            for r in job_rows
        ],
        "yaml_emitted_check_names": yaml_names,
        "yaml_emitted_count": len(yaml_names),
        "quality_yml_names": quality_names,
        "comparison_pr_checks_vs_quality_yml": vs_yaml_quality,
        "yaml_names_outside_quality": extra_vs_quality,
        "documented_required_quality_jobs": 7
        if docs.get("documents_seven_quality_required")
        else None,
        "pr_quality_jobs_vs_documented_required": {
            "documented_required": 7
            if docs.get("documents_seven_quality_required")
            else None,
            "pr_quality_check_count": len(check_names),
            "disagree": bool(
                docs.get("documents_seven_quality_required") and len(check_names) != 7
            ),
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not commit.get("ok") or not commit.get("merged_pr"):
        print(f"FAILED:{UNIT}-probe2 latest main commit is not a merged PR")
        return 1
    if not check_names:
        print(f"FAILED:{UNIT}-probe2 no check-run names on quality run {run_id}")
        return 1
    if len(check_names) < 2:
        print(f"FAILED:{UNIT}-probe2 expected multiple quality checks, got {check_names}")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 merged_pr=#{commit.get('merged_pr')} "
        f"sha={commit.get('sha')} quality_run={run_id} "
        f"check_runs={len(check_names)} yaml_emitted={len(yaml_names)} "
        f"quality_jobs={len(quality_names)} "
        f"vs_documented_7_disagree="
        f"{payload['pr_quality_jobs_vs_documented_required']['disagree']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
