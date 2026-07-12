"""``monitorcore.render_md`` — the generic Markdown renderer over ``ReportDoc``.

Byte-for-byte fidelity to PR-A's wfmon output is proven by the golden harness in the
wfmon lane; here we drive every branch of the *generic* renderer with hand-built
``ReportDoc`` s (all six block primitives, every tool/thinking mode, the empty-field and
single/zero-group edges) to hold the tools/monitorcore 100% line+branch gate.
"""

from __future__ import annotations

import pytest

from monitorcore.render_md import TOOL_OUTPUT_CAP, render_md
from monitorcore.report_doc import (
    Code,
    Heading,
    KV,
    ReportDoc,
    Section,
    Table,
    Text,
)
from monitorcore.timeline import TimelineEvent as TE


def _doc(blocks=(), **over) -> ReportDoc:
    base = dict(
        title="Run Name",
        generated_at="2026-07-12T00:00:00+00:00",
        subtitle="wf_x",
        meta=(("wf_id", "wf_x"), ("name", "Run Name")),
        rollup=(
            ("running", 1),
            ("done", 1),
            ("error", 1),
            ("idle", 1),
            ("total", 4),
            ("tokens", 1750),
        ),
        active=True,
        redaction_mode="strict",
        blocks=tuple(blocks),
    )
    base.update(over)
    return ReportDoc(**base)


def _card(**over) -> Section:
    base = dict(
        title="agentx",
        anchor="agent-x",
        card=True,
        badge="done",
        model="claude-opus-4-8[1m]",
        tokens=100,
        tool_calls=2,
        attempt=1,
        duration_ms=5,
        lead="a headline",
        task="do the task",
        output="the output",
        timeline=(),
    )
    base.update(over)
    return Section(**base)


def _group(cards, **over) -> Section:
    base = dict(title="Phase A", anchor="phase-1", index=1, children=tuple(cards))
    base.update(over)
    return Section(**base)


# ───────────────────────── document chrome ─────────────────────────
def test_front_matter_title_banner_rollup():
    md = render_md(_doc([_group([_card()])]))
    assert md.startswith("---\n")
    assert "# Run Name (`wf_x`)" in md
    assert "> **redaction: strict** - 0 masked" in md
    assert "still active" in md
    assert (
        "**Agents:** 4 total - 1 done - 1 error - 1 running - 1 idle - 1,750 tokens"
        in md
    )


def test_redact_off_banner():
    md = render_md(_doc([_group([_card()])]), redact=False)
    assert "redaction: off" in md.lower()


def test_inactive_no_rollup_no_body():
    md = render_md(_doc([], active=False, rollup=()))
    assert "still active" not in md
    assert "**Agents:**" not in md
    # zero blocks -> no body, but still a well-formed doc with contents + fan-out
    assert "## Contents" in md and "flowchart TD" in md


# ───────────────────────── fan-out DAG ─────────────────────────
def test_fanout_multi_phase_edge_and_ascii():
    doc = _doc(
        [
            _group(
                [
                    _card(anchor="agent-a", title="a"),
                    _card(anchor="agent-b", title="b", badge="error"),
                ]
            ),
            _group(
                [_card(anchor="agent-c", title="c", badge="running")],
                title="Phase B",
                anchor="phase-2",
                index=2,
            ),
        ]
    )
    md = render_md(doc)
    assert "P1 --> P2" in md
    assert 'A0["a"]' in md and 'A2["c"]' in md
    assert "├─ a [done]" in md and "└─ b [error]" in md


def test_fanout_single_phase_no_edge():
    md = render_md(_doc([_group([_card()])]))
    assert "P1 -->" in md  # phase->agent edge exists
    assert "P1 --> P2" not in md  # but no phase->phase edge


def test_fanout_single_statement_no_multiline():
    # one group, no cards -> exactly one mermaid statement, no edges/ascii tree
    md = render_md(_doc([_group([])]))
    dag = md.split("```mermaid", 1)[1].split("```", 1)[0]
    assert 'P1["Phase A"]' in dag and "-->" not in dag
    assert "├─" not in md and "└─" not in md


def test_fanout_zero_groups_bare_flowchart():
    md = render_md(_doc([Heading("only text")]))
    assert "flowchart TD\n```" in md  # bare flowchart, no statements


def test_mermaid_label_sanitised():
    md = render_md(_doc([_group([_card(title='we"ird\nlabel')])]))
    dag = md.split("```mermaid", 1)[1].split("```", 1)[0]
    assert "we'ird label" in dag  # inner quote -> apostrophe, newline -> space
    assert 'we"ird' not in dag  # the raw double quote is gone


def test_group_with_non_section_child_skipped_in_toc_and_dag():
    # a group may carry non-card children; they render in the body but are excluded
    # from the TOC + fan-out (which enumerate cards only).
    grp = _group([_card(title="realcard"), Text("loose text in group")])
    md = render_md(_doc([grp]))
    assert "loose text in group" in md  # body renders it
    toc = md.split("## Contents", 1)[1].split("## Fan-out", 1)[0]
    assert "loose text in group" not in toc  # but TOC skips the non-card
    dag = md.split("```mermaid", 1)[1].split("```", 1)[0]
    assert "loose text in group" not in dag


# ───────────────────────── card fields ─────────────────────────
def test_card_idle_badge_and_missing_model_and_attempt():
    md = render_md(_doc([_group([_card(badge="", model="", attempt=3)])]))
    assert "agentx - idle" in md  # empty badge -> idle
    assert "attempt 3" in md
    assert "`claude" not in md  # no model backtick when model empty


def test_card_empty_task_output_lead_timeline():
    md = render_md(_doc([_group([_card(task=" ", output="", lead=" ", timeline=())])]))
    assert "_(no task)_" in md
    assert "_(no output)_" in md
    assert "**Transcript:**" not in md  # empty timeline -> no transcript section


# ───────────────────────── timeline / tools ─────────────────────────
def _rich_timeline():
    return (
        TE(kind="thinking", seq=0, text="thinking hard"),
        TE(kind="thinking", seq=1, text="   "),  # blank thinking -> skipped
        TE(kind="text", seq=2, text="a plan"),
        TE(kind="text", seq=3, text="  "),  # blank text -> skipped
        TE(kind="tool_use", seq=4, name="Bash", tool_id="b", tool_input={"cmd": "ls"}),
        TE(kind="tool_result", seq=5, tool_id="b", output="ok"),
        TE(kind="tool_use", seq=6, name="Read", tool_id="orphan"),  # no result
        TE(kind="tool_use", seq=7, name="Grep", tool_id="g", tool_input={"p": "x"}),
        TE(kind="tool_result", seq=8, tool_id="g", output="boom", is_error=True),
        TE(kind="tool_use", seq=9, name="Edit", tool_id="e"),  # no input
        TE(kind="tool_result", seq=10, tool_id="e", output="   "),  # empty output
    )


def test_timeline_full_all_branches():
    md = render_md(_doc([_group([_card(timeline=_rich_timeline())])]), tools="full")
    assert "thinking hard" in md and "   \n" not in md.split("thinking hard")[0]
    assert "a plan" in md
    assert "<details>" in md and "🔧 Bash" in md
    assert "🔧 Grep - error" in md
    assert "_(no result)_" in md  # orphan Read
    assert "_(no output)_" in md  # empty Edit result


def test_timeline_summary_all_branches():
    md = render_md(_doc([_group([_card(timeline=_rich_timeline())])]), tools="summary")
    assert "- **Bash** -> ok" in md
    assert "- **Grep** -> error: boom" in md
    assert "- **Read** -> _(no result)_" in md
    assert "- **Edit** -> _(no output)_" in md
    assert "<details>" not in md


def test_timeline_none_and_thinking_off():
    md = render_md(
        _doc([_group([_card(timeline=_rich_timeline())])]), tools="none", thinking=False
    )
    assert "<details>" not in md and "- **Bash**" not in md
    assert "thinking hard" not in md
    assert "a plan" in md  # non-thinking text still present


def test_tool_full_empty_name_and_nonserialisable_input():
    tl = (TE(kind="tool_use", seq=0, name="", tool_id="t", tool_input={"o": object()}),)
    md = render_md(_doc([_group([_card(timeline=tl)])]), tools="full")
    assert "🔧 tool" in md  # empty name -> 'tool'


def test_summary_empty_name_and_blank_result_line():
    tl = (
        TE(kind="tool_use", seq=0, name="", tool_id="t"),
        TE(kind="tool_use", seq=1, name="B", tool_id="b"),
        TE(kind="tool_result", seq=2, tool_id="b", output="\n \nfirst"),
    )
    md = render_md(_doc([_group([_card(timeline=tl)])]), tools="summary")
    assert "- **tool** ->" in md
    assert "- **B** -> first" in md  # leading blank lines skipped


def test_fence_bumps_backticks_and_truncation():
    payload = "Q" * 300
    filler = "lorem ipsum dolor sit amet " * 400
    big = f"data:image/png;base64,{payload} {filler}"
    assert len(big.encode()) > TOOL_OUTPUT_CAP
    tl = (
        TE(kind="tool_use", seq=0, name="Bash", tool_id="x"),
        TE(kind="tool_result", seq=1, tool_id="x", output=big),
    )
    md = render_md(
        _doc([_group([_card(output="```\ncode\n```", timeline=tl)])]), tools="full"
    )
    assert "````" in md  # fence bumped past the inner 3-backtick run
    assert "<base64 image elided" in md
    assert "bytes elided @2000" in md
    assert filler not in md


# ───────────────────────── generic primitives ─────────────────────────
def test_heading_with_and_without_anchor():
    md = render_md(_doc([Heading("Top", level=1, anchor="a"), Heading("Sub", level=3)]))
    assert '# <a id="a"></a>Top' in md
    assert "### Sub" in md


def test_text_variants_and_redact():
    md = render_md(
        _doc(
            [
                Text("plain line"),
                Text("quoted\nlines", variant="blockquote"),
                Text("emph", variant="emphasis"),
                Text("token sk-FAKE0000000000000000000000", redact=True),
            ]
        )
    )
    assert "plain line" in md
    assert "> quoted\n> lines" in md
    assert "_emph_" in md
    assert "[REDACTED:api-key]" in md


def test_text_blockquote_empty():
    md = render_md(_doc([Text("", variant="blockquote")]))
    assert "> " in md


def test_code_with_label_redact_and_plain():
    md = render_md(
        _doc(
            [
                Code("secret sk-FAKE0000000000000000000000", label="thinking"),
                Code("raw ```body```", redact=False),
            ]
        )
    )
    assert "*thinking:*" in md
    assert "[REDACTED:api-key]" in md
    assert "````" in md  # fence bumped for the raw code with inner backticks


def test_kv_and_table():
    md = render_md(
        _doc(
            [
                KV(pairs=(("k1", "v1"), ("k2", "v2"))),
                Table(headers=("A", "B"), rows=(("1", "2"), ("3", "4"))),
            ]
        )
    )
    assert "- **k1:** v1" in md
    assert "| A | B |" in md and "| --- | --- |" in md and "| 1 | 2 |" in md


# ───────────────────────── purity ─────────────────────────
def test_deterministic():
    doc = _doc([_group([_card(timeline=_rich_timeline())])])
    assert render_md(doc) == render_md(doc)


@pytest.mark.parametrize("tools", ["full", "summary", "none"])
def test_all_tool_modes_render(tools):
    md = render_md(_doc([_group([_card(timeline=_rich_timeline())])]), tools=tools)
    assert isinstance(md, str) and md.strip()
