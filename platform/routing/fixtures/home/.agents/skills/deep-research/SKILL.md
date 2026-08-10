---
name: deep-research
description: Multi-source deep research with a routing + caching + grading harness over firecrawl, exa, tavily, perplexity, scholarly-access, tooluniverse, huggingface, and context7 MCPs. Routes each sub-question to the best live provider, caches provider calls by query hash, grades every source by confidence, and delivers cited reports with numbered citations. Use when the user wants thorough, evidence-backed research on any topic.
---

# Deep Research

> **Drift-prone skill.** Firecrawl/Exa/Tavily MCP tool names, quotas, and
> result shapes change. Verify the configured MCP tools and current API docs
> before promising coverage or quoting live source counts. The routing table in
> `references/research_harness/routing.py` is the single choke-point to update,
> and the preflight step catches name/availability drift at runtime.

Produce thorough, cited research reports from multiple sources. The base
workflow (understand to plan to search to deep-read to synthesize to deliver)
is unchanged; the **Research Harness (M-16)** below slots routing, caching,
source-confidence grading, a cited-report renderer, and a provider preflight
into that spine.

> This skill is vendored from the ECC `deep-research` skill and extended with
> the M-16 harness. The base ECC copy is left untouched.

## When to Activate

- User asks to research any topic in depth
- Competitive analysis, technology evaluation, or market sizing
- Due diligence on companies, investors, or technologies
- Any question requiring synthesis from multiple sources
- User says "research", "deep dive", "investigate", or "what's the current state of"

## MCP Requirements

At least one search provider. The harness routes across whichever of these are
live (see Preflight):

- **firecrawl** — `firecrawl_search`, `firecrawl_scrape`, `firecrawl_research_search_github` (primary web)
- **exa** (plugin `mcp__plugin_exa_exa__*`) — `web_search_exa`, `web_fetch_exa` (neural/semantic)

### Workflow
### Step 1: Understand the Goal
### Step 2: Plan the Research
### Step 2.5: Preflight (which providers are live)
### Step 3: Execute Multi-Source Search (harness-routed)
### Step 4: Deep-Read Key Sources
### Step 5: Synthesize and Write Report (graded + cited)
### [Topic]: Research Report
### Executive Summary
### 1. [First Major Theme]
### Key Takeaways
