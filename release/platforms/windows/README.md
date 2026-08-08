# Windows Platform MCP Config Snapshots

Snapshot date: 2026-04-04

> **Addendum 2026-08-09 — three files in this set capture a lane that has since been
> retired.** `codex-AGENTS.md`, `CONSULTATION_WORKFLOW.md` and
> `promptbridge-orchestration.toml` were generated into `~/.codex/` by
> `tools/mcp/codex-orchestrator/integrations/codex/bootstrap.mjs` (note the
> `<!-- promptbridge-managed -->` marker on the first two). That orchestrator, the
> PromptBridge/Agentify desktop lane it drove, and the `~/.codex/promptbridge-runtime/`
> directory it deployed were all deleted on 2026-08-09, and the `[mcp_servers]` entry for
> `codex_consult` inside `codex-config.toml` points at an entrypoint that no longer exists.
>
> **These files are NOT being edited, on purpose.** They are a dated capture of the live
> configuration as it stood on 2026-04-04; rewriting them to drop the retired lane would
> make them a snapshot of a state that never existed. Treat the set as a historical record,
> not as an install source — and in particular do not replay `codex-config.toml` into a live
> `~/.codex/config.toml`. Codex is now reached through the official `codex mcp-server`.

Live MCP and agent configuration snapshots from the Windows development workstation. All secrets, tokens, API keys, and PII have been redacted (replaced with `<REDACTED>`). Environment variable references (e.g. `${CODECOV_TOKEN}`, `$GH_TOKEN`) are preserved as-is since they contain no actual secret values.

## Files

| File | Source | Description |
|---|---|---|
| `codex-config.toml` | `~/.codex/config.toml` | Codex CLI configuration -- model settings, feature flags, MCP server definitions, plugin list, approval policies, and TUI preferences |
| `claude-config.json` | `~/.claude.json` | Claude Code configuration -- MCP server definitions (stdio and HTTP), project settings, feature flags, skill usage stats |
| `codex-AGENTS.md` | `~/.codex/AGENTS.md` | PromptBridge consultation contract -- Lane A/B operating model, required output schema, redaction policy, fallback behavior |
| `codex-model-instructions.md` | `~/.codex/model-instructions.md` | Codex model instruction file -- skill routing preferences, quality/security loop, local check commands |
| `gemini-settings.json` | `~/.gemini/settings.json` | Gemini CLI configuration -- security settings, MCP server definitions, model selection |
| `CONSULTATION_WORKFLOW.md` | `~/.codex/CONSULTATION_WORKFLOW.md` | PromptBridge desktop workflow -- lane B flow, verification contract, required reset procedures |
| `promptbridge-orchestration.toml` | `~/.codex/promptbridge-orchestration.toml` | PromptBridge orchestration profiles -- consult, brainstorm, review, discuss, coordinate, curate modes with skill mappings |

## MCP Server Summary

Across all three platforms (Codex, Claude, Gemini), the following MCP servers are configured:

**Reverse Engineering**: binary-ninja-mcp, ghidra-mcp, ida-pro-mcp, frida-mcp, cheatengine, hexstrike-ai
**Code Quality**: semgrep, codacy, codecov, deepsource, sonarqube, qlty, meta-tool
**Browser/Web**: chrome-devtools, playwright, browserstack, firecrawl, scrapegraph, tavily
**Productivity**: github, github_cli, linear, notion, figma, sentry, memory, excel, pdf-reader, markitdown
**Infrastructure**: docker, postgres, digitalocean, ralph-orchestrator, apify, stripe
**AI/Dev**: context7, repomix, mcp-graphql, huggingface, codex_consult

## Notes

- Env var references (`${VAR}`, `$VAR`, `env_vars = [...]`) are not secrets -- they are runtime lookups
- The `codex_consult` MCP server is the PromptBridge sidecar integration point
- Gemini uses `settings.json` (not a TOML config) and includes `trust: true` per-server
- Codex uses `bearer_token_env_var` for OAuth-based MCP servers (GitHub, Apify, HuggingFace)
