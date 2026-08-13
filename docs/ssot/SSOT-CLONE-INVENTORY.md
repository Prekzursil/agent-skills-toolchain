# SSOT clone inventory — agent-skills-toolchain

**Lane:** SSOT. **Measured:** 2026-08-12 19:40–21:00, extended 2026-08-13 (BUILD round 1: §2b
content check, the §5 retire-criterion correction, R8). **Read-only against every checkout.**
**Nothing was deleted, and nothing may be deleted from this document alone — every RETIRE below
is a recommendation with a named precondition.**

COVERAGE: questions 1–4 all measured against the **full 25-checkout fleet**. §2b content-checks
the stranded work in 4 locations (not all 25 — the other 21 hold no object-unique commits).
Residuals in §7; the three claims corrected on 2026-08-13 are marked inline where they occur,
with the refuted wording kept rather than deleted.

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
2. **Some — not all — of the stranded scratch work is genuinely the only copy.** Four commits are
   object-unique (§2). A content check (§2b, added 2026-08-13) shows object-uniqueness and content-
   uniqueness are different things: the CRCP security fix is byte-identical on `main` and is
   **redundant**, while 5 files across two other locations exist **nowhere on `main`**. The real
   exposure is those 5 files plus one DIVERGED set needing judgement — smaller than "four commits"
   and sharper.

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
scratch/salvage worktrees with zero inbound references.**

> **REFUTED WORDING, kept so the dead end is not re-walked.** This section originally continued:
> *"That is the fleet's real data-loss exposure."* The commit-OBJECT measurement above is correct
> and stands. The sentence was wider than its evidence: object-uniqueness is not content-
> uniqueness, and under squash-merge a fully-merged change keeps a unique SHA forever
> (`REPO-TOPOLOGY.md` rule 4 — which this document cited and then failed to apply to the scratch
> worktrees). §2b measures the content and supersedes the claim.

**A claim I had to retract mid-lane.** `ast-patch167` HEAD is byte-identical to the remote tip of
`fix/deny-credential-gaps`, which made "store B is fully pushed" look right. `merge-base
--is-ancestor` (control: root→HEAD True, HEAD→root False) shows **0 of its 8 store-unique commits
are ancestors of that tip**. `REPO-TOPOLOGY.md` content-verified the `pr242/244/245/249` lineage as
redundant; it does **not** cover the three verify commits (§7 R2).

**Earlier count corrected.** My first pass reported 13 unpushed commits on store A's `refs/heads/*`.
Against all 18 stores the store-unique figure is 6 — the difference is commits replicated into
`harness-restore/wave3/ast-cc`, `scratch/ast-gp-main` and the plugin cache. Replicated locally is
**not** the same as safe; it only means deleting store A alone would not lose them.

---

## 2b. Content check of the stranded work — added 2026-08-13, BUILD round 1

Method: for every path in each stranded commit, compare the scratch blob against
`origin/main` and classify **bidirectionally** — `ABSENT` / `DIVERGED` (both sides hold unique
lines) / `MAIN_IS_SUPERSET` / `IDENTICAL`. Bidirectional by construction because the one-
directional read ("does scratch have extra lines?") is the measured systematic blind spot:
31 of 47 agent misclassifications were DIVERGED read as safe, and **100% of those errors
pointed at data loss** (`fan-out-contract` §C.D4). Blobs read with `git cat-file -p`, never
`git archive` (CRLF on this box); compared LF-normalised so a pure line-ending delta is not
reported as divergence. Script: `command-center/ssot/content_check.py` → `content-check.json`.

**Detector controls, both states.** Blob reader: a real tree path returns content, a
fabricated path returns `None` (a reader that returned empty for everything would mark every
file ABSENT and manufacture a fleet-wide false alarm). The `IDENTICAL`/`MAIN_IS_SUPERSET`
verdicts — the only ones that could authorise a deletion — were then re-checked by a
**mechanically independent second signal**: git's own SHA-1 blob identity via `git hash-object`
on raw bytes, sharing no code path with the line-set comparison
(`_verify_identical.py` → `verify-identical.json`, control: same-file MATCH, two different real
files DIFFER). **5 of 5 corroborated.**

| location | commit subject | verdict | measured |
|---|---|---|---|
| `source/_wu/CRCP-SEC` | `fix(crcp): scope the OpenAI bearer to an allowlist` | **REDUNDANT** | `auth.py`, `sentinel.py` and **both proving tests byte-identical** on main (12,608 B / 13,487 B / 13,094 B / 10,569 B, sizes equal on both sides); `auth_broker.py` MAIN_IS_SUPERSET (0 scratch-only lines). The 2 DIVERGED files are `quality.yml` (**+689 main-only** — main evolved, scratch is stale) and `__main__.py` (+2/-13). |
| `agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | `feat(mcp-manager): dead-MCP detector` | **UNIQUE — preserve** | `core/health.py`, `mcp_health.py`, `tests/test_health.py` — all three **ABSENT from main** |
| `agent-worktrees-salvage/agent-425276811/ast` | `fix(mcpctl): strip control bytes BEFORE redacting` | **DIVERGED — needs judgement** | all 5 files diverge, incl. `mcpctl/safety.py` (+17 scratch-only / +11 main-only) and 3 test files. Not settled in either direction. |
| `D:/wt-salvage-probe` | *staged index, never committed* | **UNIQUE — preserve, highest urgency** | `ci/tests/test_codex_profiles.py` and `tools/monitorcore/r0_monitor_live_gate.py`, **both ABSENT from main** |

**Consequences.**

1. **The CRCP security fix is not at risk** — it is on `main`, twice-verified. **Almost certain
   (90–99%).** Any plan that reconciles it first is spending effort on a solved problem.
2. **`D:/wt-salvage-probe` is the sharpest hazard in the fleet**, and §4 under-rated it as "needs a
   one-file triage". It holds 2 files that exist nowhere on `main`, in a **staged index** — and a
   staged index is per-worktree and **is destroyed by `git worktree remove`**, unlike the shared
   stash (§5 note). Triage it before any retirement work.
3. **`_b5-toolchain`'s 3 files are genuinely absent** — which independently confirms the
   `tools/mcp-manager/` "42 files on main, 42 in the commit" reading was a **3-for-3 swap, not
   parity**. Equal counts on both sides is the classic collection-level tell, not evidence of
   redundancy. The correct verdict is *superseded parallel implementation*: main solves the same
   capability via `core/claude_adapter.py` + `core/models.py`; whether b5's graded-evidence logic
   holds behaviour main lacks is a judgement call, **UNVERIFIED** — settle by diffing the grading
   logic against main's detector, not by counting files.
4. **The mcpctl fix is the one genuinely open item.** *Correctly scoped:* line-set divergence does
   **not** prove main is missing capability — main may have evolved past the scratch form. It only
   proves the two are not the same text. **UNVERIFIED** whether any scratch-only behaviour is
   absent from main; settle by running the scratch test files against main's `safety.py`.

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

**Priority within this list was re-ordered 2026-08-13 by the §2b content check — the original
ordering put a solved problem first.** Correct order of attention: `D:/wt-salvage-probe` (2 files
absent from main, in a destroyable staged index) → `_b5-toolchain` (3 files absent) →
`agent-425276811/ast` (DIVERGED, needs judgement) → everything else. `CRCP-SEC` drops off the
reconcile list entirely.

| checkout | why |
|---|---|
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | 1 unique unpushed bugfix + 7 dirty — §2b: all 5 files **DIVERGED**, needs judgement |
| `.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | 2 unique unpushed feature commits — §2b: 3 files **ABSENT from main**, genuinely the only copy |
| ~~`source/_wu/CRCP-SEC`~~ | **NO LONGER RECONCILE WORK.** §2b measured the fix byte-identical on `main` (both proving tests included), corroborated by an independent hash signal. Reclassify as a RETIRE candidate once its 2 stale DIVERGED files (`quality.yml` is **689 lines behind** main) are confirmed unwanted. |
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
Two more need triage first: `D:/inc1-wt/ast-increment1` (1 untracked) and — **upgraded
2026-08-13 from "nearly clean" to the fleet's highest-urgency item** — `D:/wt-salvage-probe`.
Its **2 staged-but-uncommitted adds** are `ci/tests/test_codex_profiles.py` and
`tools/monitorcore/r0_monitor_live_gate.py`, and §2b measured **both ABSENT from `main`**: this
is real authored content that exists in exactly one place, held in a staged index that
`git worktree remove` destroys. It is **not** a retire candidate until those two files are
committed to a pushed branch or copied out.

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
   empty, **no worktree-local staged index or stash entry** (see the correction below), zero
   field-level inbound references. Produced by `measure_all25.py` + `scan_inbound_refs.py`.

   > **CORRECTED 2026-08-13 — the original third precondition was `git stash list` empty, which
   > can NEVER pass for a linked worktree and contradicted this document's own retire list.**
   > `refs/stash` is **store-level, not worktree-level**: all **five** store-A checkouts report
   > stash-count 2 and the *identical* `refs/stash` = `d90474213cca...` — canonical,
   > `ast-integrate`, `ast-harness-reconcile`, `D:/inc1-wt/ast-increment1` and
   > `D:/wt-salvage-probe`. So the criterion was simultaneously false for every store-A
   > checkout, including `ast-harness-reconcile`, which §4 lists as a RETIRE candidate. Error
   > direction was SAFE (a false blocker, never a false permission), but the rule was unusable.
   > **The right criterion splits by kind**, because removing a worktree destroys its *index*
   > and not the shared stash:
   > - **independent clone** → `git stash list` empty (the stash is its own).
   > - **linked worktree** → `git diff --cached --quiet` (empty index) **and** no reflog-only
   >   commits unique to that worktree. Measured: `staged` genuinely differs per worktree
   >   (0 / 3 / 0 / 0 / 2 across the five), so the index is the discriminating signal and the
   >   stash is not.
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
- **R6 — snapshot, not steady state. Every count in this document is a snapshot and several have
  already moved.** `main` took five values across one evening: `ae8205a4` → `9353ed1f` →
  `86dde6c1` → `f5b596e6` (local, 5 ahead of the remote) → `df6377ab` (this document's own
  commit). `ast-integrate` dirty `-uall` went 137 → 298 → 341 → 327. Canonical's "159 behind"
  read 161 within the hour. **Re-run `measure_all25.py` before acting on any number here** — and
  do not treat a changed count as a contradiction of this document.
- **R8 — CLOSED 2026-08-13: this document and its receipts were untracked.** Measured before the
  fix, with working controls (`git ls-files docs/` = 185, `REPO-TOPOLOGY.md` tracked, so the zeros
  were real): `docs/ssot/` 0 of 1 tracked, `command-center/ssot/` 1 of 24. The document defining
  the SSOT rule existed only in one working tree holding 327 dirty entries — one `git clean -fd`
  from unrecoverable, and invisible to the other 24 checkouts. The lane about drift had
  reproduced the `harness-vcs-hygiene` failure it exists to prevent. Fixed by `df6377ab`
  (25 files); postcondition re-measured 1 and 25 tracked. A secret preflight ran first, because
  `inbound-refs.json` came from scanning `~/.claude.json`, `~/.mcp.json` and
  `settings.local.json`: 0 credential-shaped findings over 800,445 chars with a both-states
  control, corroborated by the payload schema storing `{file, line, kind}` — line *numbers*, not
  line content.
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
| `content_check.py` | §2b — stranded work vs `origin/main`, bidirectional → `content-check.json` |
| `_verify_identical.py` | independent hash corroboration of the retire-authorising verdicts → `verify-identical.json` |
| `_secret_preflight.py` | credential-shape preflight with both-states control, run before any commit here |
