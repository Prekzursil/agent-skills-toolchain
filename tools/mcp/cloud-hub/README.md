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

## Backends & tool surface (279 backend tools + 54 account tools = 333)

| id | backend | pkg / runtime | tools | adopt/build | auth | cache |
|----|---------|---------------|------:|-------------|------|-------|
| `runpod` | RunPod | `npx @runpod/mcp-server@latest` | 50 | adopt | `RUNPOD_API_KEY` | live |
| `azure` | Azure | `npx @azure/mcp@latest server start` | 14 | adopt | `az login` | **hand-authored** |
| `gcloud` | Google Cloud | `npx @google-cloud/gcloud-mcp` | 1 | adopt | gcloud ADC + `GOOGLE_CLOUD_PROJECT` | live |
| `kaggle` | Kaggle | `uvx kaggle-mcp-server` | 51 | adopt | `KAGGLE_USERNAME`+`KAGGLE_KEY` / `~/.kaggle/kaggle.json` | live |
| `rclone` | rclone | `npx rclone-mcp` (over `rclone rcd`) | 56 | adopt | RC daemon on :5572 | live |
| `modal` | Modal | built FastMCP wrapper (`modal` CLI + SDK) | 41 | build | `MODAL_TOKEN_ID`+`MODAL_TOKEN_SECRET` | live |
| `lightning` | Lightning AI | built FastMCP wrapper (`lightning_sdk`) | 9 | build | `LIGHTNING_USER_ID`+`LIGHTNING_API_KEY` | live |
| `ovh` | OVHcloud | vendored TS MCP (`node ovh-mcp/dist/index.js`) | 27 | vendor+build | `OVH_APPLICATION_KEY`+`_SECRET`+`_CONSUMER_KEY` (or OAuth2) per region | live |
| `compute` | Compute (unified) | built FastMCP wrapper (`compute-mcp/`) | 10 | build | per-provider (reuses RunPod/OVH/Lightning creds) | live |
| `databricks` | Databricks | built FastMCP wrapper (`databricks-sdk`) | 65 | build | `DATABRICKS_HOST` + (`DATABRICKS_CLIENT_ID`/`_SECRET` or `DATABRICKS_TOKEN`) | live |

`azure` is a **hand-authored** representative cache: `@azure/mcp` is a .NET tool that
did not emit an MCP handshake under piped stdio in the build harness (the Node
backends enumerated fine). Run `python hub.py --refresh azure` in the environment
where it starts cleanly to replace it with the live schema. Its `az_account_*`
switching tools work regardless (they drive the `az` CLI).

### OVHcloud (`ovh`) — vendored build + region rotation

`ovh` fronts [`hlebtkachenko/ovhcloud-mcp`](https://github.com/hlebtkachenko/ovhcloud-mcp)
(MIT), vendored under `ovh-mcp/` because it is **not published to npm**. It is a
TypeScript server, so it needs a one-time build (source is committed;
`node_modules/`+`dist/` are gitignored):

```
cd ovh-mcp && npm install && npm run build     # produces dist/index.js
```

(`package-lock.json` is committed-ignored by repo policy, so use `npm install`, not `npm ci`.)

27 tools: VPS lifecycle, DNS, billing, **`ovh_ssh_exec`** (run commands on a host),
and an API explorer + **`ovh_api_raw`** that reaches ANY of OVH's 500+ endpoints —
including Public Cloud (`/cloud/project/…`) GPU-instance create/list/delete, which
have no purpose-built tool. `tools/list` needs no creds, so the cache enumerates
offline.

**Region + creds are per account.** Each `ov` account bundles `OVH_ENDPOINT`
(`ovh-eu` | `ovh-ca` | `ovh-us`) alongside its credentials, so
`ov_account_switch ca|eu|us` flips **both** region and credentials in one call
(OVHcloud EU/CA/US are separate legal entities with separate accounts — the
endpoint must match the account). Creds may be the API-key trio
(`OVH_APPLICATION_KEY`/`_SECRET`/`_CONSUMER_KEY`, from
[ovh.com/auth/api/createToken](https://www.ovh.com/auth/api/createToken)) OR OAuth2
(`OVH_CLIENT_ID`/`OVH_CLIENT_SECRET`); the env bundle is auth-agnostic. See the
`ovh` block in `accounts.example.json` for the three-region template.

`ov_account_add` (like every env-mode backend) accepts an optional **`label`**
— e.g. the account email — surfaced by `ov_account_list`/`_current` as
`name → label`, so you can tell which OVH identity each switch-name maps to
(confirm the live identity any time with `ovh_account_info` = `GET /me`).

### Compute (unified) (`compute`) — one GPU lifecycle over three providers

`compute` is a locally-built FastMCP wrapper (`compute-mcp/`) exposing **ten
normalized `compute_*` verbs** that dispatch **directly** to the RunPod, OVH, and
Lightning AI provider APIs — the hub stays a passthrough (it never proxies a
provider SDK itself). One provider-agnostic surface for the whole rent-a-GPU
lifecycle:

`compute_provision` · `compute_status` · `compute_ls` · `compute_exec` ·
`compute_logs` · `compute_pull` · `compute_push` · `compute_teardown` ·
`compute_cost` · `compute_catalog`

A box is addressed by an opaque handle `compute://<provider>/<kind>/<ident>`
returned by `compute_provision` (`runpod/pod/<id>`,
`ovh/instance/<serviceName>/<id>`, `lightning/studio/[<teamspace>/]<name>`).

- **Zero new deps.** stdlib `urllib`+`hashlib` HTTP (incl. OVH's `$1$` SHA-1
  request signing), `lightning_sdk` in-process, and subprocess `ssh`/`scp` for
  `exec`/`pull`/`push`. `pull`/`push` auto-select scp vs the rclone RC daemon by
  path (an rclone `remote:path` routes to rclone; a `via=` override forces one).
- **Creds are reused, not re-declared.** `compute_*` resolves the SAME per-account
  credentials the hub injects for the `runpod`/`ovh`/`lightning` backends (via
  `accounts.json` + seed env), so there is **no `cp_account_*` layer** — switch
  accounts with `rp_`/`ov_`/`lg_account_*` or the per-verb `account=` argument.
- **Safety gates.** `compute_teardown terminate=true` (and the OVH/RunPod deletes)
  need `confirm=true` or are refused with a `would:` preview; `dry_run=true` on
  provision/teardown returns the exact request **uncalled**. Every verb answers
  the same `{ok, provider, handle?, state?, …, error?}` envelope; honest notes
  fill capability gaps (OVH has no stop-without-billing; Lightning has no public
  cost API or SDK file-download).
### Modal (`md`) — CLI + SDK: sandboxes, functions, resources, per-call rotation

`modal` is a **built** FastMCP wrapper split across `modal-mcp/server.py` (CLI
path), `modal-mcp/sandbox.py` (SDK path), and `modal-mcp/_modal_common.py`
(shared helpers). `tools/list` enumerates with **zero credentials** — the
`modal` SDK is imported lazily only on the first real SDK call, and all library
stdout is redirected to stderr so it can never corrupt the stdio JSON-RPC stream.

**41 tools** across four tiers:

- **Sandboxes** (SDK, the container-engagement primitive): `modal_sandbox_create`
  (image/gpu/cpu/memory/volumes/`CloudBucketMount`/secrets), `_exec`,
  `_exec_stream`, `_write_file`/`_read_file`, `_upload`/`_download`, `_ls`/`_mkdir`/
  `_rm`/`_stat`, `_list`, **`_from_id`** (stateless reattach), `_poll`/`_wait`/
  `_terminate`, `_tags`, and **`_snapshot`** (`snapshot_filesystem()` → a reusable
  image, e.g. bake a Suite install once).
- **Function / container** (SDK + CLI): `modal_function_call`/`_spawn`,
  `modal_functioncall_get`, `modal_app_logs`, `modal_container_list`/`_exec`/
  `_logs`/`_stop`.
- **Resources** (CLI): `modal_volume_create`/`_put`/`_get`/`_rm`/`_delete`,
  `modal_secret_create`, plus `modal_cloud_bucket_mount_config` (a local helper
  that builds a bucket-mount config for `modal_sandbox_create`).
- **Identity / cost** (CLI + local): `modal_whoami`, `modal_estimate_cost` (a
  LOCAL calc from GPU/CPU/memory-seconds — Modal exposes **no public billing
  API**).

**Per-invocation rotation.** Every `modal_*` tool takes an optional
`account`/`environment` arg. When `account=<name>` is set, that call builds a
**fresh** `modal.Client.from_credentials(...)` (threaded via `client=` on
`Sandbox.create`/`from_id`/`list`, `App.lookup`, `Function.from_name`, …) — or,
for the CLI path, a per-call env overlay — from `MODAL_TOKEN_ID_<NAME>` /
`MODAL_TOKEN_SECRET_<NAME>` (else a `[<name>]` profile in `~/.modal.toml`).
**No global "active profile" is ever mutated** (concurrency-safe: parallel calls
can't contaminate each other). This is *in addition* to `md_account_switch`,
which flips the ambient account by kill+respawn. `environment` threads
`MODAL_ENVIRONMENT` / the CLI `--env`; an `md` account may bundle `MODAL_ENVIRONMENT`.

**Cost + destructive gating.** `gpu=` on a sandbox/function starts **billable**
per-second compute — always `modal_sandbox_terminate` when done. Destructive ops
(`modal_sandbox_terminate`, `modal_container_stop`, `modal_volume_rm`,
`modal_volume_delete`) are gated behind `confirm=true` (or `dry_run=true` to
preview).
### Databricks (`databricks`) — built `databricks-sdk` wrapper

`databricks` is a built FastMCP wrapper (`databricks-mcp/server.py`) over the
official **`databricks-sdk`** (Python), pre-namespaced `dbx_*` (65 tools). Like
the modal/lightning wrappers it lazy-imports the SDK, so `tools/list` enumerates
offline (cache is live-generated); a call without the SDK or credentials returns
a clear install/auth hint. SDK stdout + `logging` are silenced so the JSON-RPC
stream stays clean.

Surface: **clusters** (list/get/create/edit/start/restart/resize/terminate/
permanent_delete + `dbx_node_types`/`dbx_spark_versions`; GPU via a GPU
`node_type_id` + a `*-gpu-ml` runtime), **Command Execution** (the compute
primitive — `dbx_ctx_create`/`_status`/`_destroy`, `dbx_exec`, and
`dbx_run_on_cluster` convenience; **classic all-purpose clusters only**),
**jobs + runs**, **DBFS + Unity Catalog Volumes**, **SQL warehouses +
`dbx_sql_exec`**, **model serving** (incl. `dbx_serving_query`), **secrets +
repos**, `dbx_current_user`, and **`dbx_api_raw`** (call ANY Databricks REST
endpoint — the escape hatch).

**Auth:** SDK unified auth. Default is **OAuth M2M service principal**
(`DATABRICKS_HOST` + `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`); **PAT**
is the fallback (`DATABRICKS_HOST` + `DATABRICKS_TOKEN`); a `~/.databrickscfg`
profile (`DATABRICKS_CONFIG_PROFILE`) also works. Each `db` account bundles
`DATABRICKS_HOST` with its creds, so `db_account_switch` flips **both** workspace
URL and credentials (the OVH per-region pattern, per-workspace). See the
`databricks` block in `accounts.example.json`.

**Guardrails:** the destructive / code-executing tools
(`dbx_cluster_terminate`, `dbx_cluster_permanent_delete`, `dbx_warehouse_delete`,
`dbx_exec`, `dbx_run_on_cluster`) are gated behind `confirm=True` (else a dry-run
preview). Cluster/warehouse lifecycle tools expose an opt-in `wait` flag (the SDK
`*_and_wait` variants). Docstrings carry `$$$` cost cautions — clusters/
warehouses bill while running, so set `autotermination_minutes` / `auto_stop_mins`
and terminate/stop when done. `databricks-sdk` must be installed in the hub's
interpreter for live calls (`pip install databricks-sdk`).

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

- **env** (runpod, kaggle, modal, lightning, ovh, rclone) — an account is a bundle of
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
    "KAGGLE_USERNAME": "${KAGGLE_USERNAME}",
    "KAGGLE_KEY": "${KAGGLE_KEY}",
    "GOOGLE_CLOUD_PROJECT": "${GOOGLE_CLOUD_PROJECT}",
    "MODAL_TOKEN_ID": "${MODAL_TOKEN_ID}",
    "MODAL_TOKEN_SECRET": "${MODAL_TOKEN_SECRET}",
    "LIGHTNING_USER_ID": "${LIGHTNING_USER_ID}",
    "LIGHTNING_API_KEY": "${LIGHTNING_API_KEY}",
    "OVH_ENDPOINT": "${OVH_ENDPOINT}",
    "OVH_APPLICATION_KEY": "${OVH_APPLICATION_KEY}",
    "OVH_APPLICATION_SECRET": "${OVH_APPLICATION_SECRET}",
    "OVH_CONSUMER_KEY": "${OVH_CONSUMER_KEY}",
    "DATABRICKS_HOST": "${DATABRICKS_HOST}",
    "DATABRICKS_CLIENT_ID": "${DATABRICKS_CLIENT_ID}",
    "DATABRICKS_CLIENT_SECRET": "${DATABRICKS_CLIENT_SECRET}",
    "DATABRICKS_TOKEN": "${DATABRICKS_TOKEN}"
  }
}
```

Azure + gcloud inherit their CLI logins (`az login`, `gcloud auth`) — no key env.
The hub's interpreter needs `mcp` + `modal` installed (and `lightning-sdk` for the
Lightning tools, `databricks-sdk` for the Databricks tools). Node ≥ 20, `uv`, and
the `rclone`/`az`/`gcloud` CLIs on PATH.
The `ovh` backend needs its one-time build (`cd ovh-mcp && npm ci && npm run build`).

## Tests

```
python -m pytest tests -q     # 85 tests: plan logic + lazy-spawn + account + compute layers
python -m pytest tests -q     # 36 tests: plan logic + lazy-spawn + account layer + databricks wrapper
python e2e_live.py            # live: routes an account tool + modal_app_list (Windows)
```
