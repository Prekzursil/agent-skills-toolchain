---
title: auth_estate_inventory_2026-07-21
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/auth-estate-inventory-2026-07-21
---

# Auth estate inventory + multi-browser ChatGPT inject (2026-07-21)

**No secrets in this file.** Cookie values, PATs, passwords, and JWT material stay on-disk outside git.

## Multi-browser inject result

Phone-extracted ChatGPT web session cookies (36) were injected into **main profiles**:

| Browser | Profile | Result |
|---------|---------|--------|
| **Chrome** | Default ("Your Chrome" / prekzursil1993@gmail.com) | **WEB_SESSION_OK** |
| **Edge** | Default | **WEB_SESSION_OK** |
| **Comet** | Default (named Prekzursil) | **WEB_SESSION_OK** |
| **Firefox** | `default-release` (`k4cy1nuq.default-release`) | **WEB_SESSION_OK** |

Probe proof (each): `/api/auth/session` returns `user`, `accessToken`, `sessionToken` (not WARNING-only).

### How inject works

| Browser | Technique |
|---------|-----------|
| Chrome / Edge | Chromium blocks `--remote-debugging-port` on the real default User Data path. Use a **directory junction** under `~/.crcp/cookie-bridge/profile-junctions/{chrome,edge}-ud` → real User Data, then CDP `Network.setCookie`. |
| Comet | CDP directly on `%LOCALAPPDATA%\Perplexity\Comet\User Data`. |
| Firefox | Selenium against main profile path. |

Script: `~/.crcp/cookie-bridge/inject_all_main_profiles.py`  
Reapply:

```powershell
python "$env:USERPROFILE\.crcp\cookie-bridge\inject_all_main_profiles.py"
# or single browser:
python "$env:USERPROFILE\.crcp\cookie-bridge\inject_all_main_profiles.py" --only chrome,edge
```

CRCP CLI (isolated durable profile, not main Chrome):

```powershell
python -m crcp auth broker --from-phone-store --phone-browser chrome --port 9340
python -m crcp auth broker --phone-status
python -m crcp auth broker --phone-extract   # needs ADB + phone Chrome USB debug
```

Logon task: **CRCPPhoneCookieReapply** reapplies the phone store into the durable profile (not all main browsers).

---

## Auth planes we have (locations only)

### 1. ChatGPT web session (phone-origin, primary for UI)

| Item | Location |
|------|----------|
| Cookie store (SECRET) | `~/.crcp/cookie-bridge/chatgpt_cookies.json` |
| Extract source | Phone Chrome via ADB `chrome_devtools_remote_*` → port 9223 |
| Key cookie names | `__Secure-next-auth.session-token.0/.1`, `__Secure-oai-is`, `cf_clearance`, `oai-client-auth-session`, `_puid`, `oai-sc`, … |
| Durable isolated profile | `~/.crcp/cookie-bridge/chrome-durable-profile` |
| Apply engine | `~/.crcp/cookie-bridge/apply_durable.py` |
| Main-profile inject | `~/.crcp/cookie-bridge/inject_all_main_profiles.py` |

**Do not commit** `chatgpt_cookies.json`. Treat as password-equivalent.

### 2. Codex / ChatGPT OAuth (API / backend-api)

| Item | Location |
|------|----------|
| Tokens | `~/.codex/auth.json` (`access_token`, `refresh_token`, `id_token`, `account_id`) |
| Mode | `chatgpt` (WorkOS / business) |
| Public client_id | `app_EMoamEEZ73f0CkXaXp7hrann` |
| Account email (business) | `costin.ionescu@bolt.eu` |
| Databricks secret | scope `codex-harness-prekzursil` / key `auth_json` only |

Backend-api works with Bearer; `/api/auth/session` does **not** mint NextAuth from Bearer alone.

### 3. ChatGPT Desktop (Electron)

| Item | Location |
|------|----------|
| userData | `%APPDATA%\Codex\web\Codex` |
| Cookies | `Default\Network\Cookies` (+ partition) |
| CDP | `--remote-debugging-port=9222 --remote-allow-origins=*` |
| Package | `OpenAI.Codex_*` under WindowsApps (version moves) |
| Protocol | `codex://` only |

Desktop cookies lack NextAuth session-token; Desktop is Bearer-first.

### 4. Okta / SSO / enterprise identity

| Item | Notes |
|------|--------|
| IdP | WorkOS-backed OpenAI auth (`auth.openai.com`, provider family WorkOS) |
| Org email | `costin.ionescu@bolt.eu` (Bolt business ChatGPT) |
| Okta app login | Phone Okta works; PC ChatGPT web may still ask another factor / separate session |
| Credentials storage | **Not stored in this repo.** Live Okta password / MFA is in the human IdP + device authenticators only. Agents must not invent or commit Okta passwords. |
| SSO re-auth tooling | `crcp auth sso` (PKCE public client) — for API OAuth, not a substitute for web NextAuth cookies |
| Providers list | `GET /api/auth/providers` → `openai`, `openai-dev`, `openai-sidetron`, … |

If Okta creds exist in a password manager on this machine, that is the source of truth — document path in personal notes, never in git.

### 5. Databricks (bolt-datascience)

| Item | Notes |
|------|--------|
| Profile | `bolt-datascience` / DEFAULT in `~/.databrickscfg` |
| Host | `https://bolt-datascience.cloud.databricks.com` |
| Auth | PAT (redacted in status files) |
| Fan-out | policy_id `0002189219BF8EF3`, `r5d.2xlarge`, stagger 3s |
| Secret scope | `codex-harness-prekzursil` → `auth_json` |
| Owner-ops | Estate-authorized for CRCP/Codex fan-out (see basic-memory owner-ops note) |

### 6. Agent mail / bus

| Item | Notes |
|------|--------|
| Server | `127.0.0.1:8812` (MCPAgentMailSupervisor) |
| Health | `GET /api/health` → `{"status":"ok"}` |

### 7. CRCP broker modes

| Mode | Command | Outcome |
|------|---------|---------|
| Desktop + Bearer | `crcp auth broker` | API auth, often no NextAuth UI |
| Phone store | `crcp auth broker --from-phone-store` | **WEB_SESSION_OK** on durable profile |
| Main browsers | `inject_all_main_profiles.py` | **WEB_SESSION_OK** on Chrome/Edge/Comet/Firefox mains |

---

## Security rules for this inventory

1. Never commit `auth.json`, `chatgpt_cookies.json`, PATs, or cookie values.
2. Reports under `tools/crcp/reports/` must stay **metadata-only**.
3. Phone cookie re-extract when session expires (~days/weeks).
4. Multi-browser inject stops browser processes temporarily — expect a short interrupt.
5. Chrome/Edge CDP on main profiles requires the junction path (documented above).

## Related code in toolchain

- `tools/crcp/crcp/auth_broker.py` — Desktop broker + phone-store entrypoints  
- `tools/crcp/crcp/auth_mirror.py` — Desktop cookie inventory/decrypt  
- `tools/crcp/crcp/auth_sso.py` — PKCE SSO helpers  
- `tools/crcp/crcp/auth_deeplink.py` — `codex://` deeplinks  
- `tools/crcp/scripts/install_phone_cookie_reapply_task.ps1` — logon reapply  
- Reports: `multi_browser_cookie_inject_2026-07-21.json`, `live_auth_probes_2026-07-20.json`, `desktop_session_discovery_2026-07-20.md`