"""Smoke test: verify the building blocks the Schrodinger MCP will rely on.
Run via:  & "$SCHRODINGER\run.exe" python3 _smoke.py
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
out = {}

# 1) SMILES -> Structure (RDKit-backed adapter), check 3D, write SDF + MAE
try:
    from schrodinger.adapter import to_structure
    st = to_structure("CC(=O)Oc1ccccc1C(=O)O")  # aspirin
    has3d = any(abs(a.z) > 1e-6 for a in st.atom)
    out["smiles_to_structure"] = f"OK atoms={st.atom_total} has3d={has3d}"
    st.title = "aspirin"
    st.write("aspirin.sdf")
    st.write("aspirin.mae")
    out["write_files"] = f"OK sdf={os.path.getsize('aspirin.sdf')}B mae={os.path.getsize('aspirin.mae')}B"
except Exception as e:
    out["smiles_to_structure"] = "ERR " + repr(e)

# 2) Read it back (round-trip)
try:
    from schrodinger import structure
    rd = structure.StructureReader.read("aspirin.mae")
    out["read_back"] = f"OK title={rd.title!r} atoms={rd.atom_total}"
except Exception as e:
    out["read_back"] = "ERR " + repr(e)

# 3) schrodinger version/products visible from inside run
try:
    import schrodinger
    out["schrodinger_pkg"] = f"OK {getattr(schrodinger, '__version__', 'n/a')}"
except Exception as e:
    out["schrodinger_pkg"] = "ERR " + repr(e)

for k, v in out.items():
    print(f"{k} :: {v}")
