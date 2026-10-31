# 2026-03-30 cross-CLI parity snapshot

## Summary

- Goal: make the local workstation satisfy metaswarm's existing expectations without editing `.metaswarm`.
- Resulting shared executable baseline from a fresh user shell:
  - `bd`
  - `codex`
  - `gemini`
  - `claude`
  - `uv`
  - `uvx`
- Superpowers is aligned across all three CLIs at upstream `v5.0.6`.

## Permission model

- Codex: `approval_policy = "never"` and `sandbox_mode = "danger-full-access"` in the canonical profile snapshot.
- Claude: existing `bypassPermissions` posture retained.
- Gemini:
  - trusted-root settings kept on
  - `general.defaultApprovalMode = "auto_edit"`
  - local wrapper in `C:\Users\Prekzursil\.local\bin\gemini.cmd` / `gemini.ps1` injects `--approval-mode yolo` unless the caller explicitly overrides it
  - `~/.gemini/policies/999-local-full-access.toml` grants allow-all behavior, including shell redirection

## Shared skills

- Claude and Gemini both expose the upstream superpowers workflow set.
- Codex exposes the same superpowers workflow set through the shared `C:\Users\Prekzursil\.agents\skills\superpowers` junction.
- The user-level `.agents\skills` directory remains the portable cross-agent tier for non-proprietary skills.
- Codex-only orchestration and consultation skills remain outside the shared tier by design.

## Shared MCPs

- Gemini user settings now carry an env-backed essential MCP baseline:
  - GitHub via `gh-cli-mcp`
  - Codacy via `codacy-mcp-server`
  - DeepSource via the local wrapper script
  - Codecov via `mcp-codecov`
  - SonarQube via the Docker-backed server definition
  - Semgrep via `semgrep mcp`
  - Cheat Engine via the local Python bridge
  - Playwright via `playwright-mcp --headless`
  - Chrome DevTools via `chrome-devtools-mcp`
  - HexStrike AI via the local Python launcher at `C:/Users/Prekzursil/.local/opt/hexstrike-ai/hexstrike_mcp_launcher.py`
  - Hugging Face via the remote HTTP MCP endpoint
  - Figma, Notion, and Linear via remote HTTP MCP definitions
- Current runtime proof on Gemini:
  - Connected during `gemini mcp list`: GitHub, Codacy, DeepSource, Codecov, Cheat Engine, Playwright, Chrome DevTools, Figma, Notion, Hugging Face
  - Still inconsistent / follow-up required: Semgrep, SonarQube, Linear, HexStrike AI
- Claude now carries the requested common set through a mix of surviving plugins and explicit local config:
  - Connected: GitHub, Playwright, Chrome DevTools, Figma, Notion, Linear, Semgrep, SonarQube, Cheat Engine, Hugging Face, Codacy, Codecov, DeepSource
  - Added but still blocked in direct health checks: HexStrike AI via the same local launcher used by Codex and Gemini
  - Permanently removed noisy or unwanted plugin-backed MCPs: Supabase, Atlassian, Adspirer, Atlan, Circleback, FireTiger, Flint, Intercom, Legalzoom, Neon, Opsera, PostHog, Postman, Prisma, RevenueCat, Sanity, Slack, Stripe, Vercel, Amazon Location Service, CockroachDB, Discord, Fakechat, FiftyOne, Goodmem, iMessage, Laravel Boost, PagerDuty, Sourcegraph, SumUp, Telegram, Wix, ZoomInfo, Serena, Terraform, Firebase
- Codex keeps the fuller canonical inventory in `config.toml`, with the common requested set already present and enabled, including the shared HexStrike launcher path.

## Notes

- `.metaswarm/external-tools.yaml` was intentionally left untouched.
- The authoritative PATH change happened at the user level, not only in the current process.
- HexStrike's upstream MCP adapter is present and locally installable, but direct Claude / Gemini health checks still need extra compatibility work even after the localhost runtime and shared launcher wiring were added.
- This snapshot is meant to document the workstation state, not to claim that every configured MCP is equally healthy on every CLI.
