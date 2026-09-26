---
title: 'GitHub auth: GITHUB_LEGACY_TOKEN is READ-ONLY for git (2026-07-24)'
type: reference
permalink: main/reference/auth/git-hub-auth-github-legacy-token-is-read-only-for-git-2026-07-24
tags:
- github
- auth
- token
- git
- push
- read-only
---

Owner instruction 2026-07-24: "use GITHUB_LEGACY_TOKEN everywhere from now on." Tested it. Verdict below.

## Observations

- [api_behavior] `GITHUB_LEGACY_TOKEN` (40-char classic-PAT shape) authenticates git READS but NOT writes. #read-only-token — `git ls-remote`/`fetch` succeed (exit 0) via GIT_ASKPASS with username=`Prekzursil`, password=token; but `git push` (any ref, incl. a throwaway probe ref) fails `Invalid username or token. Password authentication is not supported`. Same remote URL, same token — pure read-vs-write scope split. So the token lacks `repo`/`contents:write` (or is a read-only fine-grained PAT).

- [gotcha] The working READ auth form is username=`Prekzursil` + token-as-password, NOT `x-access-token`. #git-askpass — `x-access-token` is the GitHub-App-installation-token convention and fails for a classic PAT. Use a GIT_ASKPASS script: `case "$1" in *Username*) echo Prekzursil;; *Password*) printf %s "$GITHUB_LEGACY_TOKEN";; esac`.

- [decision] For GitHub WRITES (push/merge/PR-create) neither raw git nor GITHUB_LEGACY_TOKEN works this session; the paths are: (a) the GitHub MCP (mcp__github__push_files / create_pull_request — it has its OWN valid write auth, confirmed via get_me as Prekzursil) — but MCP-push AGENTS kept dying on the account 5h session cap; (b) owner runs `! gh auth login` / provides a write-scoped token; (c) do the write from the MAIN session via the GitHub MCP directly (not a spawned agent) to avoid the per-agent cap. #github-write-path — Prefer (c): call mcp__github__* from the main loop, not a subagent, for pushes.

- [pattern] A read-succeeds/write-fails split is a SCOPE signal, not a bug — probe write explicitly with a throwaway ref before assuming a token can push. #scope-probe — corroborates [[single-signal-verification]]: ls-remote green is NOT evidence the token can push.

## Relations
- relates_to [[Git push blocked by invalid github_pat_ - use GitHub MCP push_files (2026-07-24)]]
