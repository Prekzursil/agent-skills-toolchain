#!/usr/bin/env python3
"""Static (no-probe-run) pre-check of shard3-w4 units against the G-1 delivery contract."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
CAT = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
IDS = [
    "AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057", "AUD-0064",
    "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072", "AUD-0075", "AUD-0080",
]


def digest(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def norm(rel: str) -> str:
    return str(rel or "").replace("\\", "/")


def main() -> int:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    idx = {u["id"]: u for u in cat["work_units"]}
    green, red = [], []
    for uid in IDS:
        u = idx[uid]
        out_rel = norm(u["output_path"])
        out = REPO / out_rel
        problems = []
        if not out.is_file() or out.stat().st_size <= 0:
            problems.append("ARTIFACT-ABSENT")
        else:
            try:
                text = out.read_text(encoding="utf-8")
                doc = json.loads(text)
                if isinstance(doc, dict):
                    st = str(doc.get("state") or "").upper()
                    if st in NOT_DELIVERING:
                        problems.append(f"self-decl:{st}")
                sent = str(u.get("completion_sentinel") or "")
                if sent and sent not in text:
                    problems.append("sentinel-absent")
            except Exception as exc:
                problems.append(f"unparseable:{type(exc).__name__}")
        pd = REPO / "command-center" / "p2-wave" / "probes" / uid
        ret_p, man_p = pd / "SUBAGENT-RETURN.json", pd / "UNIT-ARTIFACT-MANIFEST.json"
        ret, man = None, None
        if not ret_p.is_file():
            problems.append("RETURN-absent")
        else:
            ret = json.loads(ret_p.read_text(encoding="utf-8"))
            st_ret = str(ret.get("status") or ret.get("state") or "").upper()
            if st_ret in NOT_DELIVERING:
                problems.append(f"return:{st_ret}")
        if not man_p.is_file():
            problems.append("MANIFEST-absent")
        else:
            man = json.loads(man_p.read_text(encoding="utf-8"))
        sha = digest(out) if out.is_file() else None
        row_ok = False
        n_rows = 0
        if man and sha:
            rows = [
                a
                for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid
            ]
            n_rows = len(rows)
            for a in rows:
                if (
                    norm(a.get("path")) == out_rel
                    and str(a.get("sha256") or "") == sha
                    and a.get("present") is True
                ):
                    row_ok = True
            if not row_ok:
                problems.append("manifest-row-absent" if not rows else "MANIFEST-SHA-MISMATCH")
        status_ret = str((ret or {}).get("status") or (ret or {}).get("state") or "?")
        verdict = "GREEN" if not problems else "RED"
        (green if not problems else red).append(uid)
        print(
            f"{uid}: static={verdict} return={status_ret} "
            f"artifact={'yes' if out.is_file() else 'NO'} shaMatch={'yes' if row_ok else 'no'} "
            f"rows={n_rows} {'; '.join(problems)}"
        )
    print(f"GREEN={len(green)} {green}")
    print(f"RED={len(red)} {red}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
