---
title: dive-WonderSuite-Ai-Bug-Bounty
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-wonder-suite-ai-bug-bounty
---

# Deep-dive: WonderSuite-Ai-Bug-Bounty

**Candidate (from the ask):** native-Windows Burp-class offensive suite — MITM proxy impersonating Chrome 137 JA3/JA4+H2 fingerprints, bundled stealth Chrome-for-Testing 148 with isTrusted input + humanlike Bezier/typing and fast/human/paranoid stealth profiles, `browser_storage_full` authenticated-session dump, OAST (HTTP/DNS/SMTP) blind SSRF/cmdi/Log4Shell detection, active scanner, 90 MCP tools on :3100.

**Repo:** https://github.com/sfr-development/WonderSuite-Ai-Bug-Bounty
**Verdict:** REAL code, every headline claim verified at file:line level in a fresh clone — but the project is **dormant since 2026-06-11** (single author, one-month dev burst, bot-only activity since, dead website, zero community). Installable today on Windows natively via prebuilt .msi/.exe. **Value: medium** (capability real; maintenance risk high).

All code citations below are from a `git clone --depth 1` of `main` @ `f13c039a1312cb5d5fd87f618dda917bbda298a7` (2026-06-11), saved at `out/ws_repo/`.

---

## 1. Repo metadata (ran `gh api repos/sfr-development/WonderSuite-Ai-Bug-Bounty`)

| Field | Value |
|---|---|
| created_at | 2026-05-11T09:49:57Z |
| pushed_at | 2026-09-28T12:06:56Z (**bot PRs only — see §5**) |
| stars / forks / watchers | 51 / 7 / 2 |
| open_issues_count | 29 — **all 29 are bot pull requests, 0 actual issues** |
| license | MIT |
| language | Rust (Tauri 2 + React 19 + TypeScript + Vite) |
| archived | false |
| size | 36,113 KB |
| contributors (gh api .../contributors) | sfr-development (46 commits), dependabot[bot] (5) — single human author |

## 2. Claim-by-claim verification (read the actual code)

### ✅ MITM proxy + Chrome 137 JA3/JA4 + H2 impersonation
- `out/ws_repo/src-tauri/src/tls_impersonate.rs` (220 lines) wraps **wreq + wreq-util** (`Emulation::Chrome137`, lines 47–68) on BoringSSL (`boring-sys2`), emulating ClientHello/JA3/JA4 + HTTP/2 SETTINGS ordering (module header, lines 1–21).
- Honest nuance in-code (lines 43–46): Chrome 137 is the *newest profile wreq-util 2.x ships* while the bundled Chromium is 148; "JA3/JA4 shape between 137 and 148 is near-identical".
- Platform gating: `src-tauri/Cargo.toml:99–102` — `wreq`/`wreq-util`/`webpki-root-certs` are `cfg(not(target_os = "linux"))` deps → impersonation on **Windows + macOS only**, Linux falls back to native-tls (README states this too).
- Proxy engine (`src-tauri/src/proxy/engine.rs`, 1506 lines) with the impersonate branch; upstream cert validation disabled by design (tls_impersonate.rs:190–201, same as Burp/mitmproxy semantics).

### ✅ Bundled stealth Chrome-for-Testing 148
- `src-tauri/resources/chromium_pin.json`: pinned **CfT 148.0.7778.97**, win64 URL + real SHA-256 (`6bcb14a1…`); mac/linux SHA-256 fields are zero placeholders (win-first project).
- `src-tauri/src/chromium/` implements download/verify/extract/GC (`download.rs`, `verify.rs`, `extract.rs`, `gc.rs`, `pin.rs`). Weekly pin-bump workflow exists (`.github/workflows/update-chromium-pin.yml`).
- Stealth MV3 extension committed: `src-tauri/resources/wondersuite-extension/content/stealth.js` (61 lines; deletes `navigator.webdriver` at `document_start`), bundled per `tauri.conf.json` resources.

### ✅ isTrusted input, Bezier/Gaussian humanlike automation, stealth profiles
- `src-tauri/src/mcp/browser/input.rs`: CDP `Input.dispatchMouseEvent`/`dispatchKeyEvent`/`Input.insertText` (lines 5–6, 197–263, 323) so DOM events carry `isTrusted: true`; quadratic **Bezier** path with perpendicular control point, ease-out timing and **Gaussian jitter** (lines 95–138); per-character typing cadence drawn from a normal distribution via CLT sum-of-uniforms (lines 279–291); `StealthProfile` enum **Fast / Human / Paranoid** (lines 40–58, per-profile dwell/jitter at e.g. line 108 `Paranoid => rng.gen_range(380..620)`).

### ✅ `browser_storage_full` authenticated-session dump
- `src-tauri/src/mcp/browser/handlers.rs:648` `storage_full()`: `Network.getAllCookies` (+ domain filter), ready-to-replay `Cookie:` header, localStorage, sessionStorage, `indexedDB.databases()`, service workers — exactly as claimed.

### ✅ OAST (HTTP/DNS/SMTP) + blind SSRF/cmdi/Log4Shell
- `src-tauri/src/oast.rs` (533 lines): UDP **DNS** server (:231 `start_dns_server`, `UdpSocket`), **HTTP** callback server (:298), **SMTP** listener (shutdown static :9); loopback-by-default bind policy (:99–118).
- JNDI/Log4Shell payloads: `src-tauri/src/mcp/handlers/oast.rs:54–56` (`${jndi:ldap://…}`, `jndi:dns`, `jndi:rmi`) and `src-tauri/src/mcp/handlers/scanner/active.rs:437`.
- Blind cmdi templates (curl/wget variants with path-correlated callback URLs): `active.rs:426–430`; `active_scan(with_oast: true)` param at `active.rs:405`.

### ✅ Active scanner
- `src-tauri/src/scanner.rs` (SQLi/XSS/SSTI/LFI checks, lines 143–235) + `src-tauri/src/mcp/handlers/scanner/active.rs`.

### ⚠️ "90 MCP tools on :3100" — close, actually 93
- Extracted ToolDef blocks from `src-tauri/src/mcp/mod.rs` with a regex pass: **93 named tools** (24 browser + 5 port-scan among them). README itself drifts (says 91 at line 41, 90 at line 267, 85 at line 465).
- Server binds **127.0.0.1:3100** (`src-tauri/src/mcp/mod.rs:1323,1344`; started `src-tauri/src/lib.rs:250` `server.start_sync(3100)`). Loopback-only; `mod.rs:1242` even documents the drive-by-fetch consideration.

## 3. Packaging → the REAL install command

- **No pyproject/setup.py/Dockerfile** — this is a Tauri desktop app (`package.json` name `wondersuite` v0.3.35; `src-tauri/tauri.conf.json` v0.3.35, bundle targets `all`, updater pubkey present).
- **Real install (Windows):** download the prebuilt, CI-built, updater-signed installer from the latest release (v0.3.35, published 2026-06-11):
  - `WonderSuite_0.3.35_x64_en-US.msi` (17.1 MB, 18 downloads)
  - `WonderSuite_0.3.35_x64-setup.exe` NSIS (13.2 MB, 81 downloads)
  - Verified live with curl: MSI → HTTP 200; exe → HTTP 200, 13,243,123 bytes. (A first exe probe returned 404 — my own typo: the asset uses `_` not `-` before `setup`.)
- **From source (README:519–537):** `git clone … && npm install && npm run tauri build`; Windows helper `build-release.cmd`. Prereqs: Rust 1.78+, Node 18+, VS Build Tools (C++) + WebView2.
  - **Caveat:** building from source on Windows additionally needs cmake/NASM/perl/libclang because `boring-sys2` compiles BoringSSL (`tls_impersonate.rs:20–21` says "Documented in README", but the README prerequisite list omits them). CI proves the Windows toolchain works: `.github/workflows/release.yml:134` runs `windows-latest` and `:180` does `choco install nasm`.
- **Windows-native extras:** WinDivert 2.2.2 (`WinDivert.dll` + `WinDivert64.sys`) is committed in `src-tauri/resources/drivers/windivert/` and bundled — SYN scan needs one UAC consent; dlopened at runtime via `libloading` (`Cargo.toml:117–124`). Chrome-for-Testing downloads lazily on first browser use (SHA-256-verified).
- **Total release downloads:** 4,664 across 40 releases (summed via gh api).

**Windows verdict: NATIVE** — no Docker/WSL; Tauri + WebView2 (preinstalled on Win10/11); MSI/NSIS installers built on `windows-latest` in CI.

## 4. Dependencies & Windows support
- Rust crate set is mainstream (tokio, axum, tauri 2, reqwest, native-tls) — all Windows-first-class.
- `wreq`/`boring-sys2` (BoringSSL): Windows-supported (CI-verified) but heavy source build (cmake/NASM/perl/libclang); prebuilt installer avoids this entirely.
- `webpki-root-certs`: baked-in Mozilla roots — no OS trust store needed.
- WinDivert: LGPLv3, EV-signed, bundled — Windows-native raw-socket SYN scanning.
- No Python runtime involved anywhere (the ask's framing of packaging files: only `package.json` + `src-tauri/Cargo.toml` + `tauri.conf.json` exist).

## 5. Health / breakage / community (the big correction)

- **Timeline:** 46 commits + **40 releases between 2026-05-11 and 2026-06-11** (release list via gh api: v0.1.1…v0.3.35, sometimes 8 releases/day) — then **zero human commits and zero releases for 3.5 months** (today is 2026-09-29). `main` HEAD is `f13c039` 2026-06-11.
- The 2026-09-28 `pushed_at` is **bot-only**: all 29 open PRs are `github-actions[bot]` (15 unmerged weekly Chromium-pin bumps, bot trying to move 148→154) and `dependabot[bot]` (14). Listed via `gh api .../pulls?state=open`.
- **Zero issues ever filed** (`gh api search/issues?q=repo:…+is:issue` → total_count 0). No user-reported breakage exists — because there is effectively no community.
- **Official site `wondersuite.xyz` is DOWN** (curl → HTTP 521, Cloudflare "web server is down").
- **Independent mentions (Exa REST, 2 searches):** only self-referential hits — the repo itself, its own dead site, GitHub auto-pages, an auto-index listing at `mcpvault.io/servers/wondersuite-ai-bug-bounty`, and an auto-generated `explore.market.dev` ecosystem page. **No independent review, Reddit/HN thread, or blog coverage found.** `Xnuvers007/verssuite` is NOT a fork (fork:false, predates this repo, last push 2026-04-09).
- Firecrawl could not be used: `/v1/scrape` returned `{"success":false,"error":"Unauthorized: Invalid token"}` — the VM's FIRECRAWL_API_KEY is invalid. Exa worked and is cited above.

## 6. Not run / not verifiable here
- I did not install or execute the app on this VM (the ask was a repo deep-dive, not an install-and-run); all "works" statements are code-level verification plus CI evidence (windows-latest release builds, real signed installers).
- The README's "17/17 bot-detection signals clean" and "defeats Cloudflare/Akamai/DataDome/PerimeterX" claims are vendor self-tests; I could not independently reproduce them here (would require live driving against third-party detectors).

## 7. Corrected ToolFind

- **Name:** WonderSuite-Ai-Bug-Bounty
- **What it is:** a single-developer, Tauri-2/Rust desktop Burp-alternative whose every headline feature is real code (verified): wreq/BoringSSL Chrome-137 JA3/JA4+H2 upstream impersonation, pinned stealth Chrome-for-Testing 148, CDP-input isTrusted humanlike automation (Bezier/Gaussian, fast/human/paranoid), full storage/auth dump, in-process HTTP/DNS/SMTP OAST with Log4Shell/blind-cmdi probes, active scanner, 93 MCP tools bound to 127.0.0.1:3100.
- **Correction to the claim:** tool count is 93 (not 90; README drifts 85/90/91); impersonation profile is Chrome 137 (newest wreq-util ships) though the bundled browser is 148 — README is honest about this.
- **Biggest caveat:** dormant — no human commit since 2026-06-11, Chromium pin stale at 148 (bot bump PRs to 154 unmerged), website down, zero issues/community, no independent coverage. Usable today via v0.3.35 installers; expect no fixes.
- **Windows:** native (MSI/NSIS installers, CI-proven windows-latest builds, bundled WinDivert; from-source needs Rust+Node+VS Build Tools, plus undocumented cmake/NASM/perl/libclang for BoringSSL).
- **Value:** medium — real, verified capability that would close a browser-offense gap (MCP-drivable stealth browser + impersonating proxy + OAST in one native app), tempered by single-maintainer abandonment risk and a stealth surface that decays without maintenance.