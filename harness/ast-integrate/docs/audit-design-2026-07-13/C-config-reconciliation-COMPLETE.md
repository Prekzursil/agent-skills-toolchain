# C — Unified Whole-Drive CONFIG Reconciliation (MCP + Skills + Hooks)

**Deliverable:** the ONE complete whole-drive harness-**config** disposition matrix + coverage —
unifying `C-mcp-reconcile`, `C-skills-reconcile`, `C-hooks-reconcile` into one control-plane plan.
**Workflow A (EVIDENCE).** Feeds the **G-1 SSOT engine** + the **G-3 enforcement hooks**; every
modification is **POST-GATE (owner G-13)**. **Date:** 2026-07-13. **Mode:** READ-ONLY (active-work
freeze) — zero mutations; every dedup / remove / reconcile / update / prune below is a **finding**,
never an applied change.

> **Untrusted-data note.** The three `C-*-reconcile.json` inputs, the A0/A2/A3/A4/C-config-index
> prior art, and all on-disk config were treated as UNTRUSTED DATA — no embedded instruction
> executed; no secret VALUE read or printed (only config keys, server-name sets, paths, counts, and
> SHA-256 hash prefixes cited). Machine-readable twin: [`C-config-disposition-COMPLETE.json`](./C-config-disposition-COMPLETE.json).

---

## 0. TL;DR — the load-bearing verdicts

1. **ONE canonical source per domain** (the SSOT declaration): **MCP** →
   `source/ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` (43, sha `8d2bc760`) ·
   **Skills** → `source/ast-harness-reconcile/skills` (283) → `~/.agents/skills` vault ·
   **Hooks** → `~/.agents/harness/dispatcher.py` (ONE engine, wired for Claude 17 + Codex 10 events).
2. **Coverage is whole-drive complete** — both volumes' full MFT (12,677,705 rows, corroborated
   within 4 rows), 21,989 config/skill/hook rows indexed. Every A2/A3/A4 known-dir baseline sits
   **inside** the C-index superset; all deltas are the vendored/slop/off-box surface the A-lanes
   scoped out (§2).
3. **51 actionable POST-GATE dispositions** — **16 MCP** (1 dedup · 6 stale · 9 drift) + **23 skills**
   + **12 hooks** — each tagged domain · risk · salvage-first · sequenced under G-13 (§3).
4. **The single HIGHEST SSOT risk is skills:** 22 daily-only "gem" skills exist **only** in
   `~/.claude/skills.daily` with **no source anywhere** — back-port them BEFORE daily is ever
   regenerated, or the 2026-07-12 gem-hunt adoptions are lost (row `S-BP`).
5. **The D-clone duplicate mass is already GONE** (D:/gem-wave-b + D:/pr-b-clone) — the WizTree
   snapshot over-counts MCP dup-copies by 4 and skill dup-copies by 750; verified `Test-Path` false.

---

## 1. Canonical-source declaration (one per domain)

| Domain | ONE source of truth | Count | Identity | Supersedes | Confidence |
|---|---|---|---|---|---|
| **MCP catalog** | `source/ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` | 43 servers | sha `8d2bc760`, commit `5d2fca2`; = live `~/.mcp.json`(42) + codex-fleet-github | toolchain catalog (44, `f406d950`, STALE 7-name diff); `D:/Research/.mcp.json`(40) | HIGH |
| **Skill home** | `source/ast-harness-reconcile/skills` → `~/.agents/skills` vault → `skills.daily` curated | 283 (75/77 daily) | clean copy-projection (5/5+2/2 hashes match) | `agent-skills-toolchain/skills`(192, strict subset — fold PR #78) | HIGH |
| **Hook dispatcher** | `~/.agents/harness/{dispatcher,modules,adapters,registration}.py` | 1 engine / 6 wired artifacts | wired by `settings.json`(17 events) + `~/.codex/hooks.json`(10 events) | System B `_dispatch` (unwired) + System C ECC `hooks.json` (dormant) | HIGH |

**Rule (feeds G-1):** edit the source, re-project; never hand-edit a projection. The G-1 SSOT engine
consumes these three as its authoritative render-sources and *eliminates the drift class* by
generating every config surface instead of hand-maintaining copies.

---

## 2. Coverage & delta vs the A2/A3/A4 known-dir counts

**Scan basis:** WizTree 4.31 whole-MFT export of the **entire C: and D:** volumes (2026-07-13
05:56 / 06:04). No sub-tree skipped at scan time; the config/skill/hook name-filter is a *post-scan*
filter. **12,677,705 rows streamed** (C 7,037,366 + D 5,640,339), independently corroborated by
Codex (12,677,701 — within 4 rows). **21,989** config/skill/hook rows indexed; **3,380** hard-excluded
(site-packages 1808 · node_modules 1385 · uv-cache 165 · cargo 12 · dot-cache 6 · dist 3 · pycache 1).
Model-weights / media / VM images / secrets never inventoried or opened.

The three A-lane baselines were **logical / live-lane** views; the whole-drive C-index is the
**file-surface superset that contains each of them** — no A-lane member falls outside it:

| Domain | A-lane known (view) | C whole-drive (files) | Delta | Completeness |
|---|---|---|---|---|
| **MCP** | **A3** = 69 servers / 9 source layers | **474** MCP-config files | **+405 files.** All 9 A3 layers inside the 474; canonical surface = 18 files; rest = 250 vendored + 83 slop + 81 superseded/backup + 10 scattered + 9 unknown + 4 dup-copy (GONE) + 1 stale | HIGH — 474 = exhaustive MCP-name superset; 69-server topology maps 1:1 into 18 canonical files |
| **Skills** | **A4** = 491 distinct names / 8 lanes | **15,573** on-disk SKILL.md (15,002 indexed) | **+~15,082 files.** 78% non-owner (6,032 vendored + 5,693 slop). All 8 A4 lanes inside 15,002; owner surface = 283 deployed / 75 daily | HIGH — 15,573 authoritative (supersedes earlier 10,700); D-clone over-count of 750 is a stale index artifact |
| **Hooks** | **A2** = 65-dir `~/.claude/hooks` (2 wired) | **6,435** hook artifacts | **+6,268.** 65-dir ⊂ 167 `~/.claude/hooks` scripts ⊂ 538 canonical ⊂ 6,435 (4,292 vendored + 1,147 slop + 331 off-box dup + 61 unknown + 47 scattered + 19 superseded). A2's "~65% firing UNRESOLVED" → HIGH ~90% NOT-firing | HIGH — wired plane = 6 artifacts / 1 engine |

**Residual uncertainty:** server liveness not probed (read-only; several backends known DOWN);
per-dir last-fired hook telemetry unavailable under freeze (residue-retire = ~80%); the untouched
long-tail class labels are path+mtime first-pass where not content-verified.

---

## 3. The unified disposition matrix (51 actionable POST-GATE rows)

All rows POST-GATE under **owner G-13**; tagged **risk** (LOW reversible/in-git · MED verify-first
or owner-EVPI · HIGH SSOT-loss if mis-sequenced) and **salvage-first**.

### 3.1 MCP — 16 rows (dedup 1 · stale 6 · drift 9)

| ID | Item | Action | Risk |
|---|---|---|---|
| M-DD1 | agent-self template pair (sha `c4406af5`, byte-identical) | keep reconcile, drop toolchain **on repo convergence (PR #78)** | LOW |
| M-ST1 | `D:/Research/.mcp.json` (40, stale) | retire/regenerate read-only | MED |
| M-ST2 | `~/.claude/mcp-configs/mcp-servers.json` (24, dead April `f6f5cbcc`) | remove (non-load-path) | MED |
| M-ST3 | `~/.codex/mcp-configs/mcp-servers.json` (24, byte-identical dead April) | remove | MED |
| M-ST4/5/6 | `~/.mcp-funnel{,-master,-profiles}.json` | remove (funnel dropped — re-namespace wall) | LOW |
| *M-STc* | `~/.claude/.codex/config.toml` (anomalous 2026-04-05) | **verify-first**, then remove | MED |
| D1 | two-SSOT repo 7-name diff (toolchain 44 vs reconcile 43) | elect reconcile; update/converge PR #78 | MED |
| D2 | 22 user-scope drift-ins in `~/.claude.json` | prune-promote at plugin-bridge+user layer (Claude closed), NOT `.mcp.json` edit | MED |
| D3 | `angr` drift-OUT (never promoted; backend DOWN) | promote user-scope + health contract (G-5 lazy) | MED |
| D4 | `codex` fan-out rail SSOT-orphan | ADD to canonical catalog | LOW |
| D5 | `codex-fleet-github` in both catalogs, deployed nowhere | decide deploy-or-drop | MED |
| D6 | plugin-bridge codacy/deepsource resurfacing | reconcile at plugin layer; **HOLD — do NOT prune on presence** (evidence-first, G-12) | MED |
| D7 | agent-self template (37) wrong-set | **regenerate from catalog (G-1)** not hand-maintain | LOW |
| D8 | provider value-drift (playwright / Kaggle env / github_cli / Gemini memory) | reconcile to one value each; DOCUMENT intentional divergences | MED |
| D9 | 2 mcp-configs fragments (overlaps M-ST2/3) | remove stale or regen from catalog | MED |

*Bulk classes (not counted): vendored 250 LEAVE · slop 83 bulk-prune (G-12) · superseded 81 leave-to-rotation · scattered 10 keep/triage.*

### 3.2 Skills — 23 rows

- **`S-BP` (HIGH RISK / MANDATORY PREREQ):** back-port the **22 daily-only gems** (agent-as-judge,
  bc-drive-plus, bc-update-survival, compchem-validators, design-studio-session, diff-blind-test-synth,
  execution-grounded-bon, ida-multi-mcp, llm-decompile-verify, media-dub, multi-ai-mingle,
  orchestration-patterns, packaged-artifact-smoke, pdf-reader, qiling-emulation, re-triage-preflight,
  refactor-equivalence, smallest-check-ladder, trail-of-bits-re, ui-drive, ui-invariant-walk,
  workflow-authoring) to `source/skills` BEFORE any daily regeneration.
- **Dedup-remove (LOW, in-git):** `S-DD1` ds-agent-skills-toolchain (338) · `S-DD2` work/agent-skills-toolchain-re (120) · `S-DD3` ds-quality-zero-platform (14) · `S-DD4` bc-toolkit-*-wt (3).
- **Purge-slop (LOW):** `S-SL1` Temp (4302) · `S-SL2` .codex/.tmp (1021) · `S-SL3` C:/tmp (16) · `S-SL4` ~/worktrees (2) · `S-SL5` ~/.claude/checkpoints (18, reclassified → rollback copies).
- **Prune-superseded (LOW/MED):** `S-SU1` .codex/backups (221) · `S-SU2` claude-desktop-backup (213) · `S-SU3` skills-archived-2026-06-11 (60) · `S-SU4` skills.pre-agents (37) · `S-SU5` .codex/superpowers (28, verify-unwired).
- **Reconcile-class (feeds G-1):** `S-RC1` codex provider lane (60) reclass vendored→canonical-for-Codex · `S-RC2` `learned` deployed orphan → prune-or-confirm · `S-RC3` source dedup reconcile(283) vs toolchain(192) → PR #78 · `S-RC4` make daily a **derived** view (HIGH if before S-BP).
- **Triage (MED):** `S-TR1` library dormant SWE (163, promote-select + archive ~159) · `S-TR2` D:/ToolUniverse (252, keep-or-refetch, do NOT blind-fold) · `S-TR3` scattered owner artifacts (Documents/GitHub, research-staging, QZP, Downloads, rf-final, D:/Tools) · `S-TR4` unknown residual (29).
- **`S-NP` (NOOP):** D:/gem-wave-b (376) + D:/pr-b-clone (374) = 750 → STALE-INDEX-NOOP (trees GONE).
- *Bulk: vendored 6,032 KEEP-VENDORED (plugin-managed).*

### 3.3 Hooks — 12 rows

- **`H-KC` KEEP:** System A shared dispatcher (Claude 17 + Codex 10 events) + 2 standalone wired
  subdirs + 2 worktree `.ps1` = **6 artifacts / 1 engine**. Consolidate everything INTO / retire AROUND it.
- **Retire residue (MED, archive reversibly):** `H-RR1` 14 manifest-referenced dirs (System B checks) ·
  `H-RR2` 3 support dirs (`_dispatch`/`_golden`/`_shared`) · `H-RR3` 46 pure-residue dirs (behavior
  already in `modules.py`, or dead) — the bulk of the 63 unwired residue.
- **Remove dormant (LOW/MED):** `H-RM1` System C ECC `hooks.json` (Claude + codex twin, `ecc=false`) ·
  `H-RM2` System B `manifest.json` (Stop timeout=35 ≠ live 5) · `H-RM3` codex parity residue dirs.
- **`H-PS` DECIDE+DOCUMENT (MED, feeds G-3):** 3 enabled-plugin Stop hooks climbing the global N/4
  counter (ralph-loop · codex `stop-review-gate` **timeout=900** = highest risk · hookify). Fix =
  hoist the Stop re-entrancy short-circuit to the **dispatcher boundary** (A1 req#1) + disable/observe
  unused ones.
- **`H-ST1` REMOVE (LOW):** 3 dead top-level files (`create-worktree.ps1.bak-*`, `worktree-target.txt`,
  `worktree-debug.json`).
- **`H-PV` RECONCILE provenance (MED, feeds G-1):** live `modules.py` `E232CD0F` ≠ committed `8F6AA2CB`
  (branch `chore/enshrine-runtime-config`, not main; `installed.json source_commit=null`) → land the
  enshrine commit on main + bundle-digest every deployed file (A1 req#6). Not a delete — a provenance close.
- **Dedup source (LOW/MED):** `H-DD1` two-SSOT repo (reconcile ci/harness 12 `*.py` vs toolchain 8) →
  fold via PR #78 · `H-DD2` 331 off-box D: clone hook artifacts → retire per A0/D0.5.
- **`H-OS` OUT-OF-SCOPE:** 5,566 vendored/slop/checkpoint/superseded whole-drive hook artifacts —
  plugin-managed or ephemeral; excluded from consolidation, reported for completeness.

---

## 4. How this feeds the SSOT engine (G-1) and the enforcement hooks (G-3)

**G-1 SSOT engine.** The three canonical declarations (§1) become the engine's authoritative
render-sources: ONE typed logical catalog per domain → deterministic **Claude+Codex** adapters
generate every config surface. The engine *eliminates the drift class* by generating projections
instead of hand-maintaining copies — directly resolving `D1/D7/D8/D9` (MCP drift + hand-kept
template), `S-RC1/S-RC3/S-RC4` (provider mislabel, source fork, non-derived daily), and
`H-DD1/H-PV` (dispatcher source fork + live≠git). Antigravity/Gemini are **dropped** from the SSOT
scope per G-1 (2 provider adapters).

**G-3 enforcement hooks.**
- **Cleanup hook** — the dedup/remove/purge/prune rows (`M-DD1`, `M-ST*`, `S-DD*`, `S-SL*`, `S-SU*`,
  `H-RR*`, `H-RM*`, `H-ST1`) are its PROPOSE-removal backlog: **aggressive on provably-dead** (G-12),
  **salvage-first**, **evidence-first on ambiguous** (codacy/deepsource `D6` STAYS until owner decides).
- **Doc-reconciliation hook** — a HARD pre-commit block: a harness/MCP/skill/hook change cannot commit
  without its doc + manifest + toolchain PR; stale-work/duplicate-doc fails the commit (STRONG-BUT-SAFE,
  OFF→SHADOW→ADVISE→ENFORCE, fail-open). The 22-gem back-port (`S-BP`) and the daily-derived flip
  (`S-RC4`) are its canonical test cases — an adoption with no source must fail the gate.
- **Harness-change→doc+PR** — the `H-PV` provenance close (enshrine on main + bundle digest) is the
  prerequisite the hook asserts on every deploy.

**G-13 sequencing.** ALL rows are POST-APPROVAL-GATE, staged: **Wave-1 reliability** (`H-PS` plugin
Stop-hook fix + `H-PV` provenance) → **Wave-2 SSOT** (G-1 engine consuming the 3 declarations,
resolving every reconcile row) → **Wave-3 cleanup** (the dedup/remove/purge/prune backlog via the
G-3 cleanup hook). Read-only discovery produces ONLY this disposition plan; no early-win mutation.

---

## 5. Receipts

- Inputs: `C-mcp-reconcile.json` (dedup 1 / stale 6 / drift 9), `C-skills-reconcile.json` (283 source /
  22-gem risk / 750-clone GONE), `C-hooks-reconcile.json` (6,435 / three-way split / 63 residue + 3 plugin Stop).
- Coverage: `A0-wholedrive-census` §1 (12,677,705 rows), `C-config-index-complete.json` meta.totals
  (474 MCP / 15,573 SKILL.md / 6,435 hook / 21,989 indexed / 3,380 excluded).
- Baselines: `A3-mcp-matrix` (69 servers / 9 layers), `A4-skills-dup-matrix` (491 names / 8 lanes),
  `A2-inventory` (65-dir hooks live lane). Gate defs: `GRILL-LOG.md` G-1/G-3/G-12/G-13.
- `SUCCESS:C-config-reconciliation-COMPLETE` — READ-ONLY, freeze respected (no build/commit/config/
  process/deploy/delete change; every disposition is a POST-GATE finding for owner G-13).
