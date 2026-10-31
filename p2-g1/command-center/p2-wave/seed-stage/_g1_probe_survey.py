#!/usr/bin/env python3
"""Survey probe dirs for unit IDs: files, project imports, and the latest fail tail.

Usage: python3 _g1_probe_survey.py ID [ID ...]   (reads the WSL mirror ~/p2-g1)
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
PROBES = ROOT / "command-center" / "p2-wave" / "probes"
MON = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor")
CATALOG = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CATALOG["work_units"]}

latest = {}
for src in [MON / "g1-local-full.jsonl", MON / "g1-fails-rerun.jsonl",
            *sorted((MON / "repair-claude").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)]:
    if src.is_file():
        for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("id"):
                latest[rec["id"]] = rec

IMP_RE = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import\s+([^\n]+)|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))", re.M)
STD = set(sys.stdlib_module_names) | {"jsonschema", "yaml", "typing_extensions"}

for uid in sys.argv[1:]:
    d = PROBES / uid
    unit = UNITS.get(uid, {})
    print(f"===== {uid}  output_path={unit.get('output_path')}  title={str(unit.get('title') or unit.get('name') or '')[:80]}")
    if not d.is_dir():
        print("  (no probe dir)")
        continue
    files = sorted(p.name for p in d.iterdir())
    print("  files:", " ".join(files)[:400])
    imps = set()
    for p in d.glob("*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in IMP_RE.finditer(txt):
            mod = m.group(1) or m.group(3)
            if not mod:
                continue
            top = mod.split(".")[0]
            if top in STD:
                continue
            names = (m.group(2) or "").strip()[:120]
            imps.add(f"{mod}" + (f" -> {names}" if names else ""))
    for i in sorted(imps):
        print("  import:", i)
    rec = latest.get(uid)
    if rec:
        print(f"  ok={rec.get('ok')} line={str(rec.get('line'))[:200]}")
        tail = str(rec.get("tail") or "")
        for ln in tail.splitlines()[-14:]:
            print("   |", ln[:220])
