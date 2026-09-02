#!/usr/bin/env python3
"""ON-BOX: pack catalog output_path files for /tmp/missing_ids.json only. No probes."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

ROOT = Path("/opt/p2/ast-integrate")
CAT = json.loads((ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
IDS = json.loads(Path("/tmp/missing_ids.json").read_text(encoding="utf-8"))
OUT = Path("/tmp/p2-missing-delta.tgz")


def main() -> None:
    by = {u["id"]: u for u in CAT.get("work_units") or [] if isinstance(u, dict) and u.get("id")}
    files = []
    for uid in IDS:
        rel = str((by.get(uid) or {}).get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        p = ROOT / rel
        if p.is_file() and p.stat().st_size > 0:
            files.append((p, rel))
    OUT.unlink(missing_ok=True)
    with tarfile.open(OUT, "w:gz") as tf:
        for p, rel in files:
            tf.add(p, arcname=rel)
    print(f"PACKED n={len(files)} bytes={OUT.stat().st_size}", flush=True)
    print("PACK-MISSING-OK", flush=True)


if __name__ == "__main__":
    main()
