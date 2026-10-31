#!/usr/bin/env python3
"""CNF-0191 supporting refusal filter (wave-2 reconstruction).

Keyword rules reconstructed from the receipt's recorded rule table. The filter
runs on the COMMAND STRING only, before any subprocess — structural
refuse-before-exec. Returns the rule name, or None when the command is
execution-eligible.
"""
from __future__ import annotations


def classify(command: str):
    c = command.strip()
    low = c.lower()
    if "git clone" in low:
        return "git-clone"
    if low.startswith("claude ") or low.startswith("claude\t"):
        return "claude-config"
    if "git-crypt" in low:
        return "git-crypt"
    if "npm install" in low:
        return "npm-install"
    if "pip install" in low:
        return "pip-install"
    if "uvx " in low:
        return "uvx-network"
    if "close.py" in low and "--list" not in low:
        return "mutating-close"
    if "render.py" in low and "--check" not in low:
        return "mutating-render"
    if "seed.py" in low:
        return "mutating-seed"
    if low.startswith(("git ", "git\t")) and "stash" in low:
        return "destructive-git-stash"
    if low.startswith(("git ", "git\t")) and "checkout" in low:
        return "destructive-git-checkout"
    return None
