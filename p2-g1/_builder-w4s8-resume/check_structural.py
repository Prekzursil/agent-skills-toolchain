import json, hashlib
from pathlib import Path
REPO = Path.home() / "p2-g1"
cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
idx = {u["id"]: u for u in cat["work_units"]}
units = ["IMP-0071","IMP-0099","IMP-0104","IMP-0113","IMP-0121","IMP-0155","IMP-0166","IMP-0167","IMP-0189","IMP-0194","IMP-0195","IMP-0198"]
def digest(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
for u in units:
    e = idx[u]
    out = REPO / str(e["output_path"])
    print("==", u)
    if not out.is_file() or out.stat().st_size <= 0:
        print("  ARTIFACT MISSING/EMPTY"); continue
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
    except Exception as ex:
        print("  UNPARSEABLE:", type(ex).__name__); continue
    st = str(doc.get("state") or "").upper()
    rev = doc.get("reviewer") or {}
    print("  state:", st, "| reviewer.verdict:", rev.get("verdict"), "| independent:", rev.get("independent"))
    man_p = REPO / "command-center/p2-wave/probes" / u / "UNIT-ARTIFACT-MANIFEST.json"
    ret_p = REPO / "command-center/p2-wave/probes" / u / "SUBAGENT-RETURN.json"
    print("  manifest file:", man_p.is_file(), "| SUBAGENT-RETURN:", ret_p.is_file())
    if man_p.is_file():
        man = json.load(open(man_p, encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == u]
        live = digest(out)
        out_rel = str(e["output_path"]).replace("\\", "/")
        ok = any(str(a.get("path","")).replace("\\","/") == out_rel and a.get("sha256") == live and a.get("present") is True for a in rows)
        print("  manifest rows:", len(rows), "| sha-match-live:", ok, "| live sha:", live[:16])
