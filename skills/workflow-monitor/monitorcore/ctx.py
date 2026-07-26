"""``ctx`` — the canonical context-window occupancy gauge (WU1).

ONE pure place a ctx% is derived. It REPLACES the ``min(100, …)`` clamp that
``codex_tail.board_line`` used to apply, which SILENTLY MASKED the ``num > denom``
invariant: a last-turn token count larger than the advertised window (bad token
accounting) rendered as a benign ``ctx 100%``. Here that impossible reading is
surfaced as :attr:`CtxGauge.suspect` and shown with its true (over-100)
percentage instead of hidden.

The numerator is the LAST-turn token usage (``CodexThread.ctx_tokens``, populated
by ``codex_tail`` from the rollout ``last_token_usage`` — never the cumulative
``total_token_usage``, which would pin ctx% near 100% over a session). This module
only *consumes* that field; ``codex_tail`` owns populating it.

ctx% is a DISPLAY-ONLY diagnostic and is deliberately kept OUT of every code path
that can raise an :class:`~monitorcore.contract.Alert`: a suspect / over reading
means the *instrument* is wrong, not that the monitored work is failing, so
alerting on it would be alarm-fatigue on a measurement artifact. ``monitorcore``'s
tests pin this with a property test asserting an adapter's ``alert()`` is invariant
to every ctx value (the cardinal ctx-never-feeds-alert guardrail). The module is
stdlib-only so it vendors cleanly into a skill's plain Python.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CtxGauge", "ctx_gauge", "ctx_label"]

_FULL = 100


@dataclass(frozen=True)
class CtxGauge:
    """An immutable ctx-occupancy reading.

    ``known`` is ``False`` when either the numerator or the window is missing (there
    is nothing to show). ``pct`` is clamped ``0..100`` for a gauge/bar; ``raw_pct``
    is the true (possibly >100) percentage; ``suspect`` is ``True`` exactly when
    ``tokens > window`` — the impossible reading the old clamp hid.
    """

    tokens: int
    window: int
    known: bool
    pct: int
    raw_pct: int
    suspect: bool


def ctx_gauge(tokens: int, window: int) -> CtxGauge:
    """Derive a :class:`CtxGauge` from a last-turn token count and a window size."""
    if tokens <= 0 or window <= 0:
        return CtxGauge(
            tokens=tokens,
            window=window,
            known=False,
            pct=0,
            raw_pct=0,
            suspect=False,
        )
    raw_pct = tokens * _FULL // window
    pct = raw_pct if raw_pct < _FULL else _FULL
    return CtxGauge(
        tokens=tokens,
        window=window,
        known=True,
        pct=pct,
        raw_pct=raw_pct,
        suspect=tokens > window,
    )


def ctx_label(gauge: CtxGauge) -> str:
    """The board-line fragment for a gauge (``""`` when there is nothing to show).

    ``ctx N%`` normally; ``ctx N% SUSPECT`` (carrying the TRUE over-100 percentage)
    when the reading is impossible — so the anomaly is visible, never masked.
    """
    if not gauge.known:
        return ""
    if gauge.suspect:
        return f"ctx {gauge.raw_pct}% SUSPECT"
    return f"ctx {gauge.pct}%"
