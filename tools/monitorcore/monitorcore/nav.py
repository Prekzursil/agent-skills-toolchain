"""``nav`` — the pure keyboard-navigation state machine for the cockpit (WU5).

Holds the drill-down interaction as an IMMUTABLE :class:`ViewState` plus a single pure
:func:`apply` transition, so the whole model is exercised by injected keys with no real
``msvcrt`` — the interactive shell (raw ``getch``) lives in :mod:`monitorcore.cockpit`
behind a ``pragma: no cover``. Everything here reaches 100% line+branch under injected
inputs and vendors cleanly into a skill's plain Python.

The navigable surface is a flat list of :class:`NavItem` s — one per group header, then
(unless the group is collapsed) one per member thread — derived from the SAME group tree
the board renders (:func:`monitorcore.group_tree.derive_groups`). Two modes:

* **navigation** — ``up``/``k`` and ``down``/``j`` move the selection (clamped to the
  list); ``enter`` drills the selected THREAD (toggles its expanded event feed); ``space``
  collapses the selected GROUP; ``/`` opens the filter; ``q`` quits.
* **filter input** (after ``/``) — printable keys append to the fuzzy query, ``backspace``
  deletes, ``enter`` accepts (keeps the query as the live filter), ``escape`` cancels
  (clears it). The query is a case-insensitive subsequence match on a thread's name / a
  group's key, so ``adt`` finds ``audit``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from .group_tree import Group

__all__ = [
    "Action",
    "NavItem",
    "ViewState",
    "apply",
    "clamp",
    "fuzzy_match",
    "keymap",
    "nav_items",
    "visible_groups",
]


class Action(StrEnum):
    """A semantic navigation action a normal-mode key maps to."""

    UP = "up"
    DOWN = "down"
    DRILL = "drill"
    COLLAPSE = "collapse"
    FILTER = "filter"
    QUIT = "quit"


# normalized key → action (normal mode). Arrow keys arrive already normalized to
# "up"/"down" by the cockpit's getch; vim ``j``/``k`` are aliases.
_KEYMAP = {
    "up": Action.UP,
    "k": Action.UP,
    "down": Action.DOWN,
    "j": Action.DOWN,
    "enter": Action.DRILL,
    " ": Action.COLLAPSE,
    "/": Action.FILTER,
    "q": Action.QUIT,
}


def keymap(key: str) -> Action | None:
    """The :class:`Action` a normal-mode ``key`` maps to (``None`` when unmapped)."""
    return _KEYMAP.get(key)


@dataclass(frozen=True)
class NavItem:
    """One selectable row: a ``group`` header or a ``thread``, plus its ``group_key``."""

    kind: str
    key: str
    group_key: str


@dataclass(frozen=True)
class ViewState:
    """The immutable cockpit view state (every transition returns a fresh copy).

    ``selected`` indexes the navigable list; ``collapsed`` is the set of collapsed group
    keys; ``drilled`` is the thread key whose feed is expanded (``None`` = none); ``query``
    is the active fuzzy filter; ``filtering`` is ``True`` while typing it; ``quit`` latches
    a requested exit.
    """

    selected: int = 0
    collapsed: frozenset[str] = frozenset()
    drilled: str | None = None
    query: str = ""
    filtering: bool = False
    quit: bool = False


def fuzzy_match(query: str, text: str) -> bool:
    """Case-insensitive SUBSEQUENCE match (an empty query matches everything)."""
    q = query.lower()
    if not q:
        return True
    haystack = iter(text.lower())
    return all(ch in haystack for ch in q)


def visible_groups(groups: Sequence[Group], state: ViewState) -> tuple[Group, ...]:
    """The groups after applying the query filter and re-flagging collapse from ``state``.

    A group is kept when its key matches the query OR any member thread matches; a group
    matched by its key keeps ALL members, otherwise only the matching threads survive.
    """
    out: list[Group] = []
    for g in groups:
        key_hit = fuzzy_match(state.query, g.key)
        members = tuple(
            th for th in g.threads if key_hit or fuzzy_match(state.query, th.name())
        )
        if key_hit or members:
            out.append(
                Group(key=g.key, threads=members, collapsed=g.key in state.collapsed)
            )
    return tuple(out)


def nav_items(groups: Sequence[Group]) -> tuple[NavItem, ...]:
    """Flatten ``groups`` to the navigable list: each header, then its uncollapsed threads."""
    items: list[NavItem] = []
    for g in groups:
        items.append(NavItem("group", g.key, g.key))
        if not g.collapsed:
            for th in g.threads:
                items.append(NavItem("thread", th.key, g.key))
    return tuple(items)


def clamp(idx: int, count: int) -> int:
    """Clamp ``idx`` into ``[0, count)`` (``0`` when the list is empty).

    Public because :mod:`monitorcore.pane` re-exports it: the pane seam clamps its cursor
    against exactly the same rule the Phase-1 drill view does, and a second copy of this
    four-branch body is precisely the kind of duplicate that drifts.
    """
    if count <= 0:
        return 0
    if idx < 0:
        return 0
    if idx >= count:
        return count - 1
    return idx


def _reclamp(state: ViewState, groups: Sequence[Group]) -> ViewState:
    """Re-clamp ``selected`` after a change that may have grown/shrunk the item list."""
    count = len(nav_items(visible_groups(groups, state)))
    return replace(state, selected=clamp(state.selected, count))


def apply(state: ViewState, key: str, groups: Sequence[Group]) -> ViewState:
    """The single pure transition: fold ``key`` into ``state`` given the current ``groups``."""
    if state.filtering:
        return _apply_filter(state, key, groups)
    return _apply_nav(state, key, groups)


def _apply_nav(state: ViewState, key: str, groups: Sequence[Group]) -> ViewState:
    """Normal-mode transitions (selection movement, drill, collapse, filter open, quit)."""
    action = keymap(key)
    if action is None:
        return state
    items = nav_items(visible_groups(groups, state))
    count = len(items)
    if action is Action.UP:
        return replace(state, selected=clamp(state.selected - 1, count))
    if action is Action.DOWN:
        return replace(state, selected=clamp(state.selected + 1, count))
    if action is Action.QUIT:
        return replace(state, quit=True)
    if action is Action.FILTER:
        return replace(state, filtering=True, query="")
    selected = clamp(state.selected, count)
    item = items[selected] if count else None
    if action is Action.DRILL:
        return _drill(state, item, selected)
    return _collapse(state, item, selected, groups)


def _drill(state: ViewState, item: NavItem | None, selected: int) -> ViewState:
    """Toggle the drilled thread when the selected item is a thread; else no drill change."""
    if item is None or item.kind != "thread":
        return replace(state, selected=selected)
    drilled = None if state.drilled == item.key else item.key
    return replace(state, drilled=drilled, selected=selected)


def _collapse(
    state: ViewState, item: NavItem | None, selected: int, groups: Sequence[Group]
) -> ViewState:
    """Toggle the selected GROUP's collapse (no-op on a thread) and re-clamp the selection."""
    if item is None or item.kind != "group":
        return replace(state, selected=selected)
    collapsed = set(state.collapsed)
    if item.key in collapsed:
        collapsed.discard(item.key)
    else:
        collapsed.add(item.key)
    return _reclamp(
        replace(state, collapsed=frozenset(collapsed), selected=selected), groups
    )


def _apply_filter(state: ViewState, key: str, groups: Sequence[Group]) -> ViewState:
    """Filter-input transitions: type / delete the query, accept, or cancel."""
    if key == "enter":  # accept: keep the query as the active filter
        return _reclamp(replace(state, filtering=False), groups)
    if key == "escape":  # cancel: drop the filter
        return _reclamp(replace(state, filtering=False, query=""), groups)
    if key == "backspace":
        return _reclamp(replace(state, query=state.query[:-1]), groups)
    if len(key) == 1 and key.isprintable():
        return _reclamp(replace(state, query=state.query + key), groups)
    return state  # a special/navigation key is ignored while typing a filter
