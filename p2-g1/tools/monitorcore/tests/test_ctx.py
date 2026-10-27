"""Tests for ``monitorcore.ctx`` — the context-occupancy gauge and the cardinal
ctx-never-feeds-``alert`` guardrail (WU1), 100% line+branch.

Two things are pinned:

* the pure :func:`ctx_gauge` / :func:`ctx_label` surface the ``num > denom``
  invariant as ``suspect`` (the anomaly the old ``min(100, …)`` clamp hid), and
* ``alert()`` is INVARIANT to every ctx value — a suspect / over-window reading can
  never escalate a healthy snapshot into an :class:`~monitorcore.contract.Alert`.
  The grid deliberately includes a wildly-impossible ``(999_999, 1)`` reading; if
  ctx ever fed ``alert`` this property FIRES (a real, both-states detector).
"""

from __future__ import annotations

import pytest

from monitorcore import codex_tail as ct
from monitorcore.codex_source import CodexPayload, CodexSource
from monitorcore.contract import Snapshot, SourceState
from monitorcore.ctx import CtxGauge, ctx_gauge, ctx_label

NOW = 1_784_283_000.0


# ───────────────────────── the pure gauge ─────────────────────────
@pytest.mark.parametrize(
    ("tokens", "window", "known", "pct", "raw", "suspect"),
    [
        (0, 10, False, 0, 0, False),  # no numerator
        (-5, 10, False, 0, 0, False),  # negative numerator
        (5, 0, False, 0, 0, False),  # no window
        (5, -1, False, 0, 0, False),  # negative window
        (1, 3, True, 33, 33, False),  # floor division
        (50, 100, True, 50, 50, False),  # normal
        (100, 100, True, 100, 100, False),  # exactly full — NOT suspect
        (150, 100, True, 100, 150, True),  # over window — suspect, true pct kept
    ],
)
def test_ctx_gauge(
    tokens: int, window: int, known: bool, pct: int, raw: int, suspect: bool
) -> None:
    assert ctx_gauge(tokens, window) == CtxGauge(
        tokens=tokens,
        window=window,
        known=known,
        pct=pct,
        raw_pct=raw,
        suspect=suspect,
    )


def test_ctx_label_unknown_is_empty() -> None:
    assert ctx_label(ctx_gauge(0, 0)) == ""


def test_ctx_label_normal() -> None:
    assert ctx_label(ctx_gauge(50, 100)) == "ctx 50%"


def test_ctx_label_suspect_shows_the_true_over_100_pct() -> None:
    assert ctx_label(ctx_gauge(500, 100)) == "ctx 500% SUSPECT"


# ───────────────── the cardinal guardrail: ctx never feeds alert ─────────────────
_CTX_GRID = [(0, 0), (50, 100), (100, 100), (999_999, 1)]


def _snap(
    state: SourceState, ctx_tokens: int, ctx_window: int
) -> Snapshot[CodexPayload]:
    th = ct.CodexThread(
        key="k",
        source="stream",
        path="p",
        last_ts=NOW,
        ctx_tokens=ctx_tokens,
        ctx_window=ctx_window,
    )
    return Snapshot(
        source_id="codexmon",
        ts=NOW,
        reachable=state is not SourceState.UNREACHABLE,
        stale=False,
        state=state,
        headline="fixed headline",
        payload=CodexPayload(threads=(th,)),
        error="fixed error",
    )


@pytest.mark.parametrize("state", list(SourceState))
@pytest.mark.parametrize(("ctx_tokens", "ctx_window"), _CTX_GRID)
def test_alert_is_invariant_to_ctx(
    state: SourceState, ctx_tokens: int, ctx_window: int
) -> None:
    src = CodexSource(poller=ct.Poller("s", "x", clock=lambda: NOW), clock=lambda: NOW)
    baseline = src.alert(_snap(state, 0, 0))
    got = src.alert(_snap(state, ctx_tokens, ctx_window))
    assert got == baseline
