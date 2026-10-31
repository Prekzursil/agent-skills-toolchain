"""Process/memory guard that never kills a shared supervisor."""
from __future__ import annotations

from typing import Any

SHARED_NAMES = ("MCPAgentMailSupervisor", "basic-memory", "sshd")


def is_shared(proc: dict[str, Any]) -> bool:
    name = str(proc.get("name") or proc.get("comm") or "")
    return any(s.lower() in name.lower() for s in SHARED_NAMES)


def would_kill(proc: dict[str, Any], *, rss_limit: int) -> bool:
    if is_shared(proc):
        return False
    rss = int(proc.get("rss") or 0)
    return rss > rss_limit
