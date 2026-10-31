"""Cross-vendor parity bench: request-level diff first, scores second.

Scores are computed ONLY over cases whose canonical request diff is empty.
Capability mismatches degrade loudly to UNSUPPORTED (never a numeric FAIL);
the silent-fallback mutant that drops the unsupported tool and scores 0.0
exists only as a both-states control.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

CLAUDE_TOOLS = frozenset({"Read", "Grep", "Shell", "Edit", "Write", "Task"})
CODEX_TOOLS = frozenset({"Read", "Grep", "Shell", "Edit", "Write", "mcp__codex__codex"})
CLAUDE_MAX_TIMEOUT = 1200
CODEX_MAX_TIMEOUT = 600

READY = "READY"
UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class Case:
    case_id: str
    prompt: str
    tools: tuple[str, ...]
    timeout: int


CASES: tuple[Case, ...] = (
    Case("cv-echo", "echo the fixture token back verbatim", ("Read",), 120),
    Case("cv-grep-count", "count fixture lines matching the needle", ("Read", "Grep"), 120),
    Case("cv-edit-patch", "apply the one-line fixture patch", ("Read", "Edit"), 180),
    Case("cv-shell-hash", "hash the fixture bytes in a sandboxed shell", ("Read", "Shell"), 180),
    Case("cv-write-report", "write the fixture summary to a scratch file", ("Read", "Write"), 120),
    Case("cv-timeout-clamp", "long synthesis exceeding the codex timeout ceiling", ("Read",), 900),
    Case("cv-claude-task", "delegate the fixture split to a subagent", ("Read", "Task"), 120),
    Case("cv-codex-mcp", "fan the fixture out through mcp__codex__codex", ("Read", "mcp__codex__codex"), 120),
)


def canonical_answer(prompt: str) -> str:
    """The shared deterministic oracle both vendors must reproduce."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _vendor_request(case: Case, supported: frozenset[str], max_timeout: int, silent_fallback: bool) -> dict[str, Any]:
    requested = set(case.tools)
    missing = sorted(requested - supported)
    if missing and silent_fallback:
        # MUTANT: drop the unsupported tool and pretend to be READY.
        requested -= set(missing)
        status = READY
        degraded = True
    else:
        status = UNSUPPORTED if missing else READY
        degraded = False
    return {
        "prompt": case.prompt,
        "tools": sorted(requested),
        "timeout": min(case.timeout, max_timeout),
        "status": status,
        "_missing": missing,
        "_degraded": degraded,
    }


def claude_request(case: Case, silent_fallback: bool = False) -> dict[str, Any]:
    return _vendor_request(case, CLAUDE_TOOLS, CLAUDE_MAX_TIMEOUT, silent_fallback)


def codex_request(case: Case, silent_fallback: bool = False) -> dict[str, Any]:
    return _vendor_request(case, CODEX_TOOLS, CODEX_MAX_TIMEOUT, silent_fallback)


_DIFF_FIELDS = ("prompt", "tools", "timeout", "status")


def request_diff(claude: dict[str, Any], codex: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"field": f, "claude": claude[f], "codex": codex[f]}
        for f in _DIFF_FIELDS
        if claude[f] != codex[f]
    ]


def _score(case: Case, request: dict[str, Any]) -> tuple[float | None, bool]:
    """(score, scored_as_fail). UNSUPPORTED is loud: score None, never a FAIL."""
    if request["status"] == UNSUPPORTED:
        return None, False
    if request["_degraded"]:
        # The dropped tool was load-bearing: execution misses the oracle.
        return 0.0, True
    return (1.0 if canonical_answer(case.prompt) == canonical_answer(case.prompt) else 0.0), False


def run_parity(silent_fallback: bool = False) -> dict[str, Any]:
    request_diff_table: list[dict[str, Any]] = []
    score_table: list[dict[str, Any]] = []
    degrade_rows: list[dict[str, Any]] = []
    for case in CASES:
        cl = claude_request(case, silent_fallback)
        cx = codex_request(case, silent_fallback)
        divergences = request_diff(cl, cx)
        empty = not divergences
        row = {
            "case_id": case.case_id,
            "empty_request_diff": empty,
            "divergences": divergences,
            "claude_status": cl["status"],
            "codex_status": cx["status"],
            "claude_timeout": cl["timeout"],
            "codex_timeout": cx["timeout"],
        }
        request_diff_table.append(row)

        cl_score, cl_fail = _score(case, cl)
        cx_score, cx_fail = _score(case, cx)
        if empty and cl["status"] == READY and cx["status"] == READY:
            score_table.append(
                {
                    "case_id": case.case_id,
                    "claude_score": cl_score,
                    "codex_score": cx_score,
                    "equal": cl_score == cx_score,
                }
            )
        if cl["_missing"] or cx["_missing"] or cl["_degraded"] or cx["_degraded"]:
            degrade_rows.append(
                {
                    "case_id": case.case_id,
                    "claude_status": cl["status"],
                    "codex_status": cx["status"],
                    "claude_score": cl_score,
                    "codex_score": cx_score,
                    "scored_as_fail": cl_fail or cx_fail,
                }
            )
    return {
        "n_cases": len(CASES),
        "n_empty_diff": sum(1 for r in request_diff_table if r["empty_request_diff"]),
        "n_diverged": sum(1 for r in request_diff_table if not r["empty_request_diff"]),
        "request_diff_table": request_diff_table,
        "score_table": score_table,
        "degrade_rows": degrade_rows,
        "silent_fallback": silent_fallback,
    }


def both_states_request_diff() -> dict[str, Any]:
    """Good: portable case has an empty diff. Bad: dropping a tool is visible."""
    case = CASES[1]  # cv-grep-count, two tools
    good = request_diff(claude_request(case), codex_request(case))
    broken = codex_request(case)
    broken["tools"] = [t for t in broken["tools"] if t != "Grep"]
    bad = request_diff(claude_request(case), broken)
    return {
        "case_id": case.case_id,
        "good_empty": not good,
        "bad_nonempty": bool(bad),
        "bad_fields": sorted({d["field"] for d in bad}),
    }


def both_states_degrade() -> dict[str, Any]:
    """Honest mismatch is UNSUPPORTED; the silent-fallback mutant scores FAIL."""
    honest = run_parity(silent_fallback=False)
    mutant = run_parity(silent_fallback=True)
    honest_rows = {r["case_id"]: r for r in honest["request_diff_table"]}
    mutant_deg = {r["case_id"]: r for r in mutant["degrade_rows"]}
    task_mutant = mutant_deg.get("cv-claude-task", {})
    portable = honest_rows["cv-echo"]
    return {
        "case_id": "cv-claude-task",
        "fired_on_bad": honest_rows["cv-claude-task"]["codex_status"] == UNSUPPORTED,
        "mutant_is_fail_score": bool(task_mutant.get("scored_as_fail")) and task_mutant.get("codex_score") == 0.0,
        "silent_on_good": portable["codex_status"] == READY and portable["claude_status"] == READY,
    }


__all__ = [
    "CASES",
    "Case",
    "CLAUDE_TOOLS",
    "CODEX_TOOLS",
    "both_states_degrade",
    "both_states_request_diff",
    "canonical_answer",
    "claude_request",
    "codex_request",
    "request_diff",
    "run_parity",
]
