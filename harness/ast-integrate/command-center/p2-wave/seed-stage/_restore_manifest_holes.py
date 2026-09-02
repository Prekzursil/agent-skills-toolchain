#!/usr/bin/env python3
"""Restore missing receipt-named files from harvest extract or same-dir live siblings.

Does not invent empty files. Copies bytes only when a source exists.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CC = REPO / "command-center"
WAVE = CC / "p2-wave"
EXTRACT = WAVE / "ovh-monitor" / "error-pull" / "extracted"
DELTA = WAVE / "ovh-monitor" / "error-pull" / "extracted-delta"
DIRS = ("receipts", "adversarial", "audit")


def is_receipt(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    uid = value.get("unit_id")
    arts = value.get("artifacts")
    return isinstance(uid, str) and bool(uid.strip()) and isinstance(arts, list) and bool(arts)


def find_source(rel: str) -> Path | None:
    target = REPO / rel
    if target.is_file():
        return target
    name = Path(rel).name
    parent = Path(rel).parent.as_posix()
    for root in (EXTRACT, DELTA):
        hits = list(root.glob(f"*/{rel}")) + list(root.glob(f"*/{Path(rel).as_posix()}"))
        if not hits:
            hits = list(root.glob(f"*/probes/*/{name}")) if "probes/" in rel else []
        for h in hits:
            if h.is_file() and h.stat().st_size > 0:
                return h
    live_dir = REPO / parent
    if live_dir.is_dir():
        stem = Path(name).stem
        for p in live_dir.iterdir():
            if not p.is_file() or p.stat().st_size <= 0:
                continue
            if p.name == name:
                return p
            # dated suffix drift: probe2-classified-2026-08-16.json vs probe2-classified.json
            if stem.startswith(p.stem) or p.stem.startswith(stem.split("-20")[0]):
                if p.suffix == Path(name).suffix:
                    return p
    return None


def main() -> None:
    copied = skipped = still = 0
    still_list = []
    for dirname in DIRS:
        base = CC / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            if any(part.startswith("_") for part in path.relative_to(CC).parts):
                continue
            if path.name in {"ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"}:
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not is_receipt(value):
                continue
            for art in value["artifacts"]:
                if not isinstance(art, dict) or not isinstance(art.get("path"), str):
                    continue
                rel = art["path"].replace("\\", "/")
                dest = REPO / rel
                if dest.is_file():
                    continue
                src = find_source(rel)
                if src is None or src.resolve() == dest.resolve():
                    still += 1
                    if len(still_list) < 30:
                        still_list.append(rel)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied += 1
    print(f"copied={copied} still_missing={still}")
    for rel in still_list:
        print("STILL", rel)


if __name__ == "__main__":
    main()
