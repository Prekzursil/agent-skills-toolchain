#!/usr/bin/env python3
"""Compare shard-18 probes/modules against delivery-pull / error-pull harvest."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-18.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
STUB = ("# g1-surface: generated", "# g1-mod: real-surface", "class _NS:")
PULLS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "error-pull",
    WAVE / "ovh-monitor" / "missing-pull",
]
DUMP = json.loads((HERE / "_shard18_dump.json").read_text(encoding="utf-8"))


def is_stub(text: str) -> bool:
    head = text[:2500]
    return any(m in head for m in STUB)


def harvest_probe_copies(uid: str, name: str) -> list[dict]:
    hits = []
    for root in PULLS:
        if not root.is_dir():
            continue
        for p in root.rglob(name):
            # keep this tight: only probe dirs for this uid
            if uid not in p.parts:
                continue
            if not p.is_file() or p.stat().st_size <= 0:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(p.relative_to(root.parent)).replace("\\", "/")
            hits.append(
                {
                    "path": rel,
                    "bytes": p.stat().st_size,
                    "stub": is_stub(text),
                }
            )
            if len(hits) >= 8:
                return hits
    return hits


def harvest_mod(rel: str) -> list[dict]:
    name = Path(rel).name
    hits = []
    for root in PULLS:
        if not root.is_dir():
            continue
        for p in root.rglob(name):
            if not p.is_file() or p.stat().st_size <= 0:
                continue
            # prefer same relative tail
            posix = p.as_posix()
            if not posix.endswith(rel.replace("\\", "/")) and name not in {
                "package_cache.py",
                "nested.py",
                "meta.py",
            }:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits.append(
                {
                    "path": str(p.relative_to(root.parent)).replace("\\", "/"),
                    "bytes": p.stat().st_size,
                    "stub": is_stub(text),
                }
            )
            if len(hits) >= 6:
                return hits
    return hits


def main() -> None:
    rows = []
    for rec in DUMP:
        uid = rec["id"]
        live = WAVE / "probes" / uid
        py = {}
        if live.is_dir():
            for p in live.glob("*.py"):
                text = p.read_text(encoding="utf-8", errors="replace")
                py[p.name] = {"bytes": p.stat().st_size, "stub": is_stub(text)}
        mods = {}
        for mod, info in (rec.get("modules") or {}).items():
            hits = info.get("hits") or []
            live_hits = []
            for h in hits:
                live_hits.append(h)
            mods[mod] = {"live": live_hits}
        rows.append({"id": uid, "py": py, "mods": mods, "imports": rec.get("imports")})
    dest = HERE / "_shard18_harvest.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest, "n", len(rows))
    stubs = []
    for rec in DUMP:
        for mod, info in (rec.get("modules") or {}).items():
            for h in info.get("hits") or []:
                if h.get("stub"):
                    stubs.append((rec["id"], mod, h["path"], h["bytes"]))
    print("stub_hits", len(stubs))
    for row in stubs[:80]:
        print("STUB", *row)


if __name__ == "__main__":
    main()
