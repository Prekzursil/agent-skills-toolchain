"""Survey my 12 artifacts: structure + headline content digest."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = [
    "WFA-0065", "WFA-0069", "WFA-0070", "WFA-0074",
    "WFA-0084", "WFA-0085", "WFA-0086", "WFA-0094",
    "WFA-0106", "WFA-0107", "WFA-0110", "WFA-0113",
]


def digest(doc: dict, depth: int = 0, maxdepth: int = 2) -> None:
    if depth > maxdepth:
        return
    for k, v in doc.items():
        if isinstance(v, dict):
            print("  " * depth + f"{k}: dict({len(v)}) keys={list(v.keys())[:8]}")
            if depth < maxdepth:
                digest(v, depth + 1, maxdepth)
        elif isinstance(v, list):
            inner = ""
            if v and isinstance(v[0], dict):
                inner = f" item_keys={list(v[0].keys())[:10]}"
            print("  " * depth + f"{k}: list({len(v)}){inner}")
        else:
            s = str(v)
            print("  " * depth + f"{k}: {s[:110]}")


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if u.get("id") in UNITS}
    for uid in UNITS:
        e = entries[uid]
        out = str(e["output_path"]).replace("\\", "/")
        doc = json.loads((REPO / out).read_text(encoding="utf-8"))
        print("=" * 100)
        print(uid, out, "bytes:", (REPO / out).stat().st_size)
        # envelope status
        for f in ("schema_version", "unit_id", "state", "sentinel", "spec_anchor",
                  "min_bytes_threshold", "timestamps", "retry", "record_type"):
            if f not in doc:
                print("  ENVELOPE-MISSING:", f)
        print("  state:", doc.get("state"), "| sentinel:", str(doc.get("sentinel"))[:80])
        digest(doc, 1, 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
