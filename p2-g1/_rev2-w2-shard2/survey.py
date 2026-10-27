import json, os
base = r'C:\Users\Prekzursil\p2-g1'
ids = ['ADV-0124','ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048']
for u in ids:
    d = json.load(open(os.path.join(base,'command-center','receipts',u+'.json'), encoding='utf-8'))
    prim = [a for a in d.get('artifacts',[]) if a.get('role')=='primary']
    f = d.get('failure') or {}
    rv = d.get('reviewer') or {}
    print(f"{u}: state={d.get('state')} reviewer={rv.get('verdict')}/{rv.get('independent')} fail.class={f.get('classification')} n_art={len(d.get('artifacts',[]))} n_ev={len(d.get('evidence',[]))}")
    for a in d.get('artifacts',[]):
        print(f"    art[{a.get('role')}] {a.get('path')} sha={a.get('sha256','')[:12]} bytes={a.get('bytes')}")
    for ev in d.get('evidence',[]):
        for p in ev.get('probes',[]):
            print(f"    probe[{p.get('role')}/{p.get('method')}] exit={p.get('exit_code')} cmd={p.get('command','')[:110]}")
