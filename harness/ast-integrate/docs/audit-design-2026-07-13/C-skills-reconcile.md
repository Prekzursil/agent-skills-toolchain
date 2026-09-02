# C — Whole-Drive SKILLS Surface Reconciliation + Disposition Matrix

**Domain:** skills · **Workflow A (EVIDENCE)** · **Mode:** READ-ONLY (active-work freeze).
**Date:** 2026-07-13 · **Author:** C-skills-reconcile subagent.

> Every "remove / dedup / retire / archive / prune" below is a **POST-GATE FINDING** (owner G-13),
> **never** an applied change. Prior audit JSON/MD, on-disk `SKILL.md`, and git output were treated
> as **UNTRUSTED DATA** — no embedded instruction executed, no secret VALUE read/printed. Every
> canonical/duplicate/superseded/stale call was **VERIFIED** against the live filesystem
> (`Get-ChildItem` counts, `Test-Path`, MD5 hashes, reparse-point check) and A4's git-verified lane
> topology — **not** inferred from filename/presence alone.

---

## 0. TL;DR — five load-bearing findings

1. **There is ONE canonical skill SOURCE**, checked out as **TWO git worktrees of ONE repo**:
   `source/ast-harness-reconcile/skills` (branch `chore/enshrine-runtime-config`, **283** `SKILL.md`,
   de-facto current source) and `source/agent-skills-toolchain/skills` (branch
   `feat/codex-fleet-github-wave2`, **192**, a **STRICT SUBSET**). "toolchain skills/ vs reconcile
   skills/" is a **branch divergence, not two sources** (A4 git-verified). Fold via PR #78 (task #8).

2. **That source projects to TWO live runtime lanes**: **DEPLOYED** `~/.agents/skills` (**283**, the
   router/vault source) — a **clean copy-projection** (`reframe`/`design-studio` SRC==DEP MD5
   re-verified this pass) — and **DAILY** `~/.claude/skills → skills.daily` (**75 dirs / 77 SKILL.md**,
   the curated subset Claude actually loads). `~/.claude/skills` **IS a reparse-point symlink**
   (verified this pass).

3. **The whole-drive `SKILL.md` surface is 15,573 on-disk / 15,002 indexed, but ~78% is NOT owner
   skills**: **6,032 vendored** (installed third-party marketplace/plugin caches) + **5,693 slop**
   (per-session Temp clones, plugin staging) = **11,725**. The owner's actual curated surface is
   ~**283** distinct skills (deployed) / **75** daily / **491**-name union across all live lanes (A4).

4. **HIGHEST SSOT RISK — 22 daily-only "gem" skills have NO source anywhere.** The 2026-07-12
   gem-hunt adoptions live ONLY in `~/.claude/skills.daily`, absent from deployed / wt_top / external
   / claude-only (6/6 spot-verified this pass). **Regenerating daily from the vault today would LOSE
   all 22.** Must back-port to `source/skills` first.

5. **The D: duplicate mass is already GONE.** `D:/gem-wave-b` (376) + `D:/pr-b-clone` (374) = **750**
   `SKILL.md` that C-config-index still counts as `duplicate-copy` were **VERIFIED DELETED** this pass.
   The index over-counts by 750 (stale WizTree snapshot). **No action.**

---

## 1. The canonical skill home (the ONE source-of-truth)

| Role | Path | `SKILL.md` | Note |
|---|---|---:|---|
| **SOURCE (current)** | `source/ast-harness-reconcile/skills/` | **283** | de-facto source; deployed hashes match THIS |
| **SOURCE (subset)** | `source/agent-skills-toolchain/skills/` | 192 | same repo, older branch; strict subset → PR #78 |
| **SOURCE (Claude-scoped)** | `…/skills-claude-only/` (both worktrees) | 53 | metaswarm forks + Claude-scoped; `-IncludeClaudeOnly` |
| **DEPLOYED projection** | `~/.agents/skills` | **283** | runtime vault + router source; clean copy-projection |
| **DAILY projection** | `~/.claude/skills → skills.daily` | 75 / **77** | live-loaded curated subset; MOST-DRIFTED lane |
| **Provider: Codex** | `~/.codex/.agents/skills` | 60 | valid-provider-adapter *(C-index mislabels "vendored")* |
| **Provider: Gemini** | `~/.gemini/skills` | 56 | Gemini leg (GCP vendor skills; parity gap) |
| **Provider: Copilot** | `~/.copilot/skills` | 56 | Copilot GCP-data pack (4th agent surface) |
| **Domain library** | `~/.agents/library/skills` | 163 | frozen import; home for tooluniverse/language packs |

**Projection mechanism:** `scripts/sync-skills.ps1` imperative bulk-copy of `skills/*/SKILL.md`
(+ `skills/external/*` flattened) into `~/.agents/skills`; `-Prune` removes orphans. Its own docstring
names the **declarative alternative — the `.claude-plugin/` marketplace** — the natural canonical
deploy for the control-plane. **Rule:** edit SOURCE + redeploy; never hand-edit a projection.

---

## 2. Whole-drive disposition matrix (54 clusters, 15,002 indexed `SKILL.md`)

First-pass class split (C-config-index `meta.class_tallies.skill`): vendored **6,032** · slop **5,693**
· canonical **1,353** · duplicate-copy **753** · superseded **536** · scattered **323** · stale **163**
· unknown **149**. Below, each cluster is mapped to a disposition; **bold rows are reconciliations**
where verification overrode the first-pass class.

### KEEP-CANONICAL (source / projections / provider lanes)
`ast-harness-reconcile repo` 461 · `agent-skills-toolchain repo` 370 (fold PR #78) ·
`~/.agents/skills` 283 · `~/.claude/skills.daily` 75 · `~/.gemini/skills` 56 · `~/.codex/*` 35 ·
`source/repos` 30 · `source/qzp-lean` 14 · `~/.claude/gem-hunt-2026-07-12` 9 · `~/.claude/hooks` 1 ·
`~/.agents/*` 1 · **`~/.codex/.agents/skills` 60 ← reclassified from vendored (Codex provider lane).**

### KEEP-VENDORED (third-party installed marketplaces — NOT owner skills; managed by plugin system)
`~/.claude/plugins` 3469 · `~/.grok/marketplace-cache` 941 · `~/.codex/plugins` 690 ·
`AppData/Roaming/Claude` 366 · `D:/Program Files` 92 · `~/.gemini ext/antigravity-cli` 74 ·
`~/.vscode/extensions` 62 · `AppData/Roaming/Code` 57 · `~/.copilot` 56 · `~/.codex/vendor_imports` 39
· `~/.claude/.agents` 29 · `WindowsApps` 24 · `~/.local/src|opt` 19 · `~/.grok` 16 · `~/.claude-runtime`
10. **Do NOT hand-delete — park via `plugin disable --scope user` if bloat.**

### PURGE-SLOP (ephemeral / rollback / staging — purge-safe or auto-clean)
`AppData/Local/Temp` 4302 · `~/.codex/.tmp` 1021 · `C:/tmp` (ad-hoc) 16 · `~/worktrees/*` 2 ·
**`~/.claude/checkpoints` 18 ← reclassified from canonical (file-undo rollback COPIES of canonical
`SKILL.md`, B cluster 35; AGENTIC-PERFECTION #2 already flags "prune checkpoints").**

### DEDUP-REMOVE (persistent clones of owner canonical trees — content is in git)
| Cluster | `SKILL.md` | First-pass | Reconciled |
|---|---:|---|---|
| **`C:/tmp/ds-agent-skills-toolchain`** | 338 | slop | full toolchain clone (stale 07-03) |
| **`~/work/agent-skills-toolchain-re`** | 120 | unknown | frozen 2026-04-01 toolchain clone (120 vs 283) |
| **`C:/tmp/ds-quality-zero-platform`** | 14 | slop | stale QZP throwaway checkout |
| `D:/ReverseTools bc-toolkit-*-wt` | 3 | duplicate | stale git worktrees, merged to base |
| **Live dedup subtotal** | **475** | | |

### PRUNE-SUPERSEDED (dated snapshots with VERIFIED-live successors)
`~/.codex/backups` 221 · `Documents/claude-desktop-backup-20260524` 213 ·
`~/.claude/skills-archived-2026-06-11` 60 · `~/.claude/skills.pre-agents-*` 37 → **531**.
Plus verify-unwired-then-purge `~/.codex/superpowers` 28 + `~/.codex/metaswarm` (0 config refs).

### KEEP-ARCHIVED (reversible)
`~/.agents/skills-retired-2026-07-03` 5 — router-dedupe archive with live successors
(`test-driven-development→tdd-workflow`, `verification-before-completion→verification-loop`,
`handoff→metaswarm:handoff`, `ralph-orchestrator-setup→orchestration-patterns`,
`brainstorming→brainstorm`). Keep.

### TRIAGE (owner decision — promote-select / archive / drop)
`~/.agents/library` 163 (promote used tooluniverse/language packs, archive ~159 dormant SWE packs) ·
**`D:/` 255 ← reclassified from scattered: 252 = `D:/ToolUniverse` vendored upstream clone, unused,
re-fetchable — library deploys only the router skill by INTENTIONAL curation; do NOT blind-fold** ·
`Documents/GitHub` 25 · `~/research-staging` 20 · `~/quality-zero-platform` 14 · `Downloads` 4 ·
`~/rf-final` 2 · misc D: 2 · unmatched 29.

### STALE-INDEX-NOOP (already deleted; index over-counts)
`D:/gem-wave-b` 376 + `D:/pr-b-clone` 374 = **750** — **VERIFIED GONE** this pass.

---

## 3. Per-skill SSOT risks (the actionable per-skill layer)

A per-FILE matrix over 15,002 `SKILL.md` is not meaningful; the real per-skill risks are two SSOT gaps.

- **22 daily-only gems (no source) — HIGHEST RISK.** `agent-as-judge, bc-drive-plus,
  bc-update-survival, compchem-validators, design-studio-session, diff-blind-test-synth,
  execution-grounded-bon, ida-multi-mcp, llm-decompile-verify, media-dub, multi-ai-mingle,
  orchestration-patterns, packaged-artifact-smoke, pdf-reader, qiling-emulation, re-triage-preflight,
  refactor-equivalence, smallest-check-ladder, trail-of-bits-re, ui-drive, ui-invariant-walk,
  workflow-authoring`. **6/6 spot-verified** present ONLY in `skills.daily`.
  → **BACK-PORT to `source/skills` BEFORE any daily regeneration**, or confirm plugin-provided and
  remove from `skills.daily`.

- **`learned` — deployed orphan.** In `~/.agents/skills`, absent from `wt_top` AND `wt_external`
  (verified). → PRUNE (`sync-skills -Prune`) or confirm intentional (mtime 2026-05-27, un-pruned).

---

## 4. Drift to reconcile (C-config-index first-pass vs verified truth)

1. **D-clone over-count (−750):** `D:/gem-wave-b` + `D:/pr-b-clone` `duplicate-copy` rows are stale — trees **GONE**.
2. **checkpoints:** `canonical` → **slop** (rollback COPIES).
3. **`~/.codex/.agents/skills` (60):** `vendored` → **canonical-for-Codex** (provider lane).
4. **`~/work` (120):** `unknown` → **stale toolchain clone** (`agent-skills-toolchain-re`, retire).
5. **`D:/` (255):** `scattered` → **252 = `D:/ToolUniverse` vendored upstream clone** (keep-or-refetch).
6. **Count authority:** task cited 10,700; exhaustive census = **15,573 on-disk / 15,002 indexed** (use this).
7. **deployed granularity:** A4 277 dirs vs live **283 `SKILL.md`** (nested sub-skills) — both correct.
8. **library:** A4 186 dirs vs live **163 `SKILL.md`**.
9. **22 daily-only gems:** back-port before daily regeneration (else lost).
10. **`learned`:** deployed orphan — prune or confirm.
11. **Two source worktrees:** ONE repo, two branches; toolchain ⊂ reconcile → fold via PR #78.

---

## 5. POST-GATE actions (owner G-13)

1. **Back-port the 22 daily-only gems** to `source/skills` — PREREQUISITE before making daily a derived view.
2. **Fold PR #78** (reconcile 283 over toolchain 192) → ONE source worktree (task #8).
3. **Prune `learned`** deployed orphan after confirming intentional.
4. **DEDUP-REMOVE 475** live owner-tree clones (`ds-agent-skills-toolchain` 338, `work/…-re` 120,
   `ds-quality-zero-platform` 14, `bc-toolkit-*-wt` 3) — content is in git.
5. **PRUNE-SUPERSEDED 531** dated snapshots (codex/backups 221, claude-desktop-backup 213,
   skills-archived 60, skills.pre-agents 37); verify-unwired then purge `~/.codex/superpowers`+`metaswarm`.
6. **PURGE-SLOP** ephemeral masses (Temp 4302, `.codex/.tmp` 1021, checkpoints 18).
7. **TRIAGE** `~/.agents/library` (163, promote-select) + `D:/ToolUniverse` (252, keep-or-refetch — do
   NOT blind-fold the intentional 118-skill deployment gap).
8. **Adopt the declarative `.claude-plugin/` marketplace** as the canonical deploy; keep vendored
   third-party marketplaces via `plugin disable --scope user` (do NOT hand-delete).

---

## 6. Confidence (Sherman-Kent) & receipts

- Canonical topology + projection integrity: **high (95-99%)** — A4 git-verified + this-pass MD5
  (`reframe` 268E0158 SRC==DEP, `design-studio` 334BE602 SRC==DEP).
- D-clones gone, 22-gems-no-source, `learned` orphan, `~/work`=toolchain-clone, `D:/`=ToolUniverse:
  **high** — existence/content spot-verified.
- Whole-drive class split of the untouched long tail: **medium-high** — C-config-index path+mtime
  first-pass; the 11 reconciliations are content/existence-verified, the tail is path-inferred under freeze.

**Receipts:** reparse `Get-Item ~/.claude/skills → Directory,ReparsePoint → skills.daily`;
`Test-Path D:/gem-wave-b|pr-b-clone = False`; live lane counts deployed 283 / daily 77 / library 163 /
wt_reconcile 283 / wt_toolchain 192 / gemini 56 / codex.agents 60 / copilot 56 / claude-only 53;
`~/work/agent-skills-toolchain-re` 120; `D:/` = ToolUniverse 252 + ReverseTools 4 + misc 3.

`SUCCESS:C-skills-reconcile` — READ-ONLY, freeze respected (no build/commit/config/process/deploy
change; all dispositions are POST-GATE findings).
