#!/usr/bin/env python3
"""AUD-0043 named probe 1: CI-versus-baseline invocation census.

Parses .github/workflows/quality.yml with a real YAML parser (not a regex
scrape) and classifies every step of the `test-python` job's `run:` block by
which pytest invocation style it actually uses:

  * "bare-pytest-post-install" -- the step's run block contains a `pip
    install` line and then invokes the installed `pytest` CONSOLE SCRIPT
    directly (no `python -m`). This exercises whatever the packaging
    manifest actually shipped -- the same route `pip install <artifact>`
    would take. quality.yml's own inline comments (mcpctl/mcpapply/
    harness-drift steps) document that this style is deliberately chosen
    BECAUSE it catches import-path regressions that `python -m pytest`
    cannot.
  * "python-dash-m-pytest" -- the step invokes `python -m pytest`, which
    (per those same comments) additionally prepends the CWD to sys.path.
    This is "the baseline runner command" named in the catalog's `inputs`.
  * "bare-pytest-no-install-seen" -- a bare `pytest` invocation with no
    `pip install` line visible in the same run block (install happens
    earlier or is implicit).
  * "other" -- no recognisable pytest invocation in the run block at all
    (e.g. a step that only runs a non-pytest script).

This is a real measurement of the repo's OWN checked-in CI file: it answers
"of every declared Python test-python step, how many invoke tests the same
way a naive local `python -m pytest` baseline would, and how many invoke
tests the way an installed console script would?" It does not by itself
prove a live regression; probe 2 supplies the controlled both-states
demonstration of WHY the two styles diverge on a packaging defect.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOW = REPO / ".github/workflows/quality.yml"
JOB_NAME = "test-python"


def classify(run_block: str | None) -> str:
    if not run_block:
        return "other"
    has_python_m = bool(re.search(r"\bpython3?\s+-m\s+pytest\b", run_block))
    has_bare_pytest = bool(re.search(r"^\s*pytest\b", run_block, re.MULTILINE))
    has_pip_install = bool(re.search(r"\bpip install\b", run_block))
    if has_bare_pytest and has_pip_install and not has_python_m:
        return "bare-pytest-post-install"
    if has_python_m:
        return "python-dash-m-pytest"
    if has_bare_pytest:
        return "bare-pytest-no-install-seen"
    return "other"


def main() -> int:
    if not WORKFLOW.is_file():
        print(f"FAILED:AUD-0043-probe1 workflow file absent: {WORKFLOW}")
        return 1
    text = WORKFLOW.read_text(encoding="utf-8")
    try:
        wf = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        print(f"FAILED:AUD-0043-probe1 workflow did not parse as YAML: {exc}")
        return 1

    jobs = wf.get("jobs") if isinstance(wf, dict) else None
    if not isinstance(jobs, dict) or JOB_NAME not in jobs:
        print(f"FAILED:AUD-0043-probe1 job {JOB_NAME!r} not found in {WORKFLOW}")
        return 1
    job = jobs[JOB_NAME]
    raw_steps = job.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        print(f"FAILED:AUD-0043-probe1 job {JOB_NAME!r} has no steps")
        return 1

    steps = []
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            continue
        name = step.get("name")
        if not isinstance(name, str):
            continue  # `uses:` checkout/setup-python steps carry no test invocation
        run_block = step.get("run")
        wd = step.get("with", {}) if False else step.get("working-directory")
        kind = classify(run_block if isinstance(run_block, str) else None)
        steps.append(
            {
                "step_index": i,
                "step_name": name,
                "working_directory": wd,
                "invocation": kind,
                "has_pip_install": bool(
                    isinstance(run_block, str) and re.search(r"\bpip install\b", run_block)
                ),
                "has_uses": "uses" in step,
            }
        )

    gate_steps = [s for s in steps if s["step_name"].startswith("gate-tests-coverage")]
    non_gate_steps = [s for s in steps if s not in gate_steps]

    total = len(gate_steps)
    bare_post_install = [s for s in gate_steps if s["invocation"] == "bare-pytest-post-install"]
    python_m = [s for s in gate_steps if s["invocation"] == "python-dash-m-pytest"]
    bare_no_install = [s for s in gate_steps if s["invocation"] == "bare-pytest-no-install-seen"]
    other = [s for s in gate_steps if s["invocation"] == "other"]

    # Both-states sanity control over the classifier itself: an engineered run block for
    # each recognised class must be classified as that class, and an irrelevant body must
    # fall through to "other" -- if the classifier is broken (e.g. always returns the same
    # label, or a mis-ordered elif chain swallows one class) this control catches it before
    # the census numbers below are trusted.
    ctrl_bare = classify("pip install -e .\npytest --cov=x\n")
    ctrl_m = classify("pip install pytest\npython -m pytest tests -q\n")
    ctrl_no_install = classify("pytest tests/test_source.py -q\n")
    ctrl_other = classify("echo hello\n")
    control_ok = (
        ctrl_bare == "bare-pytest-post-install"
        and ctrl_m == "python-dash-m-pytest"
        and ctrl_no_install == "bare-pytest-no-install-seen"
        and ctrl_other == "other"
    )

    doc = {
        "unit": "AUD-0043",
        "probe": 1,
        "workflow_path": str(WORKFLOW.relative_to(REPO)),
        "job": JOB_NAME,
        "total_job_steps": len(steps),
        "non_test_steps_excluded": len(non_gate_steps),
        "gate_tests_coverage_step_count": total,
        "bare_pytest_post_install_count": len(bare_post_install),
        "python_dash_m_pytest_count": len(python_m),
        "bare_pytest_no_install_seen_count": len(bare_no_install),
        "other_count": len(other),
        "bare_pytest_post_install_steps": [s["step_name"] for s in bare_post_install],
        "python_dash_m_pytest_steps": [s["step_name"] for s in python_m],
        "bare_pytest_no_install_seen_steps": [s["step_name"] for s in bare_no_install],
        "other_steps": [s["step_name"] for s in other],
        "steps": gate_steps,
        "control": {
            "ctrl_bare": ctrl_bare,
            "ctrl_m": ctrl_m,
            "ctrl_no_install": ctrl_no_install,
            "ctrl_other": ctrl_other,
            "ok": control_ok,
        },
        "ok": total > 0 and control_ok,
    }

    print("AUD-0043 NAMED PROBE 1: CI-versus-baseline invocation census")
    print("unit=AUD-0043")
    print(f"workflow={doc['workflow_path']} job={JOB_NAME}")
    print(f"gate_tests_coverage_step_count={total}")
    print(f"bare_pytest_post_install_count={len(bare_post_install)}")
    print(f"python_dash_m_pytest_count={len(python_m)}")
    print(f"bare_pytest_no_install_seen_count={len(bare_no_install)}")
    print(f"other_count={len(other)}")
    for s in gate_steps:
        print(
            f"STEP\t{s['step_name']}\t{s['invocation']}\t"
            f"pip_install={s['has_pip_install']}\twd={s['working_directory']}"
        )
    print(
        f"CONTROL ok={control_ok} ctrl_bare={ctrl_bare} ctrl_m={ctrl_m} "
        f"ctrl_no_install={ctrl_no_install} ctrl_other={ctrl_other}"
    )
    print("SUCCESS:AUD-0043-probe1" if doc["ok"] else "FAILED:AUD-0043-probe1")

    out = Path(__file__).resolve().parent / "probe1-ci-invocation-census.json"
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
