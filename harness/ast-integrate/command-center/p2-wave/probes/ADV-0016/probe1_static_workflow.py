#!/usr/bin/env python3
"""Probe 1: YAML-only census of whether the release/quality workflow re-runs scanners.

Does not execute any gate. Does not consult an advisory mirror. A scan step
conditional on a cache key or a restored artifact is recorded as cache-backed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import QUALITY_REL, UNIT, census_workflows  # noqa: E402


def main() -> int:
    census = census_workflows(REPO)
    quality = census.get("quality")
    if quality is None:
        print(json.dumps({"probe": "probe1-static-workflow", "pass": False, "error": "quality.yml missing"}, indent=2, sort_keys=True))
        print("FAILED:ADV-0016-probe1 quality.yml absent")
        return 1

    scan_conditional = any(
        s.get("conditional") or s.get("is_cache") or s.get("is_artifact_restore")
        for s in quality.get("scan_steps") or []
    )
    payload = {
        "probe": "probe1-static-workflow",
        "unit_id": UNIT,
        "instrument": "yaml.safe_load AST walk of .github/workflows; no gate execution",
        "quality_path": QUALITY_REL,
        "quality_sha256": census["quality_sha256"],
        "quality_bytes": census["quality_bytes"],
        "workflow_count": census["workflow_count"],
        "workflow_paths": [w["path"] for w in census["workflows"]],
        "quality_job_names": [j.get("name") or j.get("job_id") for j in (quality.get("jobs") or [])],
        "quality_scan_step_count": len(quality.get("scan_steps") or []),
        "quality_scan_step_count": len(quality.get("scan_steps") or []),
        "quality_cache_or_artifact_step_count": len(quality.get("cache_or_artifact_steps") or []),
        "quality_scan_conditional_on_cache_or_artifact": scan_conditional,
        "quality_scan_conditional_on_cache_or_artifact": scan_conditional,
        "any_scan_step_in_workflows": census["any_scan_step"],
        "quality_excerpt": quality.get("excerpt"),
        "quality_jobs": quality.get("jobs"),
        "finding": (
            "quality.yml has no vulnerability or license scanner step and "
            "does not restore a stored scan artifact; the release-equivalent "
            "workflow cannot re-run scanners it does not invoke."
            if not quality.get("scan_steps")
            else (
                "quality.yml names a scanner step; cache/artifact conditioning="
                + str(scan_conditional)
            )
        ),
        "pass": True,
    }
    payload["finding"] = payload["finding"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:ADV-0016-probe1 YAML census of quality.yml completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
