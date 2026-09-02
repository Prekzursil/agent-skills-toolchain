#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
REPO = WAVE.parents[1]
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
][12:]


def main() -> None:
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        print("=" * 70)
        print(uid)
        ret = json.loads((pdir / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
        for item in ret.get("named_probes") or []:
            print("CMD", item.get("command"))
        for p in sorted(pdir.glob("probe*.py")):
            if p.name in {"probe1.py", "probe2.py"}:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            print(f"--- {p.name} {len(text)} bytes ---")
            lines = text.splitlines()
            for i, ln in enumerate(lines[:80], 1):
                print(f"{i:3}|{ln}")
            if len(lines) > 80:
                print(f"... {len(lines)-80} more lines")


if __name__ == "__main__":
    main()
