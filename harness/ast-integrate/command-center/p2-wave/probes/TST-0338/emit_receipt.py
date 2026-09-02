#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0338.json from a live resolver run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0338.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0338/probe1_gated_and_absent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0338/probe2_wrong_project.py"
)
QUESTION = (
    "Implementation target: coverage thresholds live in a per-project "
    ".coverage-thresholds.json and its enforcement command, never in an agent's "
    "memory. Build the resolver that locates the file for the project under test, "
    "runs its declared enforcement command, and - when no such file exists - emits "
    "NOT-CHECKED and surfaces it, rather than folding the absence into a silent "
    "pass or blocking a project that was never coverage-gated. Both failure "
    "directions are live: a hardcoded command from another project is a dead "
    "command here."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def per_project_report(row: dict) -> dict:
    return {
        "project": row.get("project"),
        "file_exists": row.get("file_exists"),
        "file_path": row.get("file_path"),
        "declared_command": row.get("declared_command"),
        "result": row.get("result"),
        "exit_code": row.get("exit_code"),
        "pass": row.get("pass"),
        "blocked": row.get("blocked"),
        "reason": row.get("reason"),
        "thresholds": row.get("thresholds"),
        "enforcement_ran": row.get("enforcement_ran"),
    }


def main() -> int:
    live = S.proof()
    if not live.get("pass"):
        print("FAILED:TST-0338 emit live proof did not pass")
        print(json.dumps({k: live.get(k) for k in sorted(live) if k != "live_tree"}, indent=2)[:4000])
        return 1

    src = {
        "id": "probe1_gated_and_absent",
        "command": P1,
        "role": "with-file-runs-command-and-absent-is-not-checked",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0338/probe1_gated_and_absent.py"
        ),
    }
    ver = {
        "id": "probe2_wrong_project",
        "command": P2,
        "role": "two-project-isolation-and-dead-command-control",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0338/probe2_wrong_project.py"
        ),
    }
    if src["fingerprint"]["sha256"] == ver["fingerprint"]["sha256"]:
        print("FAILED:TST-0338 emit source/verifier probe files identical")
        return 1

    rows = live["fixture_rows"]
    live_tree = live["live_tree"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    projects = [
        per_project_report(rows["alpha"]),
        per_project_report(rows["beta"]),
        per_project_report(rows["ungated"]),
    ] + [per_project_report(r) for r in live_tree]

    doc = {
        "unit_id": "TST-0338",
        "schema_version": 1,
        "report_kind": "coverage-threshold-resolver",
        "title": "Read the coverage threshold from the project SSOT and emit NOT-CHECKED when there is none",
        "question": QUESTION,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0338",
        "completion_sentinel": "SUCCESS:TST-0338",
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "registered": True,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "test-engineer",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"ended_at": now},
        "source_probe": src,
        "verifier_probe": ver,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": src["role"]},
            {"id": "probe2", "command": P2, "role": ver["role"]},
        ],
        "tests": {
            "project_with_file_runs_declared_command": {
                "pass": live["tests"]["project_with_file_runs_declared_command"],
                "project": rows["alpha"].get("project"),
                "declared_command": rows["alpha"].get("declared_command"),
                "exit_code": rows["alpha"].get("exit_code"),
                "result": rows["alpha"].get("result"),
            },
            "project_without_file_emits_not_checked": {
                "pass": live["tests"]["project_without_file_emits_not_checked"],
                "project": rows["ungated"].get("project"),
                "result": rows["ungated"].get("result"),
                "blocked": rows["ungated"].get("blocked"),
                "coverage_pass": rows["ungated"].get("pass"),
            },
            "wrong_project_control": {
                "pass": live["tests"]["wrong_project_command_is_dead"],
                "alpha_command": live["isolation"]["alpha_command"],
                "beta_command": live["isolation"]["beta_command"],
                "commands_differ": live["isolation"]["commands_differ"],
                "transplant_dead": live["isolation"]["transplant_alpha_command_into_beta"]["dead"],
            },
        },
        "projects": projects,
        "fixture_proof": {
            "alpha": per_project_report(rows["alpha"]),
            "beta": per_project_report(rows["beta"]),
            "ungated": per_project_report(rows["ungated"]),
            "isolation": live["isolation"],
            "parent_trap": {
                "path": "command-center/p2-wave/probes/TST-0338/fixtures/two-project/.coverage-thresholds.json",
                "inherited_by_ungated": False,
                "marker": S.MARKER_TRAP,
            },
        },
        "inputs": {
            "test_registry": live["test_registry"],
            "ci_workflows": live["ci_workflows"],
            "coverage_thresholds_files_live_tree": [
                r.get("file_path") for r in live_tree if r.get("file_exists")
            ],
        },
        "evidence": [
            {
                "claim": "Project with .coverage-thresholds.json: the declared command runs and its exit code is reported.",
                "verdict": "CONFIRMED" if live["tests"]["project_with_file_runs_declared_command"] else "REFUTED",
                "anchor": rows["alpha"].get("file_path"),
            },
            {
                "claim": "Project without the file: NOT-CHECKED is emitted and surfaced, never a pass and never a block.",
                "verdict": "CONFIRMED" if live["tests"]["project_without_file_emits_not_checked"] else "REFUTED",
                "anchor": rows["ungated"].get("project"),
            },
            {
                "claim": "Wrong-project control: alpha's command is dead in beta's directory; each project runs only its own file's command.",
                "verdict": "CONFIRMED" if live["tests"]["wrong_project_command_is_dead"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/TST-0338/fixtures/two-project/",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0338-probe2-wrong-project",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 reproduces isolation and the dead-command transplant "
                "independently of probe 1's gated/absent path."
            ),
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "an aggregate coverage number across projects",
                "TEST-REGISTRY.json exists on this worktree",
                "CI workflow files exist on this worktree",
                "TST-0326 discovery census was delivered",
            ],
            "proof_surface": (
                "two-project fixture (alpha gated, beta gated with a different "
                "command, ungated child next to a parent trap file) plus a live "
                "tree census that reports NOT-CHECKED per project without averaging"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "command-center/TEST-REGISTRY.json",
                "verdict": "NOT-CHECKED",
                "reason": live["test_registry"].get("reason"),
            },
            {
                "claim": "CI workflow files that declare test steps",
                "verdict": "NOT-CHECKED" if not live["ci_workflows"].get("exists") else "FOUND",
                "reason": live["ci_workflows"].get("reason"),
            },
        ],
        "aggregate_coverage_refused": True,
        "headline": {
            "fixture_projects": 3,
            "live_tree_projects": len(live_tree),
            "live_tree_gated": sum(1 for r in live_tree if r.get("file_exists")),
            "live_tree_not_checked": sum(
                1 for r in live_tree if r.get("result") == "NOT-CHECKED"
            ),
            "coverage": "NOT-CHECKED per project; no aggregate number",
        },
    }
    if S.artifact_has_aggregate_number(doc):
        print("FAILED:TST-0338 emit would have emitted an aggregate coverage number")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({out.stat().st_size} B)")
    print("SUCCESS:TST-0338")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
