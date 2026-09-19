#!/usr/bin/env python3
"""Pack AUD-0043 CI-versus-local invocation parity receipt.

Emits BLOCKED until an independent fresh-context Claude review PASS is on
disk (catalog `reviewer_requirement`); then SUCCESS. Never stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0043"
OUT = "command-center/audit/AUD-0043-ci-local-invocation-parity.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0043/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline count is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-ci-invocation-census.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (PROBE / "probe2-scratch-both-states.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-ci-invocation-census.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-scratch-both-states.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T20:55:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total_steps = p1["gate_tests_coverage_step_count"]
    bare_post_install = p1["bare_pytest_post_install_count"]
    python_m = p1["python_dash_m_pytest_count"]
    p1_ok = bool(p1.get("ok"))
    both_states = bool(p2.get("both_states"))
    p2_ok = bool(p2.get("ok"))

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
            "command-center/p2-wave/probes/AUD-0043/probe1-ci-invocation-census.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/probe2-scratch-both-states.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/probe1-ci-invocation-census.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/probe2-scratch-both-states.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/probe1_ci_invocation_census.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/probe2_scratch_build_both_states.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/fixtures/scratch_pkg_good/pyproject.toml",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0043/fixtures/scratch_pkg_bad/pyproject.toml",
            "control",
        ),
        L.art(".github/workflows/quality.yml", "supporting"),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0043/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Does running the suite the way CI does (installed console script, installed "
        "package) produce the same result as running it the way the baseline did "
        "(python -m pytest against the source tree)?"
    )
    headline = (
        f"CI test-python job: {total_steps} gate-tests-coverage steps; "
        f"{bare_post_install} route tests through an installed pytest console "
        f"script (packaging-sensitive), {python_m} use `python -m pytest` (the "
        "baseline runner, which additionally prepends CWD to sys.path and cannot "
        "see a packaging/import-path regression); scratch both-states control: "
        f"both_states={both_states} (installed-run turned RED, source-tree run "
        "stayed GREEN, for the identical one-module-removed mutation)."
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        defects = [
            {
                "id": "AUD-0043-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0043/independent-review.json"
                ),
            },
            {
                "id": "AUD-0043-D-BASELINE-BLIND-SPOT",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{python_m}/{total_steps} test-python steps invoke tests via "
                    "`python -m pytest`, the exact invocation style quality.yml's own "
                    "inline comments document as blind to a dropped package/module -- "
                    "the scratch both-states control reproduces that blind spot on a "
                    "controlled fixture."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0043"
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not seen "
                "this unit's transcript and must try to FALSIFY the headline count "
                "before PASS, not re-read the artifact. Unavailable in-session; "
                "BLOCKED instead of fake SUCCESS."
            ),
        }
        defects = [
            {
                "id": "AUD-0043-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0043-D-BASELINE-BLIND-SPOT",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{python_m}/{total_steps} test-python steps invoke tests via "
                    "`python -m pytest` (the baseline style); the scratch both-states "
                    "control shows that style stays GREEN even when the packaged "
                    "console-script run turns RED for the same one-module-removed "
                    "mutation."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            f"FAILED:AUD-0043 CI-invocation-census+scratch-both-states probes "
            f"measured gate_steps={total_steps} bare_pytest_post_install="
            f"{bare_post_install} python_dash_m_pytest={python_m} "
            f"both_states={both_states}; blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "green-not-live",
            ],
            "reason": (
                f"Measured gate_tests_coverage_step_count={total_steps} with "
                f"bare_pytest_post_install_count={bare_post_install} and "
                f"python_dash_m_pytest_count={python_m}, and confirmed the "
                f"both-states packaging control (both_states={both_states}), but "
                "reviewer_requirement is unmet."
            ),
            "diagnostic_tail": (
                f"p1_ok={p1_ok} p2_ok={p2_ok} both_states={both_states} "
                f"good_installed_pass={p2['good_installed_pass']} "
                f"bad_installed_pass={p2['bad_installed_pass']} "
                f"bad_source_tree_pass={p2['bad_source_tree_pass']}"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "transcript to try to FALSIFY the headline CI-invocation-census and "
                "both-states counts before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0043/probe2_scratch_build_both_states.py",
                    f"both_states={both_states} bad_installed_pass={p2['bad_installed_pass']}",
                    0 if p2_ok else 1,
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
        anti = "BLOCKED-with-real-probes"

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0043",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-local-p2-loop",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 CI-invocation census: {total_steps} gate-tests-coverage "
                    f"steps in the test-python job; {bare_post_install} use an "
                    f"installed pytest console script post-`pip install` (CI-realistic "
                    f"route), {python_m} use `python -m pytest` (baseline route), "
                    f"{p1['bare_pytest_no_install_seen_count']} bare pytest with no "
                    f"install visible, {p1['other_count']} other. Classifier "
                    "both-states control ok."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0043/probe1-ci-invocation-census.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0043/probe1_ci_invocation_census.py",
                        raw1,
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-ci-invocation-census.json",
                        json.dumps(
                            {
                                "gate_tests_coverage_step_count": total_steps,
                                "bare_pytest_post_install_count": bare_post_install,
                                "python_dash_m_pytest_count": python_m,
                                "ok": p1_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Probe 2 scratch both-states control: a two-top-level-package "
                    "fixture (scratch_pkg + helper_mod) built and pip-installed into a "
                    "fresh virtualenv twice -- once with both modules in "
                    "`[tool.setuptools] packages`, once with helper_mod removed. "
                    f"good_installed_pass={p2['good_installed_pass']} "
                    f"bad_installed_pass={p2['bad_installed_pass']} "
                    f"bad_source_tree_pass={p2['bad_source_tree_pass']} "
                    f"both_states={both_states}: the installed console-script run "
                    "turned RED (ModuleNotFoundError: helper_mod) exactly when "
                    "`python -m pytest` against the identical source tree stayed GREEN."
                ),
                "CONFIRMED" if p2_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0043/probe2-scratch-both-states.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0043/probe2_scratch_build_both_states.py",
                        raw2,
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-scratch-both-states.json",
                        json.dumps(
                            {
                                "both_states": both_states,
                                "fixture_files_match": p2["control"][
                                    "fixture_files_match"
                                ],
                                "ok": p2_ok,
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
                "id": "AUD-0043-both-states-scratch-build",
                "name": (
                    "both-states control: remove one module from the package include "
                    "list in a scratch build and confirm the installed-run turns RED "
                    "while the source-tree run stays GREEN"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0043/probe2_scratch_build_both_states.py",
                "result": "PASS" if both_states else "FAIL",
                "assertions": 4,
                "output_tail": raw2[-800:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0043-C1",
                "mutation",
                (
                    "Dropping helper_mod from the scratch build's package include list "
                    "must turn the installed console-script run RED while the source-"
                    "tree python -m pytest run stays GREEN on the identical files."
                ),
                True,
                True,
                bad=f"bad_installed_pass={p2['bad_installed_pass']}",
                good=f"bad_source_tree_pass={p2['bad_source_tree_pass']}",
            ),
            L.control(
                "AUD0043-C2",
                "known-broken-fixture",
                (
                    "The census classifier must recognise each of the three named "
                    "invocation styles from an engineered run block and fall through "
                    "to 'other' on an irrelevant body."
                ),
                True,
                True,
                bad="misclassified engineered run block",
                good=json.dumps(p1["control"]),
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
                "consumer": "json.loads + audit-detector-control schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0043/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the tree; "
                "restore from the AUD-0092 backup, record the mutation, and escalate"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether any of the 30 python-dash-m-pytest steps' underlying "
                    "package actually SHIPS a broken wheel today (this unit measures "
                    "the invocation-style blind spot on a controlled scratch fixture, "
                    "not a live regression in any of those 30 real packages)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "For each python-dash-m-pytest package with a pyproject.toml, "
                    "build its wheel, pip install it into a fresh venv, and diff the "
                    "installed module tree against the source tree's declared package "
                    "list."
                ),
            }
        ],
        "report": {
            "kind": "audit-detector-control",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0043-C1", "AUD0043-C2"],
            "observations": [
                {
                    "name": "gate_tests_coverage_step_count",
                    "measured": total_steps,
                    "method": "yaml.safe_load of .github/workflows/quality.yml test-python job",
                    "anchor": "command-center/p2-wave/probes/AUD-0043/probe1-ci-invocation-census.json",
                },
                {
                    "name": "bare_pytest_post_install_count",
                    "measured": bare_post_install,
                    "method": "run-block regex: pip install + bare pytest, no python -m",
                    "anchor": "command-center/p2-wave/probes/AUD-0043/probe1-ci-invocation-census.raw.txt",
                },
                {
                    "name": "python_dash_m_pytest_count",
                    "measured": python_m,
                    "method": "run-block regex: python -m pytest present",
                    "anchor": "command-center/p2-wave/probes/AUD-0043/probe1-ci-invocation-census.raw.txt",
                },
                {
                    "name": "both_states_control_ok",
                    "measured": both_states,
                    "method": (
                        "build+install scratch fixture twice (full vs one-module-"
                        "removed packages list) into fresh virtualenvs; run installed "
                        "console script and source-tree python -m pytest for each"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0043/probe2-scratch-both-states.raw.txt",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-detector-control",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "gate_tests_coverage_step_count": total_steps,
                "bare_pytest_post_install_count": bare_post_install,
                "python_dash_m_pytest_count": python_m,
                "ok": p1_ok,
            },
            "probe2_summary": {
                "both_states": both_states,
                "good_installed_pass": p2["good_installed_pass"],
                "bad_installed_pass": p2["bad_installed_pass"],
                "bad_source_tree_pass": p2["bad_source_tree_pass"],
                "ok": p2_ok,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-ci-invocation-census.json",
        PROBE / "probe2-scratch-both-states.json",
        PROBE / "probe1-ci-invocation-census.raw.txt",
        PROBE / "probe2-scratch-both-states.raw.txt",
        PROBE / "fixtures" / "scratch_pkg_good" / "pyproject.toml",
        PROBE / "fixtures" / "scratch_pkg_bad" / "pyproject.toml",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0043 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT

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
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
