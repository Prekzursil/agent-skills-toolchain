#!/usr/bin/env python3
"""Shard6 static audit: state of each unit vs the delivered contract."""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MINE = [
    "BLD-0016", "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028", "BLD-0031",
    "BLD-0032", "BLD-0033", "BLD-0035", "BLD-0037", "BLD-0040", "BLD-0042",
]


def digest(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    units = {
        u["id"]: u
        for u in (cat.get("work_units") or [])
        if isinstance(u, dict) and u.get("id")
    }
    only = sys.argv[1:] or MINE
    for uid in only:
        unit = units.get(uid)
        if unit is None:
            print(uid, "| MISSING-FROM-CATALOG")
            continue
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        parts = []
        if out.is_file() and out.stat().st_size > 0:
            try:
                text = out.read_text(encoding="utf-8")
                doc = json.loads(text)
                st = str(doc.get("state") or "").upper()
                sent = str(unit.get("completion_sentinel") or "")
                has_sent = bool(sent) and sent in text
                rev = doc.get("reviewer") or {}
                rev_v = rev.get("verdict") if isinstance(rev, dict) else None
                rev_i = rev.get("independent") if isinstance(rev, dict) else None
                parts.append(
                    f"artifact=OK state={st} sentinel={has_sent} reviewer={rev_v}/{rev_i}"
                )
            except Exception as exc:
                parts.append(f"artifact=UNPARSEABLE({type(exc).__name__})")
        else:
            parts.append("artifact=ABSENT" if not out.is_file() else "artifact=EMPTY")
        pd = REPO / "command-center/p2-wave/probes" / uid
        if pd.is_dir():
            ret_p = pd / "SUBAGENT-RETURN.json"
            man_p = pd / "UNIT-ARTIFACT-MANIFEST.json"
            if ret_p.is_file():
                try:
                    ret = json.loads(ret_p.read_text(encoding="utf-8"))
                    parts.append(
                        "return=OK status=" + str(ret.get("status") or ret.get("state"))
                    )
                except Exception:
                    parts.append("return=UNPARSEABLE")
            else:
                parts.append("return=ABSENT")
            if man_p.is_file():
                try:
                    man = json.loads(man_p.read_text(encoding="utf-8"))
                    rows = [
                        a
                        for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                    ]
                    if out.is_file():
                        live = digest(out)
                        match = [
                            a
                            for a in rows
                            if str(a.get("path") or "").replace("\\", "/") == out_rel
                            and str(a.get("sha256") or "") == live
                            and a.get("present") is True
                        ]
                        parts.append(
                            f"manifest=OK rows={len(rows)} sha-match={bool(match)}"
                            f" live_sha={live[:12]}"
                        )
                    else:
                        parts.append(f"manifest=OK rows={len(rows)} artifact-missing")
                except Exception:
                    parts.append("manifest=UNPARSEABLE")
            else:
                parts.append("manifest=ABSENT")
        else:
            parts.append("probes=NO-DIR")
        print(uid, "|", " | ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
