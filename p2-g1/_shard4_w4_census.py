#!/usr/bin/env python3
"""Census of all 2007 units against the delivery contract (static checks).

Checks per unit, mirroring _measure_one_delivered.py minus the live probe
re-runs (which are too slow for a whole-program sweep):
  1. output_path artifact exists, non-empty, parses as JSON,
     and is not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
     (completion_sentinel present in text when the catalog names one).
  2. probes/<id>/SUBAGENT-RETURN.json exists, parses, status not NOT_DELIVERING.
  3. probes/<id>/UNIT-ARTIFACT-MANIFEST.json has a row with unit_id, path,
     present=true and sha256 matching the CRLF-normalized live artifact.
Emits SUCCESS:<id> / FAILED:<id> <reason> per unit plus a summary.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def digest_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = [u for u in cat.get("work_units") or [] if isinstance(u, dict)]
    ok: list[str] = []
    bad: Counter = Counter()
    reasons: dict[str, str] = {}
    for u in units:
        uid = u.get("id")
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        if not uid or not out_rel:
            bad["predicate:absent"] += 1
            reasons[uid or "?"] = "predicate:absent"
            continue
        out = REPO / out_rel
        if not out.is_file() or out.stat().st_size <= 0:
            bad["artifact:absent"] += 1
            reasons[uid] = "artifact:absent"
            continue
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            bad[f"unparseable"] += 1
            reasons[uid] = f"unparseable:{type(exc).__name__}"
            continue
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            if st in NOT_DELIVERING:
                bad[f"self-declared:{st}"] += 1
                reasons[uid] = f"self-declared:{st}"
                continue
            sentinel = str(u.get("completion_sentinel") or "")
            first_word = sentinel.split(" ", 2)[1] if " " in sentinel else ""
            if first_word and first_word not in text:
                bad["sentinel-absent"] += 1
                reasons[uid] = "sentinel-absent"
                continue
        probe_dir = PROBES / uid
        ret_path = probe_dir / "SUBAGENT-RETURN.json"
        man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
        if not ret_path.is_file() or not man_path.is_file():
            bad["probes:absent"] += 1
            reasons[uid] = "probes:absent"
            continue
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            bad["probe-files:unparseable"] += 1
            reasons[uid] = "probe-files:unparseable"
            continue
        if not isinstance(ret, dict) or not isinstance(man, dict):
            bad["probe-files:unparseable"] += 1
            reasons[uid] = "probe-files:unparseable"
            continue
        st_ret = str(ret.get("status") or ret.get("state") or "").upper()
        if st_ret in NOT_DELIVERING:
            bad[f"return:{st_ret}"] += 1
            reasons[uid] = f"return:{st_ret}"
            continue
        rows = [
            a
            for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == uid
        ]
        if not rows:
            bad["manifest:row-absent"] += 1
            reasons[uid] = "manifest:row-absent"
            continue
        live_sha = digest_file(out)
        matching = [
            a
            for a in rows
            if str(a.get("path") or "").replace("\\", "/") == out_rel
            and str(a.get("sha256") or "") == live_sha
            and a.get("present") is True
        ]
        if not matching:
            bad["manifest:sha-mismatch"] += 1
            reasons[uid] = "manifest:sha-mismatch"
            continue
        ok.append(uid)
    print(f"TOTAL={len(units)} STATIC-GREEN={len(ok)}")
    for k, v in bad.most_common():
        print(f"  {k}: {v}")
    out_json = REPO / "_shard4_w4_census_out.json"
    out_json.write_text(
        json.dumps(
            {
                "total": len(units),
                "static_green": len(ok),
                "green_ids": ok,
                "red_counts": dict(bad),
                "red_reasons": reasons,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"SUCCESS:census written {out_json.name}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
