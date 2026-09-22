#!/usr/bin/env python3
"""AUD-0042 NAMED PROBE 1: execute the never-executed quality.yml test-python steps.

Catalog evidence_requirement Probe 1:
  the runner exit code per step.
Catalog evidence_requirement Probe 2 (see probe2_zero_count_control.py):
  the parsed result summary from each step's own output (counts of passed,
  failed, errored) - an exit code alone is never success, and a step that
  collects zero tests can exit 0.

Inputs (per catalog): "the 60-step list from AUD-0041" and "the recorded 28
executed steps and their 5326 passed / 8 failed result" (BASELINE-SNAPSHOT.json
test_baseline, captured 2026-08-09). This probe re-derives the CURRENT
quality.yml test-python step list (measured, not copied) and reconciles it
against the 27 of 28 baseline suite names that map 1:1 onto a still-existing
step (the 28th, "ci-tests-all", was a single combined pytest invocation that
CI has since split into many granular ci/tests/*.py steps -- recorded as
drift, not silently absorbed). Every remaining step is DEFINITIONALLY
never-executed-as-this-CI-step and is actually invoked here, in this Linux
cloud sandbox, with its verbatim `run:` command and a bounded per-step
timeout. Real exit codes and real parsed pytest summaries are recorded --
no step is marked executed without a subprocess.run() call against it.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-execute-never-run-steps.json"
RAW = PROBE / "probe1-execute-never-run-steps.raw.txt"
WORKFLOW = REPO / ".github" / "workflows" / "quality.yml"

PER_STEP_TIMEOUT_S = 90

# The 27 of 28 Phase-0-baseline (BASELINE-SNAPSHOT.json test_baseline,
# captured 2026-08-09) suite names that map 1:1 onto a still-existing
# quality.yml test-python step NAME today. The 28th baseline entry,
# "ci-tests-all" (1 failed, 557 passed, 1 skipped -- a single combined
# `pytest ci/tests -q` invocation), has since been split by CI into many
# separate named steps (deployable-doc, program-b-register, rules-*,
# rule-audit, adversarial-harness-corpus, docs-executable-claims, ...).
# Each of those split-out steps is treated as NEVER EXECUTED AS THIS STEP --
# the catalog's unit of measure is the CI-declared step, not the underlying
# test file, and a step introduced after the baseline was frozen was never
# run under that name.
BASELINE_MATCHED_STEP_NAMES = {
    "gate-tests-coverage mcp-manager",
    "gate-tests-coverage scholarly-access-mcp",
    "gate-tests-coverage taskwatch_monitor",
    "gate-tests-coverage monitorcore",
    "gate-tests-coverage wfmon adapter contract (skills/workflow-monitor)",
    "gate-tests-coverage mcpctl",
    "gate-tests-coverage mcpapply",
    "gate-tests-coverage stdin-server",
    "gate-tests-coverage harness-drift",
    "gate-tests-coverage command-center",
    "gate-tests-coverage agentspec",
    "gate-tests-coverage agentrail",
    "gate-tests-coverage crcp (credential egress; measured, not 100%-gated)",
    "gate-tests-coverage harness (enshrined runtime; measured, not 100%-gated)",
    "gate-tests-coverage cmd-rewrite hooks (msys-pathconv + no-pager)",
    "gate-tests-coverage search-expansion (rrf + searxng config + query plan)",
    "gate-tests-coverage program-b register (suite + mutation probe)",
    "gate-tests-coverage plugin-cache-reaper (suite + mutation probe)",
    "gate-tests-coverage strict-target hook manifests",
    "gate-tests-coverage rules scope (globally-worded rules stay reachable)",
    "gate-tests-coverage plan-lint stage-0 + resume manifest",
    "gate-tests-coverage codex-databricks-fanout",
    "gate-tests-coverage workflow-authoring lint",
    "gate-tests-coverage git-hygiene message budget",
    "gate-tests-coverage hooks regression harness",
    "gate-tests-coverage harness-corpus (hook-telemetry miner + detector control)",
    "gate-tests-coverage cloud-hub (full suite)",
}

# Steps whose `run:` body references GitHub-Actions-only context
# (${{ steps.X.outputs.Y }}, matrix, secrets, services.*) that cannot resolve
# to a real value outside an actual Actions runner. These are still
# EXECUTED (subprocess.run is called; a real exit code is recorded) but the
# expected outcome is a shell/interpreter error caused by the unresolved
# `${{ }}` literal, not a harness defect in this probe. Recorded up front so
# the report does not misclassify "GHA-context-only" as "probe broken".
GHA_CONTEXT_ONLY_STEPS = {
    "gate-tests-coverage wearables (py3.12; isolated venv)",
    "gate-tests-coverage abbyy-finereader-ocr-mcp (vendored; isolated venv)",
}

PYTEST_SUMMARY_RE = re.compile(
    r"=+ .*?"
    r"(?:(?P<failed>\d+) failed)?.*?"
    r"(?:(?P<passed>\d+) passed)?.*?"
    r"(?:(?P<errors>\d+) error)?.*?"
    r"in [\d.]+s.*?=+"
)
NO_TESTS_RAN_RE = re.compile(r"no tests ran", re.IGNORECASE)
COLLECTED_RE = re.compile(r"collected (\d+) item")
SIMPLE_PASSED_RE = re.compile(r"\b(\d+) passed\b")
SIMPLE_FAILED_RE = re.compile(r"\b(\d+) failed\b")
SIMPLE_ERROR_RE = re.compile(r"\b(\d+) error(?:s)?\b")


def load_test_python_steps() -> list[dict]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = doc["jobs"]["test-python"]
    steps = job["steps"]
    out = []
    for idx, s in enumerate(steps):
        if "uses" in s:
            out.append(
                {"idx": idx, "kind": "uses", "name": s.get("name"), "uses": s["uses"]}
            )
        else:
            out.append(
                {
                    "idx": idx,
                    "kind": "run",
                    "name": s.get("name") or f"(unnamed idx {idx})",
                    "run": s.get("run", ""),
                    "shell": s.get("shell"),
                    "working_directory": s.get("working-directory"),
                }
            )
    return out


def parse_pytest_counts(text: str) -> dict:
    passed = None
    failed = None
    errors = None
    collected = None
    m = SIMPLE_PASSED_RE.findall(text)
    if m:
        passed = sum(int(x) for x in m)
    m = SIMPLE_FAILED_RE.findall(text)
    if m:
        failed = sum(int(x) for x in m)
    m = SIMPLE_ERROR_RE.findall(text)
    if m:
        errors = sum(int(x) for x in m)
    m = COLLECTED_RE.findall(text)
    if m:
        collected = sum(int(x) for x in m)
    no_tests = bool(NO_TESTS_RAN_RE.search(text))
    # "collected count" for this unit's purposes: passed+failed+errors if any
    # pytest-shaped summary line matched, else the explicit "collected N"
    # line, else None (non-pytest step, or pytest never got far enough to
    # print any summary at all -- e.g. a collection-time crash).
    total = None
    if passed is not None or failed is not None or errors is not None:
        total = (passed or 0) + (failed or 0) + (errors or 0)
    elif collected is not None:
        total = collected
    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "collected_explicit": collected,
        "no_tests_ran": no_tests,
        "collected_count": total,
    }


def looks_like_pytest_step(cmd: str) -> bool:
    return "pytest" in cmd


def run_step(idx: int, name: str, cmd: str, timeout: int) -> dict:
    env_note = "GHA-context-only" if name in GHA_CONTEXT_ONLY_STEPS else None
    start = time.monotonic()
    try:
        r = subprocess.run(
            ["bash", "-c", cmd],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        exit_code = r.returncode
        out = (r.stdout or "") + (r.stderr or "")
        timed_out = False
    except subprocess.TimeoutExpired as e:
        exit_code = 124
        out = (
            (e.stdout or "" if isinstance(e.stdout, str) else "")
            + (e.stderr or "" if isinstance(e.stderr, str) else "")
            + f"\nTIMEOUT after {timeout}s"
        )
        timed_out = True
    except OSError as e:
        exit_code = 127
        out = f"{type(e).__name__}: {e}"
        timed_out = False
    elapsed = round(time.monotonic() - start, 2)

    is_pytest = looks_like_pytest_step(cmd)
    counts = (
        parse_pytest_counts(out)
        if is_pytest
        else {
            "passed": None,
            "failed": None,
            "errors": None,
            "collected_explicit": None,
            "no_tests_ran": False,
            "collected_count": None,
        }
    )

    return {
        "idx": idx,
        "name": name,
        "is_pytest_step": is_pytest,
        "env_note": env_note,
        "attempted": True,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_s": elapsed,
        "command_head": cmd.strip().splitlines()[0][:200] if cmd.strip() else "",
        "command_bytes": len(cmd),
        **counts,
        "stdout_tail": out[-2500:],
    }


def main() -> int:
    measured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    steps = load_test_python_steps()
    run_steps = [s for s in steps if s["kind"] == "run"]
    uses_steps = [s for s in steps if s["kind"] == "uses"]

    matched = [s for s in run_steps if s["name"] in BASELINE_MATCHED_STEP_NAMES]
    matched_names_found = {s["name"] for s in matched}
    missing_baseline_names = BASELINE_MATCHED_STEP_NAMES - matched_names_found
    never_executed = [
        s for s in run_steps if s["name"] not in BASELINE_MATCHED_STEP_NAMES
    ]

    lines = [
        "AUD-0042 NAMED PROBE 1: execute never-executed-as-this-step CI steps",
        "unit=AUD-0042",
        f"measured_at={measured_at}",
        f"workflow={WORKFLOW.relative_to(REPO)}",
        f"test_python_total_steps={len(steps)}",
        f"test_python_run_steps={len(run_steps)}",
        f"test_python_uses_steps={len(uses_steps)}",
        "baseline_matched_step_names_declared=28 (27 map 1:1 to a current step; "
        "1 ('ci-tests-all') was split by CI into many current steps -- recorded as drift)",
        f"baseline_matched_found_in_current_workflow={len(matched)}",
        f"missing_baseline_names={sorted(missing_baseline_names)}",
        f"never_executed_as_this_step_count={len(never_executed)}",
        f"per_step_timeout_s={PER_STEP_TIMEOUT_S}",
        "",
    ]
    print("\n".join(lines))

    results = []
    for i, s in enumerate(never_executed):
        print(
            f"[{i + 1}/{len(never_executed)}] idx={s['idx']} {s['name']!r} ...",
            flush=True,
        )
        res = run_step(s["idx"], s["name"], s["run"], PER_STEP_TIMEOUT_S)
        results.append(res)
        tail = res["stdout_tail"].strip().splitlines()
        tail1 = tail[-1] if tail else ""
        print(
            f"    exit={res['exit_code']} timed_out={res['timed_out']} "
            f"collected={res['collected_count']} elapsed={res['elapsed_s']}s "
            f"last_line={tail1[:160]!r}"
        )

    executed_count = len(results)
    with_nonzero_collected = [r for r in results if (r["collected_count"] or 0) > 0]
    with_zero_collected = [
        r for r in results if r["is_pytest_step"] and (r["collected_count"] or 0) == 0
    ]
    exit_zero_but_zero_collected = [
        r for r in with_zero_collected if r["exit_code"] == 0
    ]
    pytest_steps = [r for r in results if r["is_pytest_step"]]

    ok = len(with_nonzero_collected) > 0

    result = {
        "ok": ok,
        "unit": "AUD-0042",
        "probe": 1,
        "measured_at": measured_at,
        "workflow_path": str(WORKFLOW.relative_to(REPO)),
        "test_python_total_steps": len(steps),
        "test_python_run_steps": len(run_steps),
        "test_python_uses_steps": len(uses_steps),
        "baseline_declared_matched_count": 28,
        "baseline_matched_found_in_current_workflow": len(matched),
        "baseline_matched_names": sorted(matched_names_found),
        "missing_baseline_names": sorted(missing_baseline_names),
        "never_executed_before_this_probe": len(never_executed),
        "catalog_declared_never_executed": 32,
        "drift_note": (
            "AUD-0041 measured this job at 68 steps (2026-08-19); it is 70 steps "
            "now (2 gates added since: 'mcp control plane', 'dispatch wiring "
            "deploy (WF-2)'). The catalog's '32' is the 2026-08-09 Phase-0 figure "
            "and is stale; this probe recomputes the never-executed set from the "
            "CURRENT workflow file rather than reusing the stale number."
        ),
        "per_step_timeout_s": PER_STEP_TIMEOUT_S,
        "executed_count": executed_count,
        "with_nonzero_collected_count": len(with_nonzero_collected),
        "with_zero_collected_count": len(with_zero_collected),
        "exit_zero_but_zero_collected_count": len(exit_zero_but_zero_collected),
        "pytest_step_count": len(pytest_steps),
        "non_pytest_step_count": executed_count - len(pytest_steps),
        "exit_code_zero_count": sum(1 for r in results if r["exit_code"] == 0),
        "exit_code_nonzero_count": sum(1 for r in results if r["exit_code"] != 0),
        "timed_out_count": sum(1 for r in results if r["timed_out"]),
        "steps": results,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines.append(f"executed_count={executed_count}")
    lines.append(f"with_nonzero_collected_count={len(with_nonzero_collected)}")
    lines.append(f"with_zero_collected_count={len(with_zero_collected)}")
    lines.append(
        f"exit_zero_but_zero_collected_count={len(exit_zero_but_zero_collected)}"
    )
    lines.append(f"exit_code_zero_count={result['exit_code_zero_count']}")
    lines.append(f"exit_code_nonzero_count={result['exit_code_nonzero_count']}")
    lines.append(f"timed_out_count={result['timed_out_count']}")
    for r in results:
        lines.append(
            f"STEP idx={r['idx']} exit={r['exit_code']} timed_out={r['timed_out']} "
            f"pytest={r['is_pytest_step']} collected={r['collected_count']} "
            f"passed={r['passed']} failed={r['failed']} errors={r['errors']} "
            f"elapsed={r['elapsed_s']}s name={r['name']!r}"
        )
    lines.append("SUCCESS:AUD-0042-probe1" if ok else "FAILED:AUD-0042-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nSUCCESS:AUD-0042-probe1" if ok else "\nFAILED:AUD-0042-probe1")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
