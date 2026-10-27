#!/usr/bin/env python3
"""w4s2 2026-10-26: full-green intersection - delivered (canonical
ready_units.artifact_delivered) AND reviewer-closed (receipt state=SUCCESS,
reviewer.verdict=PASS, independent=true)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    spec = importlib.util.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
    ru = importlib.util.module_from_spec(spec)
    sys.modules["ru"] = ru
    try:
        spec.loader.exec_module(ru)
    except SystemExit:
        pass
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = [u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")]
    delivered = set()
    for u in units:
        try:
            ok, _why = ru.artifact_delivered(u, None)
        except Exception:
            ok = False
        if ok:
            delivered.add(u["id"])
    closed = set()
    n_receipts = 0
    for rp in (REPO / "command-center/receipts").glob("*.json"):
        if rp.name.endswith(".bak.json"):
            continue
        r = load(rp)
        if not isinstance(r, dict):
            continue
        n_receipts += 1
        rev = r.get("reviewer") or {}
        if (
            str(r.get("state") or "").upper() == "SUCCESS"
            and str(rev.get("verdict") or "").upper() == "PASS"
            and rev.get("independent") is True
        ):
            if r.get("unit_id") in delivered:
                closed.add(r.get("unit_id"))
    total = len(units)
    print(f"units={total}")
    print(f"delivered_canonical={len(delivered)} ({100.0 * len(delivered) / total:.1f}%)")
    print(f"receipts_present={n_receipts}")
    print(f"reviewer_closed_green={sum(1 for _ in load_closed_only(REPO))}")
    print(f"FULL_GREEN_delivered_and_closed={len(closed)} ({100.0 * len(closed) / total:.1f}%)")
    out = {
        "units": total,
        "delivered_canonical": len(delivered),
        "full_green_delivered_and_closed": len(closed),
    }
    (REPO / "command-center/p2-wave/_w4s2_full_green_intersection_out.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8"
    )
    print("SUCCESS:w4s2-intersection")
    return 0


def load_closed_only(REPO: Path):
    """second pass kept separate so the printed closed count matches the earlier
    reconcile instrument (1103) rather than the delivered-intersected one."""
    for rp in (REPO / "command-center/receipts").glob("*.json"):
        if rp.name.endswith(".bak.json"):
            continue
        r = load(rp)
        if not isinstance(r, dict):
            continue
        rev = r.get("reviewer") or {}
        if (
            str(r.get("state") or "").upper() == "SUCCESS"
            and str(rev.get("verdict") or "").upper() == "PASS"
            and rev.get("independent") is True
        ):
            yield r.get("unit_id")


if __name__ == "__main__":
    raise SystemExit(main())
