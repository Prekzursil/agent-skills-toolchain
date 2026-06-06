# End-to-End Drug-Discovery Research Workflow

A practical guide to the just-built, locally-verified research stack: three MCP
servers (ToolUniverse, RDKit, Schrodinger) orchestrated by an ultracode-style
loop. It covers the architecture, the tool-routing decision tree, and **two
fully worked examples** — one that runs today with zero licenses (drug-drug
interaction), and one hit-to-lead structure pipeline (the license-gated path,
with its preconditions stated honestly).

> **Scope.** This doc covers only the drug-discovery stack. The classroom MCP
> (gogcli) that was set up in the same session is unrelated and is documented
> separately.

---

## 1. The Stack at a Glance

All three are MCP `stdio` servers, all verified `✓ Connected` via
`claude mcp get` this session.

| MCP | What it is | Tools | License? | Source |
|-----|------------|-------|----------|--------|
| **tooluniverse** | Biomedical knowledge: DDI, ADMET, CYP, targets, FDA labels, repurposing, pharmacovigilance | 2206 | None (public DBs) | `uvx tooluniverse==1.2.4` · Apache-2.0 · Harvard Zitnik lab |
| **rdkit** | Cheminformatics: descriptors, fingerprints, similarity, format I/O | 74 | None | tandemai-inc/rdkit-mcp-server · MIT |
| **schrodinger** | Structure prep, 3D generation, docking, QikProp ADMET | 9 | **Some** (see below) | custom-built local wrapper |

### Server config (cross-platform)

The registered launch commands (Windows shown; POSIX equivalents in the notes):

```
tooluniverse : command "uvx"  args ["tooluniverse==1.2.4"]  env PYTHONIOENCODING=utf-8
rdkit        : <venv-python> run_server.py --transport stdio
schrodinger  : <venv-python> server.py   env SCHRODINGER="D:\Program Files\Schrodinger 2022-4"
```

- **Windows** `<venv-python>` = `.venv\Scripts\python.exe`;
  **POSIX** = `.venv/bin/python`.
- **rdkit GOTCHA:** the server defaults to SSE on port 8000 — you *must* pass
  `--transport stdio` for MCP use. (Build note: upstream pinned a dead
  `rdkit==2025.3.1`; this install uses `rdkit 2026.3.3` installed with
  `pip install --no-deps .`.)
- **schrodinger:** the only knob is the `SCHRODINGER` env var (install root).
  On Windows it points at `D:\Program Files\Schrodinger 2022-4`; on POSIX set it
  to your suite root. The wrapper auto-resolves `run.exe`/`glide.exe` on Windows
  and bare `run`/`glide` on POSIX — no path edits needed when porting.

---

## 2. Schrodinger MCP — the 9 tools (exact surface)

The wrapper **never imports `schrodinger` in-process** (that only works under
`$SCHRODINGER/run`). Every tool builds an argv list and hands it to one
non-tool `_exec()` chokepoint (`subprocess.run`, never `shell=True`). Client
paths pass through `_safe_path()` first (rejects empty/flag-like values,
normalizes to absolute) before they can reach any argv — so untrusted tool
params never reach a shell. License-token-free tools shell out to a helper
(`_sch_helper.py`) running inside the Schrodinger interpreter; the driver tools
run the product binaries with `-WAIT` (synchronous).

**License-token-FREE (safe, fast, no checkout):**

| Tool | Signature | Returns |
|------|-----------|---------|
| `schrodinger_version` | `()` | suite version string (from `run -v`) |
| `backend_info` | `()` | build + bundled RDKit version + install path |
| `smiles_to_3d` | `(smiles, out_path, title="")` | 3D `.sdf`/`.mae` (RDKit ETKDGv3 + MMFF; extension picks format) |
| `molecule_properties` | `(smiles)` | formula, MW, logP, HBD/HBA, TPSA, rot-bonds, rings, QED, Lipinski pass |
| `convert_structure` | `(src, dst)` | format convert `.sdf`↔`.mae`↔`.pdb` |
| `run_schrodinger_python` | `(code, timeout_s=300)` | escape hatch — arbitrary code in the Schrodinger interpreter (local single-user only) |

**License-token-CONSUMING (synchronous `-WAIT` product drivers):**

| Tool | Signature | Returns |
|------|-----------|---------|
| `ligprep` | `(input_file, output_mae, timeout_s=1200)` | prepared 3D ligand states (ionization/tautomer/stereo) → MAE |
| `qikprop_admet` | `(structure_file, timeout_s=900)` | QikProp ADMET/physchem CSV path + head |
| `glide_dock` | `(grid_file, ligands_mae, precision="SP", timeout_s=3600)` | `*_pv.maegz` pose-viewer; `precision` ∈ `HTVS\|SP\|XP` |

> **CRITICAL PRECONDITION for `glide_dock`:** it docks ligands into a
> **pre-existing receptor grid** (`grid_file`, validated `must_exist=True`,
> written as `GRIDFILE` into the Glide `.in`). **None of the 9 MCP tools build a
> grid.** You must produce the grid `.zip` beforehand in Maestro (Receptor Grid
> Generation) or via the `glide` grid driver — that step is *not* exposed by
> this server. Treat the grid as an input, not something the workflow creates.

---

## 3. RDKit MCP — the interface model

RDKit tools pass molecules as **base64-encoded pickled Mol handles**, not raw
SMILES, between steps. The conversion tools are the entry/exit points; the
descriptor/similarity tools mostly take SMILES directly. Confirmed tool names:

- **I/O & handles:** `smiles_to_mol`, `mol_to_smiles`, `smarts_to_mol`,
  `mol_to_sdf`, `sdf_to_mol`, `sdf_contents_to_mol`, `pdb_to_mol`,
  `pdb_contents_to_mol`, `mol_to_pdb`
- **Descriptors (SMILES → number):** `MolWt`, `ExactMolWt`, `HeavyAtomMolWt`,
  `NumValenceElectrons`, `NumRadicalElectrons`, `FpDensityMorgan1/2/3`,
  `MaxPartialCharge` / `MinPartialCharge` (and abs variants), plus the wider
  `rdMolDescriptors` / `Descriptors` families (74 tools total)
- **Similarity:** `TanimotoSimilarity(smiles1, smiles2, radius=2, nBits=2048)`
  → Morgan-fingerprint Tanimoto, 0.0–1.0
- **Scaffolds / matched pairs:** Murcko scaffold (`MurckoScaffold`),
  MMPA (`rdMMPA`), 2D depiction (`rdDepictor`)

> For a one-call drug-likeness panel, **Schrodinger's `molecule_properties`** is
> the cleanest (MW/logP/HBD/HBA/TPSA/QED/Lipinski in a single license-free
> call). Reach for the RDKit MCP when you need **similarity clustering, scaffold
> analysis, fingerprints, or batch descriptor sweeps** across a candidate set.

---

## 4. Architecture & the ultracode loop

```
                         ┌──────────────────────────────┐
                         │      RESEARCH QUESTION        │
                         │  "Does A interact with B?"    │
                         │  "Score these vs target X"    │
                         └───────────────┬──────────────┘
                                         │
                              ┌──────────▼───────────┐
                              │   ULTRACODE LOOP      │   orchestrator
                              │  plan → fan-out →     │   (Claude Code)
                              │  verify → synthesize  │
                              └──┬────────┬────────┬──┘
                  ┌──────────────┘        │        └──────────────┐
                  │ DISCOVER (parallel)   │ VERIFY (parallel)     │ SYNTHESIZE
                  ▼                       ▼                       ▼
   ┌───────────────────────┐ ┌───────────────────────┐ ┌──────────────────────┐
   │   tooluniverse  MCP    │ │      rdkit  MCP        │ │   schrodinger  MCP   │
   │ KNOWLEDGE / EVIDENCE   │ │   CHEMINFORMATICS      │ │ STRUCTURE / DOCKING  │
   ├───────────────────────┤ ├───────────────────────┤ ├──────────────────────┤
   │ ChEMBL_get_drug_      │ │ smiles_to_mol          │ │ molecule_properties  │
   │   mechanisms          │ │ MolWt / TanimotoSim... │ │ smiles_to_3d         │
   │ drugbank_get_drug_    │ │ Murcko scaffold / MMPA │ │ ligprep    (license) │
   │   interactions...     │ │ fingerprint sweep      │ │ glide_dock (license) │
   │ DailyMed FDA labels   │ │                        │ │ qikprop_admet(license)│
   │ PubMed_search_articles│ │                        │ │ convert_structure    │
   │ ADMET / CYP / targets │ │                        │ │                      │
   └──────────┬────────────┘ └──────────┬─────────────┘ └──────────┬───────────┘
              └─────────────────┬────────┴──────────────┬──────────┘
                                ▼                        ▼
                       ┌──────────────────────────────────────┐
                       │   adversarial VERIFY / reconcile      │
                       │  (evidence-grade, cross-tool agree?)  │
                       └────────────────┬─────────────────────┘
                                        ▼
                       ┌──────────────────────────────────────┐
                       │        SYNTHESIZED REPORT  (.md)      │
                       │  cited, evidence-graded, actionable   │
                       └──────────────────────────────────────┘
```

**The loop, numbered:**

1. **Frame the question** and pick the lane (knowledge vs cheminformatics vs
   structure — see the routing table in §5).
2. **Plan & decompose** — the orchestrator writes a report skeleton FIRST
   (report-first), then lists the sub-queries to fan out.
3. **DISCOVER (parallel fan-out)** — independent MCP calls run concurrently:
   ToolUniverse for evidence, RDKit for fast triage descriptors, Schrodinger
   for license-free structure work. Independent calls go in one batch.
4. **VERIFY (parallel, adversarial)** — cross-check claims against a second
   source (e.g., a mechanism predicted by reasoning must be confirmed by an FDA
   label or PubMed hit). Grade each claim by evidence quality (★★★ FDA label,
   ★★☆ clinical study, ★☆☆ theoretical).
5. **Gate the expensive steps** — only after triage/verify do you spend license
   tokens (ligprep/glide/qikprop). Cheap, license-free filtering first.
6. **SYNTHESIZE** — collapse findings into one cited markdown report with an
   explicit recommendation and any "no interaction / no result" statements made
   explicit (never silent gaps).

---

## 5. Tool-routing decision tree

| If you need… | Use | Cost |
|--------------|-----|------|
| Known DDIs, mechanisms (CYP/UGT/transporter), FDA labels, pharmacovigilance, repurposing, target/disease links | **tooluniverse** | free |
| ADMET *prediction from a structure* (physicochemical, BBB, CYP liability) on a 3D molecule | **schrodinger** `qikprop_admet` | license |
| ADMET *knowledge/lookup* (no structure needed) | **tooluniverse** | free |
| Drug-likeness panel for one SMILES (MW/logP/QED/Lipinski) | **schrodinger** `molecule_properties` | free |
| Similarity, scaffold clustering, fingerprints, batch descriptors over many candidates | **rdkit** | free |
| SMILES → quick single-conformer 3D (triage) | **schrodinger** `smiles_to_3d` | free |
| Rigorous 3D ligand prep (ionization/tautomer/stereo enumeration) | **schrodinger** `ligprep` | license |
| Dock ligands into a target pocket | **schrodinger** `glide_dock` (+ pre-built grid) | license |
| Format conversion (.sdf/.mae/.pdb) | **schrodinger** `convert_structure` or **rdkit** I/O tools | free |

---

## 6. Worked Example A — "Does drug A interact with drug B, and why?"

**Status: runs today, zero licenses.** Pure ToolUniverse knowledge work; the
`tooluniverse-drug-drug-interaction` skill drives it. Concrete pair:
**valproate + lamotrigine.**

**Step 0 — Report-first.** Create `DDI_risk_report_valproate_lamotrigine.md`
with the section skeleton (Executive Summary, Drug Profiles, PK, PD, Evidence,
Risk Score, Management, Monitoring, Alternatives) and `[Analyzing...]`
placeholders.

**Step 1 — Reason before querying (perpetrator-victim model).** Lamotrigine is
cleared >90% by **UGT1A4** glucuronidation; valproate is a potent **UGT1A4
inhibitor**. Predict: valproate = *perpetrator* (inhibitor), lamotrigine =
*victim* → lamotrigine levels roughly **double** → SJS/TEN risk. This is a
**Phase II / UGT** interaction, not CYP — the most commonly *missed* class.

**Step 2 — DISCOVER (parallel ToolUniverse calls):**
- `ChEMBL_get_drug_mechanisms` — mechanism / metabolic enzyme data for each drug
- `drugbank_get_drug_interactions_by_drug_name_or_id` — known documented DDIs
- `DailyMed_get_spl_by_setid` — the **FDA label** warning (highest evidence tier)
- `PubMed_search_articles` — clinical study / case-report corroboration

**Step 3 — VERIFY (bidirectional + evidence grade).** Confirm both directions
(A→B and B→A; here the dominant effect is valproate→lamotrigine). Grade: FDA
label present ⇒ ★★★. Sanity-check magnitude — a potent inhibitor giving ~2×
matches the literature; if a tool returned "10×" you'd reconsider the mechanism.

**Step 4 — SYNTHESIZE.** Severity **Major**; mechanism **UGT1A4 inhibition →
blocked lamotrigine glucuronidation → ~2× levels → Stevens-Johnson syndrome**;
management **halve the lamotrigine dose, titrate slowly, monitor for rash**;
alternatives that avoid UGT1A4 if needed. Risk score computed (severity base +
evidence modifier). All placeholders resolved, sources cited.

**One-line answer:** *Yes — valproate inhibits lamotrigine's UGT1A4
glucuronidation, doubling lamotrigine exposure and risking SJS; halve the
lamotrigine dose.*

---

## 7. Worked Example B — hit→lead: "score these candidate molecules vs a target"

**Status: a license-gated pipeline, not turnkey.** It requires (a) a valid
`$SCHRODINGER` install, (b) **license tokens** for `ligprep` / `glide_dock` /
`qikprop_admet`, and (c) — critically — **a pre-built Glide receptor grid
`.zip`** (made in Maestro / the glide grid driver; *no MCP tool generates it*).
The free triage steps (§7.1) run today regardless.

Assume a handful of candidate SMILES and a known target with an existing grid
`grid.zip`. Work under one staging directory (e.g. Windows
`D:\dd-run\` or POSIX `~/dd-run/`).

### 7.1 Free triage (no tokens) — fan out in parallel

1. **Drug-likeness gate** — `schrodinger.molecule_properties(smiles)` per
   candidate → drop anything failing Lipinski / with poor QED / TPSA out of
   range. (One call gives MW/logP/HBD/HBA/TPSA/rot-bonds/rings/QED/Lipinski.)
2. **Diversity / redundancy** — `rdkit.TanimotoSimilarity(smiles_i, smiles_j)`
   pairwise; cluster near-duplicates (high Tanimoto) so you don't dock the same
   chemotype five times. Optionally `rdkit` Murcko scaffold to group by core.
3. **Quick 3D for the survivors** — `schrodinger.smiles_to_3d(smiles, out_path)`
   writing `.sdf` for a fast look, or `.mae` if going straight to Glide.

After §7.1 you have a deduplicated, drug-like shortlist. *Only now* spend tokens.

### 7.2 Rigorous prep + docking (license tokens)

4. **Prepare ligand states** — `schrodinger.ligprep(input_file=shortlist.smi,
   output_mae="ligs_prepared.mae")` → proper ionization/tautomer/stereo
   enumeration (more rigorous than the §7.1 single conformer). *Consumes a
   LigPrep token; runs `-WAIT`.*
5. **Dock into the target** — `schrodinger.glide_dock(grid_file="grid.zip",
   ligands_mae="ligs_prepared.mae", precision="SP")`. Tier the precision:
   `HTVS` for a big set → `SP` → `XP` on the top survivors. Returns
   `glide_dock_job_pv.maegz` (pose viewer with docking scores). *Consumes a
   Glide token.*
   - **Precondition reminder:** `grid.zip` must already exist — build it in
     Maestro first.
6. **Predict ADMET on the docked hits** — `schrodinger.qikprop_admet(
   structure_file="ligs_prepared.mae")` (or the pose file) → ADMET/physchem CSV
   (logP, solubility, CNS, CYP2D6, %human oral absorption…). *Consumes a
   QikProp token.*

### 7.3 Verify + synthesize

7. **VERIFY (cross-tool).** Take the top docking scorers and pull *knowledge*
   back from **ToolUniverse**: is the target/scaffold already drugged?
   (`ChEMBL_get_drug_mechanisms`), known liabilities / pharmacovigilance
   signals, and a literature check (`PubMed_search_articles`). This catches
   "great dock score, terrible real-world ADMET / known tox" before you commit.
8. **SYNTHESIZE** the lead-ranking report: a table per surviving candidate with
   {Lipinski/QED (RDKit/Schrodinger), Tanimoto cluster, Glide score, QikProp
   ADMET flags, ToolUniverse evidence}, a recommended top-N, and explicit
   rationale for every drop.

**Pipeline shape (honest version):**

```
SMILES set
  │  molecule_properties (free)  ── drug-likeness gate
  │  TanimotoSimilarity (free)   ── dedupe / cluster
  ▼
shortlist ──smiles_to_3d (free, triage 3D)
  │
  │  ===== license tokens beyond this line =====
  ▼
ligprep ──► ligs_prepared.mae ──► glide_dock(+ pre-built grid.zip) ──► poses (_pv.maegz)
                                       │
                                       ▼
                                  qikprop_admet ──► ADMET CSV
                                       │
                                       ▼
                  VERIFY vs ToolUniverse (mechanism / tox / literature)
                                       │
                                       ▼
                              ranked lead report (.md)
```

---

## 8. Operating notes

- **Cheap-before-expensive is the core discipline:** free triage
  (`molecule_properties`, `TanimotoSimilarity`, ToolUniverse knowledge) gates
  every license-token step. Never dock or QikProp a set you haven't filtered.
- **Parallelize independent calls** in one batch (the fan-out phase); only
  serialize where step N+1 consumes step N's output (e.g. ligprep → glide).
- **Driver tools are synchronous** (`-WAIT`) with generous timeouts
  (ligprep 1200s, qikprop 900s, glide 3600s) — expect them to block.
- **Format choice matters:** `smiles_to_3d` extension picks the format — use
  `.mae` when feeding Glide/Prime downstream, `.sdf` for portability/inspection.
- **Security model:** the Schrodinger wrapper validates all client paths
  (`_safe_path`) and centralizes every subprocess in one non-tool `_exec()` with
  no shell — but `run_schrodinger_python` is an arbitrary-code escape hatch:
  local single-user use only.
- **Porting Windows → POSIX:** change `$SCHRODINGER`, use `.venv/bin/python` in
  the rdkit/schrodinger launch commands, and the wrappers auto-resolve the
  bare `run`/`glide` binaries. ToolUniverse (`uvx`) is identical on both.
