# Databricks Access (MCP + CLI)

_How to reach Databricks from the toolchain. Verified 2026-07 against `bolt-datascience` as `costin.ionescu@bolt.eu`. Contains **no secrets** — tokens live in `~/.databrickscfg`, a password manager, or the git-crypt-encrypted `tools/mcp/cloud-hub/accounts.json`._

## TL;DR

A **Personal Access Token (PAT)** = full programmatic access (REST / cloud-hub MCP / CLI / SDK / Databricks Connect) from any OS, with **no browser, no Okta SSO, no Device Trust** in the path. It does **not** grant the web UI (SSO-gated) and is **per-workspace**.

## cloud-hub MCP (primary path)

The Databricks MCP lives at `tools/mcp/cloud-hub/databricks-mcp/` and drives the Databricks **Python SDK** — it does **not** require the CLI.

- Register an account (env-var profile, same pattern as Modal/RunPod): `db_account_add` with `env = {DATABRICKS_HOST, DATABRICKS_TOKEN}` (e.g. profile `bolt-ds`). Stored in `accounts.json` (git-crypt-encrypted).
- Then use: `dbx_current_user`, `dbx_cluster_list`, `dbx_cluster_create`, `dbx_run_on_cluster`, `dbx_warehouse_list`, and `dbx_api_raw` (escape hatch to any REST endpoint).
- Verified: `dbx_current_user` -> costin.ionescu@bolt.eu; `dbx_cluster_list` -> 501 records.

## Databricks CLI (native shell, optional)

- **Installed:** `winget install --id Databricks.DatabricksCLI -e` -> **CLI v1.7.0**.
- **Auth:** reads `~/.databrickscfg` (profiles `[DEFAULT]`, `[bolt-datascience]`). Verified: `databricks current-user me` -> Costin-Ioan Ionescu.
- **Not required by the MCP** (which is SDK-based). Use it for native shell work: `databricks clusters list`, `databricks fs ls`, `databricks jobs run-now`, and Databricks Connect.

## Compute / GPU

- No unrestricted cluster-create entitlement (a bare create returns `PermissionDenied`).
- Creation works via the **All-purpose cluster policy** `0F61EF4EEC0002D5` (GPU node types allowed, <=18 DBU/hr, auto-termination 10-30 min). Use `dbx_api_raw POST /api/2.1/clusters/create` (the simple helper can't set `aws_attributes`), with:
  - `policy_id = 0F61EF4EEC0002D5`
  - `aws_attributes.instance_profile_arn = arn:aws:iam::287845475429:instance-profile/datascience-instance-profile`, `zone_id = auto`
  - `data_security_mode = LEGACY_SINGLE_USER_STANDARD`
  - `custom_tags.CostCenter` (required; e.g. `ENG-DATA-PLATFORM`)
  - the policy auto-injects S3 log delivery, Glue metastore, JFrog env vars, and S3 role mappings.
- **GPU verified end-to-end:** single-node `g4dn.xlarge` (Tesla T4, 15 GB, driver 580.159.03), runtime `16.4.x-gpu-ml-scala2.12`, PyTorch `2.6.0+cu124`, `torch.cuda.is_available() = True`, GPU matmul executed. Terminate when done (`dbx_cluster_terminate`); it also self-terminates when idle.
- Cheapest GPU nodes: `g4dn.xlarge` / `g5.xlarge` / `g6.xlarge` (1 GPU, 16 GB).

## Security

- PATs bypass Okta Device Trust (the browser-SSO gate) but **not** a workspace **IP access list**, if one is enforced.
- Rotate any exposed PAT; keep tokens only in `~/.databrickscfg`, the git-crypt `accounts.json`, or a password manager — never in plaintext docs/commits.
- Per-workspace: `bolt-common` / `bolt-geo` each need their own PAT.
