---
title: Grok PR 310 search-hub live 2026-09-03
type: note
permalink: main/tools/grok-pr-310-search-hub-live-2026-09-03
tags:
- decision
- fact
- cyberstrike
- search-hub
- pr310
---

# Grok PR 310 search-hub live 2026-09-03

- [decision] PR 310 search/deep-web stack is Grok/harness-side only. CyberStrike does not get Tavily, Exa, search-hub, or TrailSearch. Owner: "no do that for yourself, he doesnt need to research youd o".
- [decision] G-4 A: HackTricks MCP stays in CyberStrike; CS MCP set frozen at 10 connected servers.
- [fact] Isolated worktree `D:\\opt\\search-hub-pr310` at PR HEAD `46f6dd2ee`. Dirty toolchain checkout `C:\\Users\\Prekzursil\\source\\agent-skills-toolchain` was not used.
- [fact] Grok `~/.grok/config.toml` `[mcp_servers.search-hub]` stdio `C:\\Python314\\python.exe` + `D:\\opt\\search-hub-pr310\\tools\\mcp\\search-hub\\hub.py`. Env: `SEARXNG_URL=http://127.0.0.1:8890`, `TRAILSEARCH_URL=http://127.0.0.1:8794`, `ENABLE_ONIONS=1`. Session does not hot-reload MCP — new Grok session required to see the 84 tools.
- [fact] Estate SearXNG Docker `searxng` on `127.0.0.1:8890`. Settings `D:\\searxng\\settings.yml` mapping `use_default_settings` removes stock Tor-gated ahmia/torch; registers clearnet `onion index` engines ahmia+vormweb; keyless mix google disabled, duckduckgo/mwmbl/wikipedia on. Default JSON search returned 68 hits (mwmbl, brave) after DDG/Startpage CAPTCHA suspend.
- [fact] TrailSearch container `selfhosted-search-app` `127.0.0.1:8794->3000`. `/docs` 200. `/tavily/search` 200 after compose env `ENABLED_ENGINES=mwmbl,brave,duckduckgo` (upstream default was `baidu__general` plus disabled brave/ddg) and overlay `deploy/overlays/search_providers.py` omitting `time_range=week` (that filter returned 0 hits). Adapter `selfhosted_search` live-smoked.
- [fact] Onion lane is index-only over clearnet: no Tor, no `.onion` fetch. Hub `onions.py` gate: no-confirm → ask; confirm+low → run; `ENABLE_ONIONS=0` → killed. Live SearXNG `engines=ahmia` 10 hits, `engines=vormweb` 41 hits on query privacy (metadata only).
- [fact] CyberStrike `mcp list` 10/10 connected: github-security, cve, osint, hexstrike-ai, sliver, sliver-full, firecrawl, basic-memory, hacktricks, metasploit. No search-hub in `cyberstrike.json`.
- [fact] Bolt still queued (G-3 B, after grill). Answer engines (Vane/LDR) not started.

Related: [[CyberStrike MCPs restored 2026-09-02]] [[CyberStrike AI providers 2026-09-02]]