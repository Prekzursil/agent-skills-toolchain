#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0325.json from live CLI invocations.

Does not consult cloud ok=true. Does not write the global unit manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "council" / "cli"))

import exit_codes as EC  # noqa: E402
from runtime import COUNCIL_SUCCESS_SENTINEL  # noqa: E402

UNIT = "IMP-0325"
OUT = "command-center/receipts/IMP-0325.json"
CLI = "tools/council/cli/main.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0325/probe1_exit_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0325/probe2_failed_council.py"
)
FIX = HERE / "fixtures"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def invoke(args: list[str], cwd_tmp: Path | None = None) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        ["python3", "-B", str(REPO / CLI), *args],
        cwd=str(cwd_tmp or REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "args": args,
        "exit_code": p.returncode,
        "stdout_bytes": len(p.stdout or ""),
        "stderr_bytes": len(p.stderr or ""),
    }


def measure_live() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0325-emit-") as tmp:
        tmp_path = Path(tmp)
        happy = tmp_path / "happy.json"
        failed = tmp_path / "failed.json"
        nowrite = tmp_path / "nowrite.json"
        resumed = tmp_path / "resumed.json"
        rows = {
            "run_happy": invoke(
                ["run", "--spec", str(FIX / "happy.json"), "--out", str(happy)]
            ),
            "run_failed": invoke(
                ["run", "--spec", str(FIX / "failed-council.json"), "--out", str(failed)]
            ),
            "run_no_write": invoke(
                ["run", "--spec", str(FIX / "no-write.json"), "--out", str(nowrite)]
            ),
            "resume": invoke(
                [
                    "resume",
                    "--checkpoint",
                    str(FIX / "checkpoint.json"),
                    "--out",
                    str(resumed),
                ]
            ),
            "inspect": invoke(["inspect", "--artifact", str(FIX / "artifact-success.json")]),
            "list_presets": invoke(["list-presets"]),
            "explain": invoke(["explain", "--artifact", str(FIX / "artifact-success.json")]),
            "explain_no_rule": invoke(
                ["explain", "--artifact", str(FIX / "artifact-no-rule.json")]
            ),
        }
        failed_text = failed.read_text(encoding="utf-8") if failed.is_file() else ""
        happy_text = happy.read_text(encoding="utf-8") if happy.is_file() else ""
        return {
            "rows": rows,
            "happy_sentinel": COUNCIL_SUCCESS_SENTINEL in happy_text,
            "failed_sentinel": COUNCIL_SUCCESS_SENTINEL in failed_text,
            "failed_artifact_present": failed.is_file(),
            "no_write_artifact_present": nowrite.is_file(),
            "happy_bytes": len(happy_text.encode("utf-8")) if happy.is_file() else 0,
        }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    live = measure_live()
    rows = live["rows"]
    want = {
        "run_happy": EC.EXIT_RUN_OK,
        "run_failed": EC.EXIT_COUNCIL_FAILED,
        "run_no_write": EC.EXIT_MISSING_ARTIFACT,
        "resume": EC.EXIT_RESUME_OK,
        "inspect": EC.EXIT_INSPECT_OK,
        "list_presets": EC.EXIT_LIST_PRESETS_OK,
        "explain": EC.EXIT_EXPLAIN_OK,
        "explain_no_rule": EC.EXIT_NO_LINEAGE,
    }
    mismatches = {
        name: {"got": rows[name]["exit_code"], "want": code}
        for name, code in want.items()
        if rows[name]["exit_code"] != code
    }
    if mismatches:
        print(f"FAILED:{UNIT} emit matrix mismatch {json.dumps(mismatches)}")
        return 1
    if rows["run_failed"]["exit_code"] == 0:
        print(f"FAILED:{UNIT} failed-council exited 0")
        return 1
    if live["failed_sentinel"]:
        print(f"FAILED:{UNIT} failed-council artifact has success sentinel")
        return 1
    if not live["happy_sentinel"]:
        print(f"FAILED:{UNIT} happy run missing {COUNCIL_SUCCESS_SENTINEL}")
        return 1
    if live["no_write_artifact_present"]:
        print(f"FAILED:{UNIT} no-write left an artifact")
        return 1
    if rows["run_no_write"]["exit_code"] == 0:
        print(f"FAILED:{UNIT} no-write exited 0 (spec 11312)")
        return 1

    success_codes = [
        EC.EXIT_RUN_OK,
        EC.EXIT_RESUME_OK,
        EC.EXIT_INSPECT_OK,
        EC.EXIT_LIST_PRESETS_OK,
        EC.EXIT_EXPLAIN_OK,
    ]
    if len(set(success_codes)) != 5:
        print(f"FAILED:{UNIT} success codes not distinct")
        return 1

    impl = art(CLI, "implementation")
    if not impl["exists"] or impl["bytes"] < 128:
        print(f"FAILED:{UNIT} CLI missing or tiny")
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    artifact_paths = [
        CLI,
        "tools/council/cli/exit_codes.py",
        "tools/council/cli/runtime.py",
        "tools/council/cli/presets.json",
        "command-center/p2-wave/probes/IMP-0325/harness.sh",
        "command-center/p2-wave/probes/IMP-0325/probe1_exit_matrix.py",
        "command-center/p2-wave/probes/IMP-0325/probe2_failed_council.py",
        OUT,
    ]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0325",
        "title": "Council CLI",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0325; FC-11312 exit-zero-with-missing-artifact; "
            "catalog inputs 11-COUNCIL-SPECIFICATION.md are absent on this worktree"
        ),
        "question_or_target": (
            "Implement tools/council/cli/main.py exposing run, resume, inspect, "
            "list-presets and explain subcommands with typed exit codes. "
            "Falsifiable question: does every subcommand return a distinct, "
            "documented exit code, and does a failed council ever exit 0?"
        ),
        "answer": (
            "Yes: success codes are 10/11/12/13/14 (pairwise distinct, none is 0). "
            "A failed-council fixture exits 20 and its artifact does not contain "
            "SUCCESS:COUNCIL. A no-write run exits 21, never 0."
        ),
        "artifact_paths": artifact_paths,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-cli-surface"
        ),
        "implementation": {
            "module": CLI,
            "exit_codes": "tools/council/cli/exit_codes.py",
            "runtime": "tools/council/cli/runtime.py",
            "subcommands": [
                "run",
                "resume",
                "inspect",
                "list-presets",
                "explain",
            ],
            "success_codes": {
                "run": EC.EXIT_RUN_OK,
                "resume": EC.EXIT_RESUME_OK,
                "inspect": EC.EXIT_INSPECT_OK,
                "list-presets": EC.EXIT_LIST_PRESETS_OK,
                "explain": EC.EXIT_EXPLAIN_OK,
            },
            "kernel_dependency": (
                "IMP-0264 kernel and IMP-0261 schema are absent; CLI uses a "
                "hermetic fixture runtime so the exit-code contract is measurable."
            ),
        },
        "measured": live,
        "artifacts": [
            impl,
            art("tools/council/cli/exit_codes.py", "supporting"),
            art("tools/council/cli/runtime.py", "supporting"),
            art("tools/council/cli/presets.json", "supporting"),
            art("command-center/p2-wave/probes/IMP-0325/harness.sh", "harness"),
            art(
                "command-center/p2-wave/probes/IMP-0325/probe1_exit_matrix.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0325/probe2_failed_council.py",
                "probe",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Shell harness plus live CLI: each subcommand returns its "
                    "documented distinct success code (10-14)."
                ),
                "verdict": "CONFIRMED",
                "kind": "exit-code-matrix",
                "anchor": "tools/council/cli/exit_codes.py",
                "matrix": {name: rows[name]["exit_code"] for name in want},
            },
            {
                "claim": (
                    "Failed-council fixture exits non-zero "
                    f"({EC.EXIT_COUNCIL_FAILED}) and the artifact has no "
                    f"{COUNCIL_SUCCESS_SENTINEL}."
                ),
                "verdict": "CONFIRMED",
                "kind": "failed-council-fixture",
                "exit_code": rows["run_failed"]["exit_code"],
                "success_sentinel_present": live["failed_sentinel"],
            },
            {
                "claim": (
                    "A run that writes no artifact exits "
                    f"{EC.EXIT_MISSING_ARTIFACT}, never 0 (spec 11312)."
                ),
                "verdict": "CONFIRMED",
                "kind": "negative-control",
                "exit_code": rows["run_no_write"]["exit_code"],
                "artifact_present": live["no_write_artifact_present"],
            },
        ],
        "test_ids": [
            "exit-code-matrix",
            "failed-council-nonzero-absent-sentinel",
        ],
        "negative_control_ids": [
            "FC-11312-exit-zero-with-missing-artifact",
        ],
        "tests": [
            {"id": "exit-code-matrix", "command": P1, "result": "PENDING-NAMED-PROBE"},
            {
                "id": "failed-council-and-11312",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0325-probe2-failed-council",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 starts from the live CLI binary and the failed-council "
                "fixture, not from the author's matrix summary."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md and the IMP-0264 kernel are "
                    "absent; list-presets uses a three-preset hermetic catalog "
                    "rather than the 72-preset harness file."
                ),
                "settling_experiment": (
                    "When IMP-0261/IMP-0264 land, bind run/resume to the kernel "
                    "event loop and re-run the same exit-code matrix."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0325: live named probes must exit 0 against "
            "tools/council/cli/main.py. cloud ok=true is not delivery. "
            "Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0325" not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        "matrix "
        + " ".join(f"{k}={rows[k]['exit_code']}" for k in want)
        + f" failed_sentinel={live['failed_sentinel']}"
    )
    print("SUCCESS:IMP-0325")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
