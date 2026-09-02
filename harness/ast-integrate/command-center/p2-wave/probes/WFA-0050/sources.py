"""Published-source quotes for CrewAI and AutoGen/AG2. Licences recorded first.

No framework is imported. Excerpts are short enough to be commentary plus the
required copyright notice. Snapshotted 2026-08-25 from public GitHub/docs. AG2 GroupChat path verified against ag2-classic (ag2ai/ag2 404s).
"""
from __future__ import annotations

LICENCES = [
    {
        "framework": "CrewAI",
        "repo": "https://github.com/crewAIInc/crewAI",
        "path": "LICENSE",
        "spdx": "MIT",
        "copyright": "Copyright (c) 2025 crewAI, Inc.",
        "recorded_before_excerpt": True,
    },
    {
        "framework": "AutoGen/AG2 Classic",
        "repo": "https://github.com/ag2ai/ag2-classic",
        "path": "autogen/agentchat/groupchat.py",
        "spdx": "Apache-2.0",
        "also": (
            "AG2 v1.0 moved ConversableAgent/GroupChat off ag2ai/ag2 "
            "(that path 404s). Classic GroupChat lives in ag2-classic. "
            "Portions derived from https://github.com/microsoft/autogen are MIT."
        ),
        "copyright": "Copyright (c) 2023 - 2025, AG2ai, Inc.",
        "recorded_before_excerpt": True,
    },
]

CREWAI_PROCESS = {
    "anchor": "crewAIInc/crewAI lib/crewai/src/crewai/process.py",
    "url": "https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/process.py",
    "quote": (
        "class Process(str, Enum):\n"
        '    sequential = "sequential"\n'
        '    hierarchical = "hierarchical"\n'
        "    # TODO: consensual = 'consensual'"
    ),
}

CREWAI_KICKOFF = {
    "anchor": "crewAIInc/crewAI lib/crewai/src/crewai/crew.py Crew.kickoff",
    "url": "https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/crew.py",
    "quote": (
        "if self.process == Process.sequential:\n"
        "    result = self._run_sequential_process()\n"
        "elif self.process == Process.hierarchical:\n"
        "    result = self._run_hierarchical_process()\n"
        "else:\n"
        "    raise NotImplementedError(\n"
        '        f"The process \'{self.process}\' is not implemented yet."\n'
        "    )"
    ),
}

CREWAI_SEQUENTIAL = {
    "anchor": "crewAIInc/crewAI lib/crewai/src/crewai/crew.py _run_sequential_process/_execute_tasks",
    "url": "https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/crew.py",
    "quote": (
        "def _run_sequential_process(self) -> CrewOutput:\n"
        '    """Executes tasks sequentially and returns the final output."""\n'
        "    return self._execute_tasks(self.tasks)\n"
        "\n"
        "for task_index, task in enumerate(tasks):\n"
        "    ...\n"
        "    task_output = task.execute_sync(...)\n"
        "    task_outputs.append(task_output)\n"
        "return self._create_crew_output(task_outputs)"
    ),
    "documented_termination": (
        "Sequential crew termination is the end of the task list: after the "
        "for-loop over tasks, _create_crew_output is returned. There is no "
        "TERMINATE token. An agent hitting max_iter still returns an output "
        "and the next task proceeds."
    ),
}

CREWAI_HIERARCHICAL = {
    "anchor": "crewAIInc/crewAI lib/crewai/src/crewai/crew.py _run_hierarchical_process/_create_manager_agent",
    "url": "https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/crew.py",
    "quote": (
        "def _run_hierarchical_process(self) -> CrewOutput:\n"
        '    """Creates and assigns a manager agent to complete the tasks."""\n'
        "    self._create_manager_agent()\n"
        "    return self._execute_tasks(self.tasks)\n"
        "...\n"
        "manager = Agent(\n"
        '    role=i18n.retrieve("hierarchical_manager_agent", "role"),\n'
        "    tools=AgentTools(agents=self.agents).tools(),\n"
        "    allow_delegation=True,\n"
        "    llm=self.manager_llm,\n"
        ")"
    ),
    "documented_loop": (
        "Hierarchical still walks the task list, but the manager agent is a "
        "live conversational delegator (allow_delegation=True, AgentTools). "
        "That inner delegation loop has no barrier equivalent."
    ),
}

CREWAI_SEQUENTIAL_AGENT_REQUIRED = {
    "anchor": "crewAIInc/crewAI lib/crewai/src/crewai/crew.py validate_tasks",
    "url": "https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/crew.py",
    "quote": (
        "if self.process == Process.sequential:\n"
        "    for task in self.tasks:\n"
        "        if task.agent is None:\n"
        "            raise PydanticCustomError(\n"
        '                "missing_agent_in_task",\n'
        '                "Sequential process error: Agent is missing in the task ..."'
    ),
}

CREWAI_AGENT_DOCS = {
    "anchor": "https://docs.crewai.com/en/concepts/agents",
    "url": "https://docs.crewai.com/en/concepts/agents",
    "quote": (
        "Role | role | str | Defines the agent's function and expertise within the crew.\n"
        "Max Iterations (optional) | max_iter | int | Maximum iterations before "
        "the agent must provide its best answer. Default is 20.\n"
        "Allow Delegation (optional) | allow_delegation | bool | Allow the agent "
        "to delegate tasks to other agents. Default is False."
    ),
}

AUTOGEN_GROUPCHAT_FIELDS = {
    "anchor": "ag2ai/ag2-classic autogen/agentchat/groupchat.py GroupChat",
    "url": "https://github.com/ag2ai/ag2-classic/blob/main/autogen/agentchat/groupchat.py",
    "quote": (
        "@dataclass\n"
        "class GroupChat:\n"
        "    agents: list[Agent]\n"
        "    messages: list[dict[str, Any]] = field(default_factory=list)\n"
        "    max_round: int = 10\n"
        '    speaker_selection_method: ... Default is "auto".\n'
        '    - "auto": the next speaker is selected automatically by LLM.\n'
        '    - "manual": the next speaker is selected manually by user input.\n'
        '    - "random": the next speaker is selected randomly.\n'
        '    - "round_robin": the next speaker is selected in a round robin fashion\n'
        "    - a customized speaker selection function (Callable): ...\n"
        "      3. None, which would terminate the conversation gracefully."
    ),
}

AUTOGEN_RUN_CHAT_STOP = {
    "anchor": "ag2ai/ag2-classic autogen/agentchat/groupchat.py GroupChatManager.run_chat",
    "url": "https://github.com/ag2ai/ag2-classic/blob/main/autogen/agentchat/groupchat.py",
    "quote": (
        "for i in range(groupchat.max_round):\n"
        "    ...\n"
        "    if self._is_termination_msg(message):\n"
        "        termination_reason = (\n"
        '            f"Termination message condition on the GroupChatManager '
        "'{self.name}' met\"\n"
        "        )\n"
        "        break\n"
        "    elif i == groupchat.max_round - 1:\n"
        '        termination_reason = f"Maximum rounds ({groupchat.max_round}) reached"\n'
        "        break\n"
        "    try:\n"
        "        speaker = groupchat.select_speaker(speaker, self)\n"
        "        ...\n"
        "    except NoEligibleSpeakerError:\n"
        '        termination_reason = "No next speaker selected"\n'
        "        break\n"
        "    if reply is None:\n"
        '        termination_reason = "No reply generated"\n'
        "        break"
    ),
    "documented_termination": (
        "After broadcasting the message at round i (0-based, i in "
        "range(max_round)): stop if is_termination_msg; else stop if "
        "i == max_round - 1; else select the next speaker. A custom "
        "speaker selector returning None raises NoEligibleSpeakerError "
        "which run_chat treats as stop. generate_reply returning None "
        "also stops. Published AutoGen 0.2 notebooks bind "
        "is_termination_msg to the substring TERMINATE."
    ),
}

AUTOGEN_MANAGER_DEFAULTS = {
    "anchor": "ag2ai/ag2-classic autogen/agentchat/groupchat.py GroupChatManager.__init__",
    "url": "https://github.com/ag2ai/ag2-classic/blob/main/autogen/agentchat/groupchat.py",
    "quote": (
        "max_consecutive_auto_reply: int | None = sys.maxsize,\n"
        'human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER"'
    ),
}

NOTEBOOK_TERMINATE = {
    "anchor": "microsoft/autogen v0.2.16 notebook/agentchat_society_of_mind.ipynb",
    "url": "https://github.com/microsoft/autogen/blob/v0.2.16/notebook/agentchat_society_of_mind.ipynb",
    "quote": (
        'is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0'
    ),
}


def licences_recorded() -> bool:
    return all(row.get("recorded_before_excerpt") for row in LICENCES)
