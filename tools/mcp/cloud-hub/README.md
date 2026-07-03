# cloud-hub — lazy, name-preserving MCP multiplexer for the cloud-infra stack

Fronts the user's cloud-infrastructure MCP servers behind **one** MCP registration
while keeping every tool under its **original name**. `initialize` and `tools/list`
are answered from committed per-backend caches **without spawning anything**; a
`tools/call` lazily spawns **only** the owning backend (once, kept alive for the
session) and forwards the request. This is the multi-backend sibling of `social-hub`
(identical mechanics; only the identity + backend registry differ).

Why not a normal aggregator (mcp-funnel / 1mcp)? Those rename tools to
`serverName__tool`. This hub preserves names and only renames on a genuine
cross-backend collision (none today).

## Backends & tool surface (185 backend tools + 42 account tools = 227)

| id | backend | pkg / runtime | tools | adopt/build | auth | cache |
|----|---------|---------------|------:|-------------|------|-------|
| `runpod` | RunPod | `npx @runpod/mcp-server@latest` | 50 | adopt | `RUNPOD_API_KEY` | live |
| `azure` | Azure | `npx @azure/mcp@latest server start` | 14 | adopt | `az login` | **hand-authored** |
| `gcloud` | Google Cloud | `npx @google-cloud/gcloud-mcp` | 1 | adopt | gcloud ADC + `GOOGLE_CLOUD_PROJECT` | live |
| `kaggle` | Kaggle | `uvx kaggle-mcp-server` | 51 | adopt | `KAGGLE_API_TOKEN` / `~/.kaggle/kaggle.json` | live |
| `rclone` | rclone | `npx rclone-mcp` (over `rclone rcd`) | 56 | adopt | RC daemon on :5572 | live |
| `modal` | Modal | built FastMCP wrapper (`modal` CLI) | 6 | build | `MODAL_TOKEN_ID`+`MODAL_TOKEN_SECRET` | live |
| `lightning` | Lightning AI | built FastMCP wrapper (`lightning_sdk`) | 7 | build | `LIGHTNING_USER_ID`+`LIGHTNING_API_KEY` | live |

`azure` is a **hand-authored** representative cache: `@azure/mcp` is a .NET tool that
did not emit an MCP handshake under piped stdio in the build harness (the Node
backends enumerated fine). Run `python hub.py --refresh azure` in the environment
where it starts cleanly to replace it with the live schema. Its `az_account_*`
switching tools work regardless (they drive the `az` CLI).

### Collision policy

Unique names are kept **exactly**. Cross-backend collisions would get a minimal
`<prefix>_` and be advertised in the description — but there are **no collisions
today** (the built backends pre-namespace their tools; the adopt backends have
disjoint names). `python hub.py --print-plan` prints the live merged plan.

## Multi-account + cycling (`accounts.py`)

Each backend can hold **several named accounts** (credential profiles) for the
user's OWN accounts on that platform, switch the active one, and **cycle** through
them — via six hub-native tools per backend, merged into `tools/list` **without
spawning** and handled by the hub itself (never forwarded to a child):

`<prefix>_account_list` · `_current` · `_add` · `_remove` · `_switch` · `_cycle`
(e.g. `rp_account_switch`, `kg_account_cycle`, `md_account_add`, `az_account_list`).

Two modes:

- **env** (runpod, kaggle, modal, lightning, rclone) — an account is a bundle of
  env vars (literal values or `${ENV}` refs). The active account's env is injected
  when the hub spawns that backend. Stored in the **gitignored** `accounts.json`.
- **cli** (azure, gcloud) — an account maps to the platform CLI's own profiles
  (Azure subscriptions / gcloud configurations); list/switch/add/remove delegate
  to `az` / `gcloud`. No env is injected (the CLI holds the state).

**Switch/cycle = kill + lazy-respawn:** the hub kills the backend immediately and
the new credentials take effect on its next `tools/call` spawn.

**Seeding:** if an env-mode platform has no stored accounts but its registration
env vars are present, an in-memory `default` account is synthesized from `${ENV}`
refs (never persisted — secrets only reach disk when you explicitly `add` them).

`accounts.py` is **reusable** (stdlib-only, no backend coupling) — `social-hub` can
adopt it later. Copy `accounts.example.json` → `accounts.json` to add accounts
(gitignored; may hold literal secrets — never commit).

> **ToS caution:** switching/cycling accounts to evade a platform's per-account
> free-tier or rate limits may violate that platform's Terms of Service. This is
> ordinary account management for the user's OWN accounts.

## Runtime / commands

```
python hub.py                      # runtime stdio MCP (what ~/.mcp.json runs)
python hub.py --refresh [ids...]   # (re)generate tool caches by enumerating backends
python hub.py --print-plan         # print the merged plan summary
```

Caches live in `caches/*.json` (lazy_proxy shape: `{initialize, tools}`) and are
committed so the merged `tools/list` is complete even when a backend can't log in.
`--refresh` never overwrites a good cache with a failed enumeration. Each child
inherits `os.environ` (then the active account's env), so credentials pass through
without being hard-coded here.

Stdlib only for the hub/registry/accounts (Python 3.9+). The two built wrappers use
`mcp` (FastMCP). Fail-safe: a backend that can't spawn/enumerate returns a clear
error for **its** tools only; the hub never crashes.

## rclone RC daemon prereq

`rclone-mcp` is a **client** of rclone's remote-control daemon. The `rclone` backend
`cmd` is a launcher (`rclone_launch.py`) that starts `rclone rcd --rc-no-auth
--rc-addr :5572` if that port is down, then execs `npx -y rclone-mcp` with stdio
passed through. Needs `rclone` on PATH; if absent, rclone tools degrade cleanly.

## Windows launch note

The hub's `_spawn` runs argv directly (no shell), so `npx`/`uvx` (which are `.cmd`
shims) go through `cmd /c` in their specs. The two built wrappers + the rclone
launcher are real Python entry points run under the hub's own interpreter.

## Registration (for the orchestrator — not wired here)

```jsonc
"cloud-hub": {
  "type": "stdio",
  "command": "C:\\Python314\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\cloud-hub\\hub.py"],
  "env": {
    "RUNPOD_API_KEY": "${RUNPOD_API_KEY}",
    "KAGGLE_API_TOKEN": "${KAGGLE_API_TOKEN}",
    "GOOGLE_CLOUD_PROJECT": "${GOOGLE_CLOUD_PROJECT}",
    "MODAL_TOKEN_ID": "${MODAL_TOKEN_ID}",
    "MODAL_TOKEN_SECRET": "${MODAL_TOKEN_SECRET}",
    "LIGHTNING_USER_ID": "${LIGHTNING_USER_ID}",
    "LIGHTNING_API_KEY": "${LIGHTNING_API_KEY}"
  }
}
```

Azure + gcloud inherit their CLI logins (`az login`, `gcloud auth`) — no key env.
The hub's interpreter needs `mcp` + `modal` installed (and `lightning-sdk` for the
Lightning tools). Node ≥ 20, `uv`, and the `rclone`/`az`/`gcloud` CLIs on PATH.

## Tests

```
python -m pytest tests -q     # 24 tests: plan logic + lazy-spawn + account layer
python e2e_live.py            # live: routes an account tool + modal_app_list (Windows)
```
