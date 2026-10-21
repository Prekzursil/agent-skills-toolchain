---
name: grok-lane
description: Local on-demand Grok OpenAI-compatible lane (chenyme/grok2api bridge at
  D:\opt\grok-lane, http://127.0.0.1:8182/v1) — start command, g2a client keys, model
  mapping, credential import, token hygiene. Use when a task needs Grok models
  (grok-4.5/4.6/4.7, grok-4.20-*, grok-imagine-*, voice, stt) via an OpenAI-compatible
  endpoint. Build lane ACTIVE (owner-imported credential); smoke-verified 2026-10-21.
permalink: dqverify-agents-20261013/skills/grok-lane/skill
---

# grok-lane — local Grok OpenAI-compatible bridge

Upstream project: [chenyme/grok2api](https://github.com/chenyme/grok2api) @ `9d77b4d4`
(2026-10-21), built native on this estate (Go 1.25.5 + pnpm, no Docker needed).
Install: `D:\opt\grok-lane` (exe `grok2api.exe`, runtime state `runtime\`).

## Endpoint & auth

- Base URL: `http://127.0.0.1:8182/v1` (OpenAI-compatible:
  `POST /v1/chat/completions`, `GET /v1/models`; health `GET /healthz`)
- Auth: `Authorization: Bearer g2a_*_*` — self-issued client keys (NOT the admin
  password, NOT any Grok credential)
- Admin UI: `http://127.0.0.1:8182/` (JWT login, 15-min access tokens)

## Start / stop (on-demand, detached + hidden window)

```bash
GROK2API_LISTEN=127.0.0.1:8182 bash /d/opt/grok-lane/start-grok-lane.sh   # start; waits for healthz
bash /d/opt/grok-lane/stop-grok-lane.sh                                    # stop (graceful, then force)
curl -fsS http://127.0.0.1:8182/healthz                                    # → {"ok":true}
```

Config enters ONLY via env vars (values never live in committed files):

| Env var | Meaning | Default |
|---|---|---|
| `GROK2API_LISTEN` | listen address | `127.0.0.1:8000` — 8000 is Docker Desktop here, use 8182 |
| `GROK2API_ADMIN_USER` | bootstrap admin username | `admin` |
| `GROK2API_ADMIN_PASSWORD` | bootstrap admin password | random on first start, persisted |
| `GROK2API_JWT_SECRET` | admin JWT signing secret (≥32 chars) | random on first start, persisted |
| `GROK2API_CREDENTIAL_ENCRYPTION_KEY` | AES key for stored credentials | random on first start, persisted |

First start generates random secrets via `openssl rand` and persists them in
`D:\opt\grok-lane\runtime\config.yaml` (mode 600, local-only, never committed).
The script REFUSES to silently rotate a persisted `credentialEncryptionKey`.

## Models (public id → upstream)

Catalog verified live on this install (20 enabled routes): `grok-4.5`,
`grok-4.3`, `grok-4.20-0309-reasoning` / `-non-reasoning`,
`grok-4.20-multi-agent-0309`, `grok-build-0.1`, `grok-composer-2.5-fast`,
`grok-imagine-image` / `-lite` / `-2.0` / `-edit`, `grok-imagine-video` / `-1.5`,
`grok-voice-latest`, `grok-voice-think-fast-1.0/2.0`, `grok-stt`.
`grok-4.6` / `grok-4.7` are discovered dynamically from upstream `/models` once a
Grok Build credential is imported. NOTE: `/v1/models` only lists models servable by
imported credentials — with no account it returns an empty list and completions
404 `model_not_found`.

## Status: ACTIVE — Grok Build lane (smoke-verified 2026-10-21)

One owner-imported **Grok Build** credential (OAuth/Device flow, done via the admin
UI Accounts page; the secret never leaves the local encrypted store). Servable
models live-discovered from upstream `/models`: `grok-4.5`, `grok-4.6`, `grok-4.7`,
`grok-4.7-build-fast`, `grok-composer-2.5-fast`, `grok-imagine-video-1.5`.
Smoke (real call): `POST /v1/chat/completions` model `grok-4.5` → HTTP 200 in
1.9 s, content `grok-lane-ok`, upstream model `grok-4.5-build`.

Web/Console lanes remain unconfigured. To add one, the owner imports via the
admin UI (Accounts page): a grok.com `sso` cookie token (TXT/JSON/JSONL) for the
Web lane, or a Console SSO token. Do NOT share one Build credential across
multiple clients (refresh-token rotation conflicts). If `/v1/models` ever returns
`[]` and completions 404 `model_not_found`, that means no account is currently
available (check `/readyz`).

## Token hygiene

- Grok credentials are AES-encrypted in `runtime\data\backend.db`, keyed by the
  persisted `credentialEncryptionKey` — NEVER rotate it after accounts are stored
  (bricks them), NEVER copy `runtime\` into any repo/commit/skill.
- `g2a_*` client keys are the ONLY thing API callers get; scope them per client
  (rpm/concurrency/model allowlist via admin UI). Change the bootstrap admin
  password after first login, then delete the `bootstrapAdmin` section from
  `runtime\config.yaml`.
- Admin JWT access tokens live 15 min; keep them out of shell history/logs.

## Risks (accepted when using this lane)

- ToS-gray: unofficial reverse-engineered pooling of grok.com/Grok Build/Console
  accounts; realistic account-ban risk (upstream README: research/learning only).
- Cloudflare clean-egress dependency: a flagged IP yields 403s (WARP/FlareSolverr
  sidecars exist in upstream compose but are NOT deployed here).
- Rebuild after upstream churn (~weekly): `cd /d/opt/grok-lane && git pull &&
  cd frontend && pnpm install && pnpm build && cd ../backend &&
  go build -trimpath -ldflags "-s -w" -o ../grok2api.exe ./cmd/grok2api`
