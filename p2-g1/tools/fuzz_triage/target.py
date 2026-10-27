"""Fuzz target entry used by ADV-0041 runtime error rendering."""
from __future__ import annotations

from .engine import TARGET_FILE, execute_tracked

__all__ = ["TARGET_FILE", "execute"]


def execute(data: bytes):
    """Run one payload. Crash renders must not embed TARGET_FILE."""
    return execute_tracked(bytes(data))
