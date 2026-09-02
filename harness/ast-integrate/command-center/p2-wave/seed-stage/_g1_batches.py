#!/usr/bin/env python3
"""Emit writer batch files for the per-unit residue (02.09 cloud fan-out).

Groups the current fails (latest overlay) by `_g1_rootkey` key: units that share a real
file to fix go to the same batch (one writer per file), the rest are chunked by unit
prefix. Each batch file lists, per unit: id, catalog output_path, probe dir, the current
verdict line and the last lines of the failing tail, so a writer starts from evidence.

Usage: python3 _g1_batches.py <out-dir> [chunk=12] [--exclude ids.txt]
Prints the batch index (name, n, keys).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import CATALOG, WIN, latest_rows  # noqa: E402
from _g1_rootkey import key_for  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    chunk = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 12
    exclude: set[str] = set()
    if "--exclude" in sys.argv:
        exclude = set(Path(sys.argv[sys.argv.index("--exclude") + 1]).read_text().split())
    rows = latest_rows()
    units = {u["id"]: u for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]}
    fails = {u: r for u, r in rows.items() if not r.get("ok") and u not in exclude}
    by_key: dict[str, list[str]] = defaultdict(list)
    why: dict[str, str] = {}
    for u, r in sorted(fails.items()):
        k, w = key_for(u, r)
        by_key[k].append(u)
        why[u] = w
    shared = {k: v for k, v in by_key.items() if len(v) > 1 and not k.startswith(("PROBE:", "TIMEOUT"))}
    rest = sorted(u for k, v in by_key.items() if k not in shared for u in v)
    batches: list[tuple[str, list[str], list[str]]] = []
    # shared-file groups first (one writer per file), merged up to the chunk size
    cur: list[str] = []
    keys: list[str] = []
    for k, v in sorted(shared.items(), key=lambda kv: -len(kv[1])):
        if cur and len(cur) + len(v) > chunk:
            batches.append((f"s{len(batches):02d}", cur, keys))
            cur, keys = [], []
        cur += v
        keys.append(k)
    if cur:
        batches.append((f"s{len(batches):02d}", cur, keys))
    # the rest chunked by prefix so a writer stays in one area
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for u in rest:
        by_prefix[u.split("-")[0]].append(u)
    n = 0
    for pfx, us in sorted(by_prefix.items()):
        for i in range(0, len(us), chunk):
            batches.append((f"p{n:02d}-{pfx}", us[i : i + chunk], []))
            n += 1

    def tail_lines(r: dict, k: int = 7) -> list[str]:
        ls = [ln for ln in str(r.get("tail") or "").splitlines() if ln.strip()]
        return ls[-k:]

    index = []
    for name, us, ks in batches:
        lines = [f"# Batch {name}: {len(us)} units" + (f" — shared files: {', '.join(ks)}" if ks else ""), ""]
        for u in us:
            r = fails[u]
            cat = units.get(u, {})
            lines.append(f"## {u}  ({why.get(u, '')[:80]})")
            lines.append(f"- output_path: {cat.get('output_path')}")
            lines.append(f"- probes: command-center/p2-wave/probes/{u}/")
            lines.append(f"- verdict: {r.get('line', '')[:120]}")
            lines.append("- tail:")
            lines.extend(f"    {ln[:200]}" for ln in tail_lines(r))
            lines.append("")
        (out / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        index.append({"batch": name, "n": len(us), "units": us, "keys": ks})
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"fails={len(fails)} batches={len(batches)} shared-groups={len(shared)}")
    for b in index:
        print(f"  {b['batch']:10s} {b['n']:3d}  {' '.join(b['keys'])[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
