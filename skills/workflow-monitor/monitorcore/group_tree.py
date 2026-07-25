"""``group_tree`` — the pure fleet→group containment tree over ``CodexThread`` (WU3).

Clusters the flat thread fleet into collapsible GROUPS so the board reads as a
``fleet → group → thread → event`` containment tree rather than one long list.
Everything here is a PURE function over the already-captured, already-scrubbed
``CodexThread`` model — no I/O, no clock — so it reaches 100% line+branch under
injected inputs.

* :func:`derive_groups` buckets threads by a key drawn from fields monitorcore
  ALREADY captures — the meta ``label`` when present, else the ``source`` name — and
  degrades a thread with neither to a single ``(ungrouped)`` bucket (richer
  relay-run-id grouping is Phase-2 WU13, gated on the producer emitting a run id).
  Groups sort by their **worst member** (a corroborated ``aborted`` outranks a live
  ``running`` outranks ``idle`` outranks ``done``), with the key as a stable tiebreak.
* :func:`group_rollup` renders the fixed per-group triage grammar ``R●n I○n D✓n X✘n``
  (running / idle / done / aborted), with an ``ascii`` fallback ``Rn In Dn Xn`` for
  narrow terminals — the glyph vocab the visual spec pins.
* :func:`collapse_marker` / :func:`group_header` render the ``▾``/``▸`` collapse
  affordance and the header line; :func:`group_rows` interleaves the header with its
  thread rows (via :mod:`monitorcore.event_feed`) unless the group is collapsed, and
  accepts a ``threads`` subset so a caller (e.g. the ``<50-col`` problems-only
  breakpoint) can show only the failing members while the header rollup still counts
  every member honestly.

Red is reserved for a corroborated failure only: :func:`is_problem` is the single
predicate for "this thread is a fact-level failure" (an ``aborted`` end reason), used
by the problems-only breakpoint. The module is stdlib-only so it vendors cleanly into a
skill's plain Python.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from .codex_tail import CodexThread, clip, status_counts
from .event_feed import thread_rows

__all__ = [
    "UNGROUPED",
    "Group",
    "collapse_marker",
    "derive_groups",
    "group_header",
    "group_key",
    "group_rollup",
    "group_rows",
    "is_problem",
]

UNGROUPED = "(ungrouped)"

# rollup letter → the coarse thread status it counts, in fixed display order.
_ROLLUP_ORDER = (("R", "running"), ("I", "idle"), ("D", "done"), ("X", "aborted"))
_ROLLUP_GLYPH = {"R": "●", "I": "○", "D": "✓", "X": "✘"}
# group sort weight: the WORST (highest) member decides the group's rank.
_SEVERITY = {"aborted": 3, "running": 2, "idle": 1, "done": 0}


@dataclass(frozen=True)
class Group:
    """One containment group: a key, its member threads, and a collapse flag."""

    key: str
    threads: tuple[CodexThread, ...]
    collapsed: bool = False


def group_key(th: CodexThread) -> str:
    """The group key from already-present fields: the ``label`` else the ``source``.

    Empty when a thread has neither — the caller files that under ``(ungrouped)``.
    """
    return th.label or th.source or ""


def _group_severity(group: Group) -> int:
    """The worst-member severity (``-1`` for an empty group)."""
    return max((_SEVERITY.get(th.status, 0) for th in group.threads), default=-1)


def derive_groups(
    threads: Iterable[CodexThread],
    *,
    key_fn: Callable[[CodexThread], str] = group_key,
    collapsed_keys: Iterable[str] = (),
) -> tuple[Group, ...]:
    """Bucket ``threads`` into groups, worst-member first (key as the tiebreak).

    A thread whose ``key_fn`` yields an empty key lands in the ``(ungrouped)`` bucket;
    a group whose key is in ``collapsed_keys`` is flagged collapsed.
    """
    collapsed = set(collapsed_keys)
    buckets: dict[str, list[CodexThread]] = {}
    for th in threads:
        buckets.setdefault(key_fn(th) or UNGROUPED, []).append(th)
    groups = tuple(
        Group(key=k, threads=tuple(members), collapsed=k in collapsed)
        for k, members in buckets.items()
    )
    return tuple(sorted(groups, key=lambda g: (-_group_severity(g), g.key)))


def group_rollup(group: Group, *, ascii: bool = False) -> str:
    """The per-group triage rollup: ``R●n I○n D✓n X✘n`` (or ``Rn In Dn Xn`` in ascii)."""
    counts = status_counts(group.threads)
    parts = [
        f"{letter}{counts[status]}"
        if ascii
        else f"{letter}{_ROLLUP_GLYPH[letter]}{counts[status]}"
        for letter, status in _ROLLUP_ORDER
    ]
    return " ".join(parts)


def collapse_marker(collapsed: bool, *, ascii: bool = False) -> str:
    """The collapse affordance: ``▾``/``▸`` (open/collapsed), or ascii ``v``/``>``."""
    if ascii:
        return ">" if collapsed else "v"
    return "▸" if collapsed else "▾"


def group_header(group: Group, *, ascii: bool = False) -> str:
    """A group header line: ``<marker> <key> <rollup>``."""
    marker = collapse_marker(group.collapsed, ascii=ascii)
    return f"{marker} {group.key} {group_rollup(group, ascii=ascii)}"


def is_problem(th: CodexThread) -> bool:
    """Whether ``th`` is a corroborated (fact-level) failure — an ``aborted`` thread."""
    return th.status == "aborted"


def group_rows(
    group: Group,
    now: float,
    width: int,
    *,
    threads: Sequence[CodexThread] | None = None,
    ascii: bool = False,
    show_events: bool = False,
    event_limit: int | None = None,
) -> list[str]:
    """The group's header, then — unless collapsed — its threads' interleaved rows.

    ``threads`` overrides which members are rendered in the body (the header rollup
    still reflects every member of ``group``); ``show_events`` / ``event_limit`` are
    forwarded to :func:`monitorcore.event_feed.thread_rows`.
    """
    rows = [clip(group_header(group, ascii=ascii), width)]
    if group.collapsed:
        return rows
    members = group.threads if threads is None else threads
    for th in members:
        rows.extend(
            thread_rows(
                th,
                now,
                width,
                show_events=show_events,
                event_limit=event_limit,
            )
        )
    return rows
