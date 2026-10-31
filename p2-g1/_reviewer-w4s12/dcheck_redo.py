"""D-check redo: completion gate WITH --repo-root, tolerant conditions parser."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MINE = ["IMP-0461", "IMP-0465", "IMP-0476", "IMP-0478", "IMP-0480",
        "REL-0001", "REL-0006", "REL-0014", "REL-0017", "REL-0020",
        "REL-0021", "REL-0022"]
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

out = {}
for uid in MINE:
    out_rel = str(byid[uid]["output_path"]).replace("\\", "/")
    p = subprocess.run([sys.executable, "-I", "platform/lib/receipt_schema_gate.py",
                        out_rel, "--json", "--repo-root", str(REPO)],
                       cwd=str(REPO), capture_output=True, text=True,
                       env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": __import__("os").environ["PATH"],
                            "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
    row = {"rc": p.returncode}
    try:
        d = json.loads(p.stdout)
        r0 = d[0] if isinstance(d, list) else d
        row["complete"] = r0.get("complete")
        row["marker"] = r0.get("marker")
        conds = r0.get("conditions")
        flat = {}
        if isinstance(conds, dict):
            flat = {k: v.get("status") if isinstance(v, dict) else v for k, v in conds.items()}
        elif isinstance(conds, list):
            for r in conds:
                if isinstance(r, dict):
                    key = str(r.get("id") or r.get("condition") or r.get("number") or len(flat))
                    flat[key] = r.get("status") or r.get("state") or json.dumps(r)[:120]
        row["conditions"] = flat
        row["unsat"] = sorted(k for k, v in flat.items() if v == "UNSATISFIED")
        row["not_checked"] = sorted(k for k, v in flat.items() if v == "NOT-CHECKED")
        row["schema_errors"] = r0.get("schema_errors")
    except Exception as e:
        row["parse_error"] = type(e).__name__ + ": " + str(e)
        row["raw"] = p.stdout[:400] + " || " + p.stderr[:200]
    out[uid] = row
    print(uid, "| rc:", row["rc"], "| complete:", row.get("complete"),
          "| unsat:", row.get("unsat"), "| not_checked:", row.get("not_checked"),
          "| marker:", str(row.get("marker"))[:110], flush=True)
    if row.get("schema_errors"):
        print("   schema_errors:", json.dumps(row["schema_errors"])[:300], flush=True)

(REPO / "_reviewer-w4s12/dcheck_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("DONE")
