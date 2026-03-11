# 2026-03-11 MCP matrix

This matrix reflects the current canonical Windows profile at `C:\Users\Prekzursil\.codex\config.toml`, the secondary VS Code settings at `C:\Users\Prekzursil\AppData\Roaming\Code\User\settings.json`, and the validated workstation bundle after the owner-requested Serena and Nuxt removal.

| MCP | Current state | Decision | Evidence / gap | Exact stance |
|---|---|---|---|---|
| apify | enabled | keep | bearer token configured | keep enabled |
| browserstack | enabled | keep | env persisted in user+machine scopes | keep enabled |
| chrome-devtools | enabled | keep | active stdio launcher resolves | keep enabled |
| codacy | enabled | keep | token-backed stdio launcher resolves | keep enabled |
| codex_consult | enabled-partial | keep and monitor | lane remains partial under live runtime drift and no-kill policy | keep enabled under hybrid-explicit lane model |
| context7 | enabled | keep | token persisted in user+machine scopes | keep enabled |
| desktop-commander | enabled | keep | stdio launcher resolves | keep enabled |
| docker | enabled | keep but watch | duplicate helper spawn still occurs with many live Codex app-server parents | keep enabled; do not treat it as orphan noise by default |
| excel | enabled | keep | full Windows `uvx.exe` path in canonical config | keep enabled |
| figma | enabled-auth-gated | keep | endpoint responds but auth/runtime proof still depends on user session | keep enabled; first live use proves it |
| firecrawl | enabled | keep | token-backed stdio launcher resolves | keep enabled |
| ghidra | disabled-staged | keep staged | native Ghidra plugin/server handshake still required | keep disabled until native handshake passes |
| github | enabled-verified | keep | GitHub MCP remains part of the working curated set | keep enabled |
| github_cli | enabled | keep | CLI launcher present | keep enabled |
| huggingface | enabled | keep | bearer-token URL config present | keep enabled |
| linear | enabled-verified | keep | URL config enabled and previously verified in the workstation pass | keep enabled |
| markitdown | enabled | keep | full Windows `uvx.exe` path in canonical config | keep enabled |
| memory | enabled | keep | canonical Windows memory file path preserved | keep enabled |
| mindsdb | enabled-verified | keep | `http://127.0.0.1:47334/mcp/sse` returns `200` | keep enabled |
| notion | enabled-auth-gated | keep | `https://mcp.notion.com/sse` returns `401` until first-use auth | keep enabled; complete auth on first use |
| pdf-reader | enabled | keep | explicit enablement present | keep enabled |
| playwright | enabled | keep | stdio launcher resolves | keep enabled |
| postgres | disabled-noisy | keep installed, disable by default | process storm created >100 duplicate helper containers with no active DB context requirement | disabled in canonical config and VS Code sampling; enable on demand |
| promptbridge_talk | enabled-manual-ready-partial | keep and monitor | desktop autostart suppressed; server remains available without browser popups | keep enabled under hybrid-explicit lane model |
| scrapegraph | enabled | keep | full Windows `uvx.exe` path in canonical config | keep enabled |
| sentry | enabled-verified-api | keep | `SENTRY_HOST` now persisted as `https://sentry.io`; direct API call returns `version=0` | keep enabled |
| sonarqube | enabled-configured | keep | token/config present; fresh runtime proof still pending | keep enabled |
| tavily | enabled | keep | token-backed stdio launcher resolves | keep enabled |
| terraform | disabled-invalid-token | keep installed, disable by default | direct Terraform Cloud account API returns `401 unauthorized` with current `TFE_TOKEN` | disabled in canonical config and VS Code sampling until a valid token is supplied |
| unity | disabled-staged | keep staged | Unity Editor package/server handshake still required | keep disabled until native handshake passes |
| serena | removed | remove | owner preference and helper-noise concerns | keep removed from canonical config and sampling |
| nuxt | removed | remove | no longer present in canonical config | keep removed; historical context only |
| netlify | removed | remove | owner preference | keep removed |
