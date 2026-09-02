#!/usr/bin/env python3
"""Live two-project proof surface for TST-0338."""
from __future__ import annotations

import json
from pathlib import Path

import resolver as R

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures" / "two-project"
ALPHA = FIX / "project-alpha"
BETA = FIX / "project-beta"
UNGATED = FIX / "project-ungated"
MARKER_ALPHA = "TST0338-ALPHA-MARKER"
MARKER_BETA = "TST0338-BETA-MARKER"
MARKER_TRAP = "TST0338-PARENT-TRAP-MARKER"
FIXTURE_PREFIX = "command-center/p2-wave/probes/TST-0338/fixtures/"
FORBIDDEN_AGGREGATE_KEYS = frozenset(
    {
        "overall_coverage",
        "aggregate_coverage",
        "repo_coverage",
        "mean_coverage",
        "combined_coverage",
        "repo_wide_line_coverage_pct",
        "repo_wide_branch_coverage_pct",
    }
)


def fixture_rows() -> dict:
    alpha = R.evaluate_project(ALPHA)
    beta = R.evaluate_project(BETA)
    ungated = R.evaluate_project(UNGATED)
    return {"alpha": alpha, "beta": beta, "ungated": ungated}


def dead_command_control(rows: dict | None = None) -> dict:
    """Prove a hardcoded command from the other project is dead here."""
    rows = rows or fixture_rows()
    alpha = rows["alpha"]
    beta = rows["beta"]
    transplanted = R.run_declared_command(BETA, str(alpha.get("declared_command") or ""))
    out = transplanted.get("output") or ""
    dead = (
        transplanted.get("exit_code") not in (0, None)
        and MARKER_ALPHA not in out
        and MARKER_BETA not in out
    )
    return {
        "alpha_command": alpha.get("declared_command"),
        "beta_command": beta.get("declared_command"),
        "commands_differ": alpha.get("declared_command") != beta.get("declared_command")
        and bool(alpha.get("declared_command"))
        and bool(beta.get("declared_command")),
        "alpha_exit_code": alpha.get("exit_code"),
        "beta_exit_code": beta.get("exit_code"),
        "exit_codes_differ": alpha.get("exit_code") != beta.get("exit_code"),
        "alpha_marker_in_alpha": MARKER_ALPHA in (alpha.get("output_tail") or ""),
        "beta_marker_in_beta": MARKER_BETA in (beta.get("output_tail") or ""),
        "alpha_marker_not_in_beta": MARKER_ALPHA not in (beta.get("output_tail") or ""),
        "beta_marker_not_in_alpha": MARKER_BETA not in (alpha.get("output_tail") or ""),
        "trap_not_in_alpha": MARKER_TRAP not in (alpha.get("output_tail") or ""),
        "trap_not_in_beta": MARKER_TRAP not in (beta.get("output_tail") or ""),
        "transplant_alpha_command_into_beta": {
            "command": alpha.get("declared_command"),
            "cwd": R.relpath(BETA),
            "exit_code": transplanted.get("exit_code"),
            "output_tail": out[-800:],
            "alpha_marker_present": MARKER_ALPHA in out,
            "dead": dead,
        },
        "resolver_has_no_default_command": R.DEFAULT_ENFORCEMENT_COMMAND is None,
    }


def gated_absent_control(rows: dict | None = None) -> dict:
    rows = rows or fixture_rows()
    alpha = rows["alpha"]
    ungated = rows["ungated"]
    with_ok = (
        alpha.get("file_exists") is True
        and alpha.get("enforcement_ran") is True
        and isinstance(alpha.get("exit_code"), int)
        and MARKER_ALPHA in (alpha.get("output_tail") or "")
        and alpha.get("pass") is not True
        and alpha.get("result") != "PASS"
    )
    absent_ok = (
        ungated.get("file_exists") is False
        and ungated.get("result") == R.ABSENT
        and ungated.get("pass") is not True
        and ungated.get("blocked") is not True
        and MARKER_TRAP not in (ungated.get("output_tail") or "")
        and ungated.get("enforcement_ran") is False
        and ungated.get("exit_code") is None
    )
    return {
        "with_file_command_ran": with_ok,
        "without_file_not_checked": absent_ok,
        "parent_trap_not_inherited": absent_ok,
    }


def live_tree_rows() -> list[dict]:
    """Per-project live census. Fixture trees are reported separately.

    Census locates each project's file and declared command without executing
    third-party enforcement (pnpm test:coverage and similar). Command execution
    is the two-project fixture proof, not the repo-wide walk.
    """
    rows = []
    for root in R.discover_project_roots(REPO):
        rel = R.relpath(root)
        if rel.startswith(FIXTURE_PREFIX) or "/fixtures/two-project" in rel:
            continue
        if "/p2-wave/probes/" in rel.replace("\\", "/"):
            continue
        rows.append(R.evaluate_project(root, run_command=False))
    rows.sort(key=lambda r: str(r.get("project") or ""))
    return rows


def proof() -> dict:
    rows = fixture_rows()
    gated = gated_absent_control(rows)
    isol = dead_command_control(rows)
    live = live_tree_rows()
    tests = {
        "project_with_file_runs_declared_command": gated["with_file_command_ran"],
        "project_without_file_emits_not_checked": gated["without_file_not_checked"],
        "wrong_project_command_is_dead": (
            isol["commands_differ"]
            and isol["alpha_marker_in_alpha"]
            and isol["beta_marker_in_beta"]
            and isol["alpha_marker_not_in_beta"]
            and isol["beta_marker_not_in_alpha"]
            and isol["transplant_alpha_command_into_beta"]["dead"]
            and isol["resolver_has_no_default_command"]
        ),
    }
    passed = all(tests.values())
    return {
        "pass": passed,
        "tests": tests,
        "fixture_rows": rows,
        "gated_absent_control": gated,
        "isolation": isol,
        "live_tree": live,
        "test_registry": R.test_registry_status(REPO),
        "ci_workflows": R.find_ci_workflows(REPO),
        "aggregate_coverage_emitted": False,
    }


def artifact_has_aggregate_number(doc: dict) -> bool:
    if any(k in doc for k in FORBIDDEN_AGGREGATE_KEYS):
        return True
    headline = doc.get("headline")
    if isinstance(headline, dict):
        if any(k in headline for k in FORBIDDEN_AGGREGATE_KEYS):
            return True
        cov = headline.get("coverage")
        if isinstance(cov, (int, float)):
            return True
    return False
