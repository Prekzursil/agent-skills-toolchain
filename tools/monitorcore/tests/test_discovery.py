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


def test_newest_mtime_sees_nested_workflow_transcripts(tmp_path):
    """The newest transcript may live under ``workflows/<wf>/`` — the walk must recurse."""
    sub = tmp_path / "subagents"
    _agent(sub, "flat", {"m": 1}, mtime=1000)
    _agent(sub / "workflows" / "wf1", "deep", {"m": 2}, mtime=7000)
    assert dc.newest_mtime(str(sub)) == 7000


def test_newest_mtime_ignores_unreadable_subtree(tmp_path):
    assert dc.newest_mtime(str(tmp_path / "nope")) == 0.0


def test_iter_entries_skips_non_transcript_files(tmp_path):
    """A ``.meta.json`` sidecar is enumerated but is not a transcript."""
    sub = tmp_path / "subagents"
    _agent(sub, "a", {"m": 1}, meta={"name": "n"})
    names = sorted(e.name for e in dc._iter_transcripts(str(sub)))
    assert names == ["agent-a.jsonl"]


# ───────────────────────── enumeration-cost contract (the perf regression gate) ─────
class _CountingScandir:
    """Wraps ``os.scandir`` and counts how many directories get enumerated.

    Enumeration count -- not wall-clock -- is the falsifiable contract: a wall-clock
    assertion flakes on a loaded box and on a warm/cold page cache, while "how many
    directories did you open" is exact and deterministic.

    Counts are reported NET of :func:`_subagent_dir_candidates`, whose own non-recursive
    glob also goes through ``os.scandir``. Measuring that baseline instead of hardcoding it
    keeps the assertion about the transcript walk -- the thing under test -- and immune to
    ``glob`` internals.
    """

    def __init__(self, monkeypatch):
        self.n = 0
        self._real = os.scandir
        monkeypatch.setattr(dc.os, "scandir", self)

    def __call__(self, path):
        self.n += 1
        return self._real(path)

    def reset(self) -> None:
        self.n = 0

    def walk_cost(self, projects: str, fn) -> int:
        """Enumerations ``fn`` spends walking transcripts, net of the candidate glob."""
        self.reset()
        dc._subagent_dir_candidates(projects)
        baseline = self.n
        self.reset()
        fn()
        return self.n - baseline


def test_find_subagent_dirs_short_circuits_on_first_transcript(tmp_path, monkeypatch):
    """Non-emptiness needs the FIRST hit, not a full recursive walk of every transcript.

    The retired implementation ran ``glob('**/agent-*.jsonl', recursive=True)`` purely to
    test non-emptiness, so it enumerated the entire nested tree for a question that one
    directory entry answers.
    """
    projects = tmp_path / "projects"
    sub = projects / "p" / "s" / "subagents"
    _agent(sub, "top", {"m": 1})
    for i in range(5):
        _agent(sub / "workflows" / f"wf{i}", f"deep{i}", {"m": i})

    c = _CountingScandir(monkeypatch)
    cost = c.walk_cost(str(projects), lambda: dc.find_subagent_dirs(str(projects)))
    # The `subagents` dir alone answers it; `workflows/` and its 5 children stay unopened.
    assert cost == 1, f"expected a short-circuit after 1 dir, walked {cost}"


def test_pick_active_dir_walks_each_dir_exactly_once(tmp_path, monkeypatch):
    """The retired code walked every dir TWICE (find_subagent_dirs, then newest_mtime).

    Measured on this fixture before the fix: **27** enumerations gross / 24 net. Three
    directories per tree (``subagents``, ``workflows``, ``workflows/<wf>``) times two trees
    is 6 -- one visit each.
    """
    projects = tmp_path / "projects"
    d1 = projects / "p1" / "s1" / "subagents"
    d2 = projects / "p2" / "s2" / "subagents"
    _agent(d1, "a", {"m": 1}, mtime=1000)
    _agent(d1 / "workflows" / "wfA", "a2", {"m": 1}, mtime=1500)
    _agent(d2, "b", {"m": 2}, mtime=9000)
    _agent(d2 / "workflows" / "wfB", "b2", {"m": 2}, mtime=8000)

    c = _CountingScandir(monkeypatch)
    result: list[str | None] = []
    cost = c.walk_cost(
        str(projects), lambda: result.append(dc.pick_active_dir(str(projects)))
    )
    assert result == [str(d2)]
    assert cost == 6, f"expected one walk per dir (6 enumerations), got {cost}"


def test_pick_active_dir_keeps_earlier_dir_when_later_is_older(tmp_path):
    """The FIRST candidate staying the winner is its own branch (later dir must not clobber).

    Also covers the inner "this transcript is older than the newest so far" branch: ``p1``'s
    flat transcript is NEWER than its nested one, so the second yield must not lower the max.
    """
    projects = tmp_path / "projects"
    d1 = projects / "p1" / "s1" / "subagents"
    d2 = projects / "p2" / "s2" / "subagents"
    _agent(d1, "newest", {"m": 1}, mtime=9000)
    _agent(d1 / "workflows" / "wf", "older", {"m": 2}, mtime=2000)
    _agent(d2, "b", {"m": 3}, mtime=1000)
    assert dc.pick_active_dir(str(projects)) == str(d1)
    assert dc.newest_mtime(str(d1)) == 9000


def test_pick_active_dir_skips_candidate_with_no_transcripts(tmp_path):
    """An empty ``subagents`` dir is a candidate path but must never be selected."""
    projects = tmp_path / "projects"
    (projects / "p0" / "s0" / "subagents").mkdir(parents=True)
    good = projects / "p1" / "s1" / "subagents"
    _agent(good, "a", {"m": 1}, mtime=1000)
    assert dc.pick_active_dir(str(projects)) == str(good)


def test_pick_active_dir_all_candidates_empty_is_none(tmp_path):
    projects = tmp_path / "projects"
    (projects / "p0" / "s0" / "subagents").mkdir(parents=True)
    assert dc.pick_active_dir(str(projects)) is None


def test_scan_equal_age_rows_are_path_ordered(tmp_path):
    """Equal-mtime rows must not reshuffle between frames."""
    sub = tmp_path / "subagents"
    _agent(sub, "bbb", {"message": {"content": []}}, mtime=5000)
    _agent(sub, "aaa", {"message": {"content": []}}, mtime=5000)
    rows = dc.scan(str(sub), active_secs=1.0, width=200, now=5000.0)
    assert [os.path.basename(r["jsonl"]) for r in rows] == [
        "agent-aaa.jsonl",
        "agent-bbb.jsonl",
    ]


def test_scan_reports_real_size(tmp_path):
    """``size`` comes off the cached DirEntry stat -- it must still be the real byte count."""
    sub = tmp_path / "subagents"
    p = _agent(sub, "a", {"message": {"content": []}}, mtime=5000)
    (row,) = dc.scan(str(sub), active_secs=1.0, width=200, now=5000.0)
    assert row["size"] == os.path.getsize(p) > 0


def test_pick_active_dir_prefers_nested_newest(tmp_path):
    """A dir whose ONLY recent activity is nested must still win."""
    projects = tmp_path / "projects"
    d1 = projects / "p1" / "s1" / "subagents"
    d2 = projects / "p2" / "s2" / "subagents"
    _agent(d1, "a", {"m": 1}, mtime=5000)
    _agent(d2, "b", {"m": 2}, mtime=1000)
    _agent(d2 / "workflows" / "wf", "deep", {"m": 3}, mtime=9000)
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
    assert dc.last_event_summary(p, 80).startswith("+ Bash")


def test_last_event_text_from_content_string(tmp_path):
    p = _agent(tmp_path, "a", {"message": {"content": "just text"}})
    assert dc.last_event_summary(p, 80) == "> just text"


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
    assert dc.last_event_summary(p, 80) == "* deep"


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
    assert dc.last_event_summary(str(p), 80) == "> hi"


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
    assert dc.last_event_summary(str(p), 80) == "> hi"


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
