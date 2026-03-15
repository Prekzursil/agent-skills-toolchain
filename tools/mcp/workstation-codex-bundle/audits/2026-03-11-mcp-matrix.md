# 2026-03-11 MCP matrix

This matrix reflects the current canonical Windows profile at `C:\Users\Prekzursil\.codex\config.toml`, the secondary VS Code settings at `C:\Users\Prekzursil\AppData\Roaming\Code\User\settings.json`, and the validated workstation bundle after the owner-requested Serena, Nuxt, Netlify, and Terraform removal.

| MCP | Current state | Decision | Evidence / gap | Exact stance |
|---|---|---|---|---|
| apify | enabled | keep | bearer token configured | keep enabled |
| browserstack | enabled | keep | env persisted in user+machine scopes | keep enabled |
| chrome-devtools | enabled | keep | active stdio launcher resolves | keep enabled |
| codacy | enabled | keep | token-backed stdio launcher resolves | keep enabled |
| codex_consult | enabled-verified-single-server | keep | single managed MCP server in canonical `.codex`; exports codex_* plus promptbridge_* / agentify_* tools and passed status/probe/self-test on 2026-03-15 | keep enabled as the single managed consultation lane |
| context7 | enabled | keep | token persisted in user+machine scopes | keep enabled |
| desktop-commander | enabled | keep | stdio launcher resolves | keep enabled |
| docker | enabled | keep but watch | duplicate helper spawn still occurs with many live Codex app-server parents | keep enabled; do not treat it as orphan noise by default |
| excel | enabled | keep | full Windows `uvx.exe` path in canonical config | keep enabled |
| figma | enabled-auth-gated | keep | endpoint responds but auth/runtime proof still depends on user session | keep enabled; first live use proves it |
| firecrawl | enabled | keep | token-backed stdio launcher resolves | keep enabled |
| ghidra | enabled-verified-headless | keep | canonical config enabled; local headless server proves /check_connection and /mcp/schema on 127.0.0.1:8089 | keep enabled; GUI plugin flow is optional when CodeBrowser is open |
| github | enabled-verified | keep | GitHub MCP remains part of the working curated set | keep enabled |
| github_cli | enabled | keep | CLI launcher present | keep enabled |
| huggingface | enabled | keep | bearer-token URL config present | keep enabled |
| linear | enabled-verified | keep | URL config enabled and previously verified in the workstation pass | keep enabled |
| markitdown | enabled | keep | full Windows `uvx.exe` path in canonical config | keep enabled |
| memory | enabled | keep | canonical Windows memory file path preserved | keep enabled |
| mindsdb | enabled-verified | keep | `http://127.0.0.1:47334/mcp/status` and `/mcp/sse` respond | keep enabled |
| notion | enabled-verified-oauth | keep | canonical config points to `https://mcp.notion.com/mcp`; `codex mcp login notion` completed successfully on 2026-03-11 | keep enabled |
| pdf-reader | enabled | keep | explicit enablement present | keep enabled |
| playwright | enabled | keep | stdio launcher resolves | keep enabled |
| postgres | disabled-noisy | keep installed, disable by default | process storm created duplicate helper containers with no active DB context requirement | disabled in canonical config and VS Code sampling; enable on demand |
| scrapegraph | enabled | keep | full Windows `uvx.exe` path in canonical config | keep enabled |
| sentry | enabled-verified-api | keep | `SENTRY_HOST` persisted as `https://sentry.io`; direct API call succeeds without OpenAI API billing | keep enabled |
| sonarqube | enabled-configured | keep | token/config present; fresh runtime proof still pending | keep enabled |
| tavily | enabled | keep | token-backed stdio launcher resolves | keep enabled |
| unity | removed | remove | owner preference; local D-drive staging and env references were deleted | keep removed |
| serena | removed | remove | owner preference and helper-noise concerns | keep removed from canonical config and sampling |
| nuxt | removed | remove | no longer present in canonical config | keep removed; historical context only |
| netlify | removed | remove | owner preference | keep removed |
