#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0248.json from live null-stdin measurements."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = "command-center/receipts/TST-0248.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/ux_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0248/probe1_parser_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0248/probe2_hang_detector.py"
)
QUESTION = (
    "Does every command complete or fail without stdin when run non-interactively? "
    "PASS requires no prompt, no hang, and a non-zero exit with an actionable "
    "message where input was required."
)
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    live = H.measure_cli()
    hang = H.measure_hang_control()
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:TST-0248 emit named probes failed")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if not live["all_ok"]:
        print("FAILED:TST-0248 emit CLI coverage not all_ok")
        return 1
    if not hang["pass"]:
        print("FAILED:TST-0248 emit hang control did not pass")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "TST-0248",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0248",
        "completion_sentinel": "SUCCESS:TST-0248",
        "schema_version": 1,
        "report_kind": "ux_report",
        "title": "Non-interactive mode never blocks on stdin",
        "question": QUESTION,
        "min_bytes_threshold": MIN_BYTES,
        "cloud_ok": False,
        "registered": True,
        "enumerated_from": live["enumerated_from"],
        "cli_under_test": "command-center/p2-wave/probes/TST-0248/operator_cli.py",
        "commands": live["commands"],
        "command_count": live["command_count"],
        "stdin": live["stdin"],
        "hang_bound_s": live["hang_bound_s"],
        "max_elapsed_s": live["max_elapsed_s"],
        "any_timed_out": live["any_timed_out"],
        "invocations": live["invocations"],
        "hang_detector": hang,
        "tests": {
            "coverage_every_parser_command": {
                "pass": live["all_ok"] and not live["missing_from_runs"],
                "commands": live["commands"],
                "missing_from_runs": live["missing_from_runs"],
            },
            "detector_control_planted_prompt_caught": {
                "pass": hang["pass"],
                "fired_on_bad_state": hang["fired_on_bad_state"],
                "silent_on_good_state": hang["silent_on_good_state"],
            },
        },
        "evidence": [
            {
                "claim": (
                    "Every argparse subcommand was invoked with stdin attached to "
                    "the null device (subprocess.DEVNULL); none timed out."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0248/harness.py:run_null_stdin",
                "signal": "stdin=DEVNULL",
            },
            {
                "claim": (
                    f"Wall-clock bound {live['hang_bound_s']}s; measured max elapsed "
                    f"{live['max_elapsed_s']}s; planted prompting fixture caught at "
                    f"{hang['planted']['elapsed_s']}s."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0248/probe2_hang_detector.py",
                "signal": "wall-clock-hang-bound",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-prompting-hang",
                "path": hang["planted"]["path"],
                "fired": hang["fired_on_bad_state"],
                "description": (
                    "A fixture that prints a prompt and blocks on a private pipe "
                    "(so DEVNULL cannot satisfy the read) must be killed by the "
                    "hang bound. Naive input() against DEVNULL is EOFError and "
                    "would not exercise the bound."
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0248-probe2-hang-bound",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is a distinct detector: it requires the planted hang to "
                "time out and the good status command to finish under the bound."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "parser-enumerated-null-stdin-coverage", "command": P1},
            {"id": "probe2", "role": "hang-bound-detector-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0248/operator_cli.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_caveat": (
            "Production monitorcore.unified / cockpit binary is not on this "
            "worktree. Measurement is of the live argparse operator CLI shipped "
            "with this unit. Cloud ok=true is not delivery."
        ),
        "scope": {
            "proof_surface": (
                "argparse subcommands of operator_cli.py run with stdin=DEVNULL "
                "under a 2.0s hang bound; confirm/note fail closed with what/why/next; "
                "planted pipe-hang fixture is caught."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "production monitorcore.unified was imported",
            ],
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "output_schema": SCHEMA,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:TST-0248 artifact {size}B below floor {MIN_BYTES}")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:TST-0248" not in text:
        print("FAILED:TST-0248 sentinel missing from file")
        return 1
    if '"state": "BLOCKED"' in text or '"state": "FAILED"' in text:
        print("FAILED:TST-0248 self-declared not-delivering state")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0248 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
