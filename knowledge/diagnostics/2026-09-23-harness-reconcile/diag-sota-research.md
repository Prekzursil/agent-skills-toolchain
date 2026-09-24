# Diagnosis wave — SOTA research lane (READ ONLY)

Date: 2026-09-23 · Machine: VM offload-w2025 · Author: diagnosis subagent
Scope: research SOTA patterns for VM<->home harness reconciliation, fold toward what THIS owner adopts.
Every claim tagged VERIFIED (path/command/output) or INFERRED. Web SOTA via Exa MCP (WebSearch budget was
already exhausted 200/200 this session; Tavily key returned Unauthorized). Single-source web claims tagged UNVERIFIED.

---

## HEADLINE: the "fixes you didn't apply" are the owner's OWN home settings.json

VERIFIED. The context-rot fix and the MCP fix the owner is angry about are NOT external designs to invent —
they already exist, wired, in home's `~/.claude/settings.json`, and are simply absent on the VM.

- VM `~/.claude/settings.json` = 724 bytes. Full content read: permissions + `defaultMode:bypassPermissions`
  + model + sandbox. NO `env`, NO `hooks`, NO `statusLine`, NO `skillListingBudgetFraction`,
  NO `ENABLE_TOOL_SEARCH`. (VERIFIED: `cat ~/.claude/settings.json`.)
- home `~/.claude/settings.json` = 26,038 bytes (VERIFIED: `rclone cat homeC:/Users/prekzursil/.claude/settings.json | wc -c`).
  Saved locally at `C:\Users\prekzursil\Documents\harness-reconcile-2026-09-23\home-settings.json`.
- The on-disk harness IS present on the VM already: `~/.agents/harness/dispatcher.py` = 28,962 bytes, dated
  Sep 2 (VERIFIED `ls -la`). It is just never invoked because VM settings.json has no `hooks` block.
- Command sets are already identical: 74 commands on VM, 74 on home (VERIFIED `ls | wc -l` both sides).

So the drift is almost entirely one file: `settings.json`. Everything it wires (harness dispatcher hooks,
statusline, the env caps) is dormant on disk. This is reconcile, not redesign.

### The exact context-rot / MCP controls present on home, absent on VM (VERIFIED from home-settings.json)

```
"skillListingBudgetFraction": 0.04          # caps skill-catalog injection (see nuance below)
"env": {
  "ENABLE_TOOL_SEARCH": "auto:5",           # defers MCP tool schemas behind ToolSearch -> the "MCP fix"
  "MAX_MCP_OUTPUT_TOKENS": "50000",          # caps a single MCP tool result
  "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "90",
  "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
  "BASH_MAX_OUTPUT_LENGTH": "150000",
  "MCP_TIMEOUT": "120000", "MCP_TOOL_TIMEOUT": "600000",
  "MCP_CLIENT_SESSION_TIMEOUT_SECONDS": "600",
  "ECC_CONTEXT_MONITOR_COST_WARNINGS": "0", "ECC_GATEGUARD": "off",
  "CLAUDE_CODE_FORK_SUBAGENT": "1", "CLAUDE_CODE_USE_POWERSHELL_TOOL": "1",
  "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1", "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "5",
  "CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN": "1", "CLAUDE_CODE_DISABLE_MOUSE": "1",
  "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
}
"hooks": {  SessionStart / PreToolUse / PostToolUse / PostToolUseFailure / PreCompact / Stop /
            SubagentStop / StopFailure / PreToolUse(no-force-push) / estate-deny / worktree hooks
            all -> python C:/Users/Prekzursil/.agents/harness/dispatcher.py --provider claude --event <E>
            plus local C:/Users/Prekzursil/.claude/hooks/_dispatch/dispatch.py }
"statusLine": { command: bash C:/Users/Prekzursil/.claude/statusline-command.sh, refreshInterval:30 }
```

The owner's memory index already names the ROOT CAUSE these settings fix:
- "Harness health verdict 2026-07-04": naive-sessions root cause = skills-context-budget overflow;
  fix = curated daily skills + vault lazy via router. (VERIFIED: line in MEMORY.md.)
- "Harness drift fix 2026-07-04": behaviour drift = calibrated-silence suppressing the router. (MEMORY.md.)

---

## Sub-question 1 — Keeping two machines coherent (settings/skills/MCP/memory) without drift

### External SOTA (Exa; each is one repo unless noted — treat as UNVERIFIED single-source patterns)
Three converging community patterns, all git-backed:

1. **Symlink/junction the live dir into a git repo** — davidblemay/bash-bastion (Windows-11-specific,
   published 2026-04). Real files live in a private git repo; NTFS **directory junctions** (`mklink /J`,
   no admin) for `commands/` and `skills/`, **file symlinks** (`mklink`, needs Developer Mode) for
   settings.json/CLAUDE.md/statusline. `config.sh` = single source of truth for path mappings; idempotent
   `setup.sh` recreates links on a new machine; `checkfilestatus.sh` gives 3 exit codes (0 OK / 1 integrity
   repair / 2 pending work). Junctions auto-capture NEW files too. This is the most robust Windows answer.
2. **Copy in/out via a sync repo + apply script** — jung-wan-kim/cc-sync-template, npm `cc-config-sync`
   (per-machine folders keyed by hostname, `pull`/`push` with diff+backup+`--non-interactive` for agents),
   elizabethfuentes12/claude-code-dotfiles (a `claude()` shell wrapper that `git pull` on open, `commit`+`push`
   on exit; explicit `.gitignore` **allowlist** so only CLAUDE.md/settings.json/commands/skills/hooks/agents/rules
   are versioned and cache/projects/secrets are excluded).
3. **`/loop 1d /cc-sync`** — schedule the export from inside a session (cc-sync-template).

Cross-cutting lessons all three encode: version settings.json + CLAUDE.md + commands + skills + hooks + rules;
NEVER version `projects/`, `plugins/cache/`, `history.jsonl`, secrets; concurrent pushes from 2 machines ->
`git pull --rebase` then push.

### Adopt-recommendation for THIS owner
The owner already HAS the canonical artifacts: `~/source/agent-skills-toolchain` (git repo, public on GitHub as
Prekzursil/agent-skills-toolchain) + `~/.agents` + the skill-tree tooling (`skill-tree-reconcile`,
`skill-stocktake`, `mcp-fleet-curation`, `mcp-no-drift-architecture` note). So DON'T adopt a third-party tool.
Instead:
- Make settings.json itself a tracked, machine-parameterized artifact in the toolchain repo with an
  idempotent **apply script** (the `install.py` already in `~/.agents/harness/` is the seed). One `apply`
  wires hooks+env+statusline on any machine. This is the bash-bastion `setup.sh` pattern using files the
  owner already owns.
- Keep the human paths identical (`C:/Users/Prekzursil/...`) so a single settings.json is portable as-is —
  which it already is (home paths are all under `C:/Users/Prekzursil`, valid on the VM too). VERIFIED: home
  hook commands reference `C:/Users/Prekzursil/.agents/harness/dispatcher.py`, which exists on the VM.
- For the "durable skill uploaded to GitHub" the owner wants: package this as a `harness-apply` /
  `two-machine-reconcile` skill in the toolchain — an idempotent applier + a `checkfilestatus`-style doctor
  that diffs VM vs home (over rclone `homeC:`/`homeD:`) and reports drift. That is the reproducible artifact.

---

## Sub-question 2 — Preventing context rot / token bloat in Claude Code (2026 SOTA)

### External SOTA (Exa — anthropics/claude-code issues + context-police; strong multi-source)
The mechanisms the owner's home config uses are exactly the documented levers, but 2026 has sharp nuances:

- **`ENABLE_TOOL_SEARCH` (MCP tool-schema deferral)** is the primary MCP-bloat lever. But:
  - `auto:N` uses a **percentage threshold that scales with context window**; on a 1M-context model `auto`
    silently moved the trigger from ~20K to ~100K tokens, "effectively disabling MCP deferral"
    (issue #39279, 2026-03). Workaround: `ENABLE_TOOL_SEARCH=true` or a low `auto:N` to FORCE deferral.
    -> The owner's `auto:5` is good but on a 1M Opus session may under-defer; `true` is the safe floor.
  - Tool Search **does not defer HTTP / Streamable-HTTP MCP tools** — all schemas load upfront, one report
    measured **120K tokens = 60% of a 200K window** before the first message (issue #40314). This matters
    enormously here: the VM's fleet has many HTTP MCP servers (cloud-hub, social-hub, search-hub, zai, etc.).
    Deferral alone will NOT gate those; they must be **disabled per-project** when unused.
  - CAUTION (issue #90113, versions 2.1.220+): repeated `tool_search_tool_regex` calls can INFLATE the
    reported token count (up to 4.5x) and trigger a **false "Context limit reached"** that forces /compact
    and destroys plan/TODO state. So tool-search is both the fix and, on buggy versions, a failure mode —
    pin/verify the CLI version.
- **`skillListingBudgetFraction`** caps the skill catalog injected every turn. Default is **0.01 (1%)**.
  context-police (measured on a ~925-skill catalog) warns that RAISING this fraction is an **anti-pattern**:
  it pays the full ~100K+ token catalog bill every turn and burns rate limits. The owner's home value is
  **0.04 (4%)** — 4x the default. HONEST FLAG for the implementation wave: 0.04 is a deliberate trade
  (with hundreds of skills the 1% default drops most descriptions to names-only, losing routing info per
  issue #64606), but it is NOT free — it re-injects a large catalog every turn and is multiplied across
  subagents. The aligned SOTA is the OPPOSITE direction: keep the fraction low and SHRINK the catalog via
  `disable-model-invocation: true` on episodic "trap" skills (keeps them `/name`- and rg-invocable) — which
  is exactly what the owner's `mcp-fleet-curation` / skill-curation notes already prescribe. Also relevant:
  `skillListingMaxDescChars` (default 1536) and the undocumented `SLASH_COMMAND_TOOL_CHAR_BUDGET` env.
- Retrieval-hook-as-catalog-replacement was TESTED TO GROUND AND KILLED (context-police): a keyword/embedding
  hook to surface only relevant skills fires on ~99.6% of turns; genuine-trap moments are ~0.1% base rate, so
  precision-when-firing is <0.4%. Lesson: curation + grep-on-task-start beats any always-on retrieval hook.

### Adopt-recommendation for THIS owner
1. On the VM, adopt home's caps but harden the two weak spots: consider `ENABLE_TOOL_SEARCH:"true"` (force,
   not `auto`) given the large HTTP-MCP fleet, AND curate the fleet per-project (the owner's own
   `.mcp-disabled-defaults.json` / `mcp-no-drift-architecture`). Deferral + curation together, not either alone.
2. Re-examine `skillListingBudgetFraction:0.04`: verify with `/context` and `/doctor` whether 4% is paying its
   way vs. `0.01` + a `disable-model-invocation` curation sweep. Do NOT reflexively copy 0.04 to the VM without
   measuring — it may be re-importing bloat. (This is the one place "copy home verbatim" could regress usage.)
3. Wire the harness router (dispatcher.py) so skills/vault load lazily on demand — the owner's documented fix.
4. Pin/track the CLI version to dodge the #90113 false-context-limit regression.

---

## Sub-question 3 — Ensuring committed work is pushed and not abandoned

### External SOTA (Exa — dedicated tools, multi-source)
- **pendector** (Go CLI): scans many repos for uncommitted + **unpushed** commits, shows remote sync status,
  JSON output for CI, Slack webhook, cron for daily alerts.
- **git-remind** / **nailgun/unpushed**: scan all repos on the box for ahead-of-remote commits + uncommitted
  files, desktop notification, cron-driven (`*/10 18-20 * * *`). `unpushed` uses `locate(1)` or a tree walk.
- **DavidCanHelp/GitWell**: surfaces ABANDONED work specifically — stale branches (unmerged, 30+ days,
  ahead/behind counts), orphan commits in reflog, stashes, WIP-marker commits — and installs a **post-commit
  hook** (managed block, preserves existing hook) that nudges only when abandoned work piles up. `triage` +
  `execute --confirm` (dry-run by default) to resume/archive/delete. This is the closest to the owner's need.
- **Push-Guard** (VS Code ext): periodic + on-close reminders to push. Editor-scoped, less relevant to a CLI/agent flow.

### What home already has vs. the gap (VERIFIED from home-settings.json)
Home wires a **`no-force-push` PreToolUse hook** (`~/.claude/hooks/no-force-push/hook.py`) and an **estate-deny**
hook (NEVER-ROTATE / private-repo / secrets / force-push), plus a **Stop** hook chain (harness dispatcher +
local `_dispatch/dispatch.py stop`), and the metaswarm `finishing-a-development-branch` + `/self-reflect` +
`claude-reflect` plugin flow. But: NO grep in home settings found a hook that flags **unpushed commits / stale
draft PRs** (searched push|commit|reflect|unpush|abandon). The owner's stated failure — "committed but never
pushed, nobody checks, work gets abandoned" — is a REAL GAP even on the fully-wired home machine. INFERRED but
consistent with the owner's own memory notes ("stale tracking ref", "orphaned deferral").

### Adopt-recommendation for THIS owner
Build a small **push-guard harness module** (this is the durable skill/module to upload to
Prekzursil/agent-skills-toolchain, satisfying the owner's "durable, reproducible" ask):
- A **Stop / SubagentStop hook** (the harness already fires Stop) that runs `git status`-style checks across the
  owner's repos and emits a terminal-state marker if HEAD is ahead of upstream or a draft PR is stale — the
  GitWell/pendector logic reimplemented as one Python module under `~/.agents/harness/` so it deploys to BOTH
  machines via the same dispatcher wiring. Read-only nag by default (never auto-push per §9 / no force-push).
- A scheduled sweep (Windows Scheduled Task or `/loop 1d`) mirroring pendector's cron: daily "unpushed +
  stale-branch + WIP-marker" report over `~/source` on each machine, cross-checked VM<->home over rclone so a
  commit made on one box that never reached origin is caught by the other.
- Because both machines can read each other's disk (rclone `homeC:`/`homeD:`), the sweep can also diff
  local-only commits that exist on one box but not the other or origin — directly the owner's "discrepancies /
  mirrors / lack of data / coordination" ask.

---

## Bonus — home disk data now readable for CV/resume + other in-flight research

VERIFIED (rclone lsf/lsd against `homeC:`/`homeD:`), home holds real user data the VM lacked:
- `homeD:/basic-memory/` — the LIVE semantic vault with MANY notes (agents/, bolt/, battlecats/, ast-integrate/,
  dated .md notes). The VM's basic-memory DAEMON is down and its `~/.basic-memory` config/db is absent, so the
  VM cannot query memory; home's vault is now directly readable as markdown over rclone for recall.
- `homeC:/Users/prekzursil/` — `RESEARCH_PHENIBUT/`, `Daria_proiect/`, `bc154_research/`, `Downloads/`,
  `Documents/`, `Desktop/`, plus `Downloads_sort_plan.csv`.
- CV/resume SPECIFIC: a shallow scan of `homeC:/Users/prekzursil/Documents/` and `Desktop/` found NO obvious
  cv/resume/career/cover file at depth <=2 (VERIFIED: grep returned nothing). So the owner's "expanded venue of
  research for CV" is UNVERIFIED as a discrete folder — but the `cv-studio` skill exists, and the ADDITIONAL
  data now available is the home research corpus above + the D: basic-memory vault. Recommendation: a deeper
  targeted scan (name + content) for CV artifacts is worth one implementation-wave step; do not assert a CV
  dataset exists until found.

---

## Sources (web, via Exa MCP — WebSearch budget exhausted 200/200; Tavily key Unauthorized)
- anthropics/claude-code issue #39279 — ENABLE_TOOL_SEARCH=auto threshold scales to 100K on 1M context
- anthropics/claude-code issue #40314 — Tool Search does not defer HTTP MCP tools (120K upfront)
- anthropics/claude-code issue #64606 — skillListingBudgetFraction silently truncates skill routing
- anthropics/claude-code issue #90113 — tool_search_tool_regex inflates count -> false Context limit reached
- github.com/wan-huiyan/context-police — measured skills-catalog token tax; curation > raising the fraction
- github.com/davidblemay/bash-bastion — Windows-11 symlink/junction git-backed Claude config
- github.com/jung-wan-kim/cc-sync-template ; npmjs cc-config-sync ; github.com/elizabethfuentes12/claude-code-dotfiles — git sync patterns
- github.com/thaim/pendector ; javijuol/git-remind ; nailgun/unpushed ; DavidCanHelp/GitWell ; trynafindbhumik/Push-Guard — unpushed/abandoned-work detection
