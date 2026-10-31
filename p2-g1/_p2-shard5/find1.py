import os
base = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
hits = []
for root, dirs, files in os.walk(base):
    # prune heavy dirs
    dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", ".pytest_cache", ".ruff_cache")]
    for f in files:
        if "measure_one" in f or "receipt_core" in f.lower():
            hits.append(os.path.relpath(os.path.join(root, f), base))
    if len(hits) > 60:
        break
for h in sorted(set(hits)):
    print(h)
