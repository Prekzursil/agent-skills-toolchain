"""Full structure-based pipeline E2E for the NEW tools — proves prepwizard, glide_grid,
glide_dock and prime_mmgbsa actually EXECUTE (not just load), on a classic fast target:
trypsin + benzamidine (PDB 3PTB). Throwaway temp dir; repo stays clean. Long-running
(several license-token jobs) — intended to run in the background.

Chain:  fetch 3PTB.pdb -> prepwizard -> (centroid of the co-crystal ligand) -> glide_grid
        -> ligprep(benzamidine) -> glide_dock(SP) -> prime_mmgbsa
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import server

PDB_ID = "3PTB"
LIG_RESNAME = "BEN"  # benzamidine, the co-crystallized ligand in 3PTB
BENZAMIDINE_SMILES = "c1ccc(cc1)C(=N)N"
# Receptor PDB is fetched OUTSIDE this script (curl) and handed in via PIPE_PDB / argv —
# keeps all network egress out of the Python (no urllib / SSRF surface here).
PDB_IN = os.environ.get("PIPE_PDB") or (sys.argv[1] if len(sys.argv) > 1 else "")


def _step(name, result):
    print(f"[{name}] " + json.dumps(result, default=str)[:500], flush=True)
    return result


def main() -> int:
    ws = tempfile.mkdtemp(prefix="sch_pipe_")
    print(f"[ws] {ws}", flush=True)
    if not PDB_IN or not os.path.exists(PDB_IN):
        print(
            "VERDICT: FAIL (set PIPE_PDB to a local 3PTB.pdb path — fetch it with curl first)"
        )
        return 1
    pdb = PDB_IN
    print(f"[input] {pdb} {os.path.getsize(pdb)} bytes", flush=True)

    prep = os.path.join(ws, "receptor_prep.maegz")
    if isinstance(
        _step("prepwizard", server.prepwizard(pdb, prep, timeout_s=1800)), dict
    ):
        if not os.path.exists(prep):
            print("VERDICT: FAIL (prepwizard produced no output)")
            return 1

    # Find the co-crystal ligand's MOLECULE NUMBER -> grid centers on it AND excludes it from the
    # receptor (LIGAND_MOLECULE). Centering on bare coordinates while the ligand stays in the
    # receptor blocks the pocket => "NO GOOD POSES FOUND". (lesson baked into the skill)
    code = (
        "from schrodinger import structure\n"
        f"st=structure.StructureReader.read(r'{prep}')\n"
        f"mn=[i for i,m in enumerate(st.molecule,1) if any(a.pdbres.strip()=='{LIG_RESNAME}' for a in m.atom)]\n"
        "print('MOLNUM %d'%mn[0] if mn else 'NO_LIG')\n"
    )
    rc = server.run_schrodinger_python(code, timeout_s=300)
    molnum = 0
    for line in (rc.get("stdout", "") or "").splitlines():
        if line.startswith("MOLNUM "):
            molnum = int(line.split(" ", 1)[1].strip())
    print(f"[ligand_molnum] {molnum or rc}", flush=True)
    if not molnum:
        print("VERDICT: FAIL (could not locate co-crystal ligand molecule)")
        return 1

    grid = os.path.join(ws, "grid.zip")
    _step(
        "glide_grid",
        server.glide_grid(prep, grid, ligand_molnum=molnum, timeout_s=1800),
    )
    if not os.path.exists(grid):
        print("VERDICT: FAIL (no grid produced)")
        return 1

    smi = os.path.join(ws, "lig.smi")
    with open(smi, "w") as fh:
        fh.write(BENZAMIDINE_SMILES + " benzamidine\n")
    lig = os.path.join(ws, "lig_prepped.mae")
    _step("ligprep", server.ligprep(smi, lig, timeout_s=1200))
    if not os.path.exists(lig):
        print("VERDICT: FAIL (ligprep produced no output)")
        return 1

    dock = _step("glide_dock", server.glide_dock(grid, lig, "SP", timeout_s=3600))
    pv = dock.get("poses") if isinstance(dock, dict) else None
    if not pv or not os.path.exists(pv):
        print("VERDICT: FAIL (no docked poses)")
        return 1

    mm = _step("prime_mmgbsa", server.prime_mmgbsa(pv, timeout_s=3600))
    ok = isinstance(mm, dict) and mm.get("csv") and os.path.exists(mm["csv"])
    print(
        "VERDICT:",
        "PASS (full prepwizard->grid->dock->mmgbsa pipeline produced a dG CSV)"
        if ok
        else "PARTIAL (dock OK, mmgbsa did not produce a CSV — check tail)",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
