---
title: 'Harness learnings: generic monitor template + autofire infra + git-crypt plumbing
  + PowerShell CRLF (2026-07-13)'
type: guide
permalink: main/reference/harness/harness-learnings-generic-monitor-template-autofire-infra-git-crypt-plumbing-power-shell-crlf-2026-07-13
tags:
- harness
- monitor
- autofire
- git-crypt
- powershell
- gotcha
- reference
---

Durable harness/tooling learnings (2026-07-13 session).

## 1. Generic verbose-monitor template (protocol-driven)
`C:\Users\Prekzursil\.biomni-mcp\scw_monitor.ps1` is a reusable renderer driven by a tiny "monitor line protocol" — a collector emits `key=value` lines and one renderer draws them: `HEAD=<section>`, `GPU=i,util,mem,w`, `JOB=name,state,done,total,elapsedSec,detail` (state done|running|failed|pending; measured ETA from elapsed/done when detail empty), `BAR=label,pct`, `KV=label,value[,color]`, `NOTE=text[,color]`, `DONE=n,total`. So ONE template covers compute/agents/CI. A per-job collector (e.g. `a2d_translate.ps1` reformats the a2d box collector) feeds it. Satisfies the standing feedback "always build a verbose terminal monitor w/ progress bar + consistent ETA". Prior bug: `$ssh_output -match` on a string ARRAY doesn't set `$Matches` -> false ALL_DONE; fix = normalize to lines first.

## 2. Autofire monitor infra ALREADY EXISTS — extend, don't reinvent
- `hooks/workflow-monitor-autolaunch/check.py` (PreToolUse, matcher `Workflow`) auto-opens **wfmon** on a Claude Workflow.
- `/codex-monitor` (`~/.local/opt/mingle/monitor/launch.ps1`) = live Codex-thread dashboard (prompt/tools/tokens/status, reads `~/.codex/sessions/rollout-*.jsonl` + mingle relay) — the Codex collector was already built.
- `/agent-monitor` = Claude subagents + Workflow agents. `bg-registry/register.py` = durable bg-job ledger.
- NEW this session: `hooks/codex-monitor-autolaunch/check.py` (PreToolUse, matcher `mcp__codex__codex`) auto-opens codex-monitor on a native Codex launch — the Codex twin of the wfmon autofire. Fail-open, singleton lockfile, opt-out `CODEX_MONITOR_AUTOLAUNCH=off`.

## 3. git-crypt-safe commit (add files to a branch WITHOUT a checkout)
A `git worktree add` off main FAILS if the repo has git-crypt files (`accounts.json`) and the key is locked (`smudge filter git-crypt failed`). Sidestep with PURE PLUMBING (no working-tree write -> no smudge runs):
```
export GIT_INDEX_FILE=/tmp/x.index; git read-tree origin/main
blob=$(git hash-object -w file); git update-index --add --cacheinfo 100644,$blob,path/in/repo
tree=$(git write-tree); commit=$(git commit-tree $tree -p origin/main -F msg); git branch NAME $commit; git push origin NAME
```
`read-tree` (no `-u`) only loads index entries — never touches the working tree, so git-crypt is never invoked. Only the intended files change vs main.

## 4. Meta-principle: inspect the ACTUAL tool > web search (for harness/tool questions)
The authoritative answers this session came from the tools themselves, not the web: jaguar's own `jaguar_keywords.xml` (iacscf), `codex exec --help` (--json events), the existing hook files (autofire infra), `codex-monitor` (the built Codex viewer). tooluniverse was BROKEN (missing embedding deps) and perplexity UNAUTH — the bio MCPs don't help harness/QM-code questions. Check the installed source first.

## 5. PowerShell -> ssh CRLF footgun (re-confirmed)
Piping a here-string/file to native `ssh` re-adds CRLF EVEN AFTER a local `-replace "\`r\`n","\`n"` — PowerShell's native-stdin write re-CRLFs. Fixes: strip on the BOX side (`... | ssh box "cat > f && sed -i 's/\r//g' f && bash f"`) or pipe to `ssh box "bash -s"`. Also: the LAST line of a piped `bash -s` script often gets a trailing `\r` (`$'\r': command not found`) — put a harmless trailing line after the real last command, or `tr -d '\r' | bash`.

Related: [[feedback-always-build-a-verbose-terminal-monitor-progress-bar-consistent-eta-for-long-background-processes]], [[schrodinger-mcp-67-tool-upgrade-a2d-verbose-monitor-codex-wave-re-review-session-state-2026-07-13]].
