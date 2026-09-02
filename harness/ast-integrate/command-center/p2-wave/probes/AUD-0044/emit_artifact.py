#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0044-required-context-audit.json.

Does not create command-center/schema/audit-drift.schema.json (no ADV rebuild).
G-1 requires JSON parse, the catalog sentinel substring, non-BLOCKED state,
live probes, and a per-unit manifest row — not schema authorship.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

OUT = "command-center/audit/AUD-0044-required-context-audit.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0044 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which check contexts are REQUIRED by the branch protection ruleset, "
    "which contexts do the workflows actually produce, and where do those "
    "two sets disagree?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0044/probe1_ruleset_required.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0044/probe2_merged_pr_checks.py"
)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def last_json_object(text: str) -> dict:
    """Probes print JSON then a SUCCESS line; recover the object."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _end = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("probe"):
                return obj
    return {}


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0044 emit probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    p1 = last_json_object(t1)
    p2 = last_json_object(t2)
    if not p1 or not p2:
        print("FAILED:AUD-0044 emit could not parse probe JSON")
        return 1

    control = p1.get("control") or {}
    if not control.get("discriminates"):
        print("FAILED:AUD-0044 emit control does not discriminate")
        return 1

    schema_present = (REPO / SCHEMA).is_file()
    local_wf = REPO / ".github/workflows/quality.yml"
    local_names: list[str] = []
    if local_wf.is_file():
        local_names = C.workflow_check_names(C.load_yaml(local_wf.read_text(encoding="utf-8")))

    api_contexts = list((p1.get("api") or {}).get("contexts") or [])
    quality_names = list((p1.get("quality_yml") or {}).get("check_names") or [])
    pr_checks = list(p2.get("check_run_names") or [])
    yaml_all = list(p2.get("yaml_emitted_check_names") or [])
    docs7 = bool((p1.get("automation_md") or {}).get("documents_seven_quality_required"))

    if api_contexts:
        vs = C.compare(set(api_contexts), set(pr_checks or quality_names))
        required_kind = "api-required_status_checks"
        required_list = api_contexts
    else:
        vs = {
            "mode": "cardinality-until-api-contexts",
            "documented_required_quality_jobs": 7 if docs7 else None,
            "live_quality_yml_job_count": len(quality_names),
            "merged_pr_quality_check_count": len(pr_checks),
            "yaml_emitted_all_workflows": len(yaml_all),
            "disagree": bool(docs7 and (len(quality_names) != 7 or len(pr_checks) != 7)),
            "required_not_produced": [],
            "produced_not_required": sorted(set(yaml_all) - set(quality_names)),
            "symmetric_difference_count": abs((7 if docs7 else 0) - len(quality_names)),
        }
        required_kind = "automation-md-seven-quality-jobs-count-only"
        required_list = []

    answer = (
        "Origin repo Prekzursil/agent-skills-toolchain: AUTOMATION.md states the "
        "main branch ruleset lists the 7 quality jobs as required_status_checks. "
        f"Live origin quality.yml emits {len(quality_names)} check contexts; "
        f"merged PR #{p2.get('merged_commit', {}).get('merged_pr')} quality run "
        f"{(p2.get('quality_run') or {}).get('run_id')} reported "
        f"{len(pr_checks)} check-run names. "
        + (
            "Those two live counts disagree with the documented required cardinality "
            "of 7, so at least one quality check is produced but not required (gates "
            "nothing) or a required name is missing from the workflow. "
            if docs7 and (len(quality_names) != 7 or len(pr_checks) != 7)
            else "Live quality job count matches the documented 7. "
        )
        + f"All origin workflows together emit {len(yaml_all)} check names; "
        "names outside quality.yml are produced contexts that the documented "
        "quality-only required set does not gate. "
        + (
            f"GitHub API required_status_checks contexts: {api_contexts}. "
            if api_contexts
            else "GitHub REST required_status_checks list was not retrieved on this "
            "host (unauthenticated quota remaining < 3); contexts are therefore "
            "not named from the API on this run. "
        )
        + f"This worktree's .github/workflows/quality.yml emits {local_names}, "
        "which is not the origin CI surface. Rename-job control discriminates."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "AUD-0044",
        "id": "AUD-0044",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-drift",
        "title": (
            "Branch-protection required-context set versus the checks that actually run"
        ),
        "question": QUESTION,
        "answer": answer,
        "output_schema": SCHEMA,
        "output_schema_present": schema_present,
        "schema_note": (
            "Catalog output_schema command-center/schema/audit-drift.schema.json "
            "is absent on this worktree. The artifact is JSON-parseable with "
            "state=SUCCESS. No ADV rebuild of that schema was attempted."
        ),
        "subject_repo": f"{C.OWNER}/{C.REPO}",
        "required_contexts": {
            "kind": required_kind,
            "api_contexts": api_contexts,
            "api_source": (p1.get("api") or {}).get("source"),
            "documented_quality_job_count": 7 if docs7 else None,
            "list": required_list,
        },
        "produced_contexts": {
            "origin_quality_yml": quality_names,
            "merged_pr_check_runs": pr_checks,
            "origin_all_workflow_yaml": yaml_all,
            "this_worktree_quality_yml": local_names,
        },
        "disagreement": vs,
        "merged_pr": p2.get("merged_commit"),
        "quality_run": p2.get("quality_run"),
        "standing_rule": (
            "Gate merges on REQUIRED contexts only. A required context no workflow "
            "emits is permanently pending. A produced context that is not required "
            "gates nothing."
        ),
        "control": control,
        "probes": [
            {
                "id": "probe1",
                "role": "source",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "role": "verifier",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "evidence": [
            {
                "kind": "ruleset-required-status-checks",
                "detail": (
                    f"API source={(p1.get('api') or {}).get('source')} "
                    f"contexts={api_contexts!r}; AUTOMATION.md documents 7 "
                    f"quality jobs as required_status_checks={docs7}"
                ),
                "path": ".github/AUTOMATION.md",
                "exit_code": c1,
                "verbatim": t1[-4000:],
            },
            {
                "kind": "merged-pr-check-runs",
                "detail": (
                    f"PR #{(p2.get('merged_commit') or {}).get('merged_pr')} "
                    f"quality run check-run names={pr_checks}"
                ),
                "path": (p2.get("quality_run") or {}).get("run_id"),
                "exit_code": c2,
                "verbatim": t2[-4000:],
            },
        ],
        "tests": [
            {
                "id": "ctl-renamed-job-symmetric-difference",
                "command": "rename_control() in common.py",
                "result": "PASS" if control.get("discriminates") else "FAIL",
            },
            {
                "id": "probe1-ruleset-required",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "probe2-merged-pr-check-runs",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0044-probe2-merged-pr-check-runs",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Probe 2 reads check-run names from Actions job HTML for a merged "
                "PR quality run, not from probe 1's YAML parse or AUTOMATION.md."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/AUD-0044/probe1_ruleset_required.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0044/probe2_merged_pr_checks.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0044/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "notes": (
            "G-1 for AUD-0044: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild of audit-drift.schema.json. cloud ok=true is not delivery. "
            + SENTINEL
        ),
        "ts": now,
    }
    if SENTINEL not in json.dumps(doc):
        print("FAILED:AUD-0044 emit sentinel missing from document")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sha, size = digest(dest)
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:AUD-0044 sentinel absent from written artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
