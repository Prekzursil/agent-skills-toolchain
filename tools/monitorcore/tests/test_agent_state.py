"""Tests for ``monitorcore.agent_state`` — the unified bucket + transcript state deriver.

Authored here (the retired agent-monitor source had no tests). ``agent_status`` is driven
deterministically by setting each fixture's mtime with ``os.utime`` and injecting a fixed
``now``, so every running/working/done/stalled branch — and the terminal-status cache — is
exercised on any platform. ``bucket_agent`` is asserted to reproduce BOTH former wfmon
duplicates (``_bucket`` with ``journal_state=None`` and ``_state_bucket`` with a journal state).
"""

from __future__ import annotations

import json
import os

import pytest

from monitorcore import agent_state as st


@pytest.fixture(autouse=True)
def _clear_cache():
    st._STATUS_CACHE.clear()
    yield
    st._STATUS_CACHE.clear()


def _write(path, *entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return str(path)


def _set_age(path, now, age):
    """Set the file's mtime so ``now - mtime == age``."""
    os.utime(path, (now, now - age))


# ───────────────────────── bucket_agent ─────────────────────────
def test_bucket_agent_errored_wins():
    assert (
        st.bucket_agent(
            errored=True, state="done", running=True, journal_state="result"
        )
        == "error"
    )


def test_bucket_agent_done_from_journal_result():
    assert (
        st.bucket_agent(
            errored=False, state="running", running=True, journal_state="result"
        )
        == "done"
    )


def test_bucket_agent_done_from_manifest_state():
    assert st.bucket_agent(errored=False, state="done", running=False) == "done"


def test_bucket_agent_running():
    assert st.bucket_agent(errored=False, state="running", running=True) == "running"


def test_bucket_agent_idle():
    assert st.bucket_agent(errored=False, state="idle", running=False) == "idle"


def test_bucket_agent_journal_none_reproduces_bucket():
    # journal_state defaults to None -> the former workflow_monitor._bucket semantics
    assert st.bucket_agent(errored=False, state="queued", running=False) == "idle"
    assert st.bucket_agent(errored=False, state="queued", running=True) == "running"


# ───────────────────────── _last_entry_shape ─────────────────────────
def test_last_entry_shape_missing_file():
    assert st._last_entry_shape("/no/such/file.jsonl") == (None, None)


def test_last_entry_shape_assistant_text(tmp_path):
    p = _write(
        tmp_path / "a.jsonl",
        {"message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]}},
    )
    assert st._last_entry_shape(p) == ("text", "assistant")


def test_last_entry_shape_content_string_is_text(tmp_path):
    p = _write(tmp_path / "a.jsonl", {"message": {"role": "user", "content": "plain"}})
    assert st._last_entry_shape(p) == ("text", "user")


def test_last_entry_shape_skips_blank_malformed_lines(tmp_path):
    p = tmp_path / "a.jsonl"
    # valid FIRST, junk AFTER: reversed iteration must skip the trailing junk lines
    p.write_text(
        json.dumps(
            {"message": {"role": "assistant", "content": [{"type": "tool_use"}]}}
        )
        + "\n"
        "\n"  # blank -> skipped (line 71)
        "not-json-line\n"  # doesn't start with { -> skipped (line 71)
        "{bad json\n",  # starts with { but unparseable -> skipped (line 75)
        encoding="utf-8",
    )
    assert st._last_entry_shape(str(p)) == ("tool_use", "assistant")


def test_last_entry_shape_skips_non_type_blocks_then_returns(tmp_path):
    # reversed blocks: bare (non-dict) + dict-without-type are skipped (84->83), then text
    p = _write(
        tmp_path / "a.jsonl",
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "x"}, {"noType": 1}, "bare"],
            }
        },
    )
    assert st._last_entry_shape(p) == ("text", "assistant")


def test_last_entry_shape_no_content_bearing_event(tmp_path):
    p = _write(tmp_path / "a.jsonl", {"message": {"role": "assistant", "content": []}})
    assert st._last_entry_shape(p) == (None, None)


def test_last_entry_shape_message_not_dict(tmp_path):
    p = _write(tmp_path / "a.jsonl", {"message": "oops"})
    assert st._last_entry_shape(p) == (None, None)


# ───────────────────────── agent_status ─────────────────────────
def test_agent_status_missing_file_is_stalled():
    state, age = st.agent_status("/no/such/file.jsonl")
    assert state == "stalled" and age == 1e9


def test_agent_status_fresh_is_running(tmp_path):
    p = _write(
        tmp_path / "a.jsonl", {"message": {"content": [{"type": "text", "text": "x"}]}}
    )
    now = 10_000.0
    _set_age(p, now, age=5.0)  # < FRESH
    assert st.agent_status(p, now=now) == ("running", 5.0)


def test_agent_status_done_when_last_is_assistant_text(tmp_path):
    p = _write(
        tmp_path / "a.jsonl",
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "final"}],
            }
        },
    )
    now = 10_000.0
    _set_age(p, now, age=100.0)  # FRESH < 100 < STALL
    state, age = st.agent_status(p, now=now)
    assert state == "done" and age == 100.0
    # terminal state cached by frozen mtime -> second call hits the cache branch
    assert st.agent_status(p, now=now) == ("done", 100.0)
    assert p in st._STATUS_CACHE


def test_agent_status_stalled_when_silent_past_stall(tmp_path):
    p = _write(
        tmp_path / "a.jsonl",
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Bash"}],
            }
        },
    )
    now = 10_000.0
    _set_age(p, now, age=700.0)  # > STALL, last event not assistant-text
    assert st.agent_status(p, now=now) == ("stalled", 700.0)


def test_agent_status_working_when_recent_tool_call(tmp_path):
    p = _write(
        tmp_path / "a.jsonl",
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Bash"}],
            }
        },
    )
    now = 10_000.0
    _set_age(p, now, age=100.0)  # FRESH < 100 < STALL, not a trailing text turn
    assert st.agent_status(p, now=now) == ("working", 100.0)
    # working is NOT terminal -> not cached
    assert p not in st._STATUS_CACHE
