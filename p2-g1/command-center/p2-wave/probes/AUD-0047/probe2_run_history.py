#!/usr/bin/env python3
"""Probe 2: run-history receipt for path-filter misses.

The pattern evaluator is the model. This probe checks a commit ledger:
a one-file commit of a protected path that the filter ignores must show
the gate did not run, and a commit that still touches a visible protected
path must show the gate did run. Recorded AUD-0041 Actions API runs are
the live-estate receipt that quality.yml actually executed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from eval_audit import matcher_agrees_with_ledger, scan  # noqa: E402

LEDGER = HERE / "fixtures" / "run-history.json"
AUD41_API = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0047-probe2 {msg}")
    return 1


def try_live_search() -> dict:
    gh = shutil.which("gh")
    git = shutil.which("git")
    out: dict = {
        "gh_present": bool(gh),
        "git_present": bool(git),
        "git_repo": (REPO / ".git").exists(),
        "gh_run_list_attempted": False,
        "gh_run_list_rc": None,
        "gh_run_list_unavailable_reason": None,
    }
    if not gh:
        out["gh_run_list_unavailable_reason"] = "gh-not-on-PATH"
        return out
    out["gh_run_list_attempted"] = True
    try:
        proc = subprocess.run(
            ["gh", "run", "list", "--limit", "5"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
        out["gh_run_list_rc"] = proc.returncode
        if proc.returncode != 0:
            tail = ((proc.stderr or "") + (proc.stdout or "")).strip().replace("\n", " ")
            out["gh_run_list_unavailable_reason"] = tail[:240] or f"exit-{proc.returncode}"
    except subprocess.TimeoutExpired:
        out["gh_run_list_rc"] = 124
        out["gh_run_list_unavailable_reason"] = "timeout"
    except OSError as exc:
        out["gh_run_list_rc"] = 127
        out["gh_run_list_unavailable_reason"] = type(exc).__name__
    return out


def main() -> int:
    errors: list[str] = []
    result = scan()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ok, disagreements = matcher_agrees_with_ledger(result["fixture_rows"], ledger)
    if not ok:
        errors.append("matcher/ledger disagreement: " + "; ".join(disagreements[:8]))

    by_commit = {c["id"]: c for c in ledger.get("commits") or []}
    secret = by_commit["FIX-ONLY-SECRET"]["runs"]
    app = by_commit["FIX-ONLY-APP"]["runs"]
    mixed = by_commit["FIX-MIXED"]["runs"]

    if secret["fixture-control-miss"]["ran"]:
        errors.append("control receipt: secret-only commit must not run miss-fixture")
    if not app["fixture-control-miss"]["ran"]:
        errors.append("control receipt: app-only commit must still run miss-fixture")
    if not mixed["fixture-control-miss"]["ran"]:
        errors.append("mixed commit must still run miss-fixture (not all files ignored)")
    if secret["fixture-control-narrow"]["ran"]:
        errors.append("narrow paths must skip a secret-only commit")
    if not secret["fixture-control-hit"]["ran"]:
        errors.append("hit fixture must run on protected/secret.py")

    recorded = []
    if AUD41_API.is_file():
        api = json.loads(AUD41_API.read_text(encoding="utf-8"))
        for run in api.get("runs") or []:
            recorded.append(
                {
                    "run_id": run.get("run_id"),
                    "workflow": run.get("workflow"),
                    "api_job_count": run.get("api_job_count"),
                }
            )
        quality = [r for r in recorded if r.get("workflow") == "quality"]
        if not quality:
            errors.append("AUD-0041 API receipt has no quality workflow run")
        elif not quality[0].get("run_id"):
            errors.append("quality run_id missing")
    else:
        errors.append("AUD-0041 probe2-actions-api.json absent")

    live = try_live_search()
    if errors:
        for item in errors:
            print(" ", item)
        return fail(f"{len(errors)} assertion(s)")

    gh_join = (
        "a fresh gh file-to-run join is unavailable rather than invented"
        if not live.get("gh_present")
        else "gh is on PATH; run-list attempt recorded under live_search"
    )
    git_state = "git checkout" if live.get("git_repo") else "not a git checkout"
    note = (
        "Fixture ledger is the both-states receipt for the evaluator. "
        "AUD-0041 recorded Actions API runs are the live-estate receipt "
        "that quality.yml executed. "
        f"Live .github/workflows present={result['live_workflows_dir_exists']} "
        f"files={result['live_workflow_count']} "
        f"with_path_filter={result['live_with_path_filter']}. "
        f"This tree is {git_state}; {gh_join}."
    )
    payload = {
        "probe": "probe2-run-history",
        "unit_id": "AUD-0047",
        "pass": True,
        "matcher_agrees_with_ledger": True,
        "control_secret_only_skipped_miss_fixture": True,
        "control_app_only_ran_miss_fixture": True,
        "aud41_recorded_run_count": len(recorded),
        "aud41_quality_run_id": next(
            (r["run_id"] for r in recorded if r.get("workflow") == "quality"),
            None,
        ),
        "live_search": live,
        "live_workflows_dir_exists": result["live_workflows_dir_exists"],
        "live_workflow_count": result["live_workflow_count"],
        "live_with_path_filter": result["live_with_path_filter"],
        "note": note,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0047-probe2 run-history receipt: secret-only commit "
        "skipped the paths-ignore gate; matcher agreed with the ledger"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
