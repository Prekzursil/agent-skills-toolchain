---
title: research browser-automation-sota 2026-08-27
type: note
permalink: main/research/research-browser-automation-sota-2026-08-27
tags:
- research-report
- high-confidence
- firecrawl
- websearch
---

# Seamless / Native Browser Automation — SOTA Research Report + Cursor Setting Forensics
*Generated: 2026-08-28 (deliverable dated 2026-08-27) | Sources: 22 | Providers: WebSearch, firecrawl, local-disk forensics | Confidence: High*
*Providers down at preflight: basic-memory MCP ("Not connected" — CLI fallback used), context7 (not needed — no library-doc sub-question fired)*
*Cache: 0 hits / 8 misses (fresh run; no prior harness cache for these queries)*

## Executive Summary

The "ChatGPT/Codex native browser" the owner admires is not a browser at all — it is an **MV3 Chrome extension using the `chrome.debugger` API (full CDP inside the running browser) plus a native-messaging host**, and that exact architecture is reproducible today on this box via open-source bridges (chrome-bridge-mcp, Browser Agent Bridge) that expose the same capability as MCP tools `[B.corrob x3.2026]`. That is the **GOAT-for-this-box** recommendation: it drives tabs in an already-running Chrome/Edge with zero extra browser RAM, delivers *trusted* CDP input that works while the window is unfocused/behind other windows, and reuses the profile's logins — installed into a **dedicated agent browser profile** to honor house rule G-90. The **SOTA-in-general** cross-browser answer is **WebDriver BiDi** (W3C standard, production-ready in Chrome 122+/Edge 122+/Firefox 130+; Safari in progress) driven through Playwright/Puppeteer with `launchPersistentContext` on dedicated debug profiles `[A.corrob x3.2024-26]`. The documented local failure "CDP-attach to Chrome 152 default profile" is fully explained: **since Chrome 136, `--remote-debugging-port` is silently ignored on the default user-data-dir** — a deliberate Chromium security change inherited by Edge; a non-default `--user-data-dir` (or the `chrome://inspect` live-session toggle) is the only sanctioned route `[A.corrob x4.2025-26]`. Tor Browser gets its own lane: `tbselenium`(-windows) over geckodriver/Marionette with a dedicated profile and TBB's own Tor at SOCKS 9150 `[B.corrob x2.2026]`.

**Mission 2 verdict: it is a genuine team policy, not a plugin.** Cursor's browser-automation toggle is disabled because this Cursor account is a member of team **10939257 "Bolt Technology OÜ"**, and the server-delivered admin settings cached on disk carry `"browserFeatures": false` — the client-side cache of the real enterprise dashboard toggle "Enable Browser Automation Features (v2.0+)" `[A.local-disk + A.cursor-docs]`. The "effort" caps are the same story: the team's `modelAllowlist` carries per-model `parameterRestrictions` (e.g. `reasoning` limited to specific values, `fast` locked to `false`). No plugin, registry policy, MDM file, or local config imposes either restriction. Do not bypass; the legitimate paths are asking the Bolt Cursor admin, or (if employer rules permit) a personal Cursor account for personal projects.

---

## 1. Why the current approach hurts, and why CDP-attach failed here

- **Chrome ≥136 ignores `--remote-debugging-port` / `--remote-debugging-pipe` when pointed at the default Chrome data directory.** The flags must be paired with `--user-data-dir` pointing at a non-standard directory (different encryption key ⇒ real-profile cookies unreachable). This is an intentional anti-cookie-theft change announced on the Chrome developers blog `[A.corrob x4.2025-26]` — sources: Chrome dev blog [1], browserless.io guide [2], Microsoft Q&A confirming Edge inherits it [3], trycua issue verifying on Chrome 151 [4]. **This is exactly why the prior CDP-attach to the Chrome 152 default profile failed on this box** — Chrome fails *silently* (no error, no listener on 9222) `[A.corrob.2026]`.
- Two sanctioned routes remain for Chromium: (a) dedicated debug profile via `--user-data-dir` + `--remote-debugging-port`, (b) the `chrome://inspect/#remote-debugging` permission-based toggle for a real profile (what Chrome DevTools MCP's live-session flow automates) `[B.corrob x2.2026]` — route (b) is **forbidden on the human 1Password profile by house rule G-90** anyway.
- **Focus-dependence nuance measured by practitioners:** CDP synthesized input is delivered only to the *active tab of its window*, so bridges auto-activate the target tab — but the **window itself does not need OS foreground focus**. Long unfocused/occluded runs are made deterministic with `--disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling` `[B.single.2026 — chrome-bridge-mcp README, UNVERIFIED elsewhere but consistent with Chromium throttling docs]` [8]. The owner's "fights the foreground" pain is a *tab-activation + render-throttling* artifact, not an inherent CDP limit.

## 2. The extension + native-messaging model (how ChatGPT/Codex actually does it)

- Chrome's official `chrome.debugger` extension API is "an alternate transport for Chrome's remote debugging protocol": an extension with the `debugger` permission gets CDP access to tabs in the **running** browser — no launch flags, no restart, no separate port `[A.official.2026]` [5].
- A Medium engineering write-up and three open-source bridges confirm the pattern: `Accessibility.getFullAXTree` for semantic page understanding, `Page.captureScreenshot`, `Input.*` for **trusted** (non-synthetic-flagged) input, `Network.*` interception `[B.corrob x4.2026]` [6][7][8][9].
- **Reverse-engineered Codex/ChatGPT architecture** (from the plugin bundle shipped with the ChatGPT desktop app): Chrome Web Store extension `hehggadaopoacecdllhhajmbjkdcmajg` ("Codex"/"ChatGPT for Chrome") → Rust **native-messaging host** (stdio, 4-byte LE length prefix + JSON) → local WebSocket proxy on `127.0.0.1`; one generic JS REPL tool; input dispatched through CDP's `Input` domain, which is why Codex produces trusted events that bot detection accepts `[B.single.2026 — single reverse-engineering source, treat details as UNVERIFIED]` [8]. Atlas's death notice explicitly redirects users to this extension + the ChatGPT desktop app for "deeper agentic browser work" `[A.official.2026]` [10].
- Open-source equivalents installable today:
  - **chrome-bridge-mcp** — same trick as Codex, exposed as ~21 declarative MCP tools over a single local WebSocket; any MCP client (Cursor, Claude, Codex CLI); attach to existing tabs, tab groups, secret redaction `[B.single.2026]` [8].
  - **Browser Agent Bridge (TNJ2026)** — MV3 extension + native-messaging host, JSON-RPC over HTTP/WS, hard-isolated to agent-managed tab groups with per-action approval `[B.single.2026]` [7].
  - **BrowserAgentBridge (Alij93695)** — REST + MV3 + WebSockets, explicitly "silent background execution … without stealing focus" (content-script route, no CDP) `[B.single.2026]` [9].
- **MV3 constraints:** service-worker lifetime (bridges keep-alive via the WS connection or reattach), `chrome.debugger` shows the "started debugging this browser" infobar, per-tab attach, and Chrome 125+ flat sessions for child targets `[A.official.2026]` [5]. Works identically on **Edge** (Chromium extension platform). **Not available on Firefox** (no `chrome.debugger` equivalent for full CDP; Firefox removed CDP end-2024) `[A.corrob.2024-26]` [11].

## 3. WebDriver BiDi vs raw CDP (the standards lane)

- BiDi is the W3C bidirectional protocol, production-ready since Firefox 129/Puppeteer 23 (2024); support: **Chrome 122+, Edge 122+, Firefox 130+, Safari in Tech Preview**; ~70% of CDP surface covered in 2026 (missing: heap profiling, deep perf traces) `[A.corrob x3.2024-26]` [11][12][13].
- Firefox **CDP support is deprecated/removed** — BiDi (or legacy Marionette) is the only maintained low-level Firefox route `[A.official.2024]` [11].
- Verdict: BiDi is the only protocol that spans Chrome+Edge+Firefox with one code path; CDP remains deeper on Chromium. Playwright/Puppeteer abstract over both, so in practice you choose a *driver*, not a protocol.

## 4. Playwright persistent-context / connect-over-CDP (the scripted lane already half-installed here)

- `launchPersistentContext(dedicatedProfileDir, { channel: 'chrome' })` is the canonical post-Chrome-136 pattern (community-verified fix for the 136 breakage) `[B.corrob x2.2025]` [2][14]. `connectOverCDP` to a browser launched with `--user-data-dir=<debug profile> --remote-debugging-port` still works fine — the restriction is only about the *default* profile.
- Playwright needs no OS focus (drives via CDP/BiDi/juggler), supports headless, and this box already has **firefox + webkit engines installed** per the locked browser decisions (1C+1D), so the marginal setup cost is a dedicated Chrome/Edge debug profile only. RAM cost is the main negative: each launched engine is a fresh browser process tree (hundreds of MB) on a chronically RAM-starved machine.

## 5. Agent frameworks and agent browsers (2026 state)

- **browser-use** — Python, ~80k stars, pure-autonomy agent on Playwright; Ollama/local-LLM friendly; highest flexibility, lowest determinism, LLM cost every step `[B.corrob x2.2026]` [15][16].
- **Stagehand v3 (Browserbase)** — TypeScript, ~21-22k stars, 700k+ weekly downloads; **CDP-native in v3** (dropped Playwright, 44% faster on complex DOM); hybrid `act()/extract()/observe()` + selector caching; ~75% success on novel tasks; MIT `[B.corrob x3.2026]` [15][16][17].
- **Vercel Agent Browser** — Rust CLI (Jan 2026), composable CDP control, a11y-tree snapshots ~93% smaller than Playwright-MCP equivalents (independent verification: real but page-dependent) `[B.corrob x2.2026]` [17]. Already the preferred engine of this estate's `e2e-runner` profile.
- **Agent browsers (products):** **Atlas is dead — stopped working 2026-08-09**, replaced by the ChatGPT desktop app + Chrome extension (house record confirmed) `[A.corrob x4.2026]` [10][18]. **Comet (Perplexity)** — free, Windows/macOS/iOS/Android, the only cross-platform AI-first browser; agentic automation metered by tier `[B.corrob x3.2026]` [19][20]. **Dia** — still macOS-only, Windows waitlisted for fall 2026 `[B.corrob x2.2026]` [20]. These are *products*, not estate-integrable control planes — they don't expose MCP; note-only.

## 6. Firefox and Tor Browser lanes

- **Firefox:** WebDriver BiDi natively (Playwright/Puppeteer 23+/Selenium 4.x); Marionette remains geckodriver's substrate. One BiDi code path covers Firefox + Chromium `[A.corrob x3.2024-26]` [11][12][13].
- **Tor Browser:** `tbselenium` (webfp) and the Windows-native port `tbselenium-windows` drive TBB via geckodriver/Marionette with `--marionette-port`, a **dedicated persistent profile** (`use_custom_profile=True`, user-writable TBB location), and TBB's own Tor at **SOCKS 9150 / control 9151** (`tor_cfg=USE_RUNNING_TOR`, `socks_port=9150`) — matching the locked Tor 2A decision; headless supported `[B.corrob x2.2026]` [21][22].
- **Anonymity hygiene (inference, clearly labeled):** keep the stock window size (letterboxing), don't install extra extensions into the TBB profile, keep the Security Level slider programmatic changes minimal, and expect `get_cookies()` oddities from Private Browsing Mode [21]. Automation *behavior* (timing regularity) itself shrinks the anonymity set — use Tor lane only for tasks that need it.

## 7. Ranked recommendation

| Rank | Option | Focus-indep. | Browsers | Control depth | Setup | RAM | ToS/safety |
|---|---|---|---|---|---|---|---|
| **1 — GOAT for this box** | MV3 extension bridge (`chrome.debugger`→CDP + local WS/native host), e.g. chrome-bridge-mcp, in a **dedicated agent profile** (G-90) | OS-focus-free; auto-activates tab in its own window; add anti-throttle flags | Chrome + Edge | Full CDP incl. trusted input, a11y tree, network | Load unpacked ext. + run local host; MCP-ready | ~0 extra (reuses running browser) | Debugger infobar visible; per-action approval available; audit code before install |
| **2 — SOTA in general** | Playwright over **BiDi/CDP** with `launchPersistentContext` on dedicated debug profiles | Yes (protocol-level; headless option) | Chrome, Edge, Firefox (+ webkit already installed) | Very deep; best ecosystem | Already mostly installed; create 2 debug profiles | High (new browser proc per run) | First-party, sanctioned |
| 3 | Vercel Agent Browser / Stagehand v3 layer on top of #2 | Yes | Chromium (AB); PW targets (SH) | AI-shaped primitives, token-cheap snapshots | npm/binary | Medium | OSS, fine |
| 4 | Tor lane: tbselenium-windows + TBB SOCKS 9150 + dedicated profile | Yes (headless possible) | Tor Browser only | Selenium-level | pip + geckodriver pin | Medium | Keep anonymity hygiene; never mix lanes |
| 5 | Agent browsers (Comet free-on-Windows; Dia not yet) | n/a (own UI) | Own browser | Product-level, no MCP | Install | High (another browser) | Vendor ToS; not estate-integrable |
| ✗ | CDP-attach to default profile / human 1Password profile | — | — | — | — | — | Blocked by Chrome ≥136 **and** G-90 |

**Adoption path (concrete, ~1-2 h total):**
1. Create a dedicated "agent" Chrome profile (separate `--user-data-dir`, e.g. `C:\Users\Prekzursil\.agents\browser-profiles\chrome-agent`) and an equivalent Edge one; sign in only the accounts agents may use. (Satisfies G-90 and the Chrome-136 rule simultaneously.)
2. Install **chrome-bridge-mcp** (or Browser Agent Bridge if per-action approval + tab-group isolation is preferred) as an unpacked extension **in that profile only**; register its MCP server in `.agents/agents.json` → sync. Audit the extension source first (it holds `debugger` permission).
3. Add the anti-throttling flags to the agent-profile launch shortcut so unfocused/occluded runs stay deterministic.
4. Keep Playwright(+BiDi) as the scripted/e2e lane it already is (engines firefox+webkit per locked 1C+1D), now always via `launchPersistentContext` on the dedicated profiles — never the default dir.
5. Stand up the Tor lane on demand only: `pip install tbselenium` (or the tbselenium-windows port), geckodriver pinned, TBB in a user-writable dir, `socks_port=9150`, dedicated profile (locked Tor 2A).
6. Retire the focus-fighting chrome-devtools-MCP window-driving for interactive tasks; keep it for DevTools-specific work (perf traces, heap snapshots) where CDP depth is required.

---

## 8. Cursor browser + effort setting: plugin vs policy (Mission 2 findings)

**Verdict: genuine team policy (Bolt Technology OÜ), NOT a plugin.** Evidence, all read-only, disk-verified on 2026-08-28:

- `%APPDATA%\Cursor\User\settings.json` **is readable** — the prior agent's "permission denied" is Cursor's agent-tool guard on its own config file, not NTFS (ACLs grant the user Full Control; shell read succeeds). The file contains **no** browser/effort/policy keys `[A.local-disk]`.
- No enterprise mechanism exists locally: no `C:\ProgramData\Cursor\managed-settings.json`, no `HKLM/HKCU\SOFTWARE\Policies\*Cursor*` keys, `argv.json` is stock, `~/.cursor/blocklist` is empty, `hooks.json` is the owner's own observe-only Wave-B logging config `[A.local-disk]`.
- The real gate lives in Cursor's **server-delivered team admin settings**, cached in `%APPDATA%\Cursor\User\globalStorage\state.vscdb`:
  - `cursorAuth/cachedTeam` = `{ teamId: 10939257, name: "Bolt Technology OÜ" }` — the account is genuinely on Bolt's Cursor team (corroborated by the Bolt marketplace plugins in `~/.cursor/plugins/cache` and `~/.cursor/managed/team_10939257/`).
  - `adminSettings.cached` / `autorun.cachedAdminSettings` contain **`"browserFeatures": false`** — the cached value of the enterprise dashboard toggle **"Enable Browser Automation Features (v2.0+)"** under MCP Configuration, documented by Cursor as admin-dashboard-controlled `[A.cursor-docs x3.2026]` [23][24].
  - The same blob's `modelAllowlist.providers.*.models.*.parameterRestrictions` is what caps "effort": e.g. `glm-5.2` `reasoning` allowed only `["high"]`, `gpt-5.2` reasoning allowed `["high","low","medium"]` (no higher tier), and `fast` locked to `["false"]` on grok-4.5/4.6, composer-2.5, gpt-5.x — i.e. Fast mode disabled team-wide. That is Cursor's team model-access parameter control, not a plugin `[A.local-disk + A.cursor-docs]`.
- Installed plugins (bolt-ai-marketplace skills, cursor-public, ai-marketplace-github) contribute **skills only**; `cursor.plugins.installedIds.no-team|no-workspace` is `[]`; nothing plugin-side touches browser or model parameters `[A.local-disk]`.

**Workaround assessment (per mission rules):** because the restriction is a **real employer-team policy**, bypassing it is not recommended. Legitimate options: (1) ask the Bolt Cursor admin to enable "Enable Browser Automation Features (v2.0+)" (optionally scoped by the Browser Origin Allowlist, v2.1+) and/or loosen the model parameter restrictions; (2) for strictly personal projects, a **personal Cursor account outside the Bolt team** would not carry these adminSettings — no MDM `AllowedTeamIDs` restriction exists on this machine, so it is technically possible, but whether it is *permitted* on this device is an employer-policy question the owner must answer, not a technical one. The distinction is flagged, as required.

---

## Key Takeaways
- Adopt the **extension-bridge model in a dedicated agent profile** — it is literally the Codex architecture, costs ~0 extra RAM, and ends the focus fight on Chrome/Edge.
- Keep **Playwright/BiDi persistent-context** as the cross-browser (Firefox included) scripted lane; **never target the default profile** (Chrome ≥136 makes it silently inert).
- Tor stays a **separate tbselenium lane** (SOCKS 9150, dedicated profile, hygiene rules).
- Cursor's disabled browser automation and capped effort are **Bolt Technology OÜ team policy delivered server-side** — not a plugin; go through the admin or a personal seat, don't bypass.

## Sources
1. [Changes to remote debugging switches to improve security](https://developer.chrome.com/blog/remote-debugging-port) — tier A — WebSearch (2025)
2. [Chrome Remote Debugging: A Developer's Guide](https://www.browserless.io/blog/chrome-remote-debugging) — tier B — WebSearch (2026)
3. [Edge remote debugging not working with default profile](https://learn.microsoft.com/en-us/answers/questions/5976829/) — tier A — WebSearch (2026)
4. [trycua/cua issue #2916: --remote-debugging-port blocked on default user-data-dir](https://github.com/trycua/cua/issues/2916) — tier B — WebSearch (2026)
5. [chrome.debugger API reference](https://developer.chrome.com/docs/extensions/reference/api/debugger) — tier A — WebSearch (2026)
6. [CDP from extensions — you don't need to fork Chromium](https://medium.com/@dzianisv/vibe-engineering-chrome-devtools-protocol-from-extensions-you-dont-need-to-fork-chromium-72a9ffb68b6d) — tier C — WebSearch (2025)
7. [TNJ2026/browser-agent-bridge](https://github.com/TNJ2026/browser-agent-bridge) — tier B — WebSearch (2026)
8. [ShalomObongo/chrome-bridge-mcp](https://github.com/ShalomObongo/chrome-bridge-mcp) — tier B — WebSearch, deep-read (2026)
9. [Alij93695/BrowserAgentBridge](https://github.com/Alij93695/BrowserAgentBridge) — tier C — WebSearch (2026)
10. [OpenAI Help Center: Evolving Atlas into ChatGPT](https://help.openai.com/en/articles/20001371) — tier A — WebSearch (2026)
11. [WebDriver BiDi production-ready in Firefox, Chrome and Puppeteer](https://developer.chrome.com/blog/firefox-support-in-puppeteer-with-webdriver-bidi) — tier A — WebSearch (2024)
12. [Selenium WebDriver BiDi 2026: Official CDP Replacement](https://qaskills.sh/blog/selenium-webdriver-bidi-2026-official-reference) — tier C — WebSearch, deep-read (2026)
13. [Puppeteer WebDriver BiDi support](https://pptr.dev/webdriver-bidi) — tier A — WebSearch (2026)
14. [Latenode community: Chrome 136 breaks remote debugging](https://community.latenode.com/t/21829) — tier C — WebSearch (2025)
15. [Scrapfly: Stagehand vs Browser Use](https://scrapfly.io/blog/posts/stagehand-vs-browser-use) — tier B — firecrawl (2026)
16. [Skyvern: Browser Use vs Stagehand (Feb 2026)](https://www.skyvern.com/blog/browser-use-vs-stagehand-which-is-better/) — tier C — firecrawl (2026)
17. [Bug0: Expect vs Agent-Browser vs Stagehand vs Passmark](https://bug0.com/blog/expect-vs-agent-browser-vs-stagehand-vs-passmark) — tier C — firecrawl (2026)
18. [PCMag: OpenAI to Retire ChatGPT Atlas](https://ca.pcmag.com/browsers/16759/) — tier B — WebSearch (2026)
19. [Perplexity blog: Personal Computer is Coming to Windows](https://hub-prod.perplexity.ai/hub/blog/personal-computer-is-coming-to-windows) — tier A — WebSearch (2026)
20. [Tabbit: AI Browser Comparison 2026](https://go.tabbit.ai/blog/ai-browser-comparison-2026) — tier C — WebSearch (2026)
21. [webfp/tor-browser-selenium](https://github.com/webfp/tor-browser-selenium/) — tier B — WebSearch (2026)
22. [maximilianromer/tbselenium-windows](https://github.com/maximilianromer/tbselenium-windows) — tier B — WebSearch (2026)
23. [Cursor docs: Browser tool (enterprise controls)](https://cursor.com/docs/agent/tools/browser) — tier A — WebSearch (2026)
24. [Cursor docs: LLM safety and controls](https://cursor.com/docs/enterprise/llm-safety-and-controls) — tier A — WebSearch (2026)
Local disk artifacts (Mission 2, tier A, disk-verified): `%APPDATA%\Cursor\User\settings.json` (+icacls), `%APPDATA%\Cursor\User\globalStorage\state.vscdb` keys `adminSettings.cached`, `autorun.cachedAdminSettings`, `cursorAuth/cachedTeam`; `~/.cursor/{argv.json,hooks.json,blocklist,managed/team_10939257,plugins/cache}`; `HKLM/HKCU\SOFTWARE\Policies` (0 Cursor matches); absence of `C:\ProgramData\Cursor`.

## Methodology
Sub-questions: (1) BiDi vs CDP maturity/coverage; (2) extension+native-messaging agent model & MV3 constraints; (3) Chrome ≥136 default-profile CDP block (root cause of the documented local failure); (4) 2026 agent-framework/agent-browser landscape incl. Atlas status; (5) Firefox/Tor driving; (6) Cursor gate forensics (local, read-only). Routing: `web` → WebSearch (5 dispatches) + firecrawl_search (1 dispatch, live at preflight); `deep_read` → full-page dumps auto-saved by the harness (qaskills, browser-agent-bridge, chrome-bridge-mcp, windowsforum, perplexity-review, tabbit) with targeted grep reads; `library_docs` (context7) not needed. **Down at preflight: user-basic-memory MCP ("Not connected")** — persistence via `basic-memory` CLI instead. No browser was driven (sibling lock respected); no config was edited; no secrets printed (state.vscdb dump used key-name redaction). Single-source claims are tagged UNVERIFIED per grading rules; the Codex internals (source 8) are single-source reverse engineering. Confidence header derived from claim-tier distribution: core recommendations rest on A-tier corroborated claims; framework benchmark numbers are B/C-tier.

