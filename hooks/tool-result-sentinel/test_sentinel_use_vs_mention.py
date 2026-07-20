#!/usr/bin/env python3
"""Regression suite for the tool-sentinel use-vs-mention defect (2026-07-20).

Every RECORDED false fire must go SILENT, and every genuine infra failure must STILL
fire. A suppression that silences both proves nothing, so the positive controls are as
load-bearing as the negatives.

Recorded fires this suite locks down:
  A. dbx_run_get on a RUNNING job -> the KEY `user_cancelled_or_timedout` (value False)
     matched /tim(ed|e)-?out/. Fired 3x in one session on a job that ended SUCCESS.
  B. basic-memory read_note returning the memory note that DOCUMENTS this defect -- an
     accurate write-up must quote the trigger phrase, so the guard suppressed its own
     bug report.

Run: python test_sentinel_use_vs_mention.py     (also pytest-collectable)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sentinel import classify  # noqa: E402

MCP = "mcp__cloud-hub__dbx_run_get"
NOTE = "mcp__basic-memory__read_note"


def _resp(payload) -> dict:
    """Shape an MCP tool_response the way the hook bus delivers it."""
    return {"content": [{"type": "text", "text": payload if isinstance(payload, str)
                         else json.dumps(payload)}]}


# --- A. the field-NAME fire (must be SILENT) --------------------------------------
RUNNING_JOB = _resp(json.dumps({
    "ok": True,
    "data": {
        "run_id": 1011848026466066,
        "state": {"life_cycle_state": "RUNNING", "state_message": "In run",
                  "user_cancelled_or_timedout": False},
        "tasks": [{"state": {"life_cycle_state": "RUNNING",
                             "user_cancelled_or_timedout": False}}],
    },
}))

# --- B. the prose-MENTION fire (must be SILENT) -----------------------------------
# Faithful to the fire actually recorded: the note names the offending field in
# BACKTICKS inside a markdown table. Suppressed by the inline-code rule.
DEFECT_NOTE = _resp(json.dumps({"result": (
    "# Use-vs-mention guard defect\n\n"
    "| Detector | Fires | What it matched |\n"
    "|---|---|---|\n"
    "| tool-sentinel | 2+ | JSON field name `user_cancelled_or_timedout`, value False |\n\n"
    "The guard reported a *successful* Databricks result as missing/garbage.\n"
)}))

# --- B2. same-line negation (must be SILENT) --------------------------------------
NEGATED = _resp(json.dumps({"result": "Nothing failed and no connection timed out here."}))

# --- positive controls (must STILL fire) ------------------------------------------
REAL_TIMEOUT = _resp(json.dumps({"ok": False, "error": "connection timed out"}))
REAL_NESTED = _resp(json.dumps({"result": json.dumps(
    {"ok": False, "error": "MCP error -32000: server is not responding"})}))
REAL_PLAINTEXT = _resp("Error: ECONNREFUSED while reaching the backend")
REAL_PROSE_VALUE = _resp(json.dumps({"content": "failed to connect to the database"}))

CASES = [
    ("A  field-name on RUNNING job", MCP, RUNNING_JOB, "SUCCESS"),
    ("B  backticked mention in a note", NOTE, DEFECT_NOTE, "SUCCESS"),
    ("B2 same-line negation", NOTE, NEGATED, "SUCCESS"),
    ("PC1 genuine timeout value", MCP, REAL_TIMEOUT, "FAILED"),
    ("PC2 genuine nested MCP error", MCP, REAL_NESTED, "FAILED"),
    ("PC3 genuine non-JSON ECONNREFUSED", MCP, REAL_PLAINTEXT, "FAILED"),
    ("PC4 genuine failure in a value", MCP, REAL_PROSE_VALUE, "FAILED"),
]


def run() -> int:
    ok = True
    for label, tool, resp, expected in CASES:
        verdict, reason = classify(tool, {}, resp)
        good = verdict == expected
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] {label:34s} got={verdict:9s} "
              f"want={expected:9s} {reason[:60]}")
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


def test_use_vs_mention_regression():
    """pytest entry point."""
    assert run() == 0


if __name__ == "__main__":
    sys.exit(run())
