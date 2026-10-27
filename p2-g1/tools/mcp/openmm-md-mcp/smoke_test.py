"""End-to-end GPU smoke test -- PROVES the OpenMM CUDA pipeline actually runs.

Runs the whole pipeline directly against omm_pipeline (bypassing the MCP layer) on a tiny
real protein (chignolin) with production MD FORCED onto CUDA (allow_fallback=False), then a
ligand path (OpenFF SMIRNOFF parametrization -> short MD -> MM-GBSA). Writes smoke_result.json.

Run:  D:/micromamba/envs/openmm-md/python.exe smoke_test.py
"""

from __future__ import annotations

import json
import tempfile
import time
import traceback
from pathlib import Path

import omm_pipeline as omm

RESULT: dict = {"ok": False, "steps": []}


def log(step: str, data: dict) -> None:
    RESULT["steps"].append({"step": step, **data})
    print(f"[{step}] " + json.dumps(data, default=str)[:500], flush=True)


def main() -> None:
    base = Path(tempfile.gettempdir()) / "openmm-md"
    jd = str(base / f"smoke-{time.strftime('%H%M%S')}")

    # 1) status -- assert CUDA truly available
    st = omm.status_probe()
    log("status", {"summary": st["summary"], "cuda": st["cuda"]})
    assert st["cuda_available"], "CUDA platform NOT available -- aborting GPU smoke"

    # ---- Part A: protein-only pipeline, production forced onto CUDA ----
    prep = None
    used_pdb = None
    for pdbid in ("1UAO", "1VII", "1L2Y"):
        try:
            prep = omm.prepare(pdbid, jd)
            used_pdb = pdbid
            break
        except Exception as e:  # network/parse issue -> try next
            log("prepare_try_fail", {"pdb": pdbid, "err": str(e)[:200]})
    assert prep is not None, "could not prepare any test protein (network?)"
    log(
        "prepare",
        {
            "pdb": used_pdb,
            "n_protein_atoms": prep["n_protein_atoms"],
            "feasibility": prep["feasibility"],
        },
    )

    sv = omm.solvate(jd, padding_nm=0.8, ion_conc_M=0.15)
    log(
        "solvate",
        {
            "n_total_atoms": sv["n_total_atoms"],
            "n_waters": sv["n_waters"],
            "box_nm": sv["box_nm"],
        },
    )

    mn = omm.minimize(jd, platform="CUDA", allow_fallback=False)
    log(
        "minimize",
        {
            k: mn[k]
            for k in (
                "platform_used",
                "energy_initial_kJ_per_mol",
                "energy_final_kJ_per_mol",
            )
        },
    )

    eq = omm.equilibrate(
        jd,
        nvt_steps=1000,
        npt_steps=1000,
        restraint_k=0.0,
        platform="CUDA",
        allow_fallback=False,
    )
    log(
        "equilibrate",
        {k: eq[k] for k in ("platform_used", "energy_kJ_per_mol", "box_nm")},
    )

    t0 = time.time()
    pr = omm.production_run(
        jd,
        ns=0.02,
        timestep_fs=2.0,
        traj_ps=2.0,
        report_ps=2.0,
        checkpoint_ps=10.0,
        platform="CUDA",
        allow_fallback=False,
    )
    log(
        "production",
        {
            "status": pr["status"],
            "platform_used": pr.get("platform_used"),
            "ns_done": pr.get("ns_done"),
            "speed_ns_per_day": pr.get("speed_ns_per_day"),
            "wall_s": round(time.time() - t0, 1),
        },
    )
    assert pr["status"] == "SUCCESS" and pr.get("platform_used") == "CUDA", (
        "production did not run on CUDA"
    )

    an = omm.analyze(jd)
    log(
        "analyze",
        {
            k: an[k]
            for k in (
                "n_frames",
                "protein_ca_rmsd_A",
                "radius_of_gyration_A",
                "protein_hbonds_baker_hubbard",
            )
        },
    )
    RESULT["protein_job_dir"] = jd

    # ---- Part B: ligand path (OpenFF SMIRNOFF param + short MD + MM-GBSA) ----
    # NOTE: SMILES pose is ARBITRARY (not docked) -> mmgbsa here is a CODE-PATH smoke, not
    # a meaningful affinity. It proves the OpenFF/GBSA machinery runs end-to-end.
    jl = str(base / f"smokelig-{time.strftime('%H%M%S')}")
    try:
        pl = omm.prepare(used_pdb, jl, ligand_smiles="c1ccc(cc1)C(=O)O")  # benzoic acid
        log(
            "prepare_ligand",
            {
                "has_ligand": pl["has_ligand"],
                "n_ligand_atoms": pl["n_ligand_atoms"],
                "charge_method_used": pl.get("charge_method_used"),
                "feasibility": pl["feasibility"],
            },
        )
        omm.solvate(jl, padding_nm=0.8, ion_conc_M=0.15)
        omm.minimize(jl, platform="CUDA", allow_fallback=False)
        omm.equilibrate(
            jl,
            nvt_steps=500,
            npt_steps=500,
            restraint_k=0.0,
            platform="CUDA",
            allow_fallback=False,
        )
        prl = omm.production_run(
            jl,
            ns=0.01,
            timestep_fs=2.0,
            traj_ps=1.0,
            report_ps=1.0,
            checkpoint_ps=5.0,
            platform="CUDA",
            allow_fallback=False,
        )
        gb = omm.mmgbsa(jl, stride=1, max_frames=10)
        log(
            "mmgbsa",
            {
                "prod_status": prl["status"],
                "status": gb.get("status"),
                "dG_kcal": gb.get("dG_bind_kcal_per_mol"),
                "n_frames": gb.get("n_frames_used"),
            },
        )
        RESULT["ligand_job_dir"] = jl
        RESULT["ligand_ok"] = gb.get("status") == "SUCCESS"
    except Exception as e:
        log(
            "ligand_path_fail",
            {"err": str(e)[:400], "tb": traceback.format_exc()[-800:]},
        )
        RESULT["ligand_ok"] = False

    RESULT["ok"] = True


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        RESULT["fatal"] = f"{type(e).__name__}: {e}"
        RESULT["fatal_tb"] = traceback.format_exc()[-1500:]
        print("FATAL:", RESULT["fatal"], flush=True)
    Path(__file__).with_name("smoke_result.json").write_text(
        json.dumps(RESULT, indent=2, default=str), encoding="utf-8"
    )
    print(
        "SMOKE_DONE ok="
        + str(RESULT["ok"])
        + " ligand_ok="
        + str(RESULT.get("ligand_ok")),
        flush=True,
    )
