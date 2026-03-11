# 2026-03-11 MCP and VS Code extension audit

This is the current reliable workstation audit after the Windows-first stabilization pass. It reflects the live canonical Codex profile, the secondary VS Code settings, the extension inventory, and the no-kill parentage audit of noisy helper processes.

## Current reliable findings
- Canonical Codex home remains `C:\Users\Prekzursil\.codex`.
- VS Code remains secondary: no raw `mcpServers` duplication in `settings.json`.
- Serena, Nuxt, Netlify, and Terraform are no longer part of the active canonical MCP bundle.
- `SENTRY_HOST` is persisted in both User and Machine environment scopes and in the private workstation bundle.
- Semgrep CLI is installed locally at `C:\Users\Prekzursil\.local\bin\semgrep.exe` and wired into VS Code settings.
- Codecov uses the hosted API plus a local CLI on `D:` for pre-push gate analysis.
- Chromatic is tracked as a CLI + Playwright integration on `D:`, not as an MCP server.

## Process and container noise
A non-destructive parentage audit showed that most duplicate helper processes are children of multiple live `codex.exe app-server` parents rather than one runaway orphan. The largest avoidable source remains `postgres`, so it stays disabled by default. Terraform is no longer part of the bundle.

## Extension audit posture
- Total installed extensions: **147**
- Keep: **29**
- Optional: **95**
- Candidate-remove: **23**

The extension cleanup remains **audit then signoff**. No broad uninstall sweep was applied in this pass.

## Non-MCP integrations
- **Codecov** — VS Code points at `https://api.codecov.io`, and `D:\Tools\codecov-cli\.venv\Scripts\codecovcli.exe --help` succeeds. Use the CLI for local gate inspection before pushing.
- **Chromatic** — the CLI workspace exists at `D:\Tools\chromatic-playwright` with Playwright wiring in `package.json`. The current blocker is missing `CHROMATIC_PROJECT_TOKEN`, and no browser/site auth check was attempted by owner instruction.

## Most important remaining gaps
- `unity`: staged on `D:` but still waiting for a live Unity Editor/project handshake
- `chromatic`: CLI workspace is ready, but `CHROMATIC_PROJECT_TOKEN` is still missing
- `codex_consult` and `promptbridge_talk`: still partial under live runtime drift, but hybrid-explicit quiet behavior is preserved

## Best next operator actions
1. keep `postgres` disabled-by-default unless you actually need it
2. supply `CHROMATIC_PROJECT_TOKEN` if Chromatic should move from staged to live
3. open a real Unity Editor/project if Unity MCP should move from staged to live
4. use the Ghidra GUI plugin flow only when GUI-specific analysis is needed; the headless bridge is already a valid local runtime
5. review the 23 candidate-remove extensions and approve a removal batch if you want a quieter VS Code surface
