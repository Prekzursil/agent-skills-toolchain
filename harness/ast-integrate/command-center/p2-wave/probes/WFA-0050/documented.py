"""Documented termination oracles.

Mechanically different from stopping.py: this module follows the published
control-flow (if / elif / else), not the Boolean grammar.
"""
from __future__ import annotations

from typing import Mapping


def crew_sequential_should_stop(state: Mapping[str, Any]) -> bool:
    """CrewAI sequential: stop iff the task-list loop has finished.

    Source: _execute_tasks for-loop then _create_crew_output. max_iter on an
    agent does not terminate the crew.
    """
    return int(state["tasks_completed"]) >= int(state["task_count"])


def autogen_groupchat_should_stop(state: Mapping[str, Any]) -> bool:
    """GroupChatManager.run_chat after broadcasting message at round i.

    if is_termination_msg: stop
    elif i == max_round - 1: stop
    else: select_speaker; None/NoEligibleSpeakerError => stop
    then if reply is None: stop
    """
    if bool(state.get("is_termination_msg")):
        return True
    if int(state["round_index"]) == int(state["max_round"]) - 1:
        return True
    if bool(state.get("speaker_selection_none")):
        return True
    if bool(state.get("reply_is_none")):
        return True
    return False


def documented_stop(state: Mapping[str, Any]) -> bool:
    kind = state["kind"]
    if kind == "crew-sequential":
        return crew_sequential_should_stop(state)
    if kind == "autogen-groupchat":
        return autogen_groupchat_should_stop(state)
    raise ValueError(f"unknown kind {kind}")
