#!/usr/bin/env python3
"""Monotone ratchet on stub-marker files (02.09, frontier F13 / EVAL C3 support).

Counts files under the import roots that carry either stub marker ("# g1-surface: generated",
"# g1-mod: real-surface"), excluding probes/, shard tooling and seed-stage. Fails (exit 1) when the
count is ABOVE the committed baseline in P2-STATE/g1-placeholder-baseline.txt; `--update` may only
LOWER the baseline. Green (EVAL C3) requires the count to reach 0 for resolvable files.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import WIN  # noqa: E402

MARKERS = ("# g1-surface: " + "generated", "# g1-mod: " + "real-surface")
ROOTS = ("tools", "platform", "lib", "council", "router", "marketplace", "plugin", "workflow_foundry", "command-center")
SKIP = ("/probes/", "/g1-shards/", "/seed-stage/", "/_g1_file_to_pkg_bak/", "/_shadowed/", "/_retired-mods/")
BASELINE = WIN / "P2-STATE" / "g1-placeholder-baseline.txt"


def count() -> tuple[int, list[str]]:
    hits: list[str] = []
    for root in ROOTS:
        for p in (WIN / root).rglob("*.py"):
            s = p.as_posix()
            if any(k in s for k in SKIP):
                continue
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:1500]
            except OSError:
                continue
            if any(m in head for m in MARKERS):
                hits.append(p.relative_to(WIN).as_posix())
    return len(hits), sorted(hits)


def main() -> int:
    n, hits = count()
    base = int(BASELINE.read_text().split()[0]) if BASELINE.is_file() else None
    if "--list" in sys.argv:
        print("\n".join(hits))
    if "--update" in sys.argv:
        if base is not None and n > base:
            print(f"REFUSED: {n} > baseline {base}; the ratchet only lowers")
            return 1
        BASELINE.write_text(f"{n}\n", encoding="utf-8")
        print(f"baseline set to {n}")
        return 0
    print(f"stub-marker files: {n} (baseline {base})")
    if base is not None and n > base:
        print("FAILED: marker count rose above the baseline")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
