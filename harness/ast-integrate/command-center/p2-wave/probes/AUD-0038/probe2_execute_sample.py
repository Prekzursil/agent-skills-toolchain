#!/usr/bin/env python3
"""Probe 2: single-node execution of a stratified sample (setup-error control)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / "command-center/audit/AUD-0038-test-registry-resolution.json"
SENTINEL = (
    "SUCCESS:AUD-0038 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0038-probe2 {msg}")
    return 1


def main() -> int:
    data = E.resolve()
    exe = E.stratified_execute(data)
    ctrl = E.control_ok(data, exe)
    compact_runs = [
        {
            "stratum": r.get("stratum"),
            "test_id": r.get("test_id"),
            "nodeid": r.get("nodeid"),
            "returncode": r.get("returncode"),
            "outcome": r.get("outcome"),
            "executable_ok": r.get("executable_ok"),
            "source": r.get("source"),
        }
        for r in exe["runs"]
    ]
    payload = {
        "probe": "probe2-single-node-execution",
        "unit_id": "AUD-0038",
        "live_run_count": exe["live_run_count"],
        "setup_run_count": exe["setup_run_count"],
        "live_all_passed": exe["live_all_passed"],
        "setup_error_not_counted_executable": exe[
            "setup_error_not_counted_executable"
        ],
        "runs": compact_runs,
        "pass": bool(ctrl["execution_discriminates"]),
    }
    print(json.dumps(payload, sort_keys=True))

    if exe["live_run_count"] < 3:
        return fail(f"stratified live sample too small: {exe['live_run_count']}")
    if not exe["live_all_passed"]:
        print(json.dumps(compact_runs, indent=2)[:2000])
        return fail("a live sample node did not PASS on single-node execution")
    if exe["setup_run_count"] != 1:
        return fail("setup-error control was not executed")
    if not exe["setup_error_not_counted_executable"]:
        return fail("setup-error node counted as executable")
    setup = next(r for r in exe["runs"] if r.get("stratum") == "CONTROL-SETUP-ERROR")
    if setup["outcome"] == "PASSED":
        return fail("setup-error control PASSED")
    if data["setup_error_control"]["collectible"] is not True:
        return fail("setup-error was not collectible (probe1/probe2 split collapsed)")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable:{type(exc).__name__}")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact state={doc.get('state')}")
        if SENTINEL not in text:
            return fail("completion sentinel absent")
        print(f"artifact_state={doc.get('state')} bytes={ART.stat().st_size}")

    print(
        f"live_passed={exe['live_run_count']} "
        f"setup_outcome={setup['outcome']} "
        f"collectible_not_executable=True"
    )
    print("SUCCESS:AUD-0038-probe2 stratified single-node execution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
