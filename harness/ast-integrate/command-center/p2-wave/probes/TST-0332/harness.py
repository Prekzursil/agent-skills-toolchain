#!/usr/bin/env python3
"""Declared-vs-executed CI test-step detector (TST-0332).

A green workflow conclusion is not evidence that any particular test step ran.
This harness parses GitHub Actions YAML for declared test steps, parses a run
log / job-summary for executed ones, then reports the set difference with a
skip-reason on every unexecuted step.

Skip reasons (required): conditional_false, matrix_exclusion, earlier_failure,
cancelled.
"""
from __future__ import annotations

import itertools
import json
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0332"
PLANTED_NAME = "planted-cannot-run"
SENTINEL = "SUCCESS:TST-0332"

WF_REL = "command-center/p2-wave/probes/TST-0332/fixtures/workflows/phase0-ci-test-gap.yml"
RUN_REL = "command-center/p2-wave/probes/TST-0332/fixtures/runs/latest-green.json"
LOG_REL = "command-center/p2-wave/probes/TST-0332/fixtures/runs/latest-green.log"

# Phase-0 baseline: 60 declared test steps, 28 executed. Names are the real
# quality.yml gate-tests-coverage steps from AUD-0041's YAML inventory.
EXECUTED_NAMES = [
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
    "gate-tests-coverage measure-guard",
    "gate-tests-coverage agentspec",
    "gate-tests-coverage agentrail",
    "gate-tests-coverage crcp (credential egress; measured, not 100%-gated)",
    "gate-tests-coverage harness (enshrined runtime; measured, not 100%-gated)",
    "triage-router standalone regression",
    "gate-tests-coverage cmd-rewrite hooks (msys-pathconv + no-pager)",
    "gate-tests-coverage search-expansion (rrf + searxng config + query plan)",
    "gate-tests-coverage deployable-doc/code path consistency",
    "gate-tests-coverage program-b register (suite + mutation probe)",
    "gate-tests-coverage plugin-cache-reaper (suite + mutation probe)",
    "gate-tests-coverage strict-target hook manifests",
    "gate-tests-coverage rules tree integrity",
    "gate-tests-coverage coverage-authority consistency",
    "gate-tests-coverage rules scope (globally-worded rules stay reachable)",
    "gate-tests-coverage rules selector inheritance",
    "gate-tests-coverage plan-lint stage-0 + resume manifest",
    "gate-tests-coverage rules/common rule-vs-code contracts",
]
CONDITIONAL_NAMES = [
    "gate-tests-coverage rules/commands doc contracts",
    "gate-tests-coverage rules doc coherence (review boundary + perl examples)",
    "gate-tests-coverage adversarial harness corpus",
    "gate-tests-coverage rules hook-example shape",
    "gate-tests-coverage event-ledger prune-report + oats",
    "gate-tests-coverage review-severity coherence",
    "gate-tests-coverage hook-manifest provenance",
    "gate-tests-coverage bounded hook launcher",
    "gate-tests-coverage event-ledger recovery keystone",
    "gate-tests-coverage closed-batch config editor",
]
EARLIER_FAILURE_NAMES = [
    "gate-tests-coverage crcp control plane",
    "gate-tests-coverage repomap grounding pack",
    "gate-tests-coverage claim-verify-gate (suite + mutation probe)",
    "gate-tests-coverage fanout-schema (module + production lint)",
    "gate-tests-coverage hook manifest conformance",
    "browser-rail helper tests (pure logic, no browser)",
    "gate-tests-coverage codex-databricks-fanout",
    "gate-tests-coverage codex-databricks-fanout (backends+engine 100%)",
]
MATRIX_LEGS = [
    ("workflow-authoring", "gate-tests-coverage workflow-authoring lint"),
    ("omniaudit-mcp", "gate-tests-coverage omniaudit-mcp (vendored; isolated venv)"),
    ("vendored-isolation", "vendored-tree import isolation (shared interpreter stays clean)"),
    ("tool-result-sentinel", "gate-tests-coverage tool-result-sentinel"),
    ("git-hygiene", "gate-tests-coverage git-hygiene message budget"),
    ("deny-credential-reads", "gate-tests-coverage deny-credential-reads denylist coverage"),
    ("hooks-regression", "gate-tests-coverage hooks regression harness"),
    ("memory-guard", "gate-tests-coverage hooks standalone (memory-guard)"),
]
CANCELLED_NAMES = [
    "gate-tests-coverage agent-self deployed-config hooks",
    "gate-tests-coverage harness-corpus (hook-telemetry miner + detector control)",
    "gate-tests-coverage mcp servers (stdlib-only; per-package rootdir)",
    "gate-tests-coverage cloud-hub (full suite)",
    "gate-tests-coverage wearables (py3.12; isolated venv)",
    "gate-tests-coverage abbyy-finereader-ocr-mcp (vendored; isolated venv)",
]

SKIP_REASONS = (
    "conditional_false",
    "matrix_exclusion",
    "earlier_failure",
    "cancelled",
)
EXECUTED_CONCLUSIONS = frozenset({"success", "failure"})
GROUP_RE = re.compile(
    r"^(?:[\dT:.\-Z]+ )?##\[group\]Run\s+(.+?)\s*$",
    re.MULTILINE,
)


def q(name: str) -> str:
    return json.dumps(name, ensure_ascii=True)


def yaml_load(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a mapping")
    return doc


def yaml_triggers(doc: dict[str, Any]) -> Any:
    # PyYAML 1.1: bare key `on:` becomes boolean True.
    return doc.get("on", doc.get(True))


def expand_templates(text: Any, leg: dict[str, Any]) -> Any:
    if not isinstance(text, str) or not leg:
        return text
    out = text
    for key, val in leg.items():
        out = out.replace("${{ matrix." + str(key) + " }}", str(val))
        out = out.replace("${{matrix." + str(key) + "}}", str(val))
    return out


def matrix_included_excluded(
    job: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    strat = (job or {}).get("strategy") or {}
    matrix = strat.get("matrix")
    if not isinstance(matrix, dict):
        return [{}], []
    include = [x for x in (matrix.get("include") or []) if isinstance(x, dict)]
    exclude = [x for x in (matrix.get("exclude") or []) if isinstance(x, dict)]
    axes = {
        k: v
        for k, v in matrix.items()
        if k not in ("include", "exclude") and isinstance(v, list)
    }
    if axes:
        keys = list(axes)
        legs = [
            dict(zip(keys, combo))
            for combo in itertools.product(*(axes[k] for k in keys))
        ]
    else:
        legs = []
    for inc in include:
        matched = False
        for lg in legs:
            if all(lg.get(k) == v for k, v in inc.items() if k in lg):
                lg.update(inc)
                matched = True
        if not matched:
            legs.append(dict(inc))
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for lg in legs:
        hit = any(all(lg.get(k) == v for k, v in ex.items()) for ex in exclude)
        (excluded if hit else kept).append(lg)
    if not axes and not include:
        return [{}], []
    return kept, excluded


def matrix_key(leg: dict[str, Any]) -> str:
    if not leg:
        return ""
    parts = [f"{k}={leg[k]}" for k in sorted(leg) if k != "step_name"]
    return ",".join(parts)


def is_setup_step(name: str | None, command: str) -> bool:
    n = (name or "").strip().lower()
    c = (command or "").strip().lower()
    if c.startswith("uses:actions/checkout") or "actions/checkout@" in c:
        return True
    if c.startswith("uses:actions/setup-") or "actions/setup-python@" in c:
        return True
    if n.startswith("setup python") or n.startswith("pin the regression"):
        return True
    if n == "optional-bootstrap":
        return True
    return False


def step_command(step: dict[str, Any]) -> str:
    if "run" in step:
        return " ".join(str(step["run"]).split())[:600]
    if "uses" in step:
        return f"uses:{step['uses']}"
    return ""


def is_test_step(step: dict[str, Any]) -> bool:
    name = step.get("name") if isinstance(step.get("name"), str) else ""
    cmd = step_command(step) if "run" in step or "uses" in step else str(
        step.get("command") or ""
    )
    if is_setup_step(name, cmd):
        return False
    blob = f"{name}\n{cmd}".lower()
    needles = (
        "pytest",
        "npm test",
        "vitest",
        "gate-tests-coverage",
        "python -m pytest",
        "standalone regression",
        "helper tests",
        "mutation probe",
        "import isolation",
    )
    return any(n in blob for n in needles)


def statically_false(cond: Any) -> bool:
    if cond is False:
        return True
    if cond is True or cond is None:
        return False
    s = str(cond).strip().lower().replace(" ", "")
    return s in {"false", "${{false}}", "0", "never"}


def condition_false(cond: Any, event: str) -> bool:
    if statically_false(cond):
        return True
    if not isinstance(cond, str):
        return False
    compact = " ".join(cond.split())
    m = re.search(
        r"github\.event_name\s*==\s*['\"]([A-Za-z_]+)['\"]",
        compact,
    )
    if m and event and m.group(1) != event:
        return True
    m = re.search(
        r"github\.event_name\s*!=\s*['\"]([A-Za-z_]+)['\"]",
        compact,
    )
    if m and event and m.group(1) == event:
        return True
    return False


def declared_test_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    jobs = workflow.get("jobs") or {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        included, excluded = matrix_included_excluded(job)
        job_if = job.get("if")
        job_coe = bool(job.get("continue-on-error"))
        steps = job.get("steps") or []
        for excluded_flag, legs in ((False, included), (True, excluded)):
            for leg in legs:
                for idx, raw in enumerate(steps):
                    if not isinstance(raw, dict):
                        continue
                    step = {
                        k: expand_templates(v, leg) if isinstance(v, str) else v
                        for k, v in raw.items()
                    }
                    if not is_test_step(step):
                        continue
                    name = step.get("name") or f"step-{idx}"
                    rows.append(
                        {
                            "job_id": job_id,
                            "job_name": expand_templates(job.get("name"), leg)
                            or job_id,
                            "job_if": job_if,
                            "job_continue_on_error": job_coe,
                            "step_index": idx,
                            "name": name,
                            "command": step_command(step),
                            "conditional_on": step.get("if"),
                            "continue_on_error": bool(step.get("continue-on-error")),
                            "matrix": {k: v for k, v in leg.items() if k != "step_name"}
                            if any(leg.values())
                            else {},
                            "matrix_key": matrix_key(leg),
                            "matrix_excluded": excluded_flag,
                        }
                    )
        if not included and not excluded:
            pass
    return rows


def step_id(row: dict[str, Any]) -> str:
    mk = row.get("matrix_key") or ""
    return f"{row['job_id']}::{row['name']}::{mk}"


def load_run(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a mapping")
    return doc


def parse_log_executed(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    names = {m.group(1).strip() for m in GROUP_RE.finditer(text)}
    return names


def log_jobs(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for job in run.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        jid = str(job.get("job_id") or job.get("id") or "")
        mk = str(job.get("matrix_key") or "")
        out[f"{jid}::{mk}"] = job
        if jid and jid not in out:
            out[jid] = job
    return out


def find_log_step(job: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if not job:
        return None
    for st in job.get("steps") or []:
        if isinstance(st, dict) and st.get("name") == name:
            return st
    return None


def prior_hard_failure(job: dict[str, Any] | None, step_index: int) -> bool:
    if not job:
        return False
    for st in job.get("steps") or []:
        if not isinstance(st, dict):
            continue
        idx = st.get("index")
        if isinstance(idx, int) and idx >= step_index:
            continue
        if st.get("conclusion") == "failure" and not st.get("continue_on_error"):
            return True
    return False


def attribute(
    row: dict[str, Any],
    run: dict[str, Any],
    log_names: set[str],
) -> dict[str, Any]:
    event = str(run.get("event") or "push")
    jobs = log_jobs(run)
    mk = row.get("matrix_key") or ""
    job = jobs.get(f"{row['job_id']}::{mk}") or jobs.get(row["job_id"])
    log_step = find_log_step(job, row["name"])
    conclusion = None
    if log_step:
        conclusion = log_step.get("conclusion")
    executed = False
    if conclusion in EXECUTED_CONCLUSIONS:
        executed = True
    elif row["name"] in log_names and conclusion not in {"skipped", "cancelled"}:
        # Text log saw the step run, and the job summary did not mark it skipped.
        if conclusion is None:
            executed = True

    reason = None
    if executed:
        status = "executed"
    elif row.get("matrix_excluded"):
        status = "unexecuted"
        reason = "matrix_exclusion"
    elif (job and job.get("conclusion") == "cancelled") or conclusion == "cancelled":
        status = "unexecuted"
        reason = "cancelled"
    elif prior_hard_failure(job, int(row.get("step_index") or 0)):
        status = "unexecuted"
        reason = "earlier_failure"
    elif condition_false(row.get("conditional_on"), event) or condition_false(
        row.get("job_if"), event
    ):
        status = "unexecuted"
        reason = "conditional_false"
    elif conclusion == "skipped":
        status = "unexecuted"
        hinted = log_step.get("skip_reason") if log_step else None
        reason = hinted if hinted in SKIP_REASONS else "conditional_false"
    elif job is None:
        status = "unexecuted"
        if condition_false(row.get("job_if"), event):
            reason = "conditional_false"
        else:
            reason = "cancelled"
    else:
        status = "unexecuted"
        reason = "conditional_false"

    rec = dict(row)
    rec["status"] = status
    rec["skip_reason"] = reason
    rec["log_conclusion"] = conclusion
    rec["id"] = step_id(row)
    return rec


def analyze(
    workflow_path: Path,
    run_path: Path,
    log_path: Path | None = None,
) -> dict[str, Any]:
    wf = yaml_load(workflow_path)
    run = load_run(run_path)
    log_names = parse_log_executed(log_path) if log_path and log_path.is_file() else set()
    declared = declared_test_steps(wf)
    attributed = [attribute(row, run, log_names) for row in declared]
    executed = [r for r in attributed if r["status"] == "executed"]
    unexecuted = [r for r in attributed if r["status"] == "unexecuted"]
    reasons = sorted({r["skip_reason"] for r in unexecuted if r.get("skip_reason")})
    missing_reason = [r["id"] for r in unexecuted if r.get("skip_reason") not in SKIP_REASONS]
    green = str(run.get("conclusion") or "").lower() == "success"
    naive_all_ran = green  # the false inference the unit exists to refute
    return {
        "workflow": str(workflow_path),
        "run": str(run_path),
        "run_id": run.get("run_id"),
        "event": run.get("event"),
        "workflow_conclusion": run.get("conclusion"),
        "green_badge": green,
        "naive_green_implies_all_executed": naive_all_ran,
        "declared_count": len(declared),
        "executed_count": len(executed),
        "unexecuted_count": len(unexecuted),
        "skip_reasons_present": reasons,
        "unexecuted_missing_reason": missing_reason,
        "executed": [
            {
                "id": r["id"],
                "job": r["job_id"],
                "job_name": r["job_name"],
                "name": r["name"],
                "matrix_key": r.get("matrix_key") or "",
            }
            for r in executed
        ],
        "unexecuted": [
            {
                "id": r["id"],
                "job": r["job_id"],
                "job_name": r["job_name"],
                "name": r["name"],
                "matrix_key": r.get("matrix_key") or "",
                "skip_reason": r["skip_reason"],
            }
            for r in unexecuted
        ],
        "gap_invisible_from_badge": green and len(unexecuted) > 0,
    }


def plant_cannot_run(src: Path, dest: Path) -> Path:
    wf = yaml_load(src)
    jobs = wf.get("jobs") or {}
    job = jobs.get("test-python")
    if not isinstance(job, dict):
        raise ValueError("test-python job missing")
    steps = list(job.get("steps") or [])
    steps.append(
        {
            "name": PLANTED_NAME,
            "if": "${{ false }}",
            "run": "python -m pytest planted_cannot_run.py -q",
        }
    )
    job["steps"] = steps
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_dump_workflow(wf), encoding="utf-8")
    return dest


def detector_control(workflow_path: Path, run_path: Path, tmp: Path) -> dict[str, Any]:
    before = analyze(workflow_path, run_path, HERE / "fixtures/runs/latest-green.log")
    planted = tmp / "planted-cannot-run.yml"
    plant_cannot_run(workflow_path, planted)
    after = analyze(planted, run_path, HERE / "fixtures/runs/latest-green.log")
    before_ids = {r["name"] for r in before["unexecuted"]}
    after_unex = [r for r in after["unexecuted"] if r["name"] == PLANTED_NAME]
    after_decl = after["declared_count"] == before["declared_count"] + 1
    fired = (
        PLANTED_NAME not in before_ids
        and len(after_unex) == 1
        and after_unex[0]["skip_reason"] == "conditional_false"
        and after_decl
    )
    silent_good = PLANTED_NAME not in before_ids
    return {
        "planted_name": PLANTED_NAME,
        "before_declared": before["declared_count"],
        "after_declared": after["declared_count"],
        "before_had_planted": PLANTED_NAME in before_ids
        or any(r["name"] == PLANTED_NAME for r in before["executed"]),
        "after_unexecuted": after_unex,
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent_good,
        "ok": fired and silent_good,
    }


def live_quality_census(repo: Path) -> dict[str, Any]:
    quality = repo / ".github" / "workflows" / "quality.yml"
    if not quality.is_file():
        return {"present": False, "declared_count": 0, "names": [], "by_job": {}}
    rows = declared_test_steps(yaml_load(quality))
    by_job: dict[str, int] = {}
    for row in rows:
        by_job[str(row["job_id"])] = by_job.get(str(row["job_id"]), 0) + 1
    return {
        "present": True,
        "file": ".github/workflows/quality.yml",
        "declared_count": len(rows),
        "by_job": by_job,
        "names": [str(row["name"]) for row in rows],
    }


def bind_test_registry(repo: Path, declared_names: list[str]) -> dict[str, Any]:
    path = repo / "command-center" / "TEST-REGISTRY.json"
    if not path.is_file():
        return {"present": False, "unique_ci_steps": [], "exact_match": [], "unbound": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    ci_steps: list[str] = []
    for suite in doc.get("suites") or []:
        if isinstance(suite, dict) and isinstance(suite.get("ci_step"), str):
            ci_steps.append(suite["ci_step"])
    unique = sorted(set(ci_steps))
    declared_set = set(declared_names)
    exact = [name for name in unique if name in declared_set]
    prefix: list[dict[str, Any]] = []
    unbound: list[str] = []
    for name in unique:
        if name in declared_set:
            continue
        hits = [d for d in declared_names if d.startswith(name)]
        if hits:
            prefix.append({"ci_step": name, "declared": hits})
        else:
            unbound.append(name)
    return {
        "present": True,
        "unique_ci_steps": unique,
        "exact_match": exact,
        "prefix_match": prefix,
        "unbound": unbound,
    }


def live_sources(repo: Path) -> dict[str, Any]:
    wfdir = repo / ".github" / "workflows"
    registry = repo / "command-center" / "TEST-REGISTRY.json"
    inv = repo / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    api = repo / "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
    files = []
    if wfdir.is_dir():
        files = sorted(p.name for p in wfdir.glob("*.y*ml"))
    gh_path = shutil.which("gh")
    live_q = live_quality_census(repo)
    bind = bind_test_registry(repo, live_q.get("names") or [])
    notes = []
    if wfdir.is_dir():
        notes.append(
            f"Live .github/workflows present ({len(files)} files); "
            f"quality.yml declares {live_q.get('declared_count', 0)} test steps."
        )
    else:
        notes.append("No .github/workflows on disk.")
    if gh_path:
        notes.append(f"gh CLI present at {gh_path}.")
    else:
        notes.append(
            "gh CLI absent; the latest green GitHub Actions run was not fetched. "
            "Named probes use the Phase-0 green fixture (60 declared / 28 executed / "
            "32 unexecuted) so skip-reason attribution and the cannot-run control "
            "are live on this box. A green badge is still not evidence any "
            "particular step ran."
        )
    if registry.is_file():
        notes.append(
            "command-center/TEST-REGISTRY.json present; "
            f"exact ci_step matches={len(bind.get('exact_match') or [])} "
            f"prefix={len(bind.get('prefix_match') or [])} "
            f"unbound={bind.get('unbound') or []}."
        )
    else:
        notes.append("command-center/TEST-REGISTRY.json absent.")
    return {
        "workflows_dir": wfdir.is_dir(),
        "workflow_files": files,
        "gh_cli": gh_path is not None,
        "gh_path": gh_path,
        "test_registry": registry.is_file(),
        "aud0041_inventory": inv.is_file(),
        "aud0041_api": api.is_file(),
        "live_quality": live_q,
        "test_registry_bind": bind,
        "notes": " ".join(notes),
    }


def analyze_aud0041_nongreen(repo: Path) -> dict[str, Any] | None:
    inv_p = repo / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    api_p = repo / "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
    if not inv_p.is_file() or not api_p.is_file():
        return None
    inv = json.loads(inv_p.read_text(encoding="utf-8"))
    api = json.loads(api_p.read_text(encoding="utf-8"))
    declared: list[dict[str, Any]] = []
    for wf in inv.get("workflows") or []:
        if wf.get("file") != ".github/workflows/quality.yml":
            continue
        for job in wf.get("jobs") or []:
            for st in job.get("steps") or []:
                fake = {
                    "name": st.get("name"),
                    "run": st.get("command") or "",
                    "command": st.get("command") or "",
                }
                if not is_test_step(fake):
                    continue
                declared.append(
                    {
                        "job": job.get("job_id"),
                        "job_name": job.get("name"),
                        "name": st.get("name") or f"step-{st.get('index')}",
                    }
                )
    quality = None
    for run in api.get("runs") or []:
        if run.get("workflow") == "quality":
            quality = run
            break
    skipped: list[dict[str, Any]] = []
    if quality:
        for job in quality.get("jobs") or []:
            for name in job.get("skipped_steps") or []:
                skipped.append({"job": job.get("name"), "name": name})
    skipped_names = {s["name"] for s in skipped}
    unexecuted = [d for d in declared if d["name"] in skipped_names]
    return {
        "source": "AUD-0041 captured quality run (NOT green)",
        "run_id": quality.get("run_id") if quality else None,
        "declared_test_steps": len(declared),
        "skipped_in_api": len(skipped),
        "declared_also_skipped": len(unexecuted),
        "green": False,
        "note": (
            "This is the captured Actions API snapshot, conclusion mixed "
            "failure/success per job — not the latest green run. It still "
            "shows declared test steps that never executed."
        ),
    }


def render_workflow_yaml() -> str:
    lines = [
        "# Phase-0 CI test-step gap fixture for TST-0332.",
        "# 60 declared test steps, 28 executed on a green run.",
        "name: phase0-ci-test-gap",
        '"on": [push]',
        "jobs:",
        "  test-python:",
        "    name: gate-tests-coverage (python packages)",
        "    runs-on: ubuntu-latest",
        "    steps:",
    ]
    for name in EXECUTED_NAMES:
        lines.append(f"      - name: {q(name)}")
        lines.append("        run: python -m pytest -q")
    for name in CONDITIONAL_NAMES:
        lines.append(f"      - name: {q(name)}")
        lines.append("        if: ${{ false }}")
        lines.append("        run: python -m pytest -q")
    lines += [
        "  test-optional:",
        "    name: gate-tests-coverage (optional packages)",
        "    continue-on-error: true",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - name: optional-bootstrap",
        "        run: exit 1",
    ]
    for name in EARLIER_FAILURE_NAMES:
        lines.append(f"      - name: {q(name)}")
        lines.append("        run: python -m pytest -q")
    lines += [
        "  test-matrix:",
        "    name: gate-tests-coverage (matrix windows)",
        "    runs-on: windows-latest",
        "    strategy:",
        "      matrix:",
        "        include:",
    ]
    for suite, step_name in MATRIX_LEGS:
        lines.append(f"          - suite: {q(suite)}")
        lines.append(f"            step_name: {q(step_name)}")
    lines.append("        exclude:")
    for suite, _step_name in MATRIX_LEGS:
        lines.append(f"          - suite: {q(suite)}")
    lines += [
        "    steps:",
        '      - name: "${{ matrix.step_name }}"',
        "        run: python -m pytest -q",
        "  test-nightly:",
        "    name: gate-tests-coverage (nightly)",
        "    continue-on-error: true",
        "    runs-on: ubuntu-latest",
        "    steps:",
    ]
    for name in CANCELLED_NAMES:
        lines.append(f"      - name: {q(name)}")
        lines.append("        run: python -m pytest -q")
    lines.append("")
    return "\n".join(lines)


def _dump_workflow(wf: dict[str, Any]) -> str:
    # Keep `on` as a string key so PyYAML 1.1 cannot swallow it.
    payload = dict(wf)
    if True in payload and "on" not in payload:
        payload["on"] = payload.pop(True)
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    )
    return text if text.endswith("\n") else text + "\n"


def render_run_log() -> dict[str, Any]:
    py_steps = []
    for i, name in enumerate(EXECUTED_NAMES):
        py_steps.append({"index": i, "name": name, "conclusion": "success"})
    for j, name in enumerate(CONDITIONAL_NAMES, start=len(EXECUTED_NAMES)):
        py_steps.append(
            {
                "index": j,
                "name": name,
                "conclusion": "skipped",
                "skip_reason": "conditional_false",
            }
        )
    opt_steps = [
        {
            "index": 0,
            "name": "optional-bootstrap",
            "conclusion": "failure",
            "continue_on_error": False,
        }
    ]
    for i, name in enumerate(EARLIER_FAILURE_NAMES, start=1):
        opt_steps.append({"index": i, "name": name, "conclusion": "skipped"})
    return {
        "run_id": "fixture-latest-green",
        "event": "push",
        "conclusion": "success",
        "green_badge": True,
        "source": (
            "Fixture reconstructing the Phase-0 baseline (60 declared / 28 executed) "
            "because this worktree has no .github/workflows and no gh CLI. "
            "Job test-optional failed internally with continue-on-error so the "
            "workflow conclusion stays success. Job test-nightly is cancelled by "
            "concurrency and is not a required check."
        ),
        "jobs": [
            {
                "job_id": "test-python",
                "name": "gate-tests-coverage (python packages)",
                "conclusion": "success",
                "matrix_key": "",
                "steps": py_steps,
            },
            {
                "job_id": "test-optional",
                "name": "gate-tests-coverage (optional packages)",
                "conclusion": "failure",
                "continue_on_error": True,
                "matrix_key": "",
                "steps": opt_steps,
            },
            {
                "job_id": "test-matrix",
                "name": "gate-tests-coverage (matrix windows)",
                "conclusion": "skipped",
                "matrix_empty_after_exclude": True,
                "matrix_key": "",
                "steps": [],
                "excluded_legs": [
                    {"suite": suite, "step_name": step_name}
                    for suite, step_name in MATRIX_LEGS
                ],
            },
            {
                "job_id": "test-nightly",
                "name": "gate-tests-coverage (nightly)",
                "conclusion": "cancelled",
                "continue_on_error": True,
                "matrix_key": "",
                "steps": [
                    {"index": i, "name": name, "conclusion": "cancelled"}
                    for i, name in enumerate(CANCELLED_NAMES)
                ],
            },
        ],
    }


def render_text_log() -> str:
    lines = [
        "fixture-latest-green  conclusion=success  (green badge)",
        "A group-Run line is evidence the step started. Skipped/cancelled",
        "steps do not emit a group.",
        "",
    ]
    for name in EXECUTED_NAMES:
        lines.append(f"##[group]Run {name}")
        lines.append("collected 1 item")
        lines.append("1 passed")
        lines.append("##[endgroup]")
        lines.append("")
    return "\n".join(lines)


def _rel(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def write_fixtures(here: Path | None = None) -> dict[str, str]:
    root = (here or HERE).resolve()
    wf = root / "fixtures/workflows/phase0-ci-test-gap.yml"
    run = root / "fixtures/runs/latest-green.json"
    log = root / "fixtures/runs/latest-green.log"
    wf.parent.mkdir(parents=True, exist_ok=True)
    run.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(render_workflow_yaml(), encoding="utf-8")
    run.write_text(
        json.dumps(render_run_log(), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    log.write_text(render_text_log(), encoding="utf-8")
    return {
        "workflow": _rel(wf),
        "run": _rel(run),
        "log": _rel(log),
    }


def phase0_report(repo: Path | None = None) -> dict[str, Any]:
    root = HERE
    write_fixtures(root)
    report = analyze(
        root / "fixtures/workflows/phase0-ci-test-gap.yml",
        root / "fixtures/runs/latest-green.json",
        root / "fixtures/runs/latest-green.log",
    )
    report["live_sources"] = live_sources(repo or REPO)
    report["live_quality"] = report["live_sources"].get("live_quality")
    report["test_registry_bind"] = report["live_sources"].get("test_registry_bind")
    report["captured_nongreen"] = analyze_aud0041_nongreen(repo or REPO)
    report["phase0_expected"] = {
        "declared": 60,
        "executed": 28,
        "unexecuted": 32,
        "skip_reasons": list(SKIP_REASONS),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--write-fixtures":
        paths = write_fixtures()
        print(json.dumps(paths, indent=2, sort_keys=True))
        return 0
    report = phase0_report()
    print(
        json.dumps(
            {
                "declared_count": report["declared_count"],
                "executed_count": report["executed_count"],
                "unexecuted_count": report["unexecuted_count"],
                "skip_reasons_present": report["skip_reasons_present"],
                "gap_invisible_from_badge": report["gap_invisible_from_badge"],
                "unexecuted": report["unexecuted"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
