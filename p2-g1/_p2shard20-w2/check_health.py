import json, sys
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import _p2lib as P
e = json.loads((REPO / "_p2shard20-w2" / "entries.json").read_text(encoding="utf-8"))
report = {}
for uid, u in e.items():
    rel = str(u.get("output_path","")).replace("\\","/")
    p = REPO / rel
    row = {"output_path": rel, "exists": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0}
    if p.is_file():
        try:
            txt = p.read_text(encoding="utf-8")
            doc = json.loads(txt)
            row["parses"] = True
            row["state"] = str(doc.get("state",""))
            sent = str(u.get("completion_sentinel") or "")
            row["sentinel_required"] = sent
            row["sentinel_present"] = sent in txt
            errs = P.validate(doc, str(u.get("output_schema")))
            row["schema_errors"] = len(errs)
            row["schema_err_head"] = errs[:3]
        except Exception as ex:
            row["parses"] = False
            row["err"] = f"{type(ex).__name__}: {ex}"[:200]
    report[uid] = row
    print(json.dumps({uid: row}, default=str)[:600])
(REPO / "_p2shard20-w2" / "health.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
