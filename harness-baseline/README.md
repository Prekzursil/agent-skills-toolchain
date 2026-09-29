# harness-baseline — the `~/.claude` minimal baseline

**Problem.** `~/.claude` is **14.218 GB** and is **not a git repo**
(`git -C ~/.claude rev-parse --is-inside-work-tree` → `fatal: not a git repository`).
Version control was being done by hand with dated sidecar files: **83 backup-shaped files in the
authored config** (5 shadowing `settings.json`, 3 shadowing `AGENTS-RUNTIME.md`, 3 shadowing
`hooks/_dispatch/manifest.json`). That gives no history, no diff, no blame, no revert, and no
protection against the one failure that actually happened before: *work existing only on the
disposable VM.*

**Why not just `git init ~/.claude`.** 99.94% of that tree is not authored: `plugins/` 11.2 GB of
re-fetchable third-party clones, `projects/` 2.75 GB of session transcripts, 514 MB of
false-positive-recovery archives. Measured, the authored-and-irreplaceable set is
**452 files / 6.58 MB — 0.045% of the tree.**

**Approach.** Name that 0.045% in a manifest and copy it into `~/.agents`, which *is*
version-controlled (`origin https://github.com/Prekzursil/agent-skills-toolchain.git`).

```
~/.agents/harness-baseline/
  baseline-manifest.txt   <- what counts as authored, and why each exclusion is excluded
  dot-claude/             <- the copy, mirroring ~/.claude's layout
  README.md               <- this file
~/.agents/scripts/backup-claude-baseline.ps1   <- the tool
```

## Refresh the baseline

```powershell
# inspect first
pwsh -NoProfile -File ~/.agents/scripts/backup-claude-baseline.ps1 -DryRun
# then copy
pwsh -NoProfile -File ~/.agents/scripts/backup-claude-baseline.ps1
# commit (the script never commits - that is deliberate)
git -C ~/.agents add harness-baseline
git -C ~/.agents commit -m "harness-baseline: refresh ~/.claude authored set"
git -C ~/.agents push
```

Exit 0 + `SUCCESS:baseline DONE` is the only success. Any non-zero exit means a gate refused —
read the stage, do not re-run blindly.

## The three gates, and why each exists

| Gate | Refuses | Why it is there |
|---|---|---|
| **CRED** | credential stores (`.credentials.json`, `*.pem`, `*.key`, `id_ed25519`, `.env`, `*-credentials.json`, `*token*.json` …) | `~/.agents` has a GitHub remote. Reading credentials locally is ordinary estate work; **pushing one is not**. Enforced twice: on selection, and as a post-copy sweep of the destination. |
| **IGNORE** | any copied path that `git check-ignore` matches | **The gate that earns its keep.** `~/.agents/.gitignore` ignores `backups/`, `deploy-backups/` and `*.bak-*`. A backup written to the obvious place is *invisible to git* — it looks done and is not. |
| **DEST** | a destination resolving outside the repo root | stops a bad `-DestRel` writing anywhere on disk. |

`-SelfTest` is the both-states proof (17 assertions): each gate must FIRE on deliberately broken
input and PASS on good input. Run it after any edit to the script.

```powershell
pwsh -NoProfile -File ~/.agents/scripts/backup-claude-baseline.ps1 -SelfTest
```

### Two defects the gates caught on the first real runs — kept here as precedent

1. **IGNORE fired on `hooks/recall-gate/state/*`** (3 files). `state/` is git-ignored, so those
   would have been copied and silently dropped. They are regenerable hook state; the manifest now
   denies `**/state/**`. *A gate failing loudly beat a backup passing quietly.*
2. **CRED over-blocked the credential GUARD.** The first version matched the bare substring
   `credential`, which dropped
   `hooks/deny-credential-reads/{deny.py,test_deny.py,test_denylist_coverage.py,test_guard_scope.py}`
   — the source of the hook that *blocks* credential reads — because its **directory name**
   contains the word. A baseline that omits its own security guard is worse than no baseline.
   The heuristic is now anchored to the file name and exempts source/doc extensions, with a
   dedicated regression case (`-SelfTest` case 6). `~/.agents/.gitignore` needed a matching narrow
   re-include, added only after verifying those four files hold **0** high-entropy tokens.

## Bootstrap: rebuild `~/.claude` config on a fresh machine

This restores **config only**. Plugins, transcripts and caches are deliberately not here.

```powershell
# 0. prerequisites: git, pwsh 7, Claude Code installed once (so ~/.claude exists)
git clone https://github.com/Prekzursil/agent-skills-toolchain.git $env:USERPROFILE\.agents
cd $env:USERPROFILE\.agents

# 1. STOP every Claude session first. settings.json and hooks are read at session start,
#    and ~/.claude.json is rewritten continuously by live sessions.
Get-Process claude -ErrorAction SilentlyContinue   # must be empty

# 2. restore the authored config
Copy-Item -Path harness-baseline\dot-claude\* -Destination $env:USERPROFILE\.claude\ -Recurse -Force

# 3. deploy the authored trees that have their own SSOT (do NOT hand-edit the deployed copies)
pwsh -NoProfile -File scripts\sync-rules.ps1          # ~/.agents/rules/common -> ~/.claude/rules/common
python scripts\deploy-skills-daily.py                 # ~/.agents/skills       -> ~/.claude/skills

# 4. re-supply what is deliberately NOT in the baseline
#    - credentials: log in again (`claude` will prompt). NEVER restore a credential from a repo.
#    - plugins: `claude plugin` re-adds marketplaces; clones re-fetch from public remotes.
#    - ~/.claude.json: machine-local MCP registry. NOT in the baseline. Re-add MCP servers at
#      USER scope (`claude mcp add --scope user ...`); never hand-edit per-tree copies.

# 5. verify
pwsh -NoProfile -File scripts\backup-claude-baseline.ps1 -DryRun   # selection count should match
pwsh -NoProfile -File scripts\lint-rules-loading.ps1               # authored+deployed both hold
```

## What this is NOT

- **Not a backup of `~/.claude` as a whole.** By design. Transcripts and plugin clones are out.
- **Not the SSOT for rules or skills.** `~/.agents/rules/` and `~/.agents/skills/` are authored;
  `~/.claude/rules/` and `~/.claude/skills/` are *deploy targets*. The copies under
  `dot-claude/rules/` exist as a **drift detector** — if they differ from `~/.agents/rules/`, the
  deploy is stale. Never hand-edit them.
- **Not a reason to delete the 83 `.bak` files.** They are inventoried, not removed, at
  `knowledge/gemhunt-impl-2026-09-25/hygiene-bak-inventory.txt`. Once a few commits of real
  history exist here, they become redundant — that is the owner's call, not the script's.
- **Not automatic.** No hook, no scheduled task, no per-turn cost. It runs when invoked.
