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
- **Sentry** — production issue triage; host is fixed to `https://sentry.io`
- **SonarQube** — quality gate diagnostics
- **Figma** — design-to-implementation
- **BrowserStack** — cross-browser and device verification
- **Postgres** — keep installed but disabled by default unless you actively need database MCP access

## Useful local tooling outside MCP
- **Codecov** — keep the VS Code extension pointed at the hosted API and use the local CLI on `D:` for pre-push gate analysis
- **Chromatic** — use the CLI workspace on `D:` with Playwright and the persisted `CHROMATIC_PROJECT_TOKEN`; prefer local `chromatic --playwright --dry-run` validation, keep browser/site checks out of the normal workflow, and treat missing `test-results/chromatic-archives` as the next setup task

## Stage for later or native app required
- **Ghidra MCP** — now usable through the verified headless bridge on `127.0.0.1:8089`; use the GUI plugin flow only when you need CodeBrowser-driven analysis
- **MindsDB** — useful when you actually need a local AI/data service; otherwise keep optional

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
- **Terraform MCP** — removed from the canonical bundle after direct token validation failed and the CLI-first workflow was preferred
