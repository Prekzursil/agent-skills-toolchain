#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
targets = [
    REPO / "tools" / "marketplace",
    REPO / "tools" / "router",
    REPO / "tools" / "bench",
    REPO / "tools" / "council",
    REPO / "router",
    REPO / "council" / "schema",
    REPO / "workflow_foundry",
    REPO / "tools" / "workflow_foundry",
]
for root in targets:
    if not root.exists():
        print("MISSING", root)
        continue
    real = []
    stub = []
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        head = p.read_text(encoding="utf-8", errors="replace")[:400]
        rel = p.relative_to(REPO).as_posix()
        if "g1-surface: generated" in head or "class _NS:" in head:
            stub.append(rel)
        else:
            real.append(rel)
    print(f"=== {root.relative_to(REPO).as_posix()} real={len(real)} stub={len(stub)}")
    for r in real[:30]:
        print("  REAL", r)
    if len(real) > 30:
        print(f"  ... {len(real)-30} more real")
    print("  STUB sample", stub[:8])
