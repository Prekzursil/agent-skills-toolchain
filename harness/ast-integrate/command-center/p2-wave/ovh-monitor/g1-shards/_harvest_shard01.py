#!/usr/bin/env python3
"""Find harvest copies of missing files for shard-01."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
MON = WAVE / "ovh-monitor"
IDS = [
    ln.strip()
    for ln in (MON / "g1-shards" / "shard-01.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]

WANTED_REL = [
    "command-center/p2-wave/probes/ADV-0061/probe1_entrypoints.py",
    "command-center/p2-wave/probes/ADV-0061/probe2_failure_branches.py",
    "command-center/p2-wave/probes/ADV-0061/harness.py",
    "command-center/p2-wave/probes/ADV-0061/emit_artifact.py",
    "tools/marketplace/tests/test_dependency_graph.py",
    "tools/marketplace/dependency.py",
    "tools/selfimprove/retain.py",
    "tools/selfimprove/__init__.py",
    "tools/plugin/health_check.py",
    "tools/agentspec/agentspec/export.py",
    "tools/candidates/freshness.py",
    "tools/council/evidence/freshness.py",
    "tools/council/completeness.py",
    "tools/council/partition.py",
    "tools/orphan_reaper/liveness.py",
    "tools/concurrency_governor/__init__.py",
    "tools/elapsed.py",
    "tools/elapsed/__init__.py",
    "tools/work_unit_conformance.py",
    "command-center/work_unit_conformance.py",
    "tools/marketplace/version.py",
]


def harvest_roots() -> list[Path]:
    roots = []
    for kind in ("delivery-pull", "missing-pull", "error-pull"):
        p = MON / kind
        if not p.is_dir():
            continue
        for box in p.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta", "extracted", "extracted-delta"):
                b = box / sub
                if b.is_dir():
                    roots.append(b)
            # error-pull extracted/<box>/probes
            ext = box / "extracted"
            if ext.is_dir():
                roots.append(ext)
    return roots


def find_rel(rel: str) -> list[tuple[int, Path]]:
    hits = []
    for root in harvest_roots():
        cand = root / rel
        if cand.is_file() and cand.stat().st_size > 0:
            hits.append((cand.stat().st_size, cand))
        # probes-only extract layout
        if rel.startswith("command-center/p2-wave/probes/"):
            tail = rel.split("probes/", 1)[-1]
            alt = root / "probes" / tail
            if alt.is_file() and alt.stat().st_size > 0:
                hits.append((alt.stat().st_size, alt))
            alt2 = root / tail
            if alt2.is_file() and alt2.stat().st_size > 0:
                hits.append((alt2.stat().st_size, alt2))
        name = Path(rel).name
        # name-only in probes/<id>
        for uid in IDS:
            pdir = root / "command-center" / "p2-wave" / "probes" / uid
            if not pdir.is_dir():
                pdir = root / "probes" / uid
            if pdir.is_dir():
                c = pdir / name
                if c.is_file() and c.stat().st_size > 0:
                    hits.append((c.stat().st_size, c))
    hits.sort(key=lambda x: -x[0])
    # unique by size+name
    seen = set()
    out = []
    for sz, p in hits:
        key = (sz, p.name)
        if key in seen:
            continue
        seen.add(key)
        out.append((sz, p))
    return out[:6]


def main() -> None:
    for rel in WANTED_REL:
        live = REPO / rel
        live_sz = live.stat().st_size if live.is_file() else 0
        hits = find_rel(rel)
        print(f"\n{rel} live={live_sz} hits={len(hits)}")
        for sz, p in hits[:4]:
            print(f"  {sz:8d} {p}")


if __name__ == "__main__":
    main()
