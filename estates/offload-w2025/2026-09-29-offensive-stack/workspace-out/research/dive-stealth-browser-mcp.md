---
title: dive-stealth-browser-mcp
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-stealth-browser-mcp
---

# Deep-dive: stealth-browser-mcp (browser-offense lane)

Date: 2026-09-29. Verifier: subagent on the estate VM (win32, Git Bash). All commands below were run in this session unless marked otherwise.

## 1. Repo metadata (verified via `gh api`)

Command: `gh api repos/vibheksoni/stealth-browser-mcp`

| field | value |
|---|---|
| stars | **2162** (claim said 2161 — matches, drifted by 1) |
| forks / watchers | 296 / 2162 |
| open_issues_count | **1** (only #25, a CI benchmark proposal) |
| pushed_at | **2026-09-25** (4 days before this dive) — actively maintained |
| created_at | 2025-08-09 |
| license / language | MIT / Python (100%) |
| default branch | master |
| releases | 1: v0.2.5 "Protocol Fix, Edge Support, Repo Cleanup" (2026-02-10) |
| archived | no |

Not fake, not dead. External contributors' PRs merged recently: #29 (brandonp2412, dynamic hook cleanup), #31 (JosueM1109, page-state cookies), #33 (1letme, shared-pid-file fix) — community maintenance, not a one-man astroturf.

## 2. Claim audit — every element checked against source

Clone: `out/research/_sbm` (git clone, master @ e2ffc98, 2026-09-25).

| Claim | Verdict | Evidence |
|---|---|---|
| 2161 stars | TRUE (2162 now) | `gh api` above |
| 98 tools | TRUE, verified 3 ways | (a) `grep -c "@section_tool(" src/server.py` → 98; (b) runtime `src/server.py --list-sections` → 8+13+9+9+10+14+10+3+5+7+10 = 98; (c) **live MCP stdio `tools/list` returned exactly 98 tools** (probe below) |
| 21-tool minimal core | TRUE | `--minimal` (src/server.py:2953-2958) disables 9 sections = 77 tools, leaving browser-management (8) + element-interaction (13) = 21 |
| network inspection | TRUE | `network-debugging` section (10 tools: list/search/get_request_details/get_response_details/get_response_content); src/network_interceptor.py; SKILL.md:24 |
| dynamic Python request/response hooks | TRUE | src/dynamic_hook_system.py: AI-supplied `function_code` compiled with `exec()` (line 84), applied to CDP Fetch paused requests (`_on_request_paused`, line 245). Note: by design this executes AI-authored Python inside the server process — acceptable for a trusted single-owner local MCP; the tool's whole point |
| pixel-accurate element cloning | SUBSTANTIVE (machinery real; "pixel-perfect" is marketing) | src/cdp_element_cloner.py uses CDP `CSS.getComputedStyleForNode` + `CSS.getMatchedStylesForNode` (lines 8-11, 64-65); src/js/extract_{styles,assets,animations,events,structure}.js; 4 cloner modules |
| human-like typing | TRUE | src/dom_handler.py:338-417 — per-keystroke `delay_ms` (default 50ms) with asyncio sleeps |
| pre-document CDP scripts | TRUE | tool `add_script_to_evaluate_on_new_document` at src/server.py:2366 wrapping `uc.cdp.page.add_script_to_evaluate_on_new_document` (server.py:2391) |
| ships an agent skill | TRUE | skills/stealth-browser-mcp/SKILL.md — proper frontmatter, tool-selection guidance, pre-document script section, lifecycle/security rules. Originated from community issue #20 |
| explicit Windows install instructions | TRUE | README.md:149-150 (`venv\Scripts\activate`), 162-166 (`claude mcp add-json` PowerShell form), 183-195 (`%APPDATA%\Claude\claude_desktop_config.json`); plus run_server.bat Windows launcher in repo root |
| Chrome/Edge auto-discovery | TRUE, verified live | src/platform_utils.py:162-173 hardcodes Windows paths (Chrome: Program Files / x86 / `%LOCALAPPDATA%`; Edge same). On THIS VM, `validate_browser_environment_tool` returned `C:\Program Files\Google\Chrome\Application\chrome.exe`, browser_type "Google Chrome", issues `[]` |
| nodriver+CDP+FastMCP stack | TRUE | pyproject deps `nodriver==0.47.0`, `fastmcp==2.11.2`; server.py:17-18 imports |
| anti-bot bypass (Cloudflare/CreepJS/Sannysoft) | SELF-REPORTED, not independently verified | STEALTH_TESTS.md (dated 2026-02-10, Windows 10 + Chrome 144) claims Cloudflare PASS, CreepJS 0% stealth, Sannysoft 20/20. Author-authored evidence; I did not test against live anti-bot targets in this dive |

## 3. Real install command

**NOT a PyPI package.** pyproject.toml has no `[build-system]` and no `[project.scripts]`; not published to PyPI; no uvx one-liner. The repo is run from source:

```bat
git clone https://github.com/vibheksoni/stealth-browser-mcp.git
cd stealth-browser-mcp
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
:: then register stdio MCP: venv\Scripts\python.exe src\server.py
```
(README.md:144-155; Windows MCP JSON at README.md:162-176.)

Alternates: `fastmcp install claude-code src/server.py --with-requirements requirements.txt` (README.md:219-222, marked experimental); Dockerfile (Linux/Chrome, rootless pattern) and smithery.yaml also shipped.

Dependency note: requirements.txt pins `py2js @ git+https://github.com/am230/py2js.git@31a83c7...` — a git-locked dependency, so **git must be present at install time**. It built and installed fine here.

## 4. Windows-native feasibility — TESTED on this VM

### Failure found: Python 3.14 (default C:\Python314)
`pip install -r requirements.txt` in a 3.14 venv FAILED: `pydantic==2.11.7` → pydantic-core 2.33.2 has **no cp314 Windows wheels** (verified via `https://pypi.org/pypi/pydantic-core/2.33.2/json`: 99 files, none cp314+win); pip fell back to maturin/Rust source build, which died on an MSVC linker error (`could not compile rustversion ... maturin failed`). So the documented pinned install **breaks on Python 3.14** until pins are relaxed.

### Success: Python 3.12 (also on this VM, C:\Python312)
- `C:\Python312\python.exe -m venv venv312` + `pip install -r requirements.txt` → clean install; imports OK (fastmcp 2.11.2, pydantic 2.11.7, nodriver imported).
- `src/server.py --list-sections` → boots, lists 11 sections, 98 tools total.
- **Full MCP stdio handshake probe** (out/research/_sbm/stdio_probe.py): initialize OK (`Browser Automation MCP` v1.30.0), `tools/list` → **TOOL COUNT: 98**, `validate_browser_environment_tool` → Chrome found, zero issues.
- **Full browser lifecycle on native Windows, non-headless** (out/research/_sbm/spawn_probe.py):
  - `spawn_browser` → instance ready, temp profile under `%LOCALAPPDATA%\Temp`
  - `navigate https://example.com` → `{"url":"https://example.com/","title":"Example Domain","success":true}`
  - `close_instance` → `true`

**Conclusion: runs natively on this Windows VM — real Chrome, no WSL, no Docker — provided Python ≤ 3.13 is used for the venv.** (Repo claims `requires-python >=3.10`; the exact pins predate 3.14 wheel availability.)

## 5. Issues / breakage history

Closed-issue cadence shows genuine bug fixing: #8 debug logging broke JSON-RPC stdout (fixed), #12 proxy option accepted but never applied (fixed), #22 WebGL spoof silently no-op without Page.enable (fixed), #14/#9 tool-list timeouts (addressed), #32 startup orphan-recovery killing other clients' browsers (fixed 2026-09-20, PR #33). Windows-mentioning issues: only 2 (#3 closed "Claude cant see launched chrome", 2025-08; #25 open proposal) — no pattern of Windows breakage. Old Mac-only issue #7 (Cherry Studio) closed. README troubleshooting (lines 566-591) covers browser-not-found and Linux/Docker crashes; nothing Windows-specific outstanding.

## 6. Independent mentions (exa search, this session)

- MCPpedia review page: "Stealth Browser Mcp — Score: 73/100 (B)" — https://mcppedia.org/s/stealth-browser-mcp
- Glama MCP directory: https://glama.ai/mcp/servers/vibheksoni/stealth-browser-mcp
- pickmcp.com listing, dev.co listing
- Live alternative ecosystem (confirms a real category): andresolbach/nodriver-mcp-server, DevinoSolutions/stealth-chrome-devtools-mcp, mcp-stealth-chrome (PyPI), playwright-stealth-mcp-server (npm), plus "Nodriver vs Playwright: Which Is Stealthier in 2026?" (bytetunnels.com). No Reddit/HN threads surfaced for this specific repo.
- Repo's own COMPARISON.md positions it vs playwright-mcp / stagehand / browser-use (self-authored, treat as marketing).

## 7. Caveats

- Anti-bot bypass performance is self-reported (STEALTH_TESTS.md); not independently verified here.
- Monetization present: NodeMaven sponsor banners (latest commit e2ffc98 is sponsor-link churn) — cosmetic, no code impact.
- Dynamic hooks `exec()` AI-written Python in-process — trust boundary is the MCP client; keep HTTP transport off localhost or set `STEALTH_BROWSER_MCP_AUTH_TOKEN` (SKILL.md:45-46).
- Requires a real Chrome/Chromium/Edge install (present on this VM).

## 8. Artifacts left in place

- out/research/_sbm — clone + venv312 (working install) + stdio_probe.py + spawn_probe.py (repro scripts)
- The failed 3.14 venv (out/research/_sbm/venv) remains as evidence of the pin failure