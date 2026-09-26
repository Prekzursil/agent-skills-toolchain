---
title: Grok search-hub accounts stub 2026-09-03
type: note
permalink: main/tools/grok-search-hub-accounts-stub-2026-09-03
tags:
- search-hub
- grok
- onions
- pr310
---

- [decision] Search-hub stays Grok-only (owner: "leave search hub only for yourself"). Not in CyberStrike mcp map. Not HTTP-fronted on `:31420`.
- [fact] Grok `~/.grok/config.toml` `[mcp_servers.search-hub]` is lazy **stdio** `D:\opt\search-hub-pr310\tools\mcp\search-hub\hub.py` with `SEARXNG_URL=http://127.0.0.1:8890`, `TRAILSEARCH_URL=http://127.0.0.1:8794`, `ENABLE_ONIONS=1`.
- [fact] Isolated worktree `accounts.json` was git-crypt encrypted (worktree does not inherit unlock). Encrypted blob saved as `accounts.json.gitcrypt.bak`; runtime stub is `{}` so hub can start. `SearchHub(...)` init OK; `--print-plan` 84 tools, 0 degraded.
- [fact] Containers Up: `searxng` `:8890` (20 Brave results on a smoke query), `selfhosted-search-app` `:8794` TrailSearch `/tavily/search` HTTP 200 with 1 result. Onion indexes registered: ahmia + vormweb. VormWeb returned 1 hit; Ahmia returned 0 with unresponsive `parsing error`. Envelope unchanged: clearnet index-only, no Tor, no `.onion` fetch.
- [fact] This Grok session does **not** hot-reload MCP — search-hub tools are absent until a new session. Keyed Exa/Tavily still depend on process env keys, not the encrypted store.

[[Grok PR 310 search-hub live 2026-09-03]] [[CyberStrike MCP HTTP fronts and Bolt 2026-09-03]]