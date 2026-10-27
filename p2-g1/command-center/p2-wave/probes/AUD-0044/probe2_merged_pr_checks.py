#!/usr/bin/env python3
"""AUD-0044 probe 2 - check contexts a recent MERGED PR actually reported.

Evidence requirement (catalog): "the distinct check-run names reported on a
recent merged PR - a required context whose name no workflow emits is permanently
pending and a produced context that is not required gates nothing."

Re-measures the recorded merged PR (#289, quality run 32790298832) live from the
Actions API and asserts the artifact's disagreement finding still holds:
"gate-tests-coverage (platform)" is produced by the workflow but is NOT in the
required set (gates nothing), while every required context is produced.

Windows platform adaptation of the original probe: subprocess argv form (no
POSIX env-prefix) so cmd.exe can execute it; assertions unchanged.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0044-required-context-audit.json"
UNIT = "AUD-0044"
SUBJECT = "Prekzursil/agent-skills-toolchain"
RUN_ID = 32790298832
MERGED_PR = 289


def gh_api_json(url: str) -> tuple[int, object, str]:
    try:
        p = subprocess.run(["gh", "api", url], capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, None, f"gh-invoke-failed: {exc}"
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode != 0:
        return p.returncode, None, text[-400:]
    try:
        return 0, json.loads(p.stdout), ""
    except ValueError as exc:
        return 1, None, f"json: {exc}: {text[-200:]}"


def fail(msg: str) -> int:
    print(json.dumps({"probe": "probe2-merged-pr-checks", "unit_id": UNIT,
                      "pass": False, "error": msg}))
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))

    rec_pr = doc.get("merged_pr") or {}
    if rec_pr.get("merged_pr") != MERGED_PR:
        return fail(f"artifact merged_pr {rec_pr.get('merged_pr')} != {MERGED_PR}")

    # the merge itself: PR state MERGED (trust PR state, not commit ancestry -
    # squash-merge rewrites history; ci-hygiene rule 4)
    pr_rc, pr, _ = gh_api_json(f"/repos/{SUBJECT}/pulls/{MERGED_PR}")
    if pr_rc != 0 or not pr:
        return fail(f"pulls/{MERGED_PR} rc={pr_rc}")
    if str(pr.get("state") or "").upper() != "CLOSED" or not pr.get("merged_at"):
        return fail(f"PR #{MERGED_PR} state={pr.get('state')} merged_at={pr.get('merged_at')}")

    # the check runs the quality run actually reported
    jobs_rc, jobs, err = gh_api_json(
        f"/repos/{SUBJECT}/actions/runs/{RUN_ID}/jobs?per_page=100")
    if jobs_rc != 0 or not jobs:
        return fail(f"runs/{RUN_ID}/jobs rc={jobs_rc}: {err}")
    live_names = sorted({j.get("name") for j in jobs.get("jobs") or [] if j.get("name")})

    rec_produced = sorted((doc.get("produced_contexts") or {}).get(
        "merged_pr_check_runs") or [])
    rec_required = sorted((doc.get("disagreement") or {}).get("intersection") or [])

    produced_not_required = sorted(set(live_names) - set(rec_required))
    required_not_produced = sorted(set(rec_required) - set(live_names))

    # the artifact's headline finding, re-checked live
    finding = {
        "platform_context_produced_live": "gate-tests-coverage (platform)" in live_names,
        "platform_context_required_live": "gate-tests-coverage (platform)" in rec_required,
    }
    result = {
        "probe": "probe2-merged-pr-checks",
        "unit_id": UNIT,
        "merged_pr": MERGED_PR,
        "pr_state": pr.get("state"),
        "merged_at": pr.get("merged_at"),
        "quality_run_id": RUN_ID,
        "live_check_run_count": len(live_names),
        "live_check_run_names": live_names,
        "artifact_recorded_check_run_names": rec_produced,
        "live_equals_recorded": live_names == rec_produced,
        "required_count": len(rec_required),
        "required_not_produced": required_not_produced,
        "produced_not_required": produced_not_required,
        "finding_recheck": finding,
    }
    print(json.dumps(result, indent=1))

    if live_names != rec_produced:
        return fail(f"live check names {live_names} != artifact-recorded {rec_produced}")
    if not finding["platform_context_produced_live"]:
        return fail("recorded produced-not-required context no longer produced live")
    if required_not_produced:
        return fail(f"required contexts not produced (permanently pending): {required_not_produced}")
    print("SUCCESS:AUD-0044-probe2 merged-PR check names live-match artifact; produced-not-required finding holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
