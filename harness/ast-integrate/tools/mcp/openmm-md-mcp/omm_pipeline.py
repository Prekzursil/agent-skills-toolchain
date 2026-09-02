"""OpenMM molecular-dynamics pipeline helpers (pure functions, no MCP layer).

This module holds all the heavy OpenMM / OpenFF / PDBFixer / MDTraj logic so it can be
unit-tested and driven directly (see ``smoke_test.py``) independently of the FastMCP
wrappers in ``server.py``.

Design:
  * Every stage reads/writes plain files inside a ``job_dir`` using stable artifact
    names, so the eight MCP tools chain purely through the filesystem (like Desmond's
    ``.cms`` hand-off) and survive across separate MCP process calls.
  * Ligand parameters use the OpenFF SMIRNOFF ("Sage") force field via
    ``openmmforcefields`` -- this needs NO AmberTools (which has no Windows/conda-forge
    build). Partial charges come from NAGL (a GNN ~AM1-BCC surrogate) when installed,
    else RDKit Gasteiger. Both are clearly labelled; neither matches OpenEye/sqm AM1-BCC.
  * ``mmgbsa`` is an HONEST OpenMM-native OBC2/GBSA single-trajectory approximation
    (no entropy, element-based radii) -- NOT AmberTools MMPBSA.py (Linux-only) nor
    Schrodinger Prime MM-GBSA. Fidelity caveats are documented on the tool.

Artifact names inside a job_dir:
  protein_fixed.pdb, ligand.sdf, complex.pdb, spec.json,
  solvated.pdb, system.xml,
  minimized.pdb, state_min.xml,
  equilibrated.pdb, state_equil.xml,
  prod.dcd, prod.chk, prod.log, state_prod.xml, prod_status.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ---- Windows CUDA DLL shim -------------------------------------------------------------
# When this conda env's python.exe is launched WITHOUT activation (exactly what an MCP
# stdio subprocess does), the env's CUDA runtime DLLs (nvrtc, etc.) are not on the DLL
# search path, so OpenMM's CUDA plugin silently fails to load and only CPU/OpenCL show up.
# OpenMM's plugin resolves nvrtc via PATH, so `os.add_dll_directory` ALONE is NOT enough --
# we must also prepend the env dirs to PATH. This replicates conda activation. (Verified:
# with the shim the unactivated env python reports Reference/CPU/CUDA/OpenCL.)
_DLL_HANDLES: list = []


def _ensure_dll_path() -> None:
    if os.name != "nt":
        return
    prefix = sys.prefix
    subdirs = [
        prefix,
        os.path.join(prefix, "Library", "mingw-w64", "bin"),
        os.path.join(prefix, "Library", "usr", "bin"),
        os.path.join(prefix, "Library", "bin"),
        os.path.join(prefix, "Scripts"),
        os.path.join(prefix, "bin"),
    ]
    present = [d for d in subdirs if os.path.isdir(d)]
    os.environ["PATH"] = (
        os.pathsep.join(present) + os.pathsep + os.environ.get("PATH", "")
    )
    for d in present:
        try:
            _DLL_HANDLES.append(
                os.add_dll_directory(d)
            )  # keep handles alive at module scope
        except OSError:
            pass


_ensure_dll_path()

# ---------------------------------------------------------------- force-field constants
PROTEIN_FF = "amber14/protein.ff14SB.xml"
WATER_FF = {
    "tip3p": "amber14/tip3p.xml",
    "tip3pfb": "amber14/tip3pfb.xml",
    "spce": "amber14/spce.xml",
    "tip4pew": "amber14/tip4pew.xml",
    "tip5p": "amber14/tip5p.xml",
    "opc": "amber14/opc.xml",
    "opc3": "amber14/opc3.xml",
}
DEFAULT_LIGAND_FF = "openff-2.2.0"  # OpenFF "Sage" 2.2.0
_WATER_RESNAMES = {"HOH", "WAT", "H2O", "TIP", "T3P", "SPC"}

# Approximate GBSA-OBC (OBC2 / "mbondi2"-like) radii (nm) and scale factors, keyed by
# element. Element-based assignment lets us parametrize arbitrary ligands for which no
# GB template exists. Documented as an approximation on the mmgbsa tool.
_GB_RADII = {
    "H": 0.12,
    "C": 0.17,
    "N": 0.155,
    "O": 0.15,
    "F": 0.15,
    "P": 0.185,
    "S": 0.18,
    "Cl": 0.17,
    "Br": 0.185,
    "I": 0.198,
    "Na": 0.133,
    "Mg": 0.100,
    "K": 0.176,
    "Ca": 0.137,
    "Zn": 0.110,
}
_GB_SCALE = {
    "H": 0.85,
    "C": 0.72,
    "N": 0.79,
    "O": 0.85,
    "F": 0.88,
    "P": 0.86,
    "S": 0.96,
    "Cl": 0.80,
    "Br": 0.80,
    "I": 0.80,
}


# ============================================================ small internal utilities
def _safe(p: str, must_exist: bool = False) -> str:
    """Validate a client-supplied path before it is used (reject flag-like / control
    chars) and return an absolute normalized path."""
    if not isinstance(p, str) or not p.strip() or p.strip().startswith("-"):
        raise ValueError(f"invalid/unsafe path: {p!r}")
    if any(c in p for c in "\r\n\x00"):
        raise ValueError(f"unsafe path (control char): {p!r}")
    ap = os.path.abspath(os.path.expanduser(p))
    if must_exist and not os.path.exists(ap):
        raise FileNotFoundError(ap)
    return ap


def _job(job_dir: str, create: bool = True) -> Path:
    d = Path(_safe(job_dir))
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _read_spec(job: Path) -> dict[str, Any]:
    return json.loads((job / "spec.json").read_text(encoding="utf-8"))


def _write_spec(job: Path, spec: dict[str, Any]) -> None:
    (job / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")


def _looks_like_pdb_id(s: str) -> bool:
    return (
        isinstance(s, str)
        and len(s) == 4
        and s[0].isdigit()
        and s.isalnum()
        and os.path.sep not in s
        and not os.path.exists(s)
    )


# ============================================================================ status
def status_probe() -> dict[str, Any]:
    """Report OpenMM version, every available Platform, and whether CUDA truly works
    (by building a tiny 2-particle Context on it and reading the GPU DeviceName)."""
    import platform as _plat
    import openmm as mm
    from openmm import unit
    import numpy as np

    info: dict[str, Any] = {
        "openmm_version": mm.version.version,
        "python": _plat.python_version(),
        "os": f"{_plat.system()} {_plat.release()}",
    }
    plats: list[dict[str, Any]] = []
    cuda_ok = False
    cuda_detail: dict[str, Any] = {}
    for i in range(mm.Platform.getNumPlatforms()):
        name = mm.Platform.getPlatform(i).getName()
        entry: dict[str, Any] = {"name": name}
        try:
            plat = mm.Platform.getPlatformByName(name)
            sysm = mm.System()
            sysm.addParticle(1.0)
            sysm.addParticle(1.0)
            integ = mm.VerletIntegrator(0.001 * unit.picosecond)
            props = {"Precision": "mixed"} if name in ("CUDA", "OpenCL") else {}
            ctx = mm.Context(sysm, integ, plat, props)
            ctx.setPositions(
                unit.Quantity(np.array([[0, 0, 0], [0, 0, 0.1]]), unit.nanometer)
            )
            ctx.getState(getEnergy=True)
            entry["works"] = True
            if name in ("CUDA", "OpenCL"):
                for pn in ("DeviceName", "DeviceIndex", "Precision"):
                    try:
                        entry[pn] = plat.getPropertyValue(ctx, pn)
                    except Exception:
                        pass
            if name == "CUDA":
                cuda_ok = True
                cuda_detail = {
                    k: entry.get(k) for k in ("DeviceName", "DeviceIndex", "Precision")
                }
            del ctx, integ
        except Exception as e:  # platform present but unusable on this box
            entry["works"] = False
            entry["reason"] = str(e)[:300]
        plats.append(entry)
    info["platforms"] = plats
    info["cuda_available"] = cuda_ok
    info["cuda"] = cuda_detail

    # dependency versions (from installed distribution metadata -- accurate for packages
    # like openff-toolkit / pdbfixer that don't expose a top-level __version__)
    from importlib.metadata import version as _distver

    def _ver(dist: str) -> str | None:
        try:
            return _distver(dist)
        except Exception:
            return None

    info["versions"] = {
        "openff-toolkit": _ver("openff-toolkit"),
        "openmmforcefields": _ver("openmmforcefields"),
        "pdbfixer": _ver("pdbfixer"),
        "mdtraj": _ver("mdtraj"),
        "rdkit": _ver("rdkit"),
        "numpy": _ver("numpy"),
    }
    # ligand charge backends
    nagl = False
    try:
        import openff.nagl  # noqa: F401
        from openff.nagl_models import list_available_nagl_models

        nagl = len(list_available_nagl_models()) > 0
    except Exception:
        nagl = False
    info["ligand_charge_backends"] = {
        "gasteiger": info["versions"]["rdkit"] is not None,
        "nagl": nagl,
    }
    info["ligand_ff_default"] = DEFAULT_LIGAND_FF
    info["summary"] = (
        f"OpenMM {info['openmm_version']} | CUDA={'YES' if cuda_ok else 'NO'}"
        + (f" ({cuda_detail.get('DeviceName')})" if cuda_ok else "")
    )
    return info


# =================================================================== charge assignment
def _find_nagl_model() -> str:
    from openff.nagl_models import list_available_nagl_models

    models = [str(m) for m in list_available_nagl_models()]
    if not models:
        raise RuntimeError("no NAGL models installed")
    for m in models:
        if "am1bcc" in m.lower() and "rc" not in m.lower():
            return m
    for m in models:
        if "am1bcc" in m.lower():
            return m
    return models[0]


def _assign_charges(offmol, method: str = "auto") -> str:
    """Assign partial charges to an OpenFF Molecule. 'auto' tries NAGL (GNN ~AM1-BCC)
    then falls back to RDKit Gasteiger. Returns the method actually used."""
    method = (method or "auto").lower()
    if method in ("auto", "nagl"):
        try:
            from openff.toolkit.utils.nagl_wrapper import NAGLToolkitWrapper

            model = _find_nagl_model()
            offmol.assign_partial_charges(model, toolkit_registry=NAGLToolkitWrapper())
            return f"nagl ({os.path.basename(model)})"
        except Exception:
            if method == "nagl":
                raise
    from openff.toolkit.utils.toolkits import RDKitToolkitWrapper

    offmol.assign_partial_charges("gasteiger", toolkit_registry=RDKitToolkitWrapper())
    return "gasteiger"


def _load_ligand(sdf: str, charge_method: str = "auto"):
    """Load a ligand SDF into an OpenFF Molecule (with a conformer) and (re)assign
    charges -- SDF does not round-trip partial charges, so we recompute deterministically."""
    from openff.toolkit import Molecule

    mol = Molecule.from_file(sdf, allow_undefined_stereo=True)
    if isinstance(mol, list):
        mol = mol[0]
    if not mol.conformers:
        mol.generate_conformers(n_conformers=1)
    used = _assign_charges(mol, charge_method)
    return mol, used


def _build_forcefield(spec: dict[str, Any], offmols: list):
    """Assemble an OpenMM ForceField: ff14SB + water model + (optional) a SMIRNOFF/GAFF
    template generator registered for the ligand(s)."""
    from openmm.app import ForceField

    ff = ForceField(spec["protein_ff"], spec["water_ff"])
    if offmols:
        lig_ff = spec.get("ligand_ff", DEFAULT_LIGAND_FF)
        if lig_ff.lower().startswith("gaff"):
            from openmmforcefields.generators import GAFFTemplateGenerator

            gen = GAFFTemplateGenerator(molecules=offmols, forcefield=lig_ff)
        else:
            from openmmforcefields.generators import SMIRNOFFTemplateGenerator

            gen = SMIRNOFFTemplateGenerator(molecules=offmols, forcefield=lig_ff)
        ff.registerTemplateGenerator(gen.generator)
    return ff


# ==================================================================== stage 1: prepare
def prepare(
    protein: str,
    job_dir: str,
    ligand_smiles: str | None = None,
    ligand_file: str | None = None,
    water_model: str = "tip3p",
    ligand_ff: str = DEFAULT_LIGAND_FF,
    ph: float = 7.0,
    keep_water: bool = False,
    keep_hetero: bool = False,
    charge_method: str = "auto",
) -> dict[str, Any]:
    """PDBFixer cleanup of a protein (+ optional ligand) and a feasibility check that the
    chosen force fields actually parametrize the complex. Writes protein_fixed.pdb,
    ligand.sdf (if any), complex.pdb and spec.json."""
    from openmm import unit
    from openmm.app import PDBFile, Modeller
    from pdbfixer import PDBFixer

    job = _job(job_dir)
    if water_model not in WATER_FF:
        raise ValueError(f"water_model must be one of {sorted(WATER_FF)}")

    # --- protein cleanup ---
    if _looks_like_pdb_id(protein):
        fixer = PDBFixer(pdbid=protein)
        src = f"RCSB:{protein}"
    else:
        src = _safe(protein, must_exist=True)
        fixer = PDBFixer(filename=src)
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    if not keep_hetero:
        fixer.removeHeterogens(keepWater=keep_water)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(pH=float(ph))
    prot_pdb = job / "protein_fixed.pdb"
    with open(prot_pdb, "w") as fh:
        PDBFile.writeFile(fixer.topology, fixer.positions, fh)
    n_protein_atoms = fixer.topology.getNumAtoms()

    spec: dict[str, Any] = {
        "protein_source": src,
        "protein_pdb": str(prot_pdb),
        "protein_ff": PROTEIN_FF,
        "water_model": water_model,
        "water_ff": WATER_FF[water_model],
        "ligand_ff": ligand_ff,
        "charge_method": charge_method,
        "has_ligand": False,
        "n_protein_atoms": n_protein_atoms,
        "n_ligand_atoms": 0,
        "ph": float(ph),
    }

    offmols: list = []
    charge_used = None
    pose_warning = None
    if ligand_smiles or ligand_file:
        from openff.toolkit import Molecule

        if ligand_file:
            lig_src = _safe(ligand_file, must_exist=True)
            offmol = Molecule.from_file(lig_src, allow_undefined_stereo=True)
            if isinstance(offmol, list):
                offmol = offmol[0]
            if not offmol.conformers:
                offmol.generate_conformers(n_conformers=1)
        else:
            offmol = Molecule.from_smiles(ligand_smiles, allow_undefined_stereo=True)
            offmol.generate_conformers(n_conformers=1)
            pose_warning = (
                "Ligand built from SMILES has an ARBITRARY conformer, NOT a bound pose. "
                "For binding studies pass a docked 3D ligand via ligand_file (SDF/MOL2)."
            )
        charge_used = _assign_charges(offmol, charge_method)
        lig_sdf = job / "ligand.sdf"
        offmol.to_file(str(lig_sdf), file_format="SDF")
        offmols = [offmol]
        spec.update(
            has_ligand=True,
            ligand_sdf=str(lig_sdf),
            n_ligand_atoms=offmol.n_atoms,
            ligand_smiles=offmol.to_smiles(),
            charge_method_used=charge_used,
        )

    # --- write a reference complex.pdb (protein + ligand, no solvent) ---
    modeller = Modeller(fixer.topology, fixer.positions)
    if offmols:
        modeller.add(
            offmols[0].to_topology().to_openmm(), offmols[0].conformers[0].to_openmm()
        )
    with open(job / "complex.pdb", "w") as fh:
        PDBFile.writeFile(modeller.topology, modeller.positions, fh)

    # --- feasibility: parametrize the complex in vacuum to prove the FFs apply ---
    feas: dict[str, Any] = {}
    try:
        import openmm as mm
        from openmm.app import NoCutoff, HBonds

        ff = _build_forcefield(spec, offmols)
        vac = ff.createSystem(
            modeller.topology, nonbondedMethod=NoCutoff, constraints=HBonds
        )
        integ = mm.VerletIntegrator(0.001 * unit.picosecond)
        ctx = mm.Context(vac, integ, mm.Platform.getPlatformByName("Reference"))
        ctx.setPositions(modeller.positions)
        e = (
            ctx.getState(getEnergy=True)
            .getPotentialEnergy()
            .value_in_unit(unit.kilojoule_per_mole)
        )
        feas = {"parametrized": True, "vacuum_energy_kJ_per_mol": round(e, 2)}
        del ctx, integ
    except Exception as e:
        feas = {"parametrized": False, "error": f"{type(e).__name__}: {str(e)[:400]}"}

    _write_spec(job, spec)
    out = {
        "job_dir": str(job),
        "protein_fixed_pdb": str(prot_pdb),
        "complex_pdb": str(job / "complex.pdb"),
        "n_protein_atoms": n_protein_atoms,
        "has_ligand": spec["has_ligand"],
        "n_ligand_atoms": spec["n_ligand_atoms"],
        "charge_method_used": charge_used,
        "feasibility": feas,
    }
    if pose_warning:
        out["pose_warning"] = pose_warning
    return out


# ==================================================================== stage 2: solvate
def solvate(
    job_dir: str,
    padding_nm: float = 1.0,
    ion_conc_M: float = 0.15,
    box_shape: str = "cube",
    neutralize: bool = True,
    nonbonded_cutoff_nm: float = 1.0,
    hydrogen_mass_amu: float | None = None,
    water_model: str | None = None,
) -> dict[str, Any]:
    """Add an explicit-solvent box (TIP3P by default) + neutralizing ions around the
    prepared complex, build the parametrized OpenMM System (PME), and serialize it.
    Writes solvated.pdb and system.xml. ``hydrogen_mass_amu=4.0`` enables HMR (4 fs)."""
    import openmm as mm
    from openmm import unit
    from openmm.app import PDBFile, Modeller, PME, HBonds

    job = _job(job_dir, create=False)
    spec = _read_spec(job)
    model = water_model or spec["water_model"]
    if model not in WATER_FF:
        raise ValueError(f"water_model must be one of {sorted(WATER_FF)}")
    if box_shape not in ("cube", "dodecahedron", "octahedron"):
        raise ValueError(
            "box_shape must be one of ('cube', 'dodecahedron', 'octahedron')"
        )
    spec["water_model"], spec["water_ff"] = model, WATER_FF[model]

    prot = PDBFile(str(job / "protein_fixed.pdb"))
    modeller = Modeller(prot.topology, prot.positions)
    offmols: list = []
    if spec["has_ligand"]:
        offmol, _ = _load_ligand(spec["ligand_sdf"], spec.get("charge_method", "auto"))
        modeller.add(offmol.to_topology().to_openmm(), offmol.conformers[0].to_openmm())
        offmols = [offmol]

    ff = _build_forcefield(spec, offmols)
    n_solute = modeller.topology.getNumAtoms()
    modeller.addSolvent(
        ff,
        model=model,
        padding=float(padding_nm) * unit.nanometer,
        ionicStrength=float(ion_conc_M) * unit.molar,
        neutralize=bool(neutralize),
        boxShape=box_shape,
    )
    kwargs: dict[str, Any] = dict(
        nonbondedMethod=PME,
        nonbondedCutoff=float(nonbonded_cutoff_nm) * unit.nanometer,
        constraints=HBonds,
        rigidWater=True,
    )
    if hydrogen_mass_amu:
        kwargs["hydrogenMass"] = float(hydrogen_mass_amu) * unit.amu
    system = ff.createSystem(modeller.topology, **kwargs)

    with open(job / "solvated.pdb", "w") as fh:
        PDBFile.writeFile(modeller.topology, modeller.positions, fh)
    (job / "system.xml").write_text(
        mm.XmlSerializer.serialize(system), encoding="utf-8"
    )

    n_total = modeller.topology.getNumAtoms()
    n_waters = sum(1 for r in modeller.topology.residues() if r.name in _WATER_RESNAMES)
    box = modeller.topology.getPeriodicBoxVectors().value_in_unit(unit.nanometer)
    spec.update(
        n_solute_atoms=n_solute,
        n_total_atoms=n_total,
        n_waters=n_waters,
        hydrogen_mass_amu=hydrogen_mass_amu,
        recommended_timestep_fs=(
            4.0 if hydrogen_mass_amu and hydrogen_mass_amu >= 3.5 else 2.0
        ),
    )
    _write_spec(job, spec)
    return {
        "job_dir": str(job),
        "solvated_pdb": str(job / "solvated.pdb"),
        "system_xml": str(job / "system.xml"),
        "n_total_atoms": n_total,
        "n_solute_atoms": n_solute,
        "n_waters": n_waters,
        "box_nm": [round(box[i][i], 3) for i in range(3)],
        "recommended_timestep_fs": spec["recommended_timestep_fs"],
    }


# ============================================================= platform / restraint utils
def get_platform(name: str, allow_fallback: bool = True):
    """Return (Platform, properties, actual_name). Falls back CUDA>OpenCL>CPU>Reference
    when the requested platform is unavailable and allow_fallback is set."""
    import openmm as mm

    want = name or "CUDA"
    try:
        plat = mm.Platform.getPlatformByName(want)
        props = {"Precision": "mixed"} if want in ("CUDA", "OpenCL") else {}
        return plat, props, want
    except Exception:
        if not allow_fallback:
            raise
    for cand in ("CUDA", "OpenCL", "CPU", "Reference"):
        try:
            plat = mm.Platform.getPlatformByName(cand)
            props = {"Precision": "mixed"} if cand in ("CUDA", "OpenCL") else {}
            return plat, props, cand
        except Exception:
            continue
    raise RuntimeError("no OpenMM platform available")


def _add_position_restraint(
    system, topology, positions, k_kcal: float, n_solute: int
) -> int:
    """Harmonic restraint on solute heavy atoms (first n_solute atoms, excluding H).
    k in kcal/mol/A^2 -> kJ/mol/nm^2 via *418.4."""
    import openmm as mm
    from openmm import unit

    force = mm.CustomExternalForce("0.5*k*periodicdistance(x,y,z,x0,y0,z0)^2")
    force.addGlobalParameter("k", float(k_kcal) * 418.4)
    for p in ("x0", "y0", "z0"):
        force.addPerParticleParameter(p)
    pos = positions.value_in_unit(unit.nanometer)
    atoms = list(topology.atoms())
    n = 0
    for atom in atoms:
        i = atom.index
        if i >= n_solute:
            break
        if atom.element is not None and atom.element.symbol == "H":
            continue
        x, y, z = pos[i]
        force.addParticle(i, [x, y, z])
        n += 1
    system.addForce(force)
    return n


def _state_xml(context, path: Path) -> None:
    import openmm as mm

    st = context.getState(
        getPositions=True, getVelocities=True, enforcePeriodicBox=True
    )
    path.write_text(mm.XmlSerializer.serialize(st), encoding="utf-8")


def _load_state(sim, path: Path) -> None:
    import openmm as mm

    st = mm.XmlSerializer.deserialize(Path(path).read_text(encoding="utf-8"))
    sim.context.setState(st)


# =================================================================== stage 3: minimize
def minimize(
    job_dir: str,
    max_iterations: int = 0,
    tolerance_kj_nm: float = 10.0,
    platform: str = "CUDA",
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Energy-minimize the solvated system. Writes minimized.pdb + state_min.xml."""
    import openmm as mm
    from openmm import unit
    from openmm.app import PDBFile, Simulation

    job = _job(job_dir, create=False)
    pdb = PDBFile(str(job / "solvated.pdb"))
    system = mm.XmlSerializer.deserialize(
        (job / "system.xml").read_text(encoding="utf-8")
    )
    integ = mm.LangevinMiddleIntegrator(
        300 * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picosecond
    )
    plat, props, used = get_platform(platform, allow_fallback)
    sim = Simulation(pdb.topology, system, integ, plat, props)
    sim.context.setPositions(pdb.positions)
    e0 = (
        sim.context.getState(getEnergy=True)
        .getPotentialEnergy()
        .value_in_unit(unit.kilojoule_per_mole)
    )
    sim.minimizeEnergy(
        tolerance=float(tolerance_kj_nm) * unit.kilojoule_per_mole / unit.nanometer,
        maxIterations=int(max_iterations),
    )
    e1 = (
        sim.context.getState(getEnergy=True)
        .getPotentialEnergy()
        .value_in_unit(unit.kilojoule_per_mole)
    )
    pos = sim.context.getState(
        getPositions=True, enforcePeriodicBox=True
    ).getPositions()
    with open(job / "minimized.pdb", "w") as fh:
        PDBFile.writeFile(pdb.topology, pos, fh)
    _state_xml(sim.context, job / "state_min.xml")
    return {
        "job_dir": str(job),
        "platform_used": used,
        "energy_initial_kJ_per_mol": round(e0, 2),
        "energy_final_kJ_per_mol": round(e1, 2),
        "minimized_pdb": str(job / "minimized.pdb"),
        "state": str(job / "state_min.xml"),
    }


# ================================================================ stage 4: equilibrate
def equilibrate(
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
    """NVT (heat, optional heavy-atom restraints) then NPT (MonteCarloBarostat) from the
    minimized state. Writes equilibrated.pdb + state_equil.xml."""
    import openmm as mm
    from openmm import unit
    from openmm.app import PDBFile, Simulation

    job = _job(job_dir, create=False)
    spec = _read_spec(job)
    pdb = PDBFile(str(job / "solvated.pdb"))
    ref = PDBFile(str(job / "minimized.pdb")).positions
    system = mm.XmlSerializer.deserialize(
        (job / "system.xml").read_text(encoding="utf-8")
    )

    n_restrained = 0
    if restraint_k and restraint_k > 0:
        n_restrained = _add_position_restraint(
            system,
            pdb.topology,
            ref,
            restraint_k,
            spec.get("n_solute_atoms", spec["n_protein_atoms"]),
        )

    dt = float(timestep_fs) / 1000.0
    integ = mm.LangevinMiddleIntegrator(
        float(temperature_K) * unit.kelvin, 1.0 / unit.picosecond, dt * unit.picosecond
    )
    plat, props, used = get_platform(platform, allow_fallback)
    sim = Simulation(pdb.topology, system, integ, plat, props)
    _load_state(sim, job / "state_min.xml")
    sim.context.setVelocitiesToTemperature(float(temperature_K) * unit.kelvin)

    # NVT
    if int(nvt_steps) > 0:
        sim.step(int(nvt_steps))
    # NPT
    if int(npt_steps) > 0:
        system.addForce(
            mm.MonteCarloBarostat(
                float(pressure_bar) * unit.bar, float(temperature_K) * unit.kelvin, 25
            )
        )
        sim.context.reinitialize(preserveState=True)
        sim.step(int(npt_steps))

    e = (
        sim.context.getState(getEnergy=True)
        .getPotentialEnergy()
        .value_in_unit(unit.kilojoule_per_mole)
    )
    pos = sim.context.getState(
        getPositions=True, enforcePeriodicBox=True
    ).getPositions()
    with open(job / "equilibrated.pdb", "w") as fh:
        PDBFile.writeFile(pdb.topology, pos, fh)
    _state_xml(sim.context, job / "state_equil.xml")
    box = sim.context.getState().getPeriodicBoxVectors().value_in_unit(unit.nanometer)
    return {
        "job_dir": str(job),
        "platform_used": used,
        "temperature_K": float(temperature_K),
        "pressure_bar": float(pressure_bar),
        "nvt_steps": int(nvt_steps),
        "npt_steps": int(npt_steps),
        "restrained_atoms": n_restrained,
        "energy_kJ_per_mol": round(e, 2),
        "box_nm": [round(box[i][i], 3) for i in range(3)],
        "equilibrated_pdb": str(job / "equilibrated.pdb"),
        "state": str(job / "state_equil.xml"),
    }


# ================================================================= stage 5: production
def production_run(
    job_dir: str,
    ns: float = 1.0,
    timestep_fs: float = 2.0,
    temperature_K: float = 300.0,
    pressure_bar: float = 1.0,
    ensemble: str = "NPT",
    report_ps: float = 10.0,
    traj_ps: float = 10.0,
    checkpoint_ps: float = 100.0,
    platform: str = "CUDA",
    allow_fallback: bool = False,
    from_state: str = "state_equil.xml",
) -> dict[str, Any]:
    """Run production MD (blocking). Writes prod.dcd, prod.chk, prod.log, state_prod.xml
    and continuously updates prod_status.json. Called inline for short runs and by the
    detached worker for long ones (see server.py --worker)."""
    import openmm as mm
    from openmm import unit
    from openmm.app import (
        PDBFile,
        Simulation,
        DCDReporter,
        StateDataReporter,
        CheckpointReporter,
    )

    job = _job(job_dir, create=False)
    status = job / "prod_status.json"
    dt = float(timestep_fs) / 1000.0
    total_steps = max(1, int(round(float(ns) * 1000.0 / dt)))
    report_steps = max(1, int(round(float(report_ps) / dt)))
    traj_steps = max(1, int(round(float(traj_ps) / dt)))
    chk_steps = max(1, int(round(float(checkpoint_ps) / dt)))

    def _status(state: str, step: int, extra: dict | None = None) -> None:
        d = {
            "status": state,
            "step": step,
            "total_steps": total_steps,
            "progress": round(step / total_steps, 4),
            "ns_done": round(step * dt / 1000.0, 5),
            "ns_target": float(ns),
        }
        if extra:
            d.update(extra)
        status.write_text(json.dumps(d, indent=2), encoding="utf-8")

    try:
        pdb = PDBFile(str(job / "solvated.pdb"))
        system = mm.XmlSerializer.deserialize(
            (job / "system.xml").read_text(encoding="utf-8")
        )
        if ensemble.upper() == "NPT":
            system.addForce(
                mm.MonteCarloBarostat(
                    float(pressure_bar) * unit.bar,
                    float(temperature_K) * unit.kelvin,
                    25,
                )
            )
        integ = mm.LangevinMiddleIntegrator(
            float(temperature_K) * unit.kelvin,
            1.0 / unit.picosecond,
            dt * unit.picosecond,
        )
        plat, props, used = get_platform(platform, allow_fallback)
        sim = Simulation(pdb.topology, system, integ, plat, props)
        _load_state(sim, job / from_state)

        sim.reporters.append(DCDReporter(str(job / "prod.dcd"), traj_steps))
        sim.reporters.append(CheckpointReporter(str(job / "prod.chk"), chk_steps))
        sim.reporters.append(
            StateDataReporter(
                str(job / "prod.log"),
                report_steps,
                step=True,
                potentialEnergy=True,
                temperature=True,
                volume=True,
                speed=True,
                progress=True,
                totalSteps=total_steps,
            )
        )
        t0 = time.time()
        _status("RUNNING", 0, {"platform_used": used})
        done = 0
        while done < total_steps:
            n = min(report_steps, total_steps - done)
            sim.step(n)
            done += n
            elapsed = time.time() - t0
            ns_day = (done * dt / 1000.0) / (elapsed / 86400.0) if elapsed > 0 else 0.0
            _status(
                "RUNNING",
                done,
                {
                    "platform_used": used,
                    "elapsed_s": round(elapsed, 1),
                    "speed_ns_per_day": round(ns_day, 2),
                },
            )
        _state_xml(sim.context, job / "state_prod.xml")
        elapsed = time.time() - t0
        _status(
            "SUCCESS",
            done,
            {
                "platform_used": used,
                "elapsed_s": round(elapsed, 1),
                "speed_ns_per_day": round(
                    (total_steps * dt / 1000.0) / (elapsed / 86400.0), 2
                )
                if elapsed > 0
                else None,
                "trajectory": str(job / "prod.dcd"),
                "checkpoint": str(job / "prod.chk"),
                "final_state": str(job / "state_prod.xml"),
            },
        )
        return json.loads(status.read_text(encoding="utf-8"))
    except Exception as e:
        import traceback

        _status(
            "FAILED",
            0,
            {
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()[-1500:],
            },
        )
        raise


# ===================================================================== stage 6: analyze
def analyze(
    job_dir: str,
    trajectory: str = "prod.dcd",
    topology: str = "solvated.pdb",
    stride: int = 1,
    hbond_freq: float = 0.1,
    contact_cutoff_nm: float = 0.4,
) -> dict[str, Any]:
    """MDTraj analysis: protein-CA RMSD/RMSF, radius of gyration, H-bonds and (if a
    ligand is present) protein-ligand contacts + ligand binding-site RMSD (stability).
    Full per-frame arrays are saved to analysis.npz; the return is a numeric summary."""
    import numpy as np
    import mdtraj as md

    job = _job(job_dir, create=False)
    spec = _read_spec(job)
    traj = job / trajectory if not os.path.isabs(trajectory) else Path(trajectory)
    top = job / topology if not os.path.isabs(topology) else Path(topology)
    t = md.load(str(traj), top=str(top), stride=int(stride))

    ca = t.topology.select("protein and name CA")
    prot_heavy = t.topology.select("protein and not element H")
    t.superpose(t, 0, atom_indices=ca if len(ca) else prot_heavy)

    def _summ(a: np.ndarray) -> dict[str, float]:
        return {
            "mean": float(np.mean(a)),
            "std": float(np.std(a)),
            "min": float(np.min(a)),
            "max": float(np.max(a)),
            "last": float(a[-1]),
        }

    rmsd_nm = md.rmsd(t, t, 0, atom_indices=ca if len(ca) else prot_heavy)
    rmsf_nm = md.rmsf(t, t, 0, atom_indices=ca if len(ca) else prot_heavy)
    rg_nm = md.compute_rg(t)
    try:
        hbonds = md.baker_hubbard(t, freq=float(hbond_freq))
        n_hbonds = int(len(hbonds))
    except Exception:
        n_hbonds = -1

    arrays: dict[str, Any] = {"rmsd_nm": rmsd_nm, "rmsf_nm": rmsf_nm, "rg_nm": rg_nm}
    result: dict[str, Any] = {
        "job_dir": str(job),
        "n_frames": int(t.n_frames),
        "protein_ca_rmsd_A": {k: round(v * 10.0, 4) for k, v in _summ(rmsd_nm).items()},
        "protein_ca_rmsf_A": {
            "mean": round(float(np.mean(rmsf_nm)) * 10, 4),
            "max": round(float(np.max(rmsf_nm)) * 10, 4),
        },
        "radius_of_gyration_A": {
            k: round(v * 10.0, 4) for k, v in _summ(rg_nm).items()
        },
        "protein_hbonds_baker_hubbard": n_hbonds,
    }

    if spec.get("has_ligand"):
        nP, nL = spec["n_protein_atoms"], spec["n_ligand_atoms"]
        lig_idx = np.arange(nP, nP + nL)
        lig_heavy = np.array(
            [i for i in lig_idx if t.topology.atom(int(i)).element.symbol != "H"]
        )
        # binding-site RMSD: ligand heavy-atom RMSD after protein alignment (already superposed)
        ref = t.xyz[0, lig_heavy]
        lig_rmsd = np.sqrt(
            np.mean(np.sum((t.xyz[:, lig_heavy] - ref) ** 2, axis=2), axis=1)
        )
        # contacts: protein heavy atoms within cutoff of any ligand heavy atom, per frame
        pairs = np.array([[p, lg] for p in prot_heavy for lg in lig_heavy])
        if len(pairs) > 200000:  # cap for speed on big proteins
            pairs = pairs[:: (len(pairs) // 200000 + 1)]
        d = md.compute_distances(t, pairs)
        contacts = np.sum(d < float(contact_cutoff_nm), axis=1)
        arrays.update(ligand_rmsd_nm=lig_rmsd, contacts=contacts)
        result["ligand_binding_rmsd_A"] = {
            k: round(v * 10.0, 4) for k, v in _summ(lig_rmsd).items()
        }
        result["protein_ligand_contacts"] = {
            "mean": round(float(np.mean(contacts)), 2),
            "min": int(np.min(contacts)),
            "max": int(np.max(contacts)),
        }
        result["binding_stability_note"] = (
            "Low, stable ligand_binding_rmsd + sustained contacts => stable pose; a rising "
            "RMSD / dropping contacts => the ligand is drifting/unbinding."
        )

    np.savez(str(job / "analysis.npz"), **arrays)
    result["arrays_npz"] = str(job / "analysis.npz")
    return result


# ====================================================================== stage 7: mmgbsa
def _add_obc_gb(system, topology) -> None:
    """Add a GBSA-OBC (OBC2) implicit-solvent force, copying per-atom charge from the
    system's NonbondedForce and assigning radius/scale by element (approximation)."""
    import openmm as mm

    nb = next(f for f in system.getForces() if isinstance(f, mm.NonbondedForce))
    gb = mm.GBSAOBCForce()
    gb.setSolventDielectric(78.5)
    gb.setSoluteDielectric(1.0)
    gb.setNonbondedMethod(mm.GBSAOBCForce.NoCutoff)
    for atom in topology.atoms():
        i = atom.index
        charge = nb.getParticleParameters(i)[0]
        sym = atom.element.symbol if atom.element is not None else "C"
        gb.addParticle(charge, _GB_RADII.get(sym, 0.15), _GB_SCALE.get(sym, 0.8))
    system.addForce(gb)


def _mm_gb_energy_context(pdb_top, offmols, spec):
    """Build a vacuum + OBC-GB Context (kJ/mol energies) for an isolated solute."""
    import openmm as mm
    from openmm import unit
    from openmm.app import NoCutoff

    ff = _build_forcefield(spec, offmols)
    system = ff.createSystem(pdb_top, nonbondedMethod=NoCutoff, constraints=None)
    _add_obc_gb(system, pdb_top)
    integ = mm.VerletIntegrator(0.001 * unit.picosecond)
    ctx = mm.Context(system, integ, mm.Platform.getPlatformByName("CPU"))
    return ctx


def mmgbsa(
    job_dir: str,
    trajectory: str = "prod.dcd",
    stride: int = 10,
    start_frame: int = 0,
    max_frames: int = 50,
) -> dict[str, Any]:
    """Free MM-GBSA-style binding free energy over the trajectory (single-trajectory,
    OBC2/GBSA, no entropy). HONEST APPROXIMATION -- see fidelity note in the return.

    Requires a protein-ligand complex. Reuses the solute ordering guaranteed by solvate
    (protein atoms then ligand atoms then solvent) to slice frames without re-mapping."""
    import numpy as np
    import mdtraj as md
    from openmm import unit
    from openmm.app import PDBFile, Modeller

    job = _job(job_dir, create=False)
    spec = _read_spec(job)
    if not spec.get("has_ligand"):
        return {
            "status": "FAILED",
            "error": "mmgbsa requires a protein-ligand complex (no ligand in this job)",
        }

    nP, nL = spec["n_protein_atoms"], spec["n_ligand_atoms"]
    offmol, _ = _load_ligand(spec["ligand_sdf"], spec.get("charge_method", "auto"))

    # Rebuild the three isolated-solute topologies (protein-then-ligand order).
    prot = PDBFile(str(job / "protein_fixed.pdb"))
    complex_mod = Modeller(prot.topology, prot.positions)
    complex_mod.add(offmol.to_topology().to_openmm(), offmol.conformers[0].to_openmm())
    lig_mod = Modeller(
        offmol.to_topology().to_openmm(), offmol.conformers[0].to_openmm()
    )

    ctx_c = _mm_gb_energy_context(complex_mod.topology, [offmol], spec)
    ctx_r = _mm_gb_energy_context(prot.topology, [], spec)
    ctx_l = _mm_gb_energy_context(lig_mod.topology, [offmol], spec)

    traj = job / trajectory if not os.path.isabs(trajectory) else Path(trajectory)
    t = md.load(str(traj), top=str(job / "solvated.pdb"), stride=int(stride))
    frames = range(int(start_frame), t.n_frames)
    if max_frames and len(list(frames)) > max_frames:
        frames = list(range(int(start_frame), t.n_frames))[:max_frames]

    def _e(ctx, xyz_nm) -> float:
        ctx.setPositions(unit.Quantity(np.asarray(xyz_nm, dtype=float), unit.nanometer))
        return (
            ctx.getState(getEnergy=True)
            .getPotentialEnergy()
            .value_in_unit(unit.kilojoule_per_mole)
        )

    dG = []
    for fi in frames:
        solute = t.xyz[fi, : nP + nL]
        ec = _e(ctx_c, solute)
        er = _e(ctx_r, solute[:nP])
        el = _e(ctx_l, solute[nP : nP + nL])
        dG.append(ec - er - el)
    dG = np.asarray(dG)
    kcal = dG / 4.184
    return {
        "status": "SUCCESS",
        "job_dir": str(job),
        "method": "OpenMM OBC2/GBSA single-trajectory (no entropy, element-based radii)",
        "n_frames_used": int(len(dG)),
        "dG_bind_kJ_per_mol": {
            "mean": round(float(np.mean(dG)), 2),
            "std": round(float(np.std(dG)), 2),
        },
        "dG_bind_kcal_per_mol": {
            "mean": round(float(np.mean(kcal)), 2),
            "std": round(float(np.std(kcal)), 2),
        },
        "fidelity_note": (
            "APPROXIMATION. This is an OpenMM-native OBC2/GBSA single-trajectory estimate with "
            "NO configurational entropy (-TdS) and generic element-based GB radii. It is useful "
            "for RANKING congeneric ligands, not for absolute affinities. It is materially lower "
            "fidelity than Schrodinger Prime MM-GBSA (VSGB2.1, optimized radii) and AmberTools "
            "MMPBSA.py (unavailable natively on Windows). Charges: "
            + str(spec.get("charge_method_used", spec.get("charge_method", "auto")))
        ),
    }
