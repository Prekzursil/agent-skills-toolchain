# Lens 14: native-capability + monitoring audit
Source: subagent bc-148e974b-f9f3-5b2d-b578-09f8bc6cfd47, dispatched 2026-09-02 from cloud run bc-2a7f9bf8-4a9a-4193-a2c3-4f80d21392f9; completion notification was lost, report recovered from the transcript on 2026-09-02.
Status: raw lens report — findings, not decisions. Decisions live in ../2026-09-02-search-research-tools-gemhunt.md.

# Gem-hunt lens report: under-used native features + web monitoring for the search stack

**Scope honoured:** web/vendor-docs/GitHub research only; no files modified.
**Dedup baseline (verified against `tools/mcp/search-hub/caches/*.json` + `providers.py`):** the hub already *exposes* far more than the harness *calls*. Exa is launched via `mcp-remote https://mcp.exa.ai/mcp?tools=` with 14 tools (`web_search_advanced_exa`, `deep_researcher_*`, `agent_*`, `get_code_context_exa`, `crawling_exa`…); `firecrawl-mcp@latest` exposes 27 tools including `firecrawl_monitor_*` (8 tools), `firecrawl_research_*` (5 tools), `firecrawl_extract`, `firecrawl_agent`; `mcp-searxng@1.8.0` exposes `searxng_instance_info` besides search. Nothing below requires a new provider unless flagged **[NEW DAEMON]** / **[NEW MCP]**.
**Already built, do not rebuild:** cross-provider RRF exists at `tools/search-expansion/rank_fusion.py`; SearXNG's own cross-engine score merge is server-side; regional-engine enablement via managed `settings.yml` block exists at `tools/search-expansion/searxng_config.py` (the same pattern applies to science engines, find #2).

## Ranked summary

| # | Find | Tier | Value×Effort | Verdict |
|---|------|------|--------------|---------|
| 1 | Firecrawl Monitors (`firecrawl_monitor_create` — web-scale standing queries + page/site diffs, Firecrawl-hosted scheduler) | ENABLE-now, zero new tool | H×L | **ENABLE** |
| 2 | SearXNG keyless academic lane (`categories=science` / `engines=arxiv,google scholar,pubmed,semantic scholar,openalex,crossref`) | ENABLE-now | H×L | **ENABLE** |
| 3 | Exa `web_search_advanced_exa` freshness/category/summary knobs (`maxAgeHours`, `category`, `enableSummary`, `subpages`…) | ENABLE-now | H×L | **ENABLE** |
| 4 | Firecrawl schema-driven JSON (`firecrawl_scrape formats:[{type:"json"}]`, `firecrawl_extract`) + `firecrawl_search sources:news`/`tbs` | ENABLE-now | H×L | **ENABLE** |
| 5 | Firecrawl academic tools (`firecrawl_research_search_papers` et al.) | ENABLE-now | M/H×L | **ENABLE** |
| 6 | Tavily `topic=news|finance`, `time_range`, `search_depth=advanced`, `include_raw_content`, `exact_match`, `DEFAULT_PARAMETERS` | ENABLE-now (topic via env default) | M×L | **ENABLE** (partial) |
| 7 | Firecrawl on-demand `changeTracking` format (git-diff/json, `tag`) — diff-vs-last-scrape without a scheduler | ENABLE-now | M×L | **ENABLE** |
| 8 | Exa async agents `agent_create_run` (`outputSchema`, `effort`, `dataSources`, `input.exclusion`, `previousRunId`) | ENABLE-now (credits) | M×L | **ENABLE selectively** |
| 9 | SearXNG `format=rss` standing queries (+ RSSHub for RSS-less sites) | config flag + tiny poller | M×L (RSSHub: L×M) | **ENABLE** rss; **SKIP** RSSHub |
| 10 | Exa Websets Monitors + Webhooks | **[NEW MCP]** + REST; optional **[NEW DAEMON]** | M×M | **DEFER** |
| 11 | changedetection.io self-host | **[NEW DAEMON]** (180–280 MB; +~2 GB with Chrome) | M×M | **SKIP for now** |
| 12 | Kagi (Search/Extract API, MCP, FastGPT) | new paid key; no monitoring product | L/M×L | **SKIP** for monitoring; optional premium lane later |

---

## 1. Firecrawl Monitors — standing queries with Firecrawl as the scheduler

- **Capability:** `firecrawl_monitor_create` / `_list` / `_get` / `_update` / `_delete` / `_run` / `_checks` / `_check` — all present in `caches/firecrawl.json` (lines 1864–2082).
- **What:** Three target types. `search` (entire-web monitor): give `queries` (1–12) + `goal`; each check re-runs the searches, dedupes by canonical URL, and an AI judge scores *new* results against the goal. `scrape` (page list) and `crawl` (whole site) diff each page vs. the last retained snapshot and report `same|new|changed|removed|error`. Schedule: cron or natural-language text, **minimum 5 minutes**; `retentionDays` 30 (max 365); 1–50 targets per monitor. Notifications: webhook (`monitor.page`, `monitor.check.completed`), **email**, Slack.
- **Why THIS user:** This is exactly lens (b) — "so we don't re-search" — with **zero new daemon**: Firecrawl hosts the scheduler, the diff store, and the judge. Email/Slack delivery means no webhook receiver is required either; the harness can also just poll `firecrawl_monitor_checks`. MCP-first: it's already in the MCP the hub launches. Anti-overfit: works for any topic, not just this repo's.
- **How to enable (exact params):** simple path `{"queries":["\"Llama 4\" launch OR release"], "goal":"…2–3 sentences…", "searchWindow":"24h", "maxResults":10, "includeDomains":[…], "scheduleText":"every 6 hours", "email":"…", "webhookUrl":"…"}`; page path `{"pages":[…], "goal":"…"}`; advanced `body` for `{type:"crawl", url, crawlOptions:{limit,maxDiscoveryDepth}}` or JSON-mode `scrapeOptions.formats:[{type:"changeTracking", modes:["json"], schema, prompt}]` (per-field diff keyed like `plans[0].price` + `snapshot.json`). Tool description gives query/goal tuning rules ("queries control recall, goal controls precision"; keep `site:` out, use `includeDomains`).
- **Cost (vendor):** no per-monitor fee. Scrape monitor 1 credit/URL/check; crawl 1 credit/discovered page/check; web monitor **2 credits per 10 results per check** + 1 credit per judged result; meaningful-change +1 credit per changed page judged. Create response returns `estimatedCreditsPerMonth`. The hub's Firecrawl cooldown/exhaustion classifier already handles credit depletion.
- **Sources:** https://docs.firecrawl.dev/features/monitoring · https://docs.firecrawl.dev/features/monitoring-web-scale · https://docs.firecrawl.dev/features/monitoring-website · https://docs.firecrawl.dev/api-reference/endpoint/monitor-create · https://www.firecrawl.dev/blog/firecrawl-monitoring-launch
- **Value×Effort:** H×L. **Novelty:** high (feature is recent; nothing in the harness references `monitor`). **ENABLE.** **Confidence:** high — MCP schema in local cache + vendor docs agree on fields and pricing.

## 2. SearXNG keyless academic lane via `categories`/`engines`

- **Capability:** `searxng_web_search` already accepts `categories` (comma-separated) and `engines` (comma-separated), plus `time_range`, `language`, `safesearch`, `min_score`, `num_results`, `pageno`; `searxng_instance_info` returns the live `/config` categories/engines so the harness can verify before routing.
- **What:** SearXNG's `science` category (bang `!science`, sub-group `!scientific_publications`) ships arxiv (`!arx`), crossref (`!cr`), google scholar (`!gos`), openalex (`!oa`), pubmed (`!pub`), semantic scholar (`!se`), plus `!wikispecies`, `!pdbe`, `!openairepublications`. Results are merged/score-fused server-side across engines, so "RRF across engines" is already native inside SearXNG.
- **Why THIS user:** A **free, keyless** academic retrieval lane that never hits paid-key cooldowns; the hub's `keyless=True` SearXNG spec means it's always available as the fallback tier. Also the natural complement to `scholarly-access-mcp`. Anti-overfit: pure param routing.
- **How to enable:** `searxng_web_search(query, categories="science")` or explicit `engines="arxiv,google scholar,pubmed,semantic scholar,openalex,crossref"`; call `searxng_instance_info` once to confirm which are enabled on `127.0.0.1:8890`; if any are disabled, enable them via the existing managed-block pattern in `tools/search-expansion/searxng_config.py` (which already does this for regional engines — measured basis 2026-07-24). Caveat: several science engines do not honour `time_range` (check the "Time range" column in the configured-engines table), so date-filter at the harness for those.
- **Sources:** https://docs.searxng.org/user/configured_engines.html · https://docs.searxng.org/dev/search_api.html · local `caches/searxng.json`
- **Value×Effort:** H×L. **Novelty:** medium (known engines, unrouted). **ENABLE.** **Confidence:** high.

## 3. Exa `web_search_advanced_exa` — freshness, category, and on-search summarisation

- **Capability:** Already in `_EXA_TOOLS` (providers.py) and the cache (lines 66–235); current harness uses only `web_search_exa`/`web_fetch_exa`.
- **What:** `maxAgeHours` (0 = always live-fetch; this *is* the livecrawl control — the cache marks `livecrawl` deprecated and Exa's search reference documents `maxAgeHours`), `livecrawlTimeout`, `category` ∈ {company, research paper, news, pdf, github, personal site, people, financial report}, `startPublishedDate`/`endPublishedDate`/`startCrawlDate`/`endCrawlDate`, `includeDomains`/`excludeDomains`, `includeText`/`excludeText`, `additionalQueries` (query expansion server-side), `enableSummary`+`summaryQuery` (per-result LLM summary focused on your question), `enableHighlights`+`highlightsQuery`+`highlightsMaxCharacters`, `subpages` (1–10) + `subpageTarget`, `userLocation`, `moderation`.
- **Why THIS user:** One call replaces search→fetch→summarise chains (fewer credits, fewer round-trips); `category:"research paper"` + date filters gives a second academic lane; `subpages`/`subpageTarget` fetches docs/pricing/changelog sub-pages in the same request. Note the MCP `type` enum is only `auto|fast|instant` — Exa's `deep`, `deep-lite`, `deep-reasoning` search types are REST-only, so don't plan on them via MCP.
- **How to enable:** route "fresh/news" capability → `{"query", "maxAgeHours":0, "category":"news", "startPublishedDate":"2026-08-01"}`; route "paper" → `{"category":"research paper", "enableSummary":true, "summaryQuery":"…"}`.
- **Sources:** https://exa.ai/docs/reference/search (maxAgeHours, category, type) · local `caches/exa.json`
- **Value×Effort:** H×L. **Novelty:** medium. **ENABLE.** **Confidence:** high.

## 4. Firecrawl schema-driven structured output + search `sources`/`tbs`

- **Capability:** `firecrawl_scrape` with `formats:[{"type":"json","schema":{…},"prompt":"…"}]` (also `summary`, `branding`, `links`, `changeTracking`); `firecrawl_extract` (multi-`urls`, `prompt`, `schema`, `enableWebSearch`, `allowExternalLinks`, `includeSubdomains`); `firecrawl_search` with `sources:[{type:"news"}|{type:"images"}]`, `tbs` (time-based search, e.g. `qdr:w`), `location`, `filter`, inline `scrapeOptions.formats`. All in cache; harness currently uses scrape/search/crawl in markdown mode.
- **What:** LLM extraction into a JSON schema at scrape time, so the harness receives typed fields instead of markdown to re-parse; `firecrawl_extract` fans out across URLs and can web-search for missing fields.
- **Why THIS user:** Eliminates the harness's own post-extraction LLM pass for structured facts (pricing tables, release notes, author lists). `sources:news` + `tbs` is a second "fresh news" lane alongside Exa `category:news` and Tavily `topic:news` — good for RRF triangulation with existing `rank_fusion.py`.
- **How to enable:** `firecrawl_scrape({"url", "formats":[{"type":"json","schema":{…}}], "onlyMainContent":true})`; `firecrawl_search({"query", "sources":[{"type":"news"}], "tbs":"qdr:w", "limit":10})`. Also call `firecrawl_search_feedback` with the returned `id` — the first feedback per search refunds 1 credit (per the tool description).
- **Sources:** https://docs.firecrawl.dev/features/extract · https://docs.firecrawl.dev/features/search · local `caches/firecrawl.json`
- **Value×Effort:** H×L. **Novelty:** medium. **ENABLE.** **Confidence:** high (schema in cache; extract/search vendor pages).

## 5. Firecrawl academic tools (`firecrawl_research_*`)

- **Capability:** `firecrawl_research_search_papers` (semantic/HyDE search over arXiv abstracts; `k` up to 500, default 40; filters `authors`, `categories` e.g. `cs.LG`, `from`/`to` dates), `firecrawl_research_inspect_paper` (accepts `arxiv:`, `pmid:`, `pmcid:`, `doi:` ids), `firecrawl_research_related_papers`, `firecrawl_research_read_paper`, `firecrawl_research_search_github`. Present in cache lines 2082–2273; not referenced anywhere in the harness.
- **Why THIS user:** A second academic lane on a key the hub already rotates; the tool guidance ("run SEVERAL distinct framings … recall improves markedly") matches the harness's query-plan expansion. Pairs with #2 (keyless) for cross-lane RRF.
- **How to enable:** route capability `academic_search` → `firecrawl_research_search_papers({"query", "k":100, "from":"2025-01-01", "categories":["cs.CL"]})` → `inspect_paper` for metadata → `read_paper` for full text.
- **Sources:** local `caches/firecrawl.json` (primary evidence); https://github.com/firecrawl/firecrawl-mcp-server
- **Value×Effort:** M/H×L. **Novelty:** high. **ENABLE.** **Confidence:** medium-high — tool schemas are verified locally; I did not find a dedicated vendor docs page for the `research_*` surface, so treat pricing/coverage as unverified until probed.

## 6. Tavily `topic=news|finance`, `time_range`, depth and raw content

- **Capability:** `tavily_search` exposes `search_depth` ∈ {basic, advanced, fast, ultra-fast}, `time_range` ∈ {day, week, month, year}, `start_date`/`end_date`, `include_raw_content`, `include_domains`/`exclude_domains`, `country` (full country name, topic=general only), `exact_match`, `max_results` (5–20). `tavily_extract` has `extract_depth:"advanced"`; `tavily_research` has `model:"pro"` for broad multi-subtopic tasks (rate limit 20/min).
- **The catch:** the MCP schema enum for `topic` is `["general"]` only, while Tavily's REST API supports `general|news|finance`. The `tavily-mcp` README documents a `DEFAULT_PARAMETERS` env var (local) / header (remote) that injects defaults into every `tavily-search` call — so `topic` can be set at the provider level. The hub already injects env per rotation for `tavily-mcp@latest`, so adding `DEFAULT_PARAMETERS` to that spec's `env_defaults` is a config change, not a new tool. Also not forwarded by the MCP: `include_answer`, `chunks_per_source`, `auto_parameters`, `days` — REST-only.
- **Why THIS user:** `time_range` + `search_depth:"advanced"` + `include_raw_content:true` turns one Tavily call into search+extract, saving the separate `tavily_extract` round-trip for top hits; a news-tuned Tavily agent is a third fresh-news lane.
- **How to enable:** per-call `{"query", "search_depth":"advanced", "time_range":"week", "include_raw_content":true, "exact_match":true}`; provider-level `DEFAULT_PARAMETERS='{"topic":"news","search_depth":"advanced"}'` if a news-only Tavily spec is wanted (a separate ProviderSpec sharing the same key, since it's global to the process).
- **Sources:** https://docs.tavily.com/documentation/api-reference/endpoint/search · https://github.com/tavily-ai/tavily-mcp (README "Default Parameters Configuration") · local `caches/tavily.json`
- **Value×Effort:** M×L. **Novelty:** medium. **ENABLE (partial):** depth/time_range/raw_content now; `topic=news` via `DEFAULT_PARAMETERS` only. **Confidence:** high for REST params and env var; medium on whether a per-call `topic:"news"` passes MCP enum validation (the server handler forwards it, but strict clients may reject before send).

## 7. Firecrawl on-demand `changeTracking` (no scheduler)

- **Capability:** `firecrawl_scrape` `formats` enum includes `changeTracking`; vendor docs: `{"type":"changeTracking","modes":["git-diff","json"],"schema":{…},"prompt":"…","tag":"…"}` returns `changeStatus` (new/same/changed/removed), `previousScrapeAt`, a unified diff, and/or per-field JSON diffs against the *last scrape of that URL on your account*; `tag` keeps separate histories.
- **Why THIS user:** The harness already re-scrapes sources on each research run; adding this format makes each re-scrape return "what changed since last time" for free-ish, so unchanged pages can be skipped without a daemon or schedule. Complements #1 (Firecrawl-scheduled) for pages you only check when a run happens anyway.
- **How to enable:** `firecrawl_scrape({"url", "formats":["markdown", {"type":"changeTracking","modes":["git-diff"]}]})`; use `tag` per research thread.
- **Sources:** https://docs.firecrawl.dev/features/change-tracking · local `caches/firecrawl.json`
- **Value×Effort:** M×L. **Novelty:** medium. **ENABLE.** **Confidence:** high.

## 8. Exa async agents (`agent_create_run` family)

- **Capability:** `agent_create_run` (`query`, `systemPrompt`, `outputSchema`, `effort` ∈ low/medium/high/xhigh/auto, `dataSources` = Exa Connect providers fiber_ai, financial_datasets, similar_web, baselayer, affiliate, particle_news, jinko; `input.data` rows to enrich; `input.exclusion` rows to *not* return again; `previousRunId` to continue), `agent_wait_for_run`, `agent_get_run_output`, `agent_cancel_run`. Note the cache marks `deep_researcher_start/check` **[Deprecated]** in favour of agents.
- **Why THIS user:** `input.exclusion` + `previousRunId` is a daemon-free "standing query" idiom: re-run weekly with last week's results excluded and get only new items in your `outputSchema`. `dataSources: particle_news/financial_datasets` are paid vertical feeds the harness can't otherwise reach. Anti-overfit: generic list-building/enrichment.
- **How to enable:** `agent_create_run({"query":"…", "outputSchema":{…bounded arrays with source fields…}, "effort":"medium", "input":{"exclusion":[…prior rows…]}})` → `agent_wait_for_run` → `agent_get_run_output`.
- **Sources:** https://exa.ai/docs/reference/research/create-a-task (research/agent surface) · local `caches/exa.json` lines 497–680
- **Value×Effort:** M×L (credits scale with `effort`). **Novelty:** medium-high. **ENABLE selectively** (deep-synthesis and enrichment tasks; keep `tavily_research`/`firecrawl_agent` as alternates). **Confidence:** high on schema; medium on cost predictability.

## 9. SearXNG RSS output as a zero-cost standing query (RSSHub: skip)

- **Capability:** SearXNG `/search` accepts `format=rss` (also `json`, `csv`) when `search.formats` in `settings.yml` includes `rss`; every query + `categories` + `time_range` combination becomes a feed URL, e.g. `http://127.0.0.1:8890/search?q=…&categories=science&time_range=week&format=rss`.
- **Why THIS user:** Standing queries on the keyless lane with **no vendor credits**; consumption is any RSS poller or a cron'd `curl` + dedup by `<link>` — so it's a *scheduled task*, not a resident service, if the owner already runs a scheduler. Flag: a proper reader (Miniflux/FreshRSS) would be **[NEW DAEMON]**; not required.
- **RSSHub:** self-host is `docker run -d -p 1200:1200 diygod/rsshub` (`:chromium-bundled` tag for puppeteer routes; Redis optional; Cloudflare Workers deploy needs the paid plan). Only worth it for a specific RSS-less source; otherwise **[NEW DAEMON]** with low marginal value here.
- **How to enable:** add `rss` to `search: formats:` in the SearXNG `settings.yml`, restart the container (the existing `searxng_regional.py` already owns write+restart+health-check for that file).
- **Sources:** https://docs.searxng.org/dev/search_api.html · https://docs.searxng.org/admin/settings/settings_search.html · https://docs.rsshub.app/deploy/
- **Value×Effort:** M×L (RSSHub L×M). **Novelty:** low-medium. **ENABLE** rss format; **SKIP** RSSHub. **Confidence:** high.

## 10. Exa Websets Monitors + Webhooks — [NEW MCP] + REST, optional [NEW DAEMON]

- **Capability:** Websets = async entity collections (search → per-item criteria verification → enrichments). Monitors: `POST https://api.exa.ai/websets/v0/monitors` with `websetId`, `cadence.cron` (5-field; **triggers at most once per day**), `cadence.timezone`, `behavior.type:"search"` (find new items) or refresh. Webhooks: `POST /webhooks` with `events` such as `webset.item.created`, `webset.item.enriched`, `webset.idle`, `monitor.run.completed`; secret returned once for signature verification.
- **Reality check for MCP-first:** the Exa MCP the hub launches (`mcp.exa.ai/mcp?tools=`) does **not** expose websets. Exa's separate `exa-labs/websets-mcp-server` exposes `create_webset`, `create_search`, `create_enrichment`, `create_webhook`, etc., but its README states monitors "are not currently surfaced as MCP tools … configure via the Websets API or websets.exa.ai". So: **[NEW MCP]** for websets/webhooks, REST for monitors, and receiving webhooks needs an HTTP endpoint **[NEW DAEMON]** — or skip webhooks and poll `GET /monitors/{id}/runs` + `GET /websets/{id}/items` from the harness.
- **Why THIS user:** Strong only for entity list-building (companies/people/papers matching criteria, kept fresh daily). For topic monitoring, #1 already does it in-MCP with 5-minute granularity and an AI judge; Websets' once-per-day cron is coarser.
- **Sources:** https://exa.ai/docs/websets/api-guide-for-coding-agents · https://exa.ai/docs/websets/api/monitors/create-a-monitor · https://docs.exa.ai/websets/api/webhooks · https://github.com/exa-labs/websets-mcp-server
- **Value×Effort:** M×M. **Novelty:** medium. **DEFER** (enable only if an entity-tracking need appears). **Confidence:** high.

## 11. changedetection.io self-host — [NEW DAEMON]

- **Capability:** Docker `ghcr.io/dgtlmoon/changedetection.io` (port 5000, SQLite datastore); optional `dgtlmoon/sockpuppetbrowser` sidecar via `PLAYWRIGHT_DRIVER_URL=ws://browser-sockpuppet-chrome:3000` for JS pages, screenshots, visual selector, browser steps; notifications via Apprise (80+ targets); REST API; `EXTRA_PACKAGES` plugin install; `FETCH_WORKERS`, `MINIMUM_SECONDS_RECHECK_TIME`; LLM restock/price features (`LLM_FEATURES_DISABLED` to turn off). No official MCP.
- **RAM (the question asked):** core container ~180–280 MB (runs in a 512 MB limit for plaintext fetching); the Chrome sidecar is the cost — plan ~2 GB and `shm_size: 2g`, one Chrome per concurrent check, tune `MAX_CONCURRENT_CHROME_PROCESSES` (default 10), mount `--user-data-dir` on tmpfs. Dashboard ships without auth — put it behind the reverse proxy with a password.
- **Why THIS user / verdict:** Wins only for (a) JS-rendered or login-gated pages Firecrawl won't scrape, (b) zero-credit high-frequency polling, or (c) pixel/visual diffing. Otherwise #1 + #7 deliver semantic "meaningful change" detection with no new process. **SKIP for now**; revisit if Firecrawl credits become the binding constraint.
- **Sources:** https://github.com/dgtlmoon/changedetection.io (docker-compose.yml) · https://dgtlmoon-changedetection-io.mintlify.app/browser/playwright · https://github.com/dgtlmoon/sockpuppetbrowser
- **Value×Effort:** M×M. **Novelty:** low. **SKIP (defer).** **Confidence:** high on setup/RAM; the RAM figures for the core come from maintainer statements relayed by third-party guides, not an official requirements page (the project publishes none).

## 12. Kagi — no monitoring product; optional premium lane later

- **Capability:** Search API v1 (GA, pay-per-use **$12/1k requests**; lenses, country/language, personalised domain ranking, "extra snippets"), Extract API ($4/1k pages, up to 10 URLs/request, Markdown/JSON), Enrichment API (Teclis web / TinyGem news indexes), FastGPT, Universal Summarizer ("not yet available in v1"), free Small Web RSS feed. Official Kagi MCP server supports **Search + Extract only**.
- **Why THIS user:** Nothing here does alerting/standing queries, so it does not serve lens (b). As a search lane it's a paid 5th provider — the hub's `ProviderSpec` pattern (key env, usage URL, exhaustion classifier) can absorb it with a small spec, but it adds a new key and cost with overlapping coverage.
- **Sources:** https://help.kagi.com/kagi/api/overview.html · https://help.kagi.com/kagi/api/search.html · https://kagi.com/api/pricing
- **Value×Effort:** L/M×L. **Novelty:** low. **SKIP** for monitoring; optional later as a premium/private-index lane. **Confidence:** high.

---

### Negative findings (dedup / don't chase)
- **Tavily change-tracking/monitoring:** no such product in Tavily's API docs; Tavily's freshness lever is `time_range`/`start_date`/`topic=news`. Do not build a Tavily-based monitor.
- **Exa livecrawl:** deprecated in favour of `maxAgeHours` (already exposed, find #3).
- **Exa `deep_researcher_*`:** marked deprecated in the MCP cache; use `agent_create_run` (#8) or REST research tasks.
- **RRF across engines/providers:** SearXNG merges engines server-side; the repo already has `rank_fusion.py` for cross-provider RRF.

### Suggested enablement order (all zero-new-tool unless noted)
1) #1 Firecrawl monitors for the 3–5 evergreen research topics (email delivery, no receiver); 2) #2 + #5 academic lanes wired into the capability router with RRF; 3) #3/#4/#6 param upgrades in the router's provider adapters; 4) #7 `changeTracking` on every re-scrape; 5) #9 `rss` format flag; 6) revisit #10/#11 only if a concrete entity-tracking or JS-page need appears.