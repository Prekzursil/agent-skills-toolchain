"""Shard21 wave4 builder: validate my 12 artifacts against catalog output_schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
from schema_resolver import validator_for  # noqa: E402

UNITS = [
    "WFA-0065", "WFA-0069", "WFA-0070", "WFA-0074",
    "WFA-0084", "WFA-0085", "WFA-0086", "WFA-0094",
    "WFA-0106", "WFA-0107", "WFA-0110", "WFA-0113",
]


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if u.get("id") in UNITS}
    total_bad = 0
    for uid in UNITS:
        e = entries[uid]
        out = str(e["output_path"]).replace("\\", "/")
        doc = json.loads((REPO / out).read_text(encoding="utf-8"))
        try:
            v = validator_for(e["output_schema"])
            errs = sorted(v.iter_errors(doc), key=lambda x: str(list(x.path)))
            print(uid, "errors:", len(errs))
            for err in errs[:3]:
                print("   ", list(err.path)[:4], err.message[:140])
            total_bad += len(errs)
        except Exception as ex:
            print(uid, "RESOLVER-FAIL:", type(ex).__name__, str(ex)[:160])
            total_bad += 1
    print("TOTAL-ERRORS:", total_bad)
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
