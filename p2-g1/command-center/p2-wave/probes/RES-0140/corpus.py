#!/usr/bin/env python3
"""Fixed 20-item sample for RES-0140.

Six subjects held constant across official-docs, blog-post, and transcript
classes (18 items) plus two planted restatement transcripts (negative control).

Threshold T-DEFAULT-SOURCE-CLASS-2026-08-24 is frozen here before measurement.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"
UID = "RES-0140"
OUT_REL = (
    "command-center/research/sources-frontier/"
    "RES-0140-transcript-source-class-yield-measurement.json"
)
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
QUESTION = (
    "Measured over a fixed 20-item sample, how many distinct, non-duplicate "
    "mechanisms does a video/talk transcript produce per 10k tokens of "
    "extraction cost, compared with the blog-post and official-docs classes "
    "over the same subject matter - and does it clear the threshold to stay "
    "in the default source-class set?"
)
SENTINEL = "SUCCESS:RES-0140"

SUBJECTS = [
    "agent-skills",
    "mcp-tools",
    "openai-codex",
    "cursor-cloud-agent",
    "copilot-workspace",
    "replit-agent",
]
CLASSES = ("official-docs", "blog-post", "transcript")

# Pre-registered before measuring. Transcripts stay in the default set iff
# incremental unique-mechanism yield per 10k tokens (after collapsing the two
# planted restatements against companion blogs) is >= 1.0 AND >= 0.50 times
# official-docs incremental yield per 10k tokens on the same 20-item sample.
THRESHOLD = {
    "id": "T-DEFAULT-SOURCE-CLASS-2026-08-24",
    "frozen_at": "2026-08-24T20:00:00Z",
    "min_incremental_unique_per_10k": 1.0,
    "min_fraction_of_official_docs": 0.50,
    "rule": (
        "Transcript class stays in the default source-class set iff "
        "incremental unique-mechanism yield per 10k tokens, after collapsing "
        "restatement transcripts against companion blogs, is >= 1.0 AND "
        ">= 0.50 times the official-docs class incremental yield per 10k tokens."
    ),
}

# Fetch specs. restatement items are derived locally after companion blogs exist.
# local_fallback copies a prior in-tree capture when live HTTP fails.
ITEMS = [
    {
        "id": "od-skills",
        "source_class": "official-docs",
        "subject": "agent-skills",
        "urls": [
            "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0104/captures/anthropic-skills-overview.bin"
        ),
        "fallback_url": (
            "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md"
        ),
        "kind": "prose",
    },
    {
        "id": "od-mcp-tools",
        "source_class": "official-docs",
        "subject": "mcp-tools",
        "urls": [
            "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/tools.mdx",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0104/captures/mcp-tools-spec-mdx.bin"
        ),
        "fallback_url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/tools.mdx"
        ),
        "kind": "prose",
    },
    {
        "id": "od-codex",
        "source_class": "official-docs",
        "subject": "openai-codex",
        "urls": [
            "https://developers.openai.com/codex/llms.txt",
            "https://learn.chatgpt.com/docs/llms.txt",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/openai-codex-llms.txt"
        ),
        "fallback_url": "https://developers.openai.com/codex/llms.txt",
        "kind": "prose",
    },
    {
        "id": "od-cursor",
        "source_class": "official-docs",
        "subject": "cursor-cloud-agent",
        "urls": [
            "https://cursor.com/docs/cloud-agent",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/cursor-cloud-agent.txt"
        ),
        "fallback_url": "https://cursor.com/docs/cloud-agent",
        "kind": "prose",
    },
    {
        "id": "od-copilot",
        "source_class": "official-docs",
        "subject": "copilot-workspace",
        "urls": [
            "https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/overview.md",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/copilot-workspace-manual.txt"
        ),
        "fallback_url": (
            "https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/overview.md"
        ),
        "kind": "prose",
    },
    {
        "id": "od-replit",
        "source_class": "official-docs",
        "subject": "replit-agent",
        "urls": [
            "https://docs.replit.com/llms.txt",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/replit-agent-llms.txt"
        ),
        "fallback_url": "https://docs.replit.com/llms.txt",
        "kind": "prose",
    },
    {
        "id": "blog-skills",
        "source_class": "blog-post",
        "subject": "agent-skills",
        "urls": [
            "https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills",
        ],
        "kind": "prose",
    },
    {
        "id": "blog-mcp",
        "source_class": "blog-post",
        "subject": "mcp-tools",
        "urls": [
            "https://www.anthropic.com/news/model-context-protocol",
            "https://www.anthropic.com/research/model-context-protocol",
        ],
        "kind": "prose",
    },
    {
        "id": "blog-codex",
        "source_class": "blog-post",
        "subject": "openai-codex",
        "urls": [
            "https://openai.com/index/introducing-codex/",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0140/fixtures/blog-codex-introducing.txt"
        ),
        "fallback_url": "https://openai.com/index/introducing-codex/",
        "kind": "prose",
    },
    {
        "id": "blog-cursor",
        "source_class": "blog-post",
        "subject": "cursor-cloud-agent",
        "urls": [
            "https://cursor.com/blog/agent",
            "https://cursor.com/changelog",
        ],
        "kind": "prose",
    },
    {
        "id": "blog-copilot",
        "source_class": "blog-post",
        "subject": "copilot-workspace",
        "urls": [
            "https://github.blog/news-insights/product-news/github-copilot-workspace/",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/copilot-workspace-blog.html"
        ),
        "fallback_url": (
            "https://github.blog/news-insights/product-news/github-copilot-workspace/"
        ),
        "kind": "prose",
    },
    {
        "id": "blog-replit",
        "source_class": "blog-post",
        "subject": "replit-agent",
        "urls": [
            "https://blog.replit.com/agent",
            "https://blog.replit.com/replit-agent",
            "https://replit.com/blog/introducing-replit-agent",
        ],
        "kind": "prose",
    },
    {
        "id": "tr-skills-talk",
        "source_class": "transcript",
        "subject": "agent-skills",
        "role": "independent-talk",
        "urls": [
            "https://sozai.app/transcript/build-skills-instead-agents-anthropic/",
            "https://lilys.ai/en/notes/agent-skills-20251225/build-skills-not-agents",
        ],
        "kind": "prose",
    },
    {
        "id": "tr-mcp-talk",
        "source_class": "transcript",
        "subject": "mcp-tools",
        "role": "independent-talk",
        "urls": [
            "https://www.anthropic.com/engineering/code-execution-with-mcp",
        ],
        "kind": "prose",
        # Engineering talk-recap of MCP code-execution; not a planted restatement
        # of the MCP announcement blog.
        "note": "Anthropic engineering recap of the MCP code-execution talk/design.",
    },
    {
        "id": "tr-codex-talk",
        "source_class": "transcript",
        "subject": "openai-codex",
        "role": "independent-talk",
        "urls": [
            "https://every.to/podcast/transcript-how-openai-s-codex-team-uses-their-coding-agent",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0140/fixtures/tr-codex-talk-everyto.md"
        ),
        "fallback_url": (
            "https://every.to/podcast/transcript-how-openai-s-codex-team-uses-their-coding-agent"
        ),
        "kind": "prose",
    },
    {
        "id": "tr-cursor-talk",
        "source_class": "transcript",
        "subject": "cursor-cloud-agent",
        "role": "spec-walkthrough-talk",
        "urls": [
            "https://cursor.com/docs/cloud-agent/api/endpoints",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/cursor-cloud-api.txt"
        ),
        "fallback_url": "https://cursor.com/docs/cloud-agent/api/endpoints",
        "kind": "prose",
        "speech_wrap": True,
        "note": (
            "No public conference transcript for Cursor Cloud Agent was reachable. "
            "This item is a speech-wrapped walkthrough of the fetched API-endpoints "
            "doc (a different URL than the official-docs overview)."
        ),
    },
    {
        "id": "tr-copilot-talk",
        "source_class": "transcript",
        "subject": "copilot-workspace",
        "role": "spec-walkthrough-talk",
        "urls": [
            "https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/github-cloud-agent-api.html"
        ),
        "fallback_url": (
            "https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api"
        ),
        "kind": "prose",
        "speech_wrap": True,
        "note": (
            "No public Copilot Workspace conference transcript was reachable. "
            "This item is a speech-wrapped walkthrough of the Cloud Agent API "
            "how-to (different URL than the user-manual official-docs item)."
        ),
    },
    {
        "id": "tr-replit-talk",
        "source_class": "transcript",
        "subject": "replit-agent",
        "role": "spec-walkthrough-talk",
        "urls": [
            "https://docs.replit.com/features/agent/overview",
        ],
        "local_fallback": (
            "command-center/p2-wave/probes/RES-0032/captures/replit-agent.html"
        ),
        "fallback_url": "https://docs.replit.com/features/agent/overview",
        "kind": "prose",
        "speech_wrap": True,
        "note": (
            "No public Replit Agent conference transcript was reachable. "
            "This item is a speech-wrapped walkthrough of the agent overview "
            "HTML (different URL than the llms.txt official-docs item)."
        ),
    },
    {
        "id": "tr-restatement-skills",
        "source_class": "transcript",
        "subject": "agent-skills",
        "role": "restatement-control",
        "companion_blog_id": "blog-skills",
        "derived": True,
        "kind": "prose",
        "note": "Planted talk that restates the Agent Skills engineering blog.",
    },
    {
        "id": "tr-restatement-copilot",
        "source_class": "transcript",
        "subject": "copilot-workspace",
        "role": "restatement-control",
        "companion_blog_id": "blog-copilot",
        "derived": True,
        "kind": "prose",
        "note": "Planted talk that restates the Copilot Workspace announcement blog.",
    },
]


def item_by_id(iid: str) -> dict:
    for it in ITEMS:
        if it["id"] == iid:
            return it
    raise KeyError(iid)


def capture_path(iid: str) -> Path:
    return CAPTURES / f"{iid}.bin"


def assert_inventory() -> None:
    if len(ITEMS) != 20:
        raise RuntimeError(f"sample size {len(ITEMS)} != 20")
    ids = [it["id"] for it in ITEMS]
    if len(set(ids)) != 20:
        raise RuntimeError("duplicate item ids")
    by_class = {c: 0 for c in CLASSES}
    restatements = []
    for it in ITEMS:
        by_class[it["source_class"]] += 1
        if it.get("role") == "restatement-control":
            restatements.append(it["id"])
    if by_class["official-docs"] != 6 or by_class["blog-post"] != 6:
        raise RuntimeError(f"class counts {by_class}")
    if by_class["transcript"] != 8:
        raise RuntimeError(f"transcript count {by_class['transcript']}")
    if len(restatements) != 2:
        raise RuntimeError(f"restatement count {restatements}")
    for subj in SUBJECTS:
        have = {it["source_class"] for it in ITEMS if it["subject"] == subj}
        if set(CLASSES) - have:
            raise RuntimeError(f"subject {subj} missing classes {set(CLASSES) - have}")
