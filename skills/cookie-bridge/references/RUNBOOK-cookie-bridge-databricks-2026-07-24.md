---
title: RUNBOOK-cookie-bridge-databricks-2026-07-24
type: note
permalink: dqverify-repo-20261013/skills/cookie-bridge/references/runbook-cookie-bridge-databricks-2026-07-24
---

# Handoff: Cookie bridge, Databricks sessions, profile corruption

**Date:** 2026-07-24  
**For:** Claude (or any fresh agent)  
**Owner machine:** Prekzursil / Windows 11  
**Focus of next session:** Cookie/session estate for ChatGPT + Databricks; main browser integrity; do not re-break prefs/logins/history

---

## 1. One-sentence goal

Get **Databricks web sessions** (3 workspaces) onto the owner’s **main Chrome/Edge** from phone Chrome, without the earlier **main-profile corruption**, while **not re-injecting ChatGPT** (already present) and **preserving open windows** via session restore.

---

## 2. How stuff broke (root cause)

### What broke

Around **2026-07-20 ~21:32 UTC**, `inject_all_main_profiles.py` was used to push **ChatGPT** cookies into **main** Chrome / Edge / Comet / Firefox.

### Why it corrupted

1. **`taskkill /F`** on live browsers while profile DBs were open  
2. Rebound **real** User Data via CDP junction (not an isolated profile)  
3. **No** pre-snapshot of Preferences / Login Data / Cookies  
4. **No** post-integrity checks (account list, login counts, history)  
5. Later session-restore tooling wrote `*.bak-before-session-restore` (~2026-07-21 00:33–00:40)

**Corruption vector = force-kill + main-profile rebind without backup/verify**, not `Network.setCookie` itself.

### What was actually lost vs still OK

| Asset | Chrome | Edge |
|--------|--------|------|
| **Browser signed-in accounts** | **Real loss:** LIVE 2 Google accounts vs bak 6 | **No multi-account loss** — always single MSA `a_visalon@yahoo.com` in LIVE, Jul-21 bak, and Snapshot 150 |
| **Saved passwords (Login Data)** | Healthy (~354 logins) | Healthy (~272 = Jul-21 “Login Data New Backup”) |
| **History** | Large LIVE; **no** Jul-20 History bak to roll back | Same |
| **Bookmarks** | LIVE ≥ bak → keep LIVE | LIVE fine |
| **Site sessions (cookies)** | ChatGPT later re-applied; site logins felt “reset” | Felt like “accounts lost” but was **site cookies/tabs**, not Edge profile multi-account |

**Chrome accounts only in Jul-21 bak (missing from LIVE):**  
`darias.grama@gmail.com`, `dariabonk99@gmail.com`, `realprekzursil@gmail.com`, `mariusvisalon70@gmail.com`  
(Still present LIVE: `prekzursil1993@gmail.com`, `prekzursil@gmail.com`)

### Do **not** use

- `~\.crcp\cookie-bridge\inject_all_main_profiles.py` — **blocked** unless `I_ACCEPT_PROFILE_RISK=1`  
- July 8 **`.sso-mirror-backup-*`** — owner said **leave alone** (not the Jul 20–21 break)

---

## 3. Cookie architecture (what exists)

All under `C:\Users\Prekzursil\.crcp\cookie-bridge\` (restrictive ACLs where set).

| Artifact | Role |
|----------|------|
| `chatgpt_cookies.json` | Phone CDP extract (~2026-07-20); ChatGPT domains |
| `databricks_cookies.json` | Phone CDP extract (2026-07-23); 30 cookies incl. **DBAUTH × 3** + Okta `idx` |
| `cookie_bridge.py` | Phone extract/inject for ChatGPT (ADB → CDP) |
| `apply_durable.py` | ChatGPT → **isolated** durable profile (safe) |
| `databricks_cookie_bridge.py` | Extract/inject DBX; **default = durable isolated only** |
| `safe_main_cookie_inject.py` | **Preferred** main-profile inject (additive setCookie, snapshot, integrity, graceful close) |
| `safe_restore_prefs_accounts.py` | Merge Chrome account_info from Jul-21 bak (browsers must be quit) |
| `RESTORE_FROM_JUL20_21.md` | Runbook |
| Plan (approved): session plan file under `.grok/sessions/.../plan.md` | Full design for non-corrupting main inject |

### Three Databricks workspaces (`~\.databrickscfg`)

| Profile | Host | Org id (from phone tabs) |
|---------|------|---------------------------|
| bolt-datascience | `https://bolt-datascience.cloud.databricks.com` | `3829506390716583` |
| bolt-common | `https://bolt-common.cloud.databricks.com` | `3598988355446810` |
| bolt-geo | `https://bolt-geo.cloud.databricks.com` | `1492481942411573` |

SSO: `bolt.okta.com` (Bolt / costin.ionescu@bolt.eu context for **CLI/API**; browser may use different MSAs).

### Phone extract path

- Device ADB: was `R5CX11Z7RXR`  
- CDP: `adb forward tcp:9223 localabstract:chrome_devtools_remote`  
- Avoid hanging on `cat /proc/net/unix`; prefer existing forward + urllib `/json/version`  
- Owner often has the 3 DBX tabs open among many Chrome tabs  

---

## 4. What was done in this conversation (cookies + restore)

### A. Databricks phone → store

- Built/fixed `databricks_cookie_bridge.py`  
- Extracted **30** cookies to `databricks_cookies.json` (3× DBAUTH + Okta + marketing/analytics on `.databricks.com`)  
- **Judgment (archive work was separate):** not relevant to cookies; BEC enumeration was a different thread fragment  

### B. Safety redesign (after owner reported corruption)

- **Default inject = durable isolated profiles** under `~\.crcp\cookie-bridge\databricks-durable-profile` (and edge durable)  
- **Never** default to kill main Chrome/Edge for DBX  
- Legacy multi-browser force-inject **guarded**  

### C. Main inject (owner wanted cookies on main accounts)

Implemented `safe_main_cookie_inject.py`:

- Pre-snapshot Preferences / Cookies / Login Data / Bookmarks / Local State  
- One browser at a time; refuse if still running  
- CDP `Network.setCookie` **only** (no delete APIs)  
- Probes (no secret values)  
- Graceful `Browser.close`  
- Post-integrity: account_info unchanged, logins not decreased  
- Rollback Preferences+Cookies on integrity fail  

### D. Latest execution (2026-07-23 evening, owner: “ChatGPT already there”)

1. **Skipped ChatGPT inject** (owner instruction).  
2. Snapshot Sessions → `pre-close-sessions-20260723-233044` (+ `-postclose`).  
3. Closed Chrome + Edge (graceful then force).  
4. **`--payload databricks` only** into **main** Chrome and Edge:  
   - Chrome: 30/30 set, probe `looksApp=true` on datascience workspace, integrity OK  
   - Edge: same  
5. Restored Sessions from postclose backup; patched Preferences (`exit_type=Crashed`, `restore_on_startup=1`).  
6. Relaunched both with `--restore-last-session`.  

Reports:

- `~\.crcp\cookie-bridge\safe_main_inject_report_20260723T203206Z.json` (Chrome)  
- `~\.crcp\cookie-bridge\safe_main_inject_report_20260723T203225Z.json` (Edge)  

### E. Not done / still open

- **Chrome account merge** (2 → 6 Google accounts from Jul-21 bak) — dry-run ready, apply needs Chrome quit:  
  `python ~\.crcp\cookie-bridge\safe_restore_prefs_accounts.py --apply --browsers chrome`  
- **Comet** not closed/injected in last pass  
- Session restore is **best-effort** from on-disk `Session_*` / `Tabs_*` (if a window never flushed, it may not return)  
- ChatGPT cookies in store are **~days old**; owner said already present on main — do not thrash unless probe fails  
- DBAUTH can expire; re-extract from phone if DBX drops to Okta login  

---

## 5. Other important threads from the same conversation (not cookies)

### Databricks CLI secret harvest (related estate)

- Broken script used `databricks secrets list --scope` (invalid on CLI v1.7.0) → **0 secrets** false complete  
- Correct: `list-secrets <SCOPE>`, `get-secret <SCOPE> <KEY>`  
- Fixed harvest re-ran: **37** secrets vaulted under `~\.crcp\secret-vault\databricks\` (DPAPI)  
- Most scopes LIST-denied for the user; only readable scopes yield keys  
- Plaintext export may exist under Desktop harvest folders — treat as secret; prefer vault  

### BEC / ROAEP archive (Chrome Claude enumeration)

- Chrome Claude enumerated BEC sites but **could not write** Downloads  
- Judgment: 2007 = two referenda; no separate `bec_ref_2009` / `bec_ref_2019`; 11 real entries  
- Desktop CLI was supposed to reconcile schema against `bec_loc_2012.txt` / `bec_par_2012.txt` and write files + manifest — **handoff if still unfinished** under `C:\Users\Prekzursil\Downloads\`  

### AgentBridge / multi-AI

- AgentBridge retired on Windows; multi-ai-mingle + codex MCP are the rails  
- Budget pacing tools retired with AgentBridge  

### Do not confuse

- **Cookie bridge** = browser web sessions  
- **Databricks CLI PAT / secret vault** = API secrets, not the same as web DBAUTH cookies  
- **SSO mirror Jul 8** ≠ Jul 20 inject corruption  

---

## 6. Safe commands for next agent

```powershell
# Status only
python "$env:USERPROFILE\.crcp\cookie-bridge\databricks_cookie_bridge.py" status
python "$env:USERPROFILE\.crcp\cookie-bridge\safe_main_cookie_inject.py" --dry-run --browser chrome,edge --payload databricks

# Re-extract DBX from phone (tabs open + USB debug)
adb devices
adb forward tcp:9223 localabstract:chrome_devtools_remote
python "$env:USERPROFILE\.crcp\cookie-bridge\databricks_cookie_bridge.py" extract

# Main inject DATABRICKS ONLY (quit that browser first)
python "$env:USERPROFILE\.crcp\cookie-bridge\safe_main_cookie_inject.py" --browser chrome --payload databricks
python "$env:USERPROFILE\.crcp\cookie-bridge\safe_main_cookie_inject.py" --browser edge --payload databricks

# Optional: restore Chrome multi-account list (Chrome fully quit)
python "$env:USERPROFILE\.crcp\cookie-bridge\safe_restore_prefs_accounts.py" --dry-run
python "$env:USERPROFILE\.crcp\cookie-bridge\safe_restore_prefs_accounts.py" --apply --browsers chrome

# Durable canary (does not touch main)
python "$env:USERPROFILE\.crcp\cookie-bridge\databricks_cookie_bridge.py" inject --only chrome-durable
```

**Hard rules for next agent:**

1. Prefer `safe_main_cookie_inject.py` over any kill-all inject.  
2. **Never** `Network.deleteCookies` / wipe cookie jar on main profiles.  
3. **Never** rewrite Preferences as part of cookie inject (account merge is a **separate** step).  
4. Snapshot Sessions **before** closing browsers if windows must be preserved.  
5. After inject CDP (`about:blank`), **restore Sessions** from pre-close backup before normal launch.  
6. Do not touch `.sso-mirror-backup-20260707*` / `20260708*`.  
7. Do not print cookie values / PATs / secret vault plaintext in chat.  

---

## 7. Definition of Done (if continuing)

- [ ] Main Chrome + Edge open bolt-datascience (and ideally common/geo) without Okta wall  
- [ ] ChatGPT still works without re-inject  
- [ ] account_info emails unchanged by cookie ops (Edge still yahoo-only; Chrome 2 or 6 after explicit merge)  
- [ ] Login Data counts not decreased  
- [ ] Owner-confirmed window restore acceptable or missing tabs listed for promote from `pre-close-sessions-*-postclose`  

---

## 8. Suggested skills

| Skill | Why |
|-------|-----|
| `owner-ops-authorization` | Estate-local auth/session work is authorized; avoid over-refusal |
| `systematic-debugging` | If inject/probe fails — root cause before more profile writes |
| `verification-before-completion` | Prove WEB_LIKELY_OK + integrity before claiming done |
| `simplest-probe-first` | Check CDP/ADB/process counts before heavy inject |
| `context-sandbox` | Cookie JSON / CDP dumps are large and secret-adjacent |
| `handoff` | Re-emit if session compacts again |
| `grill-me` / `grill-me-extensive` | Only if owner wants more product decisions (which windows, Comet, account merge) |

---

## 9. Artifact index (paths only)

```
~\.crcp\cookie-bridge\
  chatgpt_cookies.json
  databricks_cookies.json
  safe_main_cookie_inject.py
  safe_restore_prefs_accounts.py
  databricks_cookie_bridge.py
  apply_durable.py
  cookie_bridge.py
  inject_all_main_profiles.py          # DEPRECATED / gated
  RESTORE_FROM_JUL20_21.md
  pre-close-sessions-20260723-233044\
  pre-close-sessions-20260723-233044-postclose\
  pre-main-inject-20260723T203206Z\    # chrome
  pre-main-inject-20260723T203225Z\    # edge
  safe_main_inject_report_20260723T203206Z.json
  safe_main_inject_report_20260723T203225Z.json
  profile-junctions\chrome-ud → real Chrome User Data
  profile-junctions\edge-ud   → real Edge User Data

~\.crcp\secret-vault\databricks\       # CLI secrets (separate from browser cookies)
~\.databrickscfg                       # hosts for 3 workspaces

Handoff copy:
  %TEMP%\agent-handoffs\handoff-cookie-bridge-databricks-2026-07-24.md
```

---

## 10. Message for Claude (paste-ready)

> Continue from cookie-bridge handoff at `%TEMP%\agent-handoffs\handoff-cookie-bridge-databricks-2026-07-24.md`.  
> Main Chrome/Edge already got **Databricks-only** safe inject (2026-07-23) with integrity OK; **do not re-inject ChatGPT** unless owner says it’s broken.  
> Root past failure: `inject_all_main_profiles.py` force-kill on main profiles — use `safe_main_cookie_inject.py` only.  
> Optional: Chrome account merge from Jul-21 Preferences bak (4 missing Google accounts).  
> Leave July-8 sso-mirror alone. Never log cookie values.

---

*Redacted: no cookie values, PATs, or secret vault contents in this document.*