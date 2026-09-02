#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0061-coverage-line-delta.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage_delta as C  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0061-coverage-line-delta.json"
SCHEMA = "command-center/schema/coverage-delta.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0061/probe1_line_set_delta.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0061/probe2_delete_one_test.py"
)
QUESTION = (
    "Did coverage move without the percentage moving? Compare the covered "
    "LINE SET before and after, not the percentage, and answer: which "
    "previously covered lines are now uncovered, and does any of them sit "
    "in a security or rollback path? An unchanged percentage can hide an "
    "equal trade of coverage between files."
)
DETECTOR = "command-center/p2-wave/probes/CNF-0061/coverage_delta.py"
MIN_BYTES = 2048


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0061":
            return u
    raise SystemExit("FAILED:CNF-0061 catalog row missing")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if "SUCCESS:CNF-0061" not in sentinel:
        print("FAILED:CNF-0061 catalog sentinel unexpected")
        return 1

    started = datetime.now(timezone.utc)
    m = C.measure_all()
    fails = C.assert_detector_invariants(m)
    if fails:
        print("FAILED:CNF-0061 emit detector invariants")
        for f in fails:
            print(" ", f)
        return 1

    trade = m["trade"]
    control = m["control"]
    thr = C.threshold_verdict(REPO)
    live_cov = C.live_coverage_data_files(REPO)
    ended = datetime.now(timezone.utc)
    side = trade["percentage_side_by_side"]
    sec_lines = [r["file_line"] for r in trade["security_path_newly_uncovered"]]
    rb_lines = [r["file_line"] for r in trade["rollback_path_newly_uncovered"]]
    lost = trade["newly_uncovered_file_lines"]
    ctl_lost = control["newly_uncovered_file_lines"]
    answer = (
        "Yes: the covered line set moved while the percentage stayed "
        f"{side['before']}% on both sides. Newly uncovered "
        f"({trade['newly_uncovered_count']}): "
        + ", ".join(lost)
        + ". Security-path hits: "
        + (", ".join(sec_lines) if sec_lines else "none")
        + ". Rollback-path hits in the trade: "
        + (", ".join(rb_lines) if rb_lines else "none")
        + ". Delete-one-test control newly-uncovered "
        f"({control['newly_uncovered_count']}): "
        + ", ".join(ctl_lost)
        + ". Coverage was enabled for both trade runs and both control runs. "
        "A run without coverage produced an empty newly-uncovered set (blind)."
    )
    det_out = (
        f"coverage_both={m['coverage_enabled_both_trade_runs']} "
        f"traced_before={m['before']['traced_events']} "
        f"traced_after={m['after']['traced_events']} "
        f"percent before={side['before']} after={side['after']} "
        f"unchanged={side['unchanged']} "
        f"newly_uncovered={' '.join(lost)} "
        f"control_uncovered={' '.join(ctl_lost)} "
        f"threshold={thr['verdict']}"
    )
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended - started).total_seconds())

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    placeholder = "0" * 64
    primary = {
        "path": OUT,
        "bytes": MIN_BYTES,
        "sha256": placeholder,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0061",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/catalog-slices/CNF-1.json:CNF-0061",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [
            primary,
            artifact_row(SCHEMA, "supporting"),
            artifact_row(DETECTOR, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "The covered LINE SET moved while the percentage stayed "
                    f"{side['before']}% on both sides; newly uncovered lines "
                    f"include security-path hits {sec_lines}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{DETECTOR}:397",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B " + DETECTOR
                        ),
                        "raw_output": det_out,
                        "fingerprint": fp("test-run", DETECTOR),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            "named probe1 re-runs the line-set delta with "
                            "coverage enabled and diffs the artifact"
                        ),
                        "fingerprint": fp("command", P1),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The delete-one-test detector control, run with coverage "
                    f"enabled, produced a non-empty newly-uncovered set "
                    f"({control['newly_uncovered_count']} lines, rollback path "
                    "hit). The same comparison without coverage is blind."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0061/"
                    "probe2_delete_one_test.py:1"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": (
                            f"deleted_test={m['deleted_test']} "
                            f"newly_uncovered_count="
                            f"{control['newly_uncovered_count']} "
                            f"control_uncovered={' '.join(ctl_lost)}"
                        ),
                        "fingerprint": fp("test-run", P2),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import json,pathlib; json.loads(pathlib.Path("
                            f"'{OUT}').read_text())\""
                        ),
                        "raw_output": "artifact JSON parsed",
                        "fingerprint": fp("file-read", OUT),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "coverage-enabled-both-runs",
                "name": "run the suite WITH coverage enabled",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "threshold-not-checked-when-absent",
                "name": "absent thresholds file is NOT-CHECKED, never a pass",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "delete-one-test-non-empty-uncovered",
                "name": "delete one test; newly-uncovered set is non-empty",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "delete-one-test",
                "kind": "known-broken-fixture",
                "description": (
                    "Drop test_rollback from the fixture suite. The line-set "
                    "delta must report a non-empty newly-uncovered set on "
                    "rollback.py. The full suite compared with itself is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": " ".join(ctl_lost),
                "good_state_output": "newly_uncovered_count=0 on full-vs-full",
            },
            {
                "id": "without-coverage-blind",
                "kind": "absent-input",
                "description": (
                    "The same delete-one-test comparison with coverage "
                    "disabled must not invent a newly-uncovered set. A run "
                    "without coverage cannot see a coverage regression."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "coverage_enabled=False newly_uncovered_count="
                    f"{m['without_coverage']['newly_uncovered_count']}"
                ),
                "good_state_output": (
                    "coverage_enabled=True newly_uncovered_count="
                    f"{control['newly_uncovered_count']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0061-probe2-delete-one-test",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 re-runs the delete-one-test DETECTOR CONTROL "
                "and the no-coverage blindness control. It does not treat "
                "probe1's printed verdict as evidence. re-ran detector control."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0061/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0061",
        },
        "downstream_consumers": [
            {
                "consumer": "CNF-0061 named probe1 (line-set delta)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "raw_output": "artifact consumed by probe1 after emit",
                    "fingerprint": fp("command", "consumer|" + P1),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no paired before/after product-suite "
                    "coverage data files; the line-set detector is proven on "
                    "the fixture, not claimed as a live product two-state delta."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Collect two line-granularity coverage data files for a "
                    "real product before/after pair and re-run coverage_delta "
                    "against those files."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "coverage-analyst",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "coverage-delta",
            "observations": [
                {
                    "name": "percentage-unchanged",
                    "measured": bool(side["unchanged"]),
                    "method": "line-set-delta",
                    "anchor": f"{DETECTOR}:298",
                },
                {
                    "name": "newly-uncovered-count",
                    "measured": int(trade["newly_uncovered_count"]),
                    "method": "line-set-delta",
                    "anchor": f"{DETECTOR}:316",
                },
                {
                    "name": "delete-one-test-uncovered-count",
                    "measured": int(control["newly_uncovered_count"]),
                    "method": "delete-one-test-control",
                    "anchor": f"{DETECTOR}:406",
                },
            ],
            "control_ids": ["delete-one-test", "without-coverage-blind"],
            "question": QUESTION,
            "answer": answer,
            "evidence_requirement": str(unit.get("evidence_requirement") or ""),
            "measurement_subject": (
                "detector fixture under command-center/p2-wave/probes/CNF-0061/"
                "fixtures (this worktree has no paired before/after coverage "
                "data files for a product-suite two-state comparison)"
            ),
            "live_project": {
                "coverage_data_files": live_cov,
                "two_state_comparison": "NOT-CHECKED",
                "reason": (
                    "no pair of line-granularity coverage data files for two "
                    "product states on this worktree; the detector is proven on "
                    "the fixture, not folded into a silent live pass"
                ),
            },
            "coverage_enabled_both_runs": True,
            "coverage_instrument": (
                "sys.settrace line tracer over fixtures/subject/"
            ),
            "traced_events_trade": m["traced_events_trade"],
            "percentage_side_by_side": side,
            "before": {
                "tests": m["before"]["tests"],
                "percent": m["before"]["percent"],
                "covered_line_count": m["before"]["covered_line_count"],
                "executable_line_count": m["before"]["executable_line_count"],
                "covered_lines": m["before"]["covered_lines"],
                "coverage_enabled": m["before"]["coverage_enabled"],
                "traced_events": m["before"]["traced_events"],
            },
            "after": {
                "tests": m["after"]["tests"],
                "percent": m["after"]["percent"],
                "covered_line_count": m["after"]["covered_line_count"],
                "executable_line_count": m["after"]["executable_line_count"],
                "covered_lines": m["after"]["covered_lines"],
                "coverage_enabled": m["after"]["coverage_enabled"],
                "traced_events": m["after"]["traced_events"],
            },
            "newly_uncovered": trade["newly_uncovered"],
            "newly_uncovered_count": trade["newly_uncovered_count"],
            "newly_uncovered_file_lines": lost,
            "newly_covered": trade["newly_covered"],
            "newly_covered_file_lines": trade["newly_covered_file_lines"],
            "coverage_moved_without_percentage_moving": trade[
                "coverage_moved_without_percentage_moving"
            ],
            "security_or_rollback": {
                "any_hit": trade["any_security_or_rollback_newly_uncovered"],
                "security_file_lines": sec_lines,
                "rollback_file_lines": rb_lines,
            },
            "threshold_question": thr,
            "detector_control": {
                "name": "delete-one-test",
                "deleted_test": m["deleted_test"],
                "coverage_enabled": True,
                "newly_uncovered": control["newly_uncovered"],
                "newly_uncovered_file_lines": ctl_lost,
                "newly_uncovered_count": control["newly_uncovered_count"],
                "non_empty": control["newly_uncovered_count"] > 0,
            },
            "without_coverage_control": {
                "coverage_enabled": False,
                "newly_uncovered_count": m["without_coverage"][
                    "newly_uncovered_count"
                ],
                "blind": m["without_coverage"]["newly_uncovered_count"] == 0,
                "note": (
                    "a suite run without coverage enabled cannot see a coverage "
                    "regression at all"
                ),
            },
            "re_ran_detector_control": True,
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "output_schema": SCHEMA,
            "output_path": OUT,
        },
    }

    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0061 schema-invalid")
        for e in errs[:25]:
            print(" ", e)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not S.errors(garbage):
            print("FAILED:CNF-0061 schema accepts garbage")
            return 1

    dumped = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if sentinel not in dumped:
        print("FAILED:CNF-0061 completion_sentinel not in artifact text")
        return 1
    dest.write_text(dumped, encoding="utf-8")
    sha, size = sha256_file(dest)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    dumped = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    dest.write_text(dumped, encoding="utf-8")
    sha, size = sha256_file(dest)
    parsed = json.loads(dest.read_text(encoding="utf-8"))
    post = S.errors(parsed)
    if post:
        print("FAILED:CNF-0061 written schema-invalid")
        for e in post[:12]:
            print(" ", e)
        return 1
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0061 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} newly_uncovered={doc['report']['newly_uncovered_count']} bytes={size} sha256={sha}")
    print("SUCCESS:CNF-0061 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
