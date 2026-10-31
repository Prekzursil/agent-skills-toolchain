---
title: QDX_REFERENCE
type: note
permalink: dqverify-repo-20261013/tools/mcp/qdx-rush-mcp/qdx-reference
---

# QDX / Rush / EXESS — Canonical Reference

QDX exposes its GPU-accelerated quantum chemistry and drug-discovery stack through **Rush**. Three pillars:

- **rush-py** — the Python SDK that submits jobs (QC, MD, folding, prep) and retrieves results.
- **EXESS** (Extreme-scale Electronic Structure System) — QDX's GPU-native quantum chemistry engine (HF, KS-DFT, RI-MP2, RI-CCSD, fragmentation/MBE, QM/MM, AIMD).
- **NN-xTB** — neural-network tight-binding for fast, approximate energies/forces/frequencies.

No-setup visual UIs: EXESS at `https://exess.qdx.co/exess-flow`, the rest of Rush at `https://qdx.co/rush`.

> **Scope note — this reference vs the `qdx-rush` MCP.** This document describes the **full** rush-py / EXESS surface. The `qdx-rush` MCP exposes only the parameters present in each tool's schema (see `~/.claude/skills/qdx-rush/SKILL.md`). Features documented here that the MCP does **not** accept — use `rush-py` directly for these: `ExportKeywords` beyond the CHELPG/Mulliken atom-charge export in `exess_esp_charges`, descriptor grids (**ESP grid descriptors / density**), `SCFKeywords` (RI Fock build, convergence), KSDFT grid control, `OptimizationKeywords` (coordinate system / constraints), Hessian / frequencies, the `get_fragments_near_fragment` pocket selector, `external_charges`, QM/MM collective variables / restraints / PBC, batched topologies, and the built-in deep-research API. EXESS hard limits (apply everywhere): elements **H–Xe** only, no excited-states / relativistic, no unrestricted-KSDFT / unrestricted-RI-MP2, MBE ≤ 4th order, `aux_basis` mandatory for RI methods.

---

## 1. Accounts, Tokens, Projects, Auth

1. **Account:** create at `https://rush.cloud/login`.
2. **Rush token:** Overview tab → accounts page `https://rush.cloud/me` → create/copy API token. This authenticates rush-py.
3. **Project + ID:** `https://rush.cloud/projects` → **New Project** → name → Continue. Landing URL is `https://rush.cloud/project/{PROJECT_ID}/workspace/{WORKSPACE_ID}`; the `{PROJECT_ID}` segment is your project ID. Every run belongs to a project and shows under it in the web UI.
4. **Install:** `pip install rush-py` (also uv/pdm/poetry; PyPI `rush-py`). **Require major version ≥ 6.0** — earlier majors have a different, undocumented design.

### Environment variables

| Var | Meaning |
|-----|---------|
| `RUSH_TOKEN` | Auth token value (required) |
| `RUSH_PROJECT` | Project ID (required) |
| `RUSH_ENDPOINT` | Optional server selector; defaults to production `https://rush.cloud`. Non-default servers need QDX-granted access. |

```bash
export RUSH_TOKEN="your_token_here"
export RUSH_PROJECT="your_project_id"
```
PowerShell: `$env:RUSH_TOKEN = "..."`, `$env:RUSH_PROJECT = "..."`.

### `.env` file (auto-loaded)
rush-py auto-loads `RUSH_TOKEN` and `RUSH_PROJECT` from a `.env`:
```
RUSH_TOKEN=your-token-here
RUSH_PROJECT=your-project-id-here
```
Placement / precedence:
- `.env` in the current project directory, **or** `~/.rush/.env` to share across all projects.
- Current-dir `.env` overrides `~/.rush/.env`.
- **Real environment variables always override `.env`.**

View runs in the web UI: `https://rush.cloud/projects/{PROJECT_ID}/runs`.

---

## 2. Client Design & Conventions

rush-py functions follow a structured argument form:
1. **Input data** first (a TRC system, topology path, etc.).
2. **Configuration** values next (method, basis, keyword objects).
3. **Object-store paths** instead of in-memory values when inputs/outputs are large.

- **Introspection:** `help(exess.energy)`, `help(exess.FragKeywords)`, etc.
- **Automatic file conversion:** where a Topology/Residues/Chains (TRC) tuple is expected, you may pass a `Path` to a **PDB** (proteins), **SDF** (ligands), or a TRC file on disk — rush-py converts it.
- Modules are individual programs; the client provides one primary function per module, faithful to the module's full capability surface (often more than the web UI).

---

## 3. Run Lifecycle (submit / Run / collect / fetch / save)

Every module call **submits asynchronously** and immediately returns a `Run` handle (jobs can be long-running).

```python
run        = exess.energy("input_topology.json")   # submit; returns Run immediately
result_ref = run.collect()                          # block until done -> ResultRef
result     = result_ref.fetch()                      # load result into memory (dataclasses)
paths      = result_ref.save()                       # download outputs to workspace, return paths
```

Convenience shortcuts on `Run`:
- `Run.fetch()` — collect + fetch in one call (in-memory result).
- `Run.save()` — collect + download to workspace, returns `ResultPaths`.
- `Run.collect()` — wait, return `ResultRef`.

`ResultRef` methods: `.fetch()` (in memory), `.save(...)` (write to workspace, naming-config args).

Timing / blocking:
- `max_wait_time` (seconds) on every module function caps how long it waits before timing out.
- `Run.collect()` **default timeout is 1 hour**.

Run metadata & resources are passed per call:
- `run_opts=rush.runs.RunOpts(name=..., description=..., tags=[...], email=<bool>)` — `email=True` sends job-notification emails to the account email.
- `run_spec=rush.runs.RunSpec(...)` — hardware/resources (see §10).

Listing / viewing runs: web UI sidebar, or `history.json` ledger in the workspace (run ID, time created, exact module revision path).

### Objects & the object store
Large inputs/outputs live in a UUID-referenced object store. Returned objects look like:
```json
{ "path": "17e16a82-b659-4fc7-83d1-740f65cfee17", "size": 0, "format": "bin" }
```
- `format` is `json` (directly downloadable) or `bin` (binary). `size` is a placeholder (currently 0).
- **Chaining:** pass an object-store path from one module straight into the next — no download/re-upload needed.
- Helpers (`from rush.objects import ...`): `upload_object`, `save_object`, `fetch_object`, `save_json` (dict → JSON in workspace).

### Workspaces
`Run.save()` / `ResultRef.save()` write into a per-project workspace folder (named by project ID). Outputs never overwrite (object-store paths are unique). A `history.json` ledger tracks all runs. Configure:
```python
from pathlib import Path
from rush import session
session.configure(workspace_dir=Path("/path/to/workspace/"))
```

---

## 4. Core API (rush-py)

| Submodule | Role |
|-----------|------|
| `rush.session` | Client/connection entry; `session.configure(workspace_dir=...)` |
| `rush.runs` | `Run` handle, `RunOpts`, `RunSpec` |
| `rush.objects` | Object store helpers (`upload_object`, `save_object`, `fetch_object`, `save_json`) |
| `rush.mol` | Molecular systems & TRC data model |
| `rush.convert` | Molecule I/O & converters (`pdb.from_pdb`, etc.) |

### TRC molecular format
TRC = **Topology + Residues + Chains** — a JSON format built on QCSchema concepts (comparable scope to PDB/mmCIF).
- **Topology** — atom types (`symbols`), `geometry`, connectivity, charges, and `fragments`.
- **Residues** — molecular subcomponent definitions (`residues`, `seqs`, `seq_ns`, `insertion_codes`).
- **Chains** — usually separate molecules.

A bare Topology (just `symbols` + `geometry`) suffices for simple cases (nearly as minimal as XYZ).

Helpers:
- `from_pdb` / `to_pdb`; `from_json` / `to_json` (static `from_json` on `Topology`, `Residues`, `Chains`).
- `TRC.check()`, `TRC.extend()`, `TRC.new_trc_from_residue_subset(...)` (split into protein-only, ligand-only, or any sub-system; also on Topology/Residues/Chains).
- `Topology.distance_between_atoms(...)`, `.distance_to_point(...)`, `.get_atoms_near_point(...)`, `.get_fragments_near_fragment(frag_index, radius_A)` (select a region around a fragment — key for pocket extraction).
- `Topology.fragment_formal_charges` — per-fragment formal charges.
- `Residues.is_amino_acid(...)`.

---

## 5. Rush Modules & Functions

### EXESS (`from rush import exess`)
Primary entry points (all return a `Run`):

| Function | Purpose |
|----------|---------|
| `exess.calculate(path, driver="Energy", ...)` | Generic entry; set `driver` explicitly |
| `exess.energy(topology, method=, basis=, aux_basis=, scf_keywords=, frag_keywords=, ksdft_keywords=, export_keywords=, standard_orientation=, force_cartesian_basis_sets=, system=, convert_hdf5_to_json=, run_opts=, run_spec=)` | Single-point energy + properties |
| `exess.interaction_energy(topology, ligand_fragment_index, method=, basis=, frag_keywords=, ...)` | QM interaction energy of one fragment vs the rest |
| `exess.optimization(topology, max_iters, optimization_keywords=, standard_orientation=, qm_fragments=, mm_fragments=, ...)` | Geometry optimization (`max_iters` required) |
| `exess.qmmm((topology, residues) or topology_path=,residues_path=, n_timesteps=, dt_ps=, temperature_kelvin=, pressure_atm=, qm_fragments=, mm_fragments=, trajectory=, restraints=, ...)` | QM/MM molecular dynamics |

Notes: `exess.optimization()` does **not** support fragment-based QM (fragments can still define QM/MM regions). rush-py accepts **JSON topology only** (symbols+geometry), not xyz paths (the CLI accepts `{"xyz": "molecule.xyz"}`).

Helper dataclasses: `exess.SCFKeywords`, `exess.FragKeywords`, `exess.KSDFTKeywords`, `exess.XCGridParameters`, `exess.DefaultGridResolution`, `exess.ExportKeywords`, `exess.OptimizationKeywords`, `exess.LBFGSKeywords`, `exess.Trajectory`, `exess.Restraints`, `exess.System`, `exess.RegularDescriptorGrid`, `exess.CustomDescriptorGrid`, `exess.StandardDescriptorGrid`, `exess.DescriptorGrid`. Plus `Topology`, `Residues`, `Residue`, `Fragment`, `Element` from `rush`.

#### `qdx-rush` MCP: ligand partial charges

`exess_esp_charges(structure_path, ...)` submits a full-system EXESS single-point calculation and immediately returns a Rush `run_id`; retrieve the QM-derived atom arrays with `run_collect(run_id, kind="charges")`. It deliberately sets `frag_keywords=None` and requests JSON exports. `structure_path` must contain a ligand-only topology whose protonation and formal charge are already correct; there is no separate charge argument.

- Default level: Restricted KS-DFT / cc-pVDZ (the EXESS KSDFT default functional applies unless `functional` is set).
- Primary `charges`: CHELPG, an atom-centered fit to the QM electrostatic potential (ESP).
- Diagnostic comparison: `mulliken_charges` from orbital population analysis.
- Units: elementary charge (`e`); arrays preserve the input topology's atom order.
- The submission response includes method, basis, resolved functional, auxiliary basis, charge models, and Rush `run_id`.
- The completed `run_collect` result includes `n_atoms`, `chelpg_charge_sum`, `mulliken_charge_sum`, and the EXESS method.

EXESS has no separate `export_esp_charges` atom-charge product. `export_esp_descriptors` samples the potential on a spatial grid and must not be used as ligand partial charges.

CHELPG is QM-derived, but force fields such as OpenFF Sage are calibrated around their documented charge models (commonly AM1-BCC-family charges). Treat Mulliken as diagnostic-only, preserve the ligand's integer net charge, and validate CHELPG compatibility with the selected force field before production MD; “more expensive” does not by itself mean “better matched.”

### Prepare (`from rush import prepare`)
- `prepare.protein_ligand(pdb_path, ligand_names=[...], run_opts=)` → `Run`; `.fetch()[0]` returns a TRC. Under the hood: **PDBFixer** (missing atoms/residues), **PDB2PQR** (protonation), **RDKit** (ligand). Output is an annotated TRC with connectivity + formal charges.
- `prepare.protein(...)` — protein-only preparation (analogous).

### NN-xTB
Neural-network tight-binding for fast energies, forces, frequencies — orders of magnitude cheaper than EXESS. (Tutorial 7: NN-xTB energy and forces.)

### Other Rush modules referenced
Boltz (folding), Auto3D (3D conformer generation), PBSA (Poisson-Boltzmann surface area solvation), MMseqs2 (sequence search), and more.

---

## 6. EXESS JSON Input Format

Loosely based on MolSSI QCSchema. The molecular group is `topology`; inputs use a `topologies` **array** to batch multiple systems through the same driver/model/keywords.

### Top-level fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `topologies` | array[Topology] | **yes** | one or more systems |
| `residues` | array[Residues] | no | required for QMMM |
| `external_charges` | object | no | `{positions:[flat XYZ Å], charges:[...]}`; len(positions)=3·len(charges); non-Dynamics drivers only |
| `driver` | string | **yes** | Energy / Gradient / Optimization / Dynamics / Hessian / QMMM |
| `model` | object | **yes** | method + basis (see below) |
| `system` | object | no | hardware config |
| `keywords` | object | **yes** (may be `{}`) | calculation parameters |
| `schema_version` | string | — | default `0.2.0` |
| `title` | string | no | printed in output |
| `check_schema` | bool | — | default true |

### Topology object
- `symbols`: array of element symbols (or `Element` enum in Python; `Element.from_str("O")`).
- `geometry`: flat float list `[x1,y1,z1, x2,y2,z2, ...]` (Ångström).
- `fragments`: array of atom-index lists, e.g. `[[0,1,2],[3,4,5]]`.
- (CLI also accepts `{"xyz": "molecule.xyz"}`; rush-py does not.)

### Residues object
`residues` (atom-index lists), `seqs` (residue names), `seq_ns` (residue numbers), `insertion_codes` (required; use `""` when none). `fragment_formal_charges` available on Topology.

### `model` object
```json
{ "method": "...", "basis": "...", "aux_basis": "...",
  "standard_orientation": "FullSystem", "force_cartesian_basis_sets": true }
```
- `method`: `RestrictedHF` | `UnrestrictedHF` | `RestrictedKSDFT` | `RestrictedRIMP2` | `RestrictedRICCSD`. `UnrestrictedRIMP2` is **not supported** (EXESS errors). rush-py default = `RestrictedKSDFT`.
- `basis`: primary basis, required. rush-py default `cc-pVDZ`.
- `aux_basis`: auxiliary basis for RI methods; **required** for RI-HF, RI-MP2, RI-CCSD, and double-hybrid KSDFT (e.g. `cc-pVDZ-RIFIT`).
- `standard_orientation`: `FullSystem` (default) | `None` (keep frame; good for comparing trajectories) | `PerFragment` (can cause inconsistent energies in fragmented runs).
- `force_cartesian_basis_sets`: bool, default true (Cartesian d-orbitals); setting false (spherical) only supported for Energy.

### `system` object (hardware)
| Key | Default | Meaning |
|-----|---------|---------|
| `max_gpu_memory_mb` | unset | per-process cap; when set caps at 90% free GPU mem; when unset 75% free (V100 <20 GB → 50%; non-RI gradient → halved again) |
| `oversubscribe_gpus` | false | multiple processes per GPU (expert) |
| `teams_per_node` | 1 | worker teams per node; one team = one fragment queue |
| `gpus_per_team` | unset | GPUs per team; overridable by `MBE_NGPUS` env var |

Python: `exess.System(max_gpu_memory_mb=24000, teams_per_node=4, gpus_per_team=1)`.

### Minimal example
```json
{ "topologies": [{"symbols": ["O","H","H"],
                  "geometry": [-1.157,0.063,-0.482, -1.157,0.818,-1.077, -1.157,-0.692,-1.077]}],
  "driver": "Energy",
  "model": {"method": "RestrictedHF", "basis": "cc-pVDZ"},
  "keywords": {} }
```
Python equivalent:
```python
from rush import exess, Element, Topology
t = Topology(symbols=[Element.O, Element.H, Element.H],
             geometry=[-1.157,0.063,-0.482, -1.157,0.818,-1.077, -1.157,-0.692,-1.077])
exess.energy(t)
```

### rush-py ↔ EXESS mapping
rush-py does NOT submit full EXESS JSON. It takes a topology path (+ optionally residues path) + keyword dataclasses and builds params internally. rush-py `Model` only carries `standard_orientation` + `force_cartesian_basis_sets` (method/basis/aux_basis are function args). `external_charges` and the `rtat`/`integrals` groups are **not exposed in rush-py**. `frag_keywords` defaults to a dimer setup; pass `frag_keywords=None` for full-system.

### Default resolution order
1. rush-py defaults (any non-None Python value is explicit) →
2. EXESS JSON parser (C++) defaults for omitted fields →
3. EXESS internal defaults for still-unset values.

---

## 7. Drivers

| Driver | What it does | rush-py |
|--------|--------------|---------|
| **Energy** | Single-point energy + properties | `exess.energy` / `exess.calculate(driver="Energy")` |
| **Gradient** | Analytic or finite-difference gradients | (CLI; not a dedicated rush-py entry — set via keywords) |
| **Optimization** | Geometry optimization | `exess.optimization` (`max_iters` required) |
| **Dynamics** | Born-Oppenheimer AIMD (Verlet, **NVE/microcanonical only**) | (CLI driver) |
| **Hessian** | Hessian + vibrational analysis | (CLI) |
| **QMMM** | QM/MM dynamics (NVT/NPT via thermostat/barostat) | `exess.qmmm` |

Interaction energy is an Energy-driver run with a `frag.reference_fragment` set (see §9 frag).

---

## 8. Methods, Basis Sets, Functionals

### Methods (level of theory)
- **RHF** (`RestrictedHF`) — closed-shell HF. Analytical gradients: yes.
- **UHF** (`UnrestrictedHF`) — open-shell. Analytical gradients: **no** (use numerical).
- **RI-HF** — enable via `scf.fock_build_type="RI"` with `method="RestrictedHF"`. Analytical gradients: yes.
- **RI-MP2** (`RestrictedRIMP2`) — the only MP2 implementation; RI by design. Analytical gradients: yes. (`UnrestrictedRIMP2` not supported.)
- **RI-CCSD** (`RestrictedRICCSD`) — in the method list; GPU CCSD energies. Check deployment support before relying on it.
- **KS-DFT** (`RestrictedKSDFT`) — restricted only; **unrestricted DFT not implemented**; analytical gradients **not** available (use numerical).

RI notes: RI reduces compute but raises memory (integrals stored). RI-HF/RI-MP2 allow higher angular momentum (up to F primary, G auxiliary). Always supply a matching `aux_basis` with RI methods.

### Basis sets
- **Pople:** 6-31G, 6-31G\*, 6-31++G\*\*, 6-311G\*\*
- **Dunning (cc):** cc-pVDZ, cc-pVTZ, cc-pVQZ, aug-cc-pVTZ (+ RIFIT auxiliary variants)
- **def2:** def2-SVP, def2-TZVP, def2-TZVPP, def2-QZVP (+ RIFIT variants)
- **STO-nG (minimal):** STO-2G, STO-3G, STO-6G
- **PCSeg:** PCSeg-0, PCSeg-1

> **STO-3G is for tutorial speed only — never production.** Use ≥ cc-pVDZ for meaningful results.

### DFT functionals (`ks_dft.functional`)
LibXC via ExchCXX. Any valid LibXC name (case-insensitive). Invalid name → EXESS errors and prints available functionals. Custom linear combos in ExchCXX syntax, e.g. `0.2*gga_x_pbe+0.8*gga_x_b88+0.2*hf`. Built-in aliases: `SVWN5` (=LDA_X+LDA_C_VWN), `B2PLYP`, `REVDSD-PBEP86-D4`, `REVDSD-PBEP86-D4(NOFC)`.

### Supported elements
H through Xe (Z = 1–54). Transition metals largely untested/experimental — validate against ORCA or Gaussian before production. No plane waves / pseudopotentials.

---

## 9. Keyword Groups (`keywords` object)

Recognized groups: `scf`, `frag`, `ks_dft`, `export`, `regions`, `optimization`, `qmmm`, `gradient`, `guess`, `integrals`, `rtat`, `hessian`, `dynamics`, `boundary`, `force_field`, `log`, `debug`. Defaults below are EXESS CLI defaults; rush-py defaults differ (end of section). Many advanced groups are "Python not supported".

### scf — `exess.SCFKeywords(...)`
- `max_iters` (50): max SCF iterations.
- `max_diis_history_length` (8): DIIS window.
- `batch_size` (2560): shell-pair batches per bin; **use multiples of 128, never below 128**.
- `convergence_metric` (DIIS): `DIIS|Energy|Density`.
- `convergence_threshold` (1e-6): tighten for higher-order fragmentation (1e-6 non-frag/dimer; 1e-8 trimer/tetramer/non-frag Energy; 1e-10 large tetramer).
- `density_threshold` (1e-10): screening; explore 1e-8..1e-12; too large → NaNs; 1e-11/1e-12 slower but crisper MP2 orbitals.
- `gradient_screening_threshold` (1e-10); `bf_cutoff_threshold` (= density_threshold).
- `density_basis_set_projection_fallback_enabled` (auto: on for fragmented, off full-system; reruns SCF in STO-3G and projects).
- `allow_crap_scf` (false, expert); `store_ri_b_on_host` (false); `compress_ri_b` (false) — for tight GPU memory with RI.
- `homo_lumo_guess_rotation_angle` (auto: 45 for unrestricted singlets else 0; 0–180°).
- `fock_build_type` (HGP): `HGP` (dense) | `UM09` (screening-heavy/long chains) | `RI` (needs aux basis, higher mem). Improved screening for >3000 basis functions.
- `exchange_screening_threshold` (1e-5, expert); `group_shared_exponents` (false, UM09 only).

### frag — `exess.FragKeywords(...)`
- `level` (**required**): `Monomer`..`Octamer`.
- `cutoffs` object (Å): keys `dimer/trimer/tetramer/pentamer/hexamer/heptamer/octamer`; keep dimer > trimer > tetramer. (rush-py exposes `dimer_cutoff`, `trimer_cutoff`, `tetramer_cutoff`.)
- `cutoff_type` (ClosestPair): `Centroid` | `ClosestPair` (ClosestPair more accurate, preferred).
- `distance_metric` (Max): `Max` | `Average` | `Min`.
- **`reference_fragment`** (unset): set to a fragment index to compute **lattice/interaction energies** relative to it. Negative result = binding/attractive, positive = repulsion. This is how `exess.interaction_energy` works.
- `included_fragments` (unset): subset treated as an independent system (restrict to binding pocket → much faster).
- `enable_speed` (false, experimental AIMD queue optimization).

N-mer counts scale combinatorially: dimers n(n-1)/2, trimers n(n-1)(n-2)/6, tetramers n(n-1)(n-2)(n-3)/24. Use cutoffs + `debug.dry_run` to validate queue size before running.

### ks_dft — `exess.KSDFTKeywords(functional=, grid=)` (used when method=RestrictedKSDFT)
- `functional` (**required**): LibXC name / linear combo / alias.
- `method` (GauXC): `GauXC | Dense | BatchDense (recommended production) | Direct | SemiDirect`.
- `use_C_opt` (true; Dense/BatchDense only).
- `grid` object (default ULTRAFINE): `radial_quad` (MuraKnowles | MurrayHandyLaming | TreutlerAldrichs); `pruning_scheme` (ROBUST | UNPRUNED | TREUTLER); `consider_weight_zero`.
  - Grid size (choose one): `default_grid` (`FINE | ULTRAFINE | SUPERFINE | TREUTLER_GM3 | TREUTLER_GM5`) **or** `radial_size`+`angular_size`.
  - Batching (choose one): closest-atom (default non-GauXC); `octree` (`max_size` 512, `max_depth`, `max_distance`, `combine_small_children` true); `space_filling` (+`target_batch_size` 1024); `batch_size` (GauXC 512). Priority: octree > batch_size > space_filling; GauXC forces GauXC batching.
- `sp_threshold`, `dp_threshold`, `batches_per_batch` (20, BatchDense only).

rush-py grid: `exess.XCGridParameters(resolution=exess.DefaultGridResolution("SUPERFINE"), radial_quad="TreutlerAldrichs", pruning_scheme="TREUTLER")`. (SUPERFINE grids significantly increase compute time.)

### export — `exess.ExportKeywords(...)` (controls HDF5/JSON output)
Boolean flags (all default false): `export_density`, `export_relaxed_mp2_density_correction`, `export_fock`, `export_overlap`, `export_h_core`, `export_expanded_density`, `export_expanded_gradient` (needs Gradient), `export_molecular_orbital_coeffs`, `export_gradient` (needs Gradient), `export_external_charge_gradient`, `export_mulliken_charges`, `export_chelpg_charges`, `export_bond_orders`, `export_h_caps`, `export_density_descriptors`, `export_esp_descriptors`, `export_expanded_esp_descriptors` (**⚠ upstream OOM — do not enable**), `export_basis_labels`, `export_hessian` (needs Hessian), `export_mass_weighted_hessian`, `export_hessian_frequencies`.
Other: `flatten_symmetric` (true), `light_json` (false), `concatenate_hdf5_files` (false; may be expensive), `training_db` (false), `descriptor_grid` (object).

The MCP's `exess_esp_charges` is the focused wrapper for `export_chelpg_charges` plus `export_mulliken_charges`; it disables fragmentation and sets `convert_hdf5_to_json=True` so callers receive complete atom arrays instead of HDF5 bytes.

Descriptor grids (`export_density_descriptors`/`export_esp_descriptors` require one; **disable fragmentation** so values aren't split per n-mer):
- `exess.RegularDescriptorGrid(min=[x,y,z], max=[x,y,z], spacing=[x,y,z])` (Å).
- `exess.CustomDescriptorGrid([x1,y1,z1, x2,y2,z2, ...])` (keep < hundreds of points).
- `exess.StandardDescriptorGrid(name)` — atom-centered radial: `FINE|ULTRAFINE|SUPERFINE|TREUTLER_GM3|TREUTLER_GM5` (outputs also reference SG1/SG2 — very fine, many points, high cost).
- `exess.DescriptorGrid(points_per_shell=, order="One"|"Two", scale=)`.

### regions — QM/MM partitioning
`qm_fragments` array[int], `mm_fragments` array[int]. Rules: one list → other inferred; both → must be disjoint and cover all; omitted → mm empty, qm=all (pure QM). Non-QM region requires `residues`; non-QM only for QMMM/Optimization (Energy etc. require pure QM); non-QM not supported for batched inputs.

### optimization — `exess.OptimizationKeywords(...)`
- `max_iters` (**required**, passed separately in rush-py).
- `convergence_criteria`: `metric` (Baker | GradientOnly), `gradient_threshold` (3e-4 Eh/a0), `delta_energy_threshold` (1e-6 Eh), `step_component_threshold` (3e-4 a0).
- `coordinate_system` (DelocalisedInternal; also Cartesian, NaturalInternal; ML opt requires Cartesian).
- `constraints` array[array[int]] ([]); `hessian_guess` (Identity/ScaledIdentity auto; Schlegel, Lindh).
- `algorithm` (EigenvectorFollowing; also TrustRegionAugmentedHessian, LBFGS). `lbfgs_keywords` required when LBFGS (`exess.LBFGSKeywords()`; linesearch BacktrackingStrongWolfe, n_corrections 6, epsilon 1e-5, max_linesearch 40, gtol 0.9).
- `trust_region`: initial_radius 0.4, max_radius 1e5, min_radius 1e-5, increase_factor 1.2, decrease_factor 0.7, etc.
- `optimizer_reset_interval`, `frozen_distance/angle_slippage_tolerance`, `debug_xyz`, `output_trc`, `fixed_atoms/free_atoms/fixed_fragments/free_fragments`, `fix_heavy`.
- `standard_orientation="None"` keeps the input frame so initial/optimized structures overlay (also `FullSystem` default, `PerFragment`).
Geometry opt supported for RHF, RI-HF, RI-MP2. Tight convergence: max gradient < 1e-4 Å.

### qmmm
- `n_timesteps` (**required**), `dt_ps` (**required**; rush-py default 0.002), `temperature_kelvin` (**required**; rush-py default 290.0).
- `pressure_atm` (unset → NVT; set → NPT).
- `biases` array (each exactly one of `harmonic_cv {k,offset,cv}`, `moving_harmonic {cv,k,rate_per_ps,...}`, `avoid_bonds {index,indices,fragments,exceptions,steepness 10,height 10000}`; CV objects: `bond {index1,index2}`, `angle`, `dihedral`, `linear_combination {scaled_cvs}`).
- `pbc_ang` [a,b,c]; `minimisation` (classical-only); `trajectory` object (`format` JSON|XYZ, `interval` 1, `start`, `end`, `include_waters` false, `forces`); `energy_csv`; `cv_values_csv`; `restraints` (`k` 2000.0, fixed/free atoms/fragments, `fix_heavy`); `ffs` (extra force-field files).
rush-py: `exess.Trajectory(interval=10, include_waters=True)`, `exess.Restraints(k=1500.0, fix_heavy=True)`.

### Other groups (Python not supported)
- **gradient:** `method` (Analytical|Numerical), `finite_difference_step_size` (5e-3).
- **guess:** `external_initial_density_path`, `bsp`/`bsp_basis`, `hcore`, `smd`, `ssfd`...
- **integrals:** `scheduler` (Callback|RoundRobin), `n_streams` (4 CUDA / 1 HIP).
- **rtat:** runtime auto-tuner (`enabled`, `synchronous`, `json_file_dump_prefix`).
- **hessian:** `method` (Numerical|Analytical), `finite_difference_step_size`.
- **dynamics:** `n_timesteps` (req), `dt` (req, ps; 1 fs = 0.001), `reuse_orbitals`, `use_async_timesteps`.
- **boundary:** `x`/`y`/`z` each `{kind: Periodic|Rigid|Delete, range:{lower,upper}}`.
- **force_field:** `ff_filename` (req; fragmented AIMD/MBE classical water/MM; QMMM uses `qmmm.ffs`).
- **log / debug:** logging levels; `debug.dry_run` (validate fragment queue, no compute), `max_fragments`, `ignore_fragments` (force full-system), `skip_calcs`.

### rush-py keyword defaults
`exess.calculate/energy/interaction_energy`: `scf_keywords` unset; `frag_keywords=FragKeywords()` (level Dimer, dimer_cutoff 100.0); `export_keywords=ExportKeywords()` (no exports); method `RestrictedKSDFT`, basis `cc-pVDZ`, `aux_basis=None`. `exess.qmmm`: same + `trajectory=Trajectory()`, dt_ps 0.002, temperature_kelvin 290.0, pressure_atm None. `exess.optimization`: `OptimizationKeywords()` defaults, max_iters required. FragKeywords by level: Monomer/Dimer dimer_cutoff 100.0; Trimer adds trimer_cutoff 25.0; Tetramer adds trimer_cutoff 25.0, tetramer_cutoff 10.0.

---

## 10. Hardware, Cost & Runtime

### Targets — `rush.runs.RunSpec(...)`
Infrastructure: 3 cloud "Bullet" clusters (Bullet, Bullet2, Bullet3) + 2 supercomputers (Gadi, Setonix). Bring-your-own HPC via hello@qdx.co.

| Field | Type / Default | Notes |
|-------|----------------|-------|
| `target` | str/None; default = random Bullet | `Bullet|Bullet2|Bullet3|Gadi|Setonix` |
| `walltime` | int/None (**minutes**) | job **stopped** when reached |
| `cpus` | int/None; module-specific | |
| `gpus` | int/None; module-specific | mismatched resources (GPU module without GPU) → run FAILS |
| `nodes` | int/None; default 1 | multi-node for very large systems on supercomputers |
| `storage` | int/None; default 10 | scratch allocation |
| `storage_units` | str/None; default 'MB' | `KB|MB|GB` |

```python
from rush import RunSpec
spec = RunSpec(walltime=60)                  # cap at 60 min
result = exess.energy(trc, run_spec=spec, collect=True)
```

### Cost drivers (ranked)
1. **System size** (atoms / basis functions) — dominant.
2. **Method/level of theory** — matters more than any other single variable: NN-xTB ≪ DFT ≪ correlated WF (orders of magnitude).
3. **Basis set** — larger basis raises cost independently of system size.
4. **Convergence** — SCF / geometry-opt iterations vary; tighter thresholds = more iterations.
5. **Calculation type** — optimizations/dynamics are iterative (cost ∝ steps).
6. **Hardware target** — prefactor differs per GPU/cluster; scaling consistent.

Two single-point energies can differ in cost by **several orders of magnitude**. Best estimate = benchmark 3–5 representative inputs at production settings, record walltime (timestamps / `history.json`), plot cost vs size, extrapolate with a buffer. What to measure per function: `energy` → walltime vs atoms/basis; `optimization` → walltime/cycle × cycles; `interaction_energy` → walltime vs fragment + system size; `qmmm` → walltime/timestep × timesteps.

### Billing
**Service Units (SU):** ~1 CPU core-hour, GPU nodes carry a multiplier. **SU definitions differ between centres** (Gadi ≠ Setonix); walltime is the portable planning metric, SU cost is centre-specific. Jobs **cost credits/SUs** — cap walltime when benchmarking unfamiliar systems.

---

## 11. Running EXESS (CLI)

Quick start: `runexess input.json -g 1` (CLI) or `exess.energy("input.json").fetch()` (rush-py).

Env: `EXESS_PATH`, `EXESS_RECORDS_PATH=$EXESS_PATH/records`, `EXESS_VALIDATION_PATH=$EXESS_PATH/validation`; output: `EXESS_OUTPUT_PATH`, `EXESS_HDF5_OUTPUT_PATH`.

- Single node: `module load exess; runexess your_input.json -g NGPUS` (omit `-g` → all GPUs). `runexess --help`.
- Multi-node (fragmentation): one team per fragment via `system.teams_per_node` × `system.gpus_per_team`. Slurm: `srun --nnodes=10 --ntasks=60 --ntasks-per-node=6 --gpus-per-node=4 exess input.json` (NTASKS_PER_NODE = NGPUS_PER_NODE + 2). mpirun: `nprocs_per_node = 1 + (NGPUS_PER_TEAM+1)*NTEAMS_PER_NODE`.
- Input conversion: `parley.py` (XYZ↔EXESS JSON; defaults input xyz, output json, basis 6-31G, driver Energy, method RestrictedHF; does NOT validate basis). Julia `create_json_input.jl` for RHF.

---

## 12. Outputs & Exports

EXESS always produces JSON; optional HDF5 exports when requested. `run.fetch()` → in-memory dataclasses; `run.save()` → `exess.ResultPaths(calc=..., exports=...)` downloaded to disk. rush-py auto-converts HDF5 exports to JSON — pass `convert_hdf5_to_json=False` to keep HDF5 (use for large/fine grids, files can be hundreds of MB). Explore HDF5 with `h5py`, `h5glance`, `h5ls`, `h5dump`.

### JSON output structure
Top: `schema_version`, `calculation_time` (s), `qmmbe` (not present for Dynamics), `trajectory` (Dynamics), `trajectory_qmmbes` (per-frame). Batched inputs → one Output per topology.

**QMMBE** fields: `num_iters`, `method`, `distance_metric/method`, `nmers` (nmers[0]=monomers, [1]=dimers...), `reference_fragment`, `expanded_hf_energy` (**total HF or, if reference_fragment set, the interaction energy**), `classical_water_energy`, `expanded_mp2_ss_correction`/`os_correction`, `expanded_ccsd_correction`, `expanded_density`, `expanded_hf_gradients`/`expanded_mp2_gradients`. With `reference_fragment`, expanded energies are interaction energies (density/gradients omitted).

**Nmer** fields: `fragments`, `density/fock/overlap/h_core`, `coeffs_initial/final`, `molecular_orbital_energies`, `hf_gradients/mp2_gradients`, `hf_energy`, `mp2_ss/os_correction`, `ccsd_correction`, `delta_hf_energy` (e.g. dimer interaction), `s_squared_eigenvalue` (spin contamination), `mulliken_charges/chelpg_charges`, `fragment_distance` (dimers), `bond_orders`, `h_caps`, `num_iters`, `num_basis_fns`.

**Trajectory/Frame:** `frames` stored as a tree of divergent paths; Frame has `parent`, `step`, `simulation_time`, `time_delta`, `kinetic_energy`, `estimated_temperature`, `positions/velocities/forces`, `changeset {sub: remove indices, add: Topology}` (apply remove then merge).

### Common accessors
- Total/interaction energy: `result.calc.qmmbe.expanded_hf_energy` (Hartrees). 1 Eh = 627.509 kcal/mol = 2625.500 kJ/mol = 27.211 eV.
- Atom charges: `result.exports["chelpg_charges"]` (ESP fit) and `result.exports["mulliken_charges"]` (population analysis).
- Optimization: `result.trajectory` (list[Topology], one per step; `.geometry` flat floats), `result.steps` (`.total_energy` Eh, `.max_gradient_component` Å).
- QM/MM: `result.geometries` (list of flat-float arrays, one per frame).

### HDF5 layout
`topology_0 → dimers → 0:1 → {density, fock, overlap, ..., chelpg_charges, descriptor_grid, density_descriptors, esp_descriptors}`; `trimers`; `fragmentation → {mbe_expanded_density, mbe_expanded_gradient}`; `topology_1...`. Matrices square `{nbas,nbas}` or packed `{nbas(nbas+1)/2}`; gradients `{natoms,3}`; descriptor_grid `{ngrid,3}`. Multi-team without concat → many `_export_N.hdf5`; `concatenate_hdf5_files` merges (may be expensive). Post-process trajectories: `julia ovito_exporter.jl -s [HDF5]`.

---

## 13. Worked Recipes (rush-py)

**CHELPG charges** (whole molecule, ~30 s):
```python
from rush import exess, from_pdb
trc = from_pdb(Path("aspirin.pdb").read_text())
topology_path = Path("aspirin_topology.json"); topology_path.write_text(json.dumps(trc.topology.to_json()))
result = exess.energy(topology_path, frag_keywords=None,
                      export_keywords=exess.ExportKeywords(export_chelpg_charges=True)).fetch()
charges = result.exports["chelpg_charges"]   # default: RestrictedKSDFT / cc-pVDZ
```

Equivalent MCP sequence (collection returns both arrays, with CHELPG also exposed as `charges`):
```text
submit = exess_esp_charges(structure_path="aspirin_topology.json")
run_collect(run_id=submit.run_id, kind="charges")
```
The collected `result` arrays contain one value per atom in `aspirin_topology.json`, in the same order. Check `n_atoms` and the charge sums before assigning the primary `charges` array to an OpenMM ligand. Do not map by length alone: reuse the exact ligand topology or verify every ordered atom identity before transferring charges to an SDF/OpenFF molecule.

**Single-point energy:**
```python
result = exess.energy("water_topology.json", method="RestrictedHF", basis="cc-pVDZ").fetch()
e = result.calc.qmmbe.expanded_hf_energy
```

**Geometry optimization:**
```python
run = exess.optimization("ethene_twisted_t.json", 100, standard_orientation="None")
res = run.fetch(); res.steps[-1].total_energy, res.steps[-1].max_gradient_component
```

**QM interaction energy (protein–ligand):**
```python
trc = prepare.protein_ligand(Path("1hsg.pdb"), ligand_names=["MK1","HOH"]).fetch()[0]
lig = trc.residues.seqs.index("MK1")
pocket = trc.topology.get_fragments_near_fragment(lig, 5.0) + [lig]
json.dump(trc.topology.to_json(), open("1hsg_t.json","w"))
result = exess.interaction_energy("1hsg_t.json", lig,
            frag_keywords=exess.FragKeywords(level="Dimer", included_fragments=pocket)).fetch()
e_int = result.calc.qmmbe.expanded_hf_energy   # negative = favorable
```

**QM/MM dynamics:**
```python
result = exess.qmmm(topology_path="6a5j_t.json", residues_path="6a5j_r.json",
                    n_timesteps=500, qm_fragments=[6]).fetch()
frames = result.geometries
```
Rule: **every fragment must be QM or MM**. `mm_fragments=[]` → all QM.

---

## 14. Support & Limits

- rush-py issues: github.com/talo/rush-py/issues; EXESS feature requests: exess.qdx.co/requests?tab=feature.
- Limits: no plane waves/pseudopotentials; AIMD is NVE only (NVT/NPT only in QMMM); `UnrestrictedRIMP2` unsupported; unrestricted DFT unimplemented; analytical gradients only for RHF/RI-HF/RI-MP2; transition metals experimental; `export_expanded_esp_descriptors` triggers OOM.