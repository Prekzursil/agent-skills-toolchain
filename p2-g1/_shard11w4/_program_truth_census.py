#!/usr/bin/env python3
"""Program-wide truth census (static, no live probes) - settles 1223 vs 453.

Per catalog unit:
  closed        = receipt state SUCCESS + reviewer PASS + independent true
  schema_ok     = repo resolver errors == [] at the unit's declared output_schema
  delivered     = probes/<id>/SUBAGENT-RETURN.json ok + UNIT-ARTIFACT-MANIFEST
                  row for output_path with matching CRLF->LF sha256, present=True
Emits the full cross-tab plus per-axis green counts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    from schema_resolver import validate_artifact  # noqa: E402

    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = [u for u in (cat.get("work_units") or []) if isinstance(u, dict)]
    n = len(units)
    full = []          # closed AND schema_ok AND delivered
    closed_only = []   # closed but not delivered or not schema_ok
    counts = {"closed": 0, "schema_ok": 0, "delivered": 0}
    breakdown: dict[str, list] = {}
    for u in units:
        uid = u["id"]
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        doc = None
        if out is not None and out.is_file() and out.stat().st_size > 0:
            try:
                doc = json.loads(out.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                doc = None
        # closed
        closed = False
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            rv = doc.get("reviewer")
            if isinstance(rv, dict):
                closed = st == "SUCCESS" and rv.get("verdict") == "PASS" and rv.get("independent") is True
        # schema_ok
        schema_ok = False
        if isinstance(doc, dict):
            try:
                schema_ok = not validate_artifact(doc, str(u.get("output_schema") or ""))
            except Exception:  # noqa: BLE001
                schema_ok = False
        # delivered (static)
        delivered = False
        pdir = PROBES / uid
        ret_p, man_p = pdir / "SUBAGENT-RETURN.json", pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if out is not None and out.is_file() and ret_p.is_file() and man_p.is_file():
            try:
                ret = json.loads(ret_p.read_text(encoding="utf-8"))
                man = json.loads(man_p.read_text(encoding="utf-8"))
                st_ret = str(ret.get("status") or ret.get("state") or "").upper()
                rows = [a for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                        and str(a.get("path") or "").replace("\\", "/") == out_rel
                        and str(a.get("sha256") or "") == lf_sha(out)
                        and a.get("present") is True
                        and st_ret not in NOT_DELIVERING]
                delivered = bool(rows)
            except Exception:  # noqa: BLE001
                delivered = False
        counts["closed"] += closed
        counts["schema_ok"] += schema_ok
        counts["delivered"] += delivered
        if closed and schema_ok and delivered:
            full.append(uid)
        key = f"closed={int(closed)} schema={int(schema_ok)} delivered={int(delivered)}"
        breakdown.setdefault(key, []).append(uid)

    res = {
        "total": n,
        "axis_counts": counts,
        "full_green_all_three": len(full),
        "full_green_ids": full,
        "breakdown_sizes": {k: len(v) for k, v in sorted(breakdown.items())},
    }
    outp = REPO / "_reviewer_w4s11_program_truth_census.json"
    outp.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "full_green_ids"}, indent=1))
    print("SUCCESS:census written", outp.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
