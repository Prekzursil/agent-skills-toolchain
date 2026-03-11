# 2026-03-11 MCP matrix

This matrix reflects the canonical Windows profile at `C:\Users\Prekzursil\.codex\config.toml`, the VS Code secondary settings at `C:\Users\Prekzursil\AppData\Roaming\Code\User\settings.json`, and the current workstation bundle after the Serena and Nuxt cleanup.

| MCP | Status | Keep / repair / remove | Key gap | Exact suggested change |
|---|---|---|---|---|
| apify | enabled | keep | token-dependent | keep current URL + bearer token env |
| browserstack | enabled | keep | none in config; runtime proof still indirect | keep config, keep secrets in env not settings |
| chrome-devtools | enabled | keep | none from local config | keep |
| codacy | enabled | keep | token-dependent | keep |
| codex_consult | enabled | repair | lane still partial under live runtime drift | keep enabled; re-run cold `orchestration:update/probe/self-test` later, do not kill Codex to force it |
| context7 | enabled | keep | token-dependent | keep enabled; Context7 key is persisted |
| desktop-commander | enabled | keep | none from local config | keep |
| docker | enabled | repair | helper/container noise is high | keep enabled; later investigate duplicate `docker-mcp` spawn paths before considering disablement |
| excel | enabled | keep | used bare `uvx` previously | normalized to full `uvx.exe` path |
| figma | enabled | repair | auth/runtime not freshly proved in this turn | keep enabled; treat as auth-gated until fresh proof |
| firecrawl | enabled | keep | token-dependent | keep |
| ghidra | disabled | keep disabled | native Ghidra plugin/server handshake required | leave disabled until `/check_connection` is live from Ghidra |
| github | enabled | keep | none | keep |
| github_cli | enabled | keep | token-dependent | keep |
| huggingface | enabled | keep | token-dependent | keep |
| linear | enabled | keep | explicit enablement was missing | added `enabled = true`; keep |
| markitdown | enabled | keep | used bare `uvx` previously | normalized to full `uvx.exe` path |
| memory | enabled | keep | none | keep canonical Windows memory file path |
| mindsdb | enabled | keep | none; local health previously proved | keep |
| notion | enabled | repair | first-use auth gate expected | keep enabled; complete auth on first use |
| pdf-reader | enabled | keep | explicit enablement was missing | added `enabled = true`; keep |
| playwright | enabled | keep | none | keep |
| postgres | enabled | repair | very high duplicate container count | keep enabled for now; later inspect duplicate launcher sources before deciding whether to disable |
| promptbridge_talk | enabled | repair | intentionally manual-ready, still partial not fully green | keep enabled under hybrid-explicit model; no autostart |
| scrapegraph | enabled | keep | used bare `uvx` previously | normalized to full `uvx.exe` path |
| sentry | enabled | repair | `SENTRY_HOST` missing from env manifest | keep enabled only if host is supplied; otherwise disable until env is complete |
| sonarqube | enabled | repair | config present, fresh runtime proof not captured in this turn | keep enabled; refresh runtime proof later |
| tavily | enabled | keep | token-dependent | keep |
| terraform | enabled | repair | docker launch works but auth is still failing | keep enabled; repair `TFE_TOKEN` / auth context, not launch shape |
| unity | disabled | keep disabled | Unity Editor package/server handshake required | leave disabled until Editor shows connected state |
| serena | removed | remove | owner preference and helper-noise concerns | removed from canonical config and VS Code sampling |
| nuxt | removed | remove | no longer present in canonical config | keep removed; historical note only |
| netlify | removed | remove | removed by owner preference | keep removed |
