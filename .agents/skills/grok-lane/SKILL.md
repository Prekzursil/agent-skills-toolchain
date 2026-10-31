---
name: grok-lane
description: Local Grok OpenAI-compatible lane (chenyme/grok2api bridge) - launch, keepalive, model catalog, client wiring and budget caps for grok-4.x models on this estate.
permalink: dqverify-agents-20261013/skills/grok-lane/skill
---

# grok-lane — local Grok OpenAI-compatible bridge (ACTIVE, verified 2026-10-21)

[chenyme/grok2api](https://github.com/chenyme/grok2api) @ `9d77b4d4`, built native
(Go 1.25.5 + pnpm, no Docker) at `D:\opt\grok-lane`. Serves the owner's Grok
subscription through an OpenAI-compatible endpoint on loopback — no hosted links, no
API-key billing. Credential = the owner's grok CLI OAuth (`~/.grok/auth.json`),
imported into the bridge's `grok_build` lane; the bridge refreshes tokens itself.

## Quick start (any AI, any machine process)

```bash
curl -s http://127.0.0.1:8182/v1/chat/completions \
  -H "Authorization: Bearer $GROK_LANE_KEY" -H "Content-Type: application/json" \
  -d '{"model":"grok-4.7","reasoning_effort":"high","max_tokens":2048,
       "messages":[{"role":"user","content":"hello"}]}'
# health: curl -s http://127.0.0.1:8182/healthz   → {"ok":true}
# ready:  curl -s http://127.0.0.1:8182/readyz    (false = no account available)
# models: curl -s http://127.0.0.1:8182/v1/models -H "Authorization: Bearer $GROK_LANE_KEY"
```

`GROK_LANE_KEY` is a persistent User+Machine env var (a `g2a_*` client key named
`estate-default`). NOT the admin password, NOT the Grok credential.

## Models and knobs (live-verified 2026-10-21)

Servable through `/v1` (Build lane, 1 synced account) — these are the ONLY ids
`/v1/models` lists; anything else 404s `model_not_found`:

| model id | reasoning_effort menu | notes |
|---|---|---|
| `grok-4.5` | low · medium · high | baseline quality tier |
| `grok-4.6` | low · medium · high · **xhigh** | |
| `grok-4.7` | low · medium · high · **xhigh** | default pick |
| `grok-4.7-build-fast` | low · medium · high · xhigh | **fast mode = pick this variant** |
| `grok-composer-2.5-fast` | none (effort param is stripped) | fastest cheap lane |
| `grok-imagine-video-1.5` | — | video capability |

- **Effort:** OpenAI-style `reasoning_effort` on chat completions (also accepted as
  `reasoning: {"effort": ...}`). Out-of-menu tiers fold to the nearest offered one
  (minimal→low; xhigh/max→high on 4.5). Verified live: low vs xhigh produce different
  reasoning-token counts.
- **Context size: NOT caller-selectable on this bridge.** Each model's context budget
  is its upstream catalog window (auto-managed; the bridge forwards auto-compaction).
  Control output budget with `max_tokens`; control prompt size client-side.
- **Fast mode = model choice** (`grok-4.7-build-fast` / composer), not a boolean param.
- Console-lane routes (voice/stt/imagine-image) are enabled in the admin catalog but
  `available: false` — they need a grok.com web/Console credential; do not advertise them.

## Native TUI wiring (persistent, consistent everywhere)

| Client | Wiring |
|---|---|
| ZCode | `~/.zcode/v2/config.json` → `provider["grok-lane"]` (kind `openai-compatible`, baseURL `http://127.0.0.1:8182/v1`, models grok-4.5/4.6/4.7/-fast/composer). Backup `.bak-pre-grok-lane-20261021`. |
| Codex | `~/.codex/config.toml` → `[model_providers.grok_lane]` (`wire_api = 'chat'`, `env_key = 'GROK_LANE_KEY'`). |
| OpenCode | `~/.config/opencode/opencode.json` → `provider["grok-lane"]` (`@ai-sdk/openai-compatible`, `apiKey: "{env.GROK_LANE_KEY}"`). |
| Claude Code | no native OpenAI-provider routing — call via curl/this skill. |
| grok TUI | is Grok itself — no wiring needed. |

## Persistence

Scheduled task **`GrokLaneKeepalive`** (logon + every 10 min, hidden, IgnoreNew,
10-min limit) runs `D:\opt\grok-lane\keepalive-grok-lane.ps1`: `/healthz` probe → if
down, restart via `start-grok-lane.sh` pinned to `GROK2API_LISTEN=127.0.0.1:8182`.
One silent bridge death already observed (2026-10-21 17:37, no stderr) — worst case
the lane self-heals within 10 minutes. Manual: `GROK2API_LISTEN=127.0.0.1:8182 bash
/d/opt/grok-lane/start-grok-lane.sh` / `stop-grok-lane.sh`.

## Keys and admin

- Client keys: admin API `POST /api/admin/v1/client-keys` (name) → `data.secret` is
  the `g2a_*` value (create returns 201); reveal existing via
  `GET /api/admin/v1/client-keys/<id>/secret`. Default 120 rpm, 8 concurrent; scope
  per client (rpm/concurrency/model allowlist) when handing keys out.
- Admin login: `POST /api/admin/v1/auth/login` → `data.tokens.accessToken` (15-min
  TTL). Bootstrap username/password live ONLY in `D:\opt\grok-lane\runtime\config.yaml`
  (generated on first start; never commit, never echo).
- Ready-made scripts (secrets in-memory only), under the ZCode workspace `out/`:
  `grok-lane-import.py` (credential import), `grok-lane-smoke.py` (key + smoke),
  `grok-lane-catalog.py` (full catalog + knob probes), `grok-lane-wire.py`
  (key env + TUI wiring).

## Credential (the one thing that is NOT regenerable)

The `grok_build` account = the owner's grok CLI OAuth tokens (AES-encrypted in
`runtime\data\backend.db`). Import format (the RAW issuer-map `auth.json` shape is
REJECTED — normalize first):

```json
{"provider":"grok_build","access_token":"<key>","refresh_token":"<refresh_token>",
 "user_id":"...","email":"...","team_id":"...","expires_at":"RFC3339","client_id":"<oidc_client_id>"}
```

POST as multipart `files` to `/api/admin/v1/accounts/import` (also accepts one
refresh-token per line as plain text). The bridge refreshes tokens itself.
**Never rotate `credentialEncryptionKey` after import (bricks stored credentials);
never delete `runtime/data/`; do NOT share one Build credential across multiple
bridge instances (refresh-token rotation conflicts).** Web/Console lanes (sso cookie /
Console token) remain unconfigured — adding one needs the owner's grok.com
credential via the admin Accounts page or `/accounts/web/import`.

## Token hygiene (verbatim rules)

- Secret VALUES (g2a keys beyond the env var, admin password, Grok tokens) never
  appear in any committed file, transcript, or reply — env-var NAMES and paths only.
- Never copy `runtime\` into any repo/commit/skill.
- Admin JWTs live 15 min; keep them out of shell history/logs.

## Risks (accepted when using this lane)

- ToS-gray: unofficial reverse-engineered bridge over a Grok Build account;
  realistic account-ban risk (upstream README: research/learning only).
- Cloudflare clean-egress dependency: a flagged IP yields 403s (WARP/FlareSolverr
  sidecars exist upstream but are NOT deployed here).
- Rebuild after upstream churn (~weekly):
  `cd /d/opt/grok-lane && git pull && cd frontend && pnpm install && pnpm build && cd ../backend && go build -trimpath -ldflags "-s -w" -o ../grok2api.exe ./cmd/grok2api`
  (then restart via the keepalive's start command — the account DB survives rebuilds).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `model_not_found` on a known id | no imported account serves it — check `/v1/models` (only servable ids) and `/readyz` |
| connection refused | bridge down; keepalive restarts ≤10 min, or start manually (command above) |
| starts on :8000 and conflicts | start script default is 8000 (Docker!) — always pin `GROK2API_LISTEN=127.0.0.1:8182` |
| `/` returns 404 in a browser | web UI not mounted on this build; the API (`/v1`, `/healthz`, `/readyz`, `/api/admin`) is the surface |
| import fails `authImportFailed` | wrong document shape — use the normalized single-entry JSON above |

## Verification receipts (2026-10-21)

Import `created:1 synced:1`; smokes HTTP 200 with real completions: grok-4.5
(110 reasoning tokens), grok-4.6 (213), grok-4.7 (41), grok-4.7-build-fast (64);
effort low=33 vs xhigh=53 reasoning tokens on grok-4.7; public `/v1/models` returns
exactly the 6 servable ids; keepalive task registered and test-fired.
