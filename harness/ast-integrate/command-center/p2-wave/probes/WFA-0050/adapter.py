"""Translate CrewAI crews and AutoGen group chats into the local IR subset.

Does not import crewai, autogen, or ag2. Reads fixtures plus published-source
quotes in sources.py.
"""
from __future__ import annotations

import sys
from typing import Any

from fixtures import WORKED_CREW, WORKED_GROUPCHAT
from ir import node, workflow_ir
from roles import map_role
from sources import (
    AUTOGEN_GROUPCHAT_FIELDS,
    AUTOGEN_RUN_CHAT_STOP,
    CREWAI_AGENT_DOCS,
    CREWAI_HIERARCHICAL,
    CREWAI_KICKOFF,
    CREWAI_PROCESS,
    CREWAI_SEQUENTIAL,
    CREWAI_SEQUENTIAL_AGENT_REQUIRED,
    NOTEBOOK_TERMINATE,
)
from stopping import AUTOGEN_GROUPCHAT_STOP, CREW_SEQUENTIAL_STOP

FORBIDDEN_MODULES = ("crewai", "autogen", "ag2", "pyautogen")

CONSTRUCTS: list[dict[str, Any]] = [
    {
        "id": "crew.agent.role-goal-backstory",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "role.payload.{job_title,goal,backstory} with extension crew-job-title",
        "anchor": CREWAI_AGENT_DOCS["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.agent.max_iter",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "stage.iteration_bound; does not stop the crew",
        "anchor": CREWAI_AGENT_DOCS["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.agent.allow_delegation",
        "framework": "CrewAI",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": CREWAI_AGENT_DOCS["anchor"],
        "live_conversational_loop": True,
        "reason": "Delegation is a live mid-task conversational handoff; no barrier equivalent.",
    },
    {
        "id": "crew.task.description-output",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "stage.payload.{description,expected_output}",
        "anchor": CREWAI_SEQUENTIAL["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.task.agent-assignment",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "stage.assignee; sequential requires agent set",
        "anchor": CREWAI_SEQUENTIAL_AGENT_REQUIRED["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.task.context",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "edges prior-stage -> stage (barrier on prior output)",
        "anchor": CREWAI_SEQUENTIAL["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.process.sequential",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "turn_policy=ordered-stages",
        "anchor": CREWAI_PROCESS["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.process.hierarchical-manager-loop",
        "framework": "CrewAI",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": CREWAI_HIERARCHICAL["anchor"],
        "live_conversational_loop": True,
        "reason": "Manager AgentTools delegation is a live conversational loop.",
    },
    {
        "id": "crew.kickoff.sequential-completion",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": f"stopping.expression={CREW_SEQUENTIAL_STOP!r}",
        "anchor": CREWAI_KICKOFF["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "crew.task.conditional-python",
        "framework": "CrewAI",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": CREWAI_SEQUENTIAL["anchor"],
        "live_conversational_loop": False,
        "reason": "ConditionalTask skip is an arbitrary Python callable, not a Boolean stopping term.",
    },
    {
        "id": "crew.task.async_execution",
        "framework": "CrewAI",
        "status": "MAPPED",
        "ir": "fan-out then barrier at next sync task (_process_async_tasks)",
        "anchor": CREWAI_SEQUENTIAL["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "autogen.conversable.system_message",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "role.payload.instructions",
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "autogen.conversable.is_termination_msg",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "stopping term is_termination_msg (TERMINATE substring in published notebooks)",
        "anchor": NOTEBOOK_TERMINATE["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "autogen.conversable.human_input_mode-live",
        "framework": "AutoGen/AG2",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": "GroupChatManager human_input_mode ALWAYS/TERMINATE",
        "live_conversational_loop": True,
        "reason": "ALWAYS/TERMINATE require a live human conversational loop.",
    },
    {
        "id": "autogen.groupchat.max_round",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "stopping term round_index == last_round",
        "anchor": AUTOGEN_RUN_CHAT_STOP["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "autogen.groupchat.speaker.auto",
        "framework": "AutoGen/AG2",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": True,
        "reason": "auto speaker selection is a nested live LLM conversational loop.",
    },
    {
        "id": "autogen.groupchat.speaker.manual",
        "framework": "AutoGen/AG2",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": True,
        "reason": "manual speaker selection is a live human loop.",
    },
    {
        "id": "autogen.groupchat.speaker.random",
        "framework": "AutoGen/AG2",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": True,
        "reason": "random speaker selection is a live nondeterministic conversational choice.",
    },
    {
        "id": "autogen.groupchat.speaker.round_robin",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "turn_policy=round-robin-schedule",
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "autogen.groupchat.speaker.callable-none",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "stopping term speaker_selection_none",
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": False,
        "reason": (
            "Custom selector returning None raises NoEligibleSpeakerError; "
            "run_chat breaks. The callable body itself is not mapped."
        ),
    },
    {
        "id": "autogen.groupchat.no-reply",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "stopping term reply_is_none",
        "anchor": AUTOGEN_RUN_CHAT_STOP["anchor"],
        "live_conversational_loop": False,
        "reason": "generate_reply returning None terminates after speaker selection.",
    },
    {
        "id": "autogen.groupchat.allow_repeat_speaker",
        "framework": "AutoGen/AG2",
        "status": "MAPPED",
        "ir": "turn_policy.repeat_speaker",
        "anchor": AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        "live_conversational_loop": False,
    },
    {
        "id": "autogen.groupchat.run_chat-loop",
        "framework": "AutoGen/AG2",
        "status": "NON-TRANSFERABLE",
        "ir": None,
        "anchor": AUTOGEN_RUN_CHAT_STOP["anchor"],
        "live_conversational_loop": True,
        "reason": (
            "The run_chat for-loop is a live conversational loop. Termination "
            "predicates map; the loop itself does not."
        ),
    },
]


def imported_forbidden() -> list[str]:
    found = []
    for name in FORBIDDEN_MODULES:
        if name in sys.modules:
            found.append(name)
    return found


def translate_crew(crew: dict[str, Any] | None = None) -> dict[str, Any]:
    crew = crew or WORKED_CREW
    roles = []
    for agent in crew["agents"]:
        hints = {"kind": "crew-job-title"}
        if agent["role"].strip().lower() == "reviewer":
            hints = {}
        mapping = map_role(agent["role"], hints=hints)
        roles.append(
            node(
                "role",
                f"crew.role.{agent['id']}",
                {
                    "agent_id": agent["id"],
                    "mapping": mapping,
                    "goal": agent["goal"],
                    "backstory": agent["backstory"],
                    "max_iter": agent["max_iter"],
                    "allow_delegation": agent["allow_delegation"],
                },
                CREWAI_AGENT_DOCS["anchor"],
            )
        )
    stages = []
    edges = []
    for task in crew["tasks"]:
        stages.append(
            node(
                "stage",
                f"crew.stage.{task['id']}",
                {
                    "description": task["description"],
                    "expected_output": task["expected_output"],
                    "assignee": task["agent"],
                    "async_execution": task["async_execution"],
                    "iteration_bound": next(
                        a["max_iter"] for a in crew["agents"] if a["id"] == task["agent"]
                    ),
                },
                CREWAI_SEQUENTIAL["anchor"],
            )
        )
        for prior in task["context"]:
            edges.append(
                node(
                    "edge",
                    f"crew.edge.{prior}->{task['id']}",
                    {"src": f"crew.stage.{prior}", "dst": f"crew.stage.{task['id']}", "kind": "barrier-output"},
                    CREWAI_SEQUENTIAL["anchor"],
                )
            )
    turn_policy = node(
        "turn_policy",
        "crew.turn.ordered-stages",
        {"policy": "ordered-stages", "process": "sequential"},
        CREWAI_PROCESS["anchor"],
    )
    stopping = node(
        "stopping",
        "crew.stop.task-list",
        {"expression": CREW_SEQUENTIAL_STOP, "grammar": "AND/OR/NOT/cmp"},
        CREWAI_SEQUENTIAL["anchor"],
    )
    nt = [c for c in CONSTRUCTS if c["framework"] == "CrewAI" and c["status"] == "NON-TRANSFERABLE"]
    return {
        "native": crew,
        "ir": workflow_ir(
            "ir.crew.research-write-review",
            roles=roles,
            stages=stages,
            turn_policy=turn_policy,
            stopping=stopping,
            gates=[],
            edges=edges,
            non_transferable=nt,
            lineage={"native_id": crew["id"], "adapter": "WFA-0050"},
        ),
        "constructs": [c for c in CONSTRUCTS if c["framework"] == "CrewAI"],
    }


def translate_groupchat(gc: dict[str, Any] | None = None) -> dict[str, Any]:
    gc = gc or WORKED_GROUPCHAT
    roles = []
    for agent in gc["agents"]:
        hints = {}
        if agent["class"] == "UserProxyAgent":
            hints = {"human_input_mode": agent.get("human_input_mode")}
        mapping = map_role(agent["name"], hints=hints)
        roles.append(
            node(
                "role",
                f"ag.role.{agent['id']}",
                {"class": agent["class"], "mapping": mapping, "system_message": agent.get("system_message")},
                AUTOGEN_GROUPCHAT_FIELDS["anchor"],
            )
        )
    roles.append(
        node(
            "role",
            "ag.role.manager",
            {
                "class": gc["manager"]["class"],
                "mapping": map_role("GroupChatManager"),
            },
            AUTOGEN_GROUPCHAT_FIELDS["anchor"],
        )
    )
    stages = [
        node(
            "stage",
            "ag.stage.round",
            {
                "kind": "conversation-round",
                "note": "A round is a message broadcast; the loop is NON-TRANSFERABLE.",
            },
            AUTOGEN_RUN_CHAT_STOP["anchor"],
        )
    ]
    policy = gc["groupchat"]["speaker_selection_method"]
    turn_payload = {
        "policy": "round-robin-schedule" if policy == "round_robin" else policy,
        "allow_repeat_speaker": gc["groupchat"]["allow_repeat_speaker"],
        "max_round": gc["groupchat"]["max_round"],
    }
    turn_policy = node(
        "turn_policy",
        "ag.turn.round-robin",
        turn_payload,
        AUTOGEN_GROUPCHAT_FIELDS["anchor"],
    )
    stopping = node(
        "stopping",
        "ag.stop.groupchat",
        {
            "expression": AUTOGEN_GROUPCHAT_STOP,
            "is_termination_msg": "TERMINATE substring (published notebook)",
        },
        AUTOGEN_RUN_CHAT_STOP["anchor"],
    )
    nt = [c for c in CONSTRUCTS if c["framework"] == "AutoGen/AG2" and c["status"] == "NON-TRANSFERABLE"]
    return {
        "native": gc,
        "ir": workflow_ir(
            "ir.autogen.engineer-critic-user",
            roles=roles,
            stages=stages,
            turn_policy=turn_policy,
            stopping=stopping,
            gates=[],
            edges=[],
            non_transferable=nt,
            lineage={"native_id": gc["id"], "adapter": "WFA-0050"},
        ),
        "constructs": [c for c in CONSTRUCTS if c["framework"] == "AutoGen/AG2"],
    }


def live_loop_must_be_non_transferable() -> list[str]:
    bad = []
    for c in CONSTRUCTS:
        if c.get("live_conversational_loop") and c["status"] != "NON-TRANSFERABLE":
            bad.append(c["id"])
    return bad
