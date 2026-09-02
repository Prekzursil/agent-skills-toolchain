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
- `searxng-min/settings.yml` — minimal SearXNG config (JSON format enabled).
- `run-selfhosted-search.{sh,ps1}` — clone/pin/build/up + real-daemon smoke.
- `smoke_selfhosted_no_docker.py` — Docker-free adapter/hub smoke.

## Secrets

None. This lane is keyless by design. The base URL is **config, not a secret**.
The only optional key TrailSearch can take (Brave fallback) is left **off**; if you
ever enable it, reference the key **by name from `.agents/local.json`** and inject
it at runtime — never inline it in `.env` or a manifest.
