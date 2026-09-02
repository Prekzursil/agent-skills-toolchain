#!/usr/bin/env python3
"""Probe 1: request-level diff of Claude vs Codex on identical cases.

Both-states: a portable case has an empty canonical diff; dropping a tool
from Codex makes the diff non-empty. A detector that is empty in both
states cannot see an adapter leak.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.cross_vendor.parity_bench import (  # noqa: E402
    both_states_request_diff,
    run_parity,
)

ART = REPO / "command-center/receipts/TST-0316.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0316-probe1 {msg}")
    return 1


def main() -> int:
    report = run_parity()
    ctrl = both_states_request_diff()
    payload = {
        "probe": "probe1-request-diff",
        "n_cases": report["n_cases"],
        "n_empty_diff": report["n_empty_diff"],
        "n_diverged": report["n_diverged"],
        "empty_ids": [r["case_id"] for r in report["score_table"]],
        "diverged_ids": [
            r["case_id"]
            for r in report["request_diff_table"]
            if not r["empty_request_diff"]
        ],
        "both_states": {
            "case_id": ctrl["case_id"],
            "good_empty": ctrl["good_empty"],
            "bad_nonempty": ctrl["bad_nonempty"],
            "bad_fields": ctrl["bad_fields"],
        },
    }
    print(json.dumps(payload, sort_keys=True))

    if report["n_cases"] < 8:
        return fail(f"corpus too small n={report['n_cases']}")
    if report["n_empty_diff"] < 4:
        return fail(f"expected >=4 empty-diff portable cases, got {report['n_empty_diff']}")
    if report["n_diverged"] < 3:
        return fail(f"expected documented leaks, diverged={report['n_diverged']}")

    by_id = {r["case_id"]: r for r in report["request_diff_table"]}
    timeout = by_id.get("cv-timeout-clamp")
    if timeout is None:
        return fail("timeout-clamp case missing")
    if timeout["empty_request_diff"]:
        return fail("timeout clamp produced empty request-diff")
    fields = {d["field"] for d in timeout["divergences"]}
    if "timeout" not in fields:
        return fail(f"timeout clamp divergences={timeout['divergences']}")
    if timeout["claude_timeout"] == timeout["codex_timeout"]:
        return fail("timeout values equal; clamp not visible")

    task = by_id.get("cv-claude-task")
    if task is None:
        return fail("claude-task case missing")
    if task["codex_status"] != "UNSUPPORTED":
        return fail(f"Task mismatch not UNSUPPORTED: {task['codex_status']}")
    if "status" not in {d["field"] for d in task["divergences"]}:
        return fail("Task mismatch omitted from request-diff table")

    mcp = by_id.get("cv-codex-mcp")
    if mcp is None or mcp["claude_status"] != "UNSUPPORTED":
        return fail("mcp__codex__codex mismatch not UNSUPPORTED on Claude")

    if not ctrl["good_empty"]:
        return fail("both-states good portable case was non-empty")
    if not ctrl["bad_nonempty"]:
        return fail("both-states drop-tool mutant stayed empty")
    if "tools" not in ctrl["bad_fields"]:
        return fail(f"drop-tool mutant fields={ctrl['bad_fields']}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0316" not in text:
            return fail("receipt-sentinel-absent")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt-self-declared {doc.get('state')}")
        tables = doc.get("tables") or []
        kinds = [t.get("kind") for t in tables if isinstance(t, dict)]
        if "request_diff" not in kinds or "score" not in kinds:
            return fail("receipt tables missing request_diff or score")
        if kinds.index("request_diff") > kinds.index("score"):
            return fail("score table published before request-diff table")
        if not doc.get("request_diff_published_before_scores"):
            return fail("receipt-flag-request-diff-first-absent")

    print(
        "SUCCESS:TST-0316-probe1 "
        f"empty={report['n_empty_diff']} diverged={report['n_diverged']} "
        f"both_states_fired={ctrl['bad_nonempty']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
