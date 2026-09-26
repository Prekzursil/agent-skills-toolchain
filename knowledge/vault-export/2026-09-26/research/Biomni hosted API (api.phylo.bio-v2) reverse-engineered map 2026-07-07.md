---
title: Biomni hosted API (api.phylo.bio/v2) reverse-engineered map 2026-07-07
type: note
permalink: main/research/biomni-hosted-api-api.phylo.bio-v2-reverse-engineered-map-2026-07-07
tags:
- research-report
- biomni
- phylo
- api
- connector
- reverse-engineering
- high-confidence
---

# Biomni hosted REST API — api.phylo.bio/v2 (reverse-engineered from HAR) 2026-07-07

Source: HAR capture of biomni.phylo.bio (user-exported, DevTools). VERDICT: **BUILDABLE** — clean JSON REST API, NOT a Next.js server action. Auth = Bearer token (WorkOS OAuth via signin.phylo.bio; device-code + offline_access/refresh supported). This EXCEEDS the official 10-tool mcp.phylo.bio MCP.

## Base + auth
- Base: `https://api.phylo.bio/v2`
- Auth: `Authorization: Bearer <token>` (WorkOS access token; short-lived, refreshable). Web app OAuth client_id=client_01KEFGHEBJP3XMFBQ0TR34DW77, redirect api.phylo.bio/v2/auth/workos/callback.

## Endpoint surface (from HAR)
- **POST /v2/agent/sessions/create** — start task. body: `{"project_id","session_mode":"agent","content":<msg>,"submit_initial_message":true,"model_profile":<effort>}` → resp `{session_id, session_status, llm:"claude-opus-4-7:effort-max", model_profile, max_iterations:30, notebook_path, ...}`
- **GET /v2/agent/model-profiles** — EFFORT options: `standard`("Standard",default) / `fast`("Fast") / `premium`("Max",multimodal). → **effort standard/fast/max == model_profile standard/fast/premium**
- GET /v2/agent/{sess} — session detail
- GET /v2/agent/{sess}/messages — poll agent output
- GET /v2/agent/{sess}/streaming — LIVE stream
- GET /v2/agent/{sess}/{background-processes,gpu-sandboxes,hpc-jobs,hpc-pipelines,machines} — runtime/compute introspection
- GET /v2/agent/projects/{proj}/sessions — list sessions
- GET /v2/projects , GET /v2/projects/{proj} — projects
- GET /v2/files/results — result files
- GET /v2/cloud-storage/connections , GET /v2/feedback/session/{sess}

## Still to capture
- SKILLS + RESOURCES attach format — NOT in this HAR (none attached). Either extra fields in the create body, or /v2/agent/skills + /v2/resources endpoints. Need 1 more HAR with a skill+resource attached, or probe from the built connector.

## Connector design (cloud-hub biomni backend, OVH pattern)
Custom MCP wrapping api.phylo.bio/v2 → tools BEYOND the official 10: create_session(model_profile=effort!), list_model_profiles, get_messages, get_streaming, list background-processes/gpu-sandboxes/hpc-jobs/hpc-pipelines/machines, list projects, list files/results. Auth per-account Bearer (env ref); account rotation for multiple Biomni accounts (labeled by email, like Modal/OVH). Add OAuth device-code refresh as follow-up.

## Security
HAR (downloads/biomni.phylo.bio.har) CONTAINS the user's Bearer token — assistant did NOT read the Authorization header into context (only bodies/responses). User must keep HAR private + delete; token wired as env ref, never in chat. Relates [[research-biomni-hosted-mcp-connector-feasibility-2026-07-07]] (which UNDER-stated — said "no REST API"; the documented OpenAPI was a stub but api.phylo.bio/v2 is real).