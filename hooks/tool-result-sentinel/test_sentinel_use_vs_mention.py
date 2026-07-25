#!/usr/bin/env python3
"""Regression suite for the tool-sentinel use-vs-mention defect (2026-07-20/24).

Every RECORDED false fire must go SILENT, and every genuine infra failure must STILL
fire. A suppression that silences both proves nothing, so the positive controls are as
load-bearing as the negatives.

Recorded fires this suite locks down:
  A. dbx_run_get on a RUNNING job -> the KEY `user_cancelled_or_timedout` (value False)
     matched /tim(ed|e)-?out/. Fired 3x in one session on a job that ended SUCCESS.
  B. basic-memory read_note returning the memory note that DOCUMENTS this defect -- an
     accurate write-up must quote the trigger phrase, so the guard suppressed its own
     bug report.
  C1-C3. Three MORE fires measured 2026-07-24, each a road AROUND the A/B fix:
     C1 the SAME Databricks field name, on a REAL-SIZE payload. `_gather_text` caps the
        scan surface at 8,000 chars; a real `dbx_run_get` body is 14,060, so the surface
        is truncated mid-document, stops parsing as JSON, `json_value_text()` returns
        None, and the raw-text fallback puts every FIELD NAME back on the scan surface.
        Case A passes only because its payload is small enough to parse -- it never
        exercises the fallback, which is why the defect kept firing after A was green.
     C2 github `get_file_contents` that SUCCEEDED (valid blob sha + full markdown) was
        flagged `timeout` because the FETCHED DOCUMENT contained a config example
        `"timeout": 100000`. A returned document is DATA; only a status field reports.
     C3 WebFetch returning HTTP 200 with correct content, reported
        `FAILED (exit code 200)` -- the generic `code` key read with exit-code
        semantics. 200 is an HTTP success, never an exit status.

Run: python test_sentinel_use_vs_mention.py     (also pytest-collectable)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sentinel import _gather_text, classify  # noqa: E402

MCP = "mcp__cloud-hub__dbx_run_get"
NOTE = "mcp__basic-memory__read_note"
GH = "mcp__github__get_file_contents"
WEB = "WebFetch"


def _resp(payload) -> dict:
    """Shape an MCP tool_response the way the hook bus delivers it."""
    return {
        "content": [
            {
                "type": "text",
                "text": payload if isinstance(payload, str) else json.dumps(payload),
            }
        ]
    }


# --- A. the field-NAME fire (must be SILENT) --------------------------------------
RUNNING_JOB = _resp(
    json.dumps(
        {
            "ok": True,
            "data": {
                "run_id": 1011848026466066,
                "state": {
                    "life_cycle_state": "RUNNING",
                    "state_message": "In run",
                    "user_cancelled_or_timedout": False,
                },
                "tasks": [
                    {
                        "state": {
                            "life_cycle_state": "RUNNING",
                            "user_cancelled_or_timedout": False,
                        }
                    }
                ],
            },
        }
    )
)

# --- B. the prose-MENTION fire (must be SILENT) -----------------------------------
# Faithful to the fire actually recorded: the note names the offending field in
# BACKTICKS inside a markdown table. Suppressed by the inline-code rule.
DEFECT_NOTE = _resp(
    json.dumps(
        {
            "result": (
                "# Use-vs-mention guard defect\n\n"
                "| Detector | Fires | What it matched |\n"
                "|---|---|---|\n"
                "| tool-sentinel | 2+ | JSON field name `user_cancelled_or_timedout`, value False |\n\n"
                "The guard reported a *successful* Databricks result as missing/garbage.\n"
            )
        }
    )
)

# --- B2. same-line negation (must be SILENT) --------------------------------------
NEGATED = _resp(
    json.dumps({"result": "Nothing failed and no connection timed out here."})
)


# --- C1. the SAME field name on a REAL-SIZE payload -------------------------------
def _dbx_run_body(*, result_state: str | None = None, tasks: int = 40) -> str:
    """A `dbx_run_get` body the size of a REAL one. The SIZE is the point.

    With `result_state=None` the run is RUNNING and the only match on the surface is
    the FIELD NAME `user_cancelled_or_timedout` (value False) -> must be SILENT.
    With `result_state="TIMEDOUT"` the same shape carries a genuine Databricks
    terminal-state VALUE -> must FIRE. Same tool, same size class, same defeated
    structural parse: the ONLY difference is key-vs-value, which is exactly the
    signal the verdict must key on.
    """
    state = (
        {
            "life_cycle_state": "RUNNING",
            "state_message": "In run",
            "user_cancelled_or_timedout": False,
        }
        if result_state is None
        else {
            "life_cycle_state": "TERMINATED",
            "result_state": result_state,
            "user_cancelled_or_timedout": False,
        }
    )
    return json.dumps(
        {
            "ok": True,
            "data": {
                "run_id": 1011848026466066,
                "state": state,
                "tasks": [
                    {
                        "task_key": f"unit_{i:03d}",
                        "notebook_task": {
                            "notebook_path": "/Workspace/Repos/fanout/runner",
                            "base_parameters": {
                                "unit": f"unit_{i:03d}",
                                "payload": "x" * 120,
                            },
                        },
                        "state": {
                            "life_cycle_state": "RUNNING",
                            "user_cancelled_or_timedout": False,
                        },
                    }
                    for i in range(tasks)
                ],
            },
        }
    )


BIG_RUNNING_JOB = _resp(_dbx_run_body())
BIG_TIMEDOUT_JOB = _resp(_dbx_run_body(result_state="TIMEDOUT"))

# --- C2. a FETCHED DOCUMENT whose body mentions a timeout --------------------------
GH_CONFIG_DOC = (
    "# MCP config\n\n"
    "Set the per-call request budget in `.mcp.json`:\n\n"
    "```json\n"
    "{\n"
    '  "mcpServers": {\n'
    '    "cloud-hub": {\n'
    '      "timeout": 100000\n'
    "    }\n"
    "  }\n"
    "}\n"
    "```\n\n"
    "That is the whole change.\n"
)
GH_FILE_OK = _resp(
    json.dumps(
        {
            "sha": "9f1c0a2b3d4e5f60718293a4b5c6d7e8f9012345",
            "path": "docs/mcp.md",
            "encoding": "utf-8",
            "content": GH_CONFIG_DOC,
        }
    )
)

# Same class, different surface: the phrase is a FENCED console TRANSCRIPT inside a
# fetched runbook, not a report about THIS call. Isolates the fenced-example rule --
# it is not a quoted JSON key, so the key rule alone cannot silence it.
GH_RUNBOOK_OK = _resp(
    json.dumps(
        {
            "sha": "0011223344556677889900aabbccddeeff001122",
            "path": "docs/runbook.md",
            "content": (
                "# Runbook\n\n"
                "If the probe hangs you will see:\n\n"
                "```console\n"
                "curl: (28) Operation timed out after 30001 milliseconds\n"
                "```\n\n"
                "Raise the budget and retry.\n"
            ),
        }
    )
)

# --- C3. WebFetch HTTP 200 under the generic `code` key ---------------------------
WEB_200 = {"code": 200, "url": "https://example.com", "content": "<html>ok</html>"}
WEB_301 = {"code": 301, "url": "https://example.com/old"}

# --- positive controls (must STILL fire) ------------------------------------------
REAL_TIMEOUT = _resp(json.dumps({"ok": False, "error": "connection timed out"}))
REAL_NESTED = _resp(
    json.dumps(
        {
            "result": json.dumps(
                {"ok": False, "error": "MCP error -32000: server is not responding"}
            )
        }
    )
)
REAL_PLAINTEXT = _resp("Error: ECONNREFUSED while reaching the backend")
REAL_PROSE_VALUE = _resp(json.dumps({"content": "failed to connect to the database"}))
# A key named `timeout` sitting NEXT TO a real error value: the key rule must suppress
# the key only, never its neighbour.
REAL_BESIDE_KEY = _resp(json.dumps({"timeout": 30000, "error": "connection refused"}))
# Guard against a fence parser that swallows the tail: the real error follows a CLOSED
# fenced example and must still fire (mirrors test_command_after_a_closed_quote).
REAL_AFTER_FENCE = _resp(
    "Fetched the doc:\n```json\n"
    '{"retries": 3}\n'
    "```\nMCP error -32000: server is not responding"
)
WEB_503 = {"code": 503, "content": "Service Unavailable"}
WEB_EXIT_1 = {"code": 1, "stderr": "boom"}
WEB_EXIT_127 = {"code": 127, "stderr": "command not found"}
# Both-states: the `code`-is-HTTP fix must NOT mask a real envelope failure.
WEB_200_ISERROR = {"code": 200, "isError": True, "content": "partial"}
WEB_200_INTERRUPTED = {"code": 200, "interrupted": True}

CASES = [
    ("A  field-name on RUNNING job", MCP, RUNNING_JOB, "SUCCESS"),
    ("B  backticked mention in a note", NOTE, DEFECT_NOTE, "SUCCESS"),
    ("B2 same-line negation", NOTE, NEGATED, "SUCCESS"),
    ("C1 field-name, REAL-SIZE payload", MCP, BIG_RUNNING_JOB, "SUCCESS"),
    ("C2 fetched doc: json config key", GH, GH_FILE_OK, "SUCCESS"),
    ("C2b fetched doc: fenced console", GH, GH_RUNBOOK_OK, "SUCCESS"),
    ("C3 WebFetch code=200", WEB, WEB_200, "SUCCESS"),
    ("C3b WebFetch code=301", WEB, WEB_301, "SUCCESS"),
    ("PC1 genuine timeout value", MCP, REAL_TIMEOUT, "FAILED"),
    ("PC2 genuine nested MCP error", MCP, REAL_NESTED, "FAILED"),
    ("PC3 genuine non-JSON ECONNREFUSED", MCP, REAL_PLAINTEXT, "FAILED"),
    ("PC4 genuine failure in a value", MCP, REAL_PROSE_VALUE, "FAILED"),
    ("PC5 real error beside timeout key", MCP, REAL_BESIDE_KEY, "FAILED"),
    ("PC6 real error after a fence", MCP, REAL_AFTER_FENCE, "FAILED"),
    ("PC7 REAL-SIZE run result TIMEDOUT", MCP, BIG_TIMEDOUT_JOB, "FAILED"),
    ("PC8 WebFetch code=503", WEB, WEB_503, "FAILED"),
    ("PC9 WebFetch code=1", WEB, WEB_EXIT_1, "FAILED"),
    ("PC10 WebFetch code=127", WEB, WEB_EXIT_127, "FAILED"),
    ("PC11 code=200 + isError", WEB, WEB_200_ISERROR, "FAILED"),
    ("PC12 code=200 + interrupted", WEB, WEB_200_INTERRUPTED, "FAILED"),
]


def run() -> int:
    ok = True
    for label, tool, resp, expected in CASES:
        verdict, reason = classify(tool, {}, resp)
        good = verdict == expected
        ok &= good
        print(
            f"[{'PASS' if good else 'FAIL'}] {label:34s} got={verdict:9s} "
            f"want={expected:9s} {reason[:60]}"
        )
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


def test_use_vs_mention_regression():
    """pytest entry point."""
    assert run() == 0


def test_code_200_envelope_failures_fire_for_the_RIGHT_reason():
    """Both-states: PC11/PC12 also FIRED before the fix, but as `exit code 200`.

    A verdict that is right for the wrong reason cannot distinguish the fixed state
    from the broken one, so asserting only "it fires" would measure nothing here.
    """
    verdict, reason = classify(WEB, {}, WEB_200_ISERROR)
    assert verdict == "FAILED"
    assert reason == "isError=true", reason
    verdict, reason = classify(WEB, {}, WEB_200_INTERRUPTED)
    assert verdict == "FAILED"
    assert reason == "interrupted", reason


def test_c1_payload_really_defeats_the_structural_parse():
    """The C1 premise, asserted rather than assumed.

    C1 only proves anything if the payload is genuinely large enough to be truncated
    by `_gather_text` -- otherwise it silently degenerates into a duplicate of case A
    and the raw-text fallback is never exercised.
    """
    body = _dbx_run_body()
    assert len(body) > 8000, f"payload must exceed the 8000-char cap, got {len(body)}"
    surface = _gather_text(_resp(body))
    assert len(surface) == 8000, "surface must be truncated to the cap"
    assert "user_cancelled_or_timedout" in surface, (
        "the field NAME must be on the surface"
    )
    try:
        json.loads(surface)
    except ValueError:
        pass  # expected: truncation broke the JSON, so the key-stripping parse is lost
    else:  # pragma: no cover - defensive
        raise AssertionError("truncated surface still parses; premise no longer holds")


if __name__ == "__main__":
    sys.exit(run())
