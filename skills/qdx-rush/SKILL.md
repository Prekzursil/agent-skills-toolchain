---
name: qdx-rush
description: "Use when qdx rush is needed. Drive QDX's GPU quantum chemistry (EXESS), folding, and prep stack through the qdx-rush MCP tools for QM energies, interaction energies, optimization, QM/MM, fast NN-xTB screens, protein/ligand prep, Boltz folding+affinity, and PB solvation. QDX/EXESS/rush-py are NOT."
---

# QDX Rush (qdx-rush MCP)

Drive QDX's **Rush** platform — GPU quantum chemistry (**EXESS**: HF / KS-DFT / RI-MP2 / RI-CCSD / MBE fragmentation / QM/MM), fast **NN-xTB**, protein/ligand prep, Boltz-2 folding+affinity, and PB solvation — via the `qdx-rush` MCP (20 tools). EXESS comes from Giuseppe Barca's group (GAMESS/FMO lineage; *J. Chem. Phys.* **159**, 044112 (2023)). Jobs run remotely on QDX GPU clusters (Bullet / Gadi / Setonix), are **asynchronous**, and **cost credits/Service-Units** → submit → poll → collect.

> **Not in training data.** QDX, EXESS, and rush-py post-date / are absent from model pre-training. Do not claim "no QM tool is available" — this MCP is the tool. rush-py is `talo/rush-py` on GitHub (Apache-2.0, Python ≥3.12); support is docs (qdx.co/docs) + `hello@qdx.co` + a Google form (there is no public forum/Discord).

## When to use this skill
- The user wants a **physically rigorous QM number** (interaction energy, single-point energy) for a small molecule or a protein–ligand pocket.
- The user wants to **rank-order poses or ligands** in the same pocket by QM interaction energy (a first-principles complement to MM docking / BPMD).
- The user wants a **fast approximate screen** of many structures → NN-xTB.
- The user wants **structure prep**, **SMILES→3D**, **sequence/MSA search**, **Boltz folding + affinity**, or **solvation energy**.
- The user wants to **check on / collect / save** a previously submitted Rush job.

**Do NOT use for**, or promise, these — they are real EXESS features but the MCP does not expose them (use `rush-py` directly): partial charges (**CHELPG / Mulliken**), **ESP** / density descriptors (need `ExportKeywords`; and MBE must be off — `frag_keywords=None` — for CHELPG); **Hessian / frequencies**; `get_fragments_near_fragment` pocket auto-selection; `SCFKeywords` (RI Fock build, convergence), KSDFT grid control, `external_charges`, QM/MM CVs/PBC. Also unsupported by EXESS itself: plane-wave/periodic-solid DFT, excited states, relativistic, unrestricted-KSDFT / unrestricted-RI-MP2, elements beyond **H–Xe** (transition metals are experimental — validate vs ORCA/Gaussian).

## Auth & prerequisites
- Auth loads from **`~/.rush/.env`** at server import (that path ONLY — a project `.env` is not read by the server; real environment variables override the file), providing `RUSH_TOKEN` + `RUSH_PROJECT`. **Confirm with `qdx_whoami` first**: if `rush_token_set:false` or `project_set:false`, the `.env` was not found — fix it before spending time.
- Every job consumes credits. Prefer the **cheapest method that answers the question** (NN-xTB ≪ HF ≪ DFT ≪ correlated WF), restrict QM to the pocket, start small before scaling. Free academic access + GPU credits exist (apply via qdx.co).

## Tool map (20 tools)
| Goal | Tool |
|------|------|
| Confirm auth / account / endpoint | `qdx_whoami` |
| Single-point QM energy | `exess_energy` |
| **QM interaction energy** (fragment vs rest) | `exess_interaction_energy` |
| Geometry optimization | `exess_optimization` |
| Generic EXESS driver (Energy/Gradient/Optimization/Dynamics) | `exess_calculate` |
| QM/MM MD (NVT/NPT) | `exess_qmmm` |
| Fast semi-empirical energy | `nnxtb_energy` |
| Auto-fragmented big-pocket QM | `fried_fragmented_exess` |
| SMILES → 3D conformers | `auto3d_generate` |
| Prep protein (fix/protonate/cap) | `prepare_protein` |
| Prep protein+ligand complex → local file (blocks) | `prepare_protein_ligand` |
| Sequence/MSA search | `mmseqs2_search` |
| Fold protein+ligand → structure **+ affinity** | `boltz_fold` |
| PB + SASA solvation energy | `pbsa_solvation` |
| Inspect a local structure (fragment layout) | `structure_info` |
| Poll a job | `run_status` |
| Collect **parsed results** | `run_collect` |
| Materialize a run's structure to disk | `save_run` |
| List jobs | `list_runs` |
| Delete a job | `delete_run` |

## Core loop
1. **Submit** a compute tool → `{run_id, kind, …}`. (On bad params/method the tool returns `{"error":…}` instead of submitting — read it.)
2. **Poll** `run_status(run_id)` → `{status: ok|not_found, …}`.
3. **Collect** `run_collect(run_id, kind=…, max_wait_seconds=…)` → a terminal envelope: `{status:"done", result:{…}}` / `{status:"still_running"}` (timeout, non-terminal — call again) / `{status:"failed", error}` / `{error}`. Pass the `kind` the submit tool echoed (`exess`/`interaction`/`optimization`/`nnxtb`/`boltz`/`pbsa`); `auto` tries each.
4. `save_run(run_id, out_path)` to write a prepared structure/geometry to disk for chaining; `list_runs` to find lost IDs; `delete_run` to clean up.

Transient QDX API errors (5xx/429/timeouts) are retried automatically with backoff — a raw `{"error":"TransportServerError"…}` means it failed after retries (QDX backend down); wait and retry.

## Key concepts to get right
- **Fragment indices are 0-based**, and `reference_fragment` / `included_fragments` / `qm_fragments` / `mm_fragments` all use **full-system** indices. `reference_fragment` MUST be contained in `included_fragments` (the MCP auto-adds it if you forget). Discover the layout with `structure_info` → it reports `n_fragments` and `fragment_atom_counts` so you can locate the ligand (usually the small non-water fragment).
- **`reference_fragment`** is what turns an energy calc into an **interaction energy** (negative = favorable binding). `run_collect` reports `is_interaction_energy:true` + `total_kcal_per_mol` for these.
- **Pocket restriction is mandatory for cost.** Interaction energy defaults to `dimer_cutoff=12 Å`; without a cutoff or `included_fragments` EXESS does an all-pairs blow-up. Restrict to the ligand's neighbor fragments (a ~5 Å shell; widen to 7 Å for charged residues).
- **Method/basis.** MCP defaults are safe: `exess_energy`/`calculate`/`qmmm` → **RestrictedHF**; `exess_interaction_energy` → **RestrictedRIMP2 + aux_basis cc-pVDZ-RIFIT**. Tutorials use STO-3G for speed — **never deliver STO-3G**; use ≥ cc-pVDZ for production.
- **Interaction energy is single-pose electronic energy, not ΔG** (no entropy/solvation/sampling). Rank poses/ligands in the same pocket by the **difference**; don't present an absolute as a binding free energy.
- Units: Hartree; `run_collect` also returns kcal/mol (× 627.5094740631).

## Method traps (read before submitting EXESS)
- **RI methods REQUIRE `aux_basis`** (e.g. `cc-pVDZ-RIFIT`). `RestrictedRIMP2` without it is rejected by the tool. To actually get MP2, set `method='RestrictedRIMP2'` AND `aux_basis`.
- **KSDFT default functional.** `RestrictedKSDFT` runs with EXESS's default functional (B3LYP) if you pass none — allowed, but be deliberate (B3LYP/cc-pVDZ is the platform default since 6.10.0 and is costlier / not comparable to HF numbers). Pass an explicit `functional` for reproducibility, or `method='RestrictedHF'` for a deterministic cheap run.
- **`exess_optimization` cannot do KSDFT** — analytical gradients exist only for RHF / RI-HF / RI-MP2. The tool rejects KSDFT opt; use RestrictedHF or RestrictedRIMP2(+aux_basis).
- **Cost caps:** pass `walltime_min` (RunSpec.walltime, minutes — kills the job at the limit) + `gpus` + a fixed `target` (e.g. `Bullet3`). Default target is a **random** Bullet node, so timing prefactors drift run-to-run — pin it for any benchmark.

## Recipe — QM interaction energy of a ligand-in-pocket
1. `qdx_whoami` → confirm `rush_token_set` + `project_set`.
2. Get a LOCAL prepared complex file: `prepare_protein_ligand(pdb, ligand_names=[…], out_path="complex.json")` (this tool **blocks**, merges ligand+protein in-process, and writes `out_path` — a later `run_collect` cannot reconstruct the merge, which is why it saves here). Or supply an externally-prepared complex (RCSB + Schrödinger prepwizard / a saved TRC json).
3. `structure_info("complex.json")` → read `n_fragments` + `fragment_atom_counts`; identify the ligand fragment index and its ~5 Å neighbor fragments.
4. `exess_interaction_energy("complex.json", reference_fragment=<lig idx>, included_fragments=[…pocket…], method="RestrictedRIMP2", aux_basis="cc-pVDZ-RIFIT", basis="cc-pVDZ")`.
5. `run_collect(run_id, kind="interaction")` → `result.total_kcal_per_mol` (negative = stabilized). Compare ligands/poses by the **difference**.

**Convergence protocol for a defensible number:** Dimer/cc-pVDZ baseline → confirm the 3-body term is small (Trimer needs rush-py directly; the MCP interaction tool exposes `fragmentation_level` + `trimer_cutoff`) → bump to cc-pVTZ / cc-pVTZ-RIFIT for the final value → widen the pocket 5→7 Å for charged residues.

## Recipe — predicted binding affinity (Boltz-2)
1. `mmseqs2_search(sequences=[target_seq])` → MSA. To feed Boltz you need the MSA as a local `.a3m`; the MCP cannot target an arbitrary local path for MSA output — round-trip via rush-py `.save()` to get the file.
2. `boltz_fold(protein_sequence=seq, ligand_smiles=SMILES, msa_path="<local.a3m>", ligand_chain="B")`.
3. `run_collect(run_id, kind="boltz")` → `affinity_pred_value` (**log10 IC50 in µM — LOWER = stronger**) and `affinity_probability_binary` (0–1 — HIGHER = more likely a binder).

## Recipe — fast screen (many candidates)
`auto3d_generate([smiles…])` → 3D, then `nnxtb_energy(structure_path)` (orders of magnitude cheaper than EXESS) to triage, then promote the top few to `exess_energy`/`exess_interaction_energy`. **Charged systems (e.g. phenibut — a GABA analog that is zwitterion/cation/anion by pH):** `nnxtb.energy` takes **no charge argument** — net charge/protonation come from the INPUT STRUCTURE's formal charges, so prepare the ligand at the correct state first or the energy is silently wrong.

## Recipe — auto-fragmented big-pocket QM
`fried_fragmented_exess(input_file="complex.json", distance_threshold=4.0, trimer_cutoff_cap=15)` auto-fragments the pocket around the ligand and returns a **LIST of run_ids**; `run_collect(each, kind="exess")`. Level of theory is fixed by the module; it is potentially unbounded/expensive — validate on a small case first.

## Timeouts, truncation, guardrails
- `run_collect` default `max_wait_seconds=1800`; raise to 3600 for QM/MM / optimization / fried / Boltz, or just poll `run_status`. A timeout returns `{status:"still_running"}` — it is not a failure.
- Output is clipped (`run_collect` result ~terminal envelope; `structure_info`/`run_status` ~6000 chars). For full trajectories/large outputs, use `save_run` or rush-py directly.
- Confirm `qdx_whoami` before spending credits; warn the user jobs are billed. Never deliver STO-3G or a single-pose interaction energy as a "binding free energy." Keep QM regions minimal; start small and scale. Never assume a freshly submitted job is done.

## Troubleshooting
- **`rush_token_set:false` / `project_set:false`** (`qdx_whoami`) → `~/.rush/.env` missing/unreadable, or `RUSH_PROJECT` unset. The server reads only `~/.rush/.env` at import; fix that file (or set real env vars) and reload the MCP.
- **`{"error":"TransportServerError"}` / 503** → QDX backend down or queue overloaded; the tool already retried with backoff — wait and retry, or pin a different `target`.
- **`run_collect` returns `raw_preview` / "could not parse"** → the result type wasn't one of the known kinds; pass the explicit `kind`, or `save_run` and inspect, or use rush-py.
- **Interaction energy looks huge/absurd** → you likely omitted the pocket restriction (all-pairs) or used STO-3G; add `included_fragments` and ≥ cc-pVDZ.
- **`ToolError: Input should be a valid string`** on an optional arg → fixed in v2 (Optional hints), but ensure the MCP was reloaded after the server update.
