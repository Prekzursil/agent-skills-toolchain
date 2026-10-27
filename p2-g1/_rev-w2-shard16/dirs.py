import os
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
def cps(s):
    return " ".join(f"{ord(c):x}" for c in s)

for name in sorted(os.listdir(REPO)):
    p = REPO / name
    if p.is_dir() and ("command" in name or name in ("platform", "tools")):
        print("DIR:", cps(name))
sub = REPO / os.listdir(REPO)[[n.startswith("comm") for n in os.listdir(REPO)].index(True)] if any(n.startswith("comm") for n in os.listdir(REPO)) else None
for name in sorted(os.listdir(sub)):
    print("  SUB:", cps(name))
