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
][:12]
PAT = re.compile(
    r"No such file or directory: ['\"]([^'\"]+)['\"]"
    r"|can't open file ['\"]([^'\"]+)['\"]"
    r"|ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]


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
    found: dict[str, dict] = {}
    with (WAVE / "ovh-monitor" / "g1-local-full.jsonl").open(encoding="utf-8") as f:
        for ln in f:
            rec = json.loads(ln)
            if rec.get("id") in want:
                found[rec["id"]] = rec
    rows = []
    for uid in IDS:
        rec = found.get(uid) or {}
        blob = (rec.get("line") or "") + "\n" + (rec.get("tail") or "")
        misses: list[str] = []
        for m in PAT.finditer(blob):
            p = (m.group(1) or m.group(2) or m.group(3) or "").replace("\\", "/")
            p = p.replace("/home/prekzursil/p2-g1/", "")
            if p.startswith("/"):
                for key in ("command-center/", "tools/", "docs/", "blueprints/", "platform/"):
                    idx = p.find(key)
                    if idx >= 0:
                        p = p[idx:]
                        break
            misses.append(p)
        ret_path = WAVE / "probes" / uid / "SUBAGENT-RETURN.json"
        named = []
        if ret_path.is_file():
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
            for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
                if isinstance(item, dict):
                    named.append(item.get("command"))
        miss_info = []
        for m in misses:
            win = REPO / m
            miss_info.append(
                {
                    "path": m,
                    "win": win.is_file(),
                    "size": win.stat().st_size if win.is_file() else 0,
                    "harvest": harvest(m)[:4],
                }
            )
        pdir = WAVE / "probes" / uid
        probes = sorted(p.name for p in pdir.glob("probe*.py")) if pdir.is_dir() else []
        row = {
            "id": uid,
            "cls": rec.get("cls"),
            "ok": rec.get("ok"),
            "misses": miss_info,
            "named": named,
            "probes": probes,
            "tail_last": (rec.get("tail") or "")[-800:],
        }
        rows.append(row)
        print("=" * 70)
        print(json.dumps({k: row[k] for k in ("id", "cls", "ok", "misses", "named", "probes")}, indent=2))
        print("TAIL:")
        print(row["tail_last"])
    out = WAVE / "ovh-monitor" / "g1-shards" / "_first12_diag.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("WROTE", out)


if __name__ == "__main__":
    main()
