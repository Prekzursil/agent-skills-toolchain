#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]
PAT = re.compile(
    r"No such file or directory: ['\"]([^'\"]+)['\"]"
    r"|can't open file ['\"]([^'\"]+)['\"]"
)


def harvest(rel: str) -> list[str]:
    hits: list[str] = []
    for root in PULL:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta", "extracted", "extracted-delta"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    hits.append(str(cand.relative_to(WAVE)))
    return hits


def main() -> None:
    want = set(IDS)
    rows = []
    for ln in JSONL.open(encoding="utf-8"):
        rec = json.loads(ln)
        if rec.get("id") not in want:
            continue
        blob = (rec.get("line") or "") + "\n" + (rec.get("tail") or "")
        misses = []
        for m in PAT.finditer(blob):
            p = (m.group(1) or m.group(2) or "").replace("\\", "/")
            p = p.replace("/home/prekzursil/p2-g1/", "")
            if p.startswith("/"):
                # leftover abs
                idx = p.find("command-center/")
                if idx < 0:
                    idx = p.find("tools/")
                if idx < 0:
                    idx = p.find("docs/")
                if idx < 0:
                    idx = p.find("blueprints/")
                if idx >= 0:
                    p = p[idx:]
            misses.append(p)
        rows.append(
            {
                "id": rec["id"],
                "cls": rec.get("cls"),
                "misses": misses,
                "tail": (rec.get("tail") or "")[-400:],
            }
        )
    print("UNITS", len(rows))
    unique: dict[str, list[str]] = {}
    for rec in rows:
        print("====", rec["id"], rec["misses"] or ["NO-PATH"])
        if not rec["misses"]:
            print(rec["tail"][:400])
        for m in rec["misses"]:
            unique.setdefault(m, []).append(rec["id"])
    print("UNIQUE", len(unique))
    for path, uids in unique.items():
        win = REPO / path
        hits = harvest(path)
        print(
            json.dumps(
                {
                    "path": path,
                    "win": win.is_file(),
                    "size": win.stat().st_size if win.is_file() else 0,
                    "harvest": hits[:3],
                    "n_harvest": len(hits),
                    "ids": uids,
                }
            )
        )


if __name__ == "__main__":
    main()
