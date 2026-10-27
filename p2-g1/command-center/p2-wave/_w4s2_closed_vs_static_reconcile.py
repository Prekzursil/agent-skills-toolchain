#!/usr/bin/env python3
"""w4s2 2026-10-26: reconcile reviewer-closed green vs static-delivered.
Classifies, for every receipt closed green (state=SUCCESS, reviewer.verdict=PASS,
independent=true), why it fails the _measure_one_delivered static predicate
(live probes excluded). Instrument disagreement must be explained, not picked."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
NOTD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")}
    closed = []
    for rp in (REPO / "command-center" / "receipts").glob("*.json"):
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
            uid = r.get("unit_id")
            if uid in units:
                closed.append(uid)
    reasons: dict[str, int] = {}
    examples: dict[str, list] = {}
    verified = 0
    for uid in closed:
        u = units[uid]
        out_rel = str(u.get("output_path") or "")
        out = REPO / out_rel
        reason = None
        if not out.is_file() or out.stat().st_size == 0:
            reason = "artifact-absent"
        else:
            doc = load(out)
            if doc is None:
                reason = "unparseable"
            elif isinstance(doc, dict) and str(doc.get("state") or "").upper() in NOTD:
                reason = "self-declared-blocked"
            else:
                ret = load(REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json")
                man = load(REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json")
                if ret is None:
                    reason = "no-subagent-return"
                elif man is None:
                    reason = "no-per-unit-manifest"
                else:
                    rows = [
                        a
                        for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                    ]
                    live = sha(out)
                    want = out_rel.replace("\\", "/")
                    if not any(
                        str(a.get("path") or "").replace("\\", "/") == want
                        and str(a.get("sha256") or "") == live
                        for a in rows
                    ):
                        reason = "manifest-sha-mismatch"
        if reason is None:
            verified += 1
        else:
            reasons[reason] = reasons.get(reason, 0) + 1
            examples.setdefault(reason, []).append(uid)
    print(f"closed={len(closed)} verified_static={verified}")
    for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"{k}: {v}  e.g. {examples[k][:8]}")
    (REPO / "command-center/p2-wave/_w4s2_closed_vs_static.json").write_text(
        json.dumps(
            {
                "closed": len(closed),
                "verified_static": verified,
                "reasons": reasons,
                "examples": {k: v[:60] for k, v in examples.items()},
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("SUCCESS:w4s2-reconcile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
