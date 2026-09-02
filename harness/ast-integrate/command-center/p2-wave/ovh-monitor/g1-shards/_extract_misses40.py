#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARD = WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt"
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]
SUBS = ("tree", "delta", "extracted", "extracted-delta")
IDS = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]
REMAINING = IDS[12:]
PAT = re.compile(
    r"No such file or directory: ['\"]([^'\"]+)['\"]"
    r"|can't open file ['\"]([^'\"]+)['\"]"
    r"|ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)


def harvest(rel: str) -> list[str]:
    hits: list[str] = []
    name = Path(rel).name
    for root in PULL:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in SUBS:
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    hits.append(str(cand.relative_to(WAVE)))
                alt = box / sub / name
                if alt.is_file() and alt.stat().st_size > 0:
                    hits.append(str(alt.relative_to(WAVE)))
    return hits


def rel_from_abs(p: str) -> str:
    p = p.replace("\\", "/")
    p = p.replace("/home/prekzursil/p2-g1/", "")
    for key in ("command-center/", "tools/", "docs/", "blueprints/", "plugin/", "marketplace/", "workflow_foundry/"):
        idx = p.find(key)
        if idx >= 0:
            return p[idx:]
    return p


def main() -> None:
    want = set(REMAINING)
    rows = []
    unique: dict[str, list[str]] = {}
    for ln in JSONL.open(encoding="utf-8"):
        rec = json.loads(ln)
        if rec.get("id") not in want:
            continue
        blob = (rec.get("line") or "") + "\n" + (rec.get("tail") or "")
        misses = []
        for m in PAT.finditer(blob):
            p = m.group(1) or m.group(2) or m.group(3) or ""
            p = rel_from_abs(p)
            misses.append(p)
            unique.setdefault(p, []).append(rec["id"])
        rows.append({"id": rec["id"], "cls": rec.get("cls"), "misses": misses, "line": rec.get("line"), "tail": (rec.get("tail") or "")[-700:]})
    print("UNITS", len(rows), "UNIQUE", len(unique))
    for path, uids in unique.items():
        win = REPO / path
        hits = harvest(path)
        print(json.dumps({
            "path": path,
            "win": win.is_file(),
            "size": win.stat().st_size if win.is_file() else 0,
            "n_harvest": len(hits),
            "harvest": hits[:2],
            "ids": uids,
        }))
    out = WAVE / "ovh-monitor" / "g1-shards" / "_misses40.json"
    out.write_text(json.dumps({"rows": rows, "unique": {k: v for k, v in unique.items()}}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
