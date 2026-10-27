import json, hashlib
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["IMP-0470","IMP-0478","REL-0001","REL-0006","REL-0014","REL-0017",
         "REL-0020","REL-0021","REL-0022","RES-0004","RES-0009","RES-0011"]

cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by = {u.get("id"): u for u in cat.get("work_units") or []}

for uid in UNITS:
    u = by.get(uid)
    if u is None:
        print(uid, "CATALOG-ABSENT"); continue
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    if not out.is_file():
        print(uid, "ARTIFACT-ABSENT", out_rel); continue
    size = out.stat().st_size
    raw = out.read_bytes()
    live_sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(uid, "UNPARSEABLE", type(e).__name__, size); continue
    st = str(doc.get("state") or "").upper()
    rev = doc.get("reviewer")
    rv = None
    if isinstance(rev, dict):
        rv = (rev.get("verdict"), rev.get("independent"))
    fail = doc.get("failure")
    cls = ""
    if isinstance(fail, dict):
        cls = ",".join(fail.get("classification") or [])
    manp = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    mrow = None
    if manp.is_file():
        man = json.loads(manp.read_text(encoding="utf-8"))
        for a in man.get("artifacts") or []:
            if (isinstance(a, dict) and a.get("unit_id") == uid
                    and str(a.get("path") or "").replace("\\", "/") == out_rel):
                mrow = a
    msha = mrow.get("sha256") if isinstance(mrow, dict) else None
    sha_ok = (msha == live_sha and isinstance(mrow, dict) and mrow.get("present") is True)
    ret = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
    ret_st = ""
    if ret.is_file():
        try:
            rd = json.loads(ret.read_text(encoding="utf-8"))
            ret_st = str(rd.get("status") or rd.get("state") or "").upper()
        except Exception:
            ret_st = "UNPARSEABLE"
    print(f"{uid} bytes={size} state={st or '-'} reviewer={rv} manifest_sha={'OK' if sha_ok else 'MISMATCH'} ret={ret_st} cls={cls[:50]} schema={u.get('output_schema')}")
