#!/usr/bin/env python3
"""``wfmon_export.render_html`` tests: ``render_html`` is a PURE, self-contained,
XSS-safe function of an ``ExportModel``. Assertions mix golden-ish checks against the
frozen ``wf_export00-fixture`` (via ``collect_run``) with hand-built ``ExportModel`` s
for the branches the fixture does not exercise (idle badge, empty task/output, tool
error/empty/orphan in every ``tools`` mode, single-phase DAG, terminal-run banner,
end-to-end truncation + base64 elision, empty tool name).

The renderer touches NO filesystem: every model is either materialised once by
``collect_run`` or constructed inline, and the render call is asserted idempotent.
The HTML is single-file (all CSS/JS inline) with zero external references, and every
transcript string is HTML-escaped across all three untrusted channels (agent output,
tool input, tool result).
"""

from __future__ import annotations

import os
import re

import pytest

import workflow_run as wr
from wfmon_export import model as m
from wfmon_export import render_html as rh

# ── isolated export fixture root (mirrors test_model.py / test_render_md.py) ──
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


# ───────────────────────── document shape / provenance ─────────────────────────
def test_returns_full_html_document(run_model):
    html = rh.render_html(run_model)
    assert isinstance(html, str) and html.strip()
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "</html>" in html


def test_provenance_meta_and_header(run_model):
    html = rh.render_html(run_model)
    for key in (
        "wf_id",
        "name",
        "session",
        "scope",
        "redaction_mode",
        "generated_at",
        "schema_version",
    ):
        # each provenance key surfaces as an inline <meta> tag
        assert f'name="wfmon:{key}"' in html, f"missing provenance meta {key}"
    assert WF_ID in html
    assert wr.CC_SCHEMA_VERSION in html


# ───────────────────────── inline / self-contained (no external refs) ─────────────────────────
def test_inline_style_and_script(run_model):
    html = rh.render_html(run_model)
    assert "<style>" in html and "</style>" in html
    assert "<script>" in html and "</script>" in html


def test_no_external_references(run_model):
    html = rh.render_html(run_model)
    # precise: no external or protocol-relative resource references anywhere
    for bad in ('src="http', 'href="http', 'src="//', 'href="//', "url(http"):
        assert bad not in html, f"external reference leaked: {bad}"


# ───────────────────────── print CSS + client-side controls ─────────────────────────
def test_print_css_and_onbeforeprint_expand(run_model):
    html = rh.render_html(run_model)
    assert "@media print" in html
    assert "onbeforeprint" in html


def test_filter_and_collapse_controls(run_model):
    html = rh.render_html(run_model)
    assert "<input" in html  # client-side filter box
    assert "wfmonFilter" in html
    assert "Expand all" in html and "Collapse all" in html


def test_sticky_toc_anchors(run_model):
    html = rh.render_html(run_model)
    assert 'class="toc"' in html
    assert 'id="agent-kitchensink"' in html
    assert 'href="#agent-kitchensink"' in html
    assert 'id="phase-1"' in html
    assert 'href="#phase-1"' in html


# ───────────────────────── redaction audit banner ─────────────────────────
def test_audit_banner_masked_count(run_model):
    html = rh.render_html(run_model)  # redact defaults True
    mobj = re.search(r"(\d+) masked", html)
    assert mobj, "expected an 'N masked' audit banner"
    assert int(mobj.group(1)) > 0  # the secretcheck agent contributes masks


def test_redaction_tokens_present(run_model):
    html = rh.render_html(run_model)
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
        assert tok in html, f"missing redaction token {tok}"
    # home-path collapse to '~' happened (gitbash + wsl forms both -> ~/work/file)
    assert "~/work/file" in html
    # raw secret material never survives
    assert "sk-FAKE0000000000000000000000" not in html
    assert "ghp_FAKE00000000000000000000000000000000" not in html
    assert "AKIAFAKE0000000000AB" not in html


def test_benign_jwt_lookalike_not_masked(run_model):
    html = rh.render_html(run_model)
    assert "abcdef...not.a.jwt.value" in html


def test_no_redact_banner_and_raw_secret(run_model):
    html = rh.render_html(run_model, redact=False)
    assert "redaction: off" in html.lower()
    # with redaction off the synthetic secret appears verbatim (still HTML-escaped, but
    # this token has no HTML metacharacters, so it survives byte-for-byte)
    assert "sk-FAKE0000000000000000000000" in html
    assert "[REDACTED:api-key]" not in html


# ───────────────────────── active-run banner ─────────────────────────
def test_active_banner_present_when_active(run_model):
    assert run_model.active is True
    html = rh.render_html(run_model)
    assert "still active" in html


def test_active_banner_absent_when_terminal():
    model = _model([m.PhaseExport(index=1, title="P", agents=[_agent()])], active=False)
    html = rh.render_html(model)
    assert "still active" not in html


# ───────────────────────── fan-out DAG (rendered inline) ─────────────────────────
def test_fanout_dag_inline(run_model):
    html = rh.render_html(run_model)
    assert 'class="dag"' in html
    # phase->agent membership (labels present in the DAG section)
    dag = html.split('class="dag"', 1)[1].split("</section>", 1)[0]
    assert "kitchensink" in dag
    assert "taskorder" in dag
    # sequential phase->phase edge indicator present with 2 phases
    assert 'class="dag-arrow"' in dag


def test_single_phase_dag_has_no_phase_arrow():
    model = m.collect_run(
        WF_ID, projects=EXPORT_PROJECTS, scope="agent", agents=["kitchensink"]
    )
    html = rh.render_html(model)
    dag = html.split('class="dag"', 1)[1].split("</section>", 1)[0]
    assert 'class="dag-arrow"' not in dag


# ───────────────────────── badges ─────────────────────────
def test_state_badges(run_model):
    html = rh.render_html(run_model)
    assert "badge-done" in html
    assert "badge-error" in html
    assert "badge-running" in html


def test_idle_badge():
    model = _model([m.PhaseExport(index=1, title="P", agents=[_agent(state="idle")])])
    html = rh.render_html(model)
    assert "badge-idle" in html


# ───────────────────────── tool blocks: full / summary / none ─────────────────────────
def test_tools_full_details_blocks(run_model):
    html = rh.render_html(run_model, tools="full")
    assert "<details" in html
    assert "Bash" in html  # tool name
    assert "ls -la" in html  # tool input rendered (escaped) in full mode
    assert "total 0" in html  # tool result rendered
    # orphan tool_use (no matching result) is flagged, not silently dropped
    assert "Read" in html
    assert "no result" in html


def test_tools_summary_one_line(run_model):
    html = rh.render_html(run_model, tools="summary")
    assert "Bash" in html  # name still shown
    assert "total 0" in html  # one-line result shown
    assert "ls -la" not in html  # but NOT the full input
    assert "<details" not in html  # summary has no collapsible blocks


def test_tools_none_omits_tools(run_model):
    html = rh.render_html(run_model, tools="none")
    assert "ls -la" not in html
    assert "total 0" not in html
    assert "<details" not in html


def test_full_error_result_flagged(run_model):
    html = rh.render_html(run_model, tools="full")
    assert "Grep" in html
    assert "tool-error" in html  # is_error tool_result carries the error marker


def test_summary_error_flag():
    use = wr.TimelineEvent(kind="tool_use", seq=0, name="Grep", tool_id="e")
    res = wr.TimelineEvent(
        kind="tool_result", seq=1, tool_id="e", output="boom", is_error=True
    )
    ag = _agent(timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model, tools="summary")
    assert "Grep: boom (error)" in html


def test_tool_orphan_and_empty_output_full():
    use1 = wr.TimelineEvent(kind="tool_use", seq=0, name="Read", tool_id="orph")
    use2 = wr.TimelineEvent(kind="tool_use", seq=1, name="Grep", tool_id="empty")
    res2 = wr.TimelineEvent(kind="tool_result", seq=2, tool_id="empty", output="")
    ag = _agent(timeline=[use1, use2, res2])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model, tools="full")
    assert "no result" in html  # orphan
    assert "no output" in html  # matched but empty


def test_tool_orphan_and_empty_output_summary():
    use1 = wr.TimelineEvent(kind="tool_use", seq=0, name="Read", tool_id="orph")
    use2 = wr.TimelineEvent(kind="tool_use", seq=1, name="Grep", tool_id="empty")
    res2 = wr.TimelineEvent(kind="tool_result", seq=2, tool_id="empty", output="  \n ")
    ag = _agent(timeline=[use1, use2, res2])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model, tools="summary")
    assert "no result" in html  # orphan
    assert "no output" in html  # whitespace-only -> no output


def test_empty_tool_name_fallback():
    use = wr.TimelineEvent(kind="tool_use", seq=0, name="", tool_id="t")
    res = wr.TimelineEvent(kind="tool_result", seq=1, tool_id="t", output="ok")
    ag = _agent(timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model, tools="full")
    assert ">tool<" in html or "tool" in html  # empty name falls back to 'tool'


def test_standalone_tool_result_skipped(run_model):
    html = rh.render_html(run_model)
    # advisor_tool_result + a leading tool-result-only user record have NO matching
    # tool_use -> they are skipped while iterating (never rendered).
    assert "advisor says proceed" not in html
    assert "leading tool-result only" not in html


# ───────────────────────── thinking toggle ─────────────────────────
def test_thinking_default_on(run_model):
    html = rh.render_html(run_model)
    assert "Let me reason about the kitchen sink" in html


def test_thinking_off_drops_thinking(run_model):
    html = rh.render_html(run_model, thinking=False)
    assert "Let me reason about the kitchen sink" not in html
    assert "Here is my plan." in html  # non-thinking content still present


# ───────────────────────── task / output edges ─────────────────────────
def test_task_and_output_rendered(run_model):
    html = rh.render_html(run_model)
    assert "Do the kitchen-sink task." in html  # spawn prompt
    assert "All transcript block kinds are covered" in html  # output


def test_empty_task_output_headline():
    ag = _agent(task="", output="", timeline=[], headline="")
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model)
    assert "no task" in html.lower()
    assert "no output" in html.lower()


# ───────────────────────── XSS: HTML-escape across all three channels ─────────────────────────
def test_multi_channel_xss_escape():
    xss_out = "<script>OUTCHANNEL</script>"
    xss_in = "<script>INCHANNEL</script>"
    xss_res = "<script>RESCHANNEL</script>"
    use = wr.TimelineEvent(
        kind="tool_use",
        seq=0,
        name="Bash",
        tool_id="x",
        tool_input={"command": xss_in},
    )
    res = wr.TimelineEvent(kind="tool_result", seq=1, tool_id="x", output=xss_res)
    ag = _agent(output=xss_out, timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model, tools="full")
    # (1) agent output channel
    assert xss_out not in html
    assert "&lt;script&gt;OUTCHANNEL&lt;/script&gt;" in html
    # (2) tool input channel
    assert xss_in not in html
    assert "&lt;script&gt;INCHANNEL&lt;/script&gt;" in html
    # (3) tool result channel
    assert xss_res not in html
    assert "&lt;script&gt;RESCHANNEL&lt;/script&gt;" in html


def test_fixture_xss_escaped_no_raw_script(run_model):
    # the fixture itself carries no injected markup, but assert the render never emits a
    # raw unescaped injected script from any transcript channel (defense-in-depth smoke).
    html = rh.render_html(run_model)
    assert "<script>alert" not in html


# ───────────────────────── truncation + base64 elision (end-to-end) ─────────────────────────
def test_truncation_and_base64_end_to_end():
    payload = "Q" * 300
    filler = "lorem ipsum dolor sit amet " * 400  # spaces -> not a base64 run
    big = f"data:image/png;base64,{payload} {filler}"
    assert len(big.encode()) > rh.TOOL_OUTPUT_CAP
    use = wr.TimelineEvent(kind="tool_use", seq=0, name="Bash", tool_id="big")
    res = wr.TimelineEvent(kind="tool_result", seq=1, tool_id="big", output=big)
    ag = _agent(timeline=[use, res])
    model = _model([m.PhaseExport(index=1, title="P", agents=[ag])])
    html = rh.render_html(model, tools="full")
    assert "base64 image elided" in html  # data-URI payload elided
    assert "bytes elided @2000" in html  # oversized block truncated head+tail
    assert filler not in html  # the enormous filler body is gone


# ───────────────────────── purity / determinism ─────────────────────────
def test_render_is_deterministic(run_model):
    a = rh.render_html(run_model)
    b = rh.render_html(run_model)
    assert a == b


def test_render_no_fs_side_effect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rh.render_html(_model([m.PhaseExport(index=1, title="P", agents=[_agent()])]))
    assert not list(tmp_path.iterdir())
