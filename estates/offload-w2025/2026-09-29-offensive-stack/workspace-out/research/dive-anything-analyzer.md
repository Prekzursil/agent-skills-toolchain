# Deep-dive: anything-analyzer (browser-offense lane)

Date: 2026-09-29. Verifier: Deep-dive agent (this session). All commands run live against GitHub API via `gh`, Exa REST, and repo file contents fetched through `gh api repos/.../contents`.

## Verdict up front

**REAL, not fake.** Every capability in the claim was located in the actual source tree. Repo is alive (last functional commit 2026-08-26; housekeeping commits 2026-09-16), ships CI-built installers for win/mac/linux with real download counts, and has an active (Chinese-majority) user base filing genuine bug reports. Value for the browser-offense lane: high, with caveats (anti-bot fragility, single maintainer, GUI-not-headless, LLM key needed for AI modes).

## 1. Repo metadata (ran `gh api repos/Mouseww/anything-analyzer`)

| Field | Value |
|---|---|
| stars | **3721** — exactly matches the claim |
| forks | 647 (high organic signal; hard to fake cheaply) |
| watchers | 3721 |
| open_issues | 52 |
| created_at | 2026-04-12T09:12:57Z (~5.5 months old) |
| pushed_at | 2026-09-16T14:53:09Z (but see commit analysis — last *functional* commit is 2026-08-26) |
| license (API) | **Apache-2.0** — LICENSE file is Apache-2.0 text (verified by decoding the file). README badge/footer still says MIT. LICENSE + CODE_OF_CONDUCT were only committed 2026-09-16, i.e. the repo had no license file for its first 5 months |
| language | TypeScript |
| default branch | main, not archived, not disabled |
| size | 1339 KB (source-only, no vendored binaries) |

Recent commits (`gh api repos/.../commits?per_page=8`):
- 2026-09-16 Create CODE_OF_CONDUCT.md / Create LICENSE (housekeeping)
- 2026-09-09 Update README.md
- 2026-08-26 Merge PR #103 `fix(win): make capture controls transition immediately` (+ `fix(win): prevent native browser view from blocking capture controls`)
- 2026-08-07 chore(release): v3.6.60, fix(ai): prevent tool calls from overflowing context

Contributors (`gh api .../contributors`): Mouseww 42 commits (dominant), then 8 contributors with 1–2 commits each. **Bus factor 1.**

## 2. Claim-by-claim verification against source

| Claim | Verdict | Evidence |
|---|---|---|
| 3721 stars | ✅ exact | `gh api` stargazers_count: 3721 |
| Electron app | ✅ | package.json: `electron ^35.0.0`, electron-vite ^5, electron-builder ^25 |
| Embedded CDP browser | ✅ | `src/main/cdp/cdp-manager.ts` — attaches `webContents.debugger.attach('1.3')` to the Electron WebContents, then `Fetch.enable` with `{urlPattern:'*', requestStage:'Request'}` + Response patterns, `Network.enable`, `Page.enable`. Body cap 1MB, binary types skipped. (Embedded browser = Electron's own Chromium, not a downloaded Chrome) |
| MITM proxy :8888 | ✅ | `src/main/proxy/mitm-proxy-config.ts`: `DEFAULT_CONFIG = { enabled:false, port: 8888, ... }`. Server `mitm-proxy-server.ts` + `ca-manager.ts` (node-forge TLS, per-domain LRU leaf certs). CA install: Windows `certutil -addstore Root` with UAC elevation (`cert-installer.ts`), macOS `security add-trusted-cert` |
| terminal/script/mobile/IoT capture into one Session | ✅ (design) | Session manager merges CDP + Proxy sources with source tags; README/USAGE document `curl -x http://127.0.0.1:8888`, Python proxies dict, HTTP_PROXY env, system proxy, Wi-Fi proxy for mobile. IoT = same gateway-proxy pattern (docs-level claim; nothing IoT-specific in code — it's just an HTTP proxy) |
| JS hooks crypto.subtle | ✅ | `src/preload/hook-script.ts:64-78` — wraps `crypto.subtle` methods, logs args + result hex |
| JS hooks CryptoJS | ✅ | `hook-script.ts:110-167` — AES/DES ciphers, MD5/SHA hashes, HMAC, PBKDF2, enc parse/stringify, guarded by `_arHooked` flag |
| JS hooks SM2/3/4 | ✅ | `hook-script.ts:243-245` — `trapGlobal('CryptoJS', ...)`, `trapGlobal('sm2'/'sm3'/'sm4', hookSmCrypto)` |
| 5 AI analysis modes incl. security audit | ✅ | `src/main/prompt-templates.ts:15-70` — ids: `auto`, `reverse-api`, `security-audit`, `performance`, `crypto-reverse`. Two-phase pipeline in `src/main/ai/` (scene-detector, subagent-analyzer, llm-router, context-budget, crypto-script-extractor) |
| Built-in MCP server exposing capture+analysis | ✅ | `src/main/mcp/mcp-server.ts` (1065 lines), 30 registered tools: list/create/delete_session, start/pause/resume/stop_capture, navigate/back/forward/reload, create/close/list_tabs, clear_browser_env, browser_screenshot, **cdp_send_command** (raw CDP passthrough), get/filter_requests, get_request_detail, get_hooks, get_storage, run_analysis, get_reports, chat_followup, get_interactions + summary, **replay_interactions**, execute_browser_action, get_page_elements. Transport: StreamableHTTP at `http://<host>:<port>/mcp`, **default host 0.0.0.0** (`mcp-server-listen.ts`) — LAN-exposed by default; authToken exists (issue #85) |
| MCP client too | ✅ | `mcp-manager.ts`, stdio + StreamableHTTP, AI analysis can call external MCP tools |

Extra capabilities not in the claim: fingerprint spoofing module (`src/main/fingerprint/`: presets, profile-generator, http-spoofing), interaction recorder + replay engine, stealth-script.ts, storage snapshots (cookies/localStorage), i18n zh/en (settings partially untranslated — issues #93/#97).

## 3. Real install command + packaging

- **No pip package, no npm-published package** (name `anything-analyzer` in package.json is private to the repo; not checked on the npm registry — stated as not checked). This is a **GUI desktop app**, not a CLI library.
- Real install (verified assets): download **`Anything-Analyzer-Setup-3.6.62.exe`** (103,431,790 bytes, **927 downloads**) from https://github.com/Mouseww/anything-analyzer/releases — NSIS installer (electron-builder.yml: `win.target: nsis`, not one-click, allows custom install dir). Mac: `Anything-Analyzer-3.6.62-arm64.dmg` (113 dl) / `-x64.dmg` (42 dl); Linux: `.AppImage` (32 dl). `latest.yml` auto-update manifest has 2379 downloads — real usage in the wild.
- Latest release published **2026-08-26**. 82 releases total; cadence was frenetic (7 releases on 2026-06-02 alone) and has now slowed to ~1/month, last functional change 5 weeks ago. Version tags started at v2.3.0/v3.0.0 **two days after repo creation** (2026-04-14) — version numbers are inflated marketing, not age.
- Build from source (README.en.md): `git clone … && pnpm install && pnpm dev`; `pnpm build && npx electron-builder --win`. Requirements Node ≥ 18, pnpm 10.24.0, VS Build Tools (Windows).
- CI provenance: `.github/workflows/build.yml` — tag push → matrix build on windows/macos/linux runners, `pnpm install` → `electron-vite build` → `electron-builder --win/--mac/--linux`, with an arch-sanity grep on better-sqlite3 for mac. Released binaries are built from the public source. 23 test files under `tests/` (vitest), incl. tests for mcp-server-listen, scene-detector, prompt-builder, crypto-script-extractor.

## 4. Windows-native feasibility: NATIVE ✅

- Ships a native Windows NSIS installer; deps all Windows-capable: better-sqlite3 ^11.8.1 (native, win32-x64 prebuilds; postinstall `electron-builder install-app-deps` handles Electron ABI), node-forge / socks / uuid / zod / antd / react (pure JS), @vscode/sudo-prompt (UAC elevation, Windows-supported), electron 35 / electron-builder 25 (Windows-supported).
- Windows CA install = `certutil -addstore Root` via UAC prompt — standard, works on a normal Windows box.
- Windows-specific issues found in tracker: #99/#101 "win10 start/stop/pause buttons unclickable" — **fixed** by PR #103 (merged 2026-08-26, in the current installer). #68 "authenticated proxy doesn't work on Windows" — closed. #100 "mitm cert installment failed" — open, 0 comments (likely environment-specific; not run by me).
- **Not run by me:** I did not download/execute the 103MB installer on this VM (static verification only, per ask scope — README + packaging + deps + issues).

## 5. Issues / breakage read (`gh api .../issues?state=all`)

Open pain points:
- **#18 (7 comments): "稍微有点反爬，就歇菜了"** — even mild anti-bot defeats the embedded browser. Electron Chromium fingerprint is detectable; the fingerprint-spoofing module exists but users report it is not Cloudflare-grade. Biggest practical limitation for offensive use.
- #106: Xiaomi phone — CA installs but app traffic not captured (cert pinning; MITM proxy can't defeat pinning, expected limitation).
- #85: MCP server authToken requires manual restart (401s after rotation). #100: cert install failure. #96/#102: analysis can't be stopped cleanly. #93/#97: settings UI not translated to English.

Closed/fixed historically: #83 better-sqlite3 wrong arch on Intel Mac (black screen), #77/#82 unsigned mac dmg "damaged" (unsigned — expected), #95, #56 large-request splitting.

Security notes for estate use: MCP server binds **0.0.0.0** by default — on a private single-owner box fine, but set host 127.0.0.1 + authToken if LAN-shared. MITM proxy is read-only (README), WebSocket tunneled not decrypted, 1MB body cap.

## 6. Independent mentions (Exa REST, ran live)

- pyshine.com article 2026-04-20 (earliest, 8 days after repo creation): "Anything Analyzer: Universal Network Protocol Analysis with AI-Powered MITM and Browser Capture"
- dudarik.com/en/blog/anything-analyzer-mcp/ (MITM + AI + MCP walkthrough)
- MCP directories: mcpgee.com/servers/anything-analyzer, automationswitch.com MCP review
- Tool directories: smartoolbox.com (review & alternatives), toolhunter.cc, aitoolnet.com, sourcepulse.org
- README credits LinuxDo (linux.do) community for support (forum posts not individually retrievable without login — not verified).

Assessment: coverage is directory/SEO-style plus a couple of write-ups; **no deep independent technical review found**. Popularity looks organic (fork ratio, real Chinese-language bug reports, 927 installer downloads on latest) amplified by promotion (LinuxDo + sponsor/affiliate links in README: Doloffer GPT-account reseller, Swiftproxy residential proxies, Bloome — monetization is affiliate marketing, slightly reputationally spicy but not an authenticity red flag). Suspicious oddities: version inflation from day one, committed AI-session artifacts (`report-2026-04-13-copilot-claude-sonnet-4.6.md`, `color-preview*.html`, `verify-aki-fix.cjs`) — consistent with heavy AI-assisted solo development, not with fakery.

## 7. Scoring

- **value: high** — the built-in MCP server (30 tools incl. raw `cdp_send_command`, `execute_browser_action`, `get_page_elements`, `replay_interactions`, `run_analysis`) turns one native Windows GUI into an agent-drivable instrumented browser + MITM proxy + AI protocol analyst. That combo (embedded CDP browser AND MITM for non-browser traffic AND crypto JS hooks AND MCP exposure) is not matched by mitmproxy (no browser), Playwright (no MITM/crypto hooks), or Charles/Fiddler (commercial, no MCP).
- **windows: native** — NSIS installer, all deps Windows-capable, Windows bugs fixed in current release.
- **install:** GitHub Releases `Anything-Analyzer-Setup-3.6.62.exe` (NSIS); source build `pnpm install && pnpm build && npx electron-builder --win`.
- Caveats carried into the find: single maintainer; last functional commit 2026-08-26; anti-bot fragile (#18); cert pinning not defeated; GUI app (not headless/scriptable except via MCP); AI modes need your own LLM API key (capture works without); README says MIT but actual LICENSE is Apache-2.0; MCP default bind 0.0.0.0.
