# SSOT clone inventory — agent-skills-toolchain

**Lane:** SSOT (grounding). **Measured:** 2026-08-12, 19:40–21:00 local. **Read-only.**
**Nothing was deleted, and nothing may be deleted from this document alone — every RETIRE below
is a recommendation with a named precondition.**

COVERAGE: questions 1–4 all measured against the **full 25-checkout fleet**. Residuals in §7.

> If it still reads this way, the unit died before measuring anything and no verdict here may be
> cited. (It did not — every row carries a measured value.)

---

## 0. Headline — the count is wrong three times over, and the count is not the problem

| source | claimed | reality |
|---|---|---|
| owner ("nine separate clones") | 9 | subset |
| `REPO-TOPOLOGY.md` (2026-08-09) | "9 local checkouts / 2 stores" | a **different** nine; 2 of its entries no longer exist |
| this lane, first pass (hand-written lists) | 14 / 8 stores | still an undercount |
| **exhaustive filesystem sweep (911 git checkouts walked)** | **25 checkouts / 18 object stores** | measured |

Both prior documents landing on "9" is coincidence, not corroboration. I only got the right number
by refusing to trust either list and walking the filesystem — the first pass gave 14 and I had
labelled that *likely (55–80%) complete*, which was correctly calibrated and still wrong.

**The clone count is not the SSOT defect.** Two things actually matter:

1. **Edit ≠ execute.** `~/source/ast-integrate` holds `main` and is where all editing happens.
   `~/source/agent-skills-toolchain` is permanently detached (git forbids two checkouts of `main`),
   sits **159 commits behind** `origin/main`, and is where **five live MCP servers** load code from.
   Correctly scoped: the drift is **latent, not active** — `git diff 53c37c6c..ae8205a4` over the
   five directories the fleet actually loads returns **0 changed files**. Nothing is broken today.
   The hazard is that the *next* commit under `tools/mcp/**` silently never reaches the running
   fleet. (likely, 55–80% — reasoned from the mechanism, no observed failure.)
2. **Four commits of real authored work are stranded** in agent scratch worktrees that no config,
   task, hook or skill references, and that nobody enumerated until this sweep (§2).

---

## 1. Q1 — worktree vs clone, by measurement

Two mechanically independent signals, agreeing on all 25: (a) `.git` FILE (linked worktree) vs DIR;
(b) `git rev-parse --path-format=absolute --git-common-dir`. A third, `objects/info/alternates`,
was empty everywhere. **25 checkouts, 18 object stores.**

| store | checkouts |
|---|---|
| **A** `~/source/agent-skills-toolchain/.git` | 5 — canonical (detached), `ast-integrate` (main), `ast-harness-reconcile`, `D:/inc1-wt/ast-increment1`, `D:/wt-salvage-probe` |
| **B** `~/source/ast-patch167/.git` | 3 — `ast-patch167`, `_verify_M04_tree`, `_verify_M13` |
| **C** `~/Documents/Playground/.git` | 2 — `Documents/Playground`, `~/.codex/worktrees/8528/Playground` |
| 15 further stores | 1 checkout each (list in `command-center/ssot/all25.json`) |

Store B's `origin/main` is pinned at `07f465f`. **Never measure a baseline there.**

**`~/.claude/codexsrc-work` and `~/.claude/tw-merge-work` are `--local` hardlink clones** whose
`origin` is the canonical *filesystem path*, not GitHub. Verified independently with
`fsutil hardlink list`: `pack-205947e4….pack` is **one inode with three hardlinks** across canonical
and both clones. Two consequences — their disk cost is double-counted, and their "modified today
11:26" mtime is canonical's pack seen through a shared inode, **not activity in them.** I nearly
reported those two as live.

---

## 2. Q2 — unique content (the finding that matters)

Method: per store, `git rev-list --all --reflog` (reflog included, so orphaned/amended work is
caught), `git cat-file --batch-check` against **every one of the other 17 stores**, then intersected
with "not reachable from any tip in `git ls-remote origin`".

**Detector controls, both states:** fabricated SHA → absent; canonical's own HEAD → present; and a
**real commit from an unrelated repo** (`qzp-lean` HEAD `3187b8a2`) → correctly absent. The third is
the load-bearing one: it proves the detector sees genuine absence of a real object.

### Stores holding commits that exist nowhere else and are not on the remote

| store / checkout | count | what it is |
|---|---|---|
| `.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | **2** | `feat(mcp-manager): dead-MCP detector with graded, citable evidence` (2026-07-18, ×2) |
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | **1** | `fix(mcpctl): strip control bytes BEFORE redacting` (2026-07-27) — plus 7 dirty files |
| `source/_wu/CRCP-SEC` | **1** | `fix(crcp): scope the OpenAI bearer to an allowlist of OpenAI hosts` (2026-07-29) — **a security fix** |
| store A (canonical) | **6** | 1 real unpushed commit on `main` (today), 1 orphaned `c165fe3d` (2026-08-10, reflog-only, in no ref), 1 checkpoint, 3 stash/index commits |
| store B (`ast-patch167`) | **3** | `d9ec177`, `be60f18`, `6451b18` — the M04/M13 verify commits |
| `work/agent-skills-toolchain-re` | **3** | 2026-03-31 RE-skills commits, reflog-only orphans |

**Four of these are genuine authored work — two features, a bugfix and a security fix — sitting in
scratch/salvage worktrees with zero inbound references.** That is the fleet's real data-loss
exposure, and it is not in either prior document.

**A claim I had to retract mid-lane.** `ast-patch167` HEAD is byte-identical to the remote tip of
`fix/deny-credential-gaps`, which made "store B is fully pushed" look right. `merge-base
--is-ancestor` (control: root→HEAD True, HEAD→root False) shows **0 of its 8 store-unique commits
are ancestors of that tip**. `REPO-TOPOLOGY.md` content-verified the `pr242/244/245/249` lineage as
redundant; it does **not** cover the three verify commits (§7 R2).

**Earlier count corrected.** My first pass reported 13 unpushed commits on store A's `refs/heads/*`.
Against all 18 stores the store-unique figure is 6 — the difference is commits replicated into
`harness-restore/wave3/ast-cc`, `scratch/ast-gp-main` and the plugin cache. Replicated locally is
**not** the same as safe; it only means deleting store A alone would not lose them.

### Uncommitted work — my first pass under-counted every row

`REPO-TOPOLOGY.md` detector-note 3 says `git status --porcelain` collapses untracked directories and
you must pass `-uall`. **I read that note and then failed to apply it.** Corrected:

| checkout | `-u normal` (wrong) | `-uall` (correct) |
|---|---|---|
| `~/Documents/Playground` | 2 | **111** |
| `~/source/ast-integrate` | 137 | **298** |
| `~/.claude/codexsrc-work` | 52 | **81** |
| `~/source/ast-patch167` | 1 | **8** |
| `.codex/plugins/cache/…/0.2.0` | not measured | **57** + 1 stash |
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | not measured | **7** |

**Fleet total: 567 uncommitted files across 25 checkouts.**

---

## 3. Q3 — inbound references

use-vs-mention applied at the **field** level, not the document level. No line from a
credential-bearing file was ever printed.

### Nothing schedules, PATHs, or env-references any checkout

- **Scheduled Tasks: 0 hits across 330 task-actions** (`Execute` / `Arguments` / `WorkingDirectory`).
  **Control, both states:** the same scanner finds `mcp_agent_mail`, `MCPAgentMail` and `Prekzursil`
  in that task set and correctly misses a fabricated string — so the silence is meaningful. This
  **refutes**, for this repo, the briefed premise that a scheduled task is registered against a
  disposable worktree. Scoped: action fields only; a task running a wrapper script that internally
  `cd`s into a checkout is invisible to this probe (§7 R3).
- **PATH (User + Machine): 0. Environment variables: 0.**

### The 8 load-bearing references — every one points at `~/source/agent-skills-toolchain`

| consumer | field | breaks if the path moves |
|---|---|---|
| `~/.mcp.json` | `.mcpServers.{cloud-hub,social-hub,search-hub}.args[0]` | 3 MCP servers |
| `~/.claude.json` | `.mcpServers.qdx-rush.args[2]`, `.mcpServers.scholarly-access.command` | 2 MCP servers |
| `~/.codex/config.toml:201` | `command = …/tools/scholarly-access-mcp/.venv/Scripts/….exe` | Codex MCP |
| `~/.codex/config.toml:475` | `[projects.'…agent-skills-toolchain']` | Codex trust entry |
| `~/.claude/settings.local.json` | `.permissions.allow[30..33]` | 4 permission grants |
| `~/.agents/skills/crcp-health/crcp_health_monitor.cmd:3` | `set "CRP=%USERPROFILE%\source\…\tools\crcp"` | CRCP health monitor |
| `~/.local/opt/mcp-http-host/run_host.ps1:59` | `[string]$Repo = "$HOME\source\agent-skills-toolchain"` | MCP HTTP host default |
| `~/.claude/workflows/reconcile-all-branches-prs-imporant.js:12` | `const TC = 'C:/…/agent-skills-toolchain'` | that workflow |

`~/.codex/config.toml:319`/`:968` additionally register `~/Documents/Playground` as a trusted Codex
project.

**Soft, degrading — the only reference to `ast-integrate`:**
`~/.claude/skills/claude-science-local/cs_monitor.py:52` (and its `.agents` twin) lists
`ast-integrate/scripts/claude-science/cs.ps1` as the **third fallback** in a candidate list and
returns `None` if all three miss.

**Correctly excluded as mentions** — `~/.agents/harness/modules.py:1036` (the path is inside a
*warning-message string*), two `~/.claude/workflows/*.js` prose templates, and ~200
`.codex/plugins/cache/**` archived audit JSON. A naive "executable extension ⇒ dependency" rule
scored **208** hits for canonical; field-level resolution reduces it to **8**.

**Referenced by nothing at all: 23 of 25 checkouts.**

---

## 4. Verdicts

**KEEP (2)** — `~/source/agent-skills-toolchain` (8 load-bearing refs; 2 dirty are `accounts.json`,
the live rotation pool — do not touch) and `~/source/ast-integrate` (holds `main`).

**RECONCILE BEFORE ANYTHING ELSE (8)** — hold unique commits and/or substantial uncommitted work:

| checkout | why |
|---|---|
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | 1 unique unpushed bugfix + 7 dirty |
| `.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | 2 unique unpushed feature commits |
| `source/_wu/CRCP-SEC` | 1 unique unpushed **security** fix |
| `.claude/codexsrc-work` | 81 uncommitted, all under `tools/editor/metaswarm/` |
| `~/Documents/Playground` | 111 uncommitted; separate repo with its own worktree |
| `.codex/plugins/cache/…/0.2.0` | 57 dirty + 1 stash + the §7 R4 hazard |
| `source/ast-patch167` (store B, 3 checkouts) | 3 unique unpushed verify commits + 8 dirty |
| `work/agent-skills-toolchain-re` | 3 reflog-only orphans, frozen since 2026-04-01 |

**RETIRE CANDIDATES — clean, zero unique commits, zero inbound references (11):**
`~/.claude/toolchain-audit` (dead since 2026-07-14) · `~/.claude/tw-merge-work` ·
`D:/sast-depth/agent-skills-toolchain` · `~/source/ast-harness-reconcile` ·
`~/.claude/scratch/ast-gp-main` · `~/.claude/harness-restore-20260806/wave3/ast-cc` ·
`~/source/_cons/C8/tc` · `~/source/_verify/v-l01` · `D:/pr-b3-clone` ·
`~/source/_verify_M04_tree` · `~/source/_verify_M13` · `~/.codex/worktrees/8528/Playground`.
Two more are nearly clean and need a one-file triage first: `D:/inc1-wt/ast-increment1` (1
untracked) and `D:/wt-salvage-probe` (**2 staged-but-uncommitted adds** — a staged index is
per-worktree and is destroyed with the worktree).

---

## 5. Q4 — the SSOT rule

> **The GitHub remote is the SSOT for history; `~/source/ast-integrate` is the only checkout you
> EDIT and `~/source/agent-skills-toolchain` is the only checkout anything EXECUTES from — every
> other checkout is disposable scratch, so no config/task/hook/skill may reference one, and none may
> be retired until its work is on a pushed branch.**

Mechanically checkable corollaries:

1. **Creating:** always `git -C <intended repo> worktree add …`. Bare `git worktree add` resolves
   the repo from cwd and has already landed agents in an unrelated project (`REPO-TOPOLOGY.md` r5).
2. **Retiring:** requires all four — `unique_commit_count == 0`, `git status --porcelain -uall`
   empty, `git stash list` empty, zero field-level inbound references. Produced by
   `measure_all25.py` + `scan_inbound_refs.py`.
3. **Scratch belongs on a pushed branch or it does not exist.** Four real commits were stranded
   precisely because agent worktrees had no push-before-exit step.

---

## 6. Prior art — read this before rebuilding anything

- **`REPO-TOPOLOGY.md`** (repo root) — still the best narrative. Correct and reusable: the
  two-store model, why the main checkout can never hold `main`, the squash-merge/ancestry warning,
  the `git archive` CRLF trap, the `-uall` note, the "identical blob counts prove nothing" note.
  **Stale in three places** this lane corrected: the checkout list (2 gone, 11 unfound), "2 stores"
  (18), and the store-B redundancy claim (3 verify commits uncovered).
- **`command-center/ssot/orchestrator-clone-probe.md`** — the orchestrator's narrow existence probe;
  explicitly defers Q1–Q4 to this lane. Consistent with everything here.
- Do **not** rebuild: worktree tooling already exists at `tools/gitcrypt-worktree/`, and
  `platform/workflows/worktree-isolated-parallel-build.json` already encodes isolated-worktree runs.

---

## 7. Residuals — each with the experiment that settles it

- **R1 — CLOSED.** The exhaustive sweep finished: 911 git checkouts walked under `~` and `D:/`,
  25 belong to this repo. Depth cap 7 and `AppData`/`node_modules` excluded, so a checkout nested
  deeper or inside `AppData` would still be missed (**almost certain (90–99%)** that 25 is complete
  for the scanned scope).
- **R2 — store B's three verify commits are not content-checked.** `REPO-TOPOLOGY.md` verified
  `pr242/244/245/249` byte-for-byte; `d9ec177`, `be60f18`, `6451b18` were not in that table.
  **Settle:** `git -C ast-patch167 diff <sha>^..<sha> --name-only`, then compare each path against
  `git -C ast-integrate cat-file -p origin/main:<path>` — never `git archive` (CRLF on this box).
- **R3 — scheduled-task indirection.** Action fields only. **Settle:** extract each task's
  `Execute`+`Arguments` script path and grep those files' contents.
- **R4 — the Codex plugin cache holds a COPY of canonical's worktree admin dir.**
  `.codex/plugins/cache/…/0.2.0/.git/worktrees/{ast-integrate,ast-harness-reconcile,ast-increment1,
  ast-statusline-capture,cookie-bridge-skill}/gitdir` point at the **real live directories**. The
  link is one-directional — the real `ast-integrate/.git` points back at canonical, not the cache —
  so the registration is stale. Whether `git -C <cache> worktree remove ast-integrate` would delete
  the real tree is **UNVERIFIED**; the probe is destructive and I did not run it. **Settle:** test
  it against a throwaway worktree, never a live one. Until then, never run a `worktree` subcommand
  from the plugin cache.
- **R5 — `git worktree remove` follows junctions.** Carried from the orchestrator brief (measured
  2026-08-10). Not independently re-verified — destructive by nature. I did measure that **no
  checkout root holds a junction/reparse point at depth 1** (`FILE_ATTRIBUTE_REPARSE_POINT` 0x400),
  so the hazard is not armed at the top level; deeper levels unscanned. **Settle:**
  `fsutil reparsepoint query` over a tree before removal, or move the directory aside instead.
- **R6 — snapshot, not steady state.** `main` advanced during this lane (`ae8205a4` → `9353ed1f`,
  now 1 ahead of the remote) and `ast-integrate` grew 137 → 298 dirty. Re-run before acting.
- **R7 — disk is only measured for 12 of 25** (3.31 GB, itself an over-count because of the shared
  hardlinked packs). Disk is not the argument here; drift and split-brain are.

---

## 8. Reproduce — all read-only, in `command-center/ssot/`

| script | answers |
|---|---|
| `sweep_all_checkouts.py` | the authoritative 25/18 enumeration → `full-sweep.json` |
| `measure_all25.py` | Q1 + Q2 for the full fleet, `-uall` → `all25.json` |
| `measure_clones.py` / `measure_unique_depth.py` | first-pass 14-checkout detail + remote decomposition |
| `report_pass3.py` | origin URLs, unpushed decomposition, dirty detail |
| `scan_inbound_refs.py` → `verify_refs.py` | Q3 raw hits, then detector controls + field resolution |
| `storeb_safety.py` | store-B ancestry, with both-states ancestor control |
| `exec_vs_edit.py` | executed-vs-edited drift → `exec-vs-edit.json` |
