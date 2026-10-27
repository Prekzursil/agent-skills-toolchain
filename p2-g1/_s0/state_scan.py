import json, os
from pathlib import Path

REPO = Path.home() / "p2-g1"
wave = ["ADV-0015", "AUD-0068", "AUD-0080", "BLD-0002", "BLD-0062", "CC-0008",
        "CNF-0097", "CNF-0146", "CNF-0149", "CNF-0158", "IMP-0070", "IMP-0090",
        "IMP-0102", "IMP-0131", "IMP-0221"]
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by_id = {u.get("id"): u for u in cat.get("work_units") or []}
report = {}
for uid in wave:
    u = by_id[uid]
    outp = REPO / str(u["output_path"])
    pd = REPO / "command-center" / "p2-wave" / "probes" / uid
    r = {"output_path": str(u["output_path"]), "artifact_exists": outp.is_file(),
         "artifact_bytes": outp.stat().st_size if outp.is_file() else 0}
    ret = pd / "SUBAGENT-RETURN.json"
    if ret.is_file():
        try:
            rd = json.loads(ret.read_text(encoding="utf-8"))
            r["ret_status"] = rd.get("status") or rd.get("state")
            r["ret_keys"] = sorted(rd.keys())
        except Exception as e:
            r["ret_status"] = "UNPARSEABLE:%s" % e
    else:
        r["ret_status"] = "ABSENT"
    man = pd / "UNIT-ARTIFACT-MANIFEST.json"
    if man.is_file():
        try:
            md = json.loads(man.read_text(encoding="utf-8"))
            rows = [a for a in (md.get("artifacts") or []) if a.get("unit_id") == uid]
            r["manifest_rows"] = [{k: a.get(k) for k in ("unit_id", "path", "sha256", "present")} for a in rows]
            r["manifest_top_keys"] = sorted(md.keys())
        except Exception as e:
            r["manifest_rows"] = "UNPARSEABLE:%s" % e
    else:
        r["manifest_rows"] = "ABSENT"
    # emit script names present
    r["emit_scripts"] = [p.name for p in sorted(pd.iterdir()) if p.is_file() and ("emit" in p.name or p.name.startswith("write_"))]
    report[uid] = r
Path("/tmp/s0_state.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print("wrote /tmp/s0_state.json", os.path.getsize("/tmp/s0_state.json"))
# find receipt_core
import subprocess
p = subprocess.run(["grep", "-rl", "reviewer-absent", str(REPO / "command-center")], capture_output=True, text=True)
print("reviewer-absent hits:")
print(p.stdout[:3000])
