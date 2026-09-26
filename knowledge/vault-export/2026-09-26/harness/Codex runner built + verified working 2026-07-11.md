---
title: Codex runner built + verified working 2026-07-11
type: note
permalink: main/harness/codex-runner-built-verified-working-2026-07-11
tags:
- codex
- github-actions
- autonomous-agents
- verified
- agent-skills-toolchain
---

# Codex runner built + verified working 2026-07-11

⭐ Built + **verified end-to-end** the private-host "codex-runner" (agent-skills-toolchain PRs #66 + #67, merged). One private repo drives OpenAI Codex against ANY of the owner's repos on the ChatGPT-subscription `auth.json` (no API key), opening propose-only PRs. Resolves the owner's ask "use codex via auth.json, run on all repos."

## Architecture
`.github/workflows/codex-runner.yml` in `agent-skills-toolchain` (PRIVATE host). `workflow_dispatch` inputs (target_repo, task, base_branch, model). Two owner-set secrets: `CODEX_AUTH_JSON` (piped `~/.codex/auth.json` contents) + `CODEX_RUNNER_PAT` (fine-grained, contents+PR write on targets). Flow: rebuild auth.json → `codex exec` → checkout target via PAT → open PR. One private host works the whole fleet; the credential never touches a public repo.

## ⭐ KEY reusable learning — Codex sandbox in CI
`codex exec` under the default sandbox FAILED to write files in the GitHub runner: *"the workspace sandbox rejected all write attempts with a permissions error"* — **Codex's bubblewrap sandbox can't set up inside the runner**. Fix (PR #67): `codex exec --dangerously-bypass-approvals-and-sandbox` + config `sandbox_mode="danger-full-access"`. Safe because the runner is ephemeral+isolated (matches the owner's local config). Also: `--full-auto` is deprecated → `--sandbox`; the owner's model slug `gpt-5.6-sol` WORKS in CI (no 400); npm-pin `@openai/codex@0.144.1`.

## Verified
A smoke run (target=env-inspector, model=gpt-5.6-sol, "create a file") reconstructed the ChatGPT-sub auth, checked out via PAT, ran codex exec which wrote the file, and **opened a real PR** (since closed). Full pipeline green.

## Broader context
Owner's active repos are PUBLIC; OpenAI FORBIDS auth.json-in-Actions on public repos (fork-PR exfil of the whole ChatGPT account) → the private control-repo pattern is the safe way to use sub-auth across public repos. The strictly-secretless alternative is the Codex Cloud GitHub App. See [[Autonomous Codex on GitHub - decision brief 2026-07-11]]. First YAML bug: multi-line PR body at column 0 broke the `run:` block (use printf + --body-file).
