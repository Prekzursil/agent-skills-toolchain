"""GitHub Actions default: a job stops at the first failing step.

Later steps are skipped unless `if` contains always() or failure(), so a
red job conclusion hides those later failures. continue-on-error does not
stop the job but marks the step optional.
"""
from __future__ import annotations

from typing import Any


def _if_runs_after_failure(expr: Any) -> bool:
    text = str(expr or "").replace(" ", "").lower()
    return "always()" in text or "failure()" in text


def apply_first_failure(steps: list[dict[str, Any]], fail_at: int) -> list[dict[str, Any]]:
    """Simulate GHA skip-after-first-failure. fail_at is the failing step index."""
    out: list[dict[str, Any]] = []
    failed = False
    for i, step in enumerate(steps):
        if_expr = step.get("if")
        continue_on_error = bool(step.get("continue-on-error"))
        if failed and not _if_runs_after_failure(if_expr):
            row = dict(step)
            row["would_run"] = False
            row["skip_reason"] = "previous_step_failed"
            out.append(row)
            continue
        row = dict(step)
        row["would_run"] = True
        out.append(row)
        if i == fail_at and not continue_on_error:
            failed = True
    return out


def hidden_after_first_failure(steps: list[dict[str, Any]], fail_at: int) -> list[str]:
    sim = apply_first_failure(steps, fail_at)
    hidden = []
    for i, row in enumerate(sim):
        if not row.get("would_run"):
            hidden.append(str(row.get("name") or f"step-{i}"))
    return hidden
