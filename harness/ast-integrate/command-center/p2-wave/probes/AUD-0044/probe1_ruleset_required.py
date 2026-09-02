#!/usr/bin/env python3
"""Probe 1: branch-ruleset required_status_checks vs live quality job names.

Primary: GitHub API rules/branches/main + rulesets when quota remains.
Live fallback: AUTOMATION.md (documents 7 quality jobs as required_status_checks)
plus the job name: fields on origin quality.yml.

Control: renamed scratch job must produce a nonempty symmetric difference.
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
    control = C.rename_control()
    api = C.try_ruleset_api()
    docs = C.fetch_automation_md()
    quality = C.fetch_workflow_yaml("quality.yml")
    quality_names = quality.get("check_names") or []

    api_contexts = list(api.get("contexts") or [])
    required_source = api.get("source")
    required: list[str] = list(api_contexts)
    if not required and docs.get("documents_seven_quality_required"):
        required_source = "automation-md-count-only"
        # Do not invent which 7 of the 8 quality names are required.
        required = []

    comparison = C.compare(set(api_contexts), set(quality_names)) if api_contexts else {
        "required_count": 7 if docs.get("documents_seven_quality_required") else 0,
        "produced_count": len(quality_names),
        "both_count": None,
        "required_not_produced": [],
        "produced_not_required": (
            ["<unidentified 1 of 8 quality jobs>"]
            if docs.get("documents_seven_quality_required") and len(quality_names) == 8
            else []
        ),
        "intersection": [],
        "symmetric_difference": (
            ["cardinality: documented-required=7 live-quality-jobs=" + str(len(quality_names))]
            if docs.get("documents_seven_quality_required")
            else []
        ),
        "symmetric_difference_count": abs(
            (7 if docs.get("documents_seven_quality_required") else 0) - len(quality_names)
        ),
        "disagree": bool(
            docs.get("documents_seven_quality_required") and len(quality_names) != 7
        ),
        "mode": "cardinality-until-api-contexts",
    }

    payload = {
        "probe": "probe1-ruleset-required",
        "unit_id": UNIT,
        "repo": f"{C.OWNER}/{C.REPO}",
        "api": {
            "source": api.get("source"),
            "attempted": api.get("attempted"),
            "quota_remaining": (api.get("quota") or {}).get("remaining"),
            "contexts": api_contexts,
            "endpoints": api.get("endpoints"),
            "skip_reason": api.get("skip_reason"),
        },
        "automation_md": docs,
        "quality_yml": {
            "ok": quality.get("ok"),
            "status": quality.get("status"),
            "bytes": quality.get("bytes"),
            "check_names": quality_names,
            "job_count": len(quality_names),
        },
        "required_source": required_source,
        "required_contexts": required,
        "comparison_vs_quality_jobs": comparison,
        "control": control,
    }

    print(json.dumps(payload, indent=1, sort_keys=True))
    if not control.get("discriminates"):
        print(f"FAILED:{UNIT}-probe1 rename-job control does not discriminate")
        return 1
    if not quality.get("ok") or len(quality_names) < 1:
        print(f"FAILED:{UNIT}-probe1 live quality.yml check names missing")
        return 1
    if not docs.get("ok"):
        print(f"FAILED:{UNIT}-probe1 AUTOMATION.md fetch failed")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe1 required_source={required_source} "
        f"api_contexts={len(api_contexts)} quality_jobs={len(quality_names)} "
        f"disagree={comparison.get('disagree')} "
        f"control_ok={control.get('discriminates')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
