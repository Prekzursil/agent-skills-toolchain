"""Tests for ``monitorcore.nav`` — the pure keyboard-nav state machine (WU5), 100%
line+branch.

Covers the ViewState transitions for up/down/j/k select, enter drill, space collapse, and
the ``/`` fuzzy-filter input mode — driven entirely through pure ``apply`` calls with an
injected normalized key, no real msvcrt.
"""

from __future__ import annotations

import pytest

from monitorcore.codex_tail import CodexThread
from monitorcore.group_tree import derive_groups
from monitorcore.nav import (
    Action,
    NavItem,
    ViewState,
    apply,
    fuzzy_match,
    keymap,
    nav_items,
    visible_groups,
)


def _th(key: str, label: str, status: str = "idle") -> CodexThread:
    th = CodexThread(key=key, source="stream", path=key, label=label)
    th.status = status
    return th


def _fleet() -> tuple[CodexThread, ...]:
    return (
        _th("t1", "audit", "running"),
        _th("t2", "audit", "idle"),
        _th("t3", "rescue", "aborted"),
    )


def _groups():
    return derive_groups(_fleet())


# ───────────────────────────── fuzzy_match ─────────────────────────────
@pytest.mark.parametrize(
    ("query", "text", "hit"),
    [
        ("", "anything", True),  # empty query matches all
        ("aud", "audit", True),  # prefix / subsequence
        ("adt", "audit", True),  # non-contiguous subsequence
        ("AUD", "audit", True),  # case-insensitive
        ("xyz", "audit", False),  # no match
        ("audd", "audit", False),  # runs out of chars
    ],
)
def test_fuzzy_match(query: str, text: str, hit: bool) -> None:
    assert fuzzy_match(query, text) is hit


# ───────────────────────────── keymap ─────────────────────────────
@pytest.mark.parametrize(
    ("key", "action"),
    [
        ("up", Action.UP),
        ("k", Action.UP),
        ("down", Action.DOWN),
        ("j", Action.DOWN),
        ("enter", Action.DRILL),
        (" ", Action.COLLAPSE),
        ("/", Action.FILTER),
        ("q", Action.QUIT),
        ("z", None),  # unmapped
    ],
)
def test_keymap(key: str, action: Action | None) -> None:
    assert keymap(key) is action


# ───────────────────────────── nav_items / visible_groups ─────────────────────────────
def test_nav_items_lists_groups_then_uncollapsed_threads() -> None:
    items = nav_items(_groups())
    # two groups (audit worst=running, rescue worst=aborted): rescue sorts first
    assert items[0] == NavItem("group", "rescue", "rescue")
    kinds = [(i.kind, i.key) for i in items]
    assert ("group", "audit") in kinds
    assert ("thread", "t1") in kinds and ("thread", "t3") in kinds
    assert len(items) == 5  # 2 groups + 3 threads


def test_nav_items_hides_threads_of_a_collapsed_group() -> None:
    state = ViewState(collapsed=frozenset({"audit"}))
    items = nav_items(visible_groups(_groups(), state))
    keys = {(i.kind, i.key) for i in items}
    assert ("group", "audit") in keys
    assert ("thread", "t1") not in keys  # collapsed → its threads are not navigable
    assert ("thread", "t3") in keys  # rescue still expanded


def test_visible_groups_filters_by_query_on_thread_name() -> None:
    state = ViewState(query="rescue")
    vg = visible_groups(_groups(), state)
    assert [g.key for g in vg] == ["rescue"]


def test_visible_groups_group_key_hit_keeps_all_members() -> None:
    # query hits the group key "audit" → keep the group with ALL its threads
    state = ViewState(query="audit")
    vg = visible_groups(_groups(), state)
    (audit,) = [g for g in vg if g.key == "audit"]
    assert len(audit.threads) == 2


# ───────────────────────────── apply: navigation ─────────────────────────────
def test_apply_ignores_an_unmapped_key() -> None:
    state = ViewState(selected=1)
    assert apply(state, "z", _groups()) is state  # unchanged identity


def test_apply_down_and_up_clamp_at_the_edges() -> None:
    g = _groups()
    n = len(nav_items(g))  # 5
    at_top = ViewState(selected=0)
    assert apply(at_top, "up", g).selected == 0  # clamp low
    at_bottom = ViewState(selected=n - 1)
    assert apply(at_bottom, "down", g).selected == n - 1  # clamp high
    mid = ViewState(selected=1)
    assert apply(mid, "down", g).selected == 2
    assert apply(mid, "k", g).selected == 0


def test_apply_quit_sets_the_quit_flag() -> None:
    assert apply(ViewState(), "q", _groups()).quit is True


def test_apply_filter_enters_input_mode_with_empty_query() -> None:
    state = apply(ViewState(query="old"), "/", _groups())
    assert state.filtering is True
    assert state.query == ""


# ───────────────────────────── apply: drill ─────────────────────────────
def test_apply_enter_drills_and_toggles_a_thread() -> None:
    g = _groups()
    # nav item index 1 is the first thread under the worst group (rescue → t3)
    items = nav_items(g)
    thread_idx = next(i for i, it in enumerate(items) if it.kind == "thread")
    state = ViewState(selected=thread_idx)
    drilled = apply(state, "enter", g)
    assert drilled.drilled == items[thread_idx].key
    # enter again on the same thread toggles the drill back off
    assert apply(drilled, "enter", g).drilled is None


def test_apply_enter_on_a_group_does_not_drill() -> None:
    g = _groups()
    state = ViewState(selected=0)  # a group header
    assert apply(state, "enter", g).drilled is None


def test_apply_drill_on_empty_fleet_is_a_no_op() -> None:
    empty: tuple[CodexThread, ...] = ()
    g = derive_groups(empty)
    state = ViewState(selected=3)
    out = apply(state, "enter", g)
    assert out.drilled is None
    assert out.selected == 0  # clamped to the empty list


# ───────────────────────────── apply: collapse ─────────────────────────────
def test_apply_space_toggles_group_collapse() -> None:
    g = _groups()
    state = ViewState(selected=0)  # the worst group (rescue)
    collapsed = apply(state, " ", g)
    assert "rescue" in collapsed.collapsed
    # collapsing again expands it
    assert "rescue" not in apply(collapsed, " ", g).collapsed


def test_apply_space_on_a_thread_does_not_collapse() -> None:
    g = _groups()
    items = nav_items(g)
    thread_idx = next(i for i, it in enumerate(items) if it.kind == "thread")
    state = ViewState(selected=thread_idx)
    assert apply(state, " ", g).collapsed == frozenset()


def test_apply_collapse_reclamps_selection_when_items_shrink() -> None:
    g = _groups()
    # collapse the first group so the navigable list shrinks; the selection re-clamps
    state = ViewState(selected=0)
    out = apply(state, " ", g)  # collapse the first group → fewer items
    assert out.selected <= len(nav_items(visible_groups(g, out))) - 1


# ───────────────────────────── apply: filter input mode ─────────────────────────────
def test_filter_typing_appends_and_backspace_deletes() -> None:
    g = _groups()
    state = ViewState(filtering=True)
    state = apply(state, "r", g)
    state = apply(state, "e", g)
    assert state.query == "re"
    state = apply(state, "backspace", g)
    assert state.query == "r"


def test_filter_enter_accepts_and_keeps_the_query() -> None:
    g = _groups()
    state = ViewState(filtering=True, query="aud")
    out = apply(state, "enter", g)
    assert out.filtering is False
    assert out.query == "aud"  # kept as the active filter


def test_filter_escape_cancels_and_clears_the_query() -> None:
    g = _groups()
    state = ViewState(filtering=True, query="aud")
    out = apply(state, "escape", g)
    assert out.filtering is False
    assert out.query == ""


def test_filter_ignores_a_special_navigation_key() -> None:
    g = _groups()
    state = ViewState(filtering=True, query="a")
    # an arrow key ("up") is multi-char and not a printable single char → ignored
    assert apply(state, "up", g) is state
