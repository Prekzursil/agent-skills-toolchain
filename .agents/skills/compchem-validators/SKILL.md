---
name: compchem-validators
description: Use when a docking / MD / free-energy campaign needs an OUTPUT quality gate - post-dock pose validity (PoseBusters), a cheap-tier prefilter before the token-gated tiers (Uni-Dock GPU-Vina before Glide, Boltz-2 affinity before FEP+/QDX credits), or a "docking done / ΔG=… / MD converged" claim that should be backed by a validity artifact before it is treated as done. compchem-preflight guards INPUT; this skill guards OUTPUT (a pose can score well yet be physically impossible). Also the map for the open-weights compute arm - MACE-OFF near-DFT MD, OpenFE token-free FEP twin, REINVENT 4 generative loop, PLINDER leakage-free splits, and the TxAgent/ToolUniverse grounded-reasoning pattern (Opus reasoner, not the fine-tuned model). All ride the existing schrodinger / qdx-rush / cloud-hub MCPs - scientific compute is NOT agent runtime. Do NOT use for the receptor-prep-to-dock pipeline itself (use structure-based-screening) or license-free cheminformatics (use cheminformatics-rdkit).
---

# Compchem validators (guard the OUTPUT of a compchem run)

`compchem-preflight` and [[structure-based-screening]] get you a *docked, rescored pose*.
Nothing then checks whether that pose is **physically real** or whether the expensive tier
was **worth spending**. This skill is the output-side quality layer — the domain expression
of the owner's *quality-no-faking* creed.

**Core principle:** a good docking *score* is not evidence of a good *pose*. Glide/Vina will
happily rank a ligand with overlapping atoms, snapped bonds, or a strained ring. Before any
"docking done / ΔG = … / MD converged" claim is treated as done, it should carry a
**validity artifact** — a PoseBusters pass, a redock RMSD, or an MD-convergence check.

Evidence: MASTER-DECISION-QUEUE **E.4** (PoseBusters · Uni-Dock · Boltz-2 · MACE-OFF · OpenFE ·
REINVENT 4 · PLINDER · TxAgent pattern) and COUNCIL-VERDICT **C5** (shadow-mode discipline) /
**C1.5** (domain gates are project-scoped, off-by-default globally).

---

## What ships here (two runnable helpers + a map)

| File | What it does | Runs without heavy deps? |
|------|--------------|--------------------------|
| `posebusters.py` | `check_pose` / `check_poses` pose validity **+** `compchem_claim_advisory` shadow claim-gate | Yes — real PoseBusters when installed, else a coarse geometry floor; the claim-gate is pure-Python |
| `prefilters.py`  | `prefilter_rank` / `prefilter_by_percentile` cheap-tier gating **+** `estimate_savings` funnel economics **+** `STAGE_MCP_ROUTES` | Yes — pure-Python + numpy |

Both are **fail-open** and **advisory** — they observe, rank, and recommend. Nothing blocks,
nags, or raises.

---

## 1. Pose validity — `posebusters.py`

```python
from posebusters import check_pose, check_poses     # helpers in THIS skill dir

r = check_pose("pose_0.sdf", cond="dock")           # or cond="redock"/"mol"
print(r.marker())          # POSEBUSTERS:PASS id=pose_0.sdf engine=posebusters ok
if not r.valid:
    print(r.failures)      # e.g. ['no_internal_clash', 'bond_lengths_in_range']
```

- **Authoritative path:** when the PyPI [`posebusters`](https://github.com/maabuu/posebusters)
  package is importable, `check_pose` runs its full reference-distribution suite
  (bond lengths/angles, aromatic-ring flatness, internal steric clash, protein-ligand volume
  overlap, etc.) — the standard post-dock validity bench (PoseBusters, *Chem. Sci.* 2024).
- **Fallback path (this host):** RDKit + PoseBusters are **not** installed under Python 3.14
  (known py3.14 incompat). `check_pose` then degrades to `engine="geometry-fallback"` — a
  **coarse, honestly-labelled** floor (bond-length range + non-bonded heavy-atom clash + atoms
  connected). It catches an *obviously* broken pose but is **not** the authoritative check;
  install `posebusters` (in a py≤3.12 env) for that. The report says which engine ran — never
  read a fallback pass as a PoseBusters pass.

`PoseReport` fields: `valid`, `engine`, `checks`, `failures`, `summary`, `n_atoms`, `n_bonds`,
`.marker()` (terminal-state string per AGENTS.md §4).

---

## 2. The SHADOW claim-gate — `compchem_claim_advisory`

The queue folds a compchem physical-validity gate into `claim_warning`: a "docking done / ΔG=… /
MD converged" claim should fire a nudge **unless** a validity artifact is present. That gate
logic lives here as an importable **SHADOW-mode** helper (COUNCIL C5). It **observes + logs
only — never blocks, never nags, never raises.**

```python
from posebusters import compchem_claim_advisory

adv = compchem_claim_advisory(
    "Docking done, dG = -9.2 kcal/mol",
    artifacts=["run1/mmgbsa-out.csv"],   # optional on-disk artifacts
)
adv["would_fire"]   # True  -> an ENFORCE gate WOULD flag this (no validity artifact)
adv["blocked"]      # False -> invariant: shadow NEVER blocks
adv["advisory"]     # human-readable nudge (or None)
```

- **`would_fire`** is True when a compchem result claim is present with **no co-located validity
  artifact**. Evidence = a lexical marker (`posebusters`, `redock … rmsd`, `rmsd = …`,
  convergence/block-averaging) in the text, **or** an artifact file that actually **EXISTS**
  (a `_pv.maegz` / `mmgbsa*.csv` / `-out.csv` / `*posebusters*` — presence, not a mere mention).
- Detection is **lexical + file-presence only** — same mechanism family as the existing
  `ClaimWarningModule`. No trained critic, no vector-DB, no second runtime (anti-overfit gate).
- Fires the log **only when a claim is actually seen** (keeps the fire-rate hypothesis honest).

**Shadow sink (COUNCIL C5.iii):** would-have-fired events go to a **separate, bounded,
auto-rotating** JSONL — `~/.Codex/gem-hunt-2026-07-12/shadow/compchem-claim-gate.jsonl`
(rotates at 512 KB; override dir with `$COMPCHEM_SHADOW_DIR`) — **not** the main ledger.

**Anti-zombie contract (COUNCIL C5.i):** `posebusters.SHADOW_CONTRACT` carries the named
promotion metric (shadow-precision vs the owner's Codex-reflect corrections on compchem claims),
the promotion bar (≥0.80 over ≥20 fires, false-nag <5 %), the owner, a 30-day graduation
deadline, and a falsifiable fire-rate hypothesis. It graduates OFF→SHADOW→ADVISE→ENFORCE only
by hitting that bar, and auto-retires otherwise — it is never left in shadow limbo.

**Wiring is deliberately NOT done here.** The `claim_warning` module is out of this skill's
scope and is **project-scoped, off-by-default globally** by council decision (C1.5 — a compchem
gate is irrelevant ~95 % of turns and must not occupy a universal slot). This file provides the
callable the gate *would* consume; the harness owner decides if/when to fold it in (as a branch
inside `claim_warning`, wrapped in its own try/except per C1.2), enabled only under a
science-project settings profile.

---

## 3. Cheap-tier prefilter — `prefilters.py`

The expensive tiers (Glide SP/XP tokens, FEP+/QDX EXESS credits) are license/credit-gated and
serial. Spending them on candidates a **cheap GPU model** would have rejected is the waste. This
module ranks candidates by a cheap score and picks the promotion set, and accounts for credits
saved. It is **decision-support, not a blocker** — it proposes; the orchestrator confirms.

```python
from prefilters import Candidate, prefilter_rank

cands = [Candidate(f"m{i}", score=s, source="uni-dock") for i, s in enumerate(vina_scores)]
res = prefilter_rank(cands, top_frac=0.20, cost_expensive=1.0)   # keep the best 20%
print(res.marker())          # PREFILTER:OK stage=uni-dock->glide in=1000 promoted=200 ...
print(res.savings)           # {'n_rejected': 800, 'saved_frac': 0.8, ...}
promote = [c.cid for c in res.promoted]
```

Two prefilter stages (both "cheap model gates expensive model"):

| Stage | Cheap tier | Gates (expensive) | Runtime (existing MCP) |
|-------|-----------|-------------------|------------------------|
| **A** | **Uni-Dock** GPU-Vina (MIT) | Glide SP/XP (schrodinger tokens) | cloud-hub GPU sandbox (Modal/RunPod) |
| **B** | **Boltz-2** open weights (affinity) | FEP+ / QDX EXESS (credits) | qdx-rush (Boltz fold+affinity) or cloud-hub GPU |

Selectors (precedence `threshold` > `top_k` > `top_frac`; default `top_frac=0.25`):
`prefilter_rank(..., top_k=, top_frac=, threshold=, direction=)` where
`direction="lower_is_better"` for docking/affinity **energies** (more negative = tighter),
`"higher_is_better"` for a pIC50-style score. `prefilter_by_percentile(..., percentile=)`
cuts on a data-driven percentile. **Unscored candidates (`score is None`) are held out as
`res.unscored`, never silently dropped** — cheap-score them first, honestly surfaced.

`estimate_savings` funnel: baseline = expensive tier on ALL; prefiltered = cheap-score all +
expensive only on the promoted set → `cost_saved`, `saved_frac`, `reduction_frac`.

`STAGE_MCP_ROUTES` / `recommend_route(stage)` map each stage to the MCP tool that runs its
compute — **this module never calls them** (scientific compute is not agent runtime).

---

## 4. The open-weights compute arm (the map — rides existing MCPs)

These are **compute**, delegated to existing MCPs; none is a new agent runtime. Adopt as the
campaign needs them:

- **MACE-OFF** — near-DFT MLIP for MD via `openmm-ml` (quality tier above a classical force
  field). Runs on cloud-hub GPU. *License-verify (MACE-OFF23 weights) before any commercial embed.*
- **OpenFE** (MIT) — token-free FEP twin; run **alongside** FEP+/QDX on the shortlist as an
  independent second-model cross-check, not a replacement.
- **Boltz-2** (open weights) — binding-affinity predictor ~1000× cheaper than FEP; the Stage-B
  pre-FEP triage (via qdx-rush Boltz fold+affinity). Triage tier, not a substitute for FEP on
  the final shortlist.
- **REINVENT 4** — the missing **generative arm**; closes the generate→dock/score→optimize loop
  (feed the prefilter's promoted set + PoseBusters validity back as the scoring signal).
- **PLINDER** — leakage-free protein-ligand train/test splits; use to build honest benchmark sets
  (feeds the planned 2.10 eval work) so a model isn't graded on data it effectively memorized.

### TxAgent / ToolUniverse grounded-reasoning pattern (Opus reasoner, NOT the fine-tuned model)
Turn the raw `tooluniverse` one-shot tool calls into a **grounded reasoning loop**: **Opus is the
reasoner** (plan → call a ToolUniverse tool → read the grounded result → decide next call →
synthesize with citations), NOT a deployed fine-tuned TxAgent-T1 model. This keeps every step
grounded in a real database call (ChEMBL/OpenTargets/tooluniverse) while the reasoning stays with
the frontier model on the existing bus — no new model to host, no un-cited generation. Use it when
a target/mechanism question needs multiple grounded lookups chained into one answer.

---

## Consumption notes (read before importing)

- **Name-collision:** this file is `posebusters.py`. Imported as the top-level module
  `posebusters` (skill dir on `sys.path`), it **shadows** the PyPI package — so
  `posebusters_available()` honestly returns False and `check_pose` uses the geometry floor. To
  use the **authoritative** PoseBusters, run in an env where the package is installed (py≤3.12)
  and either import these utilities under a distinct namespace (e.g. an `importlib` loader with a
  non-`posebusters` module name) or call `posebusters.PoseBusters` directly. The guard
  (`hasattr(pkg, "PoseBusters")`) makes this safe either way — it never mistakes the skill file
  for the real package.
- **Everything is fail-open and advisory.** No function blocks, nags, or raises on the caller;
  a dependency-absent or bad-input path returns a structured "couldn't verify" result.
- **Tested (this host, Python 3.14.6, numpy only):** 27 checks green — geometry-floor validity
  (valid/clash/absurd-bond/unparsed/file-path/batch), the shadow claim-gate (fires without
  evidence, silent with text/existing-file evidence, ignores mentioned-but-missing artifacts,
  never fires on non-claims, fail-open on bad input, bounded-rotating log written), and the
  prefilter (top_k/threshold/top_frac/percentile selection, savings math, unscored held out,
  both directions, MCP routing map).

## Related
- [[structure-based-screening]] — the receptor-prep → dock → rescore → profile pipeline this guards.
- [[schrodinger-maestro-driver]] — per-tool Schrodinger reference + security model.
- [[qdx-rush]] — QDX/EXESS GPU QM + Boltz fold+affinity (Stage-B compute).
- [[cheminformatics-rdkit]] — license-free RDKit cheminformatics (no Schrodinger token).
