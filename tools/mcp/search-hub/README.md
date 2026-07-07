# search-hub — a rotating MCP multiplexer for Exa · Tavily · Firecrawl

`search-hub` fronts the three official **stdio** search MCP servers behind ONE MCP
registration, keeps every tool under its ORIGINAL name, and adds **transparent
API-key rotation** on top. When a provider key hits its hard billing-period
limit, the hub cools that key, rotates to a backup key, and retries the same call
once — so a research session doesn't stall on a single exhausted key.

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
- **SG-2 — reactive rotation.** No background probing. On a provider's
  **hard-exhaustion** error the hub rotates to the next non-cooled key and
  **retries the same call once**; if all keys are cooled, it returns the
  provider's native error unchanged. An **on-demand** `search_usage` tool reports
  remaining balance + cooldown state when you ask for it.
- **SG-3 — paid keys, long cooldown.** On **true exhaustion** (HTTP 402) a key is
  cooled **until the billing period resets** (seconds to the next UTC month
  boundary, or a `SEARCH_HUB_EXHAUST_COOLDOWN_S` override). On a **429 rate
  limit** the key is **NOT** cooled — the native error (carrying `Retry-After`)
  is returned so the caller backs off. Rotation is for **paid / legitimate
  multi-key** setups, not for evading a single free tier.

Auto-rotation is transparent and per-invocation; it **never** flips a global
active pointer (which would yank concurrent calls). Manual `*_account_switch` /
`*_account_cycle` remain the only deliberate active-key changes (and they un-cool
the chosen key, so a manual choice wins over an earlier auto-cooldown).

---

## Providers (package + env verified live 2026-07)

| Provider  | prefix | stdio launch                         | API-key env          | usage endpoint                              | exhaustion signal |
|-----------|--------|--------------------------------------|----------------------|---------------------------------------------|-------------------|
| Exa       | `ex`   | `npx -y exa-mcp-server`              | `EXA_API_KEY`        | **none** (no balance API) → error-driven    | HTTP 402 `NO_MORE_CREDITS` / `API_KEY_BUDGET_EXCEEDED` |
| Tavily    | `tv`   | `npx -y tavily-mcp@latest`           | `TAVILY_API_KEY`     | `GET /usage` → `plan_limit - plan_usage` (+ paygo) | explicit quota, or 429 → **probe /usage** |
| Firecrawl | `fc`   | `npx -y firecrawl-mcp@latest`        | `FIRECRAWL_API_KEY`  | `GET /v2/team/credit-usage` → `data.remainingCredits` | HTTP 402 "Insufficient credits" |

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

Order matters: a hard-exhaustion signature always wins over a rate signature when
a single message mentions both.

---

## Tools

- **Provider tools (passthrough, original names):** whatever each official server
  advertises — e.g. `web_search_exa`, `web_fetch_exa`; `tavily_search`,
  `tavily_extract`, `tavily_map`, `tavily_crawl`, `tavily_research`;
  `firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`, … (33 total in the
  committed caches). Rotation is applied invisibly inside the call path.
- **Per-provider account tools (6 each = 18):** `ex_account_*`, `tv_account_*`,
  `fc_account_*` — `list` / `current` / `add` / `remove` / `switch` / `cycle`
  (from the shared `_shared/accounts.py`). Each "account" is **one API key**;
  these give you the multi-key store + labels + a **manual** switch/cycle.
- **`search_usage` (hub-native, on-demand):** per stored key, reports
  `label + remaining` (Firecrawl remaining credits; Tavily plan+paygo headroom)
  plus cooldown/health. Exa reports `"error-driven (no balance API)"`. Pass
  `provider="exa"|"tavily"|"firecrawl"` to narrow, or omit for all. Read-only;
  never spawns a search child.

`python hub.py --print-plan` prints the exposed tool counts; `--refresh [ids…]`
re-enumerates the official servers to regenerate `caches/*.json`.

---

## Multi-key setup (plug-and-play)

Rotation needs **≥2 keys per provider**. Three ways to add them, cheapest first:

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
it live you **replace** the three individual entries with the single hub. This is
a **user-approved** change to your live `~/.mcp.json`; it is **not** done for you.

1. In `~/.mcp.json`, **remove** the standalone `exa`, `tavily`, and `firecrawl`
   server entries.
2. **Add** the `search-hub` entry (copy it from
   `tools/mcp/canonical-mcp-servers.json`):

   ```json
   "search-hub": {
     "type": "stdio",
     "command": "C:\\Python314\\python.exe",
     "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\search-hub\\hub.py"],
     "env": {
       "EXA_API_KEY": "${EXA_API_KEY}",       "EXA_API_KEY_2": "${EXA_API_KEY_2}",
       "TAVILY_API_KEY": "${TAVILY_API_KEY}", "TAVILY_API_KEY_2": "${TAVILY_API_KEY_2}",
       "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}", "FIRECRAWL_API_KEY_2": "${FIRECRAWL_API_KEY_2}"
     }
   }
   ```

3. Add any real backup keys to your environment (`EXA_API_KEY_2`, …). Unset
   backup vars resolve to empty and are skipped — harmless.
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

They cover the provider specs + error classifier (402-exhaust vs 429-rate per
provider), the usage parsers, `pick_active` skipping cooled keys, the
rotate-retry-once policy (incl. the Tavily ambiguous-429 `/usage` probe),
numbered-backup seeding, the `env_for` account resolver, and the hub's
list/route/usage/switch paths against a fake backend.

**Needs live keys (manual, not in CI):** actually reaching Exa/Tavily/Firecrawl,
real `search_usage` balances, and observing a real 402→rotate in production. Use
`python hub.py --refresh` to regenerate `caches/*.json` from the live servers.

## Files

- `hub.py` — JSON-RPC stdio server; per-(provider, key) lazy children + per-call
  routing; `--refresh` / `--print-plan` modes.
- `providers.py` — the 3 provider specs (stdio cmd + env var + usage URL) and the
  exhaustion-signal classifier.
- `rotation.py` — per-key health, `pick_active`, `mark_exhausted`, the
  rotate-retry wrapper, and numbered-backup seeding.
- `usage.py` — stdlib `urllib` calls to the 3 usage endpoints.
- `caches/*.json` — committed tool enumerations (regenerate with `--refresh`).
- `../_shared/accounts.py` — the shared multi-account store (one additive
  read-only helper, `env_for`, was added for per-key resolution).
