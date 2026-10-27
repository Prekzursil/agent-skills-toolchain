import hashlib, json
from pathlib import Path
REPO = Path.cwd()
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
CRLF = bytes([13, 10])
LF = bytes([10])
BS = chr(92)
cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
units = cat["work_units"]

def digest(p):
    raw = Path(p).read_bytes().replace(CRLF, LF)
    return hashlib.sha256(raw).hexdigest()

def load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None

keys = ["delivered_static", "no_artifact", "blocked", "sentinel_absent",
        "unparseable", "sha_mismatch", "no_manifest", "no_probedir"]
res = {k: [] for k in keys}
for u in units:
    uid = u.get("id")
    out_rel = str(u.get("output_path") or "").replace(BS, "/")
    if not uid or not out_rel:
        continue
    pd = REPO / "command-center/p2-wave/probes" / uid
    if not pd.is_dir():
        res["no_probedir"].append(uid)
        continue
    out = REPO / out_rel
    if not out.is_file() or out.stat().st_size <= 0:
        res["no_artifact"].append(uid)
        continue
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception:
        res["unparseable"].append(uid)
        continue
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            res["blocked"].append(uid)
            continue
        sentinel = str(u.get("completion_sentinel") or "")
        if sentinel and sentinel not in text:
            res["sentinel_absent"].append(uid)
            continue
    man = load(pd / "UNIT-ARTIFACT-MANIFEST.json")
    if not isinstance(man, dict):
        res["no_manifest"].append(uid)
        continue
    rows = [a for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == uid]
    if not rows:
        res["no_manifest"].append(uid)
        continue
    live = digest(out)
    ok = any(str(a.get("path") or "").replace(BS, "/") == out_rel
             and str(a.get("sha256") or "") == live
             and a.get("present") is True for a in rows)
    if not ok:
        res["sha_mismatch"].append(uid)
        continue
    res["delivered_static"].append(uid)

Path("_static_sweep_w4s10_out.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
tot = len(units)
ds = len(res["delivered_static"])
print("TOTAL_UNITS=%d" % tot)
for k in keys:
    print("%s=%d" % (k, len(res[k])))
print("STATIC_GREEN=%d/%d = %.1f%%" % (ds, tot, 100.0 * ds / tot))
print("remaining_to_2007 =", tot - ds)
for k in keys:
    if k != "delivered_static" and res[k]:
        print("sample", k, res[k][:12])
