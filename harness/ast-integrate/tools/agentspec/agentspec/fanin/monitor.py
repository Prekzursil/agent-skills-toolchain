"""Fan-in barrier role=monitor."""
from __future__ import annotations

import agentspec.oracle

FANIN_ROLE = "monitor"


def consider(receipt_path, *, root=None, worker_exit_code: int = 0):
    del worker_exit_code
    return agentspec.oracle.judge(receipt_path, root=root)


__all__ = ["FANIN_ROLE", "consider"]
