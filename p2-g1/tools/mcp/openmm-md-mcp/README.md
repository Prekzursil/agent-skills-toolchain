# openmm-md-mcp

**Free, open-source, Windows-native GPU molecular dynamics as an MCP server.** OpenMM (CUDA)
+ OpenFF + PDBFixer + MDTraj, driving MD on the local NVIDIA GPU (verified: RTX 4050).

> **Positioning (important):** this is a deliberately **lesser, free** alternative to
> Schrodinger **Desmond**. It does **NOT** replace the `mcp__schrodinger__*` tools (they
> stay intact and preferred when a license is available). Use `openmm-md` when you are on
> Windows / have no Schrodinger license / a free stack is good enough. When the science needs
> validated **FEP+ / WaterMap / IFD-MD / Prime MM-GBSA / OPLS4**, use Schrodinger, or run
> **Desmond legitimately** on Linux / a licensed cloud GPU. See `skill/openmm-md/SKILL.md`
> for the full decision guide. Nothing here installs or facilitates a pirated Schrodinger suite.

## Tools (8)

| Tool | Purpose |
|---|---|
| `openmm_status` | Env/GPU check: OpenMM version, available platforms, **is CUDA live on the GPU**, dep versions, charge backends. Run first. |
| `openmm_prepare` | Protein PDB/RCSB-id (+ optional ligand SMILES/SDF) -> cleaned & parametrized (PDBFixer, ff14SB, OpenFF Sage/GAFF). |
| `openmm_solvate` | Explicit TIP3P water box + neutralizing ions (PME). Optional HMR. |
| `openmm_minimize` | Energy minimization (CUDA). |
| `openmm_equilibrate` | NVT then NPT (barostat), optional heavy-atom restraints. |
| `openmm_production` | Production MD on CUDA. **Non-blocking** (detached worker + handle); poll via `poll=True`. DCD + checkpoints. |
| `openmm_analyze` | MDTraj: RMSD, RMSF, Rg, H-bonds, protein-ligand contacts, ligand binding-site RMSD. |
| `openmm_mmgbsa` | Approximate MM-GBSA dG (OBC2/GBSA, single-trajectory, no entropy). Ranking only; honest fidelity note. |

## Requirements

- **Windows** with an **NVIDIA GPU + driver** (CUDA UMD present; verified on RTX 4050, 6 GB).
- The **conda env** at `D:\micromamba\envs\openmm-md` (built via Micromamba / conda-forge).

### Why conda-forge (not pip)

The pip `openmm` wheel does **not** include the CUDA platform on Windows -- only conda-forge
does. This env was built with Micromamba from conda-forge. AmberTools has **no native-Windows
build**, so the env uses `openff-toolkit-base` (+ pip `openmmforcefields`) and gets ligand
charges from NAGL (GNN) or RDKit Gasteiger instead of sqm AM1-BCC. See `environment.yml`.

### The Windows CUDA DLL shim

When an MCP launches the env's `python.exe` **without activation**, the CUDA runtime DLLs
(nvrtc) are not on the search path and OpenMM's CUDA plugin silently fails (CPU/OpenCL only).
`omm_pipeline.py` fixes this itself (prepends the env dirs to `PATH` + `os.add_dll_directory`),
so a plain `python.exe server.py` command works -- **no activation wrapper needed**.

## Recreate the environment

```bash
# Micromamba was installed at D:\micromamba (micromamba.exe under Library\bin).
micromamba create -y -p D:/micromamba/envs/openmm-md -f environment.yml
micromamba install -y -p D:/micromamba/envs/openmm-md -c conda-forge openff-interchange
D:/micromamba/envs/openmm-md/python.exe -m openmm.testInstallation   # expect a CUDA platform
```

`openff-interchange` is required for OpenFF SMIRNOFF ligand parametrization (it also pulls
NAGL models, enabling GNN AM1-BCC-surrogate charges).

## Register in `~/.mcp.json`

Add under `mcpServers` (no secrets / env refs needed):

```json
"openmm-md": {
  "type": "stdio",
  "command": "D:\\micromamba\\envs\\openmm-md\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\repos\\openmm-md-mcp\\server.py"],
  "env": {}
}
```

## Install the skill

Copy (or symlink) `skill/openmm-md/` into a skills directory the tooling scans, e.g.:

```bash
cp -r skill/openmm-md ~/.claude/skills/openmm-md
```

## Usage (typical protein-ligand run)

```
openmm_status()                                   # confirm CUDA on the GPU
r = openmm_prepare(protein="1UBQ", ligand_file="docked_pose.sdf")   # -> job_dir
openmm_solvate(job_dir=r.job_dir, padding_nm=1.0)
openmm_minimize(job_dir=r.job_dir)
openmm_equilibrate(job_dir=r.job_dir)
openmm_production(job_dir=r.job_dir, ns=20)        # non-blocking; returns a handle
openmm_production(job_dir=r.job_dir, poll=True)    # poll progress
openmm_analyze(job_dir=r.job_dir)                  # RMSD/RMSF/Rg/contacts
openmm_mmgbsa(job_dir=r.job_dir)                   # approximate ranking dG
```

## Verification (real GPU smoke test -- `smoke_test.py`)

Verified end-to-end on the **NVIDIA GeForce RTX 4050 Laptop GPU** (OpenMM 8.5.2, CUDA):

- `openmm_status` -> CUDA=YES, DeviceName = RTX 4050 Laptop GPU (4 platforms).
- Full protein pipeline (chignolin 1UAO): prepare (138 atoms) -> solvate (1797 atoms / 551
  waters) -> **minimize on CUDA** (443.6 -> -30936.7 kJ/mol) -> **equilibrate on CUDA** (NVT+NPT,
  box 2.73 -> 2.65 nm) -> **production on CUDA** (0.02 ns, **~368 ns/day**, 5.4 s) ->
  analyze (10 frames, CA-RMSD 0.52 Angstrom, Rg 13.5 Angstrom, 10 H-bonds).
- Ligand path (VERIFIED): OpenFF SMIRNOFF (Sage 2.2.0) + **NAGL GNN AM1-BCC-surrogate charges**
  parametrized a 15-atom ligand -> solvate -> minimize -> equilibrate -> production (CUDA) ->
  `openmm_mmgbsa` dG = -7.65 kcal/mol over 10 frames. (The smoke uses an ARBITRARY SMILES pose,
  so that dG validates the code path, not a real affinity -- use a docked pose for science.)

Re-run: `D:/micromamba/envs/openmm-md/python.exe smoke_test.py`

## Known limitations (be honest with users)

- **Windows / no AmberTools** -> no GAFF, no antechamber, no sqm AM1-BCC, no MMPBSA.py.
  Ligand charges are NAGL (GNN ~AM1-BCC) or Gasteiger -- documented lower fidelity.
- **`openmm_mmgbsa` is an approximation** (OBC2/GBSA, single-trajectory, no entropy, generic
  radii). Good for **ranking** congeneric series, not absolute affinities; materially weaker
  than Prime MM-GBSA / AmberTools MMPBSA.py.
- No FEP+, WaterMap, IFD-MD, or OPLS4 -- use Schrodinger for those.
- 6 GB GPU -> keep systems modest (reduce `padding_nm` for large proteins to avoid OOM).

## License

MIT (this wrapper). Dependencies are free/open-source (OpenMM MIT/LGPL, OpenFF MIT/CC-BY,
MDTraj LGPL, RDKit BSD). See `LICENSE`.
