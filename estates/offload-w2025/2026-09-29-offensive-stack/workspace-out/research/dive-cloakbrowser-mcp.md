---
title: dive-cloakbrowser-mcp
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-cloakbrowser-mcp
---

# Deep-dive: cloakbrowser-mcp (browser-offense lane)

Date: 2026-09-29 · Verifier ran every check below on this VM (win32 10.0.26100 x64, Node v24.21.0).
Repo clone kept at `out/research/_cloakbrowser-mcp-repo` (depth 50).

## Verdict in one line

Real, actively maintained, professionally engineered Playwright-MCP→CloakBrowser bridge. **Windows-native feasibility PROVEN by execution on this VM** (full MCP stdio session driving a real page through the downloaded stealth Chromium). One claim correction: it is **not brand-new** — 4 months old, 24 npm versions, 14 release tags. One adoption caveat: the CloakBrowser binary's free tier is capped at **1 concurrent session** (paid key beyond that).

## Claim-by-claim

| Claim | Verdict | Evidence |
|---|---|---|
| "Brand-new (pushed 2026-09-29)" | **Partly false** | `gh api repos/swimmwatch/cloakbrowser-mcp`: `created_at 2026-05-21T23:17:32Z`; npm `time.created 2026-05-23`; 24 npm versions; tags v1.0.0→v1.14.1. `pushed_at 2026-09-29` is just today's dependabot docs-deps merge (commit 7e5ddd0). 4 months old, actively shipped. |
| Playwright-MCP-compatible wrapper over CloakBrowser | **True** | Architecture doc (`docs/architecture.md`): spawns upstream `@playwright/mcp` as child over stdio, forwards tool list/calls unchanged, appends 2 local tools. Verified live: `tools/list` → 27 tools = 25 upstream (`browser_navigate`, `browser_click`, …) + `cloakbrowser_binary_info`, `cloakbrowser_bridge_info`. |
| Documented Humanized Input Behavior | **True** | `docs/humanized-input-behavior.md` (+9 translations); real CLI flags `--humanize`, `--human-preset careful` seen in `npx cloakbrowser-mcp@latest --help` output; runtime patch `src/runtime/humanize-init-page.cjs`. |
| CI covers npm on Windows x64 across Node 22/24–26 | **True, and green** | `.github/workflows/ci.yml:18` `NODE_CHECK_VERSIONS '["22","24","25","26"]'`, `ci.yml:33` platforms incl. `windows-latest`; run 36332193980 (release/v1.14.1, 2026-09-27): `quality (windows-latest, node 22/24/25/26)` + `e2e (windows-latest, node 26)` all `success` (via `gh api .../runs/36332193980/jobs`). Caveat: CI npm e2e installs *Playwright* Chromium; the real CloakBrowser-binary path runs in CI's Linux Docker jobs. Windows-native binary coverage comes from my local run below. |
| Published to MCP Registry | **True** | `curl https://registry.modelcontextprotocol.io/v0.1/servers?search=cloakbrowser` → entry `io.github.swimmwatch/cloakbrowser-mcp`, npm/stdio package. Registry copy lists version 1.10.0 (lags npm 1.14.1). Repo `server.json` at 1.14.1. |
| Listed on awesome-mcp-servers | **True** | `raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md` line 569: `swimmwatch/cloakbrowser-mcp … 📇 🏠 🍎 🪟 🐧` (Windows/macOS/Linux tags). |

## Repo facts (gh api, 2026-09-29)

- 66 stars, 9 forks, 9 open issues (all bot/dependabot), TypeScript, MIT, not archived.
- Language TS; homepage https://swimmwatch.github.io/cloakbrowser-mcp/ (mkdocs, 10 languages).
- Sole human maintainer `swimmwatch`, but repo is heavily automated: dependabot groups, self-hosted "upstream monitor" bot auto-opens update issues (#156 Playwright MCP 0.0.83, #157 CloakBrowser 0.5.11), CodeQL/OpenSSF Scorecard/Zizmor/actionlint/hadolint/Trivy workflows — all recent runs `success`.
- npm `cloakbrowser-mcp`: 2,132 downloads last month; versions cadence ~weekly-biweekly (1.13.0 2026-09-05 → 1.14.0 2026-09-24 → 1.14.1 2026-09-27).

## Packaging / real install

- `package.json:26` bin `cloakbrowser-mcp` → `dist/cli.js`; deps: `@modelcontextprotocol/sdk ^1.30.0`, `@playwright/mcp ^0.0.82`, `cloakbrowser ^0.5.10`, `commander`, `mmdb-lib`, `pino`, `socks-proxy-agent`, `ws` — all pure npm/JS, no node-gyp, no native postinstall. Lockfile resolves `@playwright/mcp` 0.0.82 and `cloakbrowser` 0.5.10.
- `cloakbrowser` npm package (CloakHQ, 0.5.11): single dep `tar`, no `os`/`cpu` restriction, no install script — the stealth Chromium binary (~537 MB) is fetched on demand via its own CLI (`node_modules/cloakbrowser/dist/cli.js install`, same call the Dockerfile makes at `Dockerfile:80`) into `~/.cloakbrowser/`.
- Real install command: `npx -y cloakbrowser-mcp@latest` (also Docker `swimmwatch/cloakbrowser-mcp:latest` / ghcr, linux/amd64+arm64 only).

## Windows-native feasibility — EXECUTED HERE, PASSED

Commands run on this VM (Node v24.21.0):

1. `npx -y cloakbrowser-mcp@latest --version` → `1.14.1`
2. `npx -y cloakbrowser-mcp@latest doctor` → `Status: warning`; all checks `[ok]` (node, playwright-mcp-cli, playwright-runtime); only warning `cloakbrowser-binary: … (windows-x64, not installed); first browser action may download it`. Platform correctly detected as windows-x64.
3. Full MCP stdio session (probe script `out/research/mcp-stdio-probe.mjs`): `initialize` → serverInfo `io.github.swimmwatch/cloakbrowser-mcp` 1.14.1; `tools/list` → 27 tools; `tools/call browser_navigate {url: https://example.com/}` → SUCCESS in 21.4 s: "Page URL: https://example.com/ — Example Domain", snapshot written to `.playwright-mcp\page-….yml`. The CloakBrowser binary auto-downloaded and launched: cache now holds `~/.cloakbrowser/chromium-146.0.7680.177.5` (537 MB).

So: **native = yes**, no WSL/Docker needed, verified end-to-end.

## Issues / breakage

- Human issue tracker is thin (good sign). #133 (Docker `PLAYWRIGHT_MCP_HEADLESS=false` needs xvfb-run) — closed, Docker-only, irrelevant to Windows-native. #134 (CDP port 9222 like cloakserve) — closed as **implemented**: managed CDP shipped in v1.14.0 (`feat(cdp): integrate managed CDP release`, commit e51323c, `--cdp-enabled` CLI flag). #141 (upstream `@playwright/mcp` 0.0.80 pulled broken `playwright-core` 1.63.0-alpha that crashed the server on any `console.log`; reporter on Windows 10/Node 26) — closed; v1.14.1 moved to 0.0.82. **Residual risk:** lockfile still resolves `playwright-core 1.64.0-alpha-…` transitively — the bridge rides upstream's alpha track; pin discipline lives upstream, and a `CLOAK_PLAYWRIGHT_MCP_CONSOLE_FALLBACK` shim exists (Dockerfile:77, `src/runtime/consoleFallback.ts`).
- Upstream dependency health: CloakHQ/CloakBrowser — **31,790 stars, 2,643 forks, MIT, pushed 2026-09-27**, npm `cloakbrowser` ≈ **299,395 downloads/month**. Not a fake or dead dependency; independent ecosystem exists (LinkedIn discussion of the anti-detect impact, third-party `abencat-browser` fingerprint controller built on it with its own MCP, separate `cloakbrowser-human` npm package).

## Caveats for estate adoption

1. **Licensing of the binary**: banner during my run: "Running the free binary (v146). The latest binary (v152) is free too, with 1 concurrent session… For more than one concurrent session -> https://cloakbrowser.dev". Multi-session/parallel agent browsing needs a paid CloakBrowser key (`cloakbrowser login`). Single-session stealth browsing is free.
2. Binary auto-download (537 MB) on first browser action — plan disk/network; pin via `CLOAKBROWSER_CACHE_DIR`, `--binary-path`, or `CLOAK_PLAYWRIGHT_MCP_RELEASE_CHANNEL`.
3. Small bus-factor-1 maintainer on the wrapper itself; mitigated by CI automation and the fact that it's a thin bridge over two large upstreams.
4. Detection-evasion dual-use: this is a stealth browser. Use on this estate is for authorized research/QA; awesome-list neighbors (solvegate-mcp, vibatchium) show it sits in the anti-bot testing lane.

## Scored ToolFind

- name: cloakbrowser-mcp
- install: `npx -y cloakbrowser-mcp@latest` (verified on this VM; Node ^22.13 || >=24)
- windows: **native** (proven: doctor + full stdio navigate with auto-downloaded binary)
- value: **high** — closes a real capability gap vs vanilla Playwright MCP: MCP-driven stealth Chromium (upstream claims 30/30 bot-detection tests), humanized input (`--humanize`), GeoIP-aware proxy matching (`--geoip-proxy-match`), persistent profiles, extension loading, managed CDP — with unchanged upstream Playwright MCP tool surface (drop-in for any MCP client config).