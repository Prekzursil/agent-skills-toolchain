# Deep-dive: js-reverse-mcp (browser-offense lane)

Date: 2026-09-29 · Verifier: lead-verifier subagent · Repo: https://github.com/zhizhuodemao/js-reverse-mcp

## Verdict

REAL, ACTIVE, and VERIFIED WORKING NATIVELY ON THIS WINDOWS VM. Install is `npx js-reverse-mcp` (npm package `js-reverse-mcp@4.0.5`). Every capability in the claim string was confirmed either in code or by live execution. Value: **high** — it is the only tool in this estate that gives an AI agent a real Chrome DevTools debugging loop (breakpoints, call-frame evaluation, XHR breakpoints, Set-Cookie provenance tracing) over a headed, persistent-login browser with protocol-level stealth.

## 1. Repo metadata (from `gh api repos/zhizhuodemao/js-reverse-mcp`)

| Field | Value |
|---|---|
| stars | **2853** (claim exact) |
| forks | 371 |
| open_issues | 11 (6 PRs + 5 issues) |
| created / pushed | 2025-11-29 / **2026-09-03** (v4.0.5 release same day) |
| license / language | Apache-2.0 / TypeScript |
| topics | anti-detection, cdp, chrome-devtools, mcp, patchright, reverse-engineering, websocket |

Release cadence is dense and organic: 39 npm versions, tags from v1.x (2026-05) through v4.0.5 (2026-09-03); last 5 commits 2026-08-25→09-03 (`git log` on shallow clone).

## 2. Real install command

`npx js-reverse-mcp` — it is a published npm package, not a git-only install.

- `package.json:2-24`: name `js-reverse-mcp`, version 4.0.5, `bin: js-reverse-mcp -> build/src/index.js`, files `build/src`.
- `npm view js-reverse-mcp`: latest 4.0.5, 39 versions, modified 2026-09-03. Release assets on GitHub are empty — npm is the channel.
- Local dev install (README_en.md:112-119): `git clone … && npm install && npm run build`, then `node build/src/index.js`.
- Requires Node ≥20.19 (engines, package.json:96-98) and **system Google Chrome stable** (README_en.md:66-69). This VM: Node v24.21.0 ✓, Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe` ✓.
- No Dockerfile, no Python. `--cloak` mode pulls `cloakbrowser` (optionalDependency, ~200MB binary download on first use; pre-download via `npx cloakbrowser install`, README_en.md:304-312).

## 3. Dependencies & Windows support

- `@modelcontextprotocol/sdk` 1.29.0 (pinned), `zod`, `yargs`, `debug`, `core-js`, `prettier` (runtime dep — used to beautify saved scripts), `devtools-protocol`.
- `@zhizhuodemao/patchright` 1.61.1-mcp.2 — the author's **own Patchright fork** (Playwright fork). Exists on npm (published ~2026-08, 4.9MB), source at https://github.com/zhizhuodemao/patchright-mcp (created 2026-08-20, pushed 2026-08-20, 5 stars, "Patchright fork for js-reverse-mcp with protocol-level observable-side-effect fixes"). Playwright-lineage → Windows fully supported.
- `cloakbrowser` ^0.4.10 optional — CloakHQ stealth Chromium (MIT wrapper, source-patched binary). Actively published (0.5.11 five days before this dive).

## 4. Claim-by-claim verification

| Claim | Evidence |
|---|---|
| 2853 stars | `gh api` — exact match |
| Headed Chrome breakpoints | `set_breakpoint_on_text`, `break_on_xhr`, `get_paused_info`, `step`, `pause_or_resume` — all present in live `tools/list` (24 tools, matching README_en.md:165) |
| Evaluate in call frames | `evaluateOnCallFrame` at `src/tools/debugger.ts:79`; `evaluate_script` accepts paused-frame context + `localFilePath` local input |
| Script search/save/beautify | `search_in_sources`, `save_script_source` (format=true default, prettier at `src/tools/debugger.ts:17`, auto-format messaging at `src/tools/debugger.ts:375,441`) |
| Network + WebSocket, XHR breakpoints, Set-Cookie | `list_network_requests` has a dedicated `cookieName` mode that traces which response created/rotated/deleted a cookie incl. HttpOnly (`src/tools/network.ts:65,128`); `break_on_xhr`; `get_websocket_messages`; `get_request_initiator` |
| Browser-state replay | `clear_site_data` + `--isolated` (README_en.md:267-275 cookie/risk-control replay flow) |
| Persistent login across sessions | `src/browser.ts:44-49` — default persistent user-data-dir `~/.cache/chrome-devtools-mcp/chrome-profile` |
| Dedicated Patchright fork | package.json:82 + fork repo above; README_en.md:54-64 states protocol-level changes, no page-level JS injection, and explicitly does NOT claim absolute undetectability |
| `--cloak` CloakBrowser | `src/cloak.ts`, `--cloak` CLI flag (verified in `--help` output), docs/cloak.en.md, physically isolated profile dir (`src/browser.ts:50-55`) |

## 5. Live Windows-native verification (this VM, this session)

1. `npm install` in the clone — succeeded (two benign postinstall warnings for core-js/unrs-resolver, blocked by this box's allowScripts policy, not needed).
2. `npm test` (custom runner `build/scripts/run-tests.js` over the compiled suite): **106 passed, 8 failed**. All 8 failures are Windows test-environment semantics, not core-logic bugs:
   - 5× `EPERM symlink` — Windows forbids `fs.symlink` without Developer Mode/admin, so the *tests* cannot construct their symlink-escape fixtures;
   - 1× `fs.realpath` returns 8.3 short path `C:\Users\PREKZU~1\...` vs the test's long-path expectation — the product still ALLOWED the read/write, only the string assertion differed;
   - 2× mode assertion `438 !== 384` (0o666 vs 0o600) — `chmod 0600` hardening is a no-op on Windows; the log-file/seed-file permission guarantee does not apply on this OS.
   - Everything else — debugger context, breakpoints, network capture, WebSocket collector, formatters, tool routing — passes on Windows.
   - Upstream CI is **ubuntu-latest only** (`.github/workflows/ci.yml:9`, `publish.yml:10`), so these Windows failures are invisible to the maintainer.
3. **Full MCP end-to-end**: spawned `build/src/index.js --isolated`, performed stdio `initialize` + `tools/list` → server `js-reverse` v4.0.5, **exactly 24 tools**; called `new_page {url: https://example.com}` → launched a real headed Chrome through the Patchright fork and returned the page listing in **2659 ms**. Exit path clean. This is the definitive Windows-native PASS for the default (non-cloak) mode.
4. `node build/src/index.js --help` — all documented flags present, exit 0.

Not run: `--cloak` end-to-end on Windows (would download a ~200MB binary; not exercised in this dive — reported as not run). `--browserUrl` attach path not exercised either; it is documented for CDP endpoints and its docs even cover AdsPower/BitBrowser fingerprint browsers.

## 6. Provenance (important, legitimate)

Source files carry `Copyright 2025 Google LLC, Apache-2.0` headers (e.g. `src/tools/script.ts:3`, `src/tools/network.ts:3`, `src/browser.ts:2-5`). This project is a reworked fork of **Google's chrome-devtools-mcp**, and `src/browser.ts:42-43` says so explicitly ("the default path is preserved across the chrome-devtools-mcp → js-reverse-mcp rename"). The value-add over upstream: the whole JS-reversing tool surface (script search/save/beautify, breakpoint/XHR-breakpoint tools, Set-Cookie tracing, WebSocket grouping, site-data replay), plus the stealth layer. Apache-2.0 permits this; attribution retained. The first dependabot PRs (#1-#3, 2025-11-29) still target chrome-devtools-frontend deps.

## 7. Issues / breakage read

- 11 open, 30+ closed; issue flow is organic Chinese/English user traffic, actively triaged.
- **Issue #36 ("[Windows] owner watchdog os.kill(pid,0)...") is misfiled** — its body is about `ai-browser-mcp`, a Python/uvx package (`browser_mcp/process_lifecycle.py`), not this TypeScript repo. It is NOT evidence of a Windows bug here.
- #34 (5MB local-file limit) closed by raising to 10 MiB in v4.0.5 (commit fd8461c).
- #27: CloakBrowser free binary uses a "delayed free-release model" — the free build **goes stale within weeks** as detection evolves; maintainer says price is unattractive and plans to adapt other fingerprint browsers. So `--cloak` is functional but its binary freshness is a moving third-party dependency.
- Historic handshake/startup failures (#12, #24) are closed with fixes.

## 8. Independent activity signal

- npm downloads (api.npmjs.org): **1,017 last week, 4,635 last month, 45,079 YTD 2026** — sustained real usage, consistent with genuine (not purchased) stars; 371 forks ≈ 13% fork ratio, typical of used tooling.
- Listed on third-party MCP directories: glama.ai, mcphello.com, mcpserver.space, npmx.dev (exa search, results saved to out/research/exa1.json, exa2.json).
- A derivative project in the same niche exists — NoOne-hub/JSReverser-MCP (1,022 stars, created 2026-02-17) — i.e., the category has competition/clones, which corroborates demand.
- Sponsorships (IPWO proxies, Infistar model API) in README — the repo monetizes attention but the code itself is unaffected.

## 9. Caveats (honest)

1. Windows is not in upstream CI; the 8 failures above will persist; `--allowedRoots` symlink-escape defense and 0600 log/seed hardening are untested/no-op on Windows. On Windows the realistic local-file boundary is therefore weaker than on Linux — run with `--allowedRoots` anyway, and treat its guarantees as soft here.
2. Anti-detection efficacy is unverifiable by static reading (by design — docs/cloak and the fork describe only boundaries). The fork repo is a 1-maintainer, 5-star project; if the author stops, protocol-level fixes go stale against detector evolution.
3. CloakBrowser free-binary staleness (issue #27).
4. Default profile path is shared with chrome-devtools-mcp — if you also run Google's chrome-devtools-mcp, they will fight over `~/.cache/chrome-devtools-mcp/chrome-profile`.
5. Primary docs are Chinese; README_en.md is complete and current (both 426 lines).

## 10. Scored result

- **value: high** — closes a real capability gap: agent-driven JS reverse engineering with live breakpoints (incl. XHR breakpoints and paused-frame evaluation), Set-Cookie/HttpOnly provenance tracing, and persistent-login headed browsing. Nothing else in the estate does this; the closest existing pieces (playwright skills, burp-mcp) cover adjacent but different ground.
- **windows: native** — proven by live handshake + headed Chrome launch on this VM; minor caveats above.
- **install: `npx js-reverse-mcp`** (or `claude mcp add js-reverse npx js-reverse-mcp`); `--cloak` variant needs `npx cloakbrowser install` first.
