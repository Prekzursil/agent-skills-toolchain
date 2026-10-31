---
title: GROUNDING-VERIFY-2026-08-12
type: note
permalink: dqverify-repo-20261013/command-center/ssot/grounding-verify-2026-08-12
---

# SSOT grounding lane — independent verification of the existing inventory

**Measured 2026-08-12, 22:10–23:00 local. Read-only. Nothing deleted, nothing retired.**

## Why this file exists (and why it is not a second SSOT doc)

This lane was dispatched to answer Q1–Q4 about "nine clones of agent-skills-toolchain". **That work
already exists** at `docs/ssot/SSOT-CLONE-INVENTORY.md`, measured earlier today (19:40–21:00), and it
is materially *more* complete than the brief: 25 checkouts across 18 object stores, not 9.

So this file does **not** rebuild it. It records (a) independent re-measurement of its load-bearing
claims with mechanically different probes, (b) the delta since it was written, and (c) **one
overclaim it must retract**. Everything here should be FOLDED INTO
`docs/ssot/SSOT-CLONE-INVENTORY.md`; `docs/ssot/` must keep exactly one canonical document.

COVERAGE: verified V1 (exec-vs-edit), V2 (kind, 9 briefed paths), V3 (fleet existence, 25),
V4 (stranded commits, 4 checkouts), V5 (content-level check, 3 of the named commits), plus the
`refs/stash` finding. **Not** re-verified: the 8 inbound references, the scheduled-task sweep, the
disk figures, R2–R7. Those rest on the inventory's own measurements, which carried controls.

---

## 1. The inventory's headline finding is an OVERCLAIM and must be re-scoped

The inventory §2 says:

> Four of these are genuine authored work — two features, a bugfix and a security fix — sitting in
> scratch/salvage worktrees with zero inbound references. **That is the fleet's real data-loss
> exposure.**

**The commit-object measurement is correct. The sentence is wider than its evidence.** Commit-object
uniqueness is not content uniqueness, and squash-merge guarantees a merged commit keeps a unique SHA
forever. `REPO-TOPOLOGY.md` rule 4 says exactly this — *"never use commit ancestry as delete
authorisation … compare content"* — and the inventory applied that rule to store B while using the
commit-object check for the scratch worktrees. Same shape as the `-uall` miss it already confessed to.

Content-checked with `git cat-file -p <rev>:<path>` (never `git archive` — CRLF on this box),
line-ending-normalised, **both directions**:

| stranded commit | inventory framing | measured content verdict |
|---|---|---|
| `c7ffc20` `fix(crcp): scope the OpenAI bearer to an allowlist` **[SECURITY]** | genuine authored work at risk | **REDUNDANT — the fix is on main.** Its own two proving tests (`test_auth_broker_credential_scope.py`, `test_credential_egress_transport.py`) are **byte-identical** on main; `auth.py` byte-identical; `auth_broker.py` is `MAIN_IS_SUPERSET` with **0 scratch-only lines** |
| `4a4f7c9` `fix(mcpctl): strip control bytes BEFORE redacting` **[SECURITY]** | genuine authored work at risk | **Fix is on main.** Main's `safety.py` carries *"ORDER IS LOAD-BEARING: strip controls FIRST, then match secrets. Reversing it is a credential-leak bypass"* and main's `test_safety.py` carries the bypass regression. Residual: the scratch draft additionally documents a **zero-width / Unicode `Cf` separator** gap main's wording drops — a doc residual, not a missing fix |
| `80130e1`+`a8e8627` `feat(mcp-manager): dead-MCP detector` | genuine authored work at risk | **SUPERSEDED PARALLEL IMPLEMENTATION — unique value UNVERIFIED.** See §2 |

**Consequence for sequencing:** the inventory's "RECONCILE BEFORE ANYTHING ELSE (8)" is driven
largely by this finding. With the two security fixes confirmed landed, the reconcile burden collapses
toward the **uncommitted** surface (567 files), which is a different and smaller problem. Re-run the
content check on the remaining stranded commits **before** scheduling reconcile work.

**UNVERIFIED (inline):** I content-checked **3** of the named commits, not all of them. Settling
experiment: run `command-center/ssot/_grounding_content.py` over every sha in
`_grounding_stranded2.py`'s output.

---

## 2. The 42 == 42 trap — I nearly shipped the dangerous verdict

`tools/mcp-manager/` holds **42 files on main and 42 files in the b5 commit**, and main's history
contains `58115d68 fix(mcp-manager): dead-MCP detector must reconcile against disabledMcpServers
(#196)`. Read together those say "the feature shipped, the scratch tree is redundant." I was one step
from writing that down. It is **wrong**.

The symmetric difference is a **3-for-3 swap**, not parity:

| only on `origin/main` | only in b5 `80130e1f` |
|---|---|
| `core/surface_census.py` | `core/health.py` (25,391 B) |
| `data/claude_ai_connectors.example.json` | `mcp_health.py` (5,245 B) |
| `tests/test_surface_census.py` | `tests/test_health.py` (27,594 B) |

Main's detector lives in `core/claude_adapter.py` + `core/models.py` (that is all PR #196 touched —
7 files, none named `health`). So main implements the **same capability with a different
architecture**, and b5's **58 KB** standalone health module is a *superseded alternative*, not a
byte-subset and not lost work.

Correctly scoped: **do not retire it as redundant, and do not escalate it as critical data loss.**
Whether it holds behaviour main lacks is a judgement call a differ cannot make (fan-out-contract
§C.D4). Settling experiment: diff `core/health.py`'s graded-evidence logic against main's
`claude_adapter.py` detector and decide whether the grading is worth porting.

This is the estate's own §3c tell: *a suspiciously equal number on both sides is more often a
collection-level mistake than genuine parity.*

---

## 3. NEW DEFECT — `refs/stash` is store-level, so one retire precondition can never pass

Inventory §5 corollary 2 requires all four to retire a checkout:
`unique_commit_count == 0` · `git status --porcelain -uall` empty · **`git stash list` empty** ·
zero field-level inbound references.

Measured — `git stash list` is **not** a per-worktree property:

| checkout | `git stash list` | `git rev-parse refs/stash` |
|---|---|---|
| `~/source/agent-skills-toolchain` (store A main) | 2 | `d90474213cca9f7e` |
| `~/source/ast-integrate` (store A worktree) | 2 | `d90474213cca9f7e` |

Identical ref, identical SHA: `refs/stash` lives in the **common** dir and is shared by all 5 store-A
checkouts. So while store A holds 2 stashes, that criterion is **simultaneously false for every
store-A worktree** — including `~/source/ast-harness-reconcile`, which the inventory's §4 lists as a
RETIRE candidate. **The rule as written contradicts the inventory's own retire list.**

The error direction is *safe* (a false blocker, not false permission), but the rule is unusable for
the 4 store-A worktrees as stated.

**Fix the criterion, not the list.** Removing a linked worktree cannot destroy `refs/stash`. The
state that *is* destroyed with a worktree is per-worktree: its **index** (staged-but-uncommitted —
`.git/worktrees/<name>/index`), its **HEAD/reflog**, and its untracked files. The inventory already
had this right for `D:/wt-salvage-probe` ("a staged index is per-worktree and is destroyed with the
worktree") and then used a store-level ref as a per-worktree gate. Replace with:

> `git stash list` empty **for an independent clone**; for a linked worktree, instead require
> `git diff --cached --quiet` (empty index) and no worktree-local reflog-only commits.

---

## 3b. NEW DEFECT, highest urgency — the SSOT lane's own output is UNTRACKED

The document that establishes the SSOT rule is not in version control.

| path | tracked / on disk |
|---|---|
| `docs/ssot/SSOT-CLONE-INVENTORY.md` | **0 / 1** — untracked |
| `docs/ssot/` (all) | **0 / 2** |
| `command-center/ssot/` | **1 / 24** — 23 untracked |
| **CONTROL** `docs/` overall | 185 tracked (detector works) |
| **CONTROL** `REPO-TOPOLOGY.md` | tracked (fires) |

The controls matter: a `git ls-files` that returned 0 everywhere would be a broken detector. It
returns 185 for `docs/` and confirms `REPO-TOPOLOGY.md`, so the zeros are real.

`ast-integrate` currently holds **341** dirty files. The inventory, the SSOT rule, and 23 of 24
measurement artifacts exist **only** as untracked files in one working tree — one `git clean -fd`
from gone, and invisible to every clone. This is the `harness-vcs-hygiene` failure class ("live-only
is drift, not a resting state") reproduced *inside* the lane whose subject is drift.

**Action: commit these before any retirement work.** Use
`git commit -F <msgfile> -- <explicit paths>` (pathspec commit needs `git add` first for new files);
never `git add -A` in a shared worktree.

---

## 4. Re-measured: claims that SURVIVED, with controls

### V1 — "canonical drift is latent, not active" → CONFIRMED, at a *moved* baseline

The inventory measured this at `origin/main = ae8205a4`. Main has since moved **twice**
(`ae8205a4` → `9353ed1f` → `86dde6c1`), and canonical is now **161** behind (was 159).

| probe | result |
|---|---|
| changed files under the 5 executed dirs, `53c37c6c..86dde6c1` | **0** |
| **CONTROL** — same differ, `command-center`+`docs` | **869** (fires) |
| **CONTROL** — same differ, whole tree | **2,386** |

The control is the load-bearing part: a differ returning 0 for the exec dirs *and* 0 for everything
else would be broken. It returns 869/2,386, so the 0 is meaningful. The five directories the live MCP
fleet loads (`tools/mcp/{cloud-hub,social-hub,search-hub,qdx-rush-mcp}`,
`tools/scholarly-access-mcp/.venv`) genuinely have not moved in 161 commits. **Nothing is broken
today; the hazard is the next commit under `tools/mcp/**`.** Now measured at two independent
baselines, which is stronger than the inventory's single reading.

### V2 — worktree vs clone, on the 9 briefed paths — the brief's framing is wrong

Two mechanically independent signals (`.git` file-vs-dir; `--git-common-dir` vs `<path>/.git`)
**agreed on all 9**.

| briefed path | kind | HEAD | origin | dirty `-uall` |
|---|---|---|---|---|
| `~/.claude/codexsrc-work` | **clone** | `feat/monitorcore-codexsource` | *filesystem path* | 81 |
| `~/.claude/toolchain-audit` | clone | `main` | GitHub | 0 |
| `~/.claude/tw-merge-work` | **clone** | `feat/taskwatch-ssh-adapter-qm-probe` | *filesystem path* | 0 |
| `~/Documents/Playground` | clone | `main` | GitHub | 111 |
| `~/source/agent-skills-toolchain` | clone (store-A main) | detached | GitHub | 2 |
| `~/source/ast-patch167` | clone (store B) | `fix/deny-credential-gaps` | GitHub | 8 |
| `~/source/ast-integrate` | **worktree** → store A | `main` | GitHub | **341** |
| `~/work/agent-skills-toolchain-re` | clone | `main` | GitHub | 0 |
| `D:/sast-depth/agent-skills-toolchain` | clone | `main` | GitHub | 0 |

**Only 1 of the 9 briefed paths is a worktree.** The brief called
`~/source/agent-skills-toolchain` "the CANONICAL git dir", implying the rest hang off it; measured,
8 of 9 are independent object stores that can and do diverge in history. The brief also omits 3 of
store A's 4 linked worktrees (`ast-harness-reconcile`, `D:/inc1-wt/ast-increment1`,
`D:/wt-salvage-probe`) and 16 further checkouts.

Independently corroborated: `codexsrc-work` and `tw-merge-work` have `origin` =
`C:\Users\Prekzursil\source\agent-skills-toolchain` — a **filesystem path, not GitHub**. That
confirms the inventory's `--local` hardlink-clone claim via a different signal (remote URL) than its
`fsutil hardlink list`.

### V3 — the fleet is stable: **25 of 25** checkouts in `all25.json` still exist, 0 missing

### V4 — detector controls, both states, on every instrument used

| instrument | real object | fabricated `dead…` sha |
|---|---|---|
| `git cat-file -e` | present | absent |
| `git cat-file --batch-check` (batched) | present | absent |
| `git cat-file -p origin/main:<path>` blob reader | returns content | returns empty |

The blob-reader control matters most: a reader silent in *both* states would make every file look
"absent from main" — which is precisely the false verdict §1/§2 turned on.

---

## 5. Delta since the inventory (its residual R6, now quantified)

| | inventory 21:00 | now 23:00 |
|---|---|---|
| `origin/main` | `ae8205a4` (`9353ed1f` local, 1 ahead) | `86dde6c1`, **0 ahead / 0 behind** |
| canonical behind main | 159 | **161** |
| `ast-integrate` dirty `-uall` | 298 | **341** |
| store-A `refs/stash` | (not reported) | 2, shared |
| checkouts existing | 25 | 25 |

`main` took **three distinct values in one evening**. Any absolute count here is a snapshot; re-run
before acting.

---

## 6. Method note — one instrument of mine was coarser than the inventory's

My stranded-commit probe reported **18** where the inventory reports **7** for the same four
checkouts. **My probe is the weaker one**, by construction: I compared against the canonical store
only (1 of 18) and filtered the remote by **tip equality**, not reachability. A commit that is an
*ancestor* of a remote tip passes my filter and is miscounted as stranded.

The gap reconciles cleanly, which is itself corroboration:
- `work/agent-skills-toolchain-re`: my 7 collapse to **4 distinct subjects** — three appear twice
  (`Add reverse engineering skills…`, `Normalize RE host launcher…`, `Add Windows host shim…`), the
  amend/rebase signature. The inventory's 3 counts distinct work items.
- `_b5-toolchain`: my extra 7 are a 2026-07-18 `agent-self/harness` PR series by a *different*
  author, which the inventory found replicated in other stores — its own §2 note that "replicated
  locally is not the same as safe".

Per the estate rule, when my probe and another disagree I suspect mine first. **The inventory's 7
stands; my 18 does not.**

---

## 7. Reproduce (all read-only, `command-center/ssot/`)

| script | answers |
|---|---|
| `_grounding_verify.py` | V1 exec-vs-edit with both-states control, V2 kind, V3 existence, V4 controls |
| `_grounding_stranded2.py` | batched stranded-commit enumeration (one `cat-file --batch-check` per store) |
| `_grounding_content.py` | content-level check of a stranded commit vs `origin/main` |
| `_grounding_direction.py` | deliberate-deletion control + **two-directional** line diff |

`_grounding_stranded.py` (v1) is kept only as a negative result: one `cat-file -e` spawn per commit
needed ~16k Windows process spawns and blew a 900 s budget. Batch, don't spawn.

---

## 8. External SOTA that bears on the open residuals

- **`git worktree repair`** is the first-class remedy for the inventory's **R4** (the Codex plugin
  cache holding a copy of canonical's worktree admin dir with `gitdir` files pointing at the *real*
  live directories). It rewrites both `.git` and the matching `.git/worktrees/<name>/gitdir`.
  **Direction is the hazard:** run from the *cache*, it would repoint the **real** worktrees at the
  cache. Never run any `worktree` subcommand from the plugin cache — matching the inventory's own
  instruction, now with the mechanism named.
  <https://git-scm.com/docs/git-worktree>
- `git worktree repair` also handles multi-directional breakage (git commit `cf76bae`), i.e. both
  main and linked worktrees moved. <https://github.com/git/git/commit/cf76baea41bb7f6431dbfa5744c861fdb844d20b>
- **UNVERIFIED (inline):** whether `git worktree prune` in the cache is safe was **not** tested — the
  probe is destructive. Settle against a throwaway worktree, never a live one. R5 (`worktree remove`
  following junctions) likewise not re-verified; the inventory measured no reparse point at depth 1.