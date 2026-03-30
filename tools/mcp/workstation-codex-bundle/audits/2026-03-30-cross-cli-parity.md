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
- Current runtime proof on Gemini:
  - Connected during `gemini mcp list`: GitHub, Codacy, DeepSource, Codecov
  - Still inconsistent / follow-up required: Semgrep, SonarQube
- Claude already carries the same essential surface through a mix of explicit MCP config and enabled plugins, and Codex keeps the fuller canonical inventory in `config.toml`.

## Notes

- `.metaswarm/external-tools.yaml` was intentionally left untouched.
- The authoritative PATH change happened at the user level, not only in the current process.
- This snapshot is meant to document the workstation state, not to claim that every configured MCP is equally healthy on every CLI.
