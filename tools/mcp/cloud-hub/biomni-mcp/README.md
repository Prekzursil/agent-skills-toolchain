# Biomni Lab connector — cookie-broker setup, usage, and how to add accounts

This directory is the cloud-hub **`biomni`** backend: a self-hosted way to *drive*
the hosted [Biomni Lab](https://biomni.phylo.bio) (Phylo Inc.) from Claude Code —
richer than the official 10-tool claude.ai connector — **without any agent ever
holding your credential**.

- `server.py` — the FastMCP child (25 `bm_*` tools) the cloud-hub spawns.
- `broker.py` — a local `127.0.0.1` reverse proxy that **injects your Biomni auth**
  into requests, so the connector holds none.
- `refresher.py` — keeps the auth fresh by reading it from your live browser session.
- `autostart.py` + `daemons.example.json` — bring the daemons up at logon.

---

## 1. How Biomni auth actually works (the important part)

Biomni's API (`api.phylo.bio`) authenticates with a single **HttpOnly `session_id`
cookie** — **not** a Bearer token. (This was verified live against the running app:
every request carries the cookie; there is no `Authorization` header, and the token
is not in `localStorage`.) The cookie is set by a WorkOS/Google sign-in and rotates
with the session.

Everything below flows from that fact:

```
  your real Chrome (signed in) ──CDP──▶ refresher.py ──▶ token store (chmod-600 file)
                                                              │  (cookie, masked in all logs)
     bm_* tools / any client ──▶ broker.py :PORT ──[injects  Cookie: session_id=…]──▶ api.phylo.bio
     (connector holds NO auth; points BIOMNI_API_BASE at the broker, BIOMNI_BROKER=1)
```

**The credential lives in exactly two places** — your browser's cookie jar and the
local broker store — and never in `accounts.json`, the hub, an agent's context, or
any log (only masked previews like `…ZGAo` ever appear).

---

## 2. One-time setup (per machine)

```bash
pip install playwright && playwright install chromium      # refresher needs it
```

The cloud-hub already registers the `biomni` backend (`backends.py`). The `bm_*`
tools appear after the hub (re)starts.

---

## 3. Add an account (repeatable)

Each Biomni account = **one debug Chrome + one broker + one refresher + one
`accounts.json` entry**, on its own ports. Pick unused ports (CDP `922N`, broker
`1878N`; **note Windows reserves some low ports — `8787` fails with WinError 10013,
so use high ports like `18787+`**).

1. **Launch a dedicated debug Chrome and sign in** (a *real*, non-automated sign-in —
   Google allows it; it will **not** work inside a Playwright-launched browser):
   ```
   chrome.exe --remote-debugging-port=9222 --user-data-dir=%LOCALAPPDATA%\biomni-chrome ^
              --no-first-run https://biomni.phylo.bio
   ```
   Sign into the account in that window.

2. **Capture the cookie into a store** (reads the `session_id` cookie via CDP; never
   prints it):
   ```
   python refresher.py --cdp http://127.0.0.1:9222 --out-file %USERPROFILE%\.biomni-mcp\broker_token refresh
   ```

3. **Start the broker** (injects the cookie; default mode is `cookie`):
   ```
   set BIOMNI_BROKER_TOKEN_FILE=%USERPROFILE%\.biomni-mcp\broker_token
   python broker.py --port 18787
   ```
   Sanity-check: `curl http://127.0.0.1:18787/v2/auth/me` → your identity;
   `curl http://127.0.0.1:18787/__broker/health` → `auth_mode: cookie`, masked token.

4. **Wire the `accounts.json` `biomni` block** (no secret — just a loopback handle):
   ```json
   "biomni": { "active": "acct1", "accounts": [
     { "name": "acct1", "label": "you@example.com (broker :18787)",
       "env": { "BIOMNI_API_BASE": "http://127.0.0.1:18787", "BIOMNI_BROKER": "1" } } ] }
   ```
   For more accounts, add entries with incrementing ports (`18788`, `18789`, …), each
   with its own debug Chrome (`9223`, `9224`, …) and token file
   (`~/.biomni-mcp/tokens/<name>`). `bm_account_switch`/`bm_account_cycle` rotate them.

5. **Keep it fresh** — run a refresher watch (or use autostart, §4):
   ```
   python refresher.py --cdp http://127.0.0.1:9222 --out-file %USERPROFILE%\.biomni-mcp\broker_token watch
   ```

Restart Claude Code → the `bm_*` tools drive Biomni as the active account.

---

## 4. Autostart the daemons at logon

`autostart.py` brings up **Chrome + broker + refresher for every account** from
`~/.biomni-mcp/daemons.json` (copy `daemons.example.json`). It is idempotent — it
skips a Chrome/broker already listening.

```json
{ "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "accounts": [
    { "name": "acct1", "cdp_port": 9222, "broker_port": 18787,
      "token_file": "~/.biomni-mcp/broker_token", "chrome_profile": "~/AppData/Local/biomni-chrome" }
  ] }
```

Run it manually with `python autostart.py`, or register it at logon — a
`biomni-autostart.bat` in the Windows **Startup folder**
(`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) containing:

```bat
@echo off
start "" /min python "<path>\biomni-mcp\autostart.py"
```

The debug-Chrome profiles must stay **signed in**; if a session expires, that
account's refresher logs it and you just re-sign-in in its Chrome window.

---

## 5. The `bm_*` tools (via the broker)

25 tools, e.g. `bm_create_session` (effort via `model_profile` standard|fast|premium),
`bm_send_message` (+ `attached_skills`, `@resource` mentions), `bm_start_processing`,
`bm_get_messages`/`_streaming`, `bm_list_skills`/`bm_set_skill_status`,
`bm_session_runtime` (HPC/GPU/machines), `bm_billing_balance` (rotate before a run
dries out), `bm_api_raw`, and `bm_account_{list,current,switch,cycle}`. See the parent
[`../README.md`](../README.md) for the full surface.

Broker knobs (env): `BIOMNI_BROKER_TOKEN_FILE` / `_OP_REF` / `_KEYRING` / `_TOKEN`
(source, in priority order), `BIOMNI_BROKER_AUTH` (`cookie` default | `bearer`),
`BIOMNI_BROKER_COOKIE_NAME` (default `session_id`), `BIOMNI_BROKER_TTL` (re-read
interval, default 60s).

---

## 6. What we did / dead-ends (so the next person doesn't re-walk them)

The connector was **first** built assuming Bearer auth (from a HAR `Authorization`
header that was never actually read). Getting to the working cookie-broker meant
ruling out three tempting-but-dead paths — the lesson each time: **live-verify auth
against the real service before building on it.**

- **OAuth device-code flow** (`bm_auth_login`) — Phylo's WorkOS `device_authorization`
  endpoint returns `401` for *any* client (incl. a bogus one): closed to public clients.
- **Persisted-profile Playwright login** — Google blocks OAuth sign-in inside an
  automation-controlled browser (*"This browser or app may not be secure"*). Evading
  that bot-detection is out of scope.
- **Capturing an `Authorization: Bearer` header** — there is none; the app uses the
  `session_id` cookie. The Bearer premise was wrong.

The **working** path: sign in normally in a real Chrome (Google is fine), expose it
over `--remote-debugging-port`, and have the refresher **attach via CDP** to read the
`session_id` cookie from the live session — no bot login, nothing evaded. The broker
injects that cookie; the connector holds nothing.

## 7. Troubleshooting

- **`WinError 10013` on the broker** → the port is OS-reserved; use a high port (`18787+`).
- **`--cdp` "unrecognized arguments"** → `--cdp` is a global flag; put it *before* the
  subcommand: `refresher.py --cdp http://… watch`.
- **refresher: "no session_id cookie … sign into Biomni there"** → that Chrome's session
  expired or isn't signed in; sign in again in its window.
- **`/v2/auth/me` → 401 through the broker** → the stored cookie is stale; run a `refresh`
  (or let `watch` catch up).
