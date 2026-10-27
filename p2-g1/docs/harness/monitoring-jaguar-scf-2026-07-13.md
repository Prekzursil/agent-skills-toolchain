# Harness monitoring + Jaguar SCF knowledge (2026-07-13)

Knowledge gained hardening the phenibut compute + observability harness. Companion to the
`scripts/monitors/` templates and `hooks/codex-monitor-autolaunch/` added in the same change.

## Generic verbose-monitor template (protocol-driven)

`scripts/monitors/scw_monitor.ps1` is a reusable renderer driven by a small **monitor line
protocol** — any collector emits `key=value` lines and one renderer draws them:

| Line | Renders |
|---|---|
| `HEAD=<section>` | section header + rule |
| `GPU=i,util,mem,w` | GPU bar + sparkline (per-i history) + power |
| `JOB=name,state,done,total,elapsedSec,detail` | job row: progress grid, state color (done=green, running=cyan, **failed=red ✗**, pending=gray), **measured ETA** from `elapsed/done` when `detail` is empty |
| `BAR=label,pct` | labeled progress bar |
| `KV=label,value[,color]` | key/value metric |
| `NOTE=text[,color]` | note line |
| `DONE=n,total` | overall; terminal when `n>=total` AND no running/pending job |

One renderer therefore covers GPU/HPC compute, agent/LLM workflows, and CI. A per-job collector
emits the protocol (e.g. `a2d_translate.ps1` reformats the box-side `mon_collect_a2d.sh` output).
Satisfies the standing feedback: *always build a verbose terminal monitor with a progress bar and
a consistent ETA for long background processes.*

**Robustness bug fixed:** `$ssh_output -match ...` where `$ssh_output` is a string **array**
never populates `$Matches` → a false `ALL_DONE`. Normalize to lines first
(`@($raw) | %{ $_ -split "\`n" } | %{ $_.TrimEnd("\`r") }`).

## Native autofire — extend the existing infra, don't reinvent

The harness already surfaces long-running work natively:

- `hooks/workflow-monitor-autolaunch` (PreToolUse, matcher `Workflow`) auto-opens **wfmon**.
- `/codex-monitor` (`~/.local/opt/mingle/monitor/launch.ps1`) — live Codex-thread dashboard
  (prompt / tool-calls / tokens+ctx% / turns / status), reading `~/.codex/sessions/rollout-*.jsonl`
  + the mingle relay. **The Codex "collector" was already built.**
- `/agent-monitor` — Claude subagents + Workflow agents. `bg-registry/register.py` — durable
  background-job ledger.

**Added:** `hooks/codex-monitor-autolaunch/check.py` (PreToolUse, matcher `mcp__codex__codex`) —
auto-opens codex-monitor on a native Codex launch, the Codex twin of the wfmon autofire. Fail-open,
per-session singleton lockfile, opt-out `CODEX_MONITOR_AUTOLAUNCH=off`. Wired as a standalone
`settings.json` PreToolUse entry (mirrors the `workflow-monitor-autolaunch` wiring).
*Follow-up:* register it in the shared harness generator (`.agents/harness/install.py`) so a
reinstall keeps it (same residual as the other local hooks).

## Jaguar oscillatory-SCF failure → `iacscf=2`

Large charged QM clusters (~150-atom pocket+ligand, `molchg=-1`, B97-3c single-point) can die with
`ERROR 2256` / `SCF convergence failure: Maximum number of iterations reached` — the default
`maxit=48` is exhausted while the energy oscillates (±1–29 Ha). The shared `pocket` job is the worst
to lose (IE = E(cluster) − E(ligand) − E(pocket)).

**Authoritative fix** (from `$SCHRODINGER/mmshare-*/data/jaguar/jaguar_keywords.xml`, not a guess):
add `iacscf=2` (+ raise `maxit`) to `&gen`. `iacscf=2` = "start with vshift 6.0, decrease over 12
iterations to 0.8, raise vshift on restart" — jaguar's own dynamic level-shift ramp, better than a
static `vshift`. Escalation: `iacscf=4` (ultrafine + max analytic). Verified: smooth monotonic
convergence (Δenergy 6.3E-2 → 3.1E-3) vs the original oscillation. Read true QM job state from
`_qm_results.log` `DONE_<job>_exit_<code>` (exit 3 = SCF fail) + the live `.out` "completed on".

## Meta-principle + a footgun

- **Inspect the actual tool > web search** for harness/tool-specific questions: jaguar's own keyword
  XML, `codex exec --help`, the hook files, and `codex-monitor` all beat web research (tooluniverse
  was dependency-broken; perplexity unauthenticated).
- **PowerShell → ssh CRLF:** piping to native `ssh` re-adds CRLF even after a local strip. Strip on
  the box side (`... | ssh box "cat > f && sed -i 's/\r//g' f && bash f"`) or pipe to `bash -s`.

## git-crypt-safe commit (how this change landed)

`git worktree add` off main fails when git-crypt is locked (`smudge filter git-crypt failed` on
`accounts.json`). Add files via pure plumbing — no working-tree write, so the smudge filter never
runs: `GIT_INDEX_FILE=… git read-tree origin/main` → `git hash-object -w` → `git update-index
--add --cacheinfo` → `git write-tree` → `git commit-tree -p origin/main` → `git branch` → push.
