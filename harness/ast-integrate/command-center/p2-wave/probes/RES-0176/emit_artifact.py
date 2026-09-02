#!/usr/bin/env python3
"""Emit RES-0176 teardown artifact from live captured snapshots."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    ARTIFACT,
    ARTIFACT_REL,
    MIN_BYTES,
    SENTINEL,
    UID,
    build_harvest_index,
    grade_claim,
    hardness_scan,
    rail,
    transfer_verdict_errors,
    utc_now,
)

QUESTION = (
    "What does each framework make easy that the other two make hard "
    "(typed state graphs, role/crew delegation, conversational group chat), "
    "and which of those abstractions is transferable to a prompt-native "
    "control plane WITHOUT importing a second orchestration runtime?"
)

# Distinctive quotes verified against captured bytes at emit time via rail().
Q_LG_SRC = (
    "Each state key can optionally be annotated with a reducer function that "
    "will be used to aggregate the values of that key received from multiple nodes."
)
Q_LG_DOC = (
    "can be either a `TypedDict` or a `Pydantic` model. All `Nodes` will emit "
    "updates to the `State` which are then applied using the specified "
    "`reducer` function."
)
Q_LG_COMPILE_SRC = (
    "You must first call `.compile()` to create an executable graph that supports"
)
Q_LG_PREGEL_DOC = (
    "When you compile the graph, the StateGraph API automatically creates the "
    "Pregel application for you."
)
Q_LG_CKPT_SRC = (
    "If provided, this `Checkpointer` serves as a fully versioned "
    '"short-term memory" for the graph'
)
Q_CREW_SRC = (
    "Each agent has a role, a goal, a backstory, and an optional language model (llm)."
)
Q_CREW_DOC = "Defines the agent's function and expertise within the crew."
Q_CREW_HIER_SRC = "Creates and assigns a manager agent to complete the tasks."
Q_CREW_HIER_DOC = (
    "The system requires a manager LLM to be set up for proper function"
)
Q_CREW_PROC = 'hierarchical = "hierarchical"'
Q_AG_BROADCAST = "broadcast the message to all agents except the speaker"
Q_AG_SPEAKER = (
    'the next speaker is selected in a round robin fashion, i.e., iterating '
    "in the same order as provided in `agents`."
)
Q_AG_MGR = "A chat manager agent that can manage a group chat of multiple agents."
Q_AG_DOC = "broadcasts the message to all other agents in the group"
Q_LG_LICENSE = "MIT License"
Q_CREW_LICENSE = "Copyright (c) 2025 crewAI, Inc."
Q_AG_LICENSE = "Attribution 4.0 International"

VPATH = (
    "probe1_quotes.py re-grep of captured bytes plus live sha256; "
    "probe2_negative_control.py both-states mutant on transfer verdicts"
)


def main() -> int:
    idx = build_harvest_index()
    hard = hardness_scan()
    if not hard["all_exclusive"]:
        print("FAILED:RES-0176 emit hardness needles not exclusive", hard)
        return 1

    claims = [
        {
            "claim_id": "RES-0176-C-LG-TYPED-STATE",
            "abstraction": "typed_state_graphs",
            "framework": "LangGraph",
            "makes_easy": (
                "Shared typed state (TypedDict or Pydantic) with per-key reducer "
                "functions, explicit nodes/edges, then compile()."
            ),
            "others_make_hard": (
                "CrewAI tasks pass string context, not per-key reducers. AutoGen "
                "group chat treats the message list as the conversation state; "
                "neither snapshot contains the LangGraph reducer annotation."
            ),
            "canonical_mechanism": (
                "A graph-shaped workflow whose nodes read/write a shared state "
                "object; each state key has an independent reducer "
                "(Value, Value) -> Value."
            ),
            "quoted_mechanism": Q_LG_SRC,
            "evidence_tier": "E2",
            "confidence_band": "highly probable",
            "sherman_kent_band": "highly probable",
            "independent_verification_path": VPATH,
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Docs MDX is the langchain-ai/docs tree, not a Python import; "
                "JS and Python sections both exist in graph-api.mdx."
            ),
            "source_lineage": [
                rail("lg_state.py", Q_LG_SRC, idx),
                rail("lg_graph_api.mdx", Q_LG_DOC, idx),
            ],
        },
        {
            "claim_id": "RES-0176-C-LG-COMPILE-PREGEL",
            "abstraction": "typed_state_graphs",
            "framework": "LangGraph",
            "makes_easy": (
                "compile() turns the builder into a Pregel application and is "
                "also where checkpointers and breakpoints are attached."
            ),
            "others_make_hard": (
                "CrewAI and AutoGen do not expose StateGraph.compile or Pregel "
                "channels. That is the runtime, not the transferable mechanism."
            ),
            "canonical_mechanism": (
                "StateGraph is a builder. Execution requires compile(), which "
                "the official Pregel guide says creates a Pregel application."
            ),
            "quoted_mechanism": Q_LG_PREGEL_DOC,
            "evidence_tier": "E2",
            "confidence_band": "highly probable",
            "sherman_kent_band": "highly probable",
            "independent_verification_path": VPATH,
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Checkpointer persistence is a runtime service; it is named so "
                "it is not smuggled in as 'just typed state'."
            ),
            "source_lineage": [
                rail("lg_state.py", Q_LG_COMPILE_SRC, idx),
                rail("lg_pregel.mdx", Q_LG_PREGEL_DOC, idx),
                rail("lg_state.py", Q_LG_CKPT_SRC, idx),
            ],
        },
        {
            "claim_id": "RES-0176-C-CREW-ROLE",
            "abstraction": "role_crew_delegation",
            "framework": "CrewAI",
            "makes_easy": (
                "First-class Agent with role, goal, backstory, plus Crew Process "
                "sequential or hierarchical."
            ),
            "others_make_hard": (
                "LangGraph nodes are state functions, not role/goal/backstory "
                "cards. AutoGen conversable agents are not Crew/Task/Process."
            ),
            "canonical_mechanism": (
                "A role/goal/backstory prompt triple bound to an agent, then a "
                "crew process that either runs tasks in listed order or "
                "delegates via a manager agent."
            ),
            "quoted_mechanism": Q_CREW_SRC,
            "evidence_tier": "E2",
            "confidence_band": "highly probable",
            "sherman_kent_band": "highly probable",
            "independent_verification_path": VPATH,
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Sequential process is the transferable slice. Hierarchical "
                "manager construction is a Crew runtime loop."
            ),
            "source_lineage": [
                rail("crew_agent_core.py", Q_CREW_SRC, idx),
                rail("crew_agents.mdx", Q_CREW_DOC, idx),
                rail("crew_process.py", Q_CREW_PROC, idx),
            ],
        },
        {
            "claim_id": "RES-0176-C-CREW-HIERARCHICAL",
            "abstraction": "role_crew_delegation",
            "framework": "CrewAI",
            "makes_easy": (
                "Process.hierarchical creates or assigns a manager agent that "
                "completes tasks via delegation; manager_llm is required if no "
                "manager_agent is supplied."
            ),
            "others_make_hard": (
                "LangGraph and AutoGen do not ship Process.hierarchical or "
                "_create_manager_agent."
            ),
            "canonical_mechanism": (
                "A manager agent with allow_delegation=True that is either "
                "user-supplied or constructed from manager_llm, then "
                "_execute_tasks."
            ),
            "quoted_mechanism": Q_CREW_HIER_SRC,
            "evidence_tier": "E2",
            "confidence_band": "highly probable",
            "sherman_kent_band": "highly probable",
            "independent_verification_path": VPATH,
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Hierarchical kickoff is CrewAI's process executor, not a "
                "prompt card. Sequential role cards remain transferable."
            ),
            "source_lineage": [
                rail("crew_crew.py", Q_CREW_HIER_SRC, idx),
                rail("crew_hier.mdx", Q_CREW_HIER_DOC, idx),
            ],
        },
        {
            "claim_id": "RES-0176-C-AG-GROUPCHAT",
            "abstraction": "conversational_group_chat",
            "framework": "AutoGen/AG2",
            "makes_easy": (
                "GroupChat plus GroupChatManager: select next speaker "
                "(auto/manual/random/round_robin), then broadcast the utterance "
                "to every other agent."
            ),
            "others_make_hard": (
                "LangGraph has no GroupChatManager broadcast loop. CrewAI "
                "hierarchical delegation is manager-to-worker tasks, not "
                "all-to-all utterance fan-out."
            ),
            "canonical_mechanism": (
                "A conversation runtime that holds an agent list and message "
                "log, selects a speaker, appends the utterance, and sends it "
                "to all non-speakers."
            ),
            "quoted_mechanism": Q_AG_BROADCAST,
            "evidence_tier": "E2",
            "confidence_band": "probable",
            "sherman_kent_band": "probable",
            "independent_verification_path": VPATH,
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "R1 is microsoft/autogen 0.2 groupchat.py (the named "
                "GroupChatManager implementation). R2 is current AG2 docs, "
                "which still describe the same select-then-broadcast loop. "
                "ag2ai/ag2 main no longer vendors autogen/agentchat/groupchat.py "
                "(migration note exists). AutoGen LICENSE on the 0.2 branch is "
                "CC-BY-4.0; this record quotes short excerpts and extracts the "
                "mechanism, it does not copy the runtime."
            ),
            "source_lineage": [
                rail("ag_groupchat.py", Q_AG_BROADCAST, idx),
                rail("ag_groupchat.py", Q_AG_SPEAKER, idx),
                rail("ag_groupchat.py", Q_AG_MGR, idx),
                rail("ag2_groupchat.html", Q_AG_DOC, idx),
            ],
        },
    ]

    # C-LG-COMPILE has two quotes from the same snapshot plus pregel docs.
    # grade_claim needs >=2 distinct rail_kinds: R1-source and R2-prose. Good.

    transfer_verdicts = [
        {
            "abstraction": "typed_state_graphs",
            "transferable": True,
            "mechanism": (
                "Named state keys with an independent merge rule per key "
                "(overwrite or list-concat / custom reducer) plus explicit "
                "node and edge topology."
            ),
            "runtime_host": (
                "langgraph.graph.state.StateGraph.compile -> CompiledStateGraph "
                "/ Pregel; optional Checkpointer"
            ),
            "runtime_service": None,
            "reimplementation_cost": (
                "Extend WFA-0044 WorkflowIR with a state_schema object "
                "(key -> {type, reducer}) and a conditional_edge table; "
                "implement overwrite and list-concat in the existing "
                "prompt-native runner. Do not install langgraph. Checkpointer "
                "put/get and interrupt_before stay unmapped (Pregel persistence)."
            ),
            "what_importing_would_do": (
                "Importing langgraph would add a Pregel superstep scheduler "
                "and checkpoint store — a second orchestration runtime."
            ),
        },
        {
            "abstraction": "role_crew_delegation",
            "transferable": True,
            "mechanism": (
                "Role/goal/backstory prompt triple plus an ordered task list "
                "(sequential process)."
            ),
            "runtime_host": "crewai.Crew.kickoff / crewai.Process",
            "runtime_service": None,
            "reimplementation_cost": (
                "Map Agent.role/goal/backstory onto existing WFA-0044 IR nodes "
                "of kind=role; map sequential Task lists onto existing stage "
                "order. Do not install crewai. Process.hierarchical "
                "(_run_hierarchical_process / _create_manager_agent) is not "
                "in this transferable slice."
            ),
            "what_importing_would_do": (
                "Importing Crew.kickoff would add CrewAI's process executor "
                "as a second control loop beside the prompt-native plane."
            ),
        },
        {
            "abstraction": "conversational_group_chat",
            "transferable": False,
            "mechanism": (
                "Speaker-selection policy over an agent roster plus broadcast "
                "of each utterance to all other agents."
            ),
            "runtime_host": (
                "autogen.agentchat.groupchat.GroupChatManager "
                "(microsoft/autogen 0.2; documented equivalently by AG2)"
            ),
            "runtime_service": (
                "GroupChatManager speaker-select-and-broadcast loop: "
                "select_speaker, groupchat.append, then self.send(message, "
                "agent, request_reply=False) to every non-speaker"
            ),
            "reimplementation_cost": (
                "Not reimplemented. Doing so would add an in-session agent "
                "registry, nested LLM speaker-selection, and all-to-all "
                "message fan-out — a second conversation orchestration "
                "runtime, forbidden by _USER-PROMPTS.md:10727. A prompt-native "
                "plane may still sequence named speakers as ordinary stages; "
                "that is not this abstraction."
            ),
            "what_importing_would_do": (
                "Importing GroupChatManager would create a second "
                "orchestration runtime inside the session."
            ),
        },
    ]

    terr = transfer_verdict_errors(transfer_verdicts)
    if terr:
        print("FAILED:RES-0176 emit transfer verdicts", terr)
        return 1

    for c in claims:
        g = grade_claim(c, idx)
        if not g["citable_as_measured_fact"]:
            print("FAILED:RES-0176 emit claim", c["claim_id"], g)
            return 1

    licenses = [
        {
            "project": "langchain-ai/langgraph",
            "license_file_quote": Q_LG_LICENSE,
            "classifier_label_not_used": True,
            "source_lineage": [rail("lg_license", Q_LG_LICENSE, idx)],
        },
        {
            "project": "crewAIInc/crewAI",
            "license_file_quote": Q_CREW_LICENSE,
            "classifier_label_not_used": True,
            "source_lineage": [rail("crew_license", Q_CREW_LICENSE, idx)],
        },
        {
            "project": "microsoft/autogen (0.2 branch)",
            "license_file_quote": Q_AG_LICENSE,
            "classifier_label_not_used": True,
            "note": (
                "LICENSE file on the 0.2 branch opens with Attribution 4.0 "
                "International (CC-BY-4.0). Mechanism extracted; runtime not copied."
            ),
            "source_lineage": [rail("ag_license", Q_AG_LICENSE, idx)],
        },
    ]

    answer = (
        "LangGraph makes typed shared-state graphs easy: nodes communicate "
        "through a TypedDict/Pydantic State whose keys carry independent "
        "reducer functions, then StateGraph.compile() builds a Pregel app "
        "(checkpointer optional). CrewAI and AutoGen snapshots do not contain "
        "that reducer annotation. CrewAI makes role/crew delegation easy: "
        "Agent(role, goal, backstory) plus Process.sequential or "
        "Process.hierarchical (manager agent + manager_llm). LangGraph and "
        "AutoGen snapshots do not contain that role/goal/backstory agent "
        "contract. AutoGen/AG2 makes conversational group chat easy: "
        "GroupChatManager selects a speaker and broadcasts each utterance to "
        "all other agents. LangGraph and CrewAI snapshots do not contain that "
        "broadcast loop. Transfer onto this estate's prompt-native control "
        "plane (WFA-0044 WorkflowIR, no second orchestration runtime): typed "
        "state graphs ARE transferable as IR state_schema + reducer names + "
        "edges (cost: schema extension plus overwrite/list-concat; do not "
        "import Pregel/checkpointer). Sequential role/crew IS transferable as "
        "existing IR role nodes plus ordered stages (cost: map the three "
        "prompt fields; do not import Crew.kickoff). Conversational group "
        "chat is NOT transferable without the GroupChatManager "
        "speaker-select-and-broadcast loop (named runtime service). "
        "SUCCESS:RES-0176"
    )

    doc = {
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "ecosystem-teardown",
        "schema": "command-center/p2-wave/probes/RES-0176/artifact.schema.json",
        "declared_output_schema": (
            "command-center/schema/ecosystem-teardown.schema.json"
        ),
        "declared_output_schema_present": (
            HERE.parents[3]
            / "command-center/schema/ecosystem-teardown.schema.json"
        ).is_file(),
        "question": QUESTION,
        "answer": answer,
        "title": (
            "Teardown: LangGraph, CrewAI and AutoGen — graph abstraction "
            "versus role abstraction versus conversational group chat"
        ),
        "frameworks": [
            {
                "id": "langgraph",
                "makes_easy": "typed_state_graphs",
                "distinctive_primitive": "StateGraph + per-key reducers + compile()",
            },
            {
                "id": "crewai",
                "makes_easy": "role_crew_delegation",
                "distinctive_primitive": "Agent role/goal/backstory + Crew Process",
            },
            {
                "id": "autogen",
                "makes_easy": "conversational_group_chat",
                "distinctive_primitive": "GroupChatManager select-then-broadcast",
            },
        ],
        "control_plane": {
            "kind": "prompt-native",
            "ir": "WFA-0044 WorkflowIR (nodes with id/kind/source_anchor)",
            "constraint": (
                "_USER-PROMPTS.md:10727 do not import a second orchestration runtime; "
                "extract the mechanism"
            ),
            "no_runtime_installed": True,
        },
        "claims": claims,
        "transfer_verdicts": transfer_verdicts,
        "negative_control": {
            "id": "T-NEG-GROUPCHAT-NOT-TRANSFERABLE",
            "abstraction": "conversational_group_chat",
            "transferable": False,
            "runtime_service": (
                "GroupChatManager speaker-select-and-broadcast loop: "
                "select_speaker, groupchat.append, then self.send(message, "
                "agent, request_reply=False) to every non-speaker"
            ),
            "why": (
                "The abstraction is the runtime: an agent registry plus nested "
                "speaker selection plus all-to-all fan-out. Importing it "
                "creates a second orchestration runtime."
            ),
        },
        "hardness": hard,
        "licenses": licenses,
        "tests": [
            {
                "id": "probe1-quotes-two-rails-hardness",
                "name": (
                    "Every load-bearing claim has two independent rails whose "
                    "quotes hit captured bytes; distinctive needles are exclusive "
                    "to the owning framework"
                ),
                "result": "PENDING",
            },
            {
                "id": "probe2-negative-control",
                "name": (
                    "At least one abstraction is NOT transferable with a named "
                    "runtime service; a mutant that marks it transferable must fail"
                ),
                "result": "PENDING",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0176-probe2-negative-control",
            "verdict": "PENDING",
            "independent": True,
            "defaults_to": "REFUTED",
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "teardown-analyst",
            "execution_substrate": "headless-linux",
        },
        "timestamps": {"emitted_at": utc_now()},
        "notes": (
            "G-1 research teardown. Live captures hashed. Two-rail (source+prose) "
            "citations required for E2 claims. Did not run global "
            "unit_manifest.py --write. Did not import langgraph, crewai, or autogen."
        ),
    }

    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0176 emit sentinel missing")
        return 1
    if len(text.encode("utf-8")) < MIN_BYTES:
        print("FAILED:RES-0176 emit too small")
        return 1

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(text, encoding="utf-8")
    print(
        f"wrote {ARTIFACT_REL} claims={len(claims)} "
        f"transfer={len(transfer_verdicts)} hardness_exclusive={hard['all_exclusive']}"
    )
    print("SUCCESS:RES-0176 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
