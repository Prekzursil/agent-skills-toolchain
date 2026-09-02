"""Divergence classes for live-versus-repo rules files (IMP-0036).

The production classifier is two-directional: a file is ``DIVERGED`` only when
*both* sides carry lines the other lacks (see :func:`plugin.drift.classify_pair`).
This module re-exports the class names used by decision packets and adds:

* :func:`unique_lines` -- the two unique-line sets a packet must carry;
* :func:`classify_texts` -- the two-directional verdict over text;
* :func:`one_directional_repo_extra` -- the deliberately broken *mutant* that
  only looks at what the repo has and live lacks.  It can never say
  ``DIVERGED``; the probes use it to show that a one-directional differ
  silently misfiles every genuinely diverged file as ``REPO-AHEAD``.
"""
from __future__ import annotations

from plugin.drift import (
    CLASSES,
    DIVERGED,
    IDENTICAL,
    IDENTICAL_MODULO_EOL,
    LIVE_AHEAD,
    REPO_AHEAD,
    classify_pair,
)

ONE_DIRECTIONAL_CLASSES = (IDENTICAL, IDENTICAL_MODULO_EOL, REPO_AHEAD, LIVE_AHEAD)


def _as_text(value: str | bytes | bytearray | None) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="surrogateescape")
    return str(value)


def _norm_eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _lines(text: str) -> list[str]:
    return _norm_eol(text).split("\n")


def unique_lines(repo_text: str | bytes | None, live_text: str | bytes | None) -> tuple[set[str], set[str]]:
    """Return ``(repo_only, live_only)`` line sets after end-of-line normalisation."""
    repo = set(_lines(_as_text(repo_text)))
    live = set(_lines(_as_text(live_text)))
    return repo - live, live - repo


def classify_texts(repo_text: str | bytes | None, live_text: str | bytes | None) -> str:
    """Two-directional verdict for a text pair (one of :data:`CLASSES`)."""
    repo = _as_text(repo_text).encode("utf-8", errors="surrogateescape")
    live = _as_text(live_text).encode("utf-8", errors="surrogateescape")
    return classify_pair(repo, live)


def one_directional_repo_extra(repo_text: str | bytes | None, live_text: str | bytes | None) -> str:
    """MUTANT classifier: decide from the repo-extra lines alone.

    Only the lines present in the repo copy and absent from the live copy are
    consulted.  When there are any, the file is filed as ``REPO-AHEAD``; when
    there are none but the copies still differ, live must hold the extra
    lines, so ``LIVE-AHEAD``.  Because the live-only set is never intersected
    with the repo-only set, a file where *both* sides changed is misfiled as
    ``REPO-AHEAD`` -- exactly the "size wins" behaviour the two-directional
    packet exists to refuse.  Returns one of :data:`ONE_DIRECTIONAL_CLASSES`.
    """
    repo = _as_text(repo_text)
    live = _as_text(live_text)
    if repo == live:
        return IDENTICAL
    if _norm_eol(repo) == _norm_eol(live):
        return IDENTICAL_MODULO_EOL
    repo_only, _live_only = unique_lines(repo, live)
    if repo_only:
        return REPO_AHEAD
    return LIVE_AHEAD


__all__ = [
    "CLASSES",
    "DIVERGED",
    "IDENTICAL",
    "IDENTICAL_MODULO_EOL",
    "LIVE_AHEAD",
    "ONE_DIRECTIONAL_CLASSES",
    "REPO_AHEAD",
    "classify_texts",
    "one_directional_repo_extra",
    "unique_lines",
]
