---
title: dive-nodriver-proxy-mcp
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-nodriver-proxy-mcp
---

# Deep-dive: nodriver-proxy-mcp (browser-offense lane)

Date: 2026-09-29 · Verifier: subagent "Deep-dive: nodriver-proxy-mcp" · Everything below was read or run in this session unless marked otherwise.

## TL;DR

**Real, unusually well-engineered, works Windows-native — but abandoned 5.5 months ago with zero adoption.**
A solo Korean dev built a 5,073-line Python MCP in a 6-day sprint (2026-04-04 → 2026-04-10), shipped it to
PyPI (1.0.0/1.0.1), and never touched it again. All 39 advertised tools exist and I got the proxy, browser,
dual-session, and code-mode legs running on this Windows VM. No license file despite MIT badge. No issues,
no community, no independent mentions. `pip install` fails on Windows (resolver bug); `uv pip install` works.

## 1. Repository facts (gh api repos/BobongKu/nodriver-proxy-mcp)

| Field | Value |
|---|---|
| created_at | 2026-04-04T06:54:28Z |
| pushed_at | **2026-04-10T04:07:00Z** (dead 5.5 months as of 2026-09-29) |
| stargazers_count | 3 |
| forks_count | 1 (internet-dot/nodriver-proxy-mcp, pushed once 2026-04-07, no divergence) |
| open_issues_count | 0 — and `state=all` returns **zero issues ever filed**; no discussions |
| license | **null — no LICENSE file exists** (see §6) |
| language | Python (100%) |
| archived | false |
| subscribers (watchers) | 0 |

Commit history (9 commits, `gh api .../commits`): 2026-04-07 chore/docs burst ("rewrite all 39 tool
descriptions + README for 1.0 release"), then 2026-04-10 `t`, `d`, `fix bug`. Classic solo release sprint.

Owner `BobongKu`: 5 repos, all ≤3 stars (ghidra-agent-mcp, MongoDB-Injection-Lab, next-mdx-blog,
notepad-plus-plus fork). No organizational backing.

## 2. Claim-by-claim verification (ask: "39 MCP tools fusing nodriver… mitmproxy… CDP Fetch… detect_auth_pattern… dual-session IDOR… code-mode with NdpSDK")

Source read from clone at `out/research/ndpm-src` (HEAD = 2026-04-10 "fix bug").

| Claim | Verdict | Evidence |
|---|---|---|
| 39 MCP tools | **TRUE** | `grep -c '@mcp.tool'` across proxy/tools.py, browser/tools.py, codemode/tools.py = **39**; names match README table exactly (18 proxy + 20 browser + 1 codemode). `main.py:59-63` registers exactly that split. |
| Real mitmproxy: record/replay/fuzz/rules/session vars | **TRUE** | `_mitm_addon.py` is a genuine mitmproxy addon (request/response hooks → SQLite TrafficDB via `recorder.py`, 5s-cached rule engine: inject_header/replace_body/block → `http.Response.make(403,…)` at `_mitm_addon.py:154-160`). replay_flow with regex + `{{var}}` substitution, fuzzer with baseline anomaly detection, session variables — all present in `proxy/tools.py`/`fuzzer.py`. Runtime-proven in §4. |
| CDP Fetch interception | **TRUE (code-read)** | `browser/daemon.py:136-219`: `cdp.fetch.enable(RequestPattern(url_pattern="*", request_stage="Request"))`, RequestPaused handler, request-stage block/modify_url, response-stage body replace via `continueRequest(interceptResponse=True)` → `fulfillRequest`. Not runtime-tested this session. |
| detect_auth_pattern (JWT/Bearer/API-key/cookie/CSRF/OAuth2) | **TRUE (code-read)** | `proxy/tools.py:608-668+`: scans 100 most recent flows' headers; JWT = Bearer token with 2 dots, API-key = x-api-key/api-key/apikey/x-auth-token header names, Basic/OAuth2-endpoint/CSRF heuristics. It's header-pattern matching, not crypto validation — fine for triage. |
| Dual-session IDOR flows | **TRUE (runtime)** | `session_manager.py:155-265`: named sessions, each a separate BrowserDaemon process + independent Chrome. I ran `victim` + `attacker` sessions simultaneously — both navigated to different domains, both listed, both closed. See §4.3. |
| Code-mode sandbox + NdpSDK | **TRUE (runtime), "sandbox" overstated** | `codemode/tools.py`: subprocess per script, HITL gate `approved=true` (line 351), 256MB Job Object + KILL_ON_JOB_CLOSE on win32, RLIMIT_CPU 60s / RLIMIT_AS 256MB on Unix, 32KB output cap, wall-clock timeout. `sdk.py` (1,023 lines) exposes the tool surface as async methods. **It is a resource-limit sandbox, not a security boundary** — arbitrary Python with full system/network access once approved; `dependencies` param runs `uv pip install --system` of arbitrary packages (line 239). |
| "Bypasses Cloudflare/DataDome automatically", "navigates like a human" | **NOT VERIFIED** | nodriver (no webdriver/selenium fingerprints) is the right foundation, but I did not test against a bot-protected site this session. Treat as marketing. |

## 3. Packaging, install, and Windows-native feasibility

- **On PyPI**: https://pypi.org/pypi/nodriver-proxy-mcp/ — 1.0.0 (2026-04-07) and 1.0.1 (2026-04-10). `requires-python >=3.10,<3.14`.
- Packaging: `pyproject.toml` (hatchling), console script `nodriver-proxy-mcp = nodriver_proxy_mcp.main:main`. No Dockerfile, no release assets beyond the sdist/wheel. `uv.lock` present (dev pins: mitmproxy 11.0.2, nodriver 0.48.1, zstandard 0.23.0).
- Dependencies: `mcp[cli]>=1.0.0`, pydantic, httpx, `mitmproxy>=10.0.0`, `nodriver>=0.38.0`, beautifulsoup4, lxml, jsonpath-ng, curl-cffi. All ship Windows wheels (mitmproxy via mitmproxy-rs/mitmproxy-windows wheels; lxml/curl-cffi standard).

### The install test (the decisive check, run on this VM)

VM: Windows Server 2025 (10.0.26100, AMD64). Pythons: 3.14.6 (default — **too new** for `requires-python <3.14`) and **3.12.10** at `C:\Python312`. uv 0.12.20.

1. `C:/Python312/python.exe -m venv out/research/ndpm-venv`
2. `…venv/Scripts/python.exe -m pip install nodriver-proxy-mcp` → **FAILED**. pip resolves
   `mitmproxy>=10.0.0` 12.2.2 → backtracks through 11.x → 10.x; the deep backtrack requires
   `zstandard<0.22`, which has **no cp312 win_amd64 wheel**, so pip builds the 0.21.0 sdist and dies:
   `distutils.compilers.errors.PlatformError: Microsoft Visual C++ 14.0 or greater is required`.
   Full log: `out/research/pip-install.log`. (zstandard 0.23.0+ does have cp312 win wheels — pip's
   backtracking is the failure, not the ecosystem.)
3. `uv pip install --python …venv/Scripts/python.exe nodriver-proxy-mcp` → **SUCCEEDED**: mitmproxy
   11.1.3, mitmproxy-rs 0.11.5, nodriver 0.50.3, mcp 1.30.0, curl-cffi 0.16.3, zstandard 0.23.0.
   Both `mitmdump.exe` and `nodriver-proxy-mcp.exe` appear in `Scripts/`.

**Real install command: `uv pip install nodriver-proxy-mcp` (Python 3.10–3.13).** Plain pip works only if
the resolver happens to avoid the zstandard trap (e.g. older mitmproxy already pinned). The repo's own
README troubleshooting admits it: "`uvx` doesn't work → Don't use `uvx`. Clone the repo and use
`uv run --directory` instead."

The codebase is deliberately cross-platform — explicit win32 branches everywhere I looked:
`controller.py:51` (mitmdump.exe), `:85-86` (CREATE_NEW_PROCESS_GROUP), `:179-198` (netstat/taskkill
orphan-port cleanup), `:253-266` (kernel32.OpenProcess liveness); `codemode/tools.py:18-101` (Windows Job
Object with 256MB + KILL_ON_JOB_CLOSE), `:110-121` (taskkill /T); `daemon.py:113-132` (OpenProcess
parent-watchdog); `session_manager.py:238-241`. Someone actually ran this on Windows.

## 4. Runtime smoke tests on Windows-native (all run this session)

### 4.1 Import / tool registration
`python -c "import nodriver_proxy_mcp.main"` → `Registered tools: Proxy(18) + Browser(20) + Code-mode(1) = 39`, FastMCP name correct.

### 4.2 Proxy leg (`out/research/smoke_proxy.py`)
`ProxyManager.start(port=8082)` → `{'status':'started','pid':44048}` (mitmdump.exe launched with the addon);
`curl -x http://127.0.0.1:8082 -k` to http://example.com and **https://example.com both → 200 through the
MITM**; SQLite TrafficDB shows the flows (`GET 200 https://example.com/` …); `stop()` clean. The
orphan-port cleanup even fired on the second run ("Killing orphan process 44844 on port 8082").

### 4.3 Browser leg (`out/research/smoke_browser.py` + dual-session one-liner)
`session_manager.open(headless=True)` → daemon subprocess + nodriver 0.50.3 headless Chrome;
`go(https://example.com)` → title "Example Domain"; `get_text(title)` works; clean close.
Dual session: `victim` (cdp 26792) + `attacker` (cdp 31083) simultaneously, both navigated, both closed.
Cosmetic bugs observed: `go()` result often has empty `final_url`/`current_url` (race), first
`get_text('h1')` returned empty text — navigation itself is fine.

### 4.4 Code-mode (`out/research/smoke_codemode.py`)
`run_in_codemode("print python/platform")` → `python: 3.12.10 | platform: Windows-2025Server-10.0.26100`,
output captured, temp script removed, Job Object path exercised without error.

## 5. Breakage & community signal

- Issues: **zero ever** (open+closed). No discussions tab activity. Nothing to mine for breakage — also
  means no evidence anyone but the author ever ran it.
- Independent mentions (Exa REST search, 10 results): PyPI page, piwheels mirror, auto-indexed
  glama.ai MCP directory entry, the repo, the one fork. **No blog posts, no reviews, no social, no
  third-party usage.** Firecrawl not needed — nothing JS-rendered to check.
- Alternatives surfaced by the same search: `andresolbach/nodriver-mcp-server` (PyPI `nodriver-mcp`
  v2.5.0, released **2026-09-25**, actively maintained, 5 stars) — but it is browser-only; it has no
  mitmproxy fusion, no traffic replay/fuzz, no code-mode sandbox. The browser+proxy+code-mode fusion in
  this repo is genuinely uncommon; nothing found that replicates the full stack.

## 6. Red flags / caveats

1. **No LICENSE file.** README badge links `LICENSE`, README footer says "MIT", pyproject declares
   `license={text="MIT"}` — but `gh api` reports `license: null` and the clone has no LICENSE file.
   Intent to license MIT is expressed three ways; the actual file is missing.
2. **Version skew**: repo pyproject says `1.0.0` at HEAD, PyPI hosts `1.0.1` (uploaded 10 min after the
   last commit) — the bump was never committed.
3. `.mcp.json` contains the author's personal absolute path (`C:/Users/jhbgj/Desktop/...`) — dev config
   committed to the repo.
4. Anti-bot claims ("Bypasses Cloudflare, DataDome automatically") unverified and phrased as certainty.
5. Dead upstream: any breakage (Chrome CDP changes, mitmproxy major bumps, nodriver API drift — note
   pyproject floor `nodriver>=0.38` vs 0.50.3 installed today) is the owner's problem alone.
6. Code-mode `dependencies` param = arbitrary package install on the host (gated only by the HITL
   `approved` flag). On a single-owner private estate that's acceptable; do not expose the MCP to
   multi-tenant use.

## 7. Verdict for the estate

Not fake — the opposite: a competent, genuinely Windows-aware implementation of a capability stack the
browser-offense lane wants (anti-bot browser + MITM record/replay/fuzz + CDP interception + agent
code sandbox + dual-session IDOR). It ran end-to-end on this VM with `uv`. But it is a 6-day,
3-star, license-file-missing, 5.5-months-dead artifact with zero community: installing it means
adopting an unmaintained codebase. Value: **medium** — real capability, verified working Windows-native,
but you are the maintainer now; pin it and vendor it if adopted.

**Scorecard**: claim accuracy high (39/39 tools real, all named subsystems present) · activity dead ·
community none · Windows-native YES (verified) · install `uv pip install nodriver-proxy-mcp` on Python
3.10–3.13 (plain pip fails on Win py3.12 today).