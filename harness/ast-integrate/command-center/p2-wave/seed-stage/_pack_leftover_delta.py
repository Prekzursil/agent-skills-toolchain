#!/usr/bin/env python3
"""ON-BOX: pack leftover remaining_ids output_path + probe dirs only."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

ROOT = Path("/opt/p2/ast-integrate")
LEFT = ROOT / "command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"
CAT = ROOT / "command-center/WORK-UNIT-CATALOG.json"
OUT = Path("/tmp/p2-leftover-delta.tgz")
DONE = Path("/opt/p2/completed.json")


def main() -> None:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    left = json.loads(LEFT.read_text(encoding="utf-8"))
    ids = [i for i in (left.get("remaining_ids") or []) if isinstance(i, str)]
    by = {u["id"]: u for u in cat.get("work_units") or [] if isinstance(u, dict) and u.get("id")}
    members: list[Path] = []
    if DONE.is_file():
        members.append(DONE)
    for uid in ids:
        unit = by.get(uid) or {}
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if rel:
            p = ROOT / rel
            if p.is_file() and p.stat().st_size > 0:
                members.append(p)
        probe = ROOT / "command-center/p2-wave/probes" / uid
        if probe.is_dir():
            members.extend(f for f in probe.rglob("*") if f.is_file())
    seen: set[str] = set()
    OUT.unlink(missing_ok=True)
    n = 0
    with tarfile.open(OUT, "w:gz") as tf:
        for p in members:
            if p == DONE:
                arc = "completed.json"
            else:
                try:
                    arc = p.relative_to(ROOT).as_posix()
                except ValueError:
                    continue
            if arc in seen:
                continue
            seen.add(arc)
            tf.add(p, arcname=arc)
            n += 1
    print(f"PACKED files={n} bytes={OUT.stat().st_size}", flush=True)
    print("PACK-DELTA-OK", flush=True)


if __name__ == "__main__":
    main()
