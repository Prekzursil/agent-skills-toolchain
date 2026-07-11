"""Pure auto-attach decision logic (grill G-4).

The auto-attach hook is the riskiest, most harness-coupled component, so its
logic is factored into pure, side-effect-free functions here and a thin I/O
shell in :mod:`hooks.posttool`. Every rule the grill demands lives in a testable
function:

* **60s threshold** — a background op must have been running at least
  :data:`ATTACH_THRESHOLD_S` before it is worth watching (trivial ops never
  attach).
* **whitelist-scoped** — only op *kinds* in the whitelist are candidates, so a
  normal foreground tool call is never auto-attached.
* **kill-switch** — a single flag hard-disables attachment (the operator escape
  hatch); it wins over every other rule.
* **dedup** — an op already attached (its :func:`dedup_key` is in the ``seen``
  set) is never attached twice, so re-fired PostToolUse events cost nothing.

:func:`should_attach` is the bare four-input predicate the grill names;
:func:`decide` layers dedup on top and returns an :class:`AttachDecision` that
also carries the *reason* (for observability / the §4 terminal-state marker).
"""

from __future__ import annotations

from dataclasses import dataclass

# An op must have run at least this long before it is worth auto-attaching a
# watch — below this it is a trivial op and attaching would be pure noise.
ATTACH_THRESHOLD_S = 60.0

# Op kinds that are long-task shaped: a detached background shell, a `longrun`
# wrapper, or a workflow/subagent dispatch. A foreground tool call is NEVER in
# this set, so it can never be auto-attached (over-attach guard, grill G-4).
DEFAULT_WHITELIST: frozenset[str] = frozenset(
    {"bash-background", "longrun", "workflow"}
)

# The single reason string that means "attach" — every other value is a
# rejection reason (used by the shell's terminal-state marker).
_ATTACH = "attach"


@dataclass(frozen=True)
class AttachOp:
    """A background op that a PostToolUse event surfaced as attach-worthy.

    ``log_path`` is the file the auto-registered task will tail; ``elapsed_s`` is
    how long the op has been running (the threshold input).
    """

    op_id: str
    op_kind: str
    elapsed_s: float
    log_path: str


@dataclass(frozen=True)
class AttachDecision:
    """The verdict for one op: whether to attach, and why (or why not)."""

    attach: bool
    reason: str
    key: str

    def to_dict(self) -> dict[str, object]:
        return {"attach": self.attach, "reason": self.reason, "key": self.key}


def dedup_key(op: AttachOp) -> str:
    """Stable identity for an op — the dedup key held in the ``seen`` set."""
    return f"{op.op_kind}:{op.op_id}"


def _gate_reason(
    op_kind: str,
    elapsed_s: float,
    whitelist: frozenset[str],
    killswitch: bool,
    threshold_s: float,
) -> str:
    """Apply the kill-switch → threshold → whitelist gate, first failure wins."""
    if killswitch:
        return "killswitch"
    if elapsed_s < threshold_s:
        return "below-threshold"
    if op_kind not in whitelist:
        return "not-whitelisted"
    return _ATTACH


def should_attach(
    op_kind: str,
    elapsed_s: float,
    whitelist: frozenset[str],
    killswitch: bool,
    *,
    threshold_s: float = ATTACH_THRESHOLD_S,
) -> bool:
    """The bare grill predicate: attach this op-kind at this elapsed time?

    ``True`` only when the kill-switch is off, ``elapsed_s`` has crossed
    ``threshold_s``, and ``op_kind`` is whitelisted. Dedup is intentionally NOT
    part of this predicate (it needs the seen-set) — see :func:`decide`.
    """
    return (
        _gate_reason(op_kind, elapsed_s, whitelist, killswitch, threshold_s) == _ATTACH
    )


def decide(
    op: AttachOp,
    *,
    whitelist: frozenset[str] = DEFAULT_WHITELIST,
    killswitch: bool = False,
    seen: frozenset[str] | set[str] = frozenset(),
    threshold_s: float = ATTACH_THRESHOLD_S,
) -> AttachDecision:
    """Full attach verdict for ``op``: the :func:`should_attach` gate + dedup.

    Returns an :class:`AttachDecision` whose ``reason`` is ``"attach"`` on the
    green path, or one of ``killswitch`` / ``below-threshold`` /
    ``not-whitelisted`` / ``duplicate`` when rejected.
    """
    key = dedup_key(op)
    reason = _gate_reason(op.op_kind, op.elapsed_s, whitelist, killswitch, threshold_s)
    if reason != _ATTACH:
        return AttachDecision(attach=False, reason=reason, key=key)
    if key in seen:
        return AttachDecision(attach=False, reason="duplicate", key=key)
    return AttachDecision(attach=True, reason=_ATTACH, key=key)
