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


def expand_dynamic_fanout(
    run: ProducerRun, *, node: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Expand a DynamicFanOut only after the producer receipt passes the shared oracle.

    IMP-0219: exit code zero alone is never success (:10646). A missing receipt, a
    progress stream (phrase/line level OR a JSON body carrying PROGRESS/RUNNING markers)
    and any oracle-refused producer expand to ZERO units.

    ``reason`` is the FAMILY string (``severed-stream``) so consumers matching the
    taxonomy never see a progress body expand; the fine cause rides in ``fine_reason``
    and ``oracle.reason`` (oracle.py: reason is the fine cause, the severed flag is the
    family for consumers).
    """
    text = run.stdout or ""
    oracle = evaluate_producer(run)
    if is_progress_stream(text):
        return {
            "cardinality": 0,
            "reason": "severed-stream",
            "fine_reason": "progress-stream",
            "units": [],
            "oracle": oracle,
        }
    if not oracle.get("ok"):
        fine = str(oracle.get("reason") or "severed-stream")
        return {
            "cardinality": 0,
            "reason": "severed-stream",
            "fine_reason": fine,
            "units": [],
            "oracle": oracle,
        }
    if run.receipt:
        n = int(run.receipt.get("n") or run.receipt.get("count") or 7)
        return {"cardinality": n, "reason": "ok", "units": list(range(n)), "oracle": oracle}
    return {
        "cardinality": 0,
        "reason": "severed-stream",
        "fine_reason": "missing-receipt",
        "units": [],
        "oracle": oracle,
    }
