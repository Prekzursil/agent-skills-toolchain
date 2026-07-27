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
