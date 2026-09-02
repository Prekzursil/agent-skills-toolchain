"""Fan-in barrier role=local-runner."""
from __future__ import annotations

from agentspec.oracle import judge

FANIN_ROLE = "local-runner"


def consider(receipt_path, *, root=None, worker_exit_code: int = 0):
    del worker_exit_code
    return judge(receipt_path, root=root)


__all__ = ["FANIN_ROLE", "consider"]
