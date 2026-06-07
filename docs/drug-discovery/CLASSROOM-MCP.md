# Google Classroom MCP (gogcli-mcp-classroom)

Connect Claude Code (and other MCP clients) to **Google Classroom** via the `gogcli`
Google CLI engine wrapped by the `gogcli-mcp-classroom` MCP server. This document is the
authoritative connection/setup guide for the build verified on **2026-06-06**.

> **Platform note.** This setup was built and verified on **Windows 11** (`gog.exe`,
> npm global on `%AppData%\npm`). On POSIX the same flow applies with `gog` (no `.exe`),
> npm global under `~/.npm-global` or the system prefix, and the config dir at
> `~/.config/gogcli/` instead of `%AppData%\gogcli\`. Paths below show the Windows form;
> swap separators (`\` -> `/`) and drop `.exe` on macOS/Linux.

---

## What this is

| Layer | What | Where (Windows) |
|-------|------|-----------------|
| Engine | `gogcli` — Google CLI for Gmail/Calendar/Classroom/Drive/etc. | `C:\Users\Prekzursil\tools\gogcli\gog.exe` (v0.21.0) |
| MCP wrapper | `gogcli-mcp-classroom` (npm, global) | `%AppData%\npm\gogcli-mcp-classroom(.cmd)` (v2.4.1) |
| Auth | Google Cloud OAuth **Desktop** client (project "WebCoder") | refresh token in OS keyring |
| Account | `prekzursil1993@gmail.com` (a **student** principal) | scope: `classroom` |

The MCP server shells out to `gog ... classroom ...` under the hood; the OAuth/token
machinery lives entirely in `gogcli`. The MCP layer is a thin pass-through.

---

## Current state (observed this session)

| Item | Status | How verified |
|------|--------|--------------|
| `gogcli` engine | **OK** | `gog.exe --version` -> `v0.21.0 (2c84d89 2026-06-01)` |
| OAuth / refresh token | **OK** | `gog.exe auth list` -> `prekzursil1993@gmail.com  default  classroom  oauth` |
| Classroom round-trip | **OK (3 courses)** | `gog -a <email> classroom courses list` (see below) |
| `gogcli-mcp-classroom` npm pkg | **Installed** | `npm ls -g gogcli-mcp-classroom` -> `@2.4.1` |
| MCP registration in Claude | **NOT currently present** | `claude mcp get gogcli-classroom` -> not found; `claude mcp list` has no `gog*`; absent from `.claude.json` |

**Read this carefully:** the engine, OAuth, and live round-trip are **verified working**.
The MCP registration is the **only** piece not currently live in any Claude scope — re-run
the `claude mcp add` command in [Register the MCP server](#5-register-the-mcp-server-with-claude)
to (re-)create it, then confirm with `claude mcp get gogcli-classroom`.

---

## Prerequisites

- `gog.exe` v0.21.0+ on disk at `C:\Users\Prekzursil\tools\gogcli\gog.exe`
  (or anywhere on `PATH`).
- Node.js + npm (for the global MCP package).
- A Google Cloud project with an **OAuth Desktop client** (below).

---

## 1. Install the MCP server (npm, global)

```powershell
npm install -g gogcli-mcp-classroom
npm ls -g gogcli-mcp-classroom          # expect: gogcli-mcp-classroom@2.4.1
```

This places `gogcli-mcp-classroom` and `gogcli-mcp-classroom.cmd` in `%AppData%\npm`
(on POSIX, in your npm global bin).

---

## 2. Create the Google Cloud OAuth Desktop client

1. Google Cloud Console -> select/create a project (this build used project **"WebCoder"**).
2. **APIs & Services -> Library** -> enable **Google Classroom API**.
3. **APIs & Services -> OAuth consent screen** -> configure (External is fine for a
   personal Gmail). While the app is in **Testing** mode, add
   `prekzursil1993@gmail.com` as a **Test user**.
4. **APIs & Services -> Credentials -> Create credentials -> OAuth client ID** ->
   application type **Desktop app**. Download the `credentials.json`.

> **Why Desktop, not Web.** A Desktop client supports the **installed-app loopback**
> redirect (`http://127.0.0.1:<port>`), which is what makes the auto-capture flow in
> step 4 work without you pasting anything.

---

## 3. Store the OAuth client credentials in gogcli

```powershell
& "C:\Users\Prekzursil\tools\gogcli\gog.exe" auth credentials set "C:\path\to\credentials.json"
```

- `<credentials>` may also be `-` to read the JSON from **stdin**.
- The client is stored under a named bucket; select it later (if you keep more than one)
  with the global `--client=<name>` flag.

---

## 4. Authorize the account (the auth flow)

The verified, recommended path is the **loopback** browser flow:

```powershell
& "C:\Users\Prekzursil\tools\gogcli\gog.exe" auth add prekzursil1993@gmail.com --services classroom
```

- `--services classroom` mints a token scoped to Classroom only (matches the
  `classroom` scope shown in `auth list`). Add `--readonly` if you want read-only
  scopes (still safe for `courses list` and reading your own submissions).
- gogcli starts a local loopback listener (`http://127.0.0.1:<port>`), opens your
  browser to Google's consent screen, you click **Allow**, and Google redirects
  back to the loopback URL — gogcli **auto-captures** the code from that callback
  and exchanges it for a refresh token (stored in the OS keyring).

### EXPECTED after you click "Allow": the "can't be reached" page

After consent, the browser navigates to something like
`http://127.0.0.1:53xxx/?code=...` and may render:

**This is success, not a failure.** By the time the browser shows that page, gogcli's
loopback listener has already received the `?code=...`, exchanged it, stored the token,
Return to
the terminal: `gog auth add` will have printed success. Confirm with:

```powershell
& "C:\Users\Prekzursil\tools\gogcli\gog.exe" auth list
# -> prekzursil1993@gmail.com  default  classroom  <timestamp>  oauth
```

### Loopback vs. `--remote` (and `--redirect-host`)

| Flow | Flags | When | This build |
|------|-------|------|------------|
| **Loopback (auto-capture)** | (default) `auth add <email> --services classroom` | Desktop with a usable browser | **Worked** — used for the live token |
| Manual | `--manual` | Browserless; paste the redirect URL back | not needed here |
| Remote / server | `--remote --step 1` then `--remote --step 2 --auth-url <redirect-url>` | Headless box; print URL, paste code on another machine | **Failed here** due to browser churn — fell back to loopback |

- `--redirect-host=<hostname>` overrides the OAuth callback host for the browser flows
  (default loopback host is `127.0.0.1`); leave it default for the auto-capture path.
- The two-step `--remote` flow prints the consent URL on step 1 and exchanges the pasted
  redirect URL on step 2 — useful only when the browser and the CLI live on different
  machines. On a normal desktop, prefer plain loopback.

---

## 5. Register the MCP server with Claude

```powershell
claude mcp add gogcli-classroom `
  -e GOG_ACCOUNT=prekzursil1993@gmail.com `
  -e GOG_PATH="C:\Users\Prekzursil\tools\gogcli\gog.exe" `
  -- gogcli-mcp-classroom
```

(POSIX bash: replace the backtick line-continuations with `\`, and the `GOG_PATH` value
with your `gog` binary path.)

Then **verify the registration actually persisted**:

```powershell
claude mcp get gogcli-classroom        # expect a connected stdio server, env GOG_ACCOUNT/GOG_PATH
```

> **Heads-up (this session).** After running the add above earlier, the server was **not**
> found by `claude mcp get gogcli-classroom`, did not appear in `claude mcp list`, and was
> absent from `.claude.json`. If `get` comes back "No MCP server found", the registration
> did not stick — re-run `claude mcp add` (check you're targeting the intended scope; add
> `-s user` or `-s project` explicitly if needed) and re-verify with `get`.

---

## 6. Round-trip test (verified)

```powershell
& "C:\Users\Prekzursil\tools\gogcli\gog.exe" -a prekzursil1993@gmail.com classroom courses list
```

**Verified result (2026-06-06) — 3 real courses:**

```
ID            NAME                                                    SECTION                                            STATE     OWNER
850164767543  Psihopedagogia adolescentilor, tinerilor si adultilor                                                     ACTIVE    108080728746498189665
845937527506  Proiectarea si managementul programelor educationale    Nivelul II 2025 -2026                              ACTIVE    107991232251936514385
38234272027   ISC_11G_2019                                            Optional - Invatare pentru societatea cunoasterii  ARCHIVED  112246330535183876647
```

That a real list comes back (2 ACTIVE + 1 ARCHIVED) confirms the engine, OAuth token,
and Classroom API access are all live. Once the MCP is registered, the equivalent MCP
tool call returns the same data.

> Tip: add `-j` (JSON) or `-p` (TSV) for machine-parseable output; `-j` is what the MCP
> wrapper consumes internally.

---

## Errors + Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `deadline-exceeded` / hang during `--remote` auth | Remote two-step flow stalled (browser churn between machines/tabs) | Abandon `--remote`; use the default **loopback auto-capture** (`auth add <email> --services classroom`). The loopback listener captures the `?code=` itself — no paste, no deadline. This is the path that worked here. |
| Browser stuck on the **account chooser** / consent loops | Multiple Google sessions; wrong account picked; stale tab | Pick `prekzursil1993@gmail.com` explicitly; if it loops, open the printed consent URL in a clean/incognito window signed into only that account; ensure the account is listed as a **Test user** on the consent screen. |
Student principals can do **reads + their own submissions**, not teacher writes. Use read tools (e.g. `courses list`) and own-submission operations. For full write access you need a teacher/owner account; authorize with `--readonly` if you want to make the read-only intent explicit. |
| `http://127.0.0.1:<port>` "site can't be reached" after clicking Allow | The loopback listener already captured the code and closed | **Not an error — this is success.** Return to the terminal and run `gog auth list` to confirm the token landed. |
| Auth suddenly broken after ~7 days; tokens stop working | OAuth consent screen still in **Testing** mode -> refresh tokens for external test users expire after ~7 days | Re-run `gog auth add prekzursil1993@gmail.com --services classroom` to re-mint, **or** move the OAuth consent screen to **Production** (publish the app) so tokens stop expiring on the test-mode clock. |
| `No MCP server found with name: "gogcli-classroom"` | The `claude mcp add` registration did not persist to the intended scope | Re-run the add (see step 5), specifying the scope explicitly (`-s user` / `-s project`) if needed; re-verify with `claude mcp get gogcli-classroom`. |
| `gog` not found by the MCP server | `GOG_PATH` wrong, or `gog` not on `PATH` | Pass the absolute path via `-e GOG_PATH=...gog.exe` in the `claude mcp add`; on POSIX use the `gog` (no `.exe`) path. |

---

## Notes

- gogcli config + keyring backend: `%AppData%\gogcli\config.json` (Windows);
  `~/.config/gogcli/config.json` (POSIX). Override the root with `--home` / `GOG_HOME`.
- The refresh token lives in the **OS keyring** (Windows Credential Manager), not in a
  plaintext config file. Do not commit `credentials.json`.
- This is a **single-user, local** integration. The OAuth client secret + tokens are
  user-scoped; keep them out of any repo or shared config.
