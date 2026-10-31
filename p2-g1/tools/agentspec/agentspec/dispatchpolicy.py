"""PRE-DISPATCH POLICY — the checks that must pass before a rail is touched at all.

MEASURED FAILURES:

* **Fire-and-forget on an awaited unit.** Three Codex-backed subagents produced zero artifacts:
  each returned a "started in the background as task-…" receipt, the barrier waiting on them
  read that as the answer, and the real work then completed on disk and was discarded unread. A
  backgrounded job's result is structurally unreachable to its barrier.
* **No explicit timeout.** A silent default timeout is what a caller rationalised
  ``--background`` to escape, so a dispatch must state its own bound.

The rule is scoped, not blanket: backgrounding a dispatch that NOTHING awaits is legitimate, and
there is a detector control asserting this function stays silent in that case.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentspec import wire

DISPATCH_VIOLATIONS: tuple[str, ...] = (
    "background-on-awaited-dispatch",
    "missing-timeout",
    "nonpositive-timeout",
)


def check_dispatch(
    *, background: bool, timeout_s: int | None, awaited: bool
) -> tuple[str, ...]:
    """Return the sorted violations for a proposed dispatch; empty means go ahead."""
    if timeout_s is not None:
        wire.require_wire_integer(timeout_s, "timeout_s")
    found: list[str] = []
    if background and awaited:
        found.append("background-on-awaited-dispatch")
    if timeout_s is None:
        found.append("missing-timeout")
    elif timeout_s <= 0:
        found.append("nonpositive-timeout")
    return wire.sorted_wire(found)


@dataclass
class DryRunPlan:
    workflow_id: str
    routing: list[dict]
    params: dict
    cardinality: list[dict]
    cost: dict
    planned_units: list[dict]
    spawn_count: int = 0
    egress_count: int = 0


def dry_run(workflow: dict, params: dict | None = None, ports=None) -> DryRunPlan:
    """Resolve routing/params/cardinality/cost without spawning or egress."""
    params = dict(params or {})
    units = list(workflow.get("units") or [])
    vendor = {"opus": "anthropic", "sonnet": "anthropic", "codex": "openai"}
    routing: list[dict] = []
    for unit in units:
        rail = str((unit.get("routing") or {}).get("rail") or "sonnet")
        routing.append(
            {
                "id": unit.get("id"),
                "rail": rail,
                "vendor": vendor.get(rail, "unknown"),
                "model": rail,
            }
        )
    bound: dict = {}
    for spec in workflow.get("params") or []:
        pid = spec.get("id")
        if pid in params:
            val = params[pid]
        else:
            val = spec.get("default")
        if spec.get("kind") == "secret_ref":
            if isinstance(val, dict):
                merged = dict(val)
                merged.setdefault("kind", "secret_ref")
                val = merged
            else:
                val = {"kind": "secret_ref", "value": val}
        bound[pid] = val
    card: list[dict] = []
    for node in workflow.get("nodes") or []:
        if node.get("type") == "fan_out":
            n = len(node.get("unit_ids") or [])
            max_c = int(node.get("max_cardinality") or n)
            card.append(
                {
                    "id": node.get("id"),
                    "width": n,
                    "max_cardinality": max_c,
                }
            )
    cost = {
        "unit_count": len(units),
        "total_micro_usd": max(1, len(units) * 25),
    }
    if ports is not None:
        # Dry-run must not spawn or egress. Ports stay at zero.
        pass
    return DryRunPlan(
        workflow_id=str(workflow.get("id") or ""),
        routing=routing,
        params=bound,
        cardinality=card,
        cost=cost,
        planned_units=units,
        spawn_count=0,
        egress_count=0,
    )
