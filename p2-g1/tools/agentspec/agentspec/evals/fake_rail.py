"""An in-process FAKE agent rail: scripted responses, injected clock, zero I/O.

This is what keeps the eval suite hermetic. It never opens a socket, never spawns a process and
never reads a real clock — ``wall_ms`` comes from the injected
:class:`~agentspec.clock.SteppableClock`, so two runs of the same script agree byte-for-byte,
which is what makes the determinism row (R8) checkable at all.

It also ENFORCES the pre-dispatch policy rather than merely reporting it: a backgrounded awaited
dispatch, or a dispatch with no timeout, raises :class:`DispatchRefused` and is not recorded. An
unscripted call raises instead of inventing a plausible result — a fake that improvises is how a
green suite ends up measuring nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agentspec.argv import ArgvPlan
from agentspec.clock import SteppableClock
from agentspec.dispatchpolicy import check_dispatch
from agentspec.oracle import RailResult


class DispatchRefused(ValueError):
    """The proposed dispatch broke the pre-dispatch policy, so nothing was launched."""

    reason = "policy-violation"

    def __init__(self, violations: tuple[str, ...]) -> None:
        super().__init__(f"policy-violation: {list(violations)}")
        self.violations = violations


class ScriptExhausted(LookupError):
    """The fake was asked for a response it was not scripted to give."""

    reason = "spawn-failed"


@dataclass(frozen=True, slots=True)
class ScriptedResponse:
    """One scripted rail answer. ``wall_ms_delta`` advances the INJECTED clock."""

    exit_code: int
    receipt: bytes | None
    progress: str = ""
    wall_ms_delta: int = 0


@dataclass(frozen=True, slots=True)
class DispatchRecord:
    """What the rail was actually asked to run — the evidence an eval asserts against."""

    unit_id: str
    argv: tuple[str, ...]
    stdin_payload: str | None
    timeout_s: int
    attempt: int
    awaited: bool


HERMETIC_CAPS: frozenset[str] = frozenset(
    {
        "structure-walk",
        "param-bind",
        "gate-eval",
        "loop-bound",
        "local-receipt-write",
        "stopping-rule",
    }
)

#: Capabilities NO in-process fake can honestly emulate, ever. ``execute_node``
#: refuses these by name even when ``can_honestly_emulate`` has been overridden
#: to lie — a fake that improvises a live-model receipt measures nothing.
NEVER_EMULATABLE: frozenset[str] = frozenset(
    {
        "live-model-infer",
        "owner-interactive",
        "network-egress",
        "real-spawn",
    }
)


class UnemulatableCapability(RuntimeError):
    """A node demanded a capability the hermetic rail refuses to fake."""

    def __init__(self, capabilities: Sequence[str], node_id: str = "") -> None:
        caps = tuple(capabilities)
        super().__init__(
            f"unemulatable capabilities {list(caps)} on node {node_id!r}; "
            "refusing to fake a receipt"
        )
        self.capabilities = caps
        self.node_id = node_id


class FakeRail:
    """A scripted rail. Its only state is the consumed-response cursor and the call log."""

    __slots__ = (
        "_calls",
        "_clock",
        "_cursor",
        "_policy",
        "_script",
        "egress_count",
        "spawn_count",
    )

    def __init__(
        self,
        *,
        script: Mapping[str, Sequence[ScriptedResponse]] | None = None,
        clock: SteppableClock | None = None,
        policy: Callable[..., Any] = check_dispatch,
    ) -> None:
        """``policy`` is injected so a mutation test can neuter it and watch the rail LAUNCH a
        forbidden dispatch — otherwise the "the rail refused it" arm is unreachable and would
        need a coverage pragma, i.e. an untested guard."""
        from agentspec.clock import FixedClock

        self._script = {unit: tuple(responses) for unit, responses in (script or {}).items()}
        self._clock = clock if clock is not None else FixedClock()
        self._policy = policy
        self._cursor: dict[str, int] = {}
        self._calls: list[DispatchRecord] = []
        self.spawn_count = 0
        self.egress_count = 0

    # --- hermetic node-simulation surface (IMP-0199) -------------------------

    def can_honestly_emulate(self, capability: str) -> bool:
        """Only structural, local, deterministic capabilities are emulatable."""
        return capability in HERMETIC_CAPS

    def unemulatable_in(self, workflow: Mapping[str, Any]) -> list[str]:
        """Capability names in ``workflow`` this rail cannot honestly emulate."""
        out: set[str] = set()
        for node in workflow.get("nodes") or []:
            for cap in node.get("capabilities") or []:
                if not self.can_honestly_emulate(str(cap)):
                    out.add(str(cap))
        return sorted(out)

    def execute_node(
        self,
        node: Mapping[str, Any],
        *,
        predecessors: Mapping[str, Any] | None = None,
        step: int = 0,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Emulate ONE node, or refuse by capability name.

        Defense in depth: capabilities in :data:`NEVER_EMULATABLE` are refused
        even when ``can_honestly_emulate`` (possibly overridden) claims them.
        """
        caps = [str(c) for c in (node.get("capabilities") or [])]
        refused = [
            c
            for c in caps
            if c in NEVER_EMULATABLE or not self.can_honestly_emulate(c)
        ]
        if refused:
            raise UnemulatableCapability(refused, node_id=str(node.get("id") or ""))
        return {
            "node": str(node.get("id") or ""),
            "kind": str(node.get("kind") or "unit"),
            "capabilities": caps,
            "step": int(step),
            "params": dict(params or {}),
            "predecessors": sorted((predecessors or {}).keys()),
            "ok": True,
            "emulated": True,
        }

    @property
    def calls(self) -> tuple[DispatchRecord, ...]:
        """Every dispatch that was actually launched, in order."""
        return tuple(self._calls)

    def dispatch(
        self,
        *,
        unit_id: str,
        plan: ArgvPlan,
        timeout_s: int | None,
        awaited: bool,
        background: bool = False,
        attempt: int = 1,
    ) -> RailResult:
        """Run one scripted dispatch, or refuse it.

        ``timeout_s`` has no default: "no dispatch without an explicit timeout" is a regression
        row, so the signature itself demands one.
        """
        violations: tuple[str, ...] = tuple(
            self._policy(background=background, timeout_s=timeout_s, awaited=awaited)
        )
        if violations:
            raise DispatchRefused(violations)

        response = self._next_response(unit_id)
        self._calls.append(
            DispatchRecord(
                unit_id=unit_id,
                argv=plan.argv,
                stdin_payload=plan.stdin_payload,
                timeout_s=timeout_s if timeout_s is not None else 0,
                attempt=attempt,
                awaited=awaited,
            )
        )
        start_ms = self._clock.now_ms()
        end_ms = self._clock.advance(response.wall_ms_delta)
        return RailResult(
            exit_code=response.exit_code,
            receipt_bytes=response.receipt,
            progress=response.progress,
            wall_ms=end_ms - start_ms,
        )

    def _next_response(self, unit_id: str) -> ScriptedResponse:
        responses = self._script.get(unit_id)
        if responses is None:
            raise ScriptExhausted(f"no script for unit {unit_id!r}")
        index = self._cursor.get(unit_id, 0)
        if index >= len(responses):
            raise ScriptExhausted(
                f"script for unit {unit_id!r} is exhausted after {len(responses)} response(s)"
            )
        self._cursor[unit_id] = index + 1
        return responses[index]
