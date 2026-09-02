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
~0 RAM to the running hub. The `ast-searchhub` code merge and the dark-web / repo-discovery
lanes are scoped here as **follow-up work**, not implemented in this PR.

This is a design + groundwork record. What shipped in the PR: the adapter interface, the
`TrailSearchAdapter`, hub wiring, the compose + run scripts for the minimal profile, and
the tests/fakes (§7). Everything below the fold that is *not* in §7 is a plan.

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

**Legal / safety envelope (mandatory before ANY dark-web adapter is wired).** These lanes
are **not** built in this PR. When built, they must ship behind:

1. **Authorized-research gate** — off by default; a `tools/list` that does not advertise the
   onion tools unless an explicit `DARKWEB_RESEARCH_AUTHORIZED=1`-style opt-in is present,
   surfaced in `search_usage` as `absent` until then.
2. **Ahmia-style content filtering** — apply Ahmia's published banned-onion blacklist and
   `banned_terms.map` to results; drop anything matching. No illegal-content retrieval.
3. **No autonomous action** — search/read only; never buy/post/exfiltrate (the OnionClaw
   README explicitly warns its `pipeline.py` is a full autonomous *operation* loop — we take
   only the read-only search/fetch primitives).
4. **Jurisdiction disclaimer** — the tool descriptions must carry the "may be illegal in your
   jurisdiction; Tor is opsec, not legal protection" warning both source tools already print.
5. **Tor is a daemon** — ~20–40 MB, but it is a network dependency; on-demand only.

Chosen integration point when the lane is built: **Sicry** (Apache-2.0, native MCP), fronted
as an `emulated` self-hosted adapter with the envelope above. Ahmia is the filter source.

### 3f. Repository-discovery lane (a hub lane, not a search backend)

| source | shape | integration |
|---|---|---|
| **OSSInsight** (`pingcap/ossinsight`, Apache-2.0) | public REST/GraphQL (`api.ossinsight.io`, live 200) + **`mcp-ossinsight`** (MIT, small) | best programmatic lane; front the public API as an `emulated` adapter (no key) |
| best-of-python / best-of-ml-python (`lukasmasuch/*`, CC-BY-SA-4.0) | static ranked Markdown lists, updated weekly | fetch + parse; `declared` until fetched |
| bestofjs (`bestofjs/bestofjs`, MIT) | static site + backend | same shape |
| awesome-lists | static Markdown | same shape |

**Recommendation:** a single keyless `repo_discovery` adapter fronting the OSSInsight public
API (RAM ~0 — it is an HTTP call like TrailSearch), with the curated static lists as a
secondary `declared` source. Follow-up (§8), not this PR.

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
| self-hosted **adapter** | in-process HTTP bridge | **~0 new** — no child, no new import (urllib already loaded); measured stdlib HTTP client roundtrip adds ~1 MB transient | **always** (part of the hub) |
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

## 7. What shipped in this PR (built, tested)

- **`tools/mcp/search-hub/adapters.py`** — the `SelfHostedAdapter` interface (capability
  lattice + probe + truthful-degradation `handle_call`) and the `TrailSearchAdapter`
  (`selfhosted_search` → `POST /tavily/search`, `selfhosted_extract` → `POST /tavily/extract`;
  base URL from `TRAILSEARCH_URL` / `SELFHOSTED_SEARCH_URL`, default `127.0.0.1:8794`). Stdlib
  only.
- **`hub.py` wiring** — the adapter lane merged into `tools/list`, a `_handle_adapter`
  dispatch branch, and the lattice folded into `search_usage` (with `probe`).
- **`deploy/`** — `docker-compose.selfhosted-search.yml` (minimal + `bundled` profiles),
  `run-selfhosted-search.{sh,ps1}`, `env.minimal.example`, `searxng-min/settings.yml`, a
  Docker-free smoke, and a README.
- **Tests / fakes** — `tests/fake_trailsearch_backend.py` (stdlib fake for the external
  service), `tests/test_adapters.py` (15), and new hub integration tests, incl. a real
  loopback-socket case. **Suite 44 → 63 passed; `ruff check` + `ruff format --check` clean.**

---

## 8. Follow-up work list — the `ast-searchhub` merge (a later lane)

Ordered; each step is resumable and tests-first. **None of this is done in this PR.**

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
8. **Second-wave adapters** (each behind the lattice, each with a fake + tests): fastCRW as an
   `emulated` scraper; the Sicry dark-web lane **behind the §3e legal/safety envelope**
   (authorized-research opt-in, Ahmia filtering, read-only, jurisdiction disclaimer); the
   OSSInsight repo-discovery lane; optionally Meilisearch and OrioSearch **iff upstream adds a
   LICENSE file** (the re-evaluation trigger).
9. **OVH end-state (optional).** Stand the daemon lane up on an OVH VPS via `cloud-hub`
   (`ovh_ssh_exec`), tunnel it, and set `TRAILSEARCH_URL` to the private endpoint — moving
   ~300 MB–2 GB off the 31.6 GB box with no hub code change.

### Re-evaluation triggers (revisit this decision if…)

- OrioSearch adds a real LICENSE file → reconsider it as the lighter Tavily lane.
- TrailSearch goes unmaintained (watch its ref) → swap the adapter base to fastCRW
  (`emulated`) or OrioSearch.
- The box gains RAM / the lane moves to OVH → Crawl4AI + Meilisearch become viable defaults.
