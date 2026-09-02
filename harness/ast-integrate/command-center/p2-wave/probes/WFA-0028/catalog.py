"""Captured niche/archival/non-English sources plus an independent mainstream index.

Quotes were retrieved this session from public HTTP(S) pages. Onion URLs are
queued only, never fetched. Probes re-run against this catalog, not the network.
"""
from __future__ import annotations

SOURCES = [
    {
        "id": "src-ja-note-metagpt-sop",
        "class": "non-english-practitioner",
        "language": "ja",
        "url": "https://note.com/snake_dragon/n/nfaa6f9b9d7a6",
        "retrieved_at": "2026-08-24T18:45:00Z",
        "archive_timestamp": None,
        "title": "MetaGPT完全ガイド（日本語実務解説）",
        "mechanism_id": "sop-encoded-role-pipeline",
        "mechanism": "SOP-encoded multi-agent assembly line",
        "original_quote": (
            "「Code = SOP(Team)」 SOPとは「Standardized Operating Procedures"
            "（標準作業手順）」のことで、企業や組織が効率的に機能するために定め"
            "たルールや業務フローのこと。MetaGPTは、このSOPをLLM（大規模言語"
            "モデル）へのプロンプトシーケンスとしてエンコードし、異なる専門役割"
            "を持つ複数のエージェントが協働する仕組みを構築している。"
        ),
        "translation": (
            '"Code = SOP(Team)". SOP means Standardized Operating Procedures: '
            "rules and workflows an organization sets so it can function "
            "efficiently. MetaGPT encodes those SOPs as prompt sequences for "
            "LLMs, building a mechanism in which multiple agents with different "
            "specialist roles collaborate."
        ),
        "tokens": ["sop", "prompt sequences", "specialized roles"],
        "proposal_only": False,
    },
    {
        "id": "src-ja-zenn-hitl-gate",
        "class": "non-english-practitioner",
        "language": "ja",
        "url": "https://zenn.dev/takuh/articles/084dc043ffa56c",
        "retrieved_at": "2026-08-24T18:45:00Z",
        "archive_timestamp": None,
        "title": "LangGraph 入門 〜初学者のためのハンズオンガイド〜",
        "mechanism_id": "durable-hitl-interrupt-gate",
        "mechanism": "durable human-in-the-loop interrupt gate",
        "original_quote": (
            "Human-in-the-loop：処理の途中で人間が確認・修正できる。"
            "実際のビジネス要件では「このアクション、本当に実行してよいですか？」"
            "という人間の承認が必要になる。"
        ),
        "translation": (
            "Human-in-the-loop: a human can inspect and correct mid-run. "
            "Real business requirements need a human approval step of the form "
            '"may this action actually be executed?"'
        ),
        "tokens": ["interrupt", "human-in-the-loop", "resume"],
        "proposal_only": False,
    },
    {
        "id": "src-ru-habr-crew-hierarchical",
        "class": "non-english-practitioner",
        "language": "ru",
        "url": "https://habr.com/ru/articles/957384/",
        "retrieved_at": "2026-08-24T18:45:00Z",
        "archive_timestamp": None,
        "title": "Мультиагентный фреймворк CrewAI: разбор архитектуры",
        "mechanism_id": "runtime-manager-task-allocation",
        "mechanism": "runtime manager agent allocating unassigned tasks",
        "original_quote": (
            "Crew поддерживает два фундаментально разных режима координации "
            "агентов: sequential и hierarchical. В hierarchical процессе "
            "появляется дополнительный слой управления — внутренний Manager "
            "агент. Этот менеджер сам анализирует все задачи и доступных "
            "агентов, затем принимает решения о распределении работы. Здесь "
            "уже можно не указывать кому накинуть задачку, решение будет "
            "принято в рантайме."
        ),
        "translation": (
            "Crew supports two fundamentally different agent-coordination "
            "modes: sequential and hierarchical. In the hierarchical process "
            "an extra control layer appears — an internal Manager agent. That "
            "manager itself analyses every task and the available agents, then "
            "decides how to distribute the work. You no longer have to name "
            "who gets the task; the decision is taken at runtime."
        ),
        "tokens": ["hierarchical", "manager_llm", "delegat"],
        "proposal_only": False,
    },
    {
        "id": "src-archival-babyagi-loop",
        "class": "archival-practitioner",
        "language": "en",
        "url": "https://yoheinakajima.com/birth-of-babyagi/",
        "retrieved_at": "2026-08-24T18:50:00Z",
        "archive_timestamp": "2023-04-01",
        "title": "Birth of BabyAGI – Yohei Nakajima",
        "mechanism_id": "create-execute-prioritize-loop",
        "mechanism": "execution / task-creation / prioritization loop",
        "original_quote": (
            "the user provides an initial objective and task. An execution "
            "agent completes the task, a task creation agents creates "
            "follow-up tasks based on the result, and a prioritization agent "
            "adjusts the task list before sending the next task to the "
            "execution agent. We store task/result pairs in Pinecone as "
            "embedded vectors"
        ),
        "translation": (
            "the user provides an initial objective and task. An execution "
            "agent completes the task, a task-creation agent creates follow-up "
            "tasks based on the result, and a prioritization agent adjusts the "
            "task list before sending the next task to the execution agent."
        ),
        "tokens": ["task creation", "prioritization", "execution agent"],
        "proposal_only": False,
    },
    {
        "id": "src-archival-babyagi-parallel-proposal",
        "class": "archival-practitioner",
        "language": "en",
        "url": "https://yoheinakajima.com/birth-of-babyagi/",
        "retrieved_at": "2026-08-24T18:50:00Z",
        "archive_timestamp": "2023-04-01",
        "title": "Birth of BabyAGI – Yohei Nakajima (future-work paragraph)",
        "mechanism_id": "parallel-task-execution-proposal",
        "mechanism": "parallel task execution as a proposed BabyAGI improvement",
        "original_quote": (
            "Some more core improvements to be made include adding "
            "safety/security measures, tracking task serialization, running "
            "parallel tasks, and adding a module to gather live updates such "
            "as checking emails and texts for new tasks and information."
        ),
        "translation": (
            "Some more core improvements to be made include adding "
            "safety/security measures, tracking task serialization, running "
            "parallel tasks, and adding a module to gather live updates such "
            "as checking emails and texts for new tasks and information."
        ),
        "tokens": ["running parallel tasks", "task serialization"],
        "proposal_only": True,
    },
    {
        "id": "src-archival-contract-net-1980",
        "class": "archival-academic",
        "language": "en",
        "url": "https://www.reidgsmith.com/The_Contract_Net_Protocol_Dec-1980.pdf",
        "retrieved_at": "2026-08-24T18:50:00Z",
        "archive_timestamp": "1980-12",
        "title": "The Contract Net Protocol (IEEE TC, Dec 1980)",
        "mechanism_id": "contract-net-bid-award",
        "mechanism": "manager/contractor bid-and-award task distribution",
        "original_quote": (
            "available contractors evaluate task announcements made by several "
            "managers and submit bids on those for which they are suited. The "
            "managers evaluate the bids and award contracts to the nodes they "
            "determine to be most appropriate."
        ),
        "translation": (
            "available contractors evaluate task announcements made by several "
            "managers and submit bids on those for which they are suited. The "
            "managers evaluate the bids and award contracts to the nodes they "
            "determine to be most appropriate."
        ),
        "tokens": ["task announcements", "submit bids", "award contracts"],
        "proposal_only": False,
    },
    {
        "id": "src-onion-queued-not-fetched",
        "class": "onion",
        "language": "und",
        "url": "http://wfa0028researchexample.onion/orchestration-index",
        "retrieved_at": None,
        "archive_timestamp": None,
        "title": "queued lawful-public onion index (not fetched)",
        "mechanism_id": None,
        "mechanism": None,
        "original_quote": None,
        "translation": None,
        "tokens": [],
        "proposal_only": False,
        "queued_only": True,
    },
]

MAINSTREAM = [
    {
        "id": "ms-arxiv-2308-00352",
        "surface": "arxiv",
        "url": "https://arxiv.org/html/2308.00352v7",
        "retrieved_at": "2026-08-24T18:45:00Z",
        "text": (
            "MetaGPT encodes Standardized Operating Procedures (SOPs) into "
            "prompt sequences for more streamlined workflows, thus allowing "
            "agents with human-like domain expertise to verify intermediate "
            "results. assembly line paradigm to assign diverse specialized "
            "roles to various agents."
        ),
    },
    {
        "id": "ms-langgraph-interrupt-docs",
        "surface": "vendor-docs",
        "url": "https://docs.langchain.com/oss/python/langgraph/interrupts",
        "retrieved_at": "2026-08-24T18:55:00Z",
        "text": (
            "Interrupts allow you to pause graph execution at specific points "
            "and wait for external input before continuing. This enables "
            "human-in-the-loop patterns. You resume execution by re-invoking "
            "the graph using Command, which then becomes the return value of "
            "the interrupt() call."
        ),
    },
    {
        "id": "ms-crewai-process-docs",
        "surface": "vendor-docs",
        "url": "https://docs.crewai.com/en/concepts/processes",
        "retrieved_at": "2026-08-24T18:55:00Z",
        "text": (
            "Hierarchical: Organizes tasks in a managerial hierarchy. A "
            "manager language model (manager_llm) or a custom manager agent "
            "(manager_agent) must be specified. This agent oversees task "
            "execution, including planning, delegation, and validation. Tasks "
            "are not pre-assigned; the manager allocates tasks to agents."
        ),
    },
    {
        "id": "ms-ibm-babyagi",
        "surface": "mainstream-explainer",
        "url": "https://www.ibm.com/think/topics/babyagi",
        "retrieved_at": "2026-08-24T18:55:00Z",
        "text": (
            "BabyAGI uses a repeating three-stage AI workflow: Task execution: "
            "The execution agent runs a task. Task creation: the task creation "
            "agent generates follow-up tasks. Task prioritization: A "
            "prioritization agent reorders all outstanding tasks."
        ),
    },
    {
        "id": "ms-wikipedia-contract-net",
        "surface": "mainstream-reference",
        "url": "https://en.wikipedia.org/wiki/Contract_Net_Protocol",
        "retrieved_at": "2026-08-24T18:50:00Z",
        "text": (
            "The Contract Net Protocol is a task-sharing protocol in "
            "multi-agent systems, introduced in 1980 by Reid G. Smith. The "
            "manager sends a call-for-proposals. Contractors submit bids. The "
            "manager awards the contract. This is equivalent to evaluating "
            "task announcements, submit bids, and award contracts."
        ),
    },
]
