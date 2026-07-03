---
name: cloud-infra-toolchain
description: "Use when working with the user's cloud-infrastructure MCP stack fronted by the cloud-hub multiplexer - RunPod, Azure, Google Cloud, Kaggle, rclone, Modal, and Lightning AI behind one lazy MCP slot. Covers which platform does what, adopt-vs-build status, per-platform auth + the account-switch/cycle multi-account layer, the workflows (train on Kaggle, rent a GPU on RunPod/Modal/Lightning, deploy to Cloud Run/AKS, move data with rclone), the rclone rcd daemon prereq, the Windows `cmd /c npx` note, GPU cost-awareness + read-before-destroy operating rules, and the per-backend tool inventory. Multi-accounting can breach a platform's ToS - flag it."
---

# Cloud Infrastructure MCP Toolchain

## Overview

The user's cloud-infra MCP servers are fronted by **`cloud-hub`** — one lazy,
name-preserving multiplexer (`tools/mcp/cloud-hub/`) that answers `tools/list`
from committed caches **without spawning** and lazily spawns **only** the owning
backend on a `tools/call`. Seven platforms, **185 backend tools + 42 account
tools = 227**, behind a single MCP registration. Five servers are **adopted**
(existing MCP packages) and two are **built** thin FastMCP wrappers.

| Platform | pkg / runtime | Auth | Adopt/Build | Tools | Hard limits |
|---|---|---|---|---:|---|
| **RunPod** | `npx @runpod/mcp-server@latest` (Node) | `RUNPOD_API_KEY` | adopt | 50 | GPU billed per-second; pods/endpoints cost money while running |
| **Azure** | `npx @azure/mcp@latest server start` (.NET) | `az login` | adopt | 14* | *hand-authored cache (the .NET server didn't enumerate under piped stdio); `--refresh azure` upgrades it |
| **Google Cloud** | `npx @google-cloud/gcloud-mcp` (Node) | gcloud ADC + `GOOGLE_CLOUD_PROJECT` | adopt | 1 | single `run_gcloud_command` passthrough — full gcloud surface, full gcloud risk |
| **Kaggle** | `uvx kaggle-mcp-server` (Python) | `KAGGLE_API_TOKEN` / `~/.kaggle/kaggle.json` | adopt | 51 | free-tier GPU/TPU quota (~30h/wk); kernels are public unless set private |
| **rclone** | `npx rclone-mcp` over `rclone rcd` | RC daemon :5572 | adopt | 56 | **needs the rcd daemon** (auto-started); `sync`/`move`/`delete` are destructive |
| **Modal** | built FastMCP wrapper (`modal` CLI) | `MODAL_TOKEN_ID`+`MODAL_TOKEN_SECRET` | build | 6 | `run`/`deploy` start billable compute |
| **Lightning AI** | built FastMCP wrapper (`lightning_sdk`) | `LIGHTNING_USER_ID`+`LIGHTNING_API_KEY` | build | 7 | Studios/Jobs bill by the second; `lightning-sdk` must be installed |

The two built wrappers **pre-namespace** their tools (`modal_*`, `lightning_*`) so
the hub's collision-prefix never fires. There are **no cross-backend collisions**
today, so every tool keeps its original name.

## Multi-account + cycling (cswap-style)

Every backend can hold **several named accounts** for the user's OWN accounts on
that platform, switch the active one, and **cycle** through them, via six hub-native
tools per backend (served without spawning, handled by the hub):

`<prefix>_account_list · _current · _add · _remove · _switch · _cycle`
— prefixes: `rp` RunPod · `az` Azure · `gc` gcloud · `kg` Kaggle · `rc` rclone ·
`md` Modal · `lg` Lightning. E.g. `rp_account_switch`, `kg_account_cycle`,
`md_account_add`, `az_account_list`.

- **env-mode** (runpod, kaggle, modal, lightning, rclone): an account is a bundle of
  env vars (literal or `${ENV}` refs), stored in the **gitignored** `accounts.json`.
  The active account's env is injected when the hub spawns that backend.
- **cli-mode** (azure, gcloud): an account is the CLI's own profile — Azure
  subscriptions (`az account set`) / gcloud configurations
  (`gcloud config configurations activate`); list/switch delegate to the CLI.
- **Switch/cycle kills + lazy-respawns** the backend so new creds take effect on the
  next call.
- **Seeding:** if an env-mode platform has no stored accounts but its registration
  env vars are set, a `default` account is synthesized in-memory (secrets never
  auto-persist).

> **Honesty / ToS:** multi-accounting to evade a platform's per-account free-tier or
> rate limits **may violate that platform's Terms of Service and risk account
> suspension**. This tooling is standard account management for the user's OWN
> accounts — treat it like the social toolchain flags ban-risk: keep it to legitimate
> use, don't farm free tiers.

## Auth-setup runbook

| Platform | Where the credential comes from |
|---|---|
| RunPod | Console → Settings → API Keys → `RUNPOD_API_KEY` |
| Azure | `az login` (device or browser); account = a subscription from `az account list` |
| Google Cloud | `gcloud auth login` + `gcloud auth application-default login`; set `GOOGLE_CLOUD_PROJECT`; account = a `gcloud config configurations` profile |
| Kaggle | kaggle.com → Account → Create New API Token → `~/.kaggle/kaggle.json` (or `KAGGLE_API_TOKEN`) |
| rclone | `rclone config` to add remotes; the hub launcher starts `rclone rcd --rc-no-auth --rc-addr :5572` |
| Modal | `modal token new` (writes `~/.modal.toml`) or `MODAL_TOKEN_ID`+`MODAL_TOKEN_SECRET` |
| Lightning AI | lightning.ai → Settings → Keys → `LIGHTNING_USER_ID`+`LIGHTNING_API_KEY`; `pip install lightning-sdk` |

Credentials pass to the hub via its registration `env` block (see the cloud-hub
README) and/or `accounts.json`. Never inline a secret in a command or commit it.

## Workflows

### Train on Kaggle (free GPU/TPU)
1. `kernel_push` — upload a notebook/script kernel (set GPU/TPU + `enable_internet`).
2. `kernel_session_create` — start a compute session for it.
3. `kernel_session_status` — poll until complete.
4. `kernel_session_output` / `kernel_output` — pull logs + output files.
Datasets: `dataset_download` (inputs), `dataset_create`/`dataset_create_version`
(publish results). Competitions: `competition_download` → train → `competition_submit`.

### Rent a GPU (three options — pick by workload)
- **RunPod pod** (persistent box): `list-gpu-types` → `create-pod` → `start-pod` →
  work → **`stop-pod`** (keeps disk, stops billing) or **`delete-pod`/`terminate`**
  (removes it). `get-billing` to check spend. Serverless: `create-endpoint` →
  `run-endpoint`/`runsync-endpoint` → `get-job-status`.
- **Modal** (ephemeral function run): `modal_run app.py::fn` or `modal_deploy`;
  stop with `modal_app_stop`. Best for containerized batch/serverless GPU.
- **Lightning Studio/Job**: `lightning_machine_types` → `lightning_studio_start
  name machine=A10G` → `lightning_studio_run` (or `lightning_job_submit` for async)
  → **`lightning_studio_stop`/`lightning_job_stop`**. Best for interactive dev.

### Deploy an app
- **Cloud Run (GCP):** `run_gcloud_command` with `run deploy <svc> --source . --region
  <r>` (or `--image`). Inspect with `run services list`.
- **Azure:** `azmcp_extension_az` with `aks ...` / `containerapp ...`, or
  `azmcp_aks_cluster_list` to find AKS clusters; `azmcp_extension_azd` for `azd up`.

### Move data (rclone)
- `config_listremotes` — see configured remotes.
- `operations_about` — **quota/free/used** for a remote (check before large copies).
- `sync_copy` (additive), `sync_sync` (mirror — **deletes extra dest files**),
  `sync_move`, `sync_bisync` (two-way). `operations_copyfile`/`movefile` for singles.
- `operations_size` for a dry sizing; `core_stats`/`core_transferred` for progress.

## rclone `rcd` daemon prereq

`rclone-mcp` is a **client** of rclone's remote-control HTTP daemon. The hub's rclone
backend is a launcher (`rclone_launch.py`) that starts `rclone rcd --rc-no-auth
--rc-addr :5572` if that port is down, then execs the MCP client with `RCLONE_URL`
pointing at it. Requires `rclone` on PATH. If the daemon can't start, rclone tools
return a clear error and the rest of the hub is unaffected.

## Windows launch note

The hub spawns argv directly (no shell), so `npx`/`uvx` (which are `.cmd` shims) run
via `cmd /c` in their backend specs. The two built wrappers + the rclone launcher are
real Python entry points run under the hub's own interpreter.

## Operating rules

- **GPU $/hr cost-awareness.** RunPod pods, Modal runs, and Lightning machines bill
  while running. **Confirm before spinning up** billable compute, and **stop/delete**
  when done (`stop-pod`/`delete-pod`, `modal_app_stop`, `lightning_studio_stop`).
  Check `get-billing` (RunPod) periodically.
- **Read before destroy.** `terminate`/`delete`/`sync_sync`/`purge` are irreversible.
  List/inspect first (`list-pods`, `operations_about`, `azmcp_*_list`) and confirm the
  target before any destructive call. Prefer `stop` over `delete` when unsure.
- **Env-only creds.** Credentials come from the environment / `accounts.json` (never
  hard-coded). Rotate anything exposed.
- **Account discipline.** Switching/cycling is for the user's OWN accounts; do not use
  it to farm per-account free tiers (ToS + suspension risk).
- **Azure caveat.** The `@azure/mcp` data-plane tools rely on a hand-authored cache
  until `--refresh azure` succeeds in the user's environment; the `az_account_*`
  switch tools work regardless (they drive `az`).

## Per-backend tool inventory

- **RunPod** (`rp`, 50): pods (`list-pods`, `create-pod`, `start-pod`, `stop-pod`,
  `restart-pod`, `delete-pod`, `get-pod`, `update-pod`), serverless endpoints
  (`list/create/update/delete-endpoint`, `run-endpoint`, `runsync-endpoint`,
  `get-job-status`, `stream-job`, `cancel-job`, `retry-job`, `endpoint-health`,
  `purge-endpoint-queue`, `list-endpoint-workers`), templates, network volumes,
  container-registry auths, tags, `list-gpu-types`/`list-cpu-types`/`list-data-centers`,
  `get-billing`.
- **Kaggle** (`kg`, 51): competitions (`competitions_list`, `competition_download`,
  `competition_submit`, `competition_leaderboard`, ...), datasets (`datasets_list`,
  `dataset_download`, `dataset_create`, `dataset_create_version`, `file_upload`, ...),
  kernels (`kernels_list`, `kernel_push`, `kernel_pull`, `kernel_output`,
  `kernel_session_create/status/output/cancel`), models, discussions.
- **rclone** (`rc`, 56): `sync_copy`/`sync_sync`/`sync_move`/`sync_bisync`,
  `operations_*` (copyfile, movefile, delete, purge, mkdir, rmdir, list, stat, about,
  size, check, hashsum, uploadfile, publiclink, settier), `config_*` (listremotes,
  create, update, delete, dump, providers), `core_*` (stats, transferred, bwlimit,
  command, version, quit).
- **Modal** (`md`, 6): `modal_run`, `modal_deploy`, `modal_app_list`, `modal_app_stop`,
  `modal_volume_ls`, `modal_secret_list`.
- **Lightning AI** (`lg`, 7): `lightning_machine_types`, `lightning_studio_start/stop/run`,
  `lightning_job_submit/status/stop`.
- **Azure** (`az`, 14, hand-authored): `azmcp_subscription_list`, `azmcp_group_list`,
  `azmcp_extension_az` (run any `az`), `azmcp_extension_azd`, `azmcp_storage_*`,
  `azmcp_cosmos_*`, `azmcp_monitor_workspace_list`/`azmcp_monitor_log_query`,
  `azmcp_keyvault_key_list`, `azmcp_aks_cluster_list`, `azmcp_bestpractices_get`.
- **Google Cloud** (`gc`, 1): `run_gcloud_command` — runs any `gcloud` command
  (compute, run, storage, container/GKE, ...).

**Registration + full mechanics:** see `tools/mcp/cloud-hub/README.md`. The hub is
not wired into `~/.mcp.json` by this skill — the orchestrator registers it.
