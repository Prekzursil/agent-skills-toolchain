#!/usr/bin/env python3
"""Find non-stub copies of modules shard-11 needs."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
NEED_NAMES = [
    "promotion.py",
    "plan.py",
    "compat_map.py",
    "tdd.py",
    "test_cross_vendor_confound.py",
    "pathnorm.py",
    "corpus.py",
    "layout_fingerprints.py",
    "layout_fixtures.py",
    "case_collision.py",
    "pack.py",
    "gates.py",
    "kernel.py",
    "evidence_map.py",
    "option_cards.py",
    "quality_rater.py",
    "path_recommender.py",
    "output_schema_gate.py",
    "strict_parser.py",
    "b07_scheduler.py",
    "matched_pairing.py",
    "ledger.py",
    "simulate.py",
    "fusion.py",
    "json_ingest.py",
    "prep.py",
]


def is_stub(text: str) -> bool:
    head = text[:2500]
    return (
        "# g1-surface: generated" in head
        or "# g1-mod: real-surface" in head
        or "class _NS:" in head
    )


def main() -> None:
    roots = [
        WAVE / "probes",
        REPO / "tools",
        REPO / "plugin",
        REPO / "marketplace",
        REPO / "workflow_foundry",
    ]
    for name in NEED_NAMES:
        hits = []
        for root in roots:
            if not root.exists():
                continue
            # limited depth walk via rglob on the filename only
            try:
                paths = list(root.rglob(name))
            except OSError:
                continue
            for p in paths:
                try:
                    sz = p.stat().st_size
                except OSError:
                    continue
                if sz < 80:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                stub = is_stub(text)
                if stub:
                    continue
                rel = p.relative_to(REPO).as_posix()
                hits.append((sz, rel))
        hits.sort(reverse=True)
        print(f"=== {name} n={len(hits)}")
        for sz, rel in hits[:8]:
            print(f"  {sz:6d}  {rel}")


if __name__ == "__main__":
    main()
