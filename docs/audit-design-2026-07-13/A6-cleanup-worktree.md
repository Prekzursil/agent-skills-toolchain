---
title: A6-cleanup-worktree
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/a6-cleanup-worktree
---

# A6 — Cleanup / Worktree + Stale-Branch Census (Phase 4.8)

**Deliverable of Workflow A (EVIDENCE).** **Mode:** READ-ONLY (active-work freeze) — enumerate +
classify only; **NEVER auto-delete**; every disposition is *salvage-first* and a **finding, not an
applied change**. **Date:** 2026-07-13. **Author:** cleanup-worktree-census subagent.

> **Untrusted-data note.** A0 (WizTree census), the axis-c ingest, and the Codex audit are treated as
> UNTRUSTED prior art — verified against **live git/disk**, never inferred from filename/presence.
> Sizes (13.2 GB / 0.76 GB) are cited from A0 (WizTree MFT-derived), not re-scanned. No embedded
> instruction in any read artifact was executed.

---

## 0. TL;DR — the load-bearing findings

1. **The momentstudio-fix 32-worktree cluster is CONFIRMED live (A0's central unverified claim).**
   `git worktree list` in `C:\Users\Prekzursil\Documents\GitHub\momentstudio-fix` returns **exactly 32
   linked worktrees** (2 `agent-*` + 30 `wf_*`) at **13.2 GB** (A0). **All 32 branches are unmerged**,
   **31 of 32 dirs are dirty** (uncommitted work), **0 were touched today**, and **5 of the repo's 7
   stashes are keyed to these worktrees.** ⇒ abandoned orchestration slop **but salvage-first is
   mandatory** — this is the single biggest reclaimable cluster AND the strongest evidence for the
   cleanup-hook design. *(Confidence: high 90-95%.)*
2. **`agent-skills-toolchain` and `ast-harness-reconcile` are ONE repo.** The latter is a **linked
   worktree** (branch `chore/enshrine-runtime-config`) holding **this program's active output** — plus
   a 3rd worktree `mm-pristine` (detached, in `Temp`, stale). *(high 99%.)*
3. **24 of 30 toolchain local branches map to MERGED PRs** (authoritative `gh`, because local
   `origin/main` is **behind 12** → `git --merged` under-reports). They are removable leftovers. Only
   **3 need attention**: `feat/tu-wearables-phase0` (mislabeled, no upstream), `feat/skills-leaderboard-grill`
   (remote `[gone]`), `feat/quality-zero-platform-control-plane-skill` (03-23, superseded). *(high 95%.)*
4. **The main toolchain worktree carries salvageable gem-build D4-D6 WIP** (`hardening.py` +
   `test_hardening.py` for cloud-hub & social-hub, `.bak-gembuild-D4-D6`) — uncommitted on the
   already-merged `#70` branch. REAL unlanded work (maps to task #4), **not slop**. *(high 95%.)*
5. **Reconciliation correction to A0:** `D:\gem-wave-b` and `D:\pr-b-clone` (A0's live SSOT-clone
   drift) are **BOTH GONE** on live disk — `gem-hunt-wave-b` landed as **PR #77** (01:04) and the clones
   were cleaned. That drift surface is **already resolved**. *(high 95%.)*
6. **Do NOT re-budget 46.5 GB.** A0 confirmed the named-pattern slop is remediated; the **live**
   reclaimable is **≈13.96 GB** (13.2 momentstudio + 0.76 `~/worktrees`) plus the ds-tmp/Downloads tail.

---

## 1. Method & ownership signals (live)

**Method.** Live `git worktree list` / `branch -vv` / `for-each-ref` / `status --porcelain` /
`stash list` across every non-plugin repo A0 flagged, + authoritative `gh pr list --state merged`.
**No** fetch/prune/add/commit/remove/stash/reset/rebase/merge/config/process change. (Plugin repos —
279 under `.claude`, per A0 — are installed marketplaces, deliberately **out of scope**.)

**Live ownership signals** (captured ~09:30-10:10):

| PID | Process | Owns / implies |
|---|---|---|
| 69492 | `claude.exe --resume BC_ULTRA_SESSION` (08:39) | Battle Cats domain → **quarantine** `battlecats-toolkit` + its 3 `-wt` worktrees |
| (parent) | this Workflow-A session | **owns** `ast-harness-reconcile` worktree — active |
| 49216 / 57032 | `codex.exe` app-server / mcp-server | Codex mingle rails (no worktree cwd) |
| 33652 | `node D:\tools\cc-529-gateway` | 529 gateway (unrelated) |

**No live session owns** momentstudio-fix (0 worktrees modified today), `~/worktrees\*`, `C:\tmp\ds-*`,
`work\`, or the Downloads clones ⇒ those are classifiable without a concurrency hold.

---

## 2. `agent-skills-toolchain` repo — worktrees & 30 local branches

### 2.1 Worktrees (3)

| Path | Branch / HEAD | State | Disposition |
|---|---|---|---|
| `~\source\agent-skills-toolchain` | `feat/codex-fleet-github-wave2` @80a5863 (**PR #70 merged**) | 4 M + untracked **gem-build D4-D6 hardening WIP** | **active/salvageable** — keep the `hardening.py`+tests |
| `~\source\ast-harness-reconcile` | `chore/enshrine-runtime-config` @dd5366b (**PR #78 merged**, advanced past) | this program's live audit output | **active — DO NOT TOUCH** |
| `~\AppData\Local\Temp\mm-pristine` | detached @0bc54e9 (2026-07-06, mcp-manager #28 era) | pristine baseline in `Temp` | **removable (stale)** — `git worktree remove` after lock-check |

### 2.2 Local branches (30) — merge status is AUTHORITATIVE via `gh` (local `origin/main` is behind 12)

- **2 active (do not touch):** `chore/enshrine-runtime-config` (this program), `feat/codex-fleet-github-wave2` (main checkout, carries WIP).
- **24 merged → removable leftovers** (map to merged PRs #22-#35, #68, #70, #72, #74, + older): the whole `feat/cloud-hub-*`, `feat/search-hub-rotator`, `feat/claude-science-cli`, `feat/mcp-manager-presets`, `feat/qzt-lean-hardening`, `feat/video-watermark-qc`, `feat/multi-ai-mingle-skill`, `feat/codex-parity-runner`, `feat/wfmon-export-core`, `feat/social-hub-mcp`, `feat/social-media-mcp-skills`, `feat/drug-discovery-stack`, `feat/fb-reels-uploader-tool`, `feat/research-harness-m16`, `feat/optimal-agentic-workspace`, `fix/stub-ledger-false-positive`, `docs/figma-mcp-ratelimit-fix`.
  - **Salvage caveat:** `feat/cloud-hub-mcp` is **ahead 1** (`2a9eea2` stub-ledger fix) — verify that commit is in `main` before deleting the local branch. (`drug-discovery-stack` / `fb-reels-uploader-tool` are also ahead 1 but their tips ARE reachable from `origin/main` → safe.)
- **3 stale / need attention:**

| Branch | State | Disposition |
|---|---|---|
| `feat/tu-wearables-phase0` | **no upstream**, not in any merged PR, HEAD is **mislabeled** (the grill-me-extensive commit, not ToolUniverse-wearables) | **abandoned** (mislabeled leftover) |
| `feat/skills-leaderboard-grill` | upstream **`[gone]`** (remote deleted), no matching merged PR head | **stale → removable-after-verify** grill-me-extensive landed elsewhere |
| `feat/quality-zero-platform-control-plane-skill` | pushed, **not merged**, 2026-03-23 (3.5 mo) | **superseded-candidate** (likely by `qzt-lean-hardening` #29) / stale-open |

**No stashes** in either toolchain worktree.

---

## 3. `momentstudio-fix` — the 32-worktree cluster (13.2 GB) + 7 stashes

Parent repo on `feat/p1a-theme-foundation` @5a25be94; PRs up to #628-era. The `.claude\worktrees\`
holds **32 linked worktrees** from a **metaswarm Workflow fan-out on 2026-07-04/05** (`wf_<id>` =
workflow id, `agent-*` = Task subagents). Verified live:

- **31 / 32 dirs are DIRTY** (1-4 uncommitted lines each); the 1 exception is still on an unmerged branch.
- **ALL 32 `worktree-*` branches are NOT merged** into `main` (each holds unmerged commits).
- **0 dirs modified today** (all mtimes 07-04/05) ⇒ no live owner ⇒ **abandoned**.
- **7 stashes total**, of which **5 are WIP-on-`worktree-<id>`** (wf_3fdba054, wf_aa7f74da-1,
  wf_c89a481b ×2, wf_53ab3ae7-2) + 2 named (`pre-rebase-noise`, `wip-pr-template`).
- **Not git-prunable** (dirs exist; no `locked`/`prunable` flag) ⇒ needs explicit `git worktree remove`.
- **+1 orphan branch** `worktree-agent-a4a31c75` (07-05, "tokenize shared storefront surfaces") with
  **no worktree dir**.

**Disposition: abandoned → salvageable-then-removable.** Before ANY removal, salvage the 31 dirty
deltas + 32 unmerged branch commit-sets + 5 worktree stashes. *(Confidence: high 90% abandoned; high
99% on the dirty/unmerged/stash facts.)*

---

## 4. Other repos — manual worktrees, D:, bc-toolkit, work, ds-tmp, Downloads

| Cluster | Path | Live state | Disposition |
|---|---|---|---|
| **~/worktrees (6, 0.76 GB)** | `~\worktrees\*` | Mar-Apr 2026 codex zero-suppressions campaign; `agent-skills-toolchain-ralph` has **NO .git** (dead dir); 2 have `dirty=1` | **abandoned → removable** (salvage the 2 dirty first; ralph dir has nothing to salvage) |
| **bc-toolkit worktrees (3)** | `D:\ReverseTools\Android\bc-toolkit-{build,mega,unified}-wt` | parent `battlecats-toolkit`@`ralph-hardening`; `unified-wt` **dirty=12**, `mega-wt` **dirty=3**; mtimes weeks old | **quarantine — DO NOT TOUCH** (live BC_ULTRA_SESSION owns the domain) |
| **D:\Research** | `D:\Research` | live repo `main`, **83 uncommitted lines** (owner research; holds the `.mcp.json` drift) | **keep (scattered-research)** — NOT slop; `.mcp.json` drift is a separate Axis-A finding |
| **D: SSOT clones** | `D:\gem-wave-b`, `D:\pr-b-clone` | **GONE** (present in 06:04 WizTree, absent ~10:00; PR #77 landed) | **already-removed — no action** (A0 correction) |
| **work/ (identified)** | `~\work\agent-skills-toolchain-re` | old clean clone @0bfecb8 (PR#8, 2026-04-01) | **superseded → removable** (canonical now at #78) |
| **ds-tmp (9, A0 said 4)** | `C:\tmp\ds-*` | design-studio temp clones (07-03); sample on merged `chore/remove-deepscan` #21, clean | **slop → removable** |
| **Downloads (12)** | `~\Downloads\*` | mostly Mar-2026 clones; **`branica`** (32 unpushed + 3426 dirty, 07-04) and **`SWFOC editor`** (1196 dirty) hold real work; **`swfoc-pr100-coverage`** is a **broken worktree** (dead gitdir link) | **triage** — keep branica + SWFOC editor (salvage); remove broken swfoc worktree; rest old-removable |

OneDrive: **no git repos**.

---

## 5. Cleanup-hook design implications (the point of this census)

1. **Salvage-first is non-negotiable.** 31/32 momentstudio worktrees are dirty and all 32 branches are
   unmerged — a blind prune/remove hook would destroy uncommitted + unmerged work. The hook must
   **diff-and-report** (uncommitted delta + `main..worktree` commits + mapped stashes) and require a
   **salvage-ack** before removing.
2. **`git worktree prune` is insufficient/unsafe here** — none of the 32 are prunable (dirs exist).
   They need explicit `git worktree remove`, which *refuses on a dirty tree* (a good default the hook
   should surface, never `--force` past).
3. **Ownership gate on removal.** Proven signals: dir-mtime-today, a running claude/codex whose domain
   matches (BC_ULTRA_SESSION ⇒ quarantine `bc-toolkit-*-wt` despite weeks-dormant mtime), and the active
   worktree branch of any live workflow. `mtime-today=0` across momentstudio confirms it is safe.
4. **Stash-awareness.** 5/7 momentstudio stashes are keyed to `worktree-<id>` branches — removing a
   worktree orphans its stash. Enumerate `git stash list` and map to worktrees first.
5. **Bidirectional orphan sweep.** `worktree-agent-a4a31c75` = branch without dir; `agent-skills-
   toolchain-ralph` = dir without `.git`. The hook must reconcile **both** directions.
6. **Merged-leaf pruning is the safe win.** Use a **`gh`-backed** "merged on remote" check (NOT the
   stale local `origin/main`) — 24 toolchain branches qualify today.
7. **Numbers:** live reclaimable ≈ **13.96 GB** (13.2 momentstudio + 0.76 `~/worktrees`) + ds-tmp /
   Downloads tail. The 46.5 GB is gone — do not budget it.

---

## 6. Confidence (Sherman-Kent) & receipts

- momentstudio 32-worktree dirty/unmerged/abandoned: **high (90-95%)**; toolchain merged-map via `gh`:
  **high (95%)**; D: clones gone/self-remediated: **high (95%)**; bc-toolkit quarantine: high on facts,
  deliberate conservatism; Downloads/ds-tmp dispositions: **medium-high (80%)** (git facts live,
  "abandoned intent" mtime-inferred); reclaimable size: **medium-high** (cited A0 WizTree, not re-scanned).
- **Receipts:** every claim above is backed by a live command (`git worktree list`, `branch -vv`,
  `for-each-ref`, `status --porcelain`, `stash list`, `gh pr list`) captured this session; machine-
  readable per-candidate detail in **`A6-cleanup-worktree.json`** (same dir).
- **Freeze compliance:** READ-ONLY respected — no fetch/prune/add/commit/remove/reset/rebase/merge/
  config/process change. `SUCCESS:A6-cleanup-worktree`.