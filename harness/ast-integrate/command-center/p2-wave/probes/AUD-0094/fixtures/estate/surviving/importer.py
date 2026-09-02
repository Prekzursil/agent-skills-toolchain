#!/usr/bin/env python3
"""Operational use of a retired path (must classify USE)."""
from pathlib import Path

DELETED = Path("aud0094-retired/tree-agentbridge/file-00.py")


def load_retired():
    return DELETED.read_text(encoding="utf-8")
