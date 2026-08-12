r"""Tier-3 measurement: does adding CONTRACT VALIDATION to delivered() change anything,
and what does it cost? Goodhart guard -- a `state` field alone can be forged; validating
against the unit's declared output_schema cannot be satisfied by a one-word edit.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    sr = load_resolver()
    units = json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]
    existing = [
        u for u in units if u.get("output_path") and (REPO / u["output_path"]).exists()
    ]
    print(f"existing artifacts: {len(existing)}")
    t0 = time.time()
    rows = []
    for u in existing:
        p = REPO / u["output_path"]
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            rows.append((u["id"], "UNPARSEABLE", type(e).__name__))
            continue
        st = doc.get("state") if isinstance(doc, dict) else None
        sch = u.get("output_schema")
        try:
            errs = sr.validate_artifact(doc, sch)
            v = "VALID" if not errs else f"INVALID({len(errs)})"
        except Exception as e:
            v = f"RESOLVE-ERR:{type(e).__name__}"
        rows.append((u["id"], st, v))
    dt = time.time() - t0
    print(f"validated {len(existing)} artifacts in {dt:.2f}s")
    from collections import Counter

    print("state x validity:", dict(Counter((r[1], r[2]) for r in rows)))
    n_state_ok = sum(1 for r in rows if r[1] not in NOT_DELIVERING)
    n_both = sum(1 for r in rows if r[1] not in NOT_DELIVERING and r[2] == "VALID")
    print(
        f"state-delivering: {n_state_ok} | state-delivering AND schema-VALID: {n_both}"
    )
    print(
        "rows where state is delivering:",
        [r for r in rows if r[1] not in NOT_DELIVERING],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
