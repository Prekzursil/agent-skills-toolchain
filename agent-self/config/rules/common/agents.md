---
title: agents
type: note
permalink: dqverify-repo-20261013/agent-self/config/rules/common/agents
---

# Agent Orchestration

The agent roster is injected live every session — read it; do NOT keep a static list (it drifts). Route via `/start-task`; prefer parallel subagents for independent work + split-role reviewers (senior / security / consistency) for high-stakes calls. Subagent-handoff contract: AGENTS.md §5.

## This rule has install dependencies — copying `rules/common` alone does not satisfy them

Both names above are separate artifacts that the documented common-rules install does **not**
deploy. `rules/README.md:56-57` installs common rules with `cp -r rules/common
~/.claude/rules/common`, and `scripts/sync-rules.ps1:48-68` likewise copies only the Markdown
files under `rules/common/`. Neither ships a command file or an `AGENTS.md`. On a clean profile
the rule is therefore active and tells the agent to route via `/start-task` and honour
`AGENTS.md §5`, while both targets are absent — the router cannot resolve and the handoff
contract cannot be read.

Install these alongside the rule, or the two references above are dangling:

| Reference | Source in this repo | Install to |
|---|---|---|
| `/start-task` | `commands/start-task.md` | `~/.claude/commands/start-task.md` |
| `AGENTS.md §5` | `agent-self/config/AGENTS.md` | `~/.claude/AGENTS.md` |

**Not the repository-root `AGENTS.md`.** That file is the contributor guide and has no §5;
`scripts/build-codespace-mirror.py:206-213` records that the harness contract lives at
`agent-self/config/AGENTS.md`. `scripts/bootstrap-codespace.sh:31-39` installs rules, commands
and agents together but copies the root `AGENTS.md` at `:95-98`, so that path broadens the
deployment without resolving the §5 dependency. `agent-self/bootstrap.ps1:26-28` deploys the
whole of `agent-self/config/`, which does carry all three.

**Verify after install, don't assume:** a rule that names a route is only as good as the route.
Confirm `~/.claude/commands/start-task.md` and a `~/.claude/AGENTS.md` containing a §5 both
exist before treating this rule as in force.