#!/usr/bin/env python3
"""Find non-stub harvest copies of shard-03 stub modules."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).replace if False else Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
INV = json.loads((WAVE / "ovh-monitor" / "g1-shards" / "_shard03_inventory.json").read_text(encoding="utf-8"))
STUBS = list(INV["stub_files"].keys())
MON = WAVE / "ovh-monitor"

CANDIDATE_ROOTS: list[Path] = []
for kind in ("error-pull", "delivery-pull", "missing-pull"):
    root = MON / kind
    if not root.is_dir():
        continue
    for box in root.iterdir():
        if not box.is_dir():
            continue
        for sub in ("tree", "delta", "extracted", "extracted-delta"):
            p = box / sub
            if p.is_dir():
                CANDIDATE_ROOTS.append(p)
        CANDIDATE_ROOTS.append(box)
# error-pull/extracted/<box>
for nested in ("extracted", "extracted-delta"):
    n = MON / "error-pull" / nested
    if n.is_dir():
        for box in n.iterdir():
            if box.is_dir():
                CANDIDATE_ROOTS.append(box)


def is_stub_text(text: str) -> bool:
    head = text[:1200]
    return "g1-surface: generated" in head or "class _NS:" in head


def main() -> None:
    hits = {}
    for rel in STUBS:
        found = []
        for root in CANDIDATE_ROOTS:
            cand = root / rel
            if cand.is_file() and cand.stat().st_size > 80:
                text = cand.read_text(encoding="utf-8", errors="replace")
                if is_stub_text(text):
                    continue
                found.append(
                    {
                        "path": str(cand),
                        "bytes": cand.stat().st_size,
                        "head": text.splitlines()[:8],
                    }
                )
            # also try without leading tools/
            if rel.startswith("tools/"):
                cand2 = root / rel[len("tools/") :]
                if cand2.is_file() and cand2.stat().st_size > 80:
                    text = cand2.read_text(encoding="utf-8", errors="replace")
                    if not is_stub_text(text):
                        found.append(
                            {
                                "path": str(cand2),
                                "bytes": cand2.stat().st_size,
                                "head": text.splitlines()[:8],
                            }
                        )
        hits[rel] = found[:5]
        print(f"{rel}: {len(found)} real copies")
        for f in found[:2]:
            print(f"  {f['bytes']:6} {f['path']}")
            print("   ", f["head"][0] if f["head"] else "")
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_shard03_real_mods.json"
    dest.write_text(json.dumps({"hits": hits}, indent=2) + "\n", encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
