#!/usr/bin/env python3
"""TST-0028 subject workflow: 8 real steps, recordable and replayable.

Record mode runs against the live machine (network attempt, credential probe,
GUI probe, wall clock). Replay mode freezes the clock from the recording and
never opens sockets, never reads credentials, never touches a GUI: those
three steps are deterministically blocked from the recording's reasons.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path

STEP_IDS = [
    "load_inputs", "plan", "digest_tool", "fetch_external",
    "credential_gate", "stamp_clock", "gui_capture", "compose_report",
]
CREDENTIAL_NAME = "TST0028_LIVE_TOKEN"
TEST_NET_HOST = "192.0.2.1"
TEST_NET_PORT = 1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(build_dir: Path, mode: str, freeze_clock_ns: int | None) -> dict:
    """Execute the workflow. Returns the recording/replay document."""
    steps: list[dict] = []
    plan_marker = ""

    def ok(step: str, **detail) -> None:
        steps.append({"step_id": step, "outcome": "ok", **detail})

    def blocked(step: str, reason: str, **detail) -> None:
        steps.append({"step_id": step, "outcome": "blocked",
                      "reason": reason, "reason_class": reason, **detail})

    # 1. load_inputs
    inputs = build_dir / "inputs.txt"
    ok("load_inputs", inputs_bytes=inputs.stat().st_size)

    # 2. plan (behaviour carrier: PLAN_MARKER)
    plan_marker = (build_dir / "plan.txt").read_text(encoding="utf-8").strip()
    ok("plan", plan_marker=plan_marker)

    # 3. digest_tool: behaviour-dependent digest (inputs + plan marker)
    digest = hashlib.sha256(
        inputs.read_bytes() + plan_marker.encode("utf-8")).hexdigest()
    (build_dir / "digest.txt").write_text(digest + "\n", encoding="utf-8")
    ok("digest_tool", digest=digest)

    # 4. fetch_external: real TEST-NET-1 attempt in record mode
    if mode == "record":
        try:
            with socket.create_connection((TEST_NET_HOST, TEST_NET_PORT),
                                          timeout=0.4):
                ok("fetch_external", host=TEST_NET_HOST)
        except OSError as exc:
            blocked("fetch_external", "network", host=TEST_NET_HOST,
                    port=TEST_NET_PORT, error_type=type(exc).__name__)
    else:
        blocked("fetch_external", "network", host=TEST_NET_HOST,
                port=TEST_NET_PORT, detail="offline replay skips the socket")

    # 5. credential_gate
    if mode == "record":
        if os.environ.get(CREDENTIAL_NAME):
            ok("credential_gate", credential_name=CREDENTIAL_NAME)
        else:
            blocked("credential_gate", "credential", credential_name=CREDENTIAL_NAME,
                    credential_present=False)
    else:
        blocked("credential_gate", "credential", credential_name=CREDENTIAL_NAME,
                detail="credential value is never copied into the recording")

    # 6. stamp_clock
    if mode == "record":
        clock_ns = time.time_ns()
        ok("stamp_clock", unix_ns=clock_ns, frozen=False)
    else:
        clock_ns = freeze_clock_ns
        ok("stamp_clock", unix_ns=clock_ns, frozen=True)

    # 7. gui_capture
    gui_session = os.environ.get("TST0028_GUI_SESSION")
    if mode == "record" and gui_session:
        blocked("gui_capture", "GUI", display_present=True)
    else:
        blocked("gui_capture", "GUI", display_present=False,
                detail="UI capture needs a live GUI session; block recorded")

    # 8. compose_report (frozen clock makes replay byte-identical)
    report = {
        "plan_marker": plan_marker,
        "input_digest": digest,
        "clock_unix_ns": clock_ns,
        "steps_ok": [s["step_id"] for s in steps if s["outcome"] == "ok"],
    }
    (build_dir / "report.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ok("compose_report", report_bytes=(build_dir / "report.json").stat().st_size)

    # decision trace: per-step decisions WITH their material inputs, so a
    # behaviour change (plan marker, digest) is visible in the trace itself
    decisions = {
        "load_inputs": "read:inputs.txt",
        "plan": "accept:" + plan_marker,
        "digest_tool": "sha256:" + digest,
        "stamp_clock": "clock:" + str(clock_ns),
        "compose_report": "write:report.json",
    }
    decision_trace = [
        {"step_id": s["step_id"], "decision": decisions[s["step_id"]]}
        for s in steps if s["outcome"] == "ok"
    ]
    decision_trace_ids = [entry["step_id"] for entry in decision_trace]
    trace_sha = hashlib.sha256(
        json.dumps(decision_trace, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "mode": mode,
        "step_ids": STEP_IDS,
        "steps": steps,
        "decision_trace": decision_trace,
        "decision_trace_ids": decision_trace_ids,
        "decision_trace_sha256": trace_sha,
        "plan_marker": plan_marker,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir", required=True)
    ap.add_argument("--mode", choices=["record", "replay"], required=True)
    ap.add_argument("--freeze-clock", type=int, default=None)
    args = ap.parse_args()
    doc = run(Path(args.build_dir), args.mode, args.freeze_clock)
    (Path(args.build_dir) / "record.json").write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "mode": args.mode}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
