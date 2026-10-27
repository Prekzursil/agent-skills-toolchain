import json, hashlib
from pathlib import Path
WS = Path.home() / "p2-g1"
CAN = Path.home() / "source" / "ast-integrate"
cat = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}
IDS = ['RES-0112','RES-0114','RES-0128','RES-0131','RES-0132','RES-0137','RES-0140','RES-0141','RES-0144','RES-0148','RES-0149','RES-0150']

def norm_sha(p):
    if not p.is_file(): return None
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

for uid in IDS:
    op = byid[uid]["output_path"]
    art_ws = WS.joinpath(*op.split("/"))
    art_can = CAN.joinpath(*op.split("/"))
    pws, pcan = WS/"command-center/p2-wave/probes"/uid, CAN/"command-center/p2-wave/probes"/uid
    rws, rcan = WS/"command-center/receipts"/f"{uid}.json", CAN/"command-center/receipts"/f"{uid}.json"
    def brief(pdir):
        if not pdir.is_dir(): return "-"
        ret = pdir/"SUBAGENT-RETURN.json"
        s = "?"
        if ret.is_file():
            try:
                d = json.loads(ret.read_text(encoding="utf-8"))
                s = str(d.get("status") or d.get("state"))
            except Exception: s = "unparseable"
        return f"{len(list(pdir.iterdir()))}files/ret:{s}"
    line = [uid]
    for label, art, pd, rc in [("WS", art_ws, pws, rws), ("CAN", art_can, pcan, rcan)]:
        ast = "-"
        if art.is_file():
            try: ast = f"{art.stat().st_size}B/{json.loads(art.read_text(encoding='utf-8')).get('state')}"
            except Exception: ast = "unparseable"
        rst = "-"
        if rc.is_file():
            try:
                d = json.loads(rc.read_text(encoding="utf-8"))
                rst = f"{d.get('state')}/{(d.get('reviewer') or {}).get('verdict')}"
            except Exception: rst = "unparseable"
        line.append(f"{label}:art={ast} probes={brief(pd)} receipt={rst}")
    # manifest sha match check (workspace)
    man = pws/"UNIT-ARTIFACT-MANIFEST.json"
    mm = "n/a"
    if man.is_file() and art_ws.is_file():
        try:
            rows = [a for a in json.loads(man.read_text(encoding="utf-8")).get("artifacts", []) if a.get("unit_id")==uid]
            live = norm_sha(art_ws)
            ok = any(a.get("sha256")==live and a.get("present") is True and str(a.get("path","")).replace("\\","/")==op for a in rows)
            mm = "SHA-OK" if ok else "SHA-MISMATCH"
        except Exception as e: mm = f"err:{type(e).__name__}"
    line.append(f"ws-manifest={mm}")
    print(" | ".join(line))
