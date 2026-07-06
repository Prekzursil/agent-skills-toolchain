"""Schrodinger-side helper — runs INSIDE the Schrodinger interpreter
(`$SCHRODINGER/run python3 _sch_helper.py <cmd> <json-args>`), where both the
`schrodinger` package and a bundled `rdkit` are importable. Emits one JSON line.

The MCP server (server.py, in its own venv) invokes this via subprocess so it
never has to import `schrodinger` directly (which only works under `run`).
"""

import sys
import os
import json


def _info(_a):
    out = {"schrodinger_path": os.environ.get("SCHRODINGER", "")}
    try:
        import schrodinger

        out["schrodinger_build"] = getattr(schrodinger, "__version__", "n/a")
    except Exception as e:
        out["schrodinger_build"] = "ERR " + repr(e)
    try:
        import rdkit

        out["rdkit"] = rdkit.__version__
    except Exception as e:
        out["rdkit"] = "ERR " + repr(e)
    return out


def _smiles_to_3d(a):
    """SMILES -> 3D structure file (.sdf or .mae). 3D via RDKit ETKDGv3 + MMFF."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    smiles, out_path, title = a["smiles"], a["out_path"], a.get("title", "")
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return {"error": "invalid SMILES: " + smiles}
    m = Chem.AddHs(m)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(m, params) != 0:
        return {"error": "3D embedding failed for " + smiles}
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    if title:
        m.SetProp("_Name", title)
    ext = os.path.splitext(out_path)[1].lower()
    if ext in (".sdf", ".sd"):
        w = Chem.SDWriter(out_path)
        w.write(m)
        w.close()
    else:  # .mae / .maegz via schrodinger structure (keeps 3D coords from rdkit)
        from schrodinger.adapter import to_structure

        st = to_structure(m)
        if title:
            st.title = title
        st.write(out_path)
    return {
        "ok": True,
        "out_path": out_path,
        "atoms": m.GetNumAtoms(),
        "size_bytes": os.path.getsize(out_path),
    }


def _properties(a):
    """Drug-likeness descriptor panel for a SMILES (RDKit)."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Crippen, Lipinski, rdMolDescriptors

    m = Chem.MolFromSmiles(a["smiles"])
    if m is None:
        return {"error": "invalid SMILES: " + a["smiles"]}
    mw, logp = Descriptors.MolWt(m), Crippen.MolLogP(m)
    hbd, hba = Lipinski.NumHDonors(m), Lipinski.NumHAcceptors(m)
    return {
        "formula": rdMolDescriptors.CalcMolFormula(m),
        "mw": round(mw, 2),
        "logp": round(logp, 2),
        "hbd": hbd,
        "hba": hba,
        "tpsa": round(Descriptors.TPSA(m), 2),
        "rotatable_bonds": Descriptors.NumRotatableBonds(m),
        "rings": rdMolDescriptors.CalcNumRings(m),
        "qed": round(Descriptors.qed(m), 3),
        "lipinski_pass": bool(mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10),
    }


def _convert(a):
    """Convert any structure file to another format via schrodinger.structure."""
    from schrodinger import structure

    src, dst = a["src"], a["dst"]
    n = 0
    with structure.StructureWriter(dst) as w:
        for st in structure.StructureReader(src):
            w.append(st)
            n += 1
    return {"ok": True, "dst": dst, "structures": n, "size_bytes": os.path.getsize(dst)}


def _job_common(j, complete):
    """Shared completed-job fields. `succeeded()` RAISES unless complete, so gate it."""
    out = {
        "jobid": j.JobId,
        "status": j.Status,
        "is_complete": complete,
        "program": j.Program,
        "name": j.Name,
    }
    try:
        out["progress"] = j.getProgressAsString()
    except Exception:
        out["progress"] = None
    if complete:
        out["succeeded"] = j.succeeded()
        out["exit_status"] = j.ExitStatus
        out["dir"] = j.Dir
        try:
            out["struct_output"] = j.StructureOutputFile
        except Exception:
            out["struct_output"] = None
        try:
            out["output_files"] = list(j.OutputFiles or [])
        except Exception:
            out["output_files"] = []
    return out


def _job_status(a):
    """Read a Job Control job's live status by id (works cross-process via the job server)."""
    from schrodinger.job import jobcontrol as jc

    j = jc.Job(a["jobid"])
    j.readAgain()
    return _job_common(j, j.isComplete())


def _job_wait(a):
    """Poll a Job Control job until it completes or `timeout` (s) elapses."""
    import time
    from schrodinger.job import jobcontrol as jc

    timeout = float(a.get("timeout", 600))
    poll = max(1.0, float(a.get("poll", 5)))
    deadline = time.time() + timeout
    j = jc.Job(a["jobid"])
    j.readAgain()
    while not j.isComplete() and time.time() < deadline:
        time.sleep(poll)
        j = jc.Job(a["jobid"])
        j.readAgain()
    complete = j.isComplete()
    res = _job_common(j, complete)
    res["timed_out"] = not complete
    return res


def _launch(a):
    """Submit an arbitrary argv under Job Control (async) and return its jobid.
    For manager scripts (e.g. thermal_mmgbsa.py) that are not themselves
    jobcontrol launchers; jobcontrol-aware drivers self-submit without -WAIT."""
    from schrodinger.job import jobcontrol as jc

    job = jc.launch_job(a["argv"], launch_dir=a.get("launch_dir") or None)
    return {"jobid": job.JobId, "name": job.Name, "program": job.Program}


def _trj_analyze(a):
    """Compact numeric trajectory analysis from a Desmond -out.cms (auto-finds its _trj).
    Uses schrodinger.application.desmond.packages {analysis, traj_util, topo}. Computes
    protein-CA RMSD (fit on CA), protein-CA RMSF, radius of gyration, and (if lig_asl)
    ligand RMSD after protein fit. Returns per-frame series + summary stats."""
    import numpy as np
    from schrodinger.application.desmond.packages import analysis, traj_util

    cms_file = a["cms_file"]
    fit_asl = a.get("fit_asl", 'protein and atom.ptype " CA "')
    lig_asl = a.get("lig_asl") or ""
    stride = int(a.get("stride", 1))
    msys, cms, tr = traj_util.read_cms_and_traj(cms_file)
    if stride > 1:
        tr = tr[::stride]
    fit_aids = cms.select_atom(fit_asl)
    if not fit_aids:
        return {"error": f"fit_asl matched 0 atoms: {fit_asl!r}"}
    fit_ref = cms.extract(fit_aids).getXYZ()
    analyzers, keys = [], []
    analyzers.append(
        analysis.RMSD(
            msys, cms, fit_aids, fit_ref, fit_aids=fit_aids, fit_ref_pos=fit_ref
        )
    )
    keys.append("protein_ca_rmsd")
    analyzers.append(analysis.RMSF(msys, cms, fit_aids, fit_aids, fit_ref))
    keys.append("protein_ca_rmsf")
    analyzers.append(analysis.Gyradius(msys, cms, asl=fit_asl))
    keys.append("radius_of_gyration")
    if lig_asl:
        lig_aids = cms.select_atom(f"({lig_asl}) and not atom.ele H")
        if lig_aids:
            lig_ref = cms.extract(lig_aids).getXYZ()
            analyzers.append(
                analysis.RMSD(
                    msys, cms, lig_aids, lig_ref, fit_aids=fit_aids, fit_ref_pos=fit_ref
                )
            )
            keys.append("ligand_rmsd")
    results = analysis.analyze(tr, *analyzers)
    if len(analyzers) == 1:
        results = [results]
    out = {
        "cms_file": cms_file,
        "n_frames": len(tr),
        "sim_time_ns": round(tr[-1].time / 1000.0, 4) if tr else None,
        "series": {},
        "summary": {},
    }
    for key, series in zip(keys, results):
        arr = np.asarray(series, dtype=float)
        if arr.ndim == 1 and key != "protein_ca_rmsf":  # per-frame series
            out["series"][key] = [round(float(x), 4) for x in arr.tolist()]
            out["summary"][key] = {
                "mean": round(float(arr.mean()), 4),
                "min": round(float(arr.min()), 4),
                "max": round(float(arr.max()), 4),
                "last": round(float(arr[-1]), 4),
            }
        else:  # RMSF = per-atom (mean over frames already)
            flat = arr.ravel()
            out["series"][key] = [round(float(x), 4) for x in flat.tolist()][:2000]
            out["summary"][key] = {
                "mean": round(float(flat.mean()), 4),
                "min": round(float(flat.min()), 4),
                "max": round(float(flat.max()), 4),
                "n": int(flat.size),
            }
    return out


CMDS = {
    "info": _info,
    "smiles_to_3d": _smiles_to_3d,
    "properties": _properties,
    "convert": _convert,
    "job_status": _job_status,
    "job_wait": _job_wait,
    "launch": _launch,
    "trj_analyze": _trj_analyze,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    try:
        print(json.dumps(CMDS[cmd](args)))
    except Exception as e:
        print(json.dumps({"error": repr(e)}))
