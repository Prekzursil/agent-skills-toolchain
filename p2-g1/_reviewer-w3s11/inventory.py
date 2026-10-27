import json, io, sys, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0207","IMP-0219","IMP-0223","IMP-0224","IMP-0228","IMP-0229","IMP-0261"]
cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat["work_units"] if isinstance(u, dict)}
for uid in UNITS:
    cu = byid.get(uid)
    print("="*90)
    if cu is None:
        print(uid, "CATALOG-ENTRY-ABSENT"); continue
    out_rel = str(cu.get("output_path") or "").replace("\\","/")
    out = REPO/out_rel
    print(f"{uid} | out={out_rel} exists={out.is_file()} size={out.stat().st_size if out.is_file() else 0}")
    print(f"  output_schema={cu.get('output_schema')}")
    print(f"  sentinel={cu.get('completion_sentinel')}")
    prov = cu.get("probes")
    print(f"  probes_field={json.dumps(prov)[:200] if prov else None}")
    if out.is_file():
        try:
            r = json.loads(out.read_text(encoding="utf-8"))
            rev = r.get("reviewer") if isinstance(r.get("reviewer"), dict) else {}
            print(f"  receipt state={r.get('state')!r} reviewer.verdict={rev.get('verdict')!r} independent={rev.get('independent')!r} reviewer_id={rev.get('reviewer_id')!r}")
            np = r.get("named_probes")
            print(f"  named_probes={[ (i.get('command') if isinstance(i,dict) else i) for i in (np or [])][:3]}")
        except Exception as e:
            print(f"  receipt UNPARSEABLE: {type(e).__name__}: {e}")
    man = REPO/"command-center"/"p2-wave"/"probes"/uid/"UNIT-ARTIFACT-MANIFEST.json"
    if man.is_file():
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
            rows = m.get("artifacts") or []
            print(f"  manifest rows={len(rows)}: " + "; ".join(f"{a.get('path')} pres={a.get('present')} sha={str(a.get('sha256'))[:8]} bytes={a.get('bytes')}" for a in rows))
        except Exception as e:
            print(f"  manifest UNPARSEABLE: {type(e).__name__}")
    else:
        print("  MANIFEST-ABSENT")
    pdir = REPO/"command-center"/"p2-wave"/"probes"/uid
    pr = [p.name for p in sorted(pdir.glob("probe[0-9]*.py"))] if pdir.is_dir() else []
    sr = pdir/"SUBAGENT-RETURN.json"
    npr = []
    if sr.is_file():
        try:
            ret = json.loads(sr.read_text(encoding="utf-8"))
            npr = [i.get("command") for i in (ret.get("named_probes") or []) + (ret.get("probes") or []) if isinstance(i,dict) and i.get("command")]
        except Exception: pass
    print(f"  probe files={pr} subagent-return-cmds={npr[:2]}")
