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

## Providers (package + env verified live 2026-07)

| Provider  | prefix | stdio launch                         | credential / config env           | usage endpoint                              | exhaustion signal |
|-----------|--------|--------------------------------------|-----------------------------------|---------------------------------------------|-------------------|
| Exa       | `ex`   | `mcp-remote` → Exa HTTP MCP          | `EXA_API_KEY`                     | **none** (no balance API) → error-driven    | HTTP 402 `NO_MORE_CREDITS` / `API_KEY_BUDGET_EXCEEDED` |
| Tavily    | `tv`   | `npx -y tavily-mcp@latest`           | `TAVILY_API_KEY`                  | `GET /usage` → `plan_limit - plan_usage` (+ paygo) | explicit quota, or 429 → **probe /usage** |
| Firecrawl | `fc`   | `npx -y firecrawl-mcp@latest`        | `FIRECRAWL_API_KEY`               | `GET /v2/team/credit-usage` → `data.remainingCredits` | HTTP 402 "Insufficient credits" |
| SearXNG   | `sx`   | `npx -y mcp-searxng@1.8.0`          | `SEARXNG_URL` (config, not a key) | **none**                                    | **none** — keyless, never cooled |

On Windows the launchers run through `cmd /c npx …` (npx is a `.cmd` shim).

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
  (its routes *are* the Tavily contract); a fastCRW / OrioSearch / Sicry /
  OSSInsight subclass would be `emulated`, same interface and honesty contract.

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
  truthful-degradation `handle_call`) and `TrailSearchAdapter` (keyless, HTTP).
- `rotation.py` — per-key health, `pick_active`, `mark_exhausted`, the
  rotate-retry wrapper, and numbered-backup seeding.
- `usage.py` — stdlib `urllib` calls to the keyed providers' usage endpoints.
- `caches/*.json` — committed tool enumerations (regenerate with `--refresh`).
- `deploy/` — compose + run scripts for the minimal self-hosted profile, a
  Docker-free smoke, and the deploy README.
- `../_shared/accounts.py` — the shared multi-account store (one additive
  read-only helper, `env_for`, was added for per-key resolution).
