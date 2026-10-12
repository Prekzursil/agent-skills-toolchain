import os, filecmp, sys

W = r"C:\Users\prekzursil\.zcode\workspace\default\out"
E = r"D:\opt\vault\agent-skills-toolchain\estates\offload-w2025\2026-09-29-offensive-stack\workspace-out"

new_items = []   # (relpath, size, is_dir)
changed = []     # files whose content differs

def du(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    return total

# walk workspace, compare against estate mirror
for root, dirs, files in os.walk(W):
    rel_root = os.path.relpath(root, W)
    for d in dirs:
        rel = os.path.relpath(os.path.join(root, d), W)
        ed = os.path.join(E, rel)
        wd = os.path.join(W, rel)
        if not os.path.exists(ed):
            new_items.append((rel, du(wd), True))
    for f in files:
        if f.lower() in ("nul", "con", "prn", "aux"):
            continue
        rel = os.path.relpath(os.path.join(root, f), W)
        ef = os.path.join(E, rel)
        wf = os.path.join(W, rel)
        if not os.path.exists(ef):
            new_items.append((rel, os.path.getsize(wf), False))
        elif os.path.getsize(wf) != os.path.getsize(ef) or \
             (open(wf,'rb').read(200) != open(ef,'rb').read(200)):
            # cheap content check: size or first 200 bytes differ -> candidate changed; do full cmp for small files
            if os.path.getsize(wf) < 5_000_000 and filecmp.cmp(wf, ef, shallow=False):
                continue
            changed.append((rel, os.path.getsize(wf)))

new_items.sort(key=lambda x: -x[1])
total_new = sum(s for _,s,_ in new_items)
total_chg = sum(s for _,s in changed)
print(f"NEW dirs/files: {len(new_items)}  total {total_new/1e6:.1f}MB")
for rel, s, isd in new_items[:25]:
    print(f"  {'DIR ' if isd else 'file'} {s/1e6:9.2f}MB  {rel}")
print(f"\nCHANGED files: {len(changed)}  total {total_chg/1e6:.1f}MB")
for rel, s in changed[:15]:
    print(f"  chg  {s/1e6:9.2f}MB  {rel}")
