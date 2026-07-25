"""Tests for ``monitorcore.group_tree`` — the pure fleet→group containment tree over
``CodexThread`` (WU3): ``derive_groups`` + rollup grammar + collapse + ``(ungrouped)``
bucket, 100% line+branch.
"""

from __future__ import annotations

import pytest

from monitorcore.codex_tail import CodexThread
from monitorcore.group_tree import (
    UNGROUPED,
    Group,
    collapse_marker,
    derive_groups,
    group_header,
    group_key,
    group_rows,
    group_rollup,
    is_problem,
)

_NOW = 1609459200.0


def _th(
    *,
    key: str,
    label: str = "",
    source: str = "stream",
    status: str = "idle",
) -> CodexThread:
    th = CodexThread(key=key, source=source, path=key, label=label)
    th.status = status
    th.start_ts = _NOW
    th.last_ts = _NOW
    return th


# ───────────────────────────── group_key ─────────────────────────────
def test_group_key_prefers_label() -> None:
    assert group_key(_th(key="a", label="audit", source="stream")) == "audit"


def test_group_key_falls_back_to_source() -> None:
    assert group_key(_th(key="a", label="", source="rollout")) == "rollout"


def test_group_key_empty_when_neither() -> None:
    assert group_key(_th(key="a", label="", source="")) == ""


# ───────────────────────────── derive_groups ─────────────────────────────
def test_derive_groups_buckets_sorts_by_worst_member_and_flags_ungrouped() -> None:
    threads = [
        _th(key="t1", label="audit", status="done"),
        _th(key="t2", label="audit", status="running"),
        _th(key="t3", label="rescue", status="aborted"),
        _th(key="t4", label="", source="rollout", status="idle"),
        _th(key="t5", label="", source="", status="done"),  # → (ungrouped)
    ]
    groups = derive_groups(threads)
    assert [g.key for g in groups] == ["rescue", "audit", "rollout", UNGROUPED]
    audit = next(g for g in groups if g.key == "audit")
    assert [t.key for t in audit.threads] == ["t1", "t2"]  # insertion order kept
    assert all(g.collapsed is False for g in groups)


def test_derive_groups_marks_collapsed_keys() -> None:
    threads = [
        _th(key="t1", label="audit", status="running"),
        _th(key="t2", label="rescue", status="running"),
    ]
    groups = derive_groups(threads, collapsed_keys={"audit"})
    collapsed = {g.key: g.collapsed for g in groups}
    assert collapsed == {"audit": True, "rescue": False}


def test_derive_groups_accepts_a_custom_key_fn() -> None:
    threads = [
        _th(key="t1", label="audit", source="stream", status="running"),
        _th(key="t2", label="rescue", source="stream", status="idle"),
    ]
    groups = derive_groups(threads, key_fn=lambda th: th.source)
    assert [g.key for g in groups] == ["stream"]
    assert len(groups[0].threads) == 2


def test_derive_groups_empty_is_empty() -> None:
    assert derive_groups([]) == ()


# ───────────────────────────── group_rollup ─────────────────────────────
def _mixed_group(collapsed: bool = False) -> Group:
    return Group(
        key="mix",
        threads=(
            _th(key="a", status="running"),
            _th(key="b", status="running"),
            _th(key="c", status="idle"),
            _th(key="d", status="done"),
            _th(key="e", status="aborted"),
        ),
        collapsed=collapsed,
    )


def test_group_rollup_rich_grammar() -> None:
    assert group_rollup(_mixed_group()) == "R●2 I○1 D✓1 X✘1"


def test_group_rollup_ascii_grammar() -> None:
    assert group_rollup(_mixed_group(), ascii=True) == "R2 I1 D1 X1"


# ───────────────────────────── collapse_marker ─────────────────────────────
@pytest.mark.parametrize(
    ("collapsed", "ascii", "expected"),
    [
        (False, False, "▾"),  # ▾ open
        (True, False, "▸"),  # ▸ collapsed
        (False, True, "v"),  # ascii open
        (True, True, ">"),  # ascii collapsed
    ],
)
def test_collapse_marker(collapsed: bool, ascii: bool, expected: str) -> None:
    assert collapse_marker(collapsed, ascii=ascii) == expected


# ───────────────────────────── group_header ─────────────────────────────
def test_group_header_rich() -> None:
    g = Group(key="audit", threads=(_th(key="a", status="running"),))
    assert group_header(g) == "▾ audit R●1 I○0 D✓0 X✘0"


def test_group_header_ascii_and_collapsed() -> None:
    g = Group(key="audit", threads=(_th(key="a", status="aborted"),), collapsed=True)
    assert group_header(g, ascii=True) == "> audit R0 I0 D0 X1"


# ───────────────────────────── is_problem ─────────────────────────────
def test_is_problem_only_aborted() -> None:
    assert is_problem(_th(key="a", status="aborted")) is True
    assert is_problem(_th(key="a", status="running")) is False


# ───────────────────────────── group_rows ─────────────────────────────
def test_group_rows_collapsed_is_header_only() -> None:
    g = Group(
        key="audit",
        threads=(_th(key="a", label="audit", status="running"),),
        collapsed=True,
    )
    rows = group_rows(g, _NOW, 120)
    assert len(rows) == 1
    assert rows[0].startswith("▸ audit ")


def test_group_rows_expanded_renders_header_then_threads() -> None:
    g = Group(
        key="audit",
        threads=(
            _th(key="a", label="fix-catalogue", status="running"),
            _th(key="b", label="fix-shim", status="aborted"),
        ),
    )
    rows = group_rows(g, _NOW, 120)
    assert len(rows) == 3  # header + two thread board lines
    assert rows[0].startswith("▾ audit ")
    assert "fix-catalogue" in rows[1]
    assert "fix-shim" in rows[2]


def test_group_rows_threads_override_subsets_the_rendered_threads() -> None:
    problem = _th(key="b", label="fix-shim", status="aborted")
    g = Group(
        key="rescue",
        threads=(_th(key="a", label="ok-thread", status="running"), problem),
    )
    rows = group_rows(g, _NOW, 120, threads=(problem,))
    # header rollup still counts BOTH threads (honest), body shows only the problem
    assert rows[0] == "▾ rescue R●1 I○0 D✓0 X✘1"
    assert len(rows) == 2
    assert "fix-shim" in rows[1]
    assert "ok-thread" not in rows[1]


def test_group_rows_forwards_event_feed_flags() -> None:
    from monitorcore.codex_tail import ToolEvent

    th = _th(key="a", label="fix", status="running")
    th.add_event(ToolEvent("tool", "shell", "pytest -q", "error", None, _NOW))
    g = Group(key="audit", threads=(th,))
    rows = group_rows(g, _NOW, 120, show_events=True, event_limit=1)
    assert len(rows) == 3  # header + board line + one event row
    assert "shell: pytest -q" in rows[2]
