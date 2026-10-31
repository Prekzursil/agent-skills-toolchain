import json, os
from pathlib import Path
REPO = Path.home() / "p2-g1"
my = ["IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0207","IMP-0219","IMP-0223","IMP-0224","IMP-0228","IMP-0229","IMP-0261"]
for uid in my:
    art = REPO / "command-center/receipts" / f"{uid}.json"
    pd = REPO / "command-center/p2-wave/probes" / uid
    print("=" * 12, uid, "=" * 12)
    if art.is_file():
        try:
            d = json.loads(art.read_text(encoding="utf-8"))
            rv = d.get("reviewer") or {}
            print(f"artifact: size={art.stat().st_size} state={d.get('state')!r} reviewer.verdict={rv.get('verdict')!r} independent={rv.get('independent')!r}")
        except Exception as e:
            print(f"artifact: size={art.stat().st_size} PARSE-ERROR {type(e).__name__}: {e}")
    else:
        print("artifact: MISSING")
    if pd.is_dir():
        names = sorted(p.name for p in pd.iterdir())
        print("probedir:", " ".join(names))
        ret = pd / "SUBAGENT-RETURN.json"
        if ret.is_file():
            try:
                r = json.loads(ret.read_text(encoding="utf-8"))
                print("  return.status:", r.get("status") or r.get("state"), "| named_probes:", len(r.get("named_probes") or r.get("probes") or []))
            except Exception as e:
                print("  return: PARSE-ERROR", e)
        man = pd / "UNIT-ARTIFACT-MANIFEST.json"
        if man.is_file():
            try:
                m = json.loads(man.read_text(encoding="utf-8"))
                rows = [a for a in (m.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
                print("  manifest rows for unit:", len(rows), [ (a.get('path'), a.get('sha256','')[:12], a.get('present')) for a in rows ])
            except Exception as e:
                print("  manifest: PARSE-ERROR", e)
        else:
            print("  manifest: MISSING")
    else:
        print("probedir: MISSING")
