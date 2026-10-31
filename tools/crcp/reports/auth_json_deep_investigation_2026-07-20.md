---
title: auth_json_deep_investigation_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/auth-json-deep-investigation-2026-07-20
---

# auth.json Deep Investigation Report
**Date:** 20.07.2026 · **Status:** MEASURED + SOURCE-GROUNDED  
**Subject:** Owner Codex ChatGPT-managed auth (`~/.codex/auth.json`)  
**No raw tokens printed.**

---

## Executive answers

| Question | Answer | Confidence |
|---|---|---|
| What triggers refresh? | **Both**: proactive (~8 day `last_refresh` OR access JWT within 5 min of exp) **and** reactive (401 recovery) | High — source constants + official CI/CD docs |
| What writes `last_refresh`? | Successful `persist_tokens` after OAuth refresh to `https://auth.openai.com/oauth/token` | High |
| Can we watch file changes? | Yes — `mtime`/`last_refresh` update together on refresh write-back | High (observed mtime == last_refresh) |
| Read-only auth.json? | Proactive refresh will **fail to persist**; 401 recovery also fails if it cannot write. While access_token still valid, **read path can work** without refresh | Medium-High (source implies write on refresh; access still valid 230h+) |
| Refresh token single-use? | **Yes** — server returns `refresh_token_reused` / Exhausted; multi-writer invalidates siblings | High — source + GitHub issues + docs |
| id_token TTL | **1 hour** | High — JWT exp measured |
| access_token TTL | **240 hours (10 days)** | High — JWT exp measured |
| agent_runtime_id on refresh? | Stored in `agent_identity` separately from OAuth tokens; registration is account-bound; **not rewritten by token refresh path** (`persist_tokens` only touches tokens + last_refresh). Stable across token refresh unless identity re-registered | High for “not in token persist”; Medium for absolute forever-stability |
| Can tokens hit ChatGPT backend-api? | **YES — LIVE BRIDGE WORKS** | High — measured 200 on `/backend-api/me` and `/backend-api/conversations` |
| ChatGPT Desktop local API? | **No listeners found** on ChatGPT.exe PIDs this session | High for this sample |
| Multi-instance same auth.json? | **Reads OK short-term; concurrent refresh unsafe** | High — docs + source semaphore is **per process**, not cross-process |

---

## 1. Token anatomy (your current file)

| Field | Observed | Notes |
|---|---|---|
| `auth_mode` | `chatgpt` | ChatGPT-managed OAuth, not API key |
| `last_refresh` | `2026-07-19T14:46:58Z` | Equals file mtime |
| `tokens.id_token` | JWT RS256, iss `https://auth.openai.com` | TTL **1.0h** from iat→exp; **EXPIRED** at audit time |
| `tokens.access_token` | JWT RS256, same iss | TTL **240.0h (10d)**; **VALID ~230h remaining** at audit |
| `tokens.refresh_token` | 211 chars, 3-part JWT-like | Decode failed (opaque/encrypted payload) — still used as OAuth refresh grant |
| `tokens.account_id` | UUID present | Matches ChatGPT account id claim |
| `agent_identity.plan_type` | `business` | Matches JWT chatgpt_plan_type |
| `agent_identity.agent_runtime_id` | present len=30 | Local agent runtime id |
| `agent_identity.agent_private_key` | present len=112 | PKCS8 material for agent identity JWT signing |

### Access token scopes (`scp`)

```
openid, profile, email, offline_access,
api.connectors.read, api.connectors.invoke
```

**Not** listed: `api.model.read` — explains `403` on `GET /v1/models` with “Missing scopes: api.model.read”.

### Auth provider

- OIDC issuer: `https://auth.openai.com`
- Identity: **WorkOS** (`auth_provider: workos` on id_token)
- SSO connection id present in claims
- OAuth client_id: `app_EMoamEEZ73f0CkXaXp7hrann` (Codex/ChatGPT app client)
- Refresh endpoint (source): `https://auth.openai.com/oauth/token` (`grant_type=refresh_token`)

---

## 2. Refresh mechanism (openai/codex source)

Source relocated from historical `core/src/auth.rs` to:

- `codex-rs/login/src/auth/manager.rs`
- `codex-rs/login/src/auth/storage.rs`

### Constants (verbatim semantics)

```rust
const TOKEN_REFRESH_INTERVAL: i64 = 8; // days
const CHATGPT_ACCESS_TOKEN_REFRESH_WINDOW_MINUTES: i64 = 5;
const REFRESH_TOKEN_URL: &str = "https://auth.openai.com/oauth/token";
```

### Proactive refresh (`should_refresh_proactively`)

Triggers if **either**:

1. **Access JWT expiry within 5 minutes** (`now >= exp - 5min`), **or**
2. **`last_refresh` older than 8 days**

Even if access_token still has multi-day JWT life, the **8-day last_refresh rule** forces a refresh on normal `auth()` load path for long-idle files.

### Reactive refresh (`UnauthorizedRecovery`)

On API **401**:

1. Guarded reload of auth from disk (another process may have refreshed)
2. If unchanged → OAuth refresh via refresh_token
3. If still 401 → error to user

Process-local **Semaphore(1)** serializes refresh inside one Codex process. **No cross-process file lock** beyond “reload if disk changed.”

### What gets written on success (`persist_tokens`)

- New `id_token`, `access_token`, optional rotated `refresh_token`
- `last_refresh = Utc::now()`
- Saved via storage backend (file / keyring / hybrid)

### Failure classification (server body codes)

| Code | Meaning | Retry? |
|---|---|---|
| `refresh_token_expired` | RT expired | Permanent until re-login |
| `refresh_token_reused` | Single-use race | Permanent for that RT |
| `refresh_token_invalidated` | Revoked | Permanent until re-login |
| account mismatch | Different account | Permanent |

### Official docs corroboration

ChatGPT Learn “Maintain Codex account auth in CI/CD”:

- stale after ~**8 days** last_refresh
- refresh on normal `codex exec`
- **one auth.json per runner / serialized stream**
- do not share concurrent jobs/machines

---

## 3. Stability strategies for long autonomous ops

### A. Do nothing special (default)
- Works while single writer owns `CODEX_HOME`
- After 8 days or near access expiry, Codex refreshes in place
- Fine for one long local process

### B. Per-process `CODEX_HOME` (recommended multi-node)
1. Seed each worker from a **snapshot** of auth.json
2. Allow that worker alone to refresh its copy
3. Never write back into the seed used by others without a refresh-coordinator

Matches measured Databricks fan-out advice.

### C. Read-only auth.json
- **Goal:** freeze tokens for bridge that only needs access_token
- **While access_token valid:** HTTP `Bearer` calls and possibly Codex reads may work
- **When Codex tries refresh:** write fails → refresh fails → eventually 401 death spiral
- **Use for:** pure bridge process that **never** calls Codex refresh path; copy access_token to memory and ignore file
- **Do not use for:** multi-day Codex CLI automation

### D. Separate refresh_token backup
- Backup of RT is **not** a second concurrent license — RT is single-use at IdP
- Backup helps **recovery after accidental clobber**, not parallel refresh
- First successful refresh invalidates previous RT (`refresh_token_reused` for losers)

### E. Bridge-only credential extract
For ChatGPT live bridge (proven):

```
access_token + ChatGPT-Account-Id header
→ https://chatgpt.com/backend-api/*
```

Bridge process should:

1. Read auth.json once (or watch for updates)
2. Use access_token in memory
3. **Not** trigger Codex refresh
4. Prefer **consumer** role: if access near exp, wait for primary Codex instance to refresh, then re-read file

---

## 4. Live ChatGPT site connection — MEASURED

### Working endpoints (this audit)

| Endpoint | Status | Result |
|---|---|---|
| `GET https://chatgpt.com/backend-api/me` | **200** | Account profile JSON |
| `GET https://chatgpt.com/backend-api/conversations?offset=0&limit=5` | **200** | `total=4`, items with titles/ids/mapping keys |
| `GET https://chatgpt.com/backend-api/conversation/{id}` | **200** | Full conversation with `mapping` |
| `GET https://chat.openai.com/backend-api/...` | **200** | Same (alias) |
| `GET https://api.openai.com/v1/models` | **403** | Missing `api.model.read` scope |
| `GET https://api.openai.com/v1/me` | **200** | Profile-like payload |

### Headers that work

```
Authorization: Bearer <access_token>
ChatGPT-Account-Id: <chatgpt_account_id from JWT claim>
Accept: application/json
```

### Implications for CRCP

**Export-folder is no longer the only ChatGPT path.**  
Primary live path:

1. Auth vault loads Codex auth.json (status only in logs)
2. Bridge uses access_token → backend-api list/get conversations
3. Normalize to bus envelopes (same schema as conversation export fixtures)
4. Stream traces remain protocol/UI fixtures only (no text)

### Limits / risks

- Unofficial for third-party products; **your own account automation** is owner-authorized ops, but OpenAI may rate-limit or change APIs without notice
- Business/SSO account (`workos` + bolt domain) may have org policies
- Access token scopes are **connector-oriented**, yet backend-api accepted them — do not assume platform.openai.com API parity
- Streaming reconnect to `async_source` / `saserver-*-prod` is **unproven**; start with REST poll, then reverse Desktop network if needed

---

## 5. ChatGPT Desktop local API

| Check | Result |
|---|---|
| ChatGPT.exe running (MSIX `OpenAI.Codex_26.715...`) | Yes (~11 processes) |
| Listeners on ChatGPT PIDs | **None observed** this session |
| Local ports related | 8765 basic-memory, 8812 agent-mail, 8787 node — **not** ChatGPT |

Conclusion: Desktop is **not** exposing a documented localhost control plane right now. Bridge via **backend-api + tokens**, not Desktop loopback.

---

## 6. Databricks / Bolt as relay

### Why you might want it
- Move bridge off laptop
- Centralize rate limiting / secret storage in Databricks secret scope (already used for `auth_json`)
- No browser CORS (server-side Python)

### What works architecturally
1. Store **seed** auth.json in secret scope (existing pattern)
2. Job cluster process:
   - Load tokens
   - Poll `backend-api/conversations` + fetch deltas
   - Push packs to agent-mail HTTP or object storage → bus
3. **Only one** refresh writer for that secret (serialized job or lease)

### What not to do
- N concurrent notebooks each refreshing same secret
- Treating RT backup as multi-writer safe
- Expecting CORS fixes to matter for pure server-side calls (they don’t)

### Stream `async_source` reconnect
- Fields in UI stream traces are **hints**, not proven public reconnect APIs
- Plan: Phase 1 REST poll bridge → Phase 2 capture Desktop/web traffic from **your** session for stream URLs if REST insufficient

---

## 7. Multi-instance matrix

| Pattern | Safe? | Notes |
|---|---|---|
| N readers, no refresh | Yes short-term | Until proactive 8d or near-exp or 401 |
| 1 Codex writer + N bridge readers | **Yes (best)** | Bridges re-read after mtime change |
| N Codex processes same auth.json | **Risky** | First refresh wins; others get `refresh_token_reused` |
| N nodes each with own CODEX_HOME seed from same RT | **Unsafe after first refresh** | Only one can hold current RT |
| Per-node seed + coordinator that hands out fresh snapshots | Safe if serialized | Complex; use for fleet |

---

## 8. Recommended CRCP design (auth + ChatGPT rail)

```
[Primary Auth Owner]
  Claude/Codex local CODEX_HOME (writable)
       │ refresh writes auth.json
       ▼
[Auth Vault / file watcher]
  exposes: access_token_valid, last_refresh, account_id (never logs secrets)
       │
       ├─► ChatGPT Live Bridge (HTTP consumer, read-only CODEX_HOME or memory)
       │     GET /backend-api/conversations
       │     GET /backend-api/conversation/{id}
       │     → bus envelopes / fixtures schema
       │
       ├─► Codex workers (optional per-process CODEX_HOME for DBX fan-out)
       │
       └─► Optional DBX relay job (single lease, same REST client)
```

### Phase-1 bridge DoD
1. List conversations via token (done)
2. Fetch full mapping for conversation id from stream/export family
3. Diff against fixture export for conversation `6a5d2b66-…` family if present in account
4. Emit CRCP envelope to bus without Desktop
5. Watch auth.json mtime; on change, reload token

---

## 9. Observability recipes (no secrets)

```powershell
# Watch refresh write-backs
Get-Item $env:USERPROFILE\.codex\auth.json |
  Select FullName, Length, LastWriteTime

# Decode TTL only
python tools/crcp/scripts/auth_jwt_audit.py tools/crcp/reports/auth_status_audit.json
```

File change ⇒ almost certainly `last_refresh` + token rotation.

---

## 10. Bottom line

You already have a **real-time pipe foundation**:

- `auth_mode=chatgpt` access_token **authorizes ChatGPT backend-api**
- Conversation list/fetch **works now** without export files
- Codex refresh is **time-based (8d / 5min-to-exp) + 401**, single-use RT, single writer
- Desktop local API **not available**; Databricks can host the **same REST bridge** with a single refresh owner
- Stream-trace reconnect is research track; **REST bridge is the production path today**