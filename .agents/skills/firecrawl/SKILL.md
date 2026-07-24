---
name: firecrawl
description: Web scraping, crawling, structured extraction, site mapping, and change monitoring via the Firecrawl MCP. Use to turn URLs into clean markdown or schema-structured JSON, extract brand identity (colors, fonts, spacing), crawl or map sites, parse local PDFs/Office files, search the web with operators, or monitor pages for changes. Pairs with the Exa MCP (Exa finds by meaning, Firecrawl fetches).
metadata:
  origin: custom
---

# Firecrawl

The web-data layer: scrape, crawl, map, structured-extract, search, monitor, and autonomously browse the web via the Firecrawl MCP server (`mcp__firecrawl__firecrawl_*`). Where Exa *finds* pages by meaning, Firecrawl *fetches and structures* them — turning any URL (or a whole site) into clean markdown, schema-typed JSON, screenshots, or brand tokens.

## When to Activate

- Scrape a known page into clean markdown, or pull specific data points as JSON
- Crawl or map a whole site (docs, blog, competitor) for comprehensive coverage
- Harvest documentation/cookbooks (like building this skill) into readable text
- Extract structured data (prices, specs, features, contacts) across many URLs
- Capture screenshots or **brand identity** (colors, fonts, spacing, UI components) for design research
- Search the web with operators/domain filters and get full page content, not just snippets
- Monitor a page or a search for meaningful changes over time
- Find academic papers (arXiv) or GitHub issues/PRs for research
- Parse a local PDF / Word / Excel file into markdown or structured JSON
- User says "scrape", "crawl", "extract from", "map the site", "monitor", or "get the data from this page"

## Firecrawl vs Exa — when to use which

The user has **both**. They are complementary, not redundant:

| Job | Reach for | Why |
|-----|-----------|-----|
| Discover pages by meaning, "find sites like X", semantic recall | **Exa** (`web_search_exa`) | Neural/embedding search; best when you don't know the URL |
| Code examples / API usage | **Exa** (`get_code_context_exa`) | Curated code-context index |
| Keyword/operator/domain-filtered web search **with full content** | **Firecrawl** (`firecrawl_search`) | Google-style operators + inline scrape; the MCP's default web search |
| Turn a known/discovered URL into clean content | **Firecrawl** (`firecrawl_scrape`) | Reliable markdown/HTML/screenshot extraction |
| Structured data with a schema, across many pages or a domain | **Firecrawl** (`firecrawl_extract`) | LLM extraction + crawl + wildcards |
| Whole-site crawl / site-map / change monitoring / browser actions | **Firecrawl** | Exa has no crawl/map/monitor/interact |
| Deep multi-step research report | **either, or both** | Exa has a managed deep-research agent; Firecrawl has `firecrawl_agent` + a paper/GitHub research index. The `deep-research` skill routes both. |

Rule of thumb: **Exa to FIND, Firecrawl to FETCH/EXTRACT/CRAWL/MONITOR.** Discover with Exa's neural recall, then hand the URLs to Firecrawl for depth and structure. For a known site, go straight to Firecrawl.

## MCP Requirement

Firecrawl MCP is already connected in this workspace (`mcp__firecrawl__*`). To reproduce elsewhere, add to `~/.claude.json`:

```json
"firecrawl": {
  "command": "npx",
  "args": ["-y", "firecrawl-mcp"],
  "env": { "FIRECRAWL_API_KEY": "fc-YOUR_KEY_HERE" }
}
```

Get a key at [firecrawl.dev](https://www.firecrawl.dev). A self-hosted instance is supported via `FIRECRAWL_API_URL`. Tool names below drop the `mcp__firecrawl__` prefix for brevity.

## Tool Routing (decision table)

| You need | Tool | Notes |
|----------|------|-------|
| One known URL → content | `firecrawl_scrape` | Fastest, most reliable; default for single pages |
| **Specific data points** from a page | `firecrawl_scrape` + `json` format + schema | NOT markdown — schema gives clean fields |
| Many related pages on one site | `firecrawl_crawl` | Bound `limit` + `maxDiscoveryDepth` or it overflows tokens |
| Just **discover** URLs / find the right page | `firecrawl_map` | Cheap (1 credit); use `search=` to locate a page |
| Structured data across many URLs / a domain | `firecrawl_extract` | Supports `urls: ["site.com/*"]` wildcards |
| Open-ended web question, unknown site | `firecrawl_search` | Operators + `sources` (web/news/images) + content |
| URLs unknown, multi-source, JS-heavy SPA | `firecrawl_agent` (+ `_status`) | Async — poll patiently (2-5 min) |
| Click / fill / login / navigate a SPA | `firecrawl_interact` (+ `_stop`) | Live browser session |
| Local PDF / Word / Excel → markdown/JSON | `firecrawl_parse` | Local files only (not remote URLs) |
| Watch a page or search for changes | `firecrawl_monitor_create` (+ list/get/run/check) | Recurring diff with a meaningful-change judge |
| arXiv papers / GitHub research | `firecrawl_research_*` | search_papers, read_paper, related_papers, search_github |

**Order of escalation when a page is hard:** `scrape` → add `waitFor` for SPAs → `map` (search=) to find the real URL → `scrape` again → `agent` only as a last resort. Map+scrape is cheaper and faster than the agent.

## Core Tools

### firecrawl_scrape
Single-URL extraction — the workhorse. Default to this for any single page.

```
firecrawl_scrape(url: "https://docs.example.com/api", formats: ["markdown"], onlyMainContent: true)
```

| Param | Notes |
|-------|-------|
| `formats` | `markdown`, `html`, `rawHtml`, `links`, `summary`, `screenshot`, `json`, `branding`, `changeTracking`, `query` |
| `onlyMainContent` | Strip nav/footer/boilerplate (default-on behavior) |
| `waitFor` | ms to wait for JS render (5000-10000 for SPAs) |
| `actions` | Array of browser steps: `click`, `write`, `press`, `scroll`, `screenshot`, `executeJavascript`, `wait`, `generatePDF` |
| `jsonOptions` | `{ prompt, schema }` for the `json` format (structured extraction) |
| `queryOptions` | `{ prompt, mode: directQuote|freeform }` for the `query` format (ask the page a question) |
| `proxy` | `basic` / `stealth` / `enhanced` / `auto` — `stealth` for anti-bot sites |
| `parsers` | `["pdf"]` to parse remote PDFs; `pdfOptions.maxPages` to cap |
| `maxAge` | Serve from cache if newer than this (ms) — cuts credits + latency |
| `location` | `{ country, languages }` for geo-specific content |
| `mobile`, `includeTags`, `excludeTags`, `removeBase64Images`, `redactPII`, `storeInCache` | Misc controls |

### firecrawl_crawl
Multi-page crawl; polls internally to a terminal state and returns the data + crawl id.

```
firecrawl_crawl(url: "https://example.com/blog/*", maxDiscoveryDepth: 2, limit: 25, sitemap: "include", deduplicateSimilarURLs: true)
```

Key params: `limit`, `maxDiscoveryDepth`, `includePaths` / `excludePaths`, `sitemap` (`skip`/`include`/`only`), `allowExternalLinks`, `allowSubdomains`, `crawlEntireDomain`, `delay`, `maxConcurrency`, `prompt` (natural-language crawl target), `scrapeOptions` (full scrape-format set per page), `webhook`. Re-check a long job later with `firecrawl_check_crawl_status(id)`. **Warning:** crawl output can blow token limits — keep `limit`/`maxDiscoveryDepth` modest, or prefer `map` + targeted `scrape`.

### firecrawl_map
Discover every indexed URL on a site, fast and cheap (1 credit).

```
firecrawl_map(url: "https://docs.example.com", search: "webhook events")
```

`search=` ranks URLs by topic — the fastest way to locate the right page before scraping. Use **before** crawl or agent.

### firecrawl_extract
LLM-powered structured extraction from one or many URLs (or a whole domain via `/*`).

```
firecrawl_extract(
  urls: ["https://example.com/pricing"],
  prompt: "Extract each plan name, monthly price, and included credits",
  schema: { type: "object", properties: { plans: { type: "array", items: {
    type: "object", properties: { name: {type:"string"}, price:{type:"number"}, credits:{type:"number"} } } } } }
)
```

`enableWebSearch: true` enriches from linked/related pages; `includeSubdomains`, `allowExternalLinks` widen scope. Backed by the FIRE-1 agent for navigation. Async-capable (job id + poll; results held ~24h). Metered by tokens (1 credit = 15 tokens), so scope it.

### firecrawl_search
Web search **with full content** — the MCP's primary search tool.

```
firecrawl_search(query: "site:firecrawl.dev change tracking", limit: 5, sources: [{type:"web"}])
```

Operators: `""` exact, `-` exclude, `site:`, `inurl:`, `intitle:`, `related:`, `imagesize:`, `larger:`. `sources` = web / news / images. `includeDomains` / `excludeDomains` (don't use both), `tbs` time filter, `location`, `scrapeOptions` to pull content inline. **Tip:** after using results, call `firecrawl_search_feedback(id)` — it improves quality and refunds 1 credit.

### firecrawl_agent / firecrawl_agent_status
Autonomous async research agent (FIRE-1) that searches, follows links, and extracts — when you don't know the URLs or the data is scattered / behind JS.

```
firecrawl_agent(prompt: "Find the founders and total funding of <company>", schema: {...})  → returns job id
firecrawl_agent_status(id: "...")  → poll every 15-30s; be patient (2-5 min, sometimes 5+)
```

Only stop polling on `completed` or `failed`. Prefer `map`+`scrape` first — the agent is the expensive last resort.

### firecrawl_research_* (paper / GitHub index)
A research-grade index for scientific and engineering questions:
- `firecrawl_research_search_papers` — semantic (HyDE) arXiv search by topic; filter by `authors`, `categories` (e.g. `cs.LG`), date `from`/`to`. Run several framings for recall.
- `firecrawl_research_read_paper` — pull full-text passages answering a specific question (verify a paper before deep-reading).
- `firecrawl_research_related_papers` — expand from a seed: `similar` / `citers` / `references`.
- `firecrawl_research_inspect_paper` — full metadata + source ids.
- `firecrawl_research_search_github` — issues, PRs, discussions, repo docs for implementation/engineering detail.

Complements `scholarly-access`, `paper-search`, and Exa for literature work.

### firecrawl_parse
Parse a **local** file (`.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, `.xls`, `.html`) into markdown / JSON / summary. Same JSON-schema rule as scrape. (In hosted-cloud mode it's a two-call upload-then-parse flow.) For remote files, use `firecrawl_scrape` with `parsers: ["pdf"]`.

### firecrawl_interact / firecrawl_interact_stop
Drive a live browser session for click / fill / login / multi-step navigation that scrape's `actions` can't express. Billed per browser minute — stop the session when done.

### firecrawl_monitor_* (change tracking on a schedule)
Recurring scrape/crawl/search that diffs each run against the last snapshot and judges whether the change is **meaningful**.

```
firecrawl_monitor_create(
  pages: ["https://competitor.com/pricing"],
  goal: "Alert me when plan prices or included credits change",
  scheduleText: "every 6 hours", email: "you@example.com")
```

- Page mode: `page` / `pages`. Search mode: `queries` (1-12) + `searchWindow` — alerts on new/changed hits.
- `goal` (plain English) drives the meaningful-change judge (`judgeEnabled` defaults on when `goal` is set); webhooks expose `isMeaningful` + `judgment`.
- Manage with `firecrawl_monitor_list` / `_get` / `_update` / `_delete` / `_run` (fire now) / `_check` / `_checks`.

## Powerful Formats (pass in `formats`)

- **`json`** — structured extraction with a schema. **Use this, not markdown, whenever the user wants specific fields/values.** Pair with `jsonOptions: { prompt, schema }`.
- **`branding`** — extract a site's brand identity: colors, fonts, typography, spacing, UI components. Ideal for **design research / style replication / design-system seeding**.
- **`screenshot`** — full-page image (`screenshotOptions.fullPage`, viewport, quality) for visual reference or UI audits.
- **`changeTracking`** — diff vs the last scrape; `modes: ["git-diff"]` (line diff, no extra cost) or `["json"]` (schema'd field changes, +5 credits/page). Returns `changeStatus` (new/same/changed/removed), `previousScrapeAt`, `visibility`, and the diff/json. Requires `markdown` also in `formats`. Use a `tag` to keep separate histories per URL.
- **`summary`** — a condensed page summary (cheap way to triage long pages).
- **`query`** — ask a natural-language question against the page (`directQuote` for verbatim, `freeform` otherwise).

## Workflows

### Doc / cookbook harvest (build a skill, learn an API)
`firecrawl_map(url, search="...")` to find the right pages → `firecrawl_scrape(formats:["markdown"], onlyMainContent:true)` each, or a bounded `firecrawl_crawl` for a whole section. This is exactly how this skill was built.

### Structured data across a site
`firecrawl_map` to enumerate → `firecrawl_extract(urls:["site.com/*"], schema)` for clean typed records (pricing, catalog, specs, contacts).

### Competitive / web audit
`firecrawl_crawl` the competitor (bounded) → `firecrawl_extract` features/pricing with a schema → `firecrawl_monitor_create` with a `goal` to get alerted on changes.

### Design research (fan-out)
For each competitor URL: `firecrawl_scrape(formats:["branding","screenshot"])` → collect color/font/spacing tokens + screenshots to seed a design system or critique. Combine with the `design-system` / `ui-audit` skills.

### Research
`firecrawl_search` (operators + domain filters) for the open web; `firecrawl_research_search_papers` + `_read_paper` for arXiv; `firecrawl_research_search_github` for engineering detail. For a full cited report, use the **`deep-research`** skill (it already routes Firecrawl as primary web + deep-read).

## Credits & Rate Limits

**Credit cost (1 credit ≈ 1 page for the basic ops):**

| Op | Cost |
|----|------|
| Scrape | 1 / page |
| Crawl | 1 / page |
| Map | 1 / call |
| Search | 2 / 10 results (then `search_feedback` refunds 1) |
| Extract | metered — 1 credit = 15 tokens |
| changeTracking `json` mode | +5 / page (git-diff is free) |
| Interact | 2 / browser-minute |
| Agent (FIRE-1) | 5 free runs/day, then dynamic |

**Monthly credit pools:** Free 1,000 · Hobby 5,000 (~$16/mo) · Standard 100,000 (~$83) · Growth 500,000 (~$333) · Scale/Enterprise 1M+.

**Rate limits (requests/min):**

| Plan | scrape | map | crawl | search | agent | concurrent browsers |
|------|--------|-----|-------|--------|-------|---------------------|
| Free | 10 | 10 | 1 | 5 | 10 | 2 |
| Hobby | 100 | 100 | 15 | 50 | 100 | 5 |
| Standard | 500 | 500 | 50 | 250 | 500 | 50 |
| Growth | 5,000 | 5,000 | 250 | 2,500 | 1,000 | 100 |

## Gotchas

- **Crawl token overflow** — crawl responses can be huge. Bound `limit` + `maxDiscoveryDepth`, or use `map` + targeted `scrape`. Don't use a bare `/*` on a large site.
- **JS / SPA returns empty** — add `waitFor: 5000-10000`; if still empty, `map(search=)` to find the real content URL, then scrape; agent only as last resort.
- **Specific data ≠ markdown** — if the user wants fields/values, use the `json` format with a schema. Markdown is for reading whole pages.
- **Agent is async** — it returns a job id; you must poll `firecrawl_agent_status` and wait (2-5+ min). Don't give up after a couple polls.
- **changeTracking needs `markdown`** in `formats` too, and `json` mode adds 5 credits/page.
- **Extract is LLM-metered** — large/many pages get expensive; scope `urls` and the schema.
- **Anti-bot sites** — escalate `proxy` to `stealth`/`enhanced` (higher cost) rather than retrying `basic`.
- **Search feedback** — call `firecrawl_search_feedback(id)` after `firecrawl_search` to refund 1 credit and improve quality.
- **Map ≠ crawl** — map only lists URLs (no content); crawl fetches content. Map first to scope.
- **Parse is local-only** — for a URL, use `scrape` with `parsers:["pdf"]`, not `parse`.

## Related Skills

- `exa` MCP (`web_search_exa` / `get_code_context_exa`) — neural/semantic search + code-context (the FIND half; Firecrawl is the FETCH half)
- `deep-research` — multi-source cited research harness that routes Firecrawl (web + deep-read) alongside Exa, Tavily, Perplexity, scholarly-access
- `design-system` / `ui-audit` — consume Firecrawl `branding` + `screenshot` output
- `scholarly-access` / `paper-search` — academic retrieval that complements `firecrawl_research_*`
