"""Tests for ``monitorcore.discovery`` — flat + workflow subagent discovery.

Authored here (the retired source had no tests). Builds a fake ``projects`` tree in ``tmp_path``
and drives ``scan`` with an injected ``now`` so age/running are deterministic. Every
``last_event_summary`` event-kind branch (tool_use / text / tool_result ok+error / thinking /
skip / empty) is exercised, and the flat-vs-workflow ``wf`` split is asserted directly.
"""

from __future__ import annotations

import json
import os

from monitorcore import discovery as dc


def _agent(dir_path, stem, *entries, meta=None, mtime=None):
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / f"agent-{stem}.jsonl"
    p.write_text(
        "".join(json.dumps(e) + "\n" for e in entries) or "{}\n", encoding="utf-8"
    )
    if meta is not None:
        (dir_path / f"agent-{stem}.meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
    if mtime is not None:
        os.utime(str(p), (mtime, mtime))
    return str(p)


# ───────────────────────── find_subagent_dirs / newest_mtime / pick_active_dir ─────
def test_find_subagent_dirs_only_dirs_with_transcripts(tmp_path):
    projects = tmp_path / "projects"
    good = projects / "projA" / "sess1" / "subagents"
    _agent(good, "a", {"message": {"content": []}})
    # a subagents dir with NO agent-*.jsonl is excluded
    (projects / "projB" / "sess2" / "subagents").mkdir(parents=True)
    found = dc.find_subagent_dirs(str(projects))
    assert found == [str(good)]


def test_newest_mtime_empty_is_zero(tmp_path):
    assert dc.newest_mtime(str(tmp_path)) == 0.0


def test_newest_mtime_picks_latest(tmp_path):
    sub = tmp_path / "subagents"
    _agent(sub, "a", {"m": 1}, mtime=1000)
    _agent(sub, "b", {"m": 2}, mtime=3000)
    assert dc.newest_mtime(str(sub)) == 3000


def test_pick_active_dir_none_when_empty(tmp_path):
    assert dc.pick_active_dir(str(tmp_path / "projects")) is None


def test_pick_active_dir_returns_most_recent(tmp_path):
    projects = tmp_path / "projects"
    d1 = projects / "p1" / "s1" / "subagents"
    d2 = projects / "p2" / "s2" / "subagents"
    _agent(d1, "a", {"m": 1}, mtime=1000)
    _agent(d2, "b", {"m": 2}, mtime=9000)
    assert dc.pick_active_dir(str(projects)) == str(d2)


# ───────────────────────── _one_line ─────────────────────────
def test_one_line_collapse_truncate_exact():
    assert dc._one_line("a\n  b\tc", 40) == "a b c"
    out = dc._one_line("x" * 100, 10)
    assert out == "x" * 9 + "…" and len(out) == 10
    assert dc._one_line("y" * 10, 10) == "y" * 10


# ───────────────────────── last_event_summary ─────────────────────────
def test_last_event_missing_file_returns_empty():
    assert dc.last_event_summary("/no/such.jsonl", 80) == ""


def test_last_event_tool_use(tmp_path):
    p = _agent(
        tmp_path,
        "a",
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "echo hi"},
                    }
                ]
            }
        },
    )
    assert dc.last_event_summary(p, 80).startswith("🔧 Bash")


def test_last_event_text_from_content_string(tmp_path):
    p = _agent(tmp_path, "a", {"message": {"content": "just text"}})
    assert dc.last_event_summary(p, 80) == "📝 just text"


def test_last_event_tool_result_ok_and_error(tmp_path):
    p_ok = _agent(
        tmp_path,
        "ok",
        {"message": {"content": [{"type": "tool_result", "content": "done"}]}},
    )
    assert dc.last_event_summary(p_ok, 80) == "↳ done"
    p_err = _agent(
        tmp_path,
        "err",
        {
            "message": {
                "content": [
                    {"type": "tool_result", "content": "boom", "is_error": True}
                ]
            }
        },
    )
    assert dc.last_event_summary(p_err, 80) == "✗ boom"


def test_last_event_tool_result_non_str_json_encoded(tmp_path):
    p = _agent(
        tmp_path,
        "a",
        {"message": {"content": [{"type": "tool_result", "content": {"k": 1}}]}},
    )
    assert dc.last_event_summary(p, 80) == '↳ {"k": 1}'


def test_last_event_thinking_after_empty_text(tmp_path):
    # reversed blocks: empty text (skipped) then thinking (returned)
    p = _agent(
        tmp_path,
        "a",
        {
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "deep"},
                    {"type": "text", "text": "   "},
                ]
            }
        },
    )
    assert dc.last_event_summary(p, 80) == "💭 deep"


def test_last_event_skips_non_dict_block_and_bad_lines(tmp_path):
    p = tmp_path / "agent-a.jsonl"
    p.write_text(
        "not-json\n"  # non-{ -> skipped
        "{bad\n"  # unparseable -> skipped
        + json.dumps({"message": {"content": [{"type": "text", "text": "hi"}, "bare"]}})
        + "\n",
        encoding="utf-8",
    )
    # reversed blocks: "bare" (non-dict, skipped) then the text block
    assert dc.last_event_summary(str(p), 80) == "📝 hi"


def test_last_event_no_meaningful_block_returns_empty(tmp_path):
    p = _agent(tmp_path, "a", {"message": {"content": [{"type": "mystery"}]}})
    assert dc.last_event_summary(p, 80) == ""


def test_last_event_message_not_dict(tmp_path):
    p = _agent(tmp_path, "a", {"message": "oops"})
    assert dc.last_event_summary(p, 80) == ""


def test_last_event_skips_trailing_blank_and_malformed_lines(tmp_path):
    # valid FIRST, junk AFTER: reversed iteration must skip the trailing junk lines
    p = tmp_path / "agent-a.jsonl"
    p.write_text(
        json.dumps({"message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n"
        "\n"  # blank -> skipped
        "plain-text\n"  # non-{ -> skipped
        "{bad json\n",  # unparseable -> skipped
        encoding="utf-8",
    )
    assert dc.last_event_summary(str(p), 80) == "📝 hi"


# ───────────────────────── scan ─────────────────────────
def test_scan_flat_and_workflow_split(tmp_path):
    sub = tmp_path / "subagents"
    _agent(
        sub,
        "flat",
        {"message": {"content": [{"type": "text", "text": "hi"}]}},
        meta={"name": "flatty", "agentType": "general-purpose", "description": "d"},
        mtime=5000,
    )
    _agent(
        sub / "workflows" / "wf9",
        "inwf",
        {"message": {"content": [{"type": "text", "text": "yo"}]}},
        mtime=4000,
    )
    rows = dc.scan(str(sub), active_secs=150.0, width=200, now=5100.0)
    by_name = {r["wf"]: r for r in rows}
    assert by_name[""]["name"] == "flatty" and by_name[""]["type"] == "general-purpose"
    assert by_name["wf9"]["wf"] == "wf9"
    # flat agent (age 100 <= 150) is running; the deeper one (age 1100) is not
    assert by_name[""]["running"] is True
    assert by_name["wf9"]["running"] is False
    # sorted most-recently-active first
    assert rows[0]["wf"] == ""


def test_scan_missing_meta_uses_defaults(tmp_path):
    sub = tmp_path / "subagents"
    _agent(sub, "nometa", {"message": {"content": []}}, mtime=5000)
    (rows,) = dc.scan(str(sub), active_secs=1.0, width=200, now=5000.0)
    assert rows["type"] == "?"  # default agentType when meta absent
    assert rows["running"] is True  # age 0 <= active_secs


def test_scan_bad_meta_json_falls_back(tmp_path):
    sub = tmp_path / "subagents"
    p = _agent(sub, "badmeta", {"message": {"content": []}}, mtime=5000)
    with open(os.path.splitext(p)[0] + ".meta.json", "w", encoding="utf-8") as fh:
        fh.write("{bad")
    (row,) = dc.scan(str(sub), active_secs=150.0, width=200, now=5010.0)
    assert row["type"] == "?"
