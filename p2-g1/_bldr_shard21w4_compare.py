"""Compare p2-g1 artifacts vs upstream ast-integrate artifacts (byte-for-byte)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
UP = Path("C:/Users/Prekzursil/source/ast-integrate")
UNITS = [
    "WFA-0065", "WFA-0069", "WFA-0070", "WFA-0074",
    "WFA-0084", "WFA-085", "WFA-0086", "WFA-0094",
    "WFA-0106", "WFA-0107", "WFA-0110", "WFA-0113",
]


def main() -> int:
    cat = json.loads((P2 / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if u.get("id") in
               ("WFA-0065", "WFA-0069", "WFA-0070", "WFA-0074", "WFA-0084", "WFA-0085",
                "WFA-0086", "WFA-0094", "WFA-0106", "WFA-0107", "WFA-0110", "WFA-0113")}
    for uid in sorted(entries):
        rel = str(entries[uid]["output_path"]).replace("\\", "/")
        a, b = P2 / rel, UP / rel
        if not a.is_file() or not b.is_file():
            print(uid, "MISSING-SIDE", a.is_file(), b.is_file())
            continue
        same = a.read_bytes() == b.read_bytes()
        print(f"{uid}: identical={same} p2g1={a.stat().st_size} up={b.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
