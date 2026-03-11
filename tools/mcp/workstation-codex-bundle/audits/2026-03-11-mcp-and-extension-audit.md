# 2026-03-11 MCP and VS Code extension audit

This is the current reliable workstation audit after the Windows-first stabilization pass. It reflects the live canonical Codex profile, the secondary VS Code settings, the extension inventory, and the no-kill parentage audit of noisy helper processes.

## Current reliable findings
- Canonical Codex home remains `C:\Users\Prekzursil\.codex`.
- VS Code remains secondary: no raw `mcpServers` duplication in `settings.json`.
- Serena is removed from the active canonical MCP set.
- Nuxt remains removed from the active canonical MCP set.
- `SENTRY_HOST` is now persisted in both User and Machine environment scopes and in the private workstation bundle.
- Semgrep CLI is installed locally at `C:\Users\Prekzursil\.local\bin\semgrep.exe` and wired into VS Code settings.
- Terraform and Postgres are now **disabled by default** in the canonical config because they were the largest avoidable noise sources in the current session.

## Process and container noise
A non-destructive parentage audit showed that most duplicate helper processes are children of multiple live `codex.exe app-server` parents rather than one runaway orphan. The two worst container-backed sources were:
- `ghcr.io/pgedge/postgres-mcp:latest`
- `hashicorp/terraform-mcp-server:0.4.0`

Those containers were stopped after the parentage audit, and both MCPs were switched to disabled-by-default in the canonical config so future sessions start quieter.

## Extension audit posture
- Total installed extensions: **147**
- Keep: **29**
- Optional: **95**
- Candidate-remove: **23**

The extension cleanup remains **audit then signoff**. No broad uninstall sweep was applied in this pass.

## Most important remaining gaps
- `terraform`: current `TFE_TOKEN` fails a direct Terraform Cloud account API check with `401 unauthorized`
- `notion`: still auth-gated until first-use login
- `unity`: staged on `D:` but still waiting for a live Unity Editor handshake
- `ghidra`: staged on `D:` but still waiting for a live plugin/server handshake
- `codex_consult` and `promptbridge_talk`: still partial under live runtime drift, but hybrid-explicit quiet behavior is preserved

## Best next operator actions
1. decide whether to keep `postgres` disabled-by-default permanently or only until needed
2. replace the invalid Terraform token if Terraform MCP should be re-enabled
3. complete first-use Notion auth
4. perform the Unity and Ghidra native-app handshakes
5. review the 23 candidate-remove extensions and approve a removal batch
