"""Tests for the schema-agnostic timeline IR (``monitorcore.timeline``).

Covers the PURE symbols extracted out of the wfmon adapter: ``_flatten_content``
(str / dict / list / other flatten paths), ``report_headline`` (heading / first-line /
empty), and ``pair_tool_calls`` (empty, matched-first-later, orphan → None), plus a
``TimelineEvent`` construction/defaults check. The adapter-specific transcript readers
(``agent_timeline`` / ``agent_task``) stay in ``workflow_run`` and keep their own tests
in the wfmon local lane.
"""

from __future__ import annotations

from monitorcore.timeline import (
    TimelineEvent,
    _flatten_content,
    pair_tool_calls,
    report_headline,
)


# ───────────────────────── TimelineEvent ─────────────────────────
def test_timeline_event_defaults():
    e = TimelineEvent(kind="text", seq=3)
    assert e.kind == "text"
    assert e.seq == 3
    assert e.text == ""
    assert e.name == ""
    assert e.tool_input == {}
    assert e.tool_id == ""
    assert e.output == ""
    assert e.is_error is False


def test_timeline_event_tool_use_fields():
    e = TimelineEvent(
        kind="tool_use", seq=0, name="Bash", tool_input={"command": "ls"}, tool_id="t1"
    )
    assert e.name == "Bash"
    assert e.tool_input == {"command": "ls"}
    assert e.tool_id == "t1"


# ───────────────────────── _flatten_content ─────────────────────────
def test_flatten_content_str_passthrough():
    assert _flatten_content("hello world") == "hello world"


def test_flatten_content_list_text_and_other():
    content = [
        {"type": "text", "text": "first"},
        {"type": "image", "source": {"k": "v"}},
        "bare-string",
    ]
    out = _flatten_content(content)
    assert out == 'first\n{"type": "image", "source": {"k": "v"}}\n"bare-string"'


def test_flatten_content_dict_text_extracted():
    # the real advisor_tool_result shape: a single {type:text,text} dict
    assert _flatten_content({"type": "text", "text": "advisor hi"}) == "advisor hi"


def test_flatten_content_dict_arbitrary_json():
    assert (
        _flatten_content({"error": "boom", "code": 2}) == '{"error": "boom", "code": 2}'
    )


def test_flatten_content_other_str_coerced():
    assert _flatten_content(None) == "None"
    assert _flatten_content(123) == "123"


def test_flatten_content_text_missing_key():
    # a text block with no "text" key flattens to "" (str of missing default)
    assert _flatten_content([{"type": "text"}]) == ""


# ───────────────────────── report_headline ─────────────────────────
def test_report_headline_markdown_heading():
    assert report_headline("# Title\nbody") == "Title"


def test_report_headline_first_line_when_no_heading():
    assert report_headline("plain first line\nsecond") == "plain first line"


def test_report_headline_empty():
    assert report_headline("") == ""
    # whitespace-only lines are stripped out too -> no non-empty line -> ""
    assert report_headline("   \n\t\n") == ""


# ───────────────────────── pair_tool_calls ─────────────────────────
def test_pair_tool_calls_empty_without_tool_use():
    only_text = [TimelineEvent(kind="text", seq=0, text="x")]
    assert pair_tool_calls(only_text) == []


def test_pair_matches_first_later_result_only():
    # a result appearing BEFORE its use (lower seq) is not matched; a later same-id result is
    events = [
        TimelineEvent(kind="tool_result", seq=0, tool_id="dup"),
        TimelineEvent(kind="tool_use", seq=1, tool_id="dup"),
        TimelineEvent(kind="tool_result", seq=2, tool_id="dup"),
    ]
    ((use, res),) = pair_tool_calls(events)
    assert use.seq == 1
    assert res is not None
    assert res.seq == 2


def test_pair_tool_calls_orphan_is_none():
    # a tool_use with no later matching result -> pairs to None
    events = [TimelineEvent(kind="tool_use", seq=0, tool_id="orphan")]
    ((use, res),) = pair_tool_calls(events)
    assert use.tool_id == "orphan"
    assert res is None


def test_pair_tool_calls_ordered_multiple():
    events = [
        TimelineEvent(kind="tool_use", seq=0, tool_id="a"),
        TimelineEvent(kind="tool_result", seq=1, tool_id="a"),
        TimelineEvent(kind="text", seq=2, text="between"),
        TimelineEvent(kind="tool_use", seq=3, tool_id="b"),
    ]
    pairs = pair_tool_calls(events)
    assert [u.tool_id for u, _ in pairs] == ["a", "b"]
    by_id = {u.tool_id: r for u, r in pairs}
    assert by_id["a"] is not None
    assert by_id["a"].tool_id == "a"
    assert by_id["b"] is None
