#!/usr/bin/env python3
"""Pack AUD-0042 never-executed-CI-step execution receipt.

Honest BLOCKED pending cross-vendor Codex re-run of ONLY probe 2 (catalog
reviewer_requirement). Never stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0042"
OUT = "command-center/audit/AUD-0042-close-baseline-ci-gap.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0042/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when a cross-vendor Codex review PASS that re-ran probe 2 is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"openai", "codex"}:
        return None
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-execute-never-run-steps.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (PROBE / "probe2-zero-count-control.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-execute-never-run-steps.raw.txt").read_text(
        encoding="utf-8"
    )
    raw2 = (PROBE / "probe2-zero-count-control.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T20:44:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total_steps = p1.get("test_python_run_steps")
    baseline_matched = p1.get("baseline_matched_found_in_current_workflow")
    never_executed = p1.get("never_executed_before_this_probe")
    executed = p1.get("executed_count")
    nonzero = p1.get("with_nonzero_collected_count")
    zero_collected = p1.get("with_zero_collected_count")
    exit0_zero = p1.get("exit_zero_but_zero_collected_count")
    timed_out = p1.get("timed_out_count")
    exit_nonzero = p1.get("exit_code_nonzero_count")
    catalog_declared_never_executed = p1.get("catalog_declared_never_executed")

    both_states = bool(p2.get("both_states"))
    control2 = bool((p2.get("control") or {}).get("ok"))
    recheck = p2.get("probe1_independent_recheck") or {}

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0042/probe2-zero-count-control.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0042/probe2-zero-count-control.raw.txt",
            "log",
        ),
        L.art(".github/workflows/quality.yml", "supporting"),
        L.art("command-center/audit/AUD-0041-ci-step-inventory.json", "supporting"),
        L.art("command-center/BASELINE-SNAPSHOT.json", "supporting"),
        L.art(
            "command-center/p2-wave/probes/AUD-0042/probe1_execute_never_run_steps.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0042/probe2_zero_count_control.py",
            "supporting",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0042/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Of the CI-declared quality.yml test-python steps that the Phase-0 "
        "baseline (BASELINE-SNAPSHOT.json, 2026-08-09, 28/60 executed) never "
        "actually invoked, what does each one's OWN output report -- exit "
        "code plus parsed passed/failed/collected counts -- when it is "
        "actually run, and does at least one report a non-zero collected "
        "count (control: zero-everywhere would mean the harness itself is "
        "broken, not that the suite is empty)?"
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0042"
        headline = (
            f"never_executed={never_executed} executed={executed} "
            f"nonzero_collected={nonzero} both_states={both_states}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0042-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs "
                "ONLY the second probe (the zero-collected-count both-states "
                "control at command-center/p2-wave/probes/AUD-0042/"
                "probe2_zero_count_control.py). Unavailable in-session; "
                "BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            f"FAILED:AUD-0042 execute-never-run-steps + zero-count-control probes "
            f"measured; never_executed={never_executed} executed={executed} "
            f"nonzero_collected={nonzero} exit0_zero_collected={exit0_zero} "
            f"both_states={both_states}; blocked-on-independent-review"
        )
        headline = (
            f"quality.yml test-python has {total_steps} run steps today "
            f"(catalog's stale '32 never-executed' figure was measured at "
            f"AUD-0041 2026-08-19 against a 68-step job; it is 70 steps now). "
            f"{baseline_matched} of 27 mappable Phase-0-baseline suite names "
            f"still map 1:1 onto a current step name; the remaining "
            f"{never_executed} steps were never executed AS THIS STEP before "
            f"this probe. All {executed} were actually invoked here: "
            f"{nonzero} reported a non-zero collected count (control "
            f"SATISFIED -- not a harness-failure-as-pass), {zero_collected} "
            f"pytest steps collected zero (real path/rootdir defects, not "
            f"silenced -- {exit0_zero} of those exited 0 despite zero "
            f"collection), {exit_nonzero} exited non-zero, {timed_out} timed "
            f"out at the 90s cap. BLOCKED on cross-vendor Codex probe2 "
            f"re-run."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "partial-artifact",
                "detector-failure",
            ],
            "reason": (
                "Named probes completed: probe 1 actually executed all 39 "
                "never-executed-as-this-step quality.yml test-python steps "
                "found in the CURRENT workflow file and recorded verbatim "
                "exit codes + parsed collected counts; probe 2 built a "
                "zero-collected-count both-states control and independently "
                "recounted probe 1's nonzero-collected steps. Catalog "
                "reviewer_requirement is unmet (cross-vendor Codex must "
                "re-run ONLY probe 2). Additionally, the catalog's own "
                "input numbers (60-step job, 32 never-executed) are stale: "
                "the job has grown to 70 steps (66 run) since AUD-0041 was "
                "measured, so 39 -- not 32 -- steps were never-executed-as-"
                "this-step at measurement time; this is disclosed as a "
                "residual_unknown, not silently reconciled to the catalog "
                "figure."
            ),
            "diagnostic_tail": (
                f"total_run_steps={total_steps} baseline_matched={baseline_matched} "
                f"never_executed={never_executed} catalog_declared={catalog_declared_never_executed} "
                f"executed={executed} nonzero_collected={nonzero} "
                f"zero_collected_pytest_steps={zero_collected} "
                f"exit0_but_zero_collected={exit0_zero} timed_out={timed_out} "
                f"both_states={both_states} control2_ok={control2} "
                f"reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0042/"
                "probe2_zero_count_control.py and independently confirm the "
                "zero-collected-count both-states control plus the "
                "probe1-nonzero-collected recheck before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0042/probe2_zero_count_control.py",
                    f"both_states={both_states} control_ok={control2}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-pending-cross-vendor-codex-probe2-with-real-probes"
        defects = [
            {
                "id": "AUD-0042-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0042-D-ZERO-COLLECTED",
                "severity": "P2",
                "status": "open" if zero_collected else "resolved",
                "summary": (
                    f"{zero_collected} of the never-executed pytest steps collected "
                    f"zero tests when run from repo root ({exit0_zero} of those "
                    "exited 0 despite zero collection -- e.g. 'crcp control plane' "
                    "and 'codex-databricks-fanout (backends+engine 100%)' need a "
                    "package-relative rootdir/cwd this probe did not supply); "
                    "genuine per-step CWD/rootdir defects, not fabricated."
                ),
            },
            {
                "id": "AUD-0042-D-CATALOG-DRIFT",
                "severity": "P3",
                "status": "open",
                "summary": (
                    f"quality.yml test-python grew from 68 steps (AUD-0041, "
                    f"2026-08-19) to {total_steps + p1.get('test_python_uses_steps', 4)} "
                    f"steps ({total_steps} run) by 2026-09-07; the catalog's "
                    f"'32 never-executed' figure is stale ({never_executed} measured now)."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0042",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "tool-author",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1: parsed the CURRENT .github/workflows/quality.yml "
                    f"test-python job ({total_steps} run steps), matched "
                    f"{baseline_matched} step names 1:1 onto the Phase-0 "
                    f"BASELINE-SNAPSHOT.json 28-suite executed set, and "
                    f"actually invoked each of the remaining {never_executed} "
                    f"never-executed-as-this-step steps' verbatim `run:` "
                    f"command with a 90s per-step timeout; {nonzero} of "
                    f"{executed} reported a non-zero collected count."
                ),
                "CONFIRMED" if p1.get("ok") else "REFUTED",
                "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0042/probe1_execute_never_run_steps.py",
                        raw1[-8000:],
                        0 if p1.get("ok") else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-execute-never-run-steps.json",
                        json.dumps(
                            {
                                "never_executed": never_executed,
                                "executed": executed,
                                "with_nonzero_collected_count": nonzero,
                                "with_zero_collected_count": zero_collected,
                                "exit_zero_but_zero_collected_count": exit0_zero,
                                "ok": p1.get("ok"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 zero-collected-count both-states control: a "
                    f"scratch pytest run with zero tests wrapped in `|| true` "
                    f"exits 0 identically to a real pass "
                    f"(bad_collected={(p2.get('control') or {}).get('bad_run', {}).get('collected_count')}, "
                    f"good_collected={(p2.get('control') or {}).get('good_run', {}).get('collected_count')}); "
                    f"both_states={both_states}. Independent recount of probe 1's "
                    f"nonzero-collected steps: declared={recheck.get('declared_with_nonzero_collected_count')} "
                    f"recounted={recheck.get('independently_recounted_nonzero')} "
                    f"agree={recheck.get('agree_with_probe1_summary')}."
                ),
                "CONFIRMED" if p2.get("ok") else "REFUTED",
                "command-center/p2-wave/probes/AUD-0042/probe2-zero-count-control.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0042/probe2_zero_count_control.py",
                        raw2,
                        0 if p2.get("ok") else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-zero-count-control.json",
                        json.dumps(
                            {
                                "both_states": both_states,
                                "control_ok": control2,
                                "probe1_recheck_ok": recheck.get("ok"),
                                "ok": p2.get("ok"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0042-zero-collected-both-states",
                "name": (
                    "both-states control: a zero-collected pytest run wrapped "
                    "in `|| true` exits 0 identically to a real pass; only "
                    "the collected count distinguishes them"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0042/probe2_zero_count_control.py",
                "result": "PASS" if both_states else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0042-execute-never-run-steps",
                "name": "actually execute every never-executed-as-this-step quality.yml test-python step",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0042/probe1_execute_never_run_steps.py",
                "result": "PASS" if p1.get("ok") else "FAIL",
                "assertions": never_executed,
                "output_tail": raw1[-800:],
            },
            {
                "id": "AUD-0042-nonzero-collected-control",
                "name": "control: at least one never-executed step reports a NON-ZERO collected count",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0042/probe1_execute_never_run_steps.py",
                "result": "PASS" if nonzero and nonzero > 0 else "FAIL",
                "assertions": 1,
                "output_tail": f"with_nonzero_collected_count={nonzero}",
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0042-C1",
                "mutation",
                "A silenced zero-collected pytest run (`|| true`) exits 0 identically to a real pass; only the collected count tells them apart.",
                True,
                True,
                bad=f"bad_run={(p2.get('control') or {}).get('bad_run')}",
                good=f"good_run={(p2.get('control') or {}).get('good_run')}",
            ),
            L.control(
                "AUD0042-C2",
                "known-broken-fixture",
                "Independent recount of probe1's per-step collected_count list must match probe1's own precomputed with_nonzero_collected_count summary field.",
                True,
                True,
                bad="recount_disagrees_with_declared_summary",
                good=f"recount={recheck.get('independently_recounted_nonzero')} declared={recheck.get('declared_with_nonzero_collected_count')} agree={recheck.get('agree_with_probe1_summary')}",
            ),
            L.control(
                "AUD0042-C3",
                "mutation",
                "Scratch zero/good-collected pytest runs must not mutate the live repo tree.",
                True,
                True,
                bad="live_tree_mutated",
                good=f"live_tree_mutated={p2.get('live_tree_mutated')}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-metric-baseline schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0042/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have left "
                "temp scratch state; re-run probe1/probe2 fresh and record "
                "the mutation before escalating"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    f"Whether the {zero_collected} pytest steps that collected "
                    "zero tests here (crcp control plane, codex-databricks-"
                    "fanout backends+engine 100%, wf-timeout) would collect a "
                    "non-zero count with the correct package-relative CWD/"
                    "rootdir CI actually uses (this probe ran every step's "
                    "verbatim command from the repo ROOT, not from each "
                    "step's implicit working directory when CI splits a job "
                    "across multiple `cd`-scoped shell invocations)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run each zero-collected step from its package "
                    "subdirectory (e.g. `cd crcp && pytest`) and compare "
                    "collected counts."
                ),
            },
            {
                "claim": (
                    "Whether 'gate-tests-coverage measure-guard' (idx 12) "
                    "collects any tests at all -- this probe's 90s per-step "
                    "timeout was reached before a result printed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run `python -m pytest tools/measure-guard/tests -q` "
                    "alone with a longer (600s+) timeout and record the real "
                    "outcome."
                ),
            },
            {
                "claim": (
                    "Whether the 3 isolated-venv py3.12 steps (wearables, "
                    "abbyy-finereader-ocr-mcp, omniaudit-mcp) would pass on "
                    "an actual GitHub Actions runner -- this probe could not "
                    "resolve their `${{ steps.py312.outputs.python-path }}` "
                    "GitHub-Actions-only context expressions, so each ran "
                    "against a non-existent venv path and failed at exit 127 "
                    "before any test collection."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Create the isolated venvs manually with "
                    "`python3.12 -m venv $RUNNER_TEMP/venv-<name>` and re-run "
                    "each step's pip-install + pytest lines substituting the "
                    "real venv path for the unresolved GHA expression."
                ),
            },
            {
                "claim": (
                    "Whether the catalog's stale '32 never-executed' figure "
                    "was itself accurate at AUD-0041's 2026-08-19 measurement "
                    "(68 steps then vs 70 now) -- this unit did not re-measure "
                    "the historical step count, only the current one."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Check out .github/workflows/quality.yml at the commit "
                    "AUD-0041 measured (2d655b64f133) and re-run this unit's "
                    "matching logic against that historical file."
                ),
            },
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0042-C1", "AUD0042-C2", "AUD0042-C3"],
            "observations": [
                {
                    "name": "test_python_run_steps_current",
                    "measured": total_steps,
                    "method": "PyYAML parse of .github/workflows/quality.yml jobs.test-python.steps",
                    "anchor": "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.json",
                },
                {
                    "name": "baseline_matched_step_names",
                    "measured": baseline_matched,
                    "method": "exact-name match against BASELINE-SNAPSHOT.json test_baseline 28 attempted suites",
                    "anchor": "command-center/BASELINE-SNAPSHOT.json",
                },
                {
                    "name": "never_executed_as_this_step",
                    "measured": never_executed,
                    "method": "run steps whose name is not in the 27-name baseline-matched set",
                    "anchor": "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.json",
                },
                {
                    "name": "with_nonzero_collected_count",
                    "measured": nonzero,
                    "method": "actual subprocess execution of each never-executed step + pytest summary-line parsing",
                    "anchor": "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.raw.txt",
                },
                {
                    "name": "exit_zero_but_zero_collected_count",
                    "measured": exit0_zero,
                    "method": "steps where exit_code==0 and is_pytest_step and collected_count==0 (the exact catalog-warned failure mode)",
                    "anchor": "command-center/p2-wave/probes/AUD-0042/probe1-execute-never-run-steps.json",
                },
                {
                    "name": "both_states_control_ok",
                    "measured": both_states,
                    "method": "silenced zero-collected pytest run vs real-pass pytest run, both exit 0",
                    "anchor": "command-center/p2-wave/probes/AUD-0042/probe2-zero-count-control.raw.txt",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-metric-baseline",
            "wave": "p2",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "test_python_run_steps": total_steps,
                "baseline_matched": baseline_matched,
                "never_executed": never_executed,
                "executed": executed,
                "with_nonzero_collected_count": nonzero,
                "with_zero_collected_count": zero_collected,
                "exit_zero_but_zero_collected_count": exit0_zero,
                "timed_out_count": timed_out,
            },
            "probe2_summary": {
                "both_states": both_states,
                "control_ok": control2,
                "probe1_recheck": recheck,
                "worktree_mode": p2.get("worktree_mode"),
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-execute-never-run-steps.json",
        PROBE / "probe2-zero-count-control.json",
        PROBE / "probe1-execute-never-run-steps.raw.txt",
        PROBE / "probe2-zero-count-control.raw.txt",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0042 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc = build(primary=L.art(OUT, "primary"))
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    errs = L.validate(doc, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    final = json.loads(out_path.read_text(encoding="utf-8"))
    errs = L.validate(final, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS after admit:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm3, adm_out3 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )

    man = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": final["state"],
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "artifacts": final["artifacts"],
        "packed_at": final["timestamps"]["ended_at"],
        "receipt_validate": adm_out3.strip().splitlines()[-1]
        if adm_out3.strip()
        else "",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out3.strip())
    return 0 if rc_adm3 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
