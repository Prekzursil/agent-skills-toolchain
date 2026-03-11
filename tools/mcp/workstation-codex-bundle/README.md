# Workstation Codex MCP Bundle

Curated Windows-first MCP bundle for the canonical Codex profile at `C:\Users\Prekzursil\.codex\config.toml`.

## Provenance split
- **Self-made**: `codex_consult`, `promptbridge_talk`, and the editor-local `prompt-optimizer-button` tool.
- **Curated upstream picks**: Serena, Notion, GitHub, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube, Terraform, MindsDB, Unity MCP, and Ghidra MCP.
- **Removed**: Netlify.

## Current status
- **Enabled now**: Serena, Notion, Terraform, MindsDB, GitHub, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube.
- **Installed/staged but intentionally disabled**: Unity MCP, Ghidra MCP.
- **Reason for disabled state**: both require a live native-app handshake before the bridge should be enabled.

## Heavy local installs on D:
- `D:\Program Files\Ghidra\ghidra_12.0.3_PUBLIC`
- `D:\Program Files\Java\jdk-21.0.10+7`
- `D:\Program Files\Apache\apache-maven-3.9.9`
- `D:\MCP\ghidra-mcp`
- `D:\MCP\unity-mcp`
- `D:\ProgramData\MindsDB`

## Files in this project
- `bundle.manifest.json`: provenance + status manifest for the saved bundle
- `config/codex-config-curated.toml`: curated MCP config snippet
- `references/upstream-sources.md`: primary-source links for the upstream picks
- `validation/2026-03-11-local-validation.md`: local evidence for this workstation bundle
