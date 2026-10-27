#!/usr/bin/env python3
"""w4s2 2026-10-26: program-wide census - how close is the estate P2 program
to full 2007 green?

STATIC predicate = _measure_one_delivered.py with the live-probe re-run
removed (artifact exists/non-empty/parses/not self-declared + sentinel present
+ SUBAGENT-RETURN not BLOCKED/FAILED + per-unit manifest sha256 row matches
the CRLF-normalized live artifact). Live probes are NOT re-run here for all
2007 units (heavy; per-unit probe re-runs are done by shard measures).
REVIEWER-CLOSED = receipt state=SUCCESS with reviewer.verdict=PASS and
independent=true (receipt_core's only green).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def digest_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = [u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")]
    n_deliv = n_notdeliv = 0
    n_receipt = n_closed = 0
    notdeliv_ids: list[str] = []
    closed_ids: list[str] = []
    for u in units:
        uid = u["id"]
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        ok = False
        if out_rel:
            out = REPO / out_rel
            doc = load(out) if out.is_file() and out.stat().st_size > 0 else None
            if isinstance(doc, dict):
                st = str(doc.get("state") or "").upper()
                sentinel = str(u.get("completion_sentinel") or "")
                text_ok = (not sentinel) or (sentinel in json.dumps(doc))
                if st not in NOT_DELIVERING and text_ok:
                    ret = load(PROBES / uid / "SUBAGENT-RETURN.json")
                    man = load(PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json")
                    if isinstance(ret, dict):
                        st_ret = str(ret.get("status") or ret.get("state") or "").upper()
                        if st_ret not in NOT_DELIVERING and isinstance(man, dict):
                            rows = [
                                a
                                for a in (man.get("artifacts") or [])
                                if isinstance(a, dict) and a.get("unit_id") == uid
                            ]
                            live = digest_file(out)
                            if any(
                                str(a.get("path") or "").replace("\\", "/") == out_rel
                                and str(a.get("sha256") or "") == live
                                and a.get("present") is True
                                for a in rows
                            ):
                                ok = True
        if ok:
            n_deliv += 1
        else:
            n_notdeliv += 1
            if len(notdeliv_ids) < 400:
                notdeliv_ids.append(uid)
        r = load(RECEIPTS / f"{uid}.json")
        if isinstance(r, dict):
            n_receipt += 1
            rev = r.get("reviewer") or {}
            if (
                str(r.get("state") or "").upper() == "SUCCESS"
                and str(rev.get("verdict") or "").upper() == "PASS"
                and rev.get("independent") is True
            ):
                n_closed += 1
                closed_ids.append(uid)
    total = len(units)
    print(f"units={total}")
    print(f"delivered_static={n_deliv} not_delivered={n_notdeliv}")
    print(f"receipts_present={n_receipt} reviewer_closed_green={n_closed}")
    print(f"pct_delivered={100.0 * n_deliv / total:.1f}%")
    print(f"pct_green={100.0 * n_closed / total:.1f}%")
    (REPO / "command-center/p2-wave/_w4s2_full2007_census_out.json").write_text(
        json.dumps(
            {
                "units": total,
                "delivered_static": n_deliv,
                "not_delivered": n_notdeliv,
                "receipts_present": n_receipt,
                "reviewer_closed_green": n_closed,
                "closed_ids": closed_ids,
                "not_delivered_ids_sample": notdeliv_ids,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("SUCCESS:w4s2-census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
