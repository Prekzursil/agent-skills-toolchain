#!/usr/bin/env python3
"""Static pre-verify of the 12 shard-5 wave-2 units without running probes.
For each: catalog entry, artifact parse, state field, sentinel-in-text,
probe dir contents, SUBAGENT-RETURN status/state, manifest row sha match."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
IDS = ["AUD-0080", "AUD-0082", "AUD-0084", "AUD-0095", "AUD-0096",
       "BLD-0001", "BLD-0002", "BLD-0004", "BLD-0005", "BLD-0010",
       "BLD-0013", "BLD-0014"]


def digest_file(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat.get("work_units", []) if isinstance(u, dict)}
    for uid in IDS:
        u = units.get(uid)
        print("=" * 10, uid)
        if u is None:
            print("  FAIL catalog-missing")
            continue
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        sent = str(u.get("completion_sentinel") or "")
        if not out.is_file() or out.stat().st_size <= 0:
            print("  FAIL artifact-missing", out_rel)
            continue
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
        except Exception as exc:
            print("  FAIL unparseable", type(exc).__name__)
            continue
        st = str(doc.get("state") or "").upper()
        sent_ok = (not sent) or (sent in text)
        live_sha, live_bytes = digest_file(out)
        reviewer = doc.get("reviewer") or {}
        closed = (str(reviewer.get("verdict") or "").upper() == "PASS"
                  and reviewer.get("independent") is True)
        print(f"  artifact: {out_rel} bytes={live_bytes} state={st} "
              f"sentinel_in_text={sent_ok} reviewer_closed={closed}")
        pdir = PROBES / uid
        ret = pdir / "SUBAGENT-RETURN.json"
        man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        p1 = sorted(pdir.glob("probe1*.py")) if pdir.is_dir() else []
        p2 = sorted(pdir.glob("probe2*.py")) if pdir.is_dir() else []
        print(f"  probes: dir={pdir.is_dir()} p1={[p.name for p in p1]} "
              f"p2={[p.name for p in p2]}")
        if ret.is_file():
            try:
                r = json.loads(ret.read_text(encoding="utf-8"))
                print(f"  return: status={r.get('status')} state={r.get('state')} "
                      f"named_probes={len(r.get('named_probes') or [])}")
            except Exception as exc:
                print("  return: UNPARSEABLE", type(exc).__name__)
        else:
            print("  return: MISSING")
        if man.is_file():
            try:
                m = json.loads(man.read_text(encoding="utf-8"))
                rows = [a for a in (m.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid]
                prim = [a for a in rows
                        if str(a.get("path") or "").replace("\\", "/") == out_rel]
                if prim:
                    a = prim[0]
                    match = (str(a.get("sha256") or "") == live_sha
                             and a.get("present") is True)
                    print(f"  manifest: rows={len(rows)} primary-sha-match={match}")
                else:
                    print(f"  manifest: rows={len(rows)} primary-row=ABSENT")
            except Exception as exc:
                print("  manifest: UNPARSEABLE", type(exc).__name__)
        else:
            print("  manifest: MISSING")
        verdict = ("STATIC-GREEN" if (st not in NOT_DELIVERING and sent_ok
                                      and pdir.is_dir() and ret.is_file()
                                      and man.is_file()) else "NEEDS-WORK")
        print(f"  pre-verify: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
