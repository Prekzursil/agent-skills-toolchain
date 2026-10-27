"""Fan-in barrier role=workflow-fan-in."""
from __future__ import annotations

from ..oracle import judge

FANIN_ROLE = "workflow-fan-in"


def consider(receipt_path, *, root=None, worker_exit_code: int = 0):
    del worker_exit_code
    return judge(receipt_path, root=root)


__all__ = ["FANIN_ROLE", "consider"]
