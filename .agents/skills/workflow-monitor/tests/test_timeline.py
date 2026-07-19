#!/usr/bin/env python3
"""Timeline drill-down tests: ``agent_timeline`` / ``agent_task`` / ``pair_tool_calls`` /
``_flatten_content`` (the PR-A additions to ``workflow_run.py``).

All fixture-reading tests point at the frozen ``wf_export00-fixture`` under an ISOLATED export
fixture root — never the live ``~/.claude`` tree and never the schema-lock ``fixtures/projects``
root (so ``test_workflow_run.py``'s single-manifest invariant stays true).
"""

from __future__ import annotations

import os

import workflow_run as wr

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
PROJECT = "C--Users-Prekzursil"
SESSION = "d219bc39-7d7f-4290-befd-f1c079161057"
WF_ID = "wf_export00-fixture"
WF_DIR = os.path.join(
    EXPORT_PROJECTS, PROJECT, SESSION, "subagents", "workflows", WF_ID
)
KITCHENSINK = os.path.join(WF_DIR, "agent-kitchensink.jsonl")
TASKORDER = os.path.join(WF_DIR, "agent-taskorder.jsonl")

# NOTE: the PURE timeline IR (`TimelineEvent`, `_flatten_content`, `report_headline`,
# `pair_tool_calls`) was extracted into `monitorcore.timeline` and its unit tests live
# in `tools/monitorcore/tests/test_timeline.py`. What remains here exercises the wfmon
# adapter's transcript readers (`agent_timeline` / `agent_task`), which stay in
# `workflow_run` and still build `TimelineEvent`s / call `pair_tool_calls` via the
# re-export shim.


# ───────────────────────── agent_timeline ─────────────────────────
EXPECTED_KINDS = [
    "tool_result",  # 0  leading tool-result-only user record (walked)
    "text",  # 1  string-content user message (the spawn prompt)
    "thinking",  # 2  real thinking (empty/signature-only dropped)
    "text",  # 3  assistant text (whitespace-only text dropped)
    "tool_use",  # 4  Bash
    "tool_result",  # 5  Bash result (str content)
    "tool_use",  # 6  server_tool_use -> tool_use (web_search)
    "tool_use",  # 7  orphan tool_use (Read, no result)
    "tool_result",  # 8  srv_web_1 result (list content)
    "tool_result",  # 9  advisor_tool_result -> tool_result (dict content)
    "tool_use",  # 10 Grep
    "tool_result",  # 11 Grep result (dict content, is_error true)
    "text",  # 12 text after unknown/non-dict blocks
]


def test_timeline_file_order_and_seq():
    tl = wr.agent_timeline(KITCHENSINK)
    assert [e.kind for e in tl] == EXPECTED_KINDS
    assert [e.seq for e in tl] == list(range(len(EXPECTED_KINDS)))


def test_timeline_attachment_and_system_skipped():
    # attachment + system records lack `message` -> produce no events; only the 13 real events remain
    assert len(wr.agent_timeline(KITCHENSINK)) == len(EXPECTED_KINDS)


def test_timeline_thinking_real_kept_empty_dropped():
    tl = wr.agent_timeline(KITCHENSINK)
    thinks = [e for e in tl if e.kind == "thinking"]
    assert len(thinks) == 1
    assert thinks[0].text == "Let me reason about the kitchen sink carefully."


def test_timeline_string_content_becomes_one_text_event():
    tl = wr.agent_timeline(KITCHENSINK)
    assert tl[1].kind == "text"
    assert tl[1].text == "Do the kitchen-sink task."


def test_timeline_tool_use_fields():
    tl = wr.agent_timeline(KITCHENSINK)
    bash = tl[4]
    assert bash.kind == "tool_use"
    assert bash.name == "Bash"
    assert bash.tool_id == "tool_bash_1"
    assert bash.tool_input == {"command": "ls -la"}


def test_timeline_server_tool_use_becomes_tool_use():
    tl = wr.agent_timeline(KITCHENSINK)
    srv = tl[6]
    assert srv.kind == "tool_use"
    assert srv.name == "web_search"
    assert srv.tool_id == "srv_web_1"


def test_timeline_tool_result_str_and_flags():
    tl = wr.agent_timeline(KITCHENSINK)
    r = tl[5]
    assert r.kind == "tool_result"
    assert r.tool_id == "tool_bash_1"
    assert r.is_error is False
    assert r.output == "total 0\ndrwxr-xr-x  2 user user"


def test_timeline_tool_result_list_content_joined():
    tl = wr.agent_timeline(KITCHENSINK)
    assert tl[8].output == "search result A\nsearch result B"


def test_timeline_advisor_tool_result_dict_text():
    tl = wr.agent_timeline(KITCHENSINK)
    adv = tl[9]
    assert adv.kind == "tool_result"
    assert adv.tool_id == "advisor_1"
    assert adv.output == "advisor says proceed"


def test_timeline_tool_result_dict_content_json_and_is_error():
    tl = wr.agent_timeline(KITCHENSINK)
    err = tl[11]
    assert err.kind == "tool_result"
    assert err.tool_id == "tool_err_1"
    assert err.is_error is True
    assert err.output == '{"error": "boom", "code": 2}'


def test_timeline_unknown_and_nondict_blocks_ignored():
    # the "image" (unknown) block and the bare "stray-string-block" produce no events;
    # the following text block still lands
    tl = wr.agent_timeline(KITCHENSINK)
    assert tl[12].kind == "text"
    assert tl[12].text == "after the image"


def test_timeline_ids_pair_up():
    tl = wr.agent_timeline(KITCHENSINK)
    use_ids = {e.tool_id for e in tl if e.kind == "tool_use"}
    res_ids = {e.tool_id for e in tl if e.kind == "tool_result"}
    # every real tool_use except the orphan has a matching result id
    assert use_ids == {"tool_bash_1", "srv_web_1", "tool_orphan_1", "tool_err_1"}
    assert {"tool_bash_1", "srv_web_1", "tool_err_1"} <= res_ids
    assert "tool_orphan_1" not in res_ids


def test_timeline_oserror_returns_empty():
    assert wr.agent_timeline(os.path.join(WF_DIR, "does-not-exist.jsonl")) == []


def test_timeline_malformed_json_line_skipped(tmp_path):
    p = tmp_path / "agent-x.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"one"}]}}\n'
        "\n"  # blank line -> skipped
        "this is not json\n"
        '{"type":"assistant","message":{"content":[{"type":"text","text":"two"}]}}\n',
        encoding="utf-8",
    )
    tl = wr.agent_timeline(str(p))
    assert [e.text for e in tl] == ["one", "two"]
    assert [e.seq for e in tl] == [0, 1]


# ───────────────────────── agent_task ─────────────────────────
def test_agent_task_returns_first_user_text():
    # skips the leading tool-result-only user AND the message-less user record
    assert wr.agent_task(KITCHENSINK) == "Do the kitchen-sink task."


def test_agent_task_short_first_not_largest():
    # agent_task returns the FIRST user text; agent_prompt returns the LARGEST -> they differ
    task = wr.agent_task(TASKORDER)
    prompt = wr.agent_prompt(TASKORDER)
    assert task == "short task"
    assert prompt != task
    assert len(prompt) > len(task)
    assert prompt.startswith("This is a much larger later user message")


def test_agent_task_empty_when_no_user_text(tmp_path):
    p = tmp_path / "agent-none.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":"hi"}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"z","content":"r"}]}}\n',
        encoding="utf-8",
    )
    assert wr.agent_task(str(p)) == ""


def test_agent_task_skips_blank_and_malformed_lines(tmp_path):
    p = tmp_path / "agent-bm.jsonl"
    p.write_text(
        '\nnot-json\n{"type":"user","message":{"content":"real task"}}\n',
        encoding="utf-8",
    )
    assert wr.agent_task(str(p)) == "real task"


def test_agent_task_oserror_returns_empty():
    assert wr.agent_task(os.path.join(WF_DIR, "nope.jsonl")) == ""


# ───────────────────────── pair_tool_calls ─────────────────────────
def test_pair_tool_calls_ordered_with_orphan():
    tl = wr.agent_timeline(KITCHENSINK)
    pairs = wr.pair_tool_calls(tl)
    assert [u.tool_id for u, _ in pairs] == [
        "tool_bash_1",
        "srv_web_1",
        "tool_orphan_1",
        "tool_err_1",
    ]
    by_id = {u.tool_id: r for u, r in pairs}
    assert by_id["tool_bash_1"].tool_id == "tool_bash_1"
    assert by_id["srv_web_1"].tool_id == "srv_web_1"
    assert by_id["tool_err_1"].is_error is True
    assert by_id["tool_orphan_1"] is None  # orphan -> None
