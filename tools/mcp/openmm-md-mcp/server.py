"""openmm-md MCP server -- FREE, Windows-native GPU molecular dynamics (OpenMM + CUDA).

POSITIONING (read this before choosing a tool):
  This server is a FREE / open-source (MIT) molecular-dynamics stack that runs NATIVELY on
  Windows with CUDA. It is a deliberate, CLEARLY LESSER alternative to the Schrodinger
  Desmond tools (mcp__schrodinger__desmond_*), which remain the preferred engine when a
  license is available. It does NOT replace them. Prefer Desmond (more-validated force
  fields, FEP+, WaterMap, IFD-MD, polished analysis) when you can run it on Linux with a
  LEGITIMATE license, or on a legit-licensed Linux cloud GPU. Use THIS when you are on
  Windows / want a free stack / need a quick GPU MD run. See the `openmm-md` skill for the
  full decision guide. Nothing here installs, cracks, or facilitates a pirated Schrodinger
  suite.

The eight tools chain through a `job_dir` on disk (prepare -> solvate -> minimize ->
equilibrate -> production -> analyze -> mmgbsa). Heavy logic lives in omm_pipeline.py;
these are thin, validated wrappers returning terminal-state JSON envelopes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

import omm_pipeline as omm  # importing this applies the Windows CUDA DLL-path shim
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openmm-md")


# ------------------------------------------------------------------ envelope helpers
def _call(fn, **kw) -> dict[str, Any]:
    """Run a pipeline function and wrap the result / any exception in a terminal-state
    envelope (status = SUCCESS | FAILED)."""
    try:
        res = fn(**kw)
        if isinstance(res, dict) and res.get("status") == "FAILED":
            return res
        out = dict(res)
        out.setdefault("status", "SUCCESS")
        return out
    except Exception as e:
        return {
            "status": "FAILED",
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc()[-1600:],
        }


def _default_job_dir() -> str:
    d = Path(tempfile.gettempdir()) / "openmm-md" / f"run-{time.strftime('%Y%m%d-%H%M%S')}"
    return str(d)


# ============================================================================= tools
@mcp.tool()
def openmm_status() -> dict[str, Any]:
    """Environment / GPU check. Reports OpenMM version, EVERY available Platform, and
    whether the CUDA platform actually works (builds a tiny Context and reads the GPU
    DeviceName), plus versions of openff-toolkit / openmmforcefields / pdbfixer / mdtraj /
    rdkit and which ligand-charge backends (NAGL, Gasteiger) are available. Run this first."""
    return _call(omm.status_probe)


@mcp.tool()
def openmm_prepare(
    protein: str,
    job_dir: str | None = None,
    ligand_smiles: str | None = None,
    ligand_file: str | None = None,
    water_model: str = "tip3p",
    ligand_ff: str = "openff-2.2.0",
    ph: float = 7.0,
    keep_water: bool = False,
    keep_hetero: bool = False,
    charge_method: str = "auto",
) -> dict[str, Any]:
    """Clean a protein and (optionally) parametrize a ligand into a job_dir.

    `protein` is a path to a PDB file OR a 4-char RCSB PDB id (auto-downloaded via PDBFixer).
    PDBFixer adds missing residues/atoms/hydrogens (at `ph`) and strips heterogens/water
    (unless keep_*). Protein FF = AMBER ff14SB. A ligand may be supplied as `ligand_file`
    (SDF/MOL2 with a real 3D/docked pose -- PREFERRED for binding work) or `ligand_smiles`
    (an ARBITRARY conformer, not a bound pose -- a warning is returned). Ligand FF =
    OpenFF SMIRNOFF `ligand_ff` (default openff-2.2.0 "Sage"); use "gaff-2.11" for GAFF
    (GAFF needs AmberTools, which is unavailable on native Windows -> will fail here).
    Charges: `charge_method` auto tries NAGL (GNN ~AM1-BCC) then RDKit Gasteiger -- neither
    equals OpenEye/sqm AM1-BCC (documented lower fidelity). Writes protein_fixed.pdb,
    ligand.sdf, complex.pdb, spec.json and runs a vacuum parametrization feasibility check."""
    jd = job_dir or _default_job_dir()
    out = _call(
        omm.prepare, protein=protein, job_dir=jd, ligand_smiles=ligand_smiles,
        ligand_file=ligand_file, water_model=water_model, ligand_ff=ligand_ff, ph=ph,
        keep_water=keep_water, keep_hetero=keep_hetero, charge_method=charge_method,
    )
    if out.get("status") == "SUCCESS":
        out["summary"] = (
            f"SUCCESS: prepared {out['n_protein_atoms']} protein atoms"
            + (f" + ligand ({out['n_ligand_atoms']} atoms, charges={out.get('charge_method_used')})"
               if out.get("has_ligand") else "")
            + f" in {out['job_dir']}"
        )
    return out


@mcp.tool()
def openmm_solvate(
    job_dir: str,
    padding_nm: float = 1.0,
    ion_conc_M: float = 0.15,
    box_shape: str = "cube",
    neutralize: bool = True,
    nonbonded_cutoff_nm: float = 1.0,
    hydrogen_mass_amu: float | None = None,
    water_model: str | None = None,
) -> dict[str, Any]:
    """Add an explicit-solvent box + neutralizing ions and build the parametrized System.

    Wraps the prepared complex in a periodic water box (default TIP3P; `box_shape` cube|
    dodecahedron|octahedron) with `padding_nm` solute-wall distance, neutralizing ions and
    salt to `ion_conc_M` (mol/L), then builds an OpenMM System with PME (`nonbonded_cutoff_nm`)
    + HBond constraints + rigid water and serializes it. Set `hydrogen_mass_amu=4.0` for
    hydrogen-mass repartitioning (enables a 4 fs timestep). Writes solvated.pdb + system.xml."""
    return _call(
        omm.solvate, job_dir=job_dir, padding_nm=padding_nm, ion_conc_M=ion_conc_M,
        box_shape=box_shape, neutralize=neutralize, nonbonded_cutoff_nm=nonbonded_cutoff_nm,
        hydrogen_mass_amu=hydrogen_mass_amu, water_model=water_model,
    )


@mcp.tool()
def openmm_minimize(
    job_dir: str,
    max_iterations: int = 0,
    tolerance_kj_nm: float = 10.0,
    platform: str = "CUDA",
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Energy-minimize the solvated system (L-BFGS). `max_iterations=0` runs to `tolerance_kj_nm`
    (kJ/mol/nm). `platform` defaults to CUDA; allow_fallback degrades to OpenCL/CPU with the
    actual platform reported. Writes minimized.pdb + state_min.xml; returns initial/final energy."""
    return _call(
        omm.minimize, job_dir=job_dir, max_iterations=max_iterations,
        tolerance_kj_nm=tolerance_kj_nm, platform=platform, allow_fallback=allow_fallback,
    )


@mcp.tool()
def openmm_equilibrate(
    job_dir: str,
    temperature_K: float = 300.0,
    pressure_bar: float = 1.0,
    nvt_steps: int = 25000,
    npt_steps: int = 25000,
    timestep_fs: float = 2.0,
    restraint_k: float = 2.0,
    platform: str = "CUDA",
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Equilibrate: NVT (heat to `temperature_K`, optional harmonic restraints of strength
    `restraint_k` kcal/mol/A^2 on solute heavy atoms) then NPT (MonteCarloBarostat at
    `pressure_bar`) from the minimized state. Writes equilibrated.pdb + state_equil.xml.
    Defaults: 25k NVT + 25k NPT steps at 2 fs (= 100 ps). Set restraint_k=0 to disable."""
    return _call(
        omm.equilibrate, job_dir=job_dir, temperature_K=temperature_K, pressure_bar=pressure_bar,
        nvt_steps=nvt_steps, npt_steps=npt_steps, timestep_fs=timestep_fs,
        restraint_k=restraint_k, platform=platform, allow_fallback=allow_fallback,
    )


@mcp.tool()
def openmm_production(
    job_dir: str,
    ns: float = 10.0,
    timestep_fs: float = 2.0,
    temperature_K: float = 300.0,
    pressure_bar: float = 1.0,
    ensemble: str = "NPT",
    report_ps: float = 10.0,
    traj_ps: float = 10.0,
    checkpoint_ps: float = 100.0,
    platform: str = "CUDA",
    blocking: bool = False,
    poll: bool = False,
    allow_fallback: bool = False,
) -> dict[str, Any]:
    """Production MD on the CUDA platform. NON-BLOCKING by default: launches a DETACHED
    worker and returns a handle immediately (long runs must not block the MCP).

      * poll=True  -> just return the current prod_status.json for this job_dir (progress,
                      ns_done, speed_ns_per_day, status RUNNING|SUCCESS|FAILED). Use this to
                      check on a run.
      * blocking=True -> run inline and return only when finished (use for short/smoke runs).
      * otherwise  -> start the detached run; poll by re-calling with poll=True (or Read the
                      returned status_file).

    Writes prod.dcd (trajectory every `traj_ps`), prod.chk (checkpoint every `checkpoint_ps`),
    prod.log, state_prod.xml. With HMR (solvate hydrogen_mass_amu=4.0) you may set timestep_fs=4.0.
    `allow_fallback=False` means it FAILS loudly if CUDA is unavailable rather than silently
    using CPU (production on CPU is impractically slow)."""
    job = Path(job_dir)
    status_file = job / "prod_status.json"

    if poll:
        if status_file.exists():
            cur = json.loads(status_file.read_text(encoding="utf-8"))
            cur["status_file"] = str(status_file)
            return cur
        return {"status": "FAILED", "error": "no production run found for this job_dir"}

    if status_file.exists():
        cur = json.loads(status_file.read_text(encoding="utf-8"))
        if cur.get("status") == "RUNNING":
            cur["note"] = "A production run is already RUNNING for this job_dir; not launching another."
            cur["status_file"] = str(status_file)
            return cur

    kw = dict(
        job_dir=str(job), ns=ns, timestep_fs=timestep_fs, temperature_K=temperature_K,
        pressure_bar=pressure_bar, ensemble=ensemble, report_ps=report_ps, traj_ps=traj_ps,
        checkpoint_ps=checkpoint_ps, platform=platform, allow_fallback=allow_fallback,
    )

    if blocking:
        out = _call(omm.production_run, **kw)
        if out.get("status") not in ("FAILED",):
            out["summary"] = f"SUCCESS: {ns} ns done -> {job / 'prod.dcd'}"
        return out

    try:
        pid = _launch_worker(str(job), kw)
    except Exception as e:
        return {"status": "FAILED", "error": f"could not launch worker: {type(e).__name__}: {e}"}
    return {
        "status": "SUCCESS",
        "action": "launched",
        "job_id": job.name,
        "pid": pid,
        "status_file": str(status_file),
        "trajectory": str(job / "prod.dcd"),
        "summary": f"SUCCESS: detached {ns} ns MD launched (pid {pid}). Poll with openmm_production(poll=True).",
        "note": "Detached MD started. Poll by calling openmm_production(job_dir, poll=True) or "
                "reading status_file (JSON: status/progress/ns_done/speed_ns_per_day).",
    }


@mcp.tool()
def openmm_analyze(
    job_dir: str,
    trajectory: str = "prod.dcd",
    topology: str = "solvated.pdb",
    stride: int = 1,
    hbond_freq: float = 0.1,
    contact_cutoff_nm: float = 0.4,
) -> dict[str, Any]:
    """MDTraj analysis of a trajectory: protein C-alpha RMSD & RMSF, radius of gyration,
    Baker-Hubbard H-bond count and -- if a ligand is present -- protein-ligand contacts and
    ligand binding-site RMSD (a binding-stability signal). Full per-frame arrays are saved to
    analysis.npz; a numeric summary (Angstrom) is returned."""
    return _call(
        omm.analyze, job_dir=job_dir, trajectory=trajectory, topology=topology,
        stride=stride, hbond_freq=hbond_freq, contact_cutoff_nm=contact_cutoff_nm,
    )


@mcp.tool()
def openmm_mmgbsa(
    job_dir: str,
    trajectory: str = "prod.dcd",
    stride: int = 10,
    start_frame: int = 0,
    max_frames: int = 50,
) -> dict[str, Any]:
    """Free MM-GBSA-style binding free energy (dG) over the trajectory. HONEST APPROXIMATION:
    OpenMM-native OBC2/GBSA, single-trajectory, NO entropy, generic element-based GB radii.
    Requires a protein-ligand complex. Good for RANKING congeneric ligands, NOT absolute
    affinities. Materially lower fidelity than Schrodinger Prime MM-GBSA (mcp__schrodinger__
    prime_mmgbsa / thermal_mmgbsa) and AmberTools MMPBSA.py (Linux-only). See the returned
    fidelity_note. Returns mean +/- std dG in kJ/mol and kcal/mol."""
    return _call(
        omm.mmgbsa, job_dir=job_dir, trajectory=trajectory, stride=stride,
        start_frame=start_frame, max_frames=max_frames,
    )


# ------------------------------------------------------- detached production worker
def _launch_worker(job_dir: str, kw: dict[str, Any]) -> int:
    """Spawn a detached subprocess (this file, --worker) to run production MD without
    blocking the MCP server. Returns the child PID."""
    job = Path(job_dir)
    job.mkdir(parents=True, exist_ok=True)
    argfile = job / "prod_args.json"
    argfile.write_text(json.dumps(kw), encoding="utf-8")
    # Write a synchronous STARTING marker BEFORE spawning so an immediate poll never reads a
    # prior run's stale prod_status.json from a reused job_dir.
    dt = float(kw.get("timestep_fs", 2.0)) / 1000.0
    total = max(1, int(round(float(kw.get("ns", 0.0)) * 1000.0 / dt)))
    (job / "prod_status.json").write_text(
        json.dumps({"status": "STARTING", "step": 0, "total_steps": total,
                    "progress": 0.0, "ns_target": kw.get("ns")}), encoding="utf-8")
    logf = open(job / "prod_worker.log", "w", encoding="utf-8")  # noqa: SIM115 (child owns it)
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", str(argfile)]
    if sys.platform == "win32":
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
        p = subprocess.Popen(cmd, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                             creationflags=flags, cwd=str(job), close_fds=True)
    else:
        p = subprocess.Popen(cmd, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                             start_new_session=True, cwd=str(job), close_fds=True)
    return p.pid


def _worker_main(argfile: str) -> None:
    kw = json.loads(Path(argfile).read_text(encoding="utf-8"))
    omm.production_run(**kw)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        _worker_main(sys.argv[2])
    else:
        mcp.run()
