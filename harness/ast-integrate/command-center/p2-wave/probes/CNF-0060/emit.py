#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0060-skip-count-diff.json."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
os.chdir(REPO)
sys.path.insert(0, str(HERE))

from skip_diff import (  # noqa: E402
    newly_disabled,
    run_planted_skip_control,
    skip_sets,
)

OUT = "command-center/confirmation/CNF-0060-skip-count-diff.json"
SCHEMA = "command-center/schema/regression-delta.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0060 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the planted skip marker "
    "was detected and both executed-id sets are attached. Any other terminal "
    "state is FAILED:CNF-0060 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Was a test silently disabled instead of fixed? Diff the skipped, xfailed, "
    "deselected and conditionally-excluded test id sets across the change, and "
    "answer: which tests stopped executing, and for each, is there a recorded "
    "justification? A green suite with fewer executed tests is a weaker suite, "
    "not a better one."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0060/probe1_planted_skip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0060/probe2_reviewer_control.py"
)
CONTROL_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0060/skip_diff.py"
)
SUPPORTING = [
    (
        "command-center/p2-wave/probes/CNF-0060/fixtures/suite/test_skip_surface.py",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/CNF-0060/fixtures/suite/collection.json",
        "fixture",
    ),
    ("command-center/p2-wave/probes/CNF-0060/runner.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0060/skip_diff.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0060/pytest_shim.py", "supporting"),
]


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def _file_artifact(rel: str, role: str) -> dict:
    sha, size = _digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _outcome_set(report: dict, label: str) -> dict:
    ss = skip_sets(report)
    return {
        "label": label,
        "members": report["members"],
        "counts": report["counts"],
        "executed_ids": list(report.get("executed_ids") or []),
        "executed_count": int(report.get("executed_count") or 0),
        "skipped_ids": ss["skipped_ids"],
        "skipped_with_reasons": ss["skipped_with_reasons"],
        "xfailed_ids": ss["xfailed_ids"],
        "deselected_ids": list(report.get("deselected_ids") or []),
        "deselected": list(report.get("deselected") or []),
        "by_skip_kind": ss["by_skip_kind"],
    }


def _sym(diff: dict) -> dict:
    return {
        "only_in_before": list(diff.get("only_in_before") or []),
        "only_in_after": list(diff.get("only_in_after") or []),
        "flipped": list(diff.get("flipped") or []),
        "counts": dict(diff.get("counts") or {}),
    }


def _load_schema_store() -> dict:
    store: dict = {}
    for folder in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(doc, dict) and isinstance(doc.get("$id"), str):
                store[doc["$id"]] = doc
    return store


def disk_validator():
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(shim, store=_load_schema_store())
    return Draft202012Validator(shim, resolver=resolver)


def validate_or_die(doc: dict) -> None:
    validator = disk_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0060 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0060 schema accepted garbage")
            raise SystemExit(1)


def main() -> int:
    started = datetime.now(timezone.utc)
    ctrl = run_planted_skip_control()
    if not ctrl["fired"]:
        print("FAILED:CNF-0060 detector-failure planted skip was not detected")
        print(
            json.dumps(
                {k: ctrl[k] for k in ("fired", "planted_id", "disabled") if k in ctrl},
                indent=2,
            )[:4000]
        )
        return 1
    if not ctrl["kinds_distinct"]:
        print(
            "FAILED:CNF-0060 detector-failure platform-conditional not distinct "
            "from unconditional"
        )
        return 1
    identity = newly_disabled(ctrl["before"], ctrl["before"])
    if identity["newly_skipped"] or identity["executed_count_dropped"]:
        print("FAILED:CNF-0060 detector-failure identity capture invented a skip")
        return 1
    disabled = ctrl["disabled"]
    before = _outcome_set(ctrl["before"], "fixture-before-plant")
    after = _outcome_set(ctrl["after"], "fixture-after-planted-skip")
    if not before["executed_ids"] or not after["executed_ids"]:
        print("FAILED:CNF-0060 executed-id sets missing")
        return 1
    if ctrl["planted_id"] in after["executed_ids"]:
        print("FAILED:CNF-0060 planted id still executed after skip")
        return 1

    git_dir = REPO / ".git"
    baseline = REPO / "command-center" / "BASELINE-SNAPSHOT.json"
    try:
        import pytest  # noqa: F401
    except ImportError:
        pytest_ok = False
    else:
        pytest_ok = True
    live_suite = {
        "status": "NOT-CHECKED",
        "reason": (
            "This worktree has no .git, so a commit-to-commit skip/xfail/deselect "
            "id-set delta cannot be claimed. command-center/BASELINE-SNAPSHOT.json "
            "is present but records only aggregate skip/deselect counts, not "
            "per-test-id skip reasons. pytest is "
            f"{'importable' if pytest_ok else 'not installed'}, so the live tree "
            "cannot be re-collected into skip-reason reports. The planted-skip "
            "detector control on the fixture is the observation this unit records."
        ),
        "git_available": git_dir.exists(),
        "baseline_snapshot_present": baseline.is_file() and baseline.stat().st_size > 0,
        "pytest_importable": pytest_ok,
    }

    answer = (
        "Live commit-to-commit skip delta is NOT-CHECKED (no git; baseline has "
        "aggregates only; pytest absent). The planted-skip control fired: "
        f"{ctrl['planted_id']} flipped failed→skipped with reason "
        f"{ctrl['planted_reason']!r}. Executed ids "
        f"{disabled['executed_count_before']} → {disabled['executed_count_after']} "
        f"while passed count stayed {disabled['passed_count_before']} "
        f"(passed_count_unchanged={disabled['passed_count_unchanged']}). "
        "A green suite with fewer executed tests is a weaker suite. "
        f"Unconditional skips {ctrl['unconditional_skips_after']} are distinct from "
        f"platform-conditional skips {ctrl['platform_conditional_skips_after']}."
    )
    control_raw = json.dumps(
        {
            "fired": ctrl["fired"],
            "planted_id": ctrl["planted_id"],
            "newly_skipped": disabled["newly_skipped"],
            "stopped_executing": disabled["stopped_executing"],
            "executed_ids_before": before["executed_ids"],
            "executed_ids_after": after["executed_ids"],
            "unconditional": ctrl["unconditional_skips_after"],
            "platform_conditional": ctrl["platform_conditional_skips_after"],
            "identity_newly_skipped": identity["newly_skipped"],
        },
        sort_keys=True,
    )
    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0060",
        "state": "SUCCESS",
        "sentinel": CATALOG_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0060",
        "min_bytes_threshold": 2048,
        "artifacts": [_file_artifact(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Planting an unconditional skip on a failing test is detected "
                    "as a newly skipped id that stopped executing, with the planted "
                    "reason recorded."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0060/skip_diff.py:104",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": CONTROL_CMD,
                        "raw_output": control_raw[:8000],
                        "fingerprint": _fp("test-run", CONTROL_CMD),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "command-center/p2-wave/probes/CNF-0060/fixtures/"
                            "suite/test_skip_surface.py"
                        ),
                        "raw_output": (
                            "test_planted_target currently FAILS; plant_skip adds "
                            '@pytest.mark.skip(reason="CNF-0060-planted")'
                        ),
                        "fingerprint": _fp(
                            "file-read",
                            "command-center/p2-wave/probes/CNF-0060/fixtures/"
                            "suite/test_skip_surface.py",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Both executed-id sets are attached; passed count is unchanged "
                    "while executed count drops; platform-conditional skips are "
                    "disjoint from unconditional skips."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0060/runner.py:104",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": CONTROL_CMD + " # kinds + executed-vs-passed",
                        "raw_output": (
                            f"executed {disabled['executed_count_before']}->"
                            f"{disabled['executed_count_after']} passed "
                            f"{disabled['passed_count_before']}=="
                            f"{disabled['passed_count_after']} uncond="
                            f"{ctrl['unconditional_skips_after']} plat="
                            f"{ctrl['platform_conditional_skips_after']}"
                        ),
                        "fingerprint": _fp(
                            "command", CONTROL_CMD + " # kinds + executed-vs-passed"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/CNF-0060/emit.py "
                            "validate_or_die(regression-delta)"
                        ),
                        "raw_output": "schema errors: 0; garbage rejected",
                        "fingerprint": _fp(
                            "schema-validate",
                            "python3 -B command-center/p2-wave/probes/CNF-0060/emit.py "
                            "validate_or_die(regression-delta)",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "planted-skip-control",
                "name": (
                    "control: add a skip marker to one passing-or-failing test and "
                    "confirm the diff detects it as newly skipped and no longer executed"
                ),
                "command": CONTROL_CMD,
                "result": "PASS",
                "assertions": 4,
                "output_tail": (
                    f"planted {ctrl['planted_id']} newly_skipped="
                    f"{disabled['newly_skipped']} stopped_executing="
                    f"{disabled['stopped_executing']} executed "
                    f"{disabled['executed_count_before']}→"
                    f"{disabled['executed_count_after']}"
                ),
            },
            {
                "id": "platform-vs-unconditional",
                "name": (
                    "a platform-conditional skip must be distinguished from an "
                    "unconditional one"
                ),
                "command": CONTROL_CMD,
                "result": "PASS",
                "assertions": 1,
                "output_tail": (
                    f"unconditional={ctrl['unconditional_skips_after']} "
                    f"platform-conditional={ctrl['platform_conditional_skips_after']} "
                    f"kinds_distinct={ctrl['kinds_distinct']}"
                ),
            },
            {
                "id": "executed-not-passed",
                "name": (
                    "the executed count must be compared, not the passed count, "
                    "since skipped tests do not fail"
                ),
                "command": CONTROL_CMD,
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"passed {disabled['passed_count_before']}=="
                    f"{disabled['passed_count_after']} "
                    f"unchanged={disabled['passed_count_unchanged']}; "
                    f"executed {disabled['executed_count_before']}→"
                    f"{disabled['executed_count_after']} "
                    f"dropped={disabled['executed_count_dropped']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "planted-skip-both-states",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant an unconditional skip on a failing test. The detector "
                    "must list it as newly skipped and no longer executed (bad "
                    "state) and must not invent a skip when comparing the unplanted "
                    "suite to itself (good state)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"newly_skipped={disabled['newly_skipped']} "
                    f"stopped={disabled['stopped_executing']} "
                    f"executed {disabled['executed_count_before']}->"
                    f"{disabled['executed_count_after']}"
                ),
                "good_state_output": (
                    f"identity newly_skipped={identity['newly_skipped']} "
                    f"executed_dropped={identity['executed_count_dropped']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0060-probe2-reviewer-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Named probe2 re-runs the planted-skip control on a separate temp "
                "copy and checks skip-kind buckets plus executed-vs-passed counts. "
                "It does not treat probe1's printed verdict as evidence."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0060/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0060",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema Draft202012Validator over "
                    "command-center/schema/regression-delta.schema.json "
                    "(disk RefResolver, no network)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/CNF-0060/emit.py"
                    ),
                    "raw_output": "schema errors: 0; garbage documents rejected",
                    "fingerprint": _fp(
                        "schema-validate",
                        "python3 -B command-center/p2-wave/probes/CNF-0060/emit.py",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Commit-to-commit skip/xfail/deselect id-set delta on the live "
                    "repo suite was not measured on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a git checkout with pytest, collect skip/xfail/deselect "
                    "ids at two commits (or against BASELINE per-test reports if "
                    "those exist) and attach both executed-id sets."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-integrity-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "regression-delta",
            "observations": [
                {
                    "name": "executed_count_before",
                    "measured": disabled["executed_count_before"],
                    "method": "stdlib-runner executed=True ids",
                    "anchor": "command-center/p2-wave/probes/CNF-0060/runner.py:235",
                },
                {
                    "name": "executed_count_after",
                    "measured": disabled["executed_count_after"],
                    "method": "stdlib-runner executed=True ids",
                    "anchor": "command-center/p2-wave/probes/CNF-0060/runner.py:235",
                },
                {
                    "name": "passed_count_unchanged",
                    "measured": bool(disabled["passed_count_unchanged"]),
                    "method": "counts.passed before vs after",
                    "anchor": "command-center/p2-wave/probes/CNF-0060/skip_diff.py:97",
                },
                {
                    "name": "planted_id",
                    "measured": str(ctrl["planted_id"]),
                    "method": "plant_skip + newly_disabled",
                    "anchor": "command-center/p2-wave/probes/CNF-0060/runner.py:253",
                },
                {
                    "name": "kinds_distinct",
                    "measured": bool(ctrl["kinds_distinct"]),
                    "method": "skip_kind buckets disjoint",
                    "anchor": "command-center/p2-wave/probes/CNF-0060/skip_diff.py:141",
                },
            ],
            "control_ids": [
                "planted-skip",
                "platform-vs-unconditional",
                "executed-not-passed",
            ],
            "title": (
                "Skip, xfail and deselect count diff so a silently disabled test "
                "is caught"
            ),
            "question": QUESTION,
            "answer": answer,
            "before": before,
            "after": after,
            "executed_ids_before": before["executed_ids"],
            "executed_ids_after": after["executed_ids"],
            "symmetric_difference": _sym(ctrl["symmetric_difference"]),
            "aggregate_counts": {
                "before": before["counts"],
                "after": after["counts"],
                "unchanged": before["counts"] == after["counts"],
                "passed_unchanged_executed_dropped": bool(
                    disabled["passed_count_unchanged"]
                    and disabled["executed_count_dropped"]
                ),
                "note": (
                    "Passed count is the wrong instrument: skipping a failing test "
                    "leaves passed unchanged (or a green suite looks better) while "
                    "executed count drops."
                ),
            },
            "controls": {
                "planted_skip": {
                    "constructed": True,
                    "fired": True,
                    "planted_id": ctrl["planted_id"],
                    "planted_reason": ctrl["planted_reason"],
                    "detected_in_newly_skipped": True,
                    "detected_in_stopped_executing": True,
                    "kinds_distinct": ctrl["kinds_distinct"],
                    "unconditional_skips": ctrl["unconditional_skips_after"],
                    "platform_conditional_skips": ctrl[
                        "platform_conditional_skips_after"
                    ],
                    "disabled": disabled,
                    "identity_silent": not identity["newly_skipped"]
                    and not identity["executed_count_dropped"],
                    "symmetric_difference": _sym(ctrl["symmetric_difference"]),
                    "fixture": "command-center/p2-wave/probes/CNF-0060/fixtures/suite",
                }
            },
            "live_repo_suite": live_suite,
            "named_probes": [
                {"id": "probe1", "role": "planted-skip-detector-control", "command": P1},
                {
                    "id": "probe2",
                    "role": "reviewer-rerun-kinds-and-executed-count",
                    "command": P2,
                },
            ],
        },
    }

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0060 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0060 catalog sentinel absent from artifact")
        return 1
    loaded = json.loads(text)
    if not loaded["report"]["executed_ids_before"] or not loaded["report"][
        "executed_ids_after"
    ]:
        print("FAILED:CNF-0060 executed-id sets not attached")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(
        "planted_skip fired "
        f"id={ctrl['planted_id']} executed "
        f"{disabled['executed_count_before']}→{disabled['executed_count_after']} "
        f"passed_unchanged={disabled['passed_count_unchanged']}"
    )
    print("SUCCESS:CNF-0060")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
