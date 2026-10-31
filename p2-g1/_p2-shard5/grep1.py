import os, sys
base = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
pat = sys.argv[1].encode()
roots = sys.argv[2:] or ["command-center", "platform/lib", "tools/agentspec", "tools/command-center"]
seen = 0
for rootrel in roots:
    root = os.path.join(base, rootrel)
    if not os.path.isdir(root):
        continue
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", ".pytest_cache")]
        for f in files:
            if not f.endswith((".py", ".json", ".md", ".sh", ".toml", ".yaml", ".yml")):
                continue
            p = os.path.join(dirpath, f)
            try:
                with open(p, "rb") as fh:
                    data = fh.read(400000)
            except OSError:
                continue
            if pat in data:
                print(os.path.relpath(p, base))
                seen += 1
                if seen > 40:
                    sys.exit(0)
