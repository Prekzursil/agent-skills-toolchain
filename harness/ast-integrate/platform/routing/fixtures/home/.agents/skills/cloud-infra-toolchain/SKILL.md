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

### Multi-account + cycling (cswap-style)
### Auth-setup runbook
### Workflows
### Train on Kaggle (free GPU/TPU)
### Rent a GPU (options — pick by workload)
### Deploy an app
### Move data (rclone)
### rclone `rcd` daemon prereq
### Windows launch note
### Operating rules
### Per-backend tool inventory
### Databricks as a Codex agent host (not just Spark)
