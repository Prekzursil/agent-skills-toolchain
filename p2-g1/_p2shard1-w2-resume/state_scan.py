import json, hashlib, os
from pathlib import Path
repo = Path.home() / "p2-g1"
cat = json.loads((repo / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u.get("id"): u for u in cat.get("work_units", [])}
mine = ["ADV-0037","ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100","ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123"]
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
def dig(p):
    if not p.is_file(): return None
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)
for uid in mine:
    u = units[uid]
    out_rel = str(u.get("output_path","")).replace("\\","/")
    out = repo / out_rel
    line = [uid]
    # artifact
    if not out.is_file(): line.append("ARTIFACT:MISSING")
    elif out.stat().st_size == 0: line.append("ARTIFACT:EMPTY")
    else:
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
            st = str(doc.get("state","")).upper() if isinstance(doc,dict) else ""
            sent = str(u.get("completion_sentinel",""))
            has_sent = (sent in out.read_text(encoding="utf-8")) if sent else None
            line.append(f"ARTIFACT:OK state={st or '?'} sentinel={'Y' if has_sent else 'N'}")
        except Exception as e:
            line.append(f"ARTIFACT:UNPARSEABLE({type(e).__name__})")
    # schema file exists?
    sch = repo / str(u.get("output_schema","")).replace("\\","/")
    line.append(f"SCHEMA:{'Y' if sch.is_file() else 'N'}")
    # probe dir contents
    pd = repo / "command-center" / "p2-wave" / "probes" / uid
    files = sorted(x.name for x in pd.iterdir()) if pd.is_dir() else []
    line.append(f"PROBES:[{','.join(files)}]" if files else "PROBES:NONE")
    sr = pd / "SUBAGENT-RETURN.json"
    if sr.is_file():
        try:
            r = json.loads(sr.read_text(encoding="utf-8"))
            line.append(f"RETURN.status={r.get('status', r.get('state','?'))}")
        except Exception as e:
            line.append("RETURN:UNPARSEABLE")
    man = pd / "UNIT-ARTIFACT-MANIFEST.json"
    if man.is_file():
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
            rows = [a for a in (m.get("artifacts") or []) if isinstance(a,dict) and a.get("unit_id")==uid]
            if out.is_file():
                live = dig(out)
                match = [a for a in rows if str(a.get("path","")).replace("\\","/")==out_rel and a.get("sha256")==live[0] and a.get("present") is True]
                line.append(f"MANIFEST:rows={len(rows)} match={'Y' if match else 'SHA-MISMATCH'}")
            else:
                line.append(f"MANIFEST:rows={len(rows)} (no artifact)")
        except Exception as e:
            line.append("MANIFEST:UNPARSEABLE")
    # receipt
    rc = repo / "command-center" / "receipts" / f"{uid}.json"
    if rc.is_file():
        try:
            r = json.loads(rc.read_text(encoding="utf-8"))
            rev = r.get("reviewer") or {}
            line.append(f"RECEIPT.state={r.get('state','?')} reviewer.verdict={rev.get('verdict','-')} ind={rev.get('independent','-')}")
        except Exception:
            line.append("RECEIPT:UNPARSEABLE")
    else:
        line.append("RECEIPT:NONE")
    print(" | ".join(str(x) for x in line))
