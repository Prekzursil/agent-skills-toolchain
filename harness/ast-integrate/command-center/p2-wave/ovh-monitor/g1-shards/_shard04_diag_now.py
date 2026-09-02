#!/usr/bin/env python3
"""Diagnose current shard-04 IDs: catalog, probes, last jsonl tails."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
want = set(IDS)
found: dict[str, dict] = {}
jsonl_paths = [
    WAVE / "ovh-monitor" / "g1-local-full.jsonl",
    HERE / "class-other.measure.jsonl",
    HERE / "class-envelope.measure.jsonl",
    HERE / "_envelope_measure.jsonl",
]
for jp in jsonl_paths:
    if not jp.is_file():
        continue
    src = jp.name
    with jp.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            uid = rec.get("id")
            if uid not in want:
                continue
            found[uid] = {
                "src": src,
                "ok": rec.get("ok"),
                "rc": rec.get("rc"),
                "cls": rec.get("cls"),
                "line": rec.get("line") or rec.get("last"),
                "tail": rec.get("tail") or "",
            }

rows = []
print(f"ids={len(IDS)} jsonl_hits={len(found)}")
for uid in IDS:
    u = BY.get(uid) or {}
    pdir = WAVE / "probes" / uid
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    files = sorted(p.name for p in pdir.iterdir()) if pdir.is_dir() else []
    rec = found.get(uid) or {}
    tail = rec.get("tail") or ""
    failed_lines = []
    for ln in tail.splitlines():
        s = ln.strip()
        if re.search(
            r"FAILED:|Error:|Exception|ModuleNotFound|AttributeError|TypeError|"
            r"FileNotFound|ImportError|KeyError|Unresolvable|TIMEOUT|manifest-sha|"
            r"AssertionError",
            s,
        ):
            failed_lines.append(s[:240])
    probe_asserts = []
    for name in files:
        if not name.endswith(".py"):
            continue
        text = (pdir / name).read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"FAILED:[^\n\"']{0,160}", text):
            probe_asserts.append(f"{name}:{m.group(0)[:160]}")
    print(f"\n=== {uid} ok={rec.get('ok')} cls={rec.get('cls')} {str(rec.get('line'))[:90]}")
    print(f"    out={out_rel} files={files[:20]}")
    for ln in (failed_lines[-4:] or ["(no fail line)"]):
        print(f"    TAIL {ln}")
    for a in probe_asserts[:6]:
        print(f"    ASSERT {a}")
    rows.append(
        {
            "id": uid,
            "ok": rec.get("ok"),
            "cls": rec.get("cls"),
            "line": rec.get("line"),
            "src": rec.get("src"),
            "output_path": out_rel,
            "files": files,
            "failed_lines": failed_lines[-6:],
            "probe_asserts": probe_asserts[:12],
            "title": (u.get("title") or "")[:160],
        }
    )

outp = HERE / "_shard04_diag_now.json"
outp.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
print(f"\nwrote {outp}")
okn = sum(1 for r in rows if r.get("ok") is True)
print(f"prior_ok={okn} prior_fail={len(rows)-okn}")
