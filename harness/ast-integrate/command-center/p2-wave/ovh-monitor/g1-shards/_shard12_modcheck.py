#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
rows = json.loads((HERE / "_shard12_dump.json").read_text(encoding="utf-8"))
skip = {
    "__future__",
    "json",
    "pathlib",
    "sys",
    "os",
    "copy",
    "shutil",
    "tempfile",
    "hashlib",
    "re",
    "ast",
    "subprocess",
    "typing",
    "itertools",
    "secrets",
    "jsonschema",
}
print("REPO", REPO)
seen: dict[str, list[str]] = {}
for r in rows:
    for imp in r.get("imports") or []:
        if imp.split(".")[0] in skip or imp in skip:
            continue
        seen.setdefault(imp, []).append(r["id"])

# try resolve
cands_roots = [
    REPO,
    REPO / "tools",
    REPO / "tools" / "measure-guard",
    REPO / "platform" / "lib",
    REPO / "command-center" / "p2-wave" / "seed-stage",
    REPO / "tools" / "agentspec",
    REPO / "command-center" / "lib",
]


def exists(mod: str) -> list[str]:
    hits = []
    rel = Path(*mod.split("."))
    for root in cands_roots:
        for suffix in (rel.with_suffix(".py"), rel / "__init__.py"):
            p = root / suffix
            if p.is_file():
                hits.append(str(p.relative_to(REPO)).replace("\\", "/"))
    return hits


for mod, uids in sorted(seen.items()):
    hits = exists(mod)
    mark = "Y" if hits else "N"
    print(f"{mark} {mod} ids={uids[:8]} hits={hits[:3]}")
