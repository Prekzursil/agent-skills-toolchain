"""``monitorcore.render_html`` — the generic, self-contained, XSS-safe HTML renderer over
``ReportDoc``.

Byte-for-byte fidelity to PR-A's wfmon HTML is proven by the golden harness in the wfmon
lane; here we drive every branch of the *generic* renderer with hand-built ``ReportDoc`` s
(all six block primitives, every tool/thinking mode, the empty-field, single/zero-group,
and non-card-child edges, and the three untrusted XSS channels) to hold the
tools/monitorcore 100% line+branch gate.
"""

from __future__ import annotations

import pytest

from monitorcore.render_html import TOOL_OUTPUT_CAP, render_html
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
def test_full_document_head_header_banners():
    html = render_html(_doc([_group([_card()])]))
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "</html>" in html
    assert '<meta name="wfmon:wf_id" content="wf_x">' in html
    assert "<title>wfmon export &mdash; wf_x</title>" in html
    assert "<h1>Run Name</h1>" in html
    assert "redaction: strict &mdash; 0 masked" in html
    assert "still active" in html
    assert "running: 1 &middot; done: 1" in html
    assert "<style>" in html and "<script>" in html


def test_redact_off_and_inactive_and_no_rollup():
    html = render_html(_doc([], active=False, rollup=()), redact=False)
    assert "redaction: off</div>" in html
    assert "still active" not in html
    assert 'class="rollup"' not in html  # no rollup when empty


def test_no_external_references():
    html = render_html(
        _doc([_group([_card(timeline=(TE(kind="text", seq=0, text="hi"),))])])
    )
    for bad in ('src="http', 'href="http', 'src="//', 'href="//', "url(http"):
        assert bad not in html


# ───────────────────────── DAG ─────────────────────────
def test_dag_multi_phase_has_arrow():
    doc = _doc(
        [
            _group([_card(title="a")]),
            _group(
                [_card(title="c", badge="running", anchor="agent-c")],
                title="Phase B",
                anchor="phase-2",
                index=2,
            ),
        ]
    )
    html = render_html(doc)
    dag = html.split('class="dag"', 1)[1].split("</section>", 1)[0]
    assert 'class="dag-arrow"' in dag
    assert "badge-running" in dag


def test_dag_single_phase_no_arrow():
    html = render_html(_doc([_group([_card()])]))
    dag = html.split('class="dag"', 1)[1].split("</section>", 1)[0]
    assert 'class="dag-arrow"' not in dag


def test_group_with_non_section_child_skipped():
    grp = _group([_card(title="realcard"), Text("loose")])
    html = render_html(_doc([grp]))
    toc = html.split('class="toc"', 1)[1].split("</nav>", 1)[0]
    assert "loose" not in toc
    dag = html.split('class="dag"', 1)[1].split("</section>", 1)[0]
    assert "loose" not in dag
    assert "<p>loose</p>" in html  # still rendered in the body


# ───────────────────────── card fields ─────────────────────────
def test_card_badges_and_empty_fields():
    html = render_html(
        _doc([_group([_card(badge="idle", lead="", task=" ", output="")])])
    )
    assert "badge-idle" in html
    assert (
        '<p class="headline">'
        not in html.split("agent-x", 1)[1].split("</article>", 1)[0]
    )
    assert "no task" in html
    assert "no output" in html


# ───────────────────────── timeline / tools ─────────────────────────
def _rich_timeline():
    return (
        TE(kind="thinking", seq=0, text="thinking hard"),
        TE(kind="text", seq=1, text="a plan"),
        TE(kind="tool_use", seq=2, name="Bash", tool_id="b", tool_input={"cmd": "ls"}),
        TE(kind="tool_result", seq=3, tool_id="b", output="ok"),
        TE(kind="tool_use", seq=4, name="Read", tool_id="orphan"),
        TE(kind="tool_use", seq=5, name="Grep", tool_id="g", tool_input={"p": "x"}),
        TE(kind="tool_result", seq=6, tool_id="g", output="boom", is_error=True),
        TE(kind="tool_use", seq=7, name="Edit", tool_id="e"),
        TE(kind="tool_result", seq=8, tool_id="e", output="   "),
    )


def test_timeline_full_branches():
    html = render_html(_doc([_group([_card(timeline=_rich_timeline())])]), tools="full")
    assert '<div class="ev thinking">' in html and "thinking hard" in html
    assert "<details" in html
    assert "tool-error" in html  # Grep error
    assert "no result" in html  # orphan Read
    assert "no output" in html  # empty Edit result


def test_timeline_summary_branches():
    html = render_html(
        _doc([_group([_card(timeline=_rich_timeline())])]), tools="summary"
    )
    assert "Bash: ok" in html
    assert "Grep: boom (error)" in html
    assert "Read: no result" in html
    assert "Edit: no output" in html
    assert "<details" not in html


def test_timeline_none_and_thinking_off():
    html = render_html(
        _doc([_group([_card(timeline=_rich_timeline())])]), tools="none", thinking=False
    )
    assert "<details" not in html
    assert "thinking hard" not in html
    assert "a plan" in html


def test_summary_empty_name_and_no_output():
    tl = (
        TE(kind="tool_use", seq=0, name="", tool_id="t"),
        TE(kind="tool_use", seq=1, name="B", tool_id="b"),
        TE(kind="tool_result", seq=2, tool_id="b", output="  "),
    )
    html = render_html(_doc([_group([_card(timeline=tl)])]), tools="summary")
    assert "tool: no result" in html
    assert "B: no output" in html


def test_full_empty_name_fallback():
    tl = (
        TE(kind="tool_use", seq=0, name="", tool_id="t", tool_input={"x": 1}),
        TE(kind="tool_result", seq=1, tool_id="t", output="ok"),
    )
    html = render_html(_doc([_group([_card(timeline=tl)])]), tools="full")
    assert ">tool<" in html


def test_multi_channel_xss_escape():
    tl = (
        TE(
            kind="tool_use",
            seq=0,
            name="Bash",
            tool_id="x",
            tool_input={"c": "<script>IN</script>"},
        ),
        TE(kind="tool_result", seq=1, tool_id="x", output="<script>RES</script>"),
    )
    html = render_html(
        _doc([_group([_card(output="<script>OUT</script>", timeline=tl)])]),
        tools="full",
    )
    assert "<script>OUT</script>" not in html
    assert "&lt;script&gt;OUT&lt;/script&gt;" in html
    assert "&lt;script&gt;IN&lt;/script&gt;" in html
    assert "&lt;script&gt;RES&lt;/script&gt;" in html


def test_truncation_and_base64():
    payload = "Q" * 300
    filler = "lorem ipsum dolor sit amet " * 400
    big = f"data:image/png;base64,{payload} {filler}"
    assert len(big.encode()) > TOOL_OUTPUT_CAP
    tl = (
        TE(kind="tool_use", seq=0, name="Bash", tool_id="x"),
        TE(kind="tool_result", seq=1, tool_id="x", output=big),
    )
    html = render_html(_doc([_group([_card(timeline=tl)])]), tools="full")
    assert "base64 image elided" in html
    assert "bytes elided @2000" in html
    assert filler not in html


# ───────────────────────── generic primitives ─────────────────────────
def test_heading_with_and_without_anchor():
    html = render_html(
        _doc([Heading("Top", level=1, anchor="a"), Heading("Sub", level=3)])
    )
    assert '<h1 id="a">Top</h1>' in html
    assert "<h3>Sub</h3>" in html


def test_text_variants_and_redact():
    html = render_html(
        _doc(
            [
                Text("plain"),
                Text("quote", variant="blockquote"),
                Text("emph", variant="emphasis"),
                Text("sk-FAKE0000000000000000000000", redact=True),
            ]
        )
    )
    assert "<p>plain</p>" in html
    assert "<blockquote>quote</blockquote>" in html
    assert '<p class="headline">emph</p>' in html
    assert "[REDACTED:api-key]" in html


def test_code_with_label_redact_and_plain():
    html = render_html(
        _doc(
            [
                Code("sk-FAKE0000000000000000000000", label="thinking"),
                Code("<raw>", redact=False),
            ]
        )
    )
    assert "<h4>thinking</h4>" in html
    assert "[REDACTED:api-key]" in html
    assert "&lt;raw&gt;" in html  # plain code still HTML-escaped


def test_kv_and_table():
    html = render_html(
        _doc(
            [
                KV(pairs=(("k1", "v1"),)),
                Table(headers=("A", "B"), rows=(("1", "2"),)),
            ]
        )
    )
    assert "<dt>k1</dt><dd>v1</dd>" in html
    assert "<th>A</th>" in html and "<td>1</td>" in html


# ───────────────────────── purity ─────────────────────────
def test_deterministic():
    doc = _doc([_group([_card(timeline=_rich_timeline())])])
    assert render_html(doc) == render_html(doc)


@pytest.mark.parametrize("tools", ["full", "summary", "none"])
def test_all_tool_modes(tools):
    html = render_html(_doc([_group([_card(timeline=_rich_timeline())])]), tools=tools)
    assert isinstance(html, str) and html.strip()
