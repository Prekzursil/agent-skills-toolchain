---
title: browser-offense
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/browser-offense
---

# browser-offense — Offensive browser automation MCP servers

Date: 2026-09-29. Researcher lane: browser-offense (subagent).
Scope: nodriver-proxy-mcp, WonderSuite, and anything newer — human-like navigation, MITM interception, authenticated-flow testing, session handling. Estate context: CyberStrike 1.1.16, single MCP gateway 127.0.0.1:31100 (43 backends, 17 live), chrome-devtools via managed stdio workers, mitmproxy already present as rpc backend, NO Docker engine (GCP no VT-x), Windows Server, Python `C:\Python314\python.exe` (3.14), Node on PATH.

Environment facts verified during this ask (commands run on the VM):
- `node --version` → `v24.21.0` (satisfies js-reverse-mcp engines `^20.19.0 || ^22.12.0 || >=23`, and veilbrowser's Node-24 requirement)
- `curl -s https://pypi.org/pypi/nodriver-proxy-mcp/json` → name nodriver-proxy-mcp, version 1.0.1, `requires_python: <3.14,>=3.10` — **estate's Python 3.14 is ABOVE the cap**; `pip install` on 3.14 will be refused by pip's resolver. Needs a 3.10–3.13 interpreter (presence on VM not verified) or `uv venv --python 3.13`.
- `curl -s https://pypi.org/pypi/nodriver-mcp/json` → 2.5.0, `>=3.12` (3.14 OK by metadata; runtime on 3.14 not tested here)
- `curl -s https://pypi.org/pypi/stealth-browser-mcp/json` → 0.1.4, `>=3.10` (note: repo README badge says 0.2.5 in pyproject; PyPI latest is 0.1.4 — publish lag)
- `curl -s https://pypi.org/pypi/wraith-mcp/json` → 0.2.2, `>=3.11`
- `curl -s https://registry.npmjs.org/js-reverse-mcp` → latest 4.0.5, engines node `^20.19.0 || ^22.12.0 || >=23`
- `curl -s https://registry.npmjs.org/mcp-camoufox` → 0.11.1, bin `mcp-camoufox`
- `curl -s https://registry.npmjs.org/jshook-reverse-tool` → 0.1.1, repo wuji1/jshook-reverse-tool
- `curl -s https://registry.npmjs.org/@achamm%2Fveilbrowser` → 1.6.1
- `curl -s https://registry.npmjs.org/bladebro` → 4.0.2
- `curl -s https://registry.npmjs.org/camoufox-reverse-mcp` → NOT published on npm (KeyError dist-tags)
- `gh api repos/sfr-development/WonderSuite-Ai-Bug-Bounty/releases/latest` → v0.3.35 with `WonderSuite_0.3.35_x64-setup.exe` (13.2MB), `WonderSuite_0.3.35_x64_en-US.msi` (17.1MB), plus .dmg/.AppImage/.deb/.rpm + sigs → **native Windows installers confirmed real**

No tool was installed or executed on the VM in this ask — research only. All "runs natively" claims below are from registry metadata + README statements, marked where unverified.

---

## 1. Named targets

### 1.1 nodriver-proxy-mcp — BobongKu/nodriver-proxy-mcp
- Repo: https://github.com/BobongKu/nodriver-proxy-mcp (3★, updated 2026-09-09, MIT, has README_ko.md — Korean author)
- README read via `gh api repos/BobongKu/nodriver-proxy-mcp/readme` (base64-decoded).
- What: "Give your AI agent a browser, a proxy, and a Python sandbox. It navigates like a human, intercepts like Burp, and codes its own exploits on the fly." 39 MCP tools = 18 proxy (real mitmproxy on :8082 + SQLite traffic.db) + 20 browser (nodriver Chrome, CDP Fetch interception, localStorage/sessionStorage dumps, httpOnly cookie set via CDP, JS exec, screenshots) + 1 code-mode (`execute_security_code` — sandboxed AI-written Python with NdpSDK exposing the other tools for loops/`asyncio.gather` race-condition and blind-SQLi work).
- Auth-flow angle: `detect_auth_pattern` auto-detects JWT/Bearer/API-key/session-cookie/CSRF/OAuth2; `extract_session_variable` + `{{placeholder}}` replay (Burp-Repeater-like); two-victim-session IDOR workflow documented; Burp chaining via `manage_proxy(upstream="localhost:8080")`.
- Two interception layers: CDP Fetch (instant, browser-only) and mitmproxy rules (system-wide, ~5s cache delay). Process lifecycle table shows Windows-aware cleanup ("Job Object / killpg; 256MB RAM, 60s CPU") — author tested on Windows.
- Install (README Quick start): `pip install nodriver-proxy-mcp` then MCP config `{"mcpServers": {"nodriver-proxy-mcp": {"command": "nodriver-proxy-mcp"}}}`. From source: `git clone ... && pip install .`
- Windows: native (Python + Chrome; **but PyPI requires_python <3.14 — estate's 3.14 interpreter fails the cap**; use a 3.13 venv/uv).
- Value: HIGH — exactly the estate gap: stealth browser + MITM + auth-pattern extraction + code-mode, single server, no Docker.

### 1.2 WonderSuite — sfr-development/WonderSuite-Ai-Bug-Bounty
- Repo: https://github.com/sfr-development/WonderSuite-Ai-Bug-Bounty (51★, 7 forks, MIT, Tauri 2 + Rust + React 19)
- Read via WebFetch of the repo page (full summary in transcript) + `gh api .../releases/latest`.
- What: open-source Burp-class desktop offensive platform with AI agent via MCP. MITM proxy with TLS interception + Chrome 137 JA3/JA4 & HTTP/2 fingerprint impersonation (BoringSSL; Windows/macOS only, Linux falls back). Bundled "WonderBrowser" (Chrome-for-Testing 148 + stealth extension, isolated profile). Scanner: SQLi/XSS/SSTI/LFI/CRLF/open-redirect/blind cmdi+SSRF+Log4Shell via built-in OAST (HTTP/DNS/SMTP). Intruder/fuzzer, crawler, port scanner (TCP/SYN via WinDivert/UDP), code audit, reporting.
- MCP: single "wondersuite" server, Axum JSON-RPC 2.0 at `http://127.0.0.1:3100/mcp`, ~90 tools (24 browser + 5 portscan + proxy/scanner/HTTP/recon/OSINT/codec/exploit/reporting). Ships a Claude skill file `.claude/skills/wondersuite.md`. Gateway-style HTTP endpoint fits the estate's 127.0.0.1:31100 aggregator pattern.
- Install: releases → `WonderSuite_0.3.35_x64-setup.exe` or `.msi` (verified assets via gh api). From source: `git clone`, `npm install`, `npm run tauri build` (needs VS Build Tools C++ + WebView2). MCP client: add `"wondersuite": {"url": "http://127.0.0.1:3100/mcp"}`.
- Windows: native (signed .msi/.exe; SYN scan needs WinDivert → one UAC prompt).
- Value: HIGH — native-Windows Burp-class MITM + stealth browser + scanner exposed as MCP; complements (not duplicates) hexstrike/nuclei.
- Caveat: web search for "WonderSuite" is heavily polluted by Bluehost's WordPress WonderSuite and an unrelated AI-safety WonderSuite (SourceForge "Best Red Team Tools of 2026"); no independent reviews/HN discussion of the bug-bounty one found — young project, low community validation.

---

## 2. Stealth / anti-bot browser MCP family

- **vibheksoni/stealth-browser-mcp** (2161★, updated 2026-09-29, MIT, v0.2.5 in pyproject / 0.1.4 on PyPI). "The only browser automation that bypasses anti-bot systems. AI writes network hooks, clones UIs pixel-perfect via simple chat." nodriver + CDP + FastMCP, Python 3.10+. Install: `pip install stealth-browser-mcp` (PyPI presence verified). Windows: native (Python). Value: HIGH — biggest community in the lane; network hooks = client-side interception.
- **RobithYusuf/mcp-stealth-chrome** (24★). "100++ tools. One-liner Cloudflare Turnstile bypass (proven), dual-mode HTTP with TLS fingerprint, AI Vision reCAPTCHA solver. Python + nodriver + curl_cffi + FastMCP." Windows: native (Python). Value: MEDIUM.
- **RobithYusuf/mcp-camoufox** (20★). "100+ tools, npx install" — npm 0.11.1 verified (`mcp-camoufox` bin). Camoufox (anti-detect Firefox). Windows: native (Firefox/Camoufox has Windows builds; untested). Value: MEDIUM.
- **andresolbach/nodriver-mcp-server** (5★). "70 tools, stealth alternative to chrome-devtools-mcp; several isolated browsers at once so parallel agents never share a session." PyPI `nodriver-mcp` 2.5.0 verified, requires_python >=3.12 (OK on 3.14 by metadata). README read. Install: `pip install nodriver-mcp` (badge-verified). Windows: native. Value: MEDIUM-HIGH — drop-in for the estate's existing chrome-devtools stdio worker, with session isolation.
- **Saber-CC/nodriver-mcp** (2★), **namecallfilter/nodriver-mcp** (0★), **mahdyarief/stealth-web-mcp** (0★) — smaller nodriver variants, LOW.
- **DevinoSolutions/stealth-chrome-devtools-mcp** (25★). "Stealth Chrome DevTools with smart profile management, anti-detection arg filtering, and CDP access." Value: MEDIUM.
- **dylangroos/patchright-mcp-lite** (24★, updated 2026-09-28). Patchright (Playwright stealth fork) MCP for lightweight models. Value: LOW-MEDIUM.
- **rickicode/patchright-browser** (20★). Multi-profile Chromium, headed/headless, StreamableHTTP, dashboard. Value: LOW-MEDIUM.
- **devAdminhu/patchright-mcp** (3★). 69 tools: stealth, CDP, multi-tab, network capture. LOW.
- **zhizhuodemao/patchright-mcp** (5★) — the recompiled Patchright fork used by js-reverse-mcp (protocol-level stealth, no page JS injection). Part of the js-reverse story.
- **CapMasterCloud/capmonster-mcp-patchright-captcha-solver** (1★) — commercial captcha solver MCP on Patchright. LOW.
- **RsGoksel/MechCP** (0★). "Hardened MCP server: CDP-level control, dynamic Python hooks, full element cloning, AST-sandboxed AI-supplied code." LOW (early).

## 3. Human-like navigation (the ask's specific lane)

- **acunningham-ship-it/veilbrowser** (43★, created 2026-06, MIT). "Stealth automation runtime for AI agents. Drives real Chrome over raw CDP — no Playwright, no Puppeteer, no WebDriver, zero runtime dependencies." README read: **curved Bézier mouse paths, eased timing, human keystroke cadence** (vs "teleport clicks, fixed-cadence typing"); webdriver/automation-switches/`Runtime.enable` tells scrubbed; accessibility-tree snapshot → stable integer refs (agents never write selectors); passes bot.sannysoft 57/57 and Cloudflare JS challenge per demo. npm `@achamm/veilbrowser` 1.6.1 verified. Node 24 or Bun (estate node v24.21.0 ✓). Windows: native (drives installed Chrome). Value: HIGH — this is the clearest "human-like navigation" implementation found.
- **dondai44423/bladebro** (283★, created 2026-07, Apache-2.0). "Agentic browser driver: 5 tools, full control, real stealth, zero runtime deps. Re-render-immune refs, batch actions, 6-layer stealth, drive your own browser. One Rust binary, Linux/macOS/Windows." README read. Install: `npm install -g bladebro && bladebro mcp` (npm 4.0.2 verified). Windows: native (binary distributed via npm). Value: MEDIUM-HIGH.
- **yinnho/aginxbrowser** (32★). "One Rust binary, stealth TLS fingerprints, MCP native for Claude Code & Cursor... render JS/SPAs with built-in V8, drive interactive login sessions, no Chromium." Value: MEDIUM (login-session drive = authenticated flow).
- **ImanKari/G9BrowserAgent** (5★). "AI agents drive real Chrome and Edge through MCP: two engines, one local daemon, human-like input, reviewable evidence. Windows, macOS, Linux." Value: LOW-MEDIUM.
- **michaelolmos/tsaagan** (2★). "Human-like browser control, verify-first (proves every action worked), MCP server + JS & Python SDKs." LOW.
- **afkcodes/calude-browse** (0★). "Trusted CDP input + accessibility-tree perception (no screenshots), MCP server." LOW.
- **ironmindai/eve** (0★). "MCP server + WebSocket router giving Claude Code live control of a real browser session — authenticated browsing, LLM-optimized page parsing, human-like interaction." On-topic but unproven. LOW.

## 4. MITM interception as MCP

- **snapspecter/mitmproxy-mcp** (123★, updated 2026-09-28). README read: wraps mitmproxy — start/stop, flow inspection, traffic search/filters, JSONPath/CSS extraction, **session variables (CSRF-token capture → replay)**, interception rules (inject headers/replace body/block), **stealth replay via curl-cffi Chrome/Safari TLS impersonation**, fuzz endpoint, OpenAPI reconstruction from captured traffic, auth-pattern detection, scraper-code generation. Install: `uvx mitmproxy-mcp` (or clone + `uv run --directory ... mitmproxy-mcp`). Windows: native (mitmproxy is pip/Windows-friendly; Python-3.14 compat of mitmproxy not verified here). Value: HIGH — layers agent-facing MCP tools directly onto the estate's existing mitmproxy investment.
- **spectral-mcp/spectral** (118★). README read: "records the traffic while you browse, uses an LLM to understand what each call does, and generates MCP tools that any AI agent can call" — websites, Android apps, desktop apps, CLI tools; self-repairing generated tools; LLM at build time only; direct HTTP calls at runtime. Install: PyPI `spectral-mcp` (`pip install spectral-mcp`, per README badge). Windows: native (Python). Value: MEDIUM-HIGH — authenticated-flow testing: log in manually once, agent gets durable API tools.
- **usestring/powhttp-mcp** (82★). "Debug HTTP requests better (powhttp)." Value: LOW-MEDIUM.
- **lucasoeth/mitmproxy-mcp** (18★), **moha-abdi/mitmproxy-mcp** (9★), **lups2000/mitmproxy-MCP** (7★, addon-first), **u33pk/mitmproxy-mcp** (7★), **Aillumine/mitmproxy-mcp** (3★, mock data), **numb747/mitmweb-mcp** (2★, reads the mitmweb session you're watching), **mplogas/mitmproxy-mcp** (1★, WiFi-AP IoT TLS interception + tshark + credential/API-key flagging), **m277m277/fiddler-mcp** (1★, credential extraction). All LOW unless a specific fit.
- **hilather/go-lab-mitmproxy** (0★). "Laboratory HTTP(S) intercepting proxy... REST, MCP, embedded flow inspector." LOW.

## 5. Burp / ZAP integration lane

- **PortSwigger/mcp-server** (1199★) — OFFICIAL Burp Suite MCP extension. README read: Java extension (build `./gradlew embedProxyJar` → load `burp-mcp-all.jar` in Burp), Burp-side SSE MCP server on `http://127.0.0.1:9876` + packaged stdio proxy for Claude Desktop. Windows: native IF Burp+Java present (estate Burp presence not verified). Value: MEDIUM (high if Burp is in the toolkit).
- **Cy-S3c/BurpMCP-Ultra** (249★). "149 tools for Burp Pro — proxy, scanner, inline fuzzer, race conditions, guided injection, JWT/IDOR attacks, recon & OOB, real-time dashboard." Requires Burp Pro. Value: MEDIUM.
- **six2dez/burp-ai-agent** (1516★) — Burp extension adding MCP tooling + AI analysis (adjacent, extension not browser). **six2dez/burp-mcp-agents** (231★) — setup guides connecting Burp MCP to Codex/Gemini/Ollama (Ollama relevant to estate's qwen3:4b).
- **h4ckologic/bughunter-ai** (76★). "Autonomous Bug Bounty Hunting Framework for Claude Code. 20 AI agents, state-machine orchestration, Burp Suite MCP, credential vault. Type 'hunt target.com'." Value: MEDIUM (orchestration layer over this lane).
- **sal-scar/ghostcrawler-mcp** (7★, GPL v3, updated 2026-09-29). README read: Chrome extension + Node MCP server (:3200) + burp-bridge daemon (:3201) + Burp MCP (:9876, SSE). "Crawls attack surfaces, fires exploits through your browser, logs every finding to Burp Proxy History + Repeater" — chains auth bypass, IDOR, stored XSS in the real browser with live cookies. Install: `git clone` + `./setup.sh` (macOS/Linux) or `powershell -ExecutionPolicy Bypass -File setup.ps1` (Windows — **explicitly untested per README**). Needs VS Code + GitHub Copilot + Burp + Burp MCP BApp. Value: MEDIUM (Windows path untested; strong concept).
- **dtkmn/mcp-zap-server** (67★). "Self-hosted ZAP operator for guided web security scans, findings, reports, production guardrails." Deployment model (Docker?) not verified → windows: unknown. Value: MEDIUM.
- **MINESY236/chrome-mcp-server-noredact** (0★). mcp-chrome MV3 extension patched for pentest automation: "no JS redaction, cookies, curl capture." Value: LOW (useful patch idea).

## 6. JS-reversing / auth-flow analysis MCP (mostly Chinese ecosystem)

- **zhizhuodemao/js-reverse-mcp** (2852★, updated 2026-09-29, Apache-2.0). README (zh) read: AI-native JS reverse-engineering MCP — headed Chrome debugging, breakpoints (evaluate in call frame, scope vars, step), script search/save + auto-beautify, network + WebSocket analysis (request call stacks, XHR breakpoints, Set-Cookie identification, raw body/header export, WS message grouping), browser-state replay (clear cookies/cache/storage + reload to reproduce cookie/risk-control flows), **default headed + persistent login state across sessions**, dedicated recompiled Patchright fork (`@zhizhuodemao/patchright`, protocol-level stealth, no page JS injection), optional `--cloak` CloakBrowser source-level fingerprint mode. Install: `claude mcp add js-reverse npx js-reverse-mcp` / `codex mcp add js-reverse -- npx js-reverse-mcp`; MCP config `{"command": "npx", "args": ["js-reverse-mcp"]}`. npm 4.0.5 verified; engines node ^20.19||^22.12||>=23 — estate v24.21.0 ✓. Windows: native (Node + Chrome stable). Value: HIGH — the heavyweight of this lane; persistent-login + breakpoint tooling is exactly authenticated-flow analysis.
- **WhiteNightShadow/camoufox-reverse-mcp** (522★, updated 2026-09-29). README (zh) read: 35 JS-reverse tools on Camoufox (Firefox, C++-level fingerprint modification — no page JS patch, avoids descriptor/prototype leaks), BrowserForge realistic fingerprint distribution, runtime probes + source instrumentation for **JSVMP bytecode analysis** (KProtect VM, javascript-obfuscator CFF, CryptoJS/FingerprintJS validated per docs), hook persistence with defineProperty anti-overwrite, network request comparison, full Cookie/Set-Cookie capture. NOT on npm (verified absent); Python-based — exact pip name not verified, install from repo. Windows: likely native (Camoufox ships Windows builds; unverified here). Value: MEDIUM-HIGH (unique JSVMP capability).
- **a0yark/js-reverse-pro-mcp** (9★) — Pro fork of js-reverse-mcp (hook framework, deobfuscation, sessions, artifacts). LOW-MEDIUM.
- **wuji1/jshook-reverse-tool** (npm 0.1.1 verified) — Chinese MCP with 80+ tools for hook injection / encrypted-parameter analysis (found via Chinese web search; npm registry entry verified). Value: LOW-MEDIUM.
- **NoOne-hub/JSReverser-MCP** (MIT, per js-reverse-pro attribution) — not individually fetched.
- **TheQmaks/awesome-web-reversing** (2★, updated 2026-09-28). "Verified tools and workflows for runtime JavaScript reverse engineering of modern defended SPAs (2024-2026 anti-bot landscape). Every entry checked against the GitHub API." Curated list worth a follow-up crawl. The **Web-Reversing-Tools** GitHub org mirrors ~hundreds of those repos (creepjs, tls-client, burp-awesome-tls, obfuscator-io-deobfuscator...) — archive, not new tools.

## 7. Session handling / authenticated flows (dedicated)

- **badchars/hackbrowser-mcp** (23★, updated 2026-09-26, MIT). README read: "The first browser MCP built for security testing." Real Firefox + 39 tools + 60+ injection payloads, runtime Bun. Killer workflow: **two isolated containers (admin + user), logs in both, browses, captures traffic, compares responses across roles → "User can access GET /api/admin/users — should return 403, returns 200"**. That is authenticated-flow IDOR testing as a first-class primitive. Install: repo + Bun runtime (exact command line not captured in the section I read — see repo Quick Start). Windows: Bun runs on Windows; Firefox native — untested. Value: MEDIUM-HIGH (small but exactly on-mission).
- **agelyhq/mcp-camoufox** (2★). "Anti-detect Firefox (Camoufox), sign-in-once profiles, and **mandatory session isolation between conversations**." The session-isolation-per-conversation design is notable for agent safety. LOW-MEDIUM.
- **ofershap/real-browser-mcp** — MCP + Chrome extension, agent controls your real browser with existing logins. **hangwin/mcp-chrome** — daily Chrome with existing sessions/habits. Both MEDIUM for authenticated testing (no stealth).
- **browsermcp/mcp** (~6.6k★ per search result) — Playwright-MCP adapted to automate the user's existing browser (sessions preserved). General-purpose, not offense-specific. MEDIUM.
- **2captcha/mcp-captcha-solver** (9★). README read: demo architecture — agent → browser/captcha MCP tools → Selenium helpers → structured result; reCAPTCHA v2 solving as a tool with session-based browser automation; human-in-the-loop patterns planned for Turnstile. LOW (demo for an article).
- **dennywu2966/oauth-for-playwright** (0★). OAuth SSO validation via Playwright MCP with human-in-the-loop MFA. LOW.
- **MikkoParkkola/nab** (14★). Rust single binary microfetch: "Real browser-cookie auth, passkeys, anti-bot reach, on-by-default prompt-injection defense" — CLI + MCP + Claude Code plugin. LOW-MEDIUM (fetch-with-session, not full browser).
- **meskhetian/linkedin-applicants-mcp** (28★), **devag7/linkedin-mcp** (10★), **Steph-ux/linkedin-mcp-server**, **guilhermesilveira/chatgpt-mcp** (persistent login, CDP-shared session) — authenticated target-specific drives; pattern references, not estate tools.

## 8. Rust/alt-engine stealth (no-Chromium lane)

- **yfedoseev/browser_oxide** (108★, updated 2026-09-29). "Stealth headless browser engine in Rust — native BoringSSL TLS/JA4 fingerprint, real JS via deno_core, no Chromium, no CDP. Python + MCP bindings. A camoufox alternative." Windows: unknown (Rust engine; Windows build unverified). Value: MEDIUM.
- **autokeren/ghostfox** (5★). "Fingerprint-coherent Firefox engine + Rust MCP runtime. Self-hosted, engine-level anti-detect." LOW (early).
- **maestrojeong/browser-rs-mcp** (25★). "One shared Chrome for many AI agents, 64+ Playwright-style tools, no Node.js runtime" (Rust). LOW-MEDIUM.
- **MathiasPaulenko/wavexis-mcp** (2★). "220 tools for Chrome/Edge/Firefox via CDP+BiDi, 13 capability tiers, stealth mode, Lighthouse audits. 100% Python, no Chromium download." LOW-MEDIUM.
- **joshfng/crucible** (via HN) — Ruby stealth MCP on Ferrum. Not fetched. LOW.

## 9. Docker-required (estate has NO Docker engine — listed for completeness)

- **psyb0t/docker-stealthy-auto-browse** (86★). Camoufox in Docker, zero CDP exposure, real OS-level mouse/keyboard via PyAutoGUI, JSON HTTP API + MCP, noVNC watch. windows: docker. Value: LOW now (interesting once Docker exists).
- **nczz/BrowseForge** (54★). Anti-detect browser workspace: isolated profiles, REST, MCP, Docker, Playwright. docker. LOW now.
- **tanishmeh/stealth-web-search** (2★). Stealth JS-rendering browser + research sub-agents in one Docker container. docker. LOW.
- **redf0x1/camofox-browser** (407★) REST anti-detect browser server (OpenClaw plugin) — Docker-leaning but has a Pinokio 1-click launcher for Windows (DSRPT/camofox-browser-pinokio); **redf0x1/camofox-mcp** (114★) is the MCP server for it. Value: MEDIUM (native Windows path exists via Pinokio; unverified).

## 10. Observed and excluded (with reason)

- **skernelx/tavily-key-generator** (1560★) — "multi-service signup automation, key validation, isolated proxy pools" (Tavily/Firecrawl free-tier key harvesting). This is ToS-abuse automation against third-party services, not authorized-security tooling — excluded from the recommended haul on policy grounds, recorded here only because it appeared in the camoufox MCP search results.
- **alijuncb/road? no** — not present. **donsetch** (761★, Rust fetch/search/crawl) — scraping infra, not offense; excluded.
- **Browser-use / Notte / Hyperbrowser / OwlBrowser** (HN hits) — commercial or general agent-browser platforms, not offensive tooling; excluded.

---

## Every query issued (exhaustive log)

WebSearch (Z.ai web_search_prime):
1. `nodriver-proxy-mcp github`
2. `WonderSuite browser automation MCP github`
3. `JS逆向 MCP 浏览器 反爬 Claude 工具` (first attempt returned -429 rate limit; retry succeeded)
4. `"WonderSuite" bug bounty AI review`

WebFetch:
5. https://github.com/sfr-development/WonderSuite-Ai-Bug-Bounty (summarize components/MCP/install/Windows)

GitHub API via `gh api` (search/repositories unless noted):
6. `q=nodriver-proxy-mcp` → 1 hit (BobongKu/nodriver-proxy-mcp)
7. `q=nodriver+mcp` → 12 hits (stealth-browser-mcp 2161★, mcp-stealth-chrome, nodriver-mcp-server, Saber-CC, namecallfilter, stealth-web-mcp, TeslaWebScrape, MechCP...)
8. `q=patchright+mcp` → 49 hits (js-reverse-mcp 2852★, patchright-mcp-lite, rickicode/patchright-browser, capmonster, ringo-patchright, wraith-mcp, deepspider...)
9. `q=camoufox+mcp` → 76 hits (camoufox-reverse-mcp 522★, whit3rabbit 49★, mcp-camoufox RobithYusuf, camofox-browser 407★, camofox-mcp 114★, browser_oxide 108★, gomoufox, BrowseForge, docker-stealthy-auto-browse, browser-search 526★, tavily-key-generator 1560★...)
10. `q=mitmproxy+mcp` → 40 hits (snapspecter 123★, spectral 118★, powhttp 82★, lucasoeth, lups2000, mplogas IoT, fiddler-mcp...)
11. `q=browser+pentest+mcp+in:name,description` → 3 hits (ghostcrawler-mcp, chrome-mcp-server-noredact, recon-orchestrator)
12. `q=mcp+security+pentest+browser+stealth&sort=stars` → **0 hits** (dead end)
13. `q=hacking+mcp+browser&sort=stars` → 12 hits (subio-mcp, 2captcha/mcp-captcha-solver, browser-ipc-cdp, antibrow/recipes...)
14. `q=zap+mcp+in:name,description&sort=stars` → 107 hits (mcp-zap-server 67★ most relevant)
15. `q=burp+mcp+in:name,description&sort=stars` → 158 hits (burp-ai-agent 1516★, PortSwigger/mcp-server 1199★, BurpMCP-Ultra 249★, burp-mcp-agents 231★, bughunter-ai 76★...)
16. `q=awesome+mcp+security&sort=stars` → 65 hits (Puliczek 740★...)
17. `q=browser+stealth+mcp+created:>2026-06-01&sort=stars` → 66 hits (bladebro 283★, veilbrowser 43★, aginxbrowser 32★, browser-rs-mcp 25★, ghostfox, wavexis, camofox-pinokio...)
18. `q=web+reversing+awesome+in:name&sort=stars` → TheQmaks/awesome-web-reversing
19. `q=awesome+web3+reversing+js&sort=stars` → **0 hits** (dead end)
20. `q=human-like+mcp+browser&sort=stars` → 6 hits (G9BrowserAgent, tsaagan, human-browser-copilot, calude-browse, eve, agentcursor)
21. `q=mcp+login+session+persist+browser&sort=stars` → **0 hits** (dead end)
22. `q=mcp+oauth+sso+browser+flow&sort=stars` → 1 hit (oauth-for-playwright)
23. `q=browser+profile+session+mcp+anti-detect&sort=stars` → 1 hit (agelyhq/mcp-camoufox)
24. `q=topic:anti-bot+topic:mcp&sort=stars` → 41 hits (donsetch, browser-search, anansi 116★, browser_oxide, mcp-stealth-chrome, deepcloak, svipall, scrapfly-mcp, nab, ghostfox)
25. `q=browser+offense+mcp` → **0 hits** (dead end)
26. `q=idor+mcp+browser&sort=stars` → 1 hit (badchars/hackbrowser-mcp)
27. `q=browser-use+mcp+stealth&sort=stars` → 4 hits (ghostfox, web-core, rust-browser-mcp, wraith-mcp — no new)
28. `users/Web-Reversing-Tools/repos` → mirror archive org (creepjs, tls-client, burp-awesome-tls mirrors...)
29. `repos/Puliczek/awesome-mcp-security/readme` → only Burp line matched browser/offense regex
30. README fetches (`repos/X/readme`): BobongKu/nodriver-proxy-mcp, vibheksoni/stealth-browser-mcp, zhizhuodemao/js-reverse-mcp, sal-scar/ghostcrawler-mcp, snapspecter/mitmproxy-mcp, PortSwigger/mcp-server, andresolbach/nodriver-mcp-server, 2captcha/mcp-captcha-solver, spectral-mcp/spectral, acunningham-ship-it/veilbrowser, dondai44423/bladebro, WhiteNightShadow/camoufox-reverse-mcp, badchars/hackbrowser-mcp (raw)
31. `repos/sfr-development/WonderSuite-Ai-Bug-Bounty/releases/latest` → v0.3.35 assets incl. Windows .exe/.msi

Registry checks (curl): pypi JSON for wraith-mcp, nodriver-proxy-mcp, stealth-browser-mcp, nodriver-mcp; npm registry for js-reverse-mcp, mcp-camoufox, jshook-reverse-tool, camoufox-reverse-mcp (absent), @achamm/veilbrowser, bladebro.

HN Algolia (`curl hn.algolia.com/api/v1/search`): `nodriver-proxy-mcp` (0 hits — dead end), `WonderSuite` (16 hits, all name-collisions: Bluehost/ThinkFree/office suites), `stealth browser MCP` (14 hits → crucible, owlbrowser, notte, hyperbrowser; general platforms).

Local: `node --version`; `mkdir -p out/research`.

## Dead ends / not reachable
- No HN, Reddit, or independent-review coverage of nodriver-proxy-mcp at all (0 Algolia hits) — 3★ project, awareness lives in the author's Korean README circle only.
- "WonderSuite" web results are ~90% Bluehost's WordPress product — the bug-bounty tool's discoverability is poor; use exact repo name.
- camoufox-reverse-mcp is not published on npm despite Node-adjacent ecosystem (Python project) — install path is repo clone.
- GitHub code/topic search for combined security qualifiers returns 0 — the lane's discovery surface is name/description search + awesome lists only.
- Korean/Japanese blog lane: only the author's own README_ko.md found; Japanese sources not searched (no leads surfaced from any query).
- Not verified anywhere: whether the estate has Burp Suite / Java (needed for the Burp lane tools); whether a Python 3.10–3.13 interpreter exists on the VM for nodriver-proxy-mcp.

## Estate fit — bottom line
1. **nodriver-proxy-mcp** (pip; needs py<=3.13) — closest single-server match to "human-like navigation + MITM interception + authenticated-flow testing + session handling" (39 tools, auth-pattern detection, session variables, dual-layer interception, sandboxed code-mode). The Python <3.14 pin is the only blocker; everything else is native Windows.
2. **WonderSuite** (native .msi, MCP at 127.0.0.1:3100/mcp) — adds Burp-class MITM + TLS/JA3 impersonation + scanner + OAST + stealth browser in one Windows-native desktop app; the HTTP MCP endpoint slots into the gateway aggregator.
3. **js-reverse-mcp** (`npx`, Node 24 ✓) — the mature (2852★) lane leader for auth-flow/JS reversing with persistent login state and breakpoint-driven analysis.
4. **veilbrowser** (npm, Node 24 ✓) — the clearest human-like navigation implementation (Bézier paths, eased timing, keystroke cadence) on real Chrome.
5. **snapspecter/mitmproxy-mcp** (`uvx`) — turns the estate's existing mitmproxy into agent-facing tools with curl-cffi stealth replay and session-variable chaining.
6. **hackbrowser-mcp** — small but purpose-built: role-isolated containers for authenticated IDOR/authz testing.

---
---

# Session 2 — 2026-09-29, second exhaustive pass (browser-offense lane)

Everything below was verified in THIS session (commands + outputs in transcript; raw JSON in `out/research/_raw/`). No tool was installed or executed on the VM — research only.

## Backends used this session (incl. one mandated workaround)

- **Exa** (env EXA_API_KEY, POST api.exa.ai/search): 5 concept queries — worked throughout.
- **Firecrawl direct** (env FIRECRAWL_API_KEY, POST api.firecrawl.dev/v1/search): **BROKEN — HTTP 401 "Unauthorized: Invalid token"** on both attempts (`_raw/fc_nodriver_proxy_mcp.json`, `_raw/fc_WonderSuite_browser_automation_MCP.json`). Configured around it instead of abandoning (mandate): 
- **Firecrawl via the estate gateway front**: probed `http://127.0.0.1:31100/mcp` — `initialize` → serverInfo `cyberstrike-gateway 1.29.0`; plain `tools/list` → error "Missing session ID"; captured `mcp-session-id` from initialize response headers; gateway exposes only 3 meta-tools (`harness_bridge_status`, `harness_capabilities`, `harness_invoke`); `harness_capabilities` shows backend `firecrawl` (kind module `fronts.firecrawl`, status available, dual-mode self-hosted/cloud); `harness_invoke {"backend":"firecrawl","tool":"search","arguments":"{\"query\":\"offensive browser automation MCP server anti-detect 2026\",\"limit\":6}"}` → `{"mode":"cloud","status_code":200,...}` (`_raw/gw_fc2.txt`). Firecrawl mandate satisfied through the estate's own front. (First attempt used tool name `firecrawl_search` → "unknown tool; tools: scrape/search/crawl/status".)
- **DDG keyless** (ddgs 9.16.0 already installed): 3 queries.
- **gh api search/repositories**: 10 templates; one transient 403 search rate-limit on `topic:mcp-server+topic:offensive-security`, retried after `sleep 6` → success.
- **HN Algolia**: 3 queries.
- **awesome-list walk**: punkpeye/awesome-mcp-servers README (1.36 MB) fetched via raw.githubusercontent and grepped — 13 stealth/nodriver/camoufox/cloak/anti-detect/undetect hits recorded below.

## NEW findings this session (not in Session 1)

### N1. CloakHQ/CloakBrowser — 31,790★ — the dominant stealth engine
- `gh api search q=cloakbrowser` → 271 repos; CloakHQ/CloakBrowser 31790★, pushed 2026-09-27. README (raw, 73 KB, `_raw/cloakbrowser-readme.md`): stealth Chromium with **87 source-level C++ fingerprint patches** ("Not a patched config. Not a JS injection."); `humanize=True` → "human-like mouse curves, keyboard timing, and scroll patterns"; passes Turnstile/FingerprintJS/BrowserScan (30+ detectors); **Windows x64 builds confirmed — README line 155: Pro Stable Chromium `152.0.7977.82.1` "on Linux x64, Linux ARM64, and Windows x64"**, line 157 "rebased the full patch set onto Chromium 152 for Linux and Windows", line 159 "Windows native GPU passthrough". Binary auto-downloads per platform. Install: `pip install cloakbrowser` or `npm install cloakbrowser`. Free tier ("free to try" via GitHub sign-in) + paid Pro.
- **swimmwatch/cloakbrowser-mcp** (66★, pushed 2026-09-29 — brand new): Playwright-MCP-compatible surface over CloakBrowser; **README line 54: "Cross-platform checks cover npm on ... Windows x64 across Node.js 22 and 24-26"**; stdio + Streamable HTTP; MCP Registry + awesome-mcp-servers listed; dedicated "Humanized Input Behavior" doc. Install: `npx -y cloakbrowser-mcp@latest` (`claude mcp add cloakbrowser -- npx -y cloakbrowser-mcp@latest`). Value: **HIGH** (engine+wrapper pair, Windows-native, newest of the new).
- CloakHQ/CloakBrowser-Agent (1★, pushed 2026-09-29) — official Jev-powered agent on CloakBrowser; watch.
- Adjacent found in same sweep: qihe-no-study/cf-killer (56★), waguriagentic/captcha-solver (275★), clawdbrunner/captcha-solver (225★), swimmwatch docs.

### N2. Mouseww/anything-analyzer — 3721★ — Chinese all-scene capture + MITM + MCP
- 3721★, TypeScript/Electron 35, pushed 2026-09-16. README (zh, raw): embedded CDP browser + MITM proxy (:8888, CA install) + terminal/script (Python/Node/Go) + mobile/IoT capture — **all sources merged into one unified Session**; JS Hook injection intercepts `fetch`/`XHR`/`crypto.subtle`/`CryptoJS`/`SM2/3/4`; encrypted-code extraction from JS files; 5 AI analysis modes (auto-identify / API reverse / **security audit** / performance / JS-crypto reverse); **built-in MCP Server** (capture+analysis exposed to Claude Desktop/Cursor) + MCP client. 
- Windows-native: README install table `Anything-Analyzer-Setup-x.x.x.exe`; `releases/latest` (tag v3.6.61) asset list includes **`Anything-Analyzer-Setup-3.6.62.exe`** (+ .dmg/.AppImage). Install: download Setup exe from Releases. Value: **HIGH** — JS-crypto reversing + unified-session traffic analysis fills a real estate gap.

### N3. WonderSuite — details hardened this session
- `gh api repos/sfr-development/WonderSuite-Ai-Bug-Bounty`: 51★, Rust, pushed 2026-09-28 (day before this session), 29 open issues.
- Full README (raw, 46 KB, `_raw/wondersuite-readme.md`) confirms and extends Session 1: **MCP = Axum JSON-RPC 2.0 at :3100, 90 tools (24 browser + 5 port-scan + proxy/scanner/recon/OAST/reporting)**; browser input goes through Chrome's real input pipeline so **`event.isTrusted === true`** (defeats fraud SDKs dropping programmatic submissions), humanlike Bezier trajectories with Gaussian jitter, per-char typing cadence from a normal distribution, **3 stealth profiles `fast`/`human`/`paranoid`**, `browser_stealth_check` self-test returning an isTrusted score; **authenticated flows: `browser_storage_full` one-shot auth dump (cookies+LS+SS+IDB+SW+Cache → ready-to-replay `Cookie:` header)** and `browser_replay_to_proxy`; OAST = embedded HTTP/DNS/SMTP listeners with path-correlated callbacks driven via `active_scan(with_oast:true)` (blind cmdi/SSRF/Log4Shell); port scanner uses bundled **WinDivert on Windows** (one UAC consent, HVCI-aware fallback). MITM proxy impersonates Chrome 137 ClientHello/JA3/JA4 + HTTP/2 SETTINGS via BoringSSL.
- Install: `WonderSuite_0.3.35_x64_en-US.msi` (17.1 MB) or `-setup.exe` (13.2 MB) from releases/latest — exact: https://github.com/sfr-development/WonderSuite-Ai-Bug-Bounty/releases/download/v0.3.35/WonderSuite_0.3.35_x64_en-US.msi . Windows: **native** (no Docker).

### N4. BobongKu/nodriver-proxy-mcp — Windows support now SOURCE-verified
- `gh api repos/BobongKu/nodriver-proxy-mcp` (this session): 3★, Python, **pushed_at 2026-04-10** (Session 1 recorded "updated 2026-09-09" — my repos call this session says 2026-04-10; treat as semi-dormant since April). Topics: ai-agent, browser-automation, cdp, claude, fuzzing, mcp, mcp-server, mitmproxy, nodriver, pentesting, proxy, security, vulnerability-scanner, web-security.
- Source-verified Windows-native process management (raw files fetched):
  - `src/nodriver_proxy_mcp/browser/daemon.py` → line 100 "Uses platform-specific checks: OpenProcess on Windows, kill(0) on Unix"; line 116 `if sys.platform == "win32":`; line 887 `if sys.platform != "win32":` (`_raw/npmc_daemon.py`).
  - `src/nodriver_proxy_mcp/codemode/tools.py` → `_create_windows_job_object(memory_limit_mb=256)` using `CreateJobObjectW`, `JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` via kernel32 ctypes (`_raw/npmc_codemode.py`).
- README full read (13,699 chars): 39 tools = 18 proxy (real mitmproxy :8082, SQLite traffic.db, record/replay/fuzz/interception rules/session variables) + 20 browser (nodriver + CDP Fetch, localStorage/sessionStorage/JS console) + `execute_security_code` sandbox (NdpSDK, 29 async methods; race conditions via `asyncio.gather`, blind-SQLi binary search); `detect_auth_pattern` auto-detects JWT/Bearer/API key/session cookie/CSRF/OAuth2; IDOR via two parallel sessions; Burp chaining `upstream="localhost:8080"`. Install: `pip install nodriver-proxy-mcp` (PyPI 1.0.1; **Session 1 verified requires_python `<3.14,>=3.10` — needs a ≤3.13 interpreter on the VM, still unverified present**). Value: **HIGH** (named in ask; exact fit; dormant upstream is the only caveat).

### N5. Session-handling specialists (new this session)
- **xav-ie/browser-session-mcp** (1★, Rust, pushed 2026-07-12, README read): isolated **long-lived Chrome sessions addressed by session id** — survive MCP reconnects and subprocess restarts; lossless console+network capture to disk; per-session stealth toggle; **"human takeover": hand a live page to a person for password/passkey/2FA login without the agent seeing credentials**; saved cookie states (login once, reuse). **Windows: prebuilt binaries are "Linux or macOS (x86_64/aarch64)" only — Windows requires a Rust source build, not verified here.** Value: MEDIUM.
- **usk6666/yorishiro-proxy** (16★, Go, pushed 2026-09-17): "AI-native MITM proxy — MCP server for traffic interception, recording & replay". Windows unverified (Go). Value: MEDIUM.
- **confuciussayuhm/ja3-proxy** (0★, Python, pushed 2026-09-06): "TLS-impersonating MITM proxy with an MCP control plane — presents a real browser JA3/JA4 + HTTP-2 fingerprint upstream of an intercepting proxy" — the free-software version of WonderSuite's TLS trick. Very new. Value: MEDIUM (watch).
- **Makhsum/httptrafficmonitr** (3★, C# WPF, pushed 2026-07-23): "Windows desktop HTTP/HTTPS traffic monitor (MITM proxy, WPF) with an MCP server" — explicitly Windows-native. Value: LOW-MEDIUM.
- Others from `q=mitm+proxy+mcp` sweep: sailro/HttpProxyMcp (14★, C#), moha-abdi/mitmproxy-mcp (9★; PyPI `mitmproxy-mcp` v0.6.1 per exa), GitterBois/proxying (14★), yfe404/proxy-mcp (9★), horizonfps/the-box-mcp (2★, 103 tools MITM+OOB+evidence vault — **platform badge WSL2/Linux → blocked on this no-VT-x VM**), moizxsec/mcpwn (4★, Burp-for-MCP-JSON-RPC — different sub-lane), hahwul/gori (116★, terminal intercepting proxy; MCP support NOT confirmed in what I read), Xor290/rustman (2★), kspkr/TrafficKit (1★).
- **horizonfps/the-box-mcp** deserves its own line: 103 MCP tools, stateful MITM + traffic DB + app graph + OOB (HTTP+DNS, ACME) + CVE/H1 RAG + Merkle evidence vault + scope guard + rate governor in the tool-call path — excellent design, **WSL2/Linux platform → unusable on this VM today**. windows: wsl (blocked).

### N6. More from the fresh-repo sweep (`q=stealth+browser+mcp+created:>2026-04-01&sort=updated`, 112 hits)
- **yinnho/aginxbrowser** (32★, pushed 2026-09-29 TODAY): Rust single binary, built-in V8, no Chromium, "stealth TLS fingerprints, MCP native", "drive interactive login sessions", meta-search 20 engines; 7.6× faster than headless Chrome to agent-usable text; Lightpanda co-founder starred it. Install: GitHub releases (v0.5.3+). Value: MEDIUM (watch-list; login-session drive = authenticated-flow angle).
- **dondai44423/bladebro** (283★): Rust one-binary MCP driver, "6-layer stealth", platforms badge "Linux | macOS | Windows", `npm install -g bladebro && bladebro mcp`. Value: MEDIUM.
- **GabriWar/umbra** (3★, pushed 2026-09-29): 64 tools, 0/0 creepjs, encrypted sessions, multi-browser. Watch.
- **askalf/browser-bridge** (5★): stealth headless Chromium on your own CDP endpoint + prompt-injection firewall between agent and web. Watch.
- **YogevKr/wraith** (2★, pushed 2026-09-29): "identity-borrowing stealth browser" (Camoufox + WAAP clearing + MCP). Watch.
- **maestrojeong/browser-rs-mcp** (25★): Rust, one shared Chrome for many agents, 64+ tools, no Node runtime. MEDIUM-LOW.
- **HuzaifaAqeel/Vibatchium-MCP** (0★): N parallel stealth Chrome sessions + encrypted credential vault with TOTP (auth-flow pattern). Watch.
- **TylerFlar/autopilot-mcp** (0★): free-roam browser MCP with learned playbooks and Bitwarden-backed credentials. Watch.
- **trueoriginlabs/vibatchium** (awesome-list hit; README 404 on main — default branch may differ): "Patchright stealth: parallel persistent profiles, encrypted credential vault with 2FA, prompt-injection scanning" — awesome-list lists it 🍎🐧 only (no 🪟). Windows unknown.
- **firerpa/lamda** (8503★, from `q=mitm+proxy+mcp`): Android full-stack control, one-click MITM, MCP/Agent — needs Android; **no VT-x on this VM → emulator impossible**; real-device only. LOW here.

### N7. awesome-mcp-servers walk (punkpeye, grepped `_raw/awesome-mcp-servers.md`)
New entries not seen via search: **acunningham-ship-it/veilbrowser** (43★ — "can attach to a running Chrome to reuse logged-in sessions"), **autokeren/ghostfox** (5★, Firefox-152-fork engine + Rust MCP runtime, PyPI `ghostfox` + npm `ghostfox`, MCP Registry listed, 🪟 badge), **dmytrome/groundhog** (stealth-patched Chrome search/reading), **MathiasPaulenko/wavexis-mcp** (CDP+BiDi, stealth mode), **Mingye-Lu/AgenticCrawler**, **lucasmartins-ai/lookacrawler**, **maxylev/searchfetch**, **FayAndXan/spectrawl** ("stealth browsing, cookie auth and actions"), **andresolbach/nodriver-mcp-server** (listed 🪟), **swimmwatch/cloakbrowser-mcp** (listed 🪟).

### N8. Commercial / SDK lane (recorded, not verified deeply)
- **Argus** (browserargus.com, by Simnetiq; HN id 49563623): anti-detect browser with automation, local API, and MCP — npm `@argus-browser/mcp-server` exists (npmjs hit via exa), /mcp + /api-reference docs pages. Paid product; Windows presumed but unverified. Value: MEDIUM (commercial).
- **antibrow/antibrow**: engine-level anti-detect SDK (PyPI `antibrow`, npm `anti-detect-browser`, Vercel AI SDK tools); JS profile open needs `ANTIBROW_KEY`; Windows unverified. Value: LOW-MEDIUM.
- **yfedoseev/browser_oxide** (108★): Rust from-scratch stealth engine, native BoringSSL TLS/JA4, V8 via deno_core, MCP bindings, 118/126 anti-bot corpus routed, "research-grade pre-1.0"; `pip install browser-oxide`. Watch-list; Windows build unverified.
- **TechQaiser/persona-studio** (74★): self-hosted anti-detect browser & profile manager, pluggable engines (CloakBrowser/Camoufox/Patchright/Playwright). Adjacent (manager, not MCP).
- **techinz/browsers-benchmark** (392★): bypass-rate benchmark across Cloudflare/DataDome/reCAPTCHA/Kasada/Imperva/Akamai/PerimeterX — use to pick engines; not itself offensive tooling.
- **dzivkovi/MCP-Server-Browser-Auth** (README read): research-only repo (no code) on SSO session-cookie extraction via Playwright for MCP auth; good concept reference for the authenticated-flow sub-lane. LOW.

## Discrepancies vs Session 1 (flagged, not silently merged)
- Session 1 says nodriver-proxy-mcp "updated 2026-09-09"; my `gh api repos` this session returned `pushed_at 2026-04-10T04:07:00Z`. I trust my call for my session; possibly a branch/tag push since. Semi-dormant either way.
- Session 1 lists stealth-browser-mcp install as `pip install stealth-browser-mcp` (PyPI 0.1.4); the repo README (read this session) recommends git-clone + `pip install -r requirements.txt` + run `src/server.py` because PyPI lags (0.1.4 vs repo 0.2.5). Use the clone path.
- Session 1's HN query `nodriver-proxy-mcp` → 0 hits matches my ddg/exa experience: the tool's awareness lives in LobeHub/mcpworld/himcp.ai directory listings only.

## Session 2 exhaustive query log (exact)

Exa (`out/research/_tools.py exa "..."`, raw in `_raw/exa_*.json`):
1. `MCP server that wraps stealth anti-detect Chrome for offensive browser automation`
2. `MCP server for MITM interception of browser traffic during security testing`
3. `anti-detect browser with local API and MCP for automation Argus`
4. `MCP server browser login authenticated session cookie testing pentest`
5. `human-like browser navigation agent MCP humanize mouse curves keystroke`

Firecrawl direct (both → HTTP 401 Invalid token): `nodriver-proxy-mcp`; `WonderSuite browser automation MCP`.
Firecrawl via gateway harness_invoke: `offensive browser automation MCP server anti-detect 2026` (limit 6) → 200 cloud mode.

DDG (ddgs 9.16.0): `nodriver-proxy-mcp MCP server`; `WonderSuite bug bounty MCP`; `offensive browser automation MCP server`.

HN Algolia: `browser automation MCP`; `stealth browser`; `wondersuite` (all name-collisions, consistent with Session 1).

gh search/repositories (per_page=100 unless noted):
1. `q=nodriver+mcp` → 12
2. `q=wondersuite` → 4 (incl. gusthemole/WonderSuite — unrelated topological prompts; api-evangelist/alice — unrelated ActiveFence WonderSuite)
3. `q=mitm+proxy+mcp` → 30 (output truncated by `head -60`; snapspecter/mitmproxy-mcp from Session 1 not re-listed in my visible cut — not contradicted, just not re-verified this session)
4. `q=camoufox+mcp` → 76
5. `q=patchright` → 216 (top 20)
6. `q=seleniumbase+mcp` → 6
7. `q=browser-use+mcp` → 207 (top 8)
8. `q=cloakbrowser` → 271 (top 8)
9. `q=topic:mcp-server+topic:offensive-security` → 23 (403 once, retry OK; mostly multi-tool consoles — LitterBox 1542★, mcp-security-hub 796★, blitzstrike 488★, RedTeam-Agent 72★, tengu 61★, tcpk 21★ — adjacent lanes, not browser-offense)
10. `q=stealth+browser+mcp+created:>2026-04-01&sort=updated` → 112 (top 20)

gh api repos/readme/releases this session: BobongKu/nodriver-proxy-mcp (repo+readme+git tree), sfr-development/WonderSuite-Ai-Bug-Bounty (repo+readme+releases+releases/latest), vibheksoni/stealth-browser-mcp, Mouseww/anything-analyzer (repo+readme+releases/latest), horizonfps/the-box-mcp, zhizhuodemao/js-reverse-mcp, WhiteNightShadow/camoufox-reverse-mcp, redf0x1/camofox-mcp, yfedoseev/browser_oxide, seleniumbase/seleniumbase-mcp, andresolbach/nodriver-mcp-server, acunningham-ship-it/veilbrowser, autokeren/ghostfox, xav-ie/browser-session-mcp, usk6666/yorishiro-proxy, confuciussayuhm/ja3-proxy, moha-abdi/mitmproxy-mcp, Makhsum/httptrafficmonitr, sailro/HttpProxyMcp, rate_limit.

raw.githubusercontent reads: CloakHQ/CloakBrowser README, swimmwatch/cloakbrowser-mcp README, BobongKu daemon.py + codemode/tools.py, zhizhuodemao README.md + README_en.md, andresolbach README, veilbrowser/ghostfox/vibatchium(404)/dzivkovi(master branch)/xav-ie/antibrow/yinnho-aginxbrowser/bladebro READMEs, sfr-development README (46 KB), punkpeye/awesome-mcp-servers README.

Local VM commands: `C:/Python314/python.exe -c ...` env/key checks; `gh auth status`; gateway probes (initialize / tools/list / capabilities / invoke) via curl.

## Session 2 dead ends
- Direct Firecrawl cloud API: dead key (401) — replaced by gateway front (worked).
- vibatchium README on `main` → 404 (default branch differs; left unresolved).
- `q=mcp+security+pentest+browser+stealth`-style combined qualifiers again returned noise/0 — consistent with Session 1's finding.
- Reddit/X/Chinese blogs beyond repo READMEs: not directly crawled this session (only snippets inside exa/ddg results); Session 1 covered Chinese WebSearch lane.
- Argus Windows support + pricing: not verified (commercial site not scraped).

## Session 2 additions to the estate bottom line
7. **CloakBrowser + cloakbrowser-mcp** — the strongest anti-detection engine (31.8k★, C++-level patches, humanize=True) with a Windows-CI-tested MCP wrapper (`npx -y cloakbrowser-mcp@latest`). Pairs with, rather than replaces, stealth-browser-mcp.
8. **anything-analyzer** (Windows Setup exe) — unified-session traffic capture + JS-crypto/SM2-3-4 reversing + built-in MCP; strongest "capture everything, reverse the crypto" desktop tool found.
9. **browser-session-mcp / yorishiro-proxy / ja3-proxy** — best-in-class primitives (session survival + human-takeover login; MCP-native MITM record/replay; JA3/JA4-impersonating MITM control plane) if individual components are preferred over suites.

Exhaustion (Session 2): the final three queries (created:>2026-04-01 sweep, exa human-like query, awesome-list grep) returned only already-recorded repos. Cross-check requirement met: exa + firecrawl(gateway) + gh sweep all used before claiming exhaustion.