# 2026-03-31 Ralph local validation

## Commands run

- `pwsh -File .\tools\editor\ralph-orchestrator\scripts\install-ralph-orchestrator.ps1`
- `pwsh -File .\tools\editor\ralph-orchestrator\scripts\validate-ralph-orchestrator.ps1`
- `pwsh -File .\scripts\validate-all-skills.ps1`
- `python .\scripts\test-live-skill-helpers.py`

## Evidence

- `ralph --version` returned `ralph 2.8.1`.
- `ralph doctor` returned `Result: PASS (2 warning(s))` from the WSL-backed install.
- `codex mcp get ralph-orchestrator` showed:
  - `enabled: true`
  - `command: C:/Windows/System32/wsl.exe`
  - `args: -e bash -lc export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph mcp serve`
- `claude mcp get ralph-orchestrator` reported `Status: ✓ Connected`.
- Gemini registration was verified from `C:\Users\Prekzursil\.gemini\settings.json`; the validation probe for `gemini mcp list` timed out after 15 seconds on this workstation, so Gemini was verified at the config level rather than by a live CLI health check.
- `npx skills ls -g -a codex|claude-code|gemini-cli --json` confirmed `ralph-hats`, `ralph-loop`, and `ralph-orchestrator-setup` were installed for all three agents.
- `pwsh -File .\scripts\validate-all-skills.ps1` passed with `Validated 33 skill(s) successfully.` after forcing a PyYAML-capable Python interpreter selection.
- `python .\scripts\test-live-skill-helpers.py` passed with `All live skill helper smoke tests passed.`

## Warnings / partials

- `ralph doctor` still warns that Anthropic auth is not detected for the Claude backend and that the workspace has uncommitted changes. These are environmental warnings, not Ralph install failures.
- Gemini CLI health probing remains best-effort because `gemini mcp list` is currently non-responsive on this workstation.
