---
name: cloud-infra-toolchain
description: "Use when working with the user's cloud-infrastructure MCP stack fronted by the cloud-hub multiplexer - RunPod, Azure, Google Cloud, Kaggle, rclone, Modal, Lightning AI, and OVHcloud behind one lazy MCP slot. Covers which platform does what, adopt-vs-build-vs-vendor status, per-platform auth + the account-switch/cycle multi-account layer (incl. OVH region rotation ca/eu/us), the workflows (train on Kaggle, rent a GPU on RunPod/Modal/Lightning/OVH, deploy to Cloud Run/AKS, move data with rclone), the rclone rcd daemon prereq, the Windows `cmd /c npx` note, GPU cost-awareness + read-before-destroy operating rules, and the per-backend tool inventory. Multi-accounting can breach a platform's ToS - flag it."
---

# Cloud Infrastructure MCP Toolchain

## Overview

The user's cloud-infra MCP servers are fronted by **`cloud-hub`** — one lazy,
name-preserving multiplexer (`tools/mcp/cloud-hub/`) that answers `tools/list`
from committed caches **without spawning** and lazily spawns **only** the owning
backend on a `tools/call`. Ten platforms, **324 backend tools + 54 account
tools = 378**, behind a single MCP registration. Five servers are **adopted**
(existing MCP packages), four are **built** thin FastMCP wrappers, and one
(OVHcloud) is a **vendored** TS server built from source.

| Platform | pkg / runtime | Auth | Adopt/Build | Tools | Hard limits |
|---|---|---|---|---:|---|
| **RunPod** | `npx @runpod/mcp-server@latest` (Node) | `RUNPOD_API_KEY` | adopt | 50 | GPU billed per-second; pods/endpoints cost money while running |
| **Azure** | `npx @azure/mcp@latest server start` (.NET) | `az login` | adopt | 14* | *hand-authored cache (the .NET server didn't enumerate under piped stdio); `--refresh azure` upgrades it |
| **Google Cloud** | `npx @google-cloud/gcloud-mcp` (Node) | gcloud ADC + `GOOGLE_CLOUD_PROJECT` | adopt | 1 | single `run_gcloud_command` passthrough — full gcloud surface, full gcloud risk |
| **Kaggle** | `uvx kaggle-mcp-server` (Python) | `KAGGLE_USERNAME`+`KAGGLE_KEY` / `~/.kaggle/kaggle.json` | adopt | 51 | free-tier GPU/TPU quota (~30h/wk); kernels are public unless set private |
| **rclone** | `npx rclone-mcp` over `rclone rcd` | RC daemon :5572 | adopt | 56 | **needs the rcd daemon** (auto-started); `sync`/`move`/`delete` are destructive |
| **Modal** | built FastMCP wrapper (`modal` CLI + SDK) | `MODAL_TOKEN_ID`+`MODAL_TOKEN_SECRET` | build | 41 | `run`/`deploy` + any `gpu=` sandbox/function start billable per-second compute; destructive ops gated behind `confirm`/`dry_run` |
| **Lightning AI** | built FastMCP wrapper (`lightning_sdk`) | `LIGHTNING_USER_ID`+`LIGHTNING_API_KEY` | build | 9 | Studios/Jobs bill by the second; `lightning-sdk` must be installed |
| **OVHcloud** | vendored TS MCP (`node ovh-mcp/dist/index.js`) | `OVH_APPLICATION_KEY`+`_SECRET`+`_CONSUMER_KEY` (or OAuth2) per region | vendor+build | 27 | GPU instances bill hourly; `ov_account_switch ca\|eu\|us` flips region+creds (EU/CA/US are separate entities) |
| **Databricks** | built FastMCP wrapper (`databricks-sdk`) | `DATABRICKS_HOST` + (`DATABRICKS_CLIENT_ID`/`_SECRET` OAuth M2M, or `DATABRICKS_TOKEN` PAT) | build | 65 | clusters/warehouses bill while running (set auto-termination); Command Execution is **classic all-purpose clusters only**; destructive/exec tools gated behind `confirm=True` |

The three built wrappers **pre-namespace** their tools (`modal_*`, `lightning_*`,
`dbx_*`) so the hub's collision-prefix never fires. There are **no cross-backend
collisions** today, so every tool keeps its original name.

## Multi-account + cycling (cswap-style)

Every backend can hold **several named accounts** for the user's OWN accounts on
that platform, switch the active one, and **cycle** through them, via six hub-native
tools per backend (served without spawning, handled by the hub):

`<prefix>_account_list · _current · _add · _remove · _switch · _cycle`
— prefixes: `rp` RunPod · `az` Azure · `gc` gcloud · `kg` Kaggle · `rc` rclone ·
`md` Modal · `lg` Lightning · `ov` OVHcloud · `db` Databricks. E.g. `rp_account_switch`,
`kg_account_cycle`, `md_account_add`, `az_account_list`, `ov_account_switch`.

- **env-mode** (runpod, kaggle, modal, lightning, ovh, rclone, databricks): an account is
  a bundle of env vars (literal or `${ENV}` refs), stored in the **gitignored**
  `accounts.json`. For **OVH** each account also carries `OVH_ENDPOINT`
  (`ovh-eu`/`ovh-ca`/`ovh-us`), so `ov_account_switch ca|eu|us` flips region AND
  credentials in one call. For **Databricks** each account bundles `DATABRICKS_HOST`
  with its creds, so `db_account_switch` flips workspace URL AND credentials.
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
| Kaggle | kaggle.com → Account → Create New API Token → `~/.kaggle/kaggle.json` (or `KAGGLE_USERNAME`+`KAGGLE_KEY`) |
| rclone | `rclone config` to add remotes; the hub launcher starts `rclone rcd --rc-no-auth --rc-addr :5572` |
| Modal | `modal token new` (writes `~/.modal.toml`) or `MODAL_TOKEN_ID`+`MODAL_TOKEN_SECRET` |
| Lightning AI | lightning.ai → Settings → Keys → `LIGHTNING_USER_ID`+`LIGHTNING_API_KEY`; `pip install lightning-sdk` |
| OVHcloud | [ovh.com/auth/api/createToken](https://www.ovh.com/auth/api/createToken) → `OVH_APPLICATION_KEY`+`_SECRET`+`_CONSUMER_KEY` (or OAuth2 `OVH_CLIENT_ID`+`OVH_CLIENT_SECRET`). One `ov` account **per region** (set `OVH_ENDPOINT`=`ovh-eu`/`ovh-ca`/`ovh-us` in each). Build once: `cd ovh-mcp && npm ci && npm run build` |
| Databricks | Workspace URL → `DATABRICKS_HOST` (e.g. `https://dbc-xxxx.cloud.databricks.com`). Default = OAuth **M2M service principal**: `DATABRICKS_CLIENT_ID`+`DATABRICKS_CLIENT_SECRET` (workspace → Settings → Identity and access → Service principals → OAuth secrets). PAT fallback: `DATABRICKS_TOKEN` (Settings → Developer → Access tokens). One `db` account **per workspace** (bundles `DATABRICKS_HOST`+creds). `pip install databricks-sdk` |

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

### Rent a GPU (options — pick by workload)
- **RunPod pod** (persistent box): `list-gpu-types` → `create-pod` → `start-pod` →
  work → **`stop-pod`** (keeps disk, stops billing) or **`delete-pod`/`terminate`**
  (removes it). `get-billing` to check spend. Serverless: `create-endpoint` →
  `run-endpoint`/`runsync-endpoint` → `get-job-status`.
- **Modal** (ephemeral function run): `modal_run app.py::fn` or `modal_deploy`;
  stop with `modal_app_stop`. Best for containerized batch/serverless GPU.
- **Modal Sandbox** (interactive GPU container — the Schrödinger path):
  `modal_estimate_cost` to price it → `modal_sandbox_create image=... gpu=a100`
  (mount data via `volumes=` or `modal_cloud_bucket_mount_config`) →
  `modal_sandbox_exec`/`_write_file`/`_upload` to install + run (e.g. a portable
  Suite + FlexLM) → `modal_sandbox_snapshot` to bake a reusable image and skip the
  re-install next run → **`modal_sandbox_terminate confirm=true`** to stop billing.
  Reattach to a running box any time with `modal_sandbox_from_id` (stateless).
- **Lightning Studio/Job**: `lightning_machine_types` → `lightning_studio_start
  name machine=A10G` → `lightning_studio_run` (or `lightning_job_submit` for async)
  → **`lightning_studio_stop`/`lightning_job_stop`**. Best for interactive dev.
- **OVHcloud instance** (persistent root VM, EU/CA/US): `ov_account_switch ca|eu|us`
  to pick region, then drive Public Cloud via **`ovh_api_raw`** (no purpose-built
  tool): `POST /cloud/project/{proj}/instance` with a GPU flavor (`l40s-90`,
  `a100-180`, `l4-90`) → poll `GET .../instance/{id}` until `ACTIVE` → read the
  public IP → run the job over **`ovh_ssh_exec`** → **`DELETE .../instance/{id}`**
  when done to stop billing. Best when you need a full **root** install (e.g.
  Schrödinger + a served FlexLM license) that a serverless container can't host.
- **Databricks GPU cluster** (managed Spark + notebooks): `dbx_spark_versions` /
  `dbx_node_types` → `dbx_cluster_create name spark_version=<*-gpu-ml>
  node_type_id=<GPU> autotermination_minutes=30 wait=true` → run code with
  `dbx_run_on_cluster cluster_id "<code>" confirm=true` (Command Execution =
  **classic all-purpose clusters only**) → **`dbx_cluster_terminate confirm=true`**.
  Best for GPU **data/ML/analytics next to Databricks-hosted data**; the driver /
  CUDA floor is pinned by the runtime image, so for a custom **root** Suite install
  (Schrödinger) prefer Modal/RunPod/OVH and route per-job.

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
- **Modal** (`md`, 41): CLI apps/run (`modal_run`, `modal_deploy`, `modal_app_list`,
  `modal_app_stop`, `modal_app_logs`); **Sandboxes** (SDK container engagement —
  `modal_sandbox_create` with image/gpu/cpu/memory/volumes/`CloudBucketMount`/secrets,
  `_exec`, `_exec_stream`, `_write_file`/`_read_file`, `_upload`/`_download`,
  `_ls`/`_mkdir`/`_rm`/`_stat`, `_list`, `_from_id` reattach, `_poll`/`_wait`/
  `_terminate`, `_tags`, `_snapshot` → reusable image); **functions/containers**
  (`modal_function_call`/`_spawn`, `modal_functioncall_get`, `modal_container_list`/
  `_exec`/`_logs`/`_stop`); **resources** (`modal_volume_create`/`_ls`/`_put`/`_get`/
  `_rm`/`_delete`, `modal_secret_list`/`_create`, `modal_cloud_bucket_mount_config`);
  **identity/cost** (`modal_whoami`, `modal_estimate_cost` — local calc, no billing
  API). Every tool takes an optional per-call `account`/`environment` (fresh
  `modal.Client` per call; no global switch); destructive ops gated by `confirm`/`dry_run`.
- **Lightning AI** (`lg`, 7): `lightning_machine_types`, `lightning_studio_start/stop/run`,
  `lightning_job_submit/status/stop`.
- **Azure** (`az`, 14, hand-authored): `azmcp_subscription_list`, `azmcp_group_list`,
  `azmcp_extension_az` (run any `az`), `azmcp_extension_azd`, `azmcp_storage_*`,
  `azmcp_cosmos_*`, `azmcp_monitor_workspace_list`/`azmcp_monitor_log_query`,
  `azmcp_keyvault_key_list`, `azmcp_aks_cluster_list`, `azmcp_bestpractices_get`.
- **Google Cloud** (`gc`, 1): `run_gcloud_command` — runs any `gcloud` command
  (compute, run, storage, container/GKE, ...).
- **OVHcloud** (`ov`, 27): VPS lifecycle (`ovh_vps_list`/`_info`/`_start`/`_stop`/
  `_reboot`/`_snapshot`/`_create_snapshot`/`_ips`/`_monitoring`), DNS (`ovh_domain_list`,
  `ovh_domain_dns_records`/`_create`/`_update`/`_delete`/`_refresh`, `ovh_domain_zone_info`),
  billing (`ovh_account_info`, `ovh_services`, `ovh_invoices`, `ovh_invoice_detail`),
  **SSH** (`ovh_ssh_exec` run a command, `ovh_ssh_check`), and the API layer
  (`ovh_api_catalog`/`_search`/`_endpoint_detail`, **`ovh_api_raw`** = call ANY of
  500+ OVH endpoints incl. Public Cloud `/cloud/project/…` GPU instances). Region +
  creds per `ov` account (`ovh-eu`/`ovh-ca`/`ovh-us`).
- **Databricks** (`db`, 65): clusters (`dbx_cluster_list`/`_get`/`_create`/`_edit`/
  `_start`/`_restart`/`_resize`/`_terminate`/`_permanent_delete`, `dbx_node_types`,
  `dbx_spark_versions`; GPU = GPU `node_type_id` + a `*-gpu-ml` runtime), **Command
  Execution** (`dbx_ctx_create`/`_status`/`_destroy`, `dbx_exec`, `dbx_run_on_cluster`
  — run code on a **classic all-purpose** cluster), jobs + runs (`dbx_job_*`,
  `dbx_run_submit`/`_get`/`_get_output`/`_list`/`_cancel`/`_repair`), storage
  (`dbx_dbfs_*`, `dbx_volume_*` for Unity Catalog Volumes), SQL warehouses
  (`dbx_warehouse_*`, **`dbx_sql_exec`**), model serving (`dbx_serving_*` incl.
  `dbx_serving_query`), secrets + repos (`dbx_secret_*`, `dbx_repo_*`),
  `dbx_current_user`, and **`dbx_api_raw`** (call ANY Databricks REST endpoint).
  Destructive/exec tools (`dbx_cluster_terminate`/`_permanent_delete`,
  `dbx_warehouse_delete`, `dbx_exec`, `dbx_run_on_cluster`) need `confirm=True`;
  lifecycle tools take an opt-in `wait`. Per-`db`-account = per workspace.

**Registration + full mechanics:** see `tools/mcp/cloud-hub/README.md`. The hub is
not wired into `~/.mcp.json` by this skill — the orchestrator registers it.
