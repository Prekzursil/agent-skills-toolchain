import os, sys
base = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
def show(rel, limit=120):
    p = os.path.join(base, rel)
    print("=== " + rel + " ===")
    if not os.path.isdir(p):
        print("  (not a dir)")
        return
    es = sorted(os.listdir(p))
    print("count:", len(es))
    for e in es[:limit]:
        full = os.path.join(p, e)
        print(("D " if os.path.isdir(full) else "F "), e)
for rel in sys.argv[1:]:
    show(rel)
