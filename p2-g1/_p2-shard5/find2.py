import os
base = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
hits = []
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", ".pytest_cache", ".ruff_cache")]
    for f in files:
        lf = f.lower()
        if "receipt" in lf and ("core" in lf or f.endswith(".py")):
            hits.append(os.path.relpath(os.path.join(root, f), base))
    if len(hits) > 80:
        break
for h in sorted(set(hits))[:80]:
    print(h)
