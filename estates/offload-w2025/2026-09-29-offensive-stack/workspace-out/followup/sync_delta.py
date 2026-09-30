import os, shutil, filecmp, hashlib

W = r"C:\Users\prekzursil\.zcode\workspace\default\out"
E = r"D:\opt\vault\agent-skills-toolchain\estates\offload-w2025\2026-09-29-offensive-stack\workspace-out"

EXCLUDE_DIRS = {"tmp", "target", "vendor", "node_modules", "mingw", "cloudfox-bin",
                "site-packages", ".venv", "venv", "artblood-src"}
RESERVED = {"nul", "con", "prn", "aux"}
MAX_FILE = 5 * 1024 * 1024  # 5MB per-file cap

copied, skipped_big, skipped_dir, failed = [], [], [], []

def lp(p):
    return "\\\\?\\" + os.path.abspath(p)

def sha(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

for root, dirs, files in os.walk(W):
    rel_root = os.path.relpath(root, W)
    parts = [] if rel_root == "." else rel_root.split(os.sep)
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    for f in files:
        if f.lower() in RESERVED:
            continue
        wf = os.path.join(root, f)
        rel = os.path.relpath(wf, W)
        ef = os.path.join(E, rel)
        try:
            sz = os.path.getsize(wf)
        except OSError:
            continue
        if sz > MAX_FILE:
            skipped_big.append((rel, sz)); continue
        try:
            if not os.path.exists(lp(ef)):
                os.makedirs(lp(os.path.dirname(ef)), exist_ok=True)
                shutil.copy2(lp(wf), lp(ef)); copied.append(rel)
            elif os.path.getsize(lp(ef)) != sz or sha(wf) != sha(lp(ef)):
                os.makedirs(lp(os.path.dirname(ef)), exist_ok=True)
                shutil.copy2(lp(wf), lp(ef)); copied.append(rel)
        except OSError as ex:
            failed.append((rel, str(ex)))

# note what the dir excludes covered (for the report)
for d in EXCLUDE_DIRS:
    p = os.path.join(W, "research", d)
    if os.path.exists(p):
        skipped_dir.append(d)

total = sum(os.path.getsize(os.path.join(E, r)) for r in copied if os.path.exists(os.path.join(E, r)))
print(f"COPIED: {len(copied)} files, {total/1e6:.2f}MB")
for r in sorted(copied)[:60]:
    print("  +", r)
print(f"\nSKIPPED (>5MB): {len(skipped_big)}")
for r, s in sorted(skipped_big, key=lambda x: -x[1])[:15]:
    print(f"  - {s/1e6:8.1f}MB {r}")
print(f"\nEXCLUDED DIRS present: {skipped_dir}")
print(f"FAILED: {len(failed)}")
for r, e in failed[:10]:
    print("  !", r, "|", e)
