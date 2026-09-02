#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
dump = json.loads(Path(__file__).with_name("_shard02_dump.json").read_text(encoding="utf-8"))
lines = []
for r in dump:
    rel = r.get("output_path") or ""
    path = REPO / rel
    if not path.is_file():
        continue
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    legacy = ext.get("legacy_root") if isinstance(ext, dict) else None
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    keys = []
    if isinstance(legacy, dict):
        keys.append(f"legacy={sorted(legacy)[:20]}")
        lt = legacy.get("tests")
        keys.append(f"legacy.tests={type(lt).__name__}")
    else:
        keys.append(f"legacy={type(legacy).__name__}")
    if "tests" in report:
        keys.append(f"report.tests={type(report.get('tests')).__name__}")
    profile = doc.get("profile")
    produced = doc.get("produced_by")
    lines.append(f"{r['id']} profile={profile} produced_by={produced} {' '.join(keys)}")
dest = Path(__file__).with_name("_shard02_legacy.txt")
dest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("wrote", dest)
