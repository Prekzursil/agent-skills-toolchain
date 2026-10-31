---
title: DOCKER-ERA-FINAL
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/docker-era-final
---

# Docker-era final status — 2026-10-01

Remote engine: ssh://offload-linux (34.116.205.199, e2-highmem-4, 32GB RAM)

## 28 containers: 25 running, 2 completed successfully, 1 needs investigation

### FULLY OPERATIONAL STACKS

**PentAGI (autonomous pentest agent)** — 6 containers ✅
| Container | Status | Notes |
|---|---|---|
| pentagi | **Up** | Serving HTTPS :8443, Ollama + GLM providers active |
| pgvector | **healthy** | Postgres with vector extension |
| scraper | **Up** | Browser automation |
| pgexporter | **Up** | Metrics |
| neo4j | **healthy** | Knowledge graph (shared with graphiti) |
| graphiti | **healthy** | Knowledge graph extraction (config fix worked!) |

**Decepticon upstream (red-team agent)** — 8 containers, ALL HEALTHY ✅
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

**Firecrawl self-host (web scraping)** — 6 containers, ALL RUNNING ✅
| Container | Status |
|---|---|
| firecrawl-api-1 | **Up** |
| firecrawl-redis-1 | **Up** |
| firecrawl-rabbitmq-1 | **healthy** (was failing with 16GB, works with 32GB) |
| firecrawl-nuq-postgres-1 | **healthy** |
| firecrawl-playwright-service-1 | **Up** |
| firecrawl-foundationdb-1 | **Up** |

**Langfuse (LLM observability)** — 6 containers ✅
| Container | Status |
|---|---|
| langfuse-web | **Up** |
| langfuse-worker | **Up** |
| langfuse-clickhouse | **healthy** |
| langfuse-minio | **healthy** (image fix worked) |
| langfuse-postgres | **healthy** |
| langfuse-redis | **healthy** |

### PARTIAL

**Strix** — 1 container, Exited (0) after initialization
The container ran, configured a proxy and CA cert, printed "Container ready", and exited. This is likely a setup/init container. The actual Strix agent needs a different invocation (CLI command or long-running process). Research needed for the correct Docker run command.

### INFRASTRUCTURE

**Ollama** — Running on the remote VM host (not a container)
- qwen3:4b model, listening on 0.0.0.0:11434 (Docker-bridge reachable)
- Persistent systemd service (survives reboots)
- Wired into PentAGI via OLLAMA_SERVER_URL=http://172.17.0.1:11434

## Resource usage
- RAM: 10GB used / 21GB available (of 32GB)
- Disk: 46GB used / 50GB free (of 99GB)
- CPU: 4 vCPUs

## What was fixed in this pass
1. VM upgraded from e2-standard-4 (16GB) to e2-highmem-4 (32GB)
2. RabbitMQ now works (was failing due to RAM)
3. Graphiti config fixed (openai.yaml schema corrected)
4. Langfuse minio image fixed (workflow found working tag)
5. Firecrawl API container started (was blocked on rabbitmq)
6. Ollama made persistent (systemd service with 0.0.0.0 binding)
7. All containers restarted and verified after VM reboot

## What remains
- Strix: needs the correct Docker run command (exited after init)
- Bolt stack mount: home still unreachable (SSH/RDP down)
- PentAGI graphiti integration: graphiti is healthy but PentAGI still shows "failed to initialize" — likely needs the correct service name/port in PentAGI's config