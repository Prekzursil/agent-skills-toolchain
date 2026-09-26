---
title: OPENAI_API_KEY is Tier 5 while Codex runs on ChatGPT Go 2026-08-07
type: reference
permalink: main/reference/openai-api-key-is-tier-5-while-codex-runs-on-chat-gpt-go-2026-08-07
tags:
- openai
- codex
- api
- tier
- capacity
- fanout
---

# OPENAI_API_KEY is Tier 5 while Codex runs on ChatGPT Go

Measured 2026-08-07 by live probe (`e2e/openai_key_probe{,2,3}.py` in `ast-patch167`).
The key literal never entered any transcript; identity is `sha256[:12]=f1bb6b26e252`.

## The headline asymmetry

The estate holds **two OpenAI credentials of very different power**, and the weaker one
has been carrying the fan-out workload:

| | `OPENAI_API_KEY` | `~/.codex/auth.json` |
|---|---|---|
| kind | `sk-proj-*`, 164 ch, project-scoped | ChatGPT OAuth (access + refresh + id_token) |
| tier / plan | **Tier 5** (top) | **`chatgpt_plan_type: "go"`** (entry paid tier) |
| gpt-4o limits | 10,000 RPM / **30,000,000 TPM** | n/a — subscription 5h + weekly windows |
| gpt-4o-mini | 30,000 RPM / **150,000,000 TPM** | n/a |
| gpt-5 | 15,000 RPM / 40,000,000 TPM | Codex models only, via CLI |
| models | **132**, `0/10 gated` | Codex-tuned subset |
| org admin | DENIED (403) — project key | n/a |

`chatgpt_plan_type` is read from the id_token's `https://api.openai.com/auth` claim.
Subscription window measured: 2026-07-31 → 2026-08-31. `auth.json` has **no**
`OPENAI_API_KEY` fallback field populated, so Codex CLI is running purely on the Go
subscription.

**Tier 5 is an inference from the rate-limit tables, but a strong one:** gpt-4o at
30M TPM vs Tier 4's 2M is unambiguous, and two independent models match the published
Tier-5 row exactly.

## Entitlement, not just listing — 0/10 gated

A listed model is not a callable model (Sora / gpt-image / computer-use are usually
org-verification gated). Probed by sending a deliberately invalid field and reading
which error returns: `model_not_found`/403 = gated, a **validation** 400 = entitled,
because a 400 proves the request reached model dispatch instead of dying at the
authorization boundary. All entitled:

`sora-2` · `sora-2-pro` · `gpt-image-2` · `gpt-image-1.5` · `computer-use-preview` ·
`o3-deep-research` · `gpt-5-pro` · `gpt-5-codex` · `gpt-4o-transcribe-diarize`

Catalogue: 41 gpt-5 models, 16 o-series, 4 deep-research, 10 realtime, 22 audio,
6 image, 2 Sora, 2 computer-use, 3 embeddings.

Endpoints reachable: Responses (**incl. server-side `web_search` + `code_interpreter`**),
Batch, Files, Vector stores, Fine-tuning, embeddings, images, audio.

## Two detector traps this probe hit

1. **`GET /v1/responses` returned 401 `missing_scope` — and that was an ARTIFACT.**
   `/v1/responses` is not a listing route (the real shape is `GET /v1/responses/{id}`).
   A `POST` returns **200**. Reporting "Responses API blocked" off the GET would have
   been a single-signal error on the single most valuable endpoint.
2. **`POST /v1/realtime/sessions` → 404** is a route-shape change, not a denial;
   session minting moved to `/v1/realtime/client_secrets`. A 404 on a moved route reads
   identically to a 404 on an absent capability.

## Why it matters operationally

Every failure mode in `rules/common/cross-vendor-dispatch.md` — `win-arg-limit`
(32,767-char CreateProcess cap), `severed-stream`, background-job loss, the
`--ignore-user-config` MCP-inventory workaround, auth.json JWT expiry — is a **Codex
CLI transport** problem. Direct API calls have none of them.

Lanes Codex structurally cannot serve: Batch API (50% off, 24h), Sora video,
gpt-image, embeddings + managed vector stores, fine-tuning, native deep-research
models, computer-use.

Lanes Codex still wins: flat subscription cost (no per-token billing), a real agent
harness (sandboxing, apply_patch, approval modes), and the already-wired
`mcp__codex__codex` rail. This is additive, not a replacement.

## Risk to close

Org admin is DENIED on this project key, so **spend is not readable from it**. Tier 5 at
150M TPM means a runaway loop bills fast. Set a hard project budget cap in the
dashboard; do not rely on noticing.

Related: [[reference_mcp_live_control_proven_2026-07-18]] ·
[[project_capacity_program_2026-07-24]] · [[project_multi_ai_mingle_2026-07-11]]
