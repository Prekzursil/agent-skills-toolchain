#!/usr/bin/env python3
"""Probe 2: provider-rendered job graph vs adapter graph; fail-fast hide.

Mechanically independent of probe 1 (YAML parse / needs topo). Uses the
AUD-0041 GitHub Actions API snapshot as the rendered graph, plus the
fail-fast control fixture. Does not rewrite the conformance artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from emit_report import API_PATH, CONTROL, OUT, SENTINEL, api_compare, fail_fast_proof  # noqa: E402
from adapter import translate  # noqa: E402
from rebuild_estate import main as rebuild_estate  # noqa: E402

ART = REPO / OUT


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0052-probe2 {msg}")
    return 1


def main() -> int:
    rebuild_estate()
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    ff = fail_fast_proof(CONTROL / "fail-fast.yml")
    if not ff.get("pass"):
        return fail(f"fail-fast {ff}")
    if not ff.get("hides_later_failure"):
        return fail("later step not hidden after first failure")

    estate = HERE / "fixtures" / "estate"
    irs = []
    for path in sorted(estate.glob("*.yml")):
        irs.append(translate(path, REPO, "probe2"))
    api = api_compare(irs)
    if not api.get("pass"):
        return fail(f"api-compare { {k: api.get(k) for k in api if k != 'python_job_skipped_steps'} }")
    if not api.get("step_count_divergence"):
        return fail("YAML step count equalled API step count; injected hooks not observed")
    if not api.get("python_job_hid_later_steps"):
        return fail("API python job did not hide later steps after failure")
    art_api = ((doc.get("tests_required") or {}).get("runtime_graph_independent") or {})
    if art_api.get("quality_api_job_count") != api.get("quality_api_job_count"):
        return fail("artifact API job count drifted from live compare")

    api_file = REPO / API_PATH
    if not api_file.is_file():
        return fail("AUD-0041 API snapshot missing")

    print(
        json.dumps(
            {
                "probe": "probe2-runtime-graph-fail-fast",
                "unit_id": "WFA-0052",
                "fail_fast_hidden": ff.get("hidden_names"),
                "quality_yaml_jobs": api.get("quality_ir_job_count"),
                "quality_api_jobs": api.get("quality_api_job_count"),
                "yaml_steps": api.get("quality_yaml_step_count"),
                "api_steps": api.get("quality_api_step_count"),
                "step_count_divergence": api.get("step_count_divergence"),
                "python_hid_later_steps": api.get("python_job_hid_later_steps"),
                "independent_source": API_PATH,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"fail_fast_hidden={ff.get('hidden_names')} api_jobs={api.get('quality_api_job_count')} "
        f"yaml_steps={api.get('quality_yaml_step_count')} api_steps={api.get('quality_api_step_count')}"
    )
    print("SUCCESS:WFA-0052-probe2 runtime graph fail-fast independent API snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
