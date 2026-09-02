"""Single permission choke point for CNF-0040.

Every capability request must call `evaluate()` (via Gate.require / Gate.try_require).
A permission that is not in the granted set is a deny. The gate never grants
silently. Silent degradation is a SUBJECT behaviour (ignore a deny and still
report success), which probe2 is written to catch.
"""
from __future__ import annotations

from typing import Iterable

EVALUATE_CALLS = 0


class PermissionDenied(Exception):
    def __init__(self, tool: str, granted: Iterable[str]) -> None:
        self.tool = tool
        self.granted = tuple(sorted(granted))
        self.message = (
            f"PERMISSION DENIED: {tool} is not in the granted set "
            f"{list(self.granted)}"
        )
        super().__init__(self.message)


class OverPrivileged(Exception):
    def __init__(self, extra: Iterable[str], spawns: int) -> None:
        self.extra = tuple(sorted(extra))
        self.spawns = spawns
        self.message = (
            f"OVER-PRIVILEGED: requested tools not in declaration: "
            f"{list(self.extra)}; spawns={spawns}"
        )
        super().__init__(self.message)


def evaluate(requested: str, granted: frozenset[str]) -> str:
    """THE choke point. Returns 'allow' or 'deny'. No other evaluator exists."""
    global EVALUATE_CALLS
    EVALUATE_CALLS += 1
    if not requested:
        return "deny"
    if requested in granted:
        return "allow"
    return "deny"


class Gate:
    def __init__(self, granted: Iterable[str]) -> None:
        self.granted = frozenset(granted)
        self.log: list[dict] = []
        self.spawns = 0
        self.requested: list[str] = []

    def _record(self, tool: str, decision: str) -> None:
        self.requested.append(tool)
        self.log.append({"tool": tool, "decision": decision})

    def require(self, tool: str) -> None:
        decision = evaluate(tool, self.granted)
        self._record(tool, decision)
        if decision != "allow":
            raise PermissionDenied(tool, self.granted)

    def try_require(self, tool: str) -> bool:
        """Soft check used only by the silent-degradation mutant subject."""
        decision = evaluate(tool, self.granted)
        self._record(tool, decision)
        return decision == "allow"

    def dispatch(self, requested_tools: Iterable[str], declared: Iterable[str]) -> None:
        """IMP-0136: refuse over-privileged units BEFORE spawn."""
        self.require("Bash")
        extra = set(requested_tools) - set(declared)
        if extra:
            raise OverPrivileged(extra, spawns=self.spawns)
        self.spawns += 1

    def dispatch_after_spawn(
        self, requested_tools: Iterable[str], declared: Iterable[str]
    ) -> None:
        """Known-broken mutant: spawn first, then check. Detector must go red."""
        self.require("Bash")
        self.spawns += 1
        extra = set(requested_tools) - set(declared)
        if extra:
            raise OverPrivileged(extra, spawns=self.spawns)
