#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
IDS = [
    "ARC-0064",
    "AUD-0011",
    "BLD-0027",
    "CC-0001",
    "CC-0010",
    "CC-0012",
    "CC-0014",
    "CC-0022",
    "CNF-0018",
    "CNF-0136",
    "CNF-0139",
    "CNF-0141",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    by = {u["id"]: u for u in cat["work_units"]}
    for uid in IDS:
        u = by[uid]
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        manp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        retp = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
        live_sha, live_n = digest(out) if out.is_file() else ("MISSING", 0)
        man = json.loads(manp.read_text(encoding="utf-8")) if manp.is_file() else {}
        rows = [
            a
            for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == uid
        ]
        match = [
            a
            for a in rows
            if str(a.get("path") or "").replace("\\", "/") == out_rel
            and str(a.get("sha256") or "") == live_sha
            and a.get("present") is True
        ]
        ret = json.loads(retp.read_text(encoding="utf-8")) if retp.is_file() else {}
        text = out.read_text(encoding="utf-8") if out.is_file() else ""
        try:
            doc = json.loads(text) if text else {}
        except json.JSONDecodeError:
            doc = {}
        st = str(doc.get("state") or "")
        sent = str(u.get("completion_sentinel") or "")
        print(
            f"{uid} exists={out.is_file()} bytes={live_n} sha={live_sha[:16]} "
            f"man_rows={len(rows)} sha_match={bool(match)} "
            f"ret={ret.get('status') or ret.get('state')} art_state={st} "
            f"sentinel={bool(sent) and sent in text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
