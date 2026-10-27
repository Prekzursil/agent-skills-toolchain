import shutil, sys
from pathlib import Path
C = Path.home() / "source" / "ast-integrate" / "command-center" / "p2-wave" / "probes"
W = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes"
IDS = ['RES-0112','RES-0114','RES-0128','RES-0131','RES-0132','RES-0137','RES-0140','RES-0141','RES-0144','RES-0148','RES-0149','RES-0150']
for uid in IDS:
    src, dst = C / uid, W / uid
    if not src.is_dir():
        print(f"FAILED:{uid} canonical probes absent"); continue
    if not dst.exists():
        shutil.copytree(src, dst)
    for pyc in dst.rglob("__pycache__"):
        shutil.rmtree(pyc, ignore_errors=True)
    n = len([p for p in dst.rglob("*") if p.is_file()])
    has_man = (dst / "UNIT-ARTIFACT-MANIFEST.json").is_file()
    has_ret = (dst / "SUBAGENT-RETURN.json").is_file()
    print(f"{uid}: {n} files manifest={has_man} return={has_ret}")
