# Git hygiene audit — unpushed / abandoned work (VM + HOME)
Diagnosis wave, READ-ONLY. 2026-09-23. All claims VERIFIED unless marked INFERRED.

## Method notes (VERIFIED)
- VM repos found: `find -L ~/source /d -maxdepth 5 -type d -name .git` plus a broader depth-6 sweep
  under `~/.agents`, `~/.local/opt/*`. Commands run via Bash tool with `dangerouslyDisableSandbox:true`
  and PowerShell, both agreeing, to rule out the session's `C:\suite\payload` overlay as an artifact.
- `gh` CLI is **not installed** on the VM (not on PATH, no `gh.exe` found under `C:\Program Files*` or
  `~`). PR data instead pulled via unauthenticated GitHub REST API (`api.github.com`, public repo) —
  sufficient for state/read but cannot see private review threads.
- HOME cannot be reached with a shell; read via `rclone cat/lsf/lsd` against `homeC:` (SFTP remote) on
  `.git/HEAD`, `.git/refs/heads`, `.git/FETCH_HEAD`, `.git/worktrees/*` per the harness's instruction.
  This gives ref pointers, not `git status`/diff — dirty-file counts on HOME are NOT assessed (would
  need a live HOME session).

## CRITICAL — VM's canonical toolchain checkout is a broken/empty git repo
`C:\Users\prekzursil\source\agent-skills-toolchain\.git` **exists but is completely empty** (0 entries
under `.git`, confirmed 3 independent ways: Bash `ls -la`/`find`, `cmd.exe /c dir`, PowerShell
`Get-ChildItem -Force` — all show zero children, no `HEAD`, no `config`, no `objects`). `git status`
there fails `fatal: not a git repository`. This is VERIFIED, not a sandbox artifact (same result with
sandbox disabled, real path `C:\suite\payload\Users\Prekzursil\source\agent-skills-toolchain`).
**This means the VM literally cannot answer "ahead/behind vs upstream" for the toolchain repo at that
path today** — there is no git history to compare. Compare: HOME's `~/source/agent-skills-toolchain/.git`
is a full, healthy repo (objects/refs/worktrees/index all present).
`.coverage-thresholds.json` memory note said "~/source/agent-skills-toolchain is present" — presence of
files ≠ presence of git metadata; this file tree is a **working-copy checkout with no VCS memory**, so
any local edits made against this exact path (not `~/.agents`, see below) are unversioned right now.

## The repo that actually IS the live git state on the VM: `~/.agents`
`C:\Users\prekzursil\.agents` (`~/.agents` — the skills vault) is a healthy clone of the same GitHub
repo (`origin = https://github.com/Prekzursil/agent-skills-toolchain.git`). This is the one that
matters for "is committed work at risk."

| Item | VM (`~/.agents`) | HOME (`~/.agents`, via rclone ref-read) |
|---|---|---|
| HEAD branch | `live-capture/2026-09-02` | `live-capture/2026-09-02` (same — `refs/heads` listing matches: `ideas/unfinished-consolidated`, `live-capture/2026-09-02`, `main`, `reconcile/ssot-2026-08-28`, `wip/harness-additions-2026-08-28`) |
| `live-capture/2026-09-02` vs `origin/live-capture/2026-09-02` | **0 ahead / 0 behind** (`git rev-list --left-right --count`) — no unpushed commits on the checked-out branch | not independently checked (would need HOME's FETCH state vs its own HEAD; ref pointer alone doesn't give ahead/behind) |
| Working tree | **163 dirty entries**: 67 modified, 21 deleted, 75 untracked (`git status --porcelain`) — includes edits across `AGENTS.md`, `agents.json`, ~40 `skills/microsoft-foundry/**` files, and ~25 new untracked `skills/azure-*`, `skills/biomni-local`, `skills/delegate-primitive`, `skills/exa-search`, `skills/zai-lanes`, `skills/voice-cloning-sota`, plus scratch/report files (`GRILL-DECISIONS_*`, `HARNESS-COMMIT-PLAN_*`, `PROGRAM-REPORT_2026-09-22.md`) | not assessed (no shell) |
| `wip/harness-additions-2026-08-28` | local branch **2 commits ahead** of `origin/wip/harness-additions-2026-08-28`: `f9fa6582 docs: harden provider-neutral harness design`, `c01f45cb docs: define provider-neutral harness control plane`. **No open PR exists for this branch** (checked GitHub API by head ref — 0 results). This is genuinely committed-but-unpushed, on-topic for exactly what this task is about (harness design), and currently invisible to any PR-based recovery. | same branch present in HOME's `refs/heads` listing — could be the origin of these commits, or a second independent copy; cannot tell without a HOME `git log` |
| `ideas/unfinished-consolidated` | local branch, **no upstream** (`for-each-ref` shows blank upstream), last commit `c3cde97b` 2026-08-28 "chore: version control-plane SSOT" | present in HOME too |
| `reconcile/ssot-2026-08-28`, `main` | tracked, even with their `origin/*` refs | present in HOME too |

**Risk:** 163 uncommitted files on the VM's live vault is the single largest amount of at-risk work
found in this audit. None of it is "pushed and lost" in the git sense (nothing here is committed yet),
but it is exactly the kind of work a VM wipe/reimage would destroy outright, with zero recovery path
(not even a local commit to `git fsck --lost-found` from).

## Other VM git repos (`~/.local/opt/*`, vendored tool forks)
| Repo | Branch | Ahead/behind | Dirty | Notes |
|---|---|---|---|---|
| `.local/opt/hexstrike-ai` | `master` (tracks `origin/master`) | even | 9 dirty (1 modified `hexstrike_server.py`, 8 untracked incl. `.venv/`, log files) | fork of `0x4m4/hexstrike-ai`; modified core file uncommitted |
| `.local/opt/mitmproxy-mcp` | `main` (tracks `origin/main`) | even | 1 dirty (`uv.lock` modified) | low risk |
| `.local/opt/cheatengine-mcp-bridge` | **detached HEAD**, no branch | n/a (`HEAD does not point to a branch`) | 4 untracked (`.venv/`, `__pycache__/`, `autorun-bootstrap.log`, `ce_cmd.py`) | fork of `miscusi-peek/cheatengine-mcp-bridge`; `ce_cmd.py` looks like real untracked work sitting on a detached HEAD — one `git checkout` away from being orphaned if HEAD moves |
| `~/source/open-coscientist` | **detached HEAD** at `00db65c` (2026-02-25, `jataware/open-coscientist` upstream, 7 months stale) | n/a | 1 untracked (`mcp_server_stdio.py`) | looks like a reference/vendored checkout, not active work; low risk |

## HOME's toolchain checkout (`~/source/agent-skills-toolchain`) — ref-level only
- `HEAD` → `refs/heads/cursor/p2-loop-to-green-0db0` — matches **open draft PR #325** "P2 loop-to-green:
  orchestrator + IMP-0434 wave 1" (last updated 2026-09-20). HOME is mid-session on this branch.
- **`index.lock` present, 0 bytes, timestamped 2026-09-22 22:22:16** — i.e. from the day before this
  audit. A leftover `index.lock` blocks any `git` write (commit/checkout/merge) on that worktree until
  removed; VERIFIED present via `rclone lsl`, age is the only evidence of staleness (could equally be a
  git process still legitimately running on HOME right now — cannot tell without a live HOME session).
  **Flag this for the owner to check on HOME directly** — if stale, it is silently blocking commits.
- 7 worktrees registered under `.git/worktrees/`, spread across three separate roots (`C:\Users\
  Prekzursil\source\`, `...\agent-skills-toolchain\.worktrees\`, and `D:\`) — each its own working
  copy, each capable of holding independent uncommitted/unpushed state that this audit could not see:
  | worktree name | branch / commit | path |
  |---|---|---|
  | `ast-docspr` | **detached** at `097df497` | `C:\Users\Prekzursil\source\ast-docspr` |
  | `ast-harness-reconcile` | `chore/enshrine-runtime-config` | `C:\Users\Prekzursil\source\ast-harness-reconcile` |
  | `ast-increment1` | `feat/variant4-increment1-dbx-monitor-20260721` | `D:\inc1-wt\ast-increment1` |
  | `ci-expansion-w1` | `feat/tool-registry-governance` | `...\agent-skills-toolchain\.worktrees\ci-expansion-w1` |
  | `consult-offsec-wave` | `consult-offsec-registration` | `...\agent-skills-toolchain\.worktrees\consult-offsec-wave` (↔ open PR #320) |
  | `search-hub-pr310` | **detached** at `46f6dd2e` | `D:\opt\search-hub-pr310` (↔ open PR #310) |
  | `wt-salvage-probe` | `salvage/codex-profiles-config-lint` | `D:\wt-salvage-probe` |
  None of these were `git status`-checked (no HOME shell); each is a candidate for uncommitted work at
  rest. Two detached-HEAD worktrees (`ast-docspr`, `search-hub-pr310`) are notable — a stray `checkout`
  in that worktree orphans the commit with no branch pointing at it.

## Open/draft PRs on `Prekzursil/agent-skills-toolchain` (GitHub API, unauthenticated, state=open) — 39 total
Most-stale-and-substantive first (age as of 2026-09-23):

| PR | Age (days) | Draft | Title | Branch |
|---|---|---|---|---|
| #310 | 21 | no | search-hub reunion, self-hosted decision record | `cursor/search-stack-reunion-self-hosted-9cde` |
| #311 | 21 | no | Estate process-hygiene supervisor (Windows) — chronic [fix] | `cursor/system-resource-hygiene-4a5e` |
| #312 | 17 | no | mcp-control-plane: carry live test lineage | `chore/reunite-mcp-control-plane-live-tests` |
| #314 | 21 | no | gem-hunt: hosted-models — 13 lenses, consolidated decision | `gemhunt/hosted-models-00-consolidated` |
| #326–#335 | 15–17 | **yes (9 of 10 are draft)** | IMP-0004/0007/0009/0010/0062 independent review / blocked-impl chain | `cursor/imp-00xx-*-0db0` |
| #321 | 19 | yes | Add fleet autonomy pointer to QZP SSOT | `cursor/fleet-autonomy-pointer-4739` |
| #323 | 16 | yes | Maintainer session 2026-09-06: CI outage re-measure | `cursor/maintainer-session-2026-09-06-0db0` |
| #315/#317–319/#322/#324 | 17–20 | no | cyberstrike, ZCode SSOT, grok stop-hook, lineage-path fixes | various |
| #325 | 3 | yes | **P2 loop-to-green** (matches HOME's current checked-out branch — active, not abandoned) | `cursor/p2-loop-to-green-0db0` |
| #336 | <1 | no | qwen38-heretic Space grill decision log | `grill/qwen38-heretic-space-2026-09-19` |
| #339–#348 | 2 | no | 10x dependabot dependency bumps (routine, low-value noise) | `dependabot/*` |
| #350, #351 | <1–1 | no | remove git-crypt filters; statusline token-HUD | active, recent |

**13 draft `cursor/imp-00xx-*` PRs (Sep 6-8, 15-17 days stale)** are the largest coherent block of
possibly-abandoned work: a chain of "independent review (PASS/FAIL)" and "BLOCKED implementer wave"
PRs for what looks like an adversarial-review pipeline (IMP-0004, 0007, 0009, 0010, 0062). None merged,
none closed — sitting exactly where "nobody remembers to check if committed stuff is pushed and not
abandoned" bites hardest, since they already ARE pushed (real PRs, real commits on GitHub) but nobody
converted them to merged or explicitly closed them.

**Confirmed abandoned (closed, unmerged) recently, GitHub API `state=closed`, sorted by update:**
- **#352** "[codex] save byte-identical AGENTS.md pedestal" — closed 2026-09-23, **not merged**
  (matches the harness's own note that #352 was closed). Branch `codex/golden-agents-pedestal`.
- #282, #291, #283, #281 — closed unmerged, dated in the 2026-09-02 batch (could be legitimate
  supersedes from that reconciliation wave, not necessarily lost work — not read in detail, flagged
  only as candidates; INFERRED that these need no recovery given the surrounding wave merged 20+
  siblings same day).

## Ranked risk summary (most-valuable-at-risk first)
1. **VM `~/.agents` — 163 uncommitted files**, including the live `AGENTS.md`/`agents.json` control
   files and ~25 new untracked skills (azure-*, biomni-local, delegate-primitive, exa-search,
   zai-lanes, voice-cloning-sota). Zero recovery if VM disk is lost. **Highest-value, highest-risk.**
2. **`wip/harness-additions-2026-08-28`** — 2 commits, harness-design docs, pushed nowhere, no PR.
   Directly on-topic for "wire the harness." Cheapest to save (just needs a push + PR).
3. **HOME `index.lock`** (0-byte, dated 2026-09-22 22:22) — possible silent commit-blocker on HOME's
   toolchain checkout right now; owner should check it directly (stale lock vs. live process).
4. **13 stale draft `cursor/imp-00xx-*` PRs** (Sep 6-8) — already pushed/safe on GitHub, but need a
   merge/close decision so they stop being invisible technical debt.
5. **7 HOME worktrees** spread across `C:\...\source\`, `.worktrees\`, and `D:\` — each an unverified
   pocket of possible uncommitted state; 2 are on detached HEAD (`ast-docspr`, `search-hub-pr310`).
6. **`~/.local/opt/hexstrike-ai`** — 1 modified core file (`hexstrike_server.py`) never committed to
   the fork; low value but a real local patch that would be lost on a re-clone.
7. **`~/.local/opt/cheatengine-mcp-bridge`** — detached HEAD, untracked `ce_cmd.py`; one checkout away
   from orphaning.
8. #310/#311/#312/#314 and the 2026-09-03/06 batch — 21-day-old substantive open PRs (search-hub,
   process-hygiene supervisor, mcp-control-plane, gem-hunt) — pushed and safe, just un-triaged.

## What this audit could NOT determine (explicitly out of scope / no access)
- HOME's actual working-tree dirty state (modified/untracked files) for ANY of its repos or 7
  worktrees — no HOME shell, rclone only exposes committed git-object/ref state.
- Whether the 13 draft `cursor/imp-*` PRs are still wanted or intentionally shelved — content not read.
- Whether HOME's `index.lock` is stale or a live in-progress git operation.
