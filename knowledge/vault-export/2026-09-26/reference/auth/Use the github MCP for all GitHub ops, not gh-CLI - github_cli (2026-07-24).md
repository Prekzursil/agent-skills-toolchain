---
title: Use the github MCP for all GitHub ops, not gh-CLI / github_cli (2026-07-24)
type: feedback
permalink: main/reference/auth/use-the-github-mcp-for-all-git-hub-ops-not-gh-cli-github-cli-2026-07-24
tags:
- github
- mcp
- auth
- workflow
- '2026-07-24'
---

Owner directive (2026-07-24, standing): **use the `github` MCP (mcp__github__*) for ALL GitHub operations — not the `gh` CLI, not `git push`, not the `github_cli` MCP.**

## Observations

- [feedback] Route every GitHub op through the `github` MCP. #github-mcp — create_branch / push_files / create_pull_request / pull_request_read / merge_pull_request etc. NOT `gh <cmd>` and NOT `git push`. **Why:** (a) the local git write auth is dead — GH_TOKEN is INVALID (401 Bad credentials, verified 2026-07-24; earlier GITHUB_LEGACY_TOKEN was read-only); (b) the `github_cli` MCP is failing to reconnect (`-32000`, seen in /mcp this session); (c) the `github` MCP is authenticated + working (get_me → Prekzursil). **How to apply:** for a branch push, get byte-exact LF content via `git show HEAD:<path>` (NOT the CRLF working tree), push_files in one commit, then VERIFY each pushed blob sha == local `git rev-parse HEAD:<path>` before trusting it (mcp-push2's #177 pattern). Reads via local git (show/rev-parse/log/diff) are still fine.

- [gotcha] Merge only after checking the FULL CI matrix. #ci-matrix — `pull_request_read method=get_check_runs` gives per-platform conclusions; a Linux-green fix can fail windows-latest (node-green != CI-green). Never merge a red/mixed PR. See [[Fan-out node is Linux-only — node-green != CI-green for cross-platform repos (2026-07-24)]].

## Relations
- relates_to [[GitHub auth- GITHUB_LEGACY_TOKEN is READ-ONLY for git (2026-07-24)]]
- relates_to [[Route workflow subagents through ANTHROPIC_API_KEY (2026-07-24)]]