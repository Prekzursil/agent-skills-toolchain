---
title: dive-mitmproxy-mcp--snapspecter-
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-mitmproxy-mcp-snapspecter
---

# Deep-dive: mitmproxy-mcp (snapspecter) — browser-offense lane

Date: 2026-09-29. Verifier session: dynamic-workflow subagent "Deep-dive: mitmproxy-mcp (snapspecter)".
Candidate as given by the ask: `https://github.com/snapspecter/mitmproxy-mcp` — "123-star MCP layer over mitmproxy … agent-facing flow inspection, session variables (CSRF-token capture+replay), interception rules, stealth replay via curl-cffi TLS impersonation, fuzzing, and OpenAPI reconstruction from captured traffic".

## 1. Repo metadata — VERIFIED EXACT

Command run: `gh api repos/snapspecter/mitmproxy-mcp --jq '{...}'`

- full_name: snapspecter/mitmproxy-mcp
- stargazers_count: **123** (claim's "123-star" is exact)
- forks: 27, open_issues_count: 1 (that 1 is PR #22 "Add Some More Useful Tools!", open since 2026-06-16 — not breakage)
- created_at: 2026-02-14, **pushed_at: 2026-09-28T00:46:31Z (the day before this dive — actively pushed)**
- license: MIT, language: Python, archived: false
- description: "MCP Server that wraps mitmproxy and exposes it as a tool to any MCP client …"
- topics: agentic-workflow, antigravity, api-reverse-engineering, claude-code, mcp, mitmproxy, reverse-engineering

Not dead, not fake.

## 2. Claimed features vs README and SOURCE — ALL VERIFIED

README (`gh api repos/snapspecter/mitmproxy-mcp/readme`, decoded to `out/research/_mpmcp_readme.md`):
- L10 session variables (grab tokens from one response, reuse in replays); L23/L31 stealth replay via curl-cffi TLS impersonation; L11/L141 fuzzing; L12/L143 `export_openapi_spec` (OpenAPI v3 from captured traffic); L30 interception rules; L32 CSRF-token extraction named explicitly.

Source: `src/mitmproxy_mcp/core/server.py` (1466 lines, fetched to `out/research/_server_py.txt`). Every README tool exists as a real async function registered on FastMCP:
- `start_proxy` L371, `stop_proxy` L398, `set_scope` L403, `set_global_header` L413
- `get_traffic_summary` L435, `inspect_flow` L441, `inspect_flows` L461, `search_traffic` L663, `clear_traffic` L729
- `set_session_variable` L682, `extract_session_variable` L689 (regex + group_index → the CSRF capture+replay loop)
- `add_interception_rule` L970, `list_rules` L1003, `clear_rules` L1016 — backed by `core/interceptor.py` (fetched): `TrafficInterceptor` with `request`/`response` mitmproxy hooks and `_apply_rules` handling `inject_header` (L74), `replace_body` (L86), `block` (L103). Real implementation, not a stub.
- `replay_flow` L925 → `MitmController.replay_request` L225: uses `curl_cffi.requests.AsyncSession(impersonate="chrome120", proxies={... through the local mitmproxy}, verify=...)` (L277–285). **Stealth-replay claim is literal in code.**
- `fuzz_endpoint` L736: DAST payload substitution, categories `sqli` (5 payloads), `xss` (3), `path_traversal` (3) with baseline-anomaly comparison (L789+). Reality check: this is a **lightweight hardcoded payload set, ~11 payloads, not a real fuzzer** — fine for quick DAST triage, not a substitute for proper tooling.
- `export_openapi_spec` L1166 → `_generate_openapi_spec` L1081; `get_api_patterns` L1184; `detect_auth_pattern` L1268 (Bearer/JWT/API-key/cookie/OAuth hints); `generate_scraper_code` L1366 rendering jinja2 templates (`templates/curl_cffi.jinja2`, `playwright.jinja2`, `requests.jinja2`, `aiohttp.jinja2`).
- Extras beyond README: `get_flow_schema` L533, `load_traffic_file` L567 (HAR/flow import).

Entrypoint `start()` L1406: argparse (`--dump-file`, `--upstream-proxy`, `--port`, `--host`, `--auto-start`, `--allow-remote-bind`) then `mcp.run()` (stdio FastMCP). Defaults are loopback-only; non-loopback bind requires explicit `--allow-remote-bind` (L91–95, L1444–1449).

## 3. Packaging — REAL install commands

`pyproject.toml` (fetched): package `mitmproxy-mcp`, version 0.7.2, **`requires-python = ">=3.12,<3.14"`**, console script `mitmproxy-mcp = "mitmproxy_mcp.core.server:start"`, deps:
`mitmproxy>=12.0.0, curl-cffi>=0.14.0, mcp>=1.25.0,<2.0.0, httpx, httpx-sse, uvicorn, pydantic, pydantic-settings, python-dotenv, structlog, jsonpath-ng, beautifulsoup4, playwright>=1.58.0, google-re2>=1.1`.

Also present: `uv.lock`, `requirements.txt` (uv export, hashed), `Dockerfile` (ghcr.io/astral-sh/uv:python3.12-bookworm-slim, CMD mitmproxy-mcp), `docker-compose.yml`, `smithery.yaml` (install `uv tool install mitmproxy-mcp`, run `uvx mitmproxy-mcp`).

PyPI (`https://pypi.org/pypi/mitmproxy-mcp/json`): **published**, latest **0.6.1** (`mitmproxy_mcp-0.6.1-py3-none-any.whl` + sdist). ⚠️ **PyPI lags GitHub by two patch releases** — 0.7.1/0.7.2 (fuzz-baseline fix, scope hardening, scraper-codegen code-execution prevention, dump-file confinement; pushed 2026-09-27/28) are **NOT on PyPI yet**. For the security fixes today: install from git (`uv tool install git+https://github.com/snapspecter/mitmproxy-mcp`) — noted, not tested here.

GitHub releases exist (0.1.0 … observed via exa; tags, no binary assets relevant to Windows).

## 4. Windows-native feasibility — PROVEN BY RUNNING IT

- VM Pythons (`py -0p`): **3.12 at C:\Python312\python.exe** and 3.14.6 at C:\Python314\python.exe. The `<3.14` pin **excludes the 3.14 default** of this VM but 3.12 is present; `uv` (0.12.20, on PATH) handles interpreter selection automatically.
- Dependency wheel availability on PyPI (checked via pypi.org JSON):
  - google-re2 1.1.20251105: win_amd64 wheels for cp310–cp314 incl. cp312/cp313 ✔
  - curl-cffi 0.16.3: `cp310-abi3-win_amd64.whl` (abi3 covers 3.10+) ✔
  - mitmproxy 12.2.3: pure `py3-none-any.whl` ✔ (mitmproxy officially supports Windows)
  - mcp/httpx/uvicorn/pydantic/playwright: pure-python or Windows-supported ✔
- **Executed**: `uv tool install --python C:/Python312/python.exe mitmproxy-mcp` → resolved and installed the full dep tree (mitmproxy, curl-cffi, google-re2, playwright, …), `Installed 1 executable: mitmproxy-mcp`.
- **Executed**: `mitmproxy-mcp --help` → prints usage (`--dump-file …`), i.e. the console script works and every top-level import in server.py (re2, curl_cffi, mitmproxy, mcp, structlog, jsonpath_ng, bs4) resolved on Windows.
- `uv tool list` shows `mitmproxy-mcp v0.6.1`; tool-venv python imports `mitmproxy_mcp, re2, curl_cffi, mitmproxy, mcp` cleanly ("version check ok").
- Caveat: browser traffic capture still needs the mitmproxy CA cert installed in the target browser (`~/.mitmproxy/mitmproxy-ca-cert.pem`, server.py L74). `playwright install` needed only if using the playwright codegen path. Untested here (no browser drive in this dive).

## 5. Issues / PRs — breakage scan

All-time: 30 items, 28 closed, 1 open (PR #22 feature request, stale since June). Zero open bug reports. External contributors merged: sleeyax (6 PRs, Mar), cataggar (3, incl. security fix #4 code injection + #5 loopback bind), snyff (#26 path-traversal refactor, Sep), Arkptz (#18 dump-file, #21 ports/auto-start), shythm (#14 port release), SamuelBorborema (#25), felipetruman (#24), sawyershoemaker (#23), dandgabr (#27).
Security history (all fixed): #4 code injection in generate_scraper_code, #5 bind-to-localhost, #16 path traversal in load_traffic_file, #17 ReDoS ×2, #26 path-containment refactor, #29/#30 (0.7.1/0.7.2, Sep 27) code-exec prevention in templates, framework allowlist, scope hardening, dump-file arbitrary-write confinement. The repo attracts and merges external security research — good maturity signal for a 7-month-old solo project.
Notable non-merge: **mcp SDK pinned `>=1.25,<2.0.0`; the "migrate to mcp 2" PR #25 was closed without merging.** Works with current MCP clients over stdio regardless; watch if clients drop mcp1-style servers.
Repo hygiene: root-level `test_outlier.py` is a leftover live experiment script hitting outlier.bet through the proxy (dev debris, no impact).

## 6. Independent mentions (exa; firecrawl unusable)

`POST https://api.exa.ai/search {"query":"snapspecter mitmproxy-mcp"}` (saved `out/research/_exa1.json`): indexed by **Glama** (glama.ai/mcp/servers/snapspecter/mitmproxy-mcp), **Context7**, **MCPVault** (mcpvault.io/servers/snapspecter-mitmproxy-mcp), PyPI, GitHub releases. These are MCP-directory listings (partly auto-generated) — ecosystem presence, not editorial reviews. No Reddit/HN/blog discussion surfaced in the results returned.
Alternatives found (exa query 2, `out/research/_exa2.json`): sailro/HttpProxyMcp, yfe404/proxy-mcp, moha-abdi/mitmproxy-mcp, dandgabr/mcp-security-mitmproxy, lups2000/mitmproxy-MCP, mplogas/mitmproxy-mcp, usk6666/yorishiro-proxy — snapspecter's is the most-starred of this set and the only one with PyPI + smithery + Docker packaging observed.
**Firecrawl check NOT RUN successfully**: `POST https://api.firecrawl.dev/v1/scrape` returned `Unauthorized: Invalid token` with the VM's FIRECRAWL_API_KEY (key present, 20 chars, rejected server-side). Exa covered the independent-mention requirement.

## 7. Verdict

Claim verified end-to-end: exact star count, active (pushed yesterday), every claimed feature present in README AND implemented in source, MIT, published on PyPI, and the Windows-native install was **executed successfully on this VM** (uv + Python 3.12). Real value-add over the estate's raw mitmproxy rpc backend: the agent-facing MCP tool surface — session variables for CSRF/token replay, live interception rules, curl-cffi chrome120 stealth replay, OpenAPI reconstruction, auth-pattern detection.

Caveats: PyPI (0.6.1) misses yesterday's security fixes — pin git main for now; `mcp<2.0.0` pin; fuzzing is a token 11-payload set, not a fuzzer; solo maintainer with drive-by contributors; Python 3.14 default on this VM is out of range (use 3.12/uv).

**Score: HIGH.** Recommended install (verified): `uv tool install --python C:/Python312/python.exe mitmproxy-mcp`, then MCP client config `{"command":"uvx","args":["mitmproxy-mcp"]}`; for the 0.7.2 security fixes use `git+https://github.com/snapspecter/mitmproxy-mcp` until PyPI catches up (untested path).