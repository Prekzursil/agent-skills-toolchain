#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAVE = HERE.parents[1]
reasons = json.loads((HERE / "_shard11_reasons.json").read_text(encoding="utf-8"))
FAIL_RE = re.compile(r"return fail\(|print\(f?\"FAILED:|_fail\(|raise AssertionError")


def main() -> None:
    for f in reasons["fails"]:
        uid = f["id"]
        pdir = WAVE / "probes" / uid
        print("=" * 72)
        print(uid, f["cls"])
        print("TAIL:", f["tail8"][-400:].replace("\n", " | "))
        if not pdir.is_dir():
            continue
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            print(f"-- {p.name} {len(lines)}L --")
            # print imports
            for ln in lines[:40]:
                if ln.startswith("from ") or ln.startswith("import "):
                    print("  IMP", ln)
            # print fail strings
            for i, ln in enumerate(lines, 1):
                if "FAILED:" in ln or "return fail(" in ln or "return _fail(" in ln:
                    print(f"  {i:3}|{ln[:180]}")


if __name__ == "__main__":
    main()
