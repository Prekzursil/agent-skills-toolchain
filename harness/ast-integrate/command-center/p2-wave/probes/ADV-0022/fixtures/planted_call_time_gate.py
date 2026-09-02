"""PLANTED both-states control for ADV-0022 probe 2.

This file is NOT a production host. Probe 2 must classify it as call-time
enforcement because evaluate_request runs before subprocess.run. Production
trees under tools/ and hooks/ must not match this pattern.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ARC = Path(__file__).resolve().parents[2] / "ARC-0081"
if str(_ARC) not in sys.path:
    sys.path.insert(0, str(_ARC))

from model import evaluate_request, pset, req, stmt  # noqa: E402


def gated_spawn(argv: list[str]) -> subprocess.CompletedProcess[str]:
    declared = pset("planted-narrow", stmt("grant", "tool", "Read"))
    decision = evaluate_request(declared, req("subprocess", "python3"))
    if decision["outcome"] != "GRANT":
        raise PermissionError(decision.get("reason") or "closed-world-default")
    return subprocess.run(argv, capture_output=True, text=True, timeout=5)
