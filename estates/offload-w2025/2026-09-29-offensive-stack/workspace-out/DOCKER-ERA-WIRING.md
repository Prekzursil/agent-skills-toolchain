---
title: DOCKER-ERA-WIRING
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/docker-era-wiring
---

# Docker-era wiring report — 2026-10-01

Remote engine: ssh://offload-linux (34.118.74.210, Debian 12, e2-standard-4)

## Final container status (21 containers)

### PentAGI stack — LIVE
| Container | Status | Port |
|---|---|---|
| pentagi | **Up** (serving) | :8443 HTTPS |
| pgvector | **healthy** | :5432 |
| scraper | **Up** | :9443 |
| pgexporter | **Up** | :9187 |
| neo4j | **healthy** | :7474/:7687 |
| graphiti | **restarting** (config issue) | :8000 |

### Decepticon upstream — ALL HEALTHY
| Container | Status | Port |
|---|---|---|
| decepticon-web | **healthy** | :3000/:3003 |
| decepticon-cli | **Up** | — |
| decepticon-langgraph | **healthy** | :2024 |
| decepticon-litellm | **healthy** | :4000 |
| decepticon-neo4j | **healthy** | :17474/:17687 |
| decepticon-postgres | **healthy** | :15432 |
| decepticon-sandbox | **healthy** | — |
| decepticon-skillogy | **healthy** | :9100 |

### Firecrawl self-host — PARTIAL
| Container | Status |
|---|---|
| firecrawl-redis-1 | **Up** |
| firecrawl-playwright-service-1 | **Up** |
| firecrawl-nuq-postgres-1 | **healthy** |
| firecrawl-foundationdb-1 | **Up** |
| firecrawl-rabbitmq-1 | **Exited** (dependency failure) |
| firecrawl-api-1 | **Created** (waiting for rabbitmq) |

## Step-by-step results

### 1. Graphiti Neo4j — PARTIAL
Created `/opt/pentagi/graphiti/openai.yaml` with OpenAI provider config. Container still restarts.
**Issue:** The volume mount maps `./graphiti` → `llm_configs` inside the container, but the Pydantic settings validation still fails. May need the correct config schema for the specific Graphiti version.
**Next action:** Check the Graphiti container's expected config format; or use the `neo4j` container that's already healthy for PentAGI (not Decepticon's).

### 2. Firecrawl — PARTIAL
Cloned to `/opt/firecrawl-src`, built and started. 4 of 6 containers up (redis, playwright, postgres, foundationdb). RabbitMQ exited.
**Issue:** RabbitMQ startup failure (likely resource or config issue on e2-standard-4 with 21 containers already running).
**Fallback:** Cloud API (FIRECRAWL_API_KEY already working in the gateway).

### 3. Langfuse — DEFERRED
Minio image pull fails (`pull access denied` — the Docker Hub repo changed).
**Next action:** Pin to a specific minio release tag or use an external S3-compatible store. Langfuse is optional (telemetry disabled in PentAGI anyway).

### 4. Ollama provider — DONE ✓
- Installed Ollama on the remote VM (CPU-only mode, no GPU on e2-standard-4)
- Pulled qwen3:4b model
- Configured to listen on 0.0.0.0:11434 (Docker bridge reachable)
- Wired into PentAGI: `OLLAMA_SERVER_URL=http://172.17.0.1:11434`
- **Verified:** PentAGI started successfully with Ollama provider active

### 5. GLM provider — DONE ✓
- Wired `GLM_API_KEY` (Z.AI key, sha8 5c264c5d) into PentAGI's .env
- `GLM_SERVER_URL=https://api.z.ai/api/paas/v4` (default)
- **Note:** Rotation happens at the gateway level (zai-keys front); PentAGI uses the key directly. For gateway-mediated rotation, point `GLM_SERVER_URL` at the gateway's proxy when that front is built.

### 6. Bolt stack access — PENDING HOME WAKE
Home machine (desktop-a60s9gp) is asleep. The mount is documented:
- SSHFS: `sshfs prekzursil@100.97.16.36:/d/bolt /mnt/bolt -o ro`
- rsync: `rsync -avz prekzursil@100.97.16.36:/d/bolt/ /mnt/bolt/`
- Container volumes: `/mnt/bolt:/opt/bolt:ro` on pentagi + decepticon-langgraph + decepticon-sandbox
**Blocked on:** home wake. Script prepared at `D:\opt\scripts\mount-bolt.sh` (to execute on the remote).

### 7. Strix — BLOCKED
`strixai/strix` image doesn't exist on Docker Hub. The correct image name needs research.
**Next action:** Find the correct Docker image for Strix (may be at a different registry or require build from source).

### 8-9. Dossier and commit — THIS REPORT

## Port allocation summary

| Port | Service | Stack |
|---|---|---|
| 5432 | pgvector (PentAGI postgres) | PentAGI |
| 8443 | pentagi (HTTPS UI) | PentAGI |
| 9443 | scraper | PentAGI |
| 9187 | pgexporter | PentAGI |
| 7474/7687 | neo4j (PentAGI) | PentAGI/Graphiti |
| 15432 | decepticon-postgres | Decepticon |
| 17474/17687 | decepticon-neo4j | Decepticon |
| 3000/3003 | decepticon-web | Decepticon |
| 2024 | decepticon-langgraph | Decepticon |
| 4000 | decepticon-litellm | Decepticon |
| 9100 | decepticon-skillogy | Decepticon |
| 8000 | graphiti (when healthy) | PentAGI/Graphiti |
| 11434 | ollama (host) | LLM provider |