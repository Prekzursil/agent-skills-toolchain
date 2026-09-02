#!/usr/bin/env python3
"""Probe 1: extract documented commands and EXECUTE them.

Exit 0 only when both required controls fire: the extractor finds the known
example, the known-good command exits 0, and the planted typo is a non-zero
exit. Product mismatches are findings, not probe failures.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from common import REPO, dump_json, repo_env  # noqa: E402
from extract import extract_all  # noqa: E402

TIMEOUT = 20
TAIL = 800


def run_command(command: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=repo_env(),
        )
    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "stdout": "",
            "stderr": "TIMEOUT",
            "timed_out": True,
        }
    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-TAIL:],
        "stderr": (proc.stderr or "")[-TAIL:],
        "timed_out": False,
    }


def evaluate(example: dict[str, Any], ran: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(example)
    if ran is None:
        row["executed"] = False
        row["skip_reason"] = "unsafe-or-destructive"
        row["verdict"] = "NOT-CHECKED"
        return row
    row["executed"] = True
    row.update(ran)
    expect_exit = (example.get("expect-exit") or "").strip()
    expect_sub = (example.get("expect-substring") or "").strip()
    expected_count = (example.get("expected-count") or "").strip()
    exit_code = int(ran["exit_code"])
    stdout = ran.get("stdout") or ""
    shape_ok = True
    notes: list[str] = []
    if expect_exit == "0":
        shape_ok = shape_ok and exit_code == 0
    elif expect_exit == "nonzero":
        shape_ok = shape_ok and exit_code != 0
    if expect_sub:
        if expect_sub not in stdout:
            shape_ok = False
            notes.append("missing-expect-substring")
    count_mismatch = False
    if expected_count and exit_code == 0:
        got = stdout.strip().splitlines()[-1].strip() if stdout.strip() else ""
        row["observed_count"] = got
        if got != expected_count:
            count_mismatch = True
            notes.append(f"count-claim {expected_count} vs executed {got}")
    role = example.get("role") or "live"
    if role == "known-broken":
        row["verdict"] = "PASS-CONTROL" if exit_code != 0 else "FAIL-CONTROL"
    elif role == "known-good":
        row["verdict"] = "PASS-CONTROL" if exit_code == 0 and shape_ok else "FAIL-CONTROL"
    elif count_mismatch:
        row["verdict"] = "MISMATCH"
    elif exit_code == 0 and shape_ok:
        row["verdict"] = "MATCH"
    else:
        row["verdict"] = "MISMATCH"
    row["notes"] = notes
    row["shape_ok"] = shape_ok
    return row


def main() -> int:
    extracted = extract_all()
    results: list[dict[str, Any]] = []
    for example in extracted["control_examples"] + extracted["live_examples"]:
        command = example["command"]
        should_run = example["safe"] or example.get("corpus") == "control"
        ran = run_command(command) if should_run else None
        results.append(evaluate(example, ran))

    controls = [r for r in results if r.get("corpus") == "control"]
    live = [r for r in results if r.get("corpus") == "shipped"]
    known_good = [r for r in controls if r.get("role") == "known-good"]
    known_broken = [r for r in controls if r.get("role") == "known-broken"]
    planted_count = [r for r in controls if r.get("role") == "planted-count-drift"]

    extractor_ok = extracted["extractor_found_known_good"] is True
    good_ok = bool(known_good) and all(r["verdict"] == "PASS-CONTROL" for r in known_good)
    broken_ok = bool(known_broken) and all(
        r["verdict"] == "PASS-CONTROL" for r in known_broken
    )
    count_detector_ok = bool(planted_count) and all(
        r["verdict"] == "MISMATCH" for r in planted_count
    )

    live_match = [r for r in live if r["verdict"] == "MATCH"]
    live_mismatch = [r for r in live if r["verdict"] == "MISMATCH"]
    live_skip = [r for r in live if r["verdict"] == "NOT-CHECKED"]

    payload = {
        "probe": "probe1-execute-docs",
        "unit_id": "ADV-0112",
        "extractor": {
            "shipped_doc_count": extracted["shipped_doc_count"],
            "control_doc_count": extracted["control_doc_count"],
            "live_example_count": extracted["live_example_count"],
            "control_example_count": extracted["control_example_count"],
            "extractor_found_known_good": extracted["extractor_found_known_good"],
            "extractor_found_known_broken": extracted["extractor_found_known_broken"],
        },
        "controls": {
            "extractor_finds_known_example": extractor_ok,
            "known_good_runs": good_ok,
            "known_broken_fails": broken_ok,
            "planted_count_drift_detected": count_detector_ok,
        },
        "live": {
            "executed": len(live) - len(live_skip),
            "match": len(live_match),
            "mismatch": len(live_mismatch),
            "not_checked": len(live_skip),
            "mismatches": [
                {
                    "id": r.get("id"),
                    "source": r.get("source"),
                    "command": r.get("command"),
                    "exit_code": r.get("exit_code"),
                    "notes": r.get("notes"),
                }
                for r in live_mismatch
            ],
        },
        "results": results,
        "ok": extractor_ok and good_ok and broken_ok and count_detector_ok,
    }
    sys.stdout.write(dump_json(payload))
    if payload["ok"]:
        print(
            "SUCCESS:ADV-0112-probe1 extractor+known-good+known-broken+"
            "planted-count-drift"
        )
        return 0
    print("FAILED:ADV-0112-probe1 controls did not all fire", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
