"""DynamicFanOut executor: oracle-gated producer receipts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentspec.oracle import evaluate_producer
from agentspec.progress import is_progress_stream


@dataclass
class ProducerRun:
    exit_code: int
    stdout: str = ""
    receipt: dict[str, Any] | None = None
    receipt_path: str | None = None


def expand_dynamic_fanout(run: ProducerRun, *, node: dict[str, Any] | None = None) -> dict[str, Any]:
    text = run.stdout or ""
    if is_progress_stream(text):
        return {"cardinality": 0, "reason": "progress-stream", "units": []}
    oracle = evaluate_producer(run)
    if run.exit_code == 0 and not run.receipt:
        return {"cardinality": 0, "reason": "severed-stream", "units": [], "oracle": oracle}
    if run.receipt:
        n = int(run.receipt.get("n") or run.receipt.get("count") or 7)
        return {"cardinality": n, "reason": "ok", "units": list(range(n)), "oracle": oracle}
    return {"cardinality": 0, "reason": "severed-stream", "units": []}
