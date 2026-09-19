# biomni-hub — Component A3: Expanded Feature Tools

Additive, backend-agnostic FastMCP tools the hub exposes **on top of** the
canonical 10-tool Biomni surface (the "drive it better" Tier-1 set), plus the
SQLite run-history/artifacts store that backs them.

These tools never redeclare the canonical surface and never import the concrete
backend adapters. They call through the `BackendClient` seam
(`backend.py`) that the hub injects on `HubContext`, so this component builds,
imports, registers, and self-tests **standalone** — before the sibling
online/databricks adapter components have landed. Backend selection is
out-of-band and **fails closed to `online`**.

## Files

| File | Role |
|---|---|
| `__init__.py` | `register_all(mcp, ctx)` — attaches all 5 tools; exports |
| `context.py` | `HubContext` dataclass + `build_default_context()` |
| `backend.py` | `BackendClient` protocol, capability tokens, `NullBackend`, `BackendRegistry` (fail-closed `resolve`) |
| `store.py` | **Feature #6** — `RunStore`: SQLite runs/artifacts/tool_catalog/injected_mcps |
| `pricing.py` | token→USD + compute→USD estimators for the cost meter |
| `run_history.py` | **Feature #1** — `biomni_run_history` |
| `fetch_artifact.py` | **Feature #2** — `biomni_fetch_artifact` |
| `cost.py` | **Feature #3** — `biomni_cost` |
| `tool_catalog.py` | **Feature #4** — `biomni_tool_catalog` |
| `inject_mcp.py` | **Feature #5** — `biomni_inject_mcp` |
| `_selftest.py` | standalone verification (`python -m features._selftest`) |

## Wiring into the hub

```python
from fastmcp import FastMCP
from features import register_all
from features.context import build_default_context

mcp = FastMCP("biomni-hub")
ctx = build_default_context()                    # NullBackend default
ctx.backends.register("online", OnlineAdapter())      # from Component A (Track A)
ctx.backends.register("databricks", DatabricksAdapter())  # from Track B
register_all(mcp, ctx)                            # adds the 5 tools below
```

A backend adapter satisfies `BackendClient` and advertises capability tokens
(`CAP_LIST_SKILLS`, `CAP_BILLING`, `CAP_FETCH_BYTES`, `CAP_BIOMNI_URL`,
`CAP_ADD_MCP`). Feature tools gate on **capabilities**, not backend names, so a
future third backend works without edits.

## Tool signatures

```python
# Feature #1 — cross-backend task history (from the durable hub ledger)
async def biomni_run_history(
    backend: str | None = None,      # filter to one backend; omit = all
    status: str | None = None,       # pending|running|completed|failed
    project_id: str | None = None,
    since: str | None = None,        # today|7d|30d  (omit = all time)
    limit: int = 50,                 # 1..1000
) -> dict   # {runs:[{run_id,backend,status,prompt,cost_usd,duration_s,artifacts}], count, backends_known}

# Feature #2 — REAL result-file download (backend-aware; fails closed)
async def biomni_fetch_artifact(
    name: str,                       # result-file name
    run_id: str | None = None,       # resolves backend+session, attaches record
    session_id: str | None = None,   # needed if run_id unknown
    backend: str | None = None,
    dest_dir: str | None = None,     # default <data_dir>/artifacts/<run>
    max_inline_bytes: int = 262_144, # also return base64 if <= this
) -> dict   # status: downloaded | url_only | not_found
            # self-host -> {artifact_id,size,sha256,local_path,bytes_base64?}
            # online    -> {biomni_url, display_instruction}  (S3 blocked)

# Feature #3 — per-run + rolling cost meter
async def biomni_cost(
    run_id: str | None = None,       # set -> per-run breakdown
    backend: str | None = None,      # filter the rolling meter
    window: str = "all",             # all|today|7d|30d
    include_balance: bool = True,    # + live bm_billing_balance if available
) -> dict   # run:    {tokens_in,tokens_out,token_usd,compute_usd,total_usd,estimated}
            # rolling:{total_usd,runs_counted,by_backend{...},balance?}

# Feature #4 — introspect Biomni's ~150 tools/skills (bm_list_skills), cached
async def biomni_tool_catalog(
    backend: str | None = None,
    category: str | None = None,     # filter by module/category
    query: str | None = None,        # substring over name/description
    include_disabled: bool = True,
    refresh: bool = False,           # force live fetch + re-cache (else offline cache)
    limit: int = 500,
) -> dict   # {backend, tools:[{name,category,description,enabled,source}], count, categories{}}

# Feature #5 — inject a fleet MCP into self-hosted Biomni via add_mcp
async def biomni_inject_mcp(
    mcp_ref: str,                    # fleet name OR logical id (w/ explicit spec)
    backend: str | None = None,      # must support CAP_ADD_MCP (self-host only)
    command: str | None = None,      # explicit stdio launch
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    url: str | None = None,          # explicit http/sse endpoint
    transport: str = "stdio",
    persist: bool = True,            # record for cluster-restart replay
) -> dict   # status: injected | unsupported | unknown_ref | error
```

Built-in `FLEET_REGISTRY` names: `chembl`, `open_targets`, `paper-search`,
`rdkit`, `scholarly-access` (pass an explicit `command`/`args` or `url` for any
other MCP).

## Key design points

- **Run store = the cross-backend truth.** Every task launched through the hub
  is upserted into `runs` with its backend; `biomni_run_history` and the rolling
  `biomni_cost` read the ledger, so they span backends with no live fan-out.
- **`biomni_fetch_artifact` respects the online limitation.** The claude.ai Lab
  returns names-only / expiring-blocked S3 links, so for `online` the tool
  surfaces `biomni_url` + a `display_instruction`; only self-host backends
  (`CAP_FETCH_BYTES`) return real bytes, hashed and persisted.
- **Cost is estimate-then-reconcile.** Token USD is authoritative when recorded
  on the run, else estimated from `pricing.PRICING` (Sonnet-class default);
  compute USD is estimated from wall-clock for self-host; the live
  `bm_billing_balance` is surfaced as the source of truth when present.
- **Injections survive ephemeral clusters.** `biomni_inject_mcp` persists each
  spec to `injected_mcps`; on a databricks cluster cold-start the hub replays
  `store.list_injections(backend)` back through `add_mcp` so the warm `A1`
  object regains the fleet tools. (Wiring detailed at the top of `inject_mcp.py`.)
- **Fail closed everywhere.** Unknown backend → default; unsupported capability
  → explicit `unsupported`/`url_only` status, never a crash; every live backend
  call is wrapped so a flaky adapter degrades the tool, not the hub.

## Verify

```
cd hub
ruff check features/            # -> All checks passed!
python -m features._selftest    # -> SUCCESS:selftest-A3 all checks passed
```

The self-test proves: all 5 tools register on a real `FastMCP` instance, the
store round-trips (run + artifact + rollup + injection replay), and the cost
estimator is sane. A `call_tool` pass additionally confirms every tool executes
end-to-end against the `NullBackend` with correct fail-closed statuses
(`inject→unsupported`, `fetch→url_only`, `catalog→empty`).

## Requirements

`fastmcp>=3`, `aiosqlite` (both present in the workspace env; Python 3.14).
