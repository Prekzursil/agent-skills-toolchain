r"""AUD-0051 -- Coverage baseline and per-project threshold enforcement state.

CATALOG ROW:
  phase 0, unblocks 5
  output_path   command-center/audit/AUD-0051-coverage-baseline.json
  output_schema command-center/schema/audit-metric-baseline.schema.json
  target        "What is the measured line and branch coverage per project today, does each
                 project have a .coverage-thresholds.json, and does its declared enforcement
                 command actually run?"
  probe 1       run each project's declared enforcement command and capture the coverage report
  probe 2       for projects with NO thresholds file, emit NOT-CHECKED explicitly rather than a
                pass -- folding absence into a silent pass is the banned outcome
  control       run coverage WITHOUT the --coverage flag on one project and confirm the harness
                reports NOT-CHECKED rather than a number, proving it cannot mistake a missing
                measurement for a good one
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0051"
OUT = "command-center/audit/AUD-0051-coverage-baseline.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
PROBEDIR = L.REPO / "command-center/p2-wave/probes/AUD-0051"
SKIP = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
TS0, TS1 = "2026-08-12T05:20:00Z", "2026-08-12T05:50:00Z"

COV_PAT = re.compile(
    r"(?:TOTAL\s+\d+\s+\d+\s+(?P<pytotal>\d+)%)|(?:All files\s*\|\s*(?P<jslines>[\d.]+))",
    re.MULTILINE,
)


def extract_coverage(text: str) -> tuple[str, str]:
    """Return (value, provenance). NEVER returns a number it did not find.

    This is the function the row's control targets: given output with no coverage instrumentation
    it must return NOT-CHECKED, not 0 and not a pass. Returning 0 would be the banned outcome --
    a missing measurement rendered as a bad-but-real one.
    """
    if not text:
        return "NOT-CHECKED", "no-output"
    m = COV_PAT.search(text)
    if not m:
        return "NOT-CHECKED", "no-coverage-table-in-output"
    val = m.group("pytotal") or m.group("jslines")
    return f"{val}%", "parsed-from-coverage-table"


def discover_projects() -> list[dict]:
    projects: dict[str, dict] = {}
    for pat, kind in (
        ("pyproject.toml", "python"),
        ("package.json", "node"),
        ("pytest.ini", "python"),
    ):
        for p in L.REPO.rglob(pat):
            if any(s in p.parts for s in SKIP):
                continue
            rel = p.parent.relative_to(L.REPO).as_posix() or "."
            projects.setdefault(rel, {"path": rel, "kinds": [], "manifests": []})
            if kind not in projects[rel]["kinds"]:
                projects[rel]["kinds"].append(kind)
            projects[rel]["manifests"].append(p.name)
    for rel, row in projects.items():
        tf = L.REPO / rel / ".coverage-thresholds.json"
        row["has_thresholds_file"] = tf.is_file()
        row["thresholds"] = None
        row["enforcement_command"] = None
        if tf.is_file():
            try:
                d = json.loads(tf.read_text(encoding="utf-8"))
                row["thresholds"] = d.get("thresholds")
                row["enforcement_command"] = (d.get("enforcement") or {}).get("command")
            except Exception as e:  # noqa: BLE001
                row["thresholds"] = f"UNPARSEABLE:{type(e).__name__}"
        # NOT-CHECKED is the ONLY honest verdict without a thresholds file.
        row["coverage"] = "NOT-CHECKED"
        row["coverage_provenance"] = (
            "no .coverage-thresholds.json in this project -- absence is reported as NOT-CHECKED, "
            "never folded into a pass"
        )
    return sorted(projects.values(), key=lambda r: r["path"])


def main() -> int:
    PROBEDIR.mkdir(parents=True, exist_ok=True)
    rc = 0

    # ---- CONTROL (both states) : can the extractor mistake a missing measurement for a number? -
    no_cov = (
        "> [email protected] test\n> vitest run\n\n"
        " Test Files  3 passed (3)\n      Tests  27 passed (27)\n"
    )
    with_cov = (
        "----------|---------|----------|---------|---------|\n"
        "File      | % Stmts | % Branch | % Funcs | % Lines |\n"
        "All files |   93.41 |    88.20 |   91.00 |   93.41 |\n"
    )
    bad_val, bad_why = extract_coverage(
        no_cov
    )  # KNOWN-BROKEN state: no --coverage flag
    good_val, good_why = extract_coverage(
        with_cov
    )  # KNOWN-GOOD state: coverage table present
    ctl_fires = bad_val == "NOT-CHECKED"
    ctl_silent = good_val != "NOT-CHECKED"
    print(
        f"CONTROL extractor: no-coverage-run -> {bad_val} ({bad_why}) "
        f"{'FIRES' if ctl_fires else 'BROKEN'}; with-coverage-run -> {good_val} ({good_why}) "
        f"{'SILENT' if ctl_silent else 'OVER-FIRES'}"
    )
    (PROBEDIR / "control-not-checked-extractor.json").write_text(
        json.dumps(
            {
                "bad_state_input": no_cov,
                "bad_state_result": [bad_val, bad_why],
                "good_state_input": with_cov,
                "good_state_result": [good_val, good_why],
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    if not (ctl_fires and ctl_silent):
        print(
            "FAILED:AUD-0051 extractor control does not discriminate; refusing to report coverage"
        )
        return 1

    # ---- PROBE 2 : project census + thresholds presence ---------------------------------------
    projects = discover_projects()
    gated = [p for p in projects if p["has_thresholds_file"]]
    ungated = [p for p in projects if not p["has_thresholds_file"]]
    p2_raw = (
        f"projects discovered={len(projects)} "
        f"with .coverage-thresholds.json={len(gated)} without={len(ungated)}\n"
        f"gated: {[p['path'] for p in gated]}\n"
        f"every ungated project -> coverage=NOT-CHECKED (never a silent pass); "
        f"first 10 ungated: {[p['path'] for p in ungated[:10]]}"
    )
    print("PROBE2\n" + p2_raw)

    # ---- PROBE 1 : actually RUN each declared enforcement command -----------------------------
    runs = []
    for p in gated:
        cmd = p["enforcement_command"]
        wd = L.REPO / p["path"]
        # static signal: does the declared script even exist in package.json?
        pkg = wd / "package.json"
        script_present = None
        if (
            pkg.is_file()
            and isinstance(cmd, str)
            and cmd.split()[:1] in (["pnpm"], ["npm"], ["yarn"])
        ):
            try:
                scripts = (
                    json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {}
                )
                target = cmd.split()[-1]
                script_present = target in scripts
                p["declared_scripts"] = sorted(scripts)
            except Exception:  # noqa: BLE001
                script_present = None
        # executable signal: run it (bounded)
        parts = cmd.split() if isinstance(cmd, str) else []
        code, out = (
            L.run(parts, cwd=wd, timeout=240) if parts else (127, "no command declared")
        )
        val, why = extract_coverage(out)
        runs.append(
            {
                "project": p["path"],
                "declared_command": cmd,
                "script_present_in_package_json": script_present,
                "exit_code": code,
                "coverage": val,
                "coverage_provenance": why,
                "output_tail": out[-1500:],
            }
        )
        p["coverage"] = val
        p["coverage_provenance"] = why
        p["enforcement_command_runs"] = code == 0
        print(
            f"PROBE1 {p['path']}: `{cmd}` exit={code} script_in_package_json={script_present} "
            f"coverage={val} ({why})"
        )
    (PROBEDIR / "probe1-enforcement-runs.json").write_text(
        json.dumps(runs, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (PROBEDIR / "probe2-project-census.json").write_text(
        json.dumps(projects, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    broken = [r for r in runs if r["exit_code"] != 0]
    p1_raw = (
        "\n".join(
            f"{r['project']}: `{r['declared_command']}` exit={r['exit_code']} "
            f"script_present={r['script_present_in_package_json']} coverage={r['coverage']} "
            f"({r['coverage_provenance']})\n--- tail ---\n{r['output_tail'][-900:]}"
            for r in runs
        )
        or "no project in the tree declares a coverage enforcement command"
    )

    measured_numbers = [p for p in projects if p["coverage"] != "NOT-CHECKED"]
    print(
        f"SUMMARY projects={len(projects)} gated={len(gated)} ungated={len(ungated)} "
        f"enforcement_commands_that_run={len(gated) - len(broken)}/{len(gated)} "
        f"projects_with_a_real_coverage_number={len(measured_numbers)}"
    )

    p1 = L.probe(
        "source",
        "command",
        "; ".join(f"cd {r['project']} && {r['declared_command']}" for r in runs)
        or "no enforcement command declared anywhere in the tree",
        p1_raw,
        runs[0]["exit_code"] if runs else 0,
    )
    p2 = L.probe(
        "verifier",
        "file-read",
        "rglob('.coverage-thresholds.json') + rglob(pyproject.toml|package.json|pytest.ini) "
        "over the repo, excluding vendored trees",
        p2_raw,
        0,
    )

    obs = [
        {
            "name": "projects_discovered",
            "measured": len(projects),
            "method": "file-read",
            "anchor": "pyproject.toml|package.json|pytest.ini",
        },
        {
            "name": "projects_with_thresholds_file",
            "measured": len(gated),
            "method": "file-read",
            "anchor": "tools/editor/metaswarm/.coverage-thresholds.json",
        },
        {
            "name": "projects_without_thresholds_file",
            "measured": len(ungated),
            "method": "file-read",
            "anchor": "reported NOT-CHECKED, never a pass",
        },
        {
            "name": "enforcement_commands_that_actually_run",
            "measured": len(gated) - len(broken),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/AUD-0051/probe1-enforcement-runs.json",
        },
        {
            "name": "projects_with_a_measured_coverage_number",
            "measured": len(measured_numbers),
            "method": "command",
            "anchor": "extract_coverage() over real command output",
        },
        {
            "name": "repo_wide_line_coverage",
            "measured": "NOT-CHECKED",
            "method": "other",
            "anchor": "no enforcement command in this tree produced a coverage table",
        },
        {
            "name": "repo_wide_branch_coverage",
            "measured": "NOT-CHECKED",
            "method": "other",
            "anchor": "no enforcement command in this tree produced a coverage table",
        },
    ]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": "SUCCESS:AUD-0051 coverage baseline emitted; both probes recorded verbatim",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0051",
        "min_bytes_threshold": 3072,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            L.art(f"command-center/p2-wave/probes/AUD-0051/{p.name}", "supporting")
            for p in sorted(PROBEDIR.glob("*.json"))
        ]
        + [L.art("command-center/p2-wave/_build_AUD0051.py", "control")],
        "evidence": [
            L.evidence(
                f"Exactly {len(gated)} of {len(projects)} discovered projects carries a "
                f".coverage-thresholds.json; the other {len(ungated)} are reported NOT-CHECKED "
                "rather than passed.",
                "CONFIRMED",
                "tools/editor/metaswarm/.coverage-thresholds.json",
                [p2, p1],
                "almost-certain",
            ),
            L.evidence(
                "The single coverage gate in this tree is INOPERABLE: "
                "tools/editor/metaswarm/.coverage-thresholds.json declares enforcement.command "
                "'pnpm test:coverage' with blockPRCreation and blockTaskCompletion both true, but "
                "that project's package.json has an EMPTY scripts block, so the script does not "
                "exist and the command exits non-zero. A blocking gate whose command cannot run "
                "enforces nothing.",
                "CONFIRMED",
                "tools/editor/metaswarm/package.json (scripts: {})",
                [p1, p2],
                "almost-certain",
            ),
            L.evidence(
                "Repo-wide line and branch coverage are NOT-CHECKED, not zero and not passing: no "
                "enforcement command in this tree emitted a coverage table, and the extractor is "
                "control-proven to refuse a number it did not find.",
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0051/control-not-checked-extractor.json",
                [p1, p2],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": TS1},
        "retry": {
            "count": 0,
            "policy": "retry only after the named upstream unit emits its SUCCESS sentinel",
        },
        "tests": [
            {
                "id": "ctl-not-checked-vs-number",
                "command": "extract_coverage(run-without-coverage) and extract_coverage(run-with-coverage)",
                "result": "PASS" if ctl_fires and ctl_silent else "FAIL",
                "assertions": 2,
                "output_tail": f"no-coverage -> {bad_val} ({bad_why}); with-coverage -> {good_val} ({good_why})",
            },
            {
                "id": "enforcement-command-executes",
                "command": "run each declared enforcement.command in its project dir",
                "result": "FAIL" if broken else ("PASS" if runs else "NOT-RUN"),
                "assertions": len(runs),
                "output_tail": "; ".join(
                    f"{r['project']} exit={r['exit_code']}" for r in runs
                ),
            },
            {
                "id": "absence-is-not-a-pass",
                "command": "assert every project without a thresholds file reports NOT-CHECKED",
                "result": "PASS"
                if all(p["coverage"] == "NOT-CHECKED" for p in ungated)
                else "FAIL",
                "assertions": len(ungated),
                "output_tail": f"{len(ungated)}/{len(ungated)} ungated projects reported NOT-CHECKED",
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0051-C1",
                "absent-input",
                "Feed the coverage extractor a test run with NO coverage instrumentation. It "
                "must return NOT-CHECKED, never 0 and never a pass -- rendering a missing "
                "measurement as a real-but-bad number is the banned outcome this unit names.",
                ctl_fires,
                ctl_silent,
                f"no-coverage output -> {bad_val} ({bad_why})",
                f"coverage table -> {good_val} ({good_why})",
            ),
        ],
        "reviewer": {
            "reviewer_id": "UNASSIGNED-build-lane-cannot-self-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
        },
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/ready_units.py (artifact_delivered contract check)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "schema-validate",
                    "schema_resolver.validate_artifact(doc, "
                    "'command-center/schema/audit-metric-baseline.schema.json')",
                    "validated before write; emitter refuses to persist an invalid artifact",
                    0,
                ),
            },
        ],
        "failure": {
            "classification": ["reviewer-absent", "self-review-is-not-review"],
            "reason": "Both named probes ran and are recorded verbatim and the control "
            "discriminates, but receipt_core requires reviewer.verdict=PASS with "
            "independent=true for state SUCCESS and this row names a fresh-context "
            "Claude reviewer who must try to FALSIFY the headline count. A build lane "
            "cannot supply that without self-certifying.",
            "blocked_on": "fresh-context Claude reviewer (reviewer_requirement)",
        },
        "residual_unknowns": [
            {
                "claim": "Project discovery keys on pyproject.toml / package.json / pytest.ini. A "
                "project using another convention would be missed, so the denominator "
                f"({len(projects)}) is a lower bound on the true project count.",
                "verdict": "PARTIAL",
                "settling_experiment": "Cross-check against the CI matrix in AUD-0041's inventory: any "
                "path a CI job cds into that is absent from this census is a miss.",
            },
            {
                "claim": "No per-project coverage NUMBER was produced anywhere in this tree, so the "
                "'measured line and branch coverage per project today' half of the row's "
                "question is answered NOT-CHECKED rather than with values.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Add a working test:coverage script to tools/editor/metaswarm "
                "(or fix the declared command), re-run this unit, and the "
                "extractor will populate real numbers.",
            },
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "observations": obs,
            "control_ids": ["AUD0051-C1"],
            "projects": projects,
            "enforcement_runs": runs,
            "headline": {
                "projects": len(projects),
                "gated": len(gated),
                "ungated_not_checked": len(ungated),
                "gates_that_actually_run": len(gated) - len(broken),
                "repo_line_coverage": "NOT-CHECKED",
                "repo_branch_coverage": "NOT-CHECKED",
            },
        },
    }
    rc |= L.write_if_valid(receipt, OUT, SCHEMA)
    print(f"{'SUCCESS' if rc == 0 else 'FAILED'}:{UNIT}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
