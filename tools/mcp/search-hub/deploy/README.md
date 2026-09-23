# Deploy: the keyless self-hosted search backend

These files stand up **TrailSearch** (github `jianjungki/tavily-open`, MIT) — the
daemon behind search-hub's keyless `selfhosted_search` / `selfhosted_extract`
tools. The hub adapter is in-process and pure stdlib; this is the one heavy piece,
and it is **on-demand**: start it when you want key-free search, stop it to reclaim
the RAM. Until it answers, the `selfhosted_*` tools return a truthful `isError`
(never a fabricated hit), so the lane is safe-inert exactly like keyless SearXNG.

TrailSearch is **not vendored** in this repo (separate MIT project). The run
scripts clone it to `deploy/trailsearch-src/` at a pinned ref and build from there.

## Minimal profile (recommended on the 31.6 GB box)

Reuses the estate's existing SearXNG (`127.0.0.1:8890`, already run for
`tools/search-expansion`), so the only new daemon is the app container.

```bash
# Linux / WSL
cd tools/mcp/search-hub/deploy
./run-selfhosted-search.sh up        # clone+build+start app on 127.0.0.1:8794, smoke it
```

```powershell
# Windows
cd tools\mcp\search-hub\deploy
.\run-selfhosted-search.ps1 -Action up
```

Then point the hub at it (already the default) and restart the session:

```
setx TRAILSEARCH_URL http://127.0.0.1:8794      # or leave unset -- 8794 is the default
```

`search_usage {"provider":"selfhosted","probe":true}` should now report every
`selfhosted_*` tool as **`probed`**.

## Self-contained profile (box with no existing SearXNG)

Adds a local SearXNG pinned to `UWSGI_WORKERS=1` (~150 MB idle instead of
~500 MB/core):

```bash
./run-selfhosted-search.sh up --bundled
```

## What runs, and the RAM it costs

| Service | When | RAM (documented) | Notes |
|---|---|---|---|
| `app` (TrailSearch) | always | ~270–320 MB | FastAPI + trafilatura; `mem_limit` 768 MB |
| estate SearXNG (reused) | minimal | already running | shared with search-expansion |
| bundled SearXNG | `--profile bundled` | ~150 MB idle | `UWSGI_WORKERS=1`; `mem_limit` 384 MB |
| Redis / Reader / Browserless | **never (minimal)** | 0 | disabled: `CACHE_ENABLED=false`, `http_first` |

So the minimal marginal cost on the estate is **one ~300 MB container**; the
self-contained cost is **~450 MB**. Full RAM budget and the OVH-server alternative
are in `docs/plans/2026-09-02-search-stack-reunion.md`.

## Validate without Docker

`smoke_selfhosted_no_docker.py` proves the adapter + hub path end to end against a
stdlib fake backend — no Docker, no SearXNG, no network:

```bash
cd tools/mcp/search-hub
python deploy/smoke_selfhosted_no_docker.py     # exit 0 = keyless lane works
```

## Files

- `docker-compose.selfhosted-search.yml` — app (always) + SearXNG (`bundled` profile).
- `env.minimal.example` — the key-free minimal env; copy to `.env` (which is gitignored).
- `searxng-min/settings.yml` — minimal SearXNG config (JSON format enabled) plus
  the Wave-1 default-mix flips — `google` **off** (keyless Google scraping is dead),
  `mwmbl` + `marginalia` **on** (`api_key: public`, rate-limited) — and the two
  clearnet onion-INDEX engines `ahmia` + `vormweb` under category `onion index`
  (see `docs/legal/onions-lane-envelope.md`). Engine changes load on a SearXNG
  **restart** only. Pinned by `tests/test_deploy_settings.py`.
- `run-selfhosted-search.{sh,ps1}` — clone/pin/build/up + real-daemon smoke.
- `smoke_selfhosted_no_docker.py` — Docker-free adapter/hub smoke.
- `docker-compose.answer-engines.yml` — the opt-in answer engines (see below): `vane`,
  `ldr` and `ollama-evict`, every one behind a profile, capped, loopback-only.
- `run-answer-engines.{sh,ps1}` / `stop-answer-engines.{sh,ps1}` — profile-selecting
  up/down (`--vane`, `--ldr`, `--ollama`) with a Docker-free `--print` mode.

## Secrets

None. This lane is keyless by design. The base URL is **config, not a secret**.
The only optional key TrailSearch can take (Brave fallback) is left **off**; if you
ever enable it, reference the key **by name from `.agents/local.json`** and inject
it at runtime — never inline it in `.env` or a manifest. The same holds for the
answer engines below: the hub only ever sees `VANE_URL` / `LDR_URL`; any LLM
credential Vane or LDR might hold for a cloud provider lives in *their* data volumes,
never in this repo — and the intended setup (Ollama on the box) needs none.

## Answer engines (opt-in, on-demand): `docker-compose.answer-engines.yml`

Program decisions G-2 / G-4 / G-5 (`docs/plans/2026-09-02-search-research-tools-gemhunt.md`,
Wave 3): heavy, LLM-backed engines are **permitted on the box, opt-in, started on
demand and evicted on demand**, and the hub reaches them through endpoint-agnostic
`*_URL`s. Accordingly **nothing in this compose file starts by default** — every
service sits behind a profile, so the idle cost is 0 RAM, and the hub's `answer`
lane is **OFF** until `ENABLE_VANE=1` (or a non-empty `VANE_URL`) is set. Until an
engine answers, its tools return a truthful `isError` (never a fabricated answer).

| Profile | Service / image (pinned, verified 2026-09-02) | Port (loopback only) | RAM cap | What it gives the hub |
|---|---|---|---|---|
| `--vane` | Vane `itzcrazykns1337/vane:slim-v1.12.2` (ex-Perplexica, MIT) | `127.0.0.1:${VANE_PORT:-3000}` | `768m` | `selfhosted_answer`: a cited LLM answer over the estate SearXNG (`lane_answer.py`) |
| `--ldr` | local-deep-research `localdeepresearch/local-deep-research:1.10.7` (MIT) | `127.0.0.1:${LDR_PORT:-5000}` | `2g` | LDR's web UI + REST API (`/api/v1/health`, `/api/v1/quick_summary`, …) for browsing / HTTP use — **not** the hub's LDR MCP path, which is STDIO on the host (see below) |
| `--ollama` | Ollama `ollama/ollama:0.33.2` with **`OLLAMA_KEEP_ALIVE=0`** | `127.0.0.1:${OLLAMA_PORT:-11434}` | `16g` | an *evicting* LLM daemon — only for a box with **no** host Ollama |

**Why the slim Vane image.** Vane also publishes an all-in-one image that bundles its
own SearXNG behind uwsgi with `workers=%k` (one worker per core, ~500 MB/core) on an
unpinned SearXNG. The slim image (`Dockerfile.slim` at `v1.12.2`: `node server.js`,
port 3000, data in `/home/vane/data`) has none of that and simply points at the
estate SearXNG through `SEARXNG_API_URL` (default `http://host.docker.internal:8890`,
override `VANE_SEARXNG_API_URL`). Docker Hub, 2026-09-02: slim `578 MB` vs bundled
`3,914 MB` (amd64, compressed). Vane seeds that URL into `data/config.json` **once**
(only while unset); after that its Settings page owns it.

**Why `GET /api/providers` first.** Vane mints every provider id with
`crypto.randomUUID()` at seed time, so the ids **drift** between installs and
re-installs. The hub therefore resolves chat/embedding provider+model on **every
call** (cached 60 s), accepts *names* as well as ids, picks the first available pair
when the caller passes none, and **reports** what it used (`providers_used`). If the
Ollama at `VANE_OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`) is
unreachable, Vane filters that provider out of `/api/providers`; the hub then says
"no chat model configured" — truthfully. Vane ships a keyless in-process
Transformers **embedding** provider (~200 MB when used), so only the *chat* model has
to come from Ollama.

**RAM cost, honestly labelled.** The caps are per-container ceilings, not
measurements: Vane slim est. 250–450 MB + ~200 MB embedder (Lens 4) → `768m`; LDR
`2g` is this kit's headroom for a Flask + SQLCipher app whose LLM lives elsewhere;
the Ollama cap is about the model (8–16 GB for a 7–14B model), which is exactly why
**`OLLAMA_KEEP_ALIVE=0`** matters: the model leaves RAM the moment an answer is done
(G-2 eviction). A *host* Ollama is outside this file — give it the same policy
(`setx OLLAMA_KEEP_ALIVE 0`, restart Ollama). Upstream LDR's compose ships `30m`,
i.e. half an hour of a resident model after every answer; not here.

```bash
cd tools/mcp/search-hub/deploy
./run-answer-engines.sh up --vane            # Vane only; smokes GET /api/providers
./run-answer-engines.sh up --vane --ldr      # both engines
./run-answer-engines.sh up --vane --print    # resolved env + exact compose command, NO Docker
./stop-answer-engines.sh                     # down for every profile -> RAM reclaimed
```

```powershell
cd tools\mcp\search-hub\deploy
.\run-answer-engines.ps1 -Action up -Vane
.\run-answer-engines.ps1 -Action up -Vane -Ldr -Print
.\stop-answer-engines.ps1
```

Then flip the hub flags (a restart of the hub session picks them up):

```
# on-box
export ENABLE_VANE=1 VANE_URL=http://127.0.0.1:3000   # VANE_TIMEOUT_S=120 is the LLM budget/answer
export ENABLE_LDR=1                                   # LDR MCP ProviderSpec (providers.py): ldr-mcp over STDIO on the host
# OVH repoint (G-4): same hub, one line, nothing else changes
export VANE_URL=https://vane.your-ovh-box.example     # LDR_URL=https://…/mcp likewise, for a resident ldr-mcp gateway
```

`search_usage {"provider":"answer","probe":true}` then reports `selfhosted_answer` as
**`probed`** (Vane answered `/api/providers`) or **`absent`** with the reason.

**`ENABLE_LDR=1` + `LDR_URL` are the hub flags for the LDR MCP**, exposed by the LDR
MCP ProviderSpec (owned by the providers slice, `providers.py`), and they do **not**
point at this container. Upstream's MCP server `ldr-mcp` is a **STDIO-only** console
script of `local-deep-research[mcp]` with the engine in-process, so `ENABLE_LDR=1`
makes the hub run `uvx --from "local-deep-research[mcp]==1.10.7" ldr-mcp` on the
host; `LDR_URL` is read only when an operator has fronted a *resident* `ldr-mcp`
with a Streamable-HTTP gateway of their own (`npx -y mcp-remote $LDR_URL` bridges to
it). The `--ldr` container is therefore a second, independent LDR install — its web
UI + REST API on `LDR_PORT`, for browsing and HTTP callers — sharing the same Ollama
and SearXNG; the same `LDR_*` setting names (`LDR_LLM_OLLAMA_URL`,
`LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL`, with `127.0.0.1`
addresses) point the host `ldr-mcp` at them too, through the inherited environment.

**Not verified here.** The authoring VM has no Docker, so this compose file has
**not been run**: image pulls, container start, and the real `/api/search` round
trip are unexercised. What *is* pinned by `tests/test_lane_answer.py`: the file parses, every
service is profiled + `mem_limit`-capped + loopback-only, the three tags above, the
run script's `--print` resolution and its refusal to start anything without a
profile, and the whole adapter contract against a loopback fake Vane
(`tests/fake_vane_backend.py`). First real run: `./run-answer-engines.sh up --vane`,
then `search_usage {"provider":"answer","probe":true}`.
