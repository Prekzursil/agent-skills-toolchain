import json, hashlib, os
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CC = REPO / "command-center"
cat = json.load(open(CC / "WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u.get("id"): u for u in (cat.get("work_units") or []) if isinstance(u, dict)}
NOTDEL = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
ids = ['AUD-0043','AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075']
def sha_norm(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
for uid in ids:
    u = byid[uid]
    out_rel = str(u.get("output_path","")).replace("\\","/")
    out = REPO / out_rel
    art = "absent"
    state = "-"
    sentinel_ok = None
    if out.is_file() and out.stat().st_size > 0:
        raw = out.read_bytes()
        try:
            text = raw.decode("utf-8"); doc = json.loads(text)
            state = str(doc.get("state") or doc.get("status") or "?").upper() if isinstance(doc, dict) else "non-dict"
            sentinel_ok = (u.get("completion_sentinel") or "") in text if u.get("completion_sentinel") else None
            art = f"{len(raw)}B"
        except Exception as e:
            art = f"UNPARSEABLE:{type(e).__name__}"; state="ERR"
    pdir = CC / "p2-wave" / "probes" / uid
    ret, man_row, man_sha = "-", None, "-"
    if (pdir/"SUBAGENT-RETURN.json").is_file():
        try:
            r = json.load(open(pdir/"SUBAGENT-RETURN.json", encoding="utf-8"))
            ret = str(r.get("status") or r.get("state") or "?").upper()
        except Exception as e:
            ret = f"ERR:{type(e).__name__}"
    if (pdir/"UNIT-ARTIFACT-MANIFEST.json").is_file():
        try:
            m = json.load(open(pdir/"UNIT-ARTIFACT-MANIFEST.json", encoding="utf-8"))
            rows = [a for a in (m.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id")==uid]
            if rows:
                a0 = rows[0]
                man_row = f"{len(rows)}row"
                if out.is_file():
                    man_sha = "MATCH" if (str(a0.get("path","")).replace("\\","/")==out_rel and a0.get("sha256")==sha_norm(out) and a0.get("present") is True) else "MISMATCH"
                else:
                    man_sha = "no-artifact"
            else:
                man_row = "0row"
        except Exception as e:
            man_row = f"ERR:{type(e).__name__}"
    receipt = "-"
    rp = CC / "receipts" / f"{uid}.json"
    if rp.is_file():
        try:
            rj = json.load(open(rp, encoding="utf-8"))
            rv = (rj.get("reviewer") or {})
            receipt = f"state={rj.get('state')} reviewer={rv.get('verdict')}/ind={rv.get('independent')}"
        except Exception as e:
            receipt = f"ERR:{type(e).__name__}"
    deps = u.get("dependencies") or []
    dep_state = []
    for d in deps:
        du = byid.get(d)
        if du is None:
            dep_state.append(f"{d}:token-unknown"); continue
        dp = REPO / str(du.get("output_path","")).replace("\\","/")
        dep_state.append(f"{d}:{'OK' if dp.is_file() and dp.stat().st_size>0 else 'absent'}")
    print(f"{uid} art={art} state={state} sent={sentinel_ok} ret={ret} man={man_row}/{man_sha} receipt[{receipt}] deps={','.join(dep_state)}")
