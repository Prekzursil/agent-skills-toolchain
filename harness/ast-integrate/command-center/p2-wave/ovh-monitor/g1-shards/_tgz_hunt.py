#!/usr/bin/env python3
from __future__ import annotations

import tarfile
from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
WANT = (
    "index_schema.py",
    "marketplace.schema.json",
    "test_index_schema.py",
    "test_dependency_graph.py",
    "explain.py",
    "role_extract.py",
    "replay_log.py",
    "blind_first.py",
    "legal_gate.py",
    "load_semantics.py",
    "nofit.py",
    "two_state.py",
    "overhead.py",
)
ROOTS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "error-pull",
    WAVE / "ovh-monitor" / "missing-pull",
]


def main() -> None:
    tgzs: list[Path] = []
    for root in ROOTS:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if box.suffix in {".tgz", ".gz"} and box.is_file():
                tgzs.append(box)
                continue
            if not box.is_dir():
                continue
            for p in box.iterdir():
                if p.is_file() and p.suffix in {".tgz", ".gz"}:
                    tgzs.append(p)
                elif p.is_dir() and p.name in {"harvest", "harvest-delta"}:
                    tgzs.extend(x for x in p.iterdir() if x.is_file() and x.suffix in {".tgz", ".gz"})
    print("tgz_count", len(tgzs))
    hits = {n: [] for n in WANT}
    for tgz in tgzs:
        try:
            with tarfile.open(tgz, "r:*") as tf:
                for m in tf.getmembers():
                    name = Path(m.name).name
                    if name in hits and m.isfile() and m.size > 0:
                        hits[name].append(f"{tgz.name}:{m.name}:{m.size}")
                        if len(hits[name]) >= 3:
                            continue
        except Exception as exc:
            print("ERR", tgz, type(exc).__name__)
    for name, rows in hits.items():
        print(name, len(rows))
        for r in rows[:3]:
            print(" ", r)


if __name__ == "__main__":
    main()
