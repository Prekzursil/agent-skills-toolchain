---
title: desktop_session_discovery_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/desktop-session-discovery-2026-07-20
---

# ChatGPT Desktop → session storage discovery (2026-07-20)

## Status

| Item | Result |
|------|--------|
| Poller task `CRCPChatGPTBridge` | **Gone** (not registered) |
| Port 8820 | **Idle** |
| Outbox cleanup | **608** duplicates → `~/Cowork/trash/crcp-outbox-bloat-20260720-105910`; **63** files remain (max 5 versions/kind/cid) |
| Live bridge delta fix | **Landed** in `crcp/live_bridge.py` — pre-fetch skip, no write if already acked, outbox rotation max 5, checkpoint after fetch |
| Poller restart | **NOT done** (by design — only after delta fix + manual enable) |

## #1 Desktop session storage (found)

ChatGPT Desktop is **Chromium/Electron** (`ChatGPT.exe` + `chrome.dll` in the MSIX package).

### Canonical userData (from live process cmdline)

```
--user-data-dir=C:\Users\Prekzursil\AppData\Roaming\Codex\web\Codex
```

| Path | Role |
|------|------|
| `%APPDATA%\Codex\web\Codex\` | Electron/Chromium **userData** root |
| `...\Default\Network\Cookies` | Primary cookie SQLite (locked while app runs) |
| `...\Default\Partitions\codex-browser-app\Network\Cookies` | Partition cookie jar |
| `...\Default\Local Storage\leveldb\` | Origin localStorage (~3.6 MB) |
| `...\Default\Session Storage\` | Session storage (tiny) |
| `...\Local State` | Chromium local state (`os_crypt`, profiles) |
| `%LOCALAPPDATA%\Packages\OpenAI.Codex_2p2nqsd0c76g0\` | MSIX sandbox (almost empty of real app data) |
| `%LOCALAPPDATA%\OpenAI\Codex\` | CLI/host binaries, **not** web session |
| `%USERPROFILE%\.codex\auth.json` | **OAuth** access + refresh tokens (Codex plane) |

MSIX package path (install only):

`C:\Program Files\WindowsApps\OpenAI.Codex_26.715.4045.0_x64__2p2nqsd0c76g0\`

### Protocol handlers

| Scheme | Source |
|--------|--------|
| **`codex://`** | AppxManifest `<uap:Protocol Name="codex" />` |
| `chatgpt://` | **Not registered** (HKCU Classes + manifest) |

Deep links do **not** appear to carry auth tokens; they open the packaged app.

### Remote debugging

Running processes have **no listen port** for CDP. Launch wrapper needed:

```text
ChatGPT.exe --remote-debugging-port=9222 --user-data-dir=%APPDATA%\Codex\web\Codex
```

(Use a separate profile dir if the live instance holds the lock.)

## #3 Cookie inventory (metadata only)

Read via **Volume Shadow Copy** while Desktop was running (direct open = sharing violation).

Full machine-readable dump: `reports/desktop_cookie_inventory_2026-07-20.json`.

### ChatGPT / OpenAI-related cookies present

| Host | Name | Secure | HttpOnly | Notes |
|------|------|--------|----------|-------|
| `.chatgpt.com` | `_puid` | yes | no | User/account id cookie |
| `.chatgpt.com` | `oai-sc` | yes | no | Long-lived (~1y) client/session marker |
| `chatgpt.com` | `_uasid` | yes | yes | Short-lived session id |
| `chatgpt.com` | `_umsid` | yes | yes | Short-lived session id |
| `chatgpt.com` | `__oailb` | yes | yes | OpenAI LB sticky |
| `chatgpt.com` / `chat.openai.com` / `ws.chatgpt.com` | `__cflb` | yes | yes | Cloudflare LB |
| `.chatgpt.com` / `.openai.com` / `.oaistatic.com` / … | `_cfuvid` | yes | yes | CF visitor (session) |
| `.chatgpt.com` / related | `__cf_bm` | yes | yes | CF bot management (~30m) |

### Classic web-login cookies **NOT** in Desktop jar

- `__Secure-next-auth.session-token`
- `__Host-next-auth.csrf-token` / callback cookies
- `cf_clearance` (Turnstile clearance)

**Implication:** Desktop auth for `/backend-api` is **Bearer OAuth** (same family as `auth.json`), **not** a portable NextAuth cookie session. Cookie export alone is **unlikely** to fully log a stock Chrome profile into ChatGPT web without also injecting access token / completing SSO.

All cookie **values** are Chromium `encrypted_value` (OSCrypt/DPAPI) — export to another browser needs decrypt-on-this-user + re-set via CDP/extension, not a raw file copy.

## #2 OIDC discovery (auth.openai.com)

Fetched `https://auth.openai.com/.well-known/openid-configuration`:

| Field | Value |
|-------|-------|
| issuer | `https://auth.openai.com` |
| authorization_endpoint | `https://auth.openai.com/api/accounts/authorize` |
| token_endpoint | `https://auth.openai.com/api/accounts/oauth/token` |
| revocation_endpoint | `https://auth.openai.com/api/accounts/oauth/revoke` |
| jwks_uri | `https://auth.openai.com/.well-known/jwks.json` |
| userinfo | `https://auth.openai.com/api/accounts/oauth/userinfo` |
| scopes | `openid`, `profile`, `email`, `offline_access` |
| grant_types | `authorization_code`, `refresh_token` only (**no** `client_credentials`) |
| code_challenge | **S256** required |
| token_endpoint_auth | `client_secret_basic`, `client_secret_post`, **`none`** (public clients OK) |

No service-account client_credentials path in discovery.

## Outbox / live_bridge fixes (code)

1. **`scripts/cleanup_outbox.py`** — keep max N versions/kind/cid; move rest to `~/Cowork/trash/…`
2. **`crcp/live_bridge.py`**
   - Skip fetch when list `update_time` ≤ saved state
   - Skip outbox write if spool already **acked** for that event key
   - Checkpoint **immediately after successful fetch** (stops re-download on publish failure)
   - **`rotate_outbox(cid, max_versions=5)`** after each write

## Recommended next steps (mirror path)

1. **Do not** expect raw Cookies file import to “always log into web.”
2. Prefer: **refresh `auth.json`** + optional **browser profile broker** that injects Bearer / SSO cookies via CDP.
3. Build `crcp auth mirror` only after DPAPI decrypt path is verified on a **closed** Desktop (or VSS + `Local State` os_crypt key).
4. `crcp auth deeplink` → `codex://…` only opens Desktop, not web session.
5. `crcp auth sso` → drive `authorization_endpoint` with PKCE + public `client_id` from auth.json (`app_EMoamEEZ…`), capture callback cookies in a controlled profile.

## Safety

- No cookie **values** or tokens written into this report.
- Inventory JSON is **names/flags/lengths only**.
- Poller left **stopped**.