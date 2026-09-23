# Repo guidance for Claude Code

## AgentBridge is RETIRED — do not follow the old protocol

This file previously carried an `<!-- AgentBridge:start -->` block instructing agents to
coordinate through AgentBridge and to call its MCP tools (`reply`, `get_messages`,
`get_budget`). **Those tools no longer exist.** AgentBridge was Windows-broken and was
disabled (`claude plugin disable agentbridge@agentbridge`); its daemon does not run. Acting
on the old instructions makes an agent call removed tools and wait for a peer that is not
listening — which is why the block was removed rather than left in place as history.

**Two rails replace it.** Both are documented, with setup and a verify-before-trust probe,
in the `multi-ai-mingle` skill (`skills/multi-ai-mingle/SKILL.md`):

1. **Fan-out (Claude to Codex).** The official `codex mcp-server` is mounted at user scope,
   so `mcp__codex__codex` / `mcp__codex__codex-reply` are native tools. Launch several in
   parallel for independent Codex threads; results return as ordinary tool results.
2. **Live peer channel.** `mcp_agent_mail` runs locally on `127.0.0.1:8812` for symmetric
   Claude/Codex messaging plus advisory file leases.

**Deprecation note, recorded 2026-09-02.** As of 2026-08-24 `codex mcp-server` is deprecated
upstream (the Codex docs now open with "use the Codex app server instead", as the hosted-models
hunt lens 12 recorded it). The mount is KEPT: lock L7 removes nothing before its replacement has
a receipt, so `mcp__codex__codex` / `mcp__codex__codex-reply` stay the autonomous fan-out rail
for now. The second, parallel path is the `codex-plugin-cc` route: Codex as a Claude Code plugin
exposing `/codex:*` slash commands, already registered in this repo as
`enabledPlugins."codex@openai-codex": true` with marketplace
`extraKnownMarketplaces.openai-codex.source.repo = "openai/codex-plugin-cc"` in
`agent-self/config/settings.json`, and as `[plugins."codex@openai-codex"]` plus
`[marketplaces.openai-codex]` (`source = "https://github.com/openai/codex-plugin-cc.git"`) in
`agent-self/config/codex/config.toml`. Slash commands are interactive, not autonomous fan-out.
The migration target for autonomous fan-out, later, is Codex app-server / ACP workers.

**Consequence worth knowing:** retiring AgentBridge also removed `get_budget`, so the
automated budget-pacing enforcement is gone. Budget pacing is now advisory and manual — see
`agent-self/config/CLAUDE.md`, which already records this.

## This repo has 178 checkouts on this box. Only two of them matter.

<!-- SSOT-WIRE:start -->

> **The GitHub remote is the SSOT for history; `~/source/ast-integrate` is the only checkout you
> EDIT and `~/source/agent-skills-toolchain` is the only checkout anything EXECUTES from — every
> other checkout is disposable scratch, so no config/task/hook/skill may reference one, and none
> may be retired until its work is on a pushed branch.**

Measured 2026-08-14: **178 checkouts across 168 object stores** — 9 linked worktrees, which share
a store and so cannot diverge in history, 168 independent clones, which can, and **1 severed
worktree** whose `.git` file still names a worktree admin dir that no longer exists, so every git
command inside it exits 128. 9 + 168 + 1 = 178. **132 of them
hold unpushed commits, dirty files or a staged index; 5 have no remote at all.** Three are named
by live harness config — one of which (`~/source/ast-harness-reconcile`, a registered Codex
local-project root) the inventory lists as a retire candidate, so check §3a before retiring
anything.

> **REFUTED 2026-08-14 (round 3), kept rather than deleted:** this paragraph used to end "5 have
> no remote at all, *so nothing in them is in git anywhere else*". The premise is right and the
> conclusion does not follow. Measured (§2c): those five hold **zero unique committed bytes** —
> three have their whole committed tree in the canonical store, two of them *only* after CRLF→LF
> normalisation, and two are 0-commit working copies with nothing committed to compare. A raw-SHA
> comparison calls 11,036 of those blobs missing and every one is a line-ending twin. Their real
> exposure is **uncommitted, not unpushed**: `~/source/_advver_M14/scratch` has no commits at all
> and carries thousands of untracked entries that are in no store anywhere.

> **REFUTED 2026-08-14 (round 4), kept rather than deleted:** the sentence above used to read
> "9 linked worktrees … and 168 independent clones", full stop. Every row in it was right and the
> arithmetic did not close: 9 + 168 = **177**, against a population of 178. One whole kind — the
> severed worktree — was missing from the sentence a future agent reads, and round 3 separately
> scored the classification DoD `178/178, two agreeing signals` when the measurement is **177**
> (`signals_agree` is False on that row and stays False; the third signal adds a verdict beside it
> rather than overwriting the record). The row is now classified `severed-worktree` in
> `command-center/ssot/population-classified.json`, which also carries a `kind_arithmetic` block
> that fails closed when the split stops adding up. Receipts:
> `command-center/ssot/apply_severed_resolution.py` and its 5-case red-proof
> `command-center/ssot/redproof_severed.py`.

The earlier figures **25** (2026-08-12/13) and **170** (round 1) are both REFUTED and kept in the
inventory's §0 with the defect that produced each: a name test standing in for an identity test,
then `merge-base --is-ancestor` compared `== 0`, which files rc=128 ("could not be asked") as
"no". Full table, per-checkout unique content and the inbound-reference scan:
`docs/ssot/SSOT-CLONE-INVENTORY.md`; the machine-readable classification of all 178 is
`command-center/ssot/population-classified.json`.

- **Creating:** always `git -C <intended repo> worktree add …`. Bare `git worktree add` resolves
  the repo from cwd and has already landed an agent in an unrelated project.
- **Retiring:** needs all four — no unique commits, `git status --porcelain -uall` empty, no
  worktree-local **staged index** (for a linked worktree; `git stash list` is store-level and can
  never be empty, so it is not the criterion), and zero inbound references. **Retire nothing on
  this list yet:** two checkouts hold files that exist nowhere else, one of them only in a staged
  index that `git worktree remove` destroys. That command also **follows junctions and deletes
  their targets**.
- **Never run a `worktree` subcommand from the Codex plugin cache.** Measured 2026-08-14:
  `~/.codex/plugins/cache/agent-skills-toolchain/agent-skills-toolchain/0.2.0/.git/worktrees/`
  holds 5 registrations and **3 are armed** — their `gitdir` names a directory that exists right
  now, including `~/source/ast-integrate` itself. A cache-side `worktree remove`/`prune` resolves
  those registrations against the real trees. Receipt:
  `command-center/ssot/r4-cache-worktrees.json`.
- **Before exiting a scratch worktree, push the branch.** Four real commits were stranded because
  agent worktrees had no push-before-exit step.

The live MCP fleet loads its entry points from the *executed* checkout, which tracks `main` only by
luck. Check that it has not fallen behind before trusting it:
`python command-center/ssot/ssot_drift_gate.py` (exit 1 = the running fleet is executing stale
bytes; it fails closed rather than reporting a clean fleet from a blind differ). This block is
itself gated — `command-center/ssot/ssot_wiring_check.py` fails CI if the rule above drifts from
the inventory or points at anything that no longer exists.

<!-- SSOT-WIRE:end -->

Repository conventions (structure, build and test commands, style, PR expectations) live in
[`AGENTS.md`](AGENTS.md).
