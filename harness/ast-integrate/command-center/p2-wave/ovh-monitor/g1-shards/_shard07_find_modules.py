#!/usr/bin/env python3
"""Locate harvest copies of missing imported modules for shard-07."""
from __future__ import annotations

from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]
REPO = WAVE.parents[1]
EP = WAVE / "ovh-monitor" / "error-pull"
NAMES = [
    "test_codex_mcp_recovery.py",
    "codex_mcp_recovery.py",
    "select_calibrated.py",
    "payload_paths.py",
    "handled-ledger.schema.json",
    "parity_bench.py",
    "load_semantics.py",
    "role_extract.py",
    "ports.py",
]


def main() -> None:
    hits: dict[str, list[str]] = {n: [] for n in NAMES}
    roots = []
    for kind in ("extracted-delta", "extracted"):
        base = EP / kind
        if not base.is_dir():
            continue
        for box in base.iterdir():
            if box.is_dir():
                roots.append(box)
    known = [
        REPO / "tools" / "command-center" / "tests" / "test_codex_mcp_recovery.py",
        REPO / "tools" / "command-center" / "codex_mcp_recovery.py",
        REPO / "tools" / "lib" / "handled-ledger.schema.json",
        REPO / "tools" / "cross_vendor" / "parity_bench.py",
        REPO / "tools" / "workflow_foundry" / "role_extract.py",
        REPO / "tools" / "agentrail" / "ports.py",
    ]
    print("LIVE")
    for p in known:
        print(" ", p, p.is_file(), p.stat().st_size if p.is_file() else 0)

    print("HARVEST")
    for box in roots:
        for n in NAMES:
            # typical leftover dump of tools next to probes
            for cand in (
                box / n,
                box / "tools" / n,
                box / "probes" / n,
            ):
                if cand.is_file():
                    hits[n].append(str(cand))
            # walk one extra level of named dirs
            for child in box.iterdir():
                if not child.is_dir():
                    continue
                if child.name in {"probes", "tools", "command-center", "platform"}:
                    p = child / n
                    if p.is_file():
                        hits[n].append(str(p))
                    # tools/command-center/tests
                    for sub in child.iterdir() if child.is_dir() else []:
                        if sub.is_dir():
                            q = sub / n
                            if q.is_file():
                                hits[n].append(str(q))
                            for sub2 in sub.iterdir() if sub.is_dir() else []:
                                if sub2.is_file() and sub2.name == n:
                                    hits[n].append(str(sub2))
                                elif sub2.is_dir():
                                    r = sub2 / n
                                    if r.is_file():
                                        hits[n].append(str(r))
    for n, rows in hits.items():
        print(n, len(rows))
        for r in rows[:6]:
            print(" ", r)


if __name__ == "__main__":
    main()
