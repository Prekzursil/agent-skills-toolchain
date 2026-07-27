"""Token / RAM impact preview for a plan -- honest about "not measured".

The one rule this module enforces everywhere: **an unmeasured cost renders as
``-``/``null``, never as ``0``.** "We did not measure this server" and "this server
costs nothing" are different facts, and collapsing them turns a budget preview into a
confident lie. Every aggregate therefore carries the list of names it could not
account for, and a delta over an incomplete set is explicitly marked ``partial``.

Two axes, deliberately NOT fused into one score
-----------------------------------------------
On this box, tokens and memory are ANTI-CORRELATED:

* ``cloud-hub``      -- 409 tools, **77,198 tokens**, but only **17 MB** commit.
* ``chrome-devtools`` -- 29 tools, **331 MB** commit.

Provenance of those two figures, stated because this module exists to make provenance
explicit: they are INHERITED from the budgeting scout run of 2026-07-27, not measured by
the work unit that wrote this file, and the ledger directory meant to hold the raw
artifact is empty. They were independently corroborated during review via
``Win32_Process``/``PagedMemorySize64`` (16.3-16.9 MB and ~320 MB respectively), i.e.
within 3-6% and conservative. See ``tests/test_impact.py`` for the full note.

A single blended "cost" number would recommend disabling exactly the wrong server, so
:class:`Impact` reports two independent deltas and the renderer shows two columns.

Measured facts encoded here
---------------------------
* **Token cost is exactly measurable** (Anthropic ``count_tokens`` over the server's
  real ``tools/list``), and per-server costs are **exactly additive** -- the
  overhead-corrected prediction matched the measurement with error 0 across two
  multi-server combinations. So summing per-server deltas carries no modelling error.
* :data:`TOOL_BLOCK_OVERHEAD_TOKENS` (496) is charged **once per request**, not per
  server. It is credited only when a plan removes the LAST tool-bearing server.
* **The cheap proxies are bad.** Tokens-per-tool spans 75.8 -> 945.0 (12.5x) and
  bytes-per-token 2.82 -> 6.24 (2.2x). A proxy-derived number is reported with its
  :class:`TokenBasis` attached -- on :class:`Impact` itself, in ``to_dict()``, in the
  text renderer and in the GUI -- so it can never be mistaken for a measurement. The
  aggregate carries the WEAKEST contributing basis (:func:`weakest_basis`), because a
  sum of one exact and one guessed number is a guess. A ``token_cost`` supplied with
  NO ``token_basis`` has unknown provenance and is therefore NOT summed at all: it is
  counted as unmeasured, which forces ``partial`` and names the server.
* **Deferred tool loading changes the arithmetic by ~14x** (cloud-hub 77,198 eager vs
  5,370 deferred). The regime is an explicit input, never assumed.
* **RAM is saved only at the NEXT session start**, and only when the disable lands in
  a scope MEASURED to prevent the spawn (:data:`~mcpapply.plan.SPAWN_PREVENTING`).
  Root ``disabledMcpServers`` hides the tools but the process still spawns.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from mcpapply.plan import SPAWN_PREVENTING, Intent, Op, Plan

__all__ = [
    "Cost",
    "Impact",
    "Regime",
    "TOOL_BLOCK_OVERHEAD_TOKENS",
    "TokenBasis",
    "preview",
    "regime_from_env",
    "render_impact",
    "weakest_basis",
]

#: The constant tool-use preamble, measured by difference: a request with no tools
#: costs 8 tokens, one trivial tool 531, two trivial tools 558 -- so a trivial tool is
#: 27 and the fixed block is 496. Charged ONCE for the whole request.
TOOL_BLOCK_OVERHEAD_TOKENS = 496


class TokenBasis(str, Enum):
    """How a token number was arrived at. Always rendered next to the number."""

    #: Anthropic ``count_tokens`` over the server's real tool schemas. Exact.
    EXACT = "exact-count-tokens"
    #: Derived from schema byte size. Spread 2.2x -- an estimate, not a measurement.
    SCHEMA_BYTES = "schema-bytes-proxy"
    #: Derived from tool count. Spread 12.5x -- the worst proxy; use only as a hint.
    TOOL_COUNT = "tool-count-proxy"
    #: No number available -- or a number whose provenance was never declared.
    NOT_MEASURED = "not-measured"

    @property
    def is_proxy(self) -> bool:
        """True for a basis that estimates rather than measures."""
        return self in (TokenBasis.SCHEMA_BYTES, TokenBasis.TOOL_COUNT)


#: How much a basis can be trusted, weakest LAST. An aggregate is only as good as its
#: worst contributor, so :func:`preview` reports the maximum of this ordering.
_BASIS_RANK: Mapping[TokenBasis, int] = {
    TokenBasis.EXACT: 0,
    TokenBasis.SCHEMA_BYTES: 1,
    TokenBasis.TOOL_COUNT: 2,
    TokenBasis.NOT_MEASURED: 3,
}


def weakest_basis(bases: Iterable[TokenBasis]) -> TokenBasis:
    """The least trustworthy basis in ``bases``; :attr:`TokenBasis.EXACT` when empty.

    A sum of one exact and one proxy number is a PROXY number. Reporting the strongest
    contributor -- or, as this module previously did, reporting nothing at all -- is
    how a guessed figure passes as a measurement.
    """
    return max(bases, key=lambda b: _BASIS_RANK[b], default=TokenBasis.EXACT)


class Regime(str, Enum):
    """Whether tool schemas are loaded eagerly or fetched on demand."""

    EAGER = "eager"
    DEFERRED = "deferred"
    UNKNOWN = "unknown"


def regime_from_env(enable_tool_search: str | None) -> Regime:
    """Classify the loading regime from an ``ENABLE_TOOL_SEARCH`` value.

    Passed in rather than read from the process environment so the module stays pure
    and both regimes are exercised without mutating global state.
    """
    if enable_tool_search is None or enable_tool_search.strip() == "":
        return Regime.UNKNOWN
    value = enable_tool_search.strip().lower()
    if value in ("0", "false", "off", "no"):
        return Regime.EAGER
    return Regime.DEFERRED


@dataclass(frozen=True)
class Cost:
    """One server's measured cost. Every field may be ``None`` = NOT MEASURED."""

    tool_count: int | None = None
    token_cost: int | None = None
    token_basis: TokenBasis = TokenBasis.NOT_MEASURED
    #: Private commit (pagefile) bytes for the whole process SUBTREE, at rest.
    #: Commit -- not RSS: RSS varied 1.4x-56.8x for the SAME server across four hosts
    #: while commit held to +/-2%, and one server showed RSS 2.6 MB against 165 MB
    #: commit (63x). An RSS-based preview would understate it by that factor.
    commit_bytes: int | None = None
    proc_count: int | None = None
    #: True for an http/sse server: there is no local process, so memory is not
    #: "unmeasured" -- it is not applicable. Distinct from ``None``.
    remote: bool = False
    measured_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "tool_count": self.tool_count,
            "token_cost": self.token_cost,
            "token_basis": self.token_basis.value,
            "commit_bytes": self.commit_bytes,
            "proc_count": self.proc_count,
            "remote": self.remote,
            "measured_at": self.measured_at,
        }


@dataclass(frozen=True)
class Impact:
    """The aggregate preview for one plan."""

    regime: Regime
    #: Tokens no longer sent per request. ``None`` = nothing measurable at all.
    token_delta: int | None = None
    #: How :attr:`token_delta` was arrived at -- the WEAKEST basis that fed it. Always
    #: rendered next to the number, so a proxy can never pass as a measurement.
    token_basis: TokenBasis = TokenBasis.NOT_MEASURED
    #: Commit bytes not allocated by a NEW session. ``None`` = nothing measurable.
    commit_delta: int | None = None
    #: Names whose cost was unavailable. Non-empty => every delta is a LOWER BOUND.
    unmeasured: tuple[str, ...] = ()
    #: Names counted for tokens but explicitly credited ZERO memory, with the reason.
    no_ram_saving: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        """True when at least one affected server had no cost record."""
        return bool(self.unmeasured)

    def to_dict(self) -> dict[str, object]:
        return {
            "regime": self.regime.value,
            "token_delta": self.token_delta,
            "token_basis": self.token_basis.value,
            "commit_delta": self.commit_delta,
            "partial": self.partial,
            "unmeasured": list(self.unmeasured),
            "no_ram_saving": list(self.no_ram_saving),
            "notes": list(self.notes),
        }


_UNMEASURED_NOTE = (
    "{n} affected server(s) have no cost record; the deltas below are LOWER BOUNDS, "
    "not totals. An unmeasured server is rendered '-', never 0."
)

_NEXT_SESSION = (
    "memory is reclaimed at the NEXT session start, not now: a live host keeps the "
    "processes it already spawned"
)

_NO_SPAWN_PREVENTION = (
    "{names}: the disable lands in a scope MEASURED not to prevent the spawn (root "
    "disabledMcpServers), so the tools go but the memory stays -- credited 0 MB"
)

_DEFERRED = (
    "ENABLE_TOOL_SEARCH indicates DEFERRED tool loading; an eager-regime token figure "
    "overstates the saving by up to ~14x on a large server"
)

_UNKNOWN_REGIME = (
    "the tool-loading regime is unknown; token figures assume the regime the costs "
    "were measured under and may not apply"
)

_PROXY_BASIS = (
    "the token figure rests on {basis}, a PROXY and not a measurement: tokens-per-tool "
    "spans 12.5x (75.8 -> 945.0) and bytes-per-token 2.2x on this box, so read it as a "
    "hint about direction, never as a budget"
)

_UNDECLARED_BASIS = (
    "{names}: a token_cost was supplied with NO token_basis, so its provenance is "
    "unknown and it is NOT summed into the total. Declare token_basis "
    "(exact-count-tokens / schema-bytes-proxy / tool-count-proxy) in the costs file to "
    "have it counted."
)


def _affected(plan: Plan) -> tuple[tuple[str, bool], ...]:
    """``(server, spawn_prevented)`` for every change that REMOVES a tool surface."""
    out: list[tuple[str, bool]] = []
    for change in plan.changes:
        if change.intent not in (Intent.DISABLE, Intent.REMOVE):
            continue
        if not change.edits:
            continue
        prevented = any(
            e.scope in SPAWN_PREVENTING
            for e in change.edits
            if e.op is not Op.LIVE_ONLY
        )
        if change.intent is Intent.REMOVE:
            prevented = True
        out.append((change.server, prevented))
    return tuple(out)


def preview(
    plan: Plan, costs: Mapping[str, Cost], *, regime: Regime, fleet_size: int = 0
) -> Impact:
    """Aggregate the per-server costs a plan would remove.

    ``fleet_size`` is the number of tool-bearing servers currently loaded; it is used
    ONLY to decide whether the one-off :data:`TOOL_BLOCK_OVERHEAD_TOKENS` is also
    reclaimed (it is, and only, when the plan removes the last of them).
    """
    affected = _affected(plan)
    token_total = 0
    commit_total = 0
    token_seen = False
    commit_seen = False
    unmeasured: list[str] = []
    undeclared: list[str] = []
    bases: list[TokenBasis] = []
    no_ram: list[str] = []
    notes: list[str] = []

    for name, spawn_prevented in affected:
        cost = costs.get(name)
        if cost is None:
            unmeasured.append(name)
            continue
        if cost.token_cost is None:
            unmeasured.append(name)
        elif cost.token_basis is TokenBasis.NOT_MEASURED:
            # A number the parser itself flagged as having no provenance. Summing it
            # would present a guess as a total, which is the exact laundering the
            # TokenBasis label exists to prevent -- so it counts as UNMEASURED.
            undeclared.append(name)
            unmeasured.append(name)
        else:
            token_total += cost.token_cost
            bases.append(cost.token_basis)
            token_seen = True
        if cost.remote:
            continue
        if cost.commit_bytes is None:
            if name not in unmeasured:
                unmeasured.append(name)
            continue
        if not spawn_prevented:
            no_ram.append(name)
            commit_seen = True
            continue
        commit_total += cost.commit_bytes
        commit_seen = True

    if token_seen and fleet_size and len(affected) >= fleet_size:
        token_total += TOOL_BLOCK_OVERHEAD_TOKENS
        notes.append(
            f"the plan removes the last tool-bearing server, so the one-off "
            f"{TOOL_BLOCK_OVERHEAD_TOKENS}-token tool block is reclaimed too"
        )
    basis = weakest_basis(bases) if token_seen else TokenBasis.NOT_MEASURED
    if basis.is_proxy:
        notes.append(_PROXY_BASIS.format(basis=basis.value))
    if undeclared:
        notes.append(_UNDECLARED_BASIS.format(names=", ".join(undeclared)))
    if unmeasured:
        notes.append(_UNMEASURED_NOTE.format(n=len(unmeasured)))
    if no_ram:
        notes.append(_NO_SPAWN_PREVENTION.format(names=", ".join(no_ram)))
    if commit_seen:
        notes.append(_NEXT_SESSION)
    if regime is Regime.DEFERRED:
        notes.append(_DEFERRED)
    elif regime is Regime.UNKNOWN:
        notes.append(_UNKNOWN_REGIME)

    return Impact(
        regime=regime,
        token_delta=token_total if token_seen else None,
        token_basis=basis,
        commit_delta=commit_total if commit_seen else None,
        unmeasured=tuple(unmeasured),
        no_ram_saving=tuple(no_ram),
        notes=tuple(notes),
    )


def _cell(value: int | None, suffix: str = "") -> str:
    """Render a possibly-unmeasured number. ``None`` becomes ``-``, NEVER ``0``."""
    return "-" if value is None else f"{value}{suffix}"


def render_impact(impact: Impact) -> str:
    """Plain-text impact preview."""
    lines = [
        f"regime:        {impact.regime.value}",
        f"tokens saved:  {_cell(impact.token_delta)} [{impact.token_basis.value}]"
        + ("  (LOWER BOUND)" if impact.partial else ""),
        f"commit saved:  {_cell(impact.commit_delta, ' bytes')}"
        + ("  (LOWER BOUND)" if impact.partial else ""),
    ]
    if impact.unmeasured:
        lines.append(f"not measured:  {', '.join(impact.unmeasured)}")
    lines.extend(f"note: {n}" for n in impact.notes)
    return "\n".join(lines)
