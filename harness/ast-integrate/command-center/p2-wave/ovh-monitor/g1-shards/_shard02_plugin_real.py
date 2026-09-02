#!/usr/bin/env python3
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
root = REPO / "tools" / "plugin"
real = stub = 0
for p in sorted(root.rglob("*.py")):
    head = p.read_text(encoding="utf-8", errors="replace")[:400]
    kind = "STUB" if ("g1-surface: generated" in head or "class _NS:" in head) else "REAL"
    if kind == "STUB":
        stub += 1
    else:
        real += 1
        print(f"REAL {p.relative_to(REPO).as_posix()} {p.stat().st_size}")
print(f"summary real={real} stub={stub}")
