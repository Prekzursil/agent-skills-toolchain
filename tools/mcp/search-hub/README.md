# search-hub — rotating keyed search + a keyless SearXNG and self-hosted lane

`search-hub` fronts Exa, Tavily, Firecrawl, and SearXNG **stdio** search MCP
servers behind ONE MCP registration and keeps every tool under its ORIGINAL
name. Exa, Tavily, and Firecrawl get **transparent API-key rotation**. Keyless,
self-hosted SearXNG remains available as the last-resort search surface even
when every keyed provider is cooling after hard exhaustion.

The fallback is an always-eligible `searxng_web_search` tool, not automatic
cross-provider argument translation: callers choose it when keyed tools are
unavailable.

A third lane is **keyless, self-hosted search+extract** (`selfhosted_search` /
`selfhosted_extract`) — an **in-process HTTP adapter** (no child spawned) that
fronts a self-hosted TrailSearch daemon so the estate can stop depending on
Tavily. It reports a **capability lattice** and **degrades truthfully** (a down
daemon returns an `isError`, never a fabricated hit). See
[Self-hosted, key-free lane](#self-hosted-key-free-lane-selfhosted_) and the
decision record [`docs/plans/2026-09-02-search-stack-reunion.md`](../../../docs/plans/2026-09-02-search-stack-reunion.md).

It is modelled on the sibling `cloud-hub` lazy multiplexer, with one key
difference: search calls are routed **per-key** and forwarded **synchronously**
(the hub must inspect a child's response to tell "402 exhausted" from "429 rate
limit" before deciding whether to rotate).

---

## Architecture (the locked grill decisions)

- **SG-1 — lazy, per-key multiplexer.** `initialize` / `tools/list` are answered
  from committed per-provider caches (`caches/*.json`) with **zero** children
  spawned (the RAM + idle-cheap win). A `tools/call` is routed to the **active
  key's** child, which is spawned lazily and kept for the session. A backup key's
  child is spawned only when the primary is cooled — usually ~1 child/provider.
  SearXNG follows the same lazy child/cache pattern without a key binding.
- **SG-2 — reactive rotation.** No background probing. On a provider's
  **hard-exhaustion** error the hub rotates to the next non-cooled key and
  **retries the same call once**; if all keys are cooled, it returns the
  provider's native error unchanged. An **on-demand** `search_usage` tool reports
  remaining balance + cooldown state when you ask for it. SearXNG bypasses the
  key rotator entirely, so keyed cooldown state cannot make it unavailable.
- **SG-3 — paid keys, long cooldown.** On **true exhaustion** (HTTP 402) a key is
  cooled **until the billing period resets** (seconds to the next UTC month
  boundary, or a `SEARCH_HUB_EXHAUST_COOLDOWN_S` override). On a **429 rate
  limit** the key is **NOT** cooled — the native error (carrying `Retry-After`)
  is returned so the caller backs off. Rotation is for **paid / legitimate
  multi-key** setups, not for evading a single free tier.

Auto-rotation is transparent and per-invocation for the three keyed providers;
it **never** flips a global active pointer (which would yank concurrent calls).
Manual `*_account_switch` / `*_account_cycle` remain the only deliberate
active-key changes (and they un-cool the chosen key, so a manual choice wins over
an earlier auto-cooldown). SearXNG has no account tools or cooldown state.

---

## Providers (package + env verified live 2026-07; Exa + gated providers re-verified 2026-09-02)

| Provider  | prefix | stdio launch                         | credential / config env           | usage endpoint                              | exhaustion signal |
|-----------|--------|--------------------------------------|-----------------------------------|---------------------------------------------|-------------------|
| Exa       | `ex`   | `mcp-remote` → Exa HTTP MCP (`?tools=` 9-tool selector) | `EXA_API_KEY`      | **none** (no balance API) → error-driven    | HTTP 402 `NO_MORE_CREDITS` / `API_KEY_BUDGET_EXCEEDED` |
| Tavily    | `tv`   | `npx -y tavily-mcp@latest`           | `TAVILY_API_KEY`                  | `GET /usage` → `plan_limit - plan_usage` (+ paygo) | explicit quota, or 429 → **probe /usage** |
| Firecrawl | `fc`   | `npx -y firecrawl-mcp@latest`        | `FIRECRAWL_API_KEY`               | `GET /v2/team/credit-usage` → `data.remainingCredits` | HTTP 402 "Insufficient credits" |
| SearXNG   | `sx`   | `npx -y mcp-searxng@1.8.0`          | `SEARXNG_URL` (config, not a key) | **none**                                    | **none** — keyless, never cooled |

On Windows the launchers run through `cmd /c npx …` (npx is a `.cmd` shim).

### Exa tool selector (Lens 14 cleanup, re-probed live 2026-09-02)

`_EXA_TOOLS` no longer names `deep_researcher_start` / `deep_researcher_check` (the live
endpoint now serves both with a "[Deprecated]" description) nor the `agent_create_run` /
`agent_wait_for_run` / `agent_get_run_output` / `agent_cancel_run` quartet, which the
endpoint resolves to ONE tool, `agent_run` (the only agent tool Exa's docs list). The
selector is now **9 tools**: `web_search_exa`, `web_search_advanced_exa`, `web_fetch_exa`,
`company_research_exa`, `linkedin_search_exa`, `people_search_exa`,
`get_code_context_exa`, `crawling_exa`, `agent_run`. `caches/exa.json` was regenerated
through the hub's own `refresh_provider` path (Linux argv `npx -y mcp-remote
"https://mcp.exa.ai/mcp?tools=<_EXA_TOOLS>" --header 'x-api-key:${EXA_API_KEY}'` with the
`REFRESH_DUMMY` placeholder — `?tools=` demands *some* key even for `tools/list`; an
anonymous call is HTTP 401): server `exa-search-server 3.2.1`, 9 tools, byte-identical on a
second run the same day. `company_research_exa` / `people_search_exa` /
`linkedin_search_exa` are also flagged deprecated upstream ("use web_search_advanced_exa")
but still answer; they stay until a caller-facing removal is decided.
`test_exa_cache_matches_tool_selector` pins cache == selector.

### Gated providers (gem-hunt waves 2-3): `enabled_providers(environ)`

`default_providers()` still returns the historical four. The runtime (`python hub.py`),
`--print-plan` and a bare `--refresh` build from `providers.enabled_providers(environ)`,
which appends each gated spec its `ENABLE_<X>` flag allows: a **kill switch** (default ON;
only an explicit `0` / `false` / `no` / `off` removes it) for the keyless remotes, an
**opt-in** (default OFF; only an explicit truthy value wires it) for the trial / heavy
children. `--refresh <id>` looks names up in `all_providers()`, so an opt-in cache can be
(re)generated without switching the provider on. Every gated provider is **keyless like
SearXNG**: no key store, no `<prefix>_account_*` tools, no rotator, no classifier patterns —
an origin 429 / 403 / 5xx is relayed verbatim as `isError` and can never create cooldown
state (fail CLOSED; results are never fabricated). All caches below were captured live
2026-09-02 from the cloud VM (a datacenter IP) through `refresh_provider` (`initialize` +
`tools/list` over stdio; remotes bridged with `npx -y mcp-remote` 0.8.3, whose list matched a
direct Streamable-HTTP probe per tool) and re-captured byte-identical later the same day.

- **Parallel Search** (`parallel`, prefix `pl`) — remote Streamable HTTP
  `https://search.parallel.ai/mcp`, bridged `npx -y mcp-remote https://search.parallel.ai/mcp`;
  keyless; **0 MB idle** (a bridge child only while called); `ENABLE_PARALLEL=0` kills it.
  Verified 2026-09-02: server `Parallel Web Search MCP Server 1.27.0`, **2 tools**
  (`web_search`, `web_fetch`) → `caches/parallel.json`; a live keyless `web_search`
  `tools/call` returned ranked excerpts with `search_id` + `structuredContent`. Proprietary
  hosted service (no OSS license; keyless tier as Parallel offers it).
- **grep.app** (`grepapp`, prefix `ga`) — remote, MCP at the host ROOT `https://mcp.grep.app`
  (`/mcp` is a 404 "Invalid MCP endpoint"); keyless; 0 MB idle; `ENABLE_GREPAPP=0` kills it.
  Verified 2026-09-02: server `mcp-typescript server on vercel 0.1.0`, **1 tool**
  (`searchGitHub`) → `caches/grepapp.json`; a live `searchGitHub` call returned repository
  snippets (SSE reply, `server: Vercel`). **Cross-lens caveat:** Lens 6 got live snippets,
  Lens 7 got HTTP 429 "Vercel Security Checkpoint" from a datacenter IP; this VM (also a
  datacenter IP) got snippets. Either way the child's own error text is relayed as `isError`
  (`test_hub_relays_origin_429_checkpoint_as_truthful_error`): nothing is retried, rotated,
  cooled or faked. Proprietary hosted service.
- **corroborate-mcp** (`corroborate`, prefix `cb`) — **TRIAL**: 1 star, single maintainer
  (`chefcohen/corroborate-mcp`, MIT). Counts independent origins of a claim over Google
  News RSS + GDELT + Hacker News; keyless; 0 MB idle; **OPT-IN** `ENABLE_CORROBORATE=1`;
  pinned `npx -y corroborate-mcp@0.1.3` (npm has 0.1.0-0.1.3; the server self-reports
  `0.1.0`). Verified 2026-09-02: **2 tools** (`corroborate_claim`, `find_sources`) →
  `caches/corroborate.json`. Errors out when its engines are down, never a fake
  UNCORROBORATED.
- **open-webSearch** (`openwebsearch`, prefix `ow`) — `Aas-ee/open-webSearch`, **Apache-2.0**
  per the upstream repo LICENSE (the npm manifest declares no `license` field); keyless
  multi-engine scraper kept as the resilience fallback when SearXNG's parsers break; 0 MB
  idle; **OPT-IN** `ENABLE_OPENWEBSEARCH=1`; pinned `npx -y open-websearch@2.1.11` with the
  hub's `env_defaults` `MODE=stdio` (upstream default `both` also binds HTTP :3000) and
  `SEARCH_MODE=request` (upstream default `auto` may pick Playwright); an operator's own
  values win (`setdefault`). Verified 2026-09-02: server `web-search 1.2.0`, **6 tools**
  (`search`, `fetchLinuxDoArticle`, `fetchCsdnArticle`, `fetchGithubReadme`,
  `fetchWebContent`, `fetchJuejinArticle`) → `caches/openwebsearch.json`.
- **local-deep-research** (`ldr`, prefix `ld`) — `LearningCircuit/local-deep-research`, MIT;
  the Wave-3 heavy answer engine (resident 8-16 GB), so **ON-DEMAND ONLY**: **OPT-IN**
  `ENABLE_LDR=1`, never spawned or listed otherwise. Upstream ships `ldr-mcp`, a STDIO-only
  FastMCP console script of the `local-deep-research[mcp]` extra (engine in-process; no HTTP
  MCP endpoint exists upstream — `src/local_deep_research/mcp/`, `docs/mcp-server.md`), so
  the default launch is `uvx --from "local-deep-research[mcp]==1.10.7" ldr-mcp`. If `LDR_URL`
  is set the hub instead bridges `npx -y mcp-remote $LDR_URL` to a resident `ldr-mcp` the
  operator has fronted with a Streamable-HTTP gateway of their own (upstream's security
  note applies to that exposure). All `LDR_*` settings reach the child through the inherited
  environment. Verified 2026-09-02 (cold `uvx` install, `PROBE_TIMEOUT=1500`): **8 tools** in
  21.5 s (`quick_research`, `detailed_research`, `generate_report`, `analyze_documents`,
  `search`, `list_search_engines`, `list_strategies`, `get_configuration`) →
  `caches/ldr.json`. The cached `serverInfo.version` `1.29.1` is the `mcp` SDK version
  FastMCP reports, not LDR's (the pinned package is 1.10.7). With open-webSearch also on,
  LDR's `search` collides and is exposed as `ld_search`.

Flags at a glance (all non-secret): `ENABLE_PARALLEL` / `ENABLE_GREPAPP` (default on; `0` =
off), `ENABLE_CORROBORATE` / `ENABLE_OPENWEBSEARCH` / `ENABLE_LDR` (default off; `1` = on),
`LDR_URL` (optional; read only when LDR is on). `deploy/env.minimal.example` lists them.

### Error classifier (per provider)

The classifier is a pure function of the child's error text (`providers.classify`):

- **Exa** — hard-exhaust on `NO_MORE_CREDITS` / `API_KEY_BUDGET_EXCEEDED` / `402`
  / "insufficient credit" / "out of credits". A **429 is a pure rate limit**
  (never rotate — Exa has no balance API to confirm exhaustion).
- **Tavily** — hard-exhaust on an explicit quota message ("usage limit", "plan
  limit", "quota exceeded", `432`, `402`, …). A bare **429 is AMBIGUOUS**, so the
  rotator **probes `/usage`**: no headroom ⇒ treat as exhausted (rotate); headroom
  ⇒ treat as rate limit (return native, don't rotate).
- **Firecrawl** — hard-exhaust on `402` / "insufficient credits" / "upgrade your
  plan". A **429 is a rate limit** (return native + `Retry-After`, don't rotate).
- **SearXNG** — bypasses the rotator and has no exhaustion/rate classifier
  patterns. Calls go directly to its one keyless child, so even response text
  containing `402` / `429` never creates key cooldown state.
- **Gated keyless providers** (Parallel, grep.app, corroborate, open-webSearch,
  LDR) — exactly the SearXNG rule: no patterns, one direct keyless child, the
  child's own error relayed verbatim. None of them documents a billing
  exhaustion signature, so nothing was added to the classifier.

Order matters: a hard-exhaustion signature always wins over a rate signature when
a single message mentions both.

---

## Deploying SearXNG (the keyless fallback)

The three keyed providers are hosted APIs; **SearXNG is a service you run
yourself.** The hub's `mcp-searxng@1.8.0` child talks to a running SearXNG
instance at the URL in the **`SEARXNG_URL`** env var (default
**`http://127.0.0.1:8890`**) — nothing is bundled or started for you. Stand one
up before relying on the fallback:

```bash
# Local Docker on the default port (SearXNG serves on container port 8080):
docker run -d --name searxng -p 8890:8080 searxng/searxng
```

The `mcp-searxng` server needs SearXNG's **JSON API**, so add `json` to
`search.formats` in the instance's `settings.yml` (the stock config enables only
`html`). To use an instance hosted elsewhere, point `SEARXNG_URL` at any trusted
endpoint you control (e.g. `SEARXNG_URL=https://searxng.example.internal`).

Until a reachable instance answers at `SEARXNG_URL`, the keyed providers are
unaffected and `searxng_*` calls simply return the child's connection error — the
fallback is **safe-inert**, never a hard dependency.

---

## Self-hosted, key-free lane (`selfhosted_*`)

The keyless lane replaces Tavily (closed, cloud-only) with a backend you run
yourself. It is an **in-process HTTP adapter** (`adapters.py`) — it spawns **no**
child and adds **no** new import beyond `urllib` (already loaded), so it costs the
running hub ~0 RAM at rest. The heavy daemon it talks to is started **on demand**.

- **Tools:** `selfhosted_search` → `POST /tavily/search`, `selfhosted_extract` →
  `POST /tavily/extract`. Tavily-shaped args (`query`, `max_results`, `topic`,
  `include_answer`, …); names are prefixed `selfhosted_` so they never collide
  with the keyed `tavily_*` provider.
- **Backend:** TrailSearch (`jianjungki/tavily-open`, MIT) at `TRAILSEARCH_URL`
  (or `SELFHOSTED_SEARCH_URL`), default `http://127.0.0.1:8794`. The base URL is
  **config, not a secret**. Bring it up with the minimal profile in
  [`deploy/`](deploy/README.md).
- **Capability lattice (never fake a result):** every tool resolves to one of
  `native | probed | declared | emulated | absent`. `tools/list` and the default
  `search_usage` do **zero** network; `search_usage {"provider":"selfhosted",
  "probe":true}` does one health GET to upgrade to `probed`/`absent`. A
  `tools/call` always hits the backend and returns a truthful `isError` (no
  fabricated hits) when it is down — **safe-inert** like SearXNG.
- **Swappable backend:** the adapter is backend-agnostic. TrailSearch is `native`
  (its routes *are* the Tavily contract); a fastCRW / OrioSearch / Sicry subclass
  would be `emulated`, same interface and honesty contract.

---

## Opt-in lanes (default OFF)

Two extra lanes ship **disabled** and are gated by env flags. See the legal/safety
envelope: [`docs/legal/onions-lane-envelope.md`](../../../docs/legal/onions-lane-envelope.md).

- **Onion-index lane: Ahmia + VormWeb (default ON, ask-first; `ENABLE_ONIONS=0`
  kills it)** — **index-only** dark-web search via the **existing**
  `searxng_web_search` tool (not a new tool/service). Two clearnet **index**
  engines, both under SearXNG category `onion index` (never the Tor-gated
  `onions`): `ahmia` (`ahmia.fi`) and, since owner decision G-7, `vormweb`
  (`vormweb.de`, a SearXNG `xpath` engine we carry in
  `deploy/searxng-min/settings.yml` because upstream ships none). **How to ask
  for one engine:** `engines=ahmia` or `engines=vormweb` queries that index only;
  omit `engines` (or pass `categories="onion index"`) to query every enabled index
  (`ahmia,vormweb` by default). It **works by default but ASKS before searching**
  — the first onion call returns a confirmation request listing the `engines` it
  will query and the modes (`low|medium|high|deepest`, index breadth only); the
  caller re-invokes with `onion_confirm=true` + `onion_mode`. Confirmed results
  are prepended with a `TOR / DARK-WEB INDEX` banner naming the index(es) + an
  `_onion` marker (`lane: ahmia-index | vormweb-index | ahmia+vormweb-index`,
  `engines`, `verified:false`) so they are clearly distinct from normal web
  results. No Tor, no `.onion` fetch (`web_url_read` of any `.onion` is refused
  regardless, whichever index listed it); both engines are clearnet and fail
  closed. Ahmia's abuse blacklist is inherited; **VormWeb's filtering is its own
  self-declared policy and unverifiable, and its operator's consent is unresolved
  (no ToS/robots published)** — the owner accepted both caveats (G-7) and declined
  a hub-side blacklist guard, so treat VormWeb hits as exactly as unvetted as the
  envelope says. **Flags:** `ENABLE_ONIONS=0` = hard kill switch for the whole
  lane; `ENABLE_VORMWEB=0` = drop VormWeb from the default set and refuse an
  explicit `engines=vormweb` with a truthful message (unset = ON). **≈ 0 MB.** See
  the envelope doc; the xpath stanza needs a SearXNG restart to load.
- **OSSInsight repo-discovery (`ENABLE_OSSINSIGHT=0`)** — keyless GitHub repo
  discovery over the public OSSInsight API: `ossinsight_repo_stats`,
  `ossinsight_collections`, `ossinsight_collection_ranking`. In-process HTTP,
  **≈ 0 MB**, wired only when the flag is set. Degraded upstream rankings are relayed
  truthfully (their `data_quality` note passes through). Base URL: `OSSINSIGHT_URL`
  (default `https://api.ossinsight.io`). OSSInsight's ranking endpoints have been
  starved upstream since ~2025-10, so the **default-ON GitHub REST lane below** is
  the working repo-discovery surface; this lane stays as the opt-in sibling.

---

## Repo discovery (keyless, default ON): GitHub REST search (`github_*`)

The `github_*` tools are the repo-discovery lane that works today: keyless
requests to GitHub's **own** REST search API (`adapters.GitHubSearchAdapter`, a
sibling of `OSSInsightAdapter`). In-process stdlib `urllib`, **no child, no new
dependency, ≈ 0 MB at rest**, and no request until a tool is called.

- **Why default ON** (the OSSInsight sibling is default OFF): first-party public
  API, keyless, no cost, no third-party terms and no legal shadow. The flag
  **`ENABLE_GITHUB_SEARCH`** is therefore only a **kill switch** — unset/truthy =
  wired, an explicit falsey value (`0`/`false`/`no`/`off`) unwires all five tools.
- **Config, not a secret:** **`GITHUB_API_URL`** (default `https://api.github.com`)
  is the base URL, so tests point the adapter at a fake backend exactly like
  `TRAILSEARCH_URL` does for TrailSearch.
- **Optional token:** **`GITHUB_TOKEN`** (fallback **`GH_TOKEN`**) is sent as
  `Authorization: Bearer …` when set. It is read by env **name** only, never logged
  or echoed (any upstream echo is scrubbed), and surfaces solely as
  `authenticated: true|false`. It lifts the search pool from **10 → 30
  requests/min** and the core pool from **60 → 5000 requests/h**.
- **Tools** (each answers compact items + `rate_limit {limit, remaining,
  reset_epoch, resource}` + `authenticated`; GitHub's `total_count` and
  `incomplete_results` are relayed, never padded — a partial upstream set is
  flagged in `note`):
  - `github_repo_search(q, sort=stars|forks|help-wanted-issues|updated, order,
    per_page<=50, page)` — full GitHub search syntax in `q`; omit `sort` for
    best-match ranking. `GET /search/repositories`.
  - `github_new_and_hot(keyword="", days=30, language="", topic="", min_stars=0,
    per_page, page)` — composes `created:>YYYY-MM-DD` (+ `language:`, `topic:`,
    `stars:>=N`) with `sort=stars`: the "new & hot" ranking OSSInsight lost.
  - `github_popular_and_alive(keyword="", pushed_days=30, language="", topic="",
    min_stars=100, per_page, page)` — composes `pushed:>YYYY-MM-DD` + `stars:>=N`
    with `sort=stars`: popular **and** still moving.
  - `github_topic_search(q, per_page, page)` — `GET /search/topics` (no preview
    header needed); feed a topic name into `github_new_and_hot`'s `topic=`.
  - `github_repo_activity(owner, repo)` — `GET /repos/{o}/{r}/stats/commit_activity`
    (52 weekly totals, `total_commits`, `recent_4_weeks_commits`) +
    `/stats/participation` (`all` vs `owner`, 52 weeks). GitHub answers **HTTP 202
    with no body while it computes** fresh statistics: the tool pauses once
    (1.5 s), retries **once**, and otherwise reports `computing: true` truthfully
    (call again shortly) — never a busy loop, never a fabricated series.
- **Compact item shape:** `full_name, html_url, description, stargazers_count,
  forks_count, language, created_at, pushed_at, topics, license` (SPDX id); topic
  hits carry `name, display_name, short_description, created_by, released,
  created_at, updated_at, featured, curated`.
- **Honest limits (also in every tool description):** GitHub search exposes only
  the **first 1000 results** (`per_page * page <= 1000`), a query is at most **256
  characters / 5 `AND`/`OR`/`NOT` operators**, and there is **no star velocity**
  keyless — `/stargazers` is 401 and GraphQL is 403 without a token — so the
  rankings are a **snapshot, not a growth curve**. Arguments are validated
  **before** a request is spent, so a bad `sort`/`per_page`/over-long `q` never
  costs a rate-limited call.
- **Truthful degradation:** a **403/429 rate limit** returns an `isError` naming
  the pool, `remaining/limit`, the reset epoch, any `Retry-After`, and the remedy
  (set a token / wait); a **422** relays GitHub's validation message and fields; a
  **401** says the token was rejected (value never shown); an unreachable API is a
  transport error — **never an empty success**.
- **`search_usage {"provider":"github"}`** reports the lattice state plus
  `authenticated` and `self_hosted: false`; `"probe":true` does one
  `GET /rate_limit` (free — not counted against any pool) and reports the
  `search` / `core` headroom.
- **Tests:** `tests/test_github_search.py` against `tests/fake_github_backend.py`
  (canned JSON per route, a 202-then-200 stats pair, a 403 rate-limit response
  with `x-ratelimit-*` headers, a 422, a token run asserting the `Authorization`
  header reached the fake and never appears in any output, the kill switch, and
  one end-to-end call over a real loopback socket). No live network.

---

## Repo health (keyless, default ON): bestofjs v2, deps.dev, OpenSSF Scorecard

The `repohealth` lane (`lane_repo_health.py`, wired through `lanes.py`) answers
"is this project trending / alive / safe to depend on" from three **public,
keyless, read-only APIs**, all through the same `SelfHostedAdapter` mechanism as
`github_*`: in-process stdlib `urllib`, **no child, no new dependency, nothing at
import**, the capability lattice, truthful degradation. Three adapters share the
platform (`BestOfJSAdapter`, `DepsDevAdapter`, `ScorecardAdapter`; `service` =
`bestofjs` / `depsdev` / `scorecard` in `search_usage {"provider":"repohealth"}`).

- **Default ON, kill switch `ENABLE_REPO_HEALTH`:** unset/truthy = wired; an
  explicit falsey value (`0`/`false`/`no`/`off`) makes `build(environ)` return `[]`
  (not wired, not degraded). Base URLs are config, not secrets, so tests point
  every adapter at one loopback fake: **`BESTOFJS_API_URL`** (default
  `https://bestofjs-static-api-v2.vercel.app`), **`DEPSDEV_API_URL`** (default
  `https://api.deps.dev`), **`SCORECARD_API_URL`** (default
  `https://api.securityscorecards.dev`); **`BESTOFJS_TTL_S`** (default `21600` =
  6 h, `0` = refetch every call; anything but a non-negative integer is a build
  `ValueError` reported as `lane:lane_repo_health` degraded).
- **bestofjs v2 — one static file is the whole dataset.** `GET /projects.json`
  (1.44 MB, `{date, tags[], projects[]}`) is fetched **lazily on the first call**,
  never at import, and cached in-process for `BESTOFJS_TTL_S`; a refetch that
  fails leaves the old copy in place but the failing call is an error (stale
  data is never served as fresh). Every answer carries `dataset_fetched_at`,
  `dataset_date` (the dataset's own build time), `dataset_projects`,
  `dataset_source` and `cache {hit, age_s, ttl_s}` so staleness is visible.
  - `bestofjs_trending(period=weekly|daily|monthly|quarterly|yearly, tag="",
    limit<=50 (default 20))` — ranked by `trends.<period>` (stars gained over the
    window; ties by stars). Young projects simply lack the longer windows (live:
    `yearly` on 1,955 of 2,157), so they are **excluded and counted**
    (`excluded_without_trend`), never scored 0. `tag` accepts a tag code or its
    display name (`framework`, `"Node.js framework"`); an unknown tag is an error
    listing similar codes. Items: `rank, delta, name, full_name, description,
    stars, trends, tags, status, created_at, pushed_at, added_at,
    contributor_count, npm, downloads, url, repo_url, bestofjs_url`.
  - `bestofjs_project(query)` — case-insensitive exact match on `name`, then
    `full_name` (`owner/repo`; `github.com` URLs are normalised), then the
    bestofjs `slug`; otherwise the **top-5 substring candidates by stars**
    (`candidates_total` counts them all). bestofjs curates monorepo packages as
    separate projects sharing one `full_name` (live: 7 repos, e.g. TanStack Start
    + TanStack Router on `TanStack/router`), so the siblings of a match are
    listed in `same_repo_entries`, never dropped. A miss is an honest
    `match: null`, not an error: bestofjs is a **curated** list (~2,200 JS/TS
    projects), not a GitHub index.
  - **Trap (lens receipt):** the v1 host `bestofjs-static-api.vercel.app` still
    answers 200 but is **frozen at 2024-08-10** (2,005 projects). `build` and the
    adapter refuse it with a `ValueError` naming the v2 host; a test pins the
    default to `bestofjs-static-api-v2.vercel.app`.
- **deps.dev v3** (Google's public dependency graph; **no search endpoint** —
  `/v3/search` is a 404 and none is invented):
  - `depsdev_project(owner, repo)` — `GET /v3/projects/github.com%2F{owner}%2F{repo}`
    (the slashes **must** be percent-encoded exactly like that: the literal form
    is `404 page not found`). Returns `stars, forks, open_issues, license,
    description, homepage`, deps.dev's **periodic** Scorecard snapshot as
    `scorecard {overall_score, date, scorecard_version, commit, checks_count,
    checks[{name, score, reason}]}` or `null` when it holds none, and `oss_fuzz`.
    A 404 (`project not found`, text/plain) is a truthful error — deps.dev only
    knows repos linked from a package it indexes — never zeros.
  - `depsdev_package(system, name)` — `GET /v3/systems/{system}/packages/{name}`
    with `system` in `npm|pypi|cargo|go|maven|nuget|rubygems` (validated before
    any request) and `name` percent-encoded (`@types/node` → `%40types%2Fnode`,
    `github.com/gin-gonic/gin` → `github.com%2Fgin-gonic%2Fgin`,
    `com.google.guava:guava` → `com.google.guava%3Aguava`). Returns `package_key`
    (deps.dev's normalised key — `pypi/Flask` comes back as `flask`),
    `versions_count`, `default_version` (the registry's `isDefault`),
    `latest_published` (newest `publishedAt`, which may be a pre-release — the
    note says so when it differs from the default), `deprecated_count` and the
    10 most recent versions (`@types/node` has 2,359 live, so the tail is capped).
- **OpenSSF Scorecard** — `scorecard_project(owner, repo)` →
  `GET /projects/github.com/{owner}/{repo}` (slashes **literal** here; the
  encoded form is 404). Returns `score, date, commit, scorecard_version,
  checks_count, checks[{name, score, reason}]` relayed verbatim — a check score
  of `-1` (inconclusive) stays `-1`. The API only holds repos its weekly cron
  scanned: a **404 (empty body) is a truthful "not scanned" error, never a zero
  score**, carrying the local remedy `scorecard --repo=github.com/o/r`.
- **Truthful everywhere:** arguments are validated before a request is spent
  (owner/repo segments `[A-Za-z0-9._-]+`, no control characters, `limit` 1–50);
  every request has a timeout (30 s; probes 5 s); every success carries
  `fetched_at` (call time, UTC) and `source` (the exact URL); every failure is an
  `isError` naming the upstream HTTP status and body (`[search-hub:repohealth]
  …`); an unreachable API is "not reachable (…)". Probes: bestofjs = the dataset
  fetch itself (warms the cache; reports project count + dataset date), deps.dev
  = `GET /v3/systems/npm/packages/left-pad`, Scorecard = `GET /` (its Swagger UI).
- **Live-probe receipts (2026-09-02, read-only `curl`, not used by tests):**
  - `curl -sS -o /tmp/bj_v2.json -w '%{http_code} %{size_download}\n'
    https://bestofjs-static-api-v2.vercel.app/projects.json` → `200 1444851`;
    top-level keys `date, projects, tags`; `date: 2026-09-01T23:58:04.175Z`,
    **2,157 projects, 254 tags**; every project carries `name, slug, added_at,
    description, stars, full_name, owner_id, status, tags, trends,
    contributor_count, pushed_at, created_at`, plus `npm`/`downloads` (1,820),
    `url` (1,710), `logo` (279); `trends` keys present on `daily` 2157 / `weekly`
    2152 / `monthly` 2140 / `quarterly` 2109 / `yearly` 1955; tag keys `code,
    name, description, createdAt`.
  - `curl -sS https://bestofjs-static-api.vercel.app/projects.json` (v1) → 200,
    `date: 2024-08-10T21:30:55.705Z`, 2,005 projects — **frozen; refused**.
  - `curl -sS -w '%{http_code}' 'https://api.deps.dev/v3/projects/github.com%2Fpallets%2Fflask'`
    → 200; keys `projectKey{id}, openIssuesCount, starsCount, forksCount,
    license, description, homepage, scorecard{date, repository{name,commit},
    scorecard{version,commit}, checks[14]{name, documentation, score, reason,
    details}, overallScore, metadata}, ossFuzz{lineCount, lineCoverCount, date,
    configUrl}`. The unencoded `/v3/projects/github.com/pallets/flask` → 404
    `404 page not found`; an unknown repo → 404 text/plain `project not found`.
  - `curl -sS 'https://api.deps.dev/v3/systems/npm/packages/left-pad'` → 200,
    `packageKey{system: NPM, name}`, 15 `versions[]{versionKey{system,name,version},
    publishedAt, isDefault, isDeprecated, deprecatedReason}`;
    `%40types%2Fnode` → 200 (2,359 versions); `pypi/packages/Flask` → 200 with
    `packageKey.name: flask`; `cargo/packages/nope-zz-nope` → 404 `package not
    found`; `/v3/search?q=flask` → 404 `404 page not found`; `/` → 303.
  - `curl -sS -w '%{http_code}' https://api.securityscorecards.dev/projects/github.com/pallets/flask`
    → 200; keys `date, repo{name,commit}, scorecard{version,commit}, score,
    checks[14]{name, score, reason, details, documentation}`; `score: 7.1`,
    `date: 2026-08-24`. An unscanned repo → **404 with an empty body**; `/` →
    200 `text/html`; the encoded-slash form → 404.
- **Tests:** `tests/test_lane_repo_health.py` (104) against
  `tests/fake_repo_health_backend.py` (one path-keyed stdlib router serving all
  three APIs' shapes, plus the failure modes: a 503, a wrong-shaped 200, a
  non-JSON 200, text/plain 404s, 500s, the empty-body Scorecard 404): trending
  sort per period + tag filter + limit clamp, exact/ci/substring lookup, TTL hit
  vs expiry with an injected clock, the frozen-v1 trap, `%2F` encoding, invalid
  system refused, 404 mappings, kill switch, `lanes.build_lane` wiring, the hub
  surface, connection refused, and one end-to-end run over a real loopback
  socket. No live network.

---

## `read_url` — in-process fetch negotiating Cloudflare Markdown for Agents (default ON)

The hub had **no fetch path of its own**: `web_url_read` belongs to the downstream
`mcp-searxng` child (no boilerplate removal, cannot add request headers) and
`selfhosted_extract` fetches server-side inside TrailSearch. `read_url`
(`adapters.ReadUrlAdapter`) is the in-process fetch: stdlib `urllib`, no child,
**no required dependency**. Wave 1 shipped the honest v0 (markdown negotiation +
a stdlib tag-stripper); **Wave 2 upgraded it in place** — same name, same output
shape, additive fields only — with an **extractor ladder** whose middle rung is the
*optional* `trafilatura` / `rs-trafilatura` readability pass, quality signals, a
`page_type` hint, and the DNS re-resolution pin the v0 note promised.

- **Tool:** `read_url(url, max_bytes=2_000_000, timeout_s=20)` →
  `{url, final_url, status, redirects, title, author, date, content_type,
  extractor, quality, extractor_ladder, markdown | text, tokens?,
  extractor_confidence?, chars, page_type, link_density, boilerplate_removed,
  min_chars, bytes, truncated, note}`. Wave-1 fields are unchanged; `author`,
  `date`, `extractor_ladder`, `extractor_confidence`, `chars`, `page_type`,
  `link_density`, `boilerplate_removed` and `min_chars` are the Wave-2 additions.
- **Negotiation:** every request sends
  `Accept: text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.1` (the
  header Cloudflare's [Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/)
  documents).
- **The extractor ladder.** `extractor` names the rung that produced the text,
  `quality` follows from it, and `extractor_ladder` lists **every rung tried with
  the chosen one last** (`…-recall` marks a `favor_recall` retry), so a caller sees
  what happened rather than guessing:
  1. `extractor: "cloudflare-markdown"`, `quality: "high"` — the zone answered
     `Content-Type: text/markdown` **with** `x-markdown-tokens` / `x-original-tokens`
     (relayed as `tokens: {markdown, original}`); the body is Cloudflare's
     server-side clean markdown (YAML frontmatter + body). Only opted-in
     Pro/Business/Enterprise zones do this (Cloudflare's own docs and blog do —
     verified live 2026-09-02, see the smoke below) — the hit-rate across the web is
     unknown, which is exactly why the field exists. `extractor: "origin-markdown"`,
     `quality: "high"` — the origin itself served `text/markdown` (no Cloudflare
     token headers); passed through verbatim. Markdown never runs a readability
     pass: the ladder is `["cloudflare-markdown"]`.
  2. `extractor: "rs-trafilatura"` or `"trafilatura"` — **HTML only, optional.**
     When `rs_trafilatura` (the Rust build) is importable it is preferred and
     labelled `rs-trafilatura`; else `trafilatura`; else the rung is skipped
     (the ladder shows the skip: `["stdlib-text"]`). A **precision pass** first —
     `trafilatura.extract(html, url=final_url, output_format="markdown",
     include_links=False, include_tables=True, favor_recall=False)` (`txt` when the
     installed version has no markdown format; then the body key is `text`) —
     `quality: "high"` when the extract is **non-empty and ≥ `READ_URL_MIN_CHARS`
     chars (default 200)**. Otherwise **one** `favor_recall=True` retry, labelled
     `quality: "medium"` (ladder `["trafilatura", "trafilatura-recall"]`); a retry
     still below `min_chars` is kept only when it covers at least a quarter of the
     page's visible text (the page itself is short), otherwise the extractor
     evidently missed the content and the stdlib text is returned with the counts in
     the `note` (`"precision pass 0 chars, favor_recall pass 11 chars"`). An
     exception in the extractor falls through truthfully too (`"trafilatura raised
     RuntimeError: …"` in the note) — a broken optional install degrades the ladder,
     never breaks the tool. `title` / `author` / `date` come from the winner's
     metadata: `trafilatura.bare_extraction(html, url=…, fast=True,
     with_metadata=True)` (measured 6 ms on a 98 KB page) or rs-trafilatura's
     `ExtractResult` (which also carries `extraction_quality`, relayed as
     `extractor_confidence`). Extractor metadata is relayed as-is — its title
     heuristic (h1-first) can differ from `<title>`, which stays the fallback.
  3. `extractor: "stdlib-text"`, `quality: "low"` — the fallback, unchanged from
     v0. HTML goes through a stdlib `html.parser` tag-stripper that drops the
     `script/style/noscript/svg/template/nav/footer/aside/header` subtrees, keeps
     `<title>`, collapses whitespace, keeps paragraph breaks and decodes entities.
     **Tag-stripping is not readability** — boilerplate outside those subtrees
     survives, hence `low`. `text/plain`, JSON and XML pass through with whitespace
     collapsed (ladder `["stdlib-text"]`, no page signal). Binary content is
     refused, not "extracted".
- **Quality signals** on every result: `chars` (length of the returned body),
  `link_density` (share of the visible text inside `<a>`, 0 … 1; for markdown the
  share inside `[label](url)` labels), `boilerplate_removed` (`true` for rungs 1–2,
  `false` for `stdlib-text` — tag-stripping removes subtrees, not boilerplate) and
  `min_chars` (the threshold in force).
- **`page_type` is a heuristic hint, not a classifier:** `article | docs | listing |
  shell | other`, computed by stdlib from the tag-stripper's single pass — no
  visible text + scripts + a big body → `shell` (a JS app shell: nothing to read
  without a browser); ≥ 2 `<pre>` blocks, a docs-looking URL or many headings with
  code → `docs`; ≥ 8 links with link text ≥ 50 % of the visible text → `listing`;
  `<article>` or ≥ 3 paragraphs and ≥ 500 chars → `article`; else `other`. For
  markdown bodies fences / link labels stand in. It is computed from the fetched
  HTML even when a readability rung wins. It is wrong sometimes by design (a blog
  post with many code fences reads as `docs`); use it to route, never to gate.
- **Optional dependency — nothing to install for the default behaviour.** The hub
  imports neither module at startup; the rung is looked up per HTML call and
  skipped when absent. On the box that runs the hub: `pip install trafilatura`
  (or `pip install -r deploy/requirements-optional.txt`, which pins the smoke
  versions); `rs-trafilatura` is an optional extra (PyPI wheel, module
  `rs_trafilatura`), preferred when importable, never required.
  `search_usage {"provider":"read_url"}` reports `readability_extractor` (the rung
  that would run now: `null`, `"trafilatura"` or `"rs-trafilatura"`),
  `extractor_ladder`, `min_chars` and `dns_rebound_check`. **CI is stdlib-only:** the
  suite forces both modules absent (`None` in `sys.modules`) and the readability
  tests inject fake modules exposing exactly the call surface used
  (`extract(...)` / `bare_extraction(...)`; rs: `extract(...)` → `ExtractResult`),
  so it behaves the same on a box with the real libraries.
- **Manual smoke, real libraries (2026-09-02, NOT in the suite):** trafilatura 2.2.0
  + rs-trafilatura 0.1.1 (`pip install --break-system-packages`), driven through
  the adapter against the saved fixtures and five live pages with the strict
  environ (no escape hatch → address check + DNS re-resolve active):
  - Fixtures: `/listing` → `rs-trafilatura` `high` (1 977 chars; trafilatura-only
    1 896), `page_type: listing`, `link_density: 0.965`; `/docs` → `high` (786 / 709
    chars), `docs`; `/short` → `medium` (23 chars, genuinely short page), `other`;
    `/html` → `medium` (173 / 134 chars < 200, recall retry), `article`; `/cf` →
    `cloudflare-markdown` (the rung never runs). `/shell` exposed a bug the fakes
    had not: rs-trafilatura's recall pass returned the `<title>` three times
    (`"AppAppApp"`) and was accepted as `medium` — fixed (a page with no visible
    text has nothing to cover; now `stdlib-text`, `chars: 0`, `page_type: shell`,
    full ladder in the result) and pinned by a test. Metadata quirks seen and
    relayed as-is: rs cuts the fixture `<title>` at the em dash (whitespace is now
    collapsed), trafilatura's h1-first heuristic returned the fixture's header
    banner as `title`.
  - Live: `developers.cloudflare.com/…/markdown-for-agents/` → `cloudflare-markdown`,
    `tokens {markdown: 4289, original: 46485}`, 17 156 chars, 0.12 s;
    `blog.cloudflare.com/markdown-for-agents/` → `cloudflare-markdown`,
    `tokens {3856, 133525}`; `docs.python.org/3/library/http.server.html` →
    `rs-trafilatura` `high`, 22 211 chars, `extractor_confidence: 1.0`,
    `page_type: docs`, 0.10 s; `example.com` → `rs-trafilatura` `medium` (113 chars —
    the page is that short); a non-existent Wikipedia article → truthful `HTTP 404`.
    **No `dns_rebound` on any of the five hosts** (two anycast CDNs among them).
  - Timing on a 98 KB article page (best of 3): `extract(markdown)` 6.8 ms,
    `bare_extraction(fast=True)` 6.1 ms, `rs_trafilatura.extract` 4.2 ms.
- **Size cap:** the body is read up to `max_bytes` (256 … 10 000 000; default 2 MB,
  Cloudflare's own conversion limit) and the returned text is capped to it;
  `truncated: true` says so. `bytes` is the body length actually kept.
- **Safety, enforced BEFORE any request and again on EVERY redirect hop:**
  - `http` / `https` only (`file:`, `ftp:`, `javascript:` … refused).
  - **`.onion` hosts refused** via `onions.is_onion_url` — the onions-lane
    envelope forbids fetching or rendering onion services anywhere in this hub, so
    no request is made (see
    [`docs/legal/onions-lane-envelope.md`](../../../docs/legal/onions-lane-envelope.md)).
  - URLs embedding credentials (`user:pass@host`) refused; **no cookies or
    credentials are ever sent**; a modest `User-Agent` is.
  - At most **5 redirects**, followed by the adapter itself (urllib's silent
    follower is disabled) so a public page cannot redirect the fetch into
    `http://169.254.169.254/`; a `Location`-less 3xx and a loop are refused.
  - Hosts that resolve to **loopback / private / link-local / multicast /
    reserved / unspecified** space (127/8, RFC 1918, 169.254/16, `::1`, `fc00::/7`,
    …) are refused — literal IPs included, and **every address in the answer is
    checked**: a mixed answer with **any** non-public address is refused.
    **`READ_URL_ALLOW_PRIVATE=1`** disables that check *and* the DNS pin below: it is
    a **test/dev escape hatch** (the test origin is 127.0.0.1), default **off**,
    never set it in production.
  - A timeout applies to **every** hop (`timeout_s`, 1 … 120). `Accept-Encoding:
    identity` is requested; a gzip/deflate body served anyway is inflated under the
    same cap, any other encoding is reported truthfully rather than mis-decoded.
  - **DNS pinning (the v0 gap, mitigated the cheap stdlib way).** v0 resolved the
    name once for the check while urllib resolved it again to connect (a TOCTOU
    a rebinding resolver could exploit). Now, after each hop's fetch, the host is
    **re-resolved and the answer compared as a set** with the one that passed the
    check (order and duplicates do not count): a changed answer — or none — is an
    `isError` carrying **`dns_rebound: true`**, both answers, whether the new one
    includes a non-public address (a rebinding pattern: do not retry blindly) or is
    merely another public set (a rotating CDN with a very short TTL can do this:
    retry), and **the fetched bytes are discarded**. **Residual risk, stated
    honestly:** a resolver that flips public → private → public *exactly* between
    our two lookups still slips through, because urllib's own connect-time lookup
    is the one that matters and stdlib does not let the adapter connect to the
    checked address itself (that needs a custom HTTPS connection class handling
    SNI/Host — not stdlib-cheap, not done here). A local caching resolver can also
    mask a flip from both lookups. The live smoke saw no false positive on five
    hosts including two anycast CDNs.
- **Truthful degradation:** non-2xx status, binary content, an unreachable origin,
  an undecodable encoding, a DNS rebound or any refusal above returns an `isError`
  naming the reason (URL credentials scrubbed) — content is never fabricated.
- **Flags:** **`ENABLE_READ_URL`** is a kill switch (default ON; explicit falsey
  unwires the tool). **`READ_URL_MIN_CHARS`** (default 200, 1 … 100 000; anything
  else falls back to the default) is the readability threshold above. **`READ_URL_ALLOW_PRIVATE`**
  is the test/dev escape hatch described above. `search_usage {"provider":"read_url"}`
  reports the lattice state plus `private_targets_allowed`, `negotiates`,
  `max_redirects`, `readability_extractor`, `extractor_ladder`, `min_chars` and
  `dns_rebound_check`; there is no backend to probe (each call names its own
  origin).
- **Tests:** `tests/test_read_url.py` (89) against `tests/fake_page_backend.py`: the
  Cloudflare-markdown path (tokens parsed, `quality: high`), the HTML fallback
  (script/nav/footer dropped, title and paragraphs kept, `quality: low`), plain
  text and charsets, the `.onion` / `file:` / `ftp:` / credential refusals with
  **no request made**, the redirect loop and >5-hop cap, the private-address
  refusal with the flag unset (and the fetch with it set), redirects into private
  space, the size cap → `truncated: true`, binary refusal, and the kill switch;
  Wave 2 adds the ladder with **faked** `trafilatura` / `rs_trafilatura` modules
  (present → `high` with metadata; short → recall retry → `medium`; empty / raising
  → truthful fall-through to `stdlib-text`; absent → skipped; old version without
  markdown output → `txt`; rs preferred and labelled, its failure falling to
  trafilatura then stdlib; a too-short recall on a link-heavy page → stdlib, on a
  genuinely short page → `medium`, on a textless shell → not `medium`), the exact
  call signatures, `READ_URL_MIN_CHARS`, the cap on extracted text, `page_type` on
  six fixtures, the quality signals on every path, and DNS pinning with an injected
  resolver (changed answer → `dns_rebound`; another public set → still flagged;
  order/duplicates ignored; two resolutions per hop; unresolvable after the fetch;
  every address checked; the escape hatch skipping both). The tests set
  `READ_URL_ALLOW_PRIVATE=1` in the adapter's **injected** environ because the fake
  origin is 127.0.0.1 — that is the escape hatch's only intended use. No live
  network.

---

## Grounding lanes (keyless, default ON): Wikipedia, Wayback, Hacker News

The `grounding` lane (`lane_wiki.py`, wired through `lanes.py`) grounds a research
answer with three **public, keyless, first-party APIs** — an encyclopedia summary,
a dated archived copy, the technical-community discussion — through the same
`SelfHostedAdapter` mechanism as `github_*`: in-process stdlib `urllib`, **no
child, no new dependency, nothing at import**, a timeout on every request (15 s;
probes 5 s), the capability lattice, truthful degradation. **One adapter**
(`GroundingAdapter`, platform `grounding`) carries every enabled source so
`--print-plan` shows a single bucket; `search_usage {"provider":"grounding"}`
reports the per-tool lattice with a `source` column (and `self_hosted: false` —
these are public APIs, not a daemon of ours); `probe=true` spends one cheap GET
per enabled source (MediaWiki `siteinfo`, the availability API for
`example.com`, one `front_page` HN hit) and marks **only** the sources that did
not answer `absent` — HN being down never hides Wikipedia.

- **Default ON, one kill switch per source:** **`ENABLE_WIKIPEDIA`**,
  **`ENABLE_WAYBACK`**, **`ENABLE_HN`** — unset/truthy = wired; an explicit falsey
  value (`0`/`false`/`no`/`off`) drops that source's tools; all three killed makes
  `build(environ)` return `[]` (not wired, not degraded). Base URLs are config,
  not secrets, so tests point every source at one loopback fake:
  **`WIKIPEDIA_API_URL`** (default `https://en.wikipedia.org`),
  **`WAYBACK_API_URL`** (default `https://archive.org`, the availability API),
  **`WAYBACK_CDX_URL`** (default `https://web.archive.org`, the CDX index — a
  different host, hence a second env), **`HN_API_URL`** (default
  `https://hn.algolia.com`). No key, no token, nothing to leak.
- **Every request** sends the descriptive `User-Agent` Wikimedia's API policy asks
  for (`search-hub/0.1 (https://github.com/prekzursil/agent-skills-toolchain; …)`)
  plus `Accept: application/json`. Every success carries `tool`, `source`
  (`wikipedia` | `wayback` | `hn`) and `fetched_at` (UTC, `YYYY-MM-DDTHH:MM:SSZ`);
  every failure is an `isError` (`[search-hub:grounding] …`) naming the source and
  the upstream HTTP status — 429 rate limit (with any `Retry-After`), 404, 5xx, a
  non-JSON 2xx body, an unexpected shape, an unreachable host, a timeout — and
  **nothing is fabricated**. Arguments are validated **before** a request is
  spent (`limit` ranges, `lang`, `timestamp`/`from_year`/`to_year` digits, HN
  `tags` grammar, no control characters, length caps).
- **Wikipedia** (MediaWiki Action API + REST summary):
  - `wikipedia_search(query, limit<=20 (default 10), lang="en")` —
    `GET /w/api.php?action=query&list=search&format=json&srsearch=…&srlimit=N`.
    Returns `results[{title, pageid, snippet, url}]` (the snippet's
    `<span class="searchmatch">` markup and HTML entities are stripped/decoded),
    `total_hits`, `suggestion`, `count`, `lang`. `lang` swaps the host's language
    label only (`de` → `de.wikipedia.org`, `zh-yue` → `zh-yue.wikipedia.org`,
    scheme/port/path kept) and is accepted only when it matches
    `^[a-z]{2,3}(-[a-z]+)?$`; anything else — and a non-default `lang` against a
    host that is not `*.wikipedia.org` (a mirror, the test fake) — is refused
    with no request. MediaWiki reports a bad request as **HTTP 200 + an `error`
    object** (`missingparam`): relayed as an error, never as "0 results".
  - `wikipedia_summary(title, lang="en")` — `GET /api/rest_v1/page/summary/{title}`
    (spaces → `_`; a `/` in the title travels as `%2F`, exactly as Wikipedia's own
    `content_urls` encode `AC%2FDC`; `Mercury (planet)` keeps its parentheses).
    Returns `title, pageid, type, description, extract, url, thumbnail?
    {source, width, height}` and **`disambiguation: true` + a `note`** when `type`
    is `disambiguation` (the extract lists meanings, it does not describe one
    topic). **404 → "no such page"** (a truthful error pointing at
    `wikipedia_search`; titles are case-sensitive after the first letter);
    **429 → rate limited**; a `text/html` 5xx is relayed with its words.
- **Wayback Machine** (`.onion` URLs are refused via `onions.is_onion_url` before
  any request — the onions-lane envelope forbids fetching or rendering onion
  services anywhere in this hub, and the Wayback Machine would replay one; see
  [`docs/legal/onions-lane-envelope.md`](../../../docs/legal/onions-lane-envelope.md)):
  - `wayback_available(url, timestamp="")` — `GET /wayback/available?url=…
    [&timestamp=YYYYMMDD]` (4–14 digits, `YYYY[MM[DD[hhmmss]]]`). Returns
    `available, snapshot_url, timestamp, status` of the closest capture, or
    `available: false` + `note` when `archived_snapshots` is `{}` — the truthful
    answer, not an error. The availability API answers `{}` **intermittently even
    for archived URLs** (measured, below), so the note points at
    `wayback_snapshots`, which reads the index, instead of asserting "never
    archived".
  - `wayback_snapshots(url, limit<=50 (default 20), from_year="", to_year="")` —
    CDX `GET /cdx/search/cdx?url=…&output=json&limit=N&fl=timestamp,original,
    statuscode,mimetype&filter=statuscode:200[&from=YYYY][&to=YYYY]`. The body is
    a JSON **array of arrays whose first row is the header**; rows are keyed by
    that header (never by assumed position) into `snapshots[{timestamp, original,
    statuscode, mimetype, snapshot_url}]`, oldest first, + `count`. "No captures"
    is `[]` (JSON mode) or an empty body (plain mode): both are `count: 0` + a
    note, never an error; a header without `timestamp`/`original`, a dict body or
    a non-JSON 200 is an error, never an empty success. The CDX host **flaps to
    HTTP 503** (measured, below): that is an error saying so, never "no captures".
- **Hacker News** (Algolia HN Search API, keyless):
  - `hn_search(query, tags="story", limit<=50 (default 20), sort="relevance"|"date")`
    — `GET /api/v1/search` (relevance) or `/api/v1/search_by_date` (newest first)
    `?query=…&tags=…&hitsPerPage=N`. Returns `hits[{title, url, points,
    num_comments, author, created_at, objectID, hn_url}]` (+ `story_title`,
    `story_url` when present and `comment_text` — entities decoded, tags stripped —
    for comment hits, which have no `title`/`url`/`points`), `total_hits`
    (`nbHits`), `pages`, `count`. `tags` is an AND-list of
    `story|comment|poll|pollopt|show_hn|ask_hn|front_page|author_<user>|story_<id>`
    with at most one `(a,b)` OR group, validated **locally**: Algolia answers
    **HTTP 200 with `nbHits: 0` for an unknown tag** (measured), so a typo would
    otherwise look like an honest "nothing found".
- **Live-probe receipts (2026-09-02 07:41–07:43Z, read-only `curl -sS -A
  'search-hub/0.1 (…)'`; not used by tests):**
  - `curl -sS 'https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch=model+context+protocol&srlimit=2'`
    → 200 `application/json`; `{batchcomplete, continue, query{searchinfo{totalhits:
    4054, suggestion, suggestionsnippet}, search[{ns, title, pageid, size,
    wordcount, snippet, timestamp}]}}`; snippet `The <span
    class="searchmatch">Model</span> <span class="searchmatch">Context</span> …`.
    The same query on `de.wikipedia.org` → 200. Without `srsearch` → **HTTP 200**
    `{"error":{"code":"missingparam","info":"The \"srsearch\" parameter must be
    set.", …}, "servedby": …}`.
  - `curl -sS https://en.wikipedia.org/api/rest_v1/page/summary/Model_Context_Protocol`
    → 200, `type: standard`, `pageid: 79706999`; keys `type, title, displaytitle,
    namespace, wikibase_item, titles, pageid, thumbnail{source,width,height},
    originalimage, lang, dir, revision, tid, timestamp, description,
    description_source, content_urls{desktop{page,…}, mobile{…}}, extract,
    extract_html`. `…/summary/Mercury` → `type: disambiguation`, extract `Mercury
    most commonly refers to: …`. `…/summary/Zzqx_No_Such_Page` → **404**
    `application/json` `{"status":404,"type":"Internal error"}` (verbatim).
    `…/summary/AC%2FDC` → 200, `title: AC/DC`, `content_urls.desktop.page:
    https://en.wikipedia.org/wiki/AC%2FDC`.
    `…/w/api.php?action=query&meta=siteinfo&siprop=general&format=json` (the probe
    route) → 200 `sitename: Wikipedia, lang: en, servername: en.wikipedia.org`.
  - `curl -sS 'https://archive.org/wayback/available?url=example.com'` → 200
    `{"url": "example.com", "archived_snapshots": {"closest": {"status": "200",
    "available": true, "url":
    "http://web.archive.org/web/20260902040541/https://example.com/", "timestamp":
    "20260902040541"}}}`. `…?url=example.com&timestamp=20200101` → 200 `{"url":
    "example.com", "archived_snapshots": {}, "timestamp": "20200101"}` — **empty
    although the CDX index lists 2015 captures of example.com** (the intermittency
    the tool's note warns about). A never-archived host → 200 `{"url": …,
    "archived_snapshots": {}}`.
  - `curl -sS 'https://web.archive.org/cdx/search/cdx?url=example.com&output=json&limit=2&fl=timestamp,original,statuscode,mimetype&filter=statuscode:200&from=2015&to=2016'`
    → 200 (179 bytes) `[["timestamp","original","statuscode","mimetype"],
    ["20150101013824","http://www.example.com/","200","text/html"],
    ["20150101021413","http://www.example.com/","200","text/html"]]` — the header
    row. A never-archived host with `output=json` → 200 `application/json`
    **`[]`** (3 bytes). The host **flaps**: four probes inside one minute
    (07:41:57Z–07:42:50Z) answered **503, 200, 503, 200**, the 503 being an
    11,832-byte `text/html` page `<title>Internet Archive: Temporarily
    Offline</title>` with a `<style>` block and base64 logos (earlier the same
    morning every CDX probe was 503) — relayed as a truthful `HTTP 503` error
    carrying the page's words ("Internet Archive services are temporarily
    offline."), CSS and tags stripped.
  - `curl -sS 'https://hn.algolia.com/api/v1/search?query=model+context+protocol&tags=story&hitsPerPage=2'`
    → 200 `application/json`; `{hits, nbHits: 660, nbPages: 330, page, hitsPerPage,
    query, params, exhaustive, exhaustiveNbHits, exhaustiveTypo, processingTimeMS,
    processingTimingsMS, serverTimeMS}`; `params` echoes the query string (+
    `advancedSyntax=true&analyticsTags=backend`); story hit keys `author,
    children, created_at, created_at_i, num_comments, objectID, points, story_id,
    title, updated_at, url` (top hit `Model Context Protocol`, 872 points, 258
    comments, objectID 42237424). `/api/v1/search_by_date?…` → newest first
    (`2026-08-25T21:24:07Z`, `2026-08-25T15:09:35Z`). `…&tags=comment` → hit keys
    `author, comment_text, created_at, created_at_i, objectID, parent_id,
    story_id, story_title, updated_at` — no `title`/`url`/`points`, and
    `comment_text` carries entities (`&#x2F;`). `…&tags=bogus_tag` → **200,
    `nbHits: 0`, `hits: []`**. `?tags=front_page&hitsPerPage=1` (the probe route)
    → 200.
- **Tests:** `tests/test_lane_wiki.py` (151) against `tests/fake_wiki_backend.py`
  (one path-keyed stdlib router standing in for all four hosts — the route
  families never collide on path — serving the MediaWiki 200 + `error` object, the
  verbatim 404 body, 429s with `Retry-After`, the `[]` and empty-body CDX answers,
  the 503 "Temporarily Offline" HTML page with its `<style>` block, comment-shaped
  HN hits, and recording every request's headers): the tool surface and honest
  descriptions, import hygiene (stdlib + hub siblings only), per-source
  probe/lattice with only the dead source `absent`, request composition for all
  five tools (spy caller), HTML-stripped snippets, `lang` validation and
  subdomain swap (pure `wikipedia_host_for`), `%2F` titles, the disambiguation
  flag, 404/429/503 mapping, CDX header-row parsing in server order + both empty
  answers + malformed shapes as errors, `.onion` refusal with **no request** for
  both Wayback tools, the HN tag grammar / sort / route, `source` + `fetched_at`
  on every success (injected clock), transport failures and non-JSON 200s as
  errors, kill switches per source and all-killed `[]`, env URLs,
  `lanes.build_lane("lane_wiki", env)`, the hub surface and the single
  `--print-plan` bucket, one end-to-end run over a real loopback socket (the
  `User-Agent` observed on the wire), and a real connection-refused and
  read-timeout. No live network.

---

## Keyed search APIs (opt-in, default OFF, secrets by env-name)

The `keyed` lane (`lane_keyed.py`, wired through `lanes.py`) is the program's
answer (decisions G-2 and G-6, Wave 4) to every search API that needs a **paid
key**: twelve vendors ride **one** mechanism, `KeyedSearchAdapter` — a
`SelfHostedAdapter` sibling, in-process stdlib `urllib`, **no child, no new
dependency, nothing at import, ≈ 0 MB idle** — and **not one of them is wired until
the owner opts in per vendor**. Nothing bills by default, and nothing here ever
calls a vendor from the tests (loopback fakes only, `X-Fake-Key-*` values only).

- **Opt-in contract.** A vendor is wired only when **both** `ENABLE_KEYED_<VENDOR>=1`
  **and** its key env is non-empty (table below); otherwise `build(environ)` simply
  omits it (`[]` when none — not degraded, absent). The key is read by env **name**
  only, sent exactly where the vendor documents it (header, query parameter or
  HTTP basic), never logged, never written to disk, and **scrubbed from every text
  the lane emits** — an upstream 401 body that echoes the key comes back as
  `[redacted]`, in plain, URL-encoded, JSON-escaped and (basic auth) base64 forms.
  The only visible surface is the boolean `authenticated`. `<VENDOR>_API_URL`
  overrides the base URL (config, not a secret) so the tests point every adapter
  at one loopback fake; `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` must **both** be
  set for that basic-auth vendor.
- **Hard spend cap (G-2).** Every call **first** reserves against a small JSON
  ledger — **`KEYED_LEDGER_PATH`**, default `caches/keyed-ledger.json` (git-ignored;
  vendor names, call counts and dollar estimates, **never a key**) — under two
  limits: a **per-vendor daily call budget `KEYED_MAX_CALLS_PER_DAY`** (default 200,
  UTC days) and a **global per-calendar-month `KEYED_SPEND_CAP_USD`** (default 5.00)
  estimated from the list-price table below (no published price → counted, not
  priced). A refused call makes **no** request and names the cap and its reset
  time (`… resets at 2026-09-03T00:00:00Z. No request was made and nothing was
  billed`). Every **attempted** call counts, failures included — most vendors bill
  non-2xx answers too, and the safe side of a hard cap is the conservative one.
  Ledger writes are atomic (temp file beside the target + `os.replace`); an
  unreadable ledger is renamed aside (`keyed-ledger.json.corrupt-<stamp>`), started
  fresh and reported **once** (`ledger_notes` on the next success); a ledger that
  cannot be **written** refuses the call (a cap that cannot be enforced is not a
  cap — point `KEYED_LEDGER_PATH` at a writable file). Two hub processes sharing
  one ledger see each other's reservations (re-read under a lock on every call;
  last writer wins — documented, not solved, there is no portable file lock).
  A bad cap value (`KEYED_MAX_CALLS_PER_DAY=lots`) makes `build` raise, so
  `lanes.extra_adapters` reports the lane **degraded** instead of running a cap it
  could not parse.
- **Honesty contract.** **No probe is ever made** — a probe to a keyed vendor can
  bill — so `search_usage {"provider":"keyed"}` / `capabilities` report
  configuration only: `authenticated`, `auth_env` (names, never values),
  `auth_placement`, `flag_env`, `url_env`, `legal_shadow`, `price_per_1k_usd` per
  tool and the ledger `spend` snapshot (today's calls/budget, the month's estimate/
  cap, both reset times). 401/402/403/429/5xx and non-JSON answers are `isError`
  (`[search-hub:keyed:<vendor>] …`) carrying the vendor's own message (scrubbed),
  any `Retry-After`, and the vendor's quota/cost headers; an unrecognised 200 shape
  is an **error, not an empty success**; **results are never fabricated**. Every
  hit is normalised to `{title, url, snippet, published?, score?, vendor}` (+ small
  vendor extras such as `section`, `position`, `snippets`; HTML highlighting
  stripped, entities decoded); every payload carries `count`, `raw_count`,
  `latency_ms`, `credits_hint` (vendor headers/fields such as `x-ratelimit-*`,
  Serper `credits`, DataForSEO `cost`, ScrapingBee `spb-cost`, Kagi `api_balance`
  when present) and `spend` (the reservation just made). Arguments are validated
  **before** anything is reserved or sent.
- **SERP scrapers carry the legal shadow (G-6).** Serper, SerpApi, DataForSEO,
  ZenSerp and ScrapingBee scrape Google. Every one of their descriptions opens
  with the same sentence: Google is litigating exactly this practice
  (*Google v. SerpApi*), and they add **no index the keyless SearXNG route lacks** —
  prefer `searxng_web_search` and use them only knowingly accepting that exposure.
  Their capabilities report `legal_shadow: true`.

**Vendors** — endpoint, auth placement and list price re-read from the vendor docs
on **2026-09-02** (all URLs below resolved that day; where the plan sketch differed
from the docs, the docs won and the difference is noted). **Assumed $/1k**:
pay-per-use vendors use their published rate; subscription vendors use the
**smallest paid plan's** effective per-call price **rounded up** to the cent (the
plan a low-volume owner behind a $5/month cap plausibly holds; larger plans are
cheaper per call, so the estimate errs high). Per-argument surcharges are
estimated too (Linkup `deep`, Serper `num>10`, Mojeek `count>10`, DataForSEO depth
pages × operators, ScrapingBee `light_request=false`).

| Vendor — flag / key env | Tools | Endpoint | Auth placement | Assumed $/1k | Docs read 2026-09-02 |
|---|---|---|---|---|---|
| **Brave** — `ENABLE_KEYED_BRAVE` / `BRAVE_API_KEY` | `brave_web_search(q, count≤20, offset≤9, country, search_lang, freshness=pd\|pw\|pm\|py\|YYYY-MM-DDtoYYYY-MM-DD)`; `brave_llm_context(q, country, search_lang)` | `GET https://api.search.brave.com/res/v1/web/search`; `GET …/res/v1/llm/context` | header `X-Subscription-Token` | 5.00 both ($5 per 1,000 requests, $5 free credit every month) | [web search](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started), [LLM context](https://api-dashboard.search.brave.com/documentation/services/llm-context), [pricing](https://brave.com/search/api/) |
| **Kagi** — `ENABLE_KEYED_KAGI` / `KAGI_API_KEY` | `kagi_search(q, limit≤100, page≤10)`; `kagi_enrich_web(q)`; `kagi_enrich_news(q)` | `POST https://kagi.com/api/v1/search` (JSON `{query, limit, page}`); `GET https://kagi.com/api/v0/enrich/web?q=`, `…/enrich/news?q=` | header `Authorization: Bearer <key>` (Search v1); header `Authorization: Bot <key>` (Enrich v0) | 12.00 search; 2.00 enrich | [Search v1 OpenAPI](https://kagi.com/api/docs/openapi), [Enrich](https://help.kagi.com/kagi/api/enrich.html), [pricing](https://kagi.com/api/pricing) |
| **Linkup** — `ENABLE_KEYED_LINKUP` / `LINKUP_API_KEY` | `linkup_search(q, depth=standard\|deep, output_type=searchResults\|sourcedAnswer, include_images)` | `POST https://api.linkup.so/v1/search` (JSON) | header `Authorization: Bearer <key>` | 5.00 standard ($0.005/request); 6.00 deep | [search reference](https://docs.linkup.so/pages/documentation/endpoints/search/reference), [pricing](https://www.linkup.so/pricing) |
| **Mojeek** — `ENABLE_KEYED_MOJEEK` / `MOJEEK_API_KEY` | `mojeek_search(q, count≤40)` | `GET https://www.mojeek.com/search?fmt=json&q=…&t=<count>` | query parameter `api_key` (never echoed) | 2.70 (Startup £2 CPM at 1.35 USD/GBP, ≤10 results/request); 4.05 when `count>10` (Business £3 CPM, ≤40) | [request parameters](https://www.mojeek.com/support/api/search/request_parameters.html), [plans](https://www.mojeek.com/services/search/web-search-api/) |
| **You.com** — `ENABLE_KEYED_YOUCOM` / `YOUCOM_API_KEY` | `youcom_search(q, count≤100, country, language)` | `POST https://ydc-index.io/v1/search` (JSON; `GET` still works upstream but is frozen) | header `X-API-Key` | 5.00 ($5.00/1k calls; $100 free credit on signup) | [v1 search](https://you.com/docs/api-reference/search/v1-search), [pricing](https://you.com/pricing) |
| **Perplexity** — `ENABLE_KEYED_PERPLEXITY` / `PERPLEXITY_API_KEY` | `perplexity_search(q, max_results≤20, country)` — the **Search API** (raw ranked results), not a Sonar answer | `POST https://api.perplexity.ai/search` (JSON) | header `Authorization: Bearer <key>` | 5.00 ($5.00 per 1K successful `POST /search` requests) | [search endpoint](https://docs.perplexity.ai/api-reference/search-post), [pricing](https://docs.perplexity.ai/docs/getting-started/pricing) |
| **Marginalia** (commercial key) — `ENABLE_KEYED_MARGINALIA` / `MARGINALIA_API_KEY` | `marginalia_search(q, count≤100)` | `GET https://api2.marginalia-search.com/search?query=…&count=…` | header `API-Key` | **none published** (metered via the portal) → counted against the daily budget, $0 in the monthly estimate | [API article](https://about.marginalia-search.com/article/api/) |
| **Serper** (SERP scraper) — `ENABLE_KEYED_SERPER` / `SERPER_API_KEY` | `serper_search(q, num≤100, gl, hl)` | `POST https://google.serper.dev/search` (JSON) | header `X-API-KEY` | 1.00 (Starter $50 / 50k credits, 1 credit per query); 2.00 when `num>10` (2 credits) | [serper.dev](https://serper.dev/) |
| **SerpApi** (SERP scraper) — `ENABLE_KEYED_SERPAPI` / `SERPAPI_API_KEY` | `serpapi_search(q, start≤990, gl, hl)` — one SERP page (~10) per call, `start` pages | `GET https://serpapi.com/search.json?engine=google&q=…` | query parameter `api_key` (never echoed) | 25.00 (Starter $25 / 1,000 searches; Developer $75 / 5,000 = 15.00; free tier 250/month) | [Google Search API](https://serpapi.com/search-api), [pricing](https://serpapi.com/pricing) |
| **DataForSEO** (SERP scraper) — `ENABLE_KEYED_DATAFORSEO` / `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` | `dataforseo_serp(q, depth≤100, location_code=2840, language_code=en)` — only `organic` items become hits | `POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced` (JSON task array) | HTTP basic `Authorization: Basic base64(login:password)` | 2.00 per SERP page of 10 (Live) × `ceil(depth/10)` × **5 per search operator** in `q` (`site:`, `intitle:`, `inurl:`, `filetype:`, … — the vendor's own rule); the API's `cost` field is relayed | [live/advanced](https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/), [SERP pricing](https://dataforseo.com/pricing/serp) |
| **ZenSerp** (SERP scraper) — `ENABLE_KEYED_ZENSERP` / `ZENSERP_API_KEY` | `zenserp_search(q, num≤100, location, gl, hl)` — organic entries with a URL become hits; question/video blocks count in `raw_count` only | `GET https://app.zenserp.com/api/v2/search?q=…&num=…` | header `apikey` | 2.00 (Small $49.99 / 25,000 searches) | [documentation](https://app.zenserp.com/documentation), [plans](https://zenserp.com/pricing-plans/) |
| **ScrapingBee** Google API (SERP scraper) — `ENABLE_KEYED_SCRAPINGBEE` / `SCRAPINGBEE_API_KEY` | `scrapingbee_google(q, page≤10, country_code, date_range=past_hour\|…\|past_year, light_request=true)` | `GET https://app.scrapingbee.com/api/v1/google?search=…` | header `Authorization: Bearer <key>` (the `?api_key=` query form is deprecated upstream) | 2.54 light (10 credits; Hobby $19 / 75,000 credits); 3.80 when `light_request=false` (15 credits) | [Google API](https://www.scrapingbee.com/documentation/google-api/), [pricing](https://www.scrapingbee.com/pricing/) |

**Where the docs differed from the plan sketch / Lens 9 (kept as read on 2026-09-02):**
Kagi's **Search** is now **v1 `POST /api/v1/search`** with an HTTP **bearer** scheme
and a sectioned answer (`data.search|news|adjacent_question|related_search`; the
lane tags each hit with its `section`, surfaces `related_searches` and the
per-section `sections` counts, relays `meta.trace`/`ms` as `upstream_trace`/
`upstream_ms`); only **Enrich** keeps the v0 `GET ?q=` + `Authorization: Bot`
contract and the `api_balance` credit hint. **Linkup** is metered per request
($0.005 standard / $0.006 deep), not $20/month. **Mojeek**'s documented host is
`www.mojeek.com` (not `api.mojeek.com`), and its plans cap results per request
(Startup 10, Business 40, Enterprise 100), so a Startup key may return fewer hits
than `count` asks for. **You.com**'s current host is `ydc-index.io` with `POST`; the
"$100" in Lens 9 is the free signup credit, not a fee. **Perplexity** does have a
Search API (`POST /search`), so `perplexity_search` is raw results, not a Sonar
completion. **Marginalia**'s commercial API is the new `api2.marginalia-search.com`
host with an `API-Key` **header** — the deprecated key-in-path
`api.marginalia.nu/{key}/search/{query}` form is not used, and the free shared
`public` key is **refused** here with a message pointing at the SearXNG
`marginalia` engine (that key is the keyless route and stays there). **SerpApi**'s
docs no longer list `num` (Google dropped it in 2025) — paging is `start=`; Serper
notes the same, so `num>10` is "up to the vendor". **ScrapingBee**'s Google endpoint
is `/api/v1/google` (not `/api/v1/store/google`) and wants the Bearer header.
**SerpApi, ZenSerp and ScrapingBee** sell monthly plans, not metered calls, so
their $/1k are the smallest-paid-plan estimates described above; Mojeek (GBP CPM)
and Serper (credit top-ups) are metered and priced at their published rates.

- **Tests:** `tests/test_lane_keyed.py` (166) against `tests/fake_keyed_backends.py`
  — one stdlib fake for all twelve route families keyed on `/<vendor>/<path>`,
  usable as a pure `HeaderCaller` or as a real loopback `HTTPServer`; it accepts
  only the synthetic `X-Fake-Key-<vendor>` values, at each vendor's **documented**
  location only (a key in the wrong place is a 401), and its 401 bodies **echo the
  presented key on purpose** so the scrub is asserted. Covered: the module is
  stdlib-only and import-safe; flag-without-key and key-without-flag wire nothing;
  every vendor's flag/key/URL env; `lanes.build_lane("lane_keyed", env)` wiring and
  the degraded report for a bad cap value; capabilities never probe; per-vendor
  request shape + normalisation (Kagi v1/v0, Brave `grounding` incl. the `poi`
  object, Linkup both output types, DataForSEO task envelope + organic filter,
  ZenSerp non-organic blocks, ScrapingBee light/regular, SerpApi/Kagi paging sent
  only past page one); the key never appears in output or error text (plain,
  URL-encoded, JSON-escaped, basic-auth base64; a 1–3 character "key" does not
  shred the payload); 429 with `Retry-After`, 402, 5xx, non-JSON 200, unrecognised
  200 shape, unreachable host (scrubbed, counted); bad arguments fail before any
  reservation or request; the daily budget is per vendor and the monthly cap is
  global, both naming the reset time, a zero cap blocks the first priced call,
  failed attempts count, both roll over on the clock; the ledger is valid JSON
  holding no key, its write is atomic (a failed replace leaves the old file
  intact, no temp files remain), an unwritable path refuses the call, a corrupt
  file is renamed aside and reported once, old days/months are pruned, reservation
  is thread-safe; and one run over a **real loopback socket** with the default
  `urllib` header-aware caller (GET, POST, 401 scrub, 429). No live network, no key.

---

## Answer engines (opt-in, on-demand): Vane adapter + local-deep-research

Wave 3 of the gem-hunt program (decisions G-2, G-4, G-5): a **keyless, local-LLM,
cited-answer path** that is **OFF by default** and costs the running hub 0 RAM until
the owner opts in. The heavy parts — Vane and the LLM it talks to — are started **on
demand** with the compose kit in [`deploy/`](deploy/README.md) and evicted the same
way; the hub side is one in-process, pure-stdlib adapter (`lane_answer.py`,
`VaneAdapter`, platform `answer`) wired through `lanes.py`.

- **Opt-in:** `ENABLE_VANE=1` (default URL `http://127.0.0.1:3000`) **or** a
  non-empty **`VANE_URL`** wires the lane; unset means `build(environ)` returns `[]`
  and no tool exists. An explicit falsey `ENABLE_VANE=0` is the kill switch even
  with a URL set. **`VANE_TIMEOUT_S`** (default **120 s**, clamped 1…3600) is the
  LLM budget per answer — minutes, not the 30 s a search hit gets. The base URL is
  **endpoint-agnostic** (G-4): on-box today, `VANE_URL=https://vane.your-ovh-box`
  tomorrow, nothing else changes.
- **Tool:** `selfhosted_answer(query, focus="webSearch", optimization="balanced",
  history=[], chat_provider="", chat_model="", embedding_provider="",
  embedding_model="")` → `POST /api/search` (non-streaming) → `{answer,
  sources[{title, url, snippet}], providers_used, latency_ms, "engine": "vane",
  focus, sources_used, optimization, history_turns, providers_cached, note}`. `focus`
  takes Perplexica's `webSearch | academicSearch | redditSearch` **or** Vane 1.12's
  own `web | academic | discussions` (comma-join several, `all` for every source):
  Vane renamed `focusMode` to a `sources` array, and the tool maps both. `history`
  is `[[role, text]]` pairs or `{role, content}` objects, passed through in Vane's
  shape (`human | assistant`).
- **Provider ids drift, so resolve — never pin.** Vane mints every provider id with
  `crypto.randomUUID()` at seed time. The adapter therefore reads
  `GET /api/providers` on **every call** (cached **60 s**), accepts provider/model
  **names** as well as ids (case-insensitive), takes the **first** chat + **first**
  embedding provider/model when the caller passes none, and **reports** the pick in
  `providers_used` (`{chat, embedding}` each with `provider_id, provider, model_key,
  model_name, selected_by: first-available | caller`). Vane ships a keyless
  in-process Transformers **embedding** provider, so only the chat model has to come
  from Ollama (`OLLAMA_BASE_URL`, set by the compose kit).
- **Capability lattice:** the probe is `GET /api/providers` — **`probed`** when it
  answers with the providers shape (the probe also warms the cache and names the
  providers in the report), **`absent`** with the reason when it does not (down,
  non-2xx, not-Vane body). `search_usage {"provider":"answer","probe":true}` shows
  it; the default `search_usage` and `tools/list` do zero network.
- **Truthful degradation — an answer is never fabricated:** Vane down or connection
  refused, a **timeout** (named with the configured seconds and `VANE_TIMEOUT_S`),
  4xx/5xx (Vane's own `message` relayed), a non-JSON 2xx body, **no providers
  configured**, no **embedding** model, or an unknown provider/model name (the error
  lists what *is* configured) — each is an `isError` naming the cause; a bad
  argument (`optimization`, `focus`, `history`, empty `query`) is refused **before**
  any request is spent. An **empty** answer is reported as empty, not padded.
  Source URLs are listed as **strings only**: a `.onion` source is counted
  (`onion_sources`) and noted, never fetched — the envelope in
  [`docs/legal/onions-lane-envelope.md`](../../../docs/legal/onions-lane-envelope.md)
  applies here too.
- **Deploy (nothing starts by default):** `deploy/docker-compose.answer-engines.yml`
  puts **Vane** (`--vane`, slim image `itzcrazykns1337/vane:slim-v1.12.2`, reusing
  the estate SearXNG via `SEARXNG_API_URL`; the bundled all-in-one image with its
  `workers=%k` SearXNG is deliberately avoided), **local-deep-research** (`--ldr`,
  `localdeepresearch/local-deep-research:1.10.7`, web UI + REST API) and an
  **evicting Ollama** (`--ollama`, `OLLAMA_KEEP_ALIVE=0`, only for a box without a
  host Ollama) each behind a compose profile with a `mem_limit` and loopback-only
  ports. `deploy/run-answer-engines.{sh,ps1} up --vane|--ldr` starts, `--print`
  shows the resolved env without touching Docker, `stop-answer-engines.{sh,ps1}`
  reclaims the RAM. **LDR's hub flags — `ENABLE_LDR=1` + `LDR_URL` — belong to the
  LDR MCP ProviderSpec in `providers.py`** (a separate slice) and do **not** point
  at the `--ldr` container: `ENABLE_LDR=1` runs upstream's STDIO-only `ldr-mcp` via
  `uvx` on the host (engine in-process), and `LDR_URL` only bridges to a resident
  `ldr-mcp` behind an operator's Streamable-HTTP gateway. The container is a second,
  independent LDR install (web UI + REST API on `LDR_PORT`) sharing the same Ollama
  and SearXNG. Tags verified against Docker Hub and the
  upstream `v1.12.2` / `v1.10.7` sources on 2026-09-02; the compose file has **not**
  been run on the authoring VM (no Docker) — see the honest note in
  [`deploy/README.md`](deploy/README.md).
- **Tests:** `tests/test_lane_answer.py` against `tests/fake_vane_backend.py` (a
  stdlib fake of `/api/providers` + `/api/search` with 500 / timeout / no-provider /
  `.onion` modes): opt-in and kill-switch semantics, `lanes.build_lane("lane_answer",
  env)` wiring, the lattice, first-available vs explicit vs name-resolved providers,
  the 60 s cache (injected clock), the request/response mapping, every degradation
  above, two loopback-socket runs with the real `urllib` caller (one a real client
  timeout), and the deploy kit (compose parses, pins, profiles, caps; the run
  script's `--print` mode and its refusal to start without a profile). No live
  network, no Docker.

---

## Tools

- **Provider tools (passthrough, original names):** whatever each server
  advertises — e.g. `web_search_exa`, `web_fetch_exa`; `tavily_search`,
  `tavily_extract`, `tavily_map`, `tavily_crawl`, `tavily_research`;
  `firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`, …; and SearXNG's
  four tools including `searxng_web_search` (49 total in the committed caches).
  Rotation is applied invisibly inside keyed-provider call paths; SearXNG is
  direct and keyless.
- **Per-provider account tools (6 each = 18):** `ex_account_*`, `tv_account_*`,
  `fc_account_*` — `list` / `current` / `add` / `remove` / `switch` / `cycle`
  (from the shared `_shared/accounts.py`). Each "account" is **one API key**;
  these give you the multi-key store + labels + a **manual** switch/cycle.
  SearXNG intentionally has no `sx_account_*` tools.
- **Self-hosted tools (keyless, HTTP-backed):** `selfhosted_search`,
  `selfhosted_extract` — Tavily-shaped, served in-process from `TRAILSEARCH_URL`
  (no child). See the lane section above.
- **Repo discovery (keyless, default ON):** `github_repo_search`,
  `github_new_and_hot`, `github_popular_and_alive`, `github_topic_search`,
  `github_repo_activity` — first-party GitHub REST, in-process, `x-ratelimit-*`
  relayed on every answer. `ENABLE_GITHUB_SEARCH=0` removes the lane.
- **`read_url` (keyless, default ON):** in-process fetch that negotiates Cloudflare
  Markdown for Agents and names the extractor that produced the text.
  `ENABLE_READ_URL=0` removes it. Never fetches `.onion` hosts.
- **`search_usage` (hub-native, on-demand):** per stored key, reports
  `label + remaining` (Firecrawl remaining credits; Tavily plan+paygo headroom)
  plus cooldown/health, **plus** the self-hosted lane's capability lattice. Exa
  reports `"error-driven (no balance API)"`; SearXNG reports `"none (keyless;
  never cooled)"`. Pass
  `provider="exa"|"tavily"|"firecrawl"|"searxng"|"selfhosted"` to narrow, or omit
  for all; `probe=true` does one health GET per self-hosted backend. Read-only;
  never spawns a search child.

`python hub.py --print-plan` prints the exposed tool counts; `--refresh [ids…]`
re-enumerates the provider servers to regenerate `caches/*.json`.

---

## Multi-key setup (plug-and-play)

Rotation needs **≥2 keys per keyed provider**. SearXNG needs no key and is not
stored in `accounts.json`. Three ways to add keyed-provider credentials, cheapest
first:

1. **Numbered env backups (auto-seeded).** Export `EXA_API_KEY` and any of
   `EXA_API_KEY_2 … EXA_API_KEY_8` (same for `TAVILY_API_KEY_*`,
   `FIRECRAWL_API_KEY_*`). On start the hub registers each numbered var as an
   extra rotation key (`key2`, `key3`, …) with **zero** manual steps. They are
   stored only as `${ENV}` **references**, never literals.
2. **`*_account_add` at runtime.** `ex_account_add { "name": "work", "env": {
   "EXA_API_KEY": "..." }, "label": "work@co" }`.
3. **`accounts.json`.** Copy `accounts.example.json` → `accounts.json` (GITIGNORED)
   and list keys as `${ENV}` refs. See that file's `_comment` for the shape.

The store (`accounts.json`) is **gitignored** and may hold literal secrets — it is
never committed. The committed `accounts.example.json` shows the `${ENV}` shape.

> **Paid keys only.** Cooling a key "until the billing period resets" is correct
> for a **paid** monthly credit pool. Rotating among multiple **free-tier** keys
> to dodge a per-account limit may violate a provider's Terms of Service; this is
> ordinary management of the user's OWN paid keys.

---

## Migrating `~/.mcp.json` (USER-APPROVED step — do this yourself)

The repo registers `search-hub` in `tools/mcp/canonical-mcp-servers.json`. To use
it live you **replace** the four individual entries with the single hub. This is
a **user-approved** change to your live `~/.mcp.json`; it is **not** done for you.

1. In `~/.mcp.json`, **remove** the standalone `exa`, `tavily`, `firecrawl`, and
   `searxng` server entries.
2. **Add or update** the `search-hub` entry:

   ```json
   "search-hub": {
     "type": "stdio",
     "command": "C:\\Python314\\python.exe",
     "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\search-hub\\hub.py"],
     "env": {
       "EXA_API_KEY": "${EXA_API_KEY}",       "EXA_API_KEY_2": "${EXA_API_KEY_2}",
       "TAVILY_API_KEY": "${TAVILY_API_KEY}", "TAVILY_API_KEY_2": "${TAVILY_API_KEY_2}",
       "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}", "FIRECRAWL_API_KEY_2": "${FIRECRAWL_API_KEY_2}",
       "SEARXNG_URL": "http://127.0.0.1:8890"
     }
   }
   ```

3. Add any real backup keys to your environment (`EXA_API_KEY_2`, …), and
   override `SEARXNG_URL` if your self-hosted instance is not at the default
   `http://127.0.0.1:8890`. Unset backup vars resolve to empty and are skipped —
   harmless.
4. Restart the session / `/mcp reconnect`. The same search tool names now come
   through `search-hub` with rotation; add `search_usage` for balances.

Notes: the tool NAMES are unchanged, so existing skills/prompts keep working.
Provider tools are served from the committed caches, so `tools/list` stays
instant and no child spawns until you actually call a search tool.

---

## Testing

Unit + integration tests are **fully mocked** — no live keys, no network:

```bash
cd tools/mcp/search-hub && python -m pytest tests/ -q
```

They cover the provider specs + error classifier (including SearXNG's keyless
PASS-only classifier), the usage parsers, `pick_active` skipping cooled keys, the
rotate-retry-once policy (incl. the Tavily ambiguous-429 `/usage` probe),
numbered-backup seeding, the `env_for` account resolver, and the hub's
list/route/usage/switch paths against a fake backend. The keyless regression
also cools every fake keyed account before proving SearXNG still serves search.

The self-hosted lane is covered by `tests/test_adapters.py` + hub integration
tests against a stdlib **fake TrailSearch backend**
(`tests/fake_trailsearch_backend.py`): the capability lattice states
(native/probed/declared/emulated/absent), Tavily-shaped request translation,
truthful degradation when the daemon is down (an `isError`, never fake hits), and
one end-to-end case over a real loopback socket using the default `urllib` caller.
`python deploy/smoke_selfhosted_no_docker.py` runs the same path standalone.

The GitHub REST lane (`tests/test_github_search.py` + `tests/fake_github_backend.py`)
and `read_url` (`tests/test_read_url.py` + `tests/fake_page_backend.py`) are covered
the same way: canned routes on a loopback `HTTPServer`, including the 202 "computing"
stats path, a 403 with rate-limit headers, Cloudflare `text/markdown` negotiation,
redirect loops and private-address refusal. The onion lane is `tests/test_onions.py`
(gate, modes, tagging, `ENABLE_ONIONS` / `ENABLE_VORMWEB` kill switches) and
`tests/test_deploy_settings.py` (text-level guards on `deploy/searxng-min/settings.yml`
so nobody silently re-enables `google` or moves VormWeb back to the Tor-gated
`onions` category).

**Needs live services (manual, not in CI):** actually reaching
Exa/Tavily/Firecrawl/SearXNG, real `search_usage` balances, and observing a real
402→rotate in production. Use `python hub.py --refresh` to regenerate
`caches/*.json` from the live servers.

## Files

- `hub.py` — JSON-RPC stdio server; per-(provider, key) lazy children + per-call
  routing; the in-process self-hosted adapter lane; `--refresh` / `--print-plan`.
- `providers.py` — the 4 provider specs (stdio cmd + env/config + usage URL) and
  the exhaustion-signal classifier.
- `adapters.py` — the self-hosted adapter interface (capability lattice + probe +
  truthful-degradation `handle_call`), `TrailSearchAdapter` (keyless Tavily lane),
  `OSSInsightAdapter` (keyless repo discovery, default OFF), `GitHubSearchAdapter`
  (keyless GitHub REST repo discovery, default ON) and `ReadUrlAdapter` (`read_url`,
  default ON); `wired_adapters` is what the hub instantiates.
- `onions.py` — the pure onions-lane envelope guard (index-only; Ahmia + VormWeb;
  `ENABLE_ONIONS` lane kill switch, `ENABLE_VORMWEB` per-engine kill switch).
- `rotation.py` — per-key health, `pick_active`, `mark_exhausted`, the
  rotate-retry wrapper, and numbered-backup seeding.
- `usage.py` — stdlib `urllib` calls to the keyed providers' usage endpoints.
- `caches/*.json` — committed tool enumerations (regenerate with `--refresh`).
- `deploy/` — compose + run scripts for the minimal self-hosted profile, a
  Docker-free smoke, and the deploy README.
- `../_shared/accounts.py` — the shared multi-account store (one additive
  read-only helper, `env_for`, was added for per-key resolution).
