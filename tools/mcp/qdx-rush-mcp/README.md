# QDX Rush / EXESS MCP (`qdx-rush`)

MCP server wrapping the **`rush-py` 7.1.0** SDK to drive QDX's Rush cloud (quantum chemistry +
drug-discovery) from Claude — built for the phenibut / α2δ work.

## Why it matters
`exess_interaction_energy` gives a **QM-accurate binding energy** (negative = binding) — a
first-principles complement to the MM-level Schrödinger BPMD pose scores.

## Tools (20)
**Quantum chemistry (EXESS)**
| Tool | Purpose |
|------|---------|
| `exess_energy` | single-point QM energy (RestrictedHF default / RI-MP2 / KSDFT, cc-pVDZ…) |
| **`exess_interaction_energy`** | QM interaction/binding energy via `reference_fragment` (negative = binding) |
| `exess_optimization` | geometry optimization (RHF / RI-MP2 — not KSDFT) |
| `exess_calculate` | generic driver (Energy/Gradient/Optimization/Dynamics) |
| `exess_qmmm` | QM/MM MD (NVT/NPT) |
| `fried_fragmented_exess` | auto-fragmented big-pocket QM → list of run_ids |
| `nnxtb_energy` | fast semi-empirical energy/forces (screening) |

**Prep / fold / solvate**
| Tool | Purpose |
|------|---------|
| `auto3d_generate` | SMILES → 3D conformers |
| `prepare_protein` | fix/protonate/cap a protein |
| `prepare_protein_ligand` | prepare a complex → writes a local file (**blocks** to keep the ligand merge) |
| `mmseqs2_search` | sequence/MSA search |
| `boltz_fold` | protein+ligand co-fold **+ affinity** (`affinity_pred_value`) |
| `pbsa_solvation` | Poisson-Boltzmann + SASA solvation |
| `structure_info` | inspect atoms + **fragment layout** (`n_fragments`, `fragment_atom_counts`) |

**Config + run lifecycle**
| Tool | Purpose |
|------|---------|
| `qdx_whoami` | auth + project + rush-py version + GraphQL endpoint |
| `run_status` | poll a run (`not_found` if missing) |
| `run_collect` | wait + return **parsed** results (hartree + kcal/mol); terminal-state envelopes |
| `save_run` | materialize a run's structure to a local file (chain producers → consumers) |
| `list_runs` / `delete_run` | list / clean up runs |

## Auth (no secrets in repo)
Credentials live in **`~/.rush/.env`** (`RUSH_TOKEN`, `RUSH_PROJECT`) — rush-py's standard location,
outside any repo. The server loads it explicitly at startup. Project = **Phenibut**
(`7aa7af6b-992c-4c2c-8f98-491cdc73088c`).

## Runtime
- venv: `.venv` (Python 3.12; 3.14 can't build `libqdx`). `.venv/` is gitignored.
- Registered in `~/.mcp.json`, `D:\Research\.mcp.json`, `D:\Research\projects\phenibut\.mcp.json`.
- Loads on **Claude restart** (MCP config is read at session start).

## v2 hardening (post deep-research audit)
- **`run_collect` returns parsed numbers** — performs the second `ResultRef.from_raw_output(raw).fetch()`, extracts `ManyBodyExpansion` energies, and returns `total_kcal_per_mol` + `is_interaction_energy` (v1 returned only object-store pointers).
- **Retry/backoff** on transient 5xx/429/timeouts; **terminal-state envelopes** (`done`/`failed`/`still_running`/`error`) instead of raw exceptions.
- **Fail-fast validation**: RI methods require `aux_basis`; KSDFT geometry-opt rejected; unrestricted-KSDFT/RI-MP2 rejected.
- **Optional type hints** (`T | None`) so clients that send explicit `null` for unused args don't error.
- `prepare_protein_ligand` blocks + saves the merged complex; `save_run` materializes producer output for chaining.

Still deferred:
- [ ] QDX built-in **deep-research** API (`deep_research_report`) — ties to the earlier deep-research thread

## Full reference + skill
- **`QDX_REFERENCE.md`** (this folder) — canonical reference synthesized from reading all 56 doc pages
  (auth, run lifecycle, TRC format, every module/function, EXESS JSON input, drivers/methods/basis,
  keyword groups, hardware, outputs).
- **Claude skill `qdx-rush`** at `~/.claude/skills/qdx-rush/SKILL.md` — when/how to drive QDX via this MCP.

## EXESS param coverage
The EXESS tools expose: `method`, `basis`, **`aux_basis`** (required for RI-MP2/RI-HF), `functional`
(KSDFT), and cost controls **`gpus` / `walltime_min` / `target`** (Bullet/Gadi/Setonix); interaction-energy
adds **`fragmentation_level`** (Dimer/Trimer/Tetramer), **`dimer_cutoff` / `trimer_cutoff`**, and
**`included_fragments`** (pocket restriction, with `reference_fragment` auto-included); QM/MM adds
`pressure_atm` (NPT) + `qm_fragments` / `mm_fragments`.

Advanced rush-py params NOT wrapped (use rush-py directly): `SCFKeywords`
(fock_build_type='RI', convergence), `KSDFTKeywords` grid, `OptimizationKeywords` (coord system/constraints),
**`ExportKeywords` + descriptor grids (ESP / Mulliken / CHELPG / density / Hessian)**, `get_fragments_near_fragment`
pocket auto-selection, QM/MM CVs/restraints/PBC, the Hessian/Gradient/AIMD drivers as dedicated tools,
`external_charges`, batched topologies, and the QDX deep-research API. See `QDX_REFERENCE.md` for the complete surface.
