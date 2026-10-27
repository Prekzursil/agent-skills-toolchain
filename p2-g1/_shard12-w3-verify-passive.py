import hashlib, json, re, sys
from pathlib import Path
REPO = Path.cwd()
CATALOG = REPO/"command-center/WORK-UNIT-CATALOG.json"
PROBES = REPO/"command-center/p2-wave/probes"
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
mine = ['IMP-0264','IMP-0269','IMP-0270','IMP-0271','IMP-0272','IMP-0273','IMP-0274','IMP-0275','IMP-0279','IMP-0303','IMP-0304','IMP-0306']
cat = json.loads(CATALOG.read_text(encoding='utf-8'))
byid = {u.get('id'): u for u in cat['work_units'] if isinstance(u,dict)}
def digest(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
for uid in mine:
    u = byid[uid]
    out_rel = str(u.get('output_path') or '').replace(chr(92), '/')
    out = REPO/out_rel
    if not out.is_file() or out.stat().st_size <= 0:
        print(f"{uid} FAIL artifact-absent"); continue
    try:
        text = out.read_text(encoding='utf-8'); doc = json.loads(text)
    except Exception as e:
        print(f"{uid} FAIL unparseable {type(e).__name__}: {e}"); continue
    if isinstance(doc, dict):
        st = str(doc.get('state') or '').upper()
        if st in NOT_DELIVERING:
            print(f"{uid} FAIL self-declared:{st}"); continue
    sentinel = str(u.get('completion_sentinel') or '')
    if sentinel and sentinel not in text:
        print(f"{uid} FAIL sentinel-absent"); continue
    ret_p = PROBES/uid/'SUBAGENT-RETURN.json'; man_p = PROBES/uid/'UNIT-ARTIFACT-MANIFEST.json'
    if not ret_p.is_file() or not man_p.is_file():
        print(f"{uid} FAIL ret/man-absent"); continue
    try:
        ret = json.loads(ret_p.read_text(encoding='utf-8'))
        man = json.loads(man_p.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"{uid} FAIL ret/man-unparseable {type(e).__name__}"); continue
    st_ret = str(ret.get('status') or ret.get('state') or '').upper()
    if st_ret in NOT_DELIVERING:
        print(f"{uid} FAIL return:{st_ret}"); continue
    rows = [a for a in (man.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==uid]
    live_sha = digest(out)
    match = [a for a in rows if str(a.get('path') or '').replace(chr(92),'/')==out_rel and str(a.get('sha256') or '')==live_sha and a.get('present') is True]
    np = ret.get('named_probes') or ret.get('probes') or []
    ncmd = len([1 for i in np if isinstance(i,dict) and isinstance(i.get('command'),str)])
    if not match:
        man_shas = [(str(a.get('path') or ''), str(a.get('sha256') or '')[:12], a.get('present')) for a in rows]
        print(f"{uid} PASSIVE-FAIL manifest-sha-mismatch rows={man_shas} live={live_sha[:12]} retstatus={st_ret} ncmd={ncmd}")
    else:
        cmds = [str(i.get('command','')) for i in np if isinstance(i,dict)]
        print(f"{uid} PASSIVE-OK sha={live_sha[:12]} retstatus={st_ret} ncmd={ncmd}")
        for c in cmds:
            print(f"    cmd: {c[-110:]}")
