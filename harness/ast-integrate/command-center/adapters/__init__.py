"""Command-center execution adapters for external coding agents.

``codex``           attached / detached Codex CLI spawns with severed-stream
                    detection (BLD-0027, IMP-0421); its public surface is
                    re-exported here so ``from adapters import CodexAdapter``
                    and ``from adapters.codex import CodexAdapter`` agree.
``claude_adapter``  permission-bounded Claude tool adapter with catalog
                    timeouts; imported by dotted path only.
"""
from __future__ import annotations

from .codex import (
    CLASS_SEVERED_STREAM,
    STATE_FAILED,
    STATE_SEVERED,
    STATE_SUCCESS,
    STATE_TIMEOUT,
    CodexAdapter,
    DetachedInvocationError,
    SpawnRecord,
)

__all__ = [
    "CLASS_SEVERED_STREAM",
    "STATE_FAILED",
    "STATE_SEVERED",
    "STATE_SUCCESS",
    "STATE_TIMEOUT",
    "CodexAdapter",
    "DetachedInvocationError",
    "SpawnRecord",
    "claude_adapter",
    "codex",
]
