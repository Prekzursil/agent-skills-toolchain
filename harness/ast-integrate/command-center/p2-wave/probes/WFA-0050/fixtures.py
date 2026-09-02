"""Worked CrewAI crew, worked AutoGen group chat, and 20 synthetic states."""
from __future__ import annotations

from typing import Any

from sources import NOTEBOOK_TERMINATE

WORKED_CREW: dict[str, Any] = {
    "id": "crew.research-write-review",
    "framework": "CrewAI",
    "process": "sequential",
    "agents": [
        {
            "id": "researcher",
            "role": "Senior Researcher",
            "goal": "Collect source-anchored facts",
            "backstory": "Desk researcher",
            "max_iter": 20,
            "allow_delegation": False,
        },
        {
            "id": "writer",
            "role": "Report Writer",
            "goal": "Draft the briefing",
            "backstory": "Technical writer",
            "max_iter": 20,
            "allow_delegation": False,
        },
        {
            "id": "reviewer",
            "role": "Reviewer",
            "goal": "Reject unsupported claims",
            "backstory": "Adversarial reviewer",
            "max_iter": 12,
            "allow_delegation": False,
        },
    ],
    "tasks": [
        {
            "id": "t-research",
            "description": "Gather facts with citations",
            "expected_output": "Bullet facts with URLs",
            "agent": "researcher",
            "context": [],
            "async_execution": False,
        },
        {
            "id": "t-write",
            "description": "Write the briefing from research",
            "expected_output": "Markdown briefing",
            "agent": "writer",
            "context": ["t-research"],
            "async_execution": False,
        },
        {
            "id": "t-review",
            "description": "Review the briefing for unsupported claims",
            "expected_output": "PASS or FAIL with cited defects",
            "agent": "reviewer",
            "context": ["t-write"],
            "async_execution": False,
        },
    ],
}

WORKED_GROUPCHAT: dict[str, Any] = {
    "id": "autogen.engineer-critic-user",
    "framework": "AutoGen/AG2",
    "agents": [
        {
            "id": "user",
            "class": "UserProxyAgent",
            "name": "User",
            "human_input_mode": "NEVER",
            "is_termination_msg": "TERMINATE-substring",
        },
        {
            "id": "engineer",
            "class": "AssistantAgent",
            "name": "Engineer",
            "system_message": "Propose a concrete change.",
        },
        {
            "id": "critic",
            "class": "AssistantAgent",
            "name": "Critic",
            "system_message": "Refute unsupported proposals.",
        },
    ],
    "groupchat": {
        "max_round": 8,
        "speaker_selection_method": "round_robin",
        "allow_repeat_speaker": False,
        "messages": [],
    },
    "manager": {
        "class": "GroupChatManager",
        "name": "chat_manager",
        "is_termination_msg": NOTEBOOK_TERMINATE["quote"],
        "human_input_mode": "NEVER",
    },
    "alt_non_transferable_policies": ["auto", "manual", "random"],
}


def _ag(
    ident: str,
    *,
    round_index: int,
    max_round: int,
    terminate: bool,
    speaker_none: bool = False,
    reply_is_none: bool = False,
    last_content: str = "",
) -> dict[str, Any]:
    if terminate and not last_content:
        last_content = "done. TERMINATE"
    return {
        "id": ident,
        "kind": "autogen-groupchat",
        "round_index": round_index,
        "max_round": max_round,
        "is_termination_msg": terminate,
        "speaker_selection_none": speaker_none,
        "reply_is_none": reply_is_none,
        "last_content": last_content,
    }


def _crew(
    ident: str,
    *,
    done: int,
    count: int,
    agent_iter: int = 0,
    max_iter: int = 20,
) -> dict[str, Any]:
    return {
        "id": ident,
        "kind": "crew-sequential",
        "tasks_completed": done,
        "task_count": count,
        "agent_iter": agent_iter,
        "max_iter": max_iter,
        "round_index": 0,
        "max_round": 1,
        "is_termination_msg": False,
        "speaker_selection_none": False,
        "reply_is_none": False,
    }


# 20 synthetic conversation / crew states. Domain for AutoGen: 0 <= i <= max_round-1.
SYNTHETIC_STATES: list[dict[str, Any]] = [
    _ag("ag-continue-early", round_index=0, max_round=10, terminate=False, last_content="hello"),
    _ag("ag-stop-terminate-mid", round_index=3, max_round=10, terminate=True),
    _ag("ag-stop-last-round", round_index=9, max_round=10, terminate=False, last_content="still going"),
    _ag("ag-continue-penultimate", round_index=8, max_round=10, terminate=False, last_content="one more"),
    _ag("ag-stop-maxround-1", round_index=0, max_round=1, terminate=False, last_content="only round"),
    _ag("ag-stop-speaker-none", round_index=2, max_round=10, terminate=False, speaker_none=True, last_content="handoff"),
    _ag("ag-stop-both-reasons", round_index=9, max_round=10, terminate=True),
    _ag(
        "ag-stop-reply-none",
        round_index=1,
        max_round=5,
        terminate=False,
        reply_is_none=True,
        last_content="",
    ),
    _ag("ag-stop-terminate-find", round_index=4, max_round=8, terminate=True, last_content="please TERMINATE now"),
    _crew("crew-continue-zero", done=0, count=3),
    _crew("crew-stop-all-three", done=3, count=3),
    _crew("crew-continue-two-of-three", done=2, count=3),
    _crew("crew-stop-singleton", done=1, count=1),
    _crew("crew-continue-maxiter-not-crew", done=1, count=3, agent_iter=20, max_iter=20),
    _crew("crew-stop-all-and-maxiter", done=3, count=3, agent_iter=20, max_iter=20),
    _crew("crew-stop-empty-list", done=0, count=0),
    _ag("ag-stop-i-eq-max-minus-1", round_index=4, max_round=5, terminate=False, last_content="cap"),
    _ag("ag-continue-mid-roundrobin", round_index=3, max_round=8, terminate=False, last_content="round robin turn"),
    _crew("crew-continue-hierarchical-pending", done=0, count=4, agent_iter=1, max_iter=20),
    _ag("ag-continue-no-token", round_index=6, max_round=12, terminate=False, last_content="no stop token"),
]


def expected_mix() -> dict[str, int]:
    from documented import documented_stop

    stops = sum(1 for s in SYNTHETIC_STATES if documented_stop(s))
    return {"n": len(SYNTHETIC_STATES), "stop": stops, "continue": len(SYNTHETIC_STATES) - stops}
