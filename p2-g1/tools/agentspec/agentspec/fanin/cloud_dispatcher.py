"""Fan-in barrier role=cloud-dispatcher."""
from __future__ import annotations

from agentspec.oracle import judge as rc

FANIN_ROLE = "cloud-dispatcher"


def consider(receipt_path, *, root=None, worker_exit_code: int = 0):
    del worker_exit_code
    return rc(receipt_path, root=root)


__all__ = ["FANIN_ROLE", "consider"]
