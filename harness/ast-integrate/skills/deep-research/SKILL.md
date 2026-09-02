---
name: deep-research
description: Multi-source deep research with a routing + caching + grading harness over firecrawl, exa, tavily, perplexity, scholarly-access, tooluniverse, huggingface, and context7 MCPs. Routes each sub-question to the best live provider, caches provider calls by query hash, grades every source by confidence, and delivers cited reports. Use when the user wants thorough, evidence-backed research.
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

**Wrong lane?** `research-ops` is the thin router over this stack: it escalates *here* for
anything needing multiple sources, citations, or confidence grading, and routes elsewhere for a
single quick fact (the `exa` MCP) or research-before-*coding* (`search-first`). This skill is the
synthesis engine that router points at -- the full loop and output format live here, not there.

## MCP Requirements

At least one search provider. The harness routes across whichever of these are
live (see Preflight):

- **firecrawl** — `firecrawl_search`, `firecrawl_scrape`, `firecrawl_research_search_github` (primary web)
- **exa** (plugin `mcp__plugin_exa_exa__*`) — `web_search_exa`, `web_fetch_exa` (neural/semantic)
- **tavily** — `tavily_search`, `tavily_extract` (web/news fallback)
- **perplexity** (cookie/session-auth web MCP, `jacob-bd/perplexity-web-mcp`) — `pplx_smart_query`, `pplx_ask`, `pplx_deep_research`, `pplx_council` (synthesized **cited** answers via the user's Pro/Max plan; drives the `synthesis` capability + high-priority web corroboration). Uses the `__Secure-next-auth.session-token` cookie supplied to the server as `PERPLEXITY_SESSION_TOKEN` — no paid API key. Gray-area/ToS-adjacent (like the IG/FB cookie MCPs); session can rate-limit/expire (~30d) and preflight routes around it when down.
- **scholarly-access** — `paper_resolve`, `paper_fetch_metadata`, `paper_summarize` (OA academic)
- **tooluniverse** — `find_tools`, `execute_tool` (bio/pharma, 1264-tool library)
- **huggingface** — `paper_search` (ML/arXiv papers)
- **context7** — `resolve-library-id`, `query-docs` (library/API docs)
- **searxng** (key-free self-hosted metasearch, `mcp-searxng`, `SEARXNG_URL` env) — `searxng_web_search` (no API key, no quota; high-priority **key-free** web corroborator and the `longtail` primary)
- **cve-mcp** (key-free local MCP, NVD/CIRCL/OSV/CISA-KEV/ExploitDB) — `cve_lookup`, `cve_search`, `cve_kev_list` (the `vuln` capability for CVE/exploit/CVSS/KEV questions)

Parked (`~/.mcp.disabled.json`): `scrapegraph`, `apify` — the harness routes
around them. Never call `mcp__sci-hub__*`; avoid `paper_find_oa_pdf` per the
standing regression note. Both are hard-excluded by the router. No dark-web /
onion provider is routed to; any `.onion` source that reaches grading is
force-flagged UNVERIFIED regardless of corroboration.

## Workflow

### Step 1: Understand the Goal

Ask 1-2 quick clarifying questions:
- "What's your goal — learning, making a decision, or writing something?"
- "Any specific angle or depth you want?"

If the user says "just research it" — skip ahead with reasonable defaults.

### Step 2: Plan the Research

Break the topic into 3-5 research sub-questions. Example:
- Topic: "Impact of AI on healthcare"
  - What are the main AI applications in healthcare today?
  - What clinical outcomes have been measured?
  - What are the regulatory challenges?
  - What companies are leading this space?
  - What's the market size and growth trajectory?

### Step 2.5: Preflight (which providers are live)

Before dispatch, probe each routable provider once (a cheap tools-list or
minimal call) and mark it live / down / quota-exhausted. Route only to live
providers; record any that were down for the Methodology section. Preflight is
READ-ONLY and never disturbs the live GUI IDA MCP on `:13337`. See
`research_harness.preflight`.

### Step 3: Execute Multi-Source Search (harness-routed)

For EACH sub-question, classify its capability and dispatch to the highest-ranked
live provider for that capability (see the Routing Table below). For high-stakes
sub-questions, query the **top-2** providers (different indexes) so the grader
can cross-corroborate. Wrap every provider call in the **query-hash cache** so an
identical sub-question across runs is a hit, not re-burned quota.

**Search strategy:**
- Use 2-3 different keyword variations per sub-question
- Aim for 15-30 unique sources total
- Prioritize per the source tiers (academic/official > reputable news > forums)

### Step 4: Deep-Read Key Sources

For the most promising URLs, fetch full content with the `deep_read` capability
(firecrawl `firecrawl_scrape` -> exa `web_fetch_exa` -> tavily `tavily_extract`).
Read 3-5 key sources in full; do not rely only on search snippets. Keep raw
payloads sandboxed to disk (the cache stores them); only the derived finding
enters the conversation.

### Step 5: Synthesize and Write Report (graded + cited)

Grade every source, then assemble the report with the cited-report renderer
(`research_harness.report.render`). Template:

```markdown
# [Topic]: Research Report
*Generated: [date] | Sources: [N] | Providers: [firecrawl, scholarly-access, ...] | Confidence: [High/Medium/Low]*
*Cache: [H hits / M misses] | Stale-allowed: [yes/no]*

## Executive Summary
[3-5 sentence overview]

## 1. [First Major Theme]
- Claim [1] `[A.corrob x2.2026]`
- Claim [2] `[C.single.2024 - UNVERIFIED]`

## Key Takeaways
- [Actionable insight]

## Sources
1. [Title](url) - tier A - provider (year)
2. ...

## Methodology
Sub-questions investigated, providers routed-to, cache hit/miss counts,
and providers that were DOWN at preflight.
```

The header `Confidence` is **derived** from the distribution of claim tiers, not
hand-waved. The Methodology section honestly lists routed providers, cache
hit/miss, and any provider down at preflight.

### Step 6: Deliver

- **Short topics**: Post the full report in chat
- **Long reports**: Post the executive summary + key takeaways, save full report to a file

### Step 7: Persist to durable memory (basic-memory bridge)

Every cited report is a durable research artifact — write it to the
`basic-memory` MCP vault so it survives context compaction and is
semantically recallable later, instead of being re-researched from scratch.

After delivering, call `mcp__basic-memory__write_note` with:

- **title**: `research <topic> <YYYY-MM-DD>`
- **folder**: `research` (keeps the report findable via the same prefix)
- **tags**: `research-report`, the confidence tier, and the providers routed-to
- **content**: the full cited report (the `report.render` output) — the
  graded claims `[tier.corroboration.year]` and the `## Sources` list are the
  load-bearing part to preserve, so recall returns the evidence, not just prose.

This is a documentation convention, not harness code: the harness renders the
report; the agent is responsible for the `write_note` push. On a later related
question, **recall first** (`mcp__basic-memory__search_notes` /
`build_context` for `research <topic>`) before re-running the harness — a cache
hit at the memory layer beats any provider round-trip. Skip the write only if
`basic-memory` is unavailable or stalls (never block delivery on it).

## Research Harness (M-16)

A thin, stateless orchestration layer (no new MCP server, no daemon) shipped as a
Python package at `references/research_harness/`. Four components plus preflight:

### 1. Capability to provider routing (`routing.py`)

A **data-driven** table maps a capability (not a tool name) to an ordered list of
providers (primary first), with a source-tier prior for grading:

| Capability | Ordered providers (primary first) |
|---|---|
| `web` | firecrawl.firecrawl_search -> perplexity.pplx_smart_query -> searxng.searxng_web_search -> exa.web_search_exa -> tavily.tavily_search |
| `synthesis` | perplexity.pplx_smart_query -> exa.web_search_exa -> firecrawl.firecrawl_search |
| `neural` | exa.web_search_exa -> firecrawl.firecrawl_search |
| `academic` | scholarly-access.paper_resolve -> huggingface.paper_search |
| `bio` | tooluniverse.find_tools -> scholarly-access.paper_resolve |
| `code` | exa.web_search_exa -> firecrawl.firecrawl_research_search_github -> context7.query-docs |
| `library_docs` | context7.query-docs -> exa.web_search_exa |
| `deep_read` | firecrawl.firecrawl_scrape -> exa.web_fetch_exa -> tavily.tavily_extract |
| `vuln` | cve-mcp.cve_lookup -> cve-mcp.cve_search -> cve-mcp.cve_kev_list |
| `longtail` | searxng.searxng_web_search -> exa.web_search_exa |

`classify_capability(subquestion)` is a cheap, conservative keyword classifier
(keywords like cve/cvss/exploit/kev/0-day/rce -> vuln; paper/study/doi -> academic;
gene/protein/drug -> bio; repo/github -> code; api docs/sdk -> library_docs;
obscure/long-tail/rarely-documented -> longtail; explain/compare/consensus ->
synthesis; else web). The security-specific `vuln` rule runs first; domain rules
win over synthesis phrasing (synthesis is the last rule); raw link/extraction
stays on firecrawl/exa while synthesized **cited** answers route to Perplexity.
The key-free additions: **searxng** (self-hosted metasearch) is the high-priority
key-free corroborator on `web` and the `longtail` primary; **cve-mcp** drives
`vuln`. `resolve_providers(capability, live_servers, top_n)` returns ordered live
providers; Sci-Hub, the regressed `paper_find_oa_pdf`, and parked servers are
hard-excluded.

### 2. Query-hash cache (`cache.py`)

SHA-256 of a normalized `{capability, provider, query, params}` envelope keys each
`{hash}.json` entry (a direct application of `content-hash-cache-pattern` with one
extension: **TTL**). Default cache dir `~/.research-harness/cache`. Per-capability
TTL: web/news ~24h, code/docs ~7d, academic/bio ~30d. Corruption or expiry == miss.
`fetch_with_cache(...)` is the service-layer wrapper; pass `cache_enabled=False`
(the `--no-cache` escape hatch) for "must be current" runs.

### 3. Source-confidence grading (`grading.py`)

`confidence(claim) = f(source_tier, corroboration_count, recency)`, fully
deterministic. Source tier = best of a domain-authority prior (.gov/.edu/doi.org
plus the security authorities nvd.nist.gov/cisa.gov/first.org/osv.dev/exploit-db.com
-> A; wikipedia/github/major-news -> B; else C) and the routing provider prior
(scholarly-access/context7/tooluniverse/**cve-mcp** -> A; firecrawl/exa/tavily/
huggingface/**searxng** -> B). A single source is flagged UNVERIFIED; >=2
independent sources are corroborated; within ~12 months boosts recency. A
dark-web / `.onion` source is **force-flagged UNVERIFIED and capped at Low**
regardless of corroboration (`is_dark_web`). Each source gets a provenance tag
like `[A.corrob x2.2026]`; the report header confidence is derived from the grade
distribution.

### 4. Cited-report output (`report.py`)

`render(Report(...))` assembles findings into markdown with inline **numbered**
citations (`[1]`), a tiered references section, per-claim provenance tags, and a
Methodology section reporting routed providers + cache hit/miss + providers down
at preflight.

### Preflight (`preflight.py`)

`run_preflight(probe, servers)` probes each routable server (probe injected,
read-only) and returns live/down/quota statuses; `live_servers(...)` feeds the
router. `harness.plan_research(subquestions, statuses, top_n)` is the pure glue
that ties preflight + routing into a research plan.

### Using the package

```python
import sys
sys.path.insert(0, "references")  # or install the package
from research_harness import (
    run_preflight, plan_research, fetch_with_cache,
    Source, grade_source, build_citations, render,
)

statuses = run_preflight(my_probe)              # which MCPs are live
plan = plan_research(subquestions, statuses)    # route each sub-question
# ... for each decision, call the live provider through fetch_with_cache(...)
# ... grade each Source with grade_source(...), then render(Report(...))
```

Run the tests: `cd references && python -m pytest -q` (pure logic, fake provider
responses, no live network).

## Parallel Research with Subagents

For broad topics, use Claude Code's Task tool to parallelize:

```
Launch 3 research agents in parallel:
1. Agent 1: Research sub-questions 1-2
2. Agent 2: Research sub-questions 3-4
3. Agent 3: Research sub-question 5 + cross-cutting themes
```

Each agent searches, reads sources, and returns findings. The main session
synthesizes into the final report. Pass the routing table + grading rubric into
each agent's prompt so grades stay consistent.

## Quality Rules

1. **Every claim needs a source.** No unsourced assertions.
2. **Cross-reference.** If only one source says it, the grader flags it UNVERIFIED.
3. **Recency matters.** Prefer sources from the last 12 months; the grader boosts them.
4. **Acknowledge gaps.** The Methodology section lists providers that were down.
5. **No hallucination.** If you don't know, say "insufficient data found."
6. **Separate fact from inference.** Label estimates, projections, and opinions clearly.

## Examples

```
"Research the current state of nuclear fusion energy"
"Deep dive into Rust vs Go for backend services in 2026"
"Research the best strategies for bootstrapping a SaaS business"
"What's happening with the US housing market right now?"
"Investigate the competitive landscape for AI code editors"
```
