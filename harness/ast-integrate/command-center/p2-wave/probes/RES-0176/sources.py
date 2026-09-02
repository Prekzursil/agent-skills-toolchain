#!/usr/bin/env python3
"""Live source table for RES-0176 (source-code rail + prose-docs rail per family)."""
from __future__ import annotations

UA = (
    "RES-0176-teardown-research/1.0 "
    "(ast-integrate; ecosystem-teardown; not-a-browser)"
)

# Two mechanically independent rails per family: published source AND official prose.
# GitHub Contents API of the same file is NOT a second rail.
SOURCES = [
    {
        "name": "lg_state.py",
        "family": "langgraph",
        "rail": "R1-source",
        "url": (
            "https://raw.githubusercontent.com/langchain-ai/langgraph/main/"
            "libs/langgraph/langgraph/graph/state.py"
        ),
        "accept": "text/plain",
    },
    {
        "name": "lg_graph_api.mdx",
        "family": "langgraph",
        "rail": "R2-prose",
        "url": (
            "https://raw.githubusercontent.com/langchain-ai/docs/main/"
            "src/oss/langgraph/graph-api.mdx"
        ),
        "accept": "text/plain",
    },
    {
        "name": "lg_pregel.mdx",
        "family": "langgraph",
        "rail": "R2-prose",
        "url": (
            "https://raw.githubusercontent.com/langchain-ai/docs/main/"
            "src/oss/langgraph/pregel.mdx"
        ),
        "accept": "text/plain",
    },
    {
        "name": "lg_license",
        "family": "langgraph",
        "rail": "R2-license",
        "url": "https://raw.githubusercontent.com/langchain-ai/langgraph/main/LICENSE",
        "accept": "text/plain",
    },
    {
        "name": "crew_agent_core.py",
        "family": "crewai",
        "rail": "R1-source",
        "url": (
            "https://raw.githubusercontent.com/crewAIInc/crewAI/main/"
            "lib/crewai/src/crewai/agent/core.py"
        ),
        "accept": "text/plain",
    },
    {
        "name": "crew_crew.py",
        "family": "crewai",
        "rail": "R1-source",
        "url": (
            "https://raw.githubusercontent.com/crewAIInc/crewAI/main/"
            "lib/crewai/src/crewai/crew.py"
        ),
        "accept": "text/plain",
    },
    {
        "name": "crew_process.py",
        "family": "crewai",
        "rail": "R1-source",
        "url": (
            "https://raw.githubusercontent.com/crewAIInc/crewAI/main/"
            "lib/crewai/src/crewai/process.py"
        ),
        "accept": "text/plain",
    },
    {
        "name": "crew_agents.mdx",
        "family": "crewai",
        "rail": "R2-prose",
        "url": (
            "https://raw.githubusercontent.com/crewAIInc/crewAI/main/"
            "docs/edge/en/concepts/agents.mdx"
        ),
        "accept": "text/plain",
    },
    {
        "name": "crew_hier.mdx",
        "family": "crewai",
        "rail": "R2-prose",
        "url": (
            "https://raw.githubusercontent.com/crewAIInc/crewAI/main/"
            "docs/edge/en/learn/hierarchical-process.mdx"
        ),
        "accept": "text/plain",
    },
    {
        "name": "crew_license",
        "family": "crewai",
        "rail": "R2-license",
        "url": "https://raw.githubusercontent.com/crewAIInc/crewAI/main/LICENSE",
        "accept": "text/plain",
    },
    {
        "name": "ag_groupchat.py",
        "family": "autogen",
        "rail": "R1-source",
        "url": (
            "https://raw.githubusercontent.com/microsoft/autogen/0.2/"
            "autogen/agentchat/groupchat.py"
        ),
        "accept": "text/plain",
    },
    {
        "name": "ag2_groupchat.html",
        "family": "autogen",
        "rail": "R2-prose",
        "url": (
            "https://docs.ag2.ai/latest/docs/user-guide/"
            "advanced-concepts/groupchat/groupchat/"
        ),
        "accept": "text/html",
    },
    {
        "name": "ag_license",
        "family": "autogen",
        "rail": "R2-license",
        "url": "https://raw.githubusercontent.com/microsoft/autogen/0.2/LICENSE",
        "accept": "text/plain",
    },
]

# Distinctive needles used as hardness evidence: present in the owning
# framework snapshots, absent from the other two.
HARDNESS_NEEDLES = {
    "typed_state_graphs": "annotated with a reducer function",
    "role_crew_delegation": "Each agent has a role, a goal, a backstory",
    "conversational_group_chat": (
        "broadcast the message to all agents except the speaker"
    ),
}

FRAMEWORK_SNAPS = {
    "langgraph": ["lg_state.py", "lg_graph_api.mdx", "lg_pregel.mdx"],
    "crewai": [
        "crew_agent_core.py",
        "crew_crew.py",
        "crew_process.py",
        "crew_agents.mdx",
        "crew_hier.mdx",
    ],
    "autogen": ["ag_groupchat.py", "ag2_groupchat.html"],
}

ABSTRACTION_OWNER = {
    "typed_state_graphs": "langgraph",
    "role_crew_delegation": "crewai",
    "conversational_group_chat": "autogen",
}
