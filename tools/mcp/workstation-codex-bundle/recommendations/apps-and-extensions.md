# Recommended Codex apps, MCPs, skills, and extension cleanup

## Best immediate MCP and Codex Settings installs
These fit the current workstation and active workflows best:
- **GitHub** — repo, PR, and automation work
- **Notion** — specs, notes, planning, knowledge capture
- **Linear** — issue and project coordination
- **Playwright** — browser automation and UI validation
- **Chrome DevTools** — frontend and network inspection
- **Docker** — local container inspection
- **Context7** — docs and context retrieval once tokened
- **Memory** — durable local memory for the canonical Windows profile

## Best if you actively use them
- **Sentry** — production issue triage; host is now fixed to `https://sentry.io`
- **SonarQube** — quality gate diagnostics
- **Figma** — design-to-implementation
- **BrowserStack** — cross-browser and device verification
- **Terraform** — keep installed but disabled until a valid Terraform Cloud token is supplied
- **Postgres** — keep installed but disabled by default unless you actively need database MCP access

## Stage for later or native app required
- **Unity MCP** — only after the Unity Editor package/server handshake succeeds
- **Ghidra MCP** — only after the Ghidra plugin/server handshake succeeds
- **MindsDB** — useful when you actually need a local AI/data service; otherwise keep optional
- **Chromatic** — use Chromatic CLI for now; no official public MCP install path was found in the current vendor docs

## Skills to keep close at hand
- `using-superpowers`
- `verification-before-completion`
- `systematic-debugging`
- `promptbridge-codex-consult`
- `read-github`
- `playwright` and `playwright-interactive`
- `writing-skills`
- `codex-runtime-recovery`
- `codex-session-reunion`
- `long-copy-orchestrator`

## Extension cleanup candidates
Suggested review list rather than blind uninstall:
1. keep `github.vscode-github-actions`, review-remove `me-dutour-mathieu.vscode-github-actions`
2. review-remove `github.remotehub` and `ms-vscode.remote-repositories` if remote browsing is inactive
3. review-remove extra AI assistants: `google.geminicodeassist`, `rainlei.superpower-copilot`
4. review-remove `wallabyjs.dingo-vscode` if Wallaby is inactive
5. review-remove `firefox-devtools.vscode-firefox-debug` if Chrome DevTools plus Playwright cover browser debugging
6. keep one icon theme only: `pkief.material-icon-theme` or `vscode-icons-team.vscode-icons`

## Explicit skip and remove
- **Serena MCP** — removed from canonical config by owner preference and helper-noise concerns
- **Netlify MCP** — removed from canonical config
- **Nuxt MCP** — removed from canonical config and no longer part of the active curated bundle
