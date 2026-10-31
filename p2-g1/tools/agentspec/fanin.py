"""Re-export inner agentspec.fanin when `tools` is on PYTHONPATH."""
from __future__ import annotations

from agentspec.agentspec.fanin import CONSIDER_FNS, EXPECTED_ROLES

__all__ = ["CONSIDER_FNS", "EXPECTED_ROLES"]
