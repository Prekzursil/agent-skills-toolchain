"""Final verification battery for shard4 wave-1 (12 units)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
mine = ['BLD-0052','BLD-0057','CC-0011','CC-0017','CC-0022','CC-0024',
        'CNF-0063','CNF-0120','CNF-0135','CNF-0141','CNF-0144','CNF-0157']

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u.get("id"): u for u in cat["work_units"] if isinstance(u, dict)}

def sha_lf(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def run(cmd):
    e = dict(PATH=None)
    import os
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True,
                       timeout=240, env=env)
    return p.returncode

results = {}
for uid in mine:
    entry = units[uid]
    out_rel = entry["output_path"].replace(chr(92), "/")
    out = REPO / out_rel
    row = {"artifact": out_rel, "exists": out.is_file() and out.stat().st_size > 0}
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
        row["state"] = doc.get("state")
        row["failure_cls"] = (doc.get("failure") or {}).get("classification")
        row["prev_closure"] = "prev_closure" in (doc.get("extensions") or {})
        text = out.read_text(encoding="utf-8")
        row["sentinel_in_text"] = (entry.get("completion_sentinel") or "") in text
    except Exception as ex:
        row["parse_error"] = str(ex)[:120]
        results[uid] = row
        continue
    man_p = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    ret_p = PROBES / uid / "SUBAGENT-RETURN.json"
    row["manifest"] = man_p.is_file()
    row["return"] = ret_p.is_file()
    if man_p.is_file():
        man = json.loads(man_p.read_text(encoding="utf-8"))
        live = sha_lf(out)
        match = [a for a in man.get("artifacts", [])
                 if isinstance(a, dict) and a.get("unit_id") == uid
                 and str(a.get("path", "")).replace(chr(92), "/") == out_rel
                 and a.get("sha256") == live and a.get("present") is True]
        row["manifest_sha_match"] = bool(match)
    if ret_p.is_file():
        ret = json.loads(ret_p.read_text(encoding="utf-8"))
        row["return_status"] = ret.get("status")
    rcs = []
    for probe in sorted((PROBES / uid).glob("probe*_shard4.py")) or sorted((PROBES / uid).glob("probe*.py")):
        rcs.append(run(f'PYTHONDONTWRITEBYTECODE=1 python3 -B "{probe.as_posix()}"'))
    row["probe_rcs"] = rcs
    row["probes_exit0"] = bool(rcs) and all(rc == 0 for rc in rcs)
    results[uid] = row

print(json.dumps(results, indent=1))
