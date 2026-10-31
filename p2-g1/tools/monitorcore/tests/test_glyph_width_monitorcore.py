"""Regression guards for terminal-cell glyph width in monitorcore.

The source guard deliberately excludes East-Asian Ambiguous glyphs U+2713, U+2717,
U+21B3, U+25B6, U+25CF, and U+2500 box drawing. They occupy one cell under a Latin font
but two under a CJK font, so that real font-dependent residual is not covered. This does
not claim that all width bugs are gone.
"""

from __future__ import annotations

import inspect
import json
import re
import unicodedata

from monitorcore import agent_tail, discovery, pane_views

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def is_wide(ch: str) -> bool:
    return (
        ch == "⚠"
        or ord(ch) >= 0x1F300
        or unicodedata.east_asian_width(ch) in ("W", "F")
    )


def _wide_chars(text: str) -> list[str]:
    return [ch for ch in text if is_wide(ch)]


def _marker(line: str) -> str:
    """Token 1 of an ANSI-stripped feed line: ``--:--:--  <marker> <text>``."""
    return _ANSI.sub("", line).split()[1]


def test_width_detector_control_fires_on_known_bad_glyphs():
    """Prove the detector fires; silence in both bad and clean states proves nothing."""
    assert all(is_wide(ch) for ch in ("⚠", "💭", "📝", "🔧"))
    assert all(not is_wide(ch) for ch in ("*", ">", "+", "!", "✓", "✗"))


def test_agent_tail_all_render_branches_have_distinct_narrow_markers():
    entry = {
        "message": {
            "content": [
                {"type": "thinking", "thinking": "plan"},
                {"type": "text", "text": "explain"},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "x"}},
                {"type": "tool_result", "content": "ok"},
                {"type": "tool_result", "content": "bad", "is_error": True},
            ]
        }
    }
    lines = agent_tail.render(entry, 200)
    assert len(lines) == 5
    assert not _wide_chars("".join(lines))
    # Positional and falsifiable.  The previous form asserted
    # ``len({"*", ">", "+"}) == 3`` over SET LITERALS, which is true no matter what
    # render() emits -- a tautology that could never fail, i.e. a control that cannot
    # distinguish the two hypotheses and so only proves the instrument ran
    # (rules/common/single-signal-verification.md 3c).  Assert instead that token 1 of
    # each stripped line IS that block type's marker, and that all five block types
    # render mutually distinct markers.
    markers = [_marker(line) for line in lines]
    assert markers[:3] == ["*", ">", "+"], markers
    assert len(set(markers)) == 5, f"marker collision across block types: {markers}"


def test_discovery_last_line_branches_have_distinct_narrow_markers(tmp_path):
    cases = [
        ({"type": "tool_use", "name": "Read", "input": {}}, "+"),
        ({"type": "text", "text": "hello"}, ">"),
        ({"type": "tool_result", "content": "ok"}, "↳"),
        ({"type": "tool_result", "content": "bad", "is_error": True}, "✗"),
        ({"type": "thinking", "thinking": "plan"}, "*"),
    ]
    summaries = []
    for index, (block, marker) in enumerate(cases):
        path = tmp_path / f"event-{index}.jsonl"
        path.write_text(
            json.dumps({"message": {"content": [block]}}) + "\n", encoding="utf-8"
        )
        summary = discovery.last_event_summary(str(path), 200)
        summaries.append(summary)
        assert summary.startswith(marker + " ")
        assert not _wide_chars(summary)
    assert (
        len({summary[0] for summary in (summaries[0], summaries[1], summaries[4])}) == 3
    )


def test_terminal_grid_module_sources_contain_no_wide_glyphs():
    for module in (agent_tail, discovery, pane_views):
        assert not _wide_chars(inspect.getsource(module)), module.__file__
