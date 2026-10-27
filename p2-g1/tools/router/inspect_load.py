"""Independent instrument for load_mode. IMP-0387."""
from __future__ import annotations

ALWAYS_ON = "ALWAYS-ON"
LAZY = "LAZY"


def inspect_load_mode(text: str) -> str:
    if not text.startswith("---"):
        return ALWAYS_ON
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ALWAYS_ON
    block = parts[1]
    if "paths:" in block and "**/*" in block:
        return LAZY
    return ALWAYS_ON
