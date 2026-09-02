#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
rows = json.loads((HERE / "_shard12_dump.json").read_text(encoding="utf-8"))
skip = {
    "__future__", "json", "pathlib", "sys", "os", "copy", "shutil", "tempfile",
    "hashlib", "re", "ast", "subprocess", "typing", "itertools", "secrets", "jsonschema",
}
mods: set[str] = set()
for r in rows:
    for imp in r.get("imports") or []:
        if imp.split(".")[0] in skip:
            continue
        mods.add(imp)

roots = [
    REPO,
    REPO / "tools",
    REPO / "platform" / "lib",
    REPO / "tools" / "agentspec",
]


def resolve(mod: str) -> list[Path]:
    rel = Path(*mod.split("."))
    hits = []
    for root in roots:
        for suffix in (rel.with_suffix(".py"), rel / "__init__.py"):
            p = root / suffix
            if p.is_file():
                hits.append(p)
    return hits


def is_stub(path: Path) -> bool:
    head = path.read_text(encoding="utf-8", errors="replace")[:900]
    return "g1-surface: generated" in head or "class _NS:" in head


def harvest_real(rel: str) -> list[tuple[int, Path]]:
    hits = []
    mon = WAVE / "ovh-monitor"
    for kind in ("delivery-pull", "missing-pull", "error-pull"):
        root = mon / kind
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta", "extracted", "extracted-delta"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 80:
                    head = cand.read_text(encoding="utf-8", errors="replace")[:240]
                    if "g1-surface: generated" in head or "class _NS:" in head:
                        continue
                    hits.append((cand.stat().st_size, cand))
    hits.sort(key=lambda x: -x[0])
    return hits[:4]


print("imported module live status")
for mod in sorted(mods):
    hits = resolve(mod)
    if not hits:
        print(f"MISSING {mod}")
        continue
    for p in hits:
        rel = p.relative_to(REPO).as_posix()
        kind = "STUB" if is_stub(p) else "REAL"
        print(f"{kind} {mod} {rel} bytes={p.stat().st_size}")
        if kind == "STUB":
            harv = harvest_real(rel)
            for sz, hp in harv:
                print(f"  HARVEST {sz} {hp}")
