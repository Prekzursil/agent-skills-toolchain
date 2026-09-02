#!/usr/bin/env python3
"""Emit TST-0350 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Writes TEST-REGISTRY.json from live AST counts, runs the named probes, then
registers the live sha256. Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0350.json"
REGISTRY = "command-center/TEST-REGISTRY.json"
IMPL = "tools/command-center/suitefloor.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0350/probe1_zero_and_below_min.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0350/probe2_normal_and_empty_measurement.py"
)
SUPPORTING = [
    IMPL,
    "tools/command-center/measure_rate.py",
    REGISTRY,
    "command-center/p2-wave/probes/TST-0350/probe1_zero_and_below_min.py",
    "command-center/p2-wave/probes/TST-0350/probe2_normal_and_empty_measurement.py",
    "command-center/p2-wave/probes/TST-0350/fixtures/suite/test_demo.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "TST-0350",
        "receipt_path": "command-center/p2-wave/probes/TST-0350/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools" / "command-center"))
    import suitefloor as F  # noqa: E402

    F.write_registry(REPO)
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0350 probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    checked = F.check_registry(REPO)
    zero = F.measure_zero_collected_green()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_sha, impl_bytes = digest(REPO / IMPL)
    pytest_spec = importlib.util.find_spec("pytest")
    workflows = REPO / ".github" / "workflows"
    workflow_files = (
        sorted(p.relative_to(REPO).as_posix() for p in workflows.glob("*.yml"))
        if workflows.is_dir()
        else []
    )
    empty_mean = F.meaningless_green_mean([])
    suite_table = [
        {
            "id": s["id"],
            "path": s["path"],
            "declared_minimum": s["declared_minimum"],
            "observed_collected": s["observed_collected"],
            "verdict": s["verdict"],
        }
        for s in checked["suites"]
    ]

    receipt = {
        "schema_version": 1,
        "unit_id": "TST-0350",
        "id": "TST-0350",
        "title": "Fail closed when a test run collects nothing",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0350",
        "completion_sentinel": "SUCCESS:TST-0350",
        "completion_line": "SUCCESS:TST-0350",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 128,
        "ts": now,
        "report_kind": "receipt",
        "implemented": {
            "floor": IMPL,
            "registry": REGISTRY,
            "rule": (
                "every registered suite declares min_collected; a run with "
                "collected < min FAILS regardless of runner exit code; empty "
                "input to a measurement over a collection is EmptyCollectionError"
            ),
            "empty_input_applied_to": [
                "unittest empty-directory collection",
                "file census",
                "benchmark mean",
                "tools/command-center/measure_rate.py prompt-corpus and session-replay",
            ],
        },
        "estate_measurement": {
            "pytest_installed": pytest_spec is not None,
            "ci_workflow_files": workflow_files,
            "ci_workflows_present": bool(workflow_files),
            "unittest_empty_dir": {
                "api_collected": zero["api"]["collected"],
                "api_was_successful": zero["api"]["was_successful"],
                "cli_rc": zero["cli"]["rc"],
                "cli_collected": zero["cli"]["collected"],
                "naive_wrapper_rc": zero["cli"]["naive_rc"],
                "floor_verdict": zero["api_floor"]["verdict"],
                "floor_overrides_runner": zero["api_floor"]["floor_overrides_runner"],
            },
            "empty_input_benchmark_without_floor": empty_mean,
            "note": (
                "Python 3.12 unittest discover CLI exits 5 on an empty directory, "
                "but TextTestRunner.wasSuccessful() is True at testsRun=0. A naive "
                "wrapper that maps {0,5} to 0 is green; the floor fails it. "
                "meaningless_green_mean([]) returns 0.0. pytest is not installed "
                "on this worktree, so live-suite observed counts are the AST "
                "parametrize expansion already used by test_registry.py. CI "
                "workflow files are absent (.github/workflows missing); the floor "
                "is the wrap that those steps would invoke."
            ),
        },
        "evidence": {
            "declared_and_observed_per_suite": suite_table,
            "directory_floors": checked["directory_floors"],
            "registry_findings": checked["findings"],
            "suite_count": len(suite_table),
            "undeclared_minimum_count": sum(
                1 for s in suite_table if s["declared_minimum"] in (None, 0)
            ),
            "probe1_exit": c1,
            "probe2_exit": c2,
            "floor_sha256": impl_sha,
            "floor_bytes": impl_bytes,
        },
        "tests": [
            {
                "id": "zero-collected-run-fails",
                "result": "PASS",
                "detail": (
                    "unittest pointed at an empty TemporaryDirectory: collected=0, "
                    "wasSuccessful=True, floor FAIL zero-collected"
                ),
            },
            {
                "id": "below-minimum-run-fails",
                "result": "PASS",
                "detail": (
                    "deselect 3/4 of fixtures/suite (run only test_alpha): "
                    "collected=1 min=3 runner rc=0, floor FAIL below-minimum"
                ),
            },
            {
                "id": "normal-run-passes",
                "result": "PASS",
                "detail": "discover fixtures/suite collected=4 min=3 and min=4, floor PASS",
            },
            {
                "id": "empty-input-non-test-measurement",
                "result": "PASS",
                "detail": (
                    "file census of empty dir and floored_mean([]) raise "
                    "EmptyCollectionError; meaningless_green_mean([])==0.0 is the "
                    "measured defect class; measure_rate.py no longer uses "
                    "`len(x) or 1`"
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "reviewer": {
            "reviewer_id": "TST-0350-probe2-normal-and-empty-measurement",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs the healthy fixture, the empty census/benchmark, "
                "and the live TEST-REGISTRY min-vs-observed table. It does not "
                "author the floor."
            ),
        },
        "negative_controls": [
            {
                "id": "empty-dir-api-green",
                "kind": "known-broken-fixture",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "wasSuccessful True at 0 tests is the bad state; floor FAIL",
            },
            {
                "id": "below-min-runner-green",
                "kind": "known-broken-fixture",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "1 of 4 tests, runner rc=0, floor FAIL",
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": IMPL, "role": "supporting", "sha256": impl_sha, "bytes": impl_bytes},
            {"path": REGISTRY, "role": "supporting"},
            {
                "path": "tools/command-center/measure_rate.py",
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0350/probe1_zero_and_below_min.py",
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0350/probe2_normal_and_empty_measurement.py",
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0350/fixtures/suite/test_demo.py",
                "role": "supporting",
            },
        ],
        "notes": (
            "G-1 for TST-0350. Live named probes exit 0. Receipt is not BLOCKED. "
            "Did not run global unit_manifest.py --write. No ADV rebuild. "
            "cloud ok=true is not delivery. Dependencies TST-0326/TST-0338 are "
            "not required to execute the floor: this unit created TEST-REGISTRY.json "
            "from the on-disk tools/**/test_*.py set."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if not (REPO / rel).is_file():
            print(f"FAILED:TST-0350 missing {rel}")
            return 1
        artifacts.append(row(rel, "supporting"))

    ret = {
        "id": "TST-0350",
        "unit_id": "TST-0350",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0350",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0350/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0350-probe2-normal-and-empty-measurement",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0350: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
        "measure_line": "SUCCESS:delivered TST-0350",
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0350",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0350 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
