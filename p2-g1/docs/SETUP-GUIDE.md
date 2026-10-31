# MCP Toolchain — Setup & Onboarding Guide

How to configure this whole personal MCP toolchain correctly **for your
situation**. Eight servers across two domains:

- **Social-media MCPs** (private/own-account read): `insta-mcp`,
  `fb-messenger-mcp`, `whatsapp-mcp` (POC-only), `tiktok` (BUILT, read-only
  public scraper, 9 tools).
- **Drug-discovery / research MCPs** (registered but **disabled-by-default**):
  `tooluniverse`, `rdkit`, `schrodinger`, `gogcli-classroom`.

The right setup depends on **account state** (IG clean vs flagged, FB
group vs 1:1, Classroom student vs teacher, WhatsApp primary vs secondary) and
**where you run** (LOCAL home residential IP vs CLOUD/datacenter). Follow the
decision tree first, then the per-MCP section.

> **Conventions.** Windows is the primary host: `~` = `C:\Users\Prekzursil`,
> repos in `~\source\repos\`, Python venvs use `.venv\Scripts\python.exe`.
> POSIX equivalents are noted inline (`~/source/repos/`,
> `.venv/bin/python`). Source of truth for registrations is
> `~\.claude.json` (`mcpServers` user scope; per-project enable/disable under
> `projects."<projectPath>"`).
>
> **Universal safety rule.** Every social MCP uses a **private/unofficial API** →
> Terms-of-Service and account-ban risk. Keep usage human-paced, read before
> write, never commit secrets (all repos `.gitignore` cookies/sessions/tokens/
> `auth_info/`/`*.db`/`.env`). If a platform throws a checkpoint/challenge, **STOP
> and surface it** — do not hammer.

---

## 0. Decision tree (start here)

```
                          ┌─────────────────────────────┐
                          │  Which MCP do you need?      │
                          └──────────────┬──────────────┘
              ┌──────────────────┬───────┴────────┬───────────────────┐
              │                  │                │                   │
        SOCIAL MEDIA       MESSAGING          RESEARCH /          GOOGLE
        (read own)         (chats/DMs)        DRUG-DISCOVERY      CLASSROOM
              │                  │                │                   │
   ┌──────────┴────────┐        │        ┌───────┴────────┐          │
   │                   │        │        │  tooluniverse  │   ┌──────┴───────┐
INSTAGRAM           TIKTOK      │        │  rdkit         │   │ Account type? │
(insta-mcp)        (BUILT)      │        │  schrodinger   │   └──────┬───────┘
   │                   │        │        └───────┬────────┘     ┌─────┴──────┐
   │            ┌──────┴─────┐  │        DISABLED-by-default     │            │
   │            │ Want WHAT? │  │        → §6 enable per-       STUDENT     TEACHER
   │            └──────┬─────┘  │           project + restart    │            │
┌──┴───────┐    ┌──────┴──────┐ │                              writes 403   full
│ Account  │    │ A own-priv  │ │                              reads OK     access
│ state?   │    │   = IMPOSS. │ │                                  └────┬───────┘
└──┬───────┘    │ B own-public│ │                                  gogcli-classroom (§7)
   │            │   = official│ │                              ┌────────────────────┐
┌──┴────┐       │ C discovery │ │                              │ FB / WhatsApp split │
CLEAN  FLAGGED  │   = BUILD   │ │                              └────────────────────┘
│        │      └─────────────┘ │                          ┌──────────┴──────────┐
│        │                      │                    FB MESSENGER          WHATSAPP
│   proxy FIRST              ┌──┴────────┐            (fb-messenger-mcp)   (whatsapp-mcp)
│   (§3 Byteful)            FB or WA?    │            ┌──────┴──────┐       │
│   minimal calls           └──┬────────┘            │ Thread type?│   ⛔ POC ONLY —
│   ban risk HIGH              │                     └──────┬──────┘   do NOT register
│                              │                  ┌─────────┴────────┐  or use. §5.3
└──────┬─────────┘         (see right)        GROUP/ROOM/PAGE     1:1 DM
       │                                        works (§5.2)      ⛔ E2EE = unreadable
   ┌───┴────────────────┐                                          by ANY API. Dead end.
   │ Where do you run?   │  ◄── asked for EVERY social/tiktok MCP
   └───┬────────────────┘
   ┌───┴──────┐
 LOCAL      CLOUD / datacenter
 (home       │
  residential│  → set up Byteful residential proxy FIRST (§3),
  IP)        │     route IG/FB/TikTok egress through it.
 no proxy    │     (WhatsApp tolerates a cloud IP — direct.)
 needed
```

**Read the tree as:** pick the MCP → resolve its **account-state** branch →
resolve **LOCAL vs CLOUD** (proxy or not). The three recurring concerns —
**residential proxy** (§3), **restart-to-load** (§2), **per-project enable**
(§6) — are documented once and referenced from each MCP.

---

## 1. Prerequisites (host-level, once)

| Need | Windows | POSIX | Used by |
|---|---|---|---|
| **Claude Code CLI** (`claude mcp ...`) | installed | installed | all |
| **Node.js ≥18** | `node`, `npm` on PATH | same | insta-mcp, whatsapp-mcp |
| **Python 3.11+** | per-repo `.venv` | per-repo `.venv` | fb-messenger, tiktok, rdkit, schrodinger |
| **uv / uvx** | `~\.local\bin\uvx.exe` on PATH | `~/.local/bin/uvx` | tooluniverse |
| **gog.exe v0.21.0** | `~\tools\gogcli\gog.exe` | platform `gog` binary | gogcli-classroom |
| **Schrodinger 2026-2** | `D:\Program Files\Schrodinger 2026-2` | e.g. `/opt/schrodinger2026-2` | schrodinger |
| **ADB + BlueStacks** (to read IG app version) | `adb` on PATH | same | insta-mcp (one-time) |
| **A browser with logged-in facebook.com** + C3C cookie-export extension | — | — | fb-messenger-mcp |

> **CLI reality:** `claude mcp` exposes `add` / `get` / `list` / `remove` /
> `add-json` — **no enable/disable subcommand**. Per-project enabling of the
> disabled-by-default research MCPs is a **config edit** (§6), not a CLI flag.

---

## 2. Shared concern — loading tools (restart) + verifying

**MCP tools only load when Claude Code restarts.** After any
`claude mcp add ...`, restart CC; then the server's tools appear in-session.

Verify any server:

```bash
claude mcp list           # health-checks every registered server (✓ Connected)
claude mcp get <name>     # shows the resolved command/args/env for one server
```

> When a social MCP is registered but not yet restarted-into, you can still
> exercise the same capability via the repo's scripts (e.g. a one-shot Node call
> against the saved Instagram session) — the underlying client exposes the same
> methods.

---

## 3. Shared concern — the Byteful residential proxy (CLOUD egress only)

**When you need it:** any time IG / FB / TikTok egress leaves a **datacenter
IP** (Oracle VM, any cloud host).
residential egress is required. **Running LOCAL on the home residential IP → no
proxy needed** for any platform. **WhatsApp tolerates a cloud IP → direct, no
proxy** even on cloud.

**Provider:** Byteful (ex-Ping-Proxies) residential, passthrough gateway
`residential.byteful.com` (HTTP/HTTPS/SOCKS5, **no TLS-termination** — the
correct, non-MITM type for a flagged account carrying a signed app body).

**⚠️ Credential gotcha (do not guess):** country/sticky targeting is **NOT a
username-append**. Appending `-cc-RO` / `-country-` / `-region-` returns **407**.
The exact sticky credential must come from the dashboard **Generator**
(Sticky + HTTP, pick Country=Romania → Generate). Verified working format:

```
user: <BYTEFUL_USER>_c_<cc>_s_<SESSION>  (underscores: _c_<cc> country e.g. ro, _s_<id> sticky)
pass: <BYTEFUL_PASS>
host: residential.byteful.com:<port>     (one sticky port per session/endpoint)
```

> The real `<BYTEFUL_USER>` / `<BYTEFUL_PASS>` values live **only** in the gitignored
> `proxy-endpoints.secret` (below) — never hard-code or commit them.

**Provisioned endpoints** (gitignored) live in
`~\source\repos\social-mcp-deploy\proxy-endpoints.secret` (e.g. IG=:8533
Cluj, FB=:8605 Sibiu; spares persisted). Validate before login:

```bash
# returns a real DIGI-Romania (AS8708) residential IP; same endpoint = sticky
# (substitute the user:pass from proxy-endpoints.secret — never commit the literal string)
curl -x "http://<BYTEFUL_USER>:<BYTEFUL_PASS>@residential.byteful.com:8533" https://api.ipify.org
```

**Flagged-account caveat:** a residential IP is **necessary, not sufficient** —
test the exit IP/geo *before* logging in; IG may still re-checkpoint a flagged
account even via a clean residential exit.

**Wiring per MCP:** insta-mcp / fb-messenger read a proxy from env/config (see
their sections); TikTok's `TikTokApi` takes a `proxies=` arg (env `TIKTOK_PROXY`).

---

## 4. INSTAGRAM — `insta-mcp` (LIVE / registered)

Repo: `~\source\repos\insta-mcp` · Runtime: Node (JS, `instagram-private-api`).
Account `@realprekzursil`. Covers own **saved / posts / feed / search / DMs /
liked / stories / followers / following**.

### 4.1 Prerequisites
Node ≥18; ADB+BlueStacks reachable once (to read the device IG app version).

### 4.2 Install + auth
Session-based, **2FA stays ON**. One-time login writes a session; the MCP rides
the session and never password-logs-in (so 2FA never re-triggers). The real
password is **never stored** (`data/credentials.json` holds username + a
placeholder).

```bash
# one-time (2FA-aware, carries the app-version override):
node login.mjs            # → data/session.json
# re-auth when the session expires: run it again
```

### 4.3 Decision branch — account state + egress

| Your state | Setup |
|---|---|
| **CLEAN + LOCAL** (home residential IP) | No proxy. Register and go. |
| **CLEAN + CLOUD** | Set up Byteful proxy **first** (§3), route IG egress through it, then login. |
| **FLAGGED** (this account is flagged) | **Highest care.** Use the residential proxy even when borderline; keep calls **minimal**; expect possible re-checkpoint; **ban risk is HIGH**. **Rotate the IG password** — it was flagged during setup and was pasted into a transcript. |

### 4.4 Register
```bash
claude mcp add insta-mcp -- node C:/Users/Prekzursil/source/repos/insta-mcp/dist/index.js
# POSIX: claude mcp add insta-mcp -- node ~/source/repos/insta-mcp/dist/index.js
```
Then **restart CC** (§2).

### 4.5 Verify
After restart: call `get_account_overview` (or `get_inbox`) — a clean return =
the session is live and the version override is holding.

### 4.6 Troubleshooting
- **`unsupported_version` / `checkpoint_required` with
  `checkpoint_url=/web/unsupported_version/`** — the library (1.46.1) spoofs a
  stale `APP_VERSION=222.0.0.13.114`; this web-only checkpoint can't be resolved
  by the private API. **FIX:** impersonate the device's **current** IG app
  version. Read it: `adb -s 127.0.0.1:5555 shell "dumpsys package com.instagram.android | grep versionName"`
  → e.g. `431.1.0.49.82`. Override via env when registering:
  `IG_APP_VERSION=431.1.0.49.82` (+ `IG_APP_VERSION_CODE=383810323`). (Already
  patched into `src/index.ts`.)
- **Session expired** → `node login.mjs` again.
- **Checkpoint/challenge during use** → STOP; do not retry (raises ban risk on a
  flagged account). Full runbook: `~\source\repos\insta-mcp\SETUP-2FA.md`.
- Dep audit: 2 critical npm vulns in deps (project's own code scans clean).

---

## 5. FACEBOOK MESSENGER + WHATSAPP

### 5.1 `fb-messenger-mcp` (being registered) — GROUPS/ROOMS/PAGES only

Repo: `~\source\repos\fb-messenger-mcp` · Runtime: Python venv
(`fbchat-muqit`, FastMCP `server.py`). Covers Messenger **group / room / page**
threads + message search.

**⛔ Hard limit (account-state branch):** **personal 1:1 Messenger DMs are
end-to-end encrypted → unreadable by any unofficial API.** This is a permanent
dead end — the only path to a 1:1 conversation is the official Messenger app
driven on-device. Say so plainly; never imply the MCP can read 1:1 DMs.

| Thread type | Path |
|---|---|
| **Group / room / page** | `fb-messenger-mcp` (`list_threads` / `read_thread` / `search_messages`) |
| **Personal 1:1 DM** | ⛔ E2EE — not accessible by any API. On-device official app only. |

**Prereqs:** Python venv; a logged-in `facebook.com` browser + the **C3C**
cookie-export extension.

**Auth (cookies):** export facebook.com cookies via C3C →
`~\source\repos\fb-messenger-mcp\data\cookies.json` (gitignored).

**Egress branch:** CLOUD → Byteful proxy (§3); LOCAL → direct.

**Register:**
```bash
claude mcp add fb-messenger -- C:/Users/Prekzursil/source/repos/fb-messenger-mcp/.venv/Scripts/python.exe C:/Users/Prekzursil/source/repos/fb-messenger-mcp/server.py
# POSIX: claude mcp add fb-messenger -- ~/source/repos/fb-messenger-mcp/.venv/bin/python ~/source/repos/fb-messenger-mcp/server.py
```
Then **restart CC** (§2).

**Verify:** `whoami` (confirms cookie session) then `list_threads`.

**Troubleshooting:** empty/auth error → cookies expired, re-export via C3C.
1:1 thread "missing" → it's E2EE, not a bug (see hard limit). FB feed/saved/posts
have **no API** and there's **no FB app on BlueStacks** → drive a logged-in
`facebook.com` browser (Claude-in-Chrome / Playwright) for those.

### 5.2 FB feed / posts / saved (no MCP)
There is no API path; drive the logged-in `facebook.com` session in the browser
(`facebook.com/saved`, a profile), scroll + screenshot, confirm with a link.

### 5.3 `whatsapp-mcp` — ⛔ PROOF-OF-CONCEPT ONLY (do NOT register/use)

Repo: `~\source\repos\whatsapp-mcp` (`jlucaso1/whatsapp-mcp-ts`, Baileys,
Node/TS). It was **built and vetted clean**, and it *technically* reads personal
chats and can send — **but it is kept only as a proof-of-concept.**

> **Recommendation: do NOT register or use it.** It exists to prove the approach
> works; it is **not** part of the live toolchain. Reasons: Baileys is unofficial
> → WhatsApp ban risk (would require a **secondary number**, never the primary);
> 22 transitive CVEs (DoS-class); first-run QR rendered via a public service.
> This block is for completeness — there is **no recommended setup path**. If you
> ever revisit it, treat a secondary number as mandatory and re-audit deps first.

(Account-state note had it existed live: **primary number = unacceptable ban
risk; secondary number only.** This is academic — the POC stays unregistered.)

---

## 6. Shared concern — enabling the disabled-by-default research MCPs

`tooluniverse`, `rdkit`, `schrodinger`, `gogcli-classroom` are **registered in
user scope but DISABLED-by-default** in every project's `disabledMcpServers`
(part of a deliberate token-reduction harness — **do not wipe that list**).

**To enable for a project** (there is **no `claude mcp` enable flag** — §1):

1. Open `~\.claude.json` (backup first; one exists at
   `~\.claude.json.bak-mcp-2026-06-06`).
2. Under `projects."<your-project-path>".disabledMcpServers`, **remove** the
   server name(s) you need (e.g. `"tooluniverse"`, `"rdkit"`).
3. **Restart CC** (§2). The server's tools now load for that project.
4. When done, add the name back to keep the token budget lean.

> `enabledMcpjsonServers` / `disabledMcpjsonServers` govern `.mcp.json`-sourced
> servers separately; the four research MCPs are user-scope, so the
> `disabledMcpServers` list is the lever.

---

## 7. RESEARCH / DRUG-DISCOVERY MCPs

All four share the **enable-per-project + restart** branch (§6). None of the
three drug MCPs needs network auth; their account-state axis is simply *"is it
enabled for this project?"*. `gogcli-classroom` adds a student/teacher axis.

### 7.1 `tooluniverse` — 2206 biomedical tools (DDI / ADMET / CYP / targets / FDA labels)
- **Prereqs:** `uvx` on PATH (Win `~\.local\bin\uvx.exe`, POSIX `~/.local/bin/uvx`).
- **Install/auth:** none — `uvx` fetches the pinned package on demand; calls
  public biomedical APIs (OpenFDA etc.), **no API key**.
- **Decision branch:** enabled for this project? → §6 + restart. Else leave off.
- **Register:**
  ```bash
  claude mcp add tooluniverse -e PYTHONIOENCODING=utf-8 -- uvx tooluniverse==1.2.4
  ```
  (`PYTHONIOENCODING=utf-8` stops Windows cp1252 from corrupting non-ASCII stdio
  output.) Cross-platform: package + args identical; only `uvx` location differs.
- **Verify:** `claude mcp get tooluniverse` → `✓ Connected`; call a DDI/label tool.
- **Troubleshoot:** garbled output → the UTF-8 env var is missing. `uvx` not
  found → install `uv` / add to PATH. Skills live at `~\.agents\skills\tooluniverse-*`.

### 7.2 `rdkit` — 74 cheminformatics tools (tandemai-inc/rdkit-mcp-server, MIT)
- **Repo:** `~\source\repos\rdkit-mcp-server` (`.venv`). Local compute, **no auth**.
- **Decision branch:** §6 enable-per-project + restart.
- **Register:**
  ```bash
  claude mcp add rdkit -- C:/Users/Prekzursil/source/repos/rdkit-mcp-server/.venv/Scripts/python.exe C:/Users/Prekzursil/source/repos/rdkit-mcp-server/run_server.py --transport stdio
  # POSIX: ...\.venv/bin/python run_server.py --transport stdio
  ```
- **Verify:** `claude mcp get rdkit` → `✓ Connected`.
- **Troubleshoot (two known gotchas):**
  - **Transport:** the server **defaults to SSE on :8000** — you **MUST** pass
    `--transport stdio` (as above) or Claude Code can't speak to it.
  - **Dead RDKit pin:** upstream pins `rdkit==2025.3.1` (gone from PyPI). This
    install uses `rdkit 2026.3.3` + `pip install --no-deps .`. If you recreate
    the venv: install rdkit + `mcp` first, then `pip install --no-deps .`.

### 7.3 `schrodinger` — custom 67-tool wrapper over local Schrodinger 2026-2
- **Repo:** `~\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp`
  (`server.py` FastMCP +
  `_sch_helper.py` runs inside `run.exe python3`). Install at
  `D:\Program Files\Schrodinger 2026-2`.
- **Auth/scopes:** no network auth. **Decision branch within the branch:** the
  **driver tools** (`prepwizard`, `glide_grid`, `ligprep`, `qikprop_admet`,
  `glide_dock`, `prime_mmgbsa`) consume **Schrodinger license tokens** and run
  synchronously (`-WAIT`) → a FlexLM / license server (or local license file)
  must be **reachable** for those. The structure/cheminformatics tools
  (`schrodinger_version`, `backend_info`, `smiles_to_3d`, `molecule_properties`,
  `convert_structure`, `run_schrodinger_python`) need **no** license.
  The core `prepwizard` → `glide_grid` → `ligprep` → `glide_dock` →
  `prime_mmgbsa` pipeline was **validated live E2E** on 2026-06-06 against the
  prior 2022-4 install (PDB 3PTB plus warfarin QikProp). The expanded 67-tool
  surface targets 2026-2 and still needs its live-box smoke gate. See
  `schrodinger-mcp/VALIDATION.md`.
- **Decision branch:** §6 enable-per-project + restart.
- **Register:**
  ```bash
  claude mcp add schrodinger -e "SCHRODINGER=D:\Program Files\Schrodinger 2026-2" -- C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/schrodinger-mcp/.venv/Scripts/python.exe C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/schrodinger-mcp/server.py
  # POSIX: -e SCHRODINGER=/opt/schrodinger2026-2 -- ~/source/agent-skills-toolchain/tools/mcp/schrodinger-mcp/.venv/bin/python ~/source/agent-skills-toolchain/tools/mcp/schrodinger-mcp/server.py
  ```
- **Verify:** call `schrodinger_version` / `backend_info` (no license needed).
- **Troubleshoot:** version tool fails → `$SCHRODINGER` wrong (note the space in
  the Windows path). Driver tool hangs/errors → license server unreachable (the
  grid is built in-server by `glide_grid`; pass `glide_dock` the `.zip` it
  produced). The server never imports `schrodinger` in-process — all subprocess
  goes through one no-shell `_exec()` chokepoint with `_safe_path()` validation;
  `run_schrodinger_python` is a **local single-user escape hatch**.

### 7.4 `gogcli-classroom` — Google Classroom over `gog.exe`
- **Prereqs:** `gogcli-mcp-classroom` (npm global) + `gog.exe v0.21.0` at
  `~\tools\gogcli\gog.exe` (checksum-verified).
- **Auth:** Google **OAuth Desktop** client. Steps: Google Cloud Console →
  project → enable Classroom API → OAuth consent (External + Testing + add
  yourself as a test user) → Credentials → OAuth client **Desktop** → download
  `client_secret.json`. Then:
  ```bash
  gog auth credentials <client_secret.json>
  gog auth add <email> --services classroom     # loopback consent click
  ```
  **Prefer loopback auto-capture over `--remote`** (the manual `--remote` flow
  lost the redirect to browser churn). The token is stored in the **OS keyring**,
  not in `~\.claude.json`. Testing-mode refresh token ≈ 7-day expiry; no
- **Decision branch — account type:**

  | Account | Capability |
  |---|---|
  | **STUDENT** (personal Gmail, e.g. `prekzursil1993@gmail.com`) | **Reads + own-submissions work; write tools return 403.** |
  | **TEACHER** | Full read/write (create coursework, grade, etc.). |

  Plus §6 enable-per-project + restart.
- **Register:**
  ```bash
  claude mcp add gogcli-classroom \
    -e GOG_ACCOUNT=prekzursil1993@gmail.com \
    -e GOG_PATH=C:\Users\Prekzursil\tools\gogcli\gog.exe \
    -- gogcli-mcp-classroom
  # POSIX: -e GOG_PATH=<platform gog binary>
  ```
- **Verify:** `gog -a <email> classroom courses list` should return your courses
  (round-trip confirmed: 3 real courses). Then `claude mcp get gogcli-classroom`.
- **⚠️ Accuracy note:** at last audit `gogcli-classroom` was **absent** from
  `~\.claude.json` / `claude mcp list` (likely added to a transient store) —
  **re-add** with the command above if `claude mcp list` doesn't show it.
- **Troubleshoot:** 403 on a write → student account (expected, not a bug).
  Token expired (~7d) → re-run `gog auth add` loopback. OAuth redirect fails →
  use loopback, not `--remote`.

---

## 8. TIKTOK — BUILT (read-only public scraper, 9 tools)

The TikTok MCP is **BUILT** — a read-only public scraper over `TikTok-Api`
7.3.3, exposing **9 read-only tools**, registered user-scope as `tiktok` (full
analysis: `TIKTOK-MCP.md`). It took **Lane C** below. The insta-mcp pattern
**inverts** for TikTok: no maintained library does authenticated own-account
read — so the lane analysis that drove the build still stands:

| Lane | Goal | Verdict |
|---|---|---|
| **A — own private** (my saved / DMs / feed, the insta-mcp spirit) | own-account private read | **Impossible / do NOT build.** The only lib that ever did this (`szdc/tiktok-api`) is dead (2019) and would need MITM device params + bespoke signing + a logged-in session on a fragile private API = maximal ban risk. DMs unreadable by any route (like FB 1:1 E2EE). |
| **B — own public footprint** (analytics / publishing) | durable, ToS-clean | **FIND/light-build the official Display API** (OAuth, app + scope approval). Gives own public posts + profile + publish. **No** saved/feed/following/DMs. |
| **C — public discovery** (trending, a creator's public posts, search, transcripts) | research | **BUILT** — a thin Python/FastMCP wrapper over `davidteather/TikTok-Api` (alive, public-only, cannot post) — mirrors `fb-messenger-mcp`, **not** insta-mcp. Self-hosted + free. |

**Setup (Lane C, as built):**
- Repo `~\source\repos\tiktok-mcp\`, Python 3.11+ `.venv`, `TikTok-Api` 7.3.3
  (+ `python -m playwright install`), FastMCP `server.py`.
- **Auth = none** (public-only). `tiktok_trending` works **keyless**; the other
  tools need an `ms_token` (copied from a logged-in `tiktok.com` cookie) passed
  via `TIKTOK_MS_TOKEN` to reduce bot-detection — store gitignored.
- **Decision branch (egress, same as IG/FB):** CLOUD → Byteful residential proxy
  **required** (TikTok bot-detection blocks datacenter IPs fast →
  `EmptyResponseException`); `TikTokApi` takes `proxies=` (env `TIKTOK_PROXY`).
  LOCAL home IP → no proxy. Note: an RO exit localizes trending to Romania.
- **Register (as registered this session):**
  ```bash
  claude mcp add tiktok --scope user -e TIKTOK_MS_TOKEN=<msToken> -- C:\Users\Prekzursil\source\repos\tiktok-mcp\.venv\Scripts\python.exe C:\Users\Prekzursil\source\repos\tiktok-mcp\server.py
  # POSIX: ...\.venv/bin/python server.py
  ```
  Consider adding it to `disabledMcpServers` and enabling per-project (§6), like
  the research MCPs.
- **Refresh:** a sudden empty-response spike = refresh `ms_token` and/or rotate
  the proxy exit (the TikTok analogue of `node login.mjs`).

**Account-state note:** unofficial scraping doesn't log into your account → it
**IP-blocked**. If you ever add authenticated actions (Lane A — don't), account
ban risk returns and the flagged-IG playbook (residential proxy + human-pacing)
applies.

---

## 9. Pending / open items (accuracy ledger)

- **Instagram:** account is **flagged** → **rotate the password** (was pasted
  into a transcript); use the proxy on any cloud egress.
- **FB Messenger:** export cookies via C3C, then register; 1:1 DMs permanently
  unreadable (E2EE).
- **WhatsApp:** POC only — keep **unregistered**.
- **gogcli-classroom:** re-add if absent from `claude mcp list`; student account
  → writes 403.
- **schrodinger:** 67 tools; product drivers consume license tokens. The core
  prep → grid → dock → MM-GBSA chain was **validated live E2E** on 2022-4
  (2026-06-06, 3PTB + warfarin; see `schrodinger-mcp/VALIDATION.md`); the
  expanded 2026-2 surface still needs live-box smoke testing. `glide_grid`
  generates the docking grid in-server (no precomputed grid needed).
- **Research MCPs:** disabled-by-default — enable per-project (§6), don't wipe
  the disable list.
- **All social MCPs:** private-API ToS/ban risk; read before write; secrets
  gitignored; stop on any checkpoint.

---

### Quick reference — register commands (Windows)

```bash
# Instagram (LIVE)
claude mcp add insta-mcp -- node C:/Users/Prekzursil/source/repos/insta-mcp/dist/index.js

# FB Messenger (groups/pages only)
claude mcp add fb-messenger -- C:/Users/Prekzursil/source/repos/fb-messenger-mcp/.venv/Scripts/python.exe C:/Users/Prekzursil/source/repos/fb-messenger-mcp/server.py

# WhatsApp — POC ONLY, do NOT register (shown for completeness, do not run)
# claude mcp add whatsapp -- node C:/Users/Prekzursil/source/repos/whatsapp-mcp/src/main.ts

# Research (disabled-by-default; enable per-project via §6)
claude mcp add tooluniverse -e PYTHONIOENCODING=utf-8 -- uvx tooluniverse==1.2.4
claude mcp add rdkit -- C:/Users/Prekzursil/source/repos/rdkit-mcp-server/.venv/Scripts/python.exe C:/Users/Prekzursil/source/repos/rdkit-mcp-server/run_server.py --transport stdio
claude mcp add schrodinger -e "SCHRODINGER=D:\Program Files\Schrodinger 2026-2" -- C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/schrodinger-mcp/.venv/Scripts/python.exe C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/schrodinger-mcp/server.py
claude mcp add gogcli-classroom -e GOG_ACCOUNT=prekzursil1993@gmail.com -e GOG_PATH=C:\Users\Prekzursil\tools\gogcli\gog.exe -- gogcli-mcp-classroom

# TikTok (BUILT — read-only public scraper, 9 tools; see §8)
claude mcp add tiktok --scope user -e TIKTOK_MS_TOKEN=<msToken> -- C:\Users\Prekzursil\source\repos\tiktok-mcp\.venv\Scripts\python.exe C:\Users\Prekzursil\source\repos\tiktok-mcp\server.py
```

After any `add`: **restart Claude Code**, then `claude mcp list` to confirm
`✓ Connected`.
