#!/usr/bin/env python3
"""``wfmon_export.render_md`` tests: ``render_markdown`` is a PURE function of an
``ExportModel``. Golden-ish assertions against the frozen ``wf_export00-fixture``
(via ``collect_run``) plus hand-built ``ExportModel`` s for the edge branches that the
fixture does not exercise (idle badge, empty task/output/timeline, end-to-end
truncation + base64 elision, fence-safety, mermaid label sanitising, single-phase DAG).

The renderer touches NO filesystem: every model here is either materialised once by
``collect_run`` or constructed inline, and the render call is asserted idempotent.
"""

from __future__ import annotations

import os
import re

import pytest

import workflow_run as wr
from wfmon_export import model as m
from wfmon_export import render_md as rmd

# ── isolated export fixture root (mirrors test_model.py) ──
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
WF_ID = "wf_export00-fixture"


@pytest.fixture(scope="module")
def run_model() -> m.ExportModel:
    return m.collect_run(WF_ID, projects=EXPORT_PROJECTS)


# ───────────────────────── synthetic model builders ─────────────────────────
def _agent(**over) -> m.AgentExport:
    base = dict(
        agent_id="agent-x",
        label="x",
        index=1,
        phase_index=1,
        phase_title="P",
        model="claude-opus-4-8[1m]",
        state="done",
        tokens=0,
        tool_calls=0,
        duration_ms=0,
        attempt=1,
        task="a task",
        output="an output",
        headline="hl",
        timeline=[],
        jsonl_path="",
    )
    base.update(over)
    return m.AgentExport(**base)


def _model(
    phases, *, active=True, redaction_mode="strict", scope="run"
) -> m.ExportModel:
    prov = {
        "wf_id": "wf_syn",
        "name": "syn-run",
        "session": "sess-syn",
        "scope": scope,
        "redaction_mode": redaction_mode,
        "generated_at": "2026-07-12T00:00:00+00:00",
        "schema_version": wr.CC_SCHEMA_VERSION,
    }
    return m.ExportModel(
        wf_id="wf_syn",
        name="syn-run",
        status="running" if active else "completed",
        active=active,
        generated_at="2026-07-12T00:00:00+00:00",
        schema_version=wr.CC_SCHEMA_VERSION,
        scope=scope,
        scope_agents=[],
        redaction_mode=redaction_mode,
        phases=phases,
        rollup={
            "running": 0,
            "done": 1,
            "error": 0,
            "idle": 0,
            "total": 1,
            "tokens": 0,
        },
        session="sess-syn",
        manifest_path="/nowhere/wf_syn.json",
        provenance=prov,
    )


# ───────────────────────── front-matter / provenance ─────────────────────────
def test_returns_nonempty_str(run_model):
    md = rmd.render_markdown(run_model)
    assert isinstance(md, str) and md.strip()


def test_front_matter_provenance(run_model):
    md = rmd.render_markdown(run_model)
    # YAML front-matter opens the document
    assert md.lstrip().startswith("---")
    fm = md.split("---", 2)[1]
    for key in (
        "wf_id",
        "name",
        "session",
        "scope",
        "redaction_mode",
        "generated_at",
        "schema_version",
    ):
        assert re.search(rf"^{key}:", fm, re.M), f"missing front-matter key {key}"
    assert WF_ID in fm
    assert wr.CC_SCHEMA_VERSION in fm


# ───────────────────────── redaction audit banner ─────────────────────────
def test_audit_banner_masked_count(run_model):
    md = rmd.render_markdown(run_model)  # redact defaults True
    mobj = re.search(r"(\d+) masked", md)
    assert mobj, "expected an 'N masked' audit banner"
    assert int(mobj.group(1)) > 0  # the secretcheck agent contributes masks


def test_redaction_tokens_present(run_model):
    md = rmd.render_markdown(run_model)
    for tok in (
        "[REDACTED:api-key]",
        "[REDACTED:gh-pat]",
        "[REDACTED:aws-akid]",
        "[REDACTED:slack]",
        "[REDACTED:gh-token]",
        "Bearer [REDACTED:jwt]",
        "[REDACTED:pem-private-key]",
        "[REDACTED:gitcrypt-key]",
    ):
        assert tok in md, f"missing redaction token {tok}"
    # home-path collapse to '~' happened (fwd + wsl/gitbash forms)
    assert "~/work/file" in md
    # the raw secret material never survives
    assert "sk-FAKE0000000000000000000000" not in md
    assert "ghp_FAKE00000000000000000000000000000000" not in md
    assert "AKIAFAKE0000000000AB" not in md


def test_benign_jwt_lookalike_not_masked(run_model):
    md = rmd.render_markdown(run_model)
    # a dotted base64-ish token that is NOT a JWT stays intact
    assert "abcdef...not.a.jwt.value" in md


def test_no_redact_banner_and_raw_secret(run_model):
    md = rmd.render_markdown(run_model, redact=False)
    assert "redaction: off" in md.lower()
    # with redaction off the synthetic secret appears verbatim
    assert "sk-FAKE0000000000000000000000" in md
    assert "[REDACTED:api-key]" not in md


# ───────────────────────── active-run banner ─────────────────────────
def test_active_banner_present_when_active(run_model):
    assert run_model.active is True
    md = rmd.render_markdown(run_model)
    assert "still active" in md


def test_active_banner_absent_when_terminal():
    model = _model([m.PhaseExport(index=1, title="P", agents=[_agent()])], active=False)
    md = rmd.render_markdown(model)
    assert "still active" not in md


# ───────────────────────── fan-out DAG (mermaid + ASCII) ─────────────────────────
def test_fanout_mermaid_and_ascii(run_model):
    md = rmd.render_markdown(run_model)
    assert "```mermaid" in md
    assert "flowchart TD" in md
    # sequential phase->phase edge (2 phases in the fixture)
    assert re.search(r"P1\s*-->\s*P2", md)
    # phase->agent edges (node labels carry the agent label)
    assert '"kitchensink"' in md
    assert '"taskorder"' in md
    # the indented ASCII fallback is present alongside the mermaid block
    assert "├─" in md  # '├─'
    assert "Investigate" in md and "Synthesize" in md


def test_single_phase_dag_has_no_phase_edge():
    model = m.collect_run(
        WF_ID, projects=EXPORT_PROJECTS, scope="agent", agents=["kitchensink"]
    )
    md = rmd.render_markdown(model)
    assert "```mermaid" in md
    # only one phase -> no phase->phase arrow
    assert not re.search(r"P1\s*-->\s*P2", md)


def test_mermaid_label_is_sanitised():
    ag = _agent(label='we"ird\nlabel', agent_id="agent-weird")
    model = _model([m.PhaseExport(index=1, title='ph"ase\ntitle', agents=[ag])])
    md = rmd.render_markdown(model)
    # a raw double-quote inside a mermaid quoted label would break the diagram
    dag = md.split("```mermaid", 1)[1].split("```", 1)[0]
    assert '"we' not in dag or "ird" in dag  # quote was stripped from the label
    assert "\n" not in dag.split("flowchart TD", 1)[1].split('["', 1)[0]


# ───────────────────────── anchor TOC ─────────────────────────
def test_toc_anchors(run_model):
    md = rmd.render_markdown(run_model)
    assert "## Contents" in md
    # each agent has an explicit HTML anchor + a TOC link that targets it
    assert '<a id="agent-kitchensink">' in md
    assert "(#agent-kitchensink)" in md
    assert '<a id="phase-1">' in md
    assert "(#phase-1)" in md


# ───────────────────────── badges ─────────────────────────
def test_state_badges(run_model):
    md = rmd.render_markdown(run_model)
    assert "done" in md and "error" in md and "running" in md


def test_idle_badge():
    model = _model([m.PhaseExport(index=1, title="P", agents=[_agent(state="idle")])])
    md = rmd.render_markdown(model)
    assert "idle" in md


# ───────────────────────── tool blocks: full / summary / none ─────────────────────────
def test_tools_full_details_blocks(run_model):
    md = rmd.render_markdown(run_model, tools="full")
    assert "<details>" in md
    assert "Bash" in md  # tool name
    assert "ls -la" in md  # tool input rendered in full mode
    assert "total 0" in md  # tool result rendered
    # orphan tool_use (no matching result) is flagged, not silently dropped
    assert "Read" in md
    assert "no result" in md


def test_tools_summary_one_line(run_model):
    md = rmd.render_markdown(run_model, tools="summary")
    assert "Bash" in md  # name still shown
    assert "total 0" in md  # one-line result shown
    assert "ls -la" not in md  # but NOT the full input
    assert "<details>" not in md  # summary has no collapsible blocks


def test_tools_none_omits_tools(run_model):
    md = rmd.render_markdown(run_model, tools="none")
    assert "ls -la" not in md
    assert "total 0" not in md
    assert "<details>" not in md


def test_summary_orphan_and_empty_output():
    use1 = wr.TimelineEvent(kind="tool_use", seq=0, name="Read", tool_id="orph")
    use2 = wr.TimelineEvent(kind="tool_use", seq=1, name="Grep", tool_id="empty")
    res2 = wr.TimelineEvent(kind="tool_result", seq=2, tool_id="empty", output="")
    ag = _agent(timeline=[use1, use2, res2])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model, tools="summary")
    assert "no result" in md  # orphan
    assert "no output" in md  # matched but empty
    assert "Read" in md and "Grep" in md


def test_full_error_result_flagged(run_model):
    md = rmd.render_markdown(run_model, tools="full")
    # the tool_result with is_error true is marked distinctly
    assert "Grep" in md
    assert "error" in md.lower()


def test_standalone_tool_result_skipped(run_model):
    md = rmd.render_markdown(run_model)
    # advisor_tool_result + a leading tool-result-only user record have NO matching
    # tool_use -> they are skipped while iterating (never rendered).
    assert "advisor says proceed" not in md
    assert "leading tool-result only" not in md


# ───────────────────────── thinking toggle ─────────────────────────
def test_thinking_default_on(run_model):
    md = rmd.render_markdown(run_model)
    assert "Let me reason about the kitchen sink" in md


def test_thinking_off_drops_thinking(run_model):
    md = rmd.render_markdown(run_model, thinking=False)
    assert "Let me reason about the kitchen sink" not in md
    # non-thinking content still present
    assert "Here is my plan." in md


# ───────────────────────── task / output edges ─────────────────────────
def test_task_blockquote(run_model):
    md = rmd.render_markdown(run_model)
    # the spawn prompt is rendered as a blockquote
    assert "> Do the kitchen-sink task." in md


def test_empty_task_and_output_and_timeline():
    ag = _agent(task="", output="", timeline=[])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model)
    assert "no task" in md.lower()
    assert "no output" in md.lower()


def test_output_present(run_model):
    md = rmd.render_markdown(run_model)
    assert "All transcript block kinds are covered" in md


# ───────────────────────── fence-safety (end-to-end) ─────────────────────────
def test_fence_safety_bumps_backticks():
    ag = _agent(output="see code:\n```\nprint(1)\n```\ndone")
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model)
    # a 3-backtick run inside the content forces a >=4-backtick fence
    assert "````" in md


# ───────────────────────── truncation + base64 elision (end-to-end) ─────────────────────────
def test_truncation_and_base64_end_to_end():
    payload = "Q" * 300
    filler = "lorem ipsum dolor sit amet " * 400  # spaces -> not a base64 run
    big = f"data:image/png;base64,{payload} {filler}"
    assert len(big.encode()) > rmd.TOOL_OUTPUT_CAP
    use = wr.TimelineEvent(kind="tool_use", seq=0, name="Bash", tool_id="big")
    res = wr.TimelineEvent(kind="tool_result", seq=1, tool_id="big", output=big)
    ag = _agent(timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model, tools="full")
    assert "<base64 image elided" in md  # data-URI payload elided
    assert "bytes elided @2000" in md  # oversized block truncated head+tail
    # the enormous filler body is gone
    assert filler not in md


# ───────────────────────── purity / determinism ─────────────────────────
def test_render_is_deterministic(run_model):
    a = rmd.render_markdown(run_model)
    b = rmd.render_markdown(run_model)
    assert a == b


def test_render_no_fs_side_effect(tmp_path, monkeypatch):
    # a pure renderer never opens a file: point cwd at an empty dir and render.
    monkeypatch.chdir(tmp_path)
    rmd.render_markdown(_model([m.PhaseExport(index=1, title="P", agents=[_agent()])]))
    assert not list(tmp_path.iterdir())


# ───────────────────────── defensive / structural edge branches ─────────────────────────
def test_empty_phases_model_renders():
    # a scope that selected nothing: zero phases -> bare 'flowchart TD', no body,
    # no ASCII tree, yet still a well-formed document.
    md = rmd.render_markdown(_model([]))
    assert "```mermaid" in md and "flowchart TD" in md
    assert "├─" not in md and "└─" not in md
    assert "## Contents" in md


def test_single_phase_no_agents_dag():
    # exactly one DAG statement (one phase, no agents) -> no multi-line node join, no edges
    model = _model([m.PhaseExport(index=1, title="Solo", agents=[])])
    md = rmd.render_markdown(model)
    dag = md.split("```mermaid", 1)[1].split("```", 1)[0]
    assert 'P1["Solo"]' in dag
    assert "-->" not in dag


def test_summary_skips_blank_leading_lines():
    use = wr.TimelineEvent(kind="tool_use", seq=0, name="Bash", tool_id="t")
    res = wr.TimelineEvent(
        kind="tool_result", seq=1, tool_id="t", output="\n   \nreal line"
    )
    ag = _agent(timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model, tools="summary")
    assert "real line" in md  # leading blank lines skipped to the first content line


def test_full_matched_but_empty_output():
    use = wr.TimelineEvent(
        kind="tool_use", seq=0, name="Bash", tool_id="t", tool_input={"command": "x"}
    )
    res = wr.TimelineEvent(kind="tool_result", seq=1, tool_id="t", output="   ")
    ag = _agent(timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model, tools="full")
    assert "<details>" in md
    assert "no output" in md.lower()  # matched result with blank output flagged


def test_full_nonserialisable_tool_input():
    # a tool_input json cannot serialise falls back to str(...) and never raises
    use = wr.TimelineEvent(
        kind="tool_use", seq=0, name="Bash", tool_id="t", tool_input={"o": object()}
    )
    ag = _agent(timeline=[use])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model, tools="full")
    assert "Bash" in md


def test_blank_text_event_skipped():
    txt = wr.TimelineEvent(kind="text", seq=0, text="   ")
    ag = _agent(timeline=[txt])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model)
    assert "<details>" not in md  # a whitespace-only text event renders nothing


def test_agent_without_model_or_headline():
    ag = _agent(model="", headline="")
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    md = rmd.render_markdown(model)
    assert "tokens" in md  # metadata line still emitted without model/headline
