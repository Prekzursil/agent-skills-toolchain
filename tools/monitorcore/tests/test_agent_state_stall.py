"""Two-signal stall tests for ``monitorcore.agent_state`` (the L1-stall regression).

A stall is an INFERENCE and may be reported only when TWO mechanically-independent
signals agree — a stale file mtime (filesystem) AND a frozen content fingerprint across
``>= 2`` polls (content). A terminal transcript is a FACT and outranks both, at any age.

The acceptance test is :func:`test_eleven_hour_old_finished_agent_is_done_never_stalled`:
it reproduces the MEASURED live defect where a long-finished agent was reported as a live
stall from mtime age alone. Its fixture is the real shape of a transcript observed on this
box (an assistant turn that declared ``stop_reason="end_turn"`` whose last content block is
a ``server_tool_use``), not an invented one.
"""

from __future__ import annotations

import json
import os

import pytest

from monitorcore import agent_state as st

ELEVEN_HOURS = 11 * 3600.0


@pytest.fixture(autouse=True)
def _clear_state():
    st.reset_state()
    yield
    st.reset_state()


def _write(path, *entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return str(path)


def _set_age(path, now, age):
    """Set the file's mtime so ``now - mtime == age``."""
    os.utime(path, (now, now - age))


def _finished_turn(text="all done"):
    """An assistant turn the model itself declared complete (``stop_reason='end_turn'``).

    The trailing content block is a ``server_tool_use``, so the pre-existing
    assistant-``text``-tail signal does NOT fire — this is the measured shape that the
    single-signal oracle mislabelled ``stalled``.
    """
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [
                {"type": "server_tool_use", "name": "web_search", "input": {}},
            ],
        },
    }


def _unfinished_turn(name="Bash"):
    """An assistant turn cut off mid-tool-call — NO terminal evidence of any kind."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "name": name}],
        },
    }


# ═════════════ THE ACCEPTANCE TEST (the measured live defect) ═════════════
def test_eleven_hour_old_finished_agent_is_done_never_stalled(tmp_path):
    """An 11-hour-old transcript carrying terminal evidence is ``done``, never ``stalled``.

    This is the regression: file mtime ALONE cannot distinguish a stalled agent from a
    long-FINISHED one, so age must never by itself produce ``stalled`` when the transcript
    says the agent finished.
    """
    p = _write(tmp_path / "finished.jsonl", _unfinished_turn(), _finished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)  # ~66x the 600s dead-man window

    # Poll it repeatedly: the content is frozen forever, yet it is terminal, so no number
    # of frozen polls may ever promote it to a stall.
    for _ in range(4):
        state, age = st.agent_status(p, now=now)
        assert state == "done", f"terminal transcript reported {state!r}"
        assert age == ELEVEN_HOURS
