# Search-stack reunion + a keyless self-hosted lane: decision record (2026-09-02)

**Decision.** Reunite the owner's search stack on **this repo's `tools/mcp/search-hub`**
as the single canonical hub, and grow it with a **keyless, self-hosted lane** so the
estate can stop depending on Tavily (closed, cloud-only). The self-hosted lane is an
**in-process HTTP adapter** in the hub (built here, tests-first) fronting a
**self-hosted TrailSearch daemon** (`jianjungki/tavily-open`, MIT) that serves native
Tavily-shaped `/tavily/search` + `/tavily/extract` over SearXNG + a local SQLite index.
Every provider adapter reports a **capability lattice** (`native | probed | declared |
emulated | absent`) and **degrades truthfully** — a backend that is down returns an
`isError`, never a fabricated hit. The heavy daemon is **on-demand**; the adapter adds
~0 RAM to the running hub.

Two of the §8 follow-up lanes are now **built, default OFF**: an **Ahmia onion lane**
(index-only, via the existing SearXNG tool, gated `ENABLE_ONIONS`, no Tor/onion-fetch — behind
[`docs/legal/onions-lane-envelope.md`](../legal/onions-lane-envelope.md)) and an **OSSInsight
repo-discovery lane** (keyless public API, gated `ENABLE_OSSINSIGHT`). Both add **≈ 0 MB**. The
`ast-searchhub` code merge is still **follow-up** (the sibling is not reachable from this VM).

This is a design record kept in lockstep with the code. What shipped on the branch is in §7;
everything else (the `ast-searchhub` merge, second-wave adapters, OVH end-state) is a plan (§8).

---

## 1. Two hubs today — the thing being reunited

| | this repo (`Prekzursil/agent-skills-toolchain`, SSOT) | sibling checkout `ast-searchhub` (a disposable clone on the box) |
|---|---|---|
| `tools/mcp/search-hub` | canonical: Exa/Tavily/Firecrawl (keyed, rotated) + keyless SearXNG; lazy per-key stdio children; committed caches; `search_usage` | a **variant** the owner iterated on locally; deltas unknown to this repo |
| `tools/mcp/cloud-hub` | canonical: 11 cloud backends incl. OVH region rotation | a local copy/variant |
| `tools/mcp/social-hub` | canonical FB/IG hub | a local copy/variant |
| shared `_shared/accounts.py` | the multi-key store all three hubs use | same module, possibly drifted |

Per the repo doctrine (`CLAUDE.md` SSOT-WIRE): the **GitHub remote is the SSOT for
history**, `~/source/ast-integrate` is the only checkout you EDIT, and every other
checkout — including `ast-searchhub` — is disposable scratch that may hold unpushed work.
So "reunion" is **not** "merge two peers"; it is **fold the sibling's useful search-hub
deltas into this canonical hub, on a pushed branch**, then retire the sibling copy. The
sibling is not reachable from this cloud VM, so the actual byte-merge is a follow-up lane
(§8) with an explicit, resumable procedure; this PR makes the canonical hub the richer
target it will merge *into* by adding the keyless lane the owner wanted.

### Reunion mapping (structural — how the sibling folds in)

| sibling surface | canonical target | fold rule |
|---|---|---|
| `search-hub/hub.py` variant | `tools/mcp/search-hub/hub.py` | three-way diff vs the common ancestor; take sibling behaviour **only** where it is a real improvement, tests-first (§8) |
| `search-hub/providers.py` variant | `providers.py` | union of provider specs; keep canonical classifier semantics (SG-2/SG-3) unless the sibling fixes a measured bug |
| any sibling self-hosted experiment | **superseded by `adapters.py`** (this PR) | if the sibling already had a keyless backend, port its backend URL/shape into an adapter subclass, not a parallel mechanism |
| `_shared/accounts.py` drift | canonical `_shared/accounts.py` | reconcile via the existing dual-write discipline; never fork the store |
| committed `caches/*.json` | canonical `caches/*.json` | regenerate with `hub.py --refresh` on the box, never hand-merge cache JSON |

---

## 2. What the estate needs, and why key-free

Tavily is **closed and cloud-only**: every query leaves the box, needs a vendor key, and
is metered. The estate already runs SearXNG (`127.0.0.1:8890`, for `tools/search-expansion`)
and already fronts keyless SearXNG in `search-hub`. What is *missing* keyless is the
**search+extract+crawl** surface Tavily provides — grounded results with clean page
content — which is exactly what a self-hosted Tavily-shaped daemon adds on top of SearXNG.

Requirements that shaped the choice:

1. **Keyless / self-hosted** — no vendor key, no cloud egress.
2. **Tavily-compatible shape** — so the hub adapter is a thin bridge and skills that expect
   Tavily-shaped results keep working.
3. **Low RAM on a 31.6 GB, chronically memory-starved Windows box** (`agent-self/home/AGENTS.md`:
   free RAM has fallen to ~1.8 GB; the freeze driver is **commit exhaustion**, not RSS —
   `docs/mcp-consolidation-plan.md` §1a).
4. **Truthful degradation** — a down daemon must never fake results.
5. **Reuse, don't multiply** — the estate's SearXNG should be shared, not re-run.

---

## 3. Candidate evaluation (current sources, verified 2026-09-02)

### 3a. The self-hosted Tavily-compatible search+extract backend (the one we wire)

**Research pass — re-verified 2026-09-02** (repo URL · LICENSE file present? · native
`/tavily/*`? · Docker image size · idle RAM). Every row was re-checked this pass; sources
in the notes column.

| candidate | repo | LICENSE file | native `/tavily/*` | Docker image | idle RAM (documented/measured) | source |
|---|---|---|---|---|---|---|
| **TrailSearch** | [github.com/jianjungki/tavily-open](https://github.com/jianjungki/tavily-open) | **YES — MIT** (`gh api .../license` → `MIT`, `LICENSE` at root) | **YES** (`openapi.json`: `POST /tavily/search`, `POST /tavily/extract`) | none published; built from `python:3.11-slim` + reqs | ~270–320 MB app (FastAPI+trafilatura, `http_first`, no browser) | gh api + `openapi.json` + `Dockerfile` |
| OrioSearch | [github.com/vkfolio/orio-search](https://github.com/vkfolio/orio-search) | **NO** — still absent (`gh api .../license` → 404; `raw .../{master,main}/LICENSE` → **404/404**) | NO (`/search`,`/extract`; not the `/tavily/*` namespace) | none published; `python` + reqs | lighter (no crawl4ai; FlashRank ~4 MB) | gh api + `curl -I` both branches |
| fastCRW | [github.com/us/crw](https://github.com/us/crw) | YES — AGPL-3.0 (engine); MIT (SDKs) | NO (Firecrawl-shaped `/v1/*`) | **~73 MB compressed / 191 MB uncompressed** (`ghcr.io/us/crw`, registry-measured) | **~14 MB idle** (maintainer-measured; ~66 MB heavy) | ghcr registry + repo BENCHMARKS.md/docs |
| Crawl4AI | [github.com/unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | YES — Apache-2.0 | NO (scraper) | **~1.65 GB** amd64 (`unclecode/crawl4ai`, Docker Hub) | base **270 MB** + browser **270 MB** + **180 MB**/pool; docs say **4 GB** | Docker Hub + ARCHITECTURE.md |
| Meilisearch | [github.com/meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) | YES — **MIT AND BUSL-1.1** (core MIT; enterprise-edition files BUSL) | NO (index engine) | **~100 MB compressed** (`getmeili/meilisearch`) | **50–100 MB idle** (third-party); official publishes none (mmap: 9 MB data → ~305 MB) | LICENSE + Docker Hub + docs |

**Corrected 2026-09-02** by five parallel research subagents (the initial figures were
vendor-blog conflations): fastCRW is **not** "~6 MB / ~8 MB" — the registry image is ~73 MB
compressed and idle RAM is ~14 MB (the "6 MB" string lives only in the GitHub About blurb);
Meilisearch is dual-licensed **MIT AND BUSL-1.1**, not an opaque "custom". TrailSearch's
~270–320 MB app figure is an **estimate** (app-only, `http_first`; undocumented — the repo's
own guidance is 4c/8 GB for the *full* demo stack with Reader+Browserless), and a stale
pre-rename `jianjungki/searcrawl-app` image (550 MB, Chromium-bundled) exists but is
unofficial.

**Re-evaluation outcome (this pass): TrailSearch stays chosen.** OrioSearch **still has no
LICENSE file** on either `master` or `main` (verified twice this pass, incl. a recursive tree
scan), so the license blocker stands — it is not eligible for an owned estate dependency.
Nothing else changed the fundamentals: TrailSearch remains the only candidate that is both
native-`/tavily/*` **and** cleanly licensed **and** runnable minimal. fastCRW stays the ranked
`emulated` Firecrawl-class fallback (still the lightest by far at ~14 MB idle);
Crawl4AI/Meilisearch stay OVH-only (too heavy for the box).

| candidate | stars / last push | license | Tavily shape | stack / deps | idle RAM (minimal) | verdict |
|---|---|---|---|---|---|---|
| **TrailSearch** (`jianjungki/tavily-open`) | 31 / 2026-07-27 | **MIT** (LICENSE present) | **native** `/tavily/search` + `/tavily/extract` | FastAPI + trafilatura + crawl4ai lib; SearXNG; SQLite index; Redis optional | ~270–320 MB app (http_first, no Reader/browser) | **CHOSEN** — only candidate with the exact required routes, clean MIT, runs minimal |
| OrioSearch (`vkfolio/orio-search`) | 42 / 2026-06-07 | **none** (README badge says MIT, **no LICENSE file** — measured) | Tavily-*compatible* `/search` + `/extract` (not the `/tavily/*` namespace) | FastAPI + trafilatura + FlashRank (~4 MB ONNX); SearXNG; Redis | lighter than TrailSearch (no crawl4ai) | strong runner-up; **blocked on the missing license** — legal-hygiene risk for an owned estate |
| fastCRW (`us/crw`) | 907 / 2026-09-02 (v0.33.0) | AGPL-3.0 | **Tavily-*style*, adapter required** (Firecrawl-shaped `/v1/*`; `content`→`description`, `max_results`→`limit`, wraps in `{success,data}`) | single Rust binary; own search backend / SearXNG sidecar | **~6 MB binary, ~8 MB image** (vendor-documented) | best RAM by far, but not a Tavily drop-in and AGPL; ideal **Firecrawl-class scraper** and a future `emulated` adapter |

**Why TrailSearch wins for the Tavily-compatible slot.** It is the *only* candidate whose
routes are already the Tavily contract (so the adapter is `native`, not a shape
translation), it is cleanly **MIT with a real LICENSE file**, and it runs in a genuinely
minimal profile (SearXNG + trafilatura, no Redis/Reader/browser). OrioSearch is lighter and
close, but committing an estate dependency on a repo **with no license file** is a
non-starter until upstream adds one — recorded as a re-evaluation trigger (§8). fastCRW is
the RAM champion and the right **Firecrawl replacement**, but it is Firecrawl-shaped; wiring
it as the Tavily lane would mean an `emulated` translation adapter, which we keep as a
ranked fallback the interface already supports.

> Honesty note on stars: TrailSearch has few stars (31). It was chosen on **fit + license +
> footprint**, not popularity; the adapter isolates us from it (swap the base URL / subclass
> to move to fastCRW or OrioSearch without touching the hub).

### 3b. Firecrawl-class scraper (the "clean content from a URL" engine)

| candidate | license | RAM (documented) | note |
|---|---|---|---|
| **fastCRW** | AGPL-3.0 | ~6–8 MB binary; browser sidecar only when needed | best minimal scraper; Firecrawl-compatible `/v1/scrape,crawl,map` |
| Crawl4AI (`unclecode/crawl4ai`) | Apache-2.0 | base **270 MB** + permanent browser **270 MB** + **180 MB**/pooled browser; docs recommend **4 GB** | powerful, but browser-heavy — wrong default for this box |
| TrailSearch built-in extraction | MIT | included in the ~300 MB app (http_first) | good enough for the Tavily lane without a separate scraper |

**Recommendation:** keep TrailSearch's `http_first` trafilatura extraction as the default
(no extra daemon). Add **fastCRW** as an optional `emulated` scraper adapter when JS-rendered
pages are needed — it is far lighter than Crawl4AI. Reserve **Crawl4AI** for an OVH host only
(§6), never as an always-on local daemon.

### 3c. Local index

| candidate | RAM (documented) | note |
|---|---|---|
| **SQLite FTS** (TrailSearch built-in) | negligible (in-process) | **chosen** — already in the app; content reuse with zero extra daemon |
| Meilisearch (`meilisearch/meilisearch`) | 50–100 MB idle; **1 GB recommended** <100k docs | defer — only worth a daemon if a large, cross-session semantic/typo-tolerant index is needed; better on OVH |

### 3d. Keyless search primitives already present / stale

- **SearXNG** — already the keyless fallback in `search-hub` and already deployed at
  `127.0.0.1:8890`. The self-hosted lane **reuses** it (no second instance).
- **agent-search** (`SciPhi-AI/agent-search`) — 554 stars but **last pushed 2024-04**;
  stale. Lattice state for a would-be adapter: **`absent`** (not wired). Recorded, not built.

### 3e. Dark-web lanes (authorized-research only; behind a legal/safety envelope)

| candidate | stars / last push | license | shape | note |
|---|---|---|---|---|
| **Sicry** (`JacobJandon/Sicry`) | 19 / 2026-07-01 | **Apache-2.0** | single file, **built-in MCP server** (`sicry_search`, `sicry_check_engines`, …), 18 onion engines, Tor circuit rotation | cleanest MCP integration point for an MCP-first estate |
| OnionClaw (`christinminor459/OnionClaw`) | 234 / 2026-08-31 | NOASSERTION | OpenClaw skill + standalone; wraps the **Sicry** engine | more visible, but license unclear and it is a skill wrapper over Sicry |
| Robin (`apurvsinghgautam/robin`) | 6924 / 2026-08-25 | **MIT** | Streamlit web UI + Docker; LLM-refined onion OSINT | the well-known tool; UI-first, heavier (Streamlit) |
| Ahmia (`ahmia/ahmia-site`) | 766 / 2026-08-21 | BSD-3 | clearnet `.onion` search + a public **banned/blacklist** (md5 of banned onions) + `banned_terms.map` | the filtering primitive, not an agent |
| Haystak | — | — | onion-only dark-web index (no public API) | reach only via Tor; no clean integration surface |

**BUILT 2026-09-02 — but deliberately NARROWER than the table above.** The onion lane that
shipped is **Ahmia index querying via the existing SearXNG provider**, index-only, no Tor,
no MCP daemon, no onion fetch (see §7, §8, and [`docs/legal/onions-lane-envelope.md`](../legal/onions-lane-envelope.md)).
The Sicry/Robin/OnionClaw agents in the table would add a **Tor daemon + onion fetching +
scraping**, which is **out of the current envelope** — they require a *new* decision record
and a fresh owner sign-off before any code. What we built:

1. **Default ON, ask-before-search (owner amendment 2026-09-02)** — the lane works by default
   but `onions.py::onion_decision` returns an `ask` (a confirmation request, not an error) for
   any onion-intent `searxng_web_search` until the caller re-invokes with `onion_confirm=true`
   + `onion_mode` (`low|medium|high|deepest`, index breadth only). `ENABLE_ONIONS=0` is a hard
   kill switch. Confirmed results are tagged with a `TOR / DARK-WEB INDEX` banner + an `_onion`
   marker so they are clearly differentiated from normal web results. Decisions happen at the
   hub (no child spawned on ask/forbid/killed).
2. **Index-only, inherits Ahmia's filtering** — the query hits the Ahmia index; Ahmia's own
   abuse blacklist ([ahmia.fi/blacklist](https://ahmia.fi/blacklist/)) applies by
   construction and we never filter around it. Results are titles + indexed metadata + the
   `.onion` URL as a string.
3. **No Tor, no onion fetch** — the SearXNG engine is pinned to **clearnet ahmia.fi** with no
   proxy; `web_url_read` of any `.onion` host is refused **regardless of the flag**. The lane
   fails closed rather than reaching for Tor.
4. **Jurisdiction disclaimer + sign-off** — carried in the envelope doc (owner fills the
   sign-off before enabling).
5. **Verified finding** — `ahmia.fi` clearnet 302-redirects datacenter/bot queries to its
   homepage, so live result verification must happen on the estate instance (residential IP);
   SearXNG upstream defaults the Ahmia engine to the `.onion` (Tor) — we do not use that.

**RAM: ≈ 0 MB** — config + a pure hub guard; no new process, no new container.

### 3f. Repository-discovery lane (a hub lane, not a search backend)

| source | shape | integration |
|---|---|---|
| **OSSInsight** (`pingcap/ossinsight`, Apache-2.0) | public REST/GraphQL (`api.ossinsight.io`, live 200) + **`mcp-ossinsight`** (MIT, small) | best programmatic lane; front the public API as an `emulated` adapter (no key) |
| best-of-python / best-of-ml-python (`lukasmasuch/*`, CC-BY-SA-4.0) | static ranked Markdown lists, updated weekly | fetch + parse; `declared` until fetched |
| bestofjs (`bestofjs/bestofjs`, MIT) | static site + backend | same shape |
| awesome-lists | static Markdown | same shape |

**BUILT 2026-09-02.** A keyless `OSSInsightAdapter` fronts the OSSInsight **public API** (no
key, in-process HTTP, **RAM ≈ 0**), default OFF behind `ENABLE_OSSINSIGHT`. Endpoint
verification came first (§3g): the API is **partially degraded** — `GET /gh/repo/{owner}/{repo}`
(repo stats) and `GET /v1/collections/` (138 curated collections) return live 200, while the
event-derived rankings are `data_quality: unavailable` since 2026-03-01 and `/v1/repos/...`
500s. The adapter builds only on the two working endpoints and **relays the API's own
`data_quality` note verbatim** for the ranking tool (truthful degradation, never faked). The
curated static lists (best-of-python, bestofjs, awesome-lists) remain a future `declared`
secondary source (§8).

### 3g. OSSInsight endpoint verification (live, 2026-09-02 — never hardcode an unverified path)

| endpoint | method | status | used? |
|---|---|---|---|
| `/gh/repo/{owner}/{repo}` | GET | **200** — GitHub repo object (stars/forks/language/topics) | **yes** → `ossinsight_repo_stats` |
| `/v1/collections/` | GET | **200** — `{data:{rows:[{id,name}]×138}}` | **yes** → `ossinsight_collections` |
| `/v1/collections/{id}/ranking_by_{stars,prs}/` | GET | **200 but empty** + `data_quality:"unavailable"` (since 2026-03-01) | **yes, truthful passthrough** → `ossinsight_collection_ranking` |
| `/v1/repos/{owner}/{repo}` | GET | **500** | no (broken) |
| `/v1/collections/{id}/` | GET | **500** | no (broken) |
| `/v1/trends/repos/` | GET | 200 but `data_quality:"unavailable"` | no (degraded ranking) |

Finding recorded per the task's rule: the public API is **not down** (two data-bearing
endpoints work), so the lane proceeds on those; the ranking degradation is surfaced, not
worked around.

---

## 4. The capability lattice (the honesty contract)

Every self-hosted tool resolves to exactly one state. The vocabulary is fixed
(`adapters.LATTICE`), ordered most-confident-realized to least-available:

| state | meaning | when reported |
|---|---|---|
| `native` | the backend implements this tool's **exact contract** (TrailSearch `/tavily/*` IS the Tavily contract) | configured, backend kind is native, **not yet probed** this session |
| `probed` | a **live health GET this session** confirmed the backend answers | `search_usage {probe:true}` and the GET succeeded |
| `declared` | present only from committed config/cache; backend kind gives no contract guarantee | generic backend, unprobed |
| `emulated` | realized by **translating a differently-shaped backend** (fastCRW `/v1/*`, OrioSearch `/search`, Sicry, OSSInsight) | non-native backend kind, unprobed |
| `absent` | no base URL, or a probe found it unreachable/unhealthy | not configured, or probe failed |

Two axes are carried without conflating them: **state** (confidence/availability) and
**`realized_by`** (`native` vs `emulated` — *how* the tool is built), so a `probed` tool still
tells you whether its result shape is native or translated.

**Truthful degradation, enforced in code and pinned by tests:**

- `tools/list` and the default `search_usage` do **zero network** — the RAM-cheap path.
- `search_usage {probe:true}` does **one** GET per backend to upgrade to `probed`/`absent`.
- A `tools/call` **always** hits the real backend; on any failure (unconfigured, transport
  error, non-2xx) it returns an `isError` result whose text says the backend is unreachable
  and that **no results were fabricated** — and it leaks no fake URLs into the error. The
  test `test_call_when_backend_down_returns_truthful_error_not_fake_hits` asserts exactly this.

This mirrors the estate's existing honesty discipline (`_shared/hardening.py`, the
basic-memory bridge's cache-vs-error split) and the "degrade truthfully, never fake" rule.

---

## 5. RAM budget — ranked, and the minimal profile

Figures are **documented** (vendor/maintainer) or **measured**, tagged inline. The metric
that matters on this box is **private commit**, not RSS (`docs/mcp-consolidation-plan.md` §1a:
an RSS census understates the real cost ~19×).

| component | role | RAM (documented / measured) | in minimal profile? |
|---|---|---|---|
| `search-hub` process (stdlib) | the hub itself | **measured ~20–25 MB RSS / ~15–17 MB private** (stdlib json+urllib; same stack the basic-memory bridge measured at ~16–17 MB private) | **always** (already running) |
| self-hosted **adapter** (TrailSearch/OSSInsight) | in-process HTTP bridge | **~0 new** — no child, no new import (urllib already loaded); measured stdlib HTTP client roundtrip adds ~1 MB transient | **always** (part of the hub) |
| **Ahmia onion lane** (via SearXNG) | index-only, ask-first, on the existing search tool | **≈ 0 MB** — config + a pure hub decision (`onions.py`); no new process/container | **default ON, ask-before-search** (`ENABLE_ONIONS=0` kill switch); reuses the estate SearXNG |
| **OSSInsight** repo-discovery | keyless public-API adapter | **≈ 0 MB** — in-process HTTP, same as the self-hosted adapter | **default OFF** (`ENABLE_OSSINSIGHT=0`); no daemon (public API) |
| estate **SearXNG** (reused) | keyless meta-search | ~150 MB idle at `UWSGI_WORKERS=1`; ~250 MB active; **~500 MB/core by default** (documented; discussion #1892 / issue #1431) | **reused** — already running for `search-expansion`, not re-run |
| **TrailSearch app** | Tavily-shaped search+extract | **~270–320 MB** (FastAPI + trafilatura, `http_first`; crawl4ai lib imported but no browser launched) | **on-demand** (start when you want keyless search) |
| Redis | cache / backfill queue | ~10–50 MB (alpine) | **off** (`CACHE_ENABLED=false`, `BACKFILL_QUEUE_BACKEND=local`) |
| Reader (jina) | high-quality extraction | ~200–400 MB | **off** |
| Browserless / Chromium | JS rendering | ~300–500 MB+/session | **off** |
| Crawl4AI (if used) | Firecrawl-class scraper | base **270 MB** + browser **270 MB** + **180 MB**/pool (docs: **4 GB**) | **off** — OVH only |
| fastCRW (if used) | lighter scraper | **~6–8 MB** (vendor-documented) | optional, tiny |
| Meilisearch (if used) | large local index | **50–100 MB idle**, 1 GB rec. <100k docs | **off** — defer / OVH |
| Tor + Sicry (dark-web) | onion search | Tor ~20–40 MB + python ~30–50 MB | **off** — authorized-research, on-demand |

**Minimal local profile (which daemons MUST run vs on-demand):**

- **Must run for keyless search:** the hub (already up) + **TrailSearch app** (~300 MB) +
  a SearXNG (reuse the estate's ~150 MB — **0 marginal**). → **~300 MB marginal** for a
  full keyless Tavily-equivalent search+extract.
- **On-demand, off by default:** Redis, Reader, Browserless, Crawl4AI, Meilisearch, Tor/Sicry.
- **Safe-inert:** if TrailSearch is not running, `selfhosted_*` returns a truthful `isError`;
  the keyed providers and keyless SearXNG are unaffected.

**Guardrails:** the compose sets `mem_limit` per container (app 768 MB, SearXNG 384 MB) so a
runaway crawl cannot starve the box, and pins SearXNG to `UWSGI_WORKERS=1`.

### OVH-server alternative (move the daemons off the box entirely)

The estate's `cloud-hub` already fronts **OVHcloud** with region rotation and
`ovh_ssh_exec` / `ovh_api_raw` (Public Cloud incl. GPU). Run the whole daemon lane on an OVH
VPS and point the hub at it — **no hub code change**, only `TRAILSEARCH_URL`:

| profile | OVH shape | fits |
|---|---|---|
| search+extract | VLE-2 / VPS-2 (2 vCPU, **4 GB**) | SearXNG (150 MB) + TrailSearch (300 MB) + Meilisearch small (100 MB) with headroom |
| + JS scraping | VPS-4 (4 GB+) or a Public Cloud instance | add fastCRW (tiny) or Crawl4AI (needs the 4 GB) |
| + dark-web (authorized) | isolated VPS with Tor | keep the onion lane off the personal box for opsec |

Reach it over a private link (WireGuard / SSH tunnel via `ovh_ssh_exec`), set
`TRAILSEARCH_URL=http://<private-ip>:8794`, and the adapter's lattice reports `probed` once
the tunnel is up. This is the recommended end-state for the memory-starved box: **~0 local
RAM beyond the hub**, all daemons on OVH.

---

## 6. Chosen architecture (what this reunion looks like)

```
             one MCP registration: search-hub  (stdlib, ~15-17 MB private, always up)
                        |
   +--------------------+---------------------------------+-------------------------+
   | keyed, rotated (stdio children, lazy)                | keyless direct          | keyless self-hosted (NEW)
   |   Exa / Tavily / Firecrawl                           |   SearXNG (stdio child)  |   selfhosted_search / _extract
   |   per-key rotation + cooldown + search_usage         |   never cooled           |   in-process HTTP adapter
   +------------------------------------------------------+-------------------------+-------------------------+
                                                                                     |  urllib (no child)
                                                                                     v
                                                          TrailSearch daemon (on-demand, ~300 MB)
                                                             /tavily/search  /tavily/extract
                                                                     |
                                                          estate SearXNG :8890 (reused) + SQLite index
```

- The keyed + keyless-SearXNG lanes are **unchanged** (44 baseline tests still green).
- The new lane is a **third kind**: keyless, self-hosted, HTTP-backed, **in-process** — no
  child spawned, so `tools/list` stays instant and idle RAM is unchanged.
- Tool names are prefixed `selfhosted_` so they **never collide** with the keyed `tavily_*`
  provider; both coexist and a caller picks the keyless lane when it wants no vendor key.
- The adapter is backend-agnostic: `TrailSearchAdapter` is `native`; a `fastCRW`/`OrioSearch`/
  `Sicry`/`OSSInsight` subclass would be `emulated`, same interface, same honesty contract.

---

## 7. What shipped on this branch (built, tested)

**Wave 1 — the keyless Tavily lane (TrailSearch):**

- **`tools/mcp/search-hub/adapters.py`** — the `SelfHostedAdapter` interface (capability
  lattice + probe + truthful-degradation `handle_call`; GET/POST via `_prepare`/`_postprocess`)
  and the `TrailSearchAdapter` (`selfhosted_search` → `POST /tavily/search`, `selfhosted_extract`
  → `POST /tavily/extract`; base URL from `TRAILSEARCH_URL` / `SELFHOSTED_SEARCH_URL`, default
  `127.0.0.1:8794`). Stdlib only.
- **`hub.py` wiring** — the adapter lane merged into `tools/list`, a `_handle_adapter`
  dispatch branch, and the lattice folded into `search_usage` (with `probe`).
- **`deploy/`** — `docker-compose.selfhosted-search.yml` (minimal + `bundled` profiles),
  `run-selfhosted-search.{sh,ps1}`, `env.minimal.example`, `searxng-min/settings.yml`, a
  Docker-free smoke, and a README.

**Wave 2 — the two §8 follow-up lanes, both default OFF (this iteration):**

- **Ahmia onion lane** — `onions.py` (the envelope guard) + `hub.py` wiring: the Ahmia index
  is a `categories=onions` parameter on the existing `searxng_web_search` tool (not a new tool
  or service), refused at the hub unless `ENABLE_ONIONS=1`; `.onion` fetch via `web_url_read`
  is refused regardless of the flag. `deploy/searxng-min/settings.yml` enables the built-in
  Ahmia engine pinned to **clearnet** with no Tor proxy (fails closed). Envelope:
  [`docs/legal/onions-lane-envelope.md`](../legal/onions-lane-envelope.md). **≈ 0 MB.**
- **OSSInsight repo-discovery lane** — `OSSInsightAdapter` in `adapters.py`
  (`ossinsight_repo_stats` / `_collections` / `_collection_ranking` on the live-200 endpoints,
  §3g), wired only when `ENABLE_OSSINSIGHT=1`. Truthful `data_quality` passthrough. **≈ 0 MB.**

**Tests / fakes** — stdlib fakes for every external service (`fake_trailsearch_backend.py`,
`fake_ossinsight_backend.py`) and a pure guard for onions; `test_adapters.py`, `test_onions.py`,
`test_ossinsight.py`, and hub integration tests incl. real loopback-socket cases and the
flag-off gate tests. **Suite 44 → 92 passed; `ruff check` + `ruff format --check` clean; both
lane flags default 0; zero new containers, zero new long-running processes.**

### 7a. Finding: SearXNG config beats a new adapter for the onion lane

The onion lane needed **no new code path in the provider layer**. Because the fronted
`mcp-searxng` `searxng_web_search` tool already accepts `categories`/`engines` passthrough,
enabling the Ahmia engine in SearXNG's `settings.yml` makes `categories=onions` reachable
**by config alone** — the only code is a small, pure hub-side *guard* (`onions.py`) that
gates it behind `ENABLE_ONIONS` and blocks `.onion` fetches. This is strictly cheaper and
safer than a bespoke onion adapter/daemon: ~0 MB, no new tool, no new service, and the
control point is one testable function. General rule recorded for future lanes: **prefer a
config + hub-guard exposure of an already-fronted capability over a new adapter or backend.**

---

## 8. Follow-up work list — the `ast-searchhub` merge (a later lane)

**Done since the first draft (this branch):**

- ✅ **Ahmia onion lane** — built as the index-only, `ENABLE_ONIONS`-gated SearXNG category
  (§3e, §7). Was the "Sicry dark-web lane" bullet below; we shipped the *narrower*,
  envelope-compliant version (no Tor/MCP-daemon). Sicry/Robin remain out-of-envelope.
- ✅ **OSSInsight repo-discovery lane** — built as `OSSInsightAdapter`, `ENABLE_OSSINSIGHT`-gated
  (§3f, §3g, §7). Was part of the "second-wave adapters" bullet.

Ordered remaining; each step is resumable and tests-first. **The `ast-searchhub` merge below
is NOT done** (the sibling is not reachable from this VM).

1. **Locate + fingerprint the sibling.** On the box, find the `ast-searchhub` checkout;
   record `git status --porcelain -uall`, unpushed commits (`git log @{u}..`), and the
   `search-hub` file hashes vs this branch. Push any unpushed sibling commits to a rescue
   branch **before** touching it (the doctrine's push-before-exit rule).
2. **Three-way diff** the sibling's `search-hub/{hub,providers,rotation,usage}.py` and
   `_shared/accounts.py` against their common ancestor and this canonical branch. Produce a
   per-hunk table: canonical-wins / sibling-wins / genuine-conflict.
3. **Port sibling improvements tests-first.** For each sibling-wins hunk, write a failing
   test against canonical, then port the behaviour. Never take a hunk without a test.
4. **Fold any sibling keyless experiment into `adapters.py`** as a backend subclass (native or
   emulated) — do **not** re-introduce a parallel mechanism.
5. **Regenerate caches on the box** (`hub.py --refresh`), never hand-merge `caches/*.json`.
6. **Retire the sibling `search-hub`** only after its work is on a pushed branch and the
   canonical suite is green (the four-part retire predicate in `CLAUDE.md`).
7. **Registry reunion.** Update `~/.mcp.json` / `.agents/agents.json` so the single canonical
   `search-hub` is the only search entry; drop the standalone `exa/tavily/firecrawl/searxng`
   entries (README already documents this owner-approved step).
8. **Second-wave adapters still open** (each behind the lattice, each with a fake + tests):
   fastCRW as an `emulated` scraper; the OSSInsight curated static lists (best-of-python,
   bestofjs, awesome-lists) as a `declared` secondary discovery source; optionally Meilisearch
   and OrioSearch **iff upstream adds a LICENSE file** (the re-evaluation trigger). The Sicry
   Tor lane is intentionally **out of the current envelope** — it needs a new decision record
   + owner sign-off (§3e).
9. **OVH end-state (optional).** Stand the daemon lane up on an OVH VPS via `cloud-hub`
   (`ovh_ssh_exec`), tunnel it, and set `TRAILSEARCH_URL` to the private endpoint — moving
   ~300 MB–2 GB off the 31.6 GB box with no hub code change.

### Re-evaluation triggers (revisit this decision if…)

- OrioSearch adds a real LICENSE file → reconsider it as the lighter Tavily lane.
- TrailSearch goes unmaintained (watch its ref) → swap the adapter base to fastCRW
  (`emulated`) or OrioSearch.
- The box gains RAM / the lane moves to OVH → Crawl4AI + Meilisearch become viable defaults.
