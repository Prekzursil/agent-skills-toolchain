Prefer available skills over ad-hoc behavior when they clearly match the task.

Skill routing preferences:
- Use `using-superpowers` when advanced Codex capabilities, high-leverage workflows, or power-user behaviors are relevant.
- Use `subagent-driven-development` and `dispatching-parallel-agents` for decomposition, delegation, and parallel work when tasks can be split safely.
- For remote repository documentation, GitHub repo archaeology, or repository-level docs lookup outside the local workspace, prefer `read-github`.
- For UI, UX, design-system, layout, accessibility, and front-end visual quality tasks, prefer `ui-ux-pro-max`.
- For browser automation and UI investigation, prefer `playwright-interactive` for iterative, stateful debugging and exploration. Use `playwright` for more straightforward scripted browser tasks.
- For targeted browser or web application validation runs, prefer `webapp-testing`.
- If the user explicitly asks for Codex-side consultation, review, or curation, prefer the `codex-consult` skill (modes: consult / review / curate).
- If the user explicitly asks for direct ChatGPT web / Agentify behavior, prefer `chatgpt5-web-query`, `chatgpt5-web-discuss`, or `chatgpt5-web-curate` rather than Codex orchestration.
- For debugging tasks, prefer `systematic-debugging`.
- Before declaring work complete, prefer `verification-before-completion` and verify the actual result.
- For larger multi-step tasks, prefer `writing-plans` for planning and `executing-plans` for carrying out an approved or established plan.
- For CI breakage, prefer `gh-fix-ci`.
- For review, auditing, or finding issues, prefer `codex-review` and `codex-audit`.

Usage guidance:
- Do not force a skill when it is not relevant.
- If a skill is clearly applicable, prefer invoking it or following its workflow rather than improvising.
- Keep outputs concise, concrete, and oriented toward finishing the user’s task.

Quality/security loop for local code generation:
- When writing or refactoring code, prefer installed security/quality skills when they clearly match the task: `code-security`, `llm-security`, `semgrep`, `autofix-bot-api`, `deepsource`, `sentry`, `security-best-practices`, `security-threat-model`, and `quality-gate-automation-architect`.
- Before claiming a non-trivial change is complete, run the applicable local checks and fix or regenerate until clean instead of rationalizing failures.
- Applicable checks on this workstation include: `semgrep scan --config auto --error`, `bandit -r src/ -ll` for Python, `lizard src/ -C 15` (or closest touched source root), `trivy fs .` for dependency/container/IaC changes, and `gitleaks detect --no-git --source .` for focused secret scans.
- Use SonarQube MCP when project-specific Sonar rules or issue verification matter. Use DeepSource skills for Autofix Bot loops or DeepSource review retrieval. Use Sentry integration when runtime or production error context matters.
